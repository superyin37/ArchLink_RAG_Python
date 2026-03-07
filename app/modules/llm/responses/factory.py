"""Response layer factory - identical to LLMOne but uses ResponseBase subclasses."""
from app.modules.llm.completions.factory import LLMOne
from app.modules.llm.responses.base import ResponseBase


class ResponseAnthropicCached(ResponseBase):
    """Anthropic with cache_control on system messages."""
    API_TYPE = "anthropic"

    async def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 4096,
                   cache_config: dict = None, **kwargs) -> str:
        system_content, user_messages = self._separate_system(messages)
        body = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_content:
            if cache_config:
                body["system"] = [{"type": "text", "text": system_content,
                                   "cache_control": {"type": "ephemeral"}}]
            else:
                body["system"] = system_content
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
            "content-type": "application/json",
        }
        return await self.request(f"{self.base_url}/v1/messages", headers, body)


class ResponseOne(LLMOne):
    """Factory with ResponseBase subclasses for prompt caching."""

    @classmethod
    def auto_register(cls):
        super().auto_register()
        cls.CLASS_MAP["anthropic-cached"] = ResponseAnthropicCached
