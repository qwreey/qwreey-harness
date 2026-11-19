#!/usr/bin/env python3
"""PreToolUse, PostToolUse, PostToolUseFailure(Bash): 디스크 여유 공간과 명령이 남긴 core dump 를 알린다.

왜: 이 기계는 core_pattern 이 `core` 라 크래시마다 그 프로세스의 cwd 에 core.<pid>(luau-lsp 는 1.4 GiB)가 쌓였고,
디스크는 모든 세션이 같이 쓴다. 명령이 돌 때마다 앞뒤로 재면 비용은 statvfs 몇 번이라(경로 셋에 약 16 us) 상주 프로세스가 필요 없다.

디스크(PROC_GUARD_DISK):
  명령 전후로 훅 cwd 와 임시 디렉터리의 파일 시스템(st_dev 로 중복 제거)을 잰다. 여유가 PROC_GUARD_DISK_MIN_FREE_GIB 또는
  전체의 PROC_GUARD_DISK_MIN_FREE_PCT % 아래면 warn. 전후 차이가 PROC_GUARD_DISK_DROP_GIB 를 넘으면 warn.
  같은 파일 시스템의 같은 종류 경고는 세션에 한 번, 그 뒤에는 DROP_GIB 만큼 더 나빠졌을 때만 다시 낸다.
core dump(PROC_GUARD_CORE, Linux 만):
  명령 뒤에 Pre 시각 이후 생긴 core 파일을 찾는다. 이름이 core_pattern 꼴(또는 core, core.<숫자>)이고, 일반 파일이고, 내 uid 이고,
  ELF 헤더의 e_type 이 ET_CORE 인 것만 센다(src/core 같은 폴더나 다른 파일은 걸리지 않는다).
  늘 보는 곳은 cwd 맨 위(그리고 core_pattern 이 절대 경로면 그 폴더). 출력에 크래시 흔적(core dumped, SIGSEGV 꼴, 종료 코드 128+신호)이
  있을 때만 cwd 아래를 깊이 4, 200 ms 안에서 넓게 훑는다. core_pattern 이 `|` 로 시작하면(systemd-coredump, apport) 파일을 찾지 않고
  크래시가 보였을 때 덤프가 처리기로 갔다고만 알린다.

명령을 막지 않는다. 어떤 예외든 아무것도 내지 않고 exit 0. 하위 프로세스를 띄우지 않는다.
상태: ${CLAUDE_PLUGIN_DATA}/resource-guard/(없으면 임시 디렉터리 아래). Pre 측정은 tool_use_id 마다 파일 하나(Post 가 읽고 지운다),
세션마다 경고 기록 파일 하나. 하루 지난 Pre 파일과 일주일 지난 세션 파일은 Pre 가 지운다.
"""
import hashlib
import json
import os
import re
import struct
import sys
import tempfile
import time

TAG = "resource-guard"
GIB = 1 << 30
# 이 훅만 읽는 harness.env 키. userConfig 키는 이 이름의 소문자다(true/false 는 on/off 로 들어온다).
ENV_DEFAULTS = {
    "PROC_GUARD_CORE": "on",
    "PROC_GUARD_DISK": "on",
    "PROC_GUARD_DISK_MIN_FREE_GIB": "10",
    "PROC_GUARD_DISK_MIN_FREE_PCT": "5",
    "PROC_GUARD_DISK_DROP_GIB": "2",
}
# 기계 전체를 지키는 안전망이라 켜고 끄기는 사용자 몫이다: 클론한 저장소가 커밋한 harness.env 로 끄지 못하게 한다.
# 문턱은 저장소 층도 정하지만 더 엄하게만 바꾼다(thresholds() 참고). 풀 수 있으면 0 으로 스위치를 우회할 수 있기 때문이다.
ENV_USER_ONLY = frozenset({"PROC_GUARD_CORE", "PROC_GUARD_DISK"})
ON_VALUES = {"on", "1", "true", "yes"}

