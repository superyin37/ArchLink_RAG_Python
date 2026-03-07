# 07 - Middleware & Infrastructure

## 1. Authentication Middleware

### Whitelist-based JWT Auth
```python
# app/middleware/auth.py

AUTH_WHITELIST = [
    # Health checks
    {"path": "/health", "methods": []},           # All methods
    {"path": "/api/health", "methods": []},
    {"path": "/ping", "methods": []},

    # Public APIs
    {"path": "/api/rag/provider/supported", "methods": ["GET"]},
    {"path": "/api/rag/provider/vector-db-types", "methods": ["GET"]},
    {"path": "/api/llm/provider", "methods": ["GET"]},
    {"path": "/api/llm/model", "methods": ["GET"]},
    {"path": "/api/llm/model/by-provider", "methods": ["GET"]},

    # Auth endpoints
    {"path": "/api/auth/**", "methods": ["POST"]},

    # Static files
    {"path": "/uploads/**", "methods": ["GET"]},

    # Webhooks
    {"path": "/api/webhook/**", "methods": ["POST"]},
]
```

### Path Matching Rules
```python
def match_path(request_path: str, pattern: str) -> bool:
    """
    Matching rules:
    - Exact: /api/health -> matches only /api/health
    - Single wildcard: /api/public/* -> matches /api/public/xxx (one level)
    - Multi wildcard: /api/public/** -> matches all subpaths
    - Param: /api/share/:id -> matches /api/share/123
    """
    pattern_parts = pattern.split("/")
    path_parts = request_path.split("/")

    for i, pp in enumerate(pattern_parts):
        if pp == "**":
            return True  # Match all remaining
        if i >= len(path_parts):
            return False
        if pp == "*":
            continue  # Match single segment
        if pp.startswith(":"):
            continue  # Match param
        if pp != path_parts[i]:
            return False

    return len(pattern_parts) == len(path_parts)


def is_whitelisted(path: str, method: str) -> bool:
    for rule in AUTH_WHITELIST:
        if match_path(path, rule["path"]):
            if not rule["methods"] or method.upper() in rule["methods"]:
                return True
    return False
```

### Auth Middleware Implementation
```python
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 1. Parse token from headers
        token = request.headers.get("token") or request.headers.get("authorization", "").replace("Bearer ", "")
        user_id = None

        if token:
            payload = decode_token(token)
            if payload:
                user_id = payload.get("user_id")

        # 2. Store in request state
        request.state.user_id = user_id

        # 3. Check whitelist
        if is_whitelisted(request.url.path, request.method):
            return await call_next(request)

        # 4. Require auth for non-whitelisted paths
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": 1, "msg": "Unauthorized", "data": None}
            )

        return await call_next(request)
```

## 2. Request Context (contextvars)

### Implementation
```python
# app/middleware/request_context.py
import contextvars
from uuid import uuid4

_request_context: contextvars.ContextVar[dict] = contextvars.ContextVar('request_context', default={})

class RequestContext:
    @staticmethod
    def get(key: str, default=None):
        return _request_context.get().get(key, default)

    @staticmethod
    def set(key: str, value):
        ctx = _request_context.get().copy()
        ctx[key] = value
        _request_context.set(ctx)

    @staticmethod
    def update(data: dict):
        ctx = _request_context.get().copy()
        ctx.update(data)
        _request_context.set(ctx)

    @staticmethod
    def get_store() -> dict:
        return _request_context.get()

    # Shortcuts
    @staticmethod
    def user_id():
        return RequestContext.get("user_id")

    @staticmethod
    def request_id():
        return RequestContext.get("request_id")

    @staticmethod
    def session_id():
        return RequestContext.get("session_id")
```

### Middleware Integration
```python
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        _request_context.set({
            "request_id": str(uuid4()),
            "user_id": getattr(request.state, "user_id", None),
        })
        response = await call_next(request)
        return response
```

## 3. Error Handler Middleware

```python
# app/middleware/error_handler.py

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except AppException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"code": 1, "msg": e.message, "data": e.data}
            )
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=500,
                content={"code": 1, "msg": "Internal server error", "data": None}
            )
```

### Custom Exceptions
```python
# app/exceptions.py

class AppException(Exception):
    def __init__(self, message="Error", status_code=400, data=None):
        self.message = message
        self.status_code = status_code
        self.data = data

class NotFoundError(AppException):
    def __init__(self, message="Resource not found"):
        super().__init__(message, 404)

class UnauthorizedError(AppException):
    def __init__(self, message="Unauthorized"):
        super().__init__(message, 401)

class ValidationError(AppException):
    def __init__(self, message="Validation failed"):
        super().__init__(message, 422)

# RAG-specific errors
class SearchError(AppException):
    pass

class EmbeddingError(SearchError):
    pass

class VectorDBError(SearchError):
    pass

class KnowledgeBaseNotFoundError(SearchError):
    def __init__(self, kb_id):
        super().__init__(f"Knowledge base {kb_id} not found", 404)
```

## 4. Response Wrapper

