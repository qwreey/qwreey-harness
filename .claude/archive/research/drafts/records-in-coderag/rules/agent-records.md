---
description: Convention for agent records under .claude/ (plan, base, research, audit, handoff, sessions, archive). Details are in the coderag:agent-records skill
paths:
  - "**/.claude/README.md"
  - "**/.claude/{plan,base,research,audit,handoff,archive,packs}/**/*.md"
---
A repo's own `.claude/README.md` wins over this.
- Living records (plan, base, research) carry one status line, in frontmatter else first line: `status: <state> [in|by <target>] [; <note>]`, state = active | landed | superseded | rejected | archived. Write supersession as `superseded by <path>`.
- A record stays active while anyone should read it as a current source; finishing the work it describes is not a reason to close it (an implemented `base/` spec stays active).
- When a status leaves active, in the same commit `git mv` the file to `archive/<origin folder>/`, fix links and the README. Never delete.
- Snapshots (audit, handoff, sessions) have no status; never edit their content (only rewrite paths after a move) and never archive them.
- Frontmatter is optional; for a new living record add `title` and `description` (the search summary). Do not backfill old records.
- Load the `coderag:agent-records` skill for folders, indexes, raw output and finding records.
