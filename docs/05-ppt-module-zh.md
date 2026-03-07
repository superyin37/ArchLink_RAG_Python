# 05 - PPT 模块规范

## 概述
PPT 生成模块，具备基于阶段的对话流程、RAG 增强响应以及通过 SSE 的流式输出。该模块协调 LLM 调用与知识库上下文，用于生成演示内容。

## 阶段状态机

```
requirement → case_selection → outline → ppt → completed
```

### 阶段转换
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
    """根据当前状态推断下一阶段"""
    stage = conversation.stage
    if stage == "requirement":
        locks = conversation.metadata.get("stage_locks", {})
        if locks.get("requirement", {}).get("locked"):
            return "case_selection"
    return stage  # 默认停留在当前阶段
```

## 处理器链

每个处理器是一个纯函数或职责单一的薄类：

### 1. conversation.py - 对话生命周期
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
    获取已有对话或创建新对话。
    对于 ppt_design 类型：自动管理阶段转换。
    """
    if conversation_id:
        conv = await get_conversation(conversation_id)
        if conv.conversation_type == "ppt_design":
            if requested_stage:
                # 用户明确选择了阶段（如点击"生成大纲"）
                if can_transition_to(conv.stage, requested_stage):
                    conv.stage = requested_stage
            else:
                conv.stage = infer_next_stage(conv)
        # 合并元数据
        if metadata:
            conv.metadata = {**conv.metadata, **metadata}
        await save_conversation(conv)
        return conv
    else:
        # 创建新对话
        conv = Conversation(
            conversation_type=conversation_type,
            stage="requirement" if conversation_type == "ppt_design" else None,
            metadata=metadata or {},
            user_id=user_id,
        )
        await save_conversation(conv)
        return conv
```

### 2. message.py - 消息 CRUD
```python
def get_message_type(stage: str) -> str:
    """将阶段映射到消息类型"""
    return {"requirement": "text", "outline": "outline", "ppt": "ppt"}.get(stage, "text")

async def save_user_message(conversation_id, content, user_id, meta=None) -> Message:
    return await message_service.create(
        conversation_id=conversation_id, role="user",
        content=content, user_id=user_id, meta=meta
    )

async def create_assistant_message(conversation_id, stage, meta=None) -> Message:
    """为助手响应创建空白占位符"""
    return await message_service.create(
        conversation_id=conversation_id, role="assistant",
        content="", message_type=get_message_type(stage), meta=meta
    )

async def get_message_history(conversation_id, limit=10, exclude_ids=None) -> list:
    """按时间顺序获取最近消息，用于 LLM 上下文"""
    messages = await message_service.get_recent(conversation_id, limit)
    if exclude_ids:
        messages = [m for m in messages if m.id not in exclude_ids]
    return [{"role": m.role, "content": m.content} for m in messages]

def transform_message_for_llm(message) -> dict:
    """将特殊消息类型转换为 LLM 可理解的格式"""
    if message.meta and message.meta.get("type") == "location_request":
        location = message.meta.get("location_data", {})
        return {
            "role": message.role,
            "content": f"{message.content}\n\n位置数据：{json.dumps(location, ensure_ascii=False)}"
        }
    return {"role": message.role, "content": message.content}
```

### 3. prompt.py - 动态提示词构建器
```python
async def build_prompt_by_stage(stage, context) -> list[dict]:
    """根据当前阶段构建 LLM 消息"""
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
    """从数据库或文件加载系统提示词模板，注入上下文"""
    system_prompt = await load_template("ppt-requirement")
    building_params = conversation.metadata.get("building_params", {})
    if building_params:
        system_prompt += f"\n\n建设参数：\n{json.dumps(building_params, ensure_ascii=False)}"
    return [{"role": "system", "content": system_prompt}] + history
```

### 4. outline.py - 大纲数据
```python
async def save_outline_data(conversation, message, content, topic=None):
    """保存生成的大纲，关联到对话"""
    outline = await create_outline(
        conversation_id=conversation.id,
        message_id=message.id,
        content=content,
        topic=topic,
    )
    # 更新消息元数据
    message.meta = {**(message.meta or {}), "outline_id": outline.id}
    await update_message(message)
    return outline
```

### 5. stage.py - 阶段状态机
（已在上方阶段状态机章节介绍）

### 6. case_selection.py - 基于 RAG 的案例选择
```python
async def handle_case_selection_stream(ctx):
    """
    1. 从对话中提取 building_params
    2. 调用 LLM 分析需求并生成搜索关键词
    3. 用关键词执行 RAG 搜索
    4. 将案例列表返回给前端
    """
    building_params = conversation.metadata.get("building_params", {})

    # 使用 LLM 分析并生成关键词
    analysis_prompt = f"""分析以下建设需求并生成 5-8 个搜索关键词：
    {json.dumps(building_params, ensure_ascii=False)}
    输出格式：[关键词1] [关键词2] [关键词3] ..."""

    keywords = await analyze_with_llm(analysis_prompt, stream)

    # 使用关键词进行 RAG 搜索
    search_results = await search_service.search(kb_id, " ".join(keywords), top_k=12)

    # 将结果推送到流
    stream.publish_event("case_selection", {"cases": search_results})
```

