"""
Qwen text-embedding-v4 vs Doubao embedding 各向同性对比测试

用法：
    cd rag-python
    python scripts/test_qwen_embedding.py

需要 .env 中设置：
    QWEN_API_KEY=sk-xxxx
    DOUBAO_API_KEY=xxxx  (可选，用于对比)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from dotenv import load_dotenv

load_dotenv()

from app.modules.rag.embedding.qwen import QwenEmbedding
from app.config import settings

# issue #001 中的 5 个测试查询
QUERIES = [
    "地下工程防水等级划分",
    "防灾避难场所责任区面积",
    "锅炉房防火间距",
    "饮食建筑厨房面积比例",
    "铁路候车室设计要求",
]

# 10 个混合文本（建筑规范内 + 跨域），用于 pairwise 统计
SAMPLE_TEXTS = [
    "地下工程防水等级一级不允许渗水",
    "锅炉房与建筑物的防火间距要求",
    "具体目标到2010年节能50%",
    "Technical requirements of panel used for assembled buildings",
    "防灾避难场所的责任区面积不应大于50公顷",
    "饮食建筑厨房与餐厅的面积比例应符合规定",
    "铁路旅客车站候车室的设计应满足旅客使用需求",
    "居住区绿化率不应低于30%",
    "The quick brown fox jumps over the lazy dog",
    "消防通道宽度不应小于4米",
]


def cosine_sim(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def run_anisotropy_test(client, model_name: str):
    print(f"\n{'='*60}")
    print(f"模型: {model_name}")
    print(f"{'='*60}")

    vecs = await client.embed(SAMPLE_TEXTS)
    print(f"向量维度: {len(vecs[0])}")

    # pairwise 统计
    sims = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            sims.append(cosine_sim(vecs[i], vecs[j]))

    sims = np.array(sims)
    print(f"\n[Pairwise 统计] 共 {len(sims)} 对")
    print(f"  max={sims.max():.4f}  min={sims.min():.4f}  avg={sims.mean():.4f}")
    print(f"  > 0.90: {(sims > 0.90).sum()} 对")
    print(f"  > 0.85: {(sims > 0.85).sum()} 对")
    print(f"  > 0.80: {(sims > 0.80).sum()} 对")
    print(f"  < 0.70: {(sims < 0.70).sum()} 对")
    print(f"  < 0.50: {(sims < 0.50).sum()} 对")

    # query vs sample 分辨率测试
    print(f"\n[Query 分辨率测试]")
    query_vecs = await client.embed(QUERIES[:3])

    related_pairs = [
        (0, 0),  # 防水查询 vs 防水文本
        (1, 4),  # 防灾查询 vs 防灾文本
        (2, 1),  # 锅炉查询 vs 锅炉文本
    ]
    unrelated_idx = 3  # 英文装配式墙板

    for qi, si in related_pairs:
        rel_sim = cosine_sim(query_vecs[qi], vecs[si])
        unrel_sim = cosine_sim(query_vecs[qi], vecs[unrelated_idx])
        margin = rel_sim - unrel_sim
        print(f"  Q: '{QUERIES[qi][:12]}...'  相关={rel_sim:.4f}  无关(英文)={unrel_sim:.4f}  裕量={margin:+.4f}")


async def main():
    if not settings.QWEN_API_KEY:
        print("错误: 请在 .env 中设置 QWEN_API_KEY")
        sys.exit(1)

    qwen = QwenEmbedding(
        api_key=settings.QWEN_API_KEY,
        model_id=settings.QWEN_EMBEDDING_MODEL,
    )
    await run_anisotropy_test(qwen, f"Qwen {settings.QWEN_EMBEDDING_MODEL} (1024维)")

    if settings.DOUBAO_API_KEY and settings.DOUBAO_EMBEDDING_MODEL:
        from app.modules.rag.embedding.doubao import DoubaoEmbedding
        doubao = DoubaoEmbedding(
            host=settings.DOUBAO_HOST,
            api_key=settings.DOUBAO_API_KEY,
            model_id=settings.DOUBAO_EMBEDDING_MODEL,
        )
        await run_anisotropy_test(doubao, f"Doubao {settings.DOUBAO_EMBEDDING_MODEL} (2048维)")


if __name__ == "__main__":
    asyncio.run(main())
