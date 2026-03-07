# 03 - LLM 模块规范

## 概述
多提供者 LLM 集成，支持流式聊天补全、提示词缓存、调用日志、费用计算、带退避的重试以及故障转移路由。

## 架构

```
工厂（LLMOne / ResponseOne）
  ├── 自动注册所有适配器类
  ├── 从数据库或配置文件提取配置
  ├── 按 api_type 选择适配器类
  └── 实例化并调用 chat()

适配器层次结构：
  LLMBase（completions/）
    ├── LLMOpenAI
    ├── LLMAnthropic
    ├── LLMAzure
    ├── LLMGemini
    └── LLMVolcengine

  ResponseBase(LLMBase)（responses/）
    ├── ResponseOpenAI
    ├── ResponseAnthropic
    ├── ResponseAzure
    └── ResponseGemini
```

## 支持的提供者

| 提供者 | api_type | 认证头 | 端点格式 | 特殊说明 |
|----------|----------|-------------|------------------|---------|
| OpenAI | `openai` | `Authorization: Bearer {key}` | `{base}/chat/completions` | 推理模式、自动缓存 |
| Azure | `azure` | `api-key: {key}` | `{base}/openai/deployments/{deploy}/chat/completions?api-version={ver}` | 基于部署 |
| Anthropic | `anthropic` | `x-api-key: {key}` | `{base}/v1/messages` | 扩展思考、显式 cache_control |
| Gemini | `google` | `key={key}`（查询参数） | `{base}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}` | 不同 SSE 分隔符 `\n\r\n` |
| 火山引擎 | `openai-compatible` | `Authorization: Bearer {key}` | 同 OpenAI | 字节跳动豆包模型 |
| DeepSeek | `openai-compatible` | `Authorization: Bearer {key}` | 同 OpenAI | OpenAI 兼容 |
| OpenRouter | `openai-compatible` | `Authorization: Bearer {key}` | 同 OpenAI | 多模型聚合器 |

## LLMBase - 基础适配器类

### 构造参数
```python
class LLMBase:
    def __init__(self, base_url: str, api_key: str, model: str,
                 user_id: int = None, session_id: str = None,
                 provider_id: str = None, api_type: str = None,
                 template_id: int = None, tags: list = None):
```

### 核心方法

#### `async chat(messages, **options) -> str`
- 构建 HTTP 请求体
- 调用 `request()` 执行流式 HTTP 请求
- 返回完整响应文本

#### `async request(url, headers, body, **kwargs) -> str`
1. 启动 LogRecorder（`start_request()`）
2. 通过 httpx 以 `stream=True` 发起 HTTP POST
3. 调用 `_parse_stream()` 处理 SSE 事件
4. 完成时：`log_recorder.complete()`
5. 出错时：`log_recorder.record_error()`
6. 返回累积文本

#### `async _parse_stream(response) -> str`
- 逐行读取响应（SSE 格式）
- 按分隔符分割（大多数为 `\n\n`，Gemini 为 `\n\r\n`）
- 对每个块调用 `message_to_value(line)`
- 按类型分发：
  - `reasoning` -> 调用 `on_thinking(text)`
  - `text` -> 调用 `on_content(text)` + `on_token_stream(text)`
  - `tool_call` -> 调用 `on_tool_call(data)`
  - `usage` -> 调用 `log_recorder.record_usage(data)`
- 流结束时：若存在思考内容，调用 `on_thinking_complete()`

#### `message_to_value(line: str) -> dict`
解析 SSE 数据行。默认（OpenAI 格式）：
```python
# 输入："data: {json}\n\n"
# 输出：{"type": "text"|"reasoning"|"usage"|"tool_call", "text": "...", "usage": {...}}

# 从以下字段提取：choices[0].delta.content, choices[0].delta.reasoning_content
# 用量从：usage.prompt_tokens, usage.completion_tokens 等
```

