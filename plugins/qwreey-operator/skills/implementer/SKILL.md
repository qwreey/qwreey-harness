---
name: implementer
description: How to hand implementation to a background subagent and merge it - brief template, working alongside it, verify-and-merge, follow-ups. Use before you launch an implementer, when a delegate-nudge notice appears, or when the user says "서브에이전트한테 맡겨", "구현 넘겨", "수행자 돌려", "백그라운드로 구현해", "hand this off".
---

# qwreey-operator:implementer

When to hand off and which model are in the session context (`## Delegation (qwreey-operator)`). This is the procedure.

## Brief
The subagent sees only the brief. Include:
- Goal, and the user's own words for it (quoted).
- What is ruled out and why (rejected approaches, decisions already made).
- Files and canon to read first (paths, not summaries).
- Scope and do-not-touch paths.
- Done criteria, including the exact test command.
- Report format: changed files, test output, open questions. No commit.

## While it runs
- Launch with `run_in_background`; keep talking with the user instead of waiting.
- Do not edit the same tree concurrently. If main must touch overlapping files, give the subagent a worktree (`isolation: "worktree"`).

## Verify and merge
1. Rerun the tests and compare the report with the done criteria (changed files within scope, `git status`). The report is a claim; open a file only where the report is vague or the tests do not reach. Reading the whole diff in main spends the context the hand-off saved.
2. For large or risky changes, a fresh reviewer subagent reads the diff (`qwreey-advisor:fresh-advisor` if installed, else a new subagent with a short brief); reproduce each finding before acting on it.
3. Main commits; the subagent never does.

## Follow-ups
Send fixes to the same subagent with `SendMessage`. If its context has grown large or the task changed shape, start a new subagent with a fresh brief.
