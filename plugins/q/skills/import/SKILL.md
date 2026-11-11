---
name: import
description: Copy pending auto-summarized session records into this repo's records home, or dismiss them. Use when a session-log notice says records are pending (it also fires before a commit), or when the user asks to import or clean up session records.
---

# /q:import - move pending session records into the repo

Records are snapshots and are copied verbatim (plus a two-line header). No curation, no rewriting.

1. Run `session-log home` (fallback `"${CLAUDE_PLUGIN_ROOT}/bin/session-log" home`). If it shows `(미설정...)`, ask the user once where records go (options: `docs/sessions/` team-visible, `.claude/records/` agents only, an existing history dir, or `session-log home --archive-only` to keep them outside the repo) and save the answer with `session-log home <path>`. `import` refuses to run without a home unless you pass `--to DIR`.
2. Run `session-log import`. It copies every pending record into the records home and marks it imported; pass rids from `session-log pending` to import only some.
3. Not wanted: `session-log dismiss <rid>... --reason "<why>"`.
4. Include the copied files and `.claude/session-log.json` in your next commit; the plugin never runs git.
