# 02 - 数据库模式

## 概述
所有表遵循以下约定：
- 主键：`id`（INTEGER，自增）
- 时间戳：`create_time`（DateTime，默认=当前时间）、`update_time`（DateTime，默认=当前时间，自动更新）、`delete_time`（DateTime，可为空，NULL=有效）
- 软删除：所有查询默认过滤 `WHERE delete_time IS NULL`
- MySQL 8.0，字符集=utf8mb4

## 基础模型（Python）
```python
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    create_time = Column(DateTime, server_default=func.now(), nullable=False)
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    delete_time = Column(DateTime, nullable=True, default=None)
```

---

## 表：`rag_knowledge_base`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| name | VARCHAR(100) | - | 知识库名称（必填） |
| description | VARCHAR(500) | NULL | 描述 |
| embedding_model | VARCHAR(50) | - | 嵌入模型类型：`doubao`、`openai` 等（必填） |
| embedding_config | JSON | NULL | 嵌入模型配置（API Key、端点等） |
| vector_db_type | VARCHAR(50) | - | 向量数据库类型：`lancedb`（必填） |
| vector_db_config | JSON | NULL | 向量数据库配置 |
| dimension | INTEGER | NULL | 向量维度（例如 Doubao 为 2048） |
| doc_count | INTEGER | 0 | 文档数量 |
| chunk_count | INTEGER | 0 | 切片数量 |
| status | TINYINT | 1 | 0=禁用，1=正常，2=索引中 |
| create_time | DateTime | NOW() | 创建时间 |
| update_time | DateTime | NOW() | 更新时间 |
| delete_time | DateTime | NULL | 软删除 |

---

## 表：`rag_document`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| kb_id | INTEGER | - | 外键，关联 knowledge_base（必填） |
| filename | VARCHAR(255) | - | 原始文件名（必填） |
| file_type | VARCHAR(50) | NULL | 文件扩展名：pdf、txt、md、docx |
| file_size | BIGINT | NULL | 文件大小（字节） |
| file_path | VARCHAR(500) | NULL | 磁盘存储路径 |
| content_hash | VARCHAR(64) | NULL | 内容 SHA256 哈希 |
| chunk_count | INTEGER | 0 | 切片数量 |
| char_count | INTEGER | 0 | 总字符数 |
| status | TINYINT | 0 | 0=待处理，1=处理中，2=完成，3=失败 |
| error_msg | VARCHAR(500) | NULL | 失败时的错误信息 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

---

## 表：`rag_chunk`

核心表，通过物化路径支持树形结构。

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| kb_id | INTEGER | - | 外键，关联 knowledge_base（必填） |
| doc_id | INTEGER | - | 外键，关联 document（必填） |
| content | TEXT | - | 切片文本内容（必填） |
| chunk_index | INTEGER | 0 | 在文档中的位置索引 |
| node_id | VARCHAR(32) | NULL | 唯一节点 ID（树） |
| parent_id | VARCHAR(32) | NULL | 父节点 ID（树） |
| level | TINYINT | 0 | 树深度级别 |
| path | VARCHAR(500) | NULL | 物化路径：`0001/0002/0003` |
| heading | VARCHAR(255) | NULL | 标题文本 |
| seq | INTEGER | 0 | 兄弟节点排序 |
| char_count | INTEGER | 0 | 字符数 |
| token_count | INTEGER | NULL | Token 数（估算） |
| vector_id | VARCHAR(100) | NULL | 向量数据库中的 ID |
| metadata | JSON | NULL | 额外元数据（可读性、索引信息） |
| status | TINYINT | 0 | 0=待处理，1=已嵌入，2=失败 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- `idx_kb_id`：(kb_id)
- `idx_doc_id`：(doc_id)
- `idx_doc_path`：(doc_id, path)
- `idx_doc_parent`：(doc_id, parent_id)

---

## 表：`rag_embedding_provider`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| name | VARCHAR(100) | - | 显示名称（必填） |
| type | VARCHAR(50) | - | 类型标识：`doubao`、`openai` 等（必填） |
| config | JSON | NULL | API 配置（密钥、端点等） |
| dimension | INTEGER | NULL | 向量维度 |
| description | VARCHAR(500) | NULL | 描述 |
| enabled | TINYINT | 1 | 0=禁用，1=启用 |
| sort_order | INTEGER | 0 | 排序权重 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

