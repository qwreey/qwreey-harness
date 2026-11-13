# qwreey-advisor (plugin development)

Self-review plugin: skills `inherit-advisor` (fork) and `fresh-advisor` (fresh reviewer), agent `qwreey-advisor:reviewer`, hooks that suggest review points. How it fits together: `docs/how-it-works.md`. Design rationale and cost measurements: `docs/rationale-*.md`.

## Where things are
- `hooks/hooks.json`: every hook registration. `second-opinion-nudge.py` (review-point notices), `track-reviewer.py` (run line and scratch per reviewer call), `readonly-for-reviewers.py` + `auditor-readonly-guard.py` (reviewer read-only guard), `expand-inherit-prompt.py` (fork marker to `skills/inherit-advisor/templates/fork-prompt.md`), `ambient.py` (injects `context/ambient.md`).
- `skills/fresh-advisor/scripts/`: `review-ledger.py`, `advisor-stats.py`, `user-asks.py`.
- `README.md` is for people deciding whether to install; technical detail goes in `docs/how-it-works.md`.

## Tests
Run each file under `tests/` with `python3 -I`; exit 0 means pass, no model calls. Cross-plugin copy checks: `python3 -I tools/tests/test-vendored-copies.py` from the repo root.

## Rules for this plugin
- `hooks/harness_nonce.py` and `hooks/compact_epoch.py` are byte copies of the repo's `lib/`. Edit the canon in `lib/`, then run `python3 -I tools/sync-copies.py --apply`; never edit the copies here. `OMIT_LINE` in `ambient.py` is the same sentence as in the other plugins' ambient hooks; `tools/tests/test-vendored-copies.py` compares them.
- The marketplace is a directory source, so installed hooks run live from this folder. Do not move, rename or delete hook scripts while the plugin is enabled; a missing script breaks every session's hook.
- Model-facing hook text (additionalContext, deny reasons) follows `home/.claude/HOOK-MESSAGES.md`: English, wrapped in `<harness-hook ...>` with the session nonce.
- Plugin agents ignore frontmatter `hooks`, so the reviewer guard must stay in `hooks/hooks.json`, selected by `agent_type`.
- State paths and the `HARNESS_REVIEW_*` names keep the old `second-opinion` naming so existing ledgers carry over; do not rename them.
- The fork prompt templates are tuned by experiment; change their wording only with a re-measurement (see `docs/rationale-inherit-advisor.md`).
