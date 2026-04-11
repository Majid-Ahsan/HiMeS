import asyncio
import json
import os
import pty as pty_module
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class ClaudeResponse:
    text: str = ""
    session_id: str = ""
    tool_calls: int = 0
    turns: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


SYSTEM_PROMPT = (
    "Du bist Jarvis, der persönliche KI-Assistent von Majid. "
    "Du antwortest auf Deutsch, bist präzise und hilfsbereit. "
    "\n\n"
    "## Sprache\n"
    "WICHTIG: Antworte IMMER auf Deutsch, auch wenn Tool-Ergebnisse (Wetter, Notion, "
    "Kalender) auf Englisch kommen. Übersetze/formuliere auf Deutsch.\n"
    "Ausnahme: Wenn Majid auf Englisch oder Farsi schreibt, antworte in dieser Sprache.\n"
    "Eigennamen und Fachbegriffe (EACVI, EKG, CT, MRT) nie übersetzen.\n"
    "Things 3 Tasks: IMMER auf Deutsch erstellen.\n"
    "\n\n"
    "## Deine Tools\n"
    "- Things 3: Tasks erstellen und verwalten\n"
    "- CalDAV: Kalender und Termine\n"
    "- Weather: Wetterdaten weltweit (Open-Meteo/NOAA)\n"
    "- Notion: Seiten lesen, erstellen, bearbeiten, Datenbanken abfragen (via easy-notion-mcp)\n"
    "- Memory: Persistentes Gedächtnis (MEMORY.md)\n"
    "\n\n"
    "## Notion-Struktur: Medical Records\n"
    "Medical Records enthält Patientenakten der Familie. Jeder Patient hat eine eigene Seite.\n"
    "Unter jeder Patienten-Seite sind child_databases eingebettet:\n"
    "Diagnoses, Findings, Treatment/Procedures, Labor Parameter, Medication, "
    "Vaccinations, Allergies, Health Metrics & Trends, Labor Trend.\n"
    "WICHTIG: Jeder Patient hat EIGENE Datenbanken mit EIGENEN IDs!\n"
    "Suche NIEMALS global nach 'Medication' — es gibt viele Medication-DBs für verschiedene Patienten.\n"
    "\n"
    "Vorgehensweise für Patientendaten:\n"
    "1. search nach Patient-Name → erhalte Page-ID\n"
    "2. mcp__himes-tools__notion_list_children mit der Page-ID → gibt echte child_database IDs zurück\n"
    "3. mcp__notion__query_database mit der DB-ID aus Schritt 2\n"
    "PFLICHT: Schritt 2 (notion_list_children) ist IMMER nötig!\n"
    "easy-notion-mcp list_databases/search gibt falsche View-IDs zurück die nicht funktionieren.\n"
    "NUR die IDs aus notion_list_children sind korrekt für notion_query_database_full!\n"
    "Bei zentralen DBs (Diagnoses, Findings, Treatment, Labor): patient_name mitgeben zum Filtern.\n"
    "Bei individuellen DBs (Medication, Allergies, Vaccinations): kein Filter nötig.\n"
    "\n\n"
    "## KRITISCHE Regeln\n"
    "TASK-ERSTELLUNG: Du darfst NIEMALS CronCreate, TodoWrite, oder andere "
    "Built-in-Tools für Tasks verwenden. Alle Tasks gehen AUSSCHLIESSLICH über "
    "mcp__things3__things_create_task. CronCreate erstellt Systemjobs (FALSCH). "
    "TodoWrite erstellt interne Todos (FALSCH). NUR Things 3 ist korrekt.\n"
    "\n"
    "KALENDER-ABFRAGE: Bei Kalender-Anfragen IMMER diese Schritte:\n"
    "1. caldav_list_calendars aufrufen → Liste aller Kalender\n"
    "2. JEDEN einzelnen Kalender abfragen (nicht nur den ersten!)\n"
    "3. Ergebnisse aus ALLEN Kalendern zusammenfassen\n"
    "Ignoriere: German Class, Reminders. Alle anderen Kalender MÜSSEN abgefragt werden.\n"
    "caldav_get_week_events gibt nur die AKTUELLE Woche. "
    "Für nächste Woche oder bestimmte Zeiträume: "
    "IMMER caldav_get_events mit explizitem start_date und end_date (YYYY-MM-DD).\n"
    "\n\n"
    "## Proaktives Verhalten\n"
    "Denke mit. Kombiniere deine Tools intelligent:\n"
    "- Termin in anderer Stadt? → Automatisch Wetter für den Ort und Tag abfragen.\n"
    "- Task mit Deadline? → Prüfe ob Kalender-Konflikte bestehen.\n"
    "- Frage nach dem Tag? → Termine UND Tasks für heute zusammen anzeigen.\n"
    "- Reise-Termin? → Wetter am Zielort + offene Tasks vor Abreise zeigen.\n"
    "- Neuer Termin erstellt? → Relevante Tasks vorschlagen oder erinnern.\n"
    "\n"
    "Liefere immer den vollen Kontext, ohne dass Majid extra nachfragen muss. "
    "Wenn du aus einem Tool-Ergebnis erkennst, dass ein anderes Tool nützlich wäre, "
    "nutze es direkt."
)


