# 09 - Implementation Guide

## Implementation Order (CRITICAL - Follow Strictly)

### Phase 1: Project Foundation
**Goal: docker-compose up works, app starts, health check passes**

1. **Create project scaffolding**
   - Create all directories per `01-architecture.md`
   - Write `pyproject.toml` / `requirements.txt`
   - Write `Dockerfile` and `docker-compose.yml`
   - Write `.env.example`

2. **App entry point**
   - `app/main.py` - FastAPI app with lifespan
   - `app/config.py` - Pydantic Settings
   - Health check endpoint: `GET /health`

3. **Database setup**
   - `app/database.py` - SQLAlchemy async engine
   - `app/models/base.py` - BaseModel with id, timestamps, soft delete

4. **Core infrastructure**
   - `app/core/redis.py` - Redis client with memory fallback
   - `app/core/jwt.py` - JWT encode/decode
   - `app/middleware/error_handler.py` - Global exception handler
   - `app/middleware/response_wrapper.py` - Unified response format `R`
   - `app/exceptions.py` - Custom exception classes
   - `app/middleware/auth.py` - Auth middleware (whitelist-based)
   - `app/middleware/request_context.py` - contextvars-based request context

**Verification:**
```bash
docker-compose up -d
curl http://localhost:4001/health  # {"status": "ok"}
```

---

### Phase 2: Database Models
**Goal: All tables created automatically on startup**

5. **RAG models** (`app/models/rag.py`)
   - KnowledgeBase
   - RagDocument
   - RagChunk (with tree structure fields + indexes)
   - EmbeddingProvider

6. **LLM models** (`app/models/llm.py`)
   - LLMProvider
   - LLMModel
   - LLMChat
   - LLMMessage
   - LLMCallLog

7. **Pydantic schemas** (`app/schemas/`)
   - `common.py` - PageRequest, PageResponse, SuccessResponse
   - `rag.py` - KB create/update, document upload, search request/response
   - `llm.py` - Provider/Model CRUD, chat, message schemas

**Verification:**
```bash
# Restart app, check MySQL tables created
docker-compose restart app
docker exec -it <mysql-container> mysql -u root -pragpassword rag_system -e "SHOW TABLES;"
# Should show all 9+ tables
```

---

### Phase 3: RAG Module - Knowledge Base CRUD
**Goal: Create, list, update, delete knowledge bases**

8. **KB service** (`app/modules/rag/services/knowledge_base.py`)
   - CRUD operations
   - Stats calculation

9. **KB router** (part of `app/modules/rag/router.py`)
   - GET/POST/PUT/DELETE endpoints

**Verification:**
```bash
# Create KB
curl -X POST localhost:4001/api/rag/kb -H "Content-Type: application/json" \
  -d '{"name":"Test","embedding_model":"doubao","vector_db_type":"lancedb"}'

# List KBs
curl localhost:4001/api/rag/kb
```

---

### Phase 4: RAG Module - Document Processing Pipeline
**Goal: Upload a file, it gets chunked, embedded, and indexed**

10. **File loaders** (`app/modules/rag/loaders/`)
    - txt.py, pdf.py, docx.py, xlsx.py

11. **Tree parser** (`app/modules/rag/chunk/parser/`)
    - base.py (NodeType, createNode)
    - markdown.py (optimized - merge paragraphs into headings)
    - txt.py
    - docx.py

12. **Chunker** (`app/modules/rag/chunk/`)
    - utils.py (split_by_size, generate_node_id, build_path)
    - chunker.py (tree_to_chunks)

13. **Embedding** (`app/modules/rag/embedding/`)
    - doubao.py (Doubao API client)
    - Service wrapper

14. **Vector storage** (`app/modules/rag/vector/`)
    - lancedb.py (LanceDB driver)
    - VectorDB service (instance cache)

15. **Meilisearch integration** (`app/modules/rag/meilisearch/`)
    - client.py (singleton)
    - index_service.py (CRUD, search)

16. **Indexing service** (`app/modules/rag/services/indexing.py`)
    - VectorIndexProvider
    - FulltextIndexProvider
    - IndexingService (unified)

17. **Document service** (`app/modules/rag/services/document.py`)
    - Upload, process_document (full pipeline), delete
    - Readability filter

18. **Document router** (in `app/modules/rag/router.py`)

