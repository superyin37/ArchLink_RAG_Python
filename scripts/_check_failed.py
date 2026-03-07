# -*- coding: utf-8 -*-
import urllib.request, json
from collections import Counter

BASE = "http://localhost:4001"
KB_ID = 5

all_docs = []
page = 1
while True:
    req = urllib.request.Request(f"{BASE}/api/rag/document/kb/{KB_ID}?page={page}&page_size=50")
    d = json.loads(urllib.request.urlopen(req).read())
    batch = d["data"]["list"]
    all_docs.extend(batch)
    total = d["data"]["total"]
    if len(all_docs) >= total or not batch:
        break
    page += 1

status_map = {0: "pending", 1: "processing", 2: "completed", 3: "failed"}
counts = Counter(doc["status"] for doc in all_docs)
print(f"Total: {total}, fetched: {len(all_docs)}")
for s, c in sorted(counts.items()):
    print(f"  {status_map.get(s,s)}({s}): {c}")

failed = [doc for doc in all_docs if doc["status"] == 3]
print(f"\nFailed ({len(failed)}):", [d["id"] for d in failed[:20]])
