---
name: back
description: 자리 복귀 — away 모드를 끄고 비운 동안 쓴 비용과 서브에이전트를 요약한다
disable-model-invocation: true
allowed-tools: Bash(python3 *subagent_ledger.py *)
---

# back

Below is the result of running `/q:back` (if output is already there, do not run it again; if only a run instruction is there, run that command once).

!`python3 "${CLAUDE_SKILL_DIR}/../../scripts/subagent_ledger.py" back ${CLAUDE_SESSION_ID}`

## What to do
If away mode was not on, relay that line only.
1. Show the summary above to the user (numbers unchanged).
2. Then add what was done while away in at most 3 lines: what finished, what is in progress (including running subagents), what needs a user decision.
3. If the budget was exceeded, write in one line which task cost the most and how to reduce it next time (smaller model, smaller pass).
Reply in Korean.
