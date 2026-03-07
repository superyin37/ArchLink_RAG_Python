"""Anthropic Claude adapter."""
import json
from app.modules.llm.completions.base import LLMBase


class LLMAnthropic(LLMBase):
    API_TYPE = "anthropic"

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        system_content, user_messages = self._separate_system(messages)
        body = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_content:
            body["system"] = system_content

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        return await self.request(f"{self.base_url}/v1/messages", headers, body)

    def message_to_value(self, line: str):
        event_type = None
        data_str = None

        for part in line.split("\n"):
            if part.startswith("event: "):
                event_type = part[7:].strip()
            elif part.startswith("data: "):
                data_str = part[6:].strip()

        if not data_str:
            return None

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return {"type": "text", "text": delta.get("text", "")}
            if delta.get("type") == "thinking_delta":
                return {"type": "reasoning", "text": delta.get("thinking", "")}

        if event_type == "message_delta":
            usage = data.get("usage", {})
            if usage:
                return {
                    "type": "usage",
                    "usage": {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                    },
                }

        return None
