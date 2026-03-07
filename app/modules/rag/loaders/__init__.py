from app.modules.rag.loaders.txt import load_txt
from app.modules.rag.loaders.pdf import load_pdf
from app.modules.rag.loaders.docx import load_docx_text
from app.modules.rag.loaders.xlsx import load_xlsx

__all__ = ["load_txt", "load_pdf", "load_docx_text", "load_xlsx"]
