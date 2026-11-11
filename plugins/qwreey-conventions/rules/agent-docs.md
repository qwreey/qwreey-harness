---
description: Conventions for documents a model reads to act (CLAUDE.md, SKILL.md, agents, rules). Details are in the qwreey-conventions:agent-docs skill
paths: ["**/CLAUDE.md", "**/SKILL.md", "**/agents/*.md", "**/.claude/rules/*.md", "**/skills/**/*.md"]
---
# Agent docs
- Test: if deleting a sentence would not change what the model does, it does not belong here.
- Keep current facts and instructions, one sentence of why, and pointers to open or run. Move who decided, when, audit or round numbers and change narration to the commit message or an existing ledger. Move, do not delete.
- References (`skills/**/references/*.md`) may keep dates, ids and old-pattern notes; the always-loaded entry documents stay lean.
- Details and what to do with a hook notice: load the `qwreey-conventions:agent-docs` skill. A repo's own rules win.
