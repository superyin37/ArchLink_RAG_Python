from sqlalchemy import Column, Integer, String, Text, BigInteger, JSON, Boolean
from sqlalchemy import Index
from app.models.base import BaseModel


class KnowledgeBase(BaseModel):
    __tablename__ = "rag_knowledge_base"

    name = Column(String(100), nullable=False, comment="Knowledge base name")
    description = Column(String(500), nullable=True)
    embedding_model = Column(String(50), nullable=False, comment="doubao, openai, etc.")
    embedding_config = Column(JSON, nullable=True)
    vector_db_type = Column(String(50), nullable=False, default="lancedb")
    vector_db_config = Column(JSON, nullable=True)
    dimension = Column(Integer, nullable=True, comment="Vector dimension")
    doc_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(Integer, default=1, comment="0=disabled, 1=active, 2=indexing")


class RagDocument(BaseModel):
    __tablename__ = "rag_document"

    kb_id = Column(Integer, nullable=False, comment="FK to knowledge_base")
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True, comment="pdf, txt, md, docx")
    file_size = Column(BigInteger, nullable=True)
    file_path = Column(String(500), nullable=True)
    content_hash = Column(String(64), nullable=True)
    chunk_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    status = Column(
        Integer, default=0, comment="0=pending, 1=processing, 2=completed, 3=failed"
    )
    error_msg = Column(String(500), nullable=True)

    __table_args__ = (Index("idx_rag_doc_kb_id", "kb_id"),)


class RagChunk(BaseModel):
    __tablename__ = "rag_chunk"

    kb_id = Column(Integer, nullable=False)
    doc_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    node_id = Column(String(32), nullable=True)
    parent_id = Column(String(32), nullable=True)
    level = Column(Integer, default=0)
    path = Column(String(500), nullable=True)
    heading = Column(String(255), nullable=True)
    seq = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    token_count = Column(Integer, nullable=True)
    vector_id = Column(String(100), nullable=True)
    extra_meta = Column(JSON, nullable=True)
    status = Column(Integer, default=0, comment="0=pending, 1=embedded, 2=failed")

    __table_args__ = (
        Index("idx_rag_chunk_kb_id", "kb_id"),
        Index("idx_rag_chunk_doc_id", "doc_id"),
        Index("idx_rag_chunk_doc_path", "doc_id", "path"),
        Index("idx_rag_chunk_doc_parent", "doc_id", "parent_id"),
    )


class EmbeddingProvider(BaseModel):
    __tablename__ = "rag_embedding_provider"

    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False, comment="doubao, openai, etc.")
    config = Column(JSON, nullable=True)
    dimension = Column(Integer, nullable=True)
    description = Column(String(500), nullable=True)
    enabled = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
