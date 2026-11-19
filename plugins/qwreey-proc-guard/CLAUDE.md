# qwreey-proc-guard (plugin development)

Three hooks. Two PreToolUse(Bash) guards: `hooks/heavy-proc-guard.py` denies heavy runs (bench, fuzz, perf, stress) not wrapped in `choom`; `hooks/self-match-guard.py` catches `pgrep -f`/`pkill -f` patterns that match the calling shell's own command line (deny inside while/until loops, notice elsewhere). Both split commands with `hooks/shell_segments.py`. `hooks/resource-guard.py` runs on PreToolUse, PostToolUse and PostToolUseFailure(Bash): it warns when disk free space is low or drops during a command, and asks the model to clean up (or report) core dumps the command left. Decision rules and settings: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test-heavy-proc-guard.py`, `python3 -I tests/test-self-match-guard.py` and `python3 -I tests/test-resource-guard.py` (exit 0 = pass). Add a case for every new pass or block pattern, including the false positive that prompted it. The resource-guard test swaps the module's `disk_usage` and `read_core_pattern` and writes fake ELF cores in temp dirs; never point a test at real core files on the machine.

## Rules for this plugin
- `hooks/harness_nonce.py` is a byte copy of the repo's `lib/harness_nonce.py`, and `hooks/harness_env.py` of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so the installed hook runs live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Deny reasons and notices follow `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook name="heavy-proc-guard">`, `name="self-match-guard"` or `name="resource-guard"` with the session nonce; a deny (level `action`) must say how to re-run.
- resource-guard never blocks and never fails: any exception exits 0 with no output, no subprocesses. It may only ask to delete core files whose mtime is after the command's Pre time; keep that rule when changing the search.
- `PROC_GUARD_DISK` and `PROC_GUARD_CORE` are user-only (`ENV_USER_ONLY`); repo layers may only tighten the thresholds (`thresholds()`). A new option needs a `userConfig` entry whose default equals `ENV_DEFAULTS`.
- `hooks/shell_segments.py` is imported by both hooks: a change there changes both, so run both tests.
- A false positive costs one retry and a miss can kill a session, so lean toward blocking; but keep git/gh commands and already-wrapped commands passing.
- With no wrapper program installed heavy-proc-guard must allow everything; Windows and macOS users rely on that. self-match-guard needs no wrapper and runs everywhere. resource-guard's disk check runs everywhere; its core check is Linux-only.
- New toolkit executors go in `TOOLKIT_EXECUTORS` and in the q plugin's `skills/doctor/references/toolkits/README.md`.
