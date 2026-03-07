import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import init_database
from app.core.redis import init_redis, close_redis
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.request_context import RequestContextMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG system...")
    await init_database()
    await init_redis()
    logger.info("RAG system started successfully")
    yield
    await close_redis()
    logger.info("RAG system shutdown complete")


app = FastAPI(
    title="RAG System API",
    description="RAG System with LLM integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware (order matters: last added = first executed)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

# Static file serving for uploads
uploads_dir = Path(settings.UPLOAD_DIR)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Test UI
test_ui_dir = Path(__file__).parent.parent / "static" / "test-ui"
test_ui_dir.mkdir(parents=True, exist_ok=True)
app.mount("/test", StaticFiles(directory=str(test_ui_dir), html=True), name="test-ui")

# Register routers
from app.modules.rag.router import router as rag_router
from app.modules.llm.router import router as llm_router
from app.modules.ppt.router import router as ppt_router

app.include_router(rag_router, prefix="/api/rag")
app.include_router(llm_router, prefix="/api/llm")
app.include_router(ppt_router, prefix="/api/ppt")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    from app.core.redis import get_redis
    from app.database import engine

    redis_ok = False
    try:
        r = await get_redis()
        if r:
            await r.ping()
            redis_ok = True
    except Exception:
        pass

    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {"status": "ok", "db": db_ok, "redis": redis_ok}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)
