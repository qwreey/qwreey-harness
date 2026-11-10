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
