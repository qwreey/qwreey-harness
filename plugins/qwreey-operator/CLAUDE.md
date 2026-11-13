# qwreey-operator (plugin development)

Keeps the main session talking with the user while large implementations go to background subagents: a five-line ambient (`context/ambient.md`) and one notice hook (`hooks/delegate-nudge.py`). Behavior, thresholds and their evidence: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test_delegate_nudge.py` (exit 0 = pass, no model calls; it redirects `TMPDIR`). Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `hooks/harness_nonce.py` is a byte copy of the repo's `lib/harness_nonce.py`. Edit the canon in `lib/`, then run `python3 -I tools/sync-copies.py --apply`; never edit the copy here. `OMIT_LINE` in `hooks/ambient.py` matches the other plugins' ambient hooks (`tools/tests/test-vendored-copies.py`).
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce, observation plus advice, and the cases where it need not be followed.
- The ambient goes to the main session only (SessionStart, no SubagentStart), so implementer subagents do not receive it. Do not restate what Claude Code's own subagent guidance already covers.
- `delegate-nudge.py` runs on every PostToolUse: return before opening state for tools that are not writes, Bash or Agent.
- The thresholds (12 writes, 8 files, 3 files / 150 lines) come from measurements cited in `docs/how-it-works.md`; change them only with new measurements.
