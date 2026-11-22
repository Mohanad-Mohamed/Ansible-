# Interview task: Ansible infrastructure-as-code for an on-prem AI stack

**Time box:** about 1 to 1.5 working days (8–10 hours). Please submit within 5 days as a Git repo or zip.
**Tools:** Ansible (2.16+), any Linux VM (Ubuntu 24.04 recommended, 4 vCPU / 8 GB RAM is enough). No GPU needed.

## Context

We deliver private AI platforms that run **inside the customer's data centre**, often with no internet access
(air-gapped). Our production platform runs on Kubernetes (OKD) with GPU servers and includes an LLM gateway,
model serving, embeddings, a vector database, speech-to-text, identity and monitoring.

This task is a small version of that platform. We want to see how you write infrastructure as code that another
engineer can run, re-run and trust.

## Goal

Write an Ansible project that manages the **whole life cycle** of a mini AI stack on a **clean Ubuntu VM**:
first deployment, patching, version updates and data migrations, with backups and a rollback path.
Use **k3s** (lightweight Kubernetes) as the cluster; we do not expect OKD here.

`stack-spec.yaml` defines two releases of the stack. You deploy **release 1.0**, put some data in it, then move it
to **release 1.1** without losing data. This is what we do at customer sites several times a year.

| Component | Purpose | Suggested image (CPU) |
|---|---|---|
| k3s | Kubernetes cluster (single node is fine) | k3s installer |
| Local registry | Image source for air-gapped sites | `registry:2` |
| Model server | Small LLM with an OpenAI-compatible API | Ollama or llama.cpp server with a tiny model (≤1B) |
| Embeddings | Text embeddings API | Hugging Face TEI (CPU) with a small multilingual model |
| Vector DB | Vector storage | Qdrant |
| LLM gateway | One API key-protected endpoint for chat and embeddings | LiteLLM |
| Database | Gateway state (keys, usage) | PostgreSQL |

## Requirements

### A. Deployment (release 1.0)
1. **Structure:** roles, an inventory per environment (`staging`, `prod`), and `group_vars` for the differences.
   One entry command, for example `ansible-playbook -i inventories/staging site.yml -e release=1.0`.
2. **Idempotency:** a second run must report **0 changed**, and `--check` must not fail. Use `shell`/`command` only
   when needed, and make them idempotent.
3. **Secrets:** nothing secret in plain text in the repo (Ansible Vault or a justified alternative); not printed in logs.
4. **Pinned versions:** every package, image, chart and model comes from the release definition, never `latest`.
5. **Air-gapped option:** with `airgapped: true`, images come **only** from the local registry. Provide a playbook
   that builds an offline bundle (images + model files + checksums) for a given release, and one that loads it.
6. **Smoke test:** a role that checks a chat call and an embedding call through LiteLLM, and a search in Qdrant.
   It fails with a clear message. It runs after every deployment, upgrade and rollback.

### B. Life cycle (release 1.0 → 1.1)
Before upgrading, load the provided `seed/documents.jsonl` (20 short texts) into Qdrant through the embeddings
API, and create 2 LiteLLM API keys. After the upgrade, both must still exist and work.

7. **Pre-flight and backup:** check disk space and cluster health, and back up PostgreSQL and Qdrant before any
   change. Stop if a check fails.
8. **OS patching:** apply Ubuntu security updates, drain the node, reboot **only if required**, uncordon, and verify.
   Explain how this works one node at a time on a multi-node cluster (`serial`).
9. **Platform and component updates:** upgrade k3s to the 1.1 version, and update the LiteLLM and Qdrant images.
   Order the steps and say why.
10. **Database migration:** PostgreSQL **major version** upgrade (16 → 17) with the data kept (dump/restore or
    `pg_upgrade`; explain your choice).
11. **Data migration:** release 1.1 changes the **embedding model**, so the old vectors are no longer valid.
    Re-embed the documents into a **new** collection, check it, then switch the application to it (for example with
    a Qdrant collection alias) with no downtime for readers. Keep the old collection until the switch is confirmed.
12. **Rollback:** a playbook that returns to release 1.0 if the upgrade fails partway. State honestly what can and
    cannot be rolled back (for example after the database upgrade) and how the backups cover it.
13. **Release notes:** a short `UPGRADE-1.0-to-1.1.md` written for the operator at the customer site: steps,
    expected downtime, how to check success, and how to roll back.

### C. Quality
14. `ansible-lint` clean, and a short CI file (GitHub Actions or GitLab CI) that runs lint and a syntax check.
15. A `gpu` role for NVIDIA nodes (driver check, container toolkit, Kubernetes device plugin) that is skipped
    automatically when there is no GPU. Code review only; you do not need a GPU.

## Your own scenario (required)

Add **one life-cycle event of your own** that happens in real on-prem operations, automate it, and explain it in
`SCENARIO.md`. Examples: renewing internal TLS certificates before they expire, rotating the LiteLLM master key and
the database password with no downtime, adding a second node to the cluster, replacing a failed disk, a CVE in one
image that needs an emergency patch, or a "disaster day" test (node reboot or restore from backup on a new VM).

## Use of AI tools

You may use AI coding assistants. The condition: **you must be able to explain every task, variable and decision
yourself.** In the review session we will ask you to walk through the code and change something live without the
assistant. Add a short `AI_USAGE.md`: which tools you used, for what, and what you changed or rejected.

## Lessons-learned presentation (required)

A **PowerPoint (.pptx) of 5–8 slides** for a 10-minute talk: your design (one diagram), the upgrade flow from 1.0 to
1.1 and its risks, what broke and how you fixed it, what you learned, how you used AI tools, and what you would
change to run this on a multi-node OKD cluster with GPUs.

## Deliverables

The Ansible repo with a README (prerequisites, how to deploy, upgrade and roll back) · logs of: the 1.0 deployment,
a second run with 0 changed, the 1.0 → 1.1 upgrade with smoke tests, and one rollback test ·
`UPGRADE-1.0-to-1.1.md` · `SCENARIO.md` · `AI_USAGE.md` · the `.pptx`.

## How we evaluate

| Area | Weight |
|---|---|
| Life cycle: patching, updates, migrations, rollback, data kept | 35% |
| Deployment design: roles, variables, environments, idempotency | 20% |
| Secrets, pinned versions, air-gapped bundle | 15% |
| Smoke tests, lint, CI, release notes | 10% |
| Own scenario, presentation and ability to explain | 20% |

We will run your project on a fresh VM ourselves (deploy 1.0, load the seed data, upgrade to 1.1, roll back), so
the README must be enough to run it. If you run out of time, a working 1.0 → 1.1 upgrade with a clear
"not finished" list is better than many half-finished parts.
