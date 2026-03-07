"""LLM adapter factory."""
import logging
from typing import Optional

from app.modules.llm.completions.base import LLMBase

logger = logging.getLogger(__name__)


class LLMOne:
    """Factory for creating LLM adapter instances."""

    CLASS_MAP: dict[str, type] = {}

    @classmethod
    def auto_register(cls):
        """Register all LLMBase subclasses by api_type."""
        from app.modules.llm.completions.openai import LLMOpenAI, LLMOpenAICompatible
        from app.modules.llm.completions.anthropic import LLMAnthropic
        from app.modules.llm.completions.azure import LLMAzure
        from app.modules.llm.completions.gemini import LLMGemini

        for klass in [LLMOpenAI, LLMOpenAICompatible, LLMAnthropic, LLMAzure, LLMGemini]:
            if klass.API_TYPE:
                cls.CLASS_MAP[klass.API_TYPE] = klass
                logger.debug(f"Registered LLM adapter: {klass.API_TYPE} -> {klass.__name__}")

    @classmethod
    def from_database(cls, db_provider, db_model, **kwargs) -> LLMBase:
        """Create from database provider + model records."""
        config = cls._extract_from_database(db_provider, db_model)
        config.update(kwargs)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config)

    @classmethod
    def from_config(cls, model_with_provider: str, **kwargs) -> LLMBase:
        """Create from config string like 'openai#gpt-4o'."""
        config = cls._extract_from_config(model_with_provider)
        config.update(kwargs)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config)

    @staticmethod
    def _extract_from_database(db_provider, db_model) -> dict:
        return {
            "base_url": db_provider.api_endpoint or "",
            "api_key": db_provider.api_key or "",
            "model": db_model.model_id,
            "api_type": db_provider.api_type,
            "provider_id": str(db_provider.id),
        }

    @staticmethod
    def _extract_from_config(model_with_provider: str) -> dict:
        """Parse 'api_type#model@base_url' format."""
        from app.config import settings

        parts = model_with_provider.split("#", 1)
        api_type = parts[0] if len(parts) > 1 else "openai"
        model_part = parts[-1]

        model = model_part
        base_url = ""

        if "@" in model_part:
            model, base_url = model_part.rsplit("@", 1)

        # Try to pull base_url and api_key from settings env vars
        api_key = getattr(settings, f"{api_type.upper().replace('-', '_')}_API_KEY", "")

        return {
            "base_url": base_url or getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key": api_key,
            "model": model,
            "api_type": api_type,
        }

    @classmethod
    def _select_adapter(cls, api_type: str) -> type:
        if not cls.CLASS_MAP:
            cls.auto_register()
        if api_type in cls.CLASS_MAP:
            return cls.CLASS_MAP[api_type]
        logger.warning(f"Unknown api_type '{api_type}', falling back to openai adapter")
        return cls.CLASS_MAP.get("openai", LLMBase)
