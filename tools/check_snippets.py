#!/usr/bin/env python3
"""luau-kb 스니펫 검증기. 스킬 references 의 'verified' 주장은 전부 snippets/*.luau 하나와 짝이다.

사용:
  python3 -I tools/check_snippets.py snippets/*.luau                 # 기본 버전(LUAU_VER, 없으면 0.742)
  python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau   # 버전 행렬, 어느 하나라도 실패면 rc=1
  python3 -I tools/check_snippets.py --luau 0.734,0.742 --table snippets/*.luau  # RESULTS.md 용 표 출력
  --lsp 1.70.1   를 더하면 luau-lsp analyze(새 솔버) 결과를 '참고 열'로 덧붙인다(판정에는 안 씀).
  --mode roblox  모든 파일을 Roblox 모드(아래 --@lsp-roblox)로 검사한다. 머리에 --@lsp-roblox 가 있는 파일은 모드와 무관하게 Roblox 모드다.
  --rbx-lsp 1.70.1,1.69.0   Roblox 모드 파일을 검사할 luau-lsp 버전들(기본 1.70.1,1.69.0 중 설치된 것). --defs 로 정의 파일을 바꾼다.

줄 끝 표식 (`--` 주석 안, 여러 개면 ` || ` 로 구분):
  -- expect-error                 이 줄에 TypeError/SyntaxError 가 1건 이상 있어야 한다 (음성 대조군)
  -- expect-error: 부분문자열      + 메시지(여러 줄 메시지는 이어 붙임)에 그 문자열이 있어야 한다
  -- bug-present                  '있어야 할 에러가 안 나는' 알려진 한계. 진단이 0건이어야 통과한다.
                                  진단이 생기면 '솔버가 바뀌었다 -> 문서 갱신' 으로 실패한다.
  각 표식 뒤에 버전 조건을 붙일 수 있다:  -- bug-present [<0.742] || expect-error [>=0.742]
  조건: <, <=, >, >=, = 와 x.y 버전. 조건이 안 맞는 표식은 그 버전에서 없는 것으로 친다.
머리 주석(처음 30줄):
  --@run            검사 통과 뒤 같은 버전의 `luau` 로 실행, rc=0 이어야 한다 (--@run=lune 이면 lune)
  --@solver=old     옛 솔버(--solver=old)로 검사한다
  --@luaurc {json}  임시 디렉터리에 이 내용의 .luaurc 를 두고 검사한다
  --@args ...       luau-analyze 에 덧붙일 인자 (예: --mode=strict)
  --@no-control 이유  bug-present 가 있는데 같은 파일에 expect-error 대조군을 둘 수 없을 때만
  --@lsp-roblox     검사기를 luau-lsp analyze --platform=roblox --definitions=typedefs/globalTypes.d.luau --flag:LuauSolverV2=true 로
                    바꾼다. 표식의 버전 조건은 luau-lsp 버전과 비교한다. --@args 는 luau-lsp 에 붙는다(머리 인자가 기본값보다
                    앞에 온다. 같은 --flag: 가 두 번이면 앞의 값이 이기고, --platform 을 두 번 주면 실패하므로 머리에 있으면 기본값을 뺀다).
  --@sourcemap {json}  (Roblox 모드) Rojo 형식 sourcemap 을 임시 파일로 두고 --sourcemap 으로 넘긴다.
실행 머리(여러 줄 가능, 처음 30줄, 검사 통과 뒤 같은 버전의 도구로 돈다. Roblox 모드에서는 쓸 수 없다):
  --@run-opt=2      `luau -O2 파일` 도 rc=0 이어야 한다. 쉼표로 여럿: --@run-opt=0,2
  --@run-with 인자 => ok|fail[; out~정규식][; out!~정규식]
                    `luau 인자 파일` 을 돌려 rc(ok=0, fail=0 아님)와 stdout+stderr 를 본다. 예: --@run-with -g0 => fail; out!~:20:
  --@compile 인자 => out~정규식[; out!~정규식 ...]
                    `luau-compile 인자 파일` 출력(stdout+stderr)을 본다. --remarks 면 `-- remark:` 줄만 본다(소스도 함께 찍히므로).
                    예: --@compile --remarks -O2 => out~loop unroll succeeded
  --@inline-remarks=2  `luau-compile --remarks -O<n>` 로, 줄 끝 주석의 [inline:ok|variadic|multret|expensive|none] 과 그 줄 위 remark 를 맞춘다
  --@codegen 인자 => 단언[; 단언 ...]
                    `luau-compile --codegen 인자 --record-stats=function` 의 함수별 asmSize 로 단언한다. 인자 `+native` 는 파일 앞에
                    `--!native` 한 줄을 붙인 사본을 쓴다는 뜻. 단언: `이름[*정수] (<|<=|>|>=|==) 이름[*정수]`, `names = a,b,…`
                    (컴파일된 함수 이름 집합, 최상위는 [top-level]). asmSize 는 아키텍처(x64/a64)마다 다르므로 비율로만 단언한다.
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

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISE = os.environ.get("MISE_DATA_DIR", "/code/.local/share/mise")
DEFS = os.path.join(KB, "typedefs", "globalTypes.d.luau")
DIAG = re.compile(r"^(?P<f>.+?)\((?P<l>\d+),(?P<c>\d+)\): (?P<k>TypeError|SyntaxError): (?P<m>.*)$")
LOC_ANY = re.compile(r"^.+?\(\d+,\d+\): ")
MARK = re.compile(r"(expect-error|bug-present)(?::\s*(.*?))?\s*(?:\[(<=|>=|<|>|=)\s*(\d+\.\d+(?:\.\d+)?)\])?\s*$")
HEAD_LINES = 30
MULTI = ("run-with", "compile", "codegen")  # 여러 줄 쓸 수 있는 머리
EXEC_HEADS = ("run", "run-opt", "run-with", "compile", "inline-remarks", "codegen")


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
    n = min(len(a), len(b))  # 0.742 와 1.70 처럼 자리 수가 다르면 짧은 쪽에 맞춘다
    a, b = a[:n], b[:n]
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b}[op]


def parse(path):
    src = open(path, encoding="utf-8").read().split("\n")
    heads, multi = {}, {}
    for line in src[:HEAD_LINES]:
        m = re.match(r"^--@([\w-]+)(?:[= ](.*))?$", line.strip())
        if m:
            k, val = m.group(1), (m.group(2) or "").strip()
            heads[k] = val
            multi.setdefault(k, []).append(val)
    heads["_multi"] = multi
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


def is_roblox(heads, mode):
    return mode == "roblox" or "lsp-roblox" in heads


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


def sh(args, cwd, limit=2097152, timeout=120):
    """메모리(KB, ulimit -v)·시간 상한 안에서 실행. 반환 (rc, stdout+stderr)."""
    pre = f"ulimit -v {limit}; " if limit else ""
    cmd = pre + f"exec timeout {timeout} " + " ".join(subprocess.list2cmdline([a]) for a in args)
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


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
        rc, out = sh(args, d)
        if rc not in (0, 1):
            return None, f"luau-analyze rc={rc}: {out[:200]}"
        return diagnostics(out), None


def analyze_roblox(path, heads, lv, defs):
    """luau-lsp analyze --platform=roblox. 함정 둘(2026-11-10 luau-lsp 1.70.1 실측):
    같은 --flag: 가 두 번 오면 앞의 값이 이긴다 → 머리 인자를 기본값보다 앞에 두고, 머리에 있는 플래그는 기본값에서 뺀다.
    --platform 을 두 번 주면 'Duplicate argument' 로 실패한다 → 머리에 있으면 기본값을 넣지 않는다."""
    b = lsp_bin(lv)
    if not os.path.exists(b):
        return None, f"luau-lsp {lv} 가 없음: {b}"
    with tempfile.TemporaryDirectory(prefix="luau-kb-rbx-") as d:
        dst = os.path.join(d, os.path.basename(path))
        shutil.copy(path, dst)
        extra = heads.get("args", "").split()
        given = {x.split("=", 1)[0] for x in extra}
        defaults = []
        if not any(x.startswith("--platform") for x in extra):
            defaults.append("--platform=roblox")
        if not any(x.startswith("--definitions") for x in extra):
            defaults.append(f"--definitions={defs}")
        if "--flag:LuauSolverV2" not in given:
            defaults.append("--flag:LuauSolverV2=true")
        if "sourcemap" in heads:
            json.loads(heads["sourcemap"])
            open(os.path.join(d, "sourcemap.json"), "w").write(heads["sourcemap"])
            extra = extra + ["--sourcemap=sourcemap.json"]
        rc, out = sh([b, "analyze"] + extra + defaults + [os.path.basename(dst)], d, limit=False, timeout=180)
        if rc not in (0, 1):
            return None, f"luau-lsp rc={rc}: {out[:200]}"
        return diagnostics(out), None


def judge(heads, marks, got, v):
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
    return errs, n_exp, n_bug


def split_spec(spec, what):
    if "=>" not in spec:
        raise ValueError(f"--@{what} 에 '=>' 가 없음: {spec!r}")
    a, b = spec.split("=>", 1)
    return a.split(), [c.strip() for c in b.split(";") if c.strip()]


def out_checks(out, checks, label):
    errs = []
    for c in checks:
        if c.startswith("out!~"):
            if re.search(c[5:], out):
                errs.append(f"{label}: 출력에 /{c[5:]}/ 가 있으면 안 됨: {out[:160]!r}")
        elif c.startswith("out~"):
            if not re.search(c[4:], out):
                errs.append(f"{label}: 출력에 /{c[4:]}/ 가 없음: {out[:160]!r}")
        else:
            errs.append(f"{label}: 모르는 검사 {c!r}")
    return errs


INLINE = [("inlining succeeded", "ok"), ("function is variadic", "variadic"),
          ("fixed returns to multret", "multret"), ("too expensive", "expensive")]


def inline_check(out):
    errs, n, rem = [], 0, ""
    for line in out.splitlines():
        if "-- remark:" in line:
            if "-- remark: inlining" in line:
                rem += line + "\n"
            continue
        m = re.search(r"\[inline:([a-z]+)\]", line)
        if m:
            n += 1
            got = next((t for k, t in INLINE if k in rem), "none")
            if got != m.group(1):
                errs.append(f"inline: {line.strip()[:80]} → got={got}")
        rem = ""
    if n == 0:
        errs.append("inline: [inline:…] 태그가 하나도 검사되지 않음")
    return errs, n


SIZE_TERM = r"(\[[\w -]+\]|[A-Za-z_]\w*)(?:\*(\d+))?"
SIZE_CMP = re.compile(rf"^{SIZE_TERM}\s*(<=|>=|==|<|>)\s*{SIZE_TERM}$")


def codegen_check(sizes, asserts, label):
    errs = []
    for a in asserts:
        if a.startswith("names"):
            want = sorted(x.strip() for x in a.split("=", 1)[1].split(",") if x.strip())
            have = sorted(sizes)
            if want != have:
                errs.append(f"{label}: 함수 목록 {have} ≠ {want}")
            continue
        m = SIZE_CMP.match(a)
        if not m:
            errs.append(f"{label}: 단언 문법 오류 {a!r}")
            continue
        n1, k1, op, n2, k2 = m.groups()
        if n1 not in sizes or n2 not in sizes:
            errs.append(f"{label}: 함수 이름 없음 {a!r} (있는 것: {sorted(sizes)})")
            continue
        x, y = sizes[n1] * int(k1 or 1), sizes[n2] * int(k2 or 1)
        ok = {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y, "==": x == y}[op]
        if not ok:
            errs.append(f"{label}: {a} 거짓 ({n1}={sizes[n1]}, {n2}={sizes[n2]})")
    return errs


def run_execs(path, heads, v):
    """검사 통과 뒤의 실행 머리들. 반환 (에러 목록, 실행한 검사 수)."""
    errs, n, ran = [], 0, False
    multi = heads["_multi"]
    luau = os.path.join(tool_dir(v), "luau")
    comp = os.path.join(tool_dir(v), "luau-compile")
    with tempfile.TemporaryDirectory(prefix="luau-kb-run-") as d:
        name = os.path.basename(path)
        shutil.copy(path, os.path.join(d, name))
        if "run" in heads:
            ran = True
            if heads["run"] == "lune":
                rc, out = sh([lune_bin(), "run", name], d, limit=False, timeout=60)
            else:
                rc, out = sh([luau, name], d, timeout=60)
            if rc:
                errs.append(f"실행 실패 rc={rc}: {out[:200]}")
        runs = [([f"-O{lv.strip()}"], ["ok"], f"run-opt={lv.strip()}")
                for spec in multi.get("run-opt", []) for lv in spec.split(",") if lv.strip()]
        for spec in multi.get("run-with", []):
            args, checks = split_spec(spec, "run-with")
            runs.append((args, checks, "run-with " + " ".join(args)))
        for args, checks, label in runs:
            n += 1
            want, rest = checks[0], checks[1:]
            if want not in ("ok", "fail"):
                errs.append(f"{label}: 기대는 ok 나 fail 로 시작해야 함: {checks}")
                continue
            rc, out = sh([luau] + args + [name], d, limit=0 if "--codegen" in args else 2097152, timeout=60)
            if (rc == 0) != (want == "ok"):
                errs.append(f"{label}: 기대 {want}, rc={rc}: {out[:200]}")
            errs += out_checks(out, rest, label)
        for spec in multi.get("compile", []):
            n += 1
            args, checks = split_spec(spec, "compile")
            rc, out = sh([comp] + args + [name], d, timeout=60)
            if rc:
                errs.append(f"compile {' '.join(args)}: rc={rc}: {out[:200]}")
            if "--remarks" in args:  # remarks 모드는 소스(머리 주석 포함)를 함께 찍으므로 remark 줄만 본다
                out = "\n".join(l for l in out.splitlines() if "-- remark:" in l)
            errs += out_checks(out, checks, "compile " + " ".join(args))
        if "inline-remarks" in heads:
            n += 1
            lv = heads["inline-remarks"] or "2"
            rc, out = sh([comp, "--remarks", f"-O{lv}", name], d, timeout=60)
            e, k = inline_check(out)
            errs += ([f"inline-remarks rc={rc}"] if rc else []) + e
        for spec in multi.get("codegen", []):
            n += 1
            args, asserts = split_spec(spec, "codegen")
            label = "codegen " + " ".join(args)
            target = name
            if "+native" in args:
                args = [a for a in args if a != "+native"]
                target = "native-" + name
                open(os.path.join(d, target), "w", encoding="utf-8").write(
                    "--!native\n" + open(os.path.join(d, name), encoding="utf-8").read())
            stats = os.path.join(d, "stats.json")
            rc, out = sh([comp, "--codegen"] + args + ["--record-stats=function", f"--stats-file={stats}", target], d, limit=0, timeout=60)
            if rc or not os.path.exists(stats):
                errs.append(f"{label}: rc={rc}: {out[:200]}")
                continue
            sizes = {}
            for fv in json.load(open(stats)).values():
                for fn in fv["lowerStats"]["functions"]:
                    sizes[fn["name"].replace("[top level]", "[top-level]")] = fn["asmSize"]
            os.remove(stats)
            errs += codegen_check(sizes, asserts, label)
    return errs, n, ran


def check(path, v, mode="luau", defs=DEFS):
    src, heads, marks = parse(path)
    rbx = is_roblox(heads, mode)
    if rbx:
        got, err = analyze_roblox(path, heads, v, defs)
    else:
        got, err = analyze(path, heads, v)
    if err:
        return [err], {}
    errs, n_exp, n_bug = judge(heads, marks, got, v)
    n_exec, ran = 0, False
    if rbx:
        bad = [k for k in EXEC_HEADS if k in heads]
        if bad:
            errs.append(f"Roblox 모드에서는 실행 머리를 쓸 수 없음: {bad} (순수 Luau 스니펫이면 --mode roblox 없이 검사한다)")
    elif not errs:
        try:
            e, n_exec, ran = run_execs(path, heads, v)
        except ValueError as ex:
            e = [str(ex)]
        errs += e
    return errs, {"E": n_exp, "B": n_bug, "run": ran, "X": n_exec}


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


def cell_of(e, info):
    cell = "FAIL" if e else "ok"
    if info:
        cell += f" (E{info['E']} B{info['B']}{' run' if info['run'] else ''}{' X' + str(info['X']) if info['X'] else ''})"
    return cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--luau", default=os.environ.get("LUAU_VER", "0.742"))
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--lsp", default="", help="참고 열: 순수 Luau 파일을 이 luau-lsp 버전으로도 돌려 비교")
    ap.add_argument("--mode", choices=["luau", "roblox"], default="luau")
    ap.add_argument("--rbx-lsp", default="", help="Roblox 모드 파일의 luau-lsp 버전들(기본: 1.70.1,1.69.0 중 설치된 것)")
    ap.add_argument("--defs", default=DEFS)
    a = ap.parse_args()
    files = a.files or sys.exit("파일을 주세요: python3 -I tools/check_snippets.py snippets/*.luau")
    vers = [x.strip() for x in a.luau.split(",") if x.strip()]
    rvers = [x.strip() for x in a.rbx_lsp.split(",") if x.strip()] or \
        [x for x in ("1.70.1", "1.69.0") if os.path.exists(lsp_bin(x))]
    kinds = {f: is_roblox(parse(f)[1], a.mode) for f in files}
    if any(not r for r in kinds.values()):
        for v in vers:
            if not os.path.exists(os.path.join(tool_dir(v), "luau-analyze")):
                sys.exit(f"luau {v} 의 luau-analyze 가 없음: {tool_dir(v)}")
    if any(kinds.values()):
        if not rvers:
            sys.exit("Roblox 모드 파일이 있는데 luau-lsp 가 없음 (--rbx-lsp)")
        for v in rvers:
            if not os.path.exists(lsp_bin(v)):
                sys.exit(f"luau-lsp {v} 가 없음: {lsp_bin(v)}")
        if not os.path.exists(a.defs):
            sys.exit(f"정의 파일이 없음: {a.defs}")
    bad = 0
    rows, rrows = [], []
    for f in files:
        rbx = kinds[f]
        cells = []
        for v in (rvers if rbx else vers):
            e, info = check(f, v, "roblox" if rbx else "luau", a.defs)
            bad |= bool(e)
            if not a.table:
                print(("FAIL " if e else "ok   ") + (f"[lsp {v}] " if rbx else f"[{v}] ") + os.path.relpath(f))
                for x in e:
                    print("     ", x)
            cells.append(cell_of(e, info))
        if rbx:
            rrows.append((os.path.basename(f), cells))
            continue
        if a.lsp:
            cells.append(lsp_info(f, a.lsp))
        rows.append((os.path.basename(f), cells))
    if a.table:
        if rows:
            head = ["스니펫"] + [f"luau {v}" for v in vers] + ([f"luau-lsp {a.lsp} (참고)"] if a.lsp else [])
            print("| " + " | ".join(head) + " |")
            print("|" + "---|" * len(head))
            for name, cells in rows:
                print(f"| `{name}` | " + " | ".join(cells) + " |")
        if rrows:
            if rows:
                print()
            head = ["스니펫 (Roblox 모드)"] + [f"luau-lsp {v}" for v in rvers]
            print("| " + " | ".join(head) + " |")
            print("|" + "---|" * len(head))
            for name, cells in rrows:
                print(f"| `{name}` | " + " | ".join(cells) + " |")
    sys.exit(bad)


if __name__ == "__main__":
    main()
