---
description: Where knowledge belongs before saving it to auto memory (memory is machine-local; repo knowledge goes in the repo). Pairs with the memory-placement hook
paths:
  - "**/MEMORY.md"
  - "**/memory/*.md"
  - "**/.claude/memory/**"
---
Auto memory lives outside the repo (`~/.claude/projects/<key>/memory/`). It does not travel with a clone, a worktree on another machine, or a teammate, and it detaches when the project folder moves (the key is derived from the path).

Before saving a memory, decide where it belongs:
- User preferences, feedback on how to work with this user, this machine / sandbox / dev-server facts: memory.
- Repo conventions, decisions, pitfalls, build/test commands, file or module ownership: the repo (CLAUDE.md, `.claude/rules/`, docs/), or the coderag project layer when the project uses one.
- Toolkit-general knowledge (Luau, web, ...): the shared pack (luau-kb etc.), not one repo's memory.
- Company/team knowledge: coderag team layer.

If a note mixes both, save the personal part in memory and propose the repo part to the user; do not edit repo files without asking.
When saving a memory that points at repo knowledge, store the pointer ("see docs/X.md"), not a copy.

Note: `paths` match files under the project, so this rule loads only when a memory file is inside the working tree; for the default memory location the `memory-placement` hook gives the same guidance at write time.
