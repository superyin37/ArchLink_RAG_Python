"""Call log service with cost calculation."""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMCallLog
from app.database import async_session as async_session_maker

logger = logging.getLogger(__name__)


async def _calculate_cost(
    provider_id: str, model: str,
    prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0
) -> dict | None:
    """Calculate cost from model pricing configuration."""
    try:
        async with async_session_maker() as db:
            from sqlalchemy import select as sql_select
            from app.models.llm import LLMModel

            result = await db.execute(
                sql_select(LLMModel).where(
                    LLMModel.provider_id == provider_id,
                    LLMModel.model_id == model,
                    LLMModel.delete_time.is_(None),
                ).limit(1)
            )
            m = result.scalar_one_or_none()
            if not m or not m.pricing:
                return None

            pricing = m.pricing
            per_tokens = pricing.get("per_tokens", 1000)
            input_cost = (prompt_tokens / per_tokens) * pricing.get("input_price", 0)
            output_cost = (completion_tokens / per_tokens) * pricing.get("output_price", 0)
            cache_cost = 0
            if cached_tokens > 0 and pricing.get("cache_hit_price"):
                cache_cost = (cached_tokens / per_tokens) * pricing["cache_hit_price"]

            return {
                "cost": input_cost + output_cost + cache_cost,
                "cost_details": {
                    "input": input_cost,
                    "output": output_cost,
                    "cache": cache_cost,
                    "currency": pricing.get("currency", "USD"),
                },
            }
    except Exception as e:
        logger.warning(f"Cost calculation failed: {e}")
        return None


class CallLogService:
    async def create(self, data: dict) -> LLMCallLog:
        try:
            async with async_session_maker() as db:
                log = LLMCallLog(**{k: v for k, v in data.items() if hasattr(LLMCallLog, k)})
                db.add(log)
                await db.commit()
                await db.refresh(log)
                return log
        except Exception as e:
            logger.warning(f"Failed to create call log: {e}")
            return None

    async def update(self, request_id: str, data: dict) -> int:
        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(LLMCallLog).where(LLMCallLog.request_id == request_id)
                )
                log = result.scalar_one_or_none()
                if not log:
                    return 0
                for k, v in data.items():
                    if hasattr(log, k):
                        setattr(log, k, v)

                # Calculate cost if we have usage data
                if data.get("is_success") and log.provider_id and log.model:
                    cost_info = await _calculate_cost(
                        log.provider_id, log.model,
                        data.get("prompt_tokens", 0),
                        data.get("completion_tokens", 0),
                        data.get("cached_tokens", 0),
                    )
                    if cost_info:
                        log.cost = cost_info["cost"]
                        log.cost_details = cost_info["cost_details"]

                await db.commit()
                return 1
        except Exception as e:
            logger.warning(f"Failed to update call log: {e}")
            return 0

    async def find_by_request_id(self, request_id: str) -> LLMCallLog | None:
        async with async_session_maker() as db:
            result = await db.execute(
                select(LLMCallLog).where(LLMCallLog.request_id == request_id)
            )
            return result.scalar_one_or_none()

    async def get_list(
        self, db: AsyncSession, filters: dict = None,
        page: int = 1, size: int = 20,
    ) -> dict:
        q = select(LLMCallLog)
        if filters:
            if filters.get("user_id"):
                q = q.where(LLMCallLog.user_id == filters["user_id"])
            if filters.get("provider_id"):
                q = q.where(LLMCallLog.provider_id == filters["provider_id"])
            if filters.get("model"):
                q = q.where(LLMCallLog.model == filters["model"])
            if filters.get("status"):
                q = q.where(LLMCallLog.status == filters["status"])
            if filters.get("start_date"):
                q = q.where(LLMCallLog.create_time >= filters["start_date"])
            if filters.get("end_date"):
                q = q.where(LLMCallLog.create_time <= filters["end_date"])
        q = q.order_by(LLMCallLog.create_time.desc())

        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        result = await db.execute(q.offset((page - 1) * size).limit(size))
        return {"list": result.scalars().all(), "total": total}

    async def get_statistics(self, db: AsyncSession, filters: dict = None) -> dict:
        q = select(
            func.count(LLMCallLog.id).label("total_calls"),
            func.sum(LLMCallLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(LLMCallLog.completion_tokens).label("total_completion_tokens"),
            func.sum(LLMCallLog.cost).label("total_cost"),
            func.avg(LLMCallLog.total_duration).label("avg_duration"),
        )
        if filters:
            if filters.get("start_date"):
                q = q.where(LLMCallLog.create_time >= filters["start_date"])
            if filters.get("end_date"):
                q = q.where(LLMCallLog.create_time <= filters["end_date"])
        result = await db.execute(q)
        row = result.one()
        return {
            "total_calls": row.total_calls or 0,
            "total_prompt_tokens": int(row.total_prompt_tokens or 0),
            "total_completion_tokens": int(row.total_completion_tokens or 0),
            "total_cost": float(row.total_cost or 0),
            "avg_duration": float(row.avg_duration or 0),
        }


call_log_service = CallLogService()
