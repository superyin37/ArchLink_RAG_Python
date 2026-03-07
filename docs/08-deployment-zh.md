# 08 - 部署

## Docker Compose（全栈）

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "4001:4001"
    environment:
      - APP_PORT=4001
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_USER=root
      - MYSQL_PASSWORD=ragpassword
      - MYSQL_DB=rag_system
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MEILISEARCH_ENABLED=true
      - MEILISEARCH_HOST=http://meilisearch:7700
      - MEILISEARCH_API_KEY=masterKey
      # LLM 密钥——在 .env 文件中设置
      - OPENAI_KEY=${OPENAI_KEY:-}
      - ANTHROPIC_KEY=${ANTHROPIC_KEY:-}
      - DEEPSEEK_KEY=${DEEPSEEK_KEY:-}
      - DOUBAO_HOST=${DOUBAO_HOST:-}
      - DOUBAO_API_KEY=${DOUBAO_API_KEY:-}
      - DOUBAO_EMBEDDING_MODEL=${DOUBAO_EMBEDDING_MODEL:-}
      - JWT_SECRET=${JWT_SECRET:-default-secret-change-me}
    volumes:
      - ./uploads:/app/uploads
      - ./database:/app/database
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      meilisearch:
        condition: service_started
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ragpassword
      MYSQL_DATABASE: rag_system
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
    ports:
      - "3307:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    command: --default-authentication-plugin=mysql_native_password --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  meilisearch:
    image: getmeili/meilisearch:v1.6
    ports:
      - "7700:7700"
    environment:
      - MEILI_MASTER_KEY=masterKey
      - MEILI_ENV=development
    volumes:
      - meilisearch_data:/meili_data

volumes:
  mysql_data:
  redis_data:
  meilisearch_data:
```

## Dockerfile

```dockerfile
FROM python:3.11-slim

# 系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

# 创建目录
RUN mkdir -p /app/uploads /app/database /app/logs

# 暴露端口
EXPOSE 4001

# 使用 uvicorn 运行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4001", "--workers", "1"]
```

## requirements.txt

```
# Web 框架
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
sse-starlette>=2.0.0

# 数据库
sqlalchemy[asyncio]>=2.0.25
aiomysql>=0.2.0
alembic>=1.13.0

# Redis
redis[hiredis]>=5.0.0

# LLM SDKs
openai>=1.12.0
anthropic>=0.18.0
google-generativeai>=0.4.0
httpx>=0.27.0

# 向量数据库
lancedb>=0.5.0
pyarrow>=15.0.0

# 全文搜索
meilisearch-python-sdk>=3.0.0

# 文档解析
python-docx>=1.1.0
PyPDF2>=3.0.0
openpyxl>=3.1.0
markdown>=3.5.0
mammoth>=1.6.0

# 认证
PyJWT>=2.8.0
bcrypt>=4.1.0

# 工具
pydantic>=2.6.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
aiofiles>=23.2.0

# 可观测性（可选）
# opentelemetry-api>=1.22.0
# opentelemetry-sdk>=1.22.0
```

## 环境变量（.env.example）

```bash
# 应用
APP_PORT=4001
APP_ENV=development

# MySQL
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=ragpassword
MYSQL_DB=rag_system

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# JWT
JWT_SECRET=your-secret-key-change-in-production

# Meilisearch
MEILISEARCH_ENABLED=true
MEILISEARCH_HOST=http://localhost:7700
MEILISEARCH_API_KEY=masterKey

# Doubao 嵌入（火山引擎）
DOUBAO_HOST=https://ark.cn-beijing.volces.com
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_EMBEDDING_MODEL=your-embedding-model-endpoint
DOUBAO_EMBEDDING_BATCH_SIZE=16

# LLM 提供者密钥（通过 API 或环境变量配置）
OPENAI_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
ANTHROPIC_KEY=
AZURE_BASE=
AZURE_KEY=
GEMINI_KEY=
DEEPSEEK_KEY=
ARK_API_KEY=

# 文件上传
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=104857600
```

## 启动序列

```python
# app/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 1. 配置日志
    setup_logging()
    logger.info("正在启动 RAG 系统...")

    # 2. 初始化数据库（创建表）
    await init_database()
    logger.info("数据库已初始化")

    # 3. 初始化 Redis
    await init_redis()
    logger.info("Redis 已初始化")

    # 4. 初始化 Meilisearch 客户端（若已启用）
    if settings.MEILISEARCH_ENABLED:
        await init_meilisearch()
        logger.info("Meilisearch 已初始化")

    # 5. 自动注册 LLM 适配器
    from app.modules.llm.completions.factory import LLMOne
    LLMOne.auto_register()
    logger.info("LLM 适配器已注册")

    # 6. 创建上传目录
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path("database/lancedb").mkdir(parents=True, exist_ok=True)

    logger.info(f"RAG 系统已在端口 {settings.APP_PORT} 就绪")

    yield  # 应用运行中

    # 关闭
    await close_redis()
    logger.info("RAG 系统已完成关闭")
```

## 快速启动命令

```bash
# 1. 克隆并配置
cp .env.example .env
# 编辑 .env，填入您的 API 密钥

# 2. 启动所有服务
docker-compose up -d

# 3. 检查健康状态
curl http://localhost:4001/health

# 4. 创建知识库
curl -X POST http://localhost:4001/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{"name": "Test KB", "embedding_model": "doubao", "vector_db_type": "lancedb"}'

# 5. 上传文档
curl -X POST http://localhost:4001/api/rag/document/upload \
  -F "kb_id=1" \
  -F "file=@test.md"

# 6. 搜索
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": 1, "query": "your search query", "top_k": 5}'
```

## 生产环境注意事项

1. **工作进程**：生产环境使用 `--workers 4`（与 CPU 核数匹配）
2. **HTTPS**：部署在带 SSL 的 nginx/caddy 反向代理后面
3. **数据库**：使用托管 MySQL（RDS）并配置连接池
4. **Redis**：使用托管 Redis（ElastiCache）并启用认证
5. **监控**：添加 Prometheus 指标端点 + Grafana 仪表板
6. **日志**：通过结构化 JSON 日志将日志发送到 ELK/CloudWatch
7. **密钥管理**：使用 Vault 或云密钥管理器代替 .env 文件
8. **备份**：定期调度 MySQL 转储 + LanceDB 目录备份
