# 01 - 架构与项目结构

## 目录布局

```
rag-python/
├── CLAUDE.md                          # AI 开发说明
├── docs/                              # 开发文档
├── docker-compose.yml                 # 全栈部署
├── Dockerfile                         # Python 应用容器
├── pyproject.toml                     # Python 项目配置（使用 poetry 或 pip）
├── requirements.txt                   # Python 依赖
├── alembic.ini                        # Alembic 迁移配置
├── alembic/                           # 数据库迁移
│   ├── env.py
│   └── versions/
├── .env.example                       # 环境变量模板
├── uploads/                           # 上传文件存储
├── database/                          # LanceDB 数据目录
│   └── lancedb/
└── app/
    ├── __init__.py
    ├── main.py                        # FastAPI 应用入口
    ├── config.py                      # Pydantic Settings 配置
    ├── database.py                    # SQLAlchemy 引擎 + 会话设置
    ├── dependencies.py                # 共享 FastAPI 依赖
    ├── exceptions.py                  # 自定义异常类
    ├── middleware/
    │   ├── __init__.py
    │   ├── auth.py                    # JWT Token 解析 + 白名单
    │   ├── error_handler.py           # 全局异常处理器
    │   ├── request_context.py         # 异步上下文（contextvars）
    │   └── response_wrapper.py        # 统一 JSON 响应格式
    ├── core/
    │   ├── __init__.py
    │   ├── redis.py                   # Redis 客户端 + 缓存存储 + 限流
    │   ├── events.py                  # 事件发射器（用户事件）
    │   └── jwt.py                     # JWT 编码/解码
    ├── models/                        # SQLAlchemy ORM 模型（共享）
    │   ├── __init__.py
    │   ├── base.py                    # BaseModel，含 id、create_time、update_time、delete_time
    │   ├── rag.py                     # KnowledgeBase、RagDocument、RagChunk、EmbeddingProvider
    │   └── llm.py                     # LLMProvider、LLMModel、LLMChat、LLMMessage、LLMCallLog
    ├── schemas/                       # Pydantic 请求/响应模式
    │   ├── __init__.py
    │   ├── common.py                  # PageResponse、SuccessResponse 等
    │   ├── rag.py                     # RAG 相关模式
    │   └── llm.py                     # LLM 相关模式
    ├── modules/
    │   ├── __init__.py
    │   ├── rag/                       # RAG 模块
    │   │   ├── __init__.py
    │   │   ├── router.py              # 所有 RAG API 路由（使用带 tags 的 APIRouter）
    │   │   ├── services/
    │   │   │   ├── __init__.py
    │   │   │   ├── knowledge_base.py  # 知识库 CRUD + 统计
    │   │   │   ├── document.py        # 文档上传、处理、切片、删除
    │   │   │   ├── search.py          # 向量搜索、全文搜索、混合搜索、高级搜索
    │   │   │   ├── embedding.py       # 嵌入生成（Doubao API）
    │   │   │   ├── indexing.py        # 统一索引（向量 + 全文）
    │   │   │   ├── provider.py        # EmbeddingProvider CRUD
    │   │   │   ├── statistics.py      # RAG 统计
    │   │   │   ├── visual.py          # 文档树可视化
    │   │   │   └── vector_db.py       # LanceDB 实例管理
    │   │   ├── chunk/
    │   │   │   ├── __init__.py
    │   │   │   ├── chunker.py         # 树转切片
    │   │   │   ├── parser/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── base.py        # NodeType、createNode、树工具
    │   │   │   │   ├── markdown.py    # Markdown 解析器（优化版）
    │   │   │   │   ├── docx.py        # DOCX 解析器
    │   │   │   │   └── txt.py         # 纯文本解析器
    │   │   │   ├── retriever.py       # 召回增强（子节点/兄弟节点/祖先节点）
    │   │   │   └── utils.py           # splitBySize、generateNodeId、buildPath
    │   │   ├── search/
    │   │   │   ├── __init__.py
    │   │   │   ├── vector_provider.py     # 通过 LanceDB 进行向量搜索
    │   │   │   ├── fulltext_provider.py   # 通过 Meilisearch 进行全文搜索
    │   │   │   ├── fusion.py              # RRF / 加权 / 线性融合
    │   │   │   ├── deduplicator.py        # ID + 内容 + 父子节点去重
    │   │   │   ├── limiter.py             # Token 预算结果限制
    │   │   │   ├── readability.py         # 可读性评分 + 重排
    │   │   │   ├── threshold.py           # 动态阈值自适应
    │   │   │   ├── keyword_extractor.py   # 全文搜索关键词提取
    │   │   │   ├── doc_prefilter.py       # 文档名称预过滤
    │   │   │   ├── context_optimizer.py   # 按 Token 预算压缩上下文
    │   │   │   └── tree_assembler.py      # 树上下文组装
    │   │   ├── vector/
    │   │   │   ├── __init__.py
    │   │   │   └── lancedb.py         # LanceDB 驱动封装
    │   │   ├── embedding/
    │   │   │   ├── __init__.py
    │   │   │   └── doubao.py          # Doubao 嵌入 API 客户端
    │   │   ├── loaders/
    │   │   │   ├── __init__.py
    │   │   │   ├── docx.py            # DOCX 加载器
    │   │   │   ├── pdf.py             # PDF 加载器
    │   │   │   ├── txt.py             # TXT/MD 加载器
    │   │   │   └── xlsx.py            # XLSX 问答加载器
    │   │   ├── meilisearch/
    │   │   │   ├── __init__.py
    │   │   │   ├── client.py          # Meilisearch 客户端单例
    │   │   │   └── index_service.py   # 索引 CRUD、搜索、重建
    │   │   ├── migration/
    │   │   │   ├── __init__.py
    │   │   │   ├── service.py         # 导出/导入知识库
    │   │   │   ├── export_cli.py      # CLI 导出命令
    │   │   │   └── import_cli.py      # CLI 导入命令
    │   │   └── config.py              # RAG 配置常量
    │   ├── llm/                       # LLM 模块
    │   │   ├── __init__.py
    │   │   ├── router.py              # LLM API 路由
    │   │   ├── services/
    │   │   │   ├── __init__.py
    │   │   │   ├── provider.py        # LLM 提供者 CRUD
    │   │   │   ├── model.py           # LLM 模型 CRUD
    │   │   │   ├── chat.py            # 聊天会话管理
    │   │   │   ├── message.py         # 消息持久化
    │   │   │   ├── call_log.py        # 调用日志 CRUD + 统计
    │   │   │   └── cost.py            # 费用计算
    │   │   ├── completions/
    │   │   │   ├── __init__.py
    │   │   │   ├── base.py            # LLMBase - 流解析、媒体处理
    │   │   │   ├── openai.py          # OpenAI 适配器
    │   │   │   ├── anthropic.py       # Anthropic 适配器
    │   │   │   ├── azure.py           # Azure OpenAI 适配器
    │   │   │   ├── gemini.py          # Google Gemini 适配器
    │   │   │   ├── volcengine.py      # 火山引擎适配器
    │   │   │   └── factory.py         # LLMOne - 自动注册 + 工厂
    │   │   ├── responses/
    │   │   │   ├── __init__.py
    │   │   │   ├── base.py            # ResponseBase - 缓存控制
    │   │   │   ├── openai.py          # OpenAI 含自动缓存
    │   │   │   ├── anthropic.py       # Anthropic 含提示词缓存
    │   │   │   ├── azure.py           # Azure 响应适配器
    │   │   │   ├── gemini.py          # Gemini 响应适配器
    │   │   │   └── factory.py         # ResponseOne - 自动注册 + 工厂
    │   │   ├── handlers/
    │   │   │   ├── __init__.py
    │   │   │   ├── chat_manager.py    # 聊天生命周期管理
    │   │   │   └── message_persister.py # 消息保存/查询
    │   │   ├── utils/
    │   │   │   ├── __init__.py
    │   │   │   ├── log_recorder.py    # LLM 调用生命周期日志
    │   │   │   ├── media_resolver.py  # 多格式媒体转数据 URL
    │   │   │   ├── model_loader.py    # 从数据库加载模型配置
    │   │   │   ├── stream.py          # SSE 流工具
    │   │   │   ├── retry.py           # withRetryBackoff
    │   │   │   └── fallback.py        # withFallbackRouter
    │   │   └── config.py              # LLM 配置
    │   └── ppt/                       # PPT 模块
    │       ├── __init__.py
    │       ├── router.py              # PPT API 路由
    │       └── handlers/
    │           ├── __init__.py
    │           ├── stream.py          # 核心流处理器
    │           ├── conversation.py    # 对话生命周期
    │           ├── message.py         # 消息 CRUD
    │           ├── prompt.py          # 按阶段构建提示词
    │           ├── outline.py         # 大纲数据管理
    │           ├── stage.py           # 阶段状态机
    │           ├── case_selection.py  # 带 RAG 的案例选择
    │           └── rag_query/
    │               ├── __init__.py
    │               ├── orchestrator.py    # RAG 查询编排
    │               ├── context_builder.py # RAG 上下文组装
    │               ├── search_executor.py # 搜索包装器
    │               ├── llm_executor.py    # LLM 调用包装器
    │               └── stream_publisher.py # SSE 事件发布器
    └── utils/
        ├── __init__.py
        ├── stream.py                  # SSE 格式化工具
        └── message_builder.py         # LLM 消息构建器
```

