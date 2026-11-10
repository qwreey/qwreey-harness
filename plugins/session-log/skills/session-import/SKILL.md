---
name: session-import
description: Review auto-summarized session records waiting outside the repo (session-log pending) and bring the useful ones into this repo following its own record conventions, or dismiss them. Use when a session-log reminder says records are pending, before a commit, during a handover, or when cleaning up records.
---

# /session-import — take pending session records into this repo

The session-log plugin writes summaries **outside** the repo (`${XDG_DATA_HOME:-~/.local/share}/session-log/<project-key>/records/`).
Nothing reaches git until the repo's main agent (you) imports it. You decide what goes in and in which shape.

## Steps
1. List: `session-log pending` (fallback: `"${CLAUDE_PLUGIN_ROOT}/bin/session-log" pending`).
   Each line: `rid  ~tokens  sections  created  [⚠flagged]` + one-line description.
2. Learn this repo's convention first: look for `.claude/session/README.md`, existing `.claude/session/*.md` names,
   handover/todo files. Do not invent a new layout if one exists.
3. For each record, read only what you need: `session-log show <rid> --section N`.
   Items marked `⚠원문 불일치` / `⚠근거 줄 다름` failed the source check; verify against the transcript `(L…)` or leave them out.
4. Choose per record:
   - **import as is**: `session-log import <rid> [--to .claude/session/]` copies the file (coderag frontmatter kept) and marks it imported.
   - **merge**: write/extend the repo's own session note in its convention (quote user directives verbatim), then
     `session-log import <rid> --merged-into <repo-relative path>` (marks it imported without copying).
   - **skip**: `session-log dismiss <rid> --reason "<why>"`.
5. Commit is yours: include imported/merged files in your next commit (the plugin never runs git add/commit).
   After the commit, `session-log status` shows the record as imported with that commit.

## Rules
- Do not edit records in the external store; they are the append-only source. Edit the repo copy instead.
- A record that gets new sections after import shows up as pending again ("new sections since import").
- Prefer one short repo note per day/topic over copying every auto record when the repo already has narrative session notes.
