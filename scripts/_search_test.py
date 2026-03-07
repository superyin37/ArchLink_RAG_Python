# -*- coding: utf-8 -*-
"""
对 Qwen KB 执行 issue #001 中的 5 个测试查询，验证向量搜索是否正常
"""
import asyncio, os, sys
import httpx

BASE_URL = "http://localhost:4001"

QUERIES = [
    ("\u5730\u4e0b\u5de5\u7a0b\u9632\u6c34\u7b49\u7ea7\u5212\u5206", 193),   # 地下工程防水等级划分 -> doc 193
    ("\u9632\u707e\u907f\u96be\u573a\u6240\u8d23\u4efb\u533a\u9762\u79ef", 426),  # 防灾避难场所责任区面积 -> doc 426
    ("\u9505\u7089\u623f\u9632\u706b\u95f4\u8ddd", 424),              # 锅炉房防火间距 -> doc 424
    ("\u996e\u98df\u5efa\u7b51\u53a8\u623f\u9762\u79ef\u6bd4\u4f8b", 429),   # 饮食建筑厨房面积比例 -> doc 429
    ("\u94c1\u8def\u5019\u8f66\u5ba4\u8bbe\u8ba1\u8981\u6c42", 420),         # 铁路候车室设计要求 -> doc 420
]

KB_ID = 2


async def search_query(client: httpx.AsyncClient, query: str, expected_doc_id: int) -> dict:
    resp = await client.post(f"{BASE_URL}/api/rag/search", json={
        "kb_id": KB_ID,
        "query": query,
        "search_type": "vector",
        "top_k": 5,
        "threshold": 0.0,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    raw = data.get("data", [])
    results = raw if isinstance(raw, list) else raw.get("results", [])
    top1 = results[0] if results else {}
    hit = any(r.get("doc_id") == expected_doc_id for r in results[:5])
    return {
        "query": query,
        "expected_doc": expected_doc_id,
        "top1_doc": top1.get("doc_id"),
        "top1_score": top1.get("score"),
        "top5_hit": hit,
        "results": [(r.get("doc_id"), round(r.get("score", 0), 4)) for r in results[:5]],
    }


async def main():
    print("=== issue #001 向量搜索验证 (Qwen text-embedding-v4, KB=1) ===\n")
    async with httpx.AsyncClient() as client:
        tasks = [search_query(client, q, d) for q, d in QUERIES]
        results = await asyncio.gather(*tasks)

    hits = 0
    for r in results:
        status = "HIT" if r["top5_hit"] else "MISS"
        if r["top5_hit"]:
            hits += 1
        print(f"[{status}] {r['query']}")
        print(f"       expected=doc{r['expected_doc']}  top1=doc{r['top1_doc']}(score={r['top1_score']})")
        print(f"       top5: {r['results']}")
        print()

    print(f"结果: {hits}/{len(QUERIES)} 命中 (threshold=0.0, top_k=5)")


asyncio.run(main())
