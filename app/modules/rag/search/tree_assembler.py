from app.modules.rag.config import RAGConfig


class TreeAssembler:
    @staticmethod
    def assemble_context(chunks: list[dict], separator: str = None) -> str:
        """Assemble chunks into formatted context text."""
        separator = separator or RAGConfig.CONTEXT_SEPARATOR

        parts = []
        hit_chunks = [c for c in chunks if c.get("is_hit", True)]
        expanded_chunks = [c for c in chunks if not c.get("is_hit", True)]

        for chunk in hit_chunks:
            heading = chunk.get("heading")
            content = chunk.get("content", "")
            if heading and RAGConfig.CONTEXT_INCLUDE_HEADING:
                parts.append(f"### {heading}\n{content}")
            else:
                parts.append(content)

        for chunk in expanded_chunks:
            content = chunk.get("content", "")
            parts.append(content)

        return separator.join(parts)
