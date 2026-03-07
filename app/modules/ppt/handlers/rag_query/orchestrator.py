"""RAG query orchestrator for PPT module."""
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10


class StreamPublisher:
    def __init__(self, stream):
        self.stream = stream

    def publish_initial_metadata(self, conversation, message):
        self._send_json({
            "type": "metadata",
            "conversation_id": conversation.id,
            "message_id": message.id,
            "stage": getattr(conversation, "stage", None),
        })

    def publish_search_results(self, result: dict):
        self._send_json({
            "type": "search_results",
            "chunks": result.get("chunks", [])[:10],
            "kb_name": result.get("kb_name"),
            "stats": result.get("stats"),
        })

    def publish_thinking(self, text: str):
        self._send_json({"type": "thinking", "content": text})

    def publish_thinking_complete(self):
        self._send_json({"type": "thinking_complete"})

    def publish_content(self, text: str):
        self.stream.send_text(text)

    def publish_warning(self, message: str):
        self._send_json({"type": "warning", "message": message})

    def publish_error(self, message: str):
        self._send_json({"type": "error", "message": message})

    def close(self):
        self.stream.close()

    def _send_json(self, data: dict):
        self.stream.send_json(data)


class SearchExecutor:
    async def execute(
        self, kb_ids: list[int], query: str,
        enhance_config: dict = None, limit_config: dict = None,
    ) -> dict:
        from app.modules.rag.embedding import embedding_service
        from app.modules.rag.vector import vector_db_service
        from app.modules.rag.meilisearch.index_service import meilisearch_index_service
        from app.modules.rag.search.providers import VectorSearchProvider, FulltextSearchProvider
        from app.modules.rag.search.fusion import SearchFusion

        all_chunks = []
        kb_name = ""

        for kb_id in kb_ids:
            try:
                from app.database import async_session
                from app.modules.rag.services.knowledge_base import kb_service
                async with async_session() as db:
                    kb = await kb_service.get_by_id(db, kb_id)

                kb_name = kb.name
                vector_results = await VectorSearchProvider().search(kb, query, top_k=10)
                fulltext_results = await FulltextSearchProvider().search(kb_id, query, top_k=10)
                fused = SearchFusion.fuse_rrf([vector_results, fulltext_results], top_k=10)
                all_chunks.extend(fused)
            except Exception as e:
                logger.warning(f"Search failed for kb {kb_id}: {e}")

        return {
            "chunks": all_chunks,
            "kb_name": kb_name,
            "stats": {"total": len(all_chunks)},
        }


class RagContextBuilder:
    def build_context(self, chunks: list) -> str:
        hit_chunks = [c for c in chunks if c.get("is_hit")]
        expanded_chunks = [c for c in chunks if not c.get("is_hit")]
        parts = []

        if hit_chunks:
            parts.append("## Directly Relevant Content")
            for c in hit_chunks:
                score = c.get("score", 0)
                score_tag = f" (similarity: {score:.2f})" if score else ""
                heading = c.get("heading")
                if heading:
                    parts.append(f"### {heading}{score_tag}\n{c['content']}")
                else:
                    parts.append(c["content"])

        if expanded_chunks:
            parts.append("\n## Related Context")
            doc_groups: dict[int, list] = {}
            for c in expanded_chunks:
                doc_groups.setdefault(c.get("doc_id", 0), []).append(c)
            for doc_id, doc_chunks in doc_groups.items():
                doc_name = doc_chunks[0].get("metadata", {}).get("doc_name", f"Document {doc_id}")
                parts.append(f"### From: {doc_name}")
                for c in doc_chunks:
                    parts.append(c["content"])

        return "\n\n".join(parts)

    async def build_system_prompt(self, context: str, kb_name: str = "Knowledge Base") -> str:
        return (
            f"You are a helpful assistant. Answer based on the following knowledge base content.\n\n"
            f"Knowledge Base: {kb_name}\n\n"
            f"{context}\n\n"
            f"Instructions:\n"
            f"- Answer based on the provided context\n"
            f"- If the context doesn't contain relevant information, say so\n"
            f"- Be concise and accurate"
        )


class LlmExecutor:
    def __init__(self, stream):
        self.stream = stream
        self._content_parts: list[str] = []
        self._thinking_parts: list[str] = []

    async def execute(
        self, messages: list, model_config: dict,
        on_thinking=None, on_thinking_complete=None, on_content=None,
    ) -> dict:
        from app.modules.llm.completions.factory import LLMOne

        model_str = model_config.get("model_id", "")

        try:
            from app.database import async_session
            from app.modules.llm.utils.model_loader import load_model_by_string
            async with async_session() as db:
                provider, model = await load_model_by_string(model_str, db)
            llm = LLMOne.from_database(provider, model)
        except Exception:
            llm = LLMOne.from_config(model_str)

        content_buf: list[str] = []
        thinking_buf: list[str] = []

        def _on_thinking(text: str):
            thinking_buf.append(text)
            if on_thinking:
                on_thinking(text)

        def _on_thinking_complete():
            if on_thinking_complete:
                on_thinking_complete()

        def _on_content(text: str):
            content_buf.append(text)
            if on_content:
                on_content(text)

        llm.on_thinking = _on_thinking
        llm.on_thinking_complete = _on_thinking_complete
        llm.on_content = _on_content

        await llm.chat(messages)

        return {
            "content": "".join(content_buf),
            "thinking": "".join(thinking_buf),
        }


class RagQueryOrchestrator:
    def __init__(self, stream, conversation, assistant_message, message_history: list, config: dict):
        self.publisher = StreamPublisher(stream)
        self.search_executor = SearchExecutor()
        self.context_builder = RagContextBuilder()
        self.llm_executor = LlmExecutor(stream)
        self.conversation = conversation
        self.assistant_message = assistant_message
        self.message_history = message_history
        self.config = config

    async def execute(self, kb_ids: list[int], query: str, model_config: dict):
        try:
            self.publisher.publish_initial_metadata(self.conversation, self.assistant_message)

            search_result = await self.search_executor.execute(
                kb_ids=kb_ids,
                query=query,
                enhance_config=self.config.get("enhance"),
                limit_config=self.config.get("limit"),
            )
            self.publisher.publish_search_results(search_result)

            context_text = self.context_builder.build_context(search_result["chunks"])
            system_prompt = await self.context_builder.build_system_prompt(
                context=context_text,
                kb_name=search_result.get("kb_name", "Knowledge Base"),
            )

            recent_history = self.message_history[-MAX_HISTORY_MESSAGES:]
            llm_messages = [{"role": "system", "content": system_prompt}] + recent_history

            llm_result = await self.llm_executor.execute(
                messages=llm_messages,
                model_config=model_config,
                on_thinking=self.publisher.publish_thinking,
                on_thinking_complete=self.publisher.publish_thinking_complete,
                on_content=self.publisher.publish_content,
            )

            from app.modules.ppt.store import update_message
            self.assistant_message.content = llm_result["content"]
            if llm_result.get("thinking"):
                self.assistant_message.meta = {
                    **(self.assistant_message.meta or {}),
                    "thinking": llm_result["thinking"],
                }
            update_message(self.assistant_message)

        except Exception as e:
            logger.exception(f"RAG query orchestrator error: {e}")
            self.publisher.publish_error(str(e))
        finally:
            self.publisher.close()
