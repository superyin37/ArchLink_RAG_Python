from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from app.modules.rag.chunk.utils import generate_node_id


class NodeType(str, Enum):
    ROOT = "root"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"


@dataclass
class TreeNode:
    id: str
    type: NodeType
    level: int
    heading: str = ""
    content: str = ""
    children: list = field(default_factory=list)
    parent: Optional["TreeNode"] = None


def create_node(
    node_type: NodeType,
    level: int,
    heading: str = "",
    content: str = "",
) -> TreeNode:
    return TreeNode(
        id=generate_node_id(),
        type=node_type,
        level=level,
        heading=heading,
        content=content,
    )


def create_root() -> TreeNode:
    return TreeNode(id=generate_node_id(), type=NodeType.ROOT, level=-1)


def find_parent_for_level(current_node: TreeNode, level: int) -> TreeNode:
    """Walk up the tree to find the appropriate parent for a heading of given level."""
    node = current_node
    while node.parent is not None and node.level >= level:
        node = node.parent
    return node
