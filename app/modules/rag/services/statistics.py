import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import KnowledgeBase, RagDocument, RagChunk

logger = logging.getLogger(__name__)


class StatisticsService:
    async def get_overview(self, db: AsyncSession) -> dict:
        kb_count = (await db.execute(
            select(func.count(KnowledgeBase.id)).where(KnowledgeBase.delete_time.is_(None))
        )).scalar() or 0

        doc_count = (await db.execute(
            select(func.count(RagDocument.id)).where(RagDocument.delete_time.is_(None))
        )).scalar() or 0

        chunk_count = (await db.execute(
            select(func.count(RagChunk.id)).where(RagChunk.delete_time.is_(None))
        )).scalar() or 0

        doc_status = {}
        for status_val in [0, 1, 2, 3]:
            count = (await db.execute(
                select(func.count(RagDocument.id)).where(
                    RagDocument.delete_time.is_(None),
                    RagDocument.status == status_val,
                )
            )).scalar() or 0
            doc_status[str(status_val)] = count

        return {
            "overview": {
                "kb_count": kb_count,
                "doc_count": doc_count,
                "chunk_count": chunk_count,
            },
            "doc_status": doc_status,
        }

    async def get_ranking(
        self,
        db: AsyncSession,
        order_by: str = "doc_count",
        limit: int = 10,
    ) -> list[dict]:
        col = KnowledgeBase.doc_count if order_by == "doc_count" else KnowledgeBase.chunk_count
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.delete_time.is_(None))
            .order_by(col.desc())
            .limit(limit)
        )
        kbs = result.scalars().all()
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "doc_count": kb.doc_count,
                "chunk_count": kb.chunk_count,
            }
            for kb in kbs
        ]

    async def get_kb_stats(self, db: AsyncSession, kb_id: int) -> dict:
        from app.modules.rag.services.knowledge_base import kb_service
        return await kb_service.get_stats(db, kb_id)


statistics_service = StatisticsService()
