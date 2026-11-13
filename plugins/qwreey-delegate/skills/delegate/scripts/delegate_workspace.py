"""Registry, work folders, run state and locks of the delegate driver (delegate.py).

The on-disk shape is the one delegate.sh uses, so either script sees the other's runs:
  <dirname(root)>/<key>-<agent>/{<name>/, .homes/<name>/, .hooks/, runs/}
  <name>/.delegate/: prompt.md meta.txt guard.txt stdout.txt report.md last-message.md, plus
    state.json (this driver) and the legacy pid / exit / collected files (delegate.sh reads only those).
Files under <name>/ belong to the task uid, so the root side never follows a link it finds there: reads use
O_NOFOLLOW and writes replace the entry through a fresh temp file.
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

AGENTS = ("agy", "codex")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STATE_FILE = "state.json"
FIRST_UID = 61000  # registry.tsv header: uids start here; register picks the next free one
# Run files collect keeps, in the order delegate.sh copied them.
RUN_FILES = ("prompt.md", "meta.txt", "guard.txt", "stdout.txt", "report.md", "last-message.md", "exit", STATE_FILE,
             "events.jsonl", "acp.jsonl")

# Exit codes of the driver. A finished run exits 0 whatever the model returned; that code is in guard.txt.
EXIT_USAGE = 2
EXIT_NO_AGENT = 3   # agent executable or its credentials missing
EXIT_REFUSED = 4    # refused by isolation policy
EXIT_BUSY = 5       # concurrency limit reached


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
class Repo:
    def __init__(self, key, root, uid, setup):
        self.key, self.root, self.uid, self.setup = key, root, uid, setup

    def base(self, agent):
        return Path(os.path.dirname(self.root)) / f"{self.key}-{agent}"


def registry_rows(registry):
    """[(key, root, uid, setup, raw line)] of the registry; comments and blank lines skipped. A missing file is empty."""
    try:
        text = Path(registry).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = line.split("\t") + ["", "", "", ""]
        rows.append((cols[0], cols[1], cols[2], cols[3], line))
    return rows


def _repo_of(row):
    key, root, uid, setup, line = row
    if not uid.isdigit():
        die(f"malformed uid: {line}")
    return Repo(key, root, int(uid), setup)


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


def register(registry, path, key=None):
    root = os.path.realpath(path)
    key = key or os.path.basename(root)
    if git_common_root(root) is None:
        die(f"not a git repository: {root}")
    rows = registry_rows(registry)
    if any(r[1] == root for r in rows):
        die(f"already registered: {root}")
    if any(r[0] == key for r in rows):
        die(f"key already exists: {key}")
    used = {r[2] for r in rows}
    uid = FIRST_UID
    while str(uid) in used or uid_in_passwd(uid):
        uid += 1
    reg = Path(registry)
    old = reg.read_text(encoding="utf-8") if reg.is_file() else ""
    sep = "" if not old or old.endswith("\n") else "\n"
    with open(reg, "a", encoding="utf-8") as f:
        f.write(f"{sep}{key}\t{root}\t{uid}\t-\tregistered {datetime.date.today().isoformat()}\n")
    return key, root, uid


def check_agent(agent):
    if agent not in AGENTS:
        die(f"backend must be {'|'.join(AGENTS)}: {agent}")


def check_name(name):
    if not NAME_RE.match(name):
        die(f"name must match [a-z0-9-]: {name}")


# ---------- files the task uid can touch ----------
def write_safe(path, text, mode=0o644):
    """Write text to path inside a task-owned folder without following a link planted there."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_safe(path, limit=None):
    """Bytes of a regular file that is not a link, else None."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read() if limit is None else f.read(limit)
    finally:
        os.close(fd)


def has_content(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_size > 0


def copy_safe(src, dst):
    data = read_safe(src)
    if data is None:
        return False
    Path(dst).write_bytes(data)
    return True


def chown_tree(path, uid, gid, follow_top=False):
    """chown -R without following links: a link the repository commits must not hand its target to the task uid."""
    os.chown(path, uid, gid, follow_symlinks=follow_top)
    for top, dirs, files in os.walk(path):
        for n in dirs + files:
            os.chown(os.path.join(top, n), uid, gid, follow_symlinks=False)


# ---------- state ----------
def read_state(d):
    data = read_safe(Path(d) / STATE_FILE)
    try:
        st = json.loads(data) if data else {}
    except ValueError:
        return {}
    return st if isinstance(st, dict) else {}


def write_state(d, **fields):
    st = read_state(d)
    st.update(fields)
    save_state(d, st)
    return st


def save_state(d, st):
    write_safe(Path(d) / STATE_FILE, json.dumps(st, ensure_ascii=False, indent=1) + "\n")


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


def legacy_pid_alive(d):
    data = read_safe(Path(d) / "pid", 64)
    try:
        return data is not None and pid_alive(int(data.strip()))
    except ValueError:
        return False


def lock_held(path):
    """True when another process holds the lock file. A missing file is not held (no file is created here)."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
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


def take_lock(path, block=False):
    """fd holding an exclusive lock on path, or None when it is held elsewhere. The lock lasts until the fd closes."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
        return fd
    except OSError:
        os.close(fd)
        return None


def is_running(w):
    d = Path(w) / ".delegate"
    if (d / STATE_FILE).is_file():
        # A run of this driver holds run.lock for its whole life; its pid file may name a reused pid after a crash.
        return lock_held(d / "run.lock")
    return legacy_pid_alive(d)


def state_of(w):
    w = Path(w)
    d = w / ".delegate"
    if is_running(w):
        return "running"
    st = read_state(d)
    if st.get("collected") or (d / "collected").is_file():
        return "collected"
    if st.get("finished") or (d / "exit").is_file():
        return "finished"
    if st:
        return "aborted"
    if (w / ".agy").is_dir():
        return "legacy"
    if (w / "answer.md").is_file() or (w / "prompt.md").is_file():
        return "legacy-record"
    return "unknown"


def workspaces(base):
    """Task folders under an agent base, sorted; runs/ and dot folders are not tasks."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [Path(base) / n for n in names if n != "runs" and not n.startswith(".") and (Path(base) / n).is_dir()]


def live_legacy_runs(repos, agent):
    """delegate.sh runs alive now (pid file, no state.json) over every registered repository."""
    n = 0
    for repo in repos:
        for w in workspaces(repo.base(agent)):
            d = w / ".delegate"
            if not (d / STATE_FILE).is_file() and legacy_pid_alive(d):
                n += 1
    return n


def acquire_slot(state_dir, agent, limit, busy_elsewhere):
    """fd of a free slot lock among `limit` per agent, or None. busy_elsewhere counts runs that hold no slot."""
    slots = Path(state_dir) / "slots"
    slots.mkdir(parents=True, exist_ok=True)
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

