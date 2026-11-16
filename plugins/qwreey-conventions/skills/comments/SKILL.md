---
name: comments
description: Conventions for source-code comments. A comment says why the code is this way now (the constraint, the trap, the reason for an odd choice); history such as dates, ledger ids, rounds and who decided goes to the commit message, CHANGELOG or ledger. Use it whenever you write or edit comments, when a qwreey-conventions hook notice names comment lines you added, and before committing code with new comments. Also covers which characters and language comments use. 주석 정리, 주석 규칙, 주석 이력 옮기기.
argument-hint: "[file or note]"
---

# qwreey-conventions:comments

A comment answers the question a reader has while looking at this line of code today. Anything else belongs somewhere else.

## When a hook notice arrives

The notice names a file and, per category, the line numbers you added, for example `L12 L15 non-keyboard symbol: <chars> (use "-", ",")`. Categories are listed with history marker first. Fix only those lines, in the same edit pass. For symbols the notice lists the offending characters and a replacement; invisible characters are named by code point (`U+00A0`) because you cannot see them.

| Category | Fix |
|---|---|
| history marker | Keep the reason as a sentence. Move the history to the commit message, CHANGELOG or ledger. If the repo tracks ledgers, keep the pointer as a `Ref:` tail (below). |
| Ref tail without a reason sentence | Write the reason sentence above the tail. A bare pointer is useless to a reader without the ledger. |
| non-keyboard symbol | Replace with what a person types, using the table below. |
| escaped character | A `\uXXXX`-style escape inside a comment is a way around the symbol check. Write the replacement from the table, or reword. |
| invisible character | Delete the code point the notice names (for example `U+00A0`). If the line is otherwise fine, rewrite it with a plain space. |
| language mismatch | Rewrite the comment in the file's comment language. |
| layout, interleaved comment, doc summary | Readable-code notices; see Readable code below. |

Example. Notice: `L12 history marker`. Line 12 is `-- Clamp the index (added in round 3, see H-973).` Rewrite it as `-- Clamp the index so the loop never reads past the end.` and put `round 3, H-973` in the commit message. When the repo keeps a ledger, add the `Ref:` tail instead.

If a flagged line is a public id or a deliberate exception, leave it and mention it once in your final report. The notice is a nudge, not a verdict.

## What a comment says

- Keep: the constraint, the trap, the reason for the odd-looking choice, the invariant a caller must hold.
- Move out: when or by whom something changed, `previously X`, `fixed from the old way`, round or session numbers, audit and session paths, `as the user decided`, `per discussion`, user quotes.
- Test: if deleting the sentence would not change how a future editor treats the code, it is not a comment.

History goes to one of three places: the commit message (default), a CHANGELOG, or a ledger document the repo already keeps. Do not create a new file to hold history.

Public ids are not history: error codes the project documents for users, standard and spec numbers (UTF-8, H264, ES2020), and issue links meant for readers stay in comments.

## Pointers to a ledger

When the repo tracks ledgers, write the reason as a sentence first, then one tail line:

```
-- Clamp the index so the loop never reads past the end.
-- Ref: <date> <ledger id> <doc section>
```

- Never leave a bare id or date as the whole comment.
- An id or number already in the code is never deleted, because removing the way back to the ledger destroys information. Move it into a `Ref:` tail. History you are writing now (who decided, which round) goes to the commit message instead.
- A documentation block (`---`, `///`, `/** */`) puts the `Ref:` line above the block, in the same comment run.

## Characters

Comments use what a person types on a keyboard: ASCII, plus the letters of the comment language (Hangul, accented Latin, kana and the like, entered through an IME). Symbols a person does not type mark a comment as machine-written, so avoid them:

- arrows, dashes longer than a hyphen, middle dot, section sign, ellipsis character, circled digits, box-drawing lines
- curly quotes, fullwidth forms, emoji and status pictographs
- invisible and direction-control characters (zero-width, NBSP, bidi marks). These are checked on the whole line, code included, because the reader and the parser see different text.

Replacements:

| Instead of | Write |
|---|---|
| middle dot | a comma or `/` |
| em dash, en dash, horizontal bar | ` - ` or `:` |
| arrows | `->`, `<-`, `=>` |
| circled digits | `1)`, `2)` |
| section sign | leave it out |
| ellipsis character | `...` |
| curly quotes | straight quotes |
| emoji, check and cross marks | `ok`, `FAIL`, `NOTE:` or plain words |

Why the middle dot is flagged too: a person rarely types it on purpose in a code comment (it usually arrives by copy and paste), code uses commas, and editors that show whitespace draw a space as a faint middle dot (and a tab as an arrow), so the symbol is easy to confuse with the editor's own display.

Never write the character as an escape (`\uXXXX`, `\u{...}`) in a comment sentence. The hook flags an escape in a comment as well, and a reader sees the escape text, not the symbol. In code (string literals, regexes) an escape is ordinary code and is not checked.

The check passes letters of every writing system (Hangul, Cyrillic, kana, accented Latin and so on) and digits; only symbols, punctuation outside ASCII, fullwidth forms and emoji are flagged. Only the lines you add are judged; existing symbols stay.

## Language