**Verification:**
```bash
# Upload a markdown file
echo "# Test Document\n\nThis is a test paragraph about AI.\n\n## Section 2\n\nMore content here." > test.md

curl -X POST localhost:4001/api/rag/document/upload \
  -F "kb_id=1" -F "file=@test.md"

# Check document status (should be 2=completed)
curl localhost:4001/api/rag/document/1

# Check chunks
curl localhost:4001/api/rag/document/1/chunks
```

---

### Phase 5: RAG Module - Search System
**Goal: Search returns relevant chunks from the knowledge base**

19. **Search components** (`app/modules/rag/search/`)
    - vector_provider.py
    - fulltext_provider.py
    - fusion.py (RRF)
    - deduplicator.py
    - limiter.py
    - readability.py
    - threshold.py
    - keyword_extractor.py
    - context_optimizer.py
    - tree_assembler.py

20. **Retriever** (`app/modules/rag/chunk/retriever.py`)
    - enhanceRetrieve with children/siblings/ancestors strategies

21. **Search service** (`app/modules/rag/services/search.py`)
    - search(), hybridSearch(), advancedSearch(), getContext()

22. **Search router** (in `app/modules/rag/router.py`)

**Verification:**
```bash
# Basic search
curl -X POST localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id":1,"query":"AI technology","top_k":5}'

# Context search
curl -X POST localhost:4001/api/rag/search/context \
  -H "Content-Type: application/json" \
  -d '{"kb_id":1,"query":"AI technology","top_k":5}'

# Check capabilities
curl localhost:4001/api/rag/search/capabilities
```

---

### Phase 6: RAG Module - Remaining Services
**Goal: All RAG endpoints functional**

23. **Embedding provider service** + router
24. **Statistics service** + router
25. **Visual service** + router
26. **Meilisearch management** router
27. **Migration service** (export/import CLI)

---

### Phase 7: LLM Module - Provider & Model CRUD
**Goal: Manage LLM providers and models via API**

28. **Provider service** (`app/modules/llm/services/provider.py`)
29. **Model service** (`app/modules/llm/services/model.py`)
30. **LLM router** (part of `app/modules/llm/router.py`)

**Verification:**
```bash
# Create a provider
curl -X POST localhost:4001/api/llm/provider -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","name":"OpenAI","api_endpoint":"https://api.openai.com/v1","api_type":"openai","api_key":"sk-xxx"}'

# Create a model
curl -X POST localhost:4001/api/llm/model -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","model_id":"gpt-4o","name":"GPT-4o","pricing":{"input_price":0.0025,"output_price":0.01,"per_tokens":1000,"currency":"USD"}}'
```

---

### Phase 8: LLM Module - Streaming Chat
**Goal: Stream LLM responses via SSE**

31. **LLM base adapter** (`app/modules/llm/completions/base.py`)
32. **OpenAI adapter** (priority - most common)
33. **Anthropic adapter**
34. **Azure, Gemini, VolcEngine adapters**
35. **LLMOne factory** (`app/modules/llm/completions/factory.py`)
36. **Response layer** (caching) - ResponseBase + adapters
37. **LogRecorder** (`app/modules/llm/utils/log_recorder.py`)
38. **Cost service** (`app/modules/llm/services/cost.py`)
39. **Call log service** (`app/modules/llm/services/call_log.py`)
40. **Chat & Message services**
41. **SSE stream utilities** (`app/utils/stream.py`)
42. **Retry & Fallback utilities**
43. **Media resolver**
44. **Chat/Message router endpoints**

**Verification:**
```bash
# Create a chat
curl -X POST localhost:4001/api/llm/chat -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","title":"Test Chat"}'

# Stream chat (SSE) - use curl with -N for streaming
curl -N -X POST localhost:4001/api/ppt/stream/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, tell me about AI","model_id":"gpt-4o"}'
```

---

### Phase 9: PPT Module
**Goal: Full PPT conversation flow with RAG**

45. **Handlers**
    - conversation.py (lifecycle)
    - message.py (CRUD)
    - prompt.py (dynamic builder)
    - stage.py (state machine)
    - outline.py (outline data)
    - case_selection.py (RAG-based)
    - stream.py (core stream handler)

46. **RAG Query**
    - orchestrator.py
    - context_builder.py
    - search_executor.py
    - llm_executor.py
    - stream_publisher.py

