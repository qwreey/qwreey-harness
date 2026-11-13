# qwreey-conventions (plugin development)

Comment, model-doc, copy and structure conventions: skills (`skills/`), path-scoped rules (`rules/`), and notice hooks (`hooks/`). How it fits together: `docs/how-it-works.md`.

## Where things are
- `hooks/hooks.json`: every hook registration. Main scripts: `conventions-check.py` (added-line checks, Stop report), `reuse-check.py` + `reuse_sets.py`, `structure-reminder.py`, `rules_inject.py`, `reply_language.py`, `memory-placement.py`, `bash-bypass-reminder.py`. Shared helpers: `conv_env.py` (off switches, config dir), `conv_lex.py` (comment lexer), `conv_edit.py`.
- A rule (`rules/*.md`) is a few lines that point to its skill; the skill holds the full convention. Change both together.
- `README.md` is for people deciding whether to install; technical detail goes in `docs/how-it-works.md`.

## Tests
Run each `tests/test-*.py` with `python3 -I` (exit 0 = pass, no model calls). Also from the repo root: `python3 -I tools/tests/test-vendored-copies.py` (copies) and `python3 -I tools/tests/test-coderag-rules-parity.py` (coderag injects pack rules byte-identically to `rules_inject.py`; needs the coderag binary).

## Rules for this plugin
- `hooks/harness_nonce.py`, `hooks/compact_epoch.py`, `hooks/memory_signals.py` and `hooks/copy_regions.py` are byte copies of the repo's `lib/`; `hooks/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- `rules_inject.py` is the reference that coderag's Rust hook matches for pack rules; a behavior change here needs the same change in coderag and a passing parity test.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce. The Stop report to the user (`systemMessage`) is Korean.
- Hooks never block, except the reply-language Stop rewrite. Notices name only lines the current edit added; old problems are counted for the Stop report, never fixed unprompted.
- `rules_inject.py` and `conventions-check.py` run on every file open or edit: standard library only, return early when nothing matches.
