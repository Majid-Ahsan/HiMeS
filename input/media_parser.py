"""Parse Claude responses for rich media (images, locations, PDFs, audio, buttons)."""

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MediaItem:
    kind: str  # "photo", "location", "document", "audio"
    url: str | None = None
    lat: float | None = None
    lon: float | None = None
    caption: str | None = None


@dataclass
class InlineButton:
    label: str
    data: str  # text sent back when user taps


@dataclass
class ParsedResponse:
    text: str
    media: list[MediaItem]
    buttons: list[InlineButton]


# --- Image patterns ---

# Notion hosted images (secure.notion-static.com, prod-files-secure.s3)
_NOTION_IMAGE = re.compile(
    r"(https?://(?:secure\.notion-static\.com|prod-files-secure\.s3[^\s)]*)"
    r"[^\s)]*\.(?:jpe?g|png|gif|webp)(?:\?[^\s)]*)?)",
    re.IGNORECASE,
)

# Markdown image: ![alt](url)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((https?://[^\s)]+)\)")

# Bare image URL
_BARE_IMAGE_URL = re.compile(
    r"(?<!\()(https?://[^\s)]+\.(?:jpe?g|png|gif|webp|bmp)(?:\?[^\s)]*)?)",
    re.IGNORECASE,
)

# --- PDF pattern ---
_PDF_URL = re.compile(
    r"(https?://[^\s)]+\.pdf(?:\?[^\s)]*)?)",
    re.IGNORECASE,
)

# --- Audio pattern ---
_AUDIO_URL = re.compile(
    r"(https?://[^\s)]+\.(?:mp3|ogg|wav|m4a|flac)(?:\?[^\s)]*)?)",
    re.IGNORECASE,
)

# --- Location patterns ---

# Google Maps: /maps/place/.../@lat,lon or /maps?q=lat,lon
_GMAPS_PLACE = re.compile(
    r"(https?://(?:www\.)?google\.[a-z.]+/maps/place/[^\s]*?@([-\d.]+),([-\d.]+)[^\s]*)"
)
_GMAPS_QUERY = re.compile(
    r"(https?://(?:www\.)?google\.[a-z.]+/maps\?[^\s]*?q=([-\d.]+),([-\d.]+)[^\s]*)"
)

# Apple Maps
_APPLE_MAPS = re.compile(
    r"(https?://maps\.apple\.com/\?[^\s]*?[&?]ll=([-\d.]+),([-\d.]+)[^\s]*)"
)

# --- Button / option patterns ---

# Numbered options: "1. Option A\n2. Option B" or "1) Option A"
_NUMBERED_OPTIONS = re.compile(
    r"^(\d+)[.)]\s+(.+)$", re.MULTILINE
)

# "Soll ich X oder Y?" followed by numbered options
_OPTION_PROMPT = re.compile(
    r"(?:soll ich|möchtest du|wähle|optionen|zur auswahl)[^:]*[:?]\s*\n",
    re.IGNORECASE,
)


def parse_response(text: str) -> ParsedResponse:
    """Parse Claude response into text, media items, and inline buttons.

    Media references are removed from the text. Remaining text is cleaned up.
    """
    media: list[MediaItem] = []
    buttons: list[InlineButton] = []
    cleaned = text
    seen_urls: set[str] = set()

    def _remove(full_match: str) -> None:
        nonlocal cleaned
        cleaned = cleaned.replace(full_match, "", 1)

    def _add_media(kind: str, url: str, caption: str | None = None) -> None:
        if url in seen_urls:
            return
        seen_urls.add(url)
        media.append(MediaItem(kind=kind, url=url, caption=caption))

    # 1) Markdown images — any URL in ![alt](url) syntax
    for m in _MD_IMAGE.finditer(text):
        alt, url = m.group(1), m.group(2)
        _add_media("photo", url, caption=alt or None)
        _remove(m.group(0))

    # 2) Notion images (often no file extension in path, but domain is distinctive)
    for m in _NOTION_IMAGE.finditer(cleaned):
        url = m.group(1)
        _add_media("photo", url)
        _remove(url)

    # 3) Bare image URLs
    for m in _BARE_IMAGE_URL.finditer(cleaned):
        url = m.group(1)
        _add_media("photo", url)
        _remove(url)

    # 4) PDF URLs
    for m in _PDF_URL.finditer(cleaned):
        url = m.group(1)
        if url not in seen_urls:
            seen_urls.add(url)
            media.append(MediaItem(kind="document", url=url))
            _remove(url)

    # 5) Audio URLs
    for m in _AUDIO_URL.finditer(cleaned):
        url = m.group(1)
        if url not in seen_urls:
            seen_urls.add(url)
            media.append(MediaItem(kind="audio", url=url))
            _remove(url)

    # 6) Google Maps with coordinates
    for pattern in (_GMAPS_PLACE, _GMAPS_QUERY):
        for m in pattern.finditer(cleaned):
            full, lat, lon = m.group(1), float(m.group(2)), float(m.group(3))
            if _valid_coords(lat, lon):
                media.append(MediaItem(kind="location", lat=lat, lon=lon))
                _remove(full)

    # 7) Apple Maps
    for m in _APPLE_MAPS.finditer(cleaned):
        full, lat, lon = m.group(1), float(m.group(2)), float(m.group(3))
        if _valid_coords(lat, lon):
            media.append(MediaItem(kind="location", lat=lat, lon=lon))
            _remove(full)

    # 8) Inline buttons — detect numbered option lists after a prompt
    buttons = _extract_buttons(cleaned)
    if buttons:
        # Remove the option lines from text, keep the prompt question
        for btn in buttons:
            pattern = re.compile(
                r"^\d+[.)]\s+" + re.escape(btn.label) + r"\s*$",
                re.MULTILINE,
            )
            cleaned = pattern.sub("", cleaned, count=1)

    # Clean up whitespace left by removals
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if media:
        logger.info(
            "media_parser.extracted",
            count=len(media),
            kinds=[i.kind for i in media],
        )
    if buttons:
        logger.info("media_parser.buttons_detected", count=len(buttons))

    return ParsedResponse(text=cleaned, media=media, buttons=buttons)


def _extract_buttons(text: str) -> list[InlineButton]:
    """Detect numbered option lists that follow a question/prompt pattern."""
    # Find if there's a prompt pattern
    prompt_match = _OPTION_PROMPT.search(text)
    if not prompt_match:
        return []

    # Look for numbered options after the prompt
    after_prompt = text[prompt_match.end():]
    options = _NUMBERED_OPTIONS.findall(after_prompt)

    # Need at least 2 options, max 8 (Telegram inline keyboard limit per row)
    if len(options) < 2 or len(options) > 8:
        return []

    return [
        InlineButton(label=label.strip(), data=label.strip())
        for _, label in options
    ]


def _valid_coords(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180
