import re


class KeywordExtractor:
    # Words to remove from keyword extraction
    STOP_WORDS_ZH = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
                     "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
                     "看", "好", "自己", "这", "那", "里", "怎么", "什么", "如何", "为什么"}
    STOP_WORDS_EN = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "have", "has", "do", "does", "did", "will", "would", "can",
                     "could", "should", "may", "might", "and", "or", "but", "if",
                     "in", "on", "at", "to", "for", "of", "with", "by", "from"}

    @classmethod
    def extract(cls, text: str, max_keywords: int = 10) -> list[str]:
        """Extract significant keywords from query text."""
        # Extract Chinese and English tokens
        zh_tokens = re.findall(r"[\u4e00-\u9fff]+", text)
        en_tokens = re.findall(r"[a-zA-Z]+", text)

        keywords = []

        # Filter Chinese tokens
        for token in zh_tokens:
            if len(token) >= 2 and token not in cls.STOP_WORDS_ZH:
                keywords.append(token)

        # Filter English tokens
        for token in en_tokens:
            t = token.lower()
            if len(t) >= 3 and t not in cls.STOP_WORDS_EN:
                keywords.append(t)

        # Deduplicate while preserving order
        seen = set()
        result = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                result.append(k)

        return result[:max_keywords]
