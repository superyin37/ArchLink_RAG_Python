import io
from app.modules.rag.chunk.parser.base import (
    TreeNode, NodeType, create_root, create_node, find_parent_for_level
)


def parse_docx(file_path: str) -> TreeNode:
    """Parse DOCX using python-docx, build heading-paragraph tree."""
    try:
        import docx
    except ImportError:
        raise ImportError("python-docx is required for DOCX parsing")

    doc = docx.Document(file_path)
    root = create_root()
    current_node: TreeNode = root

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""

        # Detect heading style
        heading_match = None
        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1]) - 1  # "Heading 1" -> 0
                heading_match = level
            except (ValueError, IndexError):
                pass

        if heading_match is not None:
            level = heading_match
            node = create_node(NodeType.HEADING, level=level, heading=text)
            parent = find_parent_for_level(current_node, level)
            node.parent = parent
            parent.children.append(node)
            current_node = node
        else:
            # Regular paragraph - append to current heading
            if current_node.content:
                current_node.content += "\n\n"
            current_node.content += text

    return root
