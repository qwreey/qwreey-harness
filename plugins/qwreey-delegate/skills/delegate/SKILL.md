---
name: delegate
description: Hand one narrow question to another model family (Gemini `agy`, OpenAI `codex`) in an isolated unprivileged worktree and verify the answer yourself before using it. Use for a root cause that several findings may share, a view from outside the current frame, merging findings that share a mechanism, an objectivity check on names, or a bug hunt scoped to one mechanism. Do not use for review rounds, full audits, decisions, or anything that should land in the main repository as is. Also when the user asks in plain words, with or without naming the skill: "codex랑 agy써서 작명 논의해봐", "제미니한테도 물어봐", "코덱스한테 물어봐", "다른 모델 시선으로 봐줘". 다른 모델 계열에게 좁은 질문 맡기기, 제미니·코덱스 위임, 외부 시선.
argument-hint: "<agy|codex> <name> <prompt file> [--mode worktree|empty] [--ref commit]"
---

# delegate - a narrow question to another model family

The driver is `python3 -I ${CLAUDE_SKILL_DIR}/scripts/delegate.py`; below `D` means that command. Prompt skeletons are `templates/tasks.md`.

**Requirements:** Linux as root (`setpriv`, unprivileged uids from the range in the plugin option `harness_delegate_uids`, `choom`), Python 3.11 or newer, the `agy` and/or `codex` CLI logged in with the user's own subscription. Without root uid isolation the driver refuses every run (exit 4); on Windows, macOS or without those CLIs use a Claude subagent instead.