- A file follows the language of its existing comments. Korean is a normal comment language.
- A new file follows the repo's `comment_language`, else the majority of sibling files in the folder. With neither, nothing is checked.
- A public library that wants English only sets `"comment_language": "en"`.
- Tool directives (`--!strict`, lint-disable lines) are not language.
- A step label (a short English line heading a step inside a body) is not judged for language, so English labels sit in a Korean file. A line with a reason word (`because`, `so`, `must`, `never`, ...), a period, or a word count outside 2-10 is not a label and follows the file's language.
- Korean comments follow the sentence ending the file already uses (합니다체 or 한다체); a new file follows its siblings.

## Style

Write for a person reading in a diff or a terminal.

- Length: as much as the reason needs and no more. One line is typical. A comment longer than the code it explains usually wants to be a design note somewhere else.
- Silence where nothing is surprising. Do not restate a line of code in words, draw banners, or describe an obviously named private function. A short step label above a paragraph is not a restatement: it names what several lines are for, so a reader can skim labels as an index (section Readable code).
- Force where it is needed. A real trap gets a plain, direct warning right at the line. A routine reason is a quiet clause. Do not use capitals, exclamation marks or markers like IMPORTANT for ordinary notes; one marker per real hazard at most.
- Vocabulary: plain words the surrounding comments already use, identifiers in backticks, ASCII punctuation. Skip ceremony words (robust, seamless, leverage, ensure, crucial).

```
-- Bad: Ensures robust handling of the edge case (added in round 3, see H-973).
-- Bad: Increment i by one.
-- Good: Walk in reverse so removals do not shift indices we have not visited.
-- Good: Roblox fires this twice on respawn; the second call must be a no-op.
-- Good (step label above a paragraph): Detach from the previous parent
```

## Readable code

The `readable-code` rule holds the convention and is loaded only where `HARNESS_READABLE_CODE=on` (the user's `~/.claude/harness.env`; a repo turns it off in `.claude/harness.env`). With it on, the hook adds a `layout (readable-code)` part to its notice for functions an edit wrote (half or more of the function's lines) or grew by 15 or more lines:

| Category | Fires when | Answer |
|---|---|---|
| layout | body of 15+ non-blank lines with no blank line, or a run of more than 20 lines without one | Split the whole function into steps with blank lines and labels. If it really is one step (a table literal, one expression), leave it and say so once in your report. |
| interleaved comment | a comment of 2+ lines with code directly above and below, inside a body | Move a design reason above the declaration, apart from the doc comment; keep one line at the trap. |
| doc summary | a public function without a doc comment in the editor's hover form (Luau `---` or `--[=[`, Python docstring, `/** */`, Rust `///`), or a first doc line over 100 characters, or a first sentence that continues on the next line | Write or fix the doc comment. A function flagged here is checked once more after your next edit. Metamethods and private functions are not asked for one. |

The numbers in the notice: lines are non-blank body lines, blank are blank lines inside the body, longest run is the most lines in a row without a blank line (comment lines count). Edits made through Bash are not seen; check them with `python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py" layout <file>`, which prints the same numbers for every function plus labels, multi-name declarations (receiving multiple returns does not count) and one-letter locals.

## Repo settings

`.claude/conventions.json` in the repo (all keys optional; the older name `.claude/comments.json` is read when `conventions.json` does not exist):

```json
{"comment_language": "ko", "allow_chars": ["emoji", "~"], "public_ids": ["Quad\\d{4}"], "exclude": ["docs/**"],
 "label_language": "en", "layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15}}
```

- `comment_language`: `en`, `ko`, `ja`, `zh`, `ru`. Used for new files. The rules hook also prints it in the comments rule (`This repo: comment_language = ...`), so a model sees it without loading this skill.
- `allow_chars`: `"emoji"` allows emoji; any other entry is a string of characters to allow.
- `public_ids`: regexes for identifiers that are not history.
- `exclude`: path globs the hook skips. `patterns` can override or disable a detector (`null` disables), `allow_ref_tail` turns the `Ref:` allowance off, `min_reason_words` (default 3) is how many words a reason sentence needs before a `Ref:` tail counts as backed.
- `label_language`: the language of step labels exempt from the language check (default `en`; `null` turns the exemption off).
- `layout`: thresholds of the readable-code notice (see Readable code).
- Environment variable `CONVENTIONS_CHECK=off` silences the hook.
- A repo's own `.claude/rules/` or conventions file wins over this skill.

## Existing comments

Fix only lines you touch anyway. Do not rewrite old comments in bulk or start a cleanup pass unprompted, because a diff full of unrelated comment edits hides the real change. A bulk cleanup is for when the user signals there is room for it.

For such a cleanup, run `python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py" scan [paths]` (the hook's checks on every line of every file, so you need not read files to find problems), then `fix --dry-run` and `fix`, which replace only unambiguous symbols and invisible characters inside comments and verify that no code changed; rewrite what it lists as needs judgment yourself.

Old comment problems in the files you edited are counted quietly and shown to the user once at the end of the turn, as one Korean line (`손댄 파일에 기존 주석 문제가 남아 있음: a.luau(이력 3, 기호 12) ...`). The hook shows it itself; you do not need to repeat it. A subagent adds nothing, since the main session's line already includes subagent edits.
