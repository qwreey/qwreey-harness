---
description: Conventions for documents a model reads to act (CLAUDE.md, SKILL.md, agents, rules). Details are in the conventions:agent-docs skill
paths: ["**/CLAUDE.md", "**/SKILL.md", "**/agents/*.md", "**/.claude/rules/*.md", "**/skills/**/*.md"]
---
# Agent docs
- Test: if deleting a sentence would not change what the model does, it does not belong here.
- Keep current facts and instructions, one sentence of why, and pointers to open or run. Move who decided, when, audit or round numbers and change narration to the commit message or an existing ledger. Move, do not delete.
- Details and what to do with a hook notice: load the `conventions:agent-docs` skill. A repo's own rules win.
