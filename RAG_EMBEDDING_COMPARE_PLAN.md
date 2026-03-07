# Embedding 模型对比实验计划

**计划时间**: 2026-03-07
**目标**: 系统对比 Doubao（doubao-embedding-large-text-250515, 2048维）与 Qwen（text-embedding-v4, 1024维）在建筑规范语料上的端到端检索效果
**对比基准**: RAG_TEST_REPORT_v2.md（Doubao + All-but-the-Top，KB 3）

---

## 实验配置

### 两个知识库

| 参数 | KB 3（Doubao） | KB 5（Qwen） |
|------|--------------|-------------|
| 知识库 ID | 3 | 5 |
| Embedding 模型 | doubao-embedding-large-text-250515 | text-embedding-v4 |
| 向量维度 | 2048 | 1024 |
| 文档数 | 427 | 428 |
| Chunk 数（向量库） | 35,083 | 32,411 |
| All-but-the-Top | 已启用（n_components=4） | 未启用（不同空间，暂不启用） |
| 向量数据库 | LanceDB cosine | LanceDB cosine |
| 全文索引 | Meilisearch `kb_3` | Meilisearch `kb_5` |

### 固定参数（两组共用）

| 参数 | 值 |
|------|----|
| top_k | 5 |
| threshold | 0.0（消除阈值干扰，完整观察分数分布） |
| RRF 权重 | vector=0.7, fulltext=0.3 |
| 搜索模式 | hybrid（vector + fulltext） |
| LLM | claude-opus-4-6 |

> **为何 threshold=0.0**：Doubao All-but-the-Top 后绝对分数降至 0.30~0.35，Qwen 未做 AbTT 处理，两者分数量纲不同。统一用 0.0 让各自 top_k=5 完整返回，再观察分数裂距（正确 chunk 的分数 vs. 噪声 chunk 的分数之差）作为核心指标。

---

## 测试问题

沿用 RAG_TEST_REPORT_v2.md 的 5 道题，确保结果可纵向比较。

| # | 问题 | 目标规范 | 目标 doc_id（KB 3） |
|---|------|---------|-------------------|
| Q1 | 地下工程防水设计中，防水等级是如何划分的？各等级的防水标准是什么？ | 《地下工程防水技术规范》GB_50108-2008 | 193 |
| Q2 | 防灾避难场所的责任区面积和服务人口规模有哪些规定？ | 《防灾避难场所设计规范》GB_51143-2015 | 426 |
| Q3 | 锅炉房与周边建筑物、构筑物的防火间距要求是什么？ | 《锅炉房设计标准》GB_50041-2020 | 424 |
| Q4 | 饮食建筑的厨房与餐厅的面积比例有哪些规定？加工间的卫生要求是什么？ | 《饮食建筑设计标准》JGJ_64-2017 | 429 |
| Q5 | 铁路旅客车站候车室的设计要求，包括面积指标和疏散通道宽度是如何规定的？ | 《铁路旅客车站设计规范》TB_10100-2018 | 420/421 |

> **注**：KB 5 的 doc_id 与 KB 3 可能不同（不同入库顺序），执行时需从返回的 chunk 内容判断是否命中目标规范，而不能仅凭 doc_id。

---

## 执行步骤

### 步骤一：确认服务状态

```bash
# 确认两个 KB 均正常
curl http://localhost:4001/api/rag/kb/3
curl http://localhost:4001/api/rag/kb/5

# 确认向量维度
curl http://localhost:4001/api/rag/kb/3/stats
curl http://localhost:4001/api/rag/kb/5/stats
```

### 步骤二：每题执行三层搜索

对每个问题，分别在 KB 3 和 KB 5 上执行：

**2a. 纯向量搜索**

```bash
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": <KB_ID>, "query": "<QUESTION>", "top_k": 5, "threshold": 0.0, "search_type": "vector"}'
```

**2b. 纯全文搜索**

```bash
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": <KB_ID>, "query": "<QUESTION>", "top_k": 5, "threshold": 0.0, "search_type": "fulltext"}'
```

**2c. Hybrid 搜索（RRF 融合）**

```bash
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": <KB_ID>, "query": "<QUESTION>", "top_k": 5, "threshold": 0.0, "search_type": "hybrid"}'
```

记录每个结果的完整 JSON 响应（包含 doc_id、chunk_id、score、content 全文）。

### 步骤三：LLM 端到端问答

对每个问题 + 每个 KB，取 hybrid 搜索结果拼装 prompt，调用 LLM：

```bash
curl -X POST http://localhost:4001/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": <KB_ID>,
    "query": "<QUESTION>",
    "top_k": 5,
    "threshold": 0.0,
    "stream": false
  }'
```

记录：
1. **最终 prompt 的完整内容**（system prompt + 拼装的 context chunks + user question）
2. **LLM 返回的完整回答**

---

## 结果记录模板

每道题按以下结构记录（参考 RAG_TEST_REPORT_v2.md 格式）：

---

### Qx: [题目名称]

**问题**: [完整问题文本]

#### x.1 向量搜索结果

| 排名 | KB 3 Score | KB 3 doc_id | KB 3 内容摘要 | 相关性 | KB 5 Score | KB 5 doc_id | KB 5 内容摘要 | 相关性 |
|------|-----------|------------|-------------|--------|-----------|------------|-------------|--------|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

