"""OpenAI and OpenAI-compatible adapter."""
from app.modules.llm.completions.base import LLMBase


class LLMOpenAI(LLMBase):
    API_TYPE = "openai"

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        thinking: dict = None,
        tools: list = None,
        **kwargs,
    ) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if thinking and thinking.get("type") == "enabled":
            body["thinking"] = thinking
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return await self.request(f"{self.base_url}/chat/completions", headers, body)


class LLMOpenAICompatible(LLMOpenAI):
    """OpenAI-compatible adapter (Qwen, Doubao, etc.) - uses max_tokens."""
    API_TYPE = "openai-compatible"

    async def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 4096,
                   thinking: dict = None, tools: list = None, **kwargs) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return await self.request(f"{self.base_url}/chat/completions", headers, body)
