---
description: Conventions for documents a model reads to act (CLAUDE.md, SKILL.md, agents, rules). Pairs with the conventions-check doc notices; reference for people in docs/agent-docs.md
paths: ["**/CLAUDE.md", "**/SKILL.md", "**/agents/*.md", "**/.claude/rules/*.md", "**/skills/**/*.md", "**/plugins/*/rules/*.md"]
---
# Agent docs
- Test: if deleting a sentence would not change what the model does, it does not belong here.
- Keep current facts and instructions, one sentence of why, and pointers to open or run. Move who decided, when, audit or round numbers and change narration to the commit message or an existing ledger. Move, do not delete.
- References (`skills/**/references/*.md`) may keep dates, ids and old-pattern notes; the always-loaded entry documents stay lean.
- State a principle once and let the model generalize; do not list cases it would infer.
- Why it is built this way, for maintainers, goes in the skill's `references/rationale.md` (linked in one line) or a `docs/` folder, not in the entry document.
- A repo's own rules win.
