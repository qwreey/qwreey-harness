---
name: code-reuse
description: Conventions for values and duplicates in source code. Decides whether a hardcoded value is policy (config with a DEFAULT_* fallback) or an invariant (const), keeps one definition per fact, marks unavoidable copies with @copy-of and a comparison test, and records why a module is hand-written instead of using a library. Use it whenever a qwreey-conventions reuse notice names lines you added, before adding a list of names, a size limit or a helper that may already exist, and before choosing between a library and your own parser. 하드코딩, 중복 구현, 바퀴의 재발명, 사본 표시.
argument-hint: "[file or note]"
---

# qwreey-conventions:code-reuse

Two copies of one fact drift apart, and the bug shows up far from both. A value baked into code that another project would set differently forces a code change where a config line would do. The rule `code-reuse` has the short form; this skill has the steps and the details.

## When a hook notice arrives

The notice names the line you added, the definition it overlaps and the shared strings. Decide in this order:

1. Same fact, and this package can import the other place (same package, or a declared dependency such as a Cargo path dependency, a wally or pesde package, an npm workspace package): delete your list and reference the definition. If neither place is the right home, move it to one module both import. Do not import across a boundary the package does not already have.
2. Same fact, not importable (separately installed plugin, another repo, another language, a reference implementation): keep the copy, mark it (see Markers) and add or extend a test that compares the two. When one side can be derived from the other (a script that reads the Luau source, a build step), generate it instead.
3. A value that varies per project (the policy table below says yes): config, with a `DEFAULT_*` fallback in code. If the list names one ecosystem (Roblox, Wally, pesde), it can instead live in that ecosystem's pack; propose that to the user, because a pack is usually another repo.
4. Alike only on the surface (an outside API's names used for another purpose, a subset chosen for another reason): put `@dup-ok: <reason>` in a line comment above the list. The reason says why they are different facts.

Fix only what you added. Old duplicates in files you edited are counted and shown to the user at turn end; do not repeat that or start a cleanup.

## Policy or invariant

| Value | Kind | Where |
|---|---|---|
| folders to skip, file extensions to index, size limits, stage ladders, tool name lists | policy, in code that runs against other repos | config key, `DEFAULT_*` in code |
| Roblox, Wally or pesde folder and package names | policy, ecosystem | config, or the ecosystem's pack (propose) |
| balance numbers, UI sizes, colors of a game or app repo | the repo's own design | `const` or the repo's data module; not config |
| schema or protocol version, known frontmatter keys, grammar tables | invariant (format) | `const` |
| tool input keys, OS paths an outside tool fixes | invariant (outside fact) | `const`, with the source in one line if not obvious |
| security allowlists | invariant (safety) | `const`; widening is a code review, not a config edit |
| cache caps, prune ages | internal | `const` |
| a value client and server (or two scripts of one game) must agree on | shared fact | one module both `require`; a "same as X" comment is not enough |

The prefix `DEFAULT_` promises an override. A value nothing overrides is a plain `const`.

## Markers

| Marker | Where | Meaning |
|---|---|---|
| `@copy-of: <path>[#NAME]` | a line comment on the line above the copied definition (value copy), or in a line comment or the module docstring within the first 10 lines of the file (file copy) | this is a copy of `<NAME>` (or of the whole file) at `<path>`, repo-relative, or `<repo>:<path>` for a sibling repo |
| `@dup-ok: <reason>` | line comment on one of the 3 lines above the list | the overlap is not one fact; the reason must be a reason ("later", "TODO", "-" are not) |
| `why not <library>: <reason>` | first 10 lines of a hand-written module | the library was considered and rejected; not checked |

Check behavior: `@copy-of` must resolve; a file copy must be byte-identical to its source, a value copy must hold the same strings as `NAME` there. Editing a source lists its copies. `#NAME` is the name as written at the definition (a Luau table key, a module field, a `const`). A copy that is meant to hold fewer strings is not a copy: use `@dup-ok`.

Syntax per language:

| Language | Value copy | File copy |
|---|---|---|
| Luau | `-- @copy-of: src/core/Shapes.luau#KINDS` | `--` line in the header |
| Python | `# @copy-of: ...` | inside the module docstring or a `#` header line |
| Rust | `// @copy-of: ...` (a `///` line is read but is published by rustdoc) | `//` or `//!` header |
| TS, JS | `// @copy-of: ...` | `//` header |
| Astro | frontmatter: `//`; template: `{/* @copy-of: ... */}`, never `<!-- -->` (it can reach the HTML) | frontmatter `//` |
| JSON | cannot hold markers; name the source in the code that reads it or in the comparison test | same |

- Use a line comment, not a doc block: a moonwave `--[=[ ]=]` block or a JSDoc `/** */` can read `@copy-of` as a doc tag.
- A marker that names its own file marks the source (an identical file whose header names its canonical path: the source carries the same bytes, so its marker names itself). Copies must stay byte-identical, so edit the source and copy it over.
- Vendored trees (`vendor.lock.json`, `vendor/`, `third_party/`) are not marked or edited. Change the source and vendor again.
- Generated files carry the generator path and "do not edit" in the header instead of a marker.

## Library or hand-written

Before writing a parser, matcher or algorithm that a well-known library provides:

1. Search the repo for one already there.
2. Name the library and measure the cost here: stripped binary size delta, cold build time, dependency count (a throwaway probe is enough), or startup time for a hook.
3. List the behavior differences that matter: strictness (a strict parser rejecting input users write), parity with a reference implementation, error messages, determinism of output that is cached or hashed, whether the runtime can install it at all (a hook that only has the standard library).
4. Pick. If you hand-write it, put the `why not <library>:` line at the top with the deciding reason from step 2 or 3.

The cost claim is measured, not guessed. Adding the dependency is the user's decision: propose it with the numbers. A lexer, state machine or AST visitor may stay long; its length is the shape of the work. Heavy parsers belong in a separate process when the core has a size budget.

## Simplify while you are there

- A match or if-chain with an arm that returns its own input (`"a" -> "a"`, `or` chains of `IsA` names) is a set membership test: use a set lookup.
- A long function that chains independent steps becomes step functions run in order, in the code you are adding.

## Repo settings

`.claude/conventions.json`, key `reuse` (all optional):

```json
{"reuse": {"mode": "on", "allow": [{"path": "src/legacy/**", "reason": "frozen"}],
           "vocab_ok": [["Edit", "Write", "MultiEdit"]], "min_shared": 3}}
```

- `mode`: `shadow` (default; duplicate checks are logged, not shown), `on` or `off`. The environment variable `REUSE_CHECK` overrides it. `@copy-of` checks run unless `off`.
- `allow`: globs whose sets are never reported, each with a reason.
- `vocab_ok`: sets known to be an outside vocabulary; a match made only of these strings is not reported.
- `min_shared`: shared strings needed for a match (default 3).
- The hook never looks at `.claude/`, `*-ignoreme*`, vendored trees, generated files, tests, stories, galleries, examples and `refs/`.
