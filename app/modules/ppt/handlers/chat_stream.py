"""PPT chat stream handler."""
import asyncio
import json
import logging
from typing import Optional

from app.modules.ppt.handlers.sse_stream import SSEStream, create_sse_response
from app.modules.ppt.handlers.stage import (
    can_transition_to, infer_next_stage, get_message_type,
)
from app.modules.ppt.store import (
    get_conversation, create_conversation, save_conversation,
    add_message, update_message, get_messages,
)

logger = logging.getLogger(__name__)


async def handle_ppt_stream(
    conversation_id: Optional[str],
    message: str,
    stage: Optional[str],
    conversation_type: str = "ppt_design",
    model_id: Optional[str] = None,
    metadata: dict = None,
    kb_ids: list = None,
    user_id: Optional[int] = None,
):
    """Main PPT chat streaming handler. Returns an SSE StreamingResponse."""
    from fastapi.responses import StreamingResponse

    # 1. Get or create conversation
    conv = None
    if conversation_id:
        conv = get_conversation(conversation_id)

    if conv is None:
        conv = create_conversation(
            conversation_type=conversation_type,
            metadata=metadata or {},
            user_id=user_id,
        )
    else:
        # Apply stage transition
        if stage and can_transition_to(conv.stage, stage):
            conv.stage = stage
        else:
            conv.stage = infer_next_stage(conv)
        # Merge metadata
        if metadata:
            conv.metadata = {**conv.metadata, **metadata}
        save_conversation(conv)

    current_stage = conv.stage

    # 2. Save user message
    user_msg = add_message(conv.id, "user", message)

    # 3. Create placeholder assistant message
    assistant_msg = add_message(
        conv.id, "assistant", "",
        message_type=get_message_type(current_stage),
    )

    # 4. Build SSE stream
    stream = SSEStream()

    # 5. Run orchestration in background
    asyncio.create_task(
        _run_ppt_stream(
            stream=stream,
            conv=conv,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            message=message,
            stage=current_stage,
            model_id=model_id,
            kb_ids=kb_ids or [],
        )
    )

    return create_sse_response(stream)


async def _run_ppt_stream(
    stream, conv, user_msg, assistant_msg,
    message: str, stage: str, model_id: str, kb_ids: list,
):
    try:
        stream.send_json({
            "type": "metadata",
            "conversation_id": conv.id,
            "message_id": assistant_msg.id,
            "stage": stage,
        })

        # Build message history for LLM
        history = get_messages(conv.id, limit=20)
        llm_history = [
            {"role": m.role, "content": m.content}
            for m in history
            if m.id not in (assistant_msg.id,) and m.content
        ]

        # Build system prompt based on stage
        system_prompt = _get_system_prompt(stage, conv)
        llm_messages = [{"role": "system", "content": system_prompt}] + llm_history

        # Handle case_selection stage specially
        if stage == "case_selection" and kb_ids:
            await _handle_case_selection(stream, conv, kb_ids, message, model_id)
            stream.close()
            return

        # Standard LLM streaming
        content_buf: list[str] = []
        thinking_buf: list[str] = []

        def on_thinking(text: str):
            thinking_buf.append(text)
            stream.send_json({"type": "thinking", "content": text})

        def on_thinking_complete():
            stream.send_json({"type": "thinking_complete"})

        def on_content(text: str):
            content_buf.append(text)
            stream.send_text(text)

        def on_error(err: Exception):
            stream.send_json({"type": "error", "message": str(err)})
            stream.close()

        from app.modules.llm.completions.factory import LLMOne
        from app.database import async_session
        from app.modules.llm.utils.model_loader import load_model_by_string

        if model_id:
            async with async_session() as db:
                try:
                    provider, model = await load_model_by_string(model_id, db)
                    llm = LLMOne.from_database(provider, model, session_id=conv.id, user_id=conv.user_id)
                except Exception:
                    llm = LLMOne.from_config(model_id, session_id=conv.id)
        else:
            from app.config import settings
            default_model = getattr(settings, "DEFAULT_LLM_MODEL", "openai#gpt-4o-mini")
            llm = LLMOne.from_config(default_model, session_id=conv.id)

        llm.on_thinking = on_thinking
        llm.on_thinking_complete = on_thinking_complete
        llm.on_content = on_content
        llm.on_error = on_error

        await llm.chat(llm_messages)

        # Save result
        full_content = "".join(content_buf)
        assistant_msg.content = full_content
        if thinking_buf:
            assistant_msg.meta = {**assistant_msg.meta, "thinking": "".join(thinking_buf)}
        update_message(assistant_msg)

    except Exception as e:
        logger.exception(f"PPT stream error: {e}")
        try:
            stream.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        stream.close()


async def _handle_case_selection(stream, conv, kb_ids: list, query: str, model_id: str):
    """Handle case selection stage: search RAG and stream results."""
    from app.modules.rag.services.knowledge_base import kb_service
    from app.modules.rag.search.providers import VectorSearchProvider, FulltextSearchProvider
    from app.modules.rag.search.fusion import SearchFusion
    from app.database import async_session

    stream.send_json({"type": "searching", "message": "Searching knowledge base..."})
    all_cases = []

    for kb_id in kb_ids:
        try:
            async with async_session() as db:
                kb = await kb_service.get_by_id(db, kb_id)
            vector_r = await VectorSearchProvider().search(kb, query, top_k=6)
            fulltext_r = await FulltextSearchProvider().search(kb_id, query, top_k=6)
            fused = SearchFusion.fuse_rrf([vector_r, fulltext_r], top_k=8)
            all_cases.extend(fused)
        except Exception as e:
            logger.warning(f"Case selection search failed for kb {kb_id}: {e}")

    stream.send_json({"type": "case_selection", "cases": all_cases})


def _get_system_prompt(stage: str, conv) -> str:
    meta = conv.metadata or {}
    building_params = meta.get("building_params", {})
    language = meta.get("language", "zh")

    prompts = {
        "requirement": (
            "You are a professional PPT design consultant. Help users clarify their "
            "presentation requirements. Ask about topic, audience, purpose, style preferences, "
            "and content structure. Be concise and helpful.\n"
            + (f"\nBuilding Parameters:\n{json.dumps(building_params, ensure_ascii=False)}" if building_params else "")
        ),
        "case_selection": (
            "You are helping select relevant cases for a PPT presentation. "
            "Analyze the requirements and identify the most relevant reference cases."
        ),
        "outline": (
            f"You are a professional PPT outline creator. Generate a detailed, structured "
            f"outline for a presentation based on the requirements. "
            f"Language: {language}. "
            f"Format the outline with clear sections and subsections."
        ),
        "ppt": (
            f"You are a professional PPT content creator. Generate detailed slide content "
            f"based on the provided outline. Language: {language}. "
            f"Format each slide with title, key points, and speaker notes."
        ),
    }
    return prompts.get(stage, "You are a helpful assistant.")
