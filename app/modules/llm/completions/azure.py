"""Azure OpenAI adapter."""
from app.modules.llm.completions.base import LLMBase


class LLMAzure(LLMBase):
    API_TYPE = "azure"

    async def chat(self, messages: list, **kwargs) -> str:
        deployment = self.model
        api_version = self.extra_params.get("api_version", "2024-08-01-preview")
        url = (
            f"{self.base_url}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={api_version}"
        )
        headers = {"api-key": self.api_key}
        body = {
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            **{k: v for k, v in kwargs.items() if k in ("temperature", "max_tokens", "tools")},
        }
        return await self.request(url, headers, body)
