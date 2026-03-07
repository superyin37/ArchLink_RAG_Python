from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ExpandStrategy(str, Enum):
    CHILDREN = "children"
    SIBLINGS = "siblings"
    ANCESTORS = "ancestors"


async def enhance_retrieve(
    base_chunks: list[dict],
    all_chunks_by_node_id: dict[str, dict],
    all_chunks_by_path: dict[str, list[dict]],
    strategies: list[str] = None,
    max_depth: int = 1,
    min_sibling_level: int = 2,
) -> list[dict]:
    """Expand base chunks with tree-based retrieval strategies."""
    strategies = strategies or [ExpandStrategy.CHILDREN]
    expanded = []
    seen_ids = {c["id"] for c in base_chunks}

    for chunk in base_chunks:
        chunk["is_hit"] = True

    for chunk in base_chunks:
        path = chunk.get("path", "")
        level = chunk.get("level", 0)
        node_id = chunk.get("node_id", "")
        parent_id = chunk.get("parent_id", "")

        if ExpandStrategy.SIBLINGS in strategies and level >= min_sibling_level:
            # Find siblings by parent_id
            for candidate in all_chunks_by_node_id.values():
                if (
                    candidate.get("parent_id") == parent_id
                    and candidate["id"] not in seen_ids
                    and candidate.get("parent_id")  # ensure has parent (not root children)
                ):
                    expanded.append({**candidate, "is_hit": False})
                    seen_ids.add(candidate["id"])

        if ExpandStrategy.CHILDREN in strategies:
            # Find children by parent_id = current node_id
            for candidate in all_chunks_by_node_id.values():
                if (
                    candidate.get("parent_id") == node_id
                    and candidate["id"] not in seen_ids
                ):
                    expanded.append({**candidate, "is_hit": False})
                    seen_ids.add(candidate["id"])

        if ExpandStrategy.ANCESTORS in strategies:
            # Find ancestors via path
            path_parts = path.split("/") if path else []
            for depth in range(1, min(max_depth + 1, len(path_parts))):
                ancestor_path = "/".join(path_parts[:-depth])
                if ancestor_path in all_chunks_by_path:
                    for candidate in all_chunks_by_path[ancestor_path]:
                        if candidate["id"] not in seen_ids:
                            expanded.append({**candidate, "is_hit": False})
                            seen_ids.add(candidate["id"])

    return base_chunks + expanded
