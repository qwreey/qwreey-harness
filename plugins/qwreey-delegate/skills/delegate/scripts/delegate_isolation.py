"""Isolation backends of the delegate driver: what the task process runs as, with which environment.

Only the uid backend exists so far: Linux root runs the task under `setpriv` as an unprivileged uid that the run takes
from the HARNESS_DELEGATE_UIDS range. The task uid owns only its worktree, the worktree's admin dir and its HOME, so it
cannot write the main working tree or .git/objects. Other backends (codex sandbox profiles, agy shell sandbox) and the
per-agent mode policy where no isolation is found plug in at select_backend().
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import delegate_workspace as ws

TIMEOUT_RC = 124        # what GNU timeout returned, so a guard.txt reads the same as from delegate.sh
NOT_FOUND_RC = 127
KILL_GRACE_SECONDS = 10  # after SIGTERM to the task's process group, before SIGKILL
KILL_ROUNDS = 50         # passes over /proc while processes of the task uid keep appearing
WAIT_POLL_SECONDS = 0.2
MISE_TIMEOUT_SECONDS = 30
GIT_TIMEOUT_SECONDS = 120
# PATH tail of the task. /usr/local/bin is left out because the Studio tools live there.
BASE_PATH = "/usr/bin:/bin"
# No setuid gain, no inheritable or bounding capabilities left in the task.
SETPRIV_HARDENING = ("--no-new-privs", "--inh-caps=-all", "--bounding-set=-all")


def secret_paths(home, config_dir):
    """Files the task uid must not read; doctor probes them."""
    return [Path(config_dir) / ".credentials.json", Path(home) / ".git-credentials", Path(home) / ".ssh"]


def setpriv_lacks(setpriv):
    """Hardening options this setpriv does not list in --help."""
    try:
        text = subprocess.run([setpriv, "--help"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    return [o.split("=")[0] for o in SETPRIV_HARDENING if o.split("=")[0] not in text]


class UidBackend:
    """Runs task commands as one unprivileged uid; uid None is the backend before a run took its uid."""
    name = "uid"

    def __init__(self, uid=None):
        self.uid = uid
        self.setpriv = shutil.which("setpriv")

    def for_uid(self, uid):
        """The same backend bound to the uid a run took."""
        return UidBackend(uid)

    def unavailable(self):
        """Why this backend cannot run here, or ''."""
        if not sys.platform.startswith("linux"):
            return "uid isolation needs Linux"
        if os.geteuid() != 0:
            return "uid isolation needs root (setpriv to the task uid)"
        if not self.setpriv:
            return "setpriv not found"
        if self.uid is not None and (self.uid == 0 or ws.id_taken(self.uid)):
            return (f"uid {self.uid} is a real {ws.id_taken(self.uid) or 'user'} (HARNESS_DELEGATE_UIDS must name "
                    f"unused ids)")
        lacks = setpriv_lacks(self.setpriv)
        if lacks:
            return f"setpriv lacks {' '.join(lacks)}"
        return ""

    def give(self, *paths):
        for p in paths:
            ws.chown_tree(p, self.uid, self.uid)

    def wrap(self, argv):
        return [self.setpriv, *SETPRIV_HARDENING, f"--reuid={self.uid}", f"--regid={self.uid}", "--clear-groups", *argv]

    def run(self, argv, env, cwd=None, timeout=GIT_TIMEOUT_SECONDS):
        """(returncode or None on timeout, stdout, stderr) of argv as the task uid."""
        try:
            p = subprocess.run(self.wrap(argv), env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                               stdin=subprocess.DEVNULL)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            return None, e.stdout or "", f"timed out after {timeout}s"

    def can(self, test, path):
        """Whether the uid passes `test -<test> path` (doctor). The path is an argument, never shell text."""
        rc, _, _ = self.run(["sh", "-c", f'test -{test} "$1"', "sh", str(path)], env={})
        return rc == 0

    def end_task(self):
        """Kill every process left running as the task uid; the number killed."""
        return kill_uid(self.uid)


def git_as_task(backend, env, wt, *args):
    """git inside the task's worktree, as the task uid. Its .git file and admin dir belong to that uid, so git run as
    root there would read config (core.fsmonitor and the like) the task could have written.
    Returns (returncode or None on timeout, stdout, stderr)."""
    return backend.run(["git", "-c", f"safe.directory={wt}", "-C", str(wt), *args], env)


def uid_processes(uid):
    """Live (not zombie) pids whose real, effective or saved uid is uid. Linux /proc."""
    out = []
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return out
    for p in pids:
        try:
            with open(f"/proc/{p}/status", encoding="utf-8") as f:
                fields = dict(line.split(":", 1) for line in f if ":" in line)
        except OSError:
            continue
        if fields.get("State", "").strip().startswith("Z"):
            continue
        if str(uid) in fields.get("Uid", "").split()[:3]:
            out.append(int(p))
    return out


def kill_uid(uid):
    # Processes that left the task's process group (setsid, daemons) still run as its uid and could change the
    # worktree while root collects or removes it.
    if uid == 0 or ws.uid_in_passwd(uid):
        return 0
    killed = 0
    for _ in range(KILL_ROUNDS):
        pids = uid_processes(uid)
        if not pids:
            break
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
                killed += 1
            except OSError:
                pass
        time.sleep(0.05)
    return killed


def select_backend():
    """The isolation for a run, before it takes its uid. Other backends and the fall back to `empty` belong here."""
    backend = UidBackend()
    why = backend.unavailable()
    if why:
        ws.die(f"{why}. Without isolation only a Claude subagent is available here", ws.EXIT_REFUSED)
    return backend


def heavy_prefix(he, cfg):
    """`choom -n 1000 --` (HARNESS_HEAVY_WRAP) with argv[0] resolved, since the task environment has another PATH."""
    argv = he.heavy_wrap(cfg)
    if argv:
        argv[0] = shutil.which(argv[0]) or argv[0]
    return argv


def tool_path(root):
    """Bin dirs of the tools the repository's own mise.toml pins, joined with ':'."""
    mise = shutil.which("mise")
    if not mise:
        return ""
    try:
        p = subprocess.run([mise, "ls", "--current", "--json"], cwd=root, capture_output=True, text=True,
                           timeout=MISE_TIMEOUT_SECONDS)
        data = json.loads(p.stdout) if p.returncode == 0 else {}
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return ""
    prefix = str(root) + os.sep
    names = [k for k, v in (data.items() if isinstance(data, dict) else ())
             if any(e.get("installed") and e.get("source", {}).get("path", "").startswith(prefix) for e in v)]
    if not names:
        return ""
    try:
        p = subprocess.run([mise, "bin-paths", *names], cwd=root, capture_output=True, text=True,
                           timeout=MISE_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return ":".join(ln for ln in p.stdout.splitlines() if ln.strip()) if p.returncode == 0 else ""


TASK_TMP = ".tmp"  # the task's temp folder, inside its HOME: agy is denied the shared temp folders


def task_env(home, tools, hooks, keep_env, extra=None):
    """The task starts from an empty environment so token-like variables of the main session do not leak."""
    env = dict(os.environ) if keep_env else {}
    env.update({
        "HOME": str(home), "TMPDIR": str(Path(home) / TASK_TMP), "PATH": f"{tools}:{BASE_PATH}" if tools else BASE_PATH, "LANG": "C.UTF-8", "TERM": "dumb",
        # A pre-push hook that refuses: the second line after the uid owning nothing to push.
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": str(hooks),
    })
    env.update(extra or {})
    return env


def setup_env(env, installs):
    """The task environment for the repository's setup line (HARNESS_DELEGATE_SETUP), plus mise.

    mise's own folder goes on PATH (setup lines such as `mise exec -- pesde install` call it) and MISE_DATA_DIR at the
    installs HARNESS_TOOL_INSTALLS names. Without the latter mise looks in the task's empty HOME, reports every pinned
    tool as missing and tries to download it."""
    mise = shutil.which("mise")
    if not mise:
        return env
    out = dict(env)
    head = out["PATH"].removesuffix(BASE_PATH).rstrip(":")
    out["PATH"] = ":".join(p for p in (head, os.path.dirname(mise), BASE_PATH) if p)
    data = Path(installs).parent if installs and Path(installs).name == "installs" else None
    if data and data.is_dir():
        out["MISE_DATA_DIR"] = str(data)
    return out


class StopSignals:
    """While active, SIGTERM/SIGHUP/SIGINT only record the first signal: the driver then ends the task and still writes
    its record instead of dying halfway. Later signals are ignored the same way."""
    SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)

    def __init__(self):
        self.signum = None
        self._old = {}

    def _handle(self, signum, _frame):
        if self.signum is None:
            self.signum = signum

    def __enter__(self):
        self._old = {s: signal.signal(s, self._handle) for s in self.SIGNALS}
        return self

    def __exit__(self, *exc):
        for s, h in self._old.items():
            signal.signal(s, h)
        return False


