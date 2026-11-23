# Project Brief — Interview Task: Ansible IaC for an On-Prem, Air-Gapped AI Platform

> Purpose of this document: a complete, self-contained summary of the delivered project.
> Feed this to an AI presentation tool to generate a rich slide deck.

---

## 1. The Challenge

Build infrastructure-as-code (Ansible) that manages the **entire lifecycle** of a private AI platform running **inside a customer data centre — often with NO internet access (air-gapped)**.

The platform must support:

- **First deployment** of release 1.0 on a clean Ubuntu VM
- **OS security patching** (reboot only when required)
- **Platform + component upgrades** (k3s, Postgres major version, Qdrant, LiteLLM)
- **Data migrations** (embedding model change → re-embedding with zero reader downtime)
- **Backups and a tested rollback path**
- **An original life-cycle scenario** of our own design

Time box: ~1–1.5 working days. Deliverable: a Git repo another engineer can run, re-run, and trust.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| IaC | **Ansible 2.16+** | Agentless, idempotent, industry standard for on-prem |
| Kubernetes | **k3s** (single-node staging, multi-node-ready design) | Lightweight k8s; task explicitly asked for it |
| LLM serving | **Ollama** (`qwen2.5:0.5b-instruct`, ~400 MB) | OpenAI-compatible chat API, CPU-friendly |
| Embeddings | **Hugging Face TEI** (text-embeddings-inference 1.6, CPU) | Production-grade embeddings API |
| Vector DB | **Qdrant** | Persistent volumes + native snapshots + collection aliases |
| API Gateway | **LiteLLM** | One API-key-protected endpoint for chat + embeddings |
| Database | **PostgreSQL** (16 → 17 major upgrade) | LiteLLM state: keys, spend, usage |
| Registry | **registry:2.8.3** local registry | Sole image source for air-gapped sites |
| GPU support | NVIDIA driver + container toolkit + k8s device plugin | Auto-detected, skipped on CPU nodes |

---

## 3. Architecture

```
                    Client Application
                           │  (single API key)
                           ▼
                    ┌─────────────┐
                    │  LiteLLM    │──────────► PostgreSQL
                    │  Gateway    │            (keys, usage, spend)
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        Ollama (chat)              TEI (embeddings)
        qwen2.5:0.5b               MiniLM-L12-v2 → e5-small
                                           │
                                           ▼
                                     Qdrant ── alias "documents"
                                     (documents_v1 → documents_v2)

        Local Registry (registry:2.8.3) = ONLY image source when airgapped=true
        Everything runs on k3s, namespace "ai-platform", all versions pinned
```

**Application contract (never changes between releases):**
- Chat model alias: `onprem-chat`
- Embedding model alias: `onprem-embed`
- Qdrant collection alias: `documents` — apps never see physical collection names

---

## 4. Repository Structure

