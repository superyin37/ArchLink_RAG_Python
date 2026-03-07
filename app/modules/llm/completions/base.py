"""LLM base adapter class."""
import asyncio
import json
import logging
import time
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMBase:
    """Base class for all LLM provider adapters."""

    API_TYPE: str = ""
    SSE_DELIMITER: str = "\n\n"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        user_id: int = None,
        session_id: str = None,
        provider_id: str = None,
        api_type: str = None,
        template_id: int = None,
        tags: list = None,
        **kwargs,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.user_id = user_id
        self.session_id = session_id
        self.provider_id = provider_id
        self.api_type = api_type or self.API_TYPE
        self.template_id = template_id
        self.tags = tags or []
        self.extra_params = kwargs

        # Callbacks
        self.on_token_stream: Optional[Callable[[str], None]] = None
        self.on_thinking: Optional[Callable[[str], None]] = None
        self.on_thinking_complete: Optional[Callable[[], None]] = None
        self.on_content: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

        # Internal state
        self._log_recorder = None
        self._thinking_started = False

    async def chat(self, messages: list, **options) -> str:
        raise NotImplementedError

    async def request(self, url: str, headers: dict, body: dict, **kwargs) -> str:
        from app.modules.llm.utils.log_recorder import LogRecorder

        headers.setdefault("Content-Type", "application/json")

        recorder = LogRecorder(
            provider_id=self.provider_id,
            model=self.model,
            api_type=self.api_type,
            user_id=self.user_id,
            session_id=self.session_id,
            template_id=self.template_id,
            tags=self.tags,
        )
        self._log_recorder = recorder

        try:
            await recorder.start_request(url, headers, body)
            result = await self._do_request(url, headers, body, recorder)
            return result
        except Exception as e:
            await recorder.record_error(e)
            if self.on_error:
                self.on_error(e)
            raise

    async def _do_request(self, url: str, headers: dict, body: dict, recorder) -> str:
        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code >= 400:
                    error_text = await response.aread()
                    raise RuntimeError(
                        f"HTTP {response.status_code}: {error_text.decode()}"
                    )
                result = await self._parse_stream(response, recorder)

        await recorder.complete()
        return result

    async def _parse_stream(self, response, recorder) -> str:
        content_parts = []
        reasoning_parts = []
        buffer = ""

        async for chunk in response.aiter_bytes():
            buffer += chunk.decode("utf-8", errors="replace")
            while self.SSE_DELIMITER in buffer:
                event, buffer = buffer.split(self.SSE_DELIMITER, 1)
                event = event.strip()
                if not event:
                    continue

                parsed = self.message_to_value(event)
                if not parsed:
                    continue

                event_type = parsed.get("type")

                if event_type == "reasoning":
                    text = parsed.get("text", "")
                    if text:
                        self._thinking_started = True
                        reasoning_parts.append(text)
                        recorder.record_content(text, "reasoning")
                        if self.on_thinking:
                            self.on_thinking(text)
                        if self.on_token_stream:
                            self.on_token_stream(text)
                        recorder.record_first_token()

                elif event_type == "text":
                    text = parsed.get("text", "")
                    if text:
                        if self._thinking_started and not content_parts:
                            # Transition from thinking to content
                            if self.on_thinking_complete:
                                self.on_thinking_complete()

                        content_parts.append(text)
                        recorder.record_content(text, "text")
                        if self.on_content:
                            self.on_content(text)
                        if self.on_token_stream:
                            self.on_token_stream(text)
                        recorder.record_first_token()

                elif event_type == "tool_call":
                    data = parsed.get("data", {})
                    # Tool call handling (extend if needed)

                elif event_type == "usage":
                    usage = parsed.get("usage", {})
                    if usage:
                        recorder.record_usage(usage)

        return "".join(content_parts)

    def message_to_value(self, line: str) -> Optional[dict]:
        """Parse SSE data line. Override in subclasses for provider-specific formats."""
        for part in line.split("\n"):
            if part.startswith("data: "):
                data_str = part[6:].strip()
                if data_str == "[DONE]":
                    return None
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # Standard OpenAI format
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    reasoning = delta.get("reasoning_content")

                    if reasoning:
                        return {"type": "reasoning", "text": reasoning}
                    if content:
                        return {"type": "text", "text": content}

                # Usage info
                usage = data.get("usage")
                if usage:
                    return {
                        "type": "usage",
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                            "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
                            "cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
                        },
                    }

        return None

    @staticmethod
    def _separate_system(messages: list) -> tuple[str, list]:
        """Extract system messages from message list."""
        system_parts = []
        user_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                user_messages.append(msg)
        return " ".join(system_parts), user_messages
