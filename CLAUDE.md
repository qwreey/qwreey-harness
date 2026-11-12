# claude-doctor

Source of truth for the Claude Code harness. Pointers only; read the target, not everything.

- `PLAN.md`: current goal and open decisions. Check it before proposing structure.
- `HUMAN_TODO.md`: what only the user does (deletes, permissions, apply). Do not do these.
- `README.md`: for humans (install, layout).
- `home/`: source of the user-level `~/.claude` (list in `home/MANIFEST`). Edit here, never `~/.claude`; the user runs `tools/home-sync.sh diff` then `apply`.
- `plugins/`: `q` (user commands, session-log), `qwreey-advisor`, `qwreey-conventions`, `qwreey-proc-guard`.
- `packs/`: domain packs, default-off plugins a repo enables in its own `.claude/settings.json` (`web-security`; luau-kb will join). See `packs/README.md`.
- `.claude/`: records, laid out per the `coderag:agent-records` skill (`../coderag/skills/agent-records/SKILL.md`). Living: `base/decisions/` (agreed conventions, D-xx), `research/drafts/` (pre-install drafts). Snapshots: `audit/`, `handoff/`, `sessions/`; never edit them and never read them whole (some are 40-80k tokens), open only the file or section you were pointed to.
- `.claude/archive/`: living records that left active (landed, superseded, rejected, archived) at their original subpath (landed drafts: `archive/research/drafts/`). Not in default search; use `q:recall` or `--all` to find why something changed.
- There is no `TODO.md`. Do not tell subagents to read it.