```
imp/
├── stack-spec.yaml                  # Task spec: two releases 1.0 → 1.1
├── seed/documents.jsonl             # 20 short texts (Arabic + English) for RAG testing
└── ai-stack/                        # The Ansible project
    ├── site.yml                     # Entry point: full deployment of one release
    ├── ansible.cfg                  # inventories/staging default, yaml output
    ├── requirements.yml             # collections
    ├── group_vars/
    │   ├── all.yml                  # ALL pinned versions, images, models, contract, paths
    │   ├── all/vault.yml            # Encrypted secrets (Ansible Vault)
    │   └── releases/
    │       ├── 1.0.yml              # Release 1.0 pins (pg16, qdrant v1.11.3, litellm v1.51.1…)
    │       └── 1.1.yml              # Release 1.1 pins (pg17, qdrant v1.12.4, litellm v1.55.0…)
    ├── inventories/
    │   ├── staging/                 # 1 node, replicas=1, airgapped=false
    │   └── prod/                    # replicas=2, airgapped=true
    ├── playbooks/
    │   ├── backup.yml               # Pre-flight checks + pg_dump + Qdrant snapshots
    │   ├── os-patch.yml             # Security updates, serial:1, reboot only if required
    │   ├── upgrade.yml              # THE upgrade orchestrator (1.0 → 1.1)
    │   ├── rollback.yml             # Full rollback to 1.0 with honest limits
    │   ├── rotate-secrets.yml       # OWN SCENARIO: zero-downtime credential rotation
    │   ├── seed-data.yml            # Load 20 docs + create 2 LiteLLM API keys
    │   ├── bundle-build.yml         # Build offline air-gap bundle (images+models+checksums)
    │   └── bundle-load.yml          # Load bundle on disconnected site
    ├── roles/                       # One role per component
    │   ├── common/                  # Base OS setup
    │   ├── k3s/                     # Pinned k3s install, namespace, kubectl symlinks
    │   ├── registry/                # Local image registry
    │   ├── database/                # Postgres deployment + PVC + secret
    │   ├── model_server/            # Ollama + chat model
    │   ├── embeddings/              # HF TEI + embedding model
    │   ├── vector_db/               # Qdrant + PVC
    │   ├── gateway/                 # LiteLLM deployment + config
    │   ├── gpu/                     # NVIDIA auto-detect → driver, toolkit, device plugin
    │   └── smoke_test/              # End-to-end verification after EVERY operation
    ├── scripts/                     # Python helpers run INSIDE the litellm pod
    │   ├── ensure_collection.py     # Create collection + move alias (SET_ALIAS=0/1 modes)
    │   ├── seed_documents.py        # Embed + upsert documents into Qdrant
    │   ├── verify_reembed.py        # Verify 20 docs + acceptance queries BEFORE alias switch
    │   └── create_keys.py           # Create LiteLLM API keys via master key
    └── docs: README.md, UPGRADE-1.0-to-1.1.md, SCENARIO.md, AI_USAGE.md
```

---

## 5. Key Design Decisions (the "why" — interview gold)

1. **Releases are data, not code** — `group_vars/releases/1.0.yml` and `1.1.yml` pin every image, model, and collection. Upgrading = changing which file is loaded via `-e release=1.1`. No `latest` anywhere.

2. **kubectl apply over Helm** — plain manifests are naturally idempotent, fully pinned, fewer moving parts for a small platform.

3. **Postgres 16→17 via `pg_dump -Fc` / `pg_restore`** — rejected `pg_upgrade` because it requires identical filesystem layout and binary paths inside the container, which breaks across image changes. Dump/restore is portable, verifiable (`pg_restore -l`), and simple to repeat in BOTH directions (upgrade AND rollback).

4. **Qdrant collection alias for the embedding-model change** — release 1.1 swaps `paraphrase-multilingual-MiniLM-L12-v2` for `intfloat/multilingual-e5-small`. Old vectors are INVALID. Instead of touching live data: create `documents_v2` → re-embed all 20 docs with the NEW model → VERIFY (count + acceptance queries) → atomically move alias `documents` → readers never see downtime → keep `documents_v1` for rollback/forensics.

5. **Secrets: Ansible Vault → k8s Secrets** — never rendered into manifest files, `no_log: true` everywhere secrets appear, generated keys written to mode-600 git-ignored files for the operator to move into the vault.

6. **Smoke tests run inside the litellm pod** — it already has Python + cluster DNS, so no extra images or port-forwards needed. Runs after EVERY deploy, upgrade, rollback, seed, and rotation.

7. **`serial: 1` OS patching** — one node at a time: patch → drain → reboot ONLY if `/var/run/reboot-required` exists → uncordon → verify Ready. Cluster always keeps N-1 healthy nodes.

8. **GPU role auto-skips** — detects NVIDIA via `nvidia-smi`/`lspci` ON THE TARGET (not controller-side), installs driver + container toolkit + device plugin only when a GPU exists.

---

## 6. The Upgrade Flow (1.0 → 1.1) — `playbooks/upgrade.yml`

