#!/usr/bin/env python3
"""structure-reminder 파이프 회귀 표. 실행: python3 -I test-structure-reminder.py  (exit 0 = 전부 기대대로)

임시 저장소를 /tmp 아래에 만들고 훅에 PostToolUse JSON 을 stdin 으로 넣는다. 상태 파일은 TMPDIR 을 임시로 바꿔 격리한다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "structure-reminder.py")
T = tempfile.mkdtemp(prefix="structrem-")
REPO = os.path.join(T, "repo")
STATE = os.path.join(T, "state")
os.makedirs(os.path.join(REPO, ".git"))
os.makedirs(STATE)


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
    env = dict(os.environ, TMPDIR=STATE, CLAUDE_PROJECT_DIR=REPO)
    env.pop("STRUCTURE_REMINDER", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=raw if raw is not None else json.dumps(data),
                       capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    out = json.loads(p.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return out["hookSpecificOutput"]["additionalContext"]


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
case("850줄 Edit → warn", run("Edit", mid, ti_extra=edit(2)), "경고 기준 800줄")
case("같은 파일 다시 → 조용(세션당 한 번)", run("Edit", mid, ti_extra=edit(2)), want_empty=True)
mk("src/Mid.luau", 1600)
out = run("Edit", mid, ti_extra=edit(5))
case("1600줄로 커짐 → hard", out, "강제 기준(1500줄)")
case("  … 세션 성장(848→1600)도 같은 알림에", out, "848 → 1600")
case("그 뒤 → 조용", run("Edit", mid, ti_extra=edit(1)), want_empty=True)

g = mk("src/Grow.luau", 1050)
out = run("Edit", g, sid="s2", ti_extra=edit(350))
case("새 세션 700→1050 → warn+grow", out, "+350")
case("  … warn 도 같이", out, "경고 기준")
case("  … 첫 알림에 기준 문서 안내", out, "structure.md")

t = mk("tests/Big.spec.luau", 1000)
case("테스트 1000줄 → 조용(두 배 기준)", run("Edit", t, ti_extra=edit(1)), want_empty=True)
t2 = mk("tests/Huge.spec.luau", 3100)
case("테스트 3100줄 → hard(3000)", run("Edit", t2, ti_extra=edit(1)), "강제 기준(3000줄)")

gen = mk("assets/meshes/Prop.luau", 5000, head="-- 만든 것: scripts/meshgen.py ← Prop.json. 손으로 고치지 않는다.")
case("생성물 머리 → 조용", run("Edit", gen, ti_extra=edit(1)), want_empty=True)

for i in range(15):
    mk(f"src/flat/Mod{i:02d}.luau", 20)
newf = mk("src/flat/Extra.luau", 20)
case("새 파일, 폴더에 16개 → flat", run("Write", newf, sid="s3", resp={"type": "create"}), "하위 폴더는 0개")
newf2 = mk("src/flat/Extra2.luau", 20)
case("같은 폴더 두 번째 → 조용", run("Write", newf2, sid="s3", resp={"type": "create"}), want_empty=True)

mk("src/client/ItemPick.luau", 30)
mk("src/client/ItemView.luau", 30)
hz = mk("src/client/ItemZoneView.luau", 30)
case("Item* 셋째 → family", run("Write", hz, sid="s4", resp={"type": "create"}), "`Item/` 폴더")
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
case("worktree 안 편집도 본다", run("Edit", wt, sid="s6", ti_extra=edit(1)), "강제 기준")

os.makedirs(os.path.join(REPO, ".claude"), exist_ok=True)
json.dump({"warn": 100, "hard": 4000, "ignore": ["src/legacy/*"]}, open(os.path.join(REPO, ".claude", "structure.json"), "w"))
o = mk("src/Over.luau", 150)
case("structure.json warn 100 → 150줄 warn", run("Edit", o, sid="s7", ti_extra=edit(1)), "경고 기준 100줄")
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
case("Bash sed -i → warn", run("Bash", "", sid="b1", ti_extra={"command": "sed -i 's/a/b/' src/BashBig.luau"}), "경고 기준 800줄")
bb2 = mk("src/BashBig2.luau", 1700)
case("Bash 리다이렉트 대상 → hard", run("Bash", "", sid="b2", ti_extra={"command": "cat part.txt >> src/BashBig2.luau"}), "강제 기준")
case("Bash 읽기(grep) → 조용", run("Bash", "", sid="b3", ti_extra={"command": "grep -n foo src/BashBig2.luau | head"}), want_empty=True)
case("Bash 읽고 /dev/null 로 → 조용", run("Bash", "", sid="b4", ti_extra={"command": "grep foo src/BashBig2.luau > /dev/null"}), want_empty=True)
case("Bash python 이 경로를 다룸 → hard", run("Bash", "", sid="b5", ti_extra={"command": "python3 - src/BashBig2.luau <<'EOF'\nx\nEOF"}), "강제 기준")
outside = os.path.join(T, "scratch", "Big.luau")
os.makedirs(os.path.dirname(outside))
open(outside, "w").write("local x = 1\n" * 3000)
case("Bash 프로젝트 밖 대상 → 조용", run("Bash", "", sid="b6", ti_extra={"command": f"sed -i 's/a/b/' {outside}"}), want_empty=True)

fails = [c for c in CASES if not c[0]]
for ok, name, got in CASES:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got: {got!r}"))
print(f"{len(CASES) - len(fails)}/{len(CASES)}")
shutil.rmtree(T, ignore_errors=True)
sys.exit(1 if fails else 0)
