---
name: back
description: Announces the user is back. Turns off away mode and summarizes the cost while away, the subagents launched or queued, and whether the budget was exceeded. User-invoked only. 돌아왔어, 자리 복귀.
disable-model-invocation: true
allowed-tools: Bash(python3 *subagent_ledger.py *)
---

# back

Below is the result of running `/q:back` (if output is already there, do not run it again; if only a run instruction is there, run that command once).

!`python3 "${CLAUDE_SKILL_DIR}/../../scripts/subagent_ledger.py" back ${CLAUDE_SESSION_ID}`

## What to do
1. Show the summary above to the user (numbers unchanged).
2. Then add what was done while away in at most 3 lines: what finished, what is in progress (including running subagents), what needs a user decision.
3. If the budget was exceeded, write in one line which task cost the most and how to reduce it next time (smaller model, smaller pass).
Reply in Korean.
