# qwreey-proc-guard (plugin development)

One PreToolUse(Bash) hook, `hooks/heavy-proc-guard.py`, that denies heavy runs (bench, fuzz, perf, stress) not wrapped in `choom`. Decision rules and settings: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test-heavy-proc-guard.py` (exit 0 = pass). Add a case for every new pass or block pattern, including the false positive that prompted it.

## Rules for this plugin
- `hooks/harness_nonce.py` is a byte copy of the repo's `lib/harness_nonce.py`, and `hooks/harness_env.py` of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so the installed hook runs live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- The deny reason follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook name="heavy-proc-guard" level="action">` with the session nonce, and it must say how to re-run.
- A false positive costs one retry and a miss can kill a session, so lean toward blocking; but keep git/gh commands and already-wrapped commands passing.
- With no wrapper program installed the hook must allow everything; Windows and macOS users rely on that.
- New toolkit executors go in `TOOLKIT_EXECUTORS` and in the q plugin's `skills/doctor/references/toolkits/README.md`.