### 回调函数
```python
on_token_stream: Callable[[str], None]  # 每个 Token（用于 SSE 输出）
on_thinking: Callable[[str], None]      # 推理/思考 Token
on_thinking_complete: Callable[[], None] # 思考阶段结束时
on_content: Callable[[str], None]       # 内容 Token（非推理）
on_error: Callable[[Exception], None]   # 错误处理器
```

## 提供者特定实现

### LLMOpenAI
```python
async def chat(self, messages, temperature=0.7, max_tokens=4096,
               thinking=None, tools=None, **kwargs):
    body = {
        "model": self.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if thinking and thinking.get("type") == "enabled":
        body["thinking"] = thinking
    if tools:
        body["tools"] = tools
    headers = {"Authorization": f"Bearer {self.api_key}"}
    return await self.request(f"{self.base_url}/chat/completions", headers, body)
```

### LLMAnthropic
```python
async def chat(self, messages, temperature=0.7, max_tokens=4096, **kwargs):
    # 分离系统消息
    system_content, user_messages = self._separate_system(messages)
    body = {
        "model": self.model,
        "messages": user_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if system_content:
        body["system"] = system_content
    headers = {
        "x-api-key": self.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    return await self.request(f"{self.base_url}/v1/messages", headers, body)

def message_to_value(self, line):
    # Anthropic 使用基于事件的 SSE：
    # "event: content_block_delta\ndata: {delta: {type: text_delta, text: ...}}"
    # "event: message_delta\ndata: {delta: {stop_reason: ...}, usage: {...}}"
```

### LLMAzure
```python
async def chat(self, messages, **kwargs):
    deployment = self.model  # Azure 使用部署名称
    api_version = self.extra_params.get("api_version", "2024-08-01-preview")
    url = f"{self.base_url}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"api-key": self.api_key}
    body = {  # Azure 没有 "model" 字段
        "messages": messages, "stream": True,
        "stream_options": {"include_usage": True}, **kwargs
    }
    return await self.request(url, headers, body)
```

### LLMGemini
```python
async def chat(self, messages, **kwargs):
    # 将 OpenAI 格式转换为 Gemini 格式
    gemini_contents = self._convert_messages(messages)
    url = f"{self.base_url}/v1beta/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
    body = {"contents": gemini_contents, "generationConfig": {...}}
    return await self.request(url, {}, body)

def _convert_messages(self, messages):
    """将 OpenAI 消息格式转换为 Gemini 格式"""
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        # Gemini：系统消息转为用户消息
        if msg["role"] == "system":
            role = "user"
        parts = [{"text": msg["content"]}]
        contents.append({"role": role, "parts": parts})
    return contents

# 重写：Gemini 使用 \n\r\n 作为 SSE 分隔符（而非 \n\n）
SSE_DELIMITER = "\n\r\n"
```

## LLMOne 工厂

```python
class LLMOne:
    CLASS_MAP = {}  # 由 auto_register() 填充

    @classmethod
    def auto_register(cls):
        """扫描 completions/ 目录，注册所有 LLMBase 子类"""
        # 映射 api_type -> 类：{"openai": LLMOpenAI, "anthropic": LLMAnthropic, ...}

    @classmethod
    def from_database(cls, db_provider, db_model, **kwargs):
        """从数据库 provider+model 记录创建"""
        config = cls._extract_from_database(db_provider, db_model)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config, **kwargs)

    @classmethod
    def from_config(cls, model_with_provider: str, **kwargs):
        """从配置字符串创建，如 'openai#gpt-4o'"""
        config = cls._extract_from_config(model_with_provider)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config, **kwargs)

    @staticmethod
    def _select_adapter(api_type):
        # "openai-compatible" -> LLMOpenAI（回退）
        if api_type in LLMOne.CLASS_MAP:
            return LLMOne.CLASS_MAP[api_type]
        return LLMOne.CLASS_MAP.get("openai")
```

## 响应层（提示词缓存）

