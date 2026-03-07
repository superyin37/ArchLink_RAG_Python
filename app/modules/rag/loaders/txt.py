from pathlib import Path


async def load_txt(file_path: str) -> str:
    """Load plain text or markdown file."""
    content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    return content
