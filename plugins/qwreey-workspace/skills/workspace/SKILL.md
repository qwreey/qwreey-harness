---
name: workspace
description: "Load before reading or changing any repo other than the current one: lists the other repos on this machine with one line each (`*-kb` toolkit knowledge repos first), and has the rules (read-only unless the user approves, ask before changing), the live-session check, and the worktree lock check. Also load before deleting any .claude/worktrees entry. Hooks deny writes to a sibling repo until this is loaded."
allowed-tools: Bash(python3 -I *map.py*)
---

# workspace

The repos on this machine are siblings run by one person; several sessions may be working in them at once.

## Rules
- Repos other than this session's are **read-only**. If a change is needed, ask the user first and say which repo and file. Do not "just fix" a sibling.
- Shared toolkit knowledge lives in the `<toolkit>-kb` repos and their skills. Look there first, before opening a sibling repo to see how something is done.
- Never delete a `.claude/worktrees/*` entry (any repo, including this one) before checking its lock file and the live sessions below.
- Do not work around a hook deny with another tool (Grep, a script) to read or write the same path; load this skill and follow the steps.

## Map (generated now)
!`python3 -I -X utf8 "${CLAUDE_SKILL_DIR}/scripts/map.py"`

If the line above is only the command, run it once. The list comes from this machine's Claude Code sessions. If a repo the user means is missing (or should not be listed), tell the user to add it to the `harness_workspace_extra` option (or `harness_workspace_exclude`) with `/plugin configure qwreey-workspace@qwreey-harness`; do not edit settings files yourself. The gate does not need the list: any git repo outside this session's repo counts.

## Live sessions
Which repos have a session running (do not use `pgrep -f`; it matches shell wrappers):
- Linux (`/proc`): `for p in $(pgrep -x claude; pgrep -x agy; pgrep -x codex); do readlink /proc/$p/cwd; done | sort -u`
- No `/proc` (macOS): `lsof -a -d cwd -c claude -c agy -c codex -Fn | sed -n 's/^n//p' | sort -u`

A repo whose path (or a path under its `.claude/worktrees/`) appears there has a live session. Tell the user instead of touching it.

## Worktree lock
Before removing `<repo>/.claude/worktrees/<name>`: `ls -la <repo>/.claude/worktrees/<name>/.git* ; cat "$(git -C <repo> rev-parse --git-common-dir)/worktrees/<name>/locked" 2>/dev/null`. A `locked` file (or a live session whose cwd is inside the worktree) means an agent may be using it: do not remove; ask the user.

## After the user approves a change in a sibling repo
1. Restate the approved scope (repo, files) in one line.
2. Make only that change. Keep it small and do not commit or push unless the user asked for it there.
3. Report to the user what changed, in which repo, so the session working there can be told.
