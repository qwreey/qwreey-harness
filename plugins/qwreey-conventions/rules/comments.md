---
description: Source-code comment conventions, all toolkits. The whole convention is here; hook notices name the lines and the fix
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt,sh,html,htm}"]
---
# Comments
- Write why: the constraint, the trap, the reason for an odd-looking choice.
- History (dates, ledger ids, rounds, who decided) goes to the commit message, CHANGELOG or ledger. Existing ids are never deleted; move them to a `Ref:` tail line.
- Type only what a keyboard types: ASCII and the file's comment language. A symbol a person did not type marks the comment as machine-written, and editors draw spaces as a faint middle dot, so symbols are easy to misread. Common slips: em dash or en dash (write ` - ` or `:`), middle dot (comma or `/`), ellipsis character (`...`), arrows (`->`), `§` (omit), circled digits (`1)`), curly quotes, emoji (`ok`, `FAIL`, `NOTE:`). Never write a character as a `\uXXXX` escape in a comment.
- Fix only comments you touch anyway; old problems in edited files are reported to the user by the hook at turn end, not cleaned up unprompted.
- Korean comments keep the file's sentence ending (합니다체 or 한다체).
- No banners, capitals or IMPORTANT for routine notes; skip ceremony words.
- On a notice, fix the named lines; leave a deliberate exception and say so once in your report.
- A repo's own rules win.
