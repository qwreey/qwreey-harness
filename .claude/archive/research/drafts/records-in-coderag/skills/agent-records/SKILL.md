---
name: agent-records
description: Convention for agent records under a repo's .claude/ (plan, base, research, audit, handoff, sessions, archive): which folder a record goes in, the one-line status, when a record closes and moves to archive, optional frontmatter (title, description; key list in references), README indexes, raw output, and how to find old records. Use it whenever you write, edit, supersede, close or move a record under .claude/, see a records-check or coderag lint notice, or set up .claude/ in a new repo. 기록 규약, 기록 폴더, 아카이브, status, frontmatter.
argument-hint: "[record path or note]"
---

# coderag:agent-records

Records hold raw context for agents: decisions, why, evidence, user quotes. Human-facing docs go in `docs/`. A repo's own `.claude/README.md` wins over this file. This does not cover `.claude/{agents,skills,rules,hooks,worktrees,commands}`; those follow their own frontmatter.

## Two classes

- Living (`plan/`, `base/`, `research/`): edited as things change; carries one status; moves to `archive/` when it leaves active.
- Snapshot (`audit/`, `handoff/`, `sessions/`): true at its date. Never edit its content and never archive it. The one exception: when files move, rewrite old paths to the new ones by script from the move map (path text only). No status, no frontmatter required. One header line after any frontmatter: `> Snapshot <YYYY-MM-DD>. May differ from now; check current files and git log before relying on it.`

## Folders

Create on first use. The only mandatory file is `.claude/README.md`: one line per folder in use.
- `plan/`: what we intend to do, open decisions.
- `base/`: settled decisions and project background; wins over other records on conflict.
- `research/`: investigation and drafts before a decision.
- `audit/NN-slug/`: measurements, reviews, debates at a point in time.
- `handoff/`: state for the next session.
- `sessions/` (a sibling's `session/` is accepted): records imported by q; generated, no README.
- `archive/<origin folder>/`: living records that left active, at their original subpath.
- `packs/<pack>/`: development material for a pack in this repo, same folders inside.

coderag infers `kind` from the folder; a frontmatter `kind` overrides it.

## Status (living records)

One line, in frontmatter if the file has one, else as the first line `status: ...`. Never both.

    status: <state> [in|by <target>] [; <note>]

- `active`: a current source someone should read. To pause write `active; on hold until <condition>`; there is no `paused`.
- `landed in <path>`: the content now lives at <path>; read that.
- `superseded by <path|id>`: replaced; read the target.
- `rejected [by <path|id>] [; <reason>]`: decided against; the body keeps why.
- `archived [; <note>]`: nobody needs it as a current source any more, and nothing replaced it.

No date on the status line (git knows). Write supersession as `status: superseded by X`; the older key `superseded_by: X` is read as the same thing but is not written. A path target must exist.

## When a record leaves active

The test is whether anyone should still read it as a current source. Finishing the work a record describes is never by itself a reason.
- `base/`: stays active after implementation; it is the canonical spec for extending or reusing that feature.
- `plan/`: usually closes as `landed in <where the result lives>` once executed.
- `research/`: closes when its conclusion lands (`landed in`) or is decided against (`rejected`).

In the same commit, the agent that changed the status: `git mv` the file to `archive/<origin folder>/<same subpath>`, fixes links to it in living docs and the README, and rewrites its old path in snapshots (path text only). Never delete a record; deleting is the user's call.
When superseding, start the new record with one line `Supersedes: <old path>` and change only the old record's status line; its body stays as evidence.

## Frontmatter (optional)

Not required. Do not backfill old records (`/coderag:docs-backfill` runs only when the user calls it). Never required for snapshots.
Recommended for a new living record: coderag search shows `description` as the one-line result, and other agents decide from that line whether to open the file.

    ---
    title: Type function policy
    description: type functions are diagnostic only; no result-type synthesis, two allowed sites
    status: active
    ---

- `description`: what it decides and when to open it, one line, at most 200 characters. Put distinctive words in it (function names, question codes, numbers); state the conclusion, not "this doc covers ...".
- `keywords` (synonyms and other-language terms not in the body; the highest search weight), `kind`, `last_verified`, `review_after`, section meta lines and extension keys: [references/frontmatter-keys.md](references/frontmatter-keys.md).

## README index

Each living folder and `audit/` may have a README: 1-3 hand-written lines, then a list. Either hand lines `- [name](path) - description` (no status, dates or banners in them), or a committed generated block: `coderag gen && coderag static-gen --dir <folder>` (text outside the markers is kept). Keep it complete: every living record appears.

## Raw output

Put bulky output in `.claude/**/raw/` and gitignore it (`.claude/**/raw/`). The summary `.md` keeps the key numbers and the command that regenerates raw. Budgets: a file over 200KB, a top-level `.claude/<folder>` over 5MB.

## Finding records

Search first (`q:recall`, or `coderag search --abs --layer project`), then read only the returned line ranges; never read whole audit or session records. Default search hides records that are not active and everything under `archive/`: add `--all` when looking for why something changed. grep over `.claude/` always works.

## Checks

- `coderag lint <file>`: frontmatter values and status grammar; exit 1 on errors or warnings, `--verbose` also shows advice.
- `coderag stale`: past `review_after`, missing supersession targets and paths, records changed since indexing.
- `python3 -I <q plugin>/scripts/records_check.py` (also run by q:doctor): bad status lines, closed records outside `archive/`, index gaps, broken links in living records, oversized files, ungitignored `raw/`.

Fix what you introduced; list the rest for the user.