ResponseBase 在 LLMBase 基础上扩展：

### 缓存控制方法
```python
class ResponseBase(LLMBase):
    def _apply_cache_control(self, messages, cache_config):
        """对消息应用提供者特定的缓存控制"""
        pass  # 子类重写

    def get_cache_stats(self):
        """返回缓存统计"""
        return {
            "cache_read_tokens": self._cache_read_tokens,
            "cache_creation_tokens": self._cache_creation_tokens,
            "hit": self._cache_read_tokens > 0,
            "savings_percent": ...
        }
```

### Anthropic 缓存实现
```python
class ResponseAnthropic(ResponseBase):
    def _apply_cache_control(self, messages, cache_config):
        # 为系统消息添加 cache_control：
        # {"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}
        # 为指定消息断点添加 cache_control
```

## 用量统计（统一格式）

所有提供者统一规范化为：
```python
{
    "prompt_tokens": int,
    "completion_tokens": int,
    "total_tokens": int,
    "reasoning_tokens": int,      # 可选
    "cached_tokens": int,          # 可选
    "cache_read_tokens": int,      # 可选（Anthropic）
    "cache_creation_tokens": int,  # 可选（Anthropic）
}
```

## LogRecorder - 调用生命周期跟踪

```python
class LogRecorder:
    def __init__(self, provider_id, model, api_type, user_id, session_id, template_id, tags):
        self.request_id = str(uuid4())
        self.content_parts = []
        self.reasoning_parts = []

    async def start_request(self, url, headers, body):
        """在数据库中创建初始日志记录（status=pending）"""
        # 对请求头脱敏（隐藏 Authorization、api-key）
        await call_log_service.create({...})

    def record_first_token(self):
        """记录首 Token 耗时（TTFT）"""
        self.first_token_time = time_ms()
        self.first_token_duration = self.first_token_time - self.request_start_time

    def record_content(self, text, content_type="text"):
        """累积内容/推理内容"""
        if content_type == "reasoning":
            self.reasoning_parts.append(text)
        else:
            self.content_parts.append(text)

    def record_usage(self, usage):
        """记录 Token 用量统计"""
        self.usage = usage

    async def complete(self):
        """完成日志记录（status=success）"""
        await call_log_service.update(self.request_id, {
            "status": "success", "is_success": True,
            "response_text": "".join(self.content_parts),
            "reasoning_text": "".join(self.reasoning_parts),
            "total_duration": time_ms() - self.request_start_time,
            **self.usage
        })

    async def record_error(self, error):
        """记录错误（status=error）"""
        await call_log_service.update(self.request_id, {
            "status": "error", "is_success": False,
            "error_message": str(error)
        })
```

## 费用计算

```python
async def calculate_cost(provider_id, model, prompt_tokens, completion_tokens, cached_tokens=0):
    """根据模型定价配置计算费用"""
    model_record = await model_service.get_by_provider_and_model(provider_id, model)
    if not model_record or not model_record.pricing:
        return None

    pricing = model_record.pricing
    per_tokens = pricing.get("per_tokens", 1000)

    input_cost = (prompt_tokens / per_tokens) * pricing.get("input_price", 0)
    output_cost = (completion_tokens / per_tokens) * pricing.get("output_price", 0)
    cache_cost = 0
    if cached_tokens > 0 and pricing.get("cache_hit_price"):
        cache_cost = (cached_tokens / per_tokens) * pricing["cache_hit_price"]

    return {
        "cost": input_cost + output_cost + cache_cost,
        "cost_details": {
            "input": input_cost, "output": output_cost,
            "cache": cache_cost, "currency": pricing.get("currency", "USD")
        }
    }
```

## 重试与故障转移

