# 06 - API Reference

## Response Format
All endpoints return:
```json
{"code": 0, "msg": "success", "data": {...}}
```
Error: `{"code": 1, "msg": "error message", "data": null}`

Pagination: `{"code": 0, "msg": "success", "data": {"list": [...], "total": 100, "page": 1, "size": 10}}`

---

## RAG - Knowledge Base (`/api/rag/kb`)

### GET `/api/rag/kb`
List knowledge bases with pagination.
- Query: `page=1, size=10, keyword=optional, status=optional`
- Response: PageResult of KnowledgeBase objects

### GET `/api/rag/kb/{id}`
Get knowledge base detail.
- Response: KnowledgeBase object

### GET `/api/rag/kb/{id}/stats`
Get KB statistics.
- Response: `{id, name, doc_count, chunk_count, total_chars, embedding_model, vector_db_type, dimension}`

### POST `/api/rag/kb`
Create knowledge base.
- Body: `{name, description?, embedding_model, vector_db_type?="lancedb"}`
- Response: KnowledgeBase object

### PUT `/api/rag/kb/{id}`
Update knowledge base.
- Body: `{name?, description?, status?}`
- Response: `{id}`

### DELETE `/api/rag/kb/{id}`
Delete knowledge base (soft delete, cascades to documents).
- Response: `{id}`

---

## RAG - Document (`/api/rag/document`)

### GET `/api/rag/document/kb/{kb_id}`
List documents in a knowledge base.
- Query: `page=1, size=10, status=optional`
- Response: PageResult of Document objects

### GET `/api/rag/document/{id}`
Get document detail.
- Response: Document object

### GET `/api/rag/document/{id}/chunks`
Get all chunks for a document.
- Response: list of Chunk objects

### GET `/api/rag/document/{id}/preview`
Get document preview (all chunks concatenated).
- Response: `{id, filename, file_type, content, chunk_count, char_count}`

### GET `/api/rag/document/{id}/download`
Download original document file.
- Response: File stream

### POST `/api/rag/document/upload-preview`
Preview chunking without saving. Multipart form.
- Form: `file` (uploaded file), `chunk_size=500`, `chunk_overlap=0`
- Response: `{filename, file_type, file_size, tree, chunks, stats}`

### POST `/api/rag/document/upload`
Upload and process a document. Multipart form.
- Form: `kb_id` (required), `file` (required), `chunk_size=500`, `chunk_overlap=0`
- Response: Document object (processing starts in background)

### POST `/api/rag/document/text`
Create document from plain text.
- Body: `{kb_id, filename, content, chunk_size=500, chunk_overlap=0}`
- Response: Document object

### DELETE `/api/rag/document/{id}`
Delete document and all its chunks + indexes.
- Response: `{id}`

---

## RAG - Search (`/api/rag/search`)

### POST `/api/rag/search`
Vector search in a single knowledge base.
- Body:
```json
{
  "kb_id": 1,
  "query": "search text",
  "top_k": 5,
  "threshold": 0.3,
  "doc_prefilter_topk": null,
  "doc_prefilter_mode": "auto"
}
```
- Response: list of SearchResult objects

### POST `/api/rag/search/multi`
Search across multiple knowledge bases.
- Body:
```json
{
  "kb_ids": [1, 2, 3],
  "query": "search text",
  "top_k": 5,
  "threshold": 0.3
}
```
- Response: `{chunks: [...], errors: [...]}`

### POST `/api/rag/search/context`
Get assembled RAG context string.
- Body:
```json
{
  "kb_id": 1,
  "query": "search text",
  "top_k": 5,
  "threshold": 0.3,
  "separator": "\n\n---\n\n",
  "enhance": true,
  "strategies": ["siblings", "children"],
  "max_depth": 1
}
```
- Response: `{context: "assembled text..."}`

### GET `/api/rag/search/capabilities`
Get search system capabilities.
- Response: `{vector: true, fulltext: true/false, hybrid: true/false}`

---

## RAG - Meilisearch (`/api/rag/meilisearch`)

