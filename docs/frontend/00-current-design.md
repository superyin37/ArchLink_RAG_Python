# 测试前端开发文档

> 文件：`static/test-ui/index.html`（单文件应用）
> 访问：`http://localhost:4001/test/`
> 挂载：`app/main.py` → `app.mount("/test", StaticFiles(directory=".../static/test-ui", html=True))`

---

## 一、技术栈

| 依赖 | 版本 | 加载方式 | 用途 |
|------|------|----------|------|
| Vue 3 | prod build | 本地 `vendor/vue.global.prod.js` | UI 框架（Composition API） |
| Tailwind CSS | CDN | 本地 `vendor/tailwind.js` | 样式工具类 |
| marked.js | 12.0.0 | CDN (jsdelivr) | Markdown 解析 |
| KaTeX | 0.16.11 | CDN (jsdelivr) | 数学公式渲染 |

无构建工具，所有逻辑写在单个 HTML 文件中。

---

## 二、页面结构

```
┌─────────────────────────────────────────┐
│  Header：Logo / API地址 / Token / 健康状态  │
├─────────────────────────────────────────┤
│  Tab 导航：搜索对比 / RAG对话 / KB概览      │
├─────────────────────────────────────────┤
│                                         │
│  Main（根据 activeTab 切换显示）           │
│                                         │
└─────────────────────────────────────────┘
```

### 2.1 Header
- 左：Logo（蓝色 R 方块）+ 标题
- 右：API Base 输入框、Token 密码输入框、「刷新数据」按钮、健康状态徽章
- `API Base` 和 `Token` 读写 `localStorage`，刷新页面后保留
- 点击「刷新数据」触发 `reload()`：持久化配置 → 并发执行健康检查 + 加载 KB 列表 + 加载模型列表

### 2.2 Tab 导航
- 三个 tab：`search`（搜索对比）、`chat`（RAG 对话）、`kb`（KB 概览）
- 当前激活 tab 通过 `activeTab` ref 控制，用 `v-show` 切换（不销毁 DOM）
- 切换到 `kb` tab 时自动触发加载所有知识库统计数据

---

## 三、各 Tab 详解

### 3.1 搜索对比（search）

**功能**：同一查询并发对比三种搜索方式的返回结果。

**配置参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 知识库 | 无（必选） | 从全局 `kbs` 列表选择 |
| 查询语句 | 空 | Enter 键触发搜索 |
| Top K | 5 | 返回结果数量上限 |
| 向量阈值 | 0.0 | 向量搜索最低相似度 |

**API 调用**：
```
POST /api/rag/meilisearch/compare/{kb_id}
Body: { query, top_k, vector_threshold }
Response: { data: { vector: [...], meilisearch: [...], hybrid: [...] } }
```

**结果展示**：三列并排卡片，分别对应：
- 向量搜索（蓝色边框）
- 全文搜索 Meilisearch（绿色边框）
- 混合搜索（紫色边框）

每个 chunk 卡片展示：序号、相似度分数、分数条、内容（截断 6 行）、来源文档名。

---

### 3.2 RAG 对话（chat）

**功能**：多轮 RAG 问答，SSE 流式输出，右侧实时展示检索到的上下文 chunks。

#### 3.2.1 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 知识库 | 无（必选） | 对话使用的知识库 |
| 模型 | 无（必选） | LLM 模型，来自 `/api/llm/model` |
| Top K | 10 | 检索 chunk 数量上限 |
| 阈值 | 0.0 | 向量相似度阈值 |

#### 3.2.2 消息结构
每条消息为对象 `{ role, content, thinking }`：
- `role`: `'user'` 或 `'assistant'`
- `content`: 消息正文（assistant 端支持 Markdown + KaTeX 渲染）
- `thinking`: 思维链内容（仅 assistant，显示为黄色 block）

#### 3.2.3 发送流程（`sendMessage`）

```
1. 校验输入（非空、已选 KB 和模型、未在加载中）
2. 清空输入框，追加 user 消息到列表
3. 创建 assistant 占位消息（reactive，content/thinking 为空字符串）
4. 清空 ragChunks，设置 chatLoading = true
5. POST /api/ppt/stream/rag-query（SSE 流）
6. 用 ReadableStream reader 逐块读取，按 \n 分割行
7. 解析每行 SSE 事件（见下方事件类型）
8. 完成后 chatLoading = false
```

#### 3.2.4 SSE 事件类型
后端使用 `app/modules/ppt/handlers/sse_stream.py` 发送，格式为 `data: {payload}\n\n`。

文本 token 中的换行符在后端被转义为 `\n` 字面字符串，前端还原：

| 事件格式 | 处理方式 |
|----------|----------|
| `data: {"type":"metadata",...}` | 保存 `conversation_id` |
| `data: {"type":"thinking","content":"..."}` | 追加到 `assistantMsg.thinking` |
| `data: {"type":"search_results","chunks":[...]}` | 更新右侧 `ragChunks` 面板 |
| `data: {"type":"error","message":"..."}` | 追加错误提示到 `assistantMsg.content` |
| `data: 纯文本token` | JSON 解析失败时，追加到 `assistantMsg.content`，并还原转义换行 |
| `data: [DONE]` | 跳过 |

#### 3.2.5 Markdown + 数学公式渲染（`renderMarkdown`）

每次 `v-html` 绑定时调用，处理步骤：

