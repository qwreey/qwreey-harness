---
description: Source-code comment conventions, all toolkits. Details are in the conventions:comments skill
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt}"]
---
# Comments
- Write why: the constraint, the trap, the reason for an odd-looking choice.
- History (dates, ledger ids, rounds, who decided) goes to the commit message, CHANGELOG or ledger. Existing ids are never deleted; move them to a `Ref:` tail line.
- Type only what a keyboard types: ASCII and the file's comment language. No arrows, em dashes, curly quotes or emoji.
- Details, repo settings and what to do with a hook notice: load the `conventions:comments` skill. A repo's own rules win.
