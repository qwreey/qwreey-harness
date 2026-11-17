# qwreey-delegate (plugin development)

One skill, `qwreey-delegate:delegate`, and its driver `skills/delegate/scripts/delegate.py` (stdlib Python 3.11+, run as `python3 -I`), which runs Gemini `agy` or OpenAI `codex` as an unprivileged uid in an isolated work folder. No hooks, no ambient. The procedure the model follows is `skills/delegate/SKILL.md`; isolation, run flow, settings and work folders: `docs/how-it-works.md`. Design and open milestones: `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/driver-design.md` (repo root).

## Where things are
- `skills/delegate/scripts/delegate.py`: CLI, `run`, `doctor`, `register` (subcommands also `collect`, `remove`, `list`, `gc`).
- `delegate_workspace.py` (registry, locations, records, locks, fd-relative reads), `delegate_isolation.py` (uid backend, task environment, processes), `delegate_agents.py` (agy print-mode and codex adapters, agy `--settings` policy), `delegate_results.py` (collect, remove, automatic cleanup, list, gc).
- `skills/delegate/scripts/delegate.sh`: a wrapper that execs `delegate.py`. Keep the path: older sessions' SKILL text and `qwreey-proc-guard`'s exemption name it.
- `skills/delegate/templates/`: `tasks.md` (prompt skeleton), `preamble-worktree.md`, `preamble-empty.md` (prepended by the driver), `AGENTS.md.template` (per-repo map).
- `skills/delegate/registry.tsv`: the shipped uid table, read only when no registry is set. `register` writes only the file the `harness_delegate_registry` option (or `HARNESS_DELEGATE_REGISTRY`) names and seeds a new one with this file's header, so header edits here reach new users.
- `.claude-plugin/plugin.json` `userConfig`: the user-facing keys (registry, models, executables). An option key is the env name in lowercase; its default must equal `ENV_DEFAULTS` or the loader's `DEFAULTS` (`tools/tests/test-plugin-userconfig.py`).

## Tests
From the repo root (fake agy/codex; nothing calls a vendor):
```bash
timeout 590 choom -n 1000 -- python3 -I tools/tests/test-delegate-cli.py </dev/null
timeout 590 choom -n 1000 -- python3 -I tools/tests/test-delegate-config.py </dev/null
python3 -I tools/tests/test-harness-env-owners.py </dev/null    # after changing harness.env keys
python3 -I plugins/qwreey-proc-guard/tests/test-heavy-proc-guard.py </dev/null    # after renaming the driver
bash -n plugins/qwreey-delegate/skills/delegate/scripts/delegate.sh
python3 -I plugins/qwreey-delegate/skills/delegate/scripts/delegate.py doctor --all </dev/null
```
Run the CLI tests as root too: the uid isolation cases skip without it. A real `run` spends the user's vendor quota; do one only when the user agrees.

## Rules for this plugin
- Isolation is the point: changes must keep the delegate unable to write the main worktree or `.git/objects`, read credentials outside its own HOME, or push. `doctor` checks this; extend it with any new isolation step.
- Every driver module is imported at start, so editing the plugin does not break a running job; keep new imports at the top of `delegate.py`.
- agy never gets `--dangerously-skip-permissions`: it turns off the headless refusals the `--settings` policy relies on.
- `skills/delegate/scripts/harness_env.py` is a byte copy of `home/.claude/lib/harness_env.py` (the harness.env layer loader); the driver always uses this copy, never `~/.claude/lib`, which can be older. Edit the canon, then run `python3 -I tools/sync-copies.py --apply`. A new `HARNESS_DELEGATE_*` key goes into `ENV_DEFAULTS` in `delegate.py` (and `ENV_USER_ONLY` when a repository must not set it), plus the design table in `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/driver-design.md`.
- Delegate output is a claim, never a decision; keep the SKILL.md verification rules intact when editing.
- Requires Linux and root (`setpriv`, `choom`); do not add paths that silently weaken isolation on other platforms.
