# claude-doctor

Source of truth for the Claude Code harness. Pointers only; read the target, not everything.

- `PLAN.md`: current goal and open decisions. Check it before proposing structure.
- `HUMAN_TODO.md`: what only the user does (deletes, permissions, apply). Do not do these.
- `README.md`: for humans (install, layout).
- `home/`: source of the user-level `~/.claude` (list in `home/MANIFEST`). Edit here, never `~/.claude`; the user runs `tools/home-sync.sh diff` then `apply`.
- `plugins/`: `q` (user commands, personal safety nets), `qwreey-sessions` (session-log, checkpoint, import, recall), `qwreey-workspace` (sibling-repo gate and map), `qwreey-operator`, `qwreey-delegate`, `qwreey-advisor`, `qwreey-conventions`, `qwreey-proc-guard`.
- Plugins are installed from a directory marketplace, so hooks run from this repo's `plugins/`; moving or deleting a hook script breaks every live session with that plugin enabled. Do such moves with the plugin disabled, or leave the old path working until sessions reload.
- `lib/`: canon of code and text shared by plugins (and coderag); plugins carry synced copies. Edit `lib/`, never a copy, then run `python3 -I tools/sync-copies.py --apply` (`lib/README.md`).
- `packs/`: domain packs (`web-security`, `luau-kb`), default-off plugins. A repo lists them in its `coderag.toml` `[[packs]]`; the coderag plugin injects their rules and `coderag adapt --harness claude` sets `enabledPlugins`. See `packs/README.md`.
- `.claude/`: records, laid out per the `coderag:agent-records` skill (`../coderag/conventions/skills/agent-records/SKILL.md`). Living: `base/decisions/` (agreed conventions, D-xx), `research/drafts/` (pre-install drafts). Snapshots: `audit/`, `handoff/`, `sessions/`; never edit them and never read them whole (some are 40-80k tokens), open only the file or section you were pointed to.
- `.claude/archive/`: living records that left active (landed, superseded, rejected, archived) at their original subpath (landed drafts: `archive/research/drafts/`). Not in default search; use `qwreey-sessions:recall` or `--all` to find why something changed.
- There is no `TODO.md`. Do not tell subagents to read it.
