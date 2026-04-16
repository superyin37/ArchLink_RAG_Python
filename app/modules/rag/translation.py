"""Query translation utility for cross-lingual RAG retrieval.

Strategy: translate non-Chinese queries to Simplified Chinese before vector/fulltext
search, so the knowledge base (stored in Chinese) can be searched effectively.
The LLM then reads Chinese chunks and responds in the user's language naturally.
"""
import logging

logger = logging.getLogger(__name__)

_TRANSLATE_PROMPT = (
    "Translate the following text to Simplified Chinese. "
    "Output ONLY the translation, no explanation, no punctuation changes.\n\n"
    "Text: {text}"
)


async def translate_to_zh(text: str, source_lang: str) -> str:
    """Translate *text* to Simplified Chinese when *source_lang* is not zh-CN.

    Returns the original text unchanged when:
    - source_lang is already "zh-CN"
    - TRANSLATION_MODEL is not configured
    - translation fails (safe fallback)
    """
    if source_lang == "zh-CN" or not text.strip():
        return text

    from app.config import settings
    model_str = getattr(settings, "TRANSLATION_MODEL", "")
    if not model_str:
        logger.debug("TRANSLATION_MODEL not set, skipping query translation")
        return text

    try:
        from app.modules.llm.completions.factory import LLMOne

        llm = LLMOne.from_config(model_str)
        parts: list[str] = []

        llm.on_content = lambda t: parts.append(t)
        llm.on_thinking = lambda _: None
        llm.on_thinking_complete = lambda: None

        prompt = _TRANSLATE_PROMPT.format(text=text)
        await llm.chat([{"role": "user", "content": prompt}])

        translated = "".join(parts).strip()
        if translated:
            logger.debug(f"Query translated [{source_lang}→zh-CN]: '{text}' → '{translated}'")
            return translated

    except Exception as e:
        logger.warning(f"Query translation failed, using original text: {e}")

    return text
