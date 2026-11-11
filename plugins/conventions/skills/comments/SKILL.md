---
name: comments
description: Conventions for source-code comments. A comment says why the code is this way now (the constraint, the trap, the reason for an odd choice); history such as dates, ledger ids, rounds and who decided goes to the commit message, CHANGELOG or ledger. Use it whenever you write or edit comments, when a conventions hook notice names comment lines you added, and before committing code with new comments. Also covers which characters and language comments use. 주석 정리, 주석 규칙, 주석 이력 옮기기.
argument-hint: "[file or note]"
---

# conventions:comments

A comment answers the question a reader has while looking at this line of code today. Anything else belongs somewhere else.

## When a hook notice arrives

The notice names a file, the line numbers you added, and a category. Fix only those lines, in the same edit pass.

| Category | Fix |
|---|---|
| history marker | Keep the reason as a sentence. Move the history to the commit message, CHANGELOG or ledger. If the repo tracks ledgers, keep the pointer as a `Ref:` tail (below). |
| Ref tail without a reason sentence | Write the reason sentence above the tail. A bare pointer is useless to a reader without the ledger. |
| non-keyboard symbol | Replace with what a person types: ASCII punctuation or plain words. |
| invisible character | Delete it. Retype the line if it is not visible. |
| language mismatch | Rewrite the comment in the file's comment language. |

If a flagged line is a public id or a deliberate exception, leave it and say why in one clause to the user. The notice is a nudge, not a verdict.

## What a comment says

- Keep: the constraint, the trap, the reason for the odd-looking choice, the invariant a caller must hold.
- Move out: when or by whom something changed, `previously X`, `fixed from the old way`, round or session numbers, audit and session paths, `as the user decided`, `per discussion`, user quotes.
- Test: if deleting the sentence would not change how a future editor treats the code, it is not a comment.

History goes to one of three places: the commit message (default), a CHANGELOG, or a ledger document the repo already keeps. Do not create a new file to hold history.

## Pointers to a ledger

When the repo tracks ledgers, write the reason as a sentence first, then one tail line:

```
-- Clamp the index so the loop never reads past the end.
-- Ref: <date> <ledger id> <doc section>
```

- Never leave a bare id or date as the whole comment.
- Existing ids and numbers are never deleted. Removing the way back to the ledger destroys information. Move them into a `Ref:` tail.
- A documentation block (`---`, `///`, `/** */`) puts the `Ref:` line above the block, in the same comment run.

## Characters

Comments use what a person types on a keyboard: ASCII, plus the letters of the comment language (Hangul, accented Latin, kana and the like, entered through an IME). Symbols a person does not type mark a comment as machine-written, so avoid them:

- arrows, dashes longer than a hyphen, middle dot, section sign, ellipsis character, circled digits, box-drawing lines (U+2190 and up)
- curly quotes, fullwidth forms, emoji and status pictographs
- invisible and direction-control characters (zero-width, NBSP, bidi marks). These are checked on the whole line, code included, because the reader and the parser see different text.

Write `->`, `-`, `...`, straight quotes, `ok`, `FAIL`, `NOTE:` instead. Only the lines you add are judged; existing symbols stay.

## Language

- A file follows the language of its existing comments. Korean is a normal comment language.
- A new file follows the repo's `comment_language`, else the majority of sibling files in the folder. With neither, nothing is checked.
- A public library that wants English only sets `"comment_language": "en"`.
- Tool directives (`--!strict`, lint-disable lines) are not language.

## Style

Write for a person reading in a diff or a terminal.

- Length: as much as the reason needs and no more. One line is typical. A comment longer than the code it explains usually wants to be a design note somewhere else.
- Silence where nothing is surprising. Do not restate the code, label sections with banners, or describe an obviously named function.
- Force where it is needed. A real trap gets a plain, direct warning right at the line. A routine reason is a quiet clause. Do not use capitals, exclamation marks or markers like IMPORTANT for ordinary notes; one marker per real hazard at most.
- Vocabulary: plain words the surrounding comments already use, identifiers in backticks, ASCII punctuation. Skip ceremony words (robust, seamless, leverage, ensure, crucial).

```
-- Bad: Ensures robust handling of the edge case (added in round 3, see H-973).
-- Bad: Increment i by one.
-- Good: Walk in reverse so removals do not shift indices we have not visited.
-- Good: Roblox fires this twice on respawn; the second call must be a no-op.
```

## Repo settings

`.claude/comments.json` in the repo (all keys optional):

```json
{"comment_language": "ko", "allow_chars": ["emoji", "~"], "public_ids": ["Quad\\d{4}"], "exclude": ["docs/**"]}
```

- `comment_language`: `en`, `ko`, `ja`, `zh`, `ru`. Used for new files.
- `allow_chars`: `"emoji"` allows emoji; any other entry is a string of characters to allow.
- `public_ids`: regexes for identifiers that are not history.
- `exclude`: path globs the hook skips. `patterns` can override or disable a detector, `allow_ref_tail` turns the `Ref:` allowance off.
- Environment variable `CONVENTIONS_CHECK=off` silences the hook.
- A repo's own `.claude/rules/` or conventions file wins over this skill.

## Public ids are not history

Error codes the project documents for users, standard and spec numbers (UTF-8, H264, ES2020), and issue links meant for readers stay in comments.

## Existing comments

Fix only lines you touch anyway. Do not rewrite old comments in bulk or start a cleanup pass unprompted. A bulk cleanup is for when the user signals there is room for it.
