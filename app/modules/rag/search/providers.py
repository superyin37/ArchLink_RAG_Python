import logging
from typing import TYPE_CHECKING

from app.modules.rag.config import RAGConfig
from app.modules.rag.embedding import embedding_service
from app.modules.rag.vector import vector_db_service
from app.modules.rag.vector.mean_vector import load_stats, apply_all_but_top
from app.modules.rag.meilisearch.index_service import meilisearch_index_service
from app.modules.rag.search.keyword_extractor import KeywordExtractor
from app.modules.rag.search.threshold import ThresholdAdapter
from app.modules.rag.search.fusion import SearchFusion
from app.modules.rag.search.deduplicator import ResultDeduplicator
from app.modules.rag.search.limiter import ResultLimiter
from app.modules.rag.search.context_optimizer import ContextOptimizer
from app.modules.rag.search.tree_assembler import TreeAssembler

logger = logging.getLogger(__name__)


def _format_vector_result(r: dict, source: str = "vector") -> dict:
    score = 1.0 - r.get("_distance", 0)
    return {
        "id": int(r.get("chunk_id")),
        "content": r.get("document", ""),
        "score": round(score, 4),
        "heading": r.get("heading", ""),
        "doc_id": r.get("doc_id"),
        "node_id": r.get("node_id", ""),
        "parent_id": r.get("parent_id", ""),
        "level": r.get("level", 0),
        "path": r.get("path", ""),
        "source": source,
        "is_hit": True,
    }


def _format_fulltext_result(hit: dict, score: float, source: str = "fulltext") -> dict:
    return {
        "id": int(hit.get("id")),
        "content": hit.get("content", ""),
        "score": round(score, 4),
        "heading": hit.get("heading", ""),
        "doc_id": hit.get("doc_id"),
        "node_id": hit.get("node_id", ""),
        "parent_id": hit.get("parent_id", ""),
        "level": hit.get("level", 0),
        "path": hit.get("path", ""),
        "source": source,
        "is_hit": True,
    }


class VectorSearchProvider:
    async def search(
        self,
        kb,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
        use_adaptive_threshold: bool = False,
        doc_prefilter_doc_ids: list[int] = None,
    ) -> list[dict]:
        query_vectors = await embedding_service.embed(
            [query], model_type=kb.embedding_model, config=kb.embedding_config
        )
        query_vector = query_vectors[0]

        # All-but-the-Top: 若已计算统计数据则对 query 向量做去均值+去主成分变换
        stats = load_stats(kb.id)
        if stats:
            query_vector = apply_all_but_top(query_vector, stats)

        where = None
        if doc_prefilter_doc_ids:
            ids_str = ", ".join(str(d) for d in doc_prefilter_doc_ids)
            where = f"doc_id IN ({ids_str})"

        dimension = kb.dimension or embedding_service.get_dimension(kb.embedding_model)
        driver = vector_db_service.get_or_create(kb.id, dimension)
        table_name = f"kb_{kb.id}"

        try:
            raw_results = driver.search(table_name, query_vector, top_k * 3, where)
        except Exception as e:
            logger.warning(f"Vector search failed for kb {kb.id}: {e}")
            return []

        results = [
            _format_vector_result(r) for r in raw_results
            if (1.0 - r.get("_distance", 1)) >= threshold
        ]

        if use_adaptive_threshold and results:
            adapted = ThresholdAdapter.adapt(results)
            results = [r for r in results if r["score"] >= adapted]

        return results[:top_k]


class FulltextSearchProvider:
    async def search(self, kb_id: int, query: str, top_k: int = 5) -> list[dict]:
        if not RAGConfig.MEILISEARCH_ENABLED:
            return []

        keywords = KeywordExtractor.extract(query)
        search_query = " ".join(keywords) if keywords else query

        result = await meilisearch_index_service.search(kb_id, search_query, limit=top_k)
        hits = result.get("hits", [])

        k = 60
        scored = []
        for rank, hit in enumerate(hits):
            score = 1.0 / (k + rank + 1)
            scored.append(_format_fulltext_result(hit, score))

        return scored

    async def is_available(self) -> bool:
        return RAGConfig.MEILISEARCH_ENABLED and meilisearch_index_service.is_available()
