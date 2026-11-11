# claude-doctor

Source of truth for the Claude Code harness. Pointers only; read the target, not everything.

- `PLAN.md`: current goal and open decisions. Check it before proposing structure.
- `HUMAN_TODO.md`: what only the user does (deletes, permissions, apply). Do not do these.
- `README.md`: for humans (install, layout).
- `home/`: source of the user-level `~/.claude` (list in `home/MANIFEST`). Edit here, never `~/.claude`; the user runs `tools/home-sync.sh diff` then `apply`.
- `plugins/`: `q` (user commands, session-log), `qwreey-advisor`, `qwreey-conventions`.
- `decisions/`: agreed conventions (D-xx).
- `audit/` and `handoff/` are history. Never read them whole (some are 40-80k tokens). Open a specific file or section you were pointed to.
- `drafts/`: pre-install drafts. A first line `status: landed in <path>; not maintained` means the draft is finished; use `<path>`.
- There is no `TODO.md`. Do not tell subagents to read it.
