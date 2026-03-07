# 01 - Architecture & Project Structure

## Directory Layout

```
rag-python/
├── CLAUDE.md                          # AI development instructions
├── docs/                              # Development documentation
├── docker-compose.yml                 # Full stack deployment
├── Dockerfile                         # Python app container
├── pyproject.toml                     # Python project config (use poetry or pip)
├── requirements.txt                   # Python dependencies
├── alembic.ini                        # Alembic migration config
├── alembic/                           # Database migrations
│   ├── env.py
│   └── versions/
├── .env.example                       # Environment variable template
├── uploads/                           # Uploaded files storage
├── database/                          # LanceDB data directory
│   └── lancedb/
└── app/
    ├── __init__.py
    ├── main.py                        # FastAPI app entry point
    ├── config.py                      # Pydantic Settings configuration
    ├── database.py                    # SQLAlchemy engine + session setup
    ├── dependencies.py                # Shared FastAPI dependencies
    ├── exceptions.py                  # Custom exception classes
    ├── middleware/
    │   ├── __init__.py
    │   ├── auth.py                    # JWT token parsing + whitelist
    │   ├── error_handler.py           # Global exception handler
    │   ├── request_context.py         # Async context (contextvars)
    │   └── response_wrapper.py        # Unified JSON response format
    ├── core/
    │   ├── __init__.py
    │   ├── redis.py                   # Redis client + cache store + rate limit
    │   ├── events.py                  # Event emitter (user events)
    │   └── jwt.py                     # JWT encode/decode
    ├── models/                        # SQLAlchemy ORM models (shared)
    │   ├── __init__.py
    │   ├── base.py                    # BaseModel with id, create_time, update_time, delete_time
    │   ├── rag.py                     # KnowledgeBase, RagDocument, RagChunk, EmbeddingProvider
    │   └── llm.py                     # LLMProvider, LLMModel, LLMChat, LLMMessage, LLMCallLog
    ├── schemas/                       # Pydantic request/response schemas
    │   ├── __init__.py
    │   ├── common.py                  # PageResponse, SuccessResponse, etc.
    │   ├── rag.py                     # RAG-related schemas
    │   └── llm.py                     # LLM-related schemas
    ├── modules/
    │   ├── __init__.py
    │   ├── rag/                       # RAG module
    │   │   ├── __init__.py
    │   │   ├── router.py              # All RAG API routes (use APIRouter with tags)
    │   │   ├── services/
    │   │   │   ├── __init__.py
    │   │   │   ├── knowledge_base.py  # KB CRUD + stats
    │   │   │   ├── document.py        # Document upload, process, chunk, delete
    │   │   │   ├── search.py          # Vector search, fulltext search, hybrid, advanced
    │   │   │   ├── embedding.py       # Embedding generation (Doubao API)
    │   │   │   ├── indexing.py        # Unified indexing (vector + fulltext)
    │   │   │   ├── provider.py        # EmbeddingProvider CRUD
    │   │   │   ├── statistics.py      # RAG statistics
    │   │   │   ├── visual.py          # Document tree visualization
    │   │   │   └── vector_db.py       # LanceDB instance management
    │   │   ├── chunk/
    │   │   │   ├── __init__.py
    │   │   │   ├── chunker.py         # Tree-to-chunks conversion
    │   │   │   ├── parser/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── base.py        # NodeType, createNode, tree utilities
    │   │   │   │   ├── markdown.py    # Markdown parser (optimized)
    │   │   │   │   ├── docx.py        # DOCX parser
    │   │   │   │   └── txt.py         # Plain text parser
    │   │   │   ├── retriever.py       # Recall enhancement (children/siblings/ancestors)
    │   │   │   └── utils.py           # splitBySize, generateNodeId, buildPath
    │   │   ├── search/
    │   │   │   ├── __init__.py
    │   │   │   ├── vector_provider.py     # Vector search via LanceDB
    │   │   │   ├── fulltext_provider.py   # Fulltext search via Meilisearch
    │   │   │   ├── fusion.py              # RRF / weighted / linear fusion
    │   │   │   ├── deduplicator.py        # ID + content + parent-child dedup
    │   │   │   ├── limiter.py             # Token budget result limiting
    │   │   │   ├── readability.py         # Readability scoring + reranking
    │   │   │   ├── threshold.py           # Dynamic threshold adaptation
    │   │   │   ├── keyword_extractor.py   # Keyword extraction for fulltext
    │   │   │   ├── doc_prefilter.py       # Document name prefiltering
    │   │   │   ├── context_optimizer.py   # Context compression by token budget
    │   │   │   └── tree_assembler.py      # Tree context assembly
    │   │   ├── vector/
    │   │   │   ├── __init__.py
    │   │   │   └── lancedb.py         # LanceDB driver wrapper
    │   │   ├── embedding/
    │   │   │   ├── __init__.py
    │   │   │   └── doubao.py          # Doubao embedding API client
    │   │   ├── loaders/
    │   │   │   ├── __init__.py
    │   │   │   ├── docx.py            # DOCX loader
    │   │   │   ├── pdf.py             # PDF loader
    │   │   │   ├── txt.py             # TXT/MD loader
    │   │   │   └── xlsx.py            # XLSX QA loader
    │   │   ├── meilisearch/
    │   │   │   ├── __init__.py
    │   │   │   ├── client.py          # Meilisearch client singleton
    │   │   │   └── index_service.py   # Index CRUD, search, rebuild
    │   │   ├── migration/
    │   │   │   ├── __init__.py
    │   │   │   ├── service.py         # Export/import knowledge bases
    │   │   │   ├── export_cli.py      # CLI export command
    │   │   │   └── import_cli.py      # CLI import command
    │   │   └── config.py              # RAG configuration constants
    │   ├── llm/                       # LLM module
    │   │   ├── __init__.py
    │   │   ├── router.py              # LLM API routes
    │   │   ├── services/
    │   │   │   ├── __init__.py
    │   │   │   ├── provider.py        # LLM provider CRUD
    │   │   │   ├── model.py           # LLM model CRUD
    │   │   │   ├── chat.py            # Chat session management
    │   │   │   ├── message.py         # Message persistence
    │   │   │   ├── call_log.py        # Call log CRUD + statistics
    │   │   │   └── cost.py            # Cost calculation
    │   │   ├── completions/
    │   │   │   ├── __init__.py
    │   │   │   ├── base.py            # LLMBase - stream parsing, media handling
    │   │   │   ├── openai.py          # OpenAI adapter
    │   │   │   ├── anthropic.py       # Anthropic adapter
    │   │   │   ├── azure.py           # Azure OpenAI adapter
    │   │   │   ├── gemini.py          # Google Gemini adapter
    │   │   │   ├── volcengine.py      # VolcEngine adapter
    │   │   │   └── factory.py         # LLMOne - auto-register + factory
    │   │   ├── responses/
    │   │   │   ├── __init__.py
    │   │   │   ├── base.py            # ResponseBase - cache control
    │   │   │   ├── openai.py          # OpenAI with auto-caching
    │   │   │   ├── anthropic.py       # Anthropic with prompt caching
    │   │   │   ├── azure.py           # Azure response adapter
    │   │   │   ├── gemini.py          # Gemini response adapter
    │   │   │   └── factory.py         # ResponseOne - auto-register + factory
    │   │   ├── handlers/
    │   │   │   ├── __init__.py
    │   │   │   ├── chat_manager.py    # Chat lifecycle management
    │   │   │   └── message_persister.py # Message save/query
    │   │   ├── utils/
    │   │   │   ├── __init__.py
    │   │   │   ├── log_recorder.py    # LLM call lifecycle logging
    │   │   │   ├── media_resolver.py  # Multi-format media to data URL
    │   │   │   ├── model_loader.py    # Load model config from DB
    │   │   │   ├── stream.py          # SSE stream helpers
    │   │   │   ├── retry.py           # withRetryBackoff
    │   │   │   └── fallback.py        # withFallbackRouter
    │   │   └── config.py              # LLM configuration
    │   └── ppt/                       # PPT module
    │       ├── __init__.py
    │       ├── router.py              # PPT API routes
    │       └── handlers/
    │           ├── __init__.py
    │           ├── stream.py          # Core stream handler
    │           ├── conversation.py    # Conversation lifecycle
    │           ├── message.py         # Message CRUD
    │           ├── prompt.py          # Prompt builder by stage
    │           ├── outline.py         # Outline data management
    │           ├── stage.py           # Stage state machine
    │           ├── case_selection.py  # Case selection with RAG
    │           └── rag_query/
    │               ├── __init__.py
    │               ├── orchestrator.py    # RAG query orchestration
    │               ├── context_builder.py # RAG context assembly
    │               ├── search_executor.py # Search wrapper
    │               ├── llm_executor.py    # LLM call wrapper
    │               └── stream_publisher.py # SSE event publisher
    └── utils/
        ├── __init__.py
        ├── stream.py                  # SSE formatting utilities
        └── message_builder.py         # LLM message builder
```

