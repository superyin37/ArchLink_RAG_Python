import re
from app.modules.rag.chunk.parser.base import (
    TreeNode, NodeType, create_root, create_node, find_parent_for_level
)


def parse_markdown_optimized(content: str) -> TreeNode:
    """
    Parse markdown using heading hierarchy.
    Paragraphs are APPENDED to their parent heading content (not child nodes).
    """
    root = create_root()
    current_node: TreeNode = root
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Heading detection
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            hashes = heading_match.group(1)
            heading_text = heading_match.group(2).strip()
            level = len(hashes) - 1  # h1=0, h2=1, ...

            node = create_node(NodeType.HEADING, level, heading=heading_text)
            parent = find_parent_for_level(current_node, level)
            node.parent = parent
            parent.children.append(node)
            current_node = node
            i += 1
            continue

        # Code block
        if line.startswith("```"):
            code_lines = [line]
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            if current_node.content:
                current_node.content += "\n\n"
            current_node.content += code_content
            continue

        # Table detection
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|", lines[i + 1]):
            table_lines = [line]
            i += 1
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            table_content = "\n".join(table_lines)
            if current_node.content:
                current_node.content += "\n\n"
            current_node.content += table_content
            continue

        # Empty line - paragraph separator
        if not line.strip():
            i += 1
            continue

        # Regular paragraph (including list items)
        paragraph_lines = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^#{1,6}\s", lines[i]):
            if lines[i].startswith("```"):
                break
            paragraph_lines.append(lines[i])
            i += 1

        paragraph = "\n".join(paragraph_lines).strip()
        if paragraph:
            if current_node.content:
                current_node.content += "\n\n"
            current_node.content += paragraph

    return root
