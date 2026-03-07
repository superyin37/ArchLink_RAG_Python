class ThresholdAdapter:
    @staticmethod
    def adapt(results: list[dict], percentile: float = 0.5) -> float:
        """Dynamically adapt threshold based on score distribution."""
        if not results:
            return 0.3

        scores = sorted([r.get("score", 0) for r in results], reverse=True)
        idx = min(int(len(scores) * percentile), len(scores) - 1)
        median_score = scores[idx]

        # Use 60% of median as new threshold (but not below 0.1)
        return max(0.1, median_score * 0.6)
