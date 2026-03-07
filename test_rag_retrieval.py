"""
RAG 检索能力测试脚本
测试知识库：KB 3 - 建筑规范库 (427文档, 37822 chunks)
"""
import asyncio
import json
import time
import httpx
from datetime import datetime

BASE_URL = "http://localhost:4001"
KB_ID = 3

# 豆包API直接调用参数
DOUBAO_API_KEY = "d75ec25c-27c4-40f1-8d30-bcd7799ed97c"
DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_MODEL = "ep-m-20260105214053-9g6v5"

# ── 测试问题设计 ─────────────────────────────────────────────────────────────────
TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "地下工程防水设计中，防水等级是如何划分的？各等级的防水标准是什么？",
        "category": "防水规范",
        "expected_doc": "《地下工程防水技术规范》GB_50108-2008",
    },
    {
        "id": 2,
        "question": "防灾避难场所的责任区面积和服务人口规模有哪些规定？",
        "category": "防灾规范",
        "expected_doc": "《防灾避难场所设计规范》GB_51143-2015",
    },
    {
        "id": 3,
        "question": "锅炉房与周边建筑物、构筑物的防火间距要求是什么？",
        "category": "防火规范",
        "expected_doc": "《锅炉房设计标准》GB_50041-2020",
    },
    {
        "id": 4,
        "question": "饮食建筑的厨房与餐厅的面积比例有哪些规定？加工间的卫生要求是什么？",
        "category": "饮食建筑",
        "expected_doc": "《饮食建筑设计标准》JGJ_64-2017",
    },
    {
        "id": 5,
        "question": "铁路旅客车站候车室的设计要求，包括面积指标和疏散通道宽度是如何规定的？",
        "category": "铁路建筑",
        "expected_doc": "《铁路旅客车站设计规范》TB_10100-2018",
    },
]


async def run_vector_search(client: httpx.AsyncClient, kb_id: int, query: str, top_k: int = 5, threshold: float = 0.3):
    payload = {"kb_id": kb_id, "query": query, "top_k": top_k, "threshold": threshold}
    t0 = time.time()
    resp = await client.post(f"{BASE_URL}/api/rag/search", json=payload)
    elapsed = int((time.time() - t0) * 1000)
    data = resp.json()
    return data.get("data", []), elapsed, payload


async def run_fulltext_search(client: httpx.AsyncClient, kb_id: int, query: str, limit: int = 10):
    payload = {"query": query, "limit": limit, "offset": 0}
    t0 = time.time()
    resp = await client.post(f"{BASE_URL}/api/rag/meilisearch/search/{kb_id}", json=payload)
    elapsed = int((time.time() - t0) * 1000)
    data = resp.json()
    return data.get("data", {}), elapsed, payload


async def run_compare_search(client: httpx.AsyncClient, kb_id: int, query: str, top_k: int = 5):
    payload = {"query": query, "top_k": top_k}
    t0 = time.time()
    resp = await client.post(f"{BASE_URL}/api/rag/meilisearch/compare/{kb_id}", json=payload)
    elapsed = int((time.time() - t0) * 1000)
    data = resp.json()
    return data.get("data", {}), elapsed


async def run_context_search(
    client: httpx.AsyncClient,
    kb_id: int,
    query: str,
    top_k: int = 5,
    threshold: float = 0.3,
    enhance: bool = True,
    strategies: list = None,
    max_depth: int = 1,
):
    payload = {
        "kb_id": kb_id,
        "query": query,
        "top_k": top_k,
        "threshold": threshold,
        "enhance": enhance,
        "strategies": strategies or ["siblings", "children"],
        "max_depth": max_depth,
    }
    t0 = time.time()
    resp = await client.post(f"{BASE_URL}/api/rag/search/context", json=payload)
    elapsed = int((time.time() - t0) * 1000)
    data = resp.json()
    return data.get("data", {}).get("context", ""), elapsed, payload


