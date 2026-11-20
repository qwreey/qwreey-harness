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
# HOOK_TEST_BIN=<바이너리> 면 python 스크립트 대신 `<바이너리> hook resource-guard` 를 하위 프로세스로 돌린다(Rust 판, crates/qwreey-proc-guard)
BIN = os.environ.get("HOOK_TEST_BIN")
# 이 시험의 대부분은 python 모듈을 이 프로세스에 적재해 부른다. 바이너리로 도는 것은 하위 프로세스 묶음(동시 Post, 깨진 입력, e2e)뿐이다
CMD = [BIN, "hook", "resource-guard"] if BIN else [sys.executable, "-I", "-X", "utf8", HOOK]
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


def event(kind, sid, tid, cwd, command="./run", **extra):
    """Bash 훅 이벤트로 handle() 을 불러 알림 글을 돌려준다."""
    data = {"session_id": sid, "hook_event_name": kind, "tool_name": "Bash", "tool_input": {"command": command},
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
check("pre with no dumps is quiet", event("PreToolUse", "c1", "k1", cw, command="./crashy --boom") == "")
elf_core(os.path.join(cw, "core.12345"))
out = event("PostToolUse", "c1", "k1", cw, command="./crashy --boom")
check("a core whose program is in the command is an action", level(out, "action") and os.path.join(cw, "core.12345") in out)
check("core action names program, args and signal", "program `./crashy --boom`" in out and "SIGSEGV" in out and "KiB" in out)
check("core action says delete if intended, keep and tell if needed",
      "delete these files now" in out and "tell the user the path and size" in out)
event("PreToolUse", "c1", "k2", cw)
check("the same core is reported once per session", event("PostToolUse", "c1", "k2", cw) == "")

# 명령에 없는 프로그램의 core: 지우라고 하지 않는다
cm = new_dir("core-mismatch")
event("PreToolUse", "m1", "m1", cm, command="cargo test")
elf_core(os.path.join(cm, "core.9"), program=b"luau-lsp", args=b"/usr/bin/luau-lsp lsp")
out = event("PostToolUseFailure", "m1", "m1", cm, command="cargo test", error="Exit code 101\n")
check("a core from a program not in the command is a warn, not an action", level(out, "warn") and not level(out, "action"))
check("the warn says it may not be from this command and names the program",
      "may not be from this command" in out and "program `/usr/bin/luau-lsp lsp`" in out and "delete these files now" not in out
      and "Keep these files and tell the user each path and size" in out)
check("an interpreter path in args matches the command", rg.program_in_command(
    {"program": "python3", "args": "/usr/bin/python3 x.py"}, "python3 x.py"))
check("sh does not match bash", not rg.program_in_command({"program": "sh", "args": ""}, "bash run.sh"))

# 두 세션이 같은 폴더에서 Pre 를 가진 채 남의 core 가 생김(재현 B)
cb = new_dir("core-two-sessions")
event("PreToolUse", "b1", "b1", cb, command="make test")
event("PreToolUse", "b2", "b2", cb, command="npm test")
elf_core(os.path.join(cb, "core.31"), program=b"luau-lsp", args=b"luau-lsp lsp")
for sid in ("b1", "b2"):
    out = event("PostToolUse", sid, sid, cb, command="make test" if sid == "b1" else "npm test")
    check("session %s gets no delete for a third-party core" % sid, level(out, "warn") and not level(out, "action"))

# 프로그램을 읽지 못한 core(재현 C)
cu = new_dir("core-unknown")
event("PreToolUse", "u1", "u1", cu)
elf_core(os.path.join(cu, "core.1"), program=b"", args=b"")
out = event("PostToolUse", "u1", "u1", cu)
check("an unknown program without a crash is a warn that says program unknown",
      level(out, "warn") and not level(out, "action") and "program unknown" in out)
cu2 = new_dir("core-unknown-crash")
event("PreToolUse", "u2", "u2", cu2)
elf_core(os.path.join(cu2, "core.2"), program=b"", args=b"")
out = event("PostToolUseFailure", "u2", "u2", cu2, error="Exit code 134\n")
check("an unknown program with a crash of this command is an action", level(out, "action") and "program unknown" in out)

# mtime 경계: 여유 없음, 초 단위 mtime 만 같은 초부터(재현 A)
ct = new_dir("core-mtime")
event("PreToolUse", "a1", "a1", ct)
t_ns = rg.read_json(rg.pre_path({"session_id": "a1", "tool_use_id": "a1"}))["t_ns"]
elf_core(os.path.join(ct, "core.1"))
os.utime(os.path.join(ct, "core.1"), ns=(t_ns - 1500000000 + 1234, t_ns - 1500000000 + 1234))
check("a core 1.5 s before Pre is ignored", event("PostToolUseFailure", "a1", "a1", ct, error="Exit code 139\n") == "")
event("PreToolUse", "a2", "a2", ct)
t_ns = rg.read_json(rg.pre_path({"session_id": "a2", "tool_use_id": "a2"}))["t_ns"]
whole = t_ns - t_ns % 10 ** 9
elf_core(os.path.join(ct, "core.2"))
os.utime(os.path.join(ct, "core.2"), ns=(whole, whole))
elf_core(os.path.join(ct, "core.3"))
os.utime(os.path.join(ct, "core.3"), ns=(whole - 10 ** 9, whole - 10 ** 9))
out = event("PostToolUseFailure", "a2", "a2", ct, error="Exit code 139\n")
check("a whole-second mtime in the Pre second counts (coarse timestamps)", os.path.join(ct, "core.2") in (out or ""))
check("a whole-second mtime before the Pre second does not", os.path.join(ct, "core.3") not in (out or ""))

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
elf_core(os.path.join(cs, "crates", "a", "core.4244"))
out = event("PostToolUseFailure", "c4", "s2", cs, error="Exit code 139\n")
check("exit code 139 walks subdirs and finds the core", os.path.join(cs, "crates", "a", "core.4244") in (out or ""))
check("a core older than this Pre in the subdir is not listed", "core.4242" not in (out or ""))
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
check("duration_ms stands in for the pre record", "core.5" in (event("PostToolUse", "c6", "x2", cd, duration_ms=5000) or ""))

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


# 넓은 훑기의 시한: 큰 나무에서도 0.5 초 안, 가짜 시계로 시한이 걷기 중간에 끊는지
big = new_dir("big-tree")
for a in range(60):
    for b in range(40):
        os.makedirs(os.path.join(big, "a%02d" % a, "b%02d" % b))
event("PreToolUse", "w1", "w1", big)
elf_core(os.path.join(big, "a59", "b39", "core.77"))
t0 = time.perf_counter()
out = event("PostToolUseFailure", "w1", "w1", big, error="Exit code 139\n")
spent = time.perf_counter() - t0
print("wide search over 2460 dirs: %.3f s" % spent)
check("wide search on a 2,460-dir tree stays under 0.5 s", spent < 0.5)
check("wide search finds the deepest-listed core", os.path.join(big, "a59", "b39", "core.77") in (out or ""))
ticks = {"n": 0}


def fake_clock():
    """부를 때마다 1 ms 가는 시계."""
    ticks["n"] += 1
    return ticks["n"] / 1000.0


rg.clock = fake_clock
event("PreToolUse", "w2", "w2", big)
elf_core(os.path.join(big, "a59", "b39", "core.78"))
out = event("PostToolUseFailure", "w2", "w2", big, error="Exit code 139\n")
rg.clock = time.monotonic
check("the deadline stops the walk part-way (fake clock)", "core.78" not in (out or "") and ticks["n"] < 2000)

# 세션 기록 잠금: 같은 core 를 여러 Post 가 함께 봐도 한 번만 알린다
cl = new_dir("core-lock")
elf_core(os.path.join(cl, "core.5"), program=b"crashy", args=b"./crashy")
raw = json.dumps({"session_id": "lk", "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "cwd": cl,
                  "tool_input": {"command": "./crashy"}, "error": "Exit code 139\n", "duration_ms": 60000})
env = dict(os.environ, PROC_GUARD_DISK="off")
# stdin 은 파일로: PIPE 와 communicate 를 차례로 부르면 하위 프로세스가 하나씩 돌아 겹치지 않는다
with open(os.path.join(T, "lock-in.json"), "w") as f:
    f.write(raw)
procs = [subprocess.Popen(CMD, stdin=open(os.path.join(T, "lock-in.json")),
                          stdout=subprocess.PIPE, text=True, env=env) for _ in range(8)]
outs = [p.communicate(timeout=20)[0] for p in procs]
check("8 parallel posts report one core once", sum("core.5" in o for o in outs) == 1)
if hasattr(os, "getuid"):
    import fcntl
    held = os.open(os.path.join(rg.state_dir(), "s-%s.json.lock" % rg.session_key({"session_id": "held"})), os.O_RDWR | os.O_CREAT)
    fcntl.flock(held, fcntl.LOCK_EX)
    t0 = time.perf_counter()
    free(1, 100)
    out = event("PreToolUse", "held", "h1", cw)
    free(500)
    check("a held lock is waited on briefly, then the hook goes on", time.perf_counter() - t0 < 2 and level(out, "warn"))
    os.close(held)

# 상태 폴더: 대체 위치는 사용자마다, 남이 쓸 수 있으면 core 를 보지 않는다
saved = os.environ.pop("CLAUDE_PLUGIN_DATA")
check("the temp fallback is per user", os.path.basename(os.path.dirname(rg.state_dir())) == "claude-qwreey-proc-guard-" + rg.my_uid())
os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(T, "data-open")
os.makedirs(rg.state_dir())
os.chmod(rg.state_dir(), 0o777)
cx = new_dir("core-untrusted")
event("PreToolUse", "x1", "x1", cx, command="./crashy")
elf_core(os.path.join(cx, "core.6"))
check("a writable-by-others state dir skips the core check",
      event("PostToolUseFailure", "x1", "x1", cx, command="./crashy", error="Exit code 139\n") == "")
os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(T, "data-new")
event("PreToolUse", "x2", "x2", cx)
check("new state dirs are 0700", os.stat(rg.state_dir()).st_mode & 0o777 == 0o700
      and os.stat(os.path.dirname(rg.state_dir())).st_mode & 0o777 == 0o700)
os.environ["CLAUDE_PLUGIN_DATA"] = saved

# 하위 프로세스: 깨진 입력은 조용히 exit 0
def run(raw, env=None):
    """훅을 하위 프로세스로 돌려 (종료 코드, stdout, stderr)."""
    e = dict(os.environ, **(env or {}))
    p = subprocess.run(CMD, input=raw, capture_output=True, text=True, timeout=20, env=e)
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
