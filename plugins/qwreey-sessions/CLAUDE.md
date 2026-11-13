# qwreey-sessions (plugin development)

Automatic session log: hooks decide when to summarize, a detached worker summarizes with `claude -p --model haiku` into a store outside the repo, and skills `checkpoint`, `import`, `recall` read it. Hook wiring, compact handling, platform: `docs/how-it-works.md`. Summary flow, store layout, notice table, `session-log` commands, settings: `docs/session-log.md`.

## Where things are
- `scripts/hook.py`: every hook event except `records_read.py` (snapshot warning on record reads). Keep it to decisions; summarizing belongs to the worker (`scripts/cli.py flush`).
- `scripts/sllib/`: the library (`config.py` settings, `messages.py` every model-facing string, `redact.py` nonce redaction, `verify.py` quote check against the transcript, `store.py`, `worker.py`, `summarize.py`).
- `bin/session-log`: the CLI on PATH when the plugin is enabled.

## Tests
- `python3 -I tests/test_session_log.py`: unit tests with a fake `claude`, no cost.
- `tests/e2e.sh [--auto-compact]` calls the real `claude -p` and haiku and costs money; run it only when the user agrees.

## Rules for this plugin
- `scripts/harness_nonce.py` and `scripts/compact_epoch.py` are byte copies of the repo's `lib/`. Edit the canon in `lib/`, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text lives in `scripts/sllib/messages.py` and follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce.
- Everything written out of a session (records, summaries, handovers, import copies) goes through `redact.py`, so a live nonce never lands in a file.
- Hooks always exit 0 and never block; the frequent paths (PostToolUse on every tool, Read/Grep) must stay cheap and return early.
- Records enter a repo only through `import`, when the user chooses it.
