---
name: import
description: Copy pending auto-summarized session records into this repo's records home in one command, or dismiss them. Use when a session-log reminder says records are pending, before a commit, or when cleaning up records.
---

# /q:import — move pending session records into the repo

Records are snapshots and are copied verbatim (plus a two-line header). No curation, no rewriting.

1. Run `session-log import` (fallback `"${CLAUDE_PLUGIN_ROOT}/bin/session-log" import`). It copies every pending record into the records home and marks it imported. Add rids to import only some.
2. If it says no records home is set, ask the user once (options: `docs/sessions/` team-visible, `.claude/records/` agents only, an existing history dir, or `session-log home --archive-only` to keep them outside the repo), then save it with `session-log home <path>` and re-run.
3. Not wanted: `session-log dismiss <rid…> --reason "<why>"`.
4. Include the copied files and `.claude/session-log.json` in your next commit; the plugin never runs git.
