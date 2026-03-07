# 04 - RAG 模块规范

## 概述
完整 RAG 流水线：文档上传 -> 树形解析 -> 切片 -> 嵌入 -> 双重索引（向量 + 全文） -> 混合搜索 -> 检索增强 -> 上下文组装。

## 配置常量（`app/modules/rag/config.py`）

```python
class RAGConfig:
    # 向量搜索
    SEARCH_DEFAULT_TOP_K = 5
    SEARCH_DEFAULT_THRESHOLD = 0.3
    SEARCH_MAX_TOP_K = 20

    # 检索增强
    ENHANCE_DEFAULT_STRATEGIES = ["siblings", "children"]
    ENHANCE_DEFAULT_MAX_DEPTH = 1
    ENHANCE_MIN_SIBLING_LEVEL = 2  # 避免展开 level-0/1 节点

    # 上下文组装
    CONTEXT_SEPARATOR = "\n\n---\n\n"
    CONTEXT_INCLUDE_HEADING = True
    CONTEXT_MAX_LENGTH = 8000  # 字符数
    CONTEXT_MAX_CHUNK_LENGTH = 2000

    # 结果限制
    LIMIT_MAX_CHUNKS = 30
    LIMIT_MAX_CONTEXT_TOKENS = 12000
    LIMIT_HIT_RATIO = 0.4
    LIMIT_GRAPH_RATIO = 0.4
    LIMIT_MIN_HITS = 3
    LIMIT_MIN_GRAPH = 10
    LIMIT_AVG_CHUNK_TOKENS = 200

    # 去重
    DEDUP_CONTENT_SIMILARITY = 0.85
    DEDUP_MIN_CONTENT_LENGTH = 50
    DEDUP_ENABLE_CONTENT = True
    DEDUP_ENABLE_PARENT_CHILD = True

    # Meilisearch
    MEILISEARCH_ENABLED = env("MEILISEARCH_ENABLED", "false") == "true"
    MEILISEARCH_HOST = env("MEILISEARCH_HOST", "http://localhost:7700")
    MEILISEARCH_API_KEY = env("MEILISEARCH_API_KEY", "masterKey")
    HYBRID_VECTOR_WEIGHT = 0.7
    HYBRID_FULLTEXT_WEIGHT = 0.3
    FUSION_STRATEGY = "rrf"  # rrf | weighted | linear

    # 历史
    MAX_HISTORY_ROUNDS = 5
    MAX_HISTORY_MESSAGES = 10

    # RAG 的 LLM 默认值
    LLM_DEFAULT_TEMPERATURE = 0.7
    LLM_DEFAULT_MAX_TOKENS = 4000
```

## 文档处理流水线

### 第 1 步：文件上传与存储
```python
async def upload_document(kb_id, file, chunk_size=500, chunk_overlap=0):
    # 1. 将文件保存到 uploads/{uuid}_{filename}
    # 2. 创建 RagDocument 记录（status=0 待处理）
    # 3. 触发异步处理
    return document
```

### 第 2 步：将文件解析为树形结构
```python
def parse_file(content: str, file_type: str) -> TreeNode:
    """根据文件类型路由到对应解析器"""
    parsers = {
        "md": parse_markdown_optimized,
        "txt": parse_txt,
        "docx": parse_docx,
        "pdf": parse_pdf,  # 先提取文本，再按 txt/md 解析
    }
    return parsers[file_type](content)
```

### 第 3 步：树形结构

#### 节点类型
```python
class NodeType(str, Enum):
    ROOT = "root"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"

@dataclass
class TreeNode:
    id: str               # 唯一节点 ID
    type: NodeType
    level: int            # root 为 -1，内容节点为 0+
    heading: str = ""     # 标题文本
    content: str = ""     # 节点内容
    children: list = field(default_factory=list)
    parent: 'TreeNode' = None
```

#### Markdown 解析器（优化版）
关键优化：**将连续段落合并到其父标题节点的内容中**，而不是创建独立子节点。这样可减少切片碎片化。

