# Upgrade runbook: release 1.0 → 1.1 (operator at customer site)

## What changes

| Component | 1.0 | 1.1 |
|---|---|---|
| k3s | v1.30.4+k3s1 | v1.31.5+k3s1 |
| PostgreSQL | 16.4 | 17.2 (major upgrade, dump/restore) |
| Qdrant | v1.11.3 | v1.12.4 |
| LiteLLM | v1.51.1 | v1.55.0 |
| Embedding model | paraphrase-multilingual-MiniLM-L12-v2 | intfloat/multilingual-e5-small |
| Qdrant collection | documents_v1 | documents_v2 (alias `documents` switches) |
| OS patching | no | yes (reboot only if required) |

Chat model, LiteLLM aliases (`onprem-chat`, `onprem-embed`) and the
`documents` collection alias are **unchanged** — applications see no
difference.

## Expected downtime

- **Single-node staging:** ~2–5 minutes total (k3s restart + postgres
  recreate + TEI model download). Qdrant/LiteLLM roll without downtime.
- **Multi-node prod:** near-zero for stateless services; postgres recreate
  causes a short write pause (seconds). OS patching reboots one node at a
  time (`serial: 1`), workloads stay up on the other nodes.

## Steps

```bash
# 1. Pre-flight + backup happen automatically inside upgrade.yml.
#    To take a manual backup first:
ansible-playbook -i inventories/staging playbooks/backup.yml -e release=1.0

# 2. Run the upgrade
ansible-playbook -i inventories/staging playbooks/upgrade.yml -e release=1.1
```

The playbook, in order:

1. **Pre-flight** — disk >5 GB free, all nodes Ready, deployments available.
   Stops immediately if a check fails.
2. **Backup** — `pg_dump -Fc` of LiteLLM DB + Qdrant snapshot of
   `documents_v1`, verified (`pg_restore -l`, non-empty).
3. **OS patching** — security updates; node drained, rebooted **only** if
   `/var/run/reboot-required` exists, uncordoned, verified Ready.
4. **k3s upgrade** — installer with pinned `INSTALL_K3S_VERSION`.
5. **Postgres 16→17** — scale to 0, delete deployment+PVC, deploy fresh
   pg17, `pg_restore --clean`. Verified by counting public tables.
6. **Component updates** — Qdrant, Ollama, TEI (now serves e5-small),
   LiteLLM. All via idempotent `kubectl apply`.
7. **Data migration** — create `documents_v2`, re-embed all 20 docs through
   the NEW model, **verify** (20 points + both acceptance queries return the
   expected doc in top 3), then atomically move alias `documents` →
   `documents_v2`. `documents_v1` is kept.
8. **Smoke test** — chat + embeddings + Qdrant alias check.

## How to check success

- Playbook ends with `SMOKE TEST PASSED`.
- `kubectl get pods -n ai-platform` — all Running.
- `kubectl exec -n ai-platform deploy/litellm -- python3 /tmp/smoke.py`
- Both LiteLLM API keys (created on 1.0) still work — they live in Postgres,
  which was restored.
- Acceptance queries through the `documents` alias return s07 / s01 top-3.

## Rollback

```bash
ansible-playbook -i inventories/staging playbooks/rollback.yml -e release=1.0
```

- Alias switches back to `documents_v1` (still present).
- Images re-applied with 1.0 pins.
- Postgres is restored from the pre-upgrade dump into a fresh pg16 PVC.
- **Honest limits:** LiteLLM writes made *during* the 1.1 window are lost
  (they were in pg17). OS security patches are not reverted. k3s downgrade
  is supported by the installer but test it — we recommend fixing forward
  for k3s if the cluster is healthy.
