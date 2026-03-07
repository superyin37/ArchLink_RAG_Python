# 05 - PPT Module Specification

## Overview
PPT generation module with stage-based conversation flow, RAG-enhanced responses, and streaming output via SSE. This module orchestrates LLM calls with knowledge base context to generate presentation content.

## Stage State Machine

```
requirement → case_selection → outline → ppt → completed
```

### Stage Transitions
```python
VALID_TRANSITIONS = {
    "requirement":    ["requirement", "case_selection"],
    "case_selection": ["case_selection", "outline"],
    "outline":        ["outline", "ppt"],
    "ppt":            ["ppt", "completed"],
    "completed":      ["completed"],
}

def can_transition_to(current_stage, target_stage) -> bool:
    return target_stage in VALID_TRANSITIONS.get(current_stage, [])

def infer_next_stage(conversation) -> str:
    """Infer next stage based on current state"""
    stage = conversation.stage
    if stage == "requirement":
        locks = conversation.metadata.get("stage_locks", {})
        if locks.get("requirement", {}).get("locked"):
            return "case_selection"
    return stage  # Stay in current stage by default
```

## Handler Chain

Each handler is a pure function or thin class with a single responsibility:

### 1. conversation.py - Conversation Lifecycle
```python
async def get_or_create_conversation(
    conversation_id: str = None,
    message: str = "",
    requested_stage: str = None,
    conversation_type: str = "ppt_design",
    metadata: dict = None,
    user_id: int = None,
) -> Conversation:
    """
    Get existing conversation or create new one.
    For ppt_design type: auto-manage stage transitions.
    """
    if conversation_id:
        conv = await get_conversation(conversation_id)
        if conv.conversation_type == "ppt_design":
            if requested_stage:
                # User explicitly chose stage (e.g., clicking "Generate Outline")
                if can_transition_to(conv.stage, requested_stage):
                    conv.stage = requested_stage
            else:
                conv.stage = infer_next_stage(conv)
        # Merge metadata
        if metadata:
            conv.metadata = {**conv.metadata, **metadata}
        await save_conversation(conv)
        return conv
    else:
        # Create new conversation
        conv = Conversation(
            conversation_type=conversation_type,
            stage="requirement" if conversation_type == "ppt_design" else None,
            metadata=metadata or {},
            user_id=user_id,
        )
        await save_conversation(conv)
        return conv
```

### 2. message.py - Message CRUD
```python
def get_message_type(stage: str) -> str:
    """Map stage to message type"""
    return {"requirement": "text", "outline": "outline", "ppt": "ppt"}.get(stage, "text")

async def save_user_message(conversation_id, content, user_id, meta=None) -> Message:
    return await message_service.create(
        conversation_id=conversation_id, role="user",
        content=content, user_id=user_id, meta=meta
    )

async def create_assistant_message(conversation_id, stage, meta=None) -> Message:
    """Create empty placeholder for assistant response"""
    return await message_service.create(
        conversation_id=conversation_id, role="assistant",
        content="", message_type=get_message_type(stage), meta=meta
    )

async def get_message_history(conversation_id, limit=10, exclude_ids=None) -> list:
    """Get recent messages in chronological order for LLM context"""
    messages = await message_service.get_recent(conversation_id, limit)
    if exclude_ids:
        messages = [m for m in messages if m.id not in exclude_ids]
    return [{"role": m.role, "content": m.content} for m in messages]

def transform_message_for_llm(message) -> dict:
    """Transform special message types for LLM understanding"""
    if message.meta and message.meta.get("type") == "location_request":
        location = message.meta.get("location_data", {})
        return {
            "role": message.role,
            "content": f"{message.content}\n\nLocation data: {json.dumps(location, ensure_ascii=False)}"
        }
    return {"role": message.role, "content": message.content}
```

### 3. prompt.py - Dynamic Prompt Builder
```python
async def build_prompt_by_stage(stage, context) -> list[dict]:
    """Build LLM messages based on current stage"""
    message = context["message"]
    conversation = context["conversation"]
    history = context.get("message_history", [])

    if stage == "requirement":
        return await build_requirement_prompt(history, conversation)
    elif stage == "outline":
        return await build_outline_prompt(
            topic=conversation.metadata.get("topic"),
            requirements=conversation.metadata.get("requirements"),
            language=conversation.metadata.get("language", "zh"),
            history=history,
            building_params=conversation.metadata.get("building_params"),
        )
    elif stage == "ppt":
        return await build_ppt_prompt(
            outline=conversation.metadata.get("current_outline"),
            language=conversation.metadata.get("language", "zh"),
            style=conversation.metadata.get("style"),
        )
    return history

async def build_requirement_prompt(history, conversation):
    """Load system prompt template from DB or file, inject context"""
    system_prompt = await load_template("ppt-requirement")
    building_params = conversation.metadata.get("building_params", {})
    if building_params:
        system_prompt += f"\n\nBuilding Parameters:\n{json.dumps(building_params, ensure_ascii=False)}"
    return [{"role": "system", "content": system_prompt}] + history
```