### GET `/api/rag/meilisearch/stats/{kb_id}`
Get fulltext index statistics.
- Response: Meilisearch index stats

### POST `/api/rag/meilisearch/index/{kb_id}`
Create fulltext index for a KB.
- Response: `{success, task_uid, documents_count, stats}`

### DELETE `/api/rag/meilisearch/index/{kb_id}`
Delete fulltext index.
- Response: `{success}`

### POST `/api/rag/meilisearch/rebuild/{kb_id}`
Rebuild fulltext index.
- Response: rebuild result

### POST `/api/rag/meilisearch/search/{kb_id}`
Direct Meilisearch search.
- Body: `{query, limit=10, offset=0, filter?, sort?}`
- Response: `{hits, total_hits, processing_time_ms}`

### POST `/api/rag/meilisearch/compare/{kb_id}`
Compare vector vs fulltext vs hybrid search.
- Body: `{query, top_k=5, weights?, vector_threshold?}`
- Response: `{vector: [...], meilisearch: [...], hybrid: [...], total_time}`

---

## RAG - Embedding Provider (`/api/rag/provider`)

### GET `/api/rag/provider`
List embedding providers.
- Query: `page=1, size=10, enabled=optional`

### GET `/api/rag/provider/enabled`
List enabled providers.

### GET `/api/rag/provider/supported`
List supported embedding model types.
- Response: `[{type: "doubao", dimension: 2048}]`

### GET `/api/rag/provider/vector-db-types`
List supported vector DB types.
- Response: `[{type: "lancedb", name: "LanceDB", description: "..."}]`

### GET `/api/rag/provider/{id}`
Get provider detail.

### POST `/api/rag/provider`
Create embedding provider.
- Body: `{name, type, config?, description?, enabled?, sort_order?}`

### POST `/api/rag/provider/init`
Initialize default providers.

### PUT `/api/rag/provider/{id}`
Update provider.
- Body: `{name?, config?, description?, enabled?, sort_order?}`

### DELETE `/api/rag/provider/{id}`
Delete provider.

---

## RAG - Statistics (`/api/rag/statistics`)

### GET `/api/rag/statistics/overview`
System-wide RAG statistics.
- Response: `{overview, doc_status, chunk_status, file_types, embedding_models, vector_dbs, upload_trend}`

### GET `/api/rag/statistics/ranking`
Knowledge base ranking.
- Query: `order_by=doc_count, limit=10`
- Response: list of KB ranking entries

### GET `/api/rag/statistics/kb/{kb_id}`
Single KB detailed statistics.

---

## RAG - Visual (`/api/rag/visual`)

### GET `/api/rag/visual/document/{doc_id}/tree`
Get document tree structure for visualization.
- Response: `{document, tree, stats}`

### POST `/api/rag/visual/search`
Search with visualization data.
- Body: `{kb_id, query, top_k, threshold, expand_strategies}`
- Response: search results with hit/expanded markers

### GET `/api/rag/visual/kb/{kb_id}/structure`
Get KB structure overview.
- Response: `{knowledge_base, documents, stats}`

---

## LLM - Provider (`/api/llm/provider`)

### GET `/api/llm/provider`
List LLM providers.
- Query: `page=1, size=10, keyword?, status?, api_type?`

### GET `/api/llm/provider/{provider_id}`
Get provider detail (includes model list).

### POST `/api/llm/provider`
Create provider.
- Body: `{provider_id, name, icon?, api_endpoint?, api_type?, api_key?, auth_type?, default_parameters?, description?, ...}`

### PUT `/api/llm/provider/{provider_id}`
Update provider.

### DELETE `/api/llm/provider/{provider_id}`
Delete provider (builtin cannot delete).

### PUT `/api/llm/provider/{provider_id}/api-key`
Update API key only.
- Body: `{api_key}`

### GET `/api/llm/provider/api-types`
Get available API types.
- Response: `["openai", "anthropic", "google", "openai-compatible"]`

---

## LLM - Model (`/api/llm/model`)

