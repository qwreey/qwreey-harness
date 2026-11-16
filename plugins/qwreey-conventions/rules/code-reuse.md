---
description: One definition per fact: policy values vs invariants, marked copies, libraries. All toolkits; pairs with the reuse-check hook, details in the qwreey-conventions:code-reuse skill
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
# Code reuse

## Values
- In code that runs against other repos or projects (tools, plugins, libraries), a value two projects could reasonably want different (folder or extension lists, size limits, stage ladders, tool names) is policy: read it from config, with a `DEFAULT_*` fallback in code. Values fixed by a format, spec, outside tool or correctness stay `const`.
- `DEFAULT_` promises an override; do not use the prefix for a value nothing overrides.
- A value two sides must agree on (client and server, two scripts of one game) lives in one shared module both require. A "same as X" comment is an unchecked copy.

## One definition
- Before writing a helper (parser, walker, hash, glob, date, string trim) or a list of names (statuses, kinds, levels), search for one this package can import, and use or extend it. Two copies of one fact drift apart.
- A copy this package cannot import (separately installed package, another repo, another language): keep it, mark it `@copy-of: <path>[#NAME]` in a line comment (or wrap copied lines in `@start-replace: <path>#<NAME>` ... `@end-replace`), and compare it with the source in a test, or generate one from the other. Where the repo has `tools/sync-copies.py`, edit the canon (`lib/`) and run it with `--apply` instead of editing copies. Do not replace it with an import across the package boundary. Vendored trees are not marked or edited: change the source and re-vendor.
- A literal checked against a type (a Luau or TS union) already references it. Names owned by an outside API (engine classes, tool names) are not your vocabulary.
- A list that mirrors a union: TS derives the union from the list (`(typeof LIST)[number]`); Luau annotates the list with the union type.

## Libraries
- Hand-writing a parser or algorithm that a well-known library provides: put `why not <library>: <reason>` at the top of the module (measured size or startup budget, exact parity with a reference, tolerant parsing, the runtime cannot install it). Adding a dependency is the user's call; propose it with measured cost (size, build time, dependency count).

## Scope
- Apply this to code you add. Do not refactor existing code for it unprompted; old duplicates in edited files are reported to the user at turn end.
- Before you add a `@copy-of` or `@start-replace` marker, or act on a reuse notice, load the `qwreey-conventions:code-reuse` skill. A repo's own rules win.