### 4. outline.py - Outline Data
```python
async def save_outline_data(conversation, message, content, topic=None):
    """Save generated outline, link to conversation"""
    outline = await create_outline(
        conversation_id=conversation.id,
        message_id=message.id,
        content=content,
        topic=topic,
    )
    # Update message meta
    message.meta = {**(message.meta or {}), "outline_id": outline.id}
    await update_message(message)
    return outline
```

### 5. stage.py - Stage State Machine
(Already covered above in Stage State Machine section)

### 6. case_selection.py - RAG-based Case Selection
```python
async def handle_case_selection_stream(ctx):
    """
    1. Extract building_params from conversation
    2. Call LLM to analyze requirements and generate search keywords
    3. Execute RAG search with keywords
    4. Return case list to frontend
    """
    building_params = conversation.metadata.get("building_params", {})

    # Use LLM to analyze and generate keywords
    analysis_prompt = f"""Analyze these building requirements and generate 5-8 search keywords:
    {json.dumps(building_params, ensure_ascii=False)}
    Output format: [keyword1] [keyword2] [keyword3] ..."""

    keywords = await analyze_with_llm(analysis_prompt, stream)

    # RAG search with keywords
    search_results = await search_service.search(kb_id, " ".join(keywords), top_k=12)

    # Push results to stream
    stream.publish_event("case_selection", {"cases": search_results})
```

### 7. stream.py - Core Stream Handler
```python
async def handle_chat_stream(
    response_type: str,
    ctx: dict,
    conversation,
    assistant_message,
    user_message_id: int,
    stage: str,
    llm_messages: list,
    model_id: str = None,
    model_with_provider: str = None,
    processor = None,
):
    """
    Core streaming handler. Creates SSE stream and orchestrates LLM call.
    CRITICAL: LLM call is NOT awaited - it runs in background while stream is returned immediately.
    """
    stream = create_sse_stream()

    # Send initial metadata
    stream.send_json({
        "type": "metadata",
        "conversation_id": conversation.id,
        "message_id": assistant_message.id,
        "stage": stage,
    })

    # Title generation (async, non-blocking) for outline stage
    title_task = None
    if stage == "outline":
        title_task = asyncio.create_task(generate_title_async(llm_messages))

    # Create LLM instance
    llm = create_llm(model_id=model_id, model_with_provider=model_with_provider)

    thinking_buffer = []
    content_buffer = []

    def on_thinking(text):
        thinking_buffer.append(text)
        stream.send_json({"type": "thinking", "content": text})

    def on_thinking_complete():
        stream.send_json({"type": "thinking_complete"})

    def on_content(text):
        content_buffer.append(text)
        if processor and processor.needs_buffer:
            return  # Buffer mode: don't stream yet
        if processor and hasattr(processor, 'filter_token'):
            filtered = processor.filter_token(text)
            if filtered:
                stream.send_text(filtered)
        else:
            stream.send_text(text)

    def on_error(error):
        stream.send_json({"type": "error", "message": str(error)})
        stream.close()

    # NON-BLOCKING LLM call
    async def run_llm():
        try:
            await llm.chat(
                llm_messages,
                on_thinking=on_thinking,
                on_thinking_complete=on_thinking_complete,
                on_content=on_content,
                on_error=on_error,
            )

            # Stream complete - handle results
            full_content = "".join(content_buffer)
            full_thinking = "".join(thinking_buffer)

            if processor and processor.needs_buffer:
                await processor.process_stream_result(full_content, stream)
            elif processor and hasattr(processor, 'on_stream_complete'):
                await processor.on_stream_complete(full_content, stream)
            else:
                await handle_stream_complete(
                    assistant_message, full_content, full_thinking,
                    conversation, stage, title_task
                )

            stream.close()
        except Exception as e:
            on_error(e)

    asyncio.create_task(run_llm())
    return stream  # Return immediately, don't wait for LLM


async def handle_stream_complete(assistant_message, content, thinking,
                                  conversation, stage, title_task=None):
    """Post-stream processing"""
    # Update assistant message
    assistant_message.content = content
    if thinking:
        assistant_message.meta = {**(assistant_message.meta or {}), "thinking": thinking}
    await update_message(assistant_message)

    # Handle outline-specific logic
    if stage == "outline" and title_task:
        topic = await title_task
        outline = await save_outline_data(conversation, assistant_message, content, topic)
        conversation.metadata["current_outline_id"] = outline.id
        await save_conversation(conversation)
```

## RAG Query Orchestrator

### Architecture
```
rag_query.handler.py
  → RagQueryOrchestrator.execute()
      ├── SearchExecutor.execute()         # RAG search
      ├── RagContextBuilder.build()        # Context assembly
      ├── StreamPublisher.publish_*()      # SSE events
      └── LlmExecutor.execute()            # LLM call (non-blocking)
```