```python
def parse_markdown_optimized(content: str) -> TreeNode:
    """
    按标题层级解析 Markdown。
    段落内容被追加（APPEND）到父标题节点的内容中。
    """
    root = TreeNode(id=generate_node_id(), type=NodeType.ROOT, level=-1)
    current_node = root

    for token in markdown_tokenize(content):
        if token.type == "heading":
            level = token.depth - 1  # h1=0, h2=1, ...
            # 向上遍历找到正确父节点
            node = TreeNode(
                id=generate_node_id(), type=NodeType.HEADING,
                level=level, heading=token.text
            )
            # 挂载到合适的父节点
            parent = find_parent_for_level(current_node, level)
            parent.children.append(node)
            node.parent = parent
            current_node = node
        elif token.type == "paragraph":
            # 追加到当前标题节点的内容（而非新建子节点）
            if current_node.content:
                current_node.content += "\n\n"
            current_node.content += token.text
        # ... 类似处理 list、code、table
    return root
```

#### DOCX 解析器
```python
def parse_docx(file_path: str) -> TreeNode:
    """使用 python-docx 解析 DOCX，提取标题和段落"""
    # 使用 mammoth 或 python-docx 提取 HTML
    # 解析 HTML 标题（h1-h6）构建树
    # 去除段落内容的 HTML 标签
```

#### TXT 解析器
```python
def parse_txt(content: str) -> TreeNode:
    """解析纯文本，按双换行分割"""
    root = TreeNode(id=generate_node_id(), type=NodeType.ROOT, level=-1)
    paragraphs = re.split(r'\n\s*\n', content)
    for i, para in enumerate(paragraphs):
        if para.strip():
            node = TreeNode(
                id=generate_node_id(), type=NodeType.PARAGRAPH,
                level=0, content=para.strip()
            )
            root.children.append(node)
    return root
```

### 第 4 步：树形结构转切片
```python
def tree_to_chunks(tree: TreeNode, doc_id: int, max_size=500) -> list[dict]:
    """
    将树转换为带元数据的扁平切片列表。
    深度优先遍历，对超大内容进行分割。
    """
    chunks = []
    chunk_index = 0

    def traverse(node, parent_path="", parent_id=None, seq=0):
        nonlocal chunk_index
        path = build_path(parent_path, seq)

        if node.content:
            # 若内容超过 max_size 则分割
            parts = split_by_size(node.content, max_size)
            for i, part in enumerate(parts):
                chunks.append({
                    "doc_id": doc_id,
                    "node_id": node.id if i == 0 else generate_node_id(),
                    "parent_id": parent_id,
                    "level": node.level,
                    "path": path,
                    "heading": node.heading,
                    "content": part,
                    "chunk_index": chunk_index,
                    "seq": seq,
                    "char_count": len(part),
                })
                chunk_index += 1

        for i, child in enumerate(node.children):
            traverse(child, path, node.id, i)

    for i, child in enumerate(tree.children):
        traverse(child, "", tree.id, i)
    return chunks
```

### 第 5 步：文本分割算法
```python
SEPARATORS = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " "]

def split_by_size(text: str, max_size: int = 500) -> list[str]:
    """
    递归字符文本分割器，按分隔符优先级处理。
    先尝试较粗粒度的分隔符，再逐步细化。
    """
    if len(text) <= max_size:
        return [text]

    for sep in SEPARATORS:
        parts = text.split(sep)
        if len(parts) > 1:
            result = []
            buffer = ""
            for part in parts:
                candidate = buffer + sep + part if buffer else part
                if len(candidate) <= max_size:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer)
                    if len(part) > max_size:
                        result.extend(split_by_size(part, max_size))
                        buffer = ""
                    else:
                        buffer = part
            if buffer:
                result.append(buffer)
            if result:
                return result

    # 最后手段：按字符级别分割
    return [text[i:i+max_size] for i in range(0, len(text), max_size)]
```

