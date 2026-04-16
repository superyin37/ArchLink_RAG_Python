# RAG Search Logic

```mermaid
flowchart TD
    Q(["用户 Query"])

    %% ── 双路召回 ──────────────────────────────────────────────
    Q --> EMB["Doubao Embed\n(2048-dim)"]
    Q --> KW["关键词提取\nKeywordExtractor"]

    EMB --> VS
    KW  --> FT

    subgraph RECALL["双路召回  ·  Dual Retrieval"]
        direction LR
        VS["向量搜索\nLanceDB cosine\ntop_k × 3 超额召回"]
        FT["全文搜索\nMeilisearch\n(可选，默认关闭)"]
    end

    VS --> THRESH["阈值过滤\ndefault ≥ 0.3\n+ 自适应截断"]
    FT --> RANK["BM25 排名\n→ RRF score\n1/(k+rank+1)"]

    %% ── 自适应阈值说明 ────────────────────────────────────────
    THRESH -. "自适应策略\n① 相对阈值 max×0.7\n② 分数悬崖检测\n③ 保底 min_results=3" .-> THRESH

    THRESH --> FUSION
    RANK  --> FUSION

    %% ── 融合 ─────────────────────────────────────────────────
    subgraph FUSION["RRF Fusion"]
        F1["对每个结果集独立排名"]
        F2["score = Σ 1/(60+rank+1)"]
        F1 --> F2
    end

    FUSION --> DEDUP

    %% ── 三层去重 ─────────────────────────────────────────────
    subgraph DEDUP["三层去重  ·  ResultDeduplicator"]
        direction TB
        D1["① ID 去重"]
        D2["② 内容相似度\nJaccard ≥ 0.85 视为重复"]
        D3["③ 父子过滤\n子节点内容已包含于祖先时移除"]
        D1 --> D2 --> D3
    end

    DEDUP --> LIMIT["结果限制\nResultLimiter\nmax 30 chunks"]

    %% ── 树感知增强 ───────────────────────────────────────────
    subgraph ENHANCE["树感知检索增强  ·  enhance_retrieve()"]
        direction LR
        HIT(["命中节点\nis_hit=True"])
        SIB["siblings\n同父兄弟节点\nlevel ≥ 2 时触发"]
        CHD["children\n子节点\nmax_depth=1"]
        ANC["ancestors\n祖先节点\n物化路径反向查找"]
        EXP(["扩展节点\nis_hit=False\nsource=expanded"])
        HIT --> SIB & CHD & ANC
        SIB & CHD & ANC --> EXP
    end

    LIMIT --> ENHANCE

    %% ── 上下文组装 ───────────────────────────────────────────
    ENHANCE --> CTX

    subgraph CTX["上下文组装  ·  Context Assembly"]
        direction TB
        C1["按 path 排序\n还原文档树顺序"]
        C2["Token 预算压缩\nContextOptimizer\nmax 12 000 tokens\n按文档分组·高分优先"]
        C3["Markdown 格式化\n命中块 → 直接相关内容\n扩展块 → 相关背景"]
        C4["字符截断 8 000 chars\n单块 max 2 000 chars"]
        C1 --> C2 --> C3 --> C4
    end

    CTX --> OUT(["最终 Chunks\n+ Context Text\n→ LLM"])

    %% ── 数据来源标注 ─────────────────────────────────────────
    VS -. "kb_{id} 表\nLanceDB" .-> VS
    FT -. "index kb_{id}\nMeilisearch" .-> FT
    ANC & SIB & CHD -. "物化路径查询\nMySQL chunks表\npath LIKE 'prefix/%'" .-> ANC

    %% ── 样式 ─────────────────────────────────────────────────
    classDef hit    fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef exp    fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef key    fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f
    classDef store  fill:#f3e8ff,stroke:#9333ea,color:#3b0764

    class FUSION,DEDUP,ENHANCE key
    class HIT hit
    class EXP exp
    class VS,FT store
```

## 关键设计点速查

| 步骤 | 设计决策 | 参数 |
|------|---------|------|
| **超额召回** | 向量召回 `top_k × 3`，阈值后再截断到 top_k | 默认 top_k=5 |
| **自适应阈值** | 根据分数分布动态调整，避免固定阈值截断过多/过少 | base=0.3 |
| **RRF 融合** | 不依赖原始分数量纲，两路结果可直接合并排名 | k=60 |
| **内容去重** | Jaccard 词级相似度，短文本跳过（< 50 chars） | ≥ 0.85 |
| **父子过滤** | 物化路径判断，子集内容不重复出现 | 路径前缀匹配 |
| **树感知增强** | 命中节点带出上下文邻居，补充 LLM 所需背景 | siblings+children |
| **Token 预算** | 按文档分组、高分优先裁剪，保证 prompt 不超限 | 12 000 tokens |
