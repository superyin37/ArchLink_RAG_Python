# 06 - API 参考

## 响应格式
所有端点返回：
```json
{"code": 0, "msg": "success", "data": {...}}
```
错误：`{"code": 1, "msg": "错误信息", "data": null}`

分页：`{"code": 0, "msg": "success", "data": {"list": [...], "total": 100, "page": 1, "size": 10}}`

---

## RAG - 知识库（`/api/rag/kb`）

### GET `/api/rag/kb`
分页列出知识库。
- 查询参数：`page=1, size=10, keyword=可选, status=可选`
- 响应：知识库对象的分页结果

### GET `/api/rag/kb/{id}`
获取知识库详情。
- 响应：KnowledgeBase 对象

### GET `/api/rag/kb/{id}/stats`
获取知识库统计信息。
- 响应：`{id, name, doc_count, chunk_count, total_chars, embedding_model, vector_db_type, dimension}`

### POST `/api/rag/kb`
创建知识库。
- 请求体：`{name, description?, embedding_model, vector_db_type?="lancedb"}`
- 响应：KnowledgeBase 对象

### PUT `/api/rag/kb/{id}`
更新知识库。
- 请求体：`{name?, description?, status?}`
- 响应：`{id}`

### DELETE `/api/rag/kb/{id}`
删除知识库（软删除，级联删除文档）。
- 响应：`{id}`

---

## RAG - 文档（`/api/rag/document`）

### GET `/api/rag/document/kb/{kb_id}`
列出知识库中的文档。
- 查询参数：`page=1, size=10, status=可选`
- 响应：Document 对象的分页结果

### GET `/api/rag/document/{id}`
获取文档详情。
- 响应：Document 对象

### GET `/api/rag/document/{id}/chunks`
获取文档的所有切片。
- 响应：Chunk 对象列表

### GET `/api/rag/document/{id}/preview`
获取文档预览（所有切片拼接）。
- 响应：`{id, filename, file_type, content, chunk_count, char_count}`

### GET `/api/rag/document/{id}/download`
下载原始文档文件。
- 响应：文件流

### POST `/api/rag/document/upload-preview`
预览切片效果而不保存。Multipart 表单。
- 表单：`file`（上传文件）、`chunk_size=500`、`chunk_overlap=0`
- 响应：`{filename, file_type, file_size, tree, chunks, stats}`

### POST `/api/rag/document/upload`
上传并处理文档。Multipart 表单。
- 表单：`kb_id`（必填）、`file`（必填）、`chunk_size=500`、`chunk_overlap=0`
- 响应：Document 对象（后台开始处理）

### POST `/api/rag/document/text`
从纯文本创建文档。
- 请求体：`{kb_id, filename, content, chunk_size=500, chunk_overlap=0}`
- 响应：Document 对象

### DELETE `/api/rag/document/{id}`
删除文档及其所有切片 + 索引。
- 响应：`{id}`

---

## RAG - 搜索（`/api/rag/search`）

### POST `/api/rag/search`
在单个知识库中进行向量搜索。
- 请求体：
```json
{
  "kb_id": 1,
  "query": "搜索文本",
  "top_k": 5,
  "threshold": 0.3,
  "doc_prefilter_topk": null,
  "doc_prefilter_mode": "auto"
}
```
- 响应：SearchResult 对象列表

### POST `/api/rag/search/multi`
跨多个知识库搜索。
- 请求体：
```json
{
  "kb_ids": [1, 2, 3],
  "query": "搜索文本",
  "top_k": 5,
  "threshold": 0.3
}
```
- 响应：`{chunks: [...], errors: [...]}`

### POST `/api/rag/search/context`
获取组装好的 RAG 上下文字符串。
- 请求体：
```json
{
  "kb_id": 1,
  "query": "搜索文本",
  "top_k": 5,
  "threshold": 0.3,
  "separator": "\n\n---\n\n",
  "enhance": true,
  "strategies": ["siblings", "children"],
  "max_depth": 1
}
```
- 响应：`{context: "组装后的文本..."}`

### GET `/api/rag/search/capabilities`
获取搜索系统能力。
- 响应：`{vector: true, fulltext: true/false, hybrid: true/false}`

