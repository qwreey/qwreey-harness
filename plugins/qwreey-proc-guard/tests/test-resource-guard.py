#!/usr/bin/env python3
"""resource-guard 회귀. 실행: python3 -I tests/test-resource-guard.py  (exit 0 = 통과)

훅 모듈을 이 프로세스에 적재해 disk_usage 와 read_core_pattern 을 바꿔 끼우고 handle() 을 부른다. 끝의 두 묶음만 하위 프로세스로
돌려(깨진 입력, 실제 core_pattern 으로 Pre -> Post) 설치된 훅처럼 본다. 모든 파일은 임시 폴더 안에 만든다: 이 기계의 기존 core
파일은 건드리지 않는다.
"""
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(os.path.dirname(HERE), "hooks")
HOOK = os.path.join(HOOKS, "resource-guard.py")
T = tempfile.mkdtemp(prefix="resource-guard-")
GIB = 1 << 30

# 사용자 설정, 저장소 층, 실제 salt 와 상태 폴더를 쓰지 않게 한다. salt "00"*32 + 세션 "abc" 의 nonce 는 39596342ed0e
for k in list(os.environ):
    if k.startswith(("PROC_GUARD_", "HARNESS_", "CLAUDE_")):
        del os.environ[k]
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(T, "cfg")
os.makedirs(os.environ["CLAUDE_CONFIG_DIR"])
os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(T, "data")

sys.path.insert(0, HOOKS)
spec = importlib.util.spec_from_file_location("resource_guard", HOOK)
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)

FAKE = {"free": 500 * GIB, "total": 1000 * GIB}
rg.disk_usage = lambda path: (FAKE["free"], FAKE["total"])
PATTERN = {"value": ("core", True)}
rg.read_core_pattern = lambda: PATTERN["value"]

ok = fail = 0


def check(name, cond):
    """통과를 세거나 실패한 경우를 찍는다."""
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name)


def new_dir(name):
    """임시 루트 아래 새 폴더를 만든다."""
    d = os.path.join(T, name)
    os.makedirs(d)
    return d


def event(kind, sid, tid, cwd, **extra):
    """Bash 훅 이벤트로 handle() 을 불러 알림 글을 돌려준다."""
    data = {"session_id": sid, "hook_event_name": kind, "tool_name": "Bash", "tool_input": {"command": "./run"},
            "tool_use_id": tid, "cwd": cwd}
    if kind == "PostToolUse":
        data["tool_response"] = {"stdout": extra.pop("stdout", ""), "stderr": extra.pop("stderr", ""), "interrupted": False}
    data.update(extra)
    return rg.handle(data)


def free(n_gib, total_gib=1000):
    """가짜 disk_usage 가 낼 값을 정한다."""
    FAKE["free"], FAKE["total"] = int(n_gib * GIB), int(total_gib * GIB)


def elf_core(path, e_type=4, program=b"crashy", args=b"./crashy --boom", sig=11, mtime=None):
    """64비트 리틀 엔디언 ELF core 헤더, PT_NOTE 하나, 그 안에 NT_PRSTATUS(pr_cursig) 와 NT_PRPSINFO."""
    prstatus = bytearray(336)
    struct.pack_into("<h", prstatus, 12, sig)
    prpsinfo = bytearray(136)
    prpsinfo[40:40 + len(program)] = program
    prpsinfo[56:56 + len(args)] = args
    notes = b""
    for n_type, desc in ((1, bytes(prstatus)), (3, bytes(prpsinfo))):
        notes += struct.pack("<III", 5, len(desc), n_type) + b"CORE\0\0\0\0" + desc

    head = bytearray(64)
    head[:6] = b"\x7fELF\x02\x01"
    head[6] = 1
    struct.pack_into("<HHI", head, 16, e_type, 62, 1)
    struct.pack_into("<Q", head, 32, 64)  # e_phoff
    struct.pack_into("<HHH", head, 52, 64, 56, 1)  # e_ehsize, e_phentsize, e_phnum
    phdr = struct.pack("<IIQQQQQQ", 4, 0, 64 + 56, 0, 0, len(notes), 0, 4)

    with open(path, "wb") as f:
        f.write(bytes(head) + phdr + notes + b"\0" * 4096)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def level(text, lv):
    """출력에 이 level 의 태그가 있으면 True."""
    return ('level="%s"' % lv) in (text or "")


# 낮은 여유 공간
cwd = new_dir("disk")
free(3, 100)
out = event("PreToolUse", "abc", "d1", cwd)
check("low free warns before the command", level(out, "warn") and "Low disk space before this command" in out and "3.0 GiB free" in out)
check("tag carries the session nonce", out.startswith('<harness-hook name="resource-guard" level="warn" nonce="39596342ed0e">\n'))
check("low warning tells the model to tell the user", "Tell the user in one line" in out)
check("pre event never writes a core action", not level(out, "action"))

