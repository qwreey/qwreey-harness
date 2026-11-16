---
name: code-reuse
description: Conventions for values and duplicates in source code. Decides whether a hardcoded value is policy (config, data table or pack, with a DEFAULT_* fallback) or an invariant (const), keeps one implementation per job, marks unavoidable copies with @copy-of and a comparison test, and records why a module is hand-written instead of using a library. Use it whenever a qwreey-conventions reuse notice names lines you added, before adding a list of names, a size limit or a helper that may already exist, and before choosing between a library and your own parser. 하드코딩, 중복 구현, 바퀴의 재발명, 사본 표시.
argument-hint: "[file or note]"
---

# qwreey-conventions:code-reuse

Two copies of the same knowledge drift apart, and the bug shows up far from both. A value baked into code that another project would set differently forces a code change where a config line would do. This skill says what to do about either.

## When a hook notice arrives

The notice names the line you added, the existing definition it overlaps and the shared strings. Decide in this order:

1. Same knowledge, importable (same package or a declared dependency): delete your list and reference the definition. If neither place is the right home, move it to one module both import.
2. Same knowledge, not importable (separately installed plugin, another repo, a reference implementation): keep the copy, mark it `@copy-of: <path>#<NAME>` on the line above, and add or extend a test that compares the two.
3. Per-project value (the policy test in the rule says yes): move it to the repo's config or data table, keep a `DEFAULT_*` fallback in code. An ecosystem list goes to that ecosystem's pack.
4. Only alike on the surface (an outside API's names used for a different purpose, a subset chosen for a different reason): put `@dup-ok: <reason>` on the line above. The reason says why they are different knowledge.

Do not touch duplicates you did not add, and do not start a repo-wide cleanup unprompted. Old ones in the files you edited are counted and shown to the user at turn end; the hook shows it, you do not repeat it.

## Markers

| Marker | Where | Meaning | Checked |
|---|---|---|---|
| `@copy-of: <path>#<NAME>` | line above the copied definition, in a comment | this value is a copy of `<NAME>` in `<path>` (repo-relative, or `<repo>:<path>` for a sibling repo) | the path and name must resolve; when both are string sets they must be equal; editing the source lists its copies |
| `@dup-ok: <reason>` | line above the list, in a comment | the overlap is not the same knowledge | the reason must be a reason ("later", "-", "TODO" are not) |
| `why not <library>: <reason>` | first 10 lines of a hand-written parser or algorithm module | the library was considered and rejected for this reason | not checked by the hook |

Whole-file copies keep the header line `Canonical copy: <path>` that the repo's vendored-copy test reads.

## Policy or invariant

| Value | Kind | Where |
|---|---|---|
| folders to skip, file extensions to index, size limits | policy | config key with `DEFAULT_*` in code |
| stage ladders, tool name lists, Roblox or Wally folder names | policy, ecosystem | the ecosystem's pack |
| schema or protocol version, known frontmatter keys, grammar tables | invariant (format) | `const` |
| tool input keys, OS paths an outside tool fixes | invariant (outside fact) | `const`, with the source in one line if it is not obvious |
| security allowlists | invariant (safety) | `const`; widening it is a code review, not a config edit |
| cache caps, prune ages | internal | `const` |

A `DEFAULT_*` name promises an override. Do not use the prefix for a value nothing overrides.

## Library or hand-written

Before writing a parser, matcher or algorithm that a well-known library provides:

1. Search the repo for one already there.
2. Name the library and measure what it costs here: stripped binary size delta, cold build time, dependency count (a throwaway probe binary is enough), or startup time for a hook.
3. List the behavior differences that matter: strictness (a strict parser rejecting input users write), parity with a reference implementation, error messages, determinism of output that is cached or hashed.
4. Pick. Write the `why not <library>:` line if you hand-write it, with the deciding reason from step 2 or 3.

Heavy parsers belong in a separate process or provider when the core has a size budget, so the core does not pay for them.

## Repo settings

`.claude/conventions.json`, key `reuse` (all optional):

```json
{"reuse": {"mode": "on", "allow": [{"path": "src/legacy/**", "reason": "frozen, replaced in v3"}],
           "vocab_ok": [["Edit", "Write", "MultiEdit"]], "min_shared": 3}}
```

- `mode`: `on`, `shadow` (log only, no notices) or `off`. The environment variable `REUSE_CHECK` overrides it.
- `allow`: globs whose sets are never reported, each with a reason.
- `vocab_ok`: sets known to be an outside vocabulary; a match made only of these strings is not reported.
- `min_shared`: shared strings needed for a match (default 3).
