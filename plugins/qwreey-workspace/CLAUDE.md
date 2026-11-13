# qwreey-workspace (plugin development)

Multi-repo workspace guard: an ambient (`context/ambient.md`) for main and subagents, a write gate for sibling repos (`scripts/workspace_gate.py`), and the `qwreey-workspace:workspace` skill (repo map, live-session and worktree-lock checks). Details: `docs/how-it-works.md`.

## Where things are
- `hooks/hooks.json`: hook registrations. `scripts/ambient.py` injects the ambient; `scripts/workspace_gate.py` judges writes; `scripts/wslib.py` holds the shared helpers (settings, paths).
- `skills/workspace/SKILL.md`: the map and the rules the gate points the model to.

## Tests
`python3 -I tests/test_workspace_gate.py` and `python3 -I tests/test_ambient.py` (exit 0 = pass, no model calls). Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `scripts/harness_nonce.py` and `scripts/compact_epoch.py` are byte copies of the repo's `lib/`. Edit the canon in `lib/`, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here. `OMIT_LINE` in `scripts/ambient.py` matches the other plugins' ambient hooks (`tools/tests/test-vendored-copies.py`).
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled. This gate also guards the session editing it, so test a change with the unit tests before relying on it live.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce.
- Compare paths with `normpath`, not `realpath`: symlinks such as `~/.claude/rules` would otherwise resolve into a sibling repo and be misjudged.
- With `HARNESS_WORKSPACE` empty or a single repo, the plugin must do nothing.
