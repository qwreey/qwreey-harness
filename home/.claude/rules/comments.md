---
description: Source-code comment conventions, all toolkits. Details are in the qwreey-conventions:comments skill
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt,sh,html,htm}"]
---
# Comments
- Write why: the constraint, the trap, the reason for an odd-looking choice.
- History (dates, ledger ids, rounds, who decided) goes to the commit message, CHANGELOG or ledger. Existing ids are never deleted; move them to a `Ref:` tail line.
- Type only what a keyboard types: ASCII and the file's comment language. A symbol a person did not type marks the comment as machine-written, and editors draw spaces as a faint middle dot, so symbols are easy to misread. Common slips: em dash or en dash (write ` - ` or `:`), middle dot (comma or `/`), ellipsis character (`...`), arrows (`->`), `§` (omit), circled digits (`1)`), curly quotes, emoji (`ok`, `FAIL`, `NOTE:`). Never write a character as a `\uXXXX` escape in a comment.
- Fix only comments you touch anyway; old problems in edited files are reported to the user by the hook at turn end, not cleaned up unprompted.
- Details, repo settings and what to do with a hook notice: load the `qwreey-conventions:comments` skill. A repo's own rules win.
