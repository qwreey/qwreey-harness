#!/usr/bin/env python3
"""Bash 로 바꾼 파일에 Edit/Write 와 같은 추가 줄 검사를 돌리고, 아직 안 보인 rules 를 넣는다. 막지 않는다.

왜: heredoc, sed -i, 인터프리터 스크립트, tee, 리다이렉트로 쓰면 Edit|Write 매처의 훅(conventions-check, rules_inject)이 돌지 않아
  주석 규약 알림도 rules 주입도 없다. 실제 기록에서 규약이 걸린 쓰기 173번 중 69번이 이 경로였다.

두 단계
  PreToolUse(Bash): bash-bypass-reminder.py 가 쓰기 신호(제자리 편집, 쓰는 인터프리터 스크립트, 저장소 안으로의 리다이렉트)가 있을 때만
    snapshot() 을 부른다. 저장소(명령 cwd 의 git 최상위, git 이 아니면 프로젝트 폴더) 안에서
    - 명령에 든 경로의 지금 내용(없으면 null)
    - git 이면 HEAD, `git status --porcelain -uall` 에 나온 파일의 (mtime, 크기), 그중 검사 대상 확장자 파일의 지금 내용
    을 $TMPDIR/claude-conventions/bash/<session>.<main|agent>.<tool_use_id>.json 에 적는다. 내용은 파일당 TEXT_MAX,
    모두 합쳐 TOTAL_MAX 까지만 적는다(그보다 큰 dirty 파일은 바뀌어도 보지 않는다).
  PostToolUse(Bash): 이 파일을 스크립트로 돌린다. 스냅숏이 없으면(쓰기 신호 없음) 바로 끝난다. 있으면 바뀐 파일과 그 전 내용을 정한다:
    - 내용을 적어 둔 파일: 지금 내용과 다르면 바뀜, 전 내용은 적어 둔 것(없던 파일은 빈 글)
    - 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일: 전 내용은 명령 전 HEAD 의 blob(새 untracked 파일은 빈 글)
    - 명령이 커밋까지 했으면(HEAD 가 바뀜) 두 HEAD 사이에 바뀐 파일도 같은 식
    추가 줄 = 지금 줄 중 전 내용에 없던 줄(conv_edit.added_set, Write 덮어쓰기와 같은 셈). 그 줄에 conventions-check 의 file_notice 를
    그대로 돌린다(같은 알림 글, 같은 상태 파일이라 중복 거르기도 Edit 경로와 함께 간다). 코드 파일은 reuse-check 를 Write 꼴 입력으로 따로
    돌려 사본 표시 알림을 합친다. 바뀐 파일에 맞는 이 플러그인의 rules 중 이 맥락에 아직 안 넣은 것을 rules_inject 의 함수와 마커로 넣는다.
  worktree 를 통째로 바꾸는 git 하위 명령(checkout, stash, reset 등)이 같은 명령에 있으면 porcelain 비교는 하지 않고 명령에 든 경로만 본다.
    되돌린 줄을 새로 쓴 줄로 오인하지 않으려는 것이다.

제외: 저장소 밖, conventions-check 의 제외(SKIP_PARTS, 생성 파일, 설정 exclude), 확장자 표 밖. 알림을 낸 파일 NOTICE_FILES_MAX 개,
  분석 BUDGET_S 초에서 끊고 남은 파일은 conventions-scan 명령으로 안내한다.
실패는 조용히 통과한다. 끄기: CONVENTIONS_CHECK=off(검사와 사본), HARNESS_CONVENTIONS_RULES=off(rules).
"""
import hashlib
import json
import os
import re
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
STALE_S = 6 * 3600
GIT_TIMEOUT_S = 3
BUDGET_S = 2.5
NOTICE_FILES_MAX = 10
REUSE_MAX = 4
OUTPUT_BUDGET = 9000  # 훅 출력 하나가 10,000자를 넘으면 잘리므로 rules_inject 시험과 같은 여유를 둔다
CHECK_EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro", ".rs", ".py", ".go", ".kt", ".sh", ".html", ".htm", ".md"}
GIT_REWRITE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?(?:checkout|switch|stash|reset|merge|rebase|pull|cherry-pick|revert|restore|am)\b")
SCAN = os.path.join(os.path.dirname(HERE), "scripts", "conventions-scan.py")


def _clean(v):
    return re.sub(r"[^\w-]", "", str(v or ""))


def snap_path(data):
    """스냅숏 파일 경로. tool_use_id 가 없으면 명령 글의 해시로 Pre 와 Post 를 잇는다."""
    tid = _clean(data.get("tool_use_id"))
    if not tid:
        cmd = (data.get("tool_input") or {}).get("command") or ""
        tid = "c" + hashlib.sha1(cmd.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    name = "%s.%s.%s.json" % (_clean(data.get("session_id")) or "nosession", _clean(data.get("agent_id")) or "main", tid)
    return os.path.join(tempfile.gettempdir(), NS, "bash", name)


def _inside(path, root):
    return os.path.normpath(path).startswith(os.path.normpath(root).rstrip("/") + "/")


def _read(path, cap):
    """파일 글. 없으면 None, 크거나 글이 아니면 False."""
    try:
        if os.path.getsize(path) > cap:
            return False
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return False


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
    """{저장소 기준 경로: XY}. 실패하면 None."""
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
        res[e[3:]] = e[:2]
    return res


def _stat(path):
    try:
        st = os.stat(path)
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return None


def _sweep(d):
    """Post 가 오지 않은(거절, 중단) 스냅숏을 지운다."""
    now = time.time()
    try:
        for n in os.listdir(d):
            p = os.path.join(d, n)
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
    texts, total = {}, 0
    for p in dict.fromkeys(candidates):
        if _inside(p, root):
            t = _read(p, CANDIDATE_MAX)
            texts[p] = t
            total += len(t) if isinstance(t, str) else 0
    wide = is_git and not GIT_REWRITE.search(cmd)
    st = porcelain(root) if wide else None
    dirty = {}
    for rel in list(st or {})[:DIRTY_MAX]:
        ap = os.path.join(root, rel)
        dirty[rel] = _stat(ap)
        if ap in texts or os.path.splitext(rel)[1].lower() not in CHECK_EXT or total >= TOTAL_MAX:
            continue
        t = _read(ap, TEXT_MAX)
        if isinstance(t, str) and total + len(t) <= TOTAL_MAX:
            texts[ap] = t
            total += len(t)
    if not texts and st is None:
        return
    fp = snap_path(data)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    _sweep(os.path.dirname(fp))
    snap = {"root": root, "head": head, "wide": st is not None, "dirty": dirty, "texts": texts, "overflow": len(st or {}) > DIRTY_MAX}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)