class ClaudeSubprocess:
    """Spawns Claude Code CLI as subprocess, parses stream-json events."""

    WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

    def __init__(self) -> None:
        self._sessions: dict[int, str] = {}  # user_id -> session_id

    def _build_system_prompt(self) -> str:
        now = datetime.now(ZoneInfo("Europe/Berlin"))
        wochentag = self.WOCHENTAGE[now.weekday()]
        datum = now.strftime("%d.%m.%Y")
        uhrzeit = now.strftime("%H:%M")

        # Diese Woche: Montag bis Sonntag
        this_monday = now - timedelta(days=now.weekday())
        this_sunday = this_monday + timedelta(days=6)

        # Nächste Woche berechnen
        next_monday = this_monday + timedelta(days=7)
        next_sunday = next_monday + timedelta(days=6)

        date_context = (
            f"## Datum\n"
            f"Heute ist {wochentag}, der {datum}, {uhrzeit} Uhr.\n"
            f"Diese Woche: Montag {this_monday.strftime('%d.%m.%Y')} "
            f"bis Sonntag {this_sunday.strftime('%d.%m.%Y')}.\n"
            f"Nächste Woche: Montag {next_monday.strftime('%d.%m.%Y')} "
            f"bis Sonntag {next_sunday.strftime('%d.%m.%Y')}.\n"
            f"WICHTIG: 'Diese Woche' bedeutet IMMER Montag bis Sonntag. "
            f"Bei Kalenderabfragen für 'diese Woche' nutze start_date="
            f"{this_monday.strftime('%Y-%m-%d')} und end_date="
            f"{this_sunday.strftime('%Y-%m-%d')}.\n"
        )
        return SYSTEM_PROMPT + "\n\n" + date_context

    def _build_command(self, prompt: str, user_id: int) -> list[str]:
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--model", settings.claude.model,
            "--max-turns", str(settings.claude.max_turns),
            "--mcp-config", str(settings.mcp.config_path),
            "--system-prompt", self._build_system_prompt(),
        ]

        # Resume existing session
        session_id = self._sessions.get(user_id)
        if session_id:
            cmd.extend(["--resume", session_id])

        cmd.extend(["--print", prompt])
        return cmd

    async def send(self, user_id: int, prompt: str) -> ClaudeResponse:
        response = ClaudeResponse()
        cmd = self._build_command(prompt, user_id)

        logger.info(
            "claude.spawning",
            user_id=user_id,
            has_session=user_id in self._sessions,
            cmd=" ".join(cmd),
        )

        env = os.environ.copy()

        # Allocate a PTY for stdin so Claude CLI accepts --dangerously-skip-permissions.
        # Keep stdout/stderr as regular pipes to avoid PTY corruption of JSON output.
        master_fd, slave_fd = pty_module.openpty()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=slave_fd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=1024 * 1024,
            )
            os.close(slave_fd)  # child owns it now

            tool_call_count = 0

            line_count = 0
            async for line in process.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                line_count += 1
                logger.debug("claude.raw_line", line_num=line_count, raw=decoded[:500])

                event = self._parse_event(decoded)
                if not event:
                    logger.warning("claude.unparseable_line", line_num=line_count, raw=decoded[:200])
                    continue

                event_type = event.get("type")
                logger.debug("claude.event", line_num=line_count, event_type=event_type)

                match event_type:
                    case "system":
                        sid = event.get("session_id", "")
                        if sid:
                            self._sessions[user_id] = sid
                            response.session_id = sid
                            logger.info("claude.session", user_id=user_id, session_id=sid)

                        # Check MCP server status — drop session if any failed
                        mcp_servers = event.get("mcp_servers", [])
                        for srv in mcp_servers:
                            logger.info(
                                "claude.mcp_status",
                                name=srv.get("name"),
                                status=srv.get("status"),
                            )
                        failed = [s["name"] for s in mcp_servers if s.get("status") == "failed"]
                        if failed:
                            logger.warning("claude.mcp_failed", servers=failed, user_id=user_id)
                            # Don't resume this broken session next time
                            self._sessions.pop(user_id, None)
                            response.session_id = ""

                    case "assistant":
                        message = event.get("message", {})
                        for block in message.get("content", []):
                            if block.get("type") == "tool_use":
                                tool_call_count += 1
                                response.tool_calls = tool_call_count

                        # Circuit breaker: max tool calls
                        if tool_call_count >= settings.claude.max_tool_calls:
                            logger.warning(
                                "claude.circuit_breaker.tool_calls",
                                user_id=user_id,
                                count=tool_call_count,
                            )
                            process.terminate()
                            response.errors.append(
                                f"Tool-Call-Limit erreicht ({settings.claude.max_tool_calls})"
                            )
                            break

                    case "result":
                        response.cost_usd = event.get("total_cost_usd", 0.0)
                        response.duration_ms = event.get("duration_ms", 0.0)
                        response.turns = event.get("num_turns", 0)
                        result_text = event.get("result", "")
                        if result_text:
                            response.text = result_text
                        # Handle max_turns exhaustion
                        if event.get("subtype") == "error_max_turns" and not result_text:
                            response.text = (
                                "Die Anfrage war zu komplex und hat das Turn-Limit erreicht. "
                                "Bitte versuche es mit einer spezifischeren Frage."
                            )

                    case "error":
                        error_msg = event.get("error", {}).get("message", str(event))
                        response.errors.append(error_msg)
                        logger.error("claude.error_event", error=error_msg)

            await process.wait()

            # Always read and log stderr
            stderr = ""
            if process.stderr:
                stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
            if stderr:
                logger.warning("claude.stderr", user_id=user_id, stderr=stderr[:1000])

            logger.info(
                "claude.process_exited",
                user_id=user_id,
                returncode=process.returncode,
                lines_received=line_count,
            )

            if process.returncode and process.returncode != 0 and not response.text:
                response.errors.append(f"Exit code {process.returncode}: {stderr}")

        except asyncio.TimeoutError:
            response.errors.append("Claude subprocess timeout")
            logger.error("claude.timeout", user_id=user_id)
        except Exception as e:
            response.errors.append(str(e))
            logger.exception("claude.subprocess_error", user_id=user_id)
        finally:
            os.close(master_fd)

        logger.info(
            "claude.response",
            user_id=user_id,
            text_len=len(response.text),
            tool_calls=response.tool_calls,
            turns=response.turns,
            cost_usd=response.cost_usd,
            errors=response.errors,
        )
        return response

    def _parse_event(self, line: str) -> dict | None:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def clear_session(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)
        logger.info("claude.session_cleared", user_id=user_id)
