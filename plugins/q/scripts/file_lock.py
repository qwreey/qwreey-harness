"""배타 파일 잠금 하나(표준 라이브러리만). POSIX 는 fcntl.flock, Windows 는 msvcrt.locking(첫 바이트).
@copy-of: lib/file_lock.py
플러그인 사본(q/scripts, qwreey-sessions/scripts/sllib)은 바이트가 같아야 한다. lib/file_lock.py 만 고치고
python3 -I tools/sync-copies.py --apply 로 사본에 옮긴다.

쓰는 법: 잠금 파일을 열어 둔 채 lock(f) 를 부르고, 닫기 전에 unlock(f).
- blocking=True: 잡을 때까지 기다린다(POSIX 는 flock 이, Windows 는 POLL_S 간격으로 다시 시도한다).
- blocking=False: 남이 잡고 있으면 바로 False.
- 둘 다 없는 플랫폼이면 잠그지 않고 True 다(잠금은 겹침을 줄일 뿐, 없다고 훅을 멈출 일은 아니다).
"""
import time

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

POLL_S = 0.05


def lock(f, blocking=True):
    """열린 파일 f 에 배타 잠금을 잡으면 True, blocking=False 이고 남이 잡고 있으면 False."""
    if fcntl is not None:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            return False
        return True
    if msvcrt is not None:
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                if not blocking:
                    return False
                time.sleep(POLL_S)
    return True


def unlock(f):
    """lock 으로 잡은 잠금을 푼다. 실패는 무시한다(닫으면 풀린다)."""
    try:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_UN)
        elif msvcrt is not None:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except (OSError, ValueError):
        pass
