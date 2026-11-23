# Mini on-prem AI stack — Ansible IaC

Manages the full life cycle of a small private AI platform on k3s:
deploy → seed → patch → upgrade 1.0→1.1 (with data migration) → rollback.

## Architecture

```
                 ┌────────────────────────── k3s (ai-platform ns) ──────────────────────────┐
  apps ──HTTP──▶ │  LiteLLM gateway :4000  (API keys, model aliases onprem-chat/onprem-embed) │
                 │      ├──▶ Ollama :11434      (chat model qwen2.5:0.5b-instruct, PVC)      │
                 │      ├──▶ TEI :80            (embeddings, HF cache PVC)                   │
                 │      └──▶ PostgreSQL :5432   (LiteLLM keys/spend, PVC)                     │
                 │  Qdrant :6333 (vectors, PVC, collection alias 'documents')                 │
                 │  Registry :5000  (image source when airgapped=true)                        │
                 └───────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Ansible 2.16+ on the controller (`pip install ansible-core ansible-lint`,
  `ansible-galaxy collection install -r requirements.yml`)
- Target: clean Ubuntu 24.04 VM, 4 vCPU / 8 GB RAM, passwordless or
  `ansible_become_pass` sudo, outbound internet for release 1.0
- `kubectl` is installed on targets by the `k3s` role (symlinked)

## Secrets setup (do this first)

```bash
cp group_vars/all/vault.yml.example group_vars/all/vault.yml
ansible-vault encrypt group_vars/all/vault.yml
# edit inventories/*/hosts.ini ansible_host / become_pass as needed
```

Nothing secret is stored outside the vault file. Generated API keys are
written to `generated-keys.json` (git-ignored, mode 600) — move them into
the vault and delete the file.

## Deploy release 1.0

```bash
ansible-playbook -i inventories/staging site.yml -e release=1.0
ansible-playbook -i inventories/staging playbooks/seed-data.yml -e release=1.0
```

`seed-data.yml` loads `seed/documents.jsonl` (20 docs) into Qdrant through
the embeddings API and creates the 2 LiteLLM API keys. Both playbooks end
with the smoke test (chat + embeddings + Qdrant alias check).

Re-run `site.yml` → **0 changed** (idempotent: `kubectl apply` + version
checks everywhere).

## Upgrade 1.0 → 1.1

```bash
ansible-playbook -i inventories/staging playbooks/upgrade.yml -e release=1.1
```

See `UPGRADE-1.0-to-1.1.md` for the operator runbook.

## Rollback

```bash
ansible-playbook -i inventories/staging playbooks/rollback.yml -e release=1.0
```

## Other playbooks

| Playbook | Purpose |
|---|---|
| `playbooks/backup.yml` | Pre-flight checks (disk, cluster health) + pg_dump + Qdrant snapshot |
| `playbooks/os-patch.yml` | Ubuntu security updates, `serial: 1`, reboot only if required |
| `playbooks/bundle-build.yml` | Build offline bundle (images + models + k3s + SHA256SUMS) |
| `playbooks/bundle-load.yml` | Verify checksums, load images to local registry, seed model stores |
| `playbooks/rotate-secrets.yml` | **Own scenario**: rotate LiteLLM master key + DB password, no downtime |

## Air-gapped (prod) flow

```bash
# on a connected machine:
ansible-playbook -i inventories/staging playbooks/bundle-build.yml -e release=1.1
# copy ai-stack/bundle/1.1/ to the site, then on the air-gapped controller:
ansible-playbook -i inventories/prod playbooks/bundle-load.yml -e release=1.1 -e bundle_path=/path/to/bundle/1.1
ansible-playbook -i inventories/prod site.yml -e release=1.1
```

## Version pinning

Every image, k3s version, model and collection name lives in
`group_vars/all.yml` + `group_vars/releases/{1.0,1.1}.yml`. Nothing uses
`latest`. Rationale for chosen versions is in the comments there.

## Project layout

```
site.yml                  # deploy entry point
playbooks/                # lifecycle playbooks
roles/                    # common, k3s, registry, database, model_server,
                          # embeddings, vector_db, gateway, smoke_test, gpu
scripts/                  # python helpers run inside the litellm pod
inventories/{staging,prod}/
group_vars/               # all.yml, releases/, all/vault.yml (encrypted)
seed/documents.jsonl      # provided seed data (parent dir)
```
