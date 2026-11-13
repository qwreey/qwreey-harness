# qwreey-delegate (plugin development)

One skill, `qwreey-delegate:delegate`, and its script `skills/delegate/scripts/delegate.sh`, which runs Gemini `agy` or OpenAI `codex` as an unprivileged uid in an isolated worktree. No hooks, no ambient. The procedure the model follows is `skills/delegate/SKILL.md`; isolation, run flow, settings and work folders: `docs/how-it-works.md`.

## Where things are
- `skills/delegate/scripts/delegate.sh`: subcommands `run`, `collect`, `remove`, `list`, `gc`, `register`, `doctor`.
- `skills/delegate/templates/`: `tasks.md` (prompt skeleton), `preamble-worktree.md`, `preamble-empty.md` (prepended by the script), `AGENTS.md.template` (per-repo map).
- `skills/delegate/registry.tsv`: uid table, edited in place by `register`. Installs read the clone's copy through `HARNESS_DELEGATE_REGISTRY`, so keep that file here as the live one.

## Tests
There is no automated test. After a change, run `bash -n skills/delegate/scripts/delegate.sh` and `delegate.sh doctor --all`. A real `run` spends the user's vendor quota; do one only when the user agrees.

## Rules for this plugin
- Isolation is the point: changes must keep the delegate unable to write the main worktree or `.git/objects`, read credentials outside its own HOME, or push. `doctor` checks this; extend it with any new isolation step.
- The script re-executes from a temporary copy, so editing it does not break a running job.
- Delegate output is a claim, never a decision; keep the SKILL.md verification rules intact when editing.
- Requires Linux and root (`setpriv`, `choom`); do not add paths that silently weaken isolation on other platforms.