# 한 세션에 한 번, 단계만큼 나빠지면 다시
check("same low warning stays quiet", event("PreToolUse", "abc", "d2", cwd) == "")
free(2, 100)
check("slightly worse stays quiet", event("PostToolUse", "abc", "d2", cwd) == "")
free(0.9, 100)
check("a step worse warns again", "0.9 GiB free" in event("PreToolUse", "abc", "d3", cwd))
free(50, 100)
check("recovered is quiet", event("PreToolUse", "abc", "d4", cwd) == "")
free(3, 100)
check("falling again after recovery warns", level(event("PreToolUse", "abc", "d5", cwd), "warn"))
check("another session warns on its own", level(event("PreToolUse", "other", "d6", cwd), "warn"))

# 퍼센트 문턱
free(40, 1000)
out = event("PreToolUse", "pct", "p1", cwd)
check("below 5 percent warns even above 10 GiB", "(4.0% of 1000.0 GiB" in (out or ""))
free(60, 1000)
check("above both thresholds is quiet", event("PreToolUse", "pct2", "p2", cwd) == "")

# 명령 중 급감
free(50, 100)
check("drop pre is quiet", event("PreToolUse", "drop", "r1", cwd) == "")
free(47, 100)
out = event("PostToolUse", "drop", "r1", cwd)
check("a 3 GiB drop warns after the command", level(out, "warn") and "fell by 3.0 GiB" in out and "du -sh" in out)
check("drop alone has no low advice", "A full disk" not in out)
free(47, 100)
event("PreToolUse", "drop", "r2", cwd)
free(46, 100)
check("a 1 GiB drop is quiet", event("PostToolUse", "drop", "r2", cwd) == "")
free(46, 100)
event("PreToolUse", "drop", "r3", cwd)
free(43, 100)
check("the same size drop again is quiet", event("PostToolUseFailure", "drop", "r3", cwd, error="Exit code 1\n") == "")
free(43, 100)
event("PreToolUse", "drop", "r4", cwd)
free(37.5, 100)
check("a drop worse by a step warns again", "fell by 5.5 GiB" in (event("PostToolUse", "drop", "r4", cwd) or ""))
check("the pre reading file is removed after the post event",
      not os.path.exists(rg.pre_path({"session_id": "drop", "tool_use_id": "r4"})))

# 문턱 설정: 환경 변수는 사용자 값, 저장소 층은 더 엄하게만
free(3, 100)
os.environ["PROC_GUARD_DISK_MIN_FREE_GIB"] = "0"
os.environ["PROC_GUARD_DISK_MIN_FREE_PCT"] = "0"
check("zero thresholds turn the low check off", event("PreToolUse", "thr1", "t1", cwd) == "")
del os.environ["PROC_GUARD_DISK_MIN_FREE_GIB"], os.environ["PROC_GUARD_DISK_MIN_FREE_PCT"]
proj = new_dir("proj")
os.makedirs(os.path.join(proj, ".claude"))
with open(os.path.join(proj, ".claude", "harness.env"), "w") as f:
    f.write("PROC_GUARD_DISK_MIN_FREE_GIB=0\nPROC_GUARD_DISK_MIN_FREE_PCT=0\nPROC_GUARD_DISK=off\nPROC_GUARD_CORE=off\n")
check("a repo layer cannot loosen thresholds or switch the check off", level(event("PreToolUse", "thr2", "t2", proj), "warn"))
with open(os.path.join(proj, ".claude", "harness.env"), "w") as f:
    f.write("PROC_GUARD_DISK_MIN_FREE_GIB=60\n")
free(50, 100)
check("a repo layer can tighten a threshold", "warning starts below 60 GiB" in (event("PreToolUse", "thr3", "t3", proj) or ""))

# 스위치
free(3, 100)
os.environ["PROC_GUARD_DISK"] = "off"
check("PROC_GUARD_DISK=off silences disk warnings", event("PreToolUse", "sw1", "s1", cwd) == "")
os.environ["PROC_GUARD_DISK"] = "0"
check("PROC_GUARD_DISK=0 also means off", event("PreToolUse", "sw1b", "s1b", cwd) == "")
free(500)
del os.environ["PROC_GUARD_DISK"]

