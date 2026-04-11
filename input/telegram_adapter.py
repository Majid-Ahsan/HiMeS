import io
import logging
from pathlib import Path
from typing import Callable, Awaitable

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config.settings import settings

logger = structlog.get_logger(__name__)

# Type for the callback that orchestrator registers
MessageCallback = Callable[[int, str, list[bytes] | None], Awaitable[str]]


class TelegramAdapter:
    def __init__(self, on_message: MessageCallback) -> None:
        self._on_message = on_message
        self._app: Application | None = None

    async def start(self) -> None:
        self._app = (
            Application.builder()
            .token(settings.telegram.bot_token)
            .build()
        )

        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
        )
        self._app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice)
        )
        self._app.add_handler(
            MessageHandler(filters.PHOTO, self._handle_photo)
        )

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram_adapter.started")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("telegram_adapter.stopped")

    def _is_authorized(self, user_id: int) -> bool:
        allowed = settings.telegram.allowed_users
        return not allowed or user_id in allowed

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_user or not update.message:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("Nicht autorisiert.")
            return
        await update.message.reply_text("HiMeS bereit.")

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_user or not update.message or not update.message.text:
            return
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return

        logger.info("telegram.text_received", user_id=user_id)
        await self._process_and_reply(update, user_id, update.message.text)

    async def _handle_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_user or not update.message:
            return
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return

        logger.info("telegram.voice_received", user_id=user_id)
        voice = update.message.voice or update.message.audio
        if not voice:
            return

        file = await context.bot.get_file(voice.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)

        transcript = await self._transcribe_audio(buf)
        if not transcript:
            await update.message.reply_text("Konnte Audio nicht transkribieren.")
            return

        await self._process_and_reply(update, user_id, transcript)

    async def _handle_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_user or not update.message or not update.message.photo:
            return
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return

        logger.info("telegram.photo_received", user_id=user_id)

        photo = update.message.photo[-1]  # highest resolution
        file = await context.bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        image_bytes = buf.getvalue()

        caption = update.message.caption or "Beschreibe dieses Bild."
        await self._process_and_reply(
            update, user_id, caption, images=[image_bytes]
        )

    async def _process_and_reply(
        self,
        update: Update,
        user_id: int,
        text: str,
        images: list[bytes] | None = None,
    ) -> None:
        await update.message.chat.send_action("typing")
        try:
            response = await self._on_message(user_id, text, images)
            await update.message.reply_text(response)
        except Exception:
            logger.exception("telegram.reply_failed", user_id=user_id)
            await update.message.reply_text(
                "Fehler bei der Verarbeitung. Bitte erneut versuchen."
            )

    async def _transcribe_audio(self, audio_buf: io.BytesIO) -> str | None:
        try:
            import whisper
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
                tmp.write(audio_buf.read())
                tmp.flush()
                model = whisper.load_model("base")
                result = model.transcribe(tmp.name)
                return result.get("text", "").strip() or None
        except Exception:
            logger.exception("telegram.transcription_failed")
            return None
