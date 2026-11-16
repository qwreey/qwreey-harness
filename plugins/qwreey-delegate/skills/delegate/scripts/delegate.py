"""delegate.py - hand one task to another model family (agy=Gemini, codex=OpenAI) in isolation.

  delegate.py run <agy|codex> <name> <prompt file> [--repo <key|path>] [--mode worktree|empty]
                  [--ref <commit>] [--model M] [--effort low|medium|high] [--timeout seconds]
  delegate.py collect <agy|codex> <name> [--repo ...]     # keep the result under <workspace>/runs/
  delegate.py remove  <agy|codex> <name> [--repo ...] [--discard] [--delete-branch]
  delegate.py list    [--repo ...|--all]                  # both backends
  delegate.py gc      [--repo ...|--all] [--days N] [--apply]   # preview only unless --apply
  delegate.py doctor  [--repo ...|--all]
  delegate.py register <repository path> [key]

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
import time  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import delegate_agents as agents  # noqa: E402
import delegate_isolation as iso  # noqa: E402
import delegate_results as results  # noqa: E402
import delegate_workspace as ws  # noqa: E402
import harness_env as own_he  # noqa: E402

PROG = ws.PROG
SKILL_DIR = Path(HERE).parent
TEMPLATES = SKILL_DIR / "templates"
DEFAULT_EFFORT = "medium"
DEFAULT_TIMEOUT_SECONDS = 3600
# gc deletes results in <state>/runs/ older than this. Results are read right after the run, and a report worth
# keeping is moved into the repository (.claude/audit/), so two weeks covers a missed read or a weekend.
DEFAULT_RUNS_DAYS = 14
START_LOCK_SECONDS = 120     # wait for another start of the same agent (seconds of git and copying) before giving up
LEGACY_LOCK_SECONDS = 30
SETUP_TIMEOUT_SECONDS = 900  # the registry's setup line, run once in a new worktree
# delegate.sh serializes its start (existence check, live count, pid file) on this lock; taking it too keeps a
# run of either script from slipping past the other's count.
LEGACY_LOCK = "/tmp/delegate-{agent}.lock"
MODES = ("worktree", "empty")
PRE_PUSH = '#!/bin/sh\necho "push refused: delegate workspace" >&2\nexit 1\n'

# harness.env keys this driver reads. Defaults and the USER_ONLY set live in harness_env.py.
KEYS = (
    "HARNESS_DELEGATE_REGISTRY", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP",
    "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX",
    "HARNESS_DELEGATE_KEEP_ENV",
    "HARNESS_DELEGATE_STATE", "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_AGY_MODEL",
    "HARNESS_DELEGATE_CODEX_MODEL", "HARNESS_DELEGATE_SECRET_GLOBS", "HARNESS_DELEGATE_RUNS_DAYS",
)
die = ws.die
note = ws.note


# ---------- config ----------
def harness_loader():
    """(module whose load_layers to use, description). An installed harness_env that does not list this driver's
    USER_ONLY keys would let a repository's committed harness.env open the isolation, so the copy next to this file
    is used instead."""
    he = own_he.installed()
    if he.load_layers is own_he.load_layers:
        return own_he, f"{own_he.__file__} (own copy)"
    need = own_he.USER_ONLY & set(KEYS)
    missing = need - set(getattr(he, "USER_ONLY", ()))
    if missing:
        return own_he, f"{own_he.__file__} (own copy: installed lacks USER_ONLY {', '.join(sorted(missing))})"
    return he, f"{getattr(he, '__file__', '?')} (installed)"


class Ctx:
    def __init__(self):
        self.he, self.he_desc = harness_loader()
        self.cfg = self.layers("")
        self.registry = self.cfg["HARNESS_DELEGATE_REGISTRY"] or str(SKILL_DIR / "registry.tsv")
        # USER_ONLY, so the user layer decides for every repository.
        self.state_dir = Path(self.cfg["HARNESS_DELEGATE_STATE"] or ws.default_state_dir())

    def layers(self, project):
        """Config of the user layer and environment (project ''), or with that repository's layers on top."""
        defaults = {k: own_he.expand(own_he.DEFAULTS.get(k, ""), {}) for k in KEYS}
        return self.he.load_layers(project, defaults=defaults)

    def repo(self, arg):
        return ws.resolve_repo(self.registry, arg or "")

    def repos(self, sel):
        return ws.all_repos(self.registry) if sel == "--all" else [self.repo(sel)]


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
    backend = iso.select_backend(repo, agent)
    uid = repo.uid_for(agent)
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
        uid_lock = ws.take_lock(ws.uid_lock_path(state_dir, uid))
        if uid_lock is None or results.legacy_runs_of_uid(repo, uid):
            sharing = repo.shares_uid(agent)
            hint = (f"; {' and '.join(sharing)} of {repo.key} share it - '{PROG} register {repo.root}' gives each "
                    f"agent its own uid" if len(sharing) > 1 else "")
            die(f"another task of uid {uid} ({repo.key}) is running; one task per uid at a time{hint}", ws.EXIT_BUSY)
        slot, live = ws.acquire_slot(state_dir, agent, limit, ws.live_legacy_runs(ws.all_repos(ctx.registry), [agent]))
        if slot is None:
            die(f"{live} {agent} task(s) already running (limit {limit}, HARNESS_DELEGATE_MAX_CONCURRENT adjusts it - "
                f"the token limit is the user's)", ws.EXIT_BUSY)
        leftover = backend.end_task()
        if leftover:
            note(f"killed {leftover} leftover process(es) of uid {uid}")
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
    with iso.StopSignals() as stop:
        if mode == "worktree" and repo.setup and repo.setup != "-":
            # The setup line comes from the registry; it runs with the task's rights and environment, not root's.
            rc, _, err = backend.run(["bash", "-c", repo.setup], iso.setup_env(env, cfg["HARNESS_TOOL_INSTALLS"]),
                                     cwd=wt, timeout=SETUP_TIMEOUT_SECONDS)
            if rc != 0:
                note(f"warning: setup failed ({'timeout' if rc is None else 'exit ' + str(rc)}): {repo.setup}"
                     f"{': ' + err.strip().splitlines()[-1] if err.strip() else ''}")
        before = ws.main_snapshot(repo.root)
        note(f"start {agent}/{name} ({model}, {mode}) {ws.now_iso()} - {wt}")
        argv = iso.heavy_prefix(own_he, cfg) + backend.wrap(
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
    results.end_leftovers(ctx.state_dir, place.repo, agent)
    st = ws.read_state(place.rec)
    if not st.get("finished") and not ws.exists_under(place.base, name, ws.TASK_OUT, "exit", kind="file"):
        note("warning: no exit record (abnormal end, or a workspace from an older script); collecting what exists")
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
    results.end_leftovers(ctx.state_dir, place.repo, agent)
    results.remove_workspace(place, bool(opts.get("--discard")), bool(opts.get("--delete-branch")))
    print(f"removed: {place.wt}")
    return 0


def cmd_list(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0}, 0, "list [--repo R|--all]")
    for repo in ctx.repos(selection(opts)):
        results.list_repo(ctx.state_dir, repo)
    return 0


