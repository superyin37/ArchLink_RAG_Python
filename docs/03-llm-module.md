# 03 - LLM Module Specification

## Overview
Multi-provider LLM integration supporting streaming chat completions, prompt caching, call logging, cost calculation, retry with backoff, and fallback routing.

## Architecture

```
Factory (LLMOne / ResponseOne)
  ├── auto-register all adapter classes
  ├── extract config from DB or config file
  ├── select adapter class by api_type
  └── instantiate + call chat()

Adapter Hierarchy:
  LLMBase (completions/)
    ├── LLMOpenAI
    ├── LLMAnthropic
    ├── LLMAzure
    ├── LLMGemini
    └── LLMVolcengine

  ResponseBase(LLMBase) (responses/)
    ├── ResponseOpenAI
    ├── ResponseAnthropic
    ├── ResponseAzure
    └── ResponseGemini
```

## Supported Providers

| Provider | api_type | Auth Header | Endpoint Pattern | Special |
|----------|----------|-------------|------------------|---------|
| OpenAI | `openai` | `Authorization: Bearer {key}` | `{base}/chat/completions` | Reasoning mode, auto-caching |
| Azure | `azure` | `api-key: {key}` | `{base}/openai/deployments/{deploy}/chat/completions?api-version={ver}` | Deployment-based |
| Anthropic | `anthropic` | `x-api-key: {key}` | `{base}/v1/messages` | Extended thinking, explicit cache_control |
| Gemini | `google` | `key={key}` (query param) | `{base}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}` | Different SSE delimiter `\n\r\n` |
| VolcEngine | `openai-compatible` | `Authorization: Bearer {key}` | Same as OpenAI | Bytedance's Doubao models |
| DeepSeek | `openai-compatible` | `Authorization: Bearer {key}` | Same as OpenAI | OpenAI-compatible |
| OpenRouter | `openai-compatible` | `Authorization: Bearer {key}` | Same as OpenAI | Multi-model aggregator |

## LLMBase - Base Adapter Class

### Constructor Parameters
```python
class LLMBase:
    def __init__(self, base_url: str, api_key: str, model: str,
                 user_id: int = None, session_id: str = None,
                 provider_id: str = None, api_type: str = None,
                 template_id: int = None, tags: list = None):
```

### Core Methods

#### `async chat(messages, **options) -> str`
- Build HTTP request body
- Call `request()` to execute streaming HTTP call
- Return complete response text

#### `async request(url, headers, body, **kwargs) -> str`
1. Start LogRecorder (`start_request()`)
2. Make HTTP POST with `stream=True` via httpx
3. Call `_parse_stream()` to process SSE events
4. On completion: `log_recorder.complete()`
5. On error: `log_recorder.record_error()`
6. Return accumulated text

#### `async _parse_stream(response) -> str`
- Read response line by line (SSE format)
- Split by delimiter (`\n\n` for most, `\n\r\n` for Gemini)
- For each chunk, call `message_to_value(line)`
- Dispatch by type:
  - `reasoning` -> call `on_thinking(text)`
  - `text` -> call `on_content(text)` + `on_token_stream(text)`
  - `tool_call` -> call `on_tool_call(data)`
  - `usage` -> call `log_recorder.record_usage(data)`
- On stream end: call `on_thinking_complete()` if thinking exists

#### `message_to_value(line: str) -> dict`
Parse SSE data line. Default (OpenAI format):
```python
# Input: "data: {json}\n\n"
# Output: {"type": "text"|"reasoning"|"usage"|"tool_call", "text": "...", "usage": {...}}

# Extract from: choices[0].delta.content, choices[0].delta.reasoning_content
# Usage from: usage.prompt_tokens, usage.completion_tokens, etc.
```

### Callbacks
```python
on_token_stream: Callable[[str], None]  # Every token (for SSE output)
on_thinking: Callable[[str], None]      # Reasoning/thinking tokens
on_thinking_complete: Callable[[], None] # When thinking phase ends
on_content: Callable[[str], None]       # Content tokens (non-reasoning)
on_error: Callable[[Exception], None]   # Error handler
```

