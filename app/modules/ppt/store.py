"""PPT module models - in-memory store for conversations/messages.

The PPT module uses a lightweight in-memory data model since the database
schema doesn't define separate PPT tables. For production, extend to DB.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class PptConversation:
    id: str
    conversation_type: str = "ppt_design"
    stage: str = "requirement"
    metadata: dict = field(default_factory=dict)
    user_id: Optional[int] = None
    create_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    update_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PptMessage:
    id: int
    conversation_id: str
    role: str
    content: str
    message_type: str = "text"
    meta: dict = field(default_factory=dict)
    create_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# In-memory stores (thread-safe enough for single-process FastAPI)
_conversations: dict[str, PptConversation] = {}
_messages: dict[str, list[PptMessage]] = {}
_message_id_counter = 0


def _next_message_id() -> int:
    global _message_id_counter
    _message_id_counter += 1
    return _message_id_counter


def create_conversation(
    conversation_type: str = "ppt_design",
    metadata: dict = None,
    user_id: int = None,
) -> PptConversation:
    conv = PptConversation(
        id=str(uuid.uuid4()),
        conversation_type=conversation_type,
        stage="requirement" if conversation_type == "ppt_design" else None,
        metadata=metadata or {},
        user_id=user_id,
    )
    _conversations[conv.id] = conv
    _messages[conv.id] = []
    return conv


def get_conversation(conversation_id: str) -> Optional[PptConversation]:
    return _conversations.get(conversation_id)


def save_conversation(conv: PptConversation):
    conv.update_time = datetime.now(timezone.utc)
    _conversations[conv.id] = conv


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    meta: dict = None,
) -> PptMessage:
    msg = PptMessage(
        id=_next_message_id(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_type=message_type,
        meta=meta or {},
    )
    _messages.setdefault(conversation_id, []).append(msg)
    return msg


def update_message(msg: PptMessage):
    msgs = _messages.get(msg.conversation_id, [])
    for i, m in enumerate(msgs):
        if m.id == msg.id:
            msgs[i] = msg
            break


def get_messages(conversation_id: str, limit: int = 50) -> list[PptMessage]:
    return _messages.get(conversation_id, [])[-limit:]
