import httpx
import logging

logger = logging.getLogger(__name__)

DASHSCOPE_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"


class QwenEmbedding:
    def __init__(self, api_key: str, model_id: str = "text-embedding-v4", batch_size: int = 10, dimension: int = 1024):
        self.api_key = api_key
        self.model_id = model_id
        self.batch_size = batch_size
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                response = await client.post(
                    DASHSCOPE_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_id,
                        "input": batch,
                        "encoding_format": "float",
                        "dimension": self.dimension,
                    },
                )
                if response.status_code != 200:
                    logger.error(f"DashScope API error {response.status_code}: {response.text[:500]}")
                response.raise_for_status()
                data = response.json()["data"]
                embeddings = [
                    item["embedding"]
                    for item in sorted(data, key=lambda x: x["index"])
                ]
                all_embeddings.extend(embeddings)

        return all_embeddings