CRASH_SIGNALS = {3: "SIGQUIT", 4: "SIGILL", 5: "SIGTRAP", 6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 11: "SIGSEGV", 31: "SIGSYS"}
CRASH_TEXT = re.compile(
    r"core dumped|Segmentation fault|Bus error|Illegal instruction|Floating point exception"
    r"|\bSIG(?:SEGV|ABRT|BUS|FPE|ILL|QUIT|TRAP|SYS)\b|signal: (?:3|4|5|6|7|8|11|31)\b")
EXIT_CODE = re.compile(r"\AExit code (\d+)")
OUTPUT_TAIL = 65536
WALK_DEPTH = 4
WALK_BUDGET_SEC = 0.2
WALK_SKIP = {"node_modules", "__pycache__"}
# 파일 시스템 시각 단위가 거친 곳(초 단위)에서 Pre 직후 생긴 덤프를 놓치지 않게 둔 여유.
MTIME_SLACK_SEC = 2
PRE_TTL_SEC = 86400
SESSION_TTL_SEC = 7 * 86400
REPORTED_KEEP = 50


def load_env(cwd=None, repo=True):
    """harness.env 층(옆의 harness_env.py 사본). repo=False 면 저장소 층 없이. 깨졌으면 {}."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import harness_env
        project = harness_env.project_dir(cwd) if repo else ""
        return harness_env.load_layers(project, defaults=ENV_DEFAULTS, user_only=ENV_USER_ONLY)
    except Exception:
        return {}


def switch(env, key):
    return (env.get(key, ENV_DEFAULTS[key]) or "").strip().lower() in ON_VALUES


def number(env, key):
    try:
        return max(0.0, float(env.get(key, ENV_DEFAULTS[key])))
    except (TypeError, ValueError):
        return float(ENV_DEFAULTS[key])


def thresholds(env, user_env):
    """(최소 여유 GiB, 최소 여유 %, 급감 GiB). 저장소 층은 사용자 값보다 엄하게만 바꾼다. 0 은 그 검사를 끈다."""
    min_gib = max(number(env, "PROC_GUARD_DISK_MIN_FREE_GIB"), number(user_env, "PROC_GUARD_DISK_MIN_FREE_GIB"))
    min_pct = max(number(env, "PROC_GUARD_DISK_MIN_FREE_PCT"), number(user_env, "PROC_GUARD_DISK_MIN_FREE_PCT"))
    drops = [v for v in (number(env, "PROC_GUARD_DISK_DROP_GIB"), number(user_env, "PROC_GUARD_DISK_DROP_GIB")) if v > 0]
    return min_gib, min_pct, (min(drops) if drops else 0.0)


def disk_usage(path):
    """(여유 바이트, 전체 바이트). 여유는 권한 없는 사용자가 쓸 수 있는 양이다. 시험이 이 함수를 바꿔 낀다."""
    if hasattr(os, "statvfs"):
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize
    import shutil  # statvfs 가 없는 Windows 에서만. import 에 수 ms 가 든다
    du = shutil.disk_usage(path)
    return du.free, du.total


def mount_point(path, dev):
    """path 가 든 파일 시스템의 맨 위 디렉터리. Windows 는 드라이브 루트."""
    if os.name == "nt":
        drive = os.path.splitdrive(path)[0]
        return drive + "\\" if drive else path
    cur = path
    while True:
        up = os.path.dirname(cur)
        if up == cur:
            return cur
        try:
            if os.stat(up).st_dev != dev:
                return cur
        except OSError:
            return cur
        cur = up


def measure(paths):
    """{st_dev 문자열: {"mount", "free", "total"}}: paths 의 파일 시스템마다 한 번."""
    out = {}
    for p in paths:
        if not p:
            continue
        try:
            p = os.path.realpath(p)
            dev = str(os.stat(p).st_dev)
            if dev in out:
                continue
            free, total = disk_usage(p)
        except OSError:
            continue
        out[dev] = {"mount": mount_point(p, int(dev)), "free": free, "total": total}
    return out


def gib(n):
    return "%.1f" % (n / GIB)


def disk_findings(now, before, limits, state, when):
    """경고 줄 목록과 종류(low, drop). state["disk"] 에 경고한 값을 적어 같은 경고를 되풀이하지 않는다."""
    min_gib, min_pct, drop_gib = limits
    step = max(drop_gib, 0.5) * GIB
    seen = state.setdefault("disk", {})
    lines, kinds = [], set()
    for dev, m in now.items():
        rec = seen.setdefault(dev, {})
        free, total = m["free"], m["total"]
        pct = 100.0 * free / total if total else 100.0

        # Low free space
        low = (min_gib > 0 and free < min_gib * GIB) or (min_pct > 0 and pct < min_pct)
        if not low:
            rec.pop("low", None)  # 회복했다가 다시 떨어지면 다시 알린다
        elif "low" not in rec or free <= rec["low"] - step:
            rec["low"] = free
            kinds.add("low")
            lines.append("Low disk space %s: %s has %s GiB free (%.1f%% of %s GiB; the warning starts below %g GiB or %g%%)."
                         % (when, m["mount"], gib(free), pct, gib(total), min_gib, min_pct))

        # Drop during this command
        prev = (before or {}).get(dev)
        drop = prev["free"] - free if prev else 0
        if drop_gib > 0 and drop > drop_gib * GIB and ("drop" not in rec or drop >= rec["drop"] + step):
            rec["drop"] = drop
            kinds.add("drop")
            lines.append("Free space on %s fell by %s GiB while this command ran (now %s GiB free)." % (m["mount"], gib(drop), gib(free)))
        if not rec:
            del seen[dev]
    if not seen:
        state.pop("disk", None)
    return lines, kinds


def disk_advice(kinds):
    advice = ["Tell the user in one line: the mount and its free GiB."]
    if "drop" in kinds:
        advice.append("If the drop came from this command, also say what used the space (check the directories it wrote, "
                      "e.g. `du -sh <dir>`); other sessions share this disk, so it may not be this command.")
    if "low" in kinds:
        advice.append("A full disk breaks builds and every session on this machine. If this session made large files it no longer "
                      "needs (build output, temp data, core dumps), consider removing them; ask before deleting anything else.")
    return " ".join(advice)


def read_core_pattern():
    """(core_pattern, core_uses_pid) 또는 None(Linux 가 아니거나 /proc 이 없다). 시험이 이 함수를 바꿔 낀다."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        with open("/proc/sys/kernel/core_pattern", encoding="utf-8", errors="replace") as f:
            pattern = f.read().strip()
    except OSError:
        return None
    try:
        with open("/proc/sys/kernel/core_uses_pid", encoding="utf-8") as f:
            uses_pid = f.read().strip() == "1"
    except OSError:
        uses_pid = False
    return pattern, uses_pid


