import re


def evaluate_readability(text: str) -> dict:
    """Evaluate chunk content quality and readability."""
    normalized = re.sub(r"!\[.*?\]\(.*?\)", "", text).strip()

    if len(text) < 40:
        return {"is_readable": False, "noise_tag": "NOISE_TOO_SHORT", "readability_score": 0}
    if len(normalized) < 12:
        return {"is_readable": False, "noise_tag": "LOW_TEXT_DENSITY", "readability_score": 0}

    chinese_ratio = len(re.findall(r"[\u4e00-\u9fff]", normalized)) / max(len(normalized), 1)
    alpha_ratio = len(re.findall(r"[a-zA-Z0-9]", normalized)) / max(len(normalized), 1)

    # Filter: primarily English chunks (< 10% Chinese, > 60% ASCII alphanumeric)
    # 纯英文块（如文档英文标题）在建筑规范单领域语料中会成为向量空间 hub，
    # 对所有中文查询稳定高分，必须在入库前过滤。
    if chinese_ratio < 0.1 and alpha_ratio > 0.6:
        return {"is_readable": False, "noise_tag": "PRIMARILY_ENGLISH", "readability_score": 0}

    # Filter: title-only chunks（无句尾标点 + 行数 <= 2 + 长度 < 80）
    # 孤立标题行没有实质内容，向量化后语义模糊，易成为噪声。
    has_sentence_end = bool(re.search(r"[。？！…；]", normalized))
    line_count = len([l for l in normalized.splitlines() if l.strip()])
    if not has_sentence_end and line_count <= 2 and len(normalized) < 80:
        return {"is_readable": False, "noise_tag": "TITLE_ONLY", "readability_score": 0}

    base_score = min(1.0, len(normalized) / 120)
    # alpha_ratio 贡献上限 0.3，防止英文内容拉高 signal_score（已有 PRIMARILY_ENGLISH 兜底）
    signal_score = min(1.0, (chinese_ratio + min(alpha_ratio, 0.3)) / 0.6)
    symbol_ratio = len(re.findall(r"[^\w\s]", normalized)) / max(len(normalized), 1)
    symbol_penalty = max(0.0, (symbol_ratio - 0.35) * 1.2)

    score = max(0.0, min(1.0, 0.55 * base_score + 0.45 * signal_score - symbol_penalty))
    is_readable = score >= 0.45

    return {
        "is_readable": is_readable,
        "readability_score": round(score, 4),
        "noise_tag": None if is_readable else "LOW_READABILITY",
    }
