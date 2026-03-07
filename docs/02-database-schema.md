# 02 - Database Schema

## Overview
All tables use the following conventions:
- Primary key: `id` (INTEGER, auto-increment)
- Timestamps: `create_time` (DateTime, default=now), `update_time` (DateTime, default=now, auto-update), `delete_time` (DateTime, nullable, NULL=active)
- Soft delete: All queries filter `WHERE delete_time IS NULL` by default
- MySQL 8.0, charset=utf8mb4

## Base Model (Python)
```python
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    create_time = Column(DateTime, server_default=func.now(), nullable=False)
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    delete_time = Column(DateTime, nullable=True, default=None)
```

---

## Table: `rag_knowledge_base`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| name | VARCHAR(100) | - | Knowledge base name (required) |
| description | VARCHAR(500) | NULL | Description |
| embedding_model | VARCHAR(50) | - | Embedding model type: `doubao`, `openai`, etc. (required) |
| embedding_config | JSON | NULL | Embedding model config (API key, endpoint, etc.) |
| vector_db_type | VARCHAR(50) | - | Vector DB type: `lancedb` (required) |
| vector_db_config | JSON | NULL | Vector DB config |
| dimension | INTEGER | NULL | Vector dimension (e.g. 2048 for Doubao) |
| doc_count | INTEGER | 0 | Number of documents |
| chunk_count | INTEGER | 0 | Number of chunks |
| status | TINYINT | 1 | 0=disabled, 1=active, 2=indexing |
| create_time | DateTime | NOW() | Created at |
| update_time | DateTime | NOW() | Updated at |
| delete_time | DateTime | NULL | Soft delete |

---

## Table: `rag_document`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| kb_id | INTEGER | - | FK to knowledge_base (required) |
| filename | VARCHAR(255) | - | Original filename (required) |
| file_type | VARCHAR(50) | NULL | File extension: pdf, txt, md, docx |
| file_size | BIGINT | NULL | File size in bytes |
| file_path | VARCHAR(500) | NULL | Storage path on disk |
| content_hash | VARCHAR(64) | NULL | SHA256 of content |
| chunk_count | INTEGER | 0 | Number of chunks |
| char_count | INTEGER | 0 | Total character count |
| status | TINYINT | 0 | 0=pending, 1=processing, 2=completed, 3=failed |
| error_msg | VARCHAR(500) | NULL | Error message if failed |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

---

## Table: `rag_chunk`

This is the core table. Supports tree structure via materialized path.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| kb_id | INTEGER | - | FK to knowledge_base (required) |
| doc_id | INTEGER | - | FK to document (required) |
| content | TEXT | - | Chunk text content (required) |
| chunk_index | INTEGER | 0 | Position index in document |
| node_id | VARCHAR(32) | NULL | Unique node ID (tree) |
| parent_id | VARCHAR(32) | NULL | Parent node ID (tree) |
| level | TINYINT | 0 | Tree depth level |
| path | VARCHAR(500) | NULL | Materialized path: `0001/0002/0003` |
| heading | VARCHAR(255) | NULL | Heading text |
| seq | INTEGER | 0 | Sibling order |
| char_count | INTEGER | 0 | Character count |
| token_count | INTEGER | NULL | Token count (estimated) |
| vector_id | VARCHAR(100) | NULL | ID in vector DB |
| metadata | JSON | NULL | Extra metadata (readability, index info) |
| status | TINYINT | 0 | 0=pending, 1=embedded, 2=failed |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- `idx_kb_id` on (kb_id)
- `idx_doc_id` on (doc_id)
- `idx_doc_path` on (doc_id, path)
- `idx_doc_parent` on (doc_id, parent_id)

---

## Table: `rag_embedding_provider`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| name | VARCHAR(100) | - | Display name (required) |
| type | VARCHAR(50) | - | Type identifier: `doubao`, `openai`, etc. (required) |
| config | JSON | NULL | API config (key, endpoint, etc.) |
| dimension | INTEGER | NULL | Vector dimension |
| description | VARCHAR(500) | NULL | Description |
| enabled | TINYINT | 1 | 0=disabled, 1=enabled |
| sort_order | INTEGER | 0 | Sort weight |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

