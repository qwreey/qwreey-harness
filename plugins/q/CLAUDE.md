# q (plugin development)

User-invoked commands (`/q:start`, `/q:doctor`, `/q:away`, `/q:back`) plus always-on hooks: hook-message ambient, subagent fan-out notice and away slots, stale background work, install drift. How it fits together: `docs/how-it-works.md`; onboarding layout: `docs/onboarding.md`.

## Where things are
- `hooks/hooks.json`: every hook registration. Scripts are in `scripts/`: `ambient.py` (injects `context/ambient.md`), `subagent-slots.py` + `subagent_ledger.py` (fan-out notice, away budget; the ledger is also the CLI behind `/q:away` and `/q:back` and is read by the claude-doctor statusline), `stale_work.py`, `drift.py`, `records_check.py` (used by `/q:doctor`).
- `skills/<name>/SKILL.md` per command; `/q:doctor` checks live in `skills/doctor/scripts/`, its references in `skills/doctor/references/`.
- `README.md` is for people deciding whether to install; technical detail goes in `docs/how-it-works.md`.

## Tests
Run each `tests/test*.py` and `skills/doctor/tests/*.py` with `python3 -I` (exit 0 = pass, no model calls). Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `scripts/harness_nonce.py`, `scripts/compact_epoch.py` and `skills/doctor/scripts/memory_signals.py` are byte copies of the repo's `lib/`. Edit the canon in `lib/`, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here.
- `context/ambient.md` is wording the user approved and other plugins' hook messages rely on it (`home/.claude/HOOK-MESSAGES.md` rule 3); propose changes, do not rewrite it on your own.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled.
- Model-facing hook text follows `home/.claude/HOOK-MESSAGES.md`: English, `<harness-hook ...>` with the session nonce. User-facing lines (`systemMessage`) are Korean.
- `subagent-slots.py` runs on every PostToolUse: keep the not-away path cheap (no ledger import, no JSON parse before `quick_not_away`).
- Skills stay `disable-model-invocation: true`; they are the user's commands, not the model's.