## 模块边界

### 模块通信规则
- **路由器（Router）** 只调用**服务（Service）**（不直接访问 ORM 模型）
- **服务（Service）** 访问 **ORM 模型**，可调用其他服务
- **跨模块调用**：只通过服务接口（例如 RAG 搜索服务调用嵌入服务）
- **共享模型**位于 `app/models/`（不在模块内部）
- **共享模式**位于 `app/schemas/`

### 模块依赖关系
```
ppt -> llm（LLM 调用）
ppt -> rag（RAG 搜索）
rag -> llm（可选，用于文档名称预过滤）
llm -> （独立，无模块依赖）
```

## FastAPI 应用设置（`app/main.py`）

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化 DB、Redis、Meilisearch
    await init_database()
    await init_redis()
    await init_meilisearch()
    yield
    # 关闭：断开连接
    await close_redis()

app = FastAPI(title="RAG System", lifespan=lifespan)

# CORS - 允许所有来源
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# 全局异常处理器
app.add_middleware(ErrorHandlerMiddleware)

# 认证中间件
app.add_middleware(AuthMiddleware)

# 注册路由
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(llm_router, prefix="/api/llm", tags=["LLM"])
app.include_router(ppt_router, prefix="/api/ppt", tags=["PPT"])

# 健康检查
@app.get("/health")
async def health(): return {"status": "ok"}

# 上传文件静态服务
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

## 统一响应格式

所有 API 响应遵循以下结构：
```json
{
  "code": 0,       // 0 = 成功，1 = 错误
  "msg": "success",
  "data": { ... }
}
```

通过响应包装器工具实现：
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
