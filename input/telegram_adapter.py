import io
import logging
from pathlib import Path
from typing import Callable, Awaitable
from uuid import uuid4

import aiohttp
import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config.settings import settings
from input.media_parser import parse_response, ParsedResponse, MediaItem, InlineButton

logger = structlog.get_logger(__name__)

# Telegram limits
_TG_PHOTO_MAX = 10 * 1024 * 1024   # 10 MB
_TG_DOC_MAX = 50 * 1024 * 1024     # 50 MB
_TG_CAPTION_MAX = 1024              # caption character limit
_DOWNLOAD_TIMEOUT = 15              # seconds

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
        self._app.add_handler(CallbackQueryHandler(self._handle_button_tap))

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

    # ── Handlers ──────────────────────────────────────────────────────

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

    async def _handle_button_tap(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline keyboard button taps — send button text as new message."""
        query = update.callback_query
        if not query or not query.from_user:
            return
        user_id = query.from_user.id
        if not self._is_authorized(user_id):
            await query.answer("Nicht autorisiert.")
            return

        await query.answer()
        button_text = query.data
        logger.info("telegram.button_tap", user_id=user_id, data=button_text)

        # Send the button label as a new user message to the orchestrator
        await query.message.chat.send_action("typing")
        try:
            response = await self._on_message(user_id, button_text, None)
            parsed = parse_response(response)
            await self._send_parsed_response(query.message, parsed)
        except Exception:
            logger.exception("telegram.button_reply_failed", user_id=user_id)
            await query.message.reply_text(
                "Es gab ein Netzwerkproblem. Bitte versuche es nochmal."
            )

    # ── Core reply logic ──────────────────────────────────────────────

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
            parsed = parse_response(response)
            await self._send_parsed_response(update.message, parsed)
        except Exception:
            logger.exception("telegram.reply_failed", user_id=user_id)
            await update.message.reply_text(
                "Es gab ein Netzwerkproblem. Bitte versuche es nochmal."
            )

    async def _send_parsed_response(self, message, parsed: ParsedResponse) -> None:
        """Send text + media + buttons from a parsed response."""
        has_text = bool(parsed.text)
        has_media = bool(parsed.media)
        has_buttons = bool(parsed.buttons)

        # Build inline keyboard if buttons detected
        reply_markup = None
        if has_buttons:
            keyboard = [
                [InlineKeyboardButton(btn.label, callback_data=btn.data)]
                for btn in parsed.buttons
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        # Strategy: if exactly 1 photo + short text → use caption on the photo
        if (
            has_text
            and len(parsed.media) == 1
            and parsed.media[0].kind == "photo"
            and len(parsed.text) <= _TG_CAPTION_MAX
        ):
            await self._send_photo(
                message,
                parsed.media[0],
                caption=parsed.text,
                reply_markup=reply_markup,
            )
            return

        # Otherwise: send text first, then each media item
        if has_text:
            await message.reply_text(
                parsed.text,
                reply_markup=reply_markup if not has_media else None,
            )

        for i, item in enumerate(parsed.media):
            # Attach buttons to the last media item if text didn't carry them
            markup = reply_markup if (i == len(parsed.media) - 1 and has_text) else None
            await self._send_media_item(message, item, reply_markup=markup)

        # If buttons but no media, and text already sent with markup → done
        # If nothing was sent at all, send original empty-ish text
        if not has_text and not has_media:
            await message.reply_text(
                parsed.text or "Keine Antwort erhalten.",
                reply_markup=reply_markup,
            )

    # ── Media senders with fallbacks ──────────────────────────────────

    async def _send_photo(
        self,
        message,
        item: MediaItem,
        caption: str | None = None,
        reply_markup=None,
    ) -> None:
        """Send photo with size check and fallbacks."""
        cap = caption or item.caption
        try:
            # First try sending URL directly (Telegram downloads it)
            await message.reply_photo(
                photo=item.url,
                caption=cap,
                reply_markup=reply_markup,
            )
        except Exception as e:
            err = str(e).lower()
            logger.warning("telegram.photo_url_failed", url=item.url, error=err)

            # If URL failed, try downloading ourselves and sending bytes
            data = await self._download_url(item.url)
            if data is None:
                # Total failure → send as clickable link
                await message.reply_text(
                    f"{cap}\n{item.url}" if cap else item.url,
                    reply_markup=reply_markup,
                )
                return

            if len(data) > _TG_PHOTO_MAX:
                # Too large for photo → send as document
                logger.info("telegram.photo_too_large_as_doc", size=len(data))
                await message.reply_document(
                    document=io.BytesIO(data),
                    filename="image.jpg",
                    caption=cap,
                    reply_markup=reply_markup,
                )
            else:
                try:
                    await message.reply_photo(
                        photo=io.BytesIO(data),
                        caption=cap,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    logger.warning("telegram.photo_bytes_failed", url=item.url)
                    await message.reply_text(
                        f"{cap}\n{item.url}" if cap else item.url,
                        reply_markup=reply_markup,
                    )

    async def _send_media_item(
        self, message, item: MediaItem, reply_markup=None
    ) -> None:
        """Route a media item to the right sender with fallback."""
        try:
            if item.kind == "photo" and item.url:
                await self._send_photo(message, item, reply_markup=reply_markup)

            elif item.kind == "document" and item.url:
                data = await self._download_url(item.url)
                if data and len(data) <= _TG_DOC_MAX:
                    filename = item.url.rsplit("/", 1)[-1].split("?")[0] or "file.pdf"
                    await message.reply_document(
                        document=io.BytesIO(data),
                        filename=filename,
                        caption=item.caption,
                        reply_markup=reply_markup,
                    )
                else:
                    await message.reply_text(
                        f"Dokument: {item.url}",
                        reply_markup=reply_markup,
                    )

            elif item.kind == "audio" and item.url:
                data = await self._download_url(item.url)
                if data:
                    filename = item.url.rsplit("/", 1)[-1].split("?")[0] or "audio.mp3"
                    await message.reply_audio(
                        audio=io.BytesIO(data),
                        filename=filename,
                        caption=item.caption,
                        reply_markup=reply_markup,
                    )
                else:
                    await message.reply_text(
                        f"Audio: {item.url}",
                        reply_markup=reply_markup,
                    )

            elif item.kind == "location" and item.lat is not None and item.lon is not None:
                await message.reply_location(
                    latitude=item.lat,
                    longitude=item.lon,
                    reply_markup=reply_markup,
                )

        except Exception:
            fallback = item.url or f"{item.lat}, {item.lon}"
            logger.warning("telegram.media_send_failed", kind=item.kind, fallback=fallback)
            await message.reply_text(
                f"[{item.kind}] {fallback}",
                reply_markup=reply_markup,
            )

    # ── Helpers ───────────────────────────────────────────────────────

    async def _download_url(self, url: str) -> bytes | None:
        """Download a URL with timeout. Returns bytes or None on failure."""
        try:
            timeout = aiohttp.ClientTimeout(total=_DOWNLOAD_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning("telegram.download_failed", url=url, status=resp.status)
                        return None
                    return await resp.read()
        except Exception:
            logger.warning("telegram.download_error", url=url)
            return None

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
