import asyncio
import sys
import os
import json
import time

sys.path.insert(0, ".")
os.environ.update({
    "MYSQL_HOST": "127.0.0.1", "MYSQL_PORT": "3306", "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "rag_dev_2024", "MYSQL_DB": "rag_system",
    "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "6379",
    "MEILISEARCH_ENABLED": "true", "MEILISEARCH_HOST": "http://127.0.0.1:7700",
    "MEILISEARCH_API_KEY": "masterKey", "JWT_SECRET": "default-secret-change-me",
    "DOUBAO_API_KEY": "d75ec25c-27c4-40f1-8d30-bcd7799ed97c",
    "DOUBAO_HOST": "https://ark.cn-beijing.volces.com",
    "DOUBAO_EMBEDDING_MODEL": "doubao-embedding-large-text-250515",
})

from app.modules.rag.search.providers import VectorSearchProvider, FulltextSearchProvider
from app.modules.rag.search.fusion import SearchFusion
from app.database import async_session
from app.models.rag import KnowledgeBase
from sqlalchemy import select

QUESTIONS = [
    ("Q1", "地下工程防水设计中，防水等级是如何划分的？各等级的防水标准是什么？"),
    ("Q2", "防灾避难场所的责任区面积和服务人口规模有哪些规定？"),
    ("Q3", "锅炉房与周边建筑物、构筑物的防火间距要求是什么？"),
    ("Q4", "饮食建筑的厨房与餐厅的面积比例有哪些规定？加工间的卫生要求是什么？"),
    ("Q5", "铁路旅客车站候车室的设计要求，包括面积指标和疏散通道宽度是如何规定的？"),
]


async def main():
    vp = VectorSearchProvider()
    fp = FulltextSearchProvider()
    all_results = {}

    for qid, query in QUESTIONS:
        print(f"\n{'='*60}", flush=True)
        print(f"{qid}: {query}")

        async with async_session() as db:
            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == 3))
            kb = kb_result.scalar_one()

        t0 = time.time()
        vec = await vp.search(kb, query, top_k=5, threshold=0.3)
        t_vec = int((time.time() - t0) * 1000)

        t1 = time.time()
        ft = await fp.search(3, query, top_k=5)
        t_ft = int((time.time() - t1) * 1000)

        hybrid = SearchFusion.fuse_rrf([vec, ft], 5)

        print(f"\nVECTOR ({t_vec}ms) — {len(vec)} results:")
        for i, r in enumerate(vec[:5], 1):
            preview = r["content"][:60].replace("\n", " ")
            print(f"  {i}. score={r['score']} doc_id={r['doc_id']} | {preview}")

        print(f"\nFULLTEXT ({t_ft}ms) — {len(ft)} results:")
        for i, r in enumerate(ft[:5], 1):
            preview = r["content"][:60].replace("\n", " ")
            print(f"  {i}. doc_id={r['doc_id']} | {preview}")

        print(f"\nHYBRID (RRF):")
        for i, r in enumerate(hybrid[:5], 1):
            preview = r["content"][:60].replace("\n", " ")
            print(f"  {i}. score={r['score']:.4f} doc_id={r['doc_id']} src={r.get('source','?')} | {preview}")

        all_results[qid] = {
            "query": query,
            "vector": [{"score": r["score"], "doc_id": r["doc_id"], "content": r["content"][:120]} for r in vec],
            "fulltext": [{"doc_id": r["doc_id"], "content": r["content"][:120]} for r in ft],
            "hybrid": [{"score": r["score"], "doc_id": r["doc_id"], "source": r.get("source"), "content": r["content"][:120]} for r in hybrid],
            "t_vec_ms": t_vec,
            "t_ft_ms": t_ft,
        }

    with open("/tmp/test_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\n\nSaved to /tmp/test_results.json")


asyncio.run(main())