### 7. stream.py - 核心流处理器
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
    核心流处理器。创建 SSE 流并协调 LLM 调用。
    关键：LLM 调用不被 await——它在后台运行，流立即返回。
    """
    stream = create_sse_stream()

    # 发送初始元数据
    stream.send_json({
        "type": "metadata",
        "conversation_id": conversation.id,
        "message_id": assistant_message.id,
        "stage": stage,
    })

    # 标题生成（异步，非阻塞），针对 outline 阶段
    title_task = None
    if stage == "outline":
        title_task = asyncio.create_task(generate_title_async(llm_messages))

    # 创建 LLM 实例
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
            return  # 缓冲模式：暂不流式输出
        if processor and hasattr(processor, 'filter_token'):
            filtered = processor.filter_token(text)
            if filtered:
                stream.send_text(filtered)
        else:
            stream.send_text(text)

    def on_error(error):
        stream.send_json({"type": "error", "message": str(error)})
        stream.close()

    # 非阻塞 LLM 调用
    async def run_llm():
        try:
            await llm.chat(
                llm_messages,
                on_thinking=on_thinking,
                on_thinking_complete=on_thinking_complete,
                on_content=on_content,
                on_error=on_error,
            )

            # 流完成 - 处理结果
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
    return stream  # 立即返回，不等待 LLM


async def handle_stream_complete(assistant_message, content, thinking,
                                  conversation, stage, title_task=None):
    """流完成后的后处理"""
    # 更新助手消息
    assistant_message.content = content
    if thinking:
        assistant_message.meta = {**(assistant_message.meta or {}), "thinking": thinking}
    await update_message(assistant_message)

    # 处理 outline 阶段特定逻辑
    if stage == "outline" and title_task:
        topic = await title_task
        outline = await save_outline_data(conversation, assistant_message, content, topic)
        conversation.metadata["current_outline_id"] = outline.id
        await save_conversation(conversation)
```

## RAG 查询编排器

### 架构
```
rag_query.handler.py
  → RagQueryOrchestrator.execute()
      ├── SearchExecutor.execute()         # RAG 搜索
      ├── RagContextBuilder.build()        # 上下文组装
      ├── StreamPublisher.publish_*()      # SSE 事件
      └── LlmExecutor.execute()            # LLM 调用（非阻塞）
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
        """主编排入口——在后台任务中运行"""
        # 1. 发布初始元数据
        self.publisher.publish_initial_metadata(self.conversation, self.assistant_message)

        # 2. 执行搜索
        search_result = await self.search_executor.execute(
            kb_ids=kb_ids, query=query,
            enhance_config=self.config.get("enhance"),
            limit_config=self.config.get("limit"),
        )

        # 3. 发布搜索结果
        self.publisher.publish_search_results(search_result)

        # 4. 构建上下文
        context_text = self.context_builder.build_context(search_result["chunks"])
        system_prompt = await self.context_builder.build_system_prompt(
            context=context_text, kb_name=search_result.get("kb_name")
        )

        # 5. 准备 LLM 消息
        recent_history = self.message_history[-RAGConfig.MAX_HISTORY_MESSAGES:]
        llm_messages = [{"role": "system", "content": system_prompt}] + recent_history

        # 6. 执行 LLM（在此任务内非阻塞）
        try:
            llm_result = await self.llm_executor.execute(
                messages=llm_messages, model_config=model_config,
                on_thinking=lambda t: self.publisher.publish_thinking(t),
                on_thinking_complete=lambda: self.publisher.publish_thinking_complete(),
                on_content=lambda t: self.publisher.publish_content(t),
            )

            # 7. 保存结果
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
        """从搜索结果构建格式化上下文"""
        hit_chunks = [c for c in chunks if c.get("is_hit")]
        expanded_chunks = [c for c in chunks if not c.get("is_hit")]

        parts = []

        if hit_chunks:
            parts.append("## 直接相关内容")
            for c in hit_chunks:
                score_tag = f"（相似度：{c.get('score', 0):.2f}）" if c.get("score") else ""
                heading = f"### {c.get('heading', '无标题')}{score_tag}\n" if c.get("heading") else ""
                parts.append(f"{heading}{c['content']}")

        if expanded_chunks:
            parts.append("\n## 相关上下文")
            by_doc = group_by_key(expanded_chunks, "doc_id")
            for doc_id, doc_chunks in by_doc.items():
                doc_name = doc_chunks[0].get("metadata", {}).get("doc_name", f"文档 {doc_id}")
                parts.append(f"### 来自：{doc_name}")
                for c in doc_chunks:
                    parts.append(c["content"])

        return "\n\n".join(parts)

    async def build_system_prompt(self, context, kb_name="知识库") -> str:
        """加载模板并注入上下文"""
        template = await load_template("rag-query")
        if template:
            return template.replace("{{kb_name}}", kb_name).replace("{{context}}", context)
        # 默认回退提示词
        return f"""你是一个有帮助的助手。根据以下知识库内容进行回答。

知识库：{kb_name}

{context}

说明：
- 基于提供的上下文进行回答
- 若上下文中不包含相关信息，请如实说明
- 回答要简洁准确"""
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
                         "chunks": result["chunks"][:10],  # 限制前端数量
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

## SSE 流实现

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
        self.queue.put_nowait(None)  # 哨兵值

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
