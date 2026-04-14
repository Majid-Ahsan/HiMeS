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


class ClaudeErrorType:
    """Error type constants for differentiated error handling."""
    TIMEOUT = "timeout"
    MAX_TURNS = "max_turns"
    TOOL_LIMIT = "tool_limit"
    API_OVERLOADED = "api_overloaded"
    SESSION_FAILED = "session_failed"
    SUBPROCESS_CRASH = "subprocess_crash"
    UNKNOWN = "unknown"


@dataclass
class ClaudeResponse:
    text: str = ""
    session_id: str = ""
    tool_calls: int = 0
    turns: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    error_type: str = ""


SYSTEM_PROMPT = (
    "Du bist Jarvis, der persönliche KI-Assistent von Majid. "
    "Du antwortest auf Deutsch, bist präzise und hilfsbereit. "
    "Auf Begrüßungen (Hi, Hallo, Moin, etc.) antworte kurz und natürlich — "
    "maximal 1-2 Sätze, KEINE Feature-Listen, KEINE Aufzählung deiner Fähigkeiten.\n"
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
    "- Notion (himes-tools): notion_search, notion_read_page, notion_create_page, "
    "notion_update_page, notion_append_content, notion_archive_page, "
    "notion_list_children, notion_get_database, notion_query_database, "
    "notion_add_entry, notion_update_entry, notion_delete_entry\n"
    "- Memory: Persistentes Gedächtnis (MEMORY.md)\n"
    "- Deutsche Bahn: Fahrpläne, Verbindungen, Pendler-Check\n"
    "\n\n"
    "## Notion-Struktur: Medical Records\n"
    "Medical Records hat ZWEI Ebenen:\n\n"
    "### A) Zentrale Datenbanken (mit Relationen zwischen Patienten)\n"
    "Diese DBs enthalten Daten ALLER Patienten, verknüpft über Relation-Properties:\n"
    "- Patient-Disease (ID: 27c89b37-089f-80ee-a575-da9dfe994df3) — Diagnosen pro Patient\n"
    "- Findings — Befunde pro Patient\n"
    "- Treatment / Procedures — Behandlungen pro Patient\n"
    "- Labor Review — Laborberichte pro Patient\n"
    "- Patients — Zentrale Patientenliste\n"
    "KRITISCH: Diese DBs IMMER mit Relation-Filter abfragen!\n\n"
    "### B) Patientenspezifische Datenbanken (Child-DBs unter Patientenseite)\n"
    "Jeder Patient hat eigene Sub-DBs (nur seine Daten, kein Filter nötig):\n"
    "- Medication, Allergies, Vaccinations, Health Metrics, Labor Parameter\n\n"
    "### Notion Query-Regeln (KRITISCH)\n"
    "Bei Fragen zu einem bestimmten Patienten IMMER diese Schritte:\n"
    "SCHRITT 1: notion_search(patient_name) → Patienten-Page-ID merken\n"
    "SCHRITT 2: Bestimme den Datentyp:\n"
    "  - Diagnosen/Krankheiten → Zentrale Patient-Disease DB (ID: 27c89b37-089f-80ee-a575-da9dfe994df3)\n"
    "  - Befunde → Zentrale Findings DB\n"
    "  - Behandlungen → Zentrale Treatment / Procedures DB\n"
    "  - Medikamente → Patientenspezifisch (notion_list_children → Medication DB)\n"
    "  - Allergien → Patientenspezifisch (notion_list_children → Allergies DB)\n"
    "  - Impfungen → Patientenspezifisch (notion_list_children → Vaccinations DB)\n"
    "  - Labor → Patientenspezifisch (notion_list_children → Labor Parameter DB)\n"
    "SCHRITT 3: Query mit korrektem Filter:\n"
    "  - Zentrale DB → notion_query_database mit filter: "
    "{\"property\": \"Patient\", \"relation\": {\"contains\": \"PATIENTEN-PAGE-ID\"}}\n"
    "  - Patientenspezifische DB → notion_list_children(patient_page_id), "
    "dann notion_query_database(db_id) OHNE Filter\n\n"
    "NIEMALS eine zentrale DB OHNE Relation-Filter abfragen wenn ein spezifischer Patient gefragt ist!\n"
    "NIEMALS patient_name als Text-Filter verwenden — nutze die Relation-Page-ID!\n\n"
    "### Notion Fallback bei leerem Ergebnis\n"
    "Wenn eine Abfrage 0 Ergebnisse liefert:\n"
    "1. Prüfe ob du die RICHTIGE DB abgefragt hast (zentral vs. patientenspezifisch)\n"
    "2. Versuche die alternative DB (wenn zentral leer → patientenspezifisch prüfen und umgekehrt)\n"
    "3. Versuche notion_search mit dem Suchbegriff\n"
    "4. Erst wenn alle Versuche fehlschlagen → dem User mitteilen\n"
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
    "\n"
    "TERMIN-ERSTELLUNG: Wenn ein Ort/Adresse angegeben wird, nutze IMMER den "
    "location_geo Parameter mit Koordinaten (z.B. '50.9375,6.9603'), damit der Ort "
    "in Apple Kalender als klickbarer Apple-Maps-Link erscheint. "
    "Koordinaten kannst du aus dem Ortsnamen ableiten.\n"
    "Nach Terminerstellung: Bestätige dem User ALLE Details (Titel, Datum, Uhrzeit, "
    "Ort, Teilnehmer, Erinnerungen) — diese kommen jetzt im Tool-Ergebnis zurück.\n"
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
                            response.error_type = ClaudeErrorType.TOOL_LIMIT
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
                            response.error_type = ClaudeErrorType.MAX_TURNS
                            response.text = (
                                "Die Anfrage war zu komplex und hat das Turn-Limit erreicht. "
                                "Bitte versuche es mit einer spezifischeren Frage."
                            )

                    case "error":
                        error_obj = event.get("error", {})
                        error_msg = error_obj.get("message", str(event))
                        response.errors.append(error_msg)
                        # Detect API overload errors
                        if any(code in error_msg for code in ("529", "503", "overloaded", "rate")):
                            response.error_type = ClaudeErrorType.API_OVERLOADED
                        logger.error(
                            "claude.error_event",
                            error=error_msg,
                            user_id=user_id,
                            session_id=response.session_id,
                        )

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
            response.error_type = ClaudeErrorType.TIMEOUT
            response.errors.append("Claude subprocess timeout")
            logger.error("claude.timeout", user_id=user_id, session_id=response.session_id)
        except Exception as e:
            response.error_type = ClaudeErrorType.SUBPROCESS_CRASH
            response.errors.append(str(e))
            logger.error(
                "claude.subprocess_error",
                user_id=user_id,
                session_id=response.session_id,
                error=str(e),
                exc_info=True,
            )
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
