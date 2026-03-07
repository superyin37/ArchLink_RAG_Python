"""PPT module API router."""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.response_wrapper import R
from app.middleware.request_context import get_current_user_id
from app.modules.ppt.handlers.chat_stream import handle_ppt_stream
from app.modules.ppt.handlers.sse_stream import SSEStream, create_sse_response
from app.modules.ppt.handlers.rag_query.orchestrator import RagQueryOrchestrator
from app.modules.ppt.store import get_conversation, get_messages, add_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stream/chat")
async def ppt_stream_chat(
    body: dict,
    user_id: int = Depends(get_current_user_id),
):
    """Main PPT chat streaming endpoint (SSE)."""
    return await handle_ppt_stream(
        conversation_id=body.get("conversation_id"),
        message=body.get("message", ""),
        stage=body.get("stage"),
        conversation_type=body.get("conversation_type", "ppt_design"),
        model_id=body.get("model_id"),
        metadata=body.get("metadata"),
        kb_ids=body.get("kb_ids", []),
        user_id=user_id,
    )


@router.post("/stream/rag-query")
async def ppt_rag_query(
    body: dict,
    user_id: int = Depends(get_current_user_id),
):
    """RAG-enhanced query endpoint (SSE)."""
    conversation_id = body.get("conversation_id")
    message = body.get("message", "")
    kb_ids = body.get("kb_ids", [])
    model_id = body.get("model_id", "")
    enhance_config = body.get("enhance_config", {})
    limit_config = body.get("limit_config", {})

    # Get or create conversation
    conv = None
    if conversation_id:
        conv = get_conversation(conversation_id)

    if conv is None:
        from app.modules.ppt.store import create_conversation
        conv = create_conversation(metadata={}, user_id=user_id)

    # Get message history
    history = get_messages(conv.id, limit=20)
    message_history = [
        {"role": m.role, "content": m.content}
        for m in history if m.content
    ]

    # Save user message
    user_msg = add_message(conv.id, "user", message)

    # Create placeholder assistant message
    assistant_msg = add_message(conv.id, "assistant", "")

    stream = SSEStream()

    model_config = {"model_id": model_id}

    config = {"enhance": enhance_config, "limit": limit_config}

    orchestrator = RagQueryOrchestrator(
        stream=stream,
        conversation=conv,
        assistant_message=assistant_msg,
        message_history=message_history + [{"role": "user", "content": message}],
        config=config,
    )

    asyncio.create_task(orchestrator.execute(kb_ids, message, model_config))

    return create_sse_response(stream)


@router.get("/conversation/{conversation_id}")
async def get_ppt_conversation(conversation_id: str):
    """Get PPT conversation details."""
    conv = get_conversation(conversation_id)
    if not conv:
        from app.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conversation_id} not found")
    return R.success({
        "id": conv.id,
        "stage": conv.stage,
        "conversation_type": conv.conversation_type,
        "metadata": conv.metadata,
        "user_id": conv.user_id,
        "create_time": conv.create_time.isoformat(),
    })


@router.get("/conversation/{conversation_id}/messages")
async def get_ppt_messages(conversation_id: str, limit: int = 50):
    """Get PPT conversation messages."""
    conv = get_conversation(conversation_id)
    if not conv:
        from app.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conversation_id} not found")
    msgs = get_messages(conversation_id, limit=limit)
    return R.success([
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "message_type": m.message_type,
            "meta": m.meta,
            "create_time": m.create_time.isoformat(),
        }
        for m in msgs
    ])
