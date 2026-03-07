from app.modules.rag.embedding.doubao import DoubaoEmbedding
from app.modules.rag.embedding.qwen import QwenEmbedding
from app.config import settings
from app.exceptions import EmbeddingError
import logging

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = {
    "doubao": {"dimension": 2048},
    "openai": {"dimension": 1536},
    "qwen": {"dimension": 1024},
}


class EmbeddingService:
    async def embed(
        self,
        texts: list[str] | str,
        model_type: str = "doubao",
        config: dict = None,
    ) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]

        config = config or {}

        try:
            if model_type == "doubao":
                client = DoubaoEmbedding(
                    host=config.get("host") or settings.DOUBAO_HOST,
                    api_key=config.get("api_key") or settings.DOUBAO_API_KEY,
                    model_id=config.get("model_id") or settings.DOUBAO_EMBEDDING_MODEL,
                    batch_size=settings.DOUBAO_EMBEDDING_BATCH_SIZE,
                )
                return await client.embed(texts)
            elif model_type == "qwen":
                client = QwenEmbedding(
                    api_key=config.get("api_key") or settings.QWEN_API_KEY,
                    model_id=config.get("model_id") or settings.QWEN_EMBEDDING_MODEL,
                    dimension=config.get("dimension") or SUPPORTED_MODELS["qwen"]["dimension"],
                )
                return await client.embed(texts)
            else:
                raise EmbeddingError(f"Unsupported embedding model type: {model_type}")
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}") from e

    def get_dimension(self, model_type: str) -> int:
        return SUPPORTED_MODELS.get(model_type, {}).get("dimension", 2048)


embedding_service = EmbeddingService()
