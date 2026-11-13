---
name: implementer
description: Hand a large implementation to a background subagent while you keep talking with the user, then verify and merge it. Use when the work spans 3+ code files, ~150+ new lines or much reading, when a delegate-nudge hook notice appears, or when the user says "서브에이전트한테 맡겨", "구현 넘겨", "수행자 돌려", "백그라운드로 구현해", "hand this off".
---

# qwreey-operator:implementer

Main stays the operator: it talks, decides and verifies; the subagent (the implementer) writes the code from a brief.

## When not to
Keep in main: small edits, applying a decision just made, docs and config, work that needs the user's answers midway (ask first, then hand off), anything whose brief would be longer than the work.

## Brief
The subagent sees only the brief. Include:
- Goal, and the user's own words for it (quoted).
- What is ruled out and why (rejected approaches, decisions already made).
- Files and canon to read first (paths, not summaries).
- Scope and do-not-touch paths.
- Done criteria, including the exact test command.
- Report format: changed files, test output, open questions. No commit.

## Model
- sonnet by default: the work is specified, and it costs about a third of opus per line.
- opus when design judgment remains; say in one line to the user why.
- Tell the user in one line before launch: what, which model, expected size.

## While it runs
- Launch with `run_in_background`; keep talking with the user instead of waiting.
- Do not edit the same tree concurrently. If main must touch overlapping files, give the subagent a worktree (`isolation: "worktree"`).

## Verify and merge
1. Read the diff yourself; do not trust the report.
2. Rerun the tests.
3. For risky or large changes, a fresh reviewer (`qwreey-advisor:fresh-advisor` if installed, else a new subagent with a short brief); reproduce each finding before acting on it.
4. Main commits; the subagent never does.

## Follow-ups
Send fixes to the same subagent with `SendMessage`. If its context has grown large or the task changed shape, start a new subagent with a fresh brief.
