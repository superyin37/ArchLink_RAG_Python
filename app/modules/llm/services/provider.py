"""LLM Provider CRUD service."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMProvider
from app.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

SUPPORTED_API_TYPES = ["openai", "anthropic", "azure", "google", "openai-compatible"]


class ProviderService:
    async def get_list(
        self, db: AsyncSession, page: int = 1, size: int = 10,
        keyword: str = None, status: int = None, api_type: str = None,
    ) -> dict:
        q = select(LLMProvider).where(LLMProvider.delete_time.is_(None))
        if keyword:
            q = q.where(LLMProvider.name.ilike(f"%{keyword}%"))
        if status is not None:
            q = q.where(LLMProvider.status == status)
        if api_type:
            q = q.where(LLMProvider.api_type == api_type)

        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        result = await db.execute(q.offset((page - 1) * size).limit(size))
        return {"list": result.scalars().all(), "total": total}

    async def get_by_id(self, db: AsyncSession, provider_id: int) -> LLMProvider:
        p = await db.get(LLMProvider, provider_id)
        if not p or p.delete_time:
            raise NotFoundError(f"Provider {provider_id} not found")
        return p

    async def create(self, db: AsyncSession, data: dict) -> LLMProvider:
        p = LLMProvider(**data)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p

    async def update(self, db: AsyncSession, provider_id: int, data: dict) -> LLMProvider:
        p = await self.get_by_id(db, provider_id)
        for k, v in data.items():
            setattr(p, k, v)
        await db.commit()
        await db.refresh(p)
        return p

    async def delete(self, db: AsyncSession, provider_id: int):
        p = await self.get_by_id(db, provider_id)
        if p.is_builtin:
            raise ConflictError("Cannot delete built-in provider")
        from datetime import datetime, timezone
        p.delete_time = datetime.now(timezone.utc)
        await db.commit()

    async def update_api_key(self, db: AsyncSession, provider_id: int, api_key: str):
        p = await self.get_by_id(db, provider_id)
        p.api_key = api_key
        await db.commit()

    async def get_api_types(self) -> list[str]:
        return SUPPORTED_API_TYPES


provider_service = ProviderService()