---

## 表：`llm_providers`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| provider_id | VARCHAR(50) | - | 唯一标识：`openai`、`anthropic` 等（必填，UNIQUE） |
| name | VARCHAR(100) | - | 显示名称（必填） |
| icon | VARCHAR(20) | NULL | Emoji 或图标类名 |
| api_endpoint | VARCHAR(500) | NULL | API 基础 URL |
| api_type | VARCHAR(50) | `openai` | API 类型：`openai`、`anthropic`、`google`、`openai-compatible` |
| api_key | TEXT | NULL | 全局 API 密钥 |
| auth_type | VARCHAR(50) | `bearer` | 认证类型：`bearer`、`api-key`、`custom` |
| default_parameters | JSON | {} | 默认请求参数 |
| description | TEXT | NULL | 提供者描述 |
| official_website | VARCHAR(500) | NULL | 官方网站 URL |
| documentation_url | VARCHAR(500) | NULL | API 文档 URL |
| status | TINYINT | 1 | 0=禁用，1=启用 |
| is_builtin | BOOLEAN | false | 是否内置（不可删除） |
| sort_order | INTEGER | 0 | 排序权重 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- UNIQUE on (provider_id)
- Index on (status)
- Index on (sort_order)

---

## 表：`llm_models`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| provider_id | VARCHAR(50) | - | 外键，关联 llm_providers.provider_id（必填） |
| model_id | VARCHAR(100) | - | 模型标识：`gpt-4o`、`claude-3-5-sonnet-20241022` 等（必填） |
| name | VARCHAR(100) | - | 显示名称（必填） |
| description | TEXT | NULL | 模型描述 |
| max_tokens | INTEGER | NULL | 最大输出 Token 数 |
| context_window | INTEGER | NULL | 上下文窗口大小 |
| capabilities | JSON | [] | 能力标签：`["chat", "vision", "function-calling"]` |
| pricing | JSON | NULL | 定价：`{input_price, output_price, cache_hit_price, currency, per_tokens}` |
| release_date | DATE | NULL | 发布日期 |
| is_deprecated | BOOLEAN | false | 是否已废弃 |
| replacement_model_id | VARCHAR(100) | NULL | 废弃时的替代模型 |
| status | TINYINT | 1 | 0=禁用，1=启用 |
| is_builtin | BOOLEAN | false | 内置（不可删除） |
| sort_order | INTEGER | 0 | 排序权重 |
| metadata | JSON | {} | 额外元数据（api_version 等） |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- UNIQUE on (provider_id, model_id)
- Index on (provider_id)
- Index on (status)
- Index on (is_deprecated)

---

## 表：`llm_chat`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| chat_id | VARCHAR(64) | - | 唯一聊天标识（必填） |
| user_id | BIGINT | NULL | 用户 ID |
| title | VARCHAR(200) | "New Chat" | 聊天标题 |
| model | VARCHAR(100) | NULL | 使用的模型 |
| message_count | INTEGER | 0 | 总消息数 |
| total_tokens | INTEGER | 0 | 总 Token 使用量 |
| status | TINYINT | 1 | 0=已归档，1=正常 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- Index on (user_id, update_time)，名称 `idx_user_update`
- Index on (chat_id)，名称 `idx_chat_id`

---

## 表：`llm_message`

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| chat_id | VARCHAR(64) | - | 外键，关联 llm_chat.chat_id（必填） |
| role | ENUM('system','user','assistant') | - | 消息角色（必填） |
| content | LONGTEXT | - | 消息内容（必填） |
| model | VARCHAR(100) | NULL | 模型名称（用于 assistant 消息） |
| token_usage | JSON | NULL | `{prompt_tokens, completion_tokens, total_tokens}` |
| meta | JSON | NULL | 扩展元数据（思考内容、附件等） |
| user_id | BIGINT | NULL | 用户 ID |
| status | TINYINT | 1 | 0=禁用，1=正常 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- Index on (chat_id, create_time)，名称 `idx_chat_time`
- Index on (user_id, create_time)，名称 `idx_user_time`

---

## 表：`llm_call_logs`

完整的 LLM 调用跟踪，含性能指标。

