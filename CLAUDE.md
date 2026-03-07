# RAG System - Python Rebuild

## Project Overview
This is a full-featured RAG (Retrieval-Augmented Generation) system rebuilt in Python from a production Node.js/Koa application. It provides: knowledge base management, document processing (chunking/embedding/indexing), hybrid search (vector + fulltext), multi-provider LLM integration with streaming, and a PPT generation module with stage-based conversation flow.

## Tech Stack (MANDATORY)
- **Framework**: FastAPI (async, with SSE streaming support)
- **ORM**: SQLAlchemy 2.0 (async) + Alembic for migrations
- **Database**: MySQL 8.0
- **Vector DB**: LanceDB (via `lancedb` Python package)
- **Fulltext Search**: Meilisearch (via `meilisearch` Python package)
- **Cache/Rate Limit**: Redis (via `redis[hiredis]` async package), with in-memory fallback
- **LLM SDKs**: `openai`, `anthropic`, `google-generativeai`, `httpx` (for generic HTTP)
- **Embedding**: Volcengine Doubao API (HTTP calls via httpx)
- **File Parsing**: `python-docx`, `PyPDF2` / `pdfplumber`, `openpyxl`, `markdown`
- **Task Queue**: None required (use background tasks or asyncio for async processing)
- **Deployment**: Docker + docker-compose (single container, uvicorn)
- **Python Version**: 3.11+

## Development Guidelines

### Code Style
- Use Python type hints everywhere (function signatures, class attributes)
- Use Pydantic v2 models for all request/response schemas
- Use async/await for all I/O operations
- Use `pathlib.Path` instead of string paths
- Follow PEP 8 naming: snake_case for functions/variables, PascalCase for classes
- Keep files under 300 lines; split into submodules when needed

### Architecture Principles
- **Modular**: Each feature is a self-contained module under `app/modules/`
- **Service Layer**: Controllers (routers) -> Services -> Repositories (ORM models)
- **Dependency Injection**: Use FastAPI's `Depends()` for service injection
- **Configuration**: All config via environment variables loaded through pydantic-settings
- **Error Handling**: Custom exception classes + global exception handler middleware

### Key Design Decisions
- Use SQLAlchemy async sessions with `async_sessionmaker`
- Use Server-Sent Events (SSE) for streaming LLM responses (not WebSocket)
- LanceDB tables use snake_case column names
- Meilisearch index naming: `kb_{kb_id}`
- All timestamps use UTC, stored as `DateTime` in MySQL
- Soft delete via `delete_time` column (NULL = active)
- Tree structure in chunks uses materialized path pattern: `0001/0002/0003`

### Documentation Files
Read ALL docs in `docs/` folder before implementation:
1. `docs/01-architecture.md` - Project structure, directory layout, module boundaries
2. `docs/02-database-schema.md` - Complete table schemas with column types and indexes
3. `docs/03-llm-module.md` - Multi-provider LLM integration, streaming, caching, logging
4. `docs/04-rag-module.md` - Document processing pipeline, search, embedding, vector storage
5. `docs/05-ppt-module.md` - PPT generation flow, stage machine, RAG query orchestration
6. `docs/06-api-reference.md` - Every API endpoint with request/response schemas
7. `docs/07-middleware-and-infra.md` - Auth, billing, context, events, Redis, JWT
8. `docs/08-deployment.md` - Docker, docker-compose, environment variables, startup
9. `docs/09-implementation-guide.md` - Implementation order, verification steps, testing

### Implementation Order (CRITICAL)
Follow `docs/09-implementation-guide.md` strictly. Summary:
1. Project scaffolding + Docker + DB setup
2. Database models + migrations
3. Core infrastructure (config, auth, context, error handling)
4. RAG module: knowledge base CRUD -> document upload -> chunking -> embedding -> indexing -> search
5. LLM module: provider/model CRUD -> base adapter -> OpenAI/Anthropic/Gemini adapters -> streaming -> logging
6. PPT module: conversation flow -> stage machine -> RAG query orchestration -> streaming
7. Integration testing with docker-compose up

### Verification Criteria
The system MUST pass these tests after implementation:
1. `docker-compose up` starts all services (app, mysql, redis, meilisearch) without errors
2. Create a knowledge base via API
3. Upload a markdown file, verify it gets chunked and indexed
4. Search the knowledge base and get relevant results
5. Chat with LLM using RAG context (streaming SSE response)
6. All CRUD operations work for KB, documents, providers, models
