#!/usr/bin/env python3
"""Ensure the release's Qdrant collection exists and the stable alias points to it.

Idempotent. Runs inside the litellm pod.
Env: QDRANT_URL, QDRANT_COLLECTION, COLLECTION_ALIAS
"""
import json
import os
import urllib.request
import urllib.error

QDRANT = os.environ["QDRANT_URL"].rstrip("/")
COLLECTION = os.environ["QDRANT_COLLECTION"]
ALIAS = os.environ["COLLECTION_ALIAS"]
VECTOR_SIZE = 384


def qdrant(method, path, payload=None):
    req = urllib.request.Request(
        f"{QDRANT}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    try:
        qdrant("GET", f"/collections/{COLLECTION}")
        print(f"collection '{COLLECTION}' exists")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        qdrant("PUT", f"/collections/{COLLECTION}", {
            "vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}
        })
        print(f"created collection '{COLLECTION}'")

    if os.environ.get("SET_ALIAS", "1") != "1":
        print(f"alias '{ALIAS}' left unchanged (SET_ALIAS=0)")
        return

    # Point the stable alias at this release's collection. On 409 (alias
    # already exists) delete it first so re-runs and release switches work.
    try:
        qdrant("POST", "/collections/aliases", {
            "actions": [{"create_alias": {"collection_name": COLLECTION, "alias_name": ALIAS}}]
        })
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        qdrant("POST", "/collections/aliases", {
            "actions": [
                {"delete_alias": {"alias_name": ALIAS}},
                {"create_alias": {"collection_name": COLLECTION, "alias_name": ALIAS}},
            ]
        })
    print(f"alias '{ALIAS}' -> '{COLLECTION}'")


if __name__ == "__main__":
    main()