Deliberate ordering, documented in the file:

```
1. Pre-flight + Backup          — disk >5GB, all nodes Ready, deployments available.
                                  pg_dump -Fc + Qdrant snapshot. STOP if checks fail.
2. OS Patching (serial:1)       — BEFORE k3s so the node reboots only ONCE.
3. k3s upgrade                  — platform first; pods keep running during API restart.
4. Postgres 16 → 17             — detect current major → scale 0 → delete deploy+PVC
                                  → deploy fresh pg17 → pg_restore --clean → verify tables.
5. Component images             — Qdrant v1.12.4, LiteLLM v1.55.0, TEI (new model).
                                  Stateless services roll with zero downtime.
6. Data migration               — create documents_v2 (SET_ALIAS=0) → re-embed 20 docs
                                  with NEW model → verify_reembed.py → SET_ALIAS=1
                                  (atomic switch) → keep documents_v1.
7. Smoke test                   — chat + embeddings + Qdrant alias check end-to-end.
```

**Expected downtime (honest):** ~2–5 min single-node staging; near-zero for stateless services on multi-node prod; seconds of write pause during Postgres recreate.

---

## 7. Rollback — `playbooks/rollback.yml`

- Finds the NEWEST backup automatically
- Switches `documents` alias back to `documents_v1` (never deleted)
- Reverses Postgres 17→16 with the same dump/restore procedure
- Re-applies ALL release-1.0 manifests (images roll back via kubectl)
- Re-runs smoke test

**Honest limits (documented in code + runbook):**
- LiteLLM writes made DURING the 1.1 window are LOST (they lived in pg17)
- OS security patches are NOT reverted (would reintroduce CVEs — accepted risk)
- k3s downgrade supported by installer but "fix forward" recommended if cluster is healthy

---

## 8. Own Scenario — Zero-Downtime Secret Rotation (`rotate-secrets.yml` + `SCENARIO.md`)

**Why this scenario:** credential rotation is a routine real on-prem operation (CVE response, staff turnover, compliance audit). Done wrong = self-inflicted outage. Exercises secrets management + rolling restarts + verification end-to-end.

**How it works:**
1. Generate new random Postgres password + LiteLLM master key (`lookup('password')`, `no_log`)
2. `ALTER USER ... WITH PASSWORD` inside Postgres — ONLINE, existing connections survive
3. Update k8s Secrets `postgres-credentials` + `litellm-credentials`
4. `kubectl rollout restart deploy/litellm` — pods come up one at a time; replicas=2 in prod = **zero downtime** (1 replica staging = few seconds, stated honestly)
5. Write rotated values to `rotated-secrets.json` (mode 600, git-ignored) → operator moves them into Vault
6. Smoke test proves chat + embeddings work with the NEW key

**The documented trap:** if the vault isn't updated, the next `site.yml` run silently REVERTS the rotation — the playbook's final debug message warns about exactly this.

---

## 9. Air-Gapped Support

- **`bundle-build.yml`** (run on internet-connected machine): `docker save` every pinned image + pull Ollama model into bundle + HF snapshot of embedding model + pinned k3s binary + `SHA256SUMS` for everything
- **`bundle-load.yml`** (run on disconnected site): verify checksums → `docker load` + tag + push to local registry → install k3s from bundle → seed model stores into PVCs
- Result: the air-gapped site runs the IDENTICAL system with zero internet

---

## 10. Quality & Verification

- **Idempotency:** second run of any playbook reports `0 changed`; `--check` clean. Achieved via `kubectl apply`, version checks before install, explicit `changed_when`/`failed_when` on every task.
- **Smoke test** (`smoke.py` rendered from `smoke.py.j2`): chat completion through LiteLLM + embedding call + Qdrant search — fails with a clear message.
- **Acceptance queries after upgrade:** Arabic query `حد السحب اليومي من الصراف الآلي` must return doc s07 top-3; `password minimum length` must return doc s01 top-3 — both through the stable `documents` alias.
- **CI:** lint + syntax check file included.
- **`ansible-lint` clean.**

