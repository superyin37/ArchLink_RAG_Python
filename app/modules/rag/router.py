import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.response_wrapper import R
from app.schemas.rag import (
    KBCreate, KBUpdate, SearchRequest, MultiSearchRequest,
    ContextSearchRequest, DocumentTextCreate,
    EmbeddingProviderCreate, EmbeddingProviderUpdate,
    MeilisearchSearchRequest, CompareSearchRequest,
)
from app.modules.rag.services.knowledge_base import kb_service
from app.modules.rag.services.document import doc_service
from app.modules.rag.services.search import search_service
from app.modules.rag.services.provider import (
    embedding_provider_service,
    SUPPORTED_EMBEDDING_TYPES,
    SUPPORTED_VECTOR_DB_TYPES,
)
from app.modules.rag.services.statistics import statistics_service
from app.modules.rag.meilisearch.index_service import meilisearch_index_service
from app.modules.rag.search import SearchFusion
from app.modules.rag.vector.mean_vector import compute_and_save_statistics
from app.modules.rag.vector import vector_db_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Knowledge Base ────────────────────────────────────────────────────────────

@router.get("/kb")
async def list_kb(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    status: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await kb_service.get_list(db, page, size, keyword, status)
    return R.page(
        items=[_kb_to_dict(kb) for kb in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/kb/{kb_id}")
async def get_kb(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await kb_service.get_by_id(db, kb_id)
    return R.success(_kb_to_dict(kb))


@router.get("/kb/{kb_id}/stats")
async def get_kb_stats(kb_id: int, db: AsyncSession = Depends(get_db)):
    stats = await kb_service.get_stats(db, kb_id)
    return R.success(stats)


@router.post("/kb/{kb_id}/vector-stats")
async def build_vector_stats(
    kb_id: int,
    n_components: int = Query(4, ge=1, le=16, description="要去除的主成分数量，建议从4开始"),
    db: AsyncSession = Depends(get_db),
):
    """
    计算并持久化知识库的向量统计数据（均值 + 主成分），用于 All-but-the-Top 去各向异性。
    知识库建立完成后或批量重建索引后调用一次，之后向量搜索自动生效。
    """
    kb = await kb_service.get_by_id(db, kb_id)
    dimension = kb.dimension or 2048
    driver = vector_db_service.get_or_create(kb_id, dimension)
    stats = await compute_and_save_statistics(kb_id, driver, n_components=n_components)
    return R.success({
        "kb_id": kb_id,
        "n_vectors": stats["n_vectors"],
        "dimension": stats["dimension"],
        "n_components": stats["n_components"],
    })


@router.post("/kb")
async def create_kb(body: KBCreate, db: AsyncSession = Depends(get_db)):
    kb = await kb_service.create(db, body.model_dump(exclude_none=True))
    return R.success(_kb_to_dict(kb))


@router.put("/kb/{kb_id}")
async def update_kb(kb_id: int, body: KBUpdate, db: AsyncSession = Depends(get_db)):
    await kb_service.update(db, kb_id, body.model_dump(exclude_none=True))
    return R.success({"id": kb_id})


@router.delete("/kb/{kb_id}")
async def delete_kb(kb_id: int, db: AsyncSession = Depends(get_db)):
    await kb_service.delete(db, kb_id)
    return R.success({"id": kb_id})


# ─── Document ──────────────────────────────────────────────────────────────────

@router.get("/document/kb/{kb_id}")
async def list_documents(
    kb_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await doc_service.get_list(db, kb_id, page, size, status)
    return R.page(
        items=[_doc_to_dict(d) for d in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/document/{doc_id}")
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_by_id(db, doc_id)
    return R.success(_doc_to_dict(doc))


@router.get("/document/{doc_id}/chunks")
async def get_chunks(doc_id: int, db: AsyncSession = Depends(get_db)):
    chunks = await doc_service.get_chunks(db, doc_id)
    return R.success([_chunk_to_dict(c) for c in chunks])


@router.get("/document/{doc_id}/preview")
async def preview_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_by_id(db, doc_id)
    chunks = await doc_service.get_chunks(db, doc_id)
    content = "\n\n".join(c.content for c in chunks)
    return R.success({
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "content": content,
        "chunk_count": doc.chunk_count,
        "char_count": doc.char_count,
    })


@router.get("/document/{doc_id}/download")
async def download_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import FileResponse
    from pathlib import Path
    doc = await doc_service.get_by_id(db, doc_id)
    if not doc.file_path or not Path(doc.file_path).exists():
        from app.exceptions import NotFoundError
        raise NotFoundError("Document file not found")
    return FileResponse(doc.file_path, filename=doc.filename)


@router.post("/document/upload-preview")
async def upload_preview(
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(0),
):
    result = await doc_service.preview_upload(file, chunk_size)
    return R.success(result)


@router.post("/document/upload")
async def upload_document(
    kb_id: int = Form(...),
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(0),
    db: AsyncSession = Depends(get_db),
):
    doc = await doc_service.upload_and_process(db, kb_id, file, chunk_size, chunk_overlap)
    return R.success(_doc_to_dict(doc))


@router.post("/document/text")
async def create_document_from_text(
    body: DocumentTextCreate,
    db: AsyncSession = Depends(get_db),
):
    doc = await doc_service.create_from_text(
        db, body.kb_id, body.filename, body.content, body.chunk_size
    )
    return R.success(_doc_to_dict(doc))


@router.delete("/document/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    await doc_service.delete(db, doc_id)
    return R.success({"id": doc_id})


# ─── Search ────────────────────────────────────────────────────────────────────

@router.post("/search")
async def search(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    results = await search_service.search(
        db, body.kb_id, body.query, body.top_k, body.threshold
    )
    return R.success(results)


@router.post("/search/multi")
async def multi_search(body: MultiSearchRequest, db: AsyncSession = Depends(get_db)):
    result = await search_service.multi_search(
        db, body.kb_ids, body.query, body.top_k, body.threshold
    )
    return R.success(result)


@router.post("/search/context")
async def context_search(body: ContextSearchRequest, db: AsyncSession = Depends(get_db)):
    context = await search_service.get_context(
        db,
        body.kb_id,
        body.query,
        body.top_k,
        body.threshold,
        body.separator,
        body.enhance,
        body.strategies,
        body.max_depth,
    )
    return R.success({"context": context})


@router.get("/search/capabilities")
async def get_capabilities():
    caps = await search_service.get_capabilities()
    return R.success(caps)


# ─── Meilisearch ───────────────────────────────────────────────────────────────

@router.get("/meilisearch/stats/{kb_id}")
async def ms_stats(kb_id: int):
    stats = await meilisearch_index_service.get_stats(kb_id)
    return R.success(stats)


@router.post("/meilisearch/index/{kb_id}")
async def ms_create_index(kb_id: int, db: AsyncSession = Depends(get_db)):
    await meilisearch_index_service.ensure_index(kb_id)
    stats = await meilisearch_index_service.get_stats(kb_id)
    return R.success({"success": True, "stats": stats})


@router.delete("/meilisearch/index/{kb_id}")
async def ms_delete_index(kb_id: int):
    await meilisearch_index_service.delete_index(kb_id)
    return R.success({"success": True})


@router.post("/meilisearch/rebuild/{kb_id}")
async def ms_rebuild_index(kb_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.rag import RagChunk
    from app.modules.rag.services.indexing import FulltextIndexProvider

    await meilisearch_index_service.delete_index(kb_id)
    await meilisearch_index_service.ensure_index(kb_id)

    result = await db.execute(
        select(RagChunk).where(
            RagChunk.kb_id == kb_id,
            RagChunk.delete_time.is_(None),
        )
    )
    chunks = result.scalars().all()

    ft_provider = FulltextIndexProvider()
    chunk_dicts = [
        {
            "id": c.id, "doc_id": c.doc_id, "content": c.content,
            "heading": c.heading or "", "node_id": c.node_id or "",
            "parent_id": c.parent_id or "", "level": c.level,
            "path": c.path or "", "chunk_index": c.chunk_index,
        }
        for c in chunks
    ]
    result_info = await ft_provider.index_chunks(kb_id, chunk_dicts)
    return R.success(result_info)


@router.post("/meilisearch/search/{kb_id}")
async def ms_search(kb_id: int, body: MeilisearchSearchRequest):
    result = await meilisearch_index_service.search(
        kb_id, body.query, body.limit, body.offset
    )
    return R.success(result)


@router.post("/meilisearch/compare/{kb_id}")
async def ms_compare(kb_id: int, body: CompareSearchRequest, db: AsyncSession = Depends(get_db)):
    from app.modules.rag.search.providers import VectorSearchProvider, FulltextSearchProvider
    import time

    kb = await kb_service.get_by_id(db, kb_id)
    top_k = body.top_k

    t0 = time.time()
    vector_res = await VectorSearchProvider().search(kb, body.query, top_k)
    fulltext_res = await FulltextSearchProvider().search(kb_id, body.query, top_k)
    hybrid_res = SearchFusion.fuse_rrf([vector_res, fulltext_res], top_k)
    total_time = int((time.time() - t0) * 1000)

    return R.success({
        "vector": vector_res,
        "meilisearch": fulltext_res,
        "hybrid": hybrid_res,
        "total_time": total_time,
    })


# ─── Embedding Provider ────────────────────────────────────────────────────────

@router.get("/provider")
async def list_providers(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    enabled: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await embedding_provider_service.get_list(db, page, size, enabled)
    return R.page(
        items=[_provider_to_dict(p) for p in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/provider/enabled")
async def list_enabled_providers(db: AsyncSession = Depends(get_db)):
    providers = await embedding_provider_service.get_enabled(db)
    return R.success([_provider_to_dict(p) for p in providers])


@router.get("/provider/supported")
async def get_supported_types():
    return R.success(SUPPORTED_EMBEDDING_TYPES)


@router.get("/provider/vector-db-types")
async def get_vector_db_types():
    return R.success(SUPPORTED_VECTOR_DB_TYPES)


@router.get("/provider/{provider_id}")
async def get_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await embedding_provider_service.get_by_id(db, provider_id)
    return R.success(_provider_to_dict(p))


@router.post("/provider")
async def create_provider(body: EmbeddingProviderCreate, db: AsyncSession = Depends(get_db)):
    p = await embedding_provider_service.create(db, body.model_dump(exclude_none=True))
    return R.success(_provider_to_dict(p))


@router.post("/provider/init")
async def init_providers(db: AsyncSession = Depends(get_db)):
    created = await embedding_provider_service.init_defaults(db)
    return R.success({"created": created})


@router.put("/provider/{provider_id}")
async def update_provider(
    provider_id: int, body: EmbeddingProviderUpdate, db: AsyncSession = Depends(get_db)
):
    p = await embedding_provider_service.update(db, provider_id, body.model_dump(exclude_none=True))
    return R.success(_provider_to_dict(p))


@router.delete("/provider/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    await embedding_provider_service.delete(db, provider_id)
    return R.success({"id": provider_id})


# ─── Statistics ────────────────────────────────────────────────────────────────

@router.get("/statistics/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    stats = await statistics_service.get_overview(db)
    return R.success(stats)


@router.get("/statistics/ranking")
async def get_ranking(
    order_by: str = Query("doc_count"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    ranking = await statistics_service.get_ranking(db, order_by, limit)
    return R.success(ranking)


@router.get("/statistics/kb/{kb_id}")
async def get_kb_statistics(kb_id: int, db: AsyncSession = Depends(get_db)):
    stats = await statistics_service.get_kb_stats(db, kb_id)
    return R.success(stats)


# ─── Visual ────────────────────────────────────────────────────────────────────

@router.get("/visual/document/{doc_id}/tree")
async def get_document_tree(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_by_id(db, doc_id)
    chunks = await doc_service.get_chunks(db, doc_id)

    # Build tree structure
    chunk_map = {c.node_id: _chunk_to_dict(c) for c in chunks if c.node_id}
    root_chunks = [c for c in chunks if not c.parent_id]

    return R.success({
        "document": _doc_to_dict(doc),
        "tree": [_chunk_to_dict(c) for c in root_chunks],
        "stats": {
            "depth": max((c.level for c in chunks), default=0) + 1,
            "total_chunks": len(chunks),
        },
    })


@router.get("/visual/kb/{kb_id}/structure")
async def get_kb_structure(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await kb_service.get_by_id(db, kb_id)
    docs_result = await doc_service.get_list(db, kb_id, page=1, size=100)
    docs = docs_result["list"]

    return R.success({
        "knowledge_base": _kb_to_dict(kb),
        "documents": [_doc_to_dict(d) for d in docs],
        "stats": {
            "total_documents": len(docs),
            "chunk_count": kb.chunk_count,
        },
    })


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _kb_to_dict(kb) -> dict:
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "embedding_model": kb.embedding_model,
        "vector_db_type": kb.vector_db_type,
        "dimension": kb.dimension,
        "doc_count": kb.doc_count,
        "chunk_count": kb.chunk_count,
        "status": kb.status,
        "create_time": kb.create_time.isoformat() if kb.create_time else None,
        "update_time": kb.update_time.isoformat() if kb.update_time else None,
    }


def _doc_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "kb_id": doc.kb_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "char_count": doc.char_count,
        "status": doc.status,
        "error_msg": doc.error_msg,
        "create_time": doc.create_time.isoformat() if doc.create_time else None,
        "update_time": doc.update_time.isoformat() if doc.update_time else None,
    }


def _chunk_to_dict(c) -> dict:
    return {
        "id": c.id,
        "kb_id": c.kb_id,
        "doc_id": c.doc_id,
        "content": c.content,
        "chunk_index": c.chunk_index,
        "node_id": c.node_id,
        "parent_id": c.parent_id,
        "level": c.level,
        "path": c.path,
        "heading": c.heading,
        "seq": c.seq,
        "char_count": c.char_count,
        "status": c.status,
        "metadata": c.extra_meta,
    }


def _provider_to_dict(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "type": p.type,
        "config": p.config,
        "dimension": p.dimension,
        "description": p.description,
        "enabled": p.enabled,
        "sort_order": p.sort_order,
        "create_time": p.create_time.isoformat() if p.create_time else None,
    }
