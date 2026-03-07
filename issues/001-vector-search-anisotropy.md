# Issue #001: 向量搜索召回完全失效（Embedding 各向异性问题）

**状态**: ✅ 已修复（切换 Embedding 模型）
**严重程度**: 高
**发现时间**: 2026-03-06
**修复时间**: 2026-03-07
**发现方式**: RAG 检索能力测试（5题全部向量搜索未命中）
**修复验证**: RAG_EMBEDDING_COMPARE_RESULT.md（对比实验，5题向量命中率 4%→96%）

---

## 现象

对建筑规范库（KB 3，427文档，37,822 chunks）执行向量搜索时，5个不同主题的查询均返回完全无关的文档：

| 查询 | 期望命中 | 实际 TOP1 | TOP1 score |
|------|---------|----------|-----------|
| 地下工程防水等级划分 | doc_id=193（地下防水规范） | doc_id=400（装配式墙板） | 0.9048 |
| 防灾避难场所责任区面积 | doc_id=426（防灾避难场所） | doc_id=126（居住区风面积比） | 0.8837 |
| 锅炉房防火间距 | doc_id=424（锅炉房设计标准） | doc_id=400（装配式墙板） | 0.8947 |
| 饮食建筑厨房面积比例 | doc_id=429（饮食建筑设计标准） | doc_id=10（节能政策文件） | 0.9059 |
| 铁路候车室设计要求 | doc_id=420/421（铁路旅客车站） | doc_id=400（装配式墙板） | 0.8936 |

**doc_id=400**（chunk 内容：`"Technical requirements of panel used for assembled buildings"`）出现在5题中4题的向量搜索 TOP1，且 score 均高达 0.89+。

---

## 根因分析

### 诊断实验

**实验1：相关 vs 不相关文本的相似度对比**

以"地下工程防水等级划分标准"为查询，测量各文本的 cosine 相似度：

```
地下工程防水等级一级不允许渗水  →  0.9282  （高度相关）
锅炉房与建筑物的防火间距要求    →  0.8930  （不相关）
具体目标到2010年节能50%       →  0.8792  （完全不相关）
装配式建筑墙板技术要求         →  0.8205  （完全不相关）

有效分辨间距：仅约 0.06~0.10
```

**实验2：10个文本 Pairwise 统计（含中英文、建筑/非建筑混合）**

```
样本: 10文本 → 45对
cosine 相似度统计:
  max=0.9006  min=0.3916  avg=0.6698
  > 0.90: 1对（无关文本对！）
  > 0.85: 4对
  > 0.80: 7对
  < 0.70: 24对
```

同领域（建筑规范）文本间的 pairwise 相似度集中在 **0.80~0.92**，而不同领域差异才较大（0.40~0.70）。

**实验3：doc_id=400 英文标题 vs 各中文查询**

```
"Technical requirements of panel used for assembled buildings"

vs Q1防水查询:    0.8658
vs Q2防灾查询:    0.8780
vs Q3锅炉查询:    0.8603
vs 防水相关chunk: 0.8675
```

该英文标题与任意中文建筑查询的相似度稳定在 **0.86~0.88**，是建筑领域 embedding 空间的"质心"附近点，对所有查询均高分——这解释了它为何总排 TOP1。

### L2 归一化排查（2026-03-06）

火山方舟官方文档对 `doubao-embedding-large-text-250515` 明确要求 L2 归一化后使用。已排查代码：

- **入库路径**（`indexing.py`）：`embedding_service.embed()` 返回的原始向量直接存入 LanceDB，**无归一化**
- **检索路径**（`search/providers.py`）：query embedding 直接传入搜索，**无归一化**
- **结论**：两侧均未做 L2 normalize，但 LanceDB 使用 `.metric("cosine")` 在内部计算时等价于 `dot(A,B)/(|A|·|B|)`，数学上与预先归一化后做点积等价，**不是本次失效的根因**

### 技术根因

`doubao-embedding-large-text-250515`（2048维）在专业单领域语料（建筑规范）上表现出严重的**各向异性（Anisotropy）**：

所有建筑规范文本的 embedding 向量紧密聚集在高维空间的一个小锥形区域，导致：

```
同领域无关文本对的 cosine 相似度基线: 0.80 ~ 0.92
相关文本比无关文本高出的裕量:         0.05 ~ 0.08

→ 37,822 chunks 中，大量无关 chunk 随机超越正确 chunk
→ 向量排序等同于噪声
```

这是大型 Transformer 语言模型 embedding 的已知特性（BEIR、SimCSE 等论文均有记录），在：
1. **单领域密集语料**（全部是建筑规范）
2. **语体高度相同**（大量"应"、"不应"、"宜"等术语）
3. **专业术语密集**

三条件叠加时尤为严重。

### 影响范围

