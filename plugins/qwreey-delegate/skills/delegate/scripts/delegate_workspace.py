"""Repositories, task uids, work folders, run records and locks of the delegate driver (delegate.py).

Layout:
  <state>/work/<key>-<agent>/               root-owned base (work_base)
    <name>/                                 the task's copy (worktree or empty folder), owned by the task uid
    <name>/.delegate/                       where the task writes report.md / last-message.md
    .homes/<name>/                          the task's HOME, owned by the task uid
    .hooks/pre-push                         root-owned
    .runs/<name>/                           the run's record, root-owned 0700: state.json, run.lock, prompt.md,
                                            meta.txt, stdout.txt, stderr.txt, report.md (snapshot), guard.txt, exit
  <state>/runs/<key>/<date>-<name>/         collected results (runs_dir), root-owned 0700
The old location beside the repository, <dirname(root)>/<key>-<agent>/ with its own runs/, has the same base shape
(Repo.legacy_base). Everything below <name>/ and .homes/<name>/ is the task's, so root never writes there after the
chown and reads there only fd-relative with O_NOFOLLOW from a directory fd it opened on the root-owned base
(read_under, copy_tree_at). Runs of the old shell script keep their records in <name>/.delegate/{pid,exit,collected};
they are read that way, never written.
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
    import grp
    import pwd

PROG = "delegate.py"  # the name messages tell the user to run
AGENTS = ("agy", "codex")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STATE_FILE = "state.json"
RECORDS = ".runs"     # record folder under the base; a dot name, so delegate.sh's `*/` globs skip it
TASK_OUT = ".delegate"  # inside the task copy: what the task writes for the driver
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


# ---------- repositories ----------
# The key names a repository's folders in the state folder: the root folder's name for people, plus a hash of the full
# path so two repositories with one folder name never share <state>/work/<key>-<agent>/ or <state>/runs/<key>/.
KEY_HASH_CHARS = 8
_KEY_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


class Repo:
    def __init__(self, root):
        self.root = str(root)
        self.name = os.path.basename(self.root.rstrip(os.sep)) or "repo"
        digest = hashlib.sha256(self.root.encode("utf-8", "surrogateescape")).hexdigest()[:KEY_HASH_CHARS]
        self.key = f"{_KEY_UNSAFE.sub('_', self.name)}-{digest}"

    def legacy_base(self, agent):
        """Where delegate.sh and the first driver runs kept workspaces, beside the repository.

        The old table's key there was the root folder's name."""
        return Path(os.path.dirname(self.root)) / f"{self.name}-{agent}"


def git_common_root(path):
    """Main working tree of the repository holding path, also from inside a linked worktree, or None."""
    p = subprocess.run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True)
    return os.path.dirname(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None


def repos_dir(state_dir):
    """<state>/repos/: one file per repository that ran here, named by its key, holding its root."""
    return Path(state_dir) / "repos"


def remember_repo(state_dir, repo):
    """Note the repository in <state>/repos/<key>, so `--all` and `--repo <key>` find it later."""
    folder = root_dir(repos_dir(state_dir), PRIVATE_MODE)
    entry = folder / repo.key
    try:
        if entry.read_text(encoding="utf-8").strip() == repo.root:
            return
    except OSError:
        pass
    write_safe(entry, repo.root + "\n")


def known_repos(state_dir):
    """Repositories that ran a delegation with this state folder, sorted by key."""
    folder = repos_dir(state_dir)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for n in names:
        data = read_under(folder, n, limit=4096)
        root = data.decode("utf-8", "surrogateescape").strip() if data else ""
        if root and os.path.isabs(root) and Repo(root).key == n:
            out.append(Repo(root))
    return out


def resolve_repo(state_dir, arg=""):
    """Repo for a path, a known key or folder name, or (empty) the current directory.

    A key or a root folder name resolves only for a repository that ran with this state folder before."""
    if arg and "/" not in arg:
        hit = [r for r in known_repos(state_dir) if arg in (r.key, r.name)]
        if len(hit) == 1:
            return hit[0]
        if len(hit) > 1:
            die(f"{arg} names several repositories ({', '.join(r.key for r in hit)}); pass the key or the path")
        if not os.path.isdir(arg):
            die(f"unknown repository {arg}: pass its path (a key or folder name works once it has run here)")
    where = arg or os.getcwd()
    root = git_common_root(where)
    if root is None:
        die(f"{where} is not a git repository")
    return Repo(root)


# ---------- task uids ----------
# HARNESS_DELEGATE_UIDS is one range ("61100-61115"); each run takes the first free uid in it. Its size is the number
# of tasks that can run at once. The bound keeps a typo such as 1-4000000000 from making doctor walk billions of ids.
MAX_UID_RANGE = 4096
_UID_RANGE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
MAX_UID = 2 ** 32 - 2  # (uid_t)-1 means "unchanged" to setreuid
# uids the per-repository table gave out before the range. Runs as them left files behind (packages hard-linked into
# main trees and shared caches, /tmp folders), and any delegation that takes such a uid can change those files.
OLD_TABLE_UIDS = range(61000, 61006)


def parse_uid_range(text):
    """(first, last) of a HARNESS_DELEGATE_UIDS value; dies with exit 2 on anything else."""
    m = _UID_RANGE.match(text or "")
    first, last = (int(m.group(1)), int(m.group(2))) if m else (0, -1)
    if not m or not 0 < first <= last <= MAX_UID or last - first + 1 > MAX_UID_RANGE:
        die(f"HARNESS_DELEGATE_UIDS must be a range of unused ids like 61100-61115 (first above 0, at most "
            f"{MAX_UID_RANGE} ids): {text!r}")
    return first, last


def uid_in_passwd(uid):
    try:
        pwd.getpwuid(uid)
        return True
    except KeyError:
        return False


def id_taken(uid):
    """'user' or 'group' when uid is a real account id, else ''.

    The task runs with that number as uid and gid, so a real group of that number would hand it the group's files."""
    if uid_in_passwd(uid):
        return "user"
    try:
        grp.getgrgid(uid)
        return "group"
    except KeyError:
        return ""


