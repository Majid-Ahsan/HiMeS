"""
Persistenter claude-code-sdk Client.

Ein einziger ClaudeSDKClient wird beim Bot-Start erzeugt und für ALLE
Nachrichten wiederverwendet. Damit bleiben MCP-Server warm und die Latenz
für Folge-Nachrichten sinkt deutlich (Test: 5.46s → 3.32s für einfache
Nachrichten ohne Tool-Calls).

Das alte claude_subprocess.py bleibt als Fallback bestehen und wird
VOM ORCHESTRATOR bei SDK-Fehlern angesprungen.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Callable

import structlog

from core.claude_subprocess import ClaudeErrorType, ClaudeResponse

logger = structlog.get_logger(__name__)


# ── Monkey-patch: SDK 0.0.25 kennt "rate_limit_event" nicht ──────────────────
# Ohne diesen Patch wirft jeder API-Call einen MessageParseError.
def _patch_sdk_parser() -> None:
    try:
        import claude_code_sdk._internal.message_parser as mp  # type: ignore
        _original_parse = mp.parse_message

        def _safe_parse(data):
            try:
                return _original_parse(data)
            except mp.MessageParseError:
                return None

        mp.parse_message = _safe_parse

        # Der Client-Modul hält eine bereits importierte Referenz — auch patchen.
        import claude_code_sdk._internal.client as cl  # type: ignore
        cl.parse_message = _safe_parse
    except Exception as exc:  # pragma: no cover — Defensiv-Code
        logger.warning("sdk_client.parser_patch_failed", error=str(exc))


_patch_sdk_parser()


from claude_code_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from config.settings import settings  # noqa: E402


# Phase 1.5.10e v2 — Tool-Whitelist.
#
# Der SDK bietet von Haus aus "ToolSearch" — Claude ruft das als erstes Tool
# auf, um bei >10 verfügbaren Tools die Schemas on-demand nachzuladen. Im
# Event-Log von Phase 1.5.10f bestätigt: ToolSearch wird bei jeder Anfrage
# als Event 2-3 aufgerufen, kostet ~0.6-1.0s Roundtrip + mehrere Sekunden
# Claude-Denkzeit davor. Summiert auf 5-7s pro Nachricht.
#
# Lösung: explizite Tool-Whitelist. Nur die aufgeführten Tools sind für
# Claude sichtbar, ToolSearch entfällt automatisch. Server-Level-Prefixe
# (z.B. ``mcp__caldav``) laden ALLE Tools des jeweiligen MCP-Servers —
# kein Hardcoding einzelner Tool-Namen, robust gegen neue Tools.
#
# Bewusst NICHT in der Liste:
# - ToolSearch (das wollen wir ja eliminieren)
# - Bash, Edit, Write, Glob, Grep, NotebookEdit (Claude soll keine Files ändern)
# - CronCreate/CronDelete/CronList, TodoWrite (verursachten BUG-2 in 1.5.11)
# - Task, Agent, AskUserQuestion (keine Sub-Agenten)
# - WebFetch, WebSearch (bis Brave Search MCP ready ist, Phase 1.5.9)
# - EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree (irrelevant)
_ALLOWED_TOOLS: list[str] = [
    "Read",  # für Foto-/Dokument-Analyse (Phase 1.5.18)
    "mcp__himes-tools",   # 14 Tools: memory (2) + notion (12)
    "mcp__things3",       # create/list/complete tasks
    "mcp__caldav",        # 9 Kalender-Tools
    "mcp__weather",       # 3 Wetter-Tools
    "mcp__time",          # get_current_time, convert_time
    "mcp__deutsche-bahn", # 9+3 DB/VRR-Tools
    "mcp__cognee",        # cognee_search (read-only)
]


class SDKClient:
    """Persistenter SDK-Client mit Singleton-Semantik.

    Der Client wird EINMAL beim Bot-Start erzeugt (``start()``) und bis
    ``shutdown()`` wiederverwendet. Ein Lock serialisiert gleichzeitige
    Nachrichten (Single-User-Szenario).
    """

    def __init__(self, build_system_prompt: Callable[[], str]) -> None:
        self._build_system_prompt = build_system_prompt
        self._client: ClaudeSDKClient | None = None
        self._lock = asyncio.Lock()
        # Restart nur bei Tageswechsel — nicht bei Minuten-Änderung der
        # Uhrzeit im System-Prompt (sonst würde jede Nachricht in einer
        # neuen Minute einen ~4s Reconnect auslösen).
        self._current_day: date | None = None
        self._restart_count = 0

    # ── Options / Lifecycle ────────────────────────────────────────────────

    def _build_options(self, system_prompt: str) -> ClaudeCodeOptions:
        """Identische Settings wie claude_subprocess._build_command().

        Phase 1.5.10e v2: optional ``allowed_tools`` — wenn gesetzt, entfällt
        ToolSearch (siehe ``_ALLOWED_TOOLS``-Kommentar). Feature-Flag in
        ``settings.claude.use_allowed_tools_whitelist`` — bei Problemen
        auf False setzen, alter Zustand ist eine Environment-Änderung entfernt.
        """
        kwargs: dict[str, object] = {
            "system_prompt": system_prompt,
            "model": settings.claude.model,
            "max_turns": settings.claude.max_turns,
            # mcp_servers akzeptiert einen Pfad (getestet in test_sdk.py) —
            # keine Format-Konvertierung nötig.
            "mcp_servers": str(settings.mcp.config_path),
            "permission_mode": "bypassPermissions",
            "cwd": "/app",
        }
        if settings.claude.use_allowed_tools_whitelist:
            kwargs["allowed_tools"] = list(_ALLOWED_TOOLS)
            logger.info(
                "sdk_client.allowed_tools_active",
                count=len(_ALLOWED_TOOLS),
                tools=_ALLOWED_TOOLS,
            )
        # Phase 1.5.10e v2b — ToolSearch-Meta-Tool komplett deaktivieren.
        # Separater Flag damit v2b isoliert revertierbar ist (Split-Strategie).
        if settings.claude.disable_tool_search:
            existing_env = dict(kwargs.get("env") or {})
            existing_env["ENABLE_TOOL_SEARCH"] = "false"
            kwargs["env"] = existing_env
            logger.info("sdk_client.tool_search_disabled")
        return ClaudeCodeOptions(**kwargs)

    async def start(self) -> None:
        """Startet den SDK-Client EINMAL beim Bot-Start."""
        if self._client is not None:
            logger.warning("sdk_client.already_started")
            return

        prompt = self._build_system_prompt()
        self._current_day = date.today()
        options = self._build_options(prompt)

        t0 = time.perf_counter()
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()
        logger.info(
            "sdk_client.started",
            connect_ms=int((time.perf_counter() - t0) * 1000),
            model=settings.claude.model,
        )

    async def shutdown(self) -> None:
        """Sauberes Beenden beim Bot-Shutdown."""
        if self._client is None:
            return
        try:
            await self._client.disconnect()
        except Exception as exc:
            logger.warning("sdk_client.disconnect_error", error=str(exc))
        finally:
            self._client = None
            logger.info("sdk_client.shutdown")

    @staticmethod
    def _log_debug_event(
        user_id: int, request_start: float, event_index: int, msg: object
    ) -> None:
        """Debug-Hilfe für Phase 1.5.10f (Streaming-Planung).

        Loggt jeden Event aus ``client.receive_response()`` mit:
        - elapsed_ms seit Request-Start
        - event_index (0-basiert, zeigt Reihenfolge)
        - Typ-Name
        - Kurz-repr (für alles was nicht AssistantMessage ist)

        Für AssistantMessage zusätzlich: Block-Struktur. Damit können wir
        erkennen, ob der SDK Delta-Streaming macht (viele AssistantMessages
        mit je 1 TextBlock wachsender Länge) oder Block-Streaming (1
        AssistantMessage pro Turn mit kompletten Blöcken).
        """
        elapsed_ms = int((time.perf_counter() - request_start) * 1000)
        msg_type = type(msg).__name__

        if isinstance(msg, AssistantMessage):
            blocks = []
            for block in msg.content:
                btype = type(block).__name__
                if isinstance(block, TextBlock):
                    text = block.text or ""
                    blocks.append(
                        {
                            "type": btype,
                            "text_len": len(text),
                            "text_preview": text[:80],
                        }
                    )
                elif isinstance(block, ToolUseBlock):
                    blocks.append(
                        {
                            "type": btype,
                            "tool_name": getattr(block, "name", ""),
                            "tool_id": getattr(block, "id", "")[:16],
                        }
                    )
                else:
                    blocks.append(
                        {"type": btype, "repr": repr(block)[:100]}
                    )
            logger.info(
                "sdk_client.debug_event",
                user_id=user_id,
                event_index=event_index,
                elapsed_ms=elapsed_ms,
                msg_type=msg_type,
                block_count=len(msg.content),
                blocks=blocks,
            )
        else:
            extra: dict[str, object] = {}
            if isinstance(msg, ResultMessage):
                result_text = getattr(msg, "result", None)
                extra.update(
                    {
                        "subtype": getattr(msg, "subtype", ""),
                        "result_len": len(result_text) if isinstance(result_text, str) else 0,
                        "num_turns": getattr(msg, "num_turns", 0),
                        "duration_ms_sdk": getattr(msg, "duration_ms", 0),
                    }
                )
            logger.info(
                "sdk_client.debug_event",
                user_id=user_id,
                event_index=event_index,
                elapsed_ms=elapsed_ms,
                msg_type=msg_type,
                repr=repr(msg)[:300],
                **extra,
            )

    async def _restart(self) -> None:
        """Client neu starten (z.B. bei Tageswechsel oder Fehler)."""
        self._restart_count += 1
        logger.info("sdk_client.restarting", restart_count=self._restart_count)
        await self.shutdown()
        prompt = self._build_system_prompt()
        self._current_day = date.today()
        options = self._build_options(prompt)
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    # ── Hauptmethode: gleiche Signatur wie ClaudeSubprocess.send() ─────────

    async def send(self, user_id: int, prompt: str) -> ClaudeResponse:
        """Sendet eine Nachricht, gibt ``ClaudeResponse``-kompatibles Objekt zurück.

        Bei Fehlern wird ``error_type`` gesetzt und ``text`` bleibt leer —
        der Orchestrator entscheidet dann über Fallback/Retry.
        """
        response = ClaudeResponse()
        t0 = time.perf_counter()

        async with self._lock:
            # Tageswechsel → Restart (damit Datum im System-Prompt stimmt).
            # Minuten-Drift der Uhrzeit ist egal: Claude nutzt bei relativen
            # Zeitangaben sowieso das time-MCP-Tool.
            today = date.today()
            if self._current_day is not None and today != self._current_day:
                logger.info(
                    "sdk_client.day_changed",
                    previous=str(self._current_day),
                    current=str(today),
                )
                try:
                    await self._restart()
                except Exception as exc:
                    logger.error("sdk_client.restart_failed", error=str(exc))
                    response.error_type = ClaudeErrorType.SUBPROCESS_CRASH
                    response.errors.append(f"SDK restart failed: {exc}")
                    return response

            # Lazy start: falls noch nie gestartet
            if self._client is None:
                try:
                    await self.start()
                except Exception as exc:
                    logger.error("sdk_client.lazy_start_failed", error=str(exc))
                    response.error_type = ClaudeErrorType.SUBPROCESS_CRASH
                    response.errors.append(f"SDK start failed: {exc}")
                    return response

            client = self._client
            assert client is not None

            # Gesammelte Zwischentexte (Claude's "Denken" zwischen Tool-Calls) —
            # nur als Fallback verwendet, falls ResultMessage.result leer ist.
            # Sonst würde "Ich lade zuerst das Tool-Schema..." vor der finalen
            # Antwort landen (Regression gegenüber CLI-Subprocess-Weg).
            intermediate_text = ""

            debug_events = settings.claude.debug_sdk_events
            event_index = 0

            try:
                await client.query(prompt)

                if debug_events:
                    logger.info(
                        "sdk_client.debug_stream_start",
                        user_id=user_id,
                        prompt_preview=prompt[:80],
                    )

                tool_call_count = 0

                async for msg in client.receive_response():
                    if msg is None:
                        continue

                    if debug_events:
                        self._log_debug_event(user_id, t0, event_index, msg)
                        event_index += 1

                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                intermediate_text += block.text
                            elif isinstance(block, ToolUseBlock):
                                tool_call_count += 1
                                response.tools_used.append(block.name)
                                response.tool_calls = tool_call_count

                        # Circuit breaker: max_tool_calls
                        if tool_call_count >= settings.claude.max_tool_calls:
                            logger.warning(
                                "sdk_client.tool_limit_reached",
                                user_id=user_id,
                                count=tool_call_count,
                            )
                            response.error_type = ClaudeErrorType.TOOL_LIMIT
                            response.errors.append(
                                f"Tool-Call-Limit erreicht ({settings.claude.max_tool_calls})"
                            )
                            break

                    elif isinstance(msg, ResultMessage):
                        # Session/Cost/Turns extrahieren
                        response.session_id = getattr(msg, "session_id", "") or ""
                        response.cost_usd = (
                            getattr(msg, "total_cost_usd", 0.0) or 0.0
                        )
                        response.turns = getattr(msg, "num_turns", 0) or 0
                        duration = getattr(msg, "duration_ms", 0.0) or 0.0
                        response.duration_ms = float(duration)

                        # Source of truth: ResultMessage.result. Das entspricht
                        # exakt dem was der CLI-Subprocess als finale Antwort
                        # liefert (ohne Denk-Zwischentexte). Nur als Fallback:
                        # gesammelter intermediate_text.
                        result_text = getattr(msg, "result", None)
                        if result_text:
                            response.text = (
                                result_text
                                if isinstance(result_text, str)
                                else str(result_text)
                            )
                        elif intermediate_text:
                            response.text = intermediate_text

                        subtype = getattr(msg, "subtype", "")
                        if subtype == "error_max_turns" and not response.text:
                            response.error_type = ClaudeErrorType.MAX_TURNS
                            response.text = (
                                "Die Anfrage war zu komplex und hat das Turn-Limit "
                                "erreicht. Bitte versuche es mit einer spezifischeren "
                                "Frage."
                            )
                        break  # ResultMessage = Ende der Antwort
                else:
                    # Stream endete ohne ResultMessage — gesammelten Text nehmen
                    if intermediate_text and not response.text:
                        response.text = intermediate_text

                if debug_events:
                    logger.info(
                        "sdk_client.debug_stream_end",
                        user_id=user_id,
                        event_count=event_index,
                        elapsed_ms=int((time.perf_counter() - t0) * 1000),
                    )

            except Exception as exc:
                logger.error(
                    "sdk_client.send_failed",
                    user_id=user_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                response.error_type = ClaudeErrorType.SUBPROCESS_CRASH
                response.errors.append(str(exc))
                # Client als kaputt markieren — nächster Aufruf startet neu
                try:
                    await self._client.disconnect()  # type: ignore[union-attr]
                except Exception:
                    pass
                self._client = None
                self._current_day = None

        response.duration_ms = response.duration_ms or (
            (time.perf_counter() - t0) * 1000
        )
        logger.info(
            "sdk_client.response",
            user_id=user_id,
            text_len=len(response.text),
            tool_calls=response.tool_calls,
            tools_used=response.tools_used,
            turns=response.turns,
            cost_usd=response.cost_usd,
            duration_ms=int(response.duration_ms),
            errors=response.errors,
        )
        return response
