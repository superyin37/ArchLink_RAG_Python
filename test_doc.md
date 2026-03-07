# RAG 系统介绍

RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索和大语言模型的技术架构。

## 核心优势

1. **知识时效性**：可以接入最新的私有知识库，克服大模型训练数据截止日期的限制。
2. **减少幻觉**：模型基于检索到的真实文档生成回答，降低捏造内容的概率。
3. **可追溯性**：每个回答都可以追溯到具体的文档来源。

## 工作流程

1. 用户提出问题
2. 系统将问题转换为向量（Embedding）
3. 在向量数据库中检索最相关的文档片段（Chunks）
4. 将检索到的上下文和问题一起发送给大语言模型
5. 模型生成最终回答

## 技术组件

- **向量数据库**：LanceDB，用于存储和检索文档 Embedding
- **全文搜索**：Meilisearch，用于关键词精确匹配
- **Embedding 模型**：豆包 Doubao Embedding，维度 2048
- **LLM**：支持 OpenAI、Anthropic、Azure、Gemini、VolcEngine 等多种提供商
