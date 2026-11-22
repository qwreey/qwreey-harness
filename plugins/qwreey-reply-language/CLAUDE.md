# qwreey-reply-language (plugin development)

One hook, on UserPromptSubmit (ask for the language once), Stop (block and rewrite a drifted reply) and PostToolBatch (interim drift and long-turn notices). `hooks/hooks.json` runs the Rust binary `native/qwreey-reply-language hook reply-language` (exec form, source `crates/qwreey-reply-language`, built and copied by hand, git-ignored); `hooks/reply_language.py` stays as the reference it must match byte for byte, so a behavior change goes into both (`python3 -I tools/tests/hook-parity.py --map crates/qwreey-reply-language/parity-map.json`, `cargo test -p qwreey-reply-language`). `hooks/reply_env.py` reads the off switch through the harness.env layers. Decision rules and settings: `docs/how-it-works.md`.

## Tests
`python3 -I tests/test-reply-language.py` (exit 0 = pass, no model calls). Add a case for every new pass or block pattern, including the false positive that prompted it.

## Rules for this plugin
- `hooks/harness_nonce.py` is a byte copy of the repo's `lib/harness_nonce.py`, and `hooks/harness_env.py` of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Colleagues run an installed copy outside this repo: the hook reads only this plugin's folder, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PROJECT_DIR` and Claude Code's own files. Check with `HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py`.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook name="reply-language">` with the session nonce. The Stop rewrite is the only block; every other output is `info`.
- Main conversation only: return early when the payload has `agent_id`. Never write reply text to the log, only counts and ratios.
- `ENV_DEFAULTS` in `hooks/reply_env.py` must match the `userConfig` defaults in `.claude-plugin/plugin.json` (`tools/tests/test-plugin-userconfig.py`).
