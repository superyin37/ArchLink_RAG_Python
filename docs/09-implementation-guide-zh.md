# 09 - 实施指南

## 实施顺序（关键——严格遵循）

### 阶段 1：项目基础
**目标：docker-compose up 可正常运行，应用启动，健康检查通过**

1. **创建项目脚手架**
   - 按 `01-architecture.md` 创建所有目录
   - 编写 `pyproject.toml` / `requirements.txt`
   - 编写 `Dockerfile` 和 `docker-compose.yml`
   - 编写 `.env.example`

2. **应用入口**
   - `app/main.py` - 带生命周期的 FastAPI 应用
   - `app/config.py` - Pydantic Settings
   - 健康检查端点：`GET /health`

3. **数据库设置**
   - `app/database.py` - SQLAlchemy 异步引擎
   - `app/models/base.py` - 含 id、时间戳、软删除的 BaseModel

4. **核心基础设施**
   - `app/core/redis.py` - 带内存回退的 Redis 客户端
   - `app/core/jwt.py` - JWT 编码/解码
   - `app/middleware/error_handler.py` - 全局异常处理器
   - `app/middleware/response_wrapper.py` - 统一响应格式 `R`
   - `app/exceptions.py` - 自定义异常类
   - `app/middleware/auth.py` - 认证中间件（基于白名单）
   - `app/middleware/request_context.py` - 基于 contextvars 的请求上下文

**验证：**
```bash
docker-compose up -d
curl http://localhost:4001/health  # {"status": "ok"}
```

---

### 阶段 2：数据库模型
**目标：所有表在启动时自动创建**

5. **RAG 模型**（`app/models/rag.py`）
   - KnowledgeBase
   - RagDocument
   - RagChunk（含树形结构字段 + 索引）
   - EmbeddingProvider

6. **LLM 模型**（`app/models/llm.py`）
   - LLMProvider
   - LLMModel
   - LLMChat
   - LLMMessage
   - LLMCallLog

7. **Pydantic 模式**（`app/schemas/`）
   - `common.py` - PageRequest、PageResponse、SuccessResponse
   - `rag.py` - 知识库创建/更新、文档上传、搜索请求/响应
   - `llm.py` - Provider/Model CRUD、聊天、消息模式

**验证：**
```bash
# 重启应用，检查 MySQL 表是否已创建
docker-compose restart app
docker exec -it <mysql-container> mysql -u root -pragpassword rag_system -e "SHOW TABLES;"
# 应显示所有 9+ 张表
```

---

### 阶段 3：RAG 模块 - 知识库 CRUD
**目标：创建、列出、更新、删除知识库**

8. **知识库服务**（`app/modules/rag/services/knowledge_base.py`）
   - CRUD 操作
   - 统计计算

9. **知识库路由**（`app/modules/rag/router.py` 的一部分）
   - GET/POST/PUT/DELETE 端点

**验证：**
```bash
# 创建知识库
curl -X POST localhost:4001/api/rag/kb -H "Content-Type: application/json" \
  -d '{"name":"Test","embedding_model":"doubao","vector_db_type":"lancedb"}'

# 列出知识库
curl localhost:4001/api/rag/kb
```

---

### 阶段 4：RAG 模块 - 文档处理流水线
**目标：上传文件，完成切片、嵌入和索引**

10. **文件加载器**（`app/modules/rag/loaders/`）
    - txt.py、pdf.py、docx.py、xlsx.py

11. **树形解析器**（`app/modules/rag/chunk/parser/`）
    - base.py（NodeType、createNode）
    - markdown.py（优化——将段落合并到标题中）
    - txt.py
    - docx.py

12. **切片器**（`app/modules/rag/chunk/`）
    - utils.py（split_by_size、generate_node_id、build_path）
    - chunker.py（tree_to_chunks）

13. **嵌入**（`app/modules/rag/embedding/`）
    - doubao.py（Doubao API 客户端）
    - 服务封装

14. **向量存储**（`app/modules/rag/vector/`）
    - lancedb.py（LanceDB 驱动）
    - VectorDB 服务（实例缓存）

15. **Meilisearch 集成**（`app/modules/rag/meilisearch/`）
    - client.py（单例）
    - index_service.py（CRUD、搜索）

16. **索引服务**（`app/modules/rag/services/indexing.py`）
    - VectorIndexProvider
    - FulltextIndexProvider
    - IndexingService（统一）

17. **文档服务**（`app/modules/rag/services/document.py`）
    - 上传、process_document（完整流水线）、删除
    - 可读性过滤

