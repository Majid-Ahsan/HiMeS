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
from core.claude_subprocess import ClaudeSubprocess
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

    def _build_health_app(self) -> FastAPI:
        app = FastAPI(docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "himes"}

        return app

    async def _handle_message(
        self, user_id: int, text: str, images: list[bytes] | None = None
    ) -> str:
        logger.info("orchestrator.message_received", user_id=user_id, text_len=len(text))

        # Warmup: erste Nachricht eines Users startet Session + MCP Verbindung
        if user_id not in self._claude._sessions:
            await self._claude.warmup(user_id)

        # Images: for now log and append hint to prompt
        if images:
            logger.info("orchestrator.images_received", user_id=user_id, count=len(images))
            text += "\n\n[Bild wurde angehängt – Bildverarbeitung kommt in Phase 2]"

        response = await self._claude.send(user_id, text)

        if response.errors and not response.text:
            error_summary = "; ".join(response.errors)
            logger.error("orchestrator.claude_errors", user_id=user_id, errors=error_summary)
            return f"Fehler bei der Verarbeitung: {error_summary}"

        if not response.text:
            return "Keine Antwort von Claude erhalten."

        logger.info(
            "orchestrator.response_sent",
            user_id=user_id,
            text_len=len(response.text),
            cost_usd=response.cost_usd,
            turns=response.turns,
        )
        return response.text

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
