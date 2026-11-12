#!/usr/bin/env python3
"""코드 구조 측정기 (읽기 전용). 저장소 하나 이상을 받아 파일 길이, 평평한 폴더, 하드코딩 의심, 중복 블록, 성장 이력을 표로 낸다.

사용:
  python3 -I structure-scan.py /code/Projects/table-sim [다른 저장소 …] [--warn 800] [--hard 1500] [--flat 15] [--history 5] [--json]

판정 기준과 근거: luau-style references/structure.md, claude-doctor .claude/audit/12-code-structure.md.
저장소 루트에 .claude/structure.json 이 있으면 그 값(warn, hard, flat, ignore 글롭 목록)이 기본값을 덮는다.

쓰기 없음. git 은 log/show 만 쓴다(--history 를 줄 때만).
"""
import argparse
import collections
import fnmatch
import json
import os
import re
import subprocess
import sys

EXT = {".luau", ".lua", ".ts", ".tsx", ".js", ".mjs", ".go", ".py", ".kt", ".rs", ".svelte", ".vue"}
SKIP_DIRS = {"node_modules", ".git", "luau_packages", "roblox_packages", "lune_packages", "Packages", "vendor",
             "third_party", "build", "dist", "refs", ".gradle", ".pesde", "typedefs", "testdata", "worktrees",
             "parser-lua", "media", "fixtures", "__pycache__"}
# 같은 종류 파일이 모이는 것이 정상인 폴더(테스트·스토리·생성 자산). 평평해도 경고하지 않는다.
HOMOGENEOUS_DIRS = {"test", "tests", "spec", "specs", "stories", "spikes", "meshes", "assets", "examples", "gallery"}
GEN_MARK = re.compile(r"generated|do not edit|auto-?generated|@generated|손으로 고치지 않는다|만든 것:|생성기", re.I)
TEST_PATH = re.compile(r"(^|/)(tests?|specs?|spikes?|bench)(/|$)|\.(spec|test|story)\.|_test\.go$", re.I)
LITERAL_LINE = re.compile(r"""^\s*(\[?["'\w.\-]+["'\]]?\s*[=:]\s*)?(["'`].*["'`]|-?[\d.x]+[\w.]*|true|false|nil|null|\{.*\}|\[.*\])\s*[,;]?\s*(--.*|//.*)?$""")
COMMENT = re.compile(r"^\s*(--|//|#)")
TRIVIAL = re.compile(r"^(end|else|\}|\)|\},|\),|return|return nil|break|end\)|do|then|\{|\]|\];?|\}\);?)$")
IFCHAIN = re.compile(r"^\s*(if|elseif|else if|\}\s*else if)\s*\(?\s*([\w.]+)\s*===?\s*[\"']")
HEAD_LINE = re.compile(r"^(if|elseif|local|const|for|while|return|switch|case)\b")
PASCAL_PREFIX = re.compile(r"^([A-Z][a-z0-9]+)(?=[A-Z])")


def load_cfg(root, args):
    cfg = {"warn": args.warn, "hard": args.hard, "flat": args.flat, "ignore": []}
    p = os.path.join(root, ".claude", "structure.json")
    if os.path.isfile(p):
        try:
            cfg.update(json.load(open(p)))
        except Exception as e:  # 설정이 깨졌으면 기본값으로 계속하되 알린다
            print(f"! {p}: {e}", file=sys.stderr)
    return cfg


def walk(root, cfg):
    for d, ds, fs in os.walk(root):
        ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not x.endswith("-ignoreme")
                       and not (x.startswith(".") and x != ".claude") and x != ".claude")
        rel_d = os.path.relpath(d, root)
        srcs = []
        for f in sorted(fs):
            if os.path.splitext(f)[1] not in EXT or f.endswith((".d.ts", ".min.js", ".d.luau")):
                continue
            rel = os.path.normpath(os.path.join(rel_d, f))
            if any(fnmatch.fnmatch(rel, g) for g in cfg["ignore"]):
                continue
            srcs.append(f)
        yield rel_d, ds, srcs