- 向量搜索（`/api/rag/search`）：**完全失效**
- 混合搜索（hybrid RRF）：被向量噪声污染，质量降级
- 高级搜索 context：噪声 chunk 被上下文拓展进一步放大
- 全文搜索（Meilisearch）：**不受影响，工作正常**

---

## 修复过程

### 阶段一：All-but-the-Top 缓解（2026-03-06，KB 3）

参考 BEIR benchmark 方法，对 Doubao 向量做去均值 + 去前 k 主成分 + 重新归一化。实现文件：

- `app/modules/rag/vector/mean_vector.py`
- `database/lancedb/kb_3_stats.json`（35,083 向量 × 2048维，n_components=4）

**效果**（见 RAG_TEST_REPORT_v2.md）：

```
向量背景相似度: 0.87~0.92 → 0.30~0.32（压低约 0.57）
向量 TOP5 正确命中: 0/25 → 1/25（仅 Q5×1条过阈值）
Hybrid TOP1 准确率: 2/5 → 3/5
```

**评估**：噪声幅度大幅压缩（doc_id=400 从 0.8947 降至 0.3095），但正确与错误 chunk 的分数差（Score Spread）仍接近零，向量搜索实用性依然极差。All-but-the-Top **必要但不充分**，无法从根本解决各向异性问题。

### 阶段二：切换 Embedding 模型（2026-03-07，KB 5）

将 Embedding 模型从 Doubao 切换为 **Qwen text-embedding-v4**（DashScope API，1024维），全量重建知识库。

**KB 5 配置**：

| 参数 | 值 |
|------|---|
| Embedding 模型 | text-embedding-v4（阿里云 DashScope） |
| 向量维度 | 1024 |
| 文档数 | 428 |
| Chunk 数 | 37,541 |
| batch_size | 10（Qwen 接口限制） |
| 并发 | 1（避免触发 RPM 限制） |
| All-but-the-Top | 未启用（不需要） |

**效果**（见 RAG_EMBEDDING_COMPARE_RESULT.md，threshold=0.0，top_k=5）：

| 指标 | Doubao + AbTT（KB 3） | Qwen（KB 5） |
|------|----------------------|-------------|
| 向量 TOP5 正确命中（满分25） | **1/25 (4%)** | **24/25 (96%)** |
| Hybrid TOP1 准确率（满分5） | **3/5 (60%)** | **5/5 (100%)** |
| 正确 chunk 平均分数 | 0.30~0.31（AbTT 后） | **0.74~0.85** |
| 是否需要后处理 | 必须 | **不需要** |
| 向量分数区分度（Score Spread） | ≈0（正确与噪声分数相近） | **>+0.5 平均** |

**根本原因**：Qwen text-embedding-v4 在建筑规范语料上未出现各向异性，embedding 空间已具备实用语义区分度，无需任何后处理。

---

## 遗留问题

### Q3：锅炉房防火间距（结构性缺陷，与 Embedding 无关）

两个模型均无法精确检索到锅炉房防火间距具体数值，原因：**防火间距表格在原始文档中以图片形式存储，LanceDB 向量索引和 Meilisearch 全文索引均无法覆盖图片内容**。

Qwen 能检索到《锅炉房设计规范》GB 50041 的相关条文（防火分隔要求、位置限制等），但无间距具体数字。

**解决方向**：对图片型表格做 OCR 转文本后重新入库，与 Embedding 模型选型无关。

### threshold 参数

Qwen 向量分数天然有效，建议生产环境将 `threshold` 从 0.0 上调至 **0.5~0.6** 以过滤低质噪声 chunk。当前实验配置为 0.0 以完整观察分数分布。

---

## 当前生产状态

```
活跃知识库:    KB 5（Qwen text-embedding-v4，1024维）
废弃知识库:    KB 3（Doubao，不再更新）
API endpoint:  http://localhost:4001/api/rag/...
生产 threshold: 建议 0.5（当前仍为 0.0，待更新）
RRF 权重:      vector=0.7, fulltext=0.3（Qwen 质量稳定，无需调整）
```

---

## 附：相关文档

- `RAG_TEST_REPORT.md` — v1 基准测试（Doubao，修复前）
- `RAG_TEST_REPORT_v2.md` — v2 测试（Doubao + All-but-the-Top）
- `RAG_EMBEDDING_COMPARE_RESULT.md` — Doubao vs Qwen 对比实验（本修复的验证报告）
- `experiment_results_kb5.json` — KB 5 实验原始数据（搜索结果全文 + prompt + LLM 回答）

---

## 附：原始测试环境（发现时）

```
知识库: KB 3 - 建筑规范库
文档数: 427
Chunk数: 37,822
Embedding模型: doubao-embedding-large-text-250515 (2048维)
向量数据库: LanceDB (cosine metric)
搜索阈值: threshold=0.3
测试时间: 2026-03-06
完整测试报告: RAG_TEST_REPORT.md
完整测试数据: rag_test_results.json
```
