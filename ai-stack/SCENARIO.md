# Own scenario: zero-downtime rotation of LiteLLM master key + Postgres password

## Why this scenario

Credential rotation is one of the most common real on-prem operations:
a CVE in LiteLLM, a staff member leaving, or a compliance audit all force
it. Done wrong it is a self-inflicted outage. It exercises secrets
management, rolling restarts and verification — all things the rest of the
project already needs.

## What the playbook does (`playbooks/rotate-secrets.yml`)

1. **Generate** new random Postgres password and LiteLLM master key
   (`lookup('password')`, `no_log: true` — never printed).
2. **`ALTER USER ... WITH PASSWORD`** inside Postgres. Postgres checks the
   password per-connection, so existing connections survive; new
   connections must use the new password.
3. **Update k8s Secrets** `postgres-credentials` and
   `litellm-credentials` (the latter also embeds the new
   `DATABASE_URL`).
4. **`kubectl rollout restart deploy/litellm`** — pods come up one at a
   time with the new env. With `replicas: 2` (prod) this is zero downtime;
   with 1 replica (staging) there are a few seconds of unavailability,
   which we state honestly.
5. **Write rotated values** to `rotated-secrets.json` (mode 600,
   git-ignored) so the operator can move them into Ansible Vault and
   re-run `site.yml` to keep manifests in sync.
6. **Smoke test** proves chat + embeddings still work with the new key.

## Why no downtime (prod)

- Postgres itself is **not restarted** — `ALTER ROLE` is online.
- LiteLLM rolls pod-by-pod; the old pod keeps serving until the new one is
  Ready (`readinessProbe` on `/health/liveliness`).
- The Qdrant alias, model aliases and API keys are untouched — applications
  see nothing.

## What breaks if you skip step 5

The vault still holds the OLD master key. The next `site.yml` run would
re-apply the old `litellm-credentials` secret and silently revert the
rotation — a classic "works on my machine" trap. The playbook's final
debug message warns about exactly this.