## Provider-Specific Implementations

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
    # Separate system messages
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
    # Anthropic uses event-based SSE:
    # "event: content_block_delta\ndata: {delta: {type: text_delta, text: ...}}"
    # "event: message_delta\ndata: {delta: {stop_reason: ...}, usage: {...}}"
```

### LLMAzure
```python
async def chat(self, messages, **kwargs):
    deployment = self.model  # Azure uses deployment name
    api_version = self.extra_params.get("api_version", "2024-08-01-preview")
    url = f"{self.base_url}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"api-key": self.api_key}
    body = {  # No "model" field for Azure
        "messages": messages, "stream": True,
        "stream_options": {"include_usage": True}, **kwargs
    }
    return await self.request(url, headers, body)
```

### LLMGemini
```python
async def chat(self, messages, **kwargs):
    # Convert OpenAI format -> Gemini format
    gemini_contents = self._convert_messages(messages)
    url = f"{self.base_url}/v1beta/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
    body = {"contents": gemini_contents, "generationConfig": {...}}
    return await self.request(url, {}, body)

def _convert_messages(self, messages):
    """Convert OpenAI messages to Gemini format"""
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        # Gemini: system messages become user messages
        if msg["role"] == "system":
            role = "user"
        parts = [{"text": msg["content"]}]
        contents.append({"role": role, "parts": parts})
    return contents

# Override: Gemini uses \n\r\n as SSE delimiter (not \n\n)
SSE_DELIMITER = "\n\r\n"
```

## LLMOne Factory

```python
class LLMOne:
    CLASS_MAP = {}  # Populated by auto_register()

    @classmethod
    def auto_register(cls):
        """Scan completions/ directory, register all LLMBase subclasses"""
        # Maps api_type -> class: {"openai": LLMOpenAI, "anthropic": LLMAnthropic, ...}

    @classmethod
    def from_database(cls, db_provider, db_model, **kwargs):
        """Create from database provider+model records"""
        config = cls._extract_from_database(db_provider, db_model)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config, **kwargs)

    @classmethod
    def from_config(cls, model_with_provider: str, **kwargs):
        """Create from config string like 'openai#gpt-4o'"""
        config = cls._extract_from_config(model_with_provider)
        adapter_class = cls._select_adapter(config["api_type"])
        return adapter_class(**config, **kwargs)

    @staticmethod
    def _select_adapter(api_type):
        # "openai-compatible" -> LLMOpenAI (fallback)
        if api_type in LLMOne.CLASS_MAP:
            return LLMOne.CLASS_MAP[api_type]
        return LLMOne.CLASS_MAP.get("openai")
```

## Response Layer (Prompt Caching)

ResponseBase extends LLMBase with:

### Cache Control Methods
```python
class ResponseBase(LLMBase):
    def _apply_cache_control(self, messages, cache_config):
        """Apply provider-specific cache control to messages"""
        pass  # Override in subclasses

    def get_cache_stats(self):
        """Return cache statistics"""
        return {
            "cache_read_tokens": self._cache_read_tokens,
            "cache_creation_tokens": self._cache_creation_tokens,
            "hit": self._cache_read_tokens > 0,
            "savings_percent": ...
        }
```

### Anthropic Cache Implementation
```python
class ResponseAnthropic(ResponseBase):
    def _apply_cache_control(self, messages, cache_config):
        # Add cache_control to system message:
        # {"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}
        # Add cache_control to specified message breakpoints
