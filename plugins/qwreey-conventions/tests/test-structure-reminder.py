#!/usr/bin/env python3
"""structure-reminder 파이프 회귀 표. 실행: python3 -I test-structure-reminder.py  (exit 0 = 전부 기대대로)

임시 저장소를 /tmp 아래에 만들고 훅에 PostToolUse JSON 을 stdin 으로 넣는다. 상태 파일은 TMPDIR 을 임시로 바꿔 격리한다.
"""
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "structure-reminder.py")
# HOOK_TEST_BIN=<바이너리> 면 python 스크립트 대신 `<바이너리> hook structure-reminder` 를 하위 프로세스로 돌린다(Rust 판, crates/qwreey-conventions)
BIN = os.environ.get("HOOK_TEST_BIN")
CMD = [BIN, "hook", "structure-reminder"] if BIN else [sys.executable, "-I", HOOK]
T = tempfile.mkdtemp(prefix="structrem-")
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
REPO = os.path.join(T, "repo")
STATE = os.path.join(T, "state")
# Claude Code 설정 폴더 흉내: 실제 ~/.claude 의 harness.env 나 설치된 luau-kb 가 계획기 안내를 바꾸지 않게
CFG = os.path.join(T, "cfg")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(STATE)
os.makedirs(os.path.join(CFG, "plugins"))


LAST = {}


def mk(rel, n, head="--!strict"):
    p = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(head + "\n" + "".join(f"local x{i} = {i}\n" for i in range(n - 1)))
    return p


