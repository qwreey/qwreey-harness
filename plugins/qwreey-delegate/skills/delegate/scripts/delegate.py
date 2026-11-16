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

import datetime  # noqa: E402
import time  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import delegate_agents as agents  # noqa: E402
import delegate_isolation as iso  # noqa: E402
import delegate_workspace as ws  # noqa: E402
import harness_env as own_he  # noqa: E402

PROG = "delegate.py"
SKILL_DIR = Path(HERE).parent
TEMPLATES = SKILL_DIR / "templates"
DEFAULT_EFFORT = "medium"
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_GC_DAYS = 14
START_LOCK_SECONDS = 120     # wait for another start of the same agent (seconds of git and copying) before giving up
LEGACY_LOCK_SECONDS = 30
SETUP_TIMEOUT_SECONDS = 900  # the registry's setup line, run once in a new worktree
OLD_RUN_DAYS = 180  # gc only reports runs/ records older than this; a person decides whether to delete them
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
    "HARNESS_DELEGATE_CODEX_MODEL", "HARNESS_DELEGATE_SECRET_GLOBS",
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
def git_task(backend, env, wt, *args):
    """git inside the task's worktree, as the task uid. Its .git file and admin dir belong to that uid, so git run as
    root there would read config (core.fsmonitor and the like) the task could have written.
    Returns (returncode or None on timeout, stdout, stderr)."""
    return backend.run(["git", "-c", f"safe.directory={wt}", "-C", str(wt), *args], env)


def snapshot_report(base, name, rec, adapter, mode):
    """Copy the task's answer into the record (root-owned) and return its path, or None when there is none."""
    data = ws.read_under(base, name, *adapter.report_rel(mode))
    if not data:
        src = adapter.fallback(mode)
        if src and src[0] == "task":
            data = ws.read_under(base, name, *src[1:])
        elif src:
            data = ws.read_under(rec, src[1])
    if not data:
        return None
    ws.write_safe(rec / "report.md", data)
    return rec / "report.md"