```

## Usage Statistics (Unified Format)

All providers normalize to:
```python
{
    "prompt_tokens": int,
    "completion_tokens": int,
    "total_tokens": int,
    "reasoning_tokens": int,      # Optional
    "cached_tokens": int,          # Optional
    "cache_read_tokens": int,      # Optional (Anthropic)
    "cache_creation_tokens": int,  # Optional (Anthropic)
}
```

## LogRecorder - Call Lifecycle Tracking

```python
class LogRecorder:
    def __init__(self, provider_id, model, api_type, user_id, session_id, template_id, tags):
        self.request_id = str(uuid4())
        self.content_parts = []
        self.reasoning_parts = []

    async def start_request(self, url, headers, body):
        """Create initial log record in DB (status=pending)"""
        # Sanitize headers (mask Authorization, api-key)
        await call_log_service.create({...})

    def record_first_token(self):
        """Record TTFT (Time To First Token)"""
        self.first_token_time = time_ms()
        self.first_token_duration = self.first_token_time - self.request_start_time

    def record_content(self, text, content_type="text"):
        """Accumulate content/reasoning"""
        if content_type == "reasoning":
            self.reasoning_parts.append(text)
        else:
            self.content_parts.append(text)

    def record_usage(self, usage):
        """Record token usage stats"""
        self.usage = usage

    async def complete(self):
        """Finalize log (status=success)"""
        await call_log_service.update(self.request_id, {
            "status": "success", "is_success": True,
            "response_text": "".join(self.content_parts),
            "reasoning_text": "".join(self.reasoning_parts),
            "total_duration": time_ms() - self.request_start_time,
            **self.usage
        })

    async def record_error(self, error):
        """Record error (status=error)"""
        await call_log_service.update(self.request_id, {
            "status": "error", "is_success": False,
            "error_message": str(error)
        })
```

## Cost Calculation

```python
async def calculate_cost(provider_id, model, prompt_tokens, completion_tokens, cached_tokens=0):
    """Calculate cost from model pricing config"""
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

## Retry & Fallback

### withRetryBackoff
```python
def with_retry_backoff(fn, retries=3, base_delay=0.5, factor=2, jitter=True,
                       retry_condition=None):
    """Wrap async function with exponential backoff retry"""
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
    """Try primary, then fallback models on failure"""
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as primary_error:
            for fb in fallbacks:
                try:
                    if on_fallback:
                        on_fallback(fb)
                    # Create new LLM instance with fallback config
                    return await fn_with_new_model(fb, *args, **kwargs)
                except Exception:
                    continue
            raise primary_error
    return wrapper
```

## Media Resolver

```python
class MediaResolver:
    MIME_SIGNATURES = {
        b'\x89PNG': 'image/png',
        b'\xff\xd8\xff': 'image/jpeg',
        b'GIF': 'image/gif',
        b'RIFF': 'image/webp',  # Check for WEBP after RIFF
        b'BM': 'image/bmp',
    }

    @staticmethod
    async def resolve(input_data) -> str:
        """Convert any media input to data URL"""
        input_type = detect_input_type(input_data)
        if input_type == "filepath":
            data = Path(input_data).read_bytes()
            mime = detect_mime(data)
            b64 = base64.b64encode(data).decode()
            return f"data:{mime};base64,{b64}"
        elif input_type == "url":
            return input_data  # Return URL directly
        elif input_type == "base64":
            mime = detect_mime(base64.b64decode(input_data[:100]))
            return f"data:{mime};base64,{input_data}"
        elif input_type == "data_url":
            return input_data
```

## LLM Service Layer

### ProviderService
```python
class ProviderService:
    async def get_list(page, size, keyword, status, api_type) -> PageResult
    async def get_detail(provider_id) -> dict  # includes models list
    async def create(data) -> dict
    async def update(provider_id, data) -> None
    async def delete(provider_id) -> None  # builtin cannot delete
    async def update_api_key(provider_id, api_key) -> None
    async def get_api_types() -> list[str]
```

### ModelService
```python
class ModelService:
    async def get_list(provider_id, page, size, keyword, status) -> PageResult
    async def get_detail(model_id) -> dict  # includes provider info
    async def create(data) -> dict
    async def update(model_id, data) -> None
    async def delete(model_id) -> None  # builtin cannot delete
    async def deprecate(model_id, replacement_model_id) -> None
    async def get_by_provider() -> list  # grouped by provider
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
    async def create(data) -> CallLog  # auto-calculate cost
    async def update(request_id, data) -> int
    async def find_by_request_id(request_id) -> CallLog
    async def get_list(filters) -> PageResult
    async def get_statistics(filters) -> dict  # aggregated stats
    async def get_stats_by_provider(filters) -> list
    async def get_stats_by_model(filters) -> list
    async def get_stats_by_time(filters, group_by) -> list  # day/hour
    async def get_token_ranking(filters, limit) -> list
```
