#!/usr/bin/env python3
"""Verify a freshly re-embedded Qdrant collection BEFORE switching the alias.

Runs the two acceptance queries from stack-spec.yaml directly against the
physical collection (not the alias), and checks the expected doc is top-3.

Env: LITELLM_MASTER_KEY, EMBED_ALIAS, QDRANT_URL, QDRANT_COLLECTION
Exit 0 = verified. Exit 1 = clear error.
"""
import json
import os
import sys
import urllib.request

LITELLM = "http://localhost:4000"
QDRANT = os.environ["QDRANT_URL"].rstrip("/")
COLLECTION = os.environ["QDRANT_COLLECTION"]
MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
EMBED_ALIAS = os.environ["EMBED_ALIAS"]

QUERIES = [
    ("حد السحب اليومي من الصراف الآلي", "s07"),
    ("password minimum length", "s01"),
]


def embed(text):
    req = urllib.request.Request(
        f"{LITELLM}/v1/embeddings",
        data=json.dumps({"model": EMBED_ALIAS, "input": text}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {MASTER_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"][0]["embedding"]


def search(vec, limit=3):
    req = urllib.request.Request(
        f"{QDRANT}/collections/{COLLECTION}/points/search",
        data=json.dumps({"vector": vec, "limit": limit,
                         "with_payload": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["result"]


def main():
    # sanity: collection must have all 20 docs
    with urllib.request.urlopen(f"{QDRANT}/collections/{COLLECTION}", timeout=15) as r:
        count = json.loads(r.read())["result"]["points_count"]
    if count != 20:
        print(f"VERIFY FAILED: '{COLLECTION}' has {count} points, expected 20",
              file=sys.stderr)
        sys.exit(1)

    for query, expected in QUERIES:
        hits = search(embed(query))
        ids = [h["payload"]["doc_id"] for h in hits]
        print(f"query {query!r}: top3={ids}")
        if expected not in ids:
            print(f"VERIFY FAILED: expected '{expected}' in top 3, got {ids}",
                  file=sys.stderr)
            sys.exit(1)

    print("VERIFY PASSED: collection is good, safe to switch alias")


if __name__ == "__main__":
    main()
