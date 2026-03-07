import httpx
import logging

logger = logging.getLogger(__name__)


class DoubaoEmbedding:
    def __init__(self, host: str, api_key: str, model_id: str, batch_size: int = 16):
        self.host = host.rstrip("/")
        self.api_key = api_key
        self.model_id = model_id
        self.batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                response = await client.post(
                    f"{self.host}/api/v3/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_id,
                        "input": batch,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                data = response.json()["data"]
                embeddings = [
                    item["embedding"]
                    for item in sorted(data, key=lambda x: x["index"])
                ]
                all_embeddings.extend(embeddings)

        return all_embeddings
