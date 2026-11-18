---
name: code-reuse
description: Steps for a definition that must live in two places. Marks a copy that cannot be imported with @copy-of or @start-replace region markers, syncs regions with sync-copies, compares a copy with its source in a test, and measures a library against a hand-written parser or algorithm. Use it when copying a definition into another package, language or repo, when adding region markers or acting on a reuse-check notice, and before hand-writing a parser or algorithm a well-known library provides. 사본 표시, 영역 복사, 라이브러리 대신 직접 구현.
argument-hint: "[file or note]"
---

# qwreey-conventions:code-reuse

The rule `code-reuse` says what must hold; this skill has the steps for copies across a boundary and for the library choice.

## Deciding on a duplicate

A reuse notice names the line you added, the definition it overlaps and the shared strings. Decide in this order:

1. Same fact, and this package can import the other place (same package, or a declared dependency such as a Cargo path dependency, a wally or pesde package, an npm workspace package): delete your list and reference the definition. If neither place is the right home, move it to one module both import. Do not import across a boundary the package does not already have.
2. Same fact, not importable (separately installed plugin, another repo, another language, a reference implementation): keep the copy, mark it (see Markers) and compare the two in a test (see Comparing a copy in a test). When one side can be derived from the other (a script that reads the Luau source, a build step), generate it instead.
3. A value that varies per project (policy in the rule's Values lines): config, with a `DEFAULT_*` fallback in code. If the list names one ecosystem (Roblox, Wally, pesde), it can instead live in that ecosystem's pack; propose that to the user, because a pack is usually another repo.
4. Alike only on the surface (an outside API's names used for another purpose, a subset chosen for another reason): put `@dup-ok: <reason>` in a line comment above the list. The reason says why they are different facts.

Fix only what you added. Old duplicates in files you edited are counted and shown to the user at turn end; do not repeat that or start a cleanup.

## Markers

| Marker | Where | Meaning |
|---|---|---|
| `@copy-of: <path>[#NAME]` | a line comment on the line above the copied definition (value copy), or in a line comment or the module docstring within the first 10 lines of the file (file copy) | this is a copy of `<NAME>` (or of the whole file) at `<path>`, repo-relative, or `<repo>:<path>` for a sibling repo |
| `@start-replace: <path>#<NAME> [key=value ...]` ... `@end-replace` | each on a line of its own holding only the comment prefix and the marker, around the copied lines | the lines between are a copy of region `NAME` in `<path>`; the region whose path names its own file is the canon |
| `@dup-ok: <reason>` | line comment on one of the 3 lines above the list | the overlap is not one fact; the reason must be a reason ("later", "TODO", "-" are not) |
| `why not <library>: <reason>` | first 10 lines of a hand-written module | the library was considered and rejected; not checked |

The two copy markers write a sibling repo differently. A mix such as `../statuslib:src/statuses.py` resolves under neither; the hook names it with the right form.

| Marker | Same repo | Sibling repo |
|---|---|---|
| `@copy-of` | `# @copy-of: src/statuses.py#STATUSES` | `# @copy-of: statuslib:src/statuses.py#STATUSES` (repo name, colon, path in that repo; found beside this repo, else among repos opened in Claude Code on this machine; not compared when not found) |
| `@start-replace` | `# @start-replace: lib/harness_texts.py#OMIT_LINE` | `// @start-replace: ../qwreey-harness/lib/harness_texts.py#OMIT_LINE` (a plain path from this repo's root; no colon form) |

The hook checks that `@copy-of` and `@start-replace` resolve; a file copy must be byte-identical to its source, a value copy must hold the same strings as `NAME` there, a region copy must equal what the canon region renders to. Editing a source (or the lines inside a canon region) lists its copies. `#NAME` is the name as written at the definition (a Luau table key, a module field, a `const`). A copy that is meant to hold fewer strings is not a copy: use `@dup-ok`.

Syntax per language:

| Language | Value copy | File copy |
|---|---|---|
| Luau | `-- @copy-of: src/core/Shapes.luau#KINDS` | `--` line in the header |
| Python | `# @copy-of: ...` | inside the module docstring or a `#` header line |
| Rust | `// @copy-of: ...` (a `///` line is read but is published by rustdoc) | `//` or `//!` header |
| TS, JS | `// @copy-of: ...` | `//` header |
| Astro | frontmatter: `//`; template: `{/* @copy-of: ... */}`, never `<!-- -->` (it can reach the HTML) | frontmatter `//` |
| JSON | cannot hold markers; name the source in the code that reads it or in the comparison test | same |

- Use a line comment, not a doc comment: a moonwave `--[=[ ]=]` block, a Luau `---` line, a JSDoc `/** */` or a Rust `///` line publishes the marker or reads it as a doc tag, and a region marker is read only alone on a line comment.
- A marker that names its own file marks the source (an identical file whose header names its canonical path). Copies must stay byte-identical, so edit the source and copy it over (see Syncing).
- Vendored trees (`vendor.lock.json`, `vendor/`, `third_party/`) are not marked or edited. Change the source and vendor again.
- Generated files carry the generator path and "do not edit" in the header instead of a marker.

### Regions

A region copies a few lines or one constant across files, languages and repos, where a value copy (a set of strings) cannot. Paths are relative to the repo root of the file holding the marker; a sibling repo is `../<repo>/<path>`.

- Without options the canon lines are copied verbatim, re-indented to the copy's marker.
- `value=string template="<text>"`: the canon region holds exactly one string literal; the copy is `<text>` with `{value}` replaced by that string as a double-quoted literal (escapes valid in Python, Rust, JS/TS and Luau).

```text
canon, lib/harness_texts.py:
# @start-replace: lib/harness_texts.py#OMIT_LINE
OMIT_LINE = "Omit the {block} block from the summary; it is re-injected after compaction."
# @end-replace

copy in another repo, Rust:
// @start-replace: ../qwreey-harness/lib/harness_texts.py#OMIT_LINE value=string template="pub const OMIT_LINE: &str = {value};"
pub const OMIT_LINE: &str = "Omit the {block} block from the summary; it is re-injected after compaction.";
// @end-replace
```

### Syncing

- A repo with `tools/sync-copies.py` (qwreey-harness): shared canon lives in `lib/`. Edit the canon, then run `python3 -I tools/sync-copies.py --apply`; `--check` (in its tests) fails on drift, and with no flag it prints the diff. Never edit text between region markers in a copy by hand.
- A repo without the tool: compare each copy with its source in a test, or generate one from the other.

### Comparing a copy in a test

The hook compares marked copies only while a session edits them; a test keeps them equal in CI and for edits made elsewhere.

1. Put the test in the repo that holds the copy, next to its other tests, and read both files by path (a sibling repo through the same workspace path the marker uses; skip with a message when it is absent).
2. Extract the copied value the way the language defines it (parse the literal, or import the module where the test runner can), not by matching text lines.
3. Assert equality of the whole value; on failure print both paths and the command that brings them back in line (`sync-copies.py --apply`, or "edit the source and copy it over").

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

Repo settings for the hook (`reuse` in `.claude/conventions.json`) and the policy-or-invariant table are for people, in the plugin's `docs/code-reuse.md`.