---

## RAG - Meilisearch（`/api/rag/meilisearch`）

### GET `/api/rag/meilisearch/stats/{kb_id}`
获取全文索引统计信息。
- 响应：Meilisearch 索引统计

### POST `/api/rag/meilisearch/index/{kb_id}`
为知识库创建全文索引。
- 响应：`{success, task_uid, documents_count, stats}`

### DELETE `/api/rag/meilisearch/index/{kb_id}`
删除全文索引。
- 响应：`{success}`

### POST `/api/rag/meilisearch/rebuild/{kb_id}`
重建全文索引。
- 响应：重建结果

### POST `/api/rag/meilisearch/search/{kb_id}`
直接 Meilisearch 搜索。
- 请求体：`{query, limit=10, offset=0, filter?, sort?}`
- 响应：`{hits, total_hits, processing_time_ms}`

### POST `/api/rag/meilisearch/compare/{kb_id}`
对比向量搜索 vs 全文搜索 vs 混合搜索。
- 请求体：`{query, top_k=5, weights?, vector_threshold?}`
- 响应：`{vector: [...], meilisearch: [...], hybrid: [...], total_time}`

---

## RAG - 嵌入提供者（`/api/rag/provider`）

### GET `/api/rag/provider`
列出嵌入提供者。
- 查询参数：`page=1, size=10, enabled=可选`

### GET `/api/rag/provider/enabled`
列出已启用的提供者。

### GET `/api/rag/provider/supported`
列出支持的嵌入模型类型。
- 响应：`[{type: "doubao", dimension: 2048}]`

### GET `/api/rag/provider/vector-db-types`
列出支持的向量数据库类型。
- 响应：`[{type: "lancedb", name: "LanceDB", description: "..."}]`

### GET `/api/rag/provider/{id}`
获取提供者详情。

### POST `/api/rag/provider`
创建嵌入提供者。
- 请求体：`{name, type, config?, description?, enabled?, sort_order?}`

### POST `/api/rag/provider/init`
初始化默认提供者。

### PUT `/api/rag/provider/{id}`
更新提供者。
- 请求体：`{name?, config?, description?, enabled?, sort_order?}`

### DELETE `/api/rag/provider/{id}`
删除提供者。

---

## RAG - 统计（`/api/rag/statistics`）

### GET `/api/rag/statistics/overview`
系统级 RAG 统计信息。
- 响应：`{overview, doc_status, chunk_status, file_types, embedding_models, vector_dbs, upload_trend}`

### GET `/api/rag/statistics/ranking`
知识库排名。
- 查询参数：`order_by=doc_count, limit=10`
- 响应：知识库排名条目列表

### GET `/api/rag/statistics/kb/{kb_id}`
单个知识库详细统计。

---

## RAG - 可视化（`/api/rag/visual`）

### GET `/api/rag/visual/document/{doc_id}/tree`
获取文档可视化树形结构。
- 响应：`{document, tree, stats}`

### POST `/api/rag/visual/search`
带可视化数据的搜索。
- 请求体：`{kb_id, query, top_k, threshold, expand_strategies}`
- 响应：带命中/扩展标记的搜索结果

### GET `/api/rag/visual/kb/{kb_id}/structure`
获取知识库结构概览。
- 响应：`{knowledge_base, documents, stats}`

---

## LLM - 提供者（`/api/llm/provider`）

### GET `/api/llm/provider`
列出 LLM 提供者。
- 查询参数：`page=1, size=10, keyword?, status?, api_type?`

### GET `/api/llm/provider/{provider_id}`
获取提供者详情（含模型列表）。

### POST `/api/llm/provider`
创建提供者。
- 请求体：`{provider_id, name, icon?, api_endpoint?, api_type?, api_key?, auth_type?, default_parameters?, description?, ...}`

### PUT `/api/llm/provider/{provider_id}`
更新提供者。

### DELETE `/api/llm/provider/{provider_id}`
删除提供者（内置不可删除）。

### PUT `/api/llm/provider/{provider_id}/api-key`
仅更新 API 密钥。
- 请求体：`{api_key}`

