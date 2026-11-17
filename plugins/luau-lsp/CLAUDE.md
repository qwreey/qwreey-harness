# luau-lsp (plugin development)

Registers the luau-lsp language server for `.luau` through `.lsp.json`. `launcher/luau-lsp` (POSIX sh) finds the binary and builds the arguments; on Windows Claude Code resolves the same command to `launcher/luau-lsp.cmd`, which gets both from `launcher/find-luau-lsp.ps1`. Search order, arguments and the Windows path: `docs/how-it-works.md`. `README.md` is for people deciding to install, in Korean.

## Tests
- `python3 -I tests/test-launcher.py`: fake binaries and stores in a temporary HOME. Set `LUAU_LSP_TEST_PWSH=<pwsh 7 path>` to run the `.ps1` against the same cases; without PowerShell only its static checks run.
- `python3 -I tests/test-lsp-smoke.py`: starts the real server through the launcher, initialize and shutdown; skips when no binary is found.
- `claude plugin validate plugins/luau-lsp` from the repo root.

## Rules for this plugin
- A change to the search order or arguments goes into both `launcher/luau-lsp` and `launcher/find-luau-lsp.ps1`, with matching `[find:*]` tags and a test case; the test compares the two.
- Nothing in either launcher may write to stdout before the server starts: stdout is the LSP channel. Probes (`--version`, `mise which`) read `/dev/null` (`<NUL` in the `.cmd`) so they cannot consume client messages.
- `launcher/luau-lsp` stays extensionless and executable: Windows finds `luau-lsp.cmd` beside it through PATHEXT. `.gitattributes` keeps the `.cmd` CRLF and the sh LF.
- `find-luau-lsp.ps1` must run on Windows PowerShell 5.1: ASCII only, no `??`, ternary or `$IsWindows`, no `$ErrorActionPreference = 'Stop'` around native calls (5.1 turns their stderr into terminating errors).
- No top-level `bin/`: claude.ai and Cowork refuse plugins that have one.
- `definitions/globalTypes.d.luau` is a byte copy of `packs/luau-kb/typedefs/globalTypes.d.luau` without a marker (a header line would change the md5 the pack's records cite). Update the pack's file, then copy it here; `tools/tests/test-vendored-copies.py` fails on drift.
- The marketplace is a directory source, so a live session runs the launcher from this folder. Keep it runnable after every edit, and do not move or rename `launcher/` files while the plugin is enabled.
- Bump `version` in `.claude-plugin/plugin.json` when the payload changes.
