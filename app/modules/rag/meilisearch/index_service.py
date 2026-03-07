import asyncio
import logging
from app.modules.rag.meilisearch.client import get_meilisearch_client

logger = logging.getLogger(__name__)


def _index_name(kb_id: int) -> str:
    return f"kb_{kb_id}"


class MeilisearchIndexService:
    def is_available(self) -> bool:
        return get_meilisearch_client() is not None

    async def ensure_index(self, kb_id: int):
        client = get_meilisearch_client()
        if not client:
            return
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: client.create_index(index_name, {"primaryKey": "id"}))
            await loop.run_in_executor(
                None,
                lambda: client.index(index_name).update_settings({
                    "searchableAttributes": ["content", "heading"],
                    "filterableAttributes": ["doc_id", "kb_id", "level"],
                    "sortableAttributes": ["chunk_index"],
                }),
            )
        except Exception as e:
            logger.warning(f"Meilisearch ensure_index failed: {e}")

    async def index_documents(self, kb_id: int, docs: list[dict]):
        client = get_meilisearch_client()
        if not client:
            return
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: client.index(index_name).add_documents(docs),
            )
        except Exception as e:
            logger.warning(f"Meilisearch index_documents failed: {e}")

    async def delete_documents(self, kb_id: int, doc_ids: list[str]):
        client = get_meilisearch_client()
        if not client:
            return
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: client.index(index_name).delete_documents(doc_ids),
            )
        except Exception as e:
            logger.warning(f"Meilisearch delete_documents failed: {e}")

    async def search(self, kb_id: int, query: str, limit: int = 10, offset: int = 0) -> dict:
        client = get_meilisearch_client()
        if not client:
            return {"hits": [], "total_hits": 0, "processing_time_ms": 0}
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.index(index_name).search(query, {"limit": limit, "offset": offset}),
            )
            return {
                "hits": result.get("hits", []),
                "total_hits": result.get("estimatedTotalHits", 0),
                "processing_time_ms": result.get("processingTimeMs", 0),
            }
        except Exception as e:
            logger.warning(f"Meilisearch search failed: {e}")
            return {"hits": [], "total_hits": 0, "processing_time_ms": 0}

    async def delete_index(self, kb_id: int):
        client = get_meilisearch_client()
        if not client:
            return
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: client.delete_index(index_name)
            )
        except Exception as e:
            logger.warning(f"Meilisearch delete_index failed: {e}")

    async def get_stats(self, kb_id: int) -> dict:
        client = get_meilisearch_client()
        if not client:
            return {}
        try:
            index_name = _index_name(kb_id)
            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(
                None, lambda: client.index(index_name).get_stats()
            )
            result = stats.__dict__ if hasattr(stats, "__dict__") else dict(stats)
            # Ensure nested objects are serializable
            return {
                k: (v.__dict__ if hasattr(v, "__dict__") else v)
                for k, v in result.items()
            }
        except Exception as e:
            logger.warning(f"Meilisearch get_stats failed: {e}")
            return {}


meilisearch_index_service = MeilisearchIndexService()
