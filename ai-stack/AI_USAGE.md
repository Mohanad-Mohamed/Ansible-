# AI_USAGE.md

## Tools used

- **Cascade (Windsurf AI assistant)** — generated the Ansible project
  skeleton, role/task/template files, Python helper scripts and docs from
  the task README + `stack-spec.yaml`.

## What AI did vs. what I decided

Decisions I made and can defend in review (AI proposed, I chose/adjusted):

- **k3s + plain manifests over Helm** — fewer moving parts, fully pinned,
  `kubectl apply` is naturally idempotent.
- **Postgres in k8s with dump/restore for the 16→17 major upgrade** —
  rejected `pg_upgrade` (needs identical FS/binary layout across container
  images); chose portable, verifiable `pg_dump -Fc`/`pg_restore`.
- **Qdrant collection alias for the embedding-model change** — atomic
  switch, readers never see a missing collection; old collection retained.
- **Secrets in k8s Secrets + Ansible Vault**, never rendered into manifest
  files (I corrected the first draft which embedded the DB password).
- **Smoke/seed/verify scripts run inside the litellm pod** — it already has
  Python and cluster DNS, so no extra images or port-forwards needed.
- **`serial: 1` + drain/uncordon/reboot-if-required** for OS patching.
- **Own scenario = secret rotation** — chosen over TLS renewal because it
  exercises vault→k8s-secret→rolling-restart flow end to end.

## What I rejected / changed from AI output

- Removed a broken first draft of the air-gap image loader (invalid Jinja
  inside a shell loop) and replaced it with an explicit image→key map.
- Replaced a fragile `lookup('k8s', ...)` plugin call with
  `kubectl get pod -o jsonpath` (no extra collection dependency).
- Fixed GPU detection to run `nvidia-smi`/`lspci` **on the target** instead
  of a controller-side `lookup('pipe')`.
- Added `SET_ALIAS=0` mode to `ensure_collection.py` so the v2 collection
  can be created and verified *before* the alias switch.

## Known limitations (honest list)

- Image versions (k3s v1.30.4/v1.31.5, qdrant v1.11.3/v1.12.4, litellm
  v1.51.1/v1.55.0, TEI 1.6, ollama 0.5.4, postgres 16.4/17.2) are pinned
  but **not yet executed on a real VM** — they must be validated on the
  fresh-VM run.
- TEI model download at first boot is slow; readiness `failureThreshold`
  is raised, but air-gapped sites must use `bundle-load.yml` to pre-seed
  the HF cache.
- `bundle-load.yml` assumes docker is present on the target for image
  loading; k3s's embedded containerd could be used instead (future work).
- The `.pptx` lessons-learned deck is **not yet produced**.