### GET `/api/llm/provider/api-types`
获取可用 API 类型。
- 响应：`["openai", "anthropic", "google", "openai-compatible"]`

---

## LLM - 模型（`/api/llm/model`）

### GET `/api/llm/model`
列出模型。
- 查询参数：`provider_id?, page, size, keyword?, status?, is_deprecated?`

### GET `/api/llm/model/{model_id}`
获取模型详情（含提供者信息）。

### POST `/api/llm/model`
创建模型。
- 请求体：`{provider_id, model_id, name, description?, max_tokens?, context_window?, capabilities?, pricing?, ...}`

### PUT `/api/llm/model/{model_id}`
更新模型。

### DELETE `/api/llm/model/{model_id}`
删除模型（内置不可删除）。

### POST `/api/llm/model/{model_id}/deprecate`
将模型标记为废弃。
- 请求体：`{replacement_model_id}`

### GET `/api/llm/model/by-provider`
获取按提供者分组的模型。

---

## LLM - 聊天（`/api/llm/chat`）

### GET `/api/llm/chat`
列出用户聊天。
- 查询参数：`page=1, size=10`
- 请求头：`token`（用户认证）

### GET `/api/llm/chat/{chat_id}`
获取聊天详情。

### POST `/api/llm/chat`
创建聊天。
- 请求体：`{model, title?}`

### PUT `/api/llm/chat/{chat_id}/title`
更新聊天标题。
- 请求体：`{title}`

### DELETE `/api/llm/chat/{chat_id}`
删除聊天。

### GET `/api/llm/chat/{chat_id}/messages`
获取聊天消息。
- 查询参数：`page=1, size=50`

---

## LLM - 调用日志（`/api/llm/call-log`）

### GET `/api/llm/call-log`
带过滤条件的调用日志列表。
- 查询参数：`page, size, provider_id?, model?, status?, is_success?, user_id?, session_id?, template_id?, tags?, start_time?, end_time?, keyword?`

### GET `/api/llm/call-log/{id}`
获取调用日志详情。

### GET `/api/llm/call-log/statistics`
获取聚合统计信息。
- 查询参数：`provider_id?, model?, start_time?, end_time?, user_id?, template_id?`
- 响应：`{total_calls, success_calls, failed_calls, success_rate, total_tokens, avg_duration, ...}`

### GET `/api/llm/call-log/stats/by-provider`
按提供者分组的统计信息。

### GET `/api/llm/call-log/stats/by-model`
按模型分组的统计信息。

### GET `/api/llm/call-log/stats/by-time`
随时间变化的统计信息。
- 查询参数：`group_by=day|hour`

### GET `/api/llm/call-log/stats/token-ranking`
Token 用量排名。
- 查询参数：`limit=10`

---

## PPT - 对话流（`/api/ppt`）

### POST `/api/ppt/stream/chat`
PPT 主聊天流式端点（SSE）。
- 请求体：
```json
{
  "conversation_id": "可选-已有ID",
  "message": "用户输入文本",
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
- 响应：SSE 流，含以下事件：
  - `data: {"type": "metadata", "conversation_id": "...", "message_id": 1, "stage": "..."}\n\n`
  - `data: {"type": "thinking", "content": "..."}\n\n`
  - `data: {"type": "thinking_complete"}\n\n`
  - `data: 纯文本内容 token\n\n`
  - `data: {"type": "search_results", "chunks": [...]}\n\n`
  - `data: {"type": "case_selection", "cases": [...]}\n\n`
  - `data: {"type": "error", "message": "..."}\n\n`

### POST `/api/ppt/stream/rag-query`
RAG 增强查询端点（SSE）。
- 请求体：
```json
{
  "conversation_id": "...",
  "message": "用户问题",
  "kb_ids": [1, 2],
  "model_id": "gpt-4o",
  "enhance_config": {"strategies": ["siblings", "children"], "max_depth": 1},
  "limit_config": {"max_chunks": 30}
}
```
- 响应：SSE 流（事件类型同上）

---

## 健康检查与通用

### GET `/health`
健康检查。
- 响应：`{"status": "ok"}`

### GET `/api/health`
详细健康检查。
- 响应：`{"status": "ok", "db": true, "redis": true, "meilisearch": true}`
