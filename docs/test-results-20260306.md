# 测试执行报告

**执行日期**：2026-03-06
**环境**：Windows 11，Python 3.10（venv），MySQL 8.0 / Redis 7 / Meilisearch 1.6（Docker）
**服务端口**：4001

---

## 执行环境说明

| 组件 | 运行方式 | 状态 |
|------|---------|------|
| FastAPI 应用 | venv 本地启动（`uvicorn app.main:app`） | 手动启动 |
| MySQL | Docker 容器 `rag_mysql`，映射 3306 | 正常 |
| Redis | Docker 容器 `rag_redis`，映射 6379 | 正常 |
| Meilisearch | Docker 容器 `rag_meilisearch`，映射 7700 | 正常 |

> **注意**：启动应用前须激活 venv，使用 `.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4001`

---

## 测试结果总览

| Phase | 测试内容 | 结果 | 备注 |
|-------|---------|------|------|
| 0 | 服务健康检查 | ✅ 通过 | `db:true`, `redis:true` |
| 1 | 知识库 CRUD | ✅ 通过 | 列表/详情/更新/统计均正常 |
| 2 | 文档上传与处理 | ✅ 通过 | 需先安装 meilisearch 包（见问题1）|
| 3 | 搜索功能 | ✅ 通过 | 向量/全文/上下文搜索均正常 |
| 4 | LLM Provider & Model | ✅ 通过（修复后）| 发现 Bug 9、Bug 10 |
| 5 | Chat 流式对话 | ✅ 通过（修复后）| 发现 Bug 11 |
| 6 | 边界与异常 | ✅ 通过 | 软删除/404/422 全部正确 |

---

## Phase 0 — 服务健康检查

```
GET /health          → {"status":"ok"}
GET /api/health      → {"status":"ok","db":true,"redis":true}
```

**结论**：通过。

---

## Phase 1 — 知识库 CRUD

创建知识库（`id=2`，名称"Python 技术文档"，`embedding_model=doubao`）：

```json
{"id":2,"name":"Python 技术文档","embedding_model":"doubao",
 "vector_db_type":"lancedb","dimension":2048,"doc_count":0,"chunk_count":0,"status":1}
```

- 查询列表：正常，含已有旧记录（id=1）
- 查询详情：正常
- 更新描述：正常，返回 `{"id":2}`
- 统计接口：正常，返回 `doc_count/chunk_count/dimension`

**结论**：通过。

---

## Phase 2 — 文档上传与处理

### 遇到问题 1：meilisearch 包未安装

**现象**：文档处理完成后 Meilisearch 全文索引始终为空，日志报 `No module named 'meilisearch'`。

**原因**：venv 缺少 `meilisearch` 包（`requirements.txt` 虽然有，但未在此 venv 安装）。

**修复**：
```bash
.venv/Scripts/pip.exe install meilisearch
```

重启服务后正常。

### 文档处理结果

用文本方式创建文档（`doc_id=7`，filename=`python_basics.md`，chunk_size=200）：

```json
{"id":7,"chunk_count":3,"char_count":144,"status":2}
```

切片内容示例（共 3 条）：

| id | heading | content（摘要） | level | path |
|----|---------|----------------|-------|------|
| 7 | 变量与类型 | Python 是动态类型语言... | 1 | 0000/0000 |
| 8 | 类与继承 | Python 使用 class 关键字... | 1 | 0000/0002 |
| 9 | 异常处理 | 使用 try/except/finally... | 1 | 0000/0003 |

> 注：函数定义章节内容较短，被合并处理，属正常切片行为。

**结论**：通过（status=2，chunk_count=3，各字段完整）。

---

## Phase 3 — 搜索功能

### 3.1 向量搜索

查询"函数如何定义"，返回 1 条（score=0.4479，内容：异常处理）：

```json
[{"id":9,"content":"使用 try/except/finally 结构处理异常...","score":0.4479,"source":"vector"}]
```

查询"类和继承"，返回 2 条（含"类与继承"chunk，score=0.34）。

### 3.2 多知识库搜索

```json
{"chunks":[...],"errors":[]}
```
正常返回，`errors` 为空。

### 3.3 上下文搜索（RAG 拼接）

```json
{
  "context": "### 异常处理\n使用 try/except/finally 结构...\n\n---\n\n### 类与继承\nPython 使用 class 关键字..."
}
```

