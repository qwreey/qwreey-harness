"""Registry, work folders, run records and locks of the delegate driver (delegate.py).

Layout, the one delegate.sh uses plus a record folder:
  <dirname(root)>/<key>-<agent>/            root-owned base
    <name>/                                 the task's copy (worktree or empty folder), owned by the task uid
    <name>/.delegate/                       where the task writes report.md / last-message.md
    .homes/<name>/                          the task's HOME, owned by the task uid
    .hooks/pre-push, runs/<date>-<name>/    root-owned
    .runs/<name>/                           this driver's record, root-owned 0700: state.json, run.lock, prompt.md,
                                            meta.txt, stdout.txt, report.md (snapshot), guard.txt, exit
Everything below <name>/ and .homes/<name>/ is the task's, so root never writes there after the chown and reads there
only fd-relative with O_NOFOLLOW from a directory fd it opened on the root-owned base (read_under, copy_tree_at).
delegate.sh runs keep their records in <name>/.delegate/{pid,exit,collected}; they are read that way, never written.
"""
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if os.name == "posix":
    import fcntl
    import pwd

PROG = "delegate.py"  # the name messages tell the user to run
AGENTS = ("agy", "codex")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STATE_FILE = "state.json"
RECORDS = ".runs"     # record folder under the base; a dot name, so delegate.sh's `*/` globs skip it
TASK_OUT = ".delegate"  # inside the task copy: what the task writes for the driver
FIRST_UID = 61000  # registry.tsv header: uids start here; register picks the next free one
# Record files collect keeps.
RUN_FILES = ("prompt.md", "meta.txt", "guard.txt", "stdout.txt", "stderr.txt", "report.md", "exit", STATE_FILE)
# delegate.sh's files inside <name>/.delegate/, read for its runs only.
LEGACY_FILES = ("prompt.md", "meta.txt", "guard.txt", "stdout.txt", "report.md", "last-message.md", "exit")
# Largest task-written file root reads back (report, probe, legacy record): a task can make a file of any size.
MAX_READ_BYTES = 64 * 1024 * 1024
LOCK_POLL_SECONDS = 0.1

# Exit codes of the driver. A finished run exits 0 whatever the model returned; that code is in guard.txt.
EXIT_USAGE = 2
EXIT_NO_AGENT = 3   # agent executable or its credentials missing
EXIT_REFUSED = 4    # refused by isolation policy
EXIT_BUSY = 5       # concurrency limit reached

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIR = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW


class DelegateError(Exception):
    """A refusal with its exit code; main prints `delegate: <message>` and exits with code."""

    def __init__(self, message, code=EXIT_USAGE):
        super().__init__(message)
        self.code = code


def die(message, code=EXIT_USAGE):
    raise DelegateError(message, code)


def note(message):
    print(f"delegate: {message}", file=sys.stderr, flush=True)


def now_iso():
    # Same shape as `date -Is` (2026-11-13T17:39:00+09:00), which delegate.sh wrote into meta.txt and guard.txt.
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- registry ----------
# registry.tsv columns: key, root, uid, setup, note, agent uids. The sixth column ("codex=61004", comma-separated
# agent=uid) gives an agent its own uid so agy and codex of one repository can run side by side without reaching
# each other's files. The first agent (agy), and any agent the sixth column does not name, uses the third column:
# rows written before the sixth column existed keep one uid for both, exactly as delegate.sh reads them
# (delegate.sh reads only the first four columns).
class Repo:
    def __init__(self, key, root, uid, setup, uids=None):
        self.key, self.root, self.uid, self.setup = key, root, uid, setup
        self.uids = dict(uids or {})

    def uid_for(self, agent):
        return self.uids.get(agent, self.uid)

    def shares_uid(self, agent):
        """Agents of this repository whose tasks run as the same uid as agent's (agent itself included)."""
        return [a for a in AGENTS if self.uid_for(a) == self.uid_for(agent)]

    def legacy_base(self, agent):
        """Where delegate.sh and the first driver runs kept workspaces: beside the repository."""
        return Path(os.path.dirname(self.root)) / f"{self.key}-{agent}"