## Module Boundaries

### Module Communication Rules
- **Routers** only call **Services** (never access ORM models directly)
- **Services** access **ORM models** and can call other services
- **Cross-module calls**: Only through service interfaces (e.g., RAG search service calls embedding service)
- **Shared models** live in `app/models/` (not inside modules)
- **Shared schemas** live in `app/schemas/`

### Module Dependencies
```
ppt -> llm (LLM calls)
ppt -> rag (RAG search)
rag -> llm (for doc name prefiltering via LLM, optional)
llm -> (standalone, no module deps)
```

## FastAPI Application Setup (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, Redis, Meilisearch
    await init_database()
    await init_redis()
    await init_meilisearch()
    yield
    # Shutdown: close connections
    await close_redis()

app = FastAPI(title="RAG System", lifespan=lifespan)

# CORS - allow all origins
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# Global exception handler
app.add_middleware(ErrorHandlerMiddleware)

# Auth middleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(llm_router, prefix="/api/llm", tags=["LLM"])
app.include_router(ppt_router, prefix="/api/ppt", tags=["PPT"])

# Health check
@app.get("/health")
async def health(): return {"status": "ok"}

# Static files for uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

## Unified Response Format

All API responses follow this structure:
```json
{
  "code": 0,       // 0 = success, 1 = error
  "msg": "success",
  "data": { ... }
}
```

Implement via a response wrapper utility:
```python
class R:
    @staticmethod
    def success(data=None, msg="success"):
        return {"code": 0, "msg": msg, "data": data}

    @staticmethod
    def fail(msg="error", data=None):
        return {"code": 1, "msg": msg, "data": data}

    @staticmethod
    def page(items, total, page, size):
        return {"code": 0, "msg": "success", "data": {
            "list": items, "total": total, "page": page, "size": size
        }}
```
