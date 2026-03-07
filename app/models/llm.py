from sqlalchemy import Column, Integer, String, Text, BigInteger, JSON, DECIMAL, Boolean, Date, Enum
from sqlalchemy import Index, UniqueConstraint
from app.models.base import BaseModel


class LLMProvider(BaseModel):
    __tablename__ = "llm_providers"

    provider_id = Column(String(50), nullable=False, unique=True, comment="Unique identifier")
    name = Column(String(100), nullable=False, comment="Display name")
    icon = Column(String(20), nullable=True, comment="Emoji or icon class")
    api_endpoint = Column(String(500), nullable=True, comment="API base URL")
    api_type = Column(String(50), default="openai", comment="API type")
    api_key = Column(Text, nullable=True, comment="Global API key")
    auth_type = Column(String(50), default="bearer", comment="Auth type")
    default_parameters = Column(JSON, default=dict, comment="Default request parameters")
    description = Column(Text, nullable=True)
    official_website = Column(String(500), nullable=True)
    documentation_url = Column(String(500), nullable=True)
    status = Column(Integer, default=1, comment="0=disabled, 1=enabled")
    is_builtin = Column(Boolean, default=False, comment="Cannot delete if true")
    sort_order = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_llm_provider_status", "status"),
        Index("idx_llm_provider_sort", "sort_order"),
    )


class LLMModel(BaseModel):
    __tablename__ = "llm_models"

    provider_id = Column(String(50), nullable=False, comment="FK to llm_providers.provider_id")
    model_id = Column(String(100), nullable=False, comment="Model identifier")
    name = Column(String(100), nullable=False, comment="Display name")
    description = Column(Text, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    context_window = Column(Integer, nullable=True)
    capabilities = Column(JSON, default=list, comment='["chat", "vision", ...]')
    pricing = Column(JSON, nullable=True, comment="Pricing config")
    release_date = Column(Date, nullable=True)
    is_deprecated = Column(Boolean, default=False)
    replacement_model_id = Column(String(100), nullable=True)
    status = Column(Integer, default=1, comment="0=disabled, 1=enabled")
    is_builtin = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    extra_meta = Column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
        Index("idx_llm_model_provider", "provider_id"),
        Index("idx_llm_model_status", "status"),
        Index("idx_llm_model_deprecated", "is_deprecated"),
    )


class LLMChat(BaseModel):
    __tablename__ = "llm_chat"

    chat_id = Column(String(64), nullable=False, comment="Unique chat identifier")
    user_id = Column(BigInteger, nullable=True)
    title = Column(String(200), default="New Chat")
    model = Column(String(100), nullable=True)
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    status = Column(Integer, default=1, comment="0=archived, 1=active")

    __table_args__ = (
        Index("idx_llm_chat_user_update", "user_id", "update_time"),
        Index("idx_llm_chat_id", "chat_id"),
    )


class LLMMessage(BaseModel):
    __tablename__ = "llm_message"

    chat_id = Column(String(64), nullable=False, comment="FK to llm_chat.chat_id")
    role = Column(
        Enum("system", "user", "assistant"), nullable=False, comment="Message role"
    )
    content = Column(Text, nullable=False)
    model = Column(String(100), nullable=True)
    token_usage = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    user_id = Column(BigInteger, nullable=True)
    status = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_llm_message_chat_time", "chat_id", "create_time"),
        Index("idx_llm_message_user_time", "user_id", "create_time"),
    )


class LLMCallLog(BaseModel):
    __tablename__ = "llm_call_logs"

    request_id = Column(String(100), nullable=False, comment="Unique request ID")
    provider_id = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    api_type = Column(String(50), nullable=True)
    request_url = Column(String(500), nullable=True)
    request_method = Column(String(10), default="POST")
    request_headers = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)
    prompt = Column(Text, nullable=True)
    messages = Column(JSON, nullable=True)
    response_text = Column(Text, nullable=True)
    reasoning_text = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    reasoning_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    cost = Column(DECIMAL(10, 6), nullable=True)
    cost_details = Column(JSON, nullable=True)
    request_start_time = Column(BigInteger, nullable=True)
    first_token_time = Column(BigInteger, nullable=True)
    response_end_time = Column(BigInteger, nullable=True)
    total_duration = Column(Integer, nullable=True)
    first_token_duration = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", comment="pending/streaming/success/error")
    is_success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True)
    session_id = Column(String(100), nullable=True)
    template_id = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    extra_meta = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_call_log_request_id", "request_id"),
        Index("idx_call_log_provider", "provider_id"),
        Index("idx_call_log_model", "model"),
        Index("idx_call_log_status", "status"),
        Index("idx_call_log_success", "is_success"),
        Index("idx_call_log_user", "user_id"),
        Index("idx_call_log_session", "session_id"),
        Index("idx_call_log_create_time", "create_time"),
    )
