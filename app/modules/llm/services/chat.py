"""LLM Chat CRUD service."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMChat
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ChatService:
    async def get_user_chats(
        self, db: AsyncSession, user_id: int, page: int = 1, size: int = 20
    ) -> dict:
        q = select(LLMChat).where(
            LLMChat.user_id == user_id,
            LLMChat.delete_time.is_(None),
        ).order_by(LLMChat.update_time.desc())

        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        result = await db.execute(q.offset((page - 1) * size).limit(size))
        return {"list": result.scalars().all(), "total": total}

    async def get_by_chat_id(self, db: AsyncSession, chat_id: str) -> LLMChat:
        result = await db.execute(
            select(LLMChat).where(
                LLMChat.chat_id == chat_id,
                LLMChat.delete_time.is_(None),
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            raise NotFoundError(f"Chat {chat_id} not found")
        return chat

    async def create(self, db: AsyncSession, data: dict) -> LLMChat:
        chat = LLMChat(**data)
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
        return chat

    async def update_title(self, db: AsyncSession, chat_id: str, title: str):
        chat = await self.get_by_chat_id(db, chat_id)
        chat.title = title
        await db.commit()

    async def delete(self, db: AsyncSession, chat_id: str) -> bool:
        chat = await self.get_by_chat_id(db, chat_id)
        from datetime import datetime, timezone
        chat.delete_time = datetime.now(timezone.utc)
        await db.commit()
        return True


chat_service = ChatService()