### withRetryBackoff
```python
def with_retry_backoff(fn, retries=3, base_delay=0.5, factor=2, jitter=True,
                       retry_condition=None):
    """使用指数退避重试包装异步函数"""
    async def wrapper(*args, **kwargs):
        for attempt in range(retries + 1):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                if attempt == retries:
                    raise
                if retry_condition and not retry_condition(e):
                    raise
                delay = base_delay * (factor ** attempt)
                if jitter:
                    delay *= 0.8 + random.random() * 0.4
                await asyncio.sleep(delay)
    return wrapper
```

### withFallbackRouter
```python
def with_fallback_router(fn, fallbacks, on_fallback=None):
    """主模型失败后尝试备用模型"""
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as primary_error:
            for fb in fallbacks:
                try:
                    if on_fallback:
                        on_fallback(fb)
                    # 使用备用配置创建新 LLM 实例
                    return await fn_with_new_model(fb, *args, **kwargs)
                except Exception:
                    continue
            raise primary_error
    return wrapper
```

## 媒体解析器

```python
class MediaResolver:
    MIME_SIGNATURES = {
        b'\x89PNG': 'image/png',
        b'\xff\xd8\xff': 'image/jpeg',
        b'GIF': 'image/gif',
        b'RIFF': 'image/webp',  # RIFF 后检查 WEBP
        b'BM': 'image/bmp',
    }

    @staticmethod
    async def resolve(input_data) -> str:
        """将任意媒体输入转换为数据 URL"""
        input_type = detect_input_type(input_data)
        if input_type == "filepath":
            data = Path(input_data).read_bytes()
            mime = detect_mime(data)
            b64 = base64.b64encode(data).decode()
            return f"data:{mime};base64,{b64}"
        elif input_type == "url":
            return input_data  # 直接返回 URL
        elif input_type == "base64":
            mime = detect_mime(base64.b64decode(input_data[:100]))
            return f"data:{mime};base64,{input_data}"
        elif input_type == "data_url":
            return input_data
```

## LLM 服务层

### ProviderService
```python
class ProviderService:
    async def get_list(page, size, keyword, status, api_type) -> PageResult
    async def get_detail(provider_id) -> dict  # 包含模型列表
    async def create(data) -> dict
    async def update(provider_id, data) -> None
    async def delete(provider_id) -> None  # 内置不可删除
    async def update_api_key(provider_id, api_key) -> None
    async def get_api_types() -> list[str]
```

### ModelService
```python
class ModelService:
    async def get_list(provider_id, page, size, keyword, status) -> PageResult
    async def get_detail(model_id) -> dict  # 包含提供者信息
    async def create(data) -> dict
    async def update(model_id, data) -> None
    async def delete(model_id) -> None  # 内置不可删除
    async def deprecate(model_id, replacement_model_id) -> None
    async def get_by_provider() -> list  # 按提供者分组
```

### ChatService
```python
class ChatService:
    async def get_user_chats(user_id, page, size) -> PageResult
    async def get_detail(chat_id) -> Chat
    async def create(user_id, model, title) -> Chat
    async def update_title(chat_id, title) -> None
    async def delete(chat_id) -> bool
    async def get_messages(chat_id, page, size) -> PageResult
```

### MessageService
```python
class MessageService:
    async def save_user_message(chat_id, content, user_id, meta) -> Message
    async def save_assistant_message(chat_id, content, model, token_usage, meta) -> Message
    async def get_messages(chat_id, page, size) -> PageResult
    async def get_last_user_message(chat_id) -> Message
    async def get_total_tokens(chat_id) -> int
```

### CallLogService
```python
class CallLogService:
    async def create(data) -> CallLog  # 自动计算费用
    async def update(request_id, data) -> int
    async def find_by_request_id(request_id) -> CallLog
    async def get_list(filters) -> PageResult
    async def get_statistics(filters) -> dict  # 聚合统计
    async def get_stats_by_provider(filters) -> list
    async def get_stats_by_model(filters) -> list
    async def get_stats_by_time(filters, group_by) -> list  # 按天/小时
    async def get_token_ranking(filters, limit) -> list
```
