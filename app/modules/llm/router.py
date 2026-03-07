"""LLM API router."""
import logging
import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.response_wrapper import R
from app.middleware.request_context import get_current_user_id
from app.schemas.llm import (
    LLMProviderCreate, LLMProviderUpdate, APIKeyUpdate,
    LLMModelCreate, LLMModelUpdate, DeprecateRequest,
    ChatCreate, ChatTitleUpdate,
)
from app.modules.llm.services.provider import provider_service
from app.modules.llm.services.model import model_service
from app.modules.llm.services.chat import chat_service
from app.modules.llm.services.message import message_service
from app.modules.llm.services.call_log import call_log_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Provider ──────────────────────────────────────────────────────────────────

@router.get("/provider")
async def list_providers(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    status: int = Query(None),
    api_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await provider_service.get_list(db, page, size, keyword, status, api_type)
    return R.page(
        items=[_provider_to_dict(p) for p in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/provider/api-types")
async def get_api_types():
    types = await provider_service.get_api_types()
    return R.success(types)


@router.get("/provider/{provider_id}")
async def get_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await provider_service.get_by_id(db, provider_id)
    return R.success(_provider_to_dict(p))


@router.post("/provider")
async def create_provider(body: LLMProviderCreate, db: AsyncSession = Depends(get_db)):
    p = await provider_service.create(db, body.model_dump(exclude_none=True))
    return R.success(_provider_to_dict(p))


@router.put("/provider/{provider_id}")
async def update_provider(
    provider_id: int, body: LLMProviderUpdate, db: AsyncSession = Depends(get_db)
):
    p = await provider_service.update(db, provider_id, body.model_dump(exclude_none=True))
    return R.success(_provider_to_dict(p))


@router.delete("/provider/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    await provider_service.delete(db, provider_id)
    return R.success({"id": provider_id})


@router.put("/provider/{provider_id}/api-key")
async def update_api_key(
    provider_id: int, body: APIKeyUpdate, db: AsyncSession = Depends(get_db)
):
    await provider_service.update_api_key(db, provider_id, body.api_key)
    return R.success({"id": provider_id})


# ─── Model ─────────────────────────────────────────────────────────────────────

@router.get("/model")
async def list_models(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    provider_id: str = Query(None),
    keyword: str = Query(None),
    status: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await model_service.get_list(db, provider_id, page, size, keyword, status)
    return R.page(
        items=[_model_to_dict(m) for m in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/model/by-provider")
async def get_models_by_provider(db: AsyncSession = Depends(get_db)):
    grouped = await model_service.get_by_provider_grouped(db)
    return R.success([
        {"provider_id": g["provider_id"], "models": [_model_to_dict(m) for m in g["models"]]}
        for g in grouped
    ])


@router.get("/model/{model_id}")
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    m = await model_service.get_by_id(db, model_id)
    return R.success(_model_to_dict(m))


@router.post("/model")
async def create_model(body: LLMModelCreate, db: AsyncSession = Depends(get_db)):
    m = await model_service.create(db, body.model_dump(exclude_none=True))
    return R.success(_model_to_dict(m))


@router.put("/model/{model_id}")
async def update_model(
    model_id: int, body: LLMModelUpdate, db: AsyncSession = Depends(get_db)
):
    m = await model_service.update(db, model_id, body.model_dump(exclude_none=True))
    return R.success(_model_to_dict(m))


@router.delete("/model/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    await model_service.delete(db, model_id)
    return R.success({"id": model_id})


@router.post("/model/{model_id}/deprecate")
async def deprecate_model(
    model_id: int, body: DeprecateRequest, db: AsyncSession = Depends(get_db)
):
    await model_service.deprecate(db, model_id, body.replacement_model_id)
    return R.success({"id": model_id})


# ─── Chat ──────────────────────────────────────────────────────────────────────

@router.get("/chat")
async def list_chats(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await chat_service.get_user_chats(db, user_id or 0, page, size)
    return R.page(
        items=[_chat_to_dict(c) for c in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/chat/{chat_id}")
async def get_chat(chat_id: str, db: AsyncSession = Depends(get_db)):
    chat = await chat_service.get_by_chat_id(db, chat_id)
    return R.success(_chat_to_dict(chat))


@router.post("/chat")
async def create_chat(
    body: ChatCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    data = {
        "chat_id": str(uuid.uuid4()),
        "user_id": user_id or 0,
        "model": body.model,
        "title": body.title or "New Chat",
    }
    chat = await chat_service.create(db, data)
    return R.success(_chat_to_dict(chat))


@router.put("/chat/{chat_id}/title")
async def update_chat_title(
    chat_id: str, body: ChatTitleUpdate, db: AsyncSession = Depends(get_db)
):
    await chat_service.update_title(db, chat_id, body.title)
    return R.success({"chat_id": chat_id})


@router.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str, db: AsyncSession = Depends(get_db)):
    await chat_service.delete(db, chat_id)
    return R.success({"chat_id": chat_id})


@router.get("/chat/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await message_service.get_messages(db, chat_id, page, size)
    return R.page(
        items=[_message_to_dict(m) for m in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


# ─── Stream Chat ───────────────────────────────────────────────────────────────

@router.post("/chat/{chat_id}/stream")
async def stream_chat(
    chat_id: str,
    body: dict,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Stream a chat completion response."""
    from app.modules.llm.utils.model_loader import load_model_by_string
    from app.modules.llm.handlers.chat_manager import stream_chat_response

    model_str = body.get("model", "")
    user_msg = body.get("message", "")
    options = body.get("options", {})

    provider, model = await load_model_by_string(model_str, db)

    # Save user message
    if user_msg:
        await message_service.save_user_message(db, chat_id, user_msg, user_id)

    # Get full history
    history = await message_service.get_chat_history(db, chat_id)

    async def generate():
        async for chunk in stream_chat_response(
            provider=provider,
            model=model,
            messages=history,
            chat_id=chat_id,
            user_id=user_id,
            save_messages=True,
            options=options,
            db=db,
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ─── Call Logs ─────────────────────────────────────────────────────────────────

@router.get("/call-log")
async def list_call_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    provider_id: str = Query(None),
    model: str = Query(None),
    status: str = Query(None),
    user_id: int = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = {k: v for k, v in {
        "provider_id": provider_id, "model": model, "status": status,
        "user_id": user_id, "start_date": start_time, "end_date": end_time,
    }.items() if v is not None}
    result = await call_log_service.get_list(db, filters, page, size)
    return R.page(
        items=[_log_to_dict(lg) for lg in result["list"]],
        total=result["total"],
        page=page,
        size=size,
    )


@router.get("/call-log/statistics")
async def get_log_statistics(
    provider_id: str = Query(None),
    model: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = {k: v for k, v in {
        "provider_id": provider_id, "model": model,
        "start_date": start_time, "end_date": end_time,
    }.items() if v is not None}
    stats = await call_log_service.get_statistics(db, filters)
    return R.success(stats)


@router.get("/call-log/{log_id}")
async def get_call_log(log_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.llm import LLMCallLog
    result = await db.execute(select(LLMCallLog).where(LLMCallLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        from app.exceptions import NotFoundError
        raise NotFoundError(f"Call log {log_id} not found")
    return R.success(_log_to_dict(log))


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _provider_to_dict(p) -> dict:
    return {
        "id": p.id,
        "provider_id": p.provider_id,
        "name": p.name,
        "icon": p.icon,
        "api_type": p.api_type,
        "api_endpoint": p.api_endpoint,
        "api_key": "***" if p.api_key else None,
        "status": p.status,
        "is_builtin": p.is_builtin,
        "description": p.description,
        "default_parameters": p.default_parameters,
        "create_time": p.create_time.isoformat() if p.create_time else None,
    }


def _model_to_dict(m) -> dict:
    return {
        "id": m.id,
        "provider_id": m.provider_id,
        "model_id": m.model_id,
        "name": m.name,
        "description": m.description,
        "max_tokens": m.max_tokens,
        "context_window": m.context_window,
        "capabilities": m.capabilities,
        "pricing": m.pricing,
        "status": m.status,
        "is_builtin": m.is_builtin,
        "create_time": m.create_time.isoformat() if m.create_time else None,
    }


def _chat_to_dict(c) -> dict:
    return {
        "id": c.id,
        "chat_id": c.chat_id,
        "user_id": c.user_id,
        "model": c.model,
        "title": c.title,
        "create_time": c.create_time.isoformat() if c.create_time else None,
        "update_time": c.update_time.isoformat() if c.update_time else None,
    }


def _message_to_dict(m) -> dict:
    return {
        "id": m.id,
        "chat_id": m.chat_id,
        "role": m.role,
        "content": m.content,
        "model": m.model,
        "token_usage": m.token_usage,
        "meta": m.meta,
        "create_time": m.create_time.isoformat() if m.create_time else None,
    }


def _log_to_dict(lg) -> dict:
    return {
        "id": lg.id,
        "request_id": lg.request_id,
        "provider_id": lg.provider_id,
        "model": lg.model,
        "api_type": lg.api_type,
        "user_id": lg.user_id,
        "session_id": lg.session_id,
        "status": lg.status,
        "is_success": lg.is_success,
        "prompt_tokens": lg.prompt_tokens,
        "completion_tokens": lg.completion_tokens,
        "total_tokens": lg.total_tokens,
        "cost": lg.cost,
        "total_duration": lg.total_duration,
        "first_token_duration": lg.first_token_duration,
        "error_message": lg.error_message,
        "create_time": lg.create_time.isoformat() if lg.create_time else None,
    }