---

## Table: `llm_providers`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| provider_id | VARCHAR(50) | - | Unique identifier: `openai`, `anthropic`, etc. (required, UNIQUE) |
| name | VARCHAR(100) | - | Display name (required) |
| icon | VARCHAR(20) | NULL | Emoji or icon class |
| api_endpoint | VARCHAR(500) | NULL | API base URL |
| api_type | VARCHAR(50) | `openai` | API type: `openai`, `anthropic`, `google`, `openai-compatible` |
| api_key | TEXT | NULL | Global API key |
| auth_type | VARCHAR(50) | `bearer` | Auth type: `bearer`, `api-key`, `custom` |
| default_parameters | JSON | {} | Default request parameters |
| description | TEXT | NULL | Provider description |
| official_website | VARCHAR(500) | NULL | Official website URL |
| documentation_url | VARCHAR(500) | NULL | API docs URL |
| status | TINYINT | 1 | 0=disabled, 1=enabled |
| is_builtin | BOOLEAN | false | Whether built-in (cannot delete) |
| sort_order | INTEGER | 0 | Sort weight |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- UNIQUE on (provider_id)
- Index on (status)
- Index on (sort_order)

---

## Table: `llm_models`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| provider_id | VARCHAR(50) | - | FK to llm_providers.provider_id (required) |
| model_id | VARCHAR(100) | - | Model identifier: `gpt-4o`, `claude-3-5-sonnet-20241022` (required) |
| name | VARCHAR(100) | - | Display name (required) |
| description | TEXT | NULL | Model description |
| max_tokens | INTEGER | NULL | Max output tokens |
| context_window | INTEGER | NULL | Context window size |
| capabilities | JSON | [] | Capability tags: `["chat", "vision", "function-calling"]` |
| pricing | JSON | NULL | Pricing: `{input_price, output_price, cache_hit_price, currency, per_tokens}` |
| release_date | DATE | NULL | Release date |
| is_deprecated | BOOLEAN | false | Whether deprecated |
| replacement_model_id | VARCHAR(100) | NULL | Replacement model if deprecated |
| status | TINYINT | 1 | 0=disabled, 1=enabled |
| is_builtin | BOOLEAN | false | Built-in (cannot delete) |
| sort_order | INTEGER | 0 | Sort weight |
| metadata | JSON | {} | Extra metadata (api_version, etc.) |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- UNIQUE on (provider_id, model_id)
- Index on (provider_id)
- Index on (status)
- Index on (is_deprecated)

---

## Table: `llm_chat`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| chat_id | VARCHAR(64) | - | Unique chat identifier (required) |
| user_id | BIGINT | NULL | User ID |
| title | VARCHAR(200) | "New Chat" | Chat title |
| model | VARCHAR(100) | NULL | Model used |
| message_count | INTEGER | 0 | Total messages |
| total_tokens | INTEGER | 0 | Total tokens used |
| status | TINYINT | 1 | 0=archived, 1=active |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- Index on (user_id, update_time) named `idx_user_update`
- Index on (chat_id) named `idx_chat_id`

---

## Table: `llm_message`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| chat_id | VARCHAR(64) | - | FK to llm_chat.chat_id (required) |
| role | ENUM('system','user','assistant') | - | Message role (required) |
| content | LONGTEXT | - | Message content (required) |
| model | VARCHAR(100) | NULL | Model name (for assistant messages) |
| token_usage | JSON | NULL | `{prompt_tokens, completion_tokens, total_tokens}` |
| meta | JSON | NULL | Extended metadata (thinking, attachments, etc.) |
| user_id | BIGINT | NULL | User ID |
| status | TINYINT | 1 | 0=disabled, 1=active |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- Index on (chat_id, create_time) named `idx_chat_time`
- Index on (user_id, create_time) named `idx_user_time`