### 第 6 步：节点 ID 与路径生成
```python
import time

_counter = 0

def generate_node_id() -> str:
    """生成唯一节点 ID：base36(时间戳) + 计数器 + 随机数"""
    global _counter
    _counter += 1
    ts = base36(int(time.time() * 1000))
    cnt = base36(_counter).zfill(4)
    rand = base36(random.randint(0, 1295))  # base36 中 2 位
    return f"{ts}{cnt}{rand}"

def build_path(parent_path: str, seq: int) -> str:
    """构建物化路径：0001/0002/0003"""
    segment = str(seq).zfill(4)
    return f"{parent_path}/{segment}" if parent_path else segment

def get_ancestor_paths(path: str) -> list[str]:
    """从物化路径获取所有祖先路径"""
    parts = path.split("/")
    return ["/".join(parts[:i+1]) for i in range(len(parts) - 1)]
```

### 第 7 步：可读性过滤
```python
def evaluate_readability(text: str) -> dict:
    """评估切片内容质量"""
    # 规范化：去除空白，删除图片引用
    normalized = re.sub(r'!\[.*?\]\(.*?\)', '', text).strip()

    # 噪声检测
    if len(text) < 40:
        return {"is_readable": False, "noise_tag": "NOISE_TOO_SHORT"}
    if len(normalized) < 12:
        return {"is_readable": False, "noise_tag": "LOW_TEXT_DENSITY"}

    # 评分
    base_score = min(1, len(normalized) / 120)
    chinese_ratio = len(re.findall(r'[\u4e00-\u9fff]', normalized)) / max(len(normalized), 1)
    alpha_ratio = len(re.findall(r'[a-zA-Z0-9]', normalized)) / max(len(normalized), 1)
    signal_score = min(1, (chinese_ratio + alpha_ratio) / 0.6)
    symbol_ratio = len(re.findall(r'[^\w\s]', normalized)) / max(len(normalized), 1)
    symbol_penalty = max(0, (symbol_ratio - 0.35) * 1.2)

    score = max(0, min(1, 0.55 * base_score + 0.45 * signal_score - symbol_penalty))
    is_readable = score >= 0.45

    return {"is_readable": is_readable, "readability_score": score, "noise_tag": None}
```

## 嵌入系统

### Doubao 嵌入客户端
```python
class DoubaoEmbedding:
    def __init__(self, host, api_key, model_id, batch_size=16):
        self.host = host
        self.api_key = api_key
        self.model_id = model_id
        self.batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            response = await httpx_client.post(
                f"{self.host}/api/v3/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model_id, "input": batch, "encoding_format": "float"}
            )
            data = response.json()["data"]
            embeddings = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
            all_embeddings.extend(embeddings)
        return all_embeddings
```

### 嵌入服务
```python
class EmbeddingService:
    SUPPORTED_MODELS = {
        "doubao": {"dimension": 2048},
    }

    async def embed(self, texts, model_type="doubao", config=None) -> list[list[float]]:
        if model_type == "doubao":
            client = DoubaoEmbedding(
                host=config.get("host") or env("DOUBAO_HOST"),
                api_key=config.get("api_key") or env("DOUBAO_API_KEY"),
                model_id=config.get("model_id") or env("DOUBAO_EMBEDDING_MODEL"),
            )
            return await client.embed(texts if isinstance(texts, list) else [texts])

    def get_dimension(self, model_type) -> int:
        return self.SUPPORTED_MODELS[model_type]["dimension"]
```

## 向量存储（LanceDB）

```python
import lancedb
import pyarrow as pa

class LanceDBDriver:
    def __init__(self, db_path: str):
        self.db = lancedb.connect(db_path)

    def ensure_table(self, table_name: str, dimension: int):
        """若表不存在则创建"""
        if table_name not in self.db.table_names():
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dimension)),
                pa.field("document", pa.string()),
                pa.field("doc_id", pa.int64()),
                pa.field("chunk_id", pa.int64()),
                pa.field("node_id", pa.string()),
                pa.field("parent_id", pa.string()),
                pa.field("level", pa.int32()),
                pa.field("path", pa.string()),
                pa.field("heading", pa.string()),
                pa.field("type", pa.string()),
            ])
            self.db.create_table(table_name, schema=schema)

    def add_vectors(self, table_name, records: list[dict]):
        """向表中添加向量"""
        table = self.db.open_table(table_name)
        table.add(records)

    def search(self, table_name, vector, top_k=5, where=None) -> list:
        """向量相似度搜索"""
        table = self.db.open_table(table_name)
        query = table.search(vector).limit(top_k).metric("cosine")
        if where:
            query = query.where(where)
        return query.to_list()

    def delete(self, table_name, where: str):
        """删除满足条件的记录"""
        table = self.db.open_table(table_name)
        table.delete(where)
```

