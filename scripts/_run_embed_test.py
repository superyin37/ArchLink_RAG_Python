# -*- coding: utf-8 -*-
import asyncio, os, sys, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

spec = importlib.util.spec_from_file_location(
    "qwen", os.path.join(os.path.dirname(__file__), "..", "app", "modules", "rag", "embedding", "qwen.py")
)
qwen_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qwen_mod)
QwenEmbedding = qwen_mod.QwenEmbedding

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import numpy as np

QWEN_API_KEY  = os.getenv("QWEN_API_KEY", "")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_HOST   = os.getenv("DOUBAO_HOST", "")
DOUBAO_MODEL  = os.getenv("DOUBAO_EMBEDDING_MODEL", "")

SAMPLE_TEXTS = [
    "\u5730\u4e0b\u5de5\u7a0b\u9632\u6c34\u7b49\u7ea7\u4e00\u7ea7\u4e0d\u5141\u8bb8\u6e17\u6c34",          # 地下工程防水等级一级不允许渗水
    "\u9505\u7089\u623f\u4e0e\u5efa\u7b51\u7269\u7684\u9632\u706b\u95f4\u8ddd\u8981\u6c42",                # 锅炉房与建筑物的防火间距要求
    "\u5177\u4f53\u76ee\u6807\u52302010\u5e74\u8282\u80fd50%",                                              # 具体目标到2010年节能50%
    "Technical requirements of panel used for assembled buildings",
    "\u9632\u707e\u907f\u96be\u573a\u6240\u7684\u8d23\u4efb\u533a\u9762\u79ef\u4e0d\u5e94\u5927\u4e8e50\u516c\u987f",  # 防灾避难场所的责任区面积不应大于50公顷
    "\u996e\u98df\u5efa\u7b51\u53a8\u623f\u4e0e\u9910\u5385\u7684\u9762\u79ef\u6bd4\u4f8b\u5e94\u7b26\u5408\u89c4\u5b9a",  # 饮食建筑厨房与餐厅的面积比例应符合规定
    "\u94c1\u8def\u65c5\u5ba2\u8f66\u7ad9\u5019\u8f66\u5ba4\u7684\u8bbe\u8ba1\u5e94\u6ee1\u8db3\u65c5\u5ba2\u4f7f\u7528\u9700\u6c42",  # 铁路旅客车站候车室的设计应满足旅客使用需求
    "\u5c45\u4f4f\u533a\u7ef3\u5316\u7387\u4e0d\u5e94\u4f4e\u4e8e30%",                                     # 居住区绿化率不应低于30%
    "The quick brown fox jumps over the lazy dog",
    "\u6d88\u9632\u901a\u9053\u5bbd\u5ea6\u4e0d\u5e94\u5c0f\u4e8e4\u7c73",                                 # 消防通道宽度不应小于4米
]

QUERIES = [
    "\u5730\u4e0b\u5de5\u7a0b\u9632\u6c34\u7b49\u7ea7\u5212\u5206",  # 地下工程防水等级划分
    "\u9632\u707e\u907f\u96be\u573a\u6240\u8d23\u4efb\u533a\u9762\u79ef",  # 防灾避难场所责任区面积
    "\u9505\u7089\u623f\u9632\u706b\u95f4\u8ddd",  # 锅炉房防火间距
]

RELATED = [(0, 0), (1, 4), (2, 1)]
UNRELATED_IDX = 3


def cosine_sim(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def report(model_name, vecs, query_vecs):
    print(f"\n{'='*60}")
    print(f"Model: {model_name}  dim={len(vecs[0])}")
    print(f"{'='*60}")
    sims = [cosine_sim(vecs[i], vecs[j]) for i in range(len(vecs)) for j in range(i+1, len(vecs))]
    sims = np.array(sims)
    print(f"[Pairwise] {len(sims)} pairs")
    print(f"  max={sims.max():.4f}  min={sims.min():.4f}  avg={sims.mean():.4f}  std={sims.std():.4f}")
    print(f"  >0.90:{(sims>0.90).sum()}  >0.85:{(sims>0.85).sum()}  >0.80:{(sims>0.80).sum()}  <0.70:{(sims<0.70).sum()}  <0.50:{(sims<0.50).sum()}")
    print(f"[Query discrimination]")
    margins = []
    labels = ["waterproof/flood", "disaster shelter", "boiler room fire"]
    for idx, (qi, si) in enumerate(RELATED):
        rel   = cosine_sim(query_vecs[qi], vecs[si])
        unrel = cosine_sim(query_vecs[qi], vecs[UNRELATED_IDX])
        m = rel - unrel
        margins.append(m)
        print(f"  Q{qi+1}({labels[idx]}): related={rel:.4f}  unrelated(EN)={unrel:.4f}  margin={m:+.4f}")
    print(f"  avg margin: {np.mean(margins):+.4f}")


async def main():
    print("=== Embedding Anisotropy Test ===")
    qwen = QwenEmbedding(api_key=QWEN_API_KEY, model_id="text-embedding-v4")
    vecs  = await qwen.embed(SAMPLE_TEXTS)
    qvecs = await qwen.embed(QUERIES)
    report("Qwen text-embedding-v4 (DashScope)", vecs, qvecs)

    if DOUBAO_API_KEY:
        spec2 = importlib.util.spec_from_file_location(
            "doubao", os.path.join(os.path.dirname(__file__), "..", "app", "modules", "rag", "embedding", "doubao.py")
        )
        doubao_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(doubao_mod)
        doubao = doubao_mod.DoubaoEmbedding(host=DOUBAO_HOST, api_key=DOUBAO_API_KEY, model_id=DOUBAO_MODEL)
        vecs2  = await doubao.embed(SAMPLE_TEXTS)
        qvecs2 = await doubao.embed(QUERIES)
        report(f"Doubao {DOUBAO_MODEL}", vecs2, qvecs2)


asyncio.run(main())
