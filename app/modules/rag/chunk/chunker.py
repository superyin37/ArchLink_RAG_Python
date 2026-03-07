from app.modules.rag.chunk.parser.base import TreeNode, NodeType
from app.modules.rag.chunk.utils import generate_node_id, build_path, split_by_size


def tree_to_chunks(tree: TreeNode, doc_id: int, kb_id: int, max_size: int = 500) -> list[dict]:
    """Convert tree to flat chunk list with metadata (DFS traversal)."""
    chunks = []
    chunk_index = 0

    def traverse(node: TreeNode, parent_path: str = "", parent_id: str = None, seq: int = 0):
        nonlocal chunk_index

        if node.type == NodeType.ROOT:
            for i, child in enumerate(node.children):
                traverse(child, "", node.id, i)
            return

        path = build_path(parent_path, seq)

        if node.content:
            parts = split_by_size(node.content, max_size)
            for i, part in enumerate(parts):
                chunks.append(
                    {
                        "doc_id": doc_id,
                        "kb_id": kb_id,
                        "node_id": node.id if i == 0 else generate_node_id(),
                        "parent_id": parent_id,
                        "level": node.level,
                        "path": path,
                        "heading": node.heading,
                        "content": part,
                        "chunk_index": chunk_index,
                        "seq": seq,
                        "char_count": len(part),
                    }
                )
                chunk_index += 1

        for i, child in enumerate(node.children):
            traverse(child, path, node.id, i)

    for i, child in enumerate(tree.children):
        traverse(child, "", tree.id, i)

    return chunks