async def call_llm(question: str, context: str) -> tuple[str, str, int]:
    """直接调用豆包API (OpenAI compatible)，返回(system_prompt, user_prompt, answer, elapsed_ms)"""
    system_prompt = (
        "你是一位专业的建筑规范解读专家。请根据提供的规范文献原文，准确、专业地回答用户的问题。\n"
        "回答要求：\n"
        "1. 必须基于提供的规范原文进行回答，不得凭空捏造规范内容\n"
        "2. 引用具体条款时请注明条款编号\n"
        "3. 如果原文中没有明确答案，请诚实说明\n"
        "4. 回答要结构清晰，重点突出"
    )
    user_prompt = (
        f"请根据以下建筑规范文献，回答用户的问题。\n\n"
        f"【参考规范原文】\n{context}\n\n"
        f"【用户问题】\n{question}\n\n"
        f"请基于以上规范原文给出专业、准确的回答："
    )

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "stream": False,
    }

    t0 = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{DOUBAO_BASE_URL}/chat/completions", headers=headers, json=payload)
    elapsed = int((time.time() - t0) * 1000)

    data = resp.json()
    answer = ""
    if "choices" in data and data["choices"]:
        answer = data["choices"][0].get("message", {}).get("content", "")
    elif "error" in data:
        answer = f"[API错误] {data['error']}"

    usage = data.get("usage", {})

    return system_prompt, user_prompt, answer, elapsed, usage


