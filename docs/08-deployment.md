# 08 - Deployment

## Docker Compose (Full Stack)

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
      # LLM keys - set in .env file
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

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

# Create directories
RUN mkdir -p /app/uploads /app/database /app/logs

# Expose port
EXPOSE 4001

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4001", "--workers", "1"]
```

## requirements.txt

```
# Web framework
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
sse-starlette>=2.0.0

# Database
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

# Vector DB
lancedb>=0.5.0
pyarrow>=15.0.0

# Fulltext search
meilisearch-python-sdk>=3.0.0

# Document parsing
python-docx>=1.1.0
PyPDF2>=3.0.0
openpyxl>=3.1.0
markdown>=3.5.0
mammoth>=1.6.0

# Auth
PyJWT>=2.8.0
bcrypt>=4.1.0

# Utils
pydantic>=2.6.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
aiofiles>=23.2.0

# Observability (optional)
# opentelemetry-api>=1.22.0
# opentelemetry-sdk>=1.22.0
```

## Environment Variables (.env.example)

```bash
# App
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

# Doubao Embedding (Volcengine)
DOUBAO_HOST=https://ark.cn-beijing.volces.com
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_EMBEDDING_MODEL=your-embedding-model-endpoint
DOUBAO_EMBEDDING_BATCH_SIZE=16

# LLM Provider Keys (configure via API or env)
OPENAI_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
ANTHROPIC_KEY=
AZURE_BASE=
AZURE_KEY=
GEMINI_KEY=
DEEPSEEK_KEY=
ARK_API_KEY=

# File Upload
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=104857600
```

## Startup Sequence

```python
# app/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle"""
    # 1. Setup logging
    setup_logging()
    logger.info("Starting RAG System...")

    # 2. Initialize database (create tables)
    await init_database()
    logger.info("Database initialized")

    # 3. Initialize Redis
    await init_redis()
    logger.info("Redis initialized")

    # 4. Initialize Meilisearch client (if enabled)
    if settings.MEILISEARCH_ENABLED:
        await init_meilisearch()
        logger.info("Meilisearch initialized")

    # 5. Auto-register LLM adapters
    from app.modules.llm.completions.factory import LLMOne
    LLMOne.auto_register()
    logger.info("LLM adapters registered")

    # 6. Create upload directory
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path("database/lancedb").mkdir(parents=True, exist_ok=True)

    logger.info(f"RAG System ready on port {settings.APP_PORT}")

    yield  # App is running

    # Shutdown
    await close_redis()
    logger.info("RAG System shutdown complete")
```

## Quick Start Commands

```bash
# 1. Clone and setup
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker-compose up -d

# 3. Check health
curl http://localhost:4001/health

# 4. Create a knowledge base
curl -X POST http://localhost:4001/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{"name": "Test KB", "embedding_model": "doubao", "vector_db_type": "lancedb"}'

# 5. Upload a document
curl -X POST http://localhost:4001/api/rag/document/upload \
  -F "kb_id=1" \
  -F "file=@test.md"

# 6. Search
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": 1, "query": "your search query", "top_k": 5}'
```

## Production Considerations

1. **Workers**: Use `--workers 4` for production (match CPU cores)
2. **HTTPS**: Put behind nginx/caddy reverse proxy with SSL
3. **Database**: Use managed MySQL (RDS) with connection pooling
4. **Redis**: Use managed Redis (ElastiCache) with authentication
5. **Monitoring**: Add Prometheus metrics endpoint + Grafana dashboard
6. **Logging**: Ship logs to ELK/CloudWatch via structured JSON logging
7. **Secrets**: Use vault or cloud secret manager instead of .env
8. **Backups**: Schedule MySQL dumps + LanceDB directory backups
