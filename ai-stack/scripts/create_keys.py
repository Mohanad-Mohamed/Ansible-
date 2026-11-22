#!/usr/bin/env python3
"""Create the two LiteLLM virtual keys required by the acceptance criteria.

Runs inside the litellm pod. Prints a JSON object with the keys on the
last stdout line; the playbook stores them in a k8s Secret and a local
(git-ignored) file for the operator to move into Ansible Vault.
"""
import json
import os
import urllib.request

LITELLM = "http://localhost:4000"
MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]


def post(path, payload):
    req = urllib.request.Request(
        f"{LITELLM}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {MASTER_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    chat = post("/key/generate", {
        "models": ["onprem-chat"], "key_alias": "app-chat",
        "metadata": {"purpose": "application chat access"},
    })
    embed = post("/key/generate", {
        "models": ["onprem-embed"], "key_alias": "app-embed",
        "metadata": {"purpose": "application embeddings access"},
    })
    print("KEYS_JSON:" + json.dumps({
        "chat_key": chat["key"],
        "embed_key": embed["key"],
    }))


if __name__ == "__main__":
    main()