| 字段 | 类型 | 默认值 | 说明 |
|--------|------|---------|-------------|
| id | INTEGER | 自增 | 主键 |
| **请求标识** |
| request_id | VARCHAR(100) | - | 唯一请求 ID（必填） |
| **模型信息** |
| provider_id | VARCHAR(50) | - | 提供者标识（必填） |
| model | VARCHAR(100) | - | 模型名称（必填） |
| api_type | VARCHAR(50) | NULL | API 类型 |
| **请求详情** |
| request_url | VARCHAR(500) | NULL | 请求 URL |
| request_method | VARCHAR(10) | `POST` | HTTP 方法 |
| request_headers | JSON | NULL | 脱敏后的请求头 |
| request_body | JSON | NULL | 请求体 |
| **输入/输出** |
| prompt | TEXT | NULL | 用户提示词文本 |
| messages | JSON | NULL | 完整消息历史 |
| response_text | TEXT | NULL | 完整响应文本 |
| reasoning_text | TEXT | NULL | 推理/思考文本 |
| **Token 统计** |
| prompt_tokens | INTEGER | 0 | 输入 Token 数 |
| completion_tokens | INTEGER | 0 | 输出 Token 数 |
| total_tokens | INTEGER | 0 | 总 Token 数 |
| reasoning_tokens | INTEGER | 0 | 推理 Token 数 |
| cached_tokens | INTEGER | 0 | 缓存 Token 数 |
| **费用** |
| cost | DECIMAL(10,6) | NULL | 计算费用 |
| cost_details | JSON | NULL | `{input, output, cache, currency}` |
| **时间（毫秒）** |
| request_start_time | BIGINT | NULL | 请求开始时间戳（ms） |
| first_token_time | BIGINT | NULL | 首个 Token 时间戳（ms） |
| response_end_time | BIGINT | NULL | 响应结束时间戳（ms） |
| total_duration | INTEGER | NULL | 总耗时（ms） |
| first_token_duration | INTEGER | NULL | 首 Token 耗时（ms） |
| **状态** |
| status | VARCHAR(20) | `pending` | `pending`、`streaming`、`success`、`error` |
| is_success | BOOLEAN | false | 是否成功 |
| error_message | TEXT | NULL | 错误信息 |
| error_stack | TEXT | NULL | 错误堆栈 |
| **上下文** |
| user_id | INTEGER | NULL | 用户 ID |
| session_id | VARCHAR(100) | NULL | 会话/聊天 ID |
| template_id | INTEGER | NULL | 提示词模板 ID |
| tags | JSON | NULL | 分类标签 |
| metadata | JSON | NULL | 额外元数据 |
| create_time | DateTime | NOW() | |
| update_time | DateTime | NOW() | |
| delete_time | DateTime | NULL | |

**索引：**
- Index on (request_id)
- Index on (provider_id)
- Index on (model)
- Index on (status)
- Index on (is_success)
- Index on (user_id)
- Index on (session_id)
- Index on (template_id)
- Index on (create_time)
- Index on (cost)

---

## LanceDB 向量表结构

每个知识库拥有独立的 LanceDB 表，表名格式：`kb_{kb_id}`

| 字段 | 类型 | 说明 |
|--------|------|-------------|
| id | string | 切片标识（如 `chunk_123`） |
| vector | float32[] | 嵌入向量（维度与知识库配置一致） |
| document | string | 切片文本内容 |
| doc_id | int | 文档 ID |
| chunk_id | int | 切片 ID |
| node_id | string | 树节点 ID |
| parent_id | string | 父节点 ID |
| level | int | 树深度级别 |
| path | string | 物化路径 |
| heading | string | 标题文本 |
| type | string | 内容类型（默认："text"） |

---

## Meilisearch 索引结构

索引名格式：`kb_{kb_id}`

**可搜索字段：** `content`、`heading`
**可过滤字段：** `kb_id`、`doc_id`、`level`
**可排序字段：** `chunk_index`

文档结构：
```json
{
  "id": "chunk_123",
  "content": "切片文本...",
  "heading": "章节标题",
  "doc_id": 1,
  "kb_id": 1,
  "level": 2,
  "path": "0001/0002",
  "chunk_index": 5
}
```
