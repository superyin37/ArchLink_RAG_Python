import hashlib
import logging
import uuid
from pathlib import Path
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.config import settings
from app.models.rag import RagDocument, RagChunk
from app.exceptions import DocumentNotFoundError, DocumentProcessingError
from app.modules.rag.services.knowledge_base import kb_service
from app.modules.rag.services.indexing import indexing_service
from app.modules.rag.chunk.chunker import tree_to_chunks
from app.modules.rag.chunk.parser.markdown import parse_markdown_optimized
from app.modules.rag.chunk.parser.txt import parse_txt
from app.modules.rag.chunk.parser.docx import parse_docx
from app.modules.rag.loaders.txt import load_txt
from app.modules.rag.loaders.pdf import load_pdf
from app.modules.rag.loaders.docx import load_docx_text
from app.modules.rag.loaders.xlsx import load_xlsx
from app.modules.rag.search.readability import evaluate_readability
from app.database import async_session

logger = logging.getLogger(__name__)


def _get_file_type(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


async def _load_content(file_path: str, file_type: str) -> str:
    if file_type in ("txt", "md"):
        return await load_txt(file_path)
    elif file_type == "pdf":
        return await load_pdf(file_path)
    elif file_type == "docx":
        return await load_docx_text(file_path)
    elif file_type == "xlsx":
        return await load_xlsx(file_path)
    else:
        return await load_txt(file_path)


def _parse_content(content: str, file_type: str, file_path: str = None):
    if file_type == "md":
        return parse_markdown_optimized(content)
    elif file_type == "docx" and file_path:
        try:
            return parse_docx(file_path)
        except Exception:
            return parse_txt(content)
    else:
        return parse_txt(content)


class DocumentService:
    async def get_list(
        self,
        db: AsyncSession,
        kb_id: int,
        page: int = 1,
        size: int = 10,
        status: int = None,
    ) -> dict:
        query = select(RagDocument).where(
            RagDocument.kb_id == kb_id,
            RagDocument.delete_time.is_(None),
        )
        count_q = select(func.count(RagDocument.id)).where(
            RagDocument.kb_id == kb_id,
            RagDocument.delete_time.is_(None),
        )

        if status is not None:
            query = query.where(RagDocument.status == status)
            count_q = count_q.where(RagDocument.status == status)

        total = (await db.execute(count_q)).scalar()
        result = await db.execute(
            query.order_by(RagDocument.create_time.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = result.scalars().all()
        return {"list": items, "total": total, "page": page, "size": size}

    async def get_by_id(self, db: AsyncSession, doc_id: int) -> RagDocument:
        result = await db.execute(
            select(RagDocument).where(
                RagDocument.id == doc_id,
                RagDocument.delete_time.is_(None),
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise DocumentNotFoundError(doc_id)
        return doc

    async def get_chunks(self, db: AsyncSession, doc_id: int) -> list[RagChunk]:
        result = await db.execute(
            select(RagChunk).where(
                RagChunk.doc_id == doc_id,
                RagChunk.delete_time.is_(None),
            ).order_by(RagChunk.chunk_index)
        )
        return result.scalars().all()

    async def upload_and_process(
        self,
        db: AsyncSession,
        kb_id: int,
        file: UploadFile,
        chunk_size: int = 500,
        chunk_overlap: int = 0,
    ) -> RagDocument:
        # Verify KB exists
        kb = await kb_service.get_by_id(db, kb_id)

        # Save file
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_type = _get_file_type(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = upload_dir / unique_name

        content_bytes = await file.read()
        file_path.write_bytes(content_bytes)

        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # Create document record
        doc = RagDocument(
            kb_id=kb_id,
            filename=file.filename,
            file_type=file_type,
            file_size=len(content_bytes),
            file_path=str(file_path),
            content_hash=content_hash,
            status=0,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        doc_id = doc.id

        # Commit now so background task can read the committed record
        await db.commit()

        # Trigger async processing
        import asyncio
        asyncio.create_task(self._process_document(doc_id, file_path, file_type, chunk_size))

        return doc

    async def create_from_text(
        self,
        db: AsyncSession,
        kb_id: int,
        filename: str,
        content: str,
        chunk_size: int = 500,
    ) -> RagDocument:
        kb = await kb_service.get_by_id(db, kb_id)

        file_type = _get_file_type(filename) or "txt"
        content_bytes = content.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # Save content to file
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = upload_dir / unique_name
        file_path.write_text(content, encoding="utf-8")

        doc = RagDocument(
            kb_id=kb_id,
            filename=filename,
            file_type=file_type,
            file_size=len(content_bytes),
            file_path=str(file_path),
            content_hash=content_hash,
            status=0,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        doc_id = doc.id

        # Commit now so background task can read the committed record
        await db.commit()

        import asyncio
        asyncio.create_task(self._process_document(doc_id, file_path, file_type, chunk_size))

        return doc

    async def _process_document(
        self,
        doc_id: int,
        file_path: Path,
        file_type: str,
        chunk_size: int = 500,
    ):
        """Background task: parse, chunk, embed, and index a document."""
        async with async_session() as db:
            try:
                result = await db.execute(
                    select(RagDocument).where(RagDocument.id == doc_id)
                )
                doc = result.scalar_one_or_none()
                if not doc:
                    return

                # Update status to processing
                doc.status = 1
                await db.commit()

                # Load content
                content = await _load_content(str(file_path), file_type)

                # Parse to tree
                tree = _parse_content(content, file_type, str(file_path))

                # Convert to chunks
                raw_chunks = tree_to_chunks(tree, doc.id, doc.kb_id, max_size=chunk_size)

                # Filter by readability
                readable_chunks = []
                for c in raw_chunks:
                    r = evaluate_readability(c["content"])
                    if r["is_readable"]:
                        c["extra_meta"] = {"readability_score": r["readability_score"]}
                        readable_chunks.append(c)

                if not readable_chunks:
                    readable_chunks = raw_chunks  # Fallback: use all chunks

                # Save chunks to DB
                chunk_objects = []
                for c in readable_chunks:
                    chunk = RagChunk(
                        kb_id=doc.kb_id,
                        doc_id=doc.id,
                        content=c["content"],
                        chunk_index=c["chunk_index"],
                        node_id=c.get("node_id"),
                        parent_id=c.get("parent_id"),
                        level=c.get("level", 0),
                        path=c.get("path"),
                        heading=c.get("heading"),
                        seq=c.get("seq", 0),
                        char_count=c.get("char_count", len(c["content"])),
                        extra_meta=c.get("extra_meta"),
                        status=0,
                    )
                    db.add(chunk)
                    chunk_objects.append(chunk)

                await db.flush()
                for chunk, obj in zip(readable_chunks, chunk_objects):
                    chunk["id"] = obj.id

                # Get KB config for indexing
                from app.models.rag import KnowledgeBase
                kb_result = await db.execute(
                    select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id)
                )
                kb = kb_result.scalar_one()

                # Index chunks
                index_result = await indexing_service.index_chunks(doc.kb_id, readable_chunks, kb)

                # Update chunk statuses
                for obj in chunk_objects:
                    obj.status = 1

                # Update document stats
                total_chars = sum(c.char_count for c in chunk_objects)
                doc.chunk_count = len(chunk_objects)
                doc.char_count = total_chars
                doc.status = 2  # completed

                await db.commit()

                # Update KB counts
                await kb_service.update_counts(db, doc.kb_id)
                await db.commit()

                logger.info(f"Document {doc_id} processed: {len(readable_chunks)} chunks")

            except Exception as e:
                logger.exception(f"Document {doc_id} processing failed: {e}")
                async with async_session() as err_db:
                    err_result = await err_db.execute(
                        select(RagDocument).where(RagDocument.id == doc_id)
                    )
                    err_doc = err_result.scalar_one_or_none()
                    if err_doc:
                        err_doc.status = 3
                        err_doc.error_msg = str(e)[:500]
                        await err_db.commit()

    async def delete(self, db: AsyncSession, doc_id: int) -> int:
        doc = await self.get_by_id(db, doc_id)

        # Get chunk IDs for index deletion
        chunks_result = await db.execute(
            select(RagChunk).where(
                RagChunk.doc_id == doc_id,
                RagChunk.delete_time.is_(None),
            )
        )
        chunks = chunks_result.scalars().all()
        chunk_ids = [c.id for c in chunks]

        # Soft delete chunks
        now = datetime.utcnow()
        for chunk in chunks:
            chunk.delete_time = now

        # Remove from indexes
        if chunk_ids:
            from app.models.rag import KnowledgeBase
            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id)
            )
            kb = kb_result.scalar_one_or_none()
            dim = kb.dimension if kb else 2048
            await indexing_service.delete_chunks(doc.kb_id, chunk_ids, dim)

        # Soft delete document
        doc.delete_time = now
        await db.flush()

        # Update KB counts
        await kb_service.update_counts(db, doc.kb_id)

        return doc_id

    async def preview_upload(
        self,
        file: UploadFile,
        chunk_size: int = 500,
    ) -> dict:
        """Preview chunking without saving to DB."""
        file_type = _get_file_type(file.filename)
        content_bytes = await file.read()

        import tempfile, os
        with tempfile.NamedTemporaryFile(
            suffix=f".{file_type}", delete=False
        ) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name

        try:
            content = await _load_content(tmp_path, file_type)
            tree = _parse_content(content, file_type, tmp_path)
            raw_chunks = tree_to_chunks(tree, 0, 0, max_size=chunk_size)

            readable = []
            for c in raw_chunks:
                r = evaluate_readability(c["content"])
                c["is_readable"] = r["is_readable"]
                c["readability_score"] = r.get("readability_score", 0)
                readable.append(c)

            return {
                "filename": file.filename,
                "file_type": file_type,
                "file_size": len(content_bytes),
                "chunks": readable,
                "stats": {
                    "total_chunks": len(readable),
                    "readable_chunks": sum(1 for c in readable if c.get("is_readable")),
                    "total_chars": sum(c["char_count"] for c in readable),
                },
            }
        finally:
            os.unlink(tmp_path)


doc_service = DocumentService()
