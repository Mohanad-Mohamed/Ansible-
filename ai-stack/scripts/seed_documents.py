#!/usr/bin/env python3
"""Load seed documents into Qdrant through the LiteLLM embeddings API.

Runs inside the litellm pod. Idempotent: point IDs are deterministic
('doc-<id>'), so re-running upserts the same points.

Env vars (set by the playbook via kubectl exec):
  LITELLM_MASTER_KEY   - gateway master key (already in pod env)
  EMBED_ALIAS          - e.g. onprem-embed
  QDRANT_URL           - e.g. http://qdrant:6333
  QDRANT_COLLECTION    - physical collection name, e.g. documents_v1
  SEED_FILE            - path to documents.jsonl inside the pod
"""
import json
import os
import sys
import urllib.request
import uuid

LITELLM = "http://localhost:4000"
MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
EMBED_ALIAS = os.environ["EMBED_ALIAS"]
QDRANT = os.environ["QDRANT_URL"].rstrip("/")
COLLECTION = os.environ["QDRANT_COLLECTION"]
SEED_FILE = os.environ.get("SEED_FILE", "/tmp/documents.jsonl")
VECTOR_SIZE = 384
BATCH = 8


def post(url, payload, timeout=120):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {MASTER_KEY}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def qdrant(method, path, payload=None):
    req = urllib.request.Request(
        f"{QDRANT}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def ensure_collection():
    try:
        qdrant("GET", f"/collections/{COLLECTION}")
        print(f"collection '{COLLECTION}' exists")
        return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    qdrant("PUT", f"/collections/{COLLECTION}", {
        "vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}
    })
    print(f"created collection '{COLLECTION}' (size={VECTOR_SIZE}, cosine)")


def main():
    docs = [json.loads(l) for l in open(SEED_FILE, encoding="utf-8") if l.strip()]
    print(f"loaded {len(docs)} documents from {SEED_FILE}")
    ensure_collection()

    points = []
    for d in docs:
        r = post(f"{LITELLM}/v1/embeddings",
                 {"model": EMBED_ALIAS, "input": d["text"]})
        vec = r["data"][0]["embedding"]
        points.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"doc-{d['id']}")),
            "vector": vec,
            "payload": {"doc_id": d["id"], "lang": d["lang"], "text": d["text"]},
        })

    for i in range(0, len(points), BATCH):
        qdrant("PUT", f"/collections/{COLLECTION}/points?wait=true",
               {"points": points[i:i + BATCH]})
        print(f"upserted batch {i // BATCH + 1}")

    info = qdrant("GET", f"/collections/{COLLECTION}")
    count = info["result"]["points_count"]
    print(f"DONE: collection '{COLLECTION}' now has {count} points")
    if count < len(docs):
        print("WARNING: point count lower than expected", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