18. **文档路由**（在 `app/modules/rag/router.py` 中）

**验证：**
```bash
# 上传 Markdown 文件
echo "# Test Document\n\nThis is a test paragraph about AI.\n\n## Section 2\n\nMore content here." > test.md

curl -X POST localhost:4001/api/rag/document/upload \
  -F "kb_id=1" -F "file=@test.md"

# 检查文档状态（应为 2=完成）
curl localhost:4001/api/rag/document/1

# 检查切片
curl localhost:4001/api/rag/document/1/chunks
```

---

### 阶段 5：RAG 模块 - 搜索系统
**目标：搜索从知识库返回相关切片**

19. **搜索组件**（`app/modules/rag/search/`）
    - vector_provider.py
    - fulltext_provider.py
    - fusion.py（RRF）
    - deduplicator.py
    - limiter.py
    - readability.py
    - threshold.py
    - keyword_extractor.py
    - context_optimizer.py
    - tree_assembler.py

20. **检索器**（`app/modules/rag/chunk/retriever.py`）
    - 带子节点/兄弟节点/祖先节点策略的 enhanceRetrieve

21. **搜索服务**（`app/modules/rag/services/search.py`）
    - search()、hybridSearch()、advancedSearch()、getContext()

22. **搜索路由**（在 `app/modules/rag/router.py` 中）

**验证：**
```bash
# 基础搜索
curl -X POST localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id":1,"query":"AI technology","top_k":5}'

# 上下文搜索
curl -X POST localhost:4001/api/rag/search/context \
  -H "Content-Type: application/json" \
  -d '{"kb_id":1,"query":"AI technology","top_k":5}'

# 检查能力
curl localhost:4001/api/rag/search/capabilities
```

---

### 阶段 6：RAG 模块 - 剩余服务
**目标：所有 RAG 端点可用**

23. **嵌入提供者服务** + 路由
24. **统计服务** + 路由
25. **可视化服务** + 路由
26. **Meilisearch 管理**路由
27. **迁移服务**（导出/导入 CLI）

---

### 阶段 7：LLM 模块 - 提供者和模型 CRUD
**目标：通过 API 管理 LLM 提供者和模型**

28. **提供者服务**（`app/modules/llm/services/provider.py`）
29. **模型服务**（`app/modules/llm/services/model.py`）
30. **LLM 路由**（`app/modules/llm/router.py` 的一部分）

**验证：**
```bash
# 创建提供者
curl -X POST localhost:4001/api/llm/provider -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","name":"OpenAI","api_endpoint":"https://api.openai.com/v1","api_type":"openai","api_key":"sk-xxx"}'

# 创建模型
curl -X POST localhost:4001/api/llm/model -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","model_id":"gpt-4o","name":"GPT-4o","pricing":{"input_price":0.0025,"output_price":0.01,"per_tokens":1000,"currency":"USD"}}'
```

---

### 阶段 8：LLM 模块 - 流式聊天
**目标：通过 SSE 流式传输 LLM 响应**

31. **LLM 基础适配器**（`app/modules/llm/completions/base.py`）
32. **OpenAI 适配器**（优先——最常用）
33. **Anthropic 适配器**
34. **Azure、Gemini、VolcEngine 适配器**
35. **LLMOne 工厂**（`app/modules/llm/completions/factory.py`）
36. **响应层**（缓存）- ResponseBase + 适配器
37. **LogRecorder**（`app/modules/llm/utils/log_recorder.py`）
38. **费用服务**（`app/modules/llm/services/cost.py`）
39. **调用日志服务**（`app/modules/llm/services/call_log.py`）
40. **聊天和消息服务**
41. **SSE 流工具**（`app/utils/stream.py`）
42. **重试和故障转移工具**
43. **媒体解析器**
44. **聊天/消息路由端点**

**验证：**
```bash
# 创建聊天
curl -X POST localhost:4001/api/llm/chat -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","title":"Test Chat"}'

# 流式聊天（SSE）——使用 curl 的 -N 参数进行流式输出
curl -N -X POST localhost:4001/api/ppt/stream/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, tell me about AI","model_id":"gpt-4o"}'
```

---

### 阶段 9：PPT 模块
**目标：带 RAG 的完整 PPT 对话流程**

45. **处理器**
    - conversation.py（生命周期）
    - message.py（CRUD）
    - prompt.py（动态构建器）
    - stage.py（状态机）
    - outline.py（大纲数据）
    - case_selection.py（基于 RAG）
    - stream.py（核心流处理器）

