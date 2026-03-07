"""LLM Model CRUD service."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMModel
from app.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)


class ModelService:
    async def get_list(
        self, db: AsyncSession, provider_id: int = None, page: int = 1,
        size: int = 10, keyword: str = None, status: int = None,
    ) -> dict:
        q = select(LLMModel).where(LLMModel.delete_time.is_(None))
        if provider_id:
            q = q.where(LLMModel.provider_id == provider_id)
        if keyword:
            q = q.where(LLMModel.model_id.ilike(f"%{keyword}%"))
        if status is not None:
            q = q.where(LLMModel.status == status)

        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        result = await db.execute(q.offset((page - 1) * size).limit(size))
        return {"list": result.scalars().all(), "total": total}

    async def get_by_id(self, db: AsyncSession, model_id: int) -> LLMModel:
        m = await db.get(LLMModel, model_id)
        if not m or m.delete_time:
            raise NotFoundError(f"Model {model_id} not found")
        return m

    async def get_by_provider_and_model(
        self, db: AsyncSession, provider_id: int, model_id_str: str
    ) -> LLMModel:
        result = await db.execute(
            select(LLMModel).where(
                LLMModel.provider_id == provider_id,
                LLMModel.model_id == model_id_str,
                LLMModel.delete_time.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, data: dict) -> LLMModel:
        m = LLMModel(**data)
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return m

    async def update(self, db: AsyncSession, model_id: int, data: dict) -> LLMModel:
        m = await self.get_by_id(db, model_id)
        for k, v in data.items():
            setattr(m, k, v)
        await db.commit()
        await db.refresh(m)
        return m

    async def delete(self, db: AsyncSession, model_id: int):
        m = await self.get_by_id(db, model_id)
        if m.is_builtin:
            raise ConflictError("Cannot delete built-in model")
        from datetime import datetime, timezone
        m.delete_time = datetime.now(timezone.utc)
        await db.commit()

    async def deprecate(
        self, db: AsyncSession, model_id: int, replacement_id: str = None
    ):
        m = await self.get_by_id(db, model_id)
        m.status = 0
        if replacement_id:
            m.replacement_model_id = replacement_id
        await db.commit()

    async def get_by_provider_grouped(self, db: AsyncSession) -> list:
        result = await db.execute(
            select(LLMModel).where(LLMModel.delete_time.is_(None))
            .order_by(LLMModel.provider_id, LLMModel.model_id)
        )
        models = result.scalars().all()
        grouped: dict[int, list] = {}
        for m in models:
            grouped.setdefault(m.provider_id, []).append(m)
        return [{"provider_id": pid, "models": mlist} for pid, mlist in grouped.items()]


model_service = ModelService()
