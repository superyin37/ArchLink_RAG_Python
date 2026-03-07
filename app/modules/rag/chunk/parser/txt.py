import re
from app.modules.rag.chunk.parser.base import TreeNode, NodeType, create_root, create_node


def parse_txt(content: str) -> TreeNode:
    """Parse plain text by splitting on double newlines."""
    root = create_root()
    paragraphs = re.split(r"\n\s*\n", content)
    for para in paragraphs:
        para = para.strip()
        if para:
            node = create_node(NodeType.PARAGRAPH, level=0, content=para)
            node.parent = root
            root.children.append(node)
    return root
