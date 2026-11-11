---
description: 주석 위생. 주석은 코드가 지금 왜 이런가만 쓴다. 날짜·원장 번호·라운드·세션 경로 같은 작업 이력은 Ref 꼬리 한 줄로만 (툴킷 공통, comment-hygiene 훅과 짝)
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
# Comment hygiene - all toolkits

> Policy: the user asked for a hook against work-history comments (2026-11-11). If the repo's `.claude/rules/`, `conventions.md`, or `.claude/comments.json` says otherwise, follow the repo.
> Pairs with the PostToolUse hook `comment-hygiene`. The hook only informs; it never blocks.

## What a comment says
- A comment says why the code is the way it is now: the constraint, the trap, the reason for the odd-looking choice.
- History does not belong in source comments. It goes to the commit message, the CHANGELOG, or the ledger document. History means:
  - when, by whom, or in which round or session something changed;
  - "fixed from the old way", "previously X", "added for Q12";
  - audit or session paths (`.claude/...`, `audit/...`, `session/...`), "as the user decided", "per discussion".

## When the repo tracks ledgers or dates
- Write the reason as a sentence first. Then add one tail line: `<comment> Ref: <date> <ledger id> <doc section>` (for example `-- Ref: 2026-11-10 H-973 typing-limits 8.43`).
- Never leave a bare ledger id or date as the whole comment. Public readers cannot use it.
- If a documentation block (`---`, `///`, `/** */`) follows, put the `Ref:` line above that block, in the same comment run.
- Do not delete existing numbers: removing the way back to the ledger is destructive. Move them into a `Ref:` tail.

## Existing comments
- Do not rewrite or delete old comments in bulk, and do not start a cleanup pass on your own.
- Fix only the lines you touch anyway, in the same edit. A bulk cleanup happens only when the user signals there is room for it.

## Exceptions
- Public identifiers are not history: error codes (`Quad0042`, `error-code: shared`), spec or standard numbers, and issue links the project documents for readers.
- Comment language follows the language already used in that file.

## Details
- The hook flags only comment lines you add: ledger ids, dates, `round N`, `.claude/`, `session/`, `audit/`, and decision phrases. A `Ref:` tail with a reason sentence in the same comment run passes.
- `.claude/comments.json` in the repo can change the patterns, list public ids, and exclude paths: `{"allow_ref_tail": true, "public_ids": ["Quad\\d{4}"], "exclude": ["docs/**"]}`.
