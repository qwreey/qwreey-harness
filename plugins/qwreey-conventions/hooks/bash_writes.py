#!/usr/bin/env python3
"""Bash 로 바꾼 파일에 Edit/Write 와 같은 추가 줄 검사를 돌리고, 아직 안 보인 rules 를 넣는다. 막지 않는다.

왜: heredoc, sed -i, 인터프리터 스크립트, tee, 리다이렉트로 쓰면 Edit|Write 매처의 훅(conventions-check, rules_inject)이 돌지 않아
  주석 규약 알림도 rules 주입도 없다. 실제 기록에서 규약이 걸린 쓰기 173번 중 69번이 이 경로였다.

두 단계
  PreToolUse(Bash): bash-bypass-reminder.py 가 늘 sweep() 을 부르고, 쓰기 신호(제자리 편집, 쓰는 인터프리터 스크립트, 저장소 안으로의
    리다이렉트)가 있을 때만 snapshot() 을 부른다. 저장소(명령 cwd 의 git 최상위, git 이 아니면 프로젝트 폴더) 안에서
    - 명령에 든 경로(named)의 지금 내용(없으면 null)과 (mtime, 크기)
    - git 이면 HEAD, `git status --porcelain -uall` 에 나온 파일의 (mtime, 크기)(DIRTY_MAX 개까지), 그중 검사 대상 확장자 파일의 지금 내용
    을 snap_dir() 의 <session>.<main|agent>.<tool_use_id>.json(0600)에 적는다. 내용은 파일당 TEXT_MAX(named 는 CANDIDATE_MAX),
    모두 합쳐 TOTAL_MAX 까지만 적는다.
  PostToolUse(Bash), PostToolUseFailure(Bash, 0 아닌 종료): 이 파일을 스크립트로 돌린다. 스냅숏이 없으면 바로 끝난다. 있으면 changes():
    - 내용을 적어 둔 파일: 지금 내용과 다르면 바뀜, 전 내용은 적어 둔 것
    - 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일: 전 내용은 명령 전 HEAD 의 blob
    - 명령이 커밋까지 했으면(HEAD 가 바뀜) 두 HEAD 사이에 바뀐 파일도 같은 식
    - porcelain 이 DIRTY_MAX 를 넘었으면(overflow) 명령 전 상태를 모르는 항목은 바뀐 것으로 보지 않는다: named 와 (mtime, 크기)를 적어 둔
      항목만 본다
    - 명령 전에 없던 파일(새 파일, untracked, HEAD 에 없는 경로)의 전 내용은 named 의 적어 둔 내용과 HEAD blob 을 합친 것이다.
      mv, cp 로 옮긴 파일의 옛 줄을 새로 쓴 줄로 세지 않으려는 것이다
    - worktree 를 다시 쓰는 git 하위 명령(GIT_REWRITE)이 같은 명령에 있으면 porcelain 비교는 하지 않고 named 만 본다. 그중 지금 내용이
      이미 git 객체로 있는 파일(git 이 되돌린 파일)은 건너뛰고, 나머지는 전 HEAD 와 지금 HEAD 의 blob 줄도 전 내용으로 친다
    - 같은 세션의 다른 스냅숏이 아직 있으면(다른 Bash 가 도는 중) named 만 본다
    읽기는 시간(CHANGES_S)과 글자 수(TOTAL_MAX)에서 끊는다.
    추가 줄 = 지금 줄 중 전 내용에 없던 줄(conv_edit.added_set, Write 덮어쓰기와 같은 셈). 그 줄에 conventions-check 의 file_notice 를
    그대로 돌린다(같은 알림 글, 같은 상태 파일과 잠금이라 중복 거르기도 Edit 경로와 함께 간다). 코드 파일은 reuse-check 를 Write 꼴 입력으로
    따로 돌려 사본 표시 알림을 합친다. 바뀐 파일에 맞는 이 플러그인의 rules 중 이 맥락에 아직 안 넣은 것을 rules_inject 의 함수와 마커로 넣는다.
  출력 하나를 OUTPUT_BUDGET 안에 둔다: 알림을 파일 순서로 넣고 안 드는 파일부터는 conventions-scan 명령 한 줄로 넘기고, rules 는 남은 자리에만.

제외: 저장소 밖, 줄바꿈이 든 경로, 일반 파일이 아닌 것(FIFO 등), conventions-check 의 제외(SKIP_PARTS, 생성 파일, 설정 exclude), 확장자 표 밖.
  알림을 낸 파일 NOTICE_FILES_MAX 개, 분석 BUDGET_S 초에서 끊고 남은 파일은 conventions-scan 명령으로 안내한다.
실패는 조용히 통과한다. 끄기: CONVENTIONS_CHECK=off(검사와 사본), HARNESS_CONVENTIONS_RULES=off(rules).
"""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다

