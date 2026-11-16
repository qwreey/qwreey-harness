# qwreey-desk (plugin development)

A Claude Code mod: a pane (`/desk`), a band above the prompt and a model tool `desk` that keep pending decisions, the plan, running work and an away log outside the chat. What users see: `README.md`.

## Where things are
- `hooks/register.tsx`: hook wiring (session start and store load, the `desk` tool, prompt and task events, band and pane render, scroll, transcript row for the tool).
- `hooks/views.tsx`: the detail views (decision, step, outbox) with a fixed header, a scrolled body and pinned input footers.
- `hooks/layout.ts`: rows as plain data shared with tests: character width, wrapping with hanging indent, markdown and tables, tab lists, scrolling, caches.
- `hooks/model.ts`: desk data changes, chat-line parsing (`D3: b`, `D3 코멘트: …`), band text.
- `types/index.d.ts`: the `$.state` contract and the stored desk shape (tag `desk-1`; new fields stay optional or come with a migration and a test seeded with old data).
- `.claude-plugin/types/` and `tsconfig.json`'s base are written by the engine when the mod loads; not committed.

## Checks
From this folder: `tsc -p .` (TypeScript 5.x), `claude plugin validate .`, `claude plugin test .`. The mod API reference is the bundled `plugin-authoring` skill (its `types/claude-code.d.ts`).

## Rules for this plugin
- A live session hot-reloads the mod at the end of every turn that changed a file, so a half-applied change breaks the open pane. Build and test in a scratch copy and swap `hooks/` in one step (`mv -T --exchange`), or keep each saved file consistent on its own.
- Layout must not move while the user reads: fixed widths and heights, no column whose width depends on content, counts in reserved slots.
- Prefer single-width ASCII for marks; emoji and some box or bullet glyphs draw two cells wide in some terminals.
- User-facing text is Korean; the tool description and hidden notes to the model are English.
