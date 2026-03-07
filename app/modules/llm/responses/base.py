"""Response layer base class (extends LLMBase with prompt caching support)."""
from app.modules.llm.completions.base import LLMBase


class ResponseBase(LLMBase):
    """Extends LLMBase with prompt caching support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_read_tokens: int = 0
        self._cache_creation_tokens: int = 0

    def _apply_cache_control(self, messages: list, cache_config: dict) -> list:
        """Apply provider-specific cache control - override in subclasses."""
        return messages

    def get_cache_stats(self) -> dict:
        total_cached = self._cache_read_tokens
        return {
            "cache_read_tokens": self._cache_read_tokens,
            "cache_creation_tokens": self._cache_creation_tokens,
            "hit": total_cached > 0,
        }

    def record_usage(self, usage: dict):
        self._cache_read_tokens = usage.get("cache_read_tokens", 0)
        self._cache_creation_tokens = usage.get("cache_creation_tokens", 0)
