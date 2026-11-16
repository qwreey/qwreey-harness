---
description: Luau 공통 규칙(저장소 무관) — 파일·문법, 이름·주석, 에러, require, 포맷·검증·보고. 근거는 각 줄의 luau-style references 링크
paths:
  - "**/*.luau"
---
# Luau core rules (all repos)

If the repo's `.claude/rules/` or CLAUDE.md says otherwise, follow the repo. Rationale and examples are in each line's link (luau-style skill references).

## Files and syntax
- Put `--!strict` on line 1 of every file. Do not rely on `.luaurc` alone. → [modules§1](../skills/luau-style/references/modules.md)
- `const` is allowed. In an existing file, follow that file's `const`/`local` habit and never mix the two in one file. → [idioms§1](../skills/luau-style/references/idioms.md)
- Never write `local const x = …`. It becomes a global assignment `x = …`. → [idioms§1](../skills/luau-style/references/idioms.md)
- Never start a statement with `(`. Bind it to a local and call that. → [idioms§1](../skills/luau-style/references/idioms.md)
- Write ternaries as the `if c then a else b` expression, not `c and a or b` (`x or y` for a default is fine). → [idioms§2](../skills/luau-style/references/idioms.md)
- `f<<T>>(…)` is an explicit type argument. Do not "fix" it into shift operators. → [idioms§3](../skills/luau-style/references/idioms.md)
- Declare module functions with `local function` or `const function`. A bare `function name()` silently becomes a global. → [idioms§6](../skills/luau-style/references/idioms.md)

## Names and comments
- PascalCase for types and `require`d modules, camelCase for locals and local functions, `isX` for predicates, `_` prefix for internals. → [naming§1](../skills/luau-style/references/naming.md)
- For other casing (namespace functions, file names), follow the neighboring modules in the same folder. → [naming§2](../skills/luau-style/references/naming.md)
- If a user-chosen name breaks these rules, do not rename it. Propose the rename with reasons; bulk edits only after approval. → [naming§3](../skills/luau-style/references/naming.md)
- Write identifiers and error messages in English. Write comments in the language the file already uses. → [quality§1](../skills/luau-style/references/quality.md)
- Comments say the "why" the code cannot say. → [quality§1](../skills/luau-style/references/quality.md)
- Public functions in code others call (a library, a module other modules require) get a `---` doc comment; luau-lsp shows only `---` and `--[=[ ]=]` on hover and completion, never `--`. → [quality§1](../skills/luau-style/references/quality.md)

## Errors
- Write the error message as a literal on the line that throws. Do not scatter it through format helpers. → [errors§1](../skills/luau-style/references/errors.md)
- Rethrow a caught error with `error(e, 0)`. → [errors§1](../skills/luau-style/references/errors.md)
- If the repo has a raise helper, use it instead of a hand-counted `error(msg, n)`. `-O2` inlining shifts the level. → [errors§2](../skills/luau-style/references/errors.md)
- Never write `pcall(f(x))`. Use `pcall(f, x)` or wrap it in a closure. → [errors§3](../skills/luau-style/references/errors.md)

## require
- Inside `init.luau`, require files in its own folder as `@self/x`. `./x` is a sibling of the folder. → [modules§3](../skills/luau-style/references/modules.md)
- Pass `require` a string literal, and never name a test entry `init.luau`. → [modules§3](../skills/luau-style/references/modules.md)
- Every new module gets a test that actually `require`s it. → [modules§3](../skills/luau-style/references/modules.md)

## Format, verification, reporting
- Run stylua from the repo root, and check the diff after formatting any file that contains `<<`. → [quality§3](../skills/luau-style/references/quality.md)
- Judge by the repo gate's exit code, and never discard stderr. → [quality§5](../skills/luau-style/references/quality.md)
- When reporting, separate "types/format only", "specs pass", and "measured in Studio". → [quality§5](../skills/luau-style/references/quality.md)

## Symptom → skill / reference index (fallback when skill auto-trigger fails)
If one of these matches, load the `luau-kb` skill or open the file before answering from memory.
- Zero diagnostics when an error is expected, result leaks to `unknown`, generic call without arguments → luau-types [generics§2–3](../skills/luau-types/references/generics.md), then [negative-controls](../skills/luau-verify/references/negative-controls.md)
- Correct code rejected ("Argument count mismatch" on `ipairs`, "No valid instantiation") → luau-types [solver-limits§4](../skills/luau-types/references/solver-limits.md), [variance§7](../skills/luau-types/references/variance.md)
- "Code is too complex to typecheck", recursive alias → luau-types [recursion-and-limits§5–6](../skills/luau-types/references/recursion-and-limits.md)
- Varargs, multiple returns, `pcall` typing → luau-types [packs-and-varargs](../skills/luau-types/references/packs-and-varargs.md)
- Is this check result trustworthy, how to call luau-analyze / luau-lsp, shim "No version is set" → luau-verify [toolchain](../skills/luau-verify/references/toolchain.md), [checkers](../skills/luau-verify/references/checkers.md)
- Test passes under `-O1` but fails under `-O2`, error-level assertions → luau-testing [optimize-levels§2](../skills/luau-testing/references/optimize-levels.md)
- Mock vs Studio, Studio MCP, Roblox API types, definition files → luau-roblox [env-dependence](../skills/luau-roblox/references/env-dependence.md), [api-types](../skills/luau-roblox/references/api-types.md)
- Slow code, metatable or table growth cost, benchmark method, `--!native` → luau-perf [metatables](../skills/luau-perf/references/metatables.md), [tables](../skills/luau-perf/references/tables.md), [benchmarking-method](../skills/luau-perf/references/benchmarking-method.md)
- Weak table entry never disappears, coroutine error vanishes, `require` does not resolve in the CLI → luau-runtime [gc-and-weak-tables](../skills/luau-runtime/references/gc-and-weak-tables.md), [coroutines](../skills/luau-runtime/references/coroutines.md), [require-by-string](../skills/luau-runtime/references/require-by-string.md)
- Signal late or after `Destroy`, Tween, `task` ordering, Actors → roblox-engine [signals-and-events](../skills/roblox-engine/references/signals-and-events.md), [tasks-and-threads](../skills/roblox-engine/references/tasks-and-threads.md)
- Remote validation, DataStore, receipts → roblox-net [remotes-and-replication](../skills/roblox-net/references/remotes-and-replication.md); GUI input, layout, physics → roblox-world [gui-and-input](../skills/roblox-world/references/gui-and-input.md)
- Bump luau / luau-lsp / stylua, new syntax or RFC, is a limitation being fixed → luau-upstream [version-bump](../skills/luau-upstream/references/version-bump.md), [watchlist](../skills/luau-upstream/references/watchlist.md)
- Roblox API signature or documentation citation → roblox-docs (`tools/roblox_docs.py`)
