# 🚀 Mini On-Prem AI Stack — Ansible IaC

An enterprise-ready, automated Infrastructure-as-Code (IaC) repository that manages the full lifecycle of a private AI platform on **k3s (Lightweight Kubernetes)**:

$$\text{Deploy 1.0} \longrightarrow \text{Seed Data} \longrightarrow \text{Patch OS} \longrightarrow \text{Upgrade 1.0} \rightarrow \text{1.1} \longrightarrow \text{Rollback}$$

Built for **On-Premises** and completely **Air-Gapped (Offline)** enterprise environments with zero external cloud dependencies.

---

## 🏛️ Architecture Overview

All workloads run in the dedicated Kubernetes namespace `ai-platform`:

```text
                    [ Client Applications ]
                               │
                               ▼ (HTTP / API Key)
┌─────────────────────────────────────────────────────────────────────────────┐
│                          k3s (Namespace: ai-platform)                       │
│                                                                             │
│                     ┌────────────────────────┐                              │
│                     │   LiteLLM Gateway      │──────────► [ PostgreSQL ]    │
│                     │      (Port: 4000)      │            (Port: 5432)      │
│                     └───────────┬────────────┘            (Keys & Usage PVC)│
│                                 │                                           │
│                  ┌──────────────┴──────────────┐                            │
│                  ▼                             ▼                            │
│        ┌──────────────────┐          ┌───────────────────┐                  │
│        │   Ollama Server  │          │   TEI Inference   │                  │
│        │   (Port: 11434)  │          │    (Port: 80)     │                  │
│        │  (qwen2.5:0.5b)  │          │  (Multilingual)   │                  │
│        │   (Model PVC)    │          │    (Cache PVC)    │                  │
│        └──────────────────┘          └─────────┬─────────┘                  │
│                                                │                            │
│                                                ▼                            │
│                                      ┌───────────────────┐                  │
│                                      │ Qdrant Vector DB  │                  │
│                                      │   (Port: 6333)    │                  │
│                                      │ (Alias: documents)│                  │
│                                      │  (Vectors & PVC)  │                  │
│                                      └───────────────────┘                  │
│                                                                             │
│  [ Local Docker Registry: 5000 ] (Sole image source when airgapped=true)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 🔒 Stable Application Contract (Never changes across releases)
* **Chat Model Alias:** `onprem-chat` *(maps to Ollama)*
* **Embedding Model Alias:** `onprem-embed` *(maps to Hugging Face TEI)*
* **Qdrant Collection Alias:** `documents` *(maps to physical collections `documents_v1` or `documents_v2`)*

---

## 📋 System Requirements & Prerequisites

### 1. Target Machine (Where the AI Stack runs):
* **OS:** Clean **Ubuntu 24.04 LTS** (VM, Bare Metal, or Cloud instance).
* **Specs:** Minimum **4 vCPU**, **8 GB RAM**, **20 GB free disk space**.
* **Access:** SSH access with passwordless `sudo` (or known sudo password).
* **Internet:** Outbound internet access required for Release 1.0 (Air-gapped flow supported via offline bundles).

### 2. Controller Machine (Where you run Ansible commands):
* Python 3.10+
* Ansible 2.16+ (`ansible-core`)

---

## ⚡ Quickstart Guide (Step-by-Step)

Follow these exact steps to run and test the complete stack from scratch:

### Step 1: Install Controller Dependencies 🛠️

From your terminal, install Ansible and required dependencies:

```bash
# 1. Install Ansible & Lint tools
pip install ansible-core ansible-lint

# 2. Navigate into the ai-stack directory
cd ai-stack

# 3. Install required Ansible collections
ansible-galaxy collection install -r requirements.yml
```

---

### Step 2: Configure Your Target Server (Inventory) 🖥️

Open `inventories/staging/hosts.ini` and set your target server IP and SSH user:

```ini
[all]
# Replace 192.168.56.10 with your actual target VM IP address:
node1 ansible_host=192.168.56.10 ansible_user=ubuntu

[staging]
node1