# core dump: 실제 ELF core 헤더를 cwd 맨 위에서
cw = new_dir("core-top")
check("pre with no dumps is quiet", event("PreToolUse", "c1", "k1", cw) == "")
elf_core(os.path.join(cw, "core.12345"))
out = event("PostToolUse", "c1", "k1", cw)
check("a new ELF core is an action", level(out, "action") and os.path.join(cw, "core.12345") in out)
check("core action names program, args and signal", "`./crashy --boom`" in out and "SIGSEGV" in out and "KiB" in out)
check("core action says delete if intended, keep and tell if needed",
      "delete these files now" in out and "tell the user the path and size" in out and "Delete only dumps this command created" in out)
event("PreToolUse", "c1", "k2", cw)
check("the same core is reported once per session", event("PostToolUse", "c1", "k2", cw) == "")

# core 가 아닌 것
cn = new_dir("core-not")
event("PreToolUse", "c2", "n1", cn)
os.makedirs(os.path.join(cn, "core"))
os.makedirs(os.path.join(cn, "src", "core"))
with open(os.path.join(cn, "core.777"), "w") as f:
    f.write("not an elf file\n")
elf_core(os.path.join(cn, "core.778"), e_type=2)  # ET_EXEC
elf_core(os.path.join(cn, "notcore.1"))
os.symlink(os.path.join(cw, "core.12345"), os.path.join(cn, "core.779"))
check("dirs, non-ELF, non-core ELF, other names and symlinks are ignored",
      event("PostToolUseFailure", "c2", "n1", cn, error="Exit code 139\nSegmentation fault (core dumped)") == "")

# Pre 전에 있던 core
co = new_dir("core-old")
elf_core(os.path.join(co, "core.1"), mtime=time.time() - 3600)
event("PreToolUse", "c3", "o1", co)
check("a core older than the command is ignored", event("PostToolUse", "c3", "o1", co) == "")

# 크래시 흔적이 있을 때만 하위 폴더까지
cs = new_dir("core-sub")
event("PreToolUse", "c4", "s1", cs)
os.makedirs(os.path.join(cs, "crates", "a", "tests"))
os.makedirs(os.path.join(cs, ".cache"))
elf_core(os.path.join(cs, "crates", "a", "core.4242"))
elf_core(os.path.join(cs, ".cache", "core.4243"))
check("without crash evidence the subdir is not walked", event("PostToolUse", "c4", "s1", cs) == "")
event("PreToolUse", "c4", "s2", cs)
out = event("PostToolUseFailure", "c4", "s2", cs, error="Exit code 139\n")
check("exit code 139 walks subdirs and finds the core", os.path.join(cs, "crates", "a", "core.4242") in (out or ""))
check("hidden dirs are skipped", ".cache" not in (out or ""))
cs2 = new_dir("core-sub2")
event("PreToolUse", "c5", "s3", cs2)
os.makedirs(os.path.join(cs2, "b"))
elf_core(os.path.join(cs2, "b", "core"))
out = event("PostToolUse", "c5", "s3", cs2, stderr="thread 'main' panicked\nprocess didn't exit successfully (signal: 11, SIGSEGV)")
check("SIGSEGV in the output walks subdirs", os.path.join(cs2, "b", "core") in (out or ""))

# Pre 기록이 없으면 duration_ms 로
cd = new_dir("core-dur")
elf_core(os.path.join(cd, "core.5"))
check("no pre record and no duration means no core check", event("PostToolUse", "c6", "x1", cd) == "")
check("duration_ms stands in for the pre record", level(event("PostToolUse", "c6", "x2", cd, duration_ms=5000), "action"))

# core_pattern: 처리기와 절대 경로
cp = new_dir("core-pipe")
PATTERN["value"] = ("|/usr/lib/systemd/systemd-coredump %P %u %g %s %t %c %h", False)
event("PreToolUse", "c7", "q1", cp)
elf_core(os.path.join(cp, "core"))
out = event("PostToolUseFailure", "c7", "q1", cp, error="Exit code 134\nAborted (core dumped)")
check("a pipe pattern says where the dump went", level(out, "info") and "systemd-coredump" in out and "coredumpctl list" in out
      and "SIGABRT" in out)
check("a pipe pattern does not scan files", not level(out, "action"))
event("PreToolUse", "c7", "q2", cp)
check("a pipe pattern without a crash is quiet", event("PostToolUse", "c7", "q2", cp) == "")
dumps = new_dir("dumps")
ca = new_dir("core-abs")
PATTERN["value"] = (os.path.join(dumps, "core.%e.%p"), False)
event("PreToolUse", "c8", "a1", ca)
elf_core(os.path.join(dumps, "core.crashy.99"))
check("an absolute pattern scans its directory", os.path.join(dumps, "core.crashy.99") in (event("PostToolUse", "c8", "a1", ca) or ""))
PATTERN["value"] = None
co2 = new_dir("core-nolinux")
event("PreToolUse", "c9", "l1", co2)
elf_core(os.path.join(co2, "core"))
check("without core_pattern (off Linux) core detection is skipped", event("PostToolUseFailure", "c9", "l1", co2, error="Exit code 139\n") == "")
PATTERN["value"] = ("core", True)

