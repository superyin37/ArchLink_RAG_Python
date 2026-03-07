"""
Embedding 对比实验执行脚本
- 对 5 道题分别调用 KB5（Qwen）的 vector/fulltext/hybrid 搜索
- 获取 assembled context
- 调用 Qwen Chat（qwen-plus，OpenAI-compatible）得到完整回答
- 将所有原始结果存入 experiment_results_kb5.json
"""

import asyncio
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

BASE_URL = "http://localhost:4001"
KB_ID = 5
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_CHAT_MODEL = "qwen-plus"

QUESTIONS = [
    {
        "id": "Q1",
        "label": "地下防水等级划分",
        "question": "地下工程防水设计中，防水等级是如何划分的？各等级的防水标准是什么？",
        "target_doc": "《地下工程防水技术规范》GB_50108-2008",
    },
    {
        "id": "Q2",
        "label": "防灾避难场所责任区规定",
        "question": "防灾避难场所的责任区面积和服务人口规模有哪些规定？",
        "target_doc": "《防灾避难场所设计规范》GB_51143-2015",
    },
    {
        "id": "Q3",
        "label": "锅炉房防火间距",
        "question": "锅炉房与周边建筑物、构筑物的防火间距要求是什么？",
        "target_doc": "《锅炉房设计标准》GB_50041-2020",
    },
    {
        "id": "Q4",
        "label": "饮食建筑厨房面积比例",
        "question": "饮食建筑的厨房与餐厅的面积比例有哪些规定？加工间的卫生要求是什么？",
        "target_doc": "《饮食建筑设计标准》JGJ_64-2017",
    },
    {
        "id": "Q5",
        "label": "铁路候车室设计要求",
        "question": "铁路旅客车站候车室的设计要求，包括面积指标和疏散通道宽度是如何规定的？",
        "target_doc": "《铁路旅客车站设计规范》TB_10100-2018",
    },
]

SYSTEM_PROMPT = (
    "你是一位专业的建筑规范顾问。请根据以下提供的建筑规范文档内容，回答用户的问题。\n"
    "要求：\n"
    "1. 只根据提供的文档内容作答，不要引用未提供的规范\n"
    "2. 如有具体数值、条款编号，请明确引用\n"
    "3. 如提供的文档内容不足以完整回答问题，请说明\n"
    "4. 回答要准确、专业、有条理"
)


async def call_compare(client: httpx.AsyncClient, question: str) -> dict:
    resp = await client.post(
        f"{BASE_URL}/api/rag/meilisearch/compare/{KB_ID}",
        json={"query": question, "top_k": 5, "vector_threshold": 0.0},
        timeout=30,
    )
    return resp.json()


async def call_context(client: httpx.AsyncClient, question: str) -> dict:
    resp = await client.post(
        f"{BASE_URL}/api/rag/search/context",
        json={
            "kb_id": KB_ID,
            "query": question,
            "top_k": 5,
            "threshold": 0.0,
            "enhance": True,
            "strategies": ["siblings", "children"],
            "max_depth": 1,
        },
        timeout=30,
    )
    return resp.json()


async def call_llm(client: httpx.AsyncClient, context: str, question: str) -> str:
    if not QWEN_API_KEY:
        return "[ERROR: QWEN_API_KEY not set]"

    user_content = (
        f"请根据以下建筑规范文档内容回答问题：\n\n---\n{context}\n---\n\n问题：{question}"
    )

    resp = await client.post(
        QWEN_CHAT_URL,
        headers={"Authorization": f"Bearer {QWEN_API_KEY}"},
        json={
            "model": QWEN_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 2048,
        },
        timeout=60,
    )
    data = resp.json()
    if resp.status_code != 200:
        return f"[ERROR {resp.status_code}]: {json.dumps(data, ensure_ascii=False)}"
    return data["choices"][0]["message"]["content"]


async def run_experiment():
    results = {}

    async with httpx.AsyncClient() as client:
        for q in QUESTIONS:
            qid = q["id"]
            question = q["question"]
            print(f"\n{'='*60}")
            print(f"[{qid}] {q['label']}")

            # 1. Compare search
            print(f"  -> compare search...", end="", flush=True)
            t0 = time.time()
            compare_result = await call_compare(client, question)
            print(f" {int((time.time()-t0)*1000)}ms")

            # 2. Context assembly
            print(f"  -> context assembly...", end="", flush=True)
            t0 = time.time()
            context_result = await call_context(client, question)
            context_text = context_result.get("data", {}).get("context", "")
            print(f" {int((time.time()-t0)*1000)}ms ({len(context_text)} chars)")

            # 3. LLM call
            print(f"  -> LLM ({QWEN_CHAT_MODEL})...", end="", flush=True)
            t0 = time.time()
            llm_response = await call_llm(client, context_text, question)
            print(f" {int((time.time()-t0)*1000)}ms")

            user_prompt = (
                f"请根据以下建筑规范文档内容回答问题：\n\n---\n{context_text}\n---\n\n问题：{question}"
            )

            results[qid] = {
                "meta": q,
                "compare": compare_result.get("data", {}),
                "context": context_text,
                "llm_system_prompt": SYSTEM_PROMPT,
                "llm_user_prompt": user_prompt,
                "llm_response": llm_response,
            }

    out_path = Path(__file__).parent.parent / "experiment_results_kb5.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\nSaved: {out_path}")
    return results


if __name__ == "__main__":
    asyncio.run(run_experiment())