47. **PPT router** (`app/modules/ppt/router.py`)

**Verification:**
```bash
# RAG-enhanced chat
curl -N -X POST localhost:4001/api/ppt/stream/rag-query \
  -H "Content-Type: application/json" \
  -d '{"message":"What does this document say about AI?","kb_ids":[1],"model_id":"gpt-4o"}'
```

---

### Phase 10: Integration Testing
**Goal: Full end-to-end workflow verified**

48. **Full workflow test:**
    ```bash
    # 1. Start everything
    docker-compose up -d

    # 2. Health check
    curl localhost:4001/health

    # 3. Create KB
    curl -X POST localhost:4001/api/rag/kb \
      -H "Content-Type: application/json" \
      -d '{"name":"My KB","embedding_model":"doubao"}'

    # 4. Upload document
    curl -X POST localhost:4001/api/rag/document/upload \
      -F "kb_id=1" -F "file=@sample.md"

    # 5. Wait for processing, check status
    sleep 5
    curl localhost:4001/api/rag/document/1

    # 6. Search
    curl -X POST localhost:4001/api/rag/search \
      -H "Content-Type: application/json" \
      -d '{"kb_id":1,"query":"search query","top_k":5}'

    # 7. RAG chat with streaming
    curl -N -X POST localhost:4001/api/ppt/stream/rag-query \
      -H "Content-Type: application/json" \
      -d '{"message":"question about document","kb_ids":[1],"model_id":"gpt-4o"}'
    ```

---

## Acceptance Criteria Checklist

### Must Have (P0)
- [ ] `docker-compose up` starts app + mysql + redis + meilisearch
- [ ] Health check returns 200
- [ ] Create knowledge base via POST /api/rag/kb
- [ ] Upload markdown file via POST /api/rag/document/upload
- [ ] Document gets parsed into tree structure with headings
- [ ] Chunks created with tree metadata (node_id, parent_id, level, path)
- [ ] Embeddings generated via Doubao API (or mock if no key)
- [ ] Vectors stored in LanceDB
- [ ] Fulltext index created in Meilisearch (if enabled)
- [ ] Vector search returns relevant chunks POST /api/rag/search
- [ ] Hybrid search (vector + fulltext) works POST /api/rag/search
- [ ] Context assembly works POST /api/rag/search/context
- [ ] LLM streaming via SSE works (at least OpenAI adapter)
- [ ] RAG-enhanced chat works (search + LLM streaming)
- [ ] All CRUD endpoints for KB, document, provider, model work

### Should Have (P1)
- [ ] Multiple LLM adapters (OpenAI, Anthropic, Azure, Gemini)
- [ ] Prompt caching (Anthropic, OpenAI)
- [ ] Call logging with cost calculation
- [ ] Retrieval enhancement (siblings, children, ancestors)
- [ ] Result deduplication and limiting
- [ ] Readability scoring and filtering
- [ ] Dynamic threshold adaptation
- [ ] Search fusion (RRF)
- [ ] Context optimization (token budget)
- [ ] PPT stage state machine
- [ ] Retry with backoff + fallback routing
- [ ] Statistics endpoints
- [ ] Visual tree endpoints

### Nice to Have (P2)
- [ ] KB migration (export/import)
- [ ] Document name prefiltering
- [ ] DOCX/PDF/XLSX file support
- [ ] Case selection handler
- [ ] Search logging
- [ ] Redis rate limiting
- [ ] OpenTelemetry tracing

## Common Pitfalls to Avoid

1. **DO NOT** use synchronous SQLAlchemy - always use async sessions
2. **DO NOT** await LLM streaming calls in the main request - use asyncio.create_task()
3. **DO NOT** load entire documents into memory for large files - use streaming
4. **DO NOT** forget soft delete filter (`WHERE delete_time IS NULL`) in queries
5. **DO NOT** store API keys in plain text in responses - mask them in list endpoints
6. **DO NOT** forget to close SSE streams on error
7. **DO NOT** use blocking I/O in async handlers - use aiofiles for file operations
8. **DO NOT** forget CORS middleware - frontend needs it
9. **DO NOT** hardcode vector dimensions - read from KB config
10. **DO NOT** skip error handling in the document processing pipeline - update status to 3 (failed) on errors
