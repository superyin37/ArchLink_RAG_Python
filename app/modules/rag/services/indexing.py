import logging
from app.modules.rag.embedding import embedding_service
from app.modules.rag.vector import vector_db_service
from app.modules.rag.meilisearch.index_service import meilisearch_index_service
from app.modules.rag.config import RAGConfig

logger = logging.getLogger(__name__)


class VectorIndexProvider:
    async def index_chunks(self, kb_id: int, chunks: list[dict], kb) -> dict:
        texts = [c["content"] for c in chunks]
        try:
            embeddings = await embedding_service.embed(
                texts, model_type=kb.embedding_model, config=kb.embedding_config
            )
        except Exception as e:
            logger.error(f"Embedding failed for kb {kb_id}: {e}")
            return {"success": 0, "failed": len(chunks)}

        dimension = kb.dimension or embedding_service.get_dimension(kb.embedding_model)
        driver = vector_db_service.get_or_create(kb_id, dimension)
        table_name = f"kb_{kb_id}"

        records = []
        for c, emb in zip(chunks, embeddings):
            records.append(
                {
                    "id": f"chunk_{c['id']}",
                    "vector": emb,
                    "document": c["content"],
                    "doc_id": c["doc_id"],
                    "chunk_id": c["id"],
                    "node_id": c.get("node_id") or "",
                    "parent_id": c.get("parent_id") or "",
                    "level": c.get("level", 0),
                    "path": c.get("path") or "",
                    "heading": c.get("heading") or "",
                    "type": "text",
                }
            )

        try:
            driver.add_vectors(table_name, records)
            return {"success": len(records), "failed": 0}
        except Exception as e:
            logger.error(f"Vector indexing failed for kb {kb_id}: {e}")
            return {"success": 0, "failed": len(chunks)}

    async def delete_chunks(self, kb_id: int, chunk_ids: list[int], dimension: int = 2048):
        driver = vector_db_service.get_or_create(kb_id, dimension)
        table_name = f"kb_{kb_id}"
        ids_str = ", ".join(f"'chunk_{cid}'" for cid in chunk_ids)
        try:
            driver.delete(table_name, f"id IN ({ids_str})")
        except Exception as e:
            logger.warning(f"Vector delete failed for kb {kb_id}: {e}")


class FulltextIndexProvider:
    async def is_available(self) -> bool:
        return RAGConfig.MEILISEARCH_ENABLED and meilisearch_index_service.is_available()

    async def index_chunks(self, kb_id: int, chunks: list[dict]) -> dict:
        if not await self.is_available():
            return {"success": 0, "failed": 0, "skipped": len(chunks)}

        await meilisearch_index_service.ensure_index(kb_id)
        docs = [
            {
                "id": str(c["id"]),
                "kb_id": kb_id,
                "doc_id": c["doc_id"],
                "content": c["content"],
                "heading": c.get("heading") or "",
                "node_id": c.get("node_id") or "",
                "parent_id": c.get("parent_id") or "",
                "level": c.get("level", 0),
                "path": c.get("path") or "",
                "chunk_index": c.get("chunk_index", 0),
            }
            for c in chunks
        ]
        try:
            await meilisearch_index_service.index_documents(kb_id, docs)
            return {"success": len(docs), "failed": 0}
        except Exception as e:
            logger.error(f"Fulltext indexing failed for kb {kb_id}: {e}")
            return {"success": 0, "failed": len(chunks)}

    async def delete_chunks(self, kb_id: int, chunk_ids: list[int]):
        if not await self.is_available():
            return
        doc_ids = [str(cid) for cid in chunk_ids]
        await meilisearch_index_service.delete_documents(kb_id, doc_ids)


class IndexingService:
    def __init__(self):
        self.vector_provider = VectorIndexProvider()
        self.fulltext_provider = FulltextIndexProvider()

    async def index_chunks(self, kb_id: int, chunks: list[dict], kb) -> dict:
        results = {}

        vector_result = await self.vector_provider.index_chunks(kb_id, chunks, kb)
        results["vector"] = vector_result

        if await self.fulltext_provider.is_available():
            ft_result = await self.fulltext_provider.index_chunks(kb_id, chunks)
            results["fulltext"] = ft_result

        return results

    async def delete_chunks(self, kb_id: int, chunk_ids: list[int], dimension: int = 2048):
        await self.vector_provider.delete_chunks(kb_id, chunk_ids, dimension)
        if await self.fulltext_provider.is_available():
            await self.fulltext_provider.delete_chunks(kb_id, chunk_ids)


indexing_service = IndexingService()
