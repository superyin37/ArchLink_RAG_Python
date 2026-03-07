"""Call lifecycle logger / recorder."""
import logging
import time
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_SENSITIVE_HEADERS = {"authorization", "api-key", "x-api-key"}


def _sanitize_headers(headers: dict) -> dict:
    return {
        k: ("***" if k.lower() in _SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


class LogRecorder:
    """Records LLM call lifecycle metrics and persists to DB."""

    def __init__(
        self,
        provider_id: Optional[str] = None,
        model: str = "",
        api_type: str = "",
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        template_id: Optional[int] = None,
        tags: Optional[list] = None,
    ):
        self.request_id = str(uuid4())
        self.provider_id = provider_id
        self.model = model
        self.api_type = api_type
        self.user_id = user_id
        self.session_id = session_id
        self.template_id = template_id
        self.tags = tags or []

        self.request_start_time: int = 0
        self.first_token_time: Optional[int] = None
        self.first_token_duration: Optional[int] = None
        self._first_token_recorded = False

        self.content_parts: list[str] = []
        self.reasoning_parts: list[str] = []
        self.usage: dict = {}
        self._log_id: Optional[int] = None

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    async def start_request(self, url: str, headers: dict, body: dict):
        self.request_start_time = self._now_ms()
        try:
            from app.modules.llm.services.call_log import call_log_service

            data = {
                "request_id": self.request_id,
                "provider_id": self.provider_id or "",
                "model": self.model or "",
                "api_type": self.api_type,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "template_id": self.template_id,
                "tags": self.tags,
                "request_url": url,
                "request_headers": _sanitize_headers(headers),
                "request_body": body,
                "status": "pending",
                "is_success": False,
            }
            log = await call_log_service.create(data)
            self._log_id = log.id if log else None
        except Exception as e:
            logger.warning(f"Failed to create call log: {e}")

    def record_first_token(self):
        if not self._first_token_recorded:
            self._first_token_recorded = True
            self.first_token_time = self._now_ms()
            self.first_token_duration = self.first_token_time - self.request_start_time

    def record_content(self, text: str, content_type: str = "text"):
        if content_type == "reasoning":
            self.reasoning_parts.append(text)
        else:
            self.content_parts.append(text)

    def record_usage(self, usage: dict):
        self.usage = usage

    async def complete(self):
        total_duration = self._now_ms() - self.request_start_time
        try:
            from app.modules.llm.services.call_log import call_log_service

            update_data = {
                "status": "success",
                "is_success": True,
                "response_text": "".join(self.content_parts),
                "reasoning_text": "".join(self.reasoning_parts),
                "total_duration": total_duration,
                "first_token_duration": self.first_token_duration,
                **self.usage,
            }
            await call_log_service.update(self.request_id, update_data)
        except Exception as e:
            logger.warning(f"Failed to update call log on complete: {e}")

    async def record_error(self, error: Exception):
        total_duration = self._now_ms() - self.request_start_time
        try:
            from app.modules.llm.services.call_log import call_log_service

            await call_log_service.update(self.request_id, {
                "status": "error",
                "is_success": False,
                "error_message": str(error),
                "total_duration": total_duration,
            })
        except Exception as e:
            logger.warning(f"Failed to update call log on error: {e}")
