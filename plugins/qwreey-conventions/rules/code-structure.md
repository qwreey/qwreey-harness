---
description: 코드 구조 규칙. 파일 길이(800/1,500줄)·예외·분리 방법·폴더·데이터·이름 (툴킷 공통, structure-reminder 훅과 짝)
paths:
  - "**/*.luau"
  - "**/*.lua"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.mjs"
  - "**/*.astro"
  - "**/*.rs"
  - "**/*.py"
  - "**/*.go"
  - "**/*.kt"
---
# Code structure (file length, folders, data) - all toolkits

> If the repo's `.claude/rules/`, `conventions.md`, or `.claude/structure.json` says otherwise, follow the repo.
> Pairs with the PostToolUse hook `structure-reminder`. The hook only informs; it never blocks.

## File length
- Check the target file's line count before adding a feature. Tests get double the limits; generated and pure-data files are excluded.
  - Over 800 lines: name the group to split out, in one line of your work report.
  - Over 1,500 lines: ask the user for a split plan before appending anything.

## Exemptions
- A file may stay over the limit for a solid reason, e.g. type limits, generated code, pure data.
- Record the reason in one of two ways:
  - `<comment> @structure-exempt: <reason>` within the first 10 lines of the file (`--`, `//`, `#`).
  - an entry in `exempt` in `structure.json`.
- No reasonless exemptions ("later", "too much work").

## How to split
- Do a move-only commit first; fix things in the next commit.
- After moving, fix stale paths left in docs and check the seams.
- Do not re-attach features to the leftover chunk. Extract shared state first into a state table or module.

## Folders
- Three or more files with the same prefix in one folder: group them into a `prefix/` folder.
- More than 15 sources of different kinds in one folder: propose a grouping.
- The repo decides the top-level categories (layer, kind).

## Data
- Per-item data with a uniform shape (request name, args, cost, permission, batch, ...) goes in one table; code reads the table.
- If one variable is branched on by string in more than 8 ways, consider replacing the branches with a table.
- Tool-generated data goes in its own file, with the generator path and "do not edit by hand" in the header.

## Naming
- If a user-chosen name or structure conflicts with these rules, do not rename right away. Propose the change with reasons; do bulk edits only after approval.

## Toolkit details
- Luau: `luau-style` skill: `references/structure.md` (cases), `references/splitting.md` (split strategy), `scripts/split-plan.py` (split planner).
- Other toolkits: none yet. Fill in after the toolkit is imported (`/q:doctor` `references/toolkits/`).