```
1. 扫描 $$...$$（块级公式），用 KaTeX displayMode 渲染，替换为占位符 \x00MATHn\x00
2. 扫描 $...$（行内公式，排除已处理的 $$），用 KaTeX 渲染，替换为占位符
3. 用 marked.parse() 解析 Markdown（开启 breaks:true、gfm:true）
4. 将占位符替换回 KaTeX 生成的 HTML
```

> 先提取公式再解析 Markdown，是为了防止 `$` 符号被 Markdown 解析器错误处理。

#### 3.2.6 布局
```
┌──────────────────────────────┬────────────┐
│  消息列表（flex-1，max-h:60vh）│ RAG 上下文  │
│                              │  宽 w-72   │
│  [用户气泡] ──────────────►  │  chunk #1  │
│  ◄── [AI 气泡 markdown]      │  chunk #2  │
│                              │  ...       │
├──────────────────────────────┴────────────┤
│  输入框（textarea）           │   发送按钮  │
└─────────────────────────────────────────-─┘
```

- 用户气泡：蓝色背景，右对齐，`border-radius: 18px 18px 4px 18px`
- AI 气泡：浅灰背景，左对齐，`border-radius: 18px 18px 18px 4px`
- Enter 发送，Shift+Enter 换行

---

### 3.3 KB 概览（kb）

**功能**：展示所有知识库的基本信息和统计数据。

**数据来源**：
- 知识库列表：`GET /api/rag/kb?page=1&size=100`
- 统计数据（按需加载）：`GET /api/rag/kb/{kb_id}/stats`

**每个 KB 卡片展示**：
- 名称、状态徽章（active=绿色）、描述、ID、Embedding 模型
- 统计数据（点击「加载统计数据」或切换到此 tab 时自动加载）：
  - 文档数（doc_count）
  - Chunk 数（chunk_count）
  - 总字符数（total_chars，超过 1w 显示为 `x.xw`）
  - 向量维度（dimension）

统计数据缓存在 `kbStats` ref（`{ [kb_id]: statsObject }`），页面生命周期内不重复请求。

---

## 四、全局状态

所有状态集中在 Vue `setup()` 中，通过 `return` 暴露给模板。

### 4.1 共享数据
| 变量 | 类型 | 说明 |
|------|------|------|
| `apiBase` | `ref<string>` | API 服务地址，持久化到 localStorage |
| `authToken` | `ref<string>` | JWT Token，持久化到 localStorage，作为请求头 `token` |
| `kbs` | `ref<array>` | 知识库列表，两个 tab 共用 |
| `models` | `ref<array>` | LLM 模型列表，chat tab 使用 |
| `activeTab` | `ref<string>` | 当前激活的 tab key |
| `healthText/Color` | `ref<string>` | 健康状态文字和样式 |

### 4.2 搜索状态
| 变量 | 说明 |
|------|------|
| `searchKbId` | 选中的知识库 ID |
| `searchQuery` | 查询语句 |
| `searchTopK` | Top K（默认 5） |
| `searchThreshold` | 向量阈值（默认 0.0） |
| `searchLoading` | 搜索加载状态 |
| `searchResults` | `{ vector, meilisearch, hybrid }` |

### 4.3 对话状态
| 变量 | 说明 |
|------|------|
| `chatKbId` | 选中的知识库 ID |
| `chatModelId` | 选中的模型 ID |
| `chatTopK` | 检索 chunk 数（默认 10） |
| `chatThreshold` | 向量阈值（默认 0.0） |
| `chatMessages` | 消息列表 `[{role, content, thinking}]` |
| `chatInput` | 输入框内容 |
| `chatLoading` | 流式请求进行中标志 |
| `conversationId` | 当前对话 ID（由后端 metadata 事件返回） |
| `ragChunks` | 最新一次检索到的 chunk 列表 |
| `chatScroll` | 消息列表 DOM ref，用于自动滚动到底部 |

---

## 五、API 对接

### 5.1 请求头
```javascript
{ 'Content-Type': 'application/json', 'token': '<JWT>' }
```
Token 为空时不发送 `token` 头。后端 `AuthMiddleware` 在开发模式下对 `/api/**` 全部放行（`auth.py` 白名单）。

### 5.2 响应格式（统一封装）
```json
{ "code": 0, "msg": "success", "data": { ... } }
```
`code=1` 表示错误，前端直接取 `res.data` 使用。

### 5.3 SSE 流格式
```
data: {"type":"metadata","conversation_id":"xxx"}\n\n
data: {"type":"search_results","chunks":[...]}\n\n
data: 文本token\n\n
data: [DONE]\n\n
```
后端在 `sse_stream.py` 中将文本 token 的 `\n` 转义为字面 `\n`，前端 catch 块还原。

---

## 六、初始化流程

```
onMounted()
  ├── checkHealth()       GET /api/health
  ├── loadKbList()        GET /api/rag/kb?page=1&size=100
  └── loadModels()        GET /api/llm/model?page=1&size=100

watch: activeTab → 'kb'
  └── loadAllKbStats()    GET /api/rag/kb/{id}/stats × n（并发）
```

---

## 七、已知限制

- 单文件，无热更新：修改后需重新 docker build 或挂载 volume
- 无错误提示 UI：大多数接口错误只 console.error，不展示给用户
- `conversation_id` 在页面刷新后丢失（不持久化），每次刷新开始新对话
- chunk 内容截断显示（line-clamp-4/6），无法查看全文
- 流式输出期间 Markdown 实时渲染，可能产生抖动