[prod:children]
staging
```

> 💡 **Testing locally on the same Ubuntu VM?**
> Simply set: `node1 ansible_connection=local`

---

### Step 3: Setup Secrets (Ansible Vault) 🔐

All sensitive passwords and API keys are protected using Ansible Vault:

```bash
# 1. Copy the example vault template
cp group_vars/all/vault.yml.example group_vars/all/vault.yml

# 2. (Optional) Edit passwords inside vault.yml before encrypting
nano group_vars/all/vault.yml

# 3. Encrypt the vault file with a password of your choice
ansible-vault encrypt group_vars/all/vault.yml
```

> 💡 **Tip:** To avoid typing the vault password on every command, save your password to a file and pass `--vault-password-file ~/.vault_pass` or export `ANSIBLE_VAULT_PASSWORD_FILE`.

---

### Step 4: Deploy Release 1.0 🚀

Run the master playbook to provision k3s, databases, AI models, and the gateway:

```bash
ansible-playbook -i inventories/staging site.yml -e release=1.0 --ask-vault-pass
```

**What happens automatically:**
1. Base packages & Linux kernel modules are configured.
2. Lightweight Kubernetes (`k3s`) is installed and verified.
3. PostgreSQL, Qdrant, Ollama (`qwen2.5:0.5b`), and TEI are deployed with persistent storage (PVCs).
4. LiteLLM Gateway is launched on port `4000`.
5. Automated **Smoke Test** runs to verify chat and embeddings end-to-end.

**Verify deployment:**
```bash
# On the target server:
kubectl get pods -n ai-platform
```
*(All pods should be in `Running` state).*

---

### Step 5: Seed Knowledge Base & Generate API Keys 📚

Ingest the 20 bilingual test documents into Qdrant and generate application API keys:

```bash
ansible-playbook -i inventories/staging playbooks/seed-data.yml -e release=1.0 --ask-vault-pass
```

* Creates 2 virtual keys: `app-chat` and `app-embed`.
* Keys are securely stored in the Kubernetes Secret: `litellm-app-keys`.
* Ingests and indexes 20 documents into `documents_v1` through the embedding model.

---

### Step 6: Test the AI Platform (Live Curl Requests) 🧪

Extract your generated API keys or use your `LITELLM_MASTER_KEY`:

```bash
# On the target VM, retrieve the chat key:
CHAT_KEY=$(kubectl get secret litellm-app-keys -n ai-platform -o jsonpath='{.data.chat_key}' | base64 -d)

# 1. Test Chat Completion:
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CHAT_KEY" \
  -d '{
    "model": "onprem-chat",
    "messages": [{"role": "user", "content": "Hello, how are you?"}]
  }'

# 2. Test Embeddings:
EMBED_KEY=$(kubectl get secret litellm-app-keys -n ai-platform -o jsonpath='{.data.embed_key}' | base64 -d)
curl http://localhost:4000/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EMBED_KEY" \
  -d '{
    "model": "onprem-embed",
    "input": "Bank account withdrawal policy"
  }'
