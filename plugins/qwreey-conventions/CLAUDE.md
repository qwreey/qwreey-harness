# qwreey-conventions (plugin development)

Comment, model-doc, copy and structure conventions: skills (`skills/`), path-scoped rules (`rules/`), and notice hooks (`hooks/`). How it fits together: `docs/how-it-works.md`.

## Where things are
- `hooks/hooks.json`: every hook registration. Main scripts: `conventions-check.py` (added-line checks, Stop report), `reuse-check.py` + `reuse_sets.py`, `structure-reminder.py`, `rules_inject.py`, `reply_language.py`, `memory-placement.py`, `bash-bypass-reminder.py` (also takes the before-command snapshot), `bash_writes.py` (PostToolUse:Bash: runs `conventions-check.py`'s `file_notice`, reuse-check and rule injection on the files a Bash command changed). Shared helpers: `conv_env.py` (off and on switches, the plugin's harness.env key defaults, config dir), `conv_lex.py` (comment lexer, also returns comment column spans and, with `keep_code`, code text), `conv_edit.py`, `layout_metrics.py` (function spans, readable-code metrics and the layout notice text, used by `conventions-check.py` and `conventions-scan.py layout`).
- `scripts/conventions-scan.py`: whole-file `scan` and mechanical `fix` for existing problems (not a hook). It imports the check functions from `hooks/conventions-check.py`, so a check change there changes the scan too; `tests/test-conventions-scan.py` covers it, including the token guard that refuses a fix touching anything outside comments.
- A rule (`rules/*.md`) is a few lines that point to its skill; the skill holds the full convention. Change both together. `readable-code.md` is the exception: the whole convention is in the rule (skill pointers are rarely followed), and the comments skill only explains the layout notice. A rule with `switch: KEY` loads only when the harness.env layers give KEY = `on`.
- `README.md` is for people deciding whether to install; technical detail goes in `docs/how-it-works.md`.

## Tests
Run each `tests/test-*.py` with `python3 -I` (exit 0 = pass, no model calls). Also from the repo root: `python3 -I tools/tests/test-vendored-copies.py` (copies) and `python3 -I tools/tests/test-coderag-rules-parity.py` (coderag injects pack rules byte-identically to `rules_inject.py`; needs the coderag binary).

## Rules for this plugin
- `hooks/harness_nonce.py`, `hooks/compact_epoch.py`, `hooks/memory_signals.py` and `hooks/copy_regions.py` are byte copies of the repo's `lib/`; `hooks/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader). Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- `rules_inject.py` is the reference that coderag's Rust hook matches for pack rules; a behavior change here needs the same change in coderag and a passing parity test. The `switch:` filter is the one exception: coderag does not read it, so pack rules must not use `switch:` until coderag does.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce. The Stop report to the user (`systemMessage`) is Korean.
- Hooks never block, except the reply-language Stop rewrite. Notices name only lines the current edit added; old problems are counted for the Stop report, never fixed unprompted.
- `rules_inject.py` and `conventions-check.py` run on every file open or edit, and `bash-bypass-reminder.py` and `bash_writes.py` on every Bash call: standard library only, return early when nothing matches (no write signal means no snapshot and no git call).