### GET `/api/llm/model`
List models.
- Query: `provider_id?, page, size, keyword?, status?, is_deprecated?`

### GET `/api/llm/model/{model_id}`
Get model detail (includes provider info).

### POST `/api/llm/model`
Create model.
- Body: `{provider_id, model_id, name, description?, max_tokens?, context_window?, capabilities?, pricing?, ...}`

### PUT `/api/llm/model/{model_id}`
Update model.

### DELETE `/api/llm/model/{model_id}`
Delete model (builtin cannot delete).

### POST `/api/llm/model/{model_id}/deprecate`
Mark model as deprecated.
- Body: `{replacement_model_id}`

### GET `/api/llm/model/by-provider`
Get models grouped by provider.

---

## LLM - Chat (`/api/llm/chat`)

### GET `/api/llm/chat`
List user chats.
- Query: `page=1, size=10`
- Header: `token` (user auth)

### GET `/api/llm/chat/{chat_id}`
Get chat detail.

### POST `/api/llm/chat`
Create chat.
- Body: `{model, title?}`

### PUT `/api/llm/chat/{chat_id}/title`
Update chat title.
- Body: `{title}`

### DELETE `/api/llm/chat/{chat_id}`
Delete chat.

### GET `/api/llm/chat/{chat_id}/messages`
Get chat messages.
- Query: `page=1, size=50`

---

## LLM - Call Logs (`/api/llm/call-log`)

### GET `/api/llm/call-log`
List call logs with filters.
- Query: `page, size, provider_id?, model?, status?, is_success?, user_id?, session_id?, template_id?, tags?, start_time?, end_time?, keyword?`

### GET `/api/llm/call-log/{id}`
Get call log detail.

### GET `/api/llm/call-log/statistics`
Get aggregated statistics.
- Query: `provider_id?, model?, start_time?, end_time?, user_id?, template_id?`
- Response: `{total_calls, success_calls, failed_calls, success_rate, total_tokens, avg_duration, ...}`

### GET `/api/llm/call-log/stats/by-provider`
Statistics grouped by provider.

### GET `/api/llm/call-log/stats/by-model`
Statistics grouped by model.

### GET `/api/llm/call-log/stats/by-time`
Statistics over time.
- Query: `group_by=day|hour`

### GET `/api/llm/call-log/stats/token-ranking`
Token usage ranking.
- Query: `limit=10`

---

## PPT - Conversation Stream (`/api/ppt`)

### POST `/api/ppt/stream/chat`
Main PPT chat streaming endpoint (SSE).
- Body:
```json
{
  "conversation_id": "optional-existing-id",
  "message": "user input text",
  "stage": "requirement|outline|ppt",
  "conversation_type": "ppt_design",
  "model_id": "gpt-4o",
  "metadata": {
    "building_params": {...},
    "language": "zh"
  },
  "kb_ids": [1, 2]
}
```
- Response: SSE stream with events:
  - `data: {"type": "metadata", "conversation_id": "...", "message_id": 1, "stage": "..."}\n\n`
  - `data: {"type": "thinking", "content": "..."}\n\n`
  - `data: {"type": "thinking_complete"}\n\n`
  - `data: plain text content token\n\n`
  - `data: {"type": "search_results", "chunks": [...]}\n\n`
  - `data: {"type": "case_selection", "cases": [...]}\n\n`
  - `data: {"type": "error", "message": "..."}\n\n`

### POST `/api/ppt/stream/rag-query`
RAG-enhanced query endpoint (SSE).
- Body:
```json
{
  "conversation_id": "...",
  "message": "user question",
  "kb_ids": [1, 2],
  "model_id": "gpt-4o",
  "enhance_config": {"strategies": ["siblings", "children"], "max_depth": 1},
  "limit_config": {"max_chunks": 30}
}
```
- Response: SSE stream (same event types as above)

---

## Health & Common

### GET `/health`
Health check.
- Response: `{"status": "ok"}`

### GET `/api/health`
Detailed health check.
- Response: `{"status": "ok", "db": true, "redis": true, "meilisearch": true}`
