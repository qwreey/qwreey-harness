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
- Moving or deleting files that running hooks or tools execute (plugin scripts, build tools) breaks them for every session using them; do that last, or in a worktree.

## Verify and merge
1. Read the diff yourself; the report is a claim, not evidence.
2. Rerun the tests.
3. For risky or large changes, a fresh reviewer (`qwreey-advisor:fresh-advisor` if installed, else a new subagent with a short brief); reproduce each finding before acting on it.
4. Main commits; the subagent never does.

## Follow-ups
Send fixes to the same subagent with `SendMessage`. If its context has grown large or the task changed shape, start a new subagent with a fresh brief.
