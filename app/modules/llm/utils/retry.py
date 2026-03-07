"""Retry with exponential backoff and fallback routing."""
import asyncio
import logging
import random
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def with_retry_backoff(
    fn: Callable,
    retries: int = 3,
    base_delay: float = 0.5,
    factor: float = 2.0,
    jitter: bool = True,
    retry_condition: Optional[Callable[[Exception], bool]] = None,
):
    """Wrap async function with exponential backoff retry."""
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
                logger.warning(
                    f"Attempt {attempt + 1}/{retries} failed: {e}. Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

    return wrapper


def with_fallback_router(
    fn: Callable,
    fallbacks: list,
    get_fn_for_model: Optional[Callable] = None,
    on_fallback: Optional[Callable] = None,
):
    """Try primary function, then fallback models on failure."""
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as primary_error:
            logger.warning(f"Primary model failed: {primary_error}")
            for fb in fallbacks:
                try:
                    if on_fallback:
                        on_fallback(fb)
                    if get_fn_for_model:
                        fallback_fn = get_fn_for_model(fb)
                        return await fallback_fn(*args, **kwargs)
                except Exception as fb_error:
                    logger.warning(f"Fallback {fb} failed: {fb_error}")
                    continue
            raise primary_error

    return wrapper
