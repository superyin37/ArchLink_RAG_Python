"""Google Gemini adapter."""
import json
from app.modules.llm.completions.base import LLMBase


class LLMGemini(LLMBase):
    API_TYPE = "google"
    SSE_DELIMITER = "\n\r\n"

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        gemini_contents = self._convert_messages(messages)
        url = (
            f"{self.base_url}/v1beta/models/{self.model}"
            f":streamGenerateContent?alt=sse&key={self.api_key}"
        )
        body = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        return await self.request(url, {}, body)

    def _convert_messages(self, messages: list) -> list:
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "assistant":
                role = "model"
            else:
                role = "user"  # system and user -> user
            content = msg.get("content", "")
            if isinstance(content, str):
                parts = [{"text": content}]
            else:
                parts = content
            contents.append({"role": role, "parts": parts})
        return contents

    def message_to_value(self, line: str):
        for part in line.split("\n"):
            if part.startswith("data: "):
                data_str = part[6:].strip()
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            return {"type": "text", "text": text}

                usage = data.get("usageMetadata")
                if usage:
                    return {
                        "type": "usage",
                        "usage": {
                            "prompt_tokens": usage.get("promptTokenCount", 0),
                            "completion_tokens": usage.get("candidatesTokenCount", 0),
                            "total_tokens": usage.get("totalTokenCount", 0),
                        },
                    }

        return None
