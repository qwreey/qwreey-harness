# luau-kb (pack development)

Default-off knowledge pack: 12 skills of general Luau and Roblox facts, two path-scoped rules, reproduction snippets and benches. Layout, verification commands and contribution rules: `docs/how-it-works.md`. Pack conventions for all packs: `packs/README.md`. `AGENTS.md` is the entry for other agents reading this knowledge, not a development guide.

## Tests
- `python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau` (every snippet across the version matrix).
- `timeout 120 python3 -I tools/tests/test-rules-inject.py </dev/null` (needs the coderag binary) and `python3 -I tools/tests/test-pack-policy.py`.
- Call luau tools by their versioned install path, not the mise shim, which fails with "No version is set" outside a pinned directory.

## Rules for this pack
- A new fact starts as a minimal snippet with markers and a control line; a section marked `status: verified` must name its snippet or bench. Unreproduced claims stay `described`.
- Do not pick a side on policies the repos disagree on; mark `> 정책: 미정` and list it in `decisions/README.md`.
- SKILL.md stays at 100 lines or fewer and routes to `references/`; new references carry the frontmatter the others have and must pass `coderag lint`.
- Keep project-specific design (one library's type names or APIs) out.
- No `hooks/` folder: coderag injects `rules/`, and a pack hook would inject them twice. Rule files stay at 40 lines or fewer (`rules/README.md`).
- The pack folder ships whole into the plugin cache: development material nothing here cites (such as skill-trigger evals) lives in the repo's `.claude/scopes/packs/luau-kb/`.
- No `.lsp.json`: the LSP is the separate `plugins/luau-lsp` plugin, and two plugins registering `luau` would start two servers.
- `typedefs/globalTypes.d.luau` is the canon; `plugins/luau-lsp/definitions/` holds a byte copy. After changing it, copy it there (`tools/tests/test-vendored-copies.py` checks).
- Bump `version` in `.claude-plugin/plugin.json` when the payload changes, so hosted installs update.
