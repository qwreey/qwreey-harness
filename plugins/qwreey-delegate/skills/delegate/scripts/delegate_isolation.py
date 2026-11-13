"""Isolation backends of the delegate driver: what the task process runs as, with which environment.

Only the uid backend exists so far: Linux root runs the task under `setpriv` as an unprivileged uid per repository
(registry.tsv). The task uid owns only its worktree, the worktree's admin dir and its HOME, so it cannot write the main
working tree or .git/objects. Other backends (codex sandbox profiles, agy shell sandbox) and the per-agent mode
policy where no isolation is found plug in at select_backend().
"""
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import delegate_workspace as ws

TIMEOUT_RC = 124        # what GNU timeout returned, so a guard.txt reads the same as from delegate.sh
NOT_FOUND_RC = 127
KILL_GRACE_SECONDS = 10  # after SIGTERM to the task's process group, before SIGKILL
MISE_TIMEOUT_SECONDS = 30
# PATH tail of the task. /usr/local/bin is left out because the Studio tools live there.
BASE_PATH = "/usr/bin:/bin"


def secret_paths(home, config_dir):
    """Files the task uid must not read; doctor probes them."""
    return [Path(config_dir) / ".credentials.json", Path(home) / ".git-credentials", Path(home) / ".ssh"]


class UidBackend:
    name = "uid"

    def __init__(self, uid):
        self.uid = uid
        self.setpriv = shutil.which("setpriv")

    def unavailable(self):
        """Why this backend cannot run here, or ''."""
        if not sys.platform.startswith("linux"):
            return "uid isolation needs Linux"
        if os.geteuid() != 0:
            return "uid isolation needs root (setpriv to the repository's uid)"
        if not self.setpriv:
            return "setpriv not found"
        return ""

    def give(self, *paths):
        for p in paths:
            ws.chown_tree(p, self.uid, self.uid)

    def take_back(self, *paths):
        for p in paths:
            os.chown(p, 0, 0, follow_symlinks=False)

    def wrap(self, argv):
        return [self.setpriv, f"--reuid={self.uid}", f"--regid={self.uid}", "--clear-groups", *argv]

    def can(self, test, path):
        """Whether the uid passes `test -<test> path` (doctor). The path is an argument, never shell text."""
        p = subprocess.run(self.wrap(["sh", "-c", f'test -{test} "$1"', "sh", str(path)]), capture_output=True)
        return p.returncode == 0


def select_backend(repo):
    """The isolation for a run. Detection of other backends and the fall back to `empty` belong here."""
    backend = UidBackend(repo.uid)
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


def task_env(home, tools, hooks, keep_env, extra=None):
    """The task starts from an empty environment so token-like variables of the main session do not leak."""
    env = dict(os.environ) if keep_env else {}
    env.update({
        "HOME": str(home), "PATH": f"{tools}:{BASE_PATH}" if tools else BASE_PATH, "LANG": "C.UTF-8", "TERM": "dumb",
        # A pre-push hook that refuses: the second line after the uid owning nothing to push.
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": str(hooks),
    })
    env.update(extra or {})
    return env


class _Stop(Exception):
    pass


def run_task(argv, cwd, env, out_path, timeout, stdin_path=None):
    """Run argv in its own process group; the whole group dies on timeout or when this driver is told to stop.
    Returns the exit code (TIMEOUT_RC on timeout, 128+signal when stopped)."""
    def stop(signum, _frame):
        raise _Stop(signum)

    old = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    proc = None
    try:
        with open(out_path, "wb") as out, open(stdin_path or os.devnull, "rb") as inp:
            try:
                proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=inp, stdout=out, stderr=subprocess.STDOUT,
                                        start_new_session=True)
            except OSError as e:
                out.write(f"delegate: cannot start {argv[0]}: {e}\n".encode())
                return NOT_FOUND_RC
            try:
                return proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_group(proc)
                return TIMEOUT_RC
            except _Stop as e:
                _kill_group(proc)
                return 128 + e.args[0]
    finally:
        for s, h in old.items():
            signal.signal(s, h)


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
