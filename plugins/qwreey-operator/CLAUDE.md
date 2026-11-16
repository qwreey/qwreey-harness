# qwreey-operator (plugin development)

Keeps the main session talking with the user while large implementations go to background subagents: a five-line ambient (`context/ambient.md`), one notice hook (`hooks/delegate-nudge.py`) and one SubagentStop hook (`hooks/subagent-bg-tasks.py`) that sends a finishing subagent back once to collect or stop its own running background tasks. Behavior, thresholds and their evidence: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test_delegate_nudge.py` and `python3 -I tests/test_subagent_bg_tasks.py` (exit 0 = pass, no model calls; they redirect `TMPDIR`). Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `hooks/ambient.py`, `hooks/compact_epoch.py` and `hooks/harness_nonce.py` are byte copies of the repo's `lib/`, and the `STOP_ERROR` region in `hooks/subagent-bg-tasks.py` is a region copy of `lib/harness_texts.py`; `hooks/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here. Ambient settings (events) live in `context/ambient.json`.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce, observation plus advice, and the cases where it need not be followed.
- The full ambient goes to the main session only (SessionStart). SubagentStart sends `context/subagent.md`: the subagent-model line, because subagents launch subagents too, and the line on collecting and stopping their own children and background work before the final report; the delegation, parallel and check lines stay main-only. Do not restate what Claude Code's own subagent guidance already covers.
- `subagent-bg-tasks.py` output is additionalContext on SubagentStop, which makes the subagent take another turn: keep its pass conditions (`stop_hook_active`, empty or error last message, once per subagent, fail-open) per the Stop section of `home/.claude/HOOK-MESSAGES.md`.
- `delegate-nudge.py` runs on every PostToolUse: return before opening state for tools that are not writes, Bash or Agent.
- The thresholds (12 writes, 8 files, 3 files / 150 lines) come from measurements cited in `docs/how-it-works.md`; change them only with new measurements.