def kept_uids(state_dir):
    """uids of finished or dead runs whose work folder nobody collected yet.

    Such a folder is left by --keep, a failed automatic collect or a run that died. A new task on that uid could change
    those files before main reads them, so a run skips these uids until collect, remove or gc."""
    out = set()
    work = Path(state_dir) / "work"
    try:
        bases = sorted(os.listdir(work))
    except OSError:
        return out

    for b in bases:
        recs = work / b / RECORDS
        try:
            names = os.listdir(recs)
        except OSError:
            continue
        for n in names:
            st = read_state(recs / n)
            # A running task holds its uid lock; take_uid counts it as busy
            if isinstance(st.get("uid"), int) and not st.get("collected") and not lock_held(recs / n / "run.lock"):
                out.add(st["uid"])
    return out


def take_uid(state_dir, first, last):
    """(uid, lock fd) of the first free uid in first..last; dies when none is free.

    Free: not a real user or group, not locked by a running task, not owning an uncollected work folder. Exit 5 when
    tasks hold them (wait), 4 when the range holds only real accounts (the setting is wrong)."""
    taken, kept, busy = [], [], []
    held = kept_uids(state_dir)

    # First free uid wins
    for uid in range(first, last + 1):
        if id_taken(uid):
            taken.append(uid)
            continue
        if uid in held:
            kept.append(uid)
            continue
        fd = take_uid_lock(state_dir, uid)
        if fd is None:
            busy.append(uid)
            continue

        # A run that held this uid during the scan may have ended since, keeping its work folder
        if uid in kept_uids(state_dir):
            os.close(fd)
            kept.append(uid)
            continue
        return uid, fd

    # None free: say what holds them
    parts = [f"{len(busy)} running" if busy else "", f"{len(kept)} hold uncollected work folders (collect/remove "
             f"them or run gc)" if kept else "", f"{len(taken)} are real users or groups" if taken else ""]
    why = f"no free uid in HARNESS_DELEGATE_UIDS {first}-{last}: " + ", ".join(p for p in parts if p)
    die(why, EXIT_BUSY if busy or kept else EXIT_REFUSED)


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


# uids are machine-wide and a run start kills every process of its uid, so their locks must be too: a lock in each
# state folder would let a run with another HARNESS_DELEGATE_STATE take a live task's uid and kill it. /run is
# root-owned on Linux; a lock file left there holds nothing once its process ends.
UID_LOCK_DIR = Path("/run/qwreey-delegate/uids")


def machine_uid_lock_dir():
    """UID_LOCK_DIR made root-owned 0700, or None when /run cannot hold it (not root, no root-owned /run).

    Dies (exit 4) when the folder exists with another owner or open to others: falling back would split the locks."""
    if os.name != "posix" or os.geteuid() != 0:
        return None
    try:
        st = os.lstat(UID_LOCK_DIR.parent.parent)
    except OSError:
        return None
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        return None
    try:
        root_dir(UID_LOCK_DIR.parent, PRIVATE_MODE)
        return root_dir(UID_LOCK_DIR, PRIVATE_MODE)
    except OSError:
        return None


def uid_lock_dir(state_dir):
    """(folder of the uid locks, whether it is machine-wide). Falls back to <state>/uids/; doctor says so."""
    folder = machine_uid_lock_dir()
    if folder is not None:
        return folder, True
    return root_dir(Path(state_dir) / "uids", PRIVATE_MODE), False


def take_uid_lock(state_dir, uid):
    """fd holding uid's lock, or None while a run holds it.

    One task per uid at a time: two tasks of one uid could reach each other's worktree, HOME and credentials, and a
    run start kills every process of its uid."""
    folder, machine_wide = uid_lock_dir(state_dir)
    fd = take_lock(folder / f"{uid}.lock")
    if fd is None or not machine_wide:
        return fd

    # An older driver that does not know /run keeps its lock in the state folder
    if lock_held(Path(state_dir) / "uids" / f"{uid}.lock"):
        os.close(fd)
        return None
    return fd


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
