# Environment (all projects)
## ~/.claude and memory
- Files that claude-doctor's `tools/home-sync.sh` installs into `~/.claude` are edited at their source under claude-doctor `home/`, never in place; then tell the user, who reviews with `home-sync.sh diff` and runs `apply`.
- Auto memory stays on this machine and in this folder. Repo conventions, decisions, pitfalls and build steps go in the repo (CLAUDE.md, `.claude/rules`, docs) or coderag; memory holds user preferences and machine facts only.
## Subagents
- haiku: read-only lookup only. Anything that writes, runs, judges, reviews or measures: sonnet or above, sized to the task.
- Prefer several small passes (find -> review -> fix -> review) to parallel fan-out. Before 2+ subagents at once or a Workflow, tell the user in one line: count, models, why, expected size.
## Reviews: do them unasked
- Before commits and done-claims, after large structural changes, before releases and after toolchain upgrades; reproduce findings before reporting. Size it by the project's budget rules, not by the occasion.
- A review you started: verify each finding, act, and tell the user in 1-3 lines what you accepted and rejected. A review the user asked for: show it in full, in the user's language. Use the built-in advisor tool only when the user asks.
## Toolchain
- If a mise shim fails with "No version is set", call the binary under `<HARNESS_TOOL_INSTALLS>/<tool>/<ver>/` (`~/.claude/harness.env`) directly.
# Compact instructions
- Keep: user decisions with verbatim quotes, unanswered questions to the user, running background agents and their tasks, commit hashes and changed files, constraints in force (read-only repos, no direct ~/.claude edits).
- Drop: raw tool output, contents of committed files, finished agents' detailed reports (keep conclusions and numbers).