### VectorDB 服务（实例管理器）
```python
class VectorDBService:
    _instances: dict = {}  # 缓存：kb_id -> LanceDBDriver

    def get_or_create(self, kb_id, dimension) -> LanceDBDriver:
        key = f"kb_{kb_id}"
        if key not in self._instances:
            db_path = f"database/lancedb/kb_{kb_id}"
            driver = LanceDBDriver(db_path)
            driver.ensure_table(f"kb_{kb_id}", dimension)
            self._instances[key] = driver
        return self._instances[key]

    def clear_cache(self, kb_id=None):
        if kb_id:
            self._instances.pop(f"kb_{kb_id}", None)
        else:
            self._instances.clear()
```

## 索引服务（统一）

```python
class IndexingService:
    def __init__(self):
        self.vector_provider = VectorIndexProvider()
        self.fulltext_provider = FulltextIndexProvider()

    async def index_chunks(self, kb_id, chunks, kb=None):
        """将切片索引到向量库和全文库"""
        results = {}

        # 向量索引
        vector_result = await self.vector_provider.index_chunks(kb_id, chunks, kb)
        results["vector"] = vector_result

        # 全文索引（若可用）
        if await self.fulltext_provider.is_available():
            ft_result = await self.fulltext_provider.index_chunks(kb_id, chunks)
            results["fulltext"] = ft_result

        return results

    async def delete_chunks(self, kb_id, chunk_ids):
        await self.vector_provider.delete_chunks(kb_id, chunk_ids)
        if await self.fulltext_provider.is_available():
            await self.fulltext_provider.delete_chunks(kb_id, chunk_ids)
```

### VectorIndexProvider
```python
class VectorIndexProvider:
    async def index_chunks(self, kb_id, chunks, kb=None):
        # 1. 获取知识库配置（嵌入模型、维度）
        # 2. 为所有切片生成嵌入向量
        texts = [c["content"] for c in chunks]
        embeddings = await embedding_service.embed(texts, kb.embedding_model, kb.embedding_config)
        # 3. 构建记录并添加到 LanceDB
        records = [{
            "id": f"chunk_{c['id']}", "vector": emb,
            "document": c["content"], "doc_id": c["doc_id"],
            "chunk_id": c["id"], "node_id": c.get("node_id"),
            "parent_id": c.get("parent_id"), "level": c.get("level", 0),
            "path": c.get("path", ""), "heading": c.get("heading", ""),
            "type": "text"
        } for c, emb in zip(chunks, embeddings)]
        driver = vector_db_service.get_or_create(kb_id, kb.dimension)
        driver.add_vectors(f"kb_{kb_id}", records)
        return {"success": len(records), "failed": 0, "embeddings": len(embeddings)}
```

## 搜索系统

### 搜索流水线（advancedSearch）
```
查询
  ├── VectorSearchProvider.search(kb_id, query, topK*2)
  └── FulltextSearchProvider.search(kb_id, query, topK*2)
  │
  ├── SearchFusion.fuse() [RRF]
  ├── ResultDeduplicator.deduplicate()
  ├── ResultLimiter.limit()
  ├── enhanceRetrieve() [兄弟节点/子节点/祖先节点]
  └── ContextOptimizer.optimize()
  → 最终切片 + 上下文文本
```

