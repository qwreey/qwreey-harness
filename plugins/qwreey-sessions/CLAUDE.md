# qwreey-sessions (plugin development)

Automatic session log: hooks decide when to summarize, a detached worker summarizes with `claude -p --model haiku` into a store outside the repo, and skills `checkpoint`, `import`, `recall` read it. Hook wiring, compact handling, platform: `docs/how-it-works.md`. Summary flow, store layout, notice table, `session-log` commands, settings: `docs/session-log.md`.

## Where things are
- `scripts/hook.py`: every hook event except `records_read.py` (PreToolUse deny of whole-file Reads of large records, PostToolUse snapshot warning on record reads). Keep it to decisions; summarizing belongs to the worker (`scripts/cli.py flush`).
- `scripts/sllib/`: the library (`config.py` settings, `messages.py` every model-facing string, `redact.py` nonce redaction, `anchors.py` the post-compact anchors (user messages and identifiers of the span just compacted, read from the transcript), `verify.py` quote check against the transcript, `store.py`, `worker.py`, `summarize.py`).
- `bin/session-log`: the CLI on PATH when the plugin is enabled.
- `crates/qwreey-sessions` (repo root): Rust port of the per-tool and per-prompt hooks (`hook.py` PostToolUse, UserPromptSubmit, PreToolUse and `records_read.py`), built and copied by hand to `native/qwreey-sessions` (git-ignored). `hooks/hooks.json` still runs the python scripts. A behavior change in those paths goes into both; check with `python3 -I tools/tests/hook-parity.py --map crates/qwreey-sessions/parity-map.json`, `cargo test -p qwreey-sessions` and `HOOK_TEST_BIN=<repo>/plugins/qwreey-sessions/native/qwreey-sessions python3 -I tests/test_session_log.py`.

## Tests
- `python3 -I tests/test_session_log.py`: unit tests with a fake `claude`, no cost.
- `python3 -I tests/test_anchors.py`: post-compact anchors on synthetic transcripts, no cost.
- `python3 -I tests/test_config_options.py`: plugin options (`userConfig` in `.claude-plugin/plugin.json`, saved in `settings.json` `pluginConfigs`) reach `sllib/config.py` and the `session-log` CLI. An option's default must equal `DEFAULTS` in `sllib/config.py`.
- `tests/e2e.sh [--auto-compact]` calls the real `claude -p` and haiku and costs money; run it only when the user agrees.

## Rules for this plugin
- `scripts/harness_nonce.py`, `scripts/compact_epoch.py` and `scripts/sllib/file_lock.py` are byte copies of the repo's `lib/`; `scripts/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text lives in `scripts/sllib/messages.py` and follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce.
- Everything written out of a session (records, summaries, handovers, import copies) goes through `redact.py`, so a live nonce never lands in a file.
- Hooks always exit 0 and never block, except the `records_read.py` read gate, which denies one Read and fails open on any error; the frequent paths (PostToolUse on every tool, Read/Grep) must stay cheap and return early.
- Records enter a repo only through `import`, when the user chooses it.
