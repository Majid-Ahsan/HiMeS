import asyncio
import json
import logging
import os
import signal
import sys

import structlog
import uvicorn
from fastapi import FastAPI

from config.settings import settings
from core.claude_subprocess import ClaudeSubprocess, ClaudeErrorType
from core.hallucination_guard import build_default_guard
from input.telegram_adapter import TelegramAdapter

logger = structlog.get_logger(__name__)


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log.level)
        ),
    )


class Orchestrator:
    def __init__(self) -> None:
        self._claude = ClaudeSubprocess()
        self._telegram = TelegramAdapter(on_message=self._handle_message)
        self._health_app = self._build_health_app()
        self._shutdown_event = asyncio.Event()
        self._guard = build_default_guard()

    def _build_health_app(self) -> FastAPI:
        app = FastAPI(docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "himes"}

        return app

    def _render_mcp_config(self) -> None:
        """Replace ${VAR} placeholders in mcp_config.json with env values."""
        config_path = settings.mcp.config_path
        template = config_path.read_text(encoding="utf-8")

        replacements = {
            "${NOTION_TOKEN}": os.environ.get("NOTION_TOKEN", ""),
            "${DB_API_CLIENT_ID}": os.environ.get("DB_API_CLIENT_ID", ""),
            "${DB_API_CLIENT_SECRET}": os.environ.get("DB_API_CLIENT_SECRET", ""),
        }

        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)

        config_path.write_text(rendered, encoding="utf-8")
        logger.info("orchestrator.mcp_config_rendered")

    _ERROR_MESSAGES = {
        ClaudeErrorType.TIMEOUT: (
            "Die Anfrage hat zu lange gedauert. "
            "Ich starte eine neue Session und versuche es nochmal..."
        ),
        ClaudeErrorType.API_OVERLOADED: (
            "Der Server ist gerade überlastet. "
            "Ich versuche es in ein paar Sekunden nochmal..."
        ),
        ClaudeErrorType.MAX_TURNS: (
            "Die Anfrage war zu komplex. "
            "Kannst du sie einfacher formulieren?"
        ),
        ClaudeErrorType.TOOL_LIMIT: (
            "Zu viele Tool-Aufrufe bei dieser Anfrage. "
            "Versuche es mit einer spezifischeren Frage."
        ),
        ClaudeErrorType.SESSION_FAILED: (
            "Es gab ein technisches Problem mit der Session. "
            "Ich starte eine neue..."
        ),
        ClaudeErrorType.SUBPROCESS_CRASH: (
            "Es gab ein technisches Problem. "
            "Ich starte eine neue Session..."
        ),
        ClaudeErrorType.MCP_FAILED: (
            "Ein Tool-Server konnte nicht gestartet werden. "
            "Ich versuche es mit einer neuen Session..."
        ),
    }

    # These error types get an automatic retry with a fresh session
    _RETRYABLE_ERRORS = {
        ClaudeErrorType.TIMEOUT,
        ClaudeErrorType.API_OVERLOADED,
        ClaudeErrorType.SUBPROCESS_CRASH,
        ClaudeErrorType.SESSION_FAILED,
        ClaudeErrorType.MCP_FAILED,
    }

    # Phrases that indicate Claude refused to use a tool it couldn't see
    # (pending MCP race). Used to trigger auto-retry.
    _TOOL_REFUSAL_MARKERS = (
        "tools sind gerade nicht verfügbar",
        "tools sind gerade nicht verfuegbar",
        "tool nicht verfügbar",
        "tool nicht verfuegbar",
        "deutsche bahn tools sind",
        "kein tool verfügbar",
        "kein tool verfuegbar",
        "kann den aktuellen standort",
        "kann den aktuellen status",
    )

    @classmethod
    def _looks_like_tool_refusal(cls, text: str) -> bool:
        """Heuristic: did Claude refuse because a tool appeared missing?"""
        if not text:
            return False
        lower = text.lower()
        return any(marker in lower for marker in cls._TOOL_REFUSAL_MARKERS)

    async def _handle_message(
        self, user_id: int, text: str, attachments: list[str] | None = None
    ) -> str:
        logger.info("orchestrator.message_received", user_id=user_id, text_len=len(text))

        # Append file references so Claude can read them with its Read tool
        if attachments:
            logger.info(
                "orchestrator.attachments_received",
                user_id=user_id,
                count=len(attachments),
                files=attachments,
            )
            file_refs = "\n".join(
                f"- {path}" for path in attachments
            )
            text += (
                f"\n\n[Der User hat folgende Dateien gesendet. "
                f"Lies sie mit dem Read-Tool:]\n{file_refs}"
            )

        try:
            return await self._process_claude(user_id, text)
        finally:
            # Cleanup temp files after processing
            if attachments:
                for path in attachments:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    async def _process_claude(self, user_id: int, text: str) -> str:
        response = await self._claude.send(user_id, text)

        # ── Differentiated error handling with auto-retry ──
        if response.errors and not response.text:
            error_type = response.error_type or ClaudeErrorType.UNKNOWN
            error_summary = "; ".join(response.errors)
            logger.error(
                "orchestrator.claude_errors",
                user_id=user_id,
                error_type=error_type,
                errors=error_summary,
                session_id=response.session_id,
                prompt=text[:200],
            )

            # Auto-retry for transient errors (1x with fresh session)
            if error_type in self._RETRYABLE_ERRORS:
                user_msg = self._ERROR_MESSAGES.get(error_type, "")
                logger.info("orchestrator.auto_retry", user_id=user_id, error_type=error_type)

                # Clear broken session and wait briefly for API overload
                self._claude.clear_session(user_id)
                if error_type == ClaudeErrorType.API_OVERLOADED:
                    await asyncio.sleep(3)

                retry_response = await self._claude.send(user_id, text)

                if retry_response.text:
                    logger.info("orchestrator.retry_success", user_id=user_id)
                    return retry_response.text

                # Retry also failed
                logger.error(
                    "orchestrator.retry_failed",
                    user_id=user_id,
                    errors="; ".join(retry_response.errors),
                )
                return (
                    user_msg
                    or f"Fehler bei der Verarbeitung: {error_summary}"
                )

            # Non-retryable errors: return user-friendly message
            return self._ERROR_MESSAGES.get(
                error_type,
                f"Fehler bei der Verarbeitung: {error_summary}",
            )

        if not response.text:
            return "Keine Antwort von Claude erhalten."

        # ── Pending-MCP auto-retry ──
        # Race condition: if an MCP was "pending" at init, its tools aren't
        # in Claude's tool list. Claude may refuse the request as "tool not
        # available" without calling it. Detect this pattern and retry ONCE
        # with a fresh session (MCPs have more time to initialise).
        if (
            response.pending_mcps
            and response.tool_calls == 0
            and self._looks_like_tool_refusal(response.text)
        ):
            logger.warning(
                "orchestrator.pending_mcp_retry",
                user_id=user_id,
                pending_mcps=response.pending_mcps,
                text_preview=response.text[:120],
            )
            self._claude.clear_session(user_id)
            # Small pause to let MCPs finish starting
            await asyncio.sleep(2)
            retry_response = await self._claude.send(user_id, text)
            if retry_response.text and retry_response.tool_calls > 0:
                logger.info(
                    "orchestrator.pending_mcp_retry_success",
                    user_id=user_id,
                    tools_used=retry_response.tools_used,
                )
                response = retry_response
            else:
                logger.info(
                    "orchestrator.pending_mcp_retry_no_improvement",
                    user_id=user_id,
                )

        # Hallucination guard — soft check: append disclaimer if output claims
        # domain-specific data (train numbers, Gleise, delays) but no tool from
        # that domain was called in this turn. Never rewrites/blocks, only logs.
        final_text = response.text
        try:
            is_suspect, disclaimer = self._guard.check(
                response.text, response.tools_used
            )
            if is_suspect:
                final_text = response.text + disclaimer
                logger.warning(
                    "orchestrator.hallucination_guard_triggered",
                    user_id=user_id,
                    tools_used=response.tools_used,
                    text_len=len(response.text),
                )
        except Exception as guard_err:
            # Guard must NEVER break the response — log and pass through
            logger.error(
                "orchestrator.guard_crashed",
                user_id=user_id,
                error=str(guard_err),
                exc_info=True,
            )
            final_text = response.text

        logger.info(
            "orchestrator.response_sent",
            user_id=user_id,
            text_len=len(final_text),
            cost_usd=response.cost_usd,
            turns=response.turns,
            tools_used=response.tools_used,
        )
        return final_text

    async def _run_health_server(self) -> None:
        config = uvicorn.Config(
            self._health_app,
            host="0.0.0.0",
            port=settings.health.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def run(self) -> None:
        _configure_logging()

        if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            raise RuntimeError(
                "CLAUDE_CODE_OAUTH_TOKEN nicht gesetzt. "
                "Generiere ein Token mit: claude setup-token"
            )

        self._render_mcp_config()
        logger.info("orchestrator.starting")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown_event.set)

        # Start Telegram + Health server
        await self._telegram.start()
        health_task = asyncio.create_task(self._run_health_server())

        logger.info("orchestrator.running")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        logger.info("orchestrator.shutting_down")
        await self._telegram.stop()
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

        logger.info("orchestrator.stopped")


def main() -> None:
    orchestrator = Orchestrator()
    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    main()
