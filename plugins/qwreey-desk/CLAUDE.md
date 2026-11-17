# qwreey-desk (plugin development)

A Claude Code mod: a pane (`/desk`), a band above the prompt and a model tool `desk` that keep pending decisions, the plan, running work and a work log outside the chat. Decisions and the plan are record files in the project's git repo (`.claude/plan/`); the plugin store keeps the pane's own state. What users see: `README.md`.

## Where things are
- `hooks/register.tsx`: hook wiring (session start, loading the store and the files, the `desk` tool, prompt and task events, band and pane render, scroll, transcript row for the tool).
- `hooks/views.tsx`: the detail views (decision, step, outbox) with a fixed header, a scrolled body and pinned input footers.
- `hooks/layout.ts`: rows as plain data shared with tests: character width, wrapping, tab lists, scrolling, detail paging, caches.
- `hooks/richtext.ts`: styled-text rows (spans, wrapping with hanging indent, markdown, tables); imports the width counting and caches from `layout.ts`.
- `hooks/model.ts`: desk data changes, decision ids (`Q3`, with `D3` read as the same), chat-line parsing (`Q3: b`, `Q3 코멘트: …`), band text, the split between store and files (`toUi`, `withFiles`, `fromV1`).
- `hooks/records.ts`: the file format (frontmatter per the coderag agent-records skill, sections 맥락, 선택지, 코멘트, 답; the plan's task list) and its parser, which keeps what it does not know.
- `hooks/files.ts`: file I/O through `$.fs` and `$.process` (git detection, reading with a size and time cache, writing, `git mv` or `mv` to the archive, moving a desk-1 store into files). Functions that take `$` here are function declarations: the mod validator follows `$` across an import only into those.
- `types/index.d.ts`: the `$.state` contract and the stored shape (tag `desk-2`, the pane's state; `desk-1` was the whole desk and is read once into files; new fields stay optional or come with a migration and a test seeded with old data).
- `.claude-plugin/types/` and `tsconfig.json`'s base are written by the engine when the mod loads; not committed.

## Checks
From this folder: `tsc -p .` (TypeScript 5.x), `claude plugin validate .`, `claude plugin test .` (`tests/kit.tsx` stands for the engine and a project folder with git; `tests/files.test.tsx` covers the files). The mod API reference is the bundled `plugin-authoring` skill (its `types/claude-code.d.ts`).

## Rules for this plugin
- A live session hot-reloads the mod at the end of every turn that changed a file, so a half-applied change breaks the open pane. Build and test in a scratch copy and swap `hooks/` in one step (`mv -T --exchange`), or keep each saved file consistent on its own.
- Layout must not move while the user reads: fixed widths and heights, no column whose width depends on content, counts in reserved slots.
- Prefer single-width ASCII for marks; emoji and some box or bullet glyphs draw two cells wide in some terminals.
- User-facing text is Korean; the tool description and hidden notes to the model are English.
- The desk never deletes or commits a file: it writes, and moves an answered decision to the archive. A change to the file format keeps old files readable (parser tolerant, round-trip tests).
