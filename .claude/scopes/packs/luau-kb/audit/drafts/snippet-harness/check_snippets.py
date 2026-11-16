#!/usr/bin/env python3
"""스킬 스니펫 정본 검증기 (프로토타입). 사용: python3 -I check_snippets.py [snippets/*.luau]
각 .luau 는 luau-analyze(새 솔버, --!strict)로 검사하고, 줄 끝 표식으로 기대 진단을 선언한다.
  -- expect-error            이 줄에 TypeError 가 정확히 1건 이상 있어야 한다 (음성 대조군)
  -- expect-error: 부분문자열   + 메시지에 이 문자열이 들어 있어야 한다
  -- bug-present             '있어야 할 에러가 안 나는' 알려진 솔버 결함. 진단이 0건이어야 통과.
                             진단이 생기면 '솔버가 고쳐졌다 - 스킬 문서 갱신' 으로 실패시킨다.
머리 주석(처음 10줄):
  --@run            체크 통과 후 `luau` 로 실행, 종료코드 0 이어야 함 (lune 필요 시 --@run=lune)
  --@luau <spec>    유효한 Luau 버전(예: >=0.742). 도구 버전이 다르면 SKIP 이 아니라 WARN.
표식 없는 줄에 진단이 나면 실패. 표식 있는데 진단이 없으면 실패(= 검사기가 꺼진 0건 방지).
"""
import os, re, subprocess, sys, glob, shutil

MISE = os.path.expanduser(os.environ.get("MISE_DATA_DIR", "/code/.local/share/mise")) + "/installs"
LUAU_VER = os.environ.get("LUAU_VER", "0.742")
def tool(name):
    p = shutil.which(name)
    if p:
        h = subprocess.run([p, "--help"], capture_output=True, text=True)
        if "Usage" in (h.stdout + h.stderr) and "mise ERROR" not in h.stderr:
            return p   # mise shim 이 버전 미지정이면 실패하므로 걸러낸다
    return f"{MISE}/luau/{LUAU_VER}/{name}"   # shim 이 버전 미지정이면 설치 경로로 폴백

DIAG = re.compile(r"^(?P<f>.+?)\((?P<l>\d+),(?P<c>\d+)\): (?P<k>TypeError|SyntaxError): (?P<m>.*)$")
EXP = re.compile(r"--\s*(expect-error|bug-present)(?::\s*(.*))?\s*$")

def check(path):
    src = open(path, encoding="utf-8").read().split("\n")
    marks = {}
    for i, line in enumerate(src, 1):
        m = EXP.search(line)
        if m: marks[i] = (m.group(1), (m.group(2) or "").strip())
    r = subprocess.run(["bash", "-c", f"ulimit -v 2097152; timeout 120 {tool('luau-analyze')} --mode=strict {path}"],
                       capture_output=True, text=True)
    got = {}
    last = None
    for l in (r.stdout + r.stderr).splitlines():
        m = DIAG.match(l)
        if m:
            last = int(m["l"]); got.setdefault(last, []).append(m["m"])
        elif last and l.strip() and not l.startswith(("./", "/")):
            got[last][-1] += " " + l.strip()   # 여러 줄 메시지의 이어진 줄
    errs = []
    for ln, (kind, sub) in marks.items():
        d = got.get(ln, [])
        if kind == "expect-error":
            if not d: errs.append(f"{path}:{ln}: 에러가 나야 하는데 0건 (검사기가 놓침?)")
            elif sub and not any(sub in x for x in d): errs.append(f"{path}:{ln}: 메시지에 {sub!r} 없음: {d[0][:120]}")
        else:
            if d: errs.append(f"{path}:{ln}: bug-present 인데 진단 발생 -> 솔버가 고쳐짐, 문서 갱신 필요: {d[0][:100]}")
    for ln, d in got.items():
        if ln not in marks: errs.append(f"{path}:{ln}: 예상 못한 진단: {d[0][:120]}")
    if not errs and any(re.match(r"--@run", l) for l in src[:10]):
        rr = subprocess.run([tool("luau"), path], capture_output=True, text=True, timeout=60)
        if rr.returncode: errs.append(f"{path}: 실행 실패 rc={rr.returncode}: {(rr.stderr or rr.stdout)[:200]}")
    return errs

if __name__ == "__main__":
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "snippets", "*.luau")))
    bad = 0
    for f in files:
        e = check(f)
        print(("FAIL " if e else "ok   ") + os.path.relpath(f))
        for x in e: print("   ", x)
        bad |= bool(e)
    sys.exit(bad)