Exit codes: 0 the run finished (the model's own exit code is in `guard.txt`), 2 usage, 3 agent or its credentials missing, 4 refused by isolation policy, 5 concurrency limit (another task of the same agent is running, or no uid of the range is free; wait for it, do not retry in a loop).

## Why and when

sonnet and opus are distilled from the same base, so they share vocabulary and selection bias, and asking for an "outsider view" does not narrow a model-level tendency. Another family looks from a different angle.

- **Gemini (agy)** jumps out of the frame to a root cause. It also reasons wrongly, invents statements and slips in operations far more often, speaks assertively, and its fixes ignore performance.
- **codex (gpt-6-luna)** is cheap and fast for an objective judgment (names) when the whole context is in the prompt.

Use it for: a root cause, an outside view, merging findings, an objectivity check on names (three families), a bug hunt scoped to one mechanism.

Do not use it for review rounds, full audits or exhaustive comparison tables (the Claude auditor or the gate does those; an external audit the user asked for by name is the exception). Do not hand it decisions, results to apply to the main repository as is, or a judgment that needs decision history without the context. Its output is a finding, never a decision, because the main session is the most accurate verifier.

Before launching, show the user in one line what you will ask.

## Cost and concurrency

- At most one task per agent at a time, summed over all repositories (`HARNESS_DELEGATE_MAX_CONCURRENT=1`), because the token limit is per user. Widen it only when the user says there is room. Put priorities in one task instead of splitting it into overlapping ones.
- agy and codex can run side by side: each run takes its own free uid from the range.
- agy uses only `gemini-3.8-flash-high`; treat pro as absent.
- codex runs on a ChatGPT Plus quota, which is small; the user checks usage. Model `gpt-6-luna`, `--effort medium`.
- `--timeout` defaults to 3600 s. Run with Bash `run_in_background` and wait for the notification.

## Setup

- Any git repository works; there is no registration and no per-repository setting. The task may read the original repository and copies ignored dependencies it needs (installed packages) from there; the preamble tells it so. An optional `HARNESS_DELEGATE_SETUP=<command>` in the repository's `.claude/harness.env` runs once as the task uid in a new worktree, for the rare repository that needs more.
- Each repository needs `AGENTS.md` at its root (skeleton: `templates/AGENTS.md.template`). Both models load it; it holds the canonical paths, the check commands and repository-only cautions, so the driver's preamble stays project-neutral. `$D doctor --all` checks the uid range, secrets, the work folder path and `AGENTS.md`.

## Run

1. **Write the task** into scratch from a skeleton in `templates/tasks.md`. The driver prepends the preamble (no writes outside the task folder, no mutating git commands, `ulimit` plus exit-code verdicts, measured versus estimated, base commit checked by the model itself, suggestions are not decisions). In the task:
   - give the canonical files to read as paths inside the repository; agy's file tools cannot open paths outside its folder, so paste anything from elsewhere into the task;
   - say which frame to jump out of;
   - require falsifiable evidence (file:line, command output);
   - to break the frame, do not pass an earlier review's classification table: the model locks onto it. Pass the ledger and code only.
2. **Launch.** The worktree is cut from the **committed** `--ref` (default HEAD), so commit what the task should see first.
   ```bash
   $D run agy   <name> <prompt> [--ref <commit>]   # repository from the cwd (or --repo)
   $D run codex <name> <prompt> --mode empty       # whole context in the prompt; number code with `nl -ba`
   ```
   - agy defaults to `worktree`: a detached worktree it may edit and run checks in (shell allowed).
   - agy `empty` is a restricted copy: an empty folder, everything it needs in the prompt, shell refused, file tools refused outside the folder and in the temp folders. Those refusals are agy's own permission rules, not an OS boundary; the uid is the boundary.
   - codex defaults to `empty`. codex `worktree` is refused (exit 4): its bubblewrap sandbox cannot make a namespace under an unprivileged uid, so no shell runs. Turning the sandbox off (`HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access`, user layer) leaves the uid as the only isolation and is the user's decision.
3. **Read.** When the run ends the driver collects everything into `<state>/runs/<key>/<date>-<name>/` (`<key>` is the repository folder name plus a path hash), checks the copy byte for byte, removes the work folder, and prints `collected: <folder>` and `report: <folder>/report.md`. The folder also holds `guard.txt` (exit code, whether the main repository changed, worktree HEAD, files the task edited, tools agy was denied), `stdout.txt`, `stderr.txt` (agy), `meta.txt`, `state.json`, `diff.patch` (worktree mode) and `agy/<conversation>/` (agy's scratch probes and transcript). `<state>` is `~/.local/state/qwreey-delegate` unless `HARNESS_DELEGATE_STATE` moves it.
   - `report: MISSING` after `agy denied: ...`: agy was refused a tool it is not allowed in headless mode and ended the turn with an empty answer. Rewrite the task so it stays inside its folder (or put the material in the prompt) and run again under a new name.
   - `kept: <work folder> - automatic collect failed`: nothing was deleted; read the record the line names, then `$D collect` and `$D remove` by hand. `--keep` on `run` skips the automatic collect the same way.
   - If the main repository shows CHANGED, check whether the main session or the user did it in the meantime.
4. **Verify and apply** (next section).
5. **Keep.** Move a report worth citing into the project's `.claude/audit/<backend>/<date>-<name>.md` with the main session's verification on top and commit it. `runs/` is outside the repository and `gc` deletes it after `HARNESS_DELEGATE_RUNS_DAYS` (14) days, so never cite it as evidence.
6. **Clean up.** `$D list --all`, then `$D gc --all` (preview) and `$D gc --all --apply`. gc collects and removes work folders left without a live run, deletes HOMEs without an owner and results older than the retention (`--days N` overrides it), and skips a work folder with a live process. Old workspaces beside a repository (`<dirname(repo)>/<folder name>-<agent>/`) and state folders of no known repository are only listed; removing them is the user's call (`$D remove`, or by hand).

## Verify before applying

0. A bug-hunt or review answer ends with a JSON block (`templates/tasks.md` B, E: verdict, findings[file, line_start, line_end, confidence, recommendation, evidence]). Read that block, then reproduce each finding from its file:line and evidence; a finding missing either, or a missing block, is unverified.
1. **The main session checks every claim.** What went wrong in practice: the base commit copied from the input document, a measured result quoted backwards, a citation pointing the wrong way, an unrun test marked "measured", a closed question counted as open, code quoted with changed indentation.
2. **Reproduce first.** For a claimed defect, write the reproduction test, then fix. If it does not reproduce, record it only as "external claim, not reproduced by main".
3. **Re-measure the fix.** The other model's fixes ignore performance: a correct fix can be a multiple slower. Measure on hot paths.
4. **A new field, name, mechanism or convention is a user question.** When only the symptom is certain, record "symptom confirmed, remedy open". Do not place an external suggestion beside a quoted user decision.
5. **Separate in reports** what the other model claimed, what main confirmed and what the user must decide.
6. **`diff.patch` is reference only**; never apply it as is.

## Isolation

On this host `agy --sandbox` and codex `-s read-only` do not stop access outside the cwd and `unshare -m` is not permitted, so these hold the line:

1. An unprivileged uid via `setpriv` (no new privileges, no capabilities), taken per run from the range; only the task folder, its `.git/worktrees/<id>` and the task HOME belong to it. The main working tree and `.git/objects` are unwritable, so no commit and nothing to push; a pre-push hook refuses anyway. One task per uid at a time. `doctor` checks this and that the uid cannot read `~/.claude/.credentials.json`, `.git-credentials` or `.ssh`.
2. agy runs in print mode without `--dangerously-skip-permissions`. Its `--settings` deny file tools in the temp folders, allow them in the task folder, and allow the shell only in a uid worktree; anything else is refused headless and listed in `guard.txt` as `agy denied`. A task folder under a denied temp folder is refused (exit 4; `doctor` shows FAIL), which is why work folders live in the state folder.
3. An empty environment; PATH is the repository's mise-pinned tools plus `/usr/bin:/bin` (not `/usr/local/bin`, where the Studio tools are), `TMPDIR` is inside the task HOME. If an agent cannot find something, `HARNESS_DELEGATE_KEEP_ENV=1` (user layer) passes the current environment, tokens included.
4. `choom -n 1000`: on OOM the task dies before claude, because agy's own Bash is invisible to the PreToolUse hooks.
5. HEAD and status of the main repository before and after, in `guard.txt`.

Quirks:
- Editing the driver while a task runs is safe; it imports every module at start.
- codex warns that bubblewrap is missing and uses a built-in one; harmless in `empty` mode, which runs no shell.
- The task HOME gets a fresh copy of the credentials only (agy: `~/.gemini` without the user's history), so tasks never see the user's other conversations.

## Work folders and sibling directories

The driver owns `<state>/work/<key>-<agent>/` (task folder `<name>/`, `.homes/<name>/`, `.hooks/`, `.runs/<name>/` records) and `<state>/runs/`; never create or edit them by hand. Beside a repository, `<repo>-scratch` holds throwaway experiments and `<repo>-proto/<slug>` holds worktrees of prototype branches (`proto/<slug>`); keep worktrees only there and in `.claude/worktrees/` (the harness's). Never cite the state folder or a sibling directory as evidence: move what matters into the repository and commit it, because a clone has neither.

`AGENTS.md` is the single entry point for external models: delete `GEMINI.md` (agy loads both, up to 24,000 bytes each). It is a map, not knowledge: canonical paths, known-findings ledgers, check commands, repository-only cautions, under 6KB. Restated decisions go stale.
