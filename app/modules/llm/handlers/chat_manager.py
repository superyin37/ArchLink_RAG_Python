"""Chat manager - orchestrate streaming LLM responses."""
import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages a single streaming chat completion request."""

    def __init__(
        self,
        provider,
        model,
        messages: list,
        chat_id: Optional[str] = None,
        user_id: Optional[int] = None,
        save_messages: bool = True,
        options: dict = None,
        db=None,
    ):
        self.provider = provider
        self.model = model
        self.messages = messages
        self.chat_id = chat_id
        self.user_id = user_id
        self.save_messages = save_messages
        self.options = options or {}
        self.db = db

        self._token_queue: asyncio.Queue = asyncio.Queue()
        self._done = False
        self._error: Optional[Exception] = None
        self._full_response = ""

    async def run_and_stream(self) -> AsyncGenerator[str, None]:
        """Start LLM call in background and yield SSE events."""
        from app.modules.llm.completions.factory import LLMOne
        from app.modules.llm.utils.stream import format_sse, format_sse_done, format_sse_error

        llm = LLMOne.from_database(
            self.provider, self.model,
            user_id=self.user_id,
            session_id=self.chat_id,
        )

        tokens: list[str] = []
        done_event = asyncio.Event()

        def on_token(text: str):
            tokens.append(text)
            self._token_queue.put_nowait(text)

        def on_error(err: Exception):
            self._error = err
            done_event.set()
            self._token_queue.put_nowait(None)  # sentinel

        llm.on_token_stream = on_token
        llm.on_error = on_error

        # Start LLM call in background
        async def _call():
            try:
                self._full_response = await llm.chat(self.messages, **self.options)
            except Exception as e:
                self._error = e
            finally:
                self._done = True
                self._token_queue.put_nowait(None)  # sentinel

        task = asyncio.create_task(_call())

        # Stream tokens
        try:
            while True:
                token = await self._token_queue.get()
                if token is None:
                    break
                yield format_sse({"text": token})

            if self._error:
                yield format_sse_error(str(self._error))
            else:
                yield format_sse_done()

        finally:
            await task

        # Save assistant message after streaming
        if self.save_messages and self.chat_id and self.db and not self._error:
            from app.modules.llm.services.message import message_service
            try:
                usage = (llm._log_recorder.usage if llm._log_recorder else {})
                await message_service.save_assistant_message(
                    self.db, self.chat_id,
                    self._full_response or "".join(tokens),
                    model=self.model.model_id if self.model else None,
                    token_usage=usage,
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant message: {e}")


async def stream_chat_response(
    provider,
    model,
    messages: list,
    chat_id: str = None,
    user_id: int = None,
    save_messages: bool = True,
    options: dict = None,
    db=None,
) -> AsyncGenerator[str, None]:
    """Convenience function for streaming a chat response."""
    manager = ChatManager(
        provider=provider,
        model=model,
        messages=messages,
        chat_id=chat_id,
        user_id=user_id,
        save_messages=save_messages,
        options=options,
        db=db,
    )
    async for chunk in manager.run_and_stream():
        yield chunk