def cmd_run(ctx, args):
    usage = "run <agy|codex> <name> <prompt file> [options]"
    (agent, name, prompt_file), opts = parse(
        args, {"--repo": 1, "--mode": 1, "--ref": 1, "--model": 1, "--effort": 1, "--timeout": 1}, 3, usage)
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
    backend = iso.select_backend(repo)
    adapter.check_mode(mode, cfg, backend)
    preamble = (TEMPLATES / f"preamble-{mode}.md").read_text(encoding="utf-8")
    task = prompt_path.read_text(encoding="utf-8", errors="replace")

    base = ws.root_dir(repo.base(agent), 0o755)
    homes, hooks = ws.root_dir(base / ".homes", 0o755), ws.root_dir(base / ".hooks", 0o755)
    ws.root_dir(base / "runs", 0o755)
    ws.root_dir(base / ws.RECORDS, 0o700)
    wt, home, rec = base / name, homes / name, ws.record_dir(base, name)
    state_dir = Path(cfg["HARNESS_DELEGATE_STATE"] or ws.default_state_dir())
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    ws.root_dir(state_dir, 0o700)

    start = ws.take_lock(state_dir / f"start-{agent}.lock", START_LOCK_SECONDS)
    if start is None:
        die(f"another {agent} run has been starting for {START_LOCK_SECONDS}s; retry later", ws.EXIT_BUSY)
    legacy = legacy_lock(agent)
    admin = None
    try:
        if os.path.lexists(wt) or os.path.lexists(rec):
            die(f"{wt} already exists - use another name, or collect/remove it")
        uid_lock = ws.take_lock(ws.uid_lock_path(state_dir, repo.uid))
        if uid_lock is None or ws.live_legacy_runs([repo]):
            die(f"another task of uid {repo.uid} ({repo.key}) is running; agy and codex of one repository share that "
                f"uid, so they run one at a time", ws.EXIT_BUSY)
        slot, live = ws.acquire_slot(state_dir, agent, limit, ws.live_legacy_runs(ws.all_repos(ctx.registry), [agent]))
        if slot is None:
            die(f"{live} {agent} task(s) already running (limit {limit}, HARNESS_DELEGATE_MAX_CONCURRENT adjusts it - "
                f"the token limit is the user's)", ws.EXIT_BUSY)
        leftover = backend.end_task()
        if leftover:
            note(f"killed {leftover} leftover process(es) of uid {repo.uid}")
        ws.write_safe(hooks / "pre-push", PRE_PUSH, 0o755)
        commit = (ws.git_out("-C", repo.root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") or "").strip()
        if not commit:
            die(f"commit not found: {ref}")
        os.mkdir(rec, 0o700)
        run_lock = ws.take_lock(rec / "run.lock")
        state = {"driver": PROG, "agent": agent, "mode": mode, "isolation": backend.name, "repo": repo.key,
                 "root": repo.root, "uid": repo.uid, "model": model, "effort": effort, "ref": ref, "commit": commit,
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
    adapter.prepare_home(cfg, home)

    report_rel = adapter.report_rel(mode)
    for k, v in (("{{WT}}", wt), ("{{ROOT}}", repo.root), ("{{KEY}}", repo.key), ("{{REPORT}}", wt.joinpath(*report_rel))):
        preamble = preamble.replace(k, str(v))
    prompt = preamble + task
    ws.write_safe(rec / "prompt.md", prompt)
    ws.write_safe(rec / "meta.txt", "".join(f"{k}: {v}\n" for k, v in (
        ("backend", agent), ("mode", mode), ("repo", f"{repo.key} ({repo.root})"), ("uid", repo.uid), ("model", model),
        ("effort", effort), ("ref", f"{ref} -> {commit}"), ("prompt-source", prompt_path), ("started", state["started"]),
        ("isolation", backend.name), ("driver", PROG))))

    backend.give(*(p for p in (wt, home, admin) if p))
    env = iso.task_env(home, iso.tool_path(repo.root), hooks, bool(cfg["HARNESS_DELEGATE_KEEP_ENV"]),
                       adapter.extra_env(home))
    with iso.StopSignals() as stop:
        if mode == "worktree" and repo.setup and repo.setup != "-":
            # The setup line comes from the registry; it runs with the task's rights and environment, not root's.
            rc, _, err = backend.run(["bash", "-c", repo.setup], env, cwd=wt, timeout=SETUP_TIMEOUT_SECONDS)
            if rc != 0:
                note(f"warning: setup failed ({'timeout' if rc is None else 'exit ' + str(rc)}): {repo.setup}"
                     f"{': ' + err.strip().splitlines()[-1] if err.strip() else ''}")
        before = ws.main_snapshot(repo.root)
        note(f"start {agent}/{name} ({model}, {mode}) {ws.now_iso()} - {wt}")
        argv = iso.heavy_prefix(own_he, cfg) + backend.wrap(
            adapter.argv(bin_path, model, effort, timeout, prompt, wt, adapter.last_path(wt, mode), cfg))
        rc = iso.run_task(argv, wt, env, rec / "stdout.txt", timeout + agents.PRINT_TIMEOUT_MARGIN, stop,
                          adapter.stdin(rec))
        killed = backend.end_task()
        report = snapshot_report(base, name, rec, adapter, mode)

        after = ws.main_snapshot(repo.root)
        guard = [f"exit: {rc}", f"finished: {ws.now_iso()}"]
        if before == after:
            guard.append("main repo: unchanged")
        else:
            guard.append(f"main repo: CHANGED during the run (HEAD {before[0]} -> {after[0]}; status hash differs) - "
                         f"check whether the main session or the user did it")
        if killed:
            guard.append(f"task processes left after the run: {killed} killed")
        if mode == "worktree":
            hrc, head, herr = git_task(backend, env, wt, "rev-parse", "HEAD")
            src, status, serr = git_task(backend, env, wt, "status", "--porcelain=v1")
            backend.end_task()
            guard.append(f"worktree HEAD: {head.strip()} (base {commit})" if hrc == 0
                         else f"worktree HEAD: unknown (git: {herr.strip() or hrc})")
            guard.append("worktree changes:" if src == 0 else f"worktree changes: unknown (git: {serr.strip() or src})")
            guard += [ln for ln in status.splitlines() if not ln.startswith(f"?? {ws.TASK_OUT}/") and ln != "?? REPORT.md"]
        guard_text = "\n".join(guard) + "\n"
        ws.write_safe(rec / "guard.txt", guard_text)
        ws.write_safe(rec / "exit", f"{rc}\n")
        state.update(finished=ws.now_iso(), rc=rc)
        ws.save_state(rec, state)
        os.close(run_lock)
        os.close(slot)
        os.close(uid_lock)

        note(f"done {agent}/{name} - exit {rc}")
        sys.stdout.write(guard_text)
        if report:
            print(f"report: {report} ({os.lstat(report).st_size} bytes)")
        else:
            print(f"report: MISSING - see {rec / 'stdout.txt'}")
        print(f"next: main reads and verifies -> {PROG} collect {agent} {name} --repo {repo.key} -> "
              f"{PROG} remove {agent} {name} --repo {repo.key}")
    return 0


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


# ---------- collect / remove ----------
def locate(ctx, agent, name, repo_arg):
    ws.check_agent(agent)
    ws.check_name(name)
    repo = ctx.repo(repo_arg)
    base = repo.base(agent)
    if not (base / name).is_dir() and not ws.record_dir(base, name).is_dir():
        die(f"not found: {base / name}")
    return repo, base


def end_leftovers(ctx, repo):
    """Kill what still runs as the repository's uid before root reads or deletes its files, unless a live task of
    that uid holds its lock (then those processes are that task's)."""
    backend = iso.UidBackend(repo.uid)
    if backend.unavailable():
        return
    state_dir = Path(ctx.cfg["HARNESS_DELEGATE_STATE"] or ws.default_state_dir())
    if not state_dir.is_dir():
        return
    fd = ws.take_lock(ws.uid_lock_path(state_dir, repo.uid))
    if fd is None:
        return
    try:
        if not ws.live_legacy_runs([repo]):
            killed = backend.end_task()
            if killed:
                note(f"killed {killed} leftover process(es) of uid {repo.uid}")
    finally:
        os.close(fd)


def copy_probes(base, name, since, out):
    """agy writes its probes to brain/<conversation>/scratch under HOME, outside the guard's worktree change list,
    and remove deletes HOME; keep this task's scratch and transcript. HOME is the task's: walked from fds, no links."""
    brain = ws.open_dir_under(base, ".homes", name, ".gemini", "antigravity-cli", "brain")
    if brain is None:
        return
    try:
        for conv in sorted(os.listdir(brain)):
            cfd = ws.open_dir_under(brain, conv)
            if cfd is None:
                continue
            try:
                newer = os.fstat(cfd).st_mtime > since or any(
                    os.stat(n, dir_fd=tfd, follow_symlinks=False).st_mtime > since
                    for _t, ds, fs, tfd in os.fwalk(".", dir_fd=cfd, follow_symlinks=False) for n in ds + fs)
                if not newer:
                    continue
                dst = out / "agy" / conv
                for d in (out / "agy", dst):
                    os.makedirs(d, mode=0o700, exist_ok=True)
                sfd = ws.open_dir_under(cfd, "scratch")
                if sfd is not None:
                    try:
                        ws.copy_tree_at(sfd, dst / "scratch")
                    finally:
                        os.close(sfd)
                data = ws.read_under(cfd, ".system_generated", "logs", "transcript.jsonl")
                if data is not None:
                    ws.write_new(dst / "transcript.jsonl", data)
            finally:
                os.close(cfd)
    finally:
        os.close(brain)


def cmd_collect(ctx, args):
    (agent, name), opts = parse(args, {"--repo": 1}, 2, "collect <agy|codex> <name> [--repo R]")
    repo, base = locate(ctx, agent, name, opts.get("--repo"))
    if ws.is_running(base, name):
        die(f"still running: {agent}/{name}")
    end_leftovers(ctx, repo)
    rec = ws.record_dir(base, name)
    st = ws.read_state(rec)
    legacy = not st
    if not st.get("finished") and not ws.exists_under(base, name, ws.TASK_OUT, "exit", kind="file"):
        note("warning: no exit record (abnormal end, or a workspace from an older script); collecting what exists")
    runs = ws.root_dir(base / "runs", 0o755)
    out = runs / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}-{name}"
    os.makedirs(out, mode=0o700, exist_ok=True)
    os.chmod(out, 0o700)
    if legacy:
        # delegate.sh kept its record inside the task copy; read it without following links.
        for f in ws.LEGACY_FILES:
            data = ws.read_under(base, name, ws.TASK_OUT, f)
            if data is not None:
                ws.write_new(out / f, data)
        data = ws.read_under(base, name, "REPORT.md")
        if data is not None:
            ws.write_new(out / "report.md", data)
    else:
        for f in ws.RUN_FILES:
            data = ws.read_under(rec, f)
            if data is not None:
                ws.write_new(out / f, data)
    if agent == "agy":
        copy_probes(base, name, float("-inf") if legacy else st.get("started_ts", float("-inf")), out)
    if ws.exists_under(base, name, ".git"):
        # The experiment diff, new files included, without .delegate/ and the report. It runs as the task uid (see
        # git_task); the HOME of the task is still there because remove deletes it later.
        backend = iso.UidBackend(repo.uid)
        why = backend.unavailable()
        if why:
            note(f"warning: diff.patch not made: {why}")
        else:
            wt = base / name
            home = base / ".homes" / name
            common = (ws.git_out("-C", repo.root, "rev-parse", "--path-format=absolute", "--git-common-dir") or "").strip()
            # `add -N` writes the empty blob, and the task uid cannot write the main .git/objects (by design): new
            # objects go to a folder in the task's HOME, the main store is read as an alternate.
            odb = home / ".delegate-objects"
            env = iso.task_env(home, "", base / ".hooks", False, {
                "GIT_OBJECT_DIRECTORY": str(odb), "GIT_ALTERNATE_OBJECT_DIRECTORIES": os.path.join(common, "objects")})
            backend.run(["mkdir", "-p", str(odb)], env)
            spec = ["--", ".", f":!{ws.TASK_OUT}", ":!REPORT.md"]
            arc, _, aerr = git_task(backend, env, wt, "add", "-N", "--all", *spec)
            drc, diff, derr = git_task(backend, env, wt, "diff", "--binary", "--no-ext-diff", "--no-textconv", *spec)
            backend.end_task()
            if arc != 0 or drc != 0:
                note(f"warning: diff.patch not made: git add -N -> {arc} {aerr.strip()}; git diff -> {drc} {derr.strip()}")
            elif diff:
                ws.write_new(out / "diff.patch", diff.encode("utf-8", "surrogateescape"))
    ws.root_dir(base / ws.RECORDS, 0o700)
    if legacy:
        os.makedirs(rec, mode=0o700, exist_ok=True)
        ws.save_state(rec, {"driver": PROG, "agent": agent, "legacy": True, "collected": str(out)})
    else:
        ws.update_state(rec, collected=str(out))
    print(f"collected: {out}")
    for p in sorted(out.rglob("*")):
        if p.is_file():
            print(f"  {p.lstat().st_size:>9}  {p.relative_to(out)}")
    return 0


def remove(ctx, repo, base, agent, name, discard=False, delete_branch=False):
    if ws.is_running(base, name):
        die(f"still running: {agent}/{name}")
    if not ws.is_collected(base, name) and not discard:
        # Workspaces from older scripts (.agy/ and AGY_REPORT.md) have a shape collect does not know; a person decides.
        die(f"not collected yet - run '{PROG} collect {agent} {name}' first, or pass --discard to throw it away")
    end_leftovers(ctx, repo)
    wt, rec = base / name, ws.record_dir(base, name)
    registered, branch = ws.worktree_entry(repo.root, wt)
    admin = ws.read_state(rec).get("admin")
    # Removed by root without running git inside the task's tree; shutil.rmtree does not follow links.
    if os.path.lexists(wt):
        shutil.rmtree(wt)
    worktrees = os.path.join(repo.root, ".git", "worktrees") + os.sep
    if admin and admin.startswith(worktrees) and os.path.lexists(admin):
        shutil.rmtree(admin)
    if registered or admin:
        subprocess.run(["git", "-C", repo.root, "worktree", "prune"], check=False)
    home = base / ".homes" / name
    if os.path.lexists(home):
        shutil.rmtree(home)
    if os.path.lexists(rec):
        shutil.rmtree(rec)
    if branch:
        if delete_branch:
            subprocess.run(["git", "-C", repo.root, "branch", "-D", branch], check=False)
        else:
            note(f"branch '{branch}' (old style) left in place; --delete-branch removes it, after the user confirms")
    print(f"removed: {wt}")


def cmd_remove(ctx, args):
    (agent, name), opts = parse(args, {"--repo": 1, "--discard": 0, "--delete-branch": 0}, 2,
                                "remove <agy|codex> <name> [--repo R] [--discard] [--delete-branch]")
    repo, base = locate(ctx, agent, name, opts.get("--repo"))
    remove(ctx, repo, base, agent, name, bool(opts.get("--discard")), bool(opts.get("--delete-branch")))
    return 0


# ---------- list / gc ----------
def prune_preview(root):
    p = subprocess.run(["git", "-C", root, "worktree", "prune", "--dry-run", "-v"], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def list_one(ctx, repo):
    for agent in ws.AGENTS:
        base = repo.base(agent)
        if not base.is_dir():
            continue
        print(f"== {base} ({ws.du_h(base)})")
        for w in ws.workspaces(base):
            print(f"  {w.name:<28} {ws.state_of(base, w.name):<10} {ws.du_h(w):>6}  {ws.mtime_str(w)}")
        runs = base / "runs"
        if runs.is_dir():
            print(f"  runs/: {sum(1 for p in runs.iterdir() if p.is_dir())} ({ws.du_h(runs)})")
        if (base / ".home").is_dir():
            print(f"  .home (old shared HOME): {ws.du_h(base / '.home')}")
    for line in prune_preview(repo.root).splitlines():
        print(f"  prune? {line}")


def cmd_list(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0}, 0, "list [--repo R|--all]")
    for repo in ctx.repos(selection(opts)):
        list_one(ctx, repo)
    return 0


def gc_one(ctx, repo, days, apply):
    for agent in ws.AGENTS:
        base = repo.base(agent)
        if not base.is_dir():
            continue
        tag = f"{repo.key}-{agent}"
        # Run locks cover this driver's tasks only; a process whose cwd is inside the workspace is checked directly.
        if ws.busy_inside(base):
            print(f"held       {tag} (a process is running inside this workspace - retry after it ends)")
            continue
        for w in ws.workspaces(base):
            st, age, n = ws.state_of(base, w.name), ws.age_days(w), w.name
            if st == "collected":
                print(f"delete     {tag}/{n} (collected, {age}d, {ws.du_h(w)})")
                if apply:
                    try:
                        remove(ctx, repo, base, agent, n)
                    except ws.DelegateError as e:
                        note(str(e))
            elif st == "finished":
                if age >= days:
                    print(f"check      {tag}/{n} (finished but not collected, {age}d) - collect it or remove --discard")
            elif st == "aborted":
                print(f"check      {tag}/{n} (run ended without a result, {age}d) - read {ws.RECORDS}/{n}/, then remove --discard")
            elif st == "legacy-record":
                print(f"old record {tag}/{n} (prompt/answer - candidate to move into runs/; --apply leaves it alone)")
            elif st == "legacy":
                print(f"check      {tag}/{n} (workspace of an older script, {age}d, {ws.du_h(w)}) - decide whether to "
                      f"keep AGY_REPORT.md, then remove --discard")
            elif st == "running":
                print(f"running    {tag}/{n}")
            else:
                print(f"check      {tag}/{n} (unknown shape - inspect by hand)")
        for r in sorted((base / ws.RECORDS).iterdir()) if (base / ws.RECORDS).is_dir() else ():
            if (base / r.name).is_dir() or ws.is_running(base, r.name):
                continue
            if ws.read_state(r).get("collected"):
                print(f"delete     {tag}/{ws.RECORDS}/{r.name} (collected record without a workspace)")
                if apply:
                    shutil.rmtree(r)
            else:
                print(f"check      {tag}/{ws.RECORDS}/{r.name} (record without a workspace) - read it, then "
                      f"remove {agent} {r.name} --discard")
        homes = base / ".homes"
        for h in sorted(homes.iterdir()) if homes.is_dir() else ():
            if not h.is_dir() or (base / h.name).is_dir():
                continue
            print(f"delete     {tag}/.homes/{h.name} (HOME without an owner, {ws.du_h(h)})")
            if apply:
                shutil.rmtree(h)
        if (base / ".home").is_dir():
            print(f"delete     {tag}/.home (old shared HOME - accumulates conversation history, {ws.du_h(base / '.home')})")
            if apply:
                shutil.rmtree(base / ".home")
        runs = base / "runs"
        for r in sorted(runs.iterdir()) if runs.is_dir() else ():
            if r.is_dir() and ws.age_days(r) > OLD_RUN_DAYS:
                print(f"old        {r} ({OLD_RUN_DAYS}d+, kept record - a person decides whether to delete)")
    p = prune_preview(repo.root)
    if p:
        print(f"prune      {repo.key}: {p}")
        if apply:
            subprocess.run(["git", "-C", repo.root, "worktree", "prune", "-v"], check=False)


def cmd_gc(ctx, args):
    _, opts = parse(args, {"--repo": 1, "--all": 0, "--days": 1, "--apply": 0}, 0,
                    "gc [--repo R|--all] [--days N] [--apply]")
    days = DEFAULT_GC_DAYS
    if "--days" in opts:
        if not opts["--days"].isdigit():
            die(f"--days must be a number: {opts['--days']}")
        days = int(opts["--days"])
    if not opts.get("--apply"):
        print("(preview - pass --apply to delete)")
    for repo in ctx.repos(selection(opts)):
        gc_one(ctx, repo, days, bool(opts.get("--apply")))
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
    for col, what in ((2, "uid"), (0, "key"), (1, "root")):
        d = dup(r[col] for r in rows)
        print(f"  ok   no duplicate {what}" if not d else f"  FAIL duplicate {what}: {d}")
    for agent, adapter in agents.ADAPTERS.items():
        cfg = ctx.cfg
        found = agents.find_bin(cfg[adapter.bin_key], agent, cfg["HARNESS_TOOL_INSTALLS"], adapter.install_rel)
        print(f"  ok   {agent} {found}" if found else f"  WARN {agent} not found: {cfg[adapter.bin_key] or 'PATH, ' + cfg['HARNESS_TOOL_INSTALLS']}")


def doctor_one(ctx, repo):
    root = Path(repo.root)
    print(f"== {repo.key}  root={repo.root}  uid={repo.uid}")
    print("  ok   git repository" if os.path.lexists(root / ".git") else "  FAIL not a git repository")
    print(f"  FAIL uid {repo.uid} collides with a real user" if ws.uid_in_passwd(repo.uid) else "  ok   uid is not in /etc/passwd")
    backend = iso.UidBackend(repo.uid)
    why = backend.unavailable()
    if why:
        print(f"  FAIL {why}")
    else:
        print(f"  ok   setpriv {backend.setpriv} {' '.join(iso.SETPRIV_HARDENING)}")
        print("  FAIL uid can write the main working tree" if backend.can("w", root) else "  ok   uid cannot write the main working tree")
        for s in iso.secret_paths(Path.home(), own_he.config_dir()):
            if os.path.exists(s):
                print(f"  FAIL uid can read a secret: {s}" if backend.can("r", s) else f"  ok   cannot read: {s}")
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
    key, root, uid = ws.register(ctx.registry, path, key[0] if key else None)
    print(f"registered: {key} {root} uid={uid}")
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
