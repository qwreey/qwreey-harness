---
name: delegate
description: Hand one narrow question to another model family (Gemini `agy`, OpenAI `codex`) in an isolated unprivileged worktree and verify the answer yourself before using it. Use for a root cause that several findings may share, a view from outside the current frame, merging findings that share a mechanism, an objectivity check on names, or a bug hunt scoped to one mechanism. Do not use for review rounds, full audits, decisions, or anything that should land in the main repository as is. Also when the user asks in plain words, with or without naming the skill: "codex랑 agy써서 작명 논의해봐", "제미니한테도 물어봐", "코덱스한테 물어봐", "다른 모델 시선으로 봐줘". 다른 모델 계열에게 좁은 질문 맡기기, 제미니·코덱스 위임, 외부 시선.
argument-hint: "<agy|codex> <name> <prompt file> [--mode worktree|empty] [--ref commit]"
---

# delegate - a narrow question to another model family

The script is `${CLAUDE_SKILL_DIR}/scripts/delegate.sh`; below `D` means that path. The uid table is `registry.tsv` (location: see Setup), prompt skeletons are `templates/tasks.md`.

**Requirements:** Linux as root (`setpriv`, an unprivileged uid per repository, `choom`), the `agy` and/or `codex` CLI logged in with the user's own subscription. On Windows, macOS or without those CLIs the script stops with an error; use a Claude subagent instead. Without OS isolation (no root uid isolation, no working OS sandbox) only `empty` mode, a read-only opinion, is acceptable; the script needs root for every mode today.

## Why and when

sonnet and opus are distilled from the same base, so they share vocabulary and selection bias, and asking for an "outsider view" does not narrow a model-level tendency. Another family looks from a different angle.

- **Gemini (agy)** jumps out of the frame to a root cause. It also reasons wrongly, invents statements and slips in operations far more often, speaks assertively, and its fixes ignore performance.
- **codex (gpt-6-luna)** is cheap and fast for an objective judgment (names) when the whole context is in the prompt.

Use it for: a root cause, an outside view, merging findings, an objectivity check on names (three families), a bug hunt scoped to one mechanism.

Do not use it for review rounds, full audits or exhaustive comparison tables (the Claude auditor or the gate does those; an external audit the user asked for by name is the exception). Do not hand it decisions, results to apply to the main repository as is, or a judgment that needs decision history without the context. Its output is a finding, never a decision, because the main session is the most accurate verifier.

Before launching, show the user in one line what you will ask.

## Cost and concurrency

- At most one task per backend at a time, summed over all repositories (`DELEGATE_MAX_CONCURRENT=1`), because the token limit is per user. Widen it only when the user says there is room. Put priorities in one task instead of splitting it into overlapping ones.
- agy uses only `gemini-3.8-flash-high`; treat pro as absent.
- codex runs on a ChatGPT Plus quota, which is small; the user checks usage. Model `gpt-6-luna`, `--effort medium`.
- `--timeout` defaults to 3600 s. Run with Bash `run_in_background` and wait for the notification.

## Setup

- The repository must be in the registry; the script refuses otherwise. `$D register <path>` assigns the next free uid; tell the user when you do it.
- `HARNESS_DELEGATE_REGISTRY` (in `~/.claude/harness.env`) points at the registry in the claude-doctor clone. The script reads it itself; the copy next to this file is only a fallback and goes stale in a plugin cache.
- Each repository needs `AGENTS.md` at its root (skeleton: `templates/AGENTS.md.template`). Both models load it; it holds the canonical paths, the check commands and repository-only cautions, so the script's preamble stays project-neutral. `$D doctor --all` checks the uids, secrets and `AGENTS.md`.

## Run

1. **Write the task** into scratch from a skeleton in `templates/tasks.md`. The script prepends the preamble (no writes outside the worktree, no mutating git commands, `ulimit` plus exit-code verdicts, measured versus estimated, base commit checked by the model itself, suggestions are not decisions). In the task:
   - give the canonical files to read as paths;
   - say which frame to jump out of;
   - require falsifiable evidence (file:line, command output);
   - to break the frame, do not pass an earlier review's classification table: the model locks onto it. Pass the ledger and code only.
2. **Launch.** The worktree is cut from the **committed** `--ref` (default HEAD), so commit what the task should see first.
   ```bash
   $D run agy   <name> <prompt> [--ref <commit>]   # repository from the cwd (or --repo)
   $D run codex <name> <prompt> --mode empty       # whole context in the prompt; number code with `nl -ba`
   ```
   - agy defaults to `worktree`, codex to `empty`.
   - codex `worktree` is refused: its bubblewrap sandbox cannot make a namespace under an unprivileged uid, so no shell runs. Turning the sandbox off (`DELEGATE_CODEX_SANDBOX=danger-full-access`) leaves the uid as the only isolation and is the user's decision.
   - agy `empty` is unverified and warns; the answer is copied from stdout into the report. Check the first result together with the user.
