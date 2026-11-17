---
name: comments-cleanup
description: 기존 주석 정리. 경로(없으면 저장소 전체)의 주석에서 이력, 기호, 보이지 않는 문자를 찾아 기계적인 것은 도구로 고치고 나머지는 다시 쓴다
argument-hint: "[path ...]"
disable-model-invocation: true
allowed-tools: Bash(python3 *conventions-scan.py *)
---

# comments-cleanup

Below is the scan summary for the paths the user gave (the whole repo when none), capped at 30 seconds. If output is already there, do not run it again.

!`python3 -I -X utf8 "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py" scan --kind comment --summary --top 15 --budget 30 --exit-zero $ARGUMENTS`

## What to do
SCAN is `python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py"`; pass `--kind comment` and the same paths as above.
1. If the summary has a `partial:` line, it covers only the files read in time: run the command that line gives with Bash (timeout 600000) before you decide. If the full summary shows no problems, say so in one line and stop.
2. Run `SCAN fix --dry-run <paths>`, then `SCAN fix <paths>`. It replaces only unambiguous symbols and invisible characters inside comments and refuses any change outside them.
3. Run `SCAN scan <paths>` and rewrite what is left (history, `Ref:` tails, escapes, language, emoji, unknown symbols) by the comments rule: keep the reason as a sentence about the code now; history goes to the commit message; an existing id moves to a `Ref:` tail under the reason. Leave a line that is right as it is and list it in the report.
4. Files reported as `copies left unfixed`: fix the canon instead, then `python3 -I tools/sync-copies.py --apply` where the repo has it.
5. Report in Korean: files changed, counts by category, what was left and why. Do not commit unless the user asks.
