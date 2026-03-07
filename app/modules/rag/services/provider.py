import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import EmbeddingProvider
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)

SUPPORTED_EMBEDDING_TYPES = [
    {"type": "doubao", "dimension": 2048, "name": "Doubao Embedding"},
    {"type": "openai", "dimension": 1536, "name": "OpenAI Embedding"},
]

SUPPORTED_VECTOR_DB_TYPES = [
    {"type": "lancedb", "name": "LanceDB", "description": "Local vector database"},
]


class EmbeddingProviderService:
    async def get_list(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 10,
        enabled: int = None,
    ) -> dict:
        query = select(EmbeddingProvider).where(EmbeddingProvider.delete_time.is_(None))
        count_q = select(func.count(EmbeddingProvider.id)).where(EmbeddingProvider.delete_time.is_(None))

        if enabled is not None:
            query = query.where(EmbeddingProvider.enabled == enabled)
            count_q = count_q.where(EmbeddingProvider.enabled == enabled)

        total = (await db.execute(count_q)).scalar()
        result = await db.execute(
            query.order_by(EmbeddingProvider.sort_order).offset((page - 1) * size).limit(size)
        )
        items = result.scalars().all()
        return {"list": items, "total": total, "page": page, "size": size}

    async def get_enabled(self, db: AsyncSession) -> list:
        result = await db.execute(
            select(EmbeddingProvider).where(
                EmbeddingProvider.delete_time.is_(None),
                EmbeddingProvider.enabled == 1,
            ).order_by(EmbeddingProvider.sort_order)
        )
        return result.scalars().all()

    async def get_by_id(self, db: AsyncSession, provider_id: int) -> EmbeddingProvider:
        result = await db.execute(
            select(EmbeddingProvider).where(
                EmbeddingProvider.id == provider_id,
                EmbeddingProvider.delete_time.is_(None),
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            raise NotFoundError(f"Embedding provider {provider_id} not found")
        return p

    async def create(self, db: AsyncSession, data: dict) -> EmbeddingProvider:
        if not data.get("dimension"):
            for t in SUPPORTED_EMBEDDING_TYPES:
                if t["type"] == data.get("type"):
                    data["dimension"] = t["dimension"]
                    break

        p = EmbeddingProvider(**data)
        db.add(p)
        await db.flush()
        await db.refresh(p)
        return p

    async def update(self, db: AsyncSession, provider_id: int, data: dict) -> EmbeddingProvider:
        p = await self.get_by_id(db, provider_id)
        for k, v in data.items():
            if v is not None:
                setattr(p, k, v)
        await db.flush()
        return p

    async def delete(self, db: AsyncSession, provider_id: int) -> int:
        p = await self.get_by_id(db, provider_id)
        from datetime import datetime
        p.delete_time = datetime.utcnow()
        await db.flush()
        return provider_id

    async def init_defaults(self, db: AsyncSession) -> list:
        created = []
        for t in SUPPORTED_EMBEDDING_TYPES:
            existing = await db.execute(
                select(EmbeddingProvider).where(
                    EmbeddingProvider.type == t["type"],
                    EmbeddingProvider.delete_time.is_(None),
                )
            )
            if not existing.scalar_one_or_none():
                p = EmbeddingProvider(
                    name=t["name"],
                    type=t["type"],
                    dimension=t["dimension"],
                    enabled=1,
                )
                db.add(p)
                created.append(t)
        await db.flush()
        return created


embedding_provider_service = EmbeddingProviderService()
