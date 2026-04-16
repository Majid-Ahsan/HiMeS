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
        """Identische Settings wie claude_subprocess._build_command()."""
        return ClaudeCodeOptions(
            system_prompt=system_prompt,
            model=settings.claude.model,
            max_turns=settings.claude.max_turns,
            # mcp_servers akzeptiert einen Pfad (getestet in test_sdk.py) —
            # keine Format-Konvertierung nötig.
            mcp_servers=str(settings.mcp.config_path),
            permission_mode="bypassPermissions",
            cwd="/app",
        )

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

            try:
                await client.query(prompt)

                tool_call_count = 0

                async for msg in client.receive_response():
                    if msg is None:
                        continue

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
