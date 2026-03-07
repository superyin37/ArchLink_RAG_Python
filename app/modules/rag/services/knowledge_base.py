import logging
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import KnowledgeBase, RagDocument, RagChunk
from app.exceptions import KnowledgeBaseNotFoundError

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    async def get_list(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 10,
        keyword: str = None,
        status: int = None,
    ) -> dict:
        query = select(KnowledgeBase).where(KnowledgeBase.delete_time.is_(None))
        count_query = select(func.count(KnowledgeBase.id)).where(KnowledgeBase.delete_time.is_(None))

        if keyword:
            query = query.where(KnowledgeBase.name.ilike(f"%{keyword}%"))
            count_query = count_query.where(KnowledgeBase.name.ilike(f"%{keyword}%"))
        if status is not None:
            query = query.where(KnowledgeBase.status == status)
            count_query = count_query.where(KnowledgeBase.status == status)

        total = (await db.execute(count_query)).scalar()
        result = await db.execute(query.offset((page - 1) * size).limit(size))
        items = result.scalars().all()

        return {"list": items, "total": total, "page": page, "size": size}

    async def get_by_id(self, db: AsyncSession, kb_id: int) -> KnowledgeBase:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.delete_time.is_(None),
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise KnowledgeBaseNotFoundError(kb_id)
        return kb

    async def create(self, db: AsyncSession, data: dict) -> KnowledgeBase:
        from app.modules.rag.embedding import embedding_service, SUPPORTED_MODELS

        dimension = data.get("dimension")
        if not dimension:
            dimension = embedding_service.get_dimension(data.get("embedding_model", "doubao"))
        data["dimension"] = dimension

        kb = KnowledgeBase(**data)
        db.add(kb)
        await db.flush()
        await db.refresh(kb)
        return kb

    async def update(self, db: AsyncSession, kb_id: int, data: dict) -> KnowledgeBase:
        kb = await self.get_by_id(db, kb_id)
        for key, value in data.items():
            if value is not None:
                setattr(kb, key, value)
        await db.flush()
        return kb

    async def delete(self, db: AsyncSession, kb_id: int) -> int:
        kb = await self.get_by_id(db, kb_id)
        from datetime import datetime
        kb.delete_time = datetime.utcnow()
        await db.flush()
        return kb_id

    async def get_stats(self, db: AsyncSession, kb_id: int) -> dict:
        kb = await self.get_by_id(db, kb_id)

        total_chars = (
            await db.execute(
                select(func.sum(RagChunk.char_count)).where(
                    RagChunk.kb_id == kb_id,
                    RagChunk.delete_time.is_(None),
                )
            )
        ).scalar() or 0

        return {
            "id": kb.id,
            "name": kb.name,
            "doc_count": kb.doc_count,
            "chunk_count": kb.chunk_count,
            "total_chars": total_chars,
            "embedding_model": kb.embedding_model,
            "vector_db_type": kb.vector_db_type,
            "dimension": kb.dimension,
        }

    async def update_counts(self, db: AsyncSession, kb_id: int):
        """Recalculate doc_count and chunk_count."""
        doc_count = (
            await db.execute(
                select(func.count(RagDocument.id)).where(
                    RagDocument.kb_id == kb_id,
                    RagDocument.delete_time.is_(None),
                    RagDocument.status == 2,
                )
            )
        ).scalar() or 0

        chunk_count = (
            await db.execute(
                select(func.count(RagChunk.id)).where(
                    RagChunk.kb_id == kb_id,
                    RagChunk.delete_time.is_(None),
                )
            )
        ).scalar() or 0

        await db.execute(
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(doc_count=doc_count, chunk_count=chunk_count)
        )


kb_service = KnowledgeBaseService()
