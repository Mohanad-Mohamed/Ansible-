#!/usr/bin/env python3
"""Generate the lessons-learned .pptx (5-8 slides) for the interview task.

Usage:
    pip install python-pptx
    python make_pptx.py
Output: lessons-learned.pptx in the current directory.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

DARK = RGBColor(0x1F, 0x2A, 0x44)
ACCENT = RGBColor(0x2E, 0x86, 0xAB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def add_slide(title, bullets, subtitle=None):
    slide = prs.slides.add_slide(blank)
    # title bar
    bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(1.1))  # rectangle
    bar.fill.solid()
    bar.fill.fore_color.rgb = DARK
    bar.line.fill.background()
    tf = bar.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(32)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = WHITE
    # body
    body = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.5))
    tf = body.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = b
        p.font.size = Pt(20)
        p.font.color.rgb = DARK
        p.space_after = Pt(10)
        if b.startswith("  "):
            p.level = 1
            p.font.size = Pt(16)
    if subtitle:
        sub = slide.shapes.add_textbox(Inches(0.6), Inches(7.0), Inches(12.1), Inches(0.4))
        sub.text_frame.text = subtitle
        sub.text_frame.paragraphs[0].font.size = Pt(12)
        sub.text_frame.paragraphs[0].font.color.rgb = ACCENT
    return slide


# Slide 1 — Title
s = prs.slides.add_slide(blank)
bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = DARK; bg.line.fill.background()
tb = s.shapes.add_textbox(Inches(1), Inches(2.6), Inches(11.3), Inches(2.4))
tf = tb.text_frame; tf.word_wrap = True
tf.text = "Mini On-Prem AI Stack — IaC Life Cycle"
p = tf.add_paragraph(); p.text = "Ansible + k3s: deploy, patch, upgrade 1.0→1.1, rollback"
p.font.size = Pt(24); p.font.color.rgb = WHITE
p2 = tf.add_paragraph(); p2.text = "Lessons learned — 10-minute talk"
p2.font.size = Pt(18); p2.font.color.rgb = ACCENT

# Slide 2 — Design (one diagram, ASCII-art style in text)
add_slide("Design: one diagram", [
    "apps ──HTTP──▶ LiteLLM gateway :4000  (API keys, aliases onprem-chat / onprem-embed)",
    "                    ├──▶ Ollama :11434     chat model (PVC)",
    "                    ├──▶ TEI :80           embeddings (HF cache PVC)",
    "                    └──▶ PostgreSQL :5432  keys/spend (PVC)",
    "Qdrant :6333  vectors on PVC; collection alias 'documents' hides physical names",
    "Registry :5000  only image source when airgapped=true",
    "All on k3s, namespace ai-platform; everything pinned in group_vars/releases/",
], subtitle="One entry point: ansible-playbook -i inventories/staging site.yml -e release=1.0")

# Slide 3 — Upgrade flow 1.0 → 1.1 and risks
add_slide("Upgrade flow 1.0 → 1.1", [
    "1. Pre-flight + backup   disk check, nodes Ready, pg_dump -Fc + Qdrant snapshot",
    "2. OS patching           serial:1 — one node at a time, reboot only if required",
    "3. k3s upgrade           platform first; pods survive the API restart",
    "4. Postgres 16→17        dump/restore (not pg_upgrade — portable across images)",
    "5. Component images      Qdrant, TEI (new embed model), LiteLLM — rolling",
    "6. Data migration        re-embed → documents_v2 → VERIFY → alias switch",
    "7. Smoke test            chat + embeddings + Qdrant alias",
    "Risks: pg major upgrade is the point of no easy return; TEI model download",
    "is slow on first boot; alias switch must happen only after verification.",
])

# Slide 4 — What broke and how fixed
add_slide("What broke & how I fixed it", [
    "kubectl apply -f - needs stdin → switched to file-based manifests",
    "kubectl cp always reported 'changed' → broke the 0-changed requirement → fixed changed_when",
    "DB password was rendered into a manifest file → moved to k8s Secret + vault",
    "lookup('k8s') plugin needed extra collection → replaced with kubectl jsonpath",
    "GPU detection ran on controller not target → fixed to nvidia-smi/lspci on host",
    "Alias would switch before v2 was verified → added SET_ALIAS=0 + verify step",
])

# Slide 5 — What I learned
add_slide("What I learned", [
    "Idempotency is a design property, not an afterthought — every task needs a changed_when story",
    "Aliases > renames: apps never learn physical collection names changed",
    "Backup before change is cheap; restore confidence is the real deliverable",
    "dump/restore beats pg_upgrade when the runtime (container image) changes",
    "Air-gap changes everything: models are data too — bundle them like images",
    "Honest rollback docs > perfect rollback code",
])

# Slide 6 — How I used AI tools
add_slide("How I used AI tools", [
    "Used Cascade to draft roles, manifests, scripts and docs from the spec",
    "I decided: k3s+manifests over Helm, dump/restore over pg_upgrade, alias strategy,",
    "secret rotation as own scenario, serial:1 patching",
    "I rejected/fixed: stdin apply, k8s lookup plugin, controller-side GPU check,",
    "premature alias switch, plaintext secret in manifest",
    "Rule followed: I can explain every task, variable and decision without the assistant",
])

# Slide 7 — Multi-node OKD + GPU future
add_slide("Running this on multi-node OKD with GPUs", [
    "OKD: replace k3s role with cluster-api / hive deploy; keep manifests (they're portable)",
    "Multi-node: patching already serial:1; add pod anti-affinity + PDBs for zero downtime",
    "Postgres/Qdrant: move to OpenShift Operators or CNPG for HA + managed failover",
    "GPU: gpu role already auto-detects; add MIG/time-slicing, nvidia device plugin,",
    "  and route chat model to GPU nodes via nodeSelector/taints",
    "Air-gap: mirror images to internal registry (already supported), sign with cosign",
    "Secrets: migrate vault → External Secrets Operator backed by Vault",
])

# Slide 8 — Summary
add_slide("Summary", [
    "Working 1.0 deploy → seed → upgrade → rollback lifecycle as code",
    "Pinned versions, vault secrets, air-gap bundle, smoke tests, lint + CI",
    "Data-safe embedding migration via verify-then-alias-switch",
    "Honest docs: what rolls back, what doesn't, and why",
    "Next: validate on fresh VM, produce run logs, iterate on review feedback",
])

prs.save("lessons-learned.pptx")
print("Saved lessons-learned.pptx")
