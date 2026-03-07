import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import RagChunk
from app.modules.rag.services.knowledge_base import kb_service
from app.modules.rag.search.providers import VectorSearchProvider, FulltextSearchProvider
from app.modules.rag.search.fusion import SearchFusion
from app.modules.rag.search.deduplicator import ResultDeduplicator
from app.modules.rag.search.limiter import ResultLimiter
from app.modules.rag.search.context_optimizer import ContextOptimizer
from app.modules.rag.search.tree_assembler import TreeAssembler
from app.modules.rag.chunk.retriever import enhance_retrieve
from app.modules.rag.config import RAGConfig

logger = logging.getLogger(__name__)

vector_provider = VectorSearchProvider()
fulltext_provider = FulltextSearchProvider()


class SearchService:
    async def search(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
        doc_prefilter_doc_ids: list[int] = None,
    ) -> list[dict]:
        kb = await kb_service.get_by_id(db, kb_id)
        results = await vector_provider.search(
            kb, query, top_k, threshold,
            doc_prefilter_doc_ids=doc_prefilter_doc_ids
        )
        return results

    async def hybrid_search(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[dict]:
        kb = await kb_service.get_by_id(db, kb_id)

        vector_results = await vector_provider.search(kb, query, top_k * 2, threshold)
        fulltext_results = await fulltext_provider.search(kb_id, query, top_k * 2)

        if fulltext_results:
            fused = SearchFusion.fuse_rrf([vector_results, fulltext_results], top_k * 2)
        else:
            fused = vector_results

        deduped = ResultDeduplicator.deduplicate(fused)
        return deduped[:top_k]

    async def advanced_search(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
        enhance: bool = True,
        strategies: list[str] = None,
        max_depth: int = 1,
    ) -> list[dict]:
        """Full pipeline: vector + fulltext + fusion + dedup + limit + enhance."""
        kb = await kb_service.get_by_id(db, kb_id)

        vector_results = await vector_provider.search(kb, query, top_k * 2, threshold)
        fulltext_results = await fulltext_provider.search(kb_id, query, top_k * 2)

        if fulltext_results:
            fused = SearchFusion.fuse_rrf([vector_results, fulltext_results], top_k * 2)
        else:
            fused = vector_results

        deduped = ResultDeduplicator.deduplicate(fused)

        if enhance and deduped:
            # Load all chunks for this KB for tree navigation
            result = await db.execute(
                select(RagChunk).where(
                    RagChunk.kb_id == kb_id,
                    RagChunk.delete_time.is_(None),
                )
            )
            all_chunks = result.scalars().all()
            all_by_node_id = {
                c.node_id: {
                    "id": c.id,
                    "content": c.content,
                    "node_id": c.node_id,
                    "parent_id": c.parent_id,
                    "level": c.level,
                    "path": c.path,
                    "heading": c.heading,
                    "doc_id": c.doc_id,
                }
                for c in all_chunks
                if c.node_id
            }
            all_by_path = {}
            for c in all_chunks:
                if c.path:
                    all_by_path.setdefault(c.path, []).append(
                        {
                            "id": c.id,
                            "content": c.content,
                            "node_id": c.node_id,
                            "parent_id": c.parent_id,
                            "level": c.level,
                            "path": c.path,
                            "heading": c.heading,
                            "doc_id": c.doc_id,
                        }
                    )

            deduped = await enhance_retrieve(
                deduped,
                all_by_node_id,
                all_by_path,
                strategies=strategies or RAGConfig.ENHANCE_DEFAULT_STRATEGIES,
                max_depth=max_depth,
                min_sibling_level=RAGConfig.ENHANCE_MIN_SIBLING_LEVEL,
            )

        limited = ResultLimiter.limit(deduped)
        return ContextOptimizer.optimize(limited)

    async def get_context(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
        separator: str = None,
        enhance: bool = True,
        strategies: list[str] = None,
        max_depth: int = 1,
    ) -> str:
        chunks = await self.advanced_search(
            db, kb_id, query, top_k, threshold, enhance, strategies, max_depth
        )
        return TreeAssembler.assemble_context(chunks, separator)

    async def multi_search(
        self,
        db: AsyncSession,
        kb_ids: list[int],
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> dict:
        all_chunks = []
        errors = []

        for kb_id in kb_ids:
            try:
                results = await self.search(db, kb_id, query, top_k, threshold)
                all_chunks.extend(results)
            except Exception as e:
                errors.append({"kb_id": kb_id, "error": str(e)})

        # Fuse and deduplicate across KBs
        deduped = ResultDeduplicator.deduplicate(all_chunks)
        return {"chunks": deduped[:top_k], "errors": errors}

    async def get_capabilities(self) -> dict:
        return {
            "vector": True,
            "fulltext": RAGConfig.MEILISEARCH_ENABLED,
            "hybrid": RAGConfig.MEILISEARCH_ENABLED,
        }


search_service = SearchService()
