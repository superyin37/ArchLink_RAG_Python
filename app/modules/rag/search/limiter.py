from app.modules.rag.config import RAGConfig


class ResultLimiter:
    @staticmethod
    def limit(
        chunks: list[dict],
        max_chunks: int = None,
        max_context_tokens: int = None,
    ) -> list[dict]:
        max_chunks = max_chunks or RAGConfig.LIMIT_MAX_CHUNKS
        max_context_tokens = max_context_tokens or RAGConfig.LIMIT_MAX_CONTEXT_TOKENS

        hit_chunks = [c for c in chunks if c.get("is_hit", True)]
        other_chunks = [c for c in chunks if not c.get("is_hit", True)]

        min_hits = min(len(hit_chunks), RAGConfig.LIMIT_MIN_HITS)
        min_graph = min(len(other_chunks), RAGConfig.LIMIT_MIN_GRAPH)

        # Calculate remaining budget after minimums
        remaining = max_chunks - min_hits - min_graph

        hit_budget = max(min_hits, min(len(hit_chunks), int(max_chunks * RAGConfig.LIMIT_HIT_RATIO)))
        graph_budget = max(min_graph, min(len(other_chunks), int(max_chunks * RAGConfig.LIMIT_GRAPH_RATIO)))

        result = hit_chunks[:hit_budget] + other_chunks[:graph_budget]

        # Apply token budget
        total_tokens = 0
        final = []
        for c in result:
            token_est = len(c.get("content", "")) // 4 or RAGConfig.LIMIT_AVG_CHUNK_TOKENS
            if total_tokens + token_est > max_context_tokens:
                break
            final.append(c)
            total_tokens += token_est

        return final