def run(tool, path, sid="s1", ti_extra=None, resp=None, env_extra=None, raw=None):
    ti = {"file_path": path}
    ti.update(ti_extra or {})
    data = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": tool,
            "tool_input": ti, "tool_response": resp or {}}
    env = dict(os.environ, TMPDIR=STATE, CLAUDE_PROJECT_DIR=REPO, CLAUDE_CONFIG_DIR=CFG)
    for k in ("STRUCTURE_REMINDER", "HARNESS_ENV", "HARNESS_LUAU_KB", "HARNESS_TOOLKITS"):
        env.pop(k, None)
    env.update(env_extra or {})
    p = subprocess.run(CMD, input=raw if raw is not None else json.dumps(data),
                       capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    out = json.loads(p.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    m = re.match(r'<harness-hook name="structure-reminder" level="(info|warn|action)" nonce="[0-9a-f]{12}">\n', ctx)
    assert m and ctx.endswith("\n</harness-hook>"), ctx
    LAST["level"] = m.group(1)
    return re.sub(r' nonce="[0-9a-f]{12}">', ">", ctx)  # 아래 표는 태그 모양만 본다(nonce 는 위에서 확인)


def edit(add):
    return {"old_string": "a", "new_string": "a" + "\n" * add}


CASES = []


def case(name, got, want_sub=None, want_empty=False, not_sub=None):
    ok = (got == "") if want_empty else (want_sub in got)
    if not_sub and not_sub in got:
        ok = False
    CASES.append((ok, name, got))


small = mk("src/Small.luau", 100)
case("작은 파일 Edit → 조용", run("Edit", small, ti_extra=edit(3)), want_empty=True)

mid = mk("src/Mid.luau", 850)
out_w = run("Edit", mid, ti_extra=edit(2))
case("850줄 Edit → warn", out_w, "warn limit 800")
case("  … level=warn", out_w, 'level="warn">')
case("같은 파일 다시 → 조용(세션당 한 번)", run("Edit", mid, ti_extra=edit(2)), want_empty=True)
mk("src/Mid.luau", 1600)
out = run("Edit", mid, ti_extra=edit(5))
case("1600줄로 커짐 → hard", out, "hard limit (1500)")
case("  … level=action 태그", out, 'level="action">\n`src/Mid.luau` is 1600')
case("  … 세션 성장(848→1600)은 따로 warn 태그에", out, 'level="warn">\n`src/Mid.luau` grew 848 -> 1600')
case("그 뒤 → 조용", run("Edit", mid, ti_extra=edit(1)), want_empty=True)

g = mk("src/Grow.luau", 1050)
out = run("Edit", g, sid="s2", ti_extra=edit(350))
case("새 세션 700→1050 → warn+grow", out, "+350")
case("  … warn 도 같이", out, "warn limit")
case("  … 첫 알림에 기준 문서 안내", out, "code-structure.md")

t = mk("tests/Big.spec.luau", 1000)
case("테스트 1000줄 → 조용(두 배 기준)", run("Edit", t, ti_extra=edit(1)), want_empty=True)
t2 = mk("tests/Huge.spec.luau", 3100)
case("테스트 3100줄 → hard(3000)", run("Edit", t2, ti_extra=edit(1)), "hard limit (3000)")

ex = mk("src/Exempt.luau", 1700, head="-- @structure-exempt: type limits, cannot split")
case("예외 사유 안내 → level=info", run("Edit", ex, sid="ex1", ti_extra=edit(1)), 'level="info">')

gen = mk("assets/meshes/Prop.luau", 5000, head="-- 만든 것: scripts/meshgen.py ← Prop.json. 손으로 고치지 않는다.")
case("생성물 머리 → 조용", run("Edit", gen, ti_extra=edit(1)), want_empty=True)

for i in range(15):
    mk(f"src/flat/Mod{i:02d}.luau", 20)
newf = mk("src/flat/Extra.luau", 20)
case("새 파일, 폴더에 16개 → flat(info)", run("Write", newf, sid="s3", resp={"type": "create"}), 'level="info">\n`src/flat/` has 16 source files and 0 subfolders')
newf2 = mk("src/flat/Extra2.luau", 20)
case("같은 폴더 두 번째 → 조용", run("Write", newf2, sid="s3", resp={"type": "create"}), want_empty=True)

mk("src/client/ItemPick.luau", 30)
mk("src/client/ItemView.luau", 30)
hz = mk("src/client/ItemZoneView.luau", 30)
case("Item* 셋째 → family", run("Write", hz, sid="s4", resp={"type": "create"}), "`Item/` folder")
os.makedirs(os.path.join(REPO, "src/client2/Item"))
mk("src/client2/ItemPick.luau", 30)
mk("src/client2/ItemView.luau", 30)
hz2 = mk("src/client2/ItemZoneView.luau", 30)
case("Item/ 폴더가 이미 있으면 → 조용", run("Write", hz2, sid="s4", resp={"type": "create"}), want_empty=True)
ed = mk("src/client/ItemExtra.luau", 30)
case("Edit 은 폴더 검사 안 함", run("Edit", ed, sid="s5", ti_extra=edit(1)), want_empty=True)

md = os.path.join(REPO, "README.md")
open(md, "w").write("x\n" * 3000)
case(".md → 조용", run("Write", md), want_empty=True)
v = mk("vendor/quad/Big.luau", 4000)
case("vendor → 조용", run("Edit", v, ti_extra=edit(1)), want_empty=True)
wt = mk(".claude/worktrees/agent-1/src/Big.luau", 2000)
case("worktree 안 편집도 본다", run("Edit", wt, sid="s6", ti_extra=edit(1)), "hard limit")

os.makedirs(os.path.join(REPO, ".claude"), exist_ok=True)
json.dump({"warn": 100, "hard": 4000, "ignore": ["src/legacy/*"]}, open(os.path.join(REPO, ".claude", "structure.json"), "w"))
o = mk("src/Over.luau", 150)
case("structure.json warn 100 → 150줄 warn", run("Edit", o, sid="s7", ti_extra=edit(1)), "warn limit 100")
lg = mk("src/legacy/Old.luau", 5000)
case("structure.json ignore → 조용", run("Edit", lg, sid="s7", ti_extra=edit(1)), want_empty=True)
os.remove(os.path.join(REPO, ".claude", "structure.json"))

case("STRUCTURE_REMINDER=off → 조용", run("Edit", mk("src/Off.luau", 2000), sid="s8", ti_extra=edit(1),
                                          env_extra={"STRUCTURE_REMINDER": "off"}), want_empty=True)
bin_ts = os.path.join(REPO, "src/seg000.ts")
open(bin_ts, "wb").write(b"G\0\0\0" * 3000)
case("바이너리 .ts(MPEG-TS) → 조용", run("Write", bin_ts, sid="s9"), want_empty=True)
case("깨진 stdin → 조용", run("Edit", small, raw="{not json"), want_empty=True)
case("Read 도구 → 조용", run("Read", mid, sid="s10"), want_empty=True)


# Bash 경로: 파일을 바꿨을 법한 명령만 본다
bb = mk("src/BashBig.luau", 900)
case("Bash sed -i → warn", run("Bash", "", sid="b1", ti_extra={"command": "sed -i 's/a/b/' src/BashBig.luau"}), "warn limit 800")
bb2 = mk("src/BashBig2.luau", 1700)
case("Bash 리다이렉트 대상 → hard", run("Bash", "", sid="b2", ti_extra={"command": "cat part.txt >> src/BashBig2.luau"}), "hard limit")
case("Bash 읽기(grep) → 조용", run("Bash", "", sid="b3", ti_extra={"command": "grep -n foo src/BashBig2.luau | head"}), want_empty=True)
case("Bash 읽고 /dev/null 로 → 조용", run("Bash", "", sid="b4", ti_extra={"command": "grep foo src/BashBig2.luau > /dev/null"}), want_empty=True)
case("Bash python 이 경로를 다룸 → hard", run("Bash", "", sid="b5", ti_extra={"command": "python3 - src/BashBig2.luau <<'EOF'\nx\nEOF"}), "hard limit")
outside = os.path.join(T, "scratch", "Big.luau")
os.makedirs(os.path.dirname(outside))
open(outside, "w").write("local x = 1\n" * 3000)
case("Bash 프로젝트 밖 대상 → 조용", run("Bash", "", sid="b6", ti_extra={"command": f"sed -i 's/a/b/' {outside}"}), want_empty=True)

# 예외 표식 (사용자 결정 D-13, 2026-11-10): 사유가 있으면 한 줄만, 없으면 무효
ex1 = mk("src/ex/Types.luau", 2000, head="--!strict\n--@structure-exempt: 재귀 타입 묶음이 한 모듈 안에 있어야 함(luau-types recursion §3)")
out = run("Edit", ex1, sid="e1", ti_extra=edit(1))
case("예외 표식 → 예외 사유 한 줄", out, "Reason: 재귀 타입 묶음", not_sub="hard limit")
case("  … 성장 알림도 안 남", run("Edit", ex1, sid="e1b", ti_extra=edit(400)), "Reason:", not_sub="grew")
case("예외 파일 다시 → 조용", run("Edit", ex1, sid="e1", ti_extra=edit(1)), want_empty=True)
ex2 = mk("src/ex/Empty.luau", 2000, head="--!strict\n-- @structure-exempt:")
out = run("Edit", ex2, sid="e2", ti_extra=edit(1))
case("빈 사유 → 강제 알림", out, "hard limit")
case("  … 무효라고 덧붙임", out, "invalid")
ex3 = mk("src/ex/Later.luau", 900, head="--@structure-exempt: 나중에")
case("사유 '나중에' → 무효", run("Edit", ex3, sid="e3", ti_extra=edit(1)), "invalid")
ex4 = mk("src/ex/Lazy.luau", 900, head="--@structure-exempt: 귀찮아서")
case("사유 '귀찮아서' → 무효", run("Edit", ex4, sid="e4", ti_extra=edit(1)), "invalid")
small_ex = mk("src/ex/Small.luau", 100, head="--@structure-exempt: 생성물")
case("예외지만 경고 기준 아래 → 조용", run("Edit", small_ex, sid="e5", ti_extra=edit(1)), want_empty=True)
json.dump({"exempt": [{"path": "src/data/*.luau", "reason": "순수 데이터 표(아이콘 이름 → 에셋 id)"},
                      {"path": "src/blank/*.luau", "reason": ""}]},
          open(os.path.join(REPO, ".claude", "structure.json"), "w"))
d1 = mk("src/data/Icons.luau", 1800)
case("structure.json exempt → 예외 사유", run("Edit", d1, sid="e6", ti_extra=edit(1)), "(structure.json)")
d2 = mk("src/blank/Big.luau", 1800)
case("structure.json 빈 reason → 무효", run("Edit", d2, sid="e7", ti_extra=edit(1)), "invalid")
os.remove(os.path.join(REPO, ".claude", "structure.json"))


def fake_pack(where):
    """where 아래에 luau-kb 팩 흉내(계획기 파일 하나)를 만들고 계획기 경로를 돌려준다."""
    planner = os.path.join(where, "skills", "luau-style", "scripts", "split-plan.py")
    os.makedirs(os.path.dirname(planner), exist_ok=True)
    open(planner, "w").write("# planner\n")
    return planner


def install(plugins, markets=None):
    """설정 폴더의 installed_plugins.json, known_marketplaces.json 을 쓴다(None 이면 지운다)."""
    for name, data in (("installed_plugins.json", plugins), ("known_marketplaces.json", markets)):
        f = os.path.join(CFG, "plugins", name)
        if data is None:
            if os.path.exists(f):
                os.remove(f)
        else:
            json.dump(data, open(f, "w"))


# 폴더 마켓: installPath 가 옛 캐시여도 마켓 정의가 가리키는 팩을 쓴다
mkt = os.path.join(T, "mkt")
mkt_planner = fake_pack(os.path.join(mkt, "packs", "luau-kb"))
os.makedirs(os.path.join(mkt, ".claude-plugin"))
json.dump({"name": "m", "plugins": [{"name": "luau-kb", "source": "./packs/luau-kb"}]}, open(os.path.join(mkt, ".claude-plugin", "marketplace.json"), "w"))
install({"version": 2, "plugins": {"luau-kb@m": [{"installPath": os.path.join(T, "cache", "stale")}]}},
        {"m": {"source": {"source": "directory", "path": mkt}, "installLocation": mkt}})
hp = mk("src/plan/Huge.luau", 1700)
case("강제 기준 .luau, 폴더 마켓의 luau-kb → 분리 계획기 안내", run("Edit", hp, sid="p1", ti_extra=edit(1)), f"python3 -I {mkt_planner} ")
# GitHub 마켓 설치본: 마켓 정의가 없으면 installPath(cache 사본)
cache_planner = fake_pack(os.path.join(T, "cache", "luau-kb", "0.7.2"))
install({"version": 2, "plugins": {"luau-kb@gh": [{"installPath": os.path.join(T, "cache", "luau-kb", "0.7.2")}]}}, None)
case("luau-kb 설치본(cache) → 그 계획기", run("Edit", mk("src/plan/Huge2.luau", 1700), sid="p1b", ti_extra=edit(1)), f"python3 -I {cache_planner} ")
# HARNESS_LUAU_KB(팩 작업 사본)가 설치본보다 앞선다
kb_planner = fake_pack(os.path.join(T, "kb"))
case("HARNESS_LUAU_KB → 설치본보다 앞선다", run("Edit", mk("src/plan/Huge3.luau", 1700), sid="p1c", ti_extra=edit(1),
     env_extra={"HARNESS_LUAU_KB": os.path.join(T, "kb")}), f"python3 -I {kb_planner} ")
open(os.path.join(CFG, "harness.env"), "w").write("HARNESS_LUAU_KB=%s\n" % os.path.join(T, "kb"))
case("사용자 harness.env 의 HARNESS_LUAU_KB → 그 계획기", run("Edit", mk("src/plan/Huge4.luau", 1700), sid="p1d", ti_extra=edit(1)), f"python3 -I {kb_planner} ")
os.remove(os.path.join(CFG, "harness.env"))
os.makedirs(os.path.join(REPO, ".claude"), exist_ok=True)
open(os.path.join(REPO, ".claude", "harness.env"), "w").write("HARNESS_LUAU_KB=%s\n" % os.path.join(T, "kb"))
case("저장소 harness.env 의 HARNESS_LUAU_KB 는 무시(사용자 전용)", run("Edit", mk("src/plan/Huge5.luau", 1700), sid="p1e", ti_extra=edit(1)),
     f"python3 -I {cache_planner} ")
os.remove(os.path.join(REPO, ".claude", "harness.env"))
install(None, None)
hts = os.path.join(REPO, "src/plan/huge.ts")
open(hts, "w").write("const x = 1;\n" * 1700)
case("강제 기준 .ts → 계획기 안내 없음", run("Edit", hts, sid="p2", ti_extra=edit(1)), "hard limit", not_sub="split-plan.py")

# --- 툴킷 무관 (TS, Python, Rust, 표 덮어쓰기) ---
def mkt(rel, n, head, line="x = 1\n"):
    p = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(head + "\n" + line * (n - 1))
    return p

TS = "const x = 1;\n"
ts = mkt("web/src/Big.ts", 900, "// ts", TS)
case("TS 900줄 → warn", run("Edit", ts, sid="t1", ti_extra=edit(1)), "warn limit 800")
tsx = mkt("web/src/Huge.tsx", 1600, "// tsx", TS)
out = run("Edit", tsx, sid="t2", ti_extra=edit(1))
case("TSX 1600줄 → hard, `//@structure-exempt` 안내", out, "//@structure-exempt", not_sub="split-plan.py")
dts = mkt("web/src/types.d.ts", 3000, "// d", "type A = 1;\n")
case(".d.ts → 조용", run("Edit", dts, sid="t3", ti_extra=edit(1)), want_empty=True)
ast = mkt("web/src/Page.astro", 900, "---", "<p>x</p>\n")
case(".astro 900줄 → warn", run("Edit", ast, sid="t4", ti_extra=edit(1)), "warn limit")
dist = mkt("web/dist/app.js", 3000, "// d", "var a=1;\n")
case("dist/ → 조용", run("Edit", dist, sid="t5", ti_extra=edit(1)), want_empty=True)
astro_gen = mkt("web/.astro/types.ts", 3000, "// d", "var a=1;\n")
case(".astro/ 폴더 → 조용", run("Edit", astro_gen, sid="t5b", ti_extra=edit(1)), want_empty=True)
tt = mkt("web/src/Big.test.ts", 1000, "// t", TS)
case("*.test.ts 1000줄 → 조용(두 배)", run("Edit", tt, sid="t6", ti_extra=edit(1)), want_empty=True)
tex = mkt("web/src/Data.ts", 2000, "// @structure-exempt: 생성 표를 한 모듈로 유지", TS)
case("TS `//` 예외 표식 → 예외 사유", run("Edit", tex, sid="t7", ti_extra=edit(1)), "Reason: 생성 표")
wrong = mkt("web/src/Wrong.ts", 2000, "-- @structure-exempt: 사유가 있다", TS)
case("TS 에 `--` 표식은 표식 아님 → hard", run("Edit", wrong, sid="t8", ti_extra=edit(1)), "hard limit")
py = mkt("py/app.py", 900, "# py")
case("Python 900줄 → warn", run("Edit", py, sid="p3", ti_extra=edit(1)), "warn limit 800")
pyh = mkt("py/big.py", 1600, "# py")
case("Python hard, `#@structure-exempt` 안내", run("Edit", pyh, sid="p4", ti_extra=edit(1)), "#@structure-exempt", not_sub="split-plan.py")
pyt = mkt("py/test_big.py", 1000, "# py")
case("test_*.py 1000줄 → 조용(두 배)", run("Edit", pyt, sid="p5", ti_extra=edit(1)), want_empty=True)
pyx = mkt("py/gen.py", 2000, "# @structure-exempt: 프로토콜 표")
case("Python `#` 예외 → 예외 사유", run("Edit", pyx, sid="p6", ti_extra=edit(1)), "Reason: 프로토콜 표")
pyc = mkt("py/__pycache__/x.py", 3000, "# py")
case("__pycache__ → 조용", run("Edit", pyc, sid="p7", ti_extra=edit(1)), want_empty=True)
rs = mkt("rs/src/lib.rs", 900, "// rs", "let x = 1;\n")
case("Rust 900줄 → warn", run("Edit", rs, sid="r1", ti_extra=edit(1)), "warn limit 800")
rsg = mkt("rs/target/debug/gen.rs", 3000, "// rs", "let x = 1;\n")
case("target/ → 조용", run("Edit", rsg, sid="r2", ti_extra=edit(1)), want_empty=True)
case("Bash sed -i 가 .py 를 건드림 → warn", run("Bash", "", sid="r3", ti_extra={"command": "sed -i 's/a/b/' py/app.py"}), "warn limit 800")
# 저장소가 툴킷 표를 덮어쓴다
os.makedirs(os.path.join(REPO, ".claude"), exist_ok=True)
json.dump({"toolkits": {"web": {"warn": 500, "hard": 600, "ext": [".ts", ".vue"]},
                        "zz": {"ext": [".zz"], "comment": [";;"], "warn": 50}}},
          open(os.path.join(REPO, ".claude", "structure.json"), "w"))
case("structure.json web.hard 600 → TS 900줄 hard(600)", run("Edit", mkt("web/src/Ov.ts", 900, "// x", TS), sid="o1", ti_extra=edit(1)), "hard limit (600)")
case("덮어쓴 ext 에 .vue 추가 → 감지", run("Edit", mkt("web/src/A.vue", 700, "<!-- v -->", "<p/>\n"), sid="o2", ti_extra=edit(1)), "hard limit (600)")
case("덮어쓰기에서 빠진 .tsx 는 안 봄", run("Edit", mkt("web/src/B.tsx", 900, "// x", TS), sid="o3", ti_extra=edit(1)), want_empty=True)
case("새 툴킷(.zz) 추가 → warn 50", run("Edit", mkt("zz/a.zz", 60, ";; x", "z\n"), sid="o4", ti_extra=edit(1)), "warn limit 50")
case("다른 툴킷(luau)은 영향 없음", run("Edit", mk("src/Luau900.luau", 900), sid="o5", ti_extra=edit(1)), "warn limit 800")
os.remove(os.path.join(REPO, ".claude", "structure.json"))
# HARNESS_TOOLKITS 필터
case("HARNESS_TOOLKITS=luau → TS 조용", run("Edit", mkt("web/src/F.ts", 900, "// x", TS), sid="f1", ti_extra=edit(1),
     env_extra={"HARNESS_TOOLKITS": "luau"}), want_empty=True)
case("HARNESS_TOOLKITS=luau → luau 는 봄", run("Edit", mk("src/F2.luau", 900), sid="f2", ti_extra=edit(1),
     env_extra={"HARNESS_TOOLKITS": "luau"}), "warn limit")
# 계획기를 못 찾으면 안내 생략
nohome = os.path.join(T, "nohome"); os.makedirs(nohome)
case("luau-kb 미설치, HARNESS_LUAU_KB 없음 → 안내 생략", run("Edit", mk("src/NoPlan.luau", 1700), sid="n1", ti_extra=edit(1),
     env_extra={"HOME": nohome}), "hard limit", not_sub="split-plan.py")
case("HARNESS_LUAU_KB 에 계획기가 없음 → 안내 생략", run("Edit", mk("src/NoPlan2.luau", 1700), sid="n2", ti_extra=edit(1),
     env_extra={"HOME": nohome, "HARNESS_LUAU_KB": nohome}), "hard limit", not_sub="split-plan.py")

import time
_t = []
for i in range(10):
    s0 = time.monotonic(); run("Edit", mid, sid="tm%d" % i, ti_extra=edit(1)); _t.append((time.monotonic() - s0) * 1000)
_t.sort()
print("지연(ms, 프로세스 기동 포함) median %.1f max %.1f" % (_t[5], _t[-1]))

fails = [c for c in CASES if not c[0]]
for ok, name, got in CASES:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got: {got!r}"))
print(f"{len(CASES) - len(fails)}/{len(CASES)}")
shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