### VectorSearchProvider
```python
class VectorSearchProvider:
    async def search(self, kb_id, query, top_k=5, threshold=0.3,
                     use_adaptive_threshold=False, doc_prefilter_doc_ids=None):
        # 1. 生成查询嵌入向量
        kb = await kb_service.get_by_id(kb_id)
        query_vector = await embedding_service.embed([query], kb.embedding_model, kb.embedding_config)

        # 2. 构建文档预过滤的 WHERE 子句
        where = None
        if doc_prefilter_doc_ids:
            ids_str = ",".join(str(d) for d in doc_prefilter_doc_ids)
            where = f"doc_id IN ({ids_str})"

        # 3. 执行搜索（recall_multiplier=3 用于后置过滤）
        driver = vector_db_service.get_or_create(kb_id, kb.dimension)
        raw_results = driver.search(f"kb_{kb_id}", query_vector[0], top_k * 3, where)

        # 4. 应用阈值
        results = [r for r in raw_results if (1 - r["_distance"]) >= threshold]

        # 5. 动态阈值自适应（可选）
        if use_adaptive_threshold and results:
            adapted_threshold = ThresholdAdapter.adapt(results)
            results = [r for r in results if (1 - r["_distance"]) >= adapted_threshold]

        # 6. 格式化并返回 top_k 条
        return [format_search_result(r, source="vector") for r in results[:top_k]]
```

### FulltextSearchProvider
```python
class FulltextSearchProvider:
    async def search(self, kb_id, query, top_k=5):
        if not RAGConfig.MEILISEARCH_ENABLED:
            return []
        # 1. 提取关键词
        keywords = KeywordExtractor.extract(query)
        search_query = " ".join(keywords) if keywords else query

        # 2. Meilisearch 查询
        results = await meilisearch_index_service.search(kb_id, search_query, limit=top_k)

        # 3. 将排名转换为分数（简化 RRF）
        k = 60
        scored = []
        for rank, hit in enumerate(results["hits"]):
            score = 1 / (k + rank + 1)
            scored.append(format_search_result(hit, score=score, source="fulltext"))
        return scored
```

### SearchFusion（RRF）
```python
class SearchFusion:
    @staticmethod
    def fuse_rrf(result_sets: list[list], top_k=10, k=60) -> list:
        """倒数排名融合"""
        scores = {}  # chunk_id -> 总分
        items = {}   # chunk_id -> 条目

        for result_set in result_sets:
            for rank, item in enumerate(result_set):
                chunk_id = item["id"]
                rrf_score = 1 / (k + rank + 1)
                scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
                if chunk_id not in items:
                    items[chunk_id] = item
                else:
                    items[chunk_id].setdefault("fused_from", []).append(item.get("source"))

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [{**items[cid], "score": scores[cid]} for cid in sorted_ids]
```

### ResultDeduplicator
```python
class ResultDeduplicator:
    @staticmethod
    def deduplicate(chunks, config=None):
        """三层去重：ID -> 内容相似度 -> 父子节点"""
        # 1. ID 去重
        seen_ids = set()
        unique = []
        for c in chunks:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique.append(c)

        # 2. 内容相似度去重（Jaccard >= 0.85）
        if config.get("enable_content_dedup", True):
            filtered = []
            for c in unique:
                is_dup = False
                for existing in filtered:
                    if jaccard_similarity(c["content"], existing["content"]) >= 0.85:
                        is_dup = True
                        break
                if not is_dup:
                    filtered.append(c)
            unique = filtered

        # 3. 父子节点过滤
        if config.get("enable_parent_child_filter", True):
            # 删除其内容是结果中祖先子集的子节点
            paths = {c.get("metadata", {}).get("path"): c for c in unique}
            unique = [c for c in unique if not _has_ancestor_in_results(c, paths)]

        return unique
```