3. **Read.** The script prints the paths: the report (agy worktree: `<workspace>/<name>/REPORT.md`; otherwise `.delegate/report.md`), `.delegate/guard.txt` (exit code, whether the main repository changed, worktree HEAD, files the task edited) and, if needed, `.delegate/stdout.txt`. If the main repository shows CHANGED, check whether the main session or the user did it in the meantime.
4. **Verify and apply** (next section).
5. **Keep and remove.**
   ```bash
   $D collect agy <name>   # <workspace>/runs/<date>-<name>/: prompt, report, guard, stdout, meta, diff.patch, agy probes
   $D remove  agy <name>   # deletes worktree and task HOME; refuses before collect (--discard to throw away)
   ```
   Move a report worth citing into the project's `.claude/audit/<backend>/<date>-<name>.md` with the main session's verification on top and commit it. `runs/` is outside the repository, so never cite it as evidence.
6. **Clean up.** `$D list --all`, then `$D gc --all` (preview) and `$D gc --all --apply`. gc removes collected workspaces, HOMEs without an owner and the old shared `.home`, and skips a workspace with a live process; it only lists old-script workspaces, old codex records and uncollected results.

## Verify before applying

1. **The main session checks every claim.** What went wrong in practice: the base commit copied from the input document, a measured result quoted backwards, a citation pointing the wrong way, an unrun test marked "measured", a closed question counted as open, code quoted with changed indentation.
2. **Reproduce first.** For a claimed defect, write the reproduction test, then fix. If it does not reproduce, record it only as "external claim, not reproduced by main".
3. **Re-measure the fix.** The other model's fixes ignore performance: a correct fix can be a multiple slower. Measure on hot paths.
4. **A new field, name, mechanism or convention is a user question.** When only the symptom is certain, record "symptom confirmed, remedy open". Do not place an external suggestion beside a quoted user decision.
5. **Separate in reports** what the other model claimed, what main confirmed and what the user must decide.
6. **`diff.patch` is reference only**; never apply it as is.

## Isolation

`agy --sandbox` and codex `-s read-only` do not stop access outside the cwd, and `unshare -m` is not permitted here, so these hold the line:

1. A per-repository unprivileged uid via `setpriv`; only the worktree, its `.git/worktrees/<id>` and the task HOME belong to it. The main working tree and `.git/objects` are unwritable, so no commit and nothing to push; a pre-push hook refuses anyway. `doctor` checks this and that the uid cannot read `~/.claude/.credentials.json`, `.git-credentials` or `.ssh`.
2. An empty environment (`env -i`); PATH is the repository's mise-pinned tools plus `/usr/bin:/bin` (not `/usr/local/bin`, where the Studio tools are). If a backend cannot find something, `DELEGATE_KEEP_ENV=1`.
3. `choom -n 1000`: on OOM the task dies before claude, because agy's own Bash is invisible to the PreToolUse hooks.
4. HEAD and status of the main repository before and after, in `guard.txt`.

Quirks:
- Editing `delegate.sh` while a task runs is safe; the script re-runs from its own copy.
- codex warns that bubblewrap is missing and uses a built-in one; harmless in `empty` mode, which runs no shell.
- agy HOME gets only credentials and settings, not the user's other conversations. If agy cannot authenticate, `DELEGATE_AGY_FULL_HOME=1`. This trimming is unverified against a real run.
- agy writes probes to `brain/<conversation>/scratch/` under HOME, outside the guard's change list; `collect` copies them to `runs/<...>/agy/`.

## Workspaces

Sibling directories of a repository: `<repo>-agy` and `<repo>-codex` belong to this script (worktree `<name>/`, `.homes/<name>/`, `.hooks/`, `runs/`); never create or edit them by hand. `<repo>-scratch` holds throwaway experiments and `<repo>-proto/<slug>` holds worktrees of prototype branches (`proto/<slug>`). Keep worktrees only in those, plus `.claude/worktrees/` (the harness's). Never cite a sibling directory as evidence: move what matters into the repository and commit it, because a clone has no sibling directories.

`AGENTS.md` is the single entry point for external models: delete `GEMINI.md` (agy loads both, up to 24,000 bytes each). It is a map, not knowledge: canonical paths, known-findings ledgers, check commands, repository-only cautions, under 6KB. Restated decisions go stale.
