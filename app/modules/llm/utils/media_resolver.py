"""Media resolver - converts file paths / base64 / URLs to data URLs."""
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIME_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"BM", "image/bmp"),
]


def detect_mime(data: bytes) -> str:
    for sig, mime in MIME_SIGNATURES:
        if data[: len(sig)] == sig:
            return mime
    # Check WebP: starts with RIFF????WEBP
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def detect_input_type(data: str) -> str:
    if data.startswith("data:"):
        return "data_url"
    if data.startswith("http://") or data.startswith("https://"):
        return "url"
    if Path(data).exists():
        return "filepath"
    # Assume base64 if it looks like one
    return "base64"


class MediaResolver:
    @staticmethod
    async def resolve(input_data: str) -> str:
        """Convert any media input to data URL or return URL as-is."""
        input_type = detect_input_type(input_data)

        if input_type == "data_url":
            return input_data

        if input_type == "url":
            return input_data

        if input_type == "filepath":
            data = Path(input_data).read_bytes()
            mime = detect_mime(data)
            b64 = base64.b64encode(data).decode()
            return f"data:{mime};base64,{b64}"

        if input_type == "base64":
            try:
                raw = base64.b64decode(input_data[:100])
                mime = detect_mime(raw)
            except Exception:
                mime = "application/octet-stream"
            return f"data:{mime};base64,{input_data}"

        return input_data