async def test_question(client: httpx.AsyncClient, q: dict) -> dict:
    print(f"\n{'='*80}")
    print(f"[问题 {q['id']}] {q['question']}")
    print(f"{'='*80}")

    result = {
        "id": q["id"],
        "question": q["question"],
        "category": q["category"],
        "expected_doc": q["expected_doc"],
        "timestamp": datetime.now().isoformat(),
        "tests": {},
    }

    # ── 1. 向量搜索 ─────────────────────────────────────────────────
    print(f"\n[1] 向量搜索 (top_k=5, threshold=0.3)...")
    vec_results, vec_ms, vec_params = await run_vector_search(client, KB_ID, q["question"], top_k=5, threshold=0.3)
    print(f"    耗时: {vec_ms}ms | 结果数: {len(vec_results)}")
    for i, r in enumerate(vec_results[:3]):
        score = r.get("score", r.get("_distance", "?"))
        content_preview = r.get("content", "")[:100].replace("\n", " ")
        doc_id = r.get("doc_id", "?")
        print(f"    [{i+1}] score={score:.4f} | doc_id={doc_id} | {content_preview}")

    result["tests"]["vector"] = {
        "method": "向量搜索（LanceDB cosine similarity）",
        "params": vec_params,
        "elapsed_ms": vec_ms,
        "result_count": len(vec_results),
        "results": vec_results,
    }

    # ── 2. 全文搜索 ─────────────────────────────────────────────────
    print(f"\n[2] 全文搜索 (Meilisearch, limit=10)...")
    ft_data, ft_ms, ft_params = await run_fulltext_search(client, KB_ID, q["question"], limit=10)
    ft_hits = ft_data.get("hits", []) if isinstance(ft_data, dict) else []
    print(f"    耗时: {ft_ms}ms | 命中数: {len(ft_hits)}")
    for i, h in enumerate(ft_hits[:3]):
        content_preview = h.get("content", "")[:100].replace("\n", " ")
        doc_id = h.get("doc_id", "?")
        print(f"    [{i+1}] doc_id={doc_id} | {content_preview}")

    result["tests"]["fulltext"] = {
        "method": "全文搜索（Meilisearch BM25）",
        "params": ft_params,
        "elapsed_ms": ft_ms,
        "result_count": len(ft_hits),
        "results": ft_data,
    }

    # ── 3. 比较搜索 ──────────────────────────────────────────────────
    print(f"\n[3] 比较搜索（向量 vs 全文 vs 混合 RRF）...")
    cmp_data, cmp_ms = await run_compare_search(client, KB_ID, q["question"], top_k=5)
    total_time = cmp_data.get("total_time", cmp_ms)
    hybrid_results = cmp_data.get("hybrid", [])
    print(f"    总耗时: {total_time}ms | 向量={len(cmp_data.get('vector',[]))} | 全文={len(cmp_data.get('meilisearch',[]))} | 混合={len(hybrid_results)}")

    result["tests"]["compare"] = {
        "method": "比较搜索（向量 + Meilisearch + RRF融合）",
        "elapsed_ms": total_time,
        "vector_count": len(cmp_data.get("vector", [])),
        "fulltext_count": len(cmp_data.get("meilisearch", [])),
        "hybrid_count": len(hybrid_results),
        "results": cmp_data,
    }

    # ── 4. 高级搜索（含上下文拓展）──────────────────────────────────
    print(f"\n[4] 高级搜索（hybrid + 上下文拓展: siblings+children, max_depth=1）...")
    context, ctx_ms, ctx_params = await run_context_search(
        client, KB_ID, q["question"],
        top_k=5, threshold=0.3, enhance=True,
        strategies=["siblings", "children"], max_depth=1,
    )
    ctx_len = len(context)
    print(f"    耗时: {ctx_ms}ms | Context长度: {ctx_len}字符")
    # 打印完整context（截断到前600字符预览）
    print(f"\n    --- Context预览（前600字符）---")
    print(context[:600])
    print(f"    --- Context结束 ---")

    result["tests"]["advanced"] = {
        "method": "高级搜索（hybrid RRF + 树状上下文拓展）",
        "params": ctx_params,
        "elapsed_ms": ctx_ms,
        "context_length": ctx_len,
        "context_full": context,
    }

    # ── 5. LLM调用 ──────────────────────────────────────────────────
    print(f"\n[5] 调用豆包Pro LLM ({DOUBAO_MODEL})...")
    if context.strip():
        system_prompt, user_prompt, answer, llm_ms, usage = await call_llm(q["question"], context)
        print(f"    LLM耗时: {llm_ms}ms | 答案长度: {len(answer)}字符")
        print(f"    Token用量: {usage}")
        print(f"\n    【完整prompt - system】\n{system_prompt}")
        print(f"\n    【完整prompt - user】\n{user_prompt[:500]}...")
        print(f"\n    【LLM完整答案】\n{answer}")
    else:
        system_prompt = user_prompt = "(Context为空)"
        answer = "(Context为空，未调用LLM)"
        llm_ms = 0
        usage = {}
        print("    Context为空，跳过LLM调用")

    result["llm"] = {
        "model": f"豆包Pro ({DOUBAO_MODEL})",
        "elapsed_ms": llm_ms,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "answer": answer,
        "answer_length": len(answer),
        "usage": usage,
    }

    return result


async def main():
    print("=" * 80)
    print("RAG 检索能力测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"知识库: KB {KB_ID} - 建筑规范库 (427文档, 37822 chunks)")
    print(f"LLM: 豆包Pro ({DOUBAO_MODEL})")
    print(f"搜索参数: top_k=5, threshold=0.3, enhance=True, strategies=[siblings,children], max_depth=1")
    print("=" * 80)

    all_results = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for q in TEST_QUESTIONS:
            try:
                result = await test_question(client, q)
                all_results.append(result)
            except Exception as e:
                print(f"\n[错误] 问题 {q['id']} 测试失败: {e}")
                import traceback
                traceback.print_exc()
                all_results.append({"id": q["id"], "question": q["question"], "error": str(e)})

    # 保存完整结果
    output_path = "rag_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*80}")
    print(f"测试完成！完整结果已保存到: {output_path}")
    print(f"共测试 {len(all_results)} 个问题")
    print("=" * 80)

    return all_results


if __name__ == "__main__":
    asyncio.run(main())
