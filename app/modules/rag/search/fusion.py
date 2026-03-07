class SearchFusion:
    @staticmethod
    def fuse_rrf(result_sets: list[list[dict]], top_k: int = 10, k: int = 60) -> list[dict]:
        """Reciprocal Rank Fusion across multiple result sets."""
        scores: dict[int, float] = {}
        items: dict[int, dict] = {}

        for result_set in result_sets:
            for rank, item in enumerate(result_set):
                chunk_id = item["id"]
                rrf_score = 1.0 / (k + rank + 1)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_score
                if chunk_id not in items:
                    items[chunk_id] = {**item}
                else:
                    sources = items[chunk_id].get("fused_from", [item.get("source")])
                    sources.append(item.get("source"))
                    items[chunk_id]["fused_from"] = sources

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [{**items[cid], "score": scores[cid]} for cid in sorted_ids]

    @staticmethod
    def fuse_weighted(
        vector_results: list[dict],
        fulltext_results: list[dict],
        vector_weight: float = 0.7,
        fulltext_weight: float = 0.3,
        top_k: int = 10,
    ) -> list[dict]:
        """Weighted score fusion."""
        scores: dict[int, float] = {}
        items: dict[int, dict] = {}

        for item in vector_results:
            cid = item["id"]
            scores[cid] = scores.get(cid, 0.0) + item.get("score", 0.0) * vector_weight
            items[cid] = item

        for item in fulltext_results:
            cid = item["id"]
            scores[cid] = scores.get(cid, 0.0) + item.get("score", 0.0) * fulltext_weight
            if cid not in items:
                items[cid] = item

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [{**items[cid], "score": scores[cid]} for cid in sorted_ids]