NS = "claude-conventions"
TEXT_MAX = 256 * 1024
CANDIDATE_MAX = 1_000_000  # conv_edit.MAX_BYTES 와 같게: 명령이 이름을 댄 파일은 Edit 경로만큼 큰 것도 본다
TOTAL_MAX = 4 * 1024 * 1024
DIRTY_MAX = 400
TOUCHED_MAX = 500  # rules 맞춤에 넘기는 바뀐 경로 수
READ_FILES_MAX = 200  # Post 가 읽는 파일 수. 알림은 NOTICE_FILES_MAX 개까지라 그 너머는 scan 명령으로 넘긴다
STALE_S = 3600
# 다른 Bash 가 도는 중이라고 볼 스냅숏 나이: 앞쪽 Bash 의 최대 timeout(10분)보다 조금 길게. 그보다 오래된 것은 거절, 중단으로 남은 것이다
PENDING_S = 620
GIT_TIMEOUT_S = 3
CHANGES_S = 1.5
BUDGET_S = 2.5
NOTICE_FILES_MAX = 10
REUSE_MAX = 4
OUTPUT_BUDGET = 9000  # 훅 출력 하나가 10,000자를 넘으면 잘리므로 rules_inject 시험과 같은 여유를 둔다
CHECK_EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro", ".rs", ".py", ".go", ".kt", ".sh", ".html", ".htm", ".md"}
# git 의 전역 옵션(-C dir, -c k=v, --no-pager, --git-dir=x) 뒤의 하위 명령까지 본다
GIT_OPTS = r"(?:\s+(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?|-[A-Za-z]+))*"
GIT_REWRITE = re.compile(r"\bgit" + GIT_OPTS + r"\s+(?:checkout|switch|stash|reset|merge|rebase|pull|cherry-pick|revert|restore|am)\b"
                         r"|\bgh\s+pr\s+checkout\b")
SCAN = os.path.join(os.path.dirname(HERE), "scripts", "conventions-scan.py")


def _clean(v):
    return re.sub(r"[^\w-]", "", str(v or ""))


def snap_dir():
    """스냅숏 폴더. TMPDIR 가 없으면 /tmp 를 여러 사용자가 함께 쓰므로 사용자별 이름을 붙인다."""
    base = tempfile.gettempdir()
    shared = not any(os.environ.get(k) for k in ("TMPDIR", "TEMP", "TMP"))
    if shared and hasattr(os, "getuid"):
        return os.path.join(base, "%s-%d" % (NS, os.getuid()), "bash")
    return os.path.join(base, NS, "bash")


def _own_dir(d):
    """d 와 그 부모를 0700 으로 만들고, 둘 다 이 사용자의 진짜 폴더(심볼릭 링크 아님)인지 본다."""
    for p in (os.path.dirname(d), d):
        try:
            os.mkdir(p, 0o700)
        except FileExistsError:
            pass
        except OSError:
            return False
        try:
            st = os.lstat(p)
        except OSError:
            return False
        if not stat.S_ISDIR(st.st_mode) or (hasattr(os, "getuid") and st.st_uid != os.getuid()):
            return False
    return True


