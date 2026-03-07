class ResultDeduplicator:
    @staticmethod
    def deduplicate(chunks: list[dict], enable_content: bool = True, enable_parent_child: bool = True) -> list[dict]:
        """Three-layer deduplication: ID -> content similarity -> parent-child."""
        # 1. ID dedup
        seen_ids: set[int] = set()
        unique = []
        for c in chunks:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique.append(c)

        # 2. Content similarity dedup (Jaccard)
        if enable_content:
            filtered = []
            for c in unique:
                is_dup = False
                c_tokens = set(c["content"].split())
                for existing in filtered:
                    e_tokens = set(existing["content"].split())
                    if not c_tokens and not e_tokens:
                        continue
                    intersection = len(c_tokens & e_tokens)
                    union = len(c_tokens | e_tokens)
                    if union > 0 and intersection / union >= 0.85:
                        is_dup = True
                        break
                if not is_dup:
                    filtered.append(c)
            unique = filtered

        # 3. Parent-child filter: remove children whose parent is in results
        if enable_parent_child:
            node_ids_in_results = {c.get("node_id") for c in unique if c.get("node_id")}
            unique = [
                c for c in unique
                if not (c.get("parent_id") and c["parent_id"] in node_ids_in_results)
            ]

        return unique