def registry_rows(registry):
    """[(key, root, uid, setup, agent uids, raw line)] of the registry; comments and blank lines skipped.
    A missing file is empty."""
    try:
        text = Path(registry).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = line.split("\t") + [""] * 6
        rows.append((cols[0], cols[1], cols[2], cols[3], cols[5], line))
    return rows


def parse_agent_uids(text, line):
    out = {}
    for part in (p.strip() for p in text.split(",")):
        if not part or part == "-":
            continue
        agent, sep, uid = part.partition("=")
        if not sep or agent not in AGENTS or not uid.isdigit():
            die(f"malformed agent uid {part!r} (want agent=uid): {line}")
        out[agent] = int(uid)
    return out


def _repo_of(row):
    key, root, uid, setup, agent_uids, line = row
    if not uid.isdigit():
        die(f"malformed uid: {line}")
    return Repo(key, root, int(uid), setup, parse_agent_uids(agent_uids, line))


def row_uids(row):
    """Every uid a registry row names (third column and agent uids)."""
    key, root, uid, setup, agent_uids, line = row
    out = [int(uid)] if uid.isdigit() else []
    try:
        out += list(parse_agent_uids(agent_uids, line).values())
    except DelegateError:
        pass
    return out


def git_common_root(path):
    """Main working tree of the repository holding path, also from inside a linked worktree, or None."""
    p = subprocess.run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True)
    return os.path.dirname(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None


def resolve_repo(registry, arg=""):
    """Repo for a registry key, a path, or (empty) the current directory."""
    rows = registry_rows(registry)
    if arg and "/" not in arg:
        hit = [r for r in rows if r[0] == arg]
    else:
        where = arg or os.getcwd()
        root = git_common_root(where)
        if root is None:
            die(f"{where} is not a git repository")
        hit = [r for r in rows if r[1] == root]
    if not hit:
        die(f"repository not in the registry ({registry}): {arg or os.getcwd()} - register it first with "
            f"'delegate.py register <path>'")
    return _repo_of(hit[0])


def all_repos(registry):
    return [_repo_of(r) for r in registry_rows(registry)]


def uid_in_passwd(uid):
    try:
        pwd.getpwuid(uid)
        return True
    except KeyError:
        return False


def _next_uid(used):
    uid = FIRST_UID
    while uid in used or uid_in_passwd(uid):
        uid += 1
    used.add(uid)
    return uid


def _rewrite_registry(reg, lines):
    """Replace the registry file atomically (it is read by running scripts)."""
    reg = Path(os.path.realpath(reg))
    fd, tmp = tempfile.mkstemp(prefix=f".{reg.name}.", dir=reg.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("".join(lines))
        os.chmod(tmp, stat.S_IMODE(os.stat(reg).st_mode))
        os.replace(tmp, reg)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def register(registry, path, key=None):
    """Add a repository with a uid per agent, or give an already registered one the agent uids its row lacks.
    Returns (key, root, {agent: uid} added)."""
    root = os.path.realpath(path)
    if git_common_root(root) is None:
        die(f"not a git repository: {root}")
    rows = registry_rows(registry)
    used = {u for r in rows for u in row_uids(r)}
    reg = Path(registry)
    old = reg.read_text(encoding="utf-8") if reg.is_file() else ""
    hit = [r for r in rows if r[1] == root]
    if hit:
        repo = _repo_of(hit[0])
        missing = [a for a in AGENTS[1:] if a not in repo.uids]
        if not missing:
            die(f"already registered: {root}")
        added = {a: _next_uid(used) for a in missing}
        cols = hit[0][-1].split("\t")
        cols += ["-"] * (5 - len(cols)) if len(cols) < 5 else []
        cols[3] = cols[3] or "-"
        cols[4] = cols[4] or "-"
        merged = dict(repo.uids, **added)
        cols[5:6] = [",".join(f"{a}={u}" for a, u in merged.items())]
        lines = old.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if ln.rstrip("\n") == hit[0][-1]:
                lines[i] = "\t".join(cols) + "\n"
                break
        _rewrite_registry(reg, lines)
        return repo.key, root, added
    key = key or os.path.basename(root)
    if any(r[0] == key for r in rows):
        die(f"key already exists: {key}")
    added = {a: _next_uid(used) for a in AGENTS}
    first, rest = AGENTS[0], AGENTS[1:]
    sep = "" if not old or old.endswith("\n") else "\n"
    with open(reg, "a", encoding="utf-8") as f:
        f.write(f"{sep}{key}\t{root}\t{added[first]}\t-\tregistered {datetime.date.today().isoformat()}\t"
                f"{','.join(f'{a}={added[a]}' for a in rest)}\n")
    return key, root, added


def check_agent(agent):
    if agent not in AGENTS:
        die(f"backend must be {'|'.join(AGENTS)}: {agent}")


def check_name(name):
    if not NAME_RE.match(name):
        die(f"name must match [a-z0-9-]: {name}")


# ---------- root-owned folders ----------
def root_dir(path, mode):
    """Create path if missing and set mode; refuse a folder the task side could swap (a link, another owner, writable
    by group or others). Root writes only into folders that pass this."""
    path = Path(path)
    try:
        os.mkdir(path, mode)
    except FileExistsError:
        pass
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
        die(f"{path} must be a folder owned by uid {os.geteuid()} that only it can write (found mode "
            f"{stat.filemode(st.st_mode)}, owner {st.st_uid}); fix it by hand", EXIT_REFUSED)
    if stat.S_IMODE(st.st_mode) != mode:
        os.chmod(path, mode)
    return path


# Folders on the way to a task's copy: the task uid passes through but cannot list them.
PASS_MODE = 0o711
PRIVATE_MODE = 0o700


def work_base(state_dir, repo, agent):
    """Where new runs keep their workspaces: <state>/work/<key>-<agent>/ (nothing under the repository's parent)."""
    return Path(state_dir) / "work" / f"{repo.key}-{agent}"


def runs_dir(state_dir, repo):
    """Where collected results go: <state>/runs/<key>/<date>-<name>/."""
    return Path(state_dir) / "runs" / repo.key


def make_work_base(state_dir, repo, agent):
    root_dir(state_dir, PASS_MODE)
    root_dir(Path(state_dir) / "work", PASS_MODE)
    return root_dir(work_base(state_dir, repo, agent), PASS_MODE)


def make_runs_dir(state_dir, repo):
    root_dir(state_dir, PASS_MODE)
    root_dir(Path(state_dir) / "runs", PRIVATE_MODE)
    return root_dir(runs_dir(state_dir, repo), PRIVATE_MODE)


def record_dir(base, name):
    return Path(base) / RECORDS / name


def write_safe(path, text, mode=0o600):
    """Write text atomically into a root-owned folder (temp file + rename)."""
    path = Path(path)
    data = text.encode("utf-8") if isinstance(text, str) else text
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------- reading what the task owns ----------
def open_dir_under(base, *parts):
    """fd of base/parts[0]/... opened component by component with O_NOFOLLOW, or None if any part is a link,
    missing or not a folder. base is a path of a root-owned folder (its entries cannot be swapped by the task) or an
    fd already opened this way."""
    try:
        fd = os.dup(base) if isinstance(base, int) else os.open(base, _DIR)
    except OSError:
        return None
    for part in parts:
        try:
            nxt = os.open(part, _DIR, dir_fd=fd)
        except OSError:
            os.close(fd)
            return None
        os.close(fd)
        fd = nxt
    return fd


def read_at(dir_fd, name, limit=MAX_READ_BYTES):
    """Bytes of a regular file name under dir_fd that is not a link, at most limit, else None."""
    try:
        fd = os.open(name, os.O_RDONLY | _NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=dir_fd)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks, left = [], limit
        while left > 0:
            b = os.read(fd, min(left, 1 << 20))
            if not b:
                break
            chunks.append(b)
            left -= len(b)
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_under(base, *parts, limit=MAX_READ_BYTES):
    """Bytes of base/parts... read without following a link anywhere below base, else None."""
    fd = open_dir_under(base, *parts[:-1])
    if fd is None:
        return None
    try:
        return read_at(fd, parts[-1], limit)
    finally:
        os.close(fd)


def exists_under(base, *parts, kind=None):
    """lstat of base/parts... resolved without links; kind 'dir' or 'file' narrows it. False on any link."""
    fd = open_dir_under(base, *parts[:-1])
    if fd is None:
        return False
    try:
        st = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
    except OSError:
        return False
    finally:
        os.close(fd)
    if kind == "dir":
        return stat.S_ISDIR(st.st_mode)
    if kind == "file":
        return stat.S_ISREG(st.st_mode)
    return True


def write_new(path, data, manifest=None):
    """A new file in a root-owned folder, 0600. manifest collects (path, sha256) so the copy can be checked later."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    if manifest is not None:
        manifest.append((Path(path), hashlib.sha256(data).hexdigest()))


def verify_manifest(manifest):
    """Paths whose bytes on disk differ from what was written (missing ones included)."""
    bad = []
    for path, digest in manifest:
        try:
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                bad.append(path)
        except OSError:
            bad.append(path)
    return bad


def copy_tree_at(dir_fd, dst, manifest=None):
    """Copy regular files and folders under dir_fd into dst (root-owned), without links; folders 0700, files 0600."""
    os.makedirs(dst, mode=0o700, exist_ok=True)
    for top, dirs, files, top_fd in os.fwalk(".", dir_fd=dir_fd, follow_symlinks=False):
        out = Path(dst) / top
        for d in dirs:
            st = os.stat(d, dir_fd=top_fd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                os.makedirs(out / d, mode=0o700, exist_ok=True)
        for f in files:
            data = read_at(top_fd, f)
            if data is not None:
                write_new(out / f, data, manifest)


def chown_tree(path, uid, gid):
    """chown -R from fds, never through a link: a link the repository commits must not hand its target to the uid."""
    os.chown(path, uid, gid, follow_symlinks=False)
    for _top, dirs, files, top_fd in os.fwalk(path, follow_symlinks=False):
        for n in dirs + files:
            os.chown(n, uid, gid, dir_fd=top_fd, follow_symlinks=False)


# ---------- state ----------
def read_state(rec):
    try:
        st = json.loads(Path(rec, STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}


def save_state(rec, st):
    write_safe(Path(rec) / STATE_FILE, json.dumps(st, ensure_ascii=False, indent=1) + "\n")


def update_state(rec, **fields):
    st = read_state(rec)
    st.update(fields)
    save_state(rec, st)
    return st


def pid_alive(pid):
    # os.kill(pid, 0) ends the process on Windows; this check is for delegate.sh runs, which are Linux only.
    if os.name != "posix":
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


def legacy_pid_alive(base, name):
    data = read_under(base, name, TASK_OUT, "pid", limit=64)
    try:
        return data is not None and pid_alive(int(data.strip()))
    except ValueError:
        return False


def lock_held(path):
    """True when another process holds the lock file. A missing file is not held (no file is created here)."""
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def take_lock(path, wait=0.0):
    """fd holding an exclusive lock on path, or None when it stays held elsewhere for `wait` seconds.
    The lock lasts until the fd closes. A file this user cannot open for writing is locked through a read fd."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
    except PermissionError:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    end = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            if time.monotonic() >= end:
                os.close(fd)
                return None
            time.sleep(LOCK_POLL_SECONDS)


def is_running(base, name):
    rec = record_dir(base, name)
    if os.path.isdir(rec):
        # A run of this driver holds run.lock in its root-owned record for its whole life.
        return lock_held(rec / "run.lock")
    return legacy_pid_alive(base, name)


def is_collected(base, name):
    # With a record, only the record counts: the task can write anything into its own .delegate/.
    rec = record_dir(base, name)
    if rec.is_dir():
        return bool(read_state(rec).get("collected"))
    return read_under(base, name, TASK_OUT, "collected", limit=4096) is not None


def state_of(base, name):
    rec = record_dir(base, name)
    if is_running(base, name):
        return "running"
    if is_collected(base, name):
        return "collected"
    if rec.is_dir():
        return "finished" if read_state(rec).get("finished") else "aborted"
    if exists_under(base, name, TASK_OUT, "exit", kind="file"):
        return "finished"
    if exists_under(base, name, ".agy", kind="dir"):
        return "legacy"
    if exists_under(base, name, "answer.md", kind="file") or exists_under(base, name, "prompt.md", kind="file"):
        return "legacy-record"
    return "unknown"


def workspaces(base):
    """Task folders under an agent base, sorted; runs/ and dot folders are not tasks."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [Path(base) / n for n in names if n != "runs" and not n.startswith(".") and (Path(base) / n).is_dir()]


def live_legacy_runs(repos, agents=AGENTS):
    """delegate.sh runs alive now (pid file, no record) of the given repositories and agents. delegate.sh runs every
    agent of a repository as the third-column uid."""
    n = 0
    for repo in repos:
        for agent in agents:
            base = repo.legacy_base(agent)
            for w in workspaces(base):
                if not record_dir(base, w.name).is_dir() and legacy_pid_alive(base, w.name):
                    n += 1
    return n


def acquire_slot(state_dir, agent, limit, busy_elsewhere):
    """fd of a free slot lock among `limit` per agent, or None. busy_elsewhere counts runs that hold no slot."""
    slots = root_dir(Path(state_dir) / "slots", 0o700)
    free = []
    for i in range(1, limit + 1):
        fd = take_lock(slots / f"{agent}-{i}.lock")
        if fd is not None:
            free.append(fd)
    held = limit - len(free)
    chosen = free.pop(0) if free and held + busy_elsewhere < limit else None
    for fd in free:
        os.close(fd)
    return chosen, held + busy_elsewhere


def uid_lock_path(state_dir, uid):
    """One task per uid at a time: two tasks of one uid could reach each other's worktree, HOME and credentials."""
    return root_dir(Path(state_dir) / "uids", 0o700) / f"{uid}.lock"


def default_state_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qwreey-delegate"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "qwreey-delegate"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "qwreey-delegate"


# ---------- git ----------
def git_out(*args, cwd=None):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def main_snapshot(root):
    """HEAD and a hash of `git status --porcelain=v1` of the main repository, compared before and after a run."""
    head = (git_out("-C", str(root), "rev-parse", "HEAD") or "").strip()
    status = git_out("-C", str(root), "status", "--porcelain=v1") or ""
    return head, hashlib.sha1(status.encode()).hexdigest()


def worktree_entry(root, wt):
    """(is a registered worktree of root, branch name or '') for wt."""
    out = git_out("-C", str(root), "worktree", "list", "--porcelain") or ""
    want = os.path.realpath(wt)
    for block in out.split("\n\n"):
        lines = block.splitlines()
        if lines and lines[0].startswith("worktree ") and os.path.realpath(lines[0][9:]) == want:
            branch = next((ln[7:] for ln in lines if ln.startswith("branch ")), "")
            return True, branch.removeprefix("refs/heads/")
    return False, ""


# ---------- listing helpers ----------
def du_h(path):
    p = subprocess.run(["du", "-sh", str(path)], capture_output=True, text=True)
    return p.stdout.split("\t", 1)[0] if p.returncode == 0 or p.stdout else "?"


def mtime_str(path):
    return datetime.datetime.fromtimestamp(os.lstat(path).st_mtime).strftime("%Y-%m-%d %H:%M")


def age_days(path, now=None):
    return int(((now or time.time()) - os.lstat(path).st_mtime) // 86400)


def busy_inside(base):
    """True when a process has its cwd inside base (Linux /proc). Runs of an older script have no lock to check."""
    prefix = str(base) + os.sep
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return False
    for p in pids:
        try:
            if os.readlink(f"/proc/{p}/cwd").startswith(prefix):
                return True
        except OSError:
            continue
    return False