SPEC_DIGITS = set("pPiIsStugcd")
SPEC_TEXT = set("eEhf")


def name_regex(template, uses_pid):
    """core_pattern 의 파일 이름 부분을 정규식으로. %p 같은 지정자는 숫자, %e 같은 것은 아무 글자로 본다."""
    out, i, has_pid = [], 0, False

    # Translate specifiers and literal text
    while i < len(template):
        c = template[i]
        if c == "%" and i + 1 < len(template):
            spec = template[i + 1]
            has_pid = has_pid or spec in "pP"
            out.append("%" if spec == "%" else r"\d+" if spec in SPEC_DIGITS else ".+" if spec in SPEC_TEXT else "")
            i += 2
            continue
        out.append(re.escape(c))
        i += 1

    body = "".join(out)
    if uses_pid and not has_pid:
        body += r"(?:\.\d+)?"  # core_uses_pid=1 이면 커널이 .PID 를 붙인다
    return re.compile(r"\A(?:%s|core(?:\.\d+)?)\Z" % body)


def core_info(path):
    """ELF core 이면 {"program", "args", "signal"}(읽지 못한 칸은 빈 문자열), 아니면 None."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
            if len(head) < 52 or head[:4] != b"\x7fELF" or head[5] not in (1, 2):
                return None
            end = "<" if head[5] == 1 else ">"
            if struct.unpack_from(end + "H", head, 16)[0] != 4:  # e_type ET_CORE
                return None

            # Optional details, 64-bit only
            info = {"program": "", "args": "", "signal": ""}
            if head[4] == 2 and len(head) == 64:
                try:
                    note_fields(f, head, end, info)
                except (OSError, struct.error, ValueError):
                    pass
            return info
    except OSError:
        return None


def note_fields(f, head, end, info):
    """64비트 core 의 PT_NOTE 에서 NT_PRSTATUS 의 신호와 NT_PRPSINFO 의 프로그램 이름, 인자를 읽는다."""
    phoff = struct.unpack_from(end + "Q", head, 32)[0]
    phentsize, phnum = struct.unpack_from(end + "HH", head, 54)
    if phentsize < 56:
        return

    # Find the first PT_NOTE among the first program headers
    f.seek(phoff)
    table = f.read(phentsize * min(phnum, 16))
    for k in range(len(table) // phentsize):
        p_type, _, p_offset = struct.unpack_from(end + "IIQ", table, k * phentsize)
        if p_type != 4:  # PT_NOTE
            continue
        p_filesz = struct.unpack_from(end + "Q", table, k * phentsize + 32)[0]
        f.seek(p_offset)
        notes = f.read(min(p_filesz, 65536))

        # Walk the notes until both fields are known
        pos = 0
        while pos + 12 <= len(notes):
            namesz, descsz, n_type = struct.unpack_from(end + "III", notes, pos)
            desc = pos + 12 + ((namesz + 3) & ~3)
            body = notes[desc:desc + descsz]
            if n_type == 1 and len(body) >= 14 and not info["signal"]:  # NT_PRSTATUS: pr_cursig
                sig = struct.unpack_from(end + "h", body, 12)[0]
                info["signal"] = CRASH_SIGNALS.get(sig, "signal %d" % sig if sig else "")
            elif n_type == 3 and descsz == 136:  # NT_PRPSINFO(x86_64, aarch64): pr_fname[16] at 40, pr_psargs[80] at 56
                info["program"] = body[40:56].split(b"\0")[0].decode("utf-8", "replace")
                info["args"] = body[56:136].split(b"\0")[0].decode("utf-8", "replace").strip()
            if info["program"] and info["signal"]:
                return
            pos = desc + ((descsz + 3) & ~3)
        return


def crash_evidence(data):
    """명령이 크래시한 흔적을 짧은 글로, 없으면 ''. 종료 코드는 PostToolUseFailure 의 error 첫 줄에서 읽는다."""
    if data.get("hook_event_name") == "PostToolUseFailure":
        text = data.get("error") if isinstance(data.get("error"), str) else ""
    else:
        resp = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
        text = "\n".join(v for v in (resp.get("stdout"), resp.get("stderr")) if isinstance(v, str))
    m = EXIT_CODE.match(text)
    if m and int(m.group(1)) - 128 in CRASH_SIGNALS:
        code = int(m.group(1))
        return "exit code %d, %s" % (code, CRASH_SIGNALS[code - 128])
    hit = CRASH_TEXT.search(text[-OUTPUT_TAIL:])
    return "output says `%s`" % hit.group(0) if hit else ""


def candidates(directory, names, since, uid):
    """directory 맨 위에서 이름이 맞고, 일반 파일이고, since 뒤에 바뀐 파일 [(경로, stat)]."""
    out = []
    try:
        with os.scandir(directory) as it:
            for e in it:
                if not names.match(e.name):
                    continue

                # Regular files only, never through a symlink
                try:
                    if not e.is_file(follow_symlinks=False):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue

                if st.st_mtime >= since and (uid is None or st.st_uid == uid):
                    out.append((e.path, st))
    except OSError:
        pass
    return out


def walk_dirs(root):
    """root 아래 디렉터리를 얕은 것부터(깊이 WALK_DEPTH, 숨은 폴더와 node_modules 는 건너뜀, 시간 WALK_BUDGET_SEC 안)."""
    deadline = time.monotonic() + WALK_BUDGET_SEC
    level = [root]
    for _ in range(WALK_DEPTH):

        # Collect the next level, stopping at the deadline
        nxt = []
        for d in level:
            if time.monotonic() > deadline:
                return
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.name.startswith(".") or e.name in WALK_SKIP:
                            continue
                        try:
                            if e.is_dir(follow_symlinks=False):
                                nxt.append(e.path)
                        except OSError:
                            continue
            except OSError:
                continue

        for d in nxt:
            yield d
        level = nxt


def find_cores(roots, pattern, uses_pid, since, wide):
    """since 뒤에 생긴 ELF core [(경로, 크기, info)]. core_pattern 이 절대 경로면 그 폴더도 본다."""
    uid = os.getuid() if hasattr(os, "getuid") else None
    dirs = []
    if pattern.startswith("/"):
        where, template = os.path.split(pattern)
        if "%" not in where:
            dirs.append(where)
    else:
        template = os.path.basename(pattern)
    names = name_regex(template or "core", uses_pid)
    for r in roots:
        if r and r not in dirs:
            dirs.append(r)
    if wide:
        for r in roots:
            dirs.extend(d for d in walk_dirs(r) if d not in dirs)

    found, seen = [], set()
    for d in dirs:
        for path, st in candidates(d, names, since, uid):
            if path in seen:
                continue
            seen.add(path)
            info = core_info(path)
            if info is not None:
                found.append((path, st, info))
    return found


def size_text(n):
    return "%s GiB" % gib(n) if n >= GIB else "%.1f MiB" % (n / (1 << 20)) if n >= 1 << 20 else "%d KiB" % max(1, n // 1024)


def core_message(found):
    lines = ["Core dump file(s) appeared while this command ran:"]
    for path, st, info in found:
        what = [size_text(st.st_size)]
        if info["program"]:
            what.append("from `%s`" % (info["args"] or info["program"]))
        if info["signal"]:
            what.append(info["signal"])
        lines.append("- `%s` (%s)" % (path, ", ".join(what)))
    lines.append("If the crash was intended (a repro, a crash test) or the dump is not needed, delete these files now. "
                 "If it may be needed for debugging, keep it and tell the user the path and size. "
                 "Delete only dumps this command created: if the program does not fit this command (another session may share "
                 "the directory), leave it and mention it.")
    return "\n".join(lines)


def handler_message(pattern, evidence):
    handler = pattern[1:].strip().split()[0] if pattern[1:].strip() else "?"
    return ("This command seems to have crashed (%s), and core_pattern sends core dumps to a handler (`%s`), not to a file here. "
            "If the dump may be needed for debugging, tell the user where to find it (`coredumpctl list` for systemd-coredump, "
            "/var/crash for apport); there is no file here to clean up." % (evidence, os.path.basename(handler)))


def state_dir():
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(tempfile.gettempdir(), "claude-qwreey-proc-guard")
    return os.path.join(base, "resource-guard")


def session_key(data):
    return hashlib.sha256(str(data.get("session_id") or "none").encode()).hexdigest()[:16]


def pre_path(data):
    tid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("tool_use_id") or ""))[:80]
    return os.path.join(state_dir(), "pre", "%s-%s.json" % (session_key(data), tid)) if tid else None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f)
        os.replace(tmp, path)
    except OSError:
        pass


def prune(directory, ttl, now):
    try:
        with os.scandir(directory) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False) and now - e.stat().st_mtime > ttl:
                        os.unlink(e.path)
                except OSError:
                    continue
    except OSError:
        pass


def handle(data):
    """hookSpecificOutput 의 additionalContext 글, 낼 것이 없으면 ''."""
    if not isinstance(data, dict) or data.get("tool_name") not in (None, "Bash"):
        return ""
    event = data.get("hook_event_name")
    if event not in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        return ""
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    env = load_env(cwd)
    disk_on, core_on = switch(env, "PROC_GUARD_DISK"), switch(env, "PROC_GUARD_CORE")
    if not (disk_on or core_on):
        return ""

    # Measure and load this session's warning record
    limits = thresholds(env, load_env(cwd, repo=False))
    now = time.time()
    spath = os.path.join(state_dir(), "s-%s.json" % session_key(data))
    state = read_json(spath)
    loaded = json.dumps(state, sort_keys=True)
    disk = measure([cwd, tempfile.gettempdir()]) if disk_on else {}
    pp = pre_path(data)
    warn, action, info = [], [], []

    # Before: keep the reading for the post event
    if event == "PreToolUse":
        if pp:
            write_json(pp, {"t": now, "cwd": cwd, "disk": disk})
            prune(os.path.dirname(pp), PRE_TTL_SEC, now)
            prune(state_dir(), SESSION_TTL_SEC, now)
        before = None
        when = "before this command"

    # After: compare with the reading, then look for dumps
    else:
        pre = read_json(pp) if pp else {}
        if pp:
            try:
                os.unlink(pp)
            except OSError:
                pass
        before = pre.get("disk")
        when = "after this command"
        if core_on:
            core_notes(data, pre, cwd, now, state, action, info)

    lines, kinds = disk_findings(disk, before, limits, state, when)
    if lines:
        warn = lines + [disk_advice(kinds)]
    if json.dumps(state, sort_keys=True) != loaded:
        write_json(spath, state)
    if not (warn or action or info):
        return ""

    # One tag per level
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
    import harness_nonce
    nonce = harness_nonce.attr(data.get("session_id"))
    tags = ['<harness-hook name="%s" level="%s"%s>\n%s\n</harness-hook>' % (TAG, lv, nonce, "\n".join(body))
            for lv, body in (("action", action), ("warn", warn), ("info", info)) if body]
    return "\n".join(tags)


def core_notes(data, pre, cwd, now, state, action, info):
    """Pre 이후 생긴 core 파일(action)이나 처리기로 간 덤프(info)를 알린다."""
    cp = read_core_pattern()
    if cp is None:
        return
    pattern, uses_pid = cp
    since = pre.get("t")
    if not isinstance(since, (int, float)):
        dur = data.get("duration_ms")
        if not isinstance(dur, (int, float)):
            return
        since = now - dur / 1000.0
    evidence = crash_evidence(data)

    if pattern.startswith("|"):
        if evidence:
            info.append(handler_message(pattern, evidence))
        return

    roots = [cwd] + ([pre["cwd"]] if isinstance(pre.get("cwd"), str) and pre["cwd"] != cwd else [])
    reported = list(state.get("cores") or [])
    found = []
    for path, st, ci in find_cores(roots, pattern, uses_pid, since - MTIME_SLACK_SEC, bool(evidence)):
        key = "%s:%d" % (path, st.st_mtime_ns)
        if key not in reported:
            reported.append(key)
            found.append((path, st, ci))
    if found:
        state["cores"] = reported[-REPORTED_KEEP:]  # 겹쳐 돈 다른 명령의 Post 가 같은 파일을 다시 알리지 않게
        action.append(core_message(found))


def main():
    try:
        data = json.load(sys.stdin)
        text = handle(data)
        if text:
            json.dump({"hookSpecificOutput": {"hookEventName": data["hook_event_name"], "additionalContext": text}}, sys.stdout)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
