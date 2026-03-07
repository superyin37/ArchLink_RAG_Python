"""SSE stream for PPT module."""
import asyncio
import json
from fastapi.responses import StreamingResponse


class SSEStream:
    """Async queue-backed SSE stream."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

    def send_text(self, text: str):
        if not self._closed:
            self.queue.put_nowait(f"data: {text}\n\n")

    def send_json(self, data: dict):
        if not self._closed:
            payload = json.dumps(data, ensure_ascii=False)
            self.queue.put_nowait(f"data: {payload}\n\n")

    def close(self):
        self._closed = True
        self.queue.put_nowait(None)

    async def generator(self):
        while True:
            data = await self.queue.get()
            if data is None:
                break
            yield data


def create_sse_response(stream: SSEStream) -> StreamingResponse:
    return StreamingResponse(
        stream.generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