---

## 11. Documentation Deliverables

- `ai-stack/README.md` — prerequisites, deploy/upgrade/rollback instructions (must be enough to run on a fresh VM)
- `UPGRADE-1.0-to-1.1.md` — operator runbook: what changes (version table), expected downtime, steps, success checks, rollback
- `SCENARIO.md` — own scenario explanation
- `AI_USAGE.md` — honest AI usage report: what AI generated vs. what I decided/rejected

---

## 12. AI Usage (honest report — required by task)

- **Tools:** Cascade (Windsurf AI assistant) generated skeleton, roles, templates, scripts, docs
- **Decisions I own and can defend:** k3s+manifests over Helm · dump/restore over pg_upgrade · Qdrant alias over rename · secrets in Vault+k8s Secrets (fixed AI's first draft that embedded the DB password) · scripts run inside litellm pod · serial:1 patching · secret rotation as own scenario
- **Rejected/fixed AI output:** broken Jinja air-gap loader → explicit image→key map · fragile `lookup('k8s')` → `kubectl jsonpath` · GPU detection moved from controller to target · added `SET_ALIAS=0` mode for safe pre-switch collection creation
- **Known limitations (stated honestly):** versions pinned but pending fresh-VM validation · TEI first-boot model download is slow (air-gap bundle pre-seeds HF cache) · bundle-load assumes docker present · .pptx deck produced separately

---

## 13. Pinned Versions (release 1.0 → 1.1)

| Component | 1.0 | 1.1 |
|---|---|---|
| k3s | v1.30.4+k3s1 | v1.31.5+k3s1 |
| PostgreSQL | 16.4 | 17.2 (major, dump/restore) |
| Qdrant | v1.11.3 | v1.12.4 |
| LiteLLM | v1.51.1 | v1.55.0 |
| Ollama | 0.5.4 | 0.5.4 (unchanged) |
| TEI | 1.6 | 1.6 (unchanged image, new model) |
| Embedding model | paraphrase-multilingual-MiniLM-L12-v2 (384d) | intfloat/multilingual-e5-small (384d, incompatible vectors) |
| Qdrant collection | documents_v1 | documents_v2 (alias switches) |
| OS patching | off | on (reboot only if required) |

---

## 14. What I Learned (slide 8 material)

- **Lifecycle ≠ deployment** — the real product is backups, migrations, rollback, and honest runbooks
- **Aliases beat renames** — applications never need to know something changed (Qdrant alias, LiteLLM model aliases)
- **Idempotency is a design constraint**, not an afterthought — it shapes every task
- **Honest rollback docs build more trust** than perfect-uptime claims
- **AI accelerates but doesn't decide** — every architectural choice is owned and defensible
- **Next step:** multi-node OKD + GPUs — `serial: 1` patching already designed for it, GPU role ready, replicas=2 in prod

---

## 15. Presentation Notes for the Deck

- **Slide count:** 8 slides, ~10 minute talk
- **Slide 1:** Title — "Lifecycle IaC for an On-Prem, Air-Gapped AI Platform"
- **Slide 2:** Architecture diagram (section 3)
- **Slide 3:** IaC design — roles, inventories, group_vars, releases-as-data, Vault
- **Slide 4:** Deployment done right — idempotency, air-gap bundle, smoke tests
- **Slide 5:** THE UPGRADE — ordered pipeline + alias-switch diagram (the money slide)
- **Slide 6:** Own scenario — zero-downtime secret rotation
- **Slide 7:** What broke / AI usage / honest limitations
- **Slide 8:** What I learned + next steps (OKD multi-node + GPU)

**Tone for the talk:** confident but honest — emphasize decisions and trade-offs, not just features. The evaluation rubric weights: Life cycle 35% · Deployment design 20% · Secrets/air-gap 15% · Quality 10% · Scenario+presentation+explainability 20%.
