# Frontmatter keys

Every key coderag indexes. All are optional for `.claude/` records. Pack knowledge docs (skill references and the like) are a lint error without `title` and `description`, because pack search picks documents by that line alone.

## Schema

```yaml
---
title: Type function policy                 # else the first H1, else the file name
description: type functions are diagnostic only; no result-type synthesis, two allowed sites   # one line, <= 200 chars; else the first paragraph is the summary
keywords: [type function, 타입 함수, D-04, types library]   # synonyms, other-language terms, question codes not in the body; weighs more than the title
kind: decision                              # else inferred from the folder (table below)
status: active                              # `<state> [in|by <target>] [; note]`, grammar in SKILL.md
last_verified: 2026-11-10                   # the day the body's claims were last measured or checked
review_after: 2027-02-01                    # after this day coderag stale reports it
---
```

- The older key `superseded_by: <path|id>` reads as `status: superseded by <path|id>`. If both are present the targets must match (lint error otherwise). New records write only the status line.
- Extension keys (coderag/.claude/base/records.md §17): `category` (one canonical path, e.g. `luau/types/recursion`) · `tags` (free words) ·
  `evidence` (verified|described|partial; aggregated from sections when omitted) · `lifecycle` (proposed→rfc→flagged→implemented-cli→beta-roblox→released-roblox→deprecated→removed) ·
  `rfc` · `applies_to` (`[luau >=0.739, luau-lsp >=1.70.1]`) · `since` · `last_confirmed` (the **tool version** re-checked, unlike the date in last_verified) ·
  `source` (repro snippet path) · `origin` (source record it was moved from) · `see` · `overrides` · `read` (sections|whole). `-` and `_` in keys are the same.
- Values use a YAML subset only: `key: value`, `key: [a, b]`, `- item` lists, `>`/`|` blocks. A value containing a colon may be quoted or not.

## Section meta lines

A line `key: value · key: value` directly under a `##` or `###` heading is that section's meta. The first key must be a known key.

```markdown
## §5 "Code is too complex" and limit flags
evidence: described · origin: quad typing-limits 8.5 · source: `snippets/x.luau`
id: too-complex-flags · category: luau/types/limits · tags: fflags
```

- `id:` pins the section ID (renaming or renumbering the heading keeps `section ….too-complex-flags`). It must be unique within the document.
- A section `status: verified|described` reads as `evidence` (older form). A section `status: archived` hides **only that section** from search.
- Keys a section lacks are inherited from the file frontmatter (category, tags, lifecycle, applies_to, last_confirmed, ...).
- Korean aliases: `근거`→source, `원천`→origin, `연결`→see. Unknown keys are kept as-is. A single `<!-- meta: key: value -->` line works the same.

## Kind and folder

| kind | what | folder |
|---|---|---|
| plan | what we intend to do (living) | `plan/` (old `plans/`) |
| base | settled design and background, wins on conflict | `base/` |
| research | investigation and drafts before a decision (living) | `research/` |
| audit | point-in-time measurements, reviews, debates (snapshot) | `audit/` |
| handoff | state for the next session (snapshot) | `handoff/` |
| session | imported session records (snapshot) | `sessions/` (old `session/`) |
| archive | living records that left active; hidden from default search | `archive/<origin folder>/` |
| decision | user decisions and their grounds | `decisions/`, question ledgers |
| reference | material other documents cite | `reference/` |
| index | folder index (README) | `*/README.md` |
| guide · todo | how-to · task list | root |

- coderag stale does not check path references inside snapshots or `archive/`.