46. **RAG 查询**
    - orchestrator.py
    - context_builder.py
    - search_executor.py
    - llm_executor.py
    - stream_publisher.py

47. **PPT 路由**（`app/modules/ppt/router.py`）

**验证：**
```bash
# RAG 增强聊天
curl -N -X POST localhost:4001/api/ppt/stream/rag-query \
  -H "Content-Type: application/json" \
  -d '{"message":"What does this document say about AI?","kb_ids":[1],"model_id":"gpt-4o"}'
```

---

### 阶段 10：集成测试
**目标：完整端到端工作流验证**

48. **完整工作流测试：**
    ```bash
    # 1. 启动所有服务
    docker-compose up -d

    # 2. 健康检查
    curl localhost:4001/health

    # 3. 创建知识库
    curl -X POST localhost:4001/api/rag/kb \
      -H "Content-Type: application/json" \
      -d '{"name":"My KB","embedding_model":"doubao"}'

    # 4. 上传文档
    curl -X POST localhost:4001/api/rag/document/upload \
      -F "kb_id=1" -F "file=@sample.md"

    # 5. 等待处理完成，检查状态
    sleep 5
    curl localhost:4001/api/rag/document/1

    # 6. 搜索
    curl -X POST localhost:4001/api/rag/search \
      -H "Content-Type: application/json" \
      -d '{"kb_id":1,"query":"search query","top_k":5}'

    # 7. 带流式输出的 RAG 聊天
    curl -N -X POST localhost:4001/api/ppt/stream/rag-query \
      -H "Content-Type: application/json" \
      -d '{"message":"question about document","kb_ids":[1],"model_id":"gpt-4o"}'
    ```

---

## 验收标准清单

### 必须具备（P0）
- [ ] `docker-compose up` 启动 app + mysql + redis + meilisearch
- [ ] 健康检查返回 200
- [ ] 通过 POST /api/rag/kb 创建知识库
- [ ] 通过 POST /api/rag/document/upload 上传 Markdown 文件
- [ ] 文档被解析为带标题的树形结构
- [ ] 切片创建时含树形元数据（node_id、parent_id、level、path）
- [ ] 通过 Doubao API 生成嵌入向量（若无密钥则使用模拟）
- [ ] 向量存储到 LanceDB
- [ ] 全文索引在 Meilisearch 中创建（若已启用）
- [ ] POST /api/rag/search 向量搜索返回相关切片
- [ ] POST /api/rag/search 混合搜索（向量 + 全文）可用
- [ ] POST /api/rag/search/context 上下文组装可用
- [ ] 通过 SSE 的 LLM 流式输出可用（至少 OpenAI 适配器）
- [ ] RAG 增强聊天可用（搜索 + LLM 流式输出）
- [ ] 知识库、文档、提供者、模型的所有 CRUD 端点可用

### 应当具备（P1）
- [ ] 多个 LLM 适配器（OpenAI、Anthropic、Azure、Gemini）
- [ ] 提示词缓存（Anthropic、OpenAI）
- [ ] 带费用计算的调用日志
- [ ] 检索增强（兄弟节点、子节点、祖先节点）
- [ ] 结果去重和限制
- [ ] 可读性评分和过滤
- [ ] 动态阈值自适应
- [ ] 搜索融合（RRF）
- [ ] 上下文优化（Token 预算）
- [ ] PPT 阶段状态机
- [ ] 带退避的重试 + 故障转移路由
- [ ] 统计端点
- [ ] 可视化树端点

### 可以具备（P2）
- [ ] 知识库迁移（导出/导入）
- [ ] 文档名称预过滤
- [ ] DOCX/PDF/XLSX 文件支持
- [ ] 案例选择处理器
- [ ] 搜索日志
- [ ] Redis 限流
- [ ] OpenTelemetry 追踪

## 常见陷阱

1. **不要**使用同步 SQLAlchemy——始终使用异步会话
2. **不要**在主请求中 await LLM 流式调用——使用 asyncio.create_task()
3. **不要**为大文件将整个文档加载到内存——使用流式处理
4. **不要**忘记软删除过滤器（`WHERE delete_time IS NULL`）
5. **不要**在响应中以明文存储 API 密钥——在列表端点中脱敏显示
6. **不要**忘记在出错时关闭 SSE 流
7. **不要**在异步处理器中使用阻塞 I/O——文件操作使用 aiofiles
8. **不要**忘记 CORS 中间件——前端需要它
9. **不要**硬编码向量维度——从知识库配置读取
10. **不要**在文档处理流水线中跳过错误处理——出错时将状态更新为 3（失败）
