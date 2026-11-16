# qwreey-proc-guard (plugin development)

Two PreToolUse(Bash) hooks: `hooks/heavy-proc-guard.py` denies heavy runs (bench, fuzz, perf, stress) not wrapped in `choom`; `hooks/self-match-guard.py` catches `pgrep -f`/`pkill -f` patterns that match the calling shell's own command line (deny inside while/until loops, notice elsewhere). Both split commands with `hooks/shell_segments.py`. Decision rules and settings: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test-heavy-proc-guard.py` and `python3 -I tests/test-self-match-guard.py` (exit 0 = pass). Add a case for every new pass or block pattern, including the false positive that prompted it.

## Rules for this plugin
- `hooks/harness_nonce.py` is a byte copy of the repo's `lib/harness_nonce.py`, and `hooks/harness_env.py` of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so the installed hook runs live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Deny reasons and notices follow `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook name="heavy-proc-guard">` or `name="self-match-guard"` with the session nonce; a deny (level `action`) must say how to re-run.
- `hooks/shell_segments.py` is imported by both hooks: a change there changes both, so run both tests.
- A false positive costs one retry and a miss can kill a session, so lean toward blocking; but keep git/gh commands and already-wrapped commands passing.
- With no wrapper program installed heavy-proc-guard must allow everything; Windows and macOS users rely on that. self-match-guard needs no wrapper and runs everywhere.
- New toolkit executors go in `TOOLKIT_EXECUTORS` and in the q plugin's `skills/doctor/references/toolkits/README.md`.
