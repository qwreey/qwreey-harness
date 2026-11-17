---
name: docs-cleanup
description: 모델용 문서 정리. 경로(없으면 저장소 전체)의 CLAUDE.md, SKILL.md, rules, agents, 스킬 문서에서 이력과 보이지 않는 문자를 찾아 기계적인 것은 도구로 고치고 나머지는 지금의 사실로 다시 쓴다
argument-hint: "[path ...]"
disable-model-invocation: true
allowed-tools: Bash(python3 *conventions-scan.py *)
---

# docs-cleanup

Below is the scan summary of model documents for the paths the user gave (the whole repo when none), capped at 30 seconds. If output is already there, do not run it again.

!`python3 -I -X utf8 "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py" scan --kind doc --summary --top 15 --budget 30 --exit-zero $ARGUMENTS`

## What to do
SCAN is `python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py"`; pass `--kind doc` and the same paths as above.
1. If the summary has a `partial:` line, it covers only the files read in time: run the command that line gives with Bash (timeout 600000) before you decide. If the full summary shows no problems, say so in one line and stop.
2. Run `SCAN fix --dry-run <paths>`, then `SCAN fix <paths>`. It only removes invisible characters from prose and leaves frontmatter, code fences, inline code, URLs and paths alone.
3. Run `SCAN scan <paths>` and rewrite each history line by the agent-docs rule: the current fact or instruction stays, in the present tense, with at most one sentence of why. Who decided, when, audit or round numbers, measurement tags, change narration and correction banners move to the commit message or a ledger the repo already keeps; do not create a file for them. A line that is both fact and history is split.
4. A ledger or decision id stays only on a line that names its `.md` file shipped with the document (same skill or plugin); otherwise give the file too or drop the id. Files under `skills/**/references/` may keep dates, ids and old-pattern notes.
5. A line that is right as it is (a quoted trigger phrase, a public id, a version requirement) stays; list it in the report.
6. Files reported as `copies left unfixed`: fix the canon instead, then `python3 -I tools/sync-copies.py --apply` where the repo has it.
7. Report in Korean: files changed, counts by category, what was left and why, and the history text the commit message should carry. Do not commit unless the user asks.
