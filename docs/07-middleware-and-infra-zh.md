# 07 - 中间件与基础设施

## 1. 认证中间件

### 基于白名单的 JWT 认证
```python
# app/middleware/auth.py

AUTH_WHITELIST = [
    # 健康检查
    {"path": "/health", "methods": []},           # 所有方法
    {"path": "/api/health", "methods": []},
    {"path": "/ping", "methods": []},

    # 公开 API
    {"path": "/api/rag/provider/supported", "methods": ["GET"]},
    {"path": "/api/rag/provider/vector-db-types", "methods": ["GET"]},
    {"path": "/api/llm/provider", "methods": ["GET"]},
    {"path": "/api/llm/model", "methods": ["GET"]},
    {"path": "/api/llm/model/by-provider", "methods": ["GET"]},

    # 认证端点
    {"path": "/api/auth/**", "methods": ["POST"]},

    # 静态文件
    {"path": "/uploads/**", "methods": ["GET"]},

    # Webhook
    {"path": "/api/webhook/**", "methods": ["POST"]},
]
```

### 路径匹配规则
```python
def match_path(request_path: str, pattern: str) -> bool:
    """
    匹配规则：
    - 精确匹配：/api/health -> 仅匹配 /api/health
    - 单层通配符：/api/public/* -> 匹配 /api/public/xxx（一层）
    - 多层通配符：/api/public/** -> 匹配所有子路径
    - 参数：/api/share/:id -> 匹配 /api/share/123
    """
    pattern_parts = pattern.split("/")
    path_parts = request_path.split("/")

    for i, pp in enumerate(pattern_parts):
        if pp == "**":
            return True  # 匹配所有剩余部分
        if i >= len(path_parts):
            return False
        if pp == "*":
            continue  # 匹配单个段
        if pp.startswith(":"):
            continue  # 匹配参数
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

### 认证中间件实现
```python
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 1. 从请求头解析 token
        token = request.headers.get("token") or request.headers.get("authorization", "").replace("Bearer ", "")
        user_id = None

        if token:
            payload = decode_token(token)
            if payload:
                user_id = payload.get("user_id")

        # 2. 存储到请求状态
        request.state.user_id = user_id

        # 3. 检查白名单
        if is_whitelisted(request.url.path, request.method):
            return await call_next(request)

        # 4. 非白名单路径要求认证
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": 1, "msg": "Unauthorized", "data": None}
            )

        return await call_next(request)
```

## 2. 请求上下文（contextvars）

### 实现
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

    # 快捷方法
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

### 中间件集成
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

## 3. 错误处理中间件

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
            logger.exception(f"未处理的错误：{e}")
            return JSONResponse(
                status_code=500,
                content={"code": 1, "msg": "Internal server error", "data": None}
            )
```

### 自定义异常
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

# RAG 专用错误
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

## 4. 响应包装器

```python
# app/middleware/response_wrapper.py

class R:
    """统一响应构建器"""

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

## 5. JWT 工具

```python
# app/core/jwt.py
import jwt
from datetime import datetime, timedelta
from app.config import settings

def encode_token(user: dict) -> str:
    """生成 JWT Token"""
    payload = {
        "user_id": user["id"],
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    """验证并解码 JWT Token"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
```

## 6. Redis 客户端

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
        logger.warning(f"Redis 不可用，使用内存回退：{e}")
        _redis_client = None

async def get_redis() -> redis.Redis | None:
    return _redis_client

async def close_redis():
    if _redis_client:
        await _redis_client.close()
```

### 缓存存储（Redis + 内存回退）
```python
class CacheStore:
    """以 Redis 为主、内存为回退的缓存"""

    def __init__(self):
        self._memory = {}  # 回退存储

    async def get(self, key: str):
        r = await get_redis()
        if r:
            val = await r.get(f"cache:{key}")
            return json.loads(val) if val else None
        # 内存回退
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

### 限流存储
```python
class RateLimitStore:
    """滑动窗口限流器"""

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
        # 内存回退
        return self._memory_increment(key, window_ms)
```

## 7. 事件系统

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
        """异步触发事件，错误隔离"""
        for callback in self._listeners.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"事件监听器错误 [{event}]：{e}")

# 单例
user_events = EventEmitter()

# 事件名称
USER_CREATED = "user:created"
USER_UPDATED = "user:updated"
USER_DELETED = "user:deleted"
```

## 8. 数据库设置

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
    """FastAPI 数据库会话依赖"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_database():
    """启动时创建表"""
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

## 9. 配置

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
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

    # Doubao 嵌入
    DOUBAO_HOST: str = ""
    DOUBAO_API_KEY: str = ""
    DOUBAO_EMBEDDING_MODEL: str = ""
    DOUBAO_EMBEDDING_BATCH_SIZE: int = 16

    # LLM 提供者（可选，可使用数据库配置）
    OPENAI_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_KEY: str = ""
    AZURE_BASE: str = ""
    AZURE_KEY: str = ""
    GEMINI_KEY: str = ""
    DEEPSEEK_KEY: str = ""
    ARK_API_KEY: str = ""

    # 文件上传
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

## 10. 计费中间件（存根）

当前已禁用（未启用付款功能）。实现为空操作中间件：
```python
def credits_check(feature_key: str = None, default_cost: int = 1):
    """计费检查中间件——当前直接透传"""
    async def middleware(request, call_next):
        # 付款已禁用——直接透传
        return await call_next(request)
    return middleware
```

## 11. 日志设置

```python
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # 静默噪音日志器
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```
