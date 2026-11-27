# qwreey-voice (plugin development)

One ambient block (`context/ambient.md`) on how the main session talks to the user and hands work over. No other hooks, no model calls.

## Rules for this plugin
- `context/ambient.md` is the user's own wording, in Korean on purpose: the user reviews every line against how the text lands on them. Change a line only when the user asks for it or approves the proposed line; do not translate it, tidy it or shorten it unprompted. HTML comments (`<!-- ... -->`) in it are notes for people on why a line reads as it does; the hook strips them before injecting, so keep the reason for a change there, in Korean.
- The block is about speech only. Do not cite it, or anything about the user, as a reason in commits, commands, code, docs or reports.
- Main session only (`SessionStart`, and the `PreCompact` omit line). Subagents do not talk to the user, so there is no `SubagentStart`.
- `hooks/ambient.py`, `hooks/compact_epoch.py` and `hooks/harness_nonce.py` are byte copies of the repo's `lib/`; `hooks/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py`. Edit the canon, then run `python3 -I tools/sync-copies.py --apply`. Settings (events, off switch) live in `context/ambient.json`.
- The marketplace is a directory source, so the installed hook runs live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.

## Tests
From the repo root: `python3 -I tools/tests/test-ambient-lib.py`, `python3 -I tools/tests/test-vendored-copies.py`. After a text change: `python3 -I tools/regen-prompt-surface.py` (add `--allow-growth` when the user's change makes it longer).
