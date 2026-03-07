async def load_docx_text(file_path: str) -> str:
    """Extract plain text from DOCX file."""
    try:
        import docx
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise ImportError("python-docx is required for DOCX loading")
