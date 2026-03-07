from typing import Any, Optional
from pydantic import BaseModel
from datetime import datetime


# Knowledge Base schemas
class KBCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embedding_model: str
    embedding_config: Optional[dict] = None
    vector_db_type: str = "lancedb"
    vector_db_config: Optional[dict] = None
    dimension: Optional[int] = None


class KBUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class KBResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    embedding_model: str
    vector_db_type: str
    dimension: Optional[int] = None
    doc_count: int = 0
    chunk_count: int = 0
    status: int = 1
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class KBStats(BaseModel):
    id: int
    name: str
    doc_count: int
    chunk_count: int
    total_chars: int = 0
    embedding_model: str
    vector_db_type: str
    dimension: Optional[int] = None


# Document schemas
class DocumentResponse(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    chunk_count: int = 0
    char_count: int = 0
    status: int = 0
    error_msg: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentTextCreate(BaseModel):
    kb_id: int
    filename: str
    content: str
    chunk_size: int = 500
    chunk_overlap: int = 0


# Chunk schemas
class ChunkResponse(BaseModel):
    id: int
    kb_id: int
    doc_id: int
    content: str
    chunk_index: int = 0
    node_id: Optional[str] = None
    parent_id: Optional[str] = None
    level: int = 0
    path: Optional[str] = None
    heading: Optional[str] = None
    seq: int = 0
    char_count: int = 0
    status: int = 0
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


# Search schemas
class SearchRequest(BaseModel):
    kb_id: int
    query: str
    top_k: int = 5
    threshold: float = 0.3
    doc_prefilter_topk: Optional[int] = None
    doc_prefilter_mode: str = "auto"


class MultiSearchRequest(BaseModel):
    kb_ids: list[int]
    query: str
    top_k: int = 5
    threshold: float = 0.3


class ContextSearchRequest(BaseModel):
    kb_id: int
    query: str
    top_k: int = 5
    threshold: float = 0.3
    separator: str = "\n\n---\n\n"
    enhance: bool = True
    strategies: list[str] = ["siblings", "children"]
    max_depth: int = 1


class SearchResult(BaseModel):
    id: int
    content: str
    score: float
    heading: Optional[str] = None
    doc_id: Optional[int] = None
    node_id: Optional[str] = None
    parent_id: Optional[str] = None
    level: int = 0
    path: Optional[str] = None
    source: str = "vector"
    metadata: Optional[dict] = None
    is_hit: bool = True


# Embedding Provider schemas
class EmbeddingProviderCreate(BaseModel):
    name: str
    type: str
    config: Optional[dict] = None
    description: Optional[str] = None
    enabled: int = 1
    sort_order: int = 0
    dimension: Optional[int] = None


class EmbeddingProviderUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None
    enabled: Optional[int] = None
    sort_order: Optional[int] = None


class EmbeddingProviderResponse(BaseModel):
    id: int
    name: str
    type: str
    config: Optional[dict] = None
    dimension: Optional[int] = None
    description: Optional[str] = None
    enabled: int = 1
    sort_order: int = 0
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True


# Meilisearch schemas
class MeilisearchSearchRequest(BaseModel):
    query: str
    limit: int = 10
    offset: int = 0
    filter: Optional[str] = None
    sort: Optional[list[str]] = None


class CompareSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    weights: Optional[dict] = None
    vector_threshold: Optional[float] = None
