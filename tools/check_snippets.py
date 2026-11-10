#!/usr/bin/env python3
"""luau-kb 스니펫 검증기. 스킬 references 의 'verified' 주장은 전부 snippets/*.luau 하나와 짝이다.

사용:
  python3 -I tools/check_snippets.py snippets/*.luau                 # 기본 버전(LUAU_VER, 없으면 0.742)
  python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau   # 버전 행렬, 어느 하나라도 실패면 rc=1
  python3 -I tools/check_snippets.py --luau 0.734,0.742 --table snippets/*.luau  # RESULTS.md 용 표 출력
  --lsp 1.70.1   를 더하면 luau-lsp analyze(새 솔버) 결과를 '참고 열'로 덧붙인다(판정에는 안 씀).

줄 끝 표식 (`--` 주석 안, 여러 개면 ` || ` 로 구분):
  -- expect-error                 이 줄에 TypeError/SyntaxError 가 1건 이상 있어야 한다 (음성 대조군)
  -- expect-error: 부분문자열      + 메시지(여러 줄 메시지는 이어 붙임)에 그 문자열이 있어야 한다
  -- bug-present                  '있어야 할 에러가 안 나는' 알려진 한계. 진단이 0건이어야 통과한다.
                                  진단이 생기면 '솔버가 바뀌었다 -> 문서 갱신' 으로 실패한다.
  각 표식 뒤에 버전 조건을 붙일 수 있다:  -- bug-present [<0.742] || expect-error [>=0.742]
  조건: <, <=, >, >=, = 와 x.y 버전. 조건이 안 맞는 표식은 그 버전에서 없는 것으로 친다.
머리 주석(처음 20줄):
  --@run            검사 통과 뒤 같은 버전의 `luau` 로 실행, rc=0 이어야 한다 (--@run=lune 이면 lune)
  --@solver=old     옛 솔버(--solver=old)로 검사한다
  --@luaurc {json}  임시 디렉터리에 이 내용의 .luaurc 를 두고 검사한다
  --@args ...       luau-analyze 에 덧붙일 인자 (예: --mode=strict)
  --@no-control 이유  bug-present 가 있는데 같은 파일에 expect-error 대조군을 둘 수 없을 때만
규칙:
  - 표식 없는 줄의 진단은 실패.  - expect-error 줄에 진단이 없으면 실패(검사기가 꺼진 0건 방지).
  - bug-present 가 있는 파일엔 그 버전에서 살아 있는 expect-error 가 최소 하나 있어야 한다(음성 대조군).
도구 위치: $LUAU_BIN_DIR/<ver> 가 있으면 그것, 없으면 $MISE_DATA_DIR(기본 /code/.local/share/mise)/installs/luau/<ver>.
mise shim 은 쓰지 않는다(버전 미지정 디렉터리에서 'No version is set' 으로 실패하고, --help 에는 rc=0 으로 답해 오판을 부른다).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

MISE = os.environ.get("MISE_DATA_DIR", "/code/.local/share/mise")
DIAG = re.compile(r"^(?P<f>.+?)\((?P<l>\d+),(?P<c>\d+)\): (?P<k>TypeError|SyntaxError): (?P<m>.*)$")
LOC_ANY = re.compile(r"^.+?\(\d+,\d+\): ")
MARK = re.compile(r"(expect-error|bug-present)(?::\s*(.*?))?\s*(?:\[(<=|>=|<|>|=)\s*(\d+\.\d+)\])?\s*$")


def ver(s):
    return tuple(int(x) for x in s.split("."))


def tool_dir(v):
    base = os.environ.get("LUAU_BIN_DIR")
    if base and os.path.isdir(os.path.join(base, v)):
        return os.path.join(base, v)
    return os.path.join(MISE, "installs", "luau", v)


def lsp_bin(v):
    return os.path.join(MISE, "installs", "github-johnny-morganz-luau-lsp", v, "luau-lsp")


def lune_bin():
    root = os.path.join(MISE, "installs", "github-lune-org-lune")
    cands = sorted(d for d in os.listdir(root) if re.fullmatch(r"\d+\.\d+\.\d+", d)) if os.path.isdir(root) else []
    return os.path.join(root, cands[-1], "lune") if cands else (shutil.which("lune") or "lune")


def cond_ok(op, v, cur):
    if not op:
        return True
    a, b = ver(cur), ver(v)
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b}[op]


def parse(path):
    src = open(path, encoding="utf-8").read().split("\n")
    heads = {}
    for line in src[:20]:
        m = re.match(r"^--@([\w-]+)(?:[= ](.*))?$", line.strip())
        if m:
            heads[m.group(1)] = (m.group(2) or "").strip()
    marks = {}  # line -> list of (kind, sub, op, v)
    for i, line in enumerate(src, 1):
        if line.lstrip().startswith("--"):
            continue  # 주석 줄은 표식 줄이 아니다(설명 주석 속 표식 이름 오인 방지)
        k = line.find("-- ")
        while k != -1 and line[:k].count('"') % 2 == 1:
            k = line.find("-- ", k + 1)
        if k == -1:
            continue
        clauses = []
        for part in line[k + 3:].split(" || "):
            m = MARK.match(part.strip())
            if m:
                clauses.append((m.group(1), (m.group(2) or "").strip(), m.group(3), m.group(4)))
        if clauses:
            marks[i] = clauses
    return src, heads, marks


def diagnostics(text):
    got, last = {}, None
    for l in text.splitlines():
        m = DIAG.match(l)
        if m:
            last = int(m["l"])
            got.setdefault(last, []).append(m["m"])
        elif LOC_ANY.match(l):
            last = None  # 린트 등 다른 종류의 줄 — 이어 붙이기 중단
        elif last is not None and l.strip():
            got[last][-1] += " " + l.strip()
    return got


def analyze(path, heads, v):
    with tempfile.TemporaryDirectory(prefix="luau-kb-") as d:
        dst = os.path.join(d, os.path.basename(path))
        shutil.copy(path, dst)
        if "luaurc" in heads:
            json.loads(heads["luaurc"])
            open(os.path.join(d, ".luaurc"), "w").write(heads["luaurc"])
        args = [os.path.join(tool_dir(v), "luau-analyze")]
        if heads.get("solver") == "old":
            args.append("--solver=old")
        args += heads.get("args", "").split() + [os.path.basename(dst)]
        cmd = "ulimit -v 2097152; exec timeout 120 " + " ".join(subprocess.list2cmdline([a]) for a in args)
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=d)
        if r.returncode not in (0, 1):
            return None, f"luau-analyze rc={r.returncode}: {(r.stderr or r.stdout)[:200]}"
        return diagnostics(r.stdout + r.stderr), None


def check(path, v):
    src, heads, marks = parse(path)
    got, err = analyze(path, heads, v)
    if err:
        return [err], {}
    active = {ln: [c for c in cl if cond_ok(c[2], c[3], v)] for ln, cl in marks.items()}
    active = {ln: cl for ln, cl in active.items() if cl}
    errs = []
    n_exp = n_bug = 0
    for ln, cl in active.items():
        if len(cl) > 1:
            errs.append(f"{ln}: 이 버전에서 표식이 둘 이상 살아 있음 — 조건을 고칠 것")
            continue
        kind, sub, _, _ = cl[0]
        d = got.get(ln, [])
        if kind == "expect-error":
            n_exp += 1
            if not d:
                errs.append(f"{ln}: expect-error 인데 0건 (검사기가 놓침 또는 동작 변화)")
            elif sub and not any(sub in x for x in d):
                errs.append(f"{ln}: 메시지에 {sub!r} 없음: {d[0][:160]}")
        else:
            n_bug += 1
            if d:
                errs.append(f"{ln}: bug-present 인데 진단 발생 -> 동작이 바뀜, 문서 갱신: {d[0][:140]}")
    for ln, d in sorted(got.items()):
        if ln not in active:
            errs.append(f"{ln}: 예상 못한 진단: {d[0][:160]}")
    if n_bug and not n_exp and "no-control" not in heads:
        errs.append("bug-present 가 있는데 살아 있는 expect-error 대조군이 없음 (또는 --@no-control 이유)")
    if not errs and "run" in heads:
        runner = heads["run"] or "luau"
        with tempfile.TemporaryDirectory(prefix="luau-kb-run-") as d:
            dst = os.path.join(d, os.path.basename(path))
            shutil.copy(path, dst)
            exe = [lune_bin(), "run", dst] if runner == "lune" else [os.path.join(tool_dir(v), "luau"), dst]
            rr = subprocess.run(exe, capture_output=True, text=True, timeout=60, cwd=d)
            if rr.returncode:
                errs.append(f"실행 실패 rc={rr.returncode}: {(rr.stderr or rr.stdout)[:200]}")
    return errs, {"E": n_exp, "B": n_bug, "run": "run" in heads}


def lsp_info(path, lv):
    """참고용: luau-lsp analyze(새 솔버) 진단 줄 목록을 표식과 비교해 한 단어로."""
    src, heads, marks = parse(path)
    b = lsp_bin(lv)
    if not os.path.exists(b) or heads.get("solver") == "old" or "luaurc" in heads:
        return "—"
    with tempfile.TemporaryDirectory(prefix="luau-kb-lsp-") as d:
        dst = os.path.join(d, os.path.basename(path))
        shutil.copy(path, dst)
        r = subprocess.run([b, "analyze", "--platform=standard", "--flag:LuauSolverV2=true", os.path.basename(dst)],
                           capture_output=True, text=True, cwd=d, timeout=120)
    got = diagnostics(r.stdout + r.stderr)
    want_err = {ln for ln, cl in marks.items() if any(c[0] == "expect-error" for c in cl)}
    want_bug = {ln for ln, cl in marks.items() if all(c[0] == "bug-present" for c in cl)}
    diff = []
    for ln in sorted(want_err):
        if ln not in got and not any(c[0] == "bug-present" for c in marks[ln]):
            diff.append(f"{ln}:놓침")
    for ln in sorted(want_bug):
        if ln in got:
            diff.append(f"{ln}:잡음")
    for ln in sorted(got):
        if ln not in marks:
            diff.append(f"{ln}:추가")
    # 버전 조건이 섞인 줄은 lsp 의 내장 Luau 버전을 모르므로 판정하지 않고 관측만 적는다
    mixed = [f"{ln}:{'잡음' if ln in got else '무진단'}" for ln in sorted(marks)
             if len({c[0] for c in marks[ln]}) > 1]
    out = "같음" if not diff else "다름(" + ",".join(diff) + ")"
    return out + (" [버전 조건 줄 " + ",".join(mixed) + "]" if mixed else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--luau", default=os.environ.get("LUAU_VER", "0.742"))
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--lsp", default="")
    a = ap.parse_args()
    files = a.files or sys.exit("파일을 주세요: python3 -I tools/check_snippets.py snippets/*.luau")
    vers = [x.strip() for x in a.luau.split(",") if x.strip()]
    for v in vers:
        if not os.path.exists(os.path.join(tool_dir(v), "luau-analyze")):
            sys.exit(f"luau {v} 의 luau-analyze 가 없음: {tool_dir(v)}")
    bad = 0
    rows = []
    for f in files:
        cells = []
        for v in vers:
            e, info = check(f, v)
            bad |= bool(e)
            if not a.table:
                print(("FAIL " if e else "ok   ") + f"[{v}] " + os.path.relpath(f))
                for x in e:
                    print("     ", x)
            cell = "FAIL" if e else "ok"
            if info:
                cell += f" (E{info['E']} B{info['B']}{' run' if info['run'] else ''})"
            cells.append(cell)
        if a.lsp:
            cells.append(lsp_info(f, a.lsp))
        rows.append((os.path.basename(f), cells))
    if a.table:
        head = ["스니펫"] + [f"luau {v}" for v in vers] + ([f"luau-lsp {a.lsp} (참고)"] if a.lsp else [])
        print("| " + " | ".join(head) + " |")
        print("|" + "---|" * len(head))
        for name, cells in rows:
            print(f"| `{name}` | " + " | ".join(cells) + " |")
    sys.exit(bad)


if __name__ == "__main__":
    main()