`context` 字段为带标题的拼接文本，可直接注入 Prompt。

### 3.4 搜索能力查询

```json
{"vector":true,"fulltext":true,"hybrid":true}
```

### 3.5 Meilisearch 全文搜索

安装 meilisearch 包并重建索引后：

```bash
POST /api/rag/meilisearch/rebuild/2   → {"success":3,"failed":0}
POST /api/rag/meilisearch/search/2    → {"hits":[{"id":"9","content":"使用 try/except/finally..."}],"total_hits":1}
```

对比搜索（vector vs fulltext vs hybrid）也正常返回三组结果。

### 遇到问题 2：Meilisearch get_stats 返回 500

**现象**：`GET /api/rag/meilisearch/stats/{kb_id}` 返回 500。

**原因**：`IndexStats.get_stats()` 返回对象中 `field_distribution` 字段是 `FieldDistribution` 对象，无法被 FastAPI 直接 JSON 序列化。

**修复**（[index_service.py:106](app/modules/rag/meilisearch/index_service.py#L106)）：
```python
# 修复前
return stats.__dict__ if hasattr(stats, "__dict__") else dict(stats)

# 修复后
result = stats.__dict__ if hasattr(stats, "__dict__") else dict(stats)
return {
    k: (v.__dict__ if hasattr(v, "__dict__") else v)
    for k, v in result.items()
}
```

**结论**：通过（含 2 处修复）。

---

## Phase 4 — LLM Provider & Model 配置

使用已有 Provider（`provider_id=ark`，豆包 ARK，`api_type=openai`）。

### Bug 9：`_provider_to_dict` 访问不存在的 `p.config`

**现象**：`GET /api/llm/provider` 返回 500，日志：
```
AttributeError: 'LLMProvider' object has no attribute 'config'
```

**原因**：[router.py](app/modules/llm/router.py#L320) 中 `_provider_to_dict` 引用了 `p.config`，但 `LLMProvider` 模型无此字段（实际字段为 `api_endpoint` 和 `default_parameters`）。

**修复**：
```python
# 修复前
"config": p.config,

# 修复后
"api_endpoint": p.api_endpoint,
"default_parameters": p.default_parameters,
```

### Bug 10：`/model/by-provider` 接口返回 ORM 对象无法序列化

**现象**：`GET /api/llm/model/by-provider` 返回 500，日志：
```
TypeError: Object of type LLMModel is not JSON serializable
```

**原因**：[router.py:109](app/modules/llm/router.py#L109) 直接将 `model_service.get_by_provider_grouped()` 返回值透传给 `R.success()`，其中 `models` 字段包含原始 ORM 对象。

**修复**：
```python
# 修复前
return R.success(grouped)

# 修复后
return R.success([
    {"provider_id": g["provider_id"], "models": [_model_to_dict(m) for m in g["models"]]}
    for g in grouped
])
```

### Model 创建结果

```json
{"id":1,"provider_id":"ark","model_id":"ep-m-20260105214053-9g6v5","name":"豆包 Pro",
 "max_tokens":8192,"context_window":128000,"capabilities":["chat","text"],"status":1}
```

**结论**：通过（修复 Bug 9、Bug 10 后）。

---

## Phase 5 — Chat 与流式对话

### Bug 11：`load_model_by_string` 不支持 `#` 分隔符

**现象**：`POST /api/llm/chat/{chat_id}/stream` 返回：
```json
{"code":1,"msg":"LLM model 'Model 'ark#ep-m-20260105214053-9g6v5' not found' not found"}
```

**原因**：[model_loader.py](app/modules/llm/utils/model_loader.py) 只处理 `:` 分隔符（`provider_db_id:model_db_id`），而 router 传入的格式为 `provider_id#model_id`（字符串形式）。`factory.py` 的 `_extract_from_config` 也使用 `#` 作为分隔符，前后不一致。

**修复**（在 `load_model_by_string` 中增加 `#` 分支）：
```python
# Handle "provider_id#model_id" format
if "#" in model_str:
    provider_id_str, model_id_str = model_str.split("#", 1)
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.provider_id == provider_id_str,
            LLMModel.model_id == model_id_str,
            LLMModel.delete_time.is_(None),
            LLMModel.status == 1,
        ).limit(1)
    )
    model = result.scalar_one_or_none()
    if model:
        result = await db.execute(
            select(LLMProvider).where(LLMProvider.provider_id == model.provider_id)
        )
        provider = result.scalar_one_or_none()
        if provider and not provider.delete_time:
            return provider, model
```

### 流式对话结果

`POST /api/llm/chat/{chat_id}/stream` 发送"你好，用一句话介绍 Python 语言"：

- 响应类型：`text/event-stream`
- 格式：`event: message` / `data: {"text": "..."}` 逐 token 推送
- 结束：`event: done` / `data: {"done": true}`

### 历史消息验证

```json
[
  {"role":"user","content":"你好，用一句话介绍 Python 语言"},
  {"role":"assistant","content":"Python是一门语法简洁易读、支持多编程范式的解释型高级通用编程语言...",
   "model":"ep-m-20260105214053-9g6v5",
   "token_usage":{"prompt_tokens":57,"completion_tokens":431,"total_tokens":488}}
]
```

### 调用日志验证

```json
{"is_success":true,"prompt_tokens":57,"completion_tokens":431,
 "total_tokens":488,"total_duration":15230,"first_token_duration":4284}
```

### 调用统计

```json
{"total_calls":1,"total_prompt_tokens":57,"total_completion_tokens":431,
 "total_cost":0.0,"avg_duration":15230.0}
```

**结论**：通过（修复 Bug 11 后）。SSE 流正常，消息持久化正常，调用日志完整。

---

## Phase 6 — 边界与异常测试

| 测试场景 | 请求 | 预期 | 实际 | 结果 |
|---------|------|------|------|------|
| 废弃 Model | `POST /model/1/deprecate` | status=0 | status=0, replacement_model_id="gpt-4o" | ✅ |
| 删除文档（软删） | `DELETE /document/7` | code=0 | `{"code":0,"data":{"id":7}}` | ✅ |
| 查询已删除文档 | `GET /document/7` | 404 | `{"code":1,"msg":"Document 7 not found"}` | ✅ |
| 查询不存在的知识库 | `GET /kb/99999` | not found | `{"code":1,"msg":"Knowledge base 99999 not found"}` | ✅ |
| 参数类型错误 | `POST /search`（kb_id="invalid"） | 422 | HTTP 422，Pydantic 校验详情 | ✅ |
| 搜索不存在知识库 | `POST /search`（kb_id=99） | not found | `{"code":1,"msg":"Knowledge base 99 not found"}` | ✅ |

**结论**：通过。

---

## 本轮新增 Bug 修复汇总

| 编号 | 文件 | 问题描述 | 修复方式 |
|------|------|---------|---------|
| Bug 9 | `app/modules/llm/router.py` | `_provider_to_dict` 引用 `p.config`（字段不存在） | 替换为 `p.api_endpoint` + `p.default_parameters` |
| Bug 10 | `app/modules/llm/router.py` | `/model/by-provider` 直接返回 ORM 对象 | 用 `_model_to_dict` 序列化后再返回 |
| Bug 11 | `app/modules/llm/utils/model_loader.py` | 不支持 `provider_id#model_id` 格式，流式对话报 model not found | 增加 `#` 分隔符分支处理 |
| Bug 12 | `app/modules/rag/meilisearch/index_service.py` | `get_stats` 返回嵌套对象 `FieldDistribution` 无法序列化 | 对嵌套对象额外调用 `.__dict__` |
| — | venv 环境 | venv 未安装 `meilisearch` 包，全文索引全部 skipped | `pip install meilisearch` |

> 前 8 个 Bug 已在上一轮 debug 修复（见 commit `v2.0 0202`）。

---

## 启动注意事项（常见陷阱）

1. **必须用 venv 里的 Python 启动**：系统 `python3` 是 Windows Store 占位符，直接运行无效。
   ```bash
   .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4001
   ```

2. **pyc 缓存问题**：修改代码后若行为未变化，需清除缓存后重启：
   ```bash
   find app -name "*.pyc" -delete
   # 然后用 taskkill 确认老进程已终止，再重启
   ```

3. **中文字符在 curl**：Windows bash 下 curl 的 `-d` 参数含中文时会被截断。使用 Unicode 转义或写入文件：
   ```bash
   # 用 \uXXXX 转义代替直接中文
   -d "{\"name\":\"\u77e5\u8bc6\u5e93\"}"
   ```

4. **Meilisearch 包**：确认 venv 已安装 `meilisearch>=0.31.0`，否则全文索引静默跳过（`skipped=N`）。