def cmd_gc(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0, "--days": 1, "--apply": 0}, 0,
                    "gc [--repo R|--all] [--days N] [--apply]")
    what = "--days" if "--days" in opts else "HARNESS_DELEGATE_RUNS_DAYS"
    days = str(opts.get("--days") or ctx.cfg["HARNESS_DELEGATE_RUNS_DAYS"] or DEFAULT_RUNS_DAYS)
    if not days.isdigit():
        die(f"{what} must be a number: {days}")
    days = int(days)
    if not opts.get("--apply"):
        print("(preview - pass --apply to delete)")
    for repo in ctx.repos(selection(opts)):
        results.gc_repo(ctx.state_dir, repo, days, bool(opts.get("--apply")))
    return 0


# ---------- doctor / register ----------
def dup(values):
    seen, out = set(), []
    for v in values:
        if v in seen and v not in out:
            out.append(v)
        seen.add(v)
    return " ".join(out)


def doctor_global(ctx):
    print(f"== registry {ctx.registry}")
    print(f"  INFO python {sys.executable} {sys.version.split()[0]}")
    print(f"  INFO harness_env {ctx.he_desc}")
    if not Path(ctx.registry).is_file():
        print("  FAIL registry file missing")
        return
    rows = ws.registry_rows(ctx.registry)
    # A uid belongs to one repository; inside a row two agents may share it only through the third-column fallback.
    d = dup(str(u) for r in rows for u in set(ws.row_uids(r)))
    print("  ok   no duplicate uid" if not d else f"  FAIL duplicate uid: {d}")
    for col, what in ((0, "key"), (1, "root")):
        d = dup(r[col] for r in rows)
        print(f"  ok   no duplicate {what}" if not d else f"  FAIL duplicate {what}: {d}")
    for agent, adapter in agents.ADAPTERS.items():
        cfg = ctx.cfg
        found = agents.find_bin(cfg[adapter.bin_key], agent, cfg["HARNESS_TOOL_INSTALLS"], adapter.install_rel)
        print(f"  ok   {agent} {found}" if found else f"  WARN {agent} not found: {cfg[adapter.bin_key] or 'PATH, ' + cfg['HARNESS_TOOL_INSTALLS']}")


