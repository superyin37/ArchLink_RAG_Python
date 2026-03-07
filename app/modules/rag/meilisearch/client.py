import logging
from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_meilisearch_client():
    global _client
    if _client is None and settings.MEILISEARCH_ENABLED:
        try:
            import meilisearch
            _client = meilisearch.Client(
                settings.MEILISEARCH_HOST,
                settings.MEILISEARCH_API_KEY,
            )
        except Exception as e:
            logger.warning(f"Meilisearch unavailable: {e}")
            _client = None
    return _client