### 检索增强（retriever.py）
```python
class ExpandStrategy(str, Enum):
    CHILDREN = "children"
    SIBLINGS = "siblings"
    ANCESTORS = "ancestors"

async def enhance_retrieve(base_chunks, chunk_repository, strategies=None, max_depth=1, min_sibling_level=2):
    """用基于树的策略扩展基础切片"""
    strategies = strategies or [ExpandStrategy.CHILDREN]
    expanded = []
    seen_ids = {c["node_id"] for c in base_chunks}

    for chunk in base_chunks:
        if ExpandStrategy.CHILDREN in strategies:
            children = await chunk_repository.find_by_path_prefix(
                doc_id=chunk["doc_id"],
                path_prefix=f"{chunk['path']}/",
                max_level=chunk["level"] + max_depth if max_depth > 0 else None
            )
            for child in children:
                if child["node_id"] not in seen_ids:
                    seen_ids.add(child["node_id"])
                    child["is_hit"] = False
                    child["source"] = "expanded"
                    expanded.append(child)

        if ExpandStrategy.SIBLINGS in strategies:
            if chunk.get("parent_id") and chunk.get("level", 0) >= min_sibling_level:
                siblings = await chunk_repository.find_by_parent_id(
                    doc_id=chunk["doc_id"], parent_id=chunk["parent_id"]
                )
                for sib in siblings:
                    if sib["node_id"] not in seen_ids:
                        seen_ids.add(sib["node_id"])
                        sib["is_hit"] = False
                        sib["source"] = "expanded"
                        expanded.append(sib)

        if ExpandStrategy.ANCESTORS in strategies:
            ancestor_paths = get_ancestor_paths(chunk.get("path", ""))
            ancestors = await chunk_repository.find_by_paths(
                doc_id=chunk["doc_id"], paths=ancestor_paths
            )
            for anc in ancestors:
                if anc["node_id"] not in seen_ids:
                    seen_ids.add(anc["node_id"])
                    anc["is_hit"] = False
                    anc["source"] = "expanded"
                    expanded.append(anc)

    # 标记基础切片
    for c in base_chunks:
        c["is_hit"] = True
        c["source"] = "hit"

    all_chunks = base_chunks + expanded
    all_chunks.sort(key=lambda x: x.get("path", ""))
    return all_chunks
```

### ThresholdAdapter
```python
class ThresholdAdapter:
    @staticmethod
    def adapt(results, min_results=3, relative_ratio=0.7):
        """根据分数分布动态调整阈值"""
        if not results:
            return 0.3
        scores = [1 - r.get("_distance", 0) for r in results]
        max_score = max(scores)

        # 策略 1：相对阈值
        relative = max_score * relative_ratio

        # 策略 2：分数断崖检测
        cliff = None
        if len(scores) > 1:
            sorted_scores = sorted(scores, reverse=True)
            max_gap = 0
            for i in range(len(sorted_scores) - 1):
                gap = sorted_scores[i] - sorted_scores[i + 1]
                if gap > max_gap:
                    max_gap = gap
                    cliff = sorted_scores[i + 1]

        # 策略 3：最小结果数保证
        if len(scores) >= min_results:
            min_guarantee = sorted(scores, reverse=True)[min_results - 1] * 0.95
        else:
            min_guarantee = min(scores) * 0.95

        # 选择：保证值 > 断崖（若显著）> 相对值
        threshold = min_guarantee
        if cliff and max_gap > 0.1:
            threshold = min(threshold, cliff)
        threshold = min(threshold, relative)

        return threshold
```

### ContextOptimizer
```python
class ContextOptimizer:
    CHARS_PER_TOKEN = 1.5

    @staticmethod
    def optimize(chunks, max_tokens=12000):
        """压缩切片以适应 Token 预算"""
        budget_chars = max_tokens * ContextOptimizer.CHARS_PER_TOKEN

        # 按 doc_id 分组，按组内最高分排序
        groups = group_by_document(chunks)
        groups.sort(key=lambda g: g["max_score"], reverse=True)

        selected = []
        used_chars = 0

        for group in groups:
            group_chars = sum(len(c["content"]) for c in group["chunks"])
            if used_chars + group_chars <= budget_chars:
                selected.extend(group["chunks"])
                used_chars += group_chars
            elif used_chars < budget_chars * 0.9:
                # 部分选取：从该组中取分数最高的切片
                remaining = budget_chars - used_chars
                for c in sorted(group["chunks"], key=lambda x: x.get("score", 0), reverse=True):
                    if remaining <= 0:
                        break
                    if len(c["content"]) <= remaining:
                        selected.append(c)
                        remaining -= len(c["content"])
                        used_chars += len(c["content"])

        return selected
```

## 文档服务（完整流水线）

