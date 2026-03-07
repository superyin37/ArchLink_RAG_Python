# -*- coding: utf-8 -*-
"""
批量上传 uploads/ 目录下所有 .md 文件到指定 KB
用法: python scripts/_batch_upload.py --kb_id 1
"""
import asyncio, os, sys, argparse
import httpx

BASE_URL = "http://localhost:4001"
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
CONCURRENCY = 1  # 串行上传，避免触发 DashScope RPM 限制


async def upload_file(client: httpx.AsyncClient, kb_id: int, filepath: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            files = {"file": (filename, content, "text/markdown")}
            data = {"kb_id": str(kb_id)}
            resp = await client.post(f"{BASE_URL}/api/rag/document/upload", files=files, data=data, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 0:
                return {"ok": True, "file": filename}
            else:
                return {"ok": False, "file": filename, "err": result.get("msg")}
        except Exception as e:
            return {"ok": False, "file": filename, "err": str(e)}


import re
HEX32 = re.compile(r'^[0-9a-f]{32}_')
DOUBLE_HEX32 = re.compile(r'^[0-9a-f]{32}_[0-9a-f]{32}_')


async def main(kb_id: int, ext: str):
    files = [
        os.path.join(UPLOAD_DIR, f)
        for f in os.listdir(UPLOAD_DIR)
        if f.endswith(ext)
        and not f.startswith(".")
        and HEX32.match(f)           # 必须有 hash 前缀（排除无关文件）
        and not DOUBLE_HEX32.match(f)  # 排除重复副本（双层 hash 前缀）
    ]
    # exclude test file
    files = [f for f in files if "test_doc" not in f]
    print(f"Found {len(files)} files -> KB {kb_id}")

    sem = asyncio.Semaphore(CONCURRENCY)
    ok = fail = 0
    async with httpx.AsyncClient() as client:
        tasks = [upload_file(client, kb_id, f, sem) for f in files]
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            result = await coro
            if result["ok"]:
                ok += 1
            else:
                fail += 1
                print(f"  FAIL: {result['file']} -> {result['err']}")
            if i % 20 == 0 or i == len(files):
                print(f"  Progress: {i}/{len(files)}  ok={ok} fail={fail}")

    print(f"\nDone: ok={ok} fail={fail}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb_id", type=int, default=1)
    parser.add_argument("--ext", default=".md")
    args = parser.parse_args()
    asyncio.run(main(args.kb_id, args.ext))
