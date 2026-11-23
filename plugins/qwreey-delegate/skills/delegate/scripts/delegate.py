"""delegate.py - hand one task to another model family (agy=Gemini, codex=OpenAI) in isolation.

  delegate.py run <agy|codex> <name> <prompt file> [--repo <key|path>] [--mode worktree|empty]
                  [--ref <commit>] [--model M] [--effort low|medium|high] [--timeout seconds]
  delegate.py collect <agy|codex> <name> [--repo ...]     # keep the result under <workspace>/runs/
  delegate.py remove  <agy|codex> <name> [--repo ...] [--discard] [--delete-branch]
  delegate.py list    [--repo ...|--all]                  # both backends
  delegate.py gc      [--repo ...|--all] [--days N] [--apply]   # preview only unless --apply
  delegate.py doctor  [--repo ...|--all]

--repo takes a path, or the key or folder name of a repository that ran here before; it defaults to the current one.
Each run takes the first free uid of HARNESS_DELEGATE_UIDS.
Lifecycle: run -> (main reads and verifies) -> collect -> remove. gc finds what is left.
Exit: 0 done (the model's own exit code is in guard.txt), 2 usage, 3 agent or credentials missing,
4 refused by isolation policy, 5 concurrency limit.
"""
import os
import sys

if sys.version_info < (3, 11):
    sys.exit("delegate: needs Python 3.11 or newer")

# `python3 -I` leaves the script folder off sys.path. Every module is imported here, at start, so a plugin update
# while a task runs for an hour cannot break the running driver halfway.
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)

import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import delegate_agents as agents  # noqa: E402
import delegate_isolation as iso  # noqa: E402
import delegate_results as results  # noqa: E402
import delegate_workspace as ws  # noqa: E402
import harness_env  # noqa: E402

PROG = ws.PROG
SKILL_DIR = Path(HERE).parent
TEMPLATES = SKILL_DIR / "templates"
DEFAULT_EFFORT = "medium"
DEFAULT_TIMEOUT_SECONDS = 3600
START_LOCK_SECONDS = 120     # wait for another start of the same agent (seconds of git and copying) before giving up
LEGACY_LOCK_SECONDS = 30
SETUP_TIMEOUT_SECONDS = 900  # the repository's setup line (HARNESS_DELEGATE_SETUP), run once in a new worktree
# delegate.sh serializes its start (existence check, live count, pid file) on this lock; taking it too keeps a
# run of either script from slipping past the other's count.
LEGACY_LOCK = "/tmp/delegate-{agent}.lock"
MODES = ("worktree", "empty")
PRE_PUSH = '#!/bin/sh\necho "push refused: delegate workspace" >&2\nexit 1\n'

