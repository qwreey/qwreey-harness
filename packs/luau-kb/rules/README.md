# rules - path-scoped shared rules

This directory holds the `paths:`-scoped rule files shared by several Luau repos. This directory is canonical. The coderag plugin injects these files (`coderag hook post-tool`, for projects that list `luau-kb` under `[[packs]]` in `coderag.toml`) when a matching file is read or written; the pack ships no hooks; plugins cannot ship `.claude/rules`. Do not also symlink them into `~/.claude/rules/`, or the rule loads twice.

| File | paths | Lines | Rationale and examples |
|---|---|---|---|
| `luau-core.md` | `**/*.luau` | 40 | `skills/luau-style/references/` (link at the end of each line) |
| `code-structure.md` | `**/*.{luau,lua}` | 11 | **Pointer only.** The structure rules (D-13, decided) are toolkit-independent, so their canonical copy moved to user level `~/.claude/rules/code-structure.md` (qwreey-harness `home/.claude/rules/code-structure.md`, a MANIFEST-managed file). This file is not linked by MANIFEST. It only tells agents that do not read the plugin where the canonical rules are and where the Luau details live (`skills/luau-style/references/structure.md`, `splitting.md`, entry `init.luau`) |

## Writing rules
- Every rule file has frontmatter with `paths` (required; without it the file loads in every session at full cost) and a one-line `description` in Korean.
- The body is English (fewer tokens per injection, see below). One rule per line, imperative, with the rationale reference link at the end. Facts and rationale stay in references; do not restate them here.
- Links are relative: `../skills/luau-style/references/X.md`. They point to the same file inside this repo and in a user home where `~/.claude/rules/` and `~/.claude/skills/luau-style` are linked side by side.
- Keep each file at 40 lines or fewer.
- Do not turn a contested policy into a rule before the user decides. Only the undisputed common part goes in (below).

## Where each line of `luau-core.md` comes from (2026-11-10)
Only lines that do not conflict with the user's decisions (qwreey-harness `.claude/base/decisions/README.md`, "사용자 결정 현황") are included.
- **Decided**: using `const` and staying consistent within a file (D-01), running stylua from the root and diffing `<<` files (D-02), gate exit code and stderr (D-06).
- **Common ground the seven repos already share**: the five naming rules (undisputed part of D-09), English identifiers and error messages plus "follow the file's comment language" (undisputed part of D-08), literal error messages, `@self`, literal paths, entry names, and real `require` tests (undisputed part of D-12).
- **Lines that come from language facts** (reproduced in snippets): `local const`, statements starting with `(`, `and/or` ternaries, bare `function`, `error(e, 0)` rethrow, `pcall(f(x))`.
- **Left out of the rules** (the user confirmed D-05 and D-07 to D-12 on 2026-11-11, but the details are per-repo or were not turned into one-line rules, so they live only in the skill, where some references still carry the older `> 정책: 제안(D-xx)` mark until updated): comment language for new files (D-08), namespace-function casing and new-repo defaults (D-09), mandatory library raise helper and line-assert tests (D-10; the rules only say "use the helper if there is one"), field reads (D-11), `@game/` (D-12), code `TODO`s (D-07), version pinning (D-05).

## English body: tokens and compliance (2026-11-10, Claude Code 2.1.316, `claude -p --model sonnet`)
- Tokens: a temporary project with only `.claude/rules/<file>` and `mod.luau`; prompt "Read mod.luau, then reply with just: ok". Rule cost = context size of the API call after the Read minus the no-rule control (23,689).

  | File | Korean body | English body | Change |
  |---|---|---|---|
  | `luau-core.md` | +1,826 | +1,409 | −417 (−23%) |
  | `code-structure.md` | +413 | +345 | −68 (−16%) |

- Compliance: the rules-only condition of the `snippets/RESULTS.md` style measurement (same task and 12-item scorer), English `luau-core.md`, 2 runs: **12/12, 12/12** (Korean body before: 12/12, 12/12). The rule loaded in both runs, and both reports separated the verification scope ("Studio not measured"). One run used a hand-counted `error(msg, 2)` 6 times; the repo had no raise helper, so this is not a rule violation (the Korean runs had 0).

## Do symlinked rules load? (measured 2026-11-10, Claude Code 2.1.316, `claude -p --model sonnet`)

Four temporary projects, each told to Read `mod.luau`; we checked whether the rule body was attached in the `stream-json` output and what the model answered. Each project is its own `git init` directory and is also the working directory.

| Project `.claude/rules/luau-core.md` | Rule loaded |
|---|---|
| Real file (copy) | **Loaded** (system reminder right after the Read; the model quoted the first line verbatim) |
| Symlink to a file **inside** the project (`../../shared/luau-core.md`) | **Loaded** (the reminder shows the link target path `shared/luau-core.md`) |
| Symlink to a file **outside** the project (`<qwreey-harness 클론>/packs/luau-kb/rules/luau-core.md`) | **Not loaded** (model answered "NONE") |
| No rule (control) | Not loaded |

This matches the official docs (code.claude.com/docs/en/memory, checked 2026-11-10).
- "Claude Code treats a symlink whose target is outside your working directory like an external import. The linked rules don't load until you approve external imports for the project, and after that only the ones without a `paths` field load."
  - The approval dialog appears only when an interactive session starts, so `-p` has no way to approve.
  - Per the docs, **even after approval, external symlinked rules that have `paths` do not load.** So linking `luau-core.md` into a project's `.claude/rules/` as an external symlink cannot work.
- User level is different: "To load shared rules without that approval, keep them in `~/.claude/rules/`". Files in `~/.claude/rules/` are treated as user-authored and trusted without a dialog.
  - The exception is desktop Cowork sessions, which skip symlinked rule files and directories that point outside the working directory.
- Conclusion at the time: a user-level symlink. Superseded: the coderag plugin injects the rule now, so no symlink is needed.
  - Loading through a user-level symlink is backed by the docs only and was not measured, to avoid changing the real home setup.
  - After home-sync creates the link, confirm with one `claude -p` that Reads a `.luau` file.
  - To apply the rules to one repo only, use a copy or a file inside that project instead of a link.