```

---

### Step 7: Zero-Downtime Upgrade (1.0 ➡️ 1.1) ⬆️

Upgrade the platform (k3s bump, Postgres 16 ➡️ 17 major upgrade, and embedding model migration):

```bash
ansible-playbook -i inventories/staging playbooks/upgrade.yml -e release=1.1 --ask-vault-pass
```

**How the safe upgrade works:**
1. **Safety Pre-flight & Backup:** Verifies disk space (>5GB) and creates snapshots.
2. **OS Patching:** Applies Ubuntu security updates (`serial: 1`, drains node if reboot is needed).
3. **Database Migration:** Dumps Postgres 16 and restores into a clean Postgres 17 instance with zero data loss.
4. **Blue/Green Vector Migration:** Re-embeds all documents into a new collection (`documents_v2`) using the new model `multilingual-e5-small`.
5. **Quality Verification:** Tests search accuracy (e.g. Arabic & English queries).
6. **Atomic Alias Switch:** Moves alias `documents` ➡️ `documents_v2` instantly with **Zero Reader Downtime**!

---

### Step 8: Emergency Rollback (1.1 ➡️ 1.0) ↩️

If an upgrade fails, restore the system back to Release 1.0:

```bash
ansible-playbook -i inventories/staging playbooks/rollback.yml -e release=1.0 --ask-vault-pass
```

* Restores the latest verified PostgreSQL database backup.
* Switches the Qdrant alias `documents` back to `documents_v1` immediately.
* Re-applies Release 1.0 component versions.

---

## 🛠️ Day-2 Operations Playbooks

| Playbook | Purpose | Command |
|---|---|---|
| **💾 Backup** | Pre-flight check + `pg_dump` + Qdrant snapshot | `ansible-playbook -i inventories/staging playbooks/backup.yml -e release=1.0` |
| **🛡️ OS Security Patch** | Ubuntu security updates (`serial: 1`), reboot only if required | `ansible-playbook -i inventories/staging playbooks/os-patch.yml -e release=1.0` |
| **🔑 Rotate Secrets** | Zero-downtime rotation of DB password & Master Key | `ansible-playbook -i inventories/staging playbooks/rotate-secrets.yml -e release=1.0` |

---

## 📦 Air-Gapped (Completely Offline) Flow

For sites with **NO internet access**:

1. **On an internet-connected machine (Build offline bundle):**
   ```bash
   ansible-playbook -i inventories/staging playbooks/bundle-build.yml -e release=1.1
   ```
   *(Saves Docker images, Ollama blobs, Hugging Face models, and SHA256SUMS into `bundle/1.1/`)*.

2. **Copy the `bundle/1.1/` directory to the offline server (via USB / SCP).**

3. **On the air-gapped target machine (Load & Deploy):**
   ```bash
   ansible-playbook -i inventories/prod playbooks/bundle-load.yml -e release=1.1 -e bundle_path=/path/to/bundle/1.1
   ansible-playbook -i inventories/prod site.yml -e release=1.1
   ```

---

## 📂 Repository Directory Structure

```text
imp/
├── stack-spec.yaml                   # Task specification & release contracts
├── README.md                         # This comprehensive guide
├── PRESENTATION-BRIEF.md             # Architecture summary for presentations & interviews
├── seed/
│   └── documents.jsonl               # 20 bilingual test documents (Arabic & English)
└── ai-stack/
    ├── site.yml                      # Master deployment entry point (10 roles)
    ├── ansible.cfg                   # Default inventory & YAML output settings
    ├── requirements.yml              # Ansible Galaxy collections
    ├── SCENARIO.md                   # Detailed secret rotation design doc
    ├── UPGRADE-1.0-to-1.1.md         # Operator upgrade runbook
    ├── AI_USAGE.md                   # Engineering transparency & decisions doc
    ├── inventories/
    │   ├── staging/                  # Single-node, connected testing environment
    │   └── prod/                     # Multi-node, air-gapped production environment
    ├── group_vars/
    │   ├── all.yml                   # Shared ports, namespaces, paths & aliases
    │   ├── all/vault.yml             # Encrypted secrets (Ansible Vault)
    │   └── releases/
    │       ├── 1.0.yml               # Pinned versions for Release 1.0
    │       └── 1.1.yml               # Pinned versions for Release 1.1
    ├── playbooks/                    # Operational playbooks (backup, upgrade, rollback, etc.)
    ├── roles/                        # Modular Ansible roles (k3s, postgres, ollama, tei, qdrant, litellm)
    └── scripts/                      # Helper Python scripts run inside the litellm pod
        ├── create_keys.py            # Generates virtual API keys
        ├── ensure_collection.py      # Creates Qdrant collections & manages aliases
        ├── seed_documents.py         # Embeds and indexes documents into Qdrant
        └── verify_reembed.py         # Gatekeeper: verifies search quality before alias swap
```

---

## 💡 Troubleshooting & FAQs

* **Q: Do I need Ollama installed on my local laptop?**
  * **A:** No! Ollama runs entirely as a containerized Pod inside Kubernetes on the target machine.
* **Q: Is the deployment idempotent?**
  * **A:** Yes. Running `site.yml` a second time reports `0 changed`.
* **Q: How to reset or clean up the cluster?**
  * **A:** Run `/usr/local/bin/k3s-uninstall.sh` on the target machine to completely remove k3s and wipe all resources.
