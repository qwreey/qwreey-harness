# qwreey-workspace (plugin development)

Multi-repo workspace guard: an ambient (`context/ambient.md`) for main and subagents, a write gate for sibling repos (`scripts/workspace_gate.py`), a session-start notice about this repo's stale worktrees (`scripts/stale_worktrees.py`), a notice when this repo's records name a sibling's internal paths (`scripts/sibling_notice.py`), and the `qwreey-workspace:workspace` skill (repo map, live-session and worktree-lock checks). Details: `docs/how-it-works.md`.

## Where things are
- `hooks/hooks.json`: hook registrations. `scripts/ambient.py` injects the ambient (settings in `context/ambient.json`); `scripts/workspace_gate.py` judges writes; `scripts/stale_worktrees.py` lists stale worktrees once per session (threshold `HARNESS_WORKSPACE_STALE_WORKTREE_DAYS`); `scripts/sibling_notice.py` scans what Write/Edit/MultiEdit put into `.claude/` records for paths into sibling repos (off `HARNESS_WORKSPACE_SIBLING_NOTICE=off`); `scripts/wslib.py` holds the shared helpers (settings, paths).
- `skills/workspace/SKILL.md`: the map and the rules the gate points the model to.

## Tests
`python3 -I tests/test_workspace_gate.py`, `python3 -I tests/test_ambient.py`, `python3 -I tests/test_stale_worktrees.py` and `python3 -I tests/test_sibling_notice.py` (exit 0 = pass, no model calls). Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `scripts/ambient.py`, `scripts/harness_nonce.py` and `scripts/compact_epoch.py` are byte copies of the repo's `lib/`; `scripts/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here. Ambient settings (events) live in `context/ambient.json`.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled. This gate also guards the session editing it, so test a change with the unit tests before relying on it live.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce.
- Compare paths with `normpath`, not `realpath`: symlinks such as `~/.claude/rules` would otherwise resolve into a sibling repo and be misjudged.
- With `HARNESS_WORKSPACE` empty or a single repo, the plugin must do nothing.
- Hooks only read other worktrees and repos: run git there with `GIT_OPTIONAL_LOCKS=0` (a plain `git status` rewrites the index), and never emit a command that deletes.
