"""LLM Message service."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMMessage
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class MessageService:
    async def save_user_message(
        self, db: AsyncSession, chat_id: str, content: str,
        user_id: int = None, meta: dict = None
    ) -> LLMMessage:
        msg = LLMMessage(
            chat_id=chat_id,
            role="user",
            content=content,
            user_id=user_id,
            meta=meta or {},
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    async def save_assistant_message(
        self, db: AsyncSession, chat_id: str, content: str,
        model: str = None, token_usage: dict = None, meta: dict = None
    ) -> LLMMessage:
        msg = LLMMessage(
            chat_id=chat_id,
            role="assistant",
            content=content,
            model=model,
            token_usage=token_usage or {},
            meta=meta or {},
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    async def get_messages(
        self, db: AsyncSession, chat_id: str, page: int = 1, size: int = 50
    ) -> dict:
        q = select(LLMMessage).where(
            LLMMessage.chat_id == chat_id,
            LLMMessage.delete_time.is_(None),
        ).order_by(LLMMessage.create_time.asc())

        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        result = await db.execute(q.offset((page - 1) * size).limit(size))
        return {"list": result.scalars().all(), "total": total}

    async def get_last_user_message(
        self, db: AsyncSession, chat_id: str
    ) -> LLMMessage | None:
        result = await db.execute(
            select(LLMMessage).where(
                LLMMessage.chat_id == chat_id,
                LLMMessage.role == "user",
                LLMMessage.delete_time.is_(None),
            ).order_by(LLMMessage.create_time.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_total_tokens(self, db: AsyncSession, chat_id: str) -> int:
        result = await db.execute(
            select(LLMMessage).where(
                LLMMessage.chat_id == chat_id,
                LLMMessage.delete_time.is_(None),
            )
        )
        messages = result.scalars().all()
        total = 0
        for msg in messages:
            usage = msg.token_usage or {}
            total += usage.get("total_tokens", 0)
        return total

    async def get_chat_history(self, db: AsyncSession, chat_id: str) -> list[dict]:
        """Return messages in OpenAI format for LLM input."""
        result = await db.execute(
            select(LLMMessage).where(
                LLMMessage.chat_id == chat_id,
                LLMMessage.delete_time.is_(None),
            ).order_by(LLMMessage.create_time.asc())
        )
        messages = result.scalars().all()
        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]


message_service = MessageService()
