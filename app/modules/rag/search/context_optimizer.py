from app.modules.rag.config import RAGConfig


class ContextOptimizer:
    @staticmethod
    def optimize(
        chunks: list[dict],
        max_length: int = None,
        max_chunk_length: int = None,
    ) -> list[dict]:
        """Truncate individual chunks if needed to fit context budget."""
        max_length = max_length or RAGConfig.CONTEXT_MAX_LENGTH
        max_chunk_length = max_chunk_length or RAGConfig.CONTEXT_MAX_CHUNK_LENGTH

        result = []
        total = 0
        for chunk in chunks:
            content = chunk["content"]
            if len(content) > max_chunk_length:
                content = content[:max_chunk_length] + "..."
            if total + len(content) > max_length:
                break
            result.append({**chunk, "content": content})
            total += len(content)

        return result
