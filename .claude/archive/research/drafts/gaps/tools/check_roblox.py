#!/usr/bin/env python3
"""Roblox 스니펫 검증기(초안). luau-kb/tools/check_snippets.py 의 표식 문법을 그대로 쓰되,
검사기를 luau-lsp analyze --platform=roblox --definitions=<globalTypes> 로 바꾼다.

사용: python3 -I check_roblox.py [--lsp 1.70.1,1.69.0] [--defs PATH] 파일...
- 표식(expect-error / bug-present / 버전 조건)은 check_snippets.py 와 같다. 버전 조건은 luau-lsp 버전과 비교한다.
- 머리 `--@args ...` 는 luau-lsp analyze 에 덧붙인다(예: --flag:LuauSolverV2=false).
- 기본은 새 솔버(--flag:LuauSolverV2=true), --platform=roblox. 머리 --@args 에 같은 플래그가 있으면 기본값을 넣지 않는다.
- 머리 `--@sourcemap {json}` 은 Rojo 형식 sourcemap 을 임시 파일로 두고 --sourcemap 으로 넘긴다.
- 린트는 판정하지 않는다.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile

KB = "/code/Projects/luau-kb/tools/check_snippets.py"
spec = importlib.util.spec_from_file_location("cs", KB)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)
DEFS = "/code/Projects/luau-kb/typedefs/globalTypes.d.luau"


def run(path, lv, defs):
    src, heads, marks = cs.parse(path)
    with tempfile.TemporaryDirectory(prefix="gaps-rbx-") as d:
        dst = os.path.join(d, os.path.basename(path))
        open(dst, "w").write("\n".join(src))
        extra = heads.get("args", "").split()
        # luau-lsp 는 같은 플래그가 두 번 오면 앞의 것을 쓴다(2026-11-10 1.70.1 실측). 머리에서 솔버를 정하면 기본값을 빼야 한다.
        solver = [] if any("LuauSolverV2" in x for x in extra) else ["--flag:LuauSolverV2=true"]
        # --platform 은 두 번 주면 "Duplicate argument" 로 실패한다. 머리에서 주면 기본값을 뺀다.
        platform = [] if any(x.startswith("--platform") for x in extra) else ["--platform=roblox"]
        if "sourcemap" in heads:  # --@sourcemap {json}: Rojo 형식 sourcemap 을 임시 파일로 두고 넘긴다
            open(os.path.join(d, "sourcemap.json"), "w").write(heads["sourcemap"])
            extra = extra + ["--sourcemap=sourcemap.json"]
        args = [cs.lsp_bin(lv), "analyze"] + platform + [f"--definitions={defs}"] + solver + extra + [os.path.basename(dst)]
        r = subprocess.run(args, capture_output=True, text=True, cwd=d, timeout=180)
    if r.returncode not in (0, 1):
        return [f"luau-lsp rc={r.returncode}: {(r.stderr or r.stdout)[:200]}"], {}
    got = cs.diagnostics(r.stdout + r.stderr)
    active = {ln: [c for c in cl if cs.cond_ok(c[2], c[3], lv)] for ln, cl in marks.items()}
    active = {ln: cl for ln, cl in active.items() if cl}
    errs, n_exp, n_bug = [], 0, 0
    for ln, cl in active.items():
        if len(cl) > 1:
            errs.append(f"{ln}: 표식 둘 이상")
            continue
        kind, sub, _, _ = cl[0]
        dd = got.get(ln, [])
        if kind == "expect-error":
            n_exp += 1
            if not dd:
                errs.append(f"{ln}: expect-error 인데 0건")
            elif sub and not any(sub in x for x in dd):
                errs.append(f"{ln}: 메시지에 {sub!r} 없음: {dd[0][:200]}")
        else:
            n_bug += 1
            if dd:
                errs.append(f"{ln}: bug-present 인데 진단: {dd[0][:200]}")
    for ln, dd in sorted(got.items()):
        if ln not in active:
            errs.append(f"{ln}: 예상 못한 진단: {dd[0][:200]}")
    if n_bug and not n_exp and "no-control" not in heads:
        errs.append("bug-present 대조군 없음")
    return errs, {"E": n_exp, "B": n_bug}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--lsp", default="1.70.1")
    ap.add_argument("--defs", default=DEFS)
    a = ap.parse_args()
    bad = 0
    for f in a.files:
        for lv in [x for x in a.lsp.split(",") if x]:
            e, info = run(f, lv, a.defs)
            bad |= bool(e)
            print(("FAIL " if e else "ok   ") + f"[lsp {lv}] {os.path.basename(f)} {info}")
            for x in e:
                print("     ", x)
    sys.exit(bad)


if __name__ == "__main__":
    main()