**分数裂距分析**（正确chunk分数 - TOP1错误chunk分数）：
- KB 3: 正确 chunk 分数 = ?, TOP1 噪声分数 = ?, 裂距 = ?
- KB 5: 正确 chunk 分数 = ?, TOP1 噪声分数 = ?, 裂距 = ?

#### x.2 全文搜索结果

| 排名 | KB 3 doc_id | 内容摘要 | 相关性 | KB 5 doc_id | 内容摘要 | 相关性 |
|------|------------|---------|--------|------------|---------|--------|

#### x.3 Hybrid 搜索结果（RRF 融合）

| 排名 | KB 3 Score | KB 3 doc_id | 来源 | 相关性 | KB 5 Score | KB 5 doc_id | 来源 | 相关性 |
|------|-----------|------------|------|--------|-----------|------------|------|--------|

#### x.4 最终 Prompt Context（完整）

**KB 3 送入 LLM 的 context**：

```
[system prompt 全文]

[Context Chunk 1 - doc_id=xxx, score=xxx]
[完整 chunk 文本]

[Context Chunk 2 - doc_id=xxx, score=xxx]
[完整 chunk 文本]

...

[User Question]
[问题全文]
```

**KB 5 送入 LLM 的 context**：

```
[同上格式]
```

#### x.5 LLM 完整回答

**KB 3 回答**：

```
[LLM 返回的完整文本，不截断]
```

**KB 5 回答**：

```
[LLM 返回的完整文本，不截断]
```

#### x.6 回答质量评估

| 维度 | KB 3（Doubao） | KB 5（Qwen） |
|------|--------------|-------------|
| 是否引用了正确规范 | | |
| 关键数值/条款是否准确 | | |
| 是否出现幻觉（引用了错误 context 的内容） | | |
| 回答完整度（1-5分） | | |
| 综合评级 | ✅/🟡/❌ | ✅/🟡/❌ |

---

## 核心评估指标

### 指标 1：向量搜索分数裂距（Score Spread）

衡量向量模型区分正确与噪声的能力。

```
Score Spread = Score(正确 chunk) - Score(最高排名错误 chunk)
```

- 正值且大：模型能明确区分，噪声不会混入 context
- 正值但小：能区分但阈值敏感
- 负值：正确 chunk 排在错误 chunk 之后（完全失效）

### 指标 2：向量搜索 TOP5 命中率

```
命中率 = TOP5 中包含正确目标规范的 chunk 数 / 5
```

### 指标 3：Hybrid TOP1 准确率

5 道题中，hybrid 搜索 TOP1 命中正确规范的题数。

### 指标 4：LLM 回答准确率

5 道题中，LLM 回答正确引用目标规范关键内容的题数（人工评估）。

### 指标 5：噪声 chunk 污染率

context 中来自错误规范的 chunk 占比（越低越好）。

---

## 综合对比汇总表（待填）

| 指标 | KB 3（Doubao + AbTT） | KB 5（Qwen） | 胜者 |
|------|---------------------|------------|------|
| 向量 TOP5 正确命中总数（满分25） | | | |
| 平均 Score Spread | | | |
| Hybrid TOP1 准确率（满分5） | | | |
| LLM 回答准确率（满分5） | | | |
| 平均 context 噪声 chunk 数（越低越好） | | | |
| 向量背景相似度（平均 TOP5 分数） | | | |

---

## 已知实验条件差异（需在报告中说明）

1. **All-but-the-Top**：KB 3 已应用（n_components=4），KB 5 未应用。这使两者向量分数量纲不可直接比较，需用 Score Spread 和命中率等相对指标评估。
2. **Chunk 数差异**：KB 3 有 35,083 chunks，KB 5 有 32,411 chunks，差异可能来自 readability 过滤（KB 3 后期入库文档过滤了英文块和标题块）。
3. **同文档不同 doc_id**：两个 KB 独立入库，同一规范文档的 doc_id 可能不同，评估时需以 chunk 内容为准。
4. **KB 5 RPM 限制**：Qwen API RPM 较低，KB 5 以 CONCURRENCY=1 入库，可能存在部分文档未完整向量化的情况，执行前需确认 chunk 数是否与预期一致。

---

## 实验执行清单

- [ ] 确认 docker-compose 服务正常（app / mysql / redis / meilisearch）
- [ ] 确认 KB 3 和 KB 5 的 chunk 数与上述记录一致
- [ ] 执行 Q1 × KB3 × {vector / fulltext / hybrid / chat}，记录完整响应
- [ ] 执行 Q1 × KB5 × {vector / fulltext / hybrid / chat}，记录完整响应
- [ ] 执行 Q2 × KB3/KB5（同上）
- [ ] 执行 Q3 × KB3/KB5（同上）
- [ ] 执行 Q4 × KB3/KB5（同上）
- [ ] 执行 Q5 × KB3/KB5（同上）
- [ ] 填写综合对比汇总表
- [ ] 输出结论与建议

---

## 预期产出

实验完成后输出 `RAG_EMBEDDING_COMPARE_RESULT.md`，格式参考本计划中的"结果记录模板"，包含：
- 每道题的三层搜索完整结果（含 chunk 全文内容）
- 每道题送入 LLM 的完整 prompt context
- 每道题 LLM 返回的完整回答
- 综合评估与模型选型建议