### RagQueryOrchestrator
```python
class RagQueryOrchestrator:
    def __init__(self, stream, conversation, assistant_message, message_history, config):
        self.publisher = StreamPublisher(stream)
        self.search_executor = SearchExecutor()
        self.context_builder = RagContextBuilder()
        self.llm_executor = LlmExecutor(stream)

    async def execute(self, kb_ids, query, model_config):
        """Main orchestration - runs in background task"""
        # 1. Publish initial metadata
        self.publisher.publish_initial_metadata(self.conversation, self.assistant_message)

        # 2. Execute search
        search_result = await self.search_executor.execute(
            kb_ids=kb_ids, query=query,
            enhance_config=self.config.get("enhance"),
            limit_config=self.config.get("limit"),
        )

        # 3. Publish search results
        self.publisher.publish_search_results(search_result)

        # 4. Build context
        context_text = self.context_builder.build_context(search_result["chunks"])
        system_prompt = await self.context_builder.build_system_prompt(
            context=context_text, kb_name=search_result.get("kb_name")
        )

        # 5. Prepare LLM messages
        recent_history = self.message_history[-RAGConfig.MAX_HISTORY_MESSAGES:]
        llm_messages = [{"role": "system", "content": system_prompt}] + recent_history

        # 6. Execute LLM (non-blocking within this task)
        try:
            llm_result = await self.llm_executor.execute(
                messages=llm_messages, model_config=model_config,
                on_thinking=lambda t: self.publisher.publish_thinking(t),
                on_thinking_complete=lambda: self.publisher.publish_thinking_complete(),
                on_content=lambda t: self.publisher.publish_content(t),
            )

            # 7. Save results
            self.assistant_message.content = llm_result["content"]
            if llm_result.get("thinking"):
                self.assistant_message.meta = {
                    **(self.assistant_message.meta or {}),
                    "thinking": llm_result["thinking"]
                }
            await update_message(self.assistant_message)
        except Exception as e:
            self.publisher.publish_error(str(e))
        finally:
            self.publisher.close()
```

### RagContextBuilder
```python
class RagContextBuilder:
    def build_context(self, chunks) -> str:
        """Build formatted context from search results"""
        hit_chunks = [c for c in chunks if c.get("is_hit")]
        expanded_chunks = [c for c in chunks if not c.get("is_hit")]

        parts = []

        if hit_chunks:
            parts.append("## Directly Relevant Content")
            for c in hit_chunks:
                score_tag = f" (similarity: {c.get('score', 0):.2f})" if c.get("score") else ""
                heading = f"### {c.get('heading', 'Untitled')}{score_tag}\n" if c.get("heading") else ""
                parts.append(f"{heading}{c['content']}")

        if expanded_chunks:
            parts.append("\n## Related Context")
            by_doc = group_by_key(expanded_chunks, "doc_id")
            for doc_id, doc_chunks in by_doc.items():
                doc_name = doc_chunks[0].get("metadata", {}).get("doc_name", f"Document {doc_id}")
                parts.append(f"### From: {doc_name}")
                for c in doc_chunks:
                    parts.append(c["content"])

        return "\n\n".join(parts)

    async def build_system_prompt(self, context, kb_name="Knowledge Base") -> str:
        """Load template and inject context"""
        template = await load_template("rag-query")
        if template:
            return template.replace("{{kb_name}}", kb_name).replace("{{context}}", context)
        # Fallback default prompt
        return f"""You are a helpful assistant. Answer based on the following knowledge base content.

Knowledge Base: {kb_name}

{context}

Instructions:
- Answer based on the provided context
- If the context doesn't contain relevant information, say so
- Be concise and accurate"""
```

### StreamPublisher
```python
class StreamPublisher:
    def __init__(self, stream):
        self.stream = stream

    def publish_initial_metadata(self, conversation, message):
        self._send_json({"type": "metadata",
                         "conversation_id": conversation.id,
                         "message_id": message.id})

    def publish_search_results(self, result):
        self._send_json({"type": "search_results",
                         "chunks": result["chunks"][:10],  # Limit for frontend
                         "kb_name": result.get("kb_name"),
                         "stats": result.get("stats")})

    def publish_thinking(self, text):
        self._send_json({"type": "thinking", "content": text})

    def publish_thinking_complete(self):
        self._send_json({"type": "thinking_complete"})

    def publish_content(self, text):
        self.stream.send_text(text)

    def publish_warning(self, message):
        self._send_json({"type": "warning", "message": message})

    def publish_error(self, message):
        self._send_json({"type": "error", "message": message})

    def close(self):
        self.stream.close()

    def _send_json(self, data):
        self.stream.send_text(json.dumps(data, ensure_ascii=False) + "\n")
```

## SSE Stream Implementation

```python
from fastapi.responses import StreamingResponse
import asyncio

class SSEStream:
    def __init__(self):
        self.queue = asyncio.Queue()
        self._closed = False

    def send_text(self, text: str):
        if not self._closed:
            self.queue.put_nowait(f"data: {text}\n\n")

    def send_json(self, data: dict):
        if not self._closed:
            text = json.dumps(data, ensure_ascii=False)
            self.queue.put_nowait(f"data: {text}\n\n")

    def close(self):
        self._closed = True
        self.queue.put_nowait(None)  # Sentinel

    async def generator(self):
        while True:
            data = await self.queue.get()
            if data is None:
                break
            yield data

def create_sse_response(stream: SSEStream) -> StreamingResponse:
    return StreamingResponse(
        stream.generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```
