# Commit B breakers (paths that move with audit/ decisions/ drafts/ handoff/)

Code/config that must change (file:line):
- `.claude/conventions.json:2` exclude `["drafts/**","audit/drafts/**"]` -> `.claude/research/drafts/**`, `.claude/archive/research/drafts/**`, `.claude/audit/drafts/**`.
- `home/.claude/harness.env:22` HARNESS_DELEGATE_REGISTRY=`${HARNESS_DOCTOR_ROOT}/drafts/delegate/skills/delegate/registry.tsv` (runtime path) -> `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/...`; line 21 and 34 comments.
- `plugins/q/skills/doctor/scripts/toolkits/web.py:58` PLUGINS_REF (printed to the user) `audit/16-marketplace.md#...` -> `.claude/audit/16-marketplace.md#...`.
- `plugins/q/scripts/sllib/records_home.py:19` HISTORY_CANDIDATES: add `.claude/audit`, `.claude/handoff`.
- `plugins/qwreey-conventions/hooks/conventions-check.py:64,90,91` history-path regexes (`audit/` still matches as substring in `.claude/audit/`; `plan/`, `archive/`, `base/`, `research/` not detected); line 21-22 doc text.
- `plugins/q/skills/doctor/scripts/scan.py:173,677,805,853,888,1055,1062` intake/HUMAN_TODO/`claude-doctor/drafts/delegate` wording (logic is git-root based; 805 is the only path string). `intake` also in doctor SKILL.md and references/{worktrees,drift-and-settings,toolkits/*}.md.
- `.gitignore:5-7` intake lines (only if intake moves; unchanged under the proposed map).
- `CLAUDE.md:5,10,11,12` (PLAN.md stays; decisions/, audit/, handoff/, drafts/ pointers), `README.md:14-18` layout table.
- Docs: `plugins/q/docs/session-log.md`, `plugins/q/skills/doctor/references/{drift-and-settings,staleness-and-kb}.md`, `references/toolkits/README.md` mention `drafts/`.
- Comments citing `audit/NN` in plugins/*.py: 32 lines (no behavior).
- Tests: none read audit/ (survey 36 sec. 3 still holds); test_records_check.py already uses `.claude/audit`.
- Not movable: `plugins/`, `.claude-plugin/` (marketplace path), PLAN.md stays at root (user decision).

Mechanical link rewriting counts (tracked *.md): 42 relative markdown links in total, 25 of them point to audit/decisions/drafts (audit 10, decisions 13, drafts 2; all from files inside those folders); 351 inline-code path mentions `` `audit/...` `` / decisions/ / drafts/ / handoff/ across tracked md (need string rewriting, not link rewriting). Snapshots (audit, handoff) must not be edited per the skill, so inside them only the unchanged-relative links survive; their `audit/NN` text mentions are left as is (resolve via a map note or grep).
