# Issues

本目录记录 RAG 系统已发现的问题、根因分析和解决方案。

| # | 问题 | 严重程度 | 状态 | 发现时间 | 修复时间 |
|---|------|---------|------|---------|---------|
| [001](./001-vector-search-anisotropy.md) | 向量搜索召回完全失效（Embedding 各向异性） | 高 | ✅ 已修复 | 2026-03-06 | 2026-03-07 |

## 修复摘要

### Issue #001

**根因**：`doubao-embedding-large-text-250515` 在建筑规范单领域语料上各向异性严重，所有向量聚集在高维空间同一方向，cosine 相似度基线高达 0.87~0.92，正确与错误 chunk 无法区分。

**尝试方案**：All-but-the-Top（去均值 + 去前4主成分），可压缩噪声幅度但无法建立有效语义区分度（向量 TOP5 命中率仅从 0% 提升至 4%）。

**最终方案**：切换至 **Qwen text-embedding-v4**（DashScope，1024维），全量重建知识库（KB 5）。向量 TOP5 命中率达 **96%**，Hybrid TOP1 准确率 **100%**，无需任何后处理。

详见 [001-vector-search-anisotropy.md](./001-vector-search-anisotropy.md) 和 [RAG_EMBEDDING_COMPARE_RESULT.md](../RAG_EMBEDDING_COMPARE_RESULT.md)。