def analyze_file(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    head = "\n".join(lines[:6])
    code = [l for l in lines if l.strip() and not COMMENT.match(l)]
    literal = sum(1 for l in code if LITERAL_LINE.match(l))
    # 같은 변수를 문자열과 비교하는 if/elseif 사슬의 최대 길이(들여쓰기마다 따로 센다 — 갈래 안의 중첩 if 는 끊지 않는다)
    chains, open_ = [], {}
    for l in lines:
        m = IFCHAIN.match(l)
        if not m:
            continue
        ind = len(l) - len(l.lstrip())
        kw, var = m.group(1), m.group(2)
        cur = open_.get(ind)
        if kw != "if" and cur and cur[0] == var:
            open_[ind] = (var, cur[1] + 1)
        else:
            if cur:
                chains.append((cur[1], cur[0]))
            open_[ind] = (var, 1)
    chains += [(n, v) for v, n in open_.values()]
    longest = max(chains, default=(0, None))
    # 같은 2줄 머리(정규화)의 반복 — 핸들러 머리 복붙 탐지
    norm = [re.sub(r"\b\d+(\.\d+)?\b", "N", re.sub(r"\"[^\"]*\"", '"S"', l.strip())) for l in code]
    norm = [l for l in norm if not TRIVIAL.match(l)]
    # 머리 줄이 분기·바인딩일 때만 센다(UI 선언 속 `Name = "S",` 같은 리터럴 나열은 데이터라 뺀다)
    pairs = collections.Counter(norm[i] + " ⏎ " + norm[i + 1] for i in range(len(norm) - 1)
                                if HEAD_LINE.match(norm[i]))
    top_pair = pairs.most_common(1)[0] if pairs else ("", 0)
    singles = collections.Counter(l for l in norm if HEAD_LINE.match(l) and len(l) > 12)
    top_line = singles.most_common(1)[0] if singles else ("", 0)
    return {
        "lines": len(lines),
        "gen": bool(GEN_MARK.search(head)),
        "literal_ratio": round(literal / len(code), 2) if code else 0.0,
        "ifchain": longest[0], "ifchain_var": longest[1],
        "repeat_pair": top_pair[1], "repeat_pair_text": top_pair[0][:120],
        "repeat_line": top_line[1], "repeat_line_text": top_line[0][:120],
        "norm": norm,
    }


def families(files):
    """같은 PascalCase 접두를 가진 파일 묶음(셋 이상). 예: ItemPick, ItemView, ItemZoneView → Item/."""
    groups = collections.defaultdict(list)
    stems = {os.path.splitext(f)[0] for f in files}
    for f in files:
        stem = os.path.splitext(f)[0]
        m = PASCAL_PREFIX.match(stem)
        key = m.group(1) if m else None
        if key:
            groups[key].append(stem)
    for stem in stems:  # 접두 그 자체인 파일도 같은 가족이다(Ref + PreRef 는 못 잡지만 Item + ItemView 는 잡는다)
        if stem in groups:
            groups[stem].append(stem)
    return {k: sorted(set(v)) for k, v in groups.items() if len(set(v)) >= 3}


def history(root, rel, limit=400):
    """git numstat 으로 커밋마다의 줄 수를 되짚는다(--follow). 최대 크기와 그 뒤의 분리(크게 준 커밋)를 찾는다."""
    try:
        out = subprocess.run(["git", "-C", root, "log", "--follow", "--numstat", "--format=@%h %ad", "--date=short",
                              f"-n{limit}", "--", rel], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None
    commits, cur = [], None
    for line in out.splitlines():
        if line.startswith("@"):
            cur = line[1:].split(" ")
            continue
        parts = line.split("\t")
        if cur and len(parts) == 3 and parts[0].isdigit():
            commits.append((cur[1], cur[0], int(parts[0]) - int(parts[1])))
            cur = None
    if not commits:
        return None
    commits.reverse()
    size, series = 0, []
    for d, h, delta in commits:
        size += delta
        series.append((d, h, size))
    peak = max(series, key=lambda x: x[2])
    drops = [(series[i][0], series[i][1], series[i - 1][2], series[i][2]) for i in range(1, len(series))
             if series[i - 1][2] - series[i][2] >= 300]
    first_over = next(((d, h) for d, h, s in series if s >= 1000), None)
    return {"commits": len(series), "first": series[0][0], "peak": peak, "drops": drops, "first_over_1000": first_over}


def scan(root, args):
    cfg = load_cfg(root, args)
    files, dirs = [], []
    for rel_d, subdirs, srcs in walk(root, cfg):
        dirs.append({"dir": rel_d, "src": len(srcs), "subdirs": len(subdirs), "families": families(srcs)})
        for f in srcs:
            rel = os.path.normpath(os.path.join(rel_d, f))
            a = analyze_file(os.path.join(root, rel))
            if a:
                a["path"] = rel
                a["test"] = bool(TEST_PATH.search(rel))
                files.append(a)
    # 파일 사이 중복(정규화 6줄 창) — 복사된 모듈 찾기
    W = 6
    win = collections.defaultdict(set)
    for a in files:
        if a["gen"] or a["test"]:
            continue
        n = a["norm"]
        for i in range(0, max(0, len(n) - W + 1)):
            win["\n".join(n[i:i + W])].add(a["path"])
    pair = collections.Counter()
    for k, ps in win.items():
        if 2 <= len(ps) <= 3:
            ps = sorted(ps)
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    pair[(ps[i], ps[j])] += 1
    for a in files:
        a.pop("norm", None)
    return cfg, files, dirs, pair


def report(root, args):
    cfg, files, dirs, pair = scan(root, args)
    name = os.path.basename(os.path.abspath(root))
    src = [f for f in files if not f["gen"] and not f["test"]]
    L = sorted(f["lines"] for f in src)
    q = lambda p: L[min(len(L) - 1, int(len(L) * p))] if L else 0
    out = {"repo": name, "cfg": cfg, "summary": {
        "src_files": len(src), "src_lines": sum(L), "p50": q(.5), "p90": q(.9), "max": L[-1] if L else 0,
        "over_warn": sum(x >= cfg["warn"] for x in L), "over_hard": sum(x >= cfg["hard"] for x in L),
        "generated": sum(f["gen"] for f in files), "tests": sum(f["test"] for f in files)}}
    big = sorted((f for f in files if not f["gen"]), key=lambda f: -f["lines"])
    out["long_files"] = [f for f in big if f["lines"] >= (cfg["warn"] * (2 if f["test"] else 1))][:20]
    out["flat_dirs"] = [d for d in dirs if d["src"] >= cfg["flat"] and d["subdirs"] <= 2
                        and os.path.basename(d["dir"]).lower() not in HOMOGENEOUS_DIRS]
    out["family_dirs"] = [d for d in dirs if d["families"] and d["src"] >= 8
                          and os.path.basename(d["dir"]).lower() not in HOMOGENEOUS_DIRS]
    out["literal_heavy"] = [f for f in src if f["lines"] >= 200 and f["literal_ratio"] >= 0.5]
    out["if_chains"] = [f for f in src if f["ifchain"] >= 8]
    out["repeated_heads"] = [f for f in src if f["repeat_pair"] >= 10 or f["repeat_line"] >= 20]
    out["copied_pairs"] = [{"a": a, "b": b, "windows": n} for (a, b), n in pair.most_common(8) if n >= 20]
    if args.history:
        out["history"] = {f["path"]: history(root, f["path"]) for f in big[:args.history] if not f["test"]}
    return out


def show(o):
    s, c = o["summary"], o["cfg"]
    print(f"## {o['repo']}  (warn {c['warn']} / hard {c['hard']} / flat {c['flat']})")
    print(f"소스 {s['src_files']}개 {s['src_lines']}줄, p50 {s['p50']} p90 {s['p90']} 최대 {s['max']}, "
          f"warn 이상 {s['over_warn']} · hard 이상 {s['over_hard']}, 생성물 {s['generated']} · 테스트 {s['tests']}")
    for title, key, fmt in [
        ("긴 파일", "long_files", lambda f: f"{f['lines']:>6}  {f['path']}" + ("  [test]" if f["test"] else "")),
        ("평평한 폴더", "flat_dirs", lambda d: f"{d['src']:>6}  {d['dir']}/  (하위 폴더 {d['subdirs']})"),
        ("접두 가족", "family_dirs", lambda d: f"{d['dir']}/  " + "; ".join(f"{k}: {', '.join(v)}" for k, v in d["families"].items())),
        ("리터럴 위주(데이터 모듈 후보)", "literal_heavy", lambda f: f"{f['lines']:>6}  {f['path']}  리터럴 {int(f['literal_ratio']*100)}%"),
        ("긴 문자열 분기 사슬", "if_chains", lambda f: f"{f['ifchain']:>6}갈래  {f['path']}  ({f['ifchain_var']})"),
        ("반복되는 두 줄 머리", "repeated_heads", lambda f: f"{f['path']}: 두 줄 {f['repeat_pair']}회 `{f['repeat_pair_text']}` / 한 줄 {f['repeat_line']}회 `{f['repeat_line_text']}`"),
        ("파일 사이 복사 의심", "copied_pairs", lambda p: f"{p['windows']:>6}창  {p['a']}  ↔  {p['b']}"),
    ]:
        if o.get(key):
            print(f"\n### {title}")
            for x in o[key]:
                print("- " + fmt(x))
    if o.get("history"):
        print("\n### 성장 이력 (git numstat 누적, --follow)")
        for p, h in o["history"].items():
            if not h:
                continue
            drops = ", ".join(f"{d} {hh} {a}→{b}" for d, hh, a, b in h["drops"]) or "없음"
            over = f"{h['first_over_1000'][0]}" if h["first_over_1000"] else "-"
            print(f"- {p}: 커밋 {h['commits']}, 시작 {h['first']}, 1000줄 넘은 날 {over}, 최대 {h['peak'][2]}({h['peak'][0]}), 크게 준 커밋 {drops}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--warn", type=int, default=800)
    ap.add_argument("--hard", type=int, default=1500)
    ap.add_argument("--flat", type=int, default=15)
    ap.add_argument("--history", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    outs = [report(r, args) for r in args.repos]
    if args.json:
        json.dump(outs, sys.stdout, ensure_ascii=False, indent=1)
    else:
        for o in outs:
            show(o)


if __name__ == "__main__":
    main()
