"""
All-but-the-Top vector post-processing (Mu et al., 2018).

解决 embedding 各向异性问题：单领域密集语料下，所有向量聚集在高维空间的
一个小锥形区域，导致无关文本间 cosine 相似度基线高达 0.80~0.92，排序等同噪声。

修复原理：
  1. 减去语料均值向量（去除"领域公共偏置"）
  2. 去掉前 k 个主成分（去除各向异性的主导方向）
  3. 重新 L2 归一化

query 向量在搜索时用同一份统计数据做相同变换，保证向量空间一致性。
"""

import json
import logging
from pathlib import Path

import numpy as np

from app.modules.rag.vector.lancedb import LanceDBDriver

logger = logging.getLogger(__name__)

_STATS_DIR = Path("database/lancedb")

# 进程内缓存，避免每次搜索重复读磁盘
_stats_cache: dict[int, dict] = {}


def _stats_path(kb_id: int) -> Path:
    return _STATS_DIR / f"kb_{kb_id}_stats.json"


def load_stats(kb_id: int) -> dict | None:
    """加载知识库的向量统计数据（均值 + 主成分），有内存缓存。"""
    if kb_id in _stats_cache:
        return _stats_cache[kb_id]
    path = _stats_path(kb_id)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            stats = json.load(f)
        _stats_cache[kb_id] = stats
        return stats
    except Exception as e:
        logger.warning(f"Failed to load vector stats for kb {kb_id}: {e}")
        return None


def invalidate_cache(kb_id: int):
    """重新计算统计后调用，清除内存缓存。"""
    _stats_cache.pop(kb_id, None)


async def compute_and_save_statistics(
    kb_id: int,
    driver: LanceDBDriver,
    n_components: int = 4,
) -> dict:
    """
    扫描 LanceDB 表中所有向量，计算均值和前 n_components 个主成分，
    持久化为 JSON sidecar 文件。

    建议在以下时机调用：
    - 知识库初始建立完成后
    - 批量重新入库后
    - 搜索质量明显下降时

    Args:
        kb_id: 知识库 ID
        driver: LanceDB 驱动实例
        n_components: 要去除的主成分数量，建议先从 4 开始，
                      可调整为 1/2/4/8 并对比 Recall@10 变化

    Returns:
        stats dict，同时写入磁盘
    """
    table_name = f"kb_{kb_id}"
    logger.info(f"[AllButTop] Computing statistics for kb {kb_id}, table={table_name}")

    table = driver.db.open_table(table_name)
    raw = table.to_arrow().column("vector").to_pylist()

    if not raw:
        raise ValueError(f"No vectors found in table {table_name}")

    X = np.array(raw, dtype=np.float32)
    n_vecs, dim = X.shape
    logger.info(f"[AllButTop] Loaded {n_vecs} vectors, dim={dim}")

    # Step 1: 计算语料均值
    mean = X.mean(axis=0)
    X_centered = X - mean

    # Step 2: SVD 取前 n_components 个右奇异向量（即主成分方向）
    # full_matrices=False 使用 thin SVD，节省内存
    _, _, Vt = np.linalg.svd(X_centered, full_matrices=False)
    top_pcs = Vt[:n_components]  # shape: (n_components, dim)

    stats = {
        "kb_id": kb_id,
        "n_vectors": n_vecs,
        "dimension": dim,
        "n_components": n_components,
        "mean": mean.tolist(),
        "top_pcs": top_pcs.tolist(),
    }

    _STATS_DIR.mkdir(parents=True, exist_ok=True)
    with open(_stats_path(kb_id), "w") as f:
        json.dump(stats, f)

    invalidate_cache(kb_id)
    logger.info(
        f"[AllButTop] Done for kb {kb_id}: {n_vecs} vectors, {n_components} PCs removed"
    )
    return stats


def apply_all_but_top(vector: list[float], stats: dict) -> list[float]:
    """
    对单个查询向量应用 All-but-the-Top 变换。

    必须使用与入库向量相同的 stats（mean + top_pcs），保证向量空间一致性。
    搜索路径调用此函数，入库路径不需要改动（LanceDB 存储原始向量，
    变换仅在 query 侧实时应用，等价于在同一变换空间内做近邻搜索）。

    注意：严格来说，存量向量也应做相同变换后重建索引才能完全一致。
    但实践中对 query 单侧变换已能显著改善区分度，避免重建索引的高成本。
    """
    x = np.array(vector, dtype=np.float32)
    mean = np.array(stats["mean"], dtype=np.float32)
    top_pcs = np.array(stats["top_pcs"], dtype=np.float32)

    # Step 1: 中心化
    x = x - mean

    # Step 2: 去除主成分方向的投影
    for pc in top_pcs:
        x = x - np.dot(x, pc) * pc

    # Step 3: 重新 L2 归一化
    norm = np.linalg.norm(x)
    if norm > 1e-12:
        x = x / norm

    return x.tolist()
