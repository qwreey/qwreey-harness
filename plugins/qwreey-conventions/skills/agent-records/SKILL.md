---
name: agent-records
description: Convention for agent records under a repo's .claude/ (plan, base, research, audit, handoff, sessions, archive): which folder a record goes in, the one-line status, when and how to archive a finished record, README indexes, raw output, and how to find old records. Use it whenever you write, finish, supersede or move a record under .claude/, finish a plan or research doc, see a records-check notice, or set up .claude/ in a new repo. 기록 규약, 기록 폴더, 계획 문서 마무리, 아카이브, status.
argument-hint: "[record path or note]"
---

# qwreey-conventions:agent-records

Records hold raw context for agents: decisions, why, evidence, user quotes. Human-facing docs go in `docs/`. A repo's own README wins over this file. This does not cover `.claude/{agents,skills,rules,hooks,worktrees,commands}`.

## Two classes

- Living (`plan/`, `base/`, `research/`): edited as things change; carries a status; moves to `archive/` when finished.
- Snapshot (`audit/`, `handoff/`, `sessions/`): true at its date. Never edit its content and never archive it. The one exception: when files move, rewrite old paths to the new ones by script from the move map (path text only, nothing else). No status. One header line after any frontmatter: `> Snapshot <YYYY-MM-DD>. May differ from now; check current files and git log before relying on it.`

## Folders

Create on first use. The only mandatory file is `.claude/README.md`: one line per folder in use.
- `plan/`: what we intend to do, open decisions.
- `base/`: settled decisions and project background; wins over other records on conflict.
- `research/`: investigation and drafts before a decision.
- `audit/NN-slug/`: measurements, reviews, debates at a point in time.
- `handoff/`: state for the next session.
- `sessions/` (a sibling's `session/` is accepted): records imported by q; generated, no README.
- `archive/<origin folder>/`: finished living records at their original subpath.
- `packs/<pack>/`: development material for a pack in this repo, same folders inside.

## Status (living records)

One line, in frontmatter if the file has one, else as the first line `status: ...`. Never both.

    status: <state> [in|by <target>] [; <note>]

- `active`: current. To pause write `active; on hold until <condition>`; there is no `paused`.
- `landed in <path>`: the content now lives at <path>; read that.
- `superseded by <path|id>`: replaced; read the target.
- `rejected [by <path|id>] [; <reason>]`: decided against; the body keeps why.
- `archived [; <note>]`: finished with no successor.

No date on the status line (git knows). `superseded_by: X` equals `superseded by X`. A path target must exist.
A new living doc needs frontmatter with `title`, `description`, `status`: the description is what a search result shows, so write what it decides and when to open it. Do not backfill old docs.

## When a status leaves active

In the same commit, by the agent that changed it: `git mv` the file to `archive/<origin folder>/<same subpath>`, fix links to it in living docs and the README, and rewrite its old path in snapshots (path text only). Never delete a record; deleting is the user's call.

## README index

Each living folder and `audit/` may have a README: 1-3 hand-written lines, then a list. Either hand lines `- [name](path) - description` (no status, dates or banners in them), or a committed generated block: `coderag gen && coderag static-gen` (then commit the result). Keep it complete: every living doc appears.

## Raw output

Put bulky output in `.claude/**/raw/` and gitignore it (`.claude/**/raw/`). The summary `.md` keeps the key numbers and the command that regenerates raw. Budgets: a file over 200KB, a top-level `.claude/<folder>` over 5MB.

## Finding records

Search first (`q:recall`, or `coderag search --abs --layer project`), then read only the returned line ranges; never read whole audit or session records. coderag infers kind from the folder and hides finished docs (superseded, rejected, archived, `archive/`) from default search: add `--all` when looking for why something changed. grep over `.claude/` always works.

## Checks

`python3 -I <q plugin>/scripts/records_check.py` (also run by q:doctor) reports bad status lines, finished docs outside `archive/`, index gaps, broken links in living docs, oversized files and ungitignored `raw/`. Fix what you introduced; list the rest for the user.