def doctor_one(ctx, repo):
    root = Path(repo.root)
    print(f"== {repo.key}  root={repo.root}  " + "  ".join(f"{a}={repo.uid_for(a)}" for a in ws.AGENTS))
    print("  ok   git repository" if os.path.lexists(root / ".git") else "  FAIL not a git repository")
    shared = [a for a in ws.AGENTS if len(repo.shares_uid(a)) > 1]
    if shared:
        print(f"  WARN {' and '.join(shared)} share uid {repo.uid_for(shared[0])}, so they run one at a time and can "
              f"reach each other's files; '{PROG} register {repo.root}' gives each agent its own uid")
    for uid in sorted({repo.uid_for(a) for a in ws.AGENTS}):
        print(f"  -- uid {uid}")
        print(f"  FAIL uid {uid} collides with a real user" if ws.uid_in_passwd(uid) else "  ok   uid is not in /etc/passwd")
        backend = iso.UidBackend(uid)
        why = backend.unavailable()
        if why:
            print(f"  FAIL {why}")
            continue
        print(f"  ok   setpriv {backend.setpriv} {' '.join(iso.SETPRIV_HARDENING)}")
        print("  FAIL uid can write the main working tree" if backend.can("w", root) else "  ok   uid cannot write the main working tree")
        for s in iso.secret_paths(Path.home(), own_he.config_dir()):
            if os.path.exists(s):
                print(f"  FAIL uid can read a secret: {s}" if backend.can("r", s) else f"  ok   cannot read: {s}")
        # The work folder sits in the state folder (0711, set by run); everything above it must let the uid pass.
        above = ctx.state_dir.parent
        while not above.exists():
            above = above.parent
        print(f"  ok   uid can pass through {above}" if backend.can("x", above)
              else f"  FAIL uid cannot pass through {above}, so it cannot reach its work folder under {ctx.state_dir}")
    work = ws.work_base(ctx.state_dir, repo, "agy")
    settings, notes = agents.ADAPTERS["agy"].policy("worktree", iso.UidBackend(repo.uid_for("agy")), work / "workspace")
    temp = [r[len("read_file("):-1] for r in settings["permissions"]["deny"] if r.startswith("read_file(")]
    print(f"  INFO work folders {ctx.state_dir / 'work' / (repo.key + '-<agent>')}, results {ws.runs_dir(ctx.state_dir, repo)}")
    print(f"  INFO agy file tools denied in temp folders: {' '.join(temp) or '(none)'}")
    for n in notes:
        print(f"  FAIL agy {n}; agy runs are refused until HARNESS_DELEGATE_STATE (user layer) points elsewhere")
    print("  ok   AGENTS.md present" if (root / "AGENTS.md").is_file()
          else "  WARN no AGENTS.md (entry point for external models; see templates/AGENTS.md.template)")
    if (root / "GEMINI.md").is_file() and (root / "AGENTS.md").is_file():
        print("  WARN GEMINI.md and AGENTS.md both present - agy loads both")
    if (root / ".claude" / "tools" / "agy-delegate.sh").is_file():
        print("  INFO old per-repository copy left: .claude/tools/agy-delegate.sh (superseded by this script)")
    cfg = ctx.layers(repo.root)
    print(f"  config: {cfg.get('_files') or '(no harness.env files)'}")
    print(f"  PATH tools: {iso.tool_path(repo.root) or '(none - no pins in mise.toml)'}")


def cmd_doctor(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0}, 0, "doctor [--repo R|--all]")
    doctor_global(ctx)
    for repo in ctx.repos(selection(opts)):
        doctor_one(ctx, repo)
    return 0


def cmd_register(ctx, args):
    (path, *key), _ = parse(args, {}, 1, "register <repository path> [key]", max_pos=2)
    key, root, added = ws.register(ctx.registry, path, key[0] if key else None)
    print(f"registered: {key} {root} " + " ".join(f"{a}={u}" for a, u in added.items()))
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