# 이름 꼴
r = rg.name_regex("core.%e.%p", False)
check("name regex: specifiers", bool(r.match("core.luau-lsp.123")) and r.match("core.txt.x") is None and r.match("src") is None)
r = rg.name_regex("%e.core", True)
check("name regex: uses_pid suffix and plain core", bool(r.match("prog.core.12")) and bool(r.match("core")) and bool(r.match("core.7")))
check("name regex: plain name does not match prefixes", rg.name_regex("core", True).match("core_test.py") is None)

# 스위치: core 끔, 둘 다 끔
cf = new_dir("core-off")
os.environ["PROC_GUARD_CORE"] = "off"
event("PreToolUse", "c10", "f1", cf)
elf_core(os.path.join(cf, "core.3"))
check("PROC_GUARD_CORE=off silences core notices", event("PostToolUseFailure", "c10", "f1", cf, error="Exit code 139\n") == "")
os.environ["PROC_GUARD_DISK"] = "off"
pre_dir = os.path.join(T, "data", "resource-guard", "pre")
before = set(os.listdir(pre_dir))
free(1, 100)
check("both off does nothing", event("PreToolUse", "c11", "f2", cf) == "")
check("both off writes no pre record", set(os.listdir(pre_dir)) == before)
del os.environ["PROC_GUARD_CORE"], os.environ["PROC_GUARD_DISK"]
free(500)


# 하위 프로세스: 깨진 입력은 조용히 exit 0
def run(raw, env=None):
    """훅을 하위 프로세스로 돌려 (종료 코드, stdout, stderr)."""
    e = dict(os.environ, **(env or {}))
    p = subprocess.run([sys.executable, "-I", "-X", "utf8", HOOK], input=raw, capture_output=True, text=True, timeout=20, env=e)
    return p.returncode, p.stdout, p.stderr


for raw in ["", "not json", "[]", "null", '{"hook_event_name": "PostToolUse"}', '{"hook_event_name": "PostToolUse", "cwd": 123}',
            '{"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/nonexistent/x", "tool_use_id": "../../x"}',
            '{"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": 5, "duration_ms": "x", "cwd": "/"}']:
    rc, so, se = run(raw, {"PROC_GUARD_DISK": "off"})
    check("malformed input exits 0 silently: %r" % raw[:40], rc == 0 and so == "" and se == "")
rc, so, se = run('{"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/"}', {"CLAUDE_PLUGIN_DATA": "/proc/forbidden"})
check("an unwritable state dir exits 0", rc == 0 and se == "")
check("a non-Bash tool is ignored", rg.handle({"hook_event_name": "PreToolUse", "tool_name": "Read", "cwd": cwd}) == "")

# 하위 프로세스: 이 기계의 실제 core_pattern 으로 Pre -> Post
try:
    real_pattern = open("/proc/sys/kernel/core_pattern").read().strip()
except OSError:
    real_pattern = None
if real_pattern and not real_pattern.startswith(("|", "/")) and "/" not in real_pattern:
    ce = new_dir("e2e")
    base = {"session_id": "abc", "tool_name": "Bash", "tool_input": {"command": "./crashy"}, "tool_use_id": "e1", "cwd": ce}
    rc, so, _ = run(json.dumps(dict(base, hook_event_name="PreToolUse")), {"PROC_GUARD_DISK": "off"})
    check("e2e pre is quiet", rc == 0 and so == "")
    name = rg.name_regex(real_pattern, True)
    fname = "core.31337" if name.match("core.31337") else "core"
    elf_core(os.path.join(ce, fname))
    rc, so, _ = run(json.dumps(dict(base, hook_event_name="PostToolUseFailure", error="Exit code 139\n")), {"PROC_GUARD_DISK": "off"})
    o = json.loads(so) if so.strip() else {}
    hso = o.get("hookSpecificOutput") or {}
    check("e2e post emits the core action", hso.get("hookEventName") == "PostToolUseFailure"
          and os.path.join(ce, fname) in hso.get("additionalContext", ""))
else:
    print("skip e2e: core_pattern is %r" % real_pattern)

shutil.rmtree(T, ignore_errors=True)
print("ok %d fail %d" % (ok, fail))
sys.exit(1 if fail else 0)
