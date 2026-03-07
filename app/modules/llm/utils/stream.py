"""SSE stream helpers."""
import json
from typing import AsyncGenerator


async def stream_text_events(
    text_chunks: AsyncGenerator[str, None],
    event: str = "message",
) -> AsyncGenerator[str, None]:
    """Wrap text chunks as SSE events."""
    async for chunk in text_chunks:
        yield f"event: {event}\ndata: {json.dumps({'text': chunk})}\n\n"
    yield f"event: done\ndata: {json.dumps({'done': True})}\n\n"


def format_sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_sse_done() -> str:
    return "event: done\ndata: {\"done\": true}\n\n"


def format_sse_error(message: str) -> str:
    return f"event: error\ndata: {json.dumps({'error': message})}\n\n"