```python
# app/middleware/response_wrapper.py

class R:
    """Unified response builder"""

    @staticmethod
    def success(data=None, msg="success", status_code=200):
        return JSONResponse(
            status_code=status_code,
            content={"code": 0, "msg": msg, "data": data}
        )

    @staticmethod
    def fail(msg="error", data=None, status_code=400):
        return JSONResponse(
            status_code=status_code,
            content={"code": 1, "msg": msg, "data": data}
        )

    @staticmethod
    def page(items: list, total: int, page: int, size: int):
        return {"code": 0, "msg": "success", "data": {
            "list": items, "total": total, "page": page, "size": size
        }}
```

## 5. JWT Utilities

```python
# app/core/jwt.py
import jwt
from datetime import datetime, timedelta
from app.config import settings

def encode_token(user: dict) -> str:
    """Generate JWT token"""
    payload = {
        "user_id": user["id"],
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    """Verify and decode JWT token"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
```

## 6. Redis Client

```python
# app/core/redis.py
import redis.asyncio as redis
from app.config import settings

_redis_client: redis.Redis | None = None

async def init_redis():
    global _redis_client
    try:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        await _redis_client.ping()
    except Exception as e:
        logger.warning(f"Redis not available, using memory fallback: {e}")
        _redis_client = None

async def get_redis() -> redis.Redis | None:
    return _redis_client

async def close_redis():
    if _redis_client:
        await _redis_client.close()
```

### Cache Store (Redis + Memory Fallback)
```python
class CacheStore:
    """Redis-first cache with in-memory fallback"""

    def __init__(self):
        self._memory = {}  # Fallback

    async def get(self, key: str):
        r = await get_redis()
        if r:
            val = await r.get(f"cache:{key}")
            return json.loads(val) if val else None
        # Memory fallback
        entry = self._memory.get(key)
        if entry and (entry["exp"] is None or entry["exp"] > time.time()):
            return entry["val"]
        return None

    async def set(self, key: str, value, ttl: int = None):
        r = await get_redis()
        if r:
            val = json.dumps(value, ensure_ascii=False, default=str)
            if ttl:
                await r.setex(f"cache:{key}", ttl, val)
            else:
                await r.set(f"cache:{key}", val)
        else:
            self._memory[key] = {
                "val": value,
                "exp": time.time() + ttl if ttl else None
            }

    async def delete(self, key: str):
        r = await get_redis()
        if r:
            await r.delete(f"cache:{key}")
        else:
            self._memory.pop(key, None)

cache_store = CacheStore()
```

### Rate Limit Store
```python
class RateLimitStore:
    """Sliding window rate limiter"""

    async def increment(self, key: str, window_ms: int) -> int:
        r = await get_redis()
        if r:
            pipe = r.pipeline()
            now = int(time.time() * 1000)
            window_key = f"rl:{key}:{now // window_ms}"
            pipe.incr(window_key)
            pipe.pexpire(window_key, window_ms)
            results = await pipe.execute()
            return results[0]
        # Memory fallback
        return self._memory_increment(key, window_ms)
```

## 7. Event System

```python
# app/core/events.py
import asyncio
from collections import defaultdict

class EventEmitter:
    def __init__(self):
        self._listeners = defaultdict(list)

    def on(self, event: str, callback):
        self._listeners[event].append(callback)

    def off(self, event: str, callback):
        self._listeners[event].remove(callback)

    async def emit(self, event: str, *args, **kwargs):
        """Emit event asynchronously with error isolation"""
        for callback in self._listeners.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Event listener error [{event}]: {e}")

# Singleton
user_events = EventEmitter()

# Event names
USER_CREATED = "user:created"
USER_UPDATED = "user:updated"
USER_DELETED = "user:deleted"
```

## 8. Database Setup

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

DATABASE_URL = (
    f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
    f"?charset=utf8mb4"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    """FastAPI dependency for DB sessions"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_database():
    """Create tables on startup"""
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

## 9. Configuration

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_PORT: int = 4001
    APP_ENV: str = "development"

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "rag_system"

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # JWT
    JWT_SECRET: str = "your-secret-key"

    # Meilisearch
    MEILISEARCH_ENABLED: bool = False
    MEILISEARCH_HOST: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = "masterKey"

    # Doubao Embedding
    DOUBAO_HOST: str = ""
    DOUBAO_API_KEY: str = ""
    DOUBAO_EMBEDDING_MODEL: str = ""
    DOUBAO_EMBEDDING_BATCH_SIZE: int = 16

    # LLM Providers (optional, can use DB config)
    OPENAI_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_KEY: str = ""
    AZURE_BASE: str = ""
    AZURE_KEY: str = ""
    GEMINI_KEY: str = ""
    DEEPSEEK_KEY: str = ""
    ARK_API_KEY: str = ""

    # File upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

## 10. Billing Middleware (Stub)

Currently disabled (payment not enabled). Implement as no-op middleware:
```python
def credits_check(feature_key: str = None, default_cost: int = 1):
    """Billing check middleware - currently pass-through"""
    async def middleware(request, call_next):
        # Payment disabled - pass through
        return await call_next(request)
    return middleware
```

## 11. Logging Setup

```python
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Quiet noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```