def blobs(root, head, rels):
    """{경로: head 에서의 글}. head 에 없는 경로는 빈 글이다."""
    out = {r: "" for r in rels}
    if not head or not rels:
        return out
    raw = _git(root, "cat-file", "--batch", stdin="".join("%s:%s\n" % (head, r) for r in rels).encode("utf-8", "surrogateescape"))
    if raw is None:
        return None
    pos = 0
    for r in rels:
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


def changes(snap):
    """(검사할 [(절대 경로, 전 글, 지금 글)], 바뀐 모든 절대 경로). 전 글을 모르는 파일은 앞 목록에서 빠진다."""
    root, head = snap["root"], snap.get("head")
    texts, dirty = snap.get("texts") or {}, snap.get("dirty") or {}
    out, touched = {}, []
    for ap, before in texts.items():
        now = _read(ap, CANDIDATE_MAX)
        if now is None or now == before:
            continue
        touched.append(ap)
        if isinstance(now, str) and before is not False:
            out[ap] = (before or "", now)
    if not snap.get("wide"):
        return [(ap, b, n) for ap, (b, n) in out.items()], touched

    # Clean before the command, changed now
    st = porcelain(root) or {}
    need = []
    for rel, xy in st.items():
        ap = os.path.join(root, rel)
        if ap in texts:
            continue
        if rel in dirty:
            if dirty[rel] != _stat(ap):
                touched.append(ap)  # 전 글을 적어 두지 못한 dirty 파일: rules 만 넣는다
            continue
        if "D" in xy:
            continue
        touched.append(ap)
        if os.path.splitext(rel)[1].lower() not in CHECK_EXT:
            continue
        if xy == "??":
            now = _read(ap, CANDIDATE_MAX)
            if isinstance(now, str):
                out[ap] = ("", now)
        else:
            need.append(rel)

    # The command committed: files between the two HEADs
    now_head = _git(root, "rev-parse", "-q", "--verify", "HEAD")
    now_head = now_head.decode().strip() if now_head else None
    if head and now_head and now_head != head:
        names = (_git(root, "diff", "--name-only", "-z", head, now_head) or b"").decode("utf-8", "surrogateescape").split("\0")
        for rel in names:
            ap = os.path.join(root, rel)
            if rel and ap not in texts and rel not in dirty and rel not in need and os.path.exists(ap):
                touched.append(ap)
                if os.path.splitext(rel)[1].lower() in CHECK_EXT:
                    need.append(rel)
    old = blobs(root, head, need) or {}
    for rel in need:
        ap = os.path.join(root, rel)
        now = _read(ap, CANDIDATE_MAX)
        if rel in old and isinstance(now, str):
            out[ap] = (old[rel], now)
    return [(ap, b, n) for ap, (b, n) in sorted(out.items())], list(dict.fromkeys(touched))


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
            p = subprocess.Popen([sys.executable, "-I", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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


def main():
    t0 = time.monotonic()
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
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
    items, touched = changes(snap)
    if not touched:
        return 0
    check = (os.environ.get("CONVENTIONS_CHECK") or "").lower() != "off"

    # Added-line checks with the Edit path's state
    body, left, code = [], [], []
    if check and items:
        cc = _load_check()
        from conv_edit import added_set
        state_path = cc.state_file(data.get("session_id"), data.get("agent_id"))
        state = cc.load_state(state_path)
        dirty = False
        noticed = 0
        tails = []
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
            parts, changed = cc.file_notice(data, ap, rel, kind, ext, cfg, now, added_set(before, now, 0), state, tail=False)
            dirty = dirty or changed
            if parts:
                noticed += 1
                body.extend(parts)
                tails.append(cc.COMMENT_TAIL if kind == "comment" else cc.DOC_TAIL)
            if kind == "comment":
                code.append((ap, before, now))
        if dirty:
            cc.save_state(state_path, state)
        body.extend(dict.fromkeys(tails))  # 대응 문장은 종류마다 한 번
        if left:
            shown = " ".join(os.path.relpath(p, snap["root"]) for p in left[:6]) + (" ..." if len(left) > 6 else "")
            body.append(f"This command changed more files than the hook checks at once; check the rest with "
                        f"`python3 -I {SCAN} scan {shown}` and fix what it lists in lines you added.")
        body.extend(reuse_notes(data, code))

    # Notice first, then rules in the room left
    out = cc.notice_tag(data, body) if body else ""
    rules = rules_block(data, touched, OUTPUT_BUDGET - len(out) - 1)
    ctx = "\n".join(x for x in (out, rules) if x)
    if ctx:
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
