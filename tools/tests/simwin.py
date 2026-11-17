"""Windows 흉내로 파이썬 스크립트를 돌린다. 사용: python3 -I tools/tests/simwin.py <스크립트> [인자...]

Linux 에서 Windows 에 없는 것을 빼고 돌려, 훅이 그 없는 것에 걸려 죽는지 미리 본다. 진짜 Windows 를 대신하지 않는다:
경로 구분자, Git Bash 와 PowerShell, 코드 페이지, 잠금의 실제 의미, os.name == "nt" 분기는 여기서 볼 수 없다.

빼는 것
- 모듈: fcntl, pwd, grp, resource, termios (import 하면 ImportError)
- os 의 POSIX 전용 함수: getuid, geteuid, getgid, getegid, setsid, killpg, getpgid, fork, setpgrp
- signal.SIGKILL, signal.SIGHUP
- /proc 읽기(open, os.listdir, os.scandir, os.readlink 가 /proc 아래면 FileNotFoundError)
- PATH 의 setsid, choom, pgrep, prlimit (shutil.which 가 None)
넣는 것
- msvcrt.locking: 진짜 fcntl.lockf 로 흉내 내어 Windows 잠금 길(lib/file_lock.py)을 밟게 한다.

tools/tests/hook_sandbox.py 는 HOOK_SANDBOX_SIMWIN=1 이면 모든 훅을 이 파일로 돈다(test-hook-replay.py 를 그대로 Windows 흉내로).
"""
import builtins
import io
import os
import runpy
import shutil
import signal
import sys
import types

import fcntl as _real_fcntl  # 지우기 전에 잡아 둔다(가짜 msvcrt 가 쓴다)
import subprocess  # noqa: F401  msvcrt 가 있으면 Windows 로 아는 모듈은 가짜 msvcrt 를 넣기 전에 적재해 둔다
import getpass  # noqa: F401

for _m in ("fcntl", "pwd", "grp", "resource", "termios"):
    sys.modules[_m] = None  # import 하면 ImportError

for _f in ("getuid", "geteuid", "getgid", "getegid", "setsid", "killpg", "getpgid", "fork", "setpgrp"):
    if hasattr(os, _f):
        delattr(os, _f)
for _s in ("SIGKILL", "SIGHUP"):
    if hasattr(signal, _s):
        delattr(signal, _s)


def _is_proc(p):
    try:
        p = os.fspath(p)
    except TypeError:
        return False
    if isinstance(p, bytes):
        p = p.decode(errors="replace")
    return isinstance(p, str) and (p == "/proc" or p.startswith("/proc/"))


def _guard(fn):
    def wrapped(p=".", *a, **kw):
        if _is_proc(p):
            raise FileNotFoundError(2, "No such file or directory (simwin)", str(p))
        return fn(p, *a, **kw)
    return wrapped


_open = builtins.open
builtins.open = io.open = _guard(_open)
os.listdir = _guard(os.listdir)
os.scandir = _guard(os.scandir)
os.readlink = _guard(os.readlink)

_which = shutil.which
shutil.which = lambda cmd, *a, **kw: None if os.path.basename(str(cmd)) in ("setsid", "choom", "pgrep", "prlimit") else _which(cmd, *a, **kw)

msvcrt = types.ModuleType("msvcrt")
msvcrt.LK_UNLCK, msvcrt.LK_LOCK, msvcrt.LK_NBLCK, msvcrt.LK_RLCK, msvcrt.LK_NBRLCK = 0, 1, 2, 3, 4


def _locking(fd, mode, nbytes):
    try:
        if mode == msvcrt.LK_UNLCK:
            _real_fcntl.lockf(fd, _real_fcntl.LOCK_UN, nbytes, 0, os.SEEK_CUR)
        else:
            flags = _real_fcntl.LOCK_EX | (_real_fcntl.LOCK_NB if mode in (msvcrt.LK_NBLCK, msvcrt.LK_NBRLCK) else 0)
            _real_fcntl.lockf(fd, flags, nbytes, 0, os.SEEK_CUR)
    except BlockingIOError as e:
        raise PermissionError(13, "Permission denied (simwin lock held)") from e


msvcrt.locking = _locking
sys.modules["msvcrt"] = msvcrt

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: simwin.py <script> [args...]")
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
