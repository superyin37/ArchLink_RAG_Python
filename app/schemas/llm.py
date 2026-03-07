from typing import Any, Optional
from pydantic import BaseModel
from datetime import datetime, date


# Provider schemas
class LLMProviderCreate(BaseModel):
    provider_id: str
    name: str
    icon: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_type: str = "openai"
    api_key: Optional[str] = None
    auth_type: str = "bearer"
    default_parameters: Optional[dict] = None
    description: Optional[str] = None
    official_website: Optional[str] = None
    documentation_url: Optional[str] = None
    status: int = 1
    sort_order: int = 0


class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    auth_type: Optional[str] = None
    default_parameters: Optional[dict] = None
    description: Optional[str] = None
    status: Optional[int] = None
    sort_order: Optional[int] = None


class APIKeyUpdate(BaseModel):
    api_key: str


class LLMProviderResponse(BaseModel):
    id: int
    provider_id: str
    name: str
    icon: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_type: str = "openai"
    auth_type: str = "bearer"
    default_parameters: Optional[dict] = None
    description: Optional[str] = None
    status: int = 1
    is_builtin: bool = False
    sort_order: int = 0
    create_time: Optional[datetime] = None
    models: Optional[list] = None

    class Config:
        from_attributes = True


# Model schemas
class LLMModelCreate(BaseModel):
    provider_id: str
    model_id: str
    name: str
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    capabilities: Optional[list] = None
    pricing: Optional[dict] = None
    release_date: Optional[date] = None
    status: int = 1
    sort_order: int = 0
    extra_meta: Optional[dict] = None


class LLMModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    capabilities: Optional[list] = None
    pricing: Optional[dict] = None
    status: Optional[int] = None
    sort_order: Optional[int] = None
    extra_meta: Optional[dict] = None


class DeprecateRequest(BaseModel):
    replacement_model_id: str


class LLMModelResponse(BaseModel):
    id: int
    provider_id: str
    model_id: str
    name: str
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    capabilities: Optional[list] = None
    pricing: Optional[dict] = None
    status: int = 1
    is_builtin: bool = False
    is_deprecated: bool = False
    sort_order: int = 0
    create_time: Optional[datetime] = None
    provider: Optional[dict] = None

    class Config:
        from_attributes = True


# Chat schemas
class ChatCreate(BaseModel):
    model: Optional[str] = None
    title: Optional[str] = "New Chat"


class ChatTitleUpdate(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: int
    chat_id: str
    title: str
    model: Optional[str] = None
    message_count: int = 0
    total_tokens: int = 0
    status: int = 1
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    chat_id: str
    role: str
    content: str
    model: Optional[str] = None
    token_usage: Optional[dict] = None
    meta: Optional[dict] = None
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True


# Call log filter
class CallLogFilter(BaseModel):
    page: int = 1
    size: int = 20
    provider_id: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    is_success: Optional[bool] = None
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keyword: Optional[str] = None