```python
class DocumentService:
    async def process_document(self, doc_id, content=None, chunk_size=500):
        """完整处理流水线"""
        doc = await self.get_by_id(doc_id)
        kb = await kb_service.get_by_id(doc.kb_id)

        # 更新状态为处理中
        doc.status = 1
        await self.update(doc)

        try:
            # 若未提供内容则读取文件
            if not content:
                content = await self._read_file(doc.file_path, doc.file_type)

            # 解析为树
            tree = parse_file(content, doc.file_type)

            # 树转切片
            chunks = tree_to_chunks(tree, doc.id, max_size=chunk_size)

            # 可读性过滤
            readable_chunks = []
            filtered_count = 0
            for chunk in chunks:
                readability = evaluate_readability(chunk["content"])
                chunk["metadata"] = {"readability": readability}
                if readability["is_readable"]:
                    readable_chunks.append(chunk)
                else:
                    chunk["metadata"]["index_skipped"] = True
                    chunk["metadata"]["index_skip_reason"] = readability["noise_tag"]
                    filtered_count += 1

            # 所有切片保存到数据库（包括被过滤的）
            saved_chunks = await self._save_chunks(doc.kb_id, chunks)

            # 仅为可读切片建立索引
            if readable_chunks:
                await indexing_service.index_chunks(doc.kb_id, saved_chunks[:len(readable_chunks)], kb)

            # 更新切片状态
            for sc in saved_chunks[:len(readable_chunks)]:
                sc.status = 1  # 已嵌入
                sc.vector_id = f"chunk_{sc.id}"
            await self._batch_update_chunks(saved_chunks)

            # 更新文档统计
            doc.status = 2  # 完成
            doc.chunk_count = len(chunks)
            doc.char_count = sum(c["char_count"] for c in chunks)
            await self.update(doc)

            # 更新知识库统计
            await kb_service.update_stats(doc.kb_id)

            return {
                "doc_id": doc.id,
                "chunk_count": len(chunks),
                "indexed_chunk_count": len(readable_chunks),
                "filtered_chunk_count": filtered_count,
            }
        except Exception as e:
            doc.status = 3  # 失败
            doc.error_msg = str(e)[:500]
            await self.update(doc)
            raise
```

## Meilisearch 集成

```python
class MeilisearchIndexService:
    def get_index_name(self, kb_id) -> str:
        return f"kb_{kb_id}"

    async def create_or_update_index(self, kb_id):
        client = await meilisearch_client.get_client()
        index_name = self.get_index_name(kb_id)
        index = client.index(index_name)
        await index.update_searchable_attributes(["content", "heading"])
        await index.update_filterable_attributes(["kb_id", "doc_id", "level"])
        return index

    async def index_knowledge_base(self, kb_id):
        """为知识库的所有切片建立索引"""
        chunks = await chunk_repository.get_by_kb_id(kb_id)
        documents = [{
            "id": f"chunk_{c.id}", "content": c.content,
            "heading": c.heading, "doc_id": c.doc_id,
            "kb_id": c.kb_id, "level": c.level,
            "path": c.path, "chunk_index": c.chunk_index,
        } for c in chunks]
        index = await self.create_or_update_index(kb_id)
        task = await index.add_documents(documents)
        return {"success": True, "task_uid": task.task_uid, "count": len(documents)}

    async def search(self, kb_id, query, limit=10, offset=0, filter=None):
        client = await meilisearch_client.get_client()
        index = client.index(self.get_index_name(kb_id))
        params = {"limit": limit, "offset": offset}
        if filter:
            params["filter"] = filter
        return await index.search(query, params)
```

## 迁移服务

```python
class MigrationService:
    async def export_kb(self, kb_id, output_dir="exports"):
        """导出知识库：MySQL 数据 + LanceDB 向量 -> tar.gz"""
        # 1. 导出 MySQL 数据（知识库、文档、切片）为 JSON
        # 2. 复制 LanceDB 目录
        # 3. 生成 manifest.json
        # 4. 创建 tar.gz 压缩包
        # 5. 计算 SHA256 校验和
        return {"archive_path": path, "manifest": manifest}

    async def import_kb(self, archive_path, force=False, skip_meilisearch=False):
        """从 tar.gz 导入知识库"""
        # 1. 验证 SHA256 校验和
        # 2. 解压压缩包
        # 3. 冲突检测（force=True 则覆盖）
        # 4. 导入 MySQL 数据
        # 5. 恢复 LanceDB 文件
        # 6. 重建 Meilisearch 索引（除非跳过）
        return manifest
```