def _who(data):
    return "%s.%s." % (_clean(data.get("session_id")) or "nosession", _clean(data.get("agent_id")) or "main")


def snap_path(data):
    """스냅숏 파일 경로. tool_use_id 가 없으면 명령 글의 해시로 Pre 와 Post 를 잇는다."""
    tid = _clean(data.get("tool_use_id"))
    if not tid:
        ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
        cmd = ti.get("command") if isinstance(ti.get("command"), str) else ""
        tid = "c" + hashlib.sha1(cmd.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    return os.path.join(snap_dir(), _who(data) + tid + ".json")


def pending(data, mine=None):
    """같은 세션의 다른 스냅숏(아직 Post 가 오지 않은 Bash)이 있는가. 서브에이전트도 session_id 가 같아 함께 센다."""
    d = snap_dir()
    sid = (_clean(data.get("session_id")) or "nosession") + "."
    now = time.time()
    try:
        names = os.listdir(d)
    except OSError:
        return False
    for n in names:
        if n.startswith(sid) and n != mine:
            try:
                if now - os.path.getmtime(os.path.join(d, n)) < PENDING_S:
                    return True
            except OSError:
                continue
    return False


def _inside(path, root):
    return os.path.normpath(path).startswith(os.path.normpath(root).rstrip("/") + "/")


def _read(path, cap):
    """일반 파일의 글. 없으면 None, cap 보다 크거나 글이 아니거나 일반 파일이 아니면(FIFO, 장치) False.

    O_NONBLOCK 으로 열고 fstat 로 종류를 본 뒤에야 읽는다: FIFO 를 그냥 열면 쓰는 쪽이 올 때까지 멈춘다."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return None
    except OSError:
        return False
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > cap:
            return False
        with os.fdopen(fd, encoding="utf-8") as f:
            fd = None
            return f.read()
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    finally:
        if fd is not None:
            os.close(fd)


def _size(path):
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def _git(root, *args, stdin=None):
    import subprocess
    try:
        r = subprocess.run(["git", "--no-optional-locks", "-C", root, *args], input=stdin, capture_output=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def repo(cwd):
    """(git 최상위, HEAD sha 또는 None). git 저장소가 아니면 (None, None)."""
    out = _git(cwd, "rev-parse", "--show-toplevel")
    if not out:
        return None, None
    head = _git(cwd, "rev-parse", "-q", "--verify", "HEAD")
    return out.decode().strip(), (head.decode().strip() if head else None)


def porcelain(root):
    """{저장소 기준 경로: XY}. 실패하면 None. 줄바꿈이 든 경로는 뺀다(git cat-file --batch 의 줄 맞춤이 깨진다)."""
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules")
    if out is None:
        return None
    items = out.decode("utf-8", "surrogateescape").split("\0")
    res, i = {}, 0
    while i < len(items):
        e = items[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC":
            i += 1  # 이름 바꾸기는 원래 경로가 한 항목 더 온다
        if "\n" not in e:
            res[e[3:]] = e[:2]
    return res


def _stat(path):
    try:
        st = os.stat(path)
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return None


def sweep():
    """Post 가 오지 않은(거절, 중단) 스냅숏 중 STALE_S 를 넘은 것을 지운다. 모든 PreToolUse(Bash) 에서 부른다(폴더 하나 읽기)."""
    d = snap_dir()
    now = time.time()
    try:
        names = os.listdir(d)
    except OSError:
        return
    for n in names:
        p = os.path.join(d, n)
        try:
            if now - os.path.getmtime(p) > STALE_S:
                os.remove(p)
        except OSError:
            pass


def snapshot(data, cmd, cwd, candidates, signal):
    """PreToolUse(Bash): 명령 전 상태를 적는다. candidates 는 명령에 든 절대 경로, signal 은 쓰기 신호가 있는가."""
    if not signal:
        return
    import conv_env
    if (os.environ.get("CONVENTIONS_CHECK") or "").lower() == "off" and conv_env.is_off("HARNESS_CONVENTIONS_RULES"):
        return
    root, head = repo(cwd)
    is_git = root is not None
    if not is_git:
        root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd

    # Named paths: text while the total fits, (mtime, size) always
    texts, stats, named, total = {}, {}, [], 0
    for p in dict.fromkeys(candidates):
        if not _inside(p, root) or "\n" in p:
            continue
        named.append(p)
        stats[p] = _stat(p)
        t = _read(p, min(CANDIDATE_MAX, TOTAL_MAX - total))
        texts[p] = t
        total += len(t) if isinstance(t, str) else 0

    # Dirty files: (mtime, size) and text within the limits
    rewrite = bool(GIT_REWRITE.search(cmd))
    st = porcelain(root) if is_git and not rewrite else None
    dirty = {}
    for rel in list(st or {})[:DIRTY_MAX]:
        ap = os.path.join(root, rel)
        dirty[rel] = _stat(ap)
        if ap in texts or os.path.splitext(rel)[1].lower() not in CHECK_EXT or total >= TOTAL_MAX:
            continue
        t = _read(ap, min(TEXT_MAX, TOTAL_MAX - total))
        if isinstance(t, str):
            texts[ap] = t
            total += len(t)
    if not texts and st is None:
        return

    # Private file in a private folder
    fp = snap_path(data)
    d = os.path.dirname(fp)
    if not _own_dir(d):
        return
    snap = {"root": root, "head": head, "wide": st is not None, "dirty": dirty, "texts": texts, "stats": stats, "named": named,
            "overflow": len(st or {}) > DIRTY_MAX, "rewrite": rewrite, "concurrent": pending(data, os.path.basename(fp))}
    fd = os.open(fp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if hasattr(os, "fchmod"):
            os.fchmod(f.fileno(), 0o600)  # 같은 이름이 이미 있었으면 O_CREAT 의 권한이 적용되지 않는다
        json.dump(snap, f, ensure_ascii=False)


def blobs(root, rev, rels):
    """{경로: rev 에서의 글, 없으면 None}. 줄바꿈이 든 경로는 묻지 않는다(None). git 이 실패하면 None 을 돌려준다."""
    out = {r: None for r in rels}
    ask = [r for r in rels if "\n" not in r]
    if not rev or not ask:
        return out
    raw = _git(root, "cat-file", "--batch", stdin="".join("%s:%s\n" % (rev, r) for r in ask).encode("utf-8", "surrogateescape"))
    if raw is None:
        return None
    pos = 0
    for r in ask:
        nl = raw.find(b"\n", pos)
        if nl < 0:
            break
        hdr = raw[pos:nl].split()
        pos = nl + 1
        if len(hdr) == 3 and hdr[1] == b"blob":
            size = int(hdr[2])
            out[r] = raw[pos:pos + size].decode("utf-8", "replace")
            pos += size + 1
    return out


def in_git(root, paths):
    """paths 중 지금 내용이 이미 git 객체로 있는 것(git 이 되돌리거나 꺼낸 파일). 객체를 쓰지 않는다."""
    ps = [p for p in paths if "\n" not in p]
    if not ps:
        return set()
    out = _git(root, "hash-object", "--stdin-paths", stdin=("\n".join(ps) + "\n").encode("utf-8", "surrogateescape"))
    hashes = out.decode().split() if out else []
    if len(hashes) != len(ps):
        return set()
    chk = _git(root, "cat-file", "--batch-check", stdin=("\n".join(hashes) + "\n").encode())
    lines = chk.decode().splitlines() if chk else []
    return {p for p, l in zip(ps, lines) if not l.endswith(" missing")} if len(lines) == len(ps) else set()


class _Reader:
    """Post 의 읽기: 마감 시각, 글자 수, 파일 수 한도 안에서만 읽는다. 넘으면 False(모름)이고 그 경로를 skipped 에 적는다."""

    def __init__(self, deadline):
        self.deadline = deadline
        self.left = TOTAL_MAX
        self.files = READ_FILES_MAX
        self.skipped = []

    def __call__(self, path):
        size = _size(path)
        if self.files <= 0 or size > self.left or (self.deadline is not None and time.monotonic() > self.deadline):
            self.skipped.append(path)
            return False
        self.files -= 1
        t = _read(path, min(CANDIDATE_MAX, self.left))
        if isinstance(t, str):
            self.left -= len(t)
        return t


def changes(snap, deadline=None, restrict=False):
    """(검사할 [(절대 경로, 전 글, 지금 글)], 바뀐 모든 절대 경로, 한도로 읽지 못한 경로). 전 글을 모르는 파일은 첫 목록에서 빠진다.

    restrict 가 참이면(다른 Bash 가 도는 중) 명령이 이름을 댄 경로만 본다."""
    root, head = snap["root"], snap.get("head")
    texts, dirty, stats = snap.get("texts") or {}, snap.get("dirty") or {}, snap.get("stats") or {}
    named = set(snap.get("named") or texts)
    restrict = restrict or bool(snap.get("concurrent"))
    if restrict:
        texts = {p: t for p, t in texts.items() if p in named}
    read = _Reader(deadline)
    out, touched, new = {}, [], set()

    # Files whose text was recorded
    for ap, before in texts.items():
        if before is False:
            if ap in stats and stats[ap] != _stat(ap):
                touched.append(ap)  # 너무 커서 글을 적지 못한 파일: rules 만 넣는다
            continue
        now = read(ap)
        if now is False:
            was = stats.get(ap) or dirty.get(os.path.relpath(ap, root))
            if was and was != _stat(ap):
                touched.append(ap)  # 시간이나 글자 한도로 못 읽었다: rules 만 넣는다
            continue
        if now is None or now == before:
            continue
        touched.append(ap)
        out[ap] = (before or "", now)
        if before is None:
            new.add(ap)

    # Clean before the command, changed now
    need, fresh = [], []
    if snap.get("wide") and not restrict:
        overflow = bool(snap.get("overflow"))
        for rel, xy in (porcelain(root) or {}).items():
            ap = os.path.join(root, rel)
            if ap in texts:
                continue
            if rel in dirty:
                if dirty[rel] != _stat(ap):
                    touched.append(ap)  # 전 글을 적어 두지 못한 dirty 파일: rules 만 넣는다
                continue
            if overflow or "D" in xy:
                continue  # overflow: 명령 전 상태를 모르는 항목은 바뀐 것으로 보지 않는다
            touched.append(ap)
            if os.path.splitext(rel)[1].lower() in CHECK_EXT:
                (fresh if xy == "??" else need).append(rel)

        # The command committed: files between the two HEADs
        now_head = _git(root, "rev-parse", "-q", "--verify", "HEAD")
        now_head = now_head.decode().strip() if now_head else None
        if head and now_head and now_head != head and not overflow:
            names = (_git(root, "diff", "--name-only", "-z", head, now_head) or b"").decode("utf-8", "surrogateescape").split("\0")
            for rel in names:
                ap = os.path.join(root, rel)
                if rel and "\n" not in rel and ap not in texts and rel not in dirty and rel not in need and os.path.exists(ap):
                    touched.append(ap)
                    if os.path.splitext(rel)[1].lower() in CHECK_EXT:
                        need.append(rel)
    old = (blobs(root, head, need) or {}) if need else {}
    for rel in need + fresh:
        ap = os.path.join(root, rel)
        before = old.get(rel)
        if rel in need and rel not in old:
            continue  # git 이 실패했다
        now = read(ap)
        if isinstance(now, str):
            out[ap] = (before or "", now)
            if before is None:
                new.add(ap)

    # Lines that came from moved, copied or restored files
    if (new or snap.get("rewrite")) and out:
        rels = sorted(os.path.relpath(p, root) for p in named if _inside(p, root))
        head_texts = (blobs(root, head, rels) or {}) if snap.get("head") is not None else {}
        if new:
            pool = "\n".join([t for p, t in texts.items() if p in named and isinstance(t, str)]
                             + [t for t in head_texts.values() if isinstance(t, str)])
            for ap in new:
                out[ap] = (pool, out[ap][1])
        if snap.get("rewrite"):
            mine = [p for p in out if p in named]
            for p in in_git(root, mine):
                del out[p]
            now_head = _git(root, "rev-parse", "-q", "--verify", "HEAD")
            now_head = now_head.decode().strip() if now_head else None
            after = (blobs(root, now_head, rels) or {}) if now_head and now_head != head else {}
            for p in mine:
                if p in out:
                    rel = os.path.relpath(p, root)
                    extra = [t for t in (head_texts.get(rel), after.get(rel)) if isinstance(t, str)]
                    out[p] = ("\n".join([out[p][0]] + extra), out[p][1])
    seen = set(touched)
    unread = [p for p in read.skipped if p in seen and os.path.splitext(p)[1].lower() in CHECK_EXT]
    return [(ap, b, n) for ap, (b, n) in sorted(out.items())], list(dict.fromkeys(touched))[:TOUCHED_MAX], unread


def _load_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("conventions_check", os.path.join(HERE, "conventions-check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reuse_notes(data, items):
    """reuse-check 를 Write 꼴 입력으로 돌린 알림 본문들. 프로세스를 나란히 띄워 가장 느린 하나만큼 걸린다."""
    import subprocess
    script = os.path.join(HERE, "reuse-check.py")
    procs = []
    for ap, before, now in items[:REUSE_MAX]:
        payload = {k: data.get(k) for k in ("session_id", "agent_id", "cwd", "transcript_path") if data.get(k)}
        payload.update({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": ap, "content": now},
                        "tool_response": {"type": "create"} if not before else {"type": "update", "originalFile": before}})
        try:
            p = subprocess.Popen([sys.executable, "-I", "-X", "utf8", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            p.stdin.write(json.dumps(payload).encode())
            p.stdin.close()
            procs.append(p)
        except OSError:
            continue
    notes = []
    for p in procs:
        try:
            out = p.communicate(timeout=4)[0]
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else ""
        except Exception:
            p.kill()
            continue
        m = re.match(r"<harness-hook [^>]*>(.*)</harness-hook>\Z", ctx, re.S)
        if m:
            notes.append(m.group(1))
    return notes


def rules_block(data, paths, room):
    """바뀐 파일에 맞는 rules 중 이 맥락에 아직 안 넣은 것. room 글자 안에 드는 것만 마커를 잡고, 나머지는 다음 Read/Edit 에 맡긴다."""
    import conv_env
    if conv_env.is_off("HARNESS_CONVENTIONS_RULES"):
        return ""
    import compact_epoch
    import rules_inject as ri
    proj = ri.project_root(data)
    skip = ri.excluded(proj)
    base = compact_epoch.state_path(ri.PLUGIN, ri.NS, data.get("session_id"), data.get("agent_id"))
    hits = {}
    for ap in paths:
        if ri.skipped_dir(ap, proj):
            continue
        for n, rx, b, sw in ri.load_rules():
            if n not in hits and n not in skip and not os.path.exists("%s.%s" % (base, n)) and ri.rule_matches(rx, ap, proj) and ri.switch_on(sw):
                hits[n] = (ri.with_setting(n, b, ap, data), ap)
    picked, files = [], []
    for n, (b, ap) in hits.items():
        trial = ri.injection(", ".join(dict.fromkeys(files + [os.path.basename(ap)])), picked + [(n, b)], True, data.get("session_id"))
        if len(trial) <= room and ri.claim(base, n):
            picked.append((n, b))
            files.append(os.path.basename(ap))
    return ri.injection(", ".join(dict.fromkeys(files)), picked, True, data.get("session_id")) if picked else ""


def more_line(root, left):
    """알림에 담지 못한 파일을 conventions-scan 명령 한 줄로."""
    rels = [os.path.relpath(p, root) for p in left]
    shown, size = [], 0
    for r in rels:
        if size + len(r) > 600:
            break
        shown.append(r)
        size += len(r) + 1
    rest = " (and %d more)" % (len(rels) - len(shown)) if len(shown) < len(rels) else ""
    return (f"{len(rels)} more files: run `python3 -I {SCAN} scan {' '.join(shown)}`{rest} and fix what it lists in lines you added.")


def notices(cc, data, snap, items, t0, unread=()):
    """(알림 본문 목록, 사본 검사에 넘길 코드 파일). 본문은 알림 태그를 씌워도 OUTPUT_BUDGET 안에 든다. cc 는 conventions-check 모듈."""
    import copy
    from conv_edit import added_set
    state_path = cc.state_file(data.get("session_id"), data.get("agent_id"))
    tails_room = len(cc.COMMENT_TAIL) + len(cc.DOC_TAIL) + 2
    more_room = len(more_line(snap["root"], [os.path.join(snap["root"], "x" * 600)] * 2)) + 1  # 경로 600자와 "(and N more)"
    room = OUTPUT_BUDGET - len(cc.notice_tag(data, [])) - tails_room - more_room
    body, tails, code, left = [], [], [], []
    with cc.state_lock(state_path):
        state = cc.load_state(state_path)
        dirty, noticed = False, 0
        for i, (ap, before, now) in enumerate(items):
            if noticed >= NOTICE_FILES_MAX or time.monotonic() - t0 > BUDGET_S:
                left = [x[0] for x in items[i:]]
                break
            found = cc.target(ap, data)
            if not found:
                continue
            root, cfg, rel, kind, ext = found
            if kind == "comment" and cc.generated(now):
                continue
            keep = copy.deepcopy(state)
            parts, changed = cc.file_notice(data, ap, rel, kind, ext, cfg, now, added_set(before, now, 0), state, tail=False)
            size = sum(len(p) + 1 for p in parts)
            if parts and size > room:
                state = keep  # 담지 못한 알림은 알린 것으로 적지 않는다
                left = [x[0] for x in items[i:]]
                break
            dirty = dirty or changed
            if parts:
                noticed += 1
                room -= size
                body.extend(parts)
                tails.append(cc.COMMENT_TAIL if kind == "comment" else cc.DOC_TAIL)
            if kind == "comment":
                code.append((ap, before, now))
        if dirty:
            cc.save_state(state_path, state)
    body.extend(dict.fromkeys(tails))  # 대응 문장은 종류마다 한 번
    have = set(left)
    left = left + [p for p in unread if p not in have]
    if left:
        body.append(more_line(snap["root"], left))
    return body, code


def main():
    t0 = time.monotonic()
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    event = data.get("hook_event_name") if data.get("hook_event_name") in ("PostToolUse", "PostToolUseFailure") else "PostToolUse"
    fp = snap_path(data)
    try:
        with open(fp, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, ValueError):
        return 0
    try:
        os.remove(fp)
    except OSError:
        pass

    # What the command changed
    items, touched, unread = changes(snap, deadline=t0 + CHANGES_S, restrict=pending(data))
    if not touched:
        return 0

    # Added-line checks, then copy notes in the room left
    body, out = [], ""
    if (os.environ.get("CONVENTIONS_CHECK") or "").lower() != "off" and (items or unread):
        cc = _load_check()
        body, code = notices(cc, data, snap, items, t0, unread)
        for note in reuse_notes(data, code):
            if len(cc.notice_tag(data, body + [note])) <= OUTPUT_BUDGET:
                body.append(note)
        out = cc.notice_tag(data, body) if body else ""

    # Notice first, then rules in the room left
    rules = rules_block(data, touched, OUTPUT_BUDGET - len(out) - 1)
    ctx = "\n".join(x for x in (out, rules) if x)
    if ctx:
        json.dump({"hookSpecificOutput": {"hookEventName": event, "additionalContext": ctx}}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
