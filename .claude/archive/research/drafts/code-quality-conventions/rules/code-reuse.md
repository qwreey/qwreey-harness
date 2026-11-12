---
description: Code reuse conventions, all toolkits. Policy values vs invariants, one implementation per job, marked copies, library vs hand-written. Details in the qwreey-conventions:code-reuse skill
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt}"]
---
# Code reuse: values, duplicates, libraries

> A repo's own rules win. Pairs with the PostToolUse hook `reuse-check`, which only informs.

## Policy values
- Test: could two projects reasonably want a different value, and is it a judgment about the target repo rather than about the program's correctness? Then it is policy.
- Policy (folder and extension lists, size limits, stage ladders, tool names) lives in config, a data table or a pack; code keeps only a `DEFAULT_*` fallback that config overrides.
- Values fixed by a format, a spec, an outside tool or correctness (schema versions, grammar tables, security allowlists) stay `const`.
- A list that names one ecosystem (Roblox, Wally, pesde) belongs to that ecosystem's pack, not to the core.
- Use the `DEFAULT_` prefix only when an override exists; readers take the prefix as that promise.

## One implementation
- Before writing a walker, frontmatter or TOML reader, hash, glob, truncation, token estimate or date helper, search the repo for one and extend it. Copies drift apart silently, and the disagreement surfaces as a bug far from both.
- A vocabulary (status names, folder kinds, level names) is defined once and referenced everywhere.
- When a copy is unavoidable (separately installed packages, another repo, a reference implementation), mark it `@copy-of: <path>#<NAME>` and keep a test that compares it with the source.
- A runtime list that mirrors a type union: derive one from the other where the language can (TS `typeof LIST[number]`); where it cannot (Luau), keep them next to each other.

## Libraries and hand-written code
- Prefer the library when the format is correctness-critical and the library is the reference parser (CommonMark, YAML, full_moon for Luau), or when your version would need its own test suite to be trusted.
- Hand-written is right when a measured size or startup budget rules the library out, when behavior must match a reference implementation exactly, or when you need tolerant parsing the library rejects.
- Either way, put one line at the top of the hand-written module: `why not <library>: <reason>`. No reason, use the library.
- Claims about cost are measured: binary size delta, cold build time, dependency count.

## Simplification
- String branches on one variable: see code-structure (Data).
- A long function that chains independent steps becomes step functions run from a table. A lexer, state machine or AST visitor may stay long; its length is the shape of the work.
- An arm that maps each value to itself is a membership test; replace the chain with a set lookup.

## Notices
- Marker syntax, repo settings and what to do with a hook notice: load the `qwreey-conventions:code-reuse` skill. Fix only what you added; old duplicates in edited files are reported to the user at turn end, not cleaned up unprompted.