# harness.env keys only this driver reads, with their defaults. It also reads the shared HARNESS_DELEGATE_UIDS,
# HARNESS_TOOL_INSTALLS and HARNESS_HEAVY_WRAP, whose defaults and user-only status are in harness_env.py.
ENV_DEFAULTS = {
    # Agent executables. Empty: agy/codex on PATH (mise shims are skipped: they fail in the empty task environment),
    # else under HARNESS_TOOL_INSTALLS.
    "HARNESS_DELEGATE_AGY_BIN": "",
    "HARNESS_DELEGATE_CODEX_BIN": "",
    # Credential sources: agy copies this folder per task, codex copies auth.json from it. Empty codex: $CODEX_HOME, else ~/.codex.
    "HARNESS_DELEGATE_AGY_HOME": "~/.gemini",
    "HARNESS_DELEGATE_CODEX_HOME": "",
    # What opens an agy worktree: uid (only with root's uid isolation) | sandbox (agy's shell sandbox alone; file tools are not confined).
    "HARNESS_DELEGATE_AGY_WORKTREE": "uid",
    # agy without uid isolation: empty is off; allow opens empty mode only (file tools read HOME secrets and write outside as the user).
    "HARNESS_DELEGATE_AGY_UNISOLATED": "",
    # codex sandbox. Empty: the driver default (read-only). danger-full-access is accepted only with uid isolation.
    "HARNESS_DELEGATE_CODEX_SANDBOX": "",
    # Non-empty: tasks get the current environment instead of an empty one (tokens in variables can leak).
    "HARNESS_DELEGATE_KEEP_ENV": "",
    # State folder (work/, runs/, concurrency slots and locks). Empty: the platform state folder (Linux ~/.local/state/qwreey-delegate).
    "HARNESS_DELEGATE_STATE": "",
    # gc deletes results in <state>/runs/ older than this many days. Results are read right after the run, and a report
    # worth keeping is moved into the repository (.claude/audit/), so two weeks covers a missed read or a weekend.
    "HARNESS_DELEGATE_RUNS_DAYS": "14",
    # Delegations running at once per agent, summed over every repository: the token limit is per user subscription.
    "HARNESS_DELEGATE_MAX_CONCURRENT": "1",
    # Default models (run --model wins). Unrelated to isolation, so a repository layer may set them.
    "HARNESS_DELEGATE_AGY_MODEL": "gemini-4-hydrogen-high",
    "HARNESS_DELEGATE_CODEX_MODEL": "gpt-6-luna",
    # Extra names (space-separated globs) kept out of empty-mode files. It only adds to the built-in list, so a repository may set it.
    "HARNESS_DELEGATE_SECRET_GLOBS": "",
    # Command run once in a new worktree before the agent (e.g. `timeout 300 mise exec -- pesde install`), as the task
    # uid with the task's environment plus mise. A repository sets it: in worktree mode the agent itself gets a shell
    # as that uid there, so the line can do nothing the task could not. setup_line reads it unexpanded.
    "HARNESS_DELEGATE_SETUP": "",
}
# A repository's committed harness.env must not change what runs, where credentials come from, the isolation gates,
# or limits that span every repository. Only the user layer and the environment set these.
ENV_USER_ONLY = frozenset({
    "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX",
    "HARNESS_DELEGATE_KEEP_ENV", "HARNESS_DELEGATE_STATE", "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_RUNS_DAYS",
})
SETUP_KEY = "HARNESS_DELEGATE_SETUP"
_SETUP_LINE = re.compile(rf"^\s*(?:export\s+)?{SETUP_KEY}\s*=(.*)$")
SHARED_KEYS = ("HARNESS_DELEGATE_UIDS", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP")
KEYS = SHARED_KEYS + tuple(ENV_DEFAULTS)
die = ws.die
note = ws.note


# ---------- config ----------
def config(project):
    """harness.env layers for this driver: user layer and environment (project ''), or with that repository's layers on
    top. Always the copy next to this file: an installed ~/.claude/lib/harness_env.py can be older and not know ENV_USER_ONLY."""
    return harness_env.load_layers(project, defaults=ENV_DEFAULTS, user_only=ENV_USER_ONLY)


def setup_line(project):
    """HARNESS_DELEGATE_SETUP of project as written in its layers, without $NAME expansion.

    The loader expands $NAME from the driver's environment, which would put root's variables (tokens) into a command
    a repository wrote and the task runs. bash expands the line later, in the task's own environment."""
    if SETUP_KEY in os.environ:
        return os.environ[SETUP_KEY].strip()
    user, repo_files = harness_env.layer_files(project)
    value = ""
    for f in ([user] if user else []) + repo_files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            m = _SETUP_LINE.match(line)
            if m:
                value = harness_env._value(m.group(1))
    return value.strip()


class Ctx:
    def __init__(self):
        self.cfg = self.layers("")
        # USER_ONLY, so the user layer decides for every repository.
        self.state_dir = Path(self.cfg["HARNESS_DELEGATE_STATE"] or ws.default_state_dir())

    def layers(self, project):
        return config(project)

    def uid_range(self):
        # Read without repository layers: a repository must not pick the uids its task runs as.
        return ws.parse_uid_range(self.cfg["HARNESS_DELEGATE_UIDS"])

    def repo(self, arg):
        return ws.resolve_repo(self.state_dir, arg or "")

    def repos(self, sel):
        """Repositories for --all (those that ran here, plus the current one), else the one named.

        The current repository is added because a first doctor runs before any delegation."""
        if sel != "--all":
            return [self.repo(sel)]
        known = ws.known_repos(self.state_dir)
        here = ws.git_common_root(os.getcwd())
        if here and all(r.root != here for r in known):
            known.append(ws.Repo(here))
        return known


def parse(args, spec, npos, usage, max_pos=None):
    """(positionals, {option: value or True}). spec maps an option to whether it takes a value."""
    pos, opts, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            if a not in spec:
                die(f"unknown option {a}")
            if spec[a]:
                if i + 1 >= len(args):
                    die(f"{a} needs a value")
                opts[a] = args[i + 1]
                i += 2
                continue
            opts[a] = True
        else:
            pos.append(a)
        i += 1
    if not npos <= len(pos) <= (npos if max_pos is None else max_pos):
        die(f"usage: {usage}")
    return pos, opts


def positive_int(value, what):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        die(f"{what} must be a positive integer: {value}")
    return n


def selection(opts):
    return "--all" if opts.get("--all") else opts.get("--repo", "")


# ---------- run ----------
def snapshot_report(base, name, rec, adapter, mode, outcome):
    """Copy the task's answer into the record (root-owned) and return its path, or None when there is none.
    Order: the report file the preamble names, the adapter's other file, the answer the agent printed."""
    data = ws.read_under(base, name, *adapter.report_rel(mode))
    if not data and adapter.fallback(mode):
        data = ws.read_under(base, name, *adapter.fallback(mode))
    if not data and outcome.get("response"):
        data = outcome["response"].encode("utf-8")
    if not data:
        return None
    ws.write_safe(rec / "report.md", data)
    return rec / "report.md"


def cmd_run(ctx, args):
    usage = "run <agy|codex> <name> <prompt file> [options]"
    (agent, name, prompt_file), opts = parse(
        args, {"--repo": 1, "--mode": 1, "--ref": 1, "--model": 1, "--effort": 1, "--timeout": 1, "--keep": 0}, 3, usage)
    ws.check_agent(agent)
    ws.check_name(name)
    prompt_path = Path(prompt_file)
    if not prompt_path.is_file():
        die(f"prompt file not found: {prompt_file}")
    prompt_path = prompt_path.resolve()
    timeout = positive_int(opts.get("--timeout", DEFAULT_TIMEOUT_SECONDS), "--timeout")
    repo = ctx.repo(opts.get("--repo"))
    cfg = ctx.layers(repo.root)
    adapter = agents.ADAPTERS[agent]
    mode = opts.get("--mode") or adapter.default_mode
    if mode not in MODES:
        die(f"--mode must be {'|'.join(MODES)}")
    model = opts.get("--model") or cfg[adapter.model_key]
    if not model:
        die(f"no model: pass --model or set {adapter.model_key}")
    effort = opts.get("--effort") or DEFAULT_EFFORT
    ref = opts.get("--ref") or "HEAD"
    limit = positive_int(cfg["HARNESS_DELEGATE_MAX_CONCURRENT"], "HARNESS_DELEGATE_MAX_CONCURRENT")
    bin_path = agents.find_bin(cfg[adapter.bin_key], agent, cfg["HARNESS_TOOL_INSTALLS"], adapter.install_rel)
    if not bin_path:
        where = cfg[adapter.bin_key] or f"PATH or {Path(cfg['HARNESS_TOOL_INSTALLS']) / adapter.install_rel}"
        die(f"{agent} not found: {where} ({adapter.bin_key} sets it)", ws.EXIT_NO_AGENT)
    creds = adapter.credentials(cfg)
    if not creds.exists():
        die(f"{agent} credentials not found: {creds} ({adapter.home_key} sets the folder)", ws.EXIT_NO_AGENT)
    first_uid, last_uid = ctx.uid_range()
    backend = iso.select_backend()
    adapter.check_mode(mode, cfg, backend)
    preamble = (TEMPLATES / f"preamble-{mode}.md").read_text(encoding="utf-8")
    task = prompt_path.read_text(encoding="utf-8", errors="replace")

    state_dir = ctx.state_dir
    wt_planned = ws.work_base(state_dir, repo, agent) / name
    settings, policy_notes = adapter.policy(mode, backend, wt_planned)
    if policy_notes:
        die(f"{'; '.join(policy_notes)}. The work folder must not sit under a temp folder the agent is denied; "
            f"HARNESS_DELEGATE_STATE (user layer) moves it", ws.EXIT_REFUSED)
    state_dir.parent.mkdir(parents=True, exist_ok=True)
    base = ws.make_work_base(state_dir, repo, agent)
    ws.remember_repo(state_dir, repo)
    homes, hooks = ws.root_dir(base / ".homes", ws.PASS_MODE), ws.root_dir(base / ".hooks", ws.PASS_MODE)
    ws.root_dir(base / ws.RECORDS, ws.PRIVATE_MODE)
    wt, home, rec = base / name, homes / name, ws.record_dir(base, name)

    start = ws.take_lock(state_dir / f"start-{agent}.lock", START_LOCK_SECONDS)
    if start is None:
        die(f"another {agent} run has been starting for {START_LOCK_SECONDS}s; retry later", ws.EXIT_BUSY)
    legacy = legacy_lock(agent)
    admin = None
    try:
        if os.path.lexists(wt) or os.path.lexists(rec):
            die(f"{wt} already exists - use another name, or collect/remove it")
        # Per run, not per repository: the work folder and HOME below are always new, so nothing carries over
        uid, uid_lock = ws.take_uid(state_dir, first_uid, last_uid)
        backend = backend.for_uid(uid)
        why = backend.unavailable()
        if why:
            die(why, ws.EXIT_REFUSED)
        known = {r.key: r for r in ws.known_repos(state_dir) + [repo]}
        slot, live = ws.acquire_slot(state_dir, agent, limit, ws.live_legacy_runs(list(known.values()), [agent]))
        if slot is None:
            die(f"{live} {agent} task(s) already running (limit {limit}, HARNESS_DELEGATE_MAX_CONCURRENT adjusts it - "
                f"the token limit is the user's)", ws.EXIT_BUSY)
        # A live process of the uid while its machine-wide lock was free belongs to no run: a driver that died
        # without ending its task (SIGKILL, crash) left it, so it goes before the new task gets the uid
        leftover = backend.end_task()
        if leftover:
            note(f"killed {leftover} leftover process(es) of uid {uid} (a run that died left them)")
        ws.write_safe(hooks / "pre-push", PRE_PUSH, 0o755)
        commit = (ws.git_out("-C", repo.root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") or "").strip()
        if not commit:
            die(f"commit not found: {ref}")
        os.mkdir(rec, 0o700)
        run_lock = ws.take_lock(rec / "run.lock")
        state = {"driver": PROG, "agent": agent, "mode": mode, "isolation": backend.name, "repo": repo.key,
                 "root": repo.root, "uid": uid, "model": model, "effort": effort, "ref": ref, "commit": commit,
                 "pid": os.getpid(), "started": ws.now_iso(), "started_ts": time.time(), "admin": None,
                 "finished": None, "rc": None, "collected": None, "token_refreshed": None}
        ws.save_state(rec, state)
        if mode == "worktree":
            p = subprocess.run(["git", "-C", repo.root, "worktree", "add", "-q", "--detach", str(wt), commit],
                               capture_output=True, text=True)
            if p.returncode != 0:
                die(f"git worktree add failed: {p.stderr.strip()}")
            # git may number the admin dir (same basename in another workspace), so ask for the real path, and ask
            # now: after the chown git refuses the worktree as dubious ownership.
            admin = (ws.git_out("-C", str(wt), "rev-parse", "--path-format=absolute", "--git-dir") or "").strip() or None
            state["admin"] = admin
            ws.save_state(rec, state)
        else:
            os.mkdir(wt, 0o700)
        os.mkdir(wt / ws.TASK_OUT, 0o700)
    finally:
        os.close(start)
        if legacy is not None:
            os.close(legacy)

    # HOME per task with a fresh credential copy: a shared HOME let two concurrent runs delete each other's copy.
    if os.path.lexists(home):
        shutil.rmtree(home)
    os.mkdir(home, 0o700)
    os.mkdir(home / iso.TASK_TMP, 0o700)
    adapter.prepare_home(cfg, home)

    report_rel = adapter.report_rel(mode)
    for k, v in (("{{WT}}", wt), ("{{ROOT}}", repo.root), ("{{KEY}}", repo.key), ("{{REPORT}}", wt.joinpath(*report_rel))):
        preamble = preamble.replace(k, str(v))
    prompt = preamble + task
    ws.write_safe(rec / "prompt.md", prompt)
    ws.write_safe(rec / "meta.txt", "".join(f"{k}: {v}\n" for k, v in (
        ("backend", agent), ("mode", mode), ("repo", f"{repo.key} ({repo.root})"), ("uid", uid), ("model", model),
        ("effort", effort), ("ref", f"{ref} -> {commit}"), ("prompt-source", prompt_path), ("started", state["started"]),
        ("isolation", backend.name), ("driver", PROG))
        + ((("agy-settings", json.dumps(settings, separators=(",", ":"))),) if settings else ())))

    backend.give(*(p for p in (wt, home, admin) if p))
    env = iso.task_env(home, iso.tool_path(repo.root), hooks, bool(cfg["HARNESS_DELEGATE_KEEP_ENV"]),
                       adapter.extra_env(home))
    setup = setup_line(repo.root)
    with iso.StopSignals() as stop:
        if mode == "worktree" and setup:
            # The repository's line runs with the task's rights and environment, never root's.
            rc, _, err = backend.run(["bash", "-c", setup], iso.setup_env(env, cfg["HARNESS_TOOL_INSTALLS"]),
                                     cwd=wt, timeout=SETUP_TIMEOUT_SECONDS)
            if rc != 0:
                note(f"warning: setup failed ({'timeout' if rc is None else 'exit ' + str(rc)}): {setup}"
                     f"{': ' + err.strip().splitlines()[-1] if err.strip() else ''}")
        before = ws.main_snapshot(repo.root)
        note(f"start {agent}/{name} ({model}, {mode}) {ws.now_iso()} - {wt}")
        argv = iso.heavy_prefix(harness_env, cfg) + backend.wrap(
            adapter.argv(bin_path, model, effort, timeout, prompt, wt, adapter.last_path(wt, mode), cfg, settings))
        rc = iso.run_task(argv, wt, env, rec / "stdout.txt", timeout + agents.PRINT_TIMEOUT_MARGIN, stop,
                          adapter.stdin(rec), rec / "stderr.txt" if adapter.separate_stderr else None)
        killed = backend.end_task()
        outcome = adapter.outcome(rec)
        report = snapshot_report(base, name, rec, adapter, mode, outcome)
        denied = outcome.get("denied") or []

        after = ws.main_snapshot(repo.root)
        guard = [f"exit: {rc}", f"finished: {ws.now_iso()}"]
        if before == after:
            guard.append("main repo: unchanged")
        else:
            guard.append(f"main repo: CHANGED during the run (HEAD {before[0]} -> {after[0]}; status hash differs) - "
                         f"check whether the main session or the user did it")
        if killed:
            guard.append(f"task processes left after the run: {killed} killed")
        if denied:
            guard.append(f"{agent} denied: {', '.join(denied)}")
        if outcome and outcome.get("status") not in (None, "SUCCESS"):
            guard.append(f"{agent} status: {outcome.get('status')}")
        if mode == "worktree":
            hrc, head, herr = iso.git_as_task(backend, env, wt, "rev-parse", "HEAD")
            src, status, serr = iso.git_as_task(backend, env, wt, "status", "--porcelain=v1")
            backend.end_task()
            guard.append(f"worktree HEAD: {head.strip()} (base {commit})" if hrc == 0
                         else f"worktree HEAD: unknown (git: {herr.strip() or hrc})")
            guard.append("worktree changes:" if src == 0 else f"worktree changes: unknown (git: {serr.strip() or src})")
            guard += [ln for ln in status.splitlines() if not ln.startswith(f"?? {ws.TASK_OUT}/") and ln != "?? REPORT.md"]
        guard_text = "\n".join(guard) + "\n"
        ws.write_safe(rec / "guard.txt", guard_text)
        ws.write_safe(rec / "exit", f"{rc}\n")
        state.update(finished=ws.now_iso(), rc=rc, denied=denied)
        ws.save_state(rec, state)
        if denied:
            meta = (ws.read_under(rec, "meta.txt") or b"").decode("utf-8", "replace")
            ws.write_safe(rec / "meta.txt", meta + f"{agent}-denied: {', '.join(denied)}\n")
        note(f"done {agent}/{name} - exit {rc}")
        sys.stdout.write(guard_text)
        out, problems = (None, None) if opts.get("--keep") else results.auto_cleanup(
            state_dir, results.Place(repo, agent, name, base, False))
        os.close(run_lock)
        os.close(slot)
        os.close(uid_lock)
        if out and not problems:
            print(f"collected: {out} (workspace removed)")
            print_report(out / "report.md" if report else None, agent, denied, out)
            print("next: main reads the report there and verifies it")
            return 0
        if problems:
            print(f"kept: {wt} - automatic collect failed, so nothing was deleted: {'; '.join(problems)}")
        print_report(report, agent, denied, rec)
        print(f"next: main reads and verifies -> {PROG} collect {agent} {name} --repo {repo.key} -> "
              f"{PROG} remove {agent} {name} --repo {repo.key}")
    return 0


def print_report(report, agent, denied, folder):
    if report:
        print(f"report: {report} ({os.lstat(report).st_size} bytes)")
    elif denied:
        print(f"report: MISSING - {agent} ended the turn with an empty answer after it was denied {', '.join(denied)} "
              f"(headless print mode refuses tools outside its allowed set); see {folder / 'stderr.txt'}")
    else:
        print(f"report: MISSING - see {folder / 'stdout.txt'}")


def legacy_lock(agent):
    """delegate.sh's start lock, or None when it stays busy or cannot be opened (the driver's own lock still holds)."""
    try:
        fd = ws.take_lock(LEGACY_LOCK.format(agent=agent), LEGACY_LOCK_SECONDS)
    except OSError as e:
        note(f"warning: delegate.sh start lock unusable ({e}); its runs may start alongside")
        return None
    if fd is None:
        note(f"warning: delegate.sh start lock busy for {LEGACY_LOCK_SECONDS}s; going on without it")
    return fd


# ---------- collect / remove / list / gc ----------
def located(ctx, agent, name, repo_arg):
    ws.check_agent(agent)
    ws.check_name(name)
    repo = ctx.repo(repo_arg)
    place = results.find(ctx.state_dir, repo, agent, name)
    if place is None:
        die(f"not found: {agent}/{name} in {ws.work_base(ctx.state_dir, repo, agent)} or {repo.legacy_base(agent)}")
    return place


def cmd_collect(ctx, args):
    (agent, name), opts = parse(args, {"--repo": 1}, 2, "collect <agy|codex> <name> [--repo R]")
    place = located(ctx, agent, name, opts.get("--repo"))
    if ws.is_running(place.base, name):
        die(f"still running: {agent}/{name}")
    st = ws.read_state(place.rec)
    if not st.get("finished") and not ws.exists_under(place.base, name, ws.TASK_OUT, "exit", kind="file"):
        note("warning: no exit record (abnormal end, or a workspace from an older script); collecting what exists")
    with results.task_uid_held(ctx.state_dir, place.task_uid()):
        out, problems = results.collect_into(ctx.state_dir, place)
    for p in problems:
        note(f"warning: {p}")
    print(f"collected: {out}")
    for p in sorted(out.rglob("*")):
        if p.is_file():
            print(f"  {p.lstat().st_size:>9}  {p.relative_to(out)}")
    return 0


def cmd_remove(ctx, args):
    (agent, name), opts = parse(args, {"--repo": 1, "--discard": 0, "--delete-branch": 0}, 2,
                                "remove <agy|codex> <name> [--repo R] [--discard] [--delete-branch]")
    place = located(ctx, agent, name, opts.get("--repo"))
    if ws.is_running(place.base, name):
        die(f"still running: {agent}/{name}")
    with results.task_uid_held(ctx.state_dir, place.task_uid()):
        results.remove_workspace(place, bool(opts.get("--discard")), bool(opts.get("--delete-branch")))
    print(f"removed: {place.wt}")
    return 0


def cmd_list(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0}, 0, "list [--repo R|--all]")
    repos = ctx.repos(selection(opts))
    for repo in repos:
        results.list_repo(ctx.state_dir, repo)
    if opts.get("--all"):
        results.list_unknown(ctx.state_dir, repos)
    return 0


def cmd_gc(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0, "--days": 1, "--apply": 0}, 0,
                    "gc [--repo R|--all] [--days N] [--apply]")
    what = "--days" if "--days" in opts else "HARNESS_DELEGATE_RUNS_DAYS"
    days = str(opts.get("--days") or ctx.cfg["HARNESS_DELEGATE_RUNS_DAYS"] or ENV_DEFAULTS["HARNESS_DELEGATE_RUNS_DAYS"])
    if not days.isdigit():
        die(f"{what} must be a number: {days}")
    days = int(days)
    if not opts.get("--apply"):
        print("(preview - pass --apply to delete)")
    repos = ctx.repos(selection(opts))
    for repo in repos:
        results.gc_repo(ctx.state_dir, repo, days, bool(opts.get("--apply")))
    if opts.get("--all"):
        results.gc_unknown(ctx.state_dir, repos, days, bool(opts.get("--apply")))
    return 0


# ---------- doctor / register ----------
MAX_LISTED_IDS = 10  # doctor names this many colliding uids, then counts the rest
MAX_LISTED_PATHS = 3


def doctor_uids(ctx):
    """Check the HARNESS_DELEGATE_UIDS range and return the uid doctor probes as, or None."""
    try:
        first, last = ctx.uid_range()
    except ws.DelegateError as e:
        print(f"  FAIL {e}")
        return None
    taken = [(u, ws.id_taken(u)) for u in range(first, last + 1)]
    taken = [(u, kind) for u, kind in taken if kind]
    usable = [u for u in range(first, last + 1) if u not in dict(taken)]
    print(f"  INFO task uids {first}-{last} (HARNESS_DELEGATE_UIDS): {len(usable)} usable, so at most {len(usable)} "
          f"tasks at once")

    # Collisions only shrink the range; a range with nothing left refuses every run
    if taken:
        shown = ", ".join(f"{u} ({kind})" for u, kind in taken[:MAX_LISTED_IDS])
        more = f" and {len(taken) - MAX_LISTED_IDS} more" if len(taken) > MAX_LISTED_IDS else ""
        print(f"  {'FAIL' if not usable else 'WARN'} real accounts in the range, skipped: {shown}{more}")
    else:
        print("  ok   no uid in the range is in /etc/passwd or /etc/group")
    kept = sorted(ws.kept_uids(ctx.state_dir) & set(usable))
    if kept:
        print(f"  INFO held by uncollected work folders until collect/remove or gc: {' '.join(map(str, kept))}")

    # Files the old table's runs left (doctor_one counts those in main trees) belong to these uids
    old = [u for u in usable if u in ws.OLD_TABLE_UIDS]
    if old:
        print(f"  WARN the range includes uid(s) {' '.join(map(str, old))} of the old per-repository table: files its "
              f"runs left owned by them (packages hard-linked into main trees and package caches, /tmp/codex-*-<uid>) "
              f"are writable to any delegation that gets one - chown them to root (find / -xdev -uid <uid>) or start "
              f"the range above {ws.OLD_TABLE_UIDS[-1]}")
    doctor_uid_locks(ctx)
    return usable[0] if usable else None


def doctor_uid_locks(ctx):
    """Say where the uid locks are: machine-wide in /run, or the state folder fallback."""
    try:
        folder = ws.machine_uid_lock_dir()
    except ws.DelegateError as e:
        print(f"  FAIL uid locks: {e}")
        return
    if folder is not None:
        print(f"  ok   uid locks in {folder} (machine-wide)")
    else:
        print(f"  WARN uid locks in {ctx.state_dir / 'uids'}: {ws.UID_LOCK_DIR} is unusable (needs root and a "
              f"root-owned /run), so a run with another HARNESS_DELEGATE_STATE cannot see them and may take and kill "
              f"a running task's uid")


def doctor_global(ctx):
    """Print the checks shared by every repository; the backend bound to the probed uid, or None."""
    print(f"== delegate  state={ctx.state_dir}")
    print(f"  INFO python {sys.executable} {sys.version.split()[0]}")
    print(f"  INFO harness_env {harness_env.__file__}")
    uid = doctor_uids(ctx)
    for agent, adapter in agents.ADAPTERS.items():
        cfg = ctx.cfg
        found = agents.find_bin(cfg[adapter.bin_key], agent, cfg["HARNESS_TOOL_INSTALLS"], adapter.install_rel)
        print(f"  ok   {agent} {found}" if found else f"  WARN {agent} not found: {cfg[adapter.bin_key] or 'PATH, ' + cfg['HARNESS_TOOL_INSTALLS']}")
    if uid is None:
        return None

    # Probes as one uid of the range: every uid there is an id with no account, so one stands for all
    print(f"  -- uid {uid}")
    backend = iso.UidBackend(uid)
    why = backend.unavailable()
    if why:
        print(f"  FAIL {why}")
        return None
    print(f"  ok   setpriv {backend.setpriv} {' '.join(iso.SETPRIV_HARDENING)}")
    for s in iso.secret_paths(Path.home(), harness_env.config_dir()):
        if os.path.exists(s):
            print(f"  FAIL uid can read a secret: {s}" if backend.can("r", s) else f"  ok   cannot read: {s}")

    # The work folder sits in the state folder (0711, set by run); everything above it must let the uid pass
    above = ctx.state_dir.parent
    while not above.exists():
        above = above.parent
    print(f"  ok   uid can pass through {above}" if backend.can("x", above)
          else f"  FAIL uid cannot pass through {above}, so it cannot reach its work folder under {ctx.state_dir}")
    return backend


def owned_under(root, groups):
    """{group: (count, owners, first few paths)} of entries under root whose owner is in groups[group], a set of uids.

    .git/worktrees/ is skipped: the admin dirs of task worktrees belong to their uids by design."""
    found = {g: [0, set(), []] for g in groups}
    for top, dirs, files in os.walk(root):
        if os.path.basename(top) == ".git":
            dirs[:] = [d for d in dirs if d != "worktrees"]

        for n in dirs + files:
            path = os.path.join(top, n)
            try:
                owner = os.lstat(path).st_uid
            except OSError:
                continue
            for g, uids in groups.items():
                if owner in uids:
                    hit = found[g]
                    hit[0] += 1
                    hit[1].add(owner)
                    if len(hit[2]) < MAX_LISTED_PATHS:
                        hit[2].append(path)
    return {g: tuple(v) for g, v in found.items()}


def doctor_one(ctx, repo, backend):
    """Print one repository's checks; backend (from doctor_global) probes the main working tree."""
    root = Path(repo.root)
    print(f"== {repo.key}  root={repo.root}")
    print("  ok   git repository" if os.path.lexists(root / ".git") else "  FAIL not a git repository")
    if backend is not None:
        print("  FAIL uid can write the main working tree" if backend.can("w", root) else "  ok   uid cannot write the main working tree")

    # A file a task uid owns stays writable to it (chmod), and any delegation may get that uid next
    try:
        first, last = ctx.uid_range()
    except ws.DelegateError:
        first, last = 1, 0
    in_range = set(range(first, last + 1))
    owned = owned_under(repo.root, {"range": in_range, "old": set(ws.OLD_TABLE_UIDS) - in_range})
    count, _, sample = owned["range"]
    if count:
        print(f"  FAIL {count} file(s) in the main working tree belong to a task uid, so a delegation can change them: "
              f"{' '.join(sample)}{' ...' if count > len(sample) else ''} - chown them back (hard links share the owner "
              f"with their other names, e.g. a package store)")
    elif first <= last:
        print("  ok   no file in the main working tree belongs to a task uid")

    # Outside the range no run gets these uids, but widening the range back would hand the files over
    count, owners, sample = owned["old"]
    if count:
        print(f"  WARN {count} file(s) in the main working tree belong to uid(s) {' '.join(map(str, sorted(owners)))} "
              f"of the old per-repository table, outside the range: {' '.join(sample)}"
              f"{' ...' if count > len(sample) else ''} - chown them back all the same (with their hard links "
              f"elsewhere, e.g. a package cache)")

    # Work folders and the agy policy over them
    work = ws.work_base(ctx.state_dir, repo, "agy")
    settings, notes = agents.ADAPTERS["agy"].policy("worktree", iso.UidBackend(), work / "workspace")
    temp = [r[len("read_file("):-1] for r in settings["permissions"]["deny"] if r.startswith("read_file(")]
    print(f"  INFO work folders {ctx.state_dir / 'work' / (repo.key + '-<agent>')}, results {ws.runs_dir(ctx.state_dir, repo)}")
    print(f"  INFO agy file tools denied in temp folders: {' '.join(temp) or '(none)'}")
    for n in notes:
        print(f"  FAIL agy {n}; agy runs are refused until HARNESS_DELEGATE_STATE (user layer) points elsewhere")

    # What the repository gives the external models
    print("  ok   AGENTS.md present" if (root / "AGENTS.md").is_file()
          else "  WARN no AGENTS.md (entry point for external models; see templates/AGENTS.md.template)")
    if (root / "GEMINI.md").is_file() and (root / "AGENTS.md").is_file():
        print("  WARN GEMINI.md and AGENTS.md both present - agy loads both")
    if (root / ".claude" / "tools" / "agy-delegate.sh").is_file():
        print("  INFO old per-repository copy left: .claude/tools/agy-delegate.sh (superseded by this script)")
    cfg = ctx.layers(repo.root)
    print(f"  config: {cfg.get('_files') or '(no harness.env files)'}")
    print(f"  setup: {setup_line(repo.root) or '(none - HARNESS_DELEGATE_SETUP in the repository layer)'}")
    print(f"  PATH tools: {iso.tool_path(repo.root) or '(none - no pins in mise.toml)'}")


def cmd_doctor(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0}, 0, "doctor [--repo R|--all]")
    backend = doctor_global(ctx)
    for repo in ctx.repos(selection(opts)):
        doctor_one(ctx, repo, backend)
    return 0


def cmd_register(ctx, args):
    # Older SKILL text in running sessions still says to register a repository first; tell it once and go on.
    print("register is no longer needed: each run takes a free uid from HARNESS_DELEGATE_UIDS (option "
          "harness_delegate_uids). A repository's setup command goes in its .claude/harness.env as "
          "HARNESS_DELEGATE_SETUP.")
    return 0


COMMANDS = {"run": cmd_run, "collect": cmd_collect, "remove": cmd_remove, "list": cmd_list, "gc": cmd_gc,
            "doctor": cmd_doctor, "register": cmd_register}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(__doc__.strip())
        return ws.EXIT_USAGE
    try:
        return COMMANDS[argv[0]](Ctx(), argv[1:])
    except ws.DelegateError as e:
        print(f"delegate: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
