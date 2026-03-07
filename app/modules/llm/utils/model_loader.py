"""Model loader - retrieve LLM provider and model from DB."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def load_provider_and_model(
    provider_id: int,
    model_id: int,
    db,
) -> tuple:
    """Load provider and model records from DB."""
    from sqlalchemy import select
    from app.models.llm import LLMProvider, LLMModel

    provider = await db.get(LLMProvider, provider_id)
    if not provider or provider.delete_time:
        from app.exceptions import LLMProviderNotFoundError
        raise LLMProviderNotFoundError(f"Provider {provider_id} not found")

    model = await db.get(LLMModel, model_id)
    if not model or model.delete_time:
        from app.exceptions import LLMModelNotFoundError
        raise LLMModelNotFoundError(f"Model {model_id} not found")

    return provider, model


async def load_model_by_string(model_str: str, db) -> tuple:
    """Load provider + model by 'provider_id:model_id' string or model name."""
    from sqlalchemy import select
    from app.models.llm import LLMProvider, LLMModel

    if ":" in model_str:
        parts = model_str.split(":", 1)
        try:
            p_id = int(parts[0])
            m_id = int(parts[1])
            return await load_provider_and_model(p_id, m_id, db)
        except ValueError:
            pass

    # Handle "provider_id#model_id" format
    if "#" in model_str:
        provider_id_str, model_id_str = model_str.split("#", 1)
        result = await db.execute(
            select(LLMModel).where(
                LLMModel.provider_id == provider_id_str,
                LLMModel.model_id == model_id_str,
                LLMModel.delete_time.is_(None),
                LLMModel.status == 1,
            ).limit(1)
        )
        model = result.scalar_one_or_none()
        if model:
            result = await db.execute(
                select(LLMProvider).where(LLMProvider.provider_id == model.provider_id)
            )
            provider = result.scalar_one_or_none()
            if provider and not provider.delete_time:
                return provider, model

    # Search by model_id string
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.model_id == model_str,
            LLMModel.delete_time.is_(None),
            LLMModel.status == 1,
        ).limit(1)
    )
    model = result.scalar_one_or_none()
    if not model:
        from app.exceptions import LLMModelNotFoundError
        raise LLMModelNotFoundError(f"Model '{model_str}' not found")

    result = await db.execute(
        select(LLMProvider).where(LLMProvider.provider_id == model.provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider or provider.delete_time:
        from app.exceptions import LLMProviderNotFoundError
        raise LLMProviderNotFoundError(f"Provider '{model.provider_id}' not found")
    return provider, model