---

## Table: `llm_call_logs`

Complete LLM call tracking with performance metrics.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INTEGER | auto | Primary key |
| **Request Identity** |
| request_id | VARCHAR(100) | - | Unique request ID (required) |
| **Model Info** |
| provider_id | VARCHAR(50) | - | Provider identifier (required) |
| model | VARCHAR(100) | - | Model name (required) |
| api_type | VARCHAR(50) | NULL | API type |
| **Request Details** |
| request_url | VARCHAR(500) | NULL | Request URL |
| request_method | VARCHAR(10) | `POST` | HTTP method |
| request_headers | JSON | NULL | Sanitized headers |
| request_body | JSON | NULL | Request body |
| **Input/Output** |
| prompt | TEXT | NULL | User prompt text |
| messages | JSON | NULL | Full message history |
| response_text | TEXT | NULL | Complete response text |
| reasoning_text | TEXT | NULL | Reasoning/thinking text |
| **Token Stats** |
| prompt_tokens | INTEGER | 0 | Input tokens |
| completion_tokens | INTEGER | 0 | Output tokens |
| total_tokens | INTEGER | 0 | Total tokens |
| reasoning_tokens | INTEGER | 0 | Reasoning tokens |
| cached_tokens | INTEGER | 0 | Cached tokens |
| **Cost** |
| cost | DECIMAL(10,6) | NULL | Calculated cost |
| cost_details | JSON | NULL | `{input, output, cache, currency}` |
| **Timing (milliseconds)** |
| request_start_time | BIGINT | NULL | Request start timestamp(ms) |
| first_token_time | BIGINT | NULL | First token timestamp(ms) |
| response_end_time | BIGINT | NULL | Response end timestamp(ms) |
| total_duration | INTEGER | NULL | Total duration(ms) |
| first_token_duration | INTEGER | NULL | Time to first token(ms) |
| **Status** |
| status | VARCHAR(20) | `pending` | `pending`, `streaming`, `success`, `error` |
| is_success | BOOLEAN | false | Whether successful |
| error_message | TEXT | NULL | Error message |
| error_stack | TEXT | NULL | Error stacktrace |
| **Context** |
| user_id | INTEGER | NULL | User ID |
| session_id | VARCHAR(100) | NULL | Session/chat ID |
| template_id | INTEGER | NULL | Prompt template ID |
| tags | JSON | NULL | Tags for categorization |
| metadata | JSON | NULL | Extra metadata |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**Indexes:**
- Index on (request_id)
- Index on (provider_id)
- Index on (model)
- Index on (status)
- Index on (is_success)
- Index on (user_id)
- Index on (session_id)
- Index on (template_id)
- Index on (create_time)
- Index on (cost)

---

## LanceDB Vector Table Schema

Each knowledge base has its own LanceDB table. Table name format: `kb_{kb_id}`

| Column | Type | Description |
|--------|------|-------------|
| id | string | Chunk identifier (e.g. `chunk_123`) |
| vector | float32[] | Embedding vector (dimension matches KB config) |
| document | string | Chunk text content |
| doc_id | int | Document ID |
| chunk_id | int | Chunk ID |
| node_id | string | Tree node ID |
| parent_id | string | Parent node ID |
| level | int | Tree depth level |
| path | string | Materialized path |
| heading | string | Heading text |
| type | string | Content type (default: "text") |

---

## Meilisearch Index Schema

Index name format: `kb_{kb_id}`

**Searchable attributes:** `content`, `heading`
**Filterable attributes:** `kb_id`, `doc_id`, `level`
**Sortable attributes:** `chunk_index`

Document structure:
```json
{
  "id": "chunk_123",
  "content": "chunk text...",
  "heading": "Section Title",
  "doc_id": 1,
  "kb_id": 1,
  "level": 2,
  "path": "0001/0002",
  "chunk_index": 5
}
```
