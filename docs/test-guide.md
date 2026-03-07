# RAG System 测试指南

> 覆盖范围：RAG 模块 + LLM 模块（PPT 模块不在本文档范围内）
> 服务地址：`http://localhost:4001`
> 认证：开发模式下 `/api/**` 已在白名单，无需 Token

---

## 目录

1. [环境准备](#1-环境准备)
2. [Phase 0 — 服务健康检查](#phase-0--服务健康检查)
3. [Phase 1 — 知识库 CRUD](#phase-1--知识库-crud)
4. [Phase 2 — 文档上传与处理](#phase-2--文档上传与处理)
5. [Phase 3 — 搜索功能](#phase-3--搜索功能)
6. [Phase 4 — LLM Provider & Model 配置](#phase-4--llm-provider--model-配置)
7. [Phase 5 — Chat 与流式对话](#phase-5--chat-与流式对话)
8. [Phase 6 — 边界与异常测试](#phase-6--边界与异常测试)
9. [快速冒烟测试](#快速冒烟测试)
10. [验证点汇总](#验证点汇总)

---

## 1. 环境准备

### 1.1 启动服务

```bash
# Docker 方式
docker-compose up -d

# 本地方式
cd rag-python
uvicorn app.main:app --host 0.0.0.0 --port 4001 --reload
```

### 1.2 准备测试文件

创建 `test.md`，用于文档上传测试：

```markdown
# Python 编程基础

## 变量与类型

Python 是动态类型语言，变量不需要声明类型，解释器会自动推断。
常见类型包括：int、float、str、bool、list、dict、tuple、set。

## 函数定义

使用 `def` 关键字定义函数，支持默认参数、关键字参数和可变参数。

```python
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"
```

## 类与继承

Python 使用 `class` 关键字定义类，支持单继承和多继承。
`__init__` 方法是构造函数，`self` 指向实例本身。

## 异常处理

使用 `try/except/finally` 结构处理异常，可以捕获特定异常类型。
```

### 1.3 全局变量约定

测试过程中记录以下变量，后续步骤会用到：

| 变量 | 说明 | 示例 |
|------|------|------|
| `KB_ID` | 知识库 ID | `1` |
| `DOC_ID` | 文档 ID | `1` |
| `PROVIDER_DB_ID` | LLM Provider 数据库 ID | `1` |
| `MODEL_DB_ID` | LLM Model 数据库 ID | `1` |
| `CHAT_ID` | Chat 会话 ID（UUID） | `abc-123...` |

---

## Phase 0 — 服务健康检查

### 0.1 基础 Ping

```bash
curl http://localhost:4001/health
```

**预期响应**：
```json
{"status": "ok"}
```

### 0.2 完整健康检查（含 DB + Redis）

```bash
curl http://localhost:4001/api/health
```

**预期响应**：
```json
{"status": "ok", "db": true, "redis": true}
```

**验证点**：
- `db: true` — MySQL 连接正常
- `redis: true` — Redis 连接正常（若为 false，检查 `.env` 中 `REDIS_HOST/REDIS_PORT`）

---

## Phase 1 — 知识库 CRUD

### 1.1 创建知识库

```bash
curl -X POST http://localhost:4001/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python 技术文档",
    "description": "用于测试的 Python 知识库",
    "embedding_model": "doubao"
  }'
```

**预期响应**：
```json
{
  "code": 0,
  "data": {
    "id": 1,
    "name": "Python 技术文档",
    "embedding_model": "doubao",
    "doc_count": 0,
    "chunk_count": 0,
    "status": 1
  }
}
```

> 记录 `data.id` 为 `KB_ID`。

### 1.2 查询知识库列表

```bash
curl "http://localhost:4001/api/rag/kb?page=1&size=10"
```

**可选参数**：`keyword`（名称模糊搜索）、`status`（1=正常）

### 1.3 获取知识库详情

```bash
curl http://localhost:4001/api/rag/kb/${KB_ID}
```

### 1.4 更新知识库

```bash
curl -X PUT http://localhost:4001/api/rag/kb/${KB_ID} \
  -H "Content-Type: application/json" \
  -d '{"description": "已更新的描述"}'
```

### 1.5 知识库统计

```bash
curl http://localhost:4001/api/rag/kb/${KB_ID}/stats
```

### 1.6 可视化：知识库结构

```bash
curl http://localhost:4001/api/rag/visual/kb/${KB_ID}/structure
```

---

## Phase 2 — 文档上传与处理

### 2.1 方式一：文本直接创建（推荐用于快速测试）

```bash
curl -X POST http://localhost:4001/api/rag/document/text \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": 1,
    "filename": "python_basics.md",
    "content": "# Python 编程基础\n\n## 变量与类型\n\nPython 是动态类型语言，变量不需要声明类型。\n常见类型包括：int、float、str、bool、list、dict。\n\n## 函数定义\n\n使用 def 关键字定义函数，支持默认参数和关键字参数。\n\n## 类与继承\n\nPython 使用 class 关键字定义类，支持单继承和多继承。",
    "chunk_size": 200
  }'
```

> 记录 `data.id` 为 `DOC_ID`。

### 2.2 方式二：文件上传

```bash
curl -X POST http://localhost:4001/api/rag/document/upload \
  -F "kb_id=1" \
  -F "file=@test.md" \
  -F "chunk_size=200" \
  -F "chunk_overlap=0"
```

**支持的文件格式**：`.md`、`.txt`、`.docx`、`.pdf`、`.xlsx`

### 2.3 上传预览（不入库，仅看切片效果）

```bash
curl -X POST http://localhost:4001/api/rag/document/upload-preview \
  -F "file=@test.md" \
  -F "chunk_size=200"
```

### 2.4 查询文档列表

```bash
curl "http://localhost:4001/api/rag/document/kb/${KB_ID}?page=1&size=10"
```

### 2.5 轮询文档处理状态

文档上传后会异步处理（解析 → 切片 → 嵌入 → 向量入库），需轮询直到 `status=2`：

```bash
curl http://localhost:4001/api/rag/document/${DOC_ID}
```

**状态码说明**：

| status | 含义 |
|--------|------|
| `0` | 待处理 |
| `1` | 处理中 |
| `2` | 处理完成 |
| `3` | 处理失败（查看 `error_msg`） |

**轮询脚本**：
```bash
while true; do
  STATUS=$(curl -s http://localhost:4001/api/rag/document/${DOC_ID} | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "2" ] && echo "Done!" && break
  [ "$STATUS" = "3" ] && echo "Failed!" && break
  sleep 2
done
```

### 2.6 查看切片结果

```bash
curl http://localhost:4001/api/rag/document/${DOC_ID}/chunks
```

**验证点**：
- `chunk_count > 0`
- 每个 chunk 包含 `content`、`node_id`、`level`、`path`、`heading`

### 2.7 预览文档全文

```bash
curl http://localhost:4001/api/rag/document/${DOC_ID}/preview
```

### 2.8 可视化：文档树结构

```bash
curl http://localhost:4001/api/rag/visual/document/${DOC_ID}/tree
```

**验证点**：树结构层级正确，根节点 `level=0`，子节点 `level` 递增。

---

## Phase 3 — 搜索功能

> 前提：Phase 2 中文档 `status=2`（处理完成）。

### 3.1 基础向量搜索

```bash
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": 1,
    "query": "Python 如何定义函数",
    "top_k": 5,
    "threshold": 0.3
  }'
```

**预期响应**（data 为 list）：
```json
{
  "code": 0,
  "data": [
    {
      "id": 3,
      "content": "使用 def 关键字定义函数...",
      "score": 0.8721,
      "heading": "函数定义",
      "doc_id": 1,
      "source": "vector"
    }
  ]
}
```

**验证点**：
- 结果与查询语义相关
- `score` 在 `[0, 1]` 之间，且 `>= threshold`
- `source` 为 `"vector"`

### 3.2 多知识库搜索

```bash
curl -X POST http://localhost:4001/api/rag/search/multi \
  -H "Content-Type: application/json" \
  -d '{
    "kb_ids": [1],
    "query": "变量类型声明",
    "top_k": 5,
    "threshold": 0.3
  }'
```

### 3.3 上下文搜索（RAG Prompt 组装）

```bash
curl -X POST http://localhost:4001/api/rag/search/context \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": 1,
    "query": "Python 类如何使用继承",
    "top_k": 3,
    "threshold": 0.3,
    "separator": "\n\n---\n\n",
    "enhance": true
  }'
```

**预期响应**：
```json
{
  "code": 0,
  "data": {
    "context": "Python 使用 class 关键字定义类...\n\n---\n\n支持单继承和多继承..."
  }
}
```

**验证点**：`context` 字段为非空字符串，内容与查询相关。

### 3.4 查询搜索能力

```bash
curl http://localhost:4001/api/rag/search/capabilities
```

**预期响应**：返回 `vector_search`、`fulltext_search` 的可用状态。

### 3.5 （可选）Meilisearch 全文搜索

> 需要 `.env` 中 `MEILISEARCH_ENABLED=true` 且 Meilisearch 服务运行。

```bash
# 查看索引状态
curl http://localhost:4001/api/rag/meilisearch/stats/${KB_ID}

# 手动创建/重建索引
curl -X POST http://localhost:4001/api/rag/meilisearch/index/${KB_ID}
curl -X POST http://localhost:4001/api/rag/meilisearch/rebuild/${KB_ID}

# 全文搜索
curl -X POST http://localhost:4001/api/rag/meilisearch/search/${KB_ID} \
  -H "Content-Type: application/json" \
  -d '{"query": "函数 def", "limit": 5, "offset": 0}'

# 向量 vs 全文 对比搜索
curl -X POST http://localhost:4001/api/rag/meilisearch/compare/${KB_ID} \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 函数定义", "top_k": 5}'
```

### 3.6 统计信息

```bash
# 全局统计
curl http://localhost:4001/api/rag/statistics/overview

# 知识库排名
curl "http://localhost:4001/api/rag/statistics/ranking?order_by=doc_count&limit=10"

# 单个知识库统计
curl http://localhost:4001/api/rag/statistics/kb/${KB_ID}
```

---

## Phase 4 — LLM Provider & Model 配置

### 4.1 查询支持的 API 类型

```bash
curl http://localhost:4001/api/llm/provider/api-types
```

**预期**：返回 `openai`、`anthropic`、`azure`、`gemini` 等类型列表。

### 4.2 创建 LLM Provider

```bash
# OpenAI 兼容接口（包括 DeepSeek、豆包等）
curl -X POST http://localhost:4001/api/llm/provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "openai",
    "name": "OpenAI",
    "api_type": "openai",
    "api_endpoint": "https://api.openai.com/v1",
    "api_key": "sk-your-real-key",
    "status": 1,
    "sort_order": 1
  }'
```

> 记录 `data.id` 为 `PROVIDER_DB_ID`。

**其他 Provider 示例**：

```bash
# Anthropic
curl -X POST http://localhost:4001/api/llm/provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "anthropic",
    "name": "Anthropic",
    "api_type": "anthropic",
    "api_key": "sk-ant-your-key",
    "status": 1
  }'

# DeepSeek（OpenAI 兼容接口）
curl -X POST http://localhost:4001/api/llm/provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "deepseek",
    "name": "DeepSeek",
    "api_type": "openai",
    "api_endpoint": "https://api.deepseek.com/v1",
    "api_key": "sk-your-deepseek-key",
    "status": 1
  }'
```

### 4.3 更新 API Key

```bash
curl -X PUT http://localhost:4001/api/llm/provider/${PROVIDER_DB_ID}/api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-new-key"}'
```

### 4.4 查询 Provider 列表

```bash
curl "http://localhost:4001/api/llm/provider?page=1&size=10"
```

### 4.5 创建 LLM Model

```bash
curl -X POST http://localhost:4001/api/llm/model \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "openai",
    "model_id": "gpt-4o-mini",
    "name": "GPT-4o Mini",
    "max_tokens": 16384,
    "context_window": 128000,
    "capabilities": ["chat", "text"],
    "status": 1,
    "sort_order": 1
  }'
```

> 记录 `data.id` 为 `MODEL_DB_ID`。
> `model_id` 必须与 LLM 服务商实际的模型名称一致。

### 4.6 查询 Model 列表（按 Provider 分组）

```bash
curl http://localhost:4001/api/llm/model/by-provider
```

### 4.7 查询 Model 列表（分页）

```bash
curl "http://localhost:4001/api/llm/model?page=1&size=20"
```

### 4.8 更新 Model

```bash
curl -X PUT http://localhost:4001/api/llm/model/${MODEL_DB_ID} \
  -H "Content-Type: application/json" \
  -d '{"description": "GPT-4o 的轻量版本", "status": 1}'
```

---

## Phase 5 — Chat 与流式对话

> `model` 字段格式为 `"provider_id#model_id"`，例如 `"openai#gpt-4o-mini"`。

### 5.1 创建 Chat 会话

```bash
curl -X POST http://localhost:4001/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai#gpt-4o-mini",
    "title": "Python 技术问答"
  }'
```

> 记录 `data.chat_id` 为 `CHAT_ID`（UUID 格式）。

### 5.2 流式对话（核心测试）

```bash
curl -N -X POST http://localhost:4001/api/llm/chat/${CHAT_ID}/stream \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai#gpt-4o-mini",
    "message": "请用一句话解释 Python 的动态类型特性"
  }'
```

**预期输出**（SSE 格式）：
```
data: {"type":"delta","content":"Python"}

data: {"type":"delta","content":" 的动态类型"}

data: {"type":"delta","content":"意味着变量在运行时才确定类型。"}

data: {"type":"done","usage":{"prompt_tokens":20,"completion_tokens":30,"total_tokens":50}}
```

**验证点**：
- 响应为 `text/event-stream` 格式
- `type:delta` 事件连续出现，内容逐段累积
- 最终有 `type:done` 事件，包含 token 用量

### 5.3 多轮对话（续接上下文）

```bash
# 第二轮问题，CHAT_ID 不变，历史记录自动携带
curl -N -X POST http://localhost:4001/api/llm/chat/${CHAT_ID}/stream \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai#gpt-4o-mini",
    "message": "那静态类型语言有什么优势？"
  }'
```

**验证点**：模型能理解上文语境，回答与 Python/动态类型相关。

### 5.4 查询历史消息

```bash
curl "http://localhost:4001/api/llm/chat/${CHAT_ID}/messages?page=1&size=50"
```

**验证点**：消息按 `create_time` 排列，`role` 交替出现 `user` 和 `assistant`。

### 5.5 更新会话标题

```bash
curl -X PUT http://localhost:4001/api/llm/chat/${CHAT_ID}/title \
  -H "Content-Type: application/json" \
  -d '{"title": "Python 动态类型讨论"}'
```

### 5.6 查询会话列表

```bash
curl "http://localhost:4001/api/llm/chat?page=1&size=10"
```

### 5.7 查询调用日志

```bash
# 列表
curl "http://localhost:4001/api/llm/call-log?page=1&size=10"

# 按 provider 过滤
curl "http://localhost:4001/api/llm/call-log?provider_id=openai&page=1&size=10"
```

**验证点**：
- `is_success: true`
- `prompt_tokens`、`completion_tokens` 不为 0
- `total_duration` 有值（毫秒）

### 5.8 查询调用统计

```bash
curl http://localhost:4001/api/llm/call-log/statistics
```

**预期响应**：
```json
{
  "code": 0,
  "data": {
    "total_calls": 2,
    "total_prompt_tokens": 50,
    "total_completion_tokens": 60,
    "total_cost": 0.0,
    "avg_duration": 1234.5
  }
}
```

---

## Phase 6 — 边界与异常测试

### 6.1 废弃 Model

```bash
curl -X POST http://localhost:4001/api/llm/model/${MODEL_DB_ID}/deprecate \
  -H "Content-Type: application/json" \
  -d '{"replacement_model_id": "gpt-4o"}'
```

**验证点**：该 model `status` 变为 `0`，`replacement_model_id` 有值。

### 6.2 删除文档（软删除）

```bash
curl -X DELETE http://localhost:4001/api/rag/document/${DOC_ID}

# 再次查询应返回 404
curl http://localhost:4001/api/rag/document/${DOC_ID}
```

**预期**：
```json
{"code": 1, "msg": "Document ... not found", "data": null}
```

**验证点**：
- 文档软删除（`delete_time` 有值）
- 对应的向量数据从 LanceDB 中清除
- 对应的 Meilisearch 文档也被删除（若启用）

### 6.3 删除知识库

```bash
curl -X DELETE http://localhost:4001/api/rag/kb/${KB_ID}

# 验证已删除
curl http://localhost:4001/api/rag/kb/${KB_ID}
```

### 6.4 删除 Chat 会话

```bash
curl -X DELETE http://localhost:4001/api/llm/chat/${CHAT_ID}

# 验证已删除
curl http://localhost:4001/api/llm/chat/${CHAT_ID}
```

### 6.5 资源不存在（404）

```bash
curl http://localhost:4001/api/rag/kb/99999
curl http://localhost:4001/api/rag/document/99999
curl http://localhost:4001/api/llm/provider/99999
curl http://localhost:4001/api/llm/model/99999
```

**预期**：HTTP 200，响应体 `code: 1`，`msg` 包含 `not found`。

### 6.6 参数校验（422）

```bash
# kb_id 类型错误
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "invalid", "query": "test"}'

# 缺少必填字段
curl -X POST http://localhost:4001/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{}'
```

**预期**：HTTP 422 Unprocessable Entity，返回字段校验错误详情。

### 6.7 搜索空知识库

```bash
# 先创建一个没有文档的知识库
curl -X POST http://localhost:4001/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{"name": "空知识库", "embedding_model": "doubao"}'

# 对空知识库搜索
curl -X POST http://localhost:4001/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"kb_id": 2, "query": "任意查询", "top_k": 5}'
```

**预期**：返回空数组 `[]`，不报错。

---

## 快速冒烟测试

以下为最小化验证核心链路的步骤，适合快速确认系统可用性：

```bash
BASE="http://localhost:4001"

# Step 1: 健康检查
curl -s $BASE/api/health

# Step 2: 创建知识库
KB=$(curl -s -X POST $BASE/api/rag/kb \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-test","embedding_model":"doubao"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "KB_ID: $KB"

# Step 3: 上传文档（文本方式）
DOC=$(curl -s -X POST $BASE/api/rag/document/text \
  -H "Content-Type: application/json" \
  -d "{\"kb_id\":$KB,\"filename\":\"smoke.md\",\"content\":\"# 测试\\n\\nPython 函数用 def 关键字定义。\",\"chunk_size\":100}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "DOC_ID: $DOC"

# Step 4: 等待处理完成（最多等 30 秒）
for i in $(seq 1 15); do
  STATUS=$(curl -s $BASE/api/rag/document/$DOC | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "2" ] && break
  sleep 2
done

# Step 5: 搜索
curl -s -X POST $BASE/api/rag/search \
  -H "Content-Type: application/json" \
  -d "{\"kb_id\":$KB,\"query\":\"Python 函数\",\"top_k\":3,\"threshold\":0.3}" \
  | python3 -m json.tool

# Step 6: 创建 LLM Provider（替换真实 key）
P=$(curl -s -X POST $BASE/api/llm/provider \
  -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","name":"OpenAI","api_type":"openai","api_endpoint":"https://api.openai.com/v1","api_key":"sk-xxx"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Step 7: 创建 LLM Model
curl -s -X POST $BASE/api/llm/model \
  -H "Content-Type: application/json" \
  -d '{"provider_id":"openai","model_id":"gpt-4o-mini","name":"GPT-4o Mini"}'

# Step 8: 创建 Chat
CHAT=$(curl -s -X POST $BASE/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"openai#gpt-4o-mini","title":"smoke-test"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['chat_id'])")
echo "CHAT_ID: $CHAT"

# Step 9: 流式对话
curl -N -X POST $BASE/api/llm/chat/$CHAT/stream \
  -H "Content-Type: application/json" \
  -d '{"model":"openai#gpt-4o-mini","message":"你好，用一句话介绍 Python"}'
```

---

## 验证点汇总

| Phase | 关键验证项 | 预期结果 |
|-------|-----------|---------|
| 0 | `GET /api/health` | `db:true`, `redis:true` |
| 1 | 创建知识库 | 返回 `id`，`status:1` |
| 2 | 文档上传后轮询 | `status` 最终变为 `2` |
| 2 | 切片结果 | `chunk_count > 0`，每条有 `node_id`、`level` |
| 3 | 向量搜索 | 结果语义相关，`score >= threshold` |
| 3 | 上下文搜索 | `context` 为非空拼接字符串 |
| 4 | 创建 Provider | `api_key` 返回 `"***"` 脱敏 |
| 5 | 流式对话 | SSE `type:delta` 连续输出，最终 `type:done` |
| 5 | 调用日志 | `is_success:true`，token 数不为 0 |
| 6 | 删除资源后查询 | 返回 `not found` 错误 |
| 6 | 参数类型错误 | HTTP 422 |
| 6 | 搜索空知识库 | 返回空数组不报错 |