def _record_file(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600), "wb")


def run_task(argv, cwd, env, out_path, timeout, stop, stdin_path=None, err_path=None):
    """Run argv in its own process group with stdout into out_path and stderr into err_path (or out_path too). The
    group ends on timeout or when stop records a signal. Returns the exit code (TIMEOUT_RC on timeout, 128+signal
    when stopped)."""
    with _record_file(out_path) as out, open(stdin_path or os.devnull, "rb") as inp, \
            (_record_file(err_path) if err_path else open(os.devnull, "wb")) as err:
        try:
            # A signal during Popen only sets stop.signum, so the child exists in `proc` before anything reacts.
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=inp, stdout=out,
                                    stderr=err if err_path else subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            out.write(f"delegate: cannot start {argv[0]}: {e}\n".encode())
            return NOT_FOUND_RC
        deadline = time.monotonic() + timeout
        while True:
            if stop.signum is not None:
                _kill_group(proc)
                return 128 + stop.signum
            left = deadline - time.monotonic()
            if left <= 0:
                _kill_group(proc)
                return TIMEOUT_RC
            try:
                return proc.wait(timeout=min(WAIT_POLL_SECONDS, left))
            except subprocess.TimeoutExpired:
                continue


def _kill_group(proc):
    # SIGKILL follows even when the leader exits on SIGTERM: children left in the group would keep running.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=KILL_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    proc.wait()
