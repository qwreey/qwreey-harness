#!/usr/bin/env python3
"""Output-size measure of `coderag search` path/tag forms (no model calls). Reuses audit/39 measure.py
(tree building, config, gold.json, --map) and the audit/43 estimator.

python3 -I measure.py --root <repo> --map <move-map.tsv> --new <bin> --old <bin> [--quad /code/Projects/quad]
"""
import argparse, importlib.util, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("m39", HERE.parent / "39-records-experiment" / "measure.py")
m39 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m39)

COEFF = (0.4, 1.6, 1.5)
HDR = re.compile(r"^(\S+?):(\d+)-(\d+)(?:\s|$)(.*)")
LEG = re.compile(r"^@(\w+) = (/.*)$")
PACK_Q = [("__index", "__index", ["skills/luau-perf/references/metatables.md"]),
          ("table.freeze", "table.freeze", ["skills/luau-perf/references/metatables.md"]),
          ("type function 제약", "type function", ["skills/luau-types/references/type-functions-limits.md"]),
          ("debug.info", "debug.info", ["skills/luau-testing/references/optimize-levels.md", "skills/luau-style/references/errors.md"]),
          ("generic 상한", "상한", ["skills/luau-types/references/generics.md"])]


def est(text):
    a = h = o = 0
    for c in text:
        if ord(c) < 128:
            a += 1
        elif 0xAC00 <= ord(c) <= 0xD7A3:
            h += 1
        else:
            o += 1
    return round(COEFF[0] * a + COEFF[1] * h + COEFF[2] * o)


def run(cmd, env, cwd):
    return subprocess.run(["choom", "-n", "1000", "--", "timeout", "600"] + cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True)


def headers(out):
    """[(location, a, b, rest)] of non-indented result lines."""
    res = []
    for ln in out.splitlines():
        m = HDR.match(ln)
        if m and not ln.startswith(" "):
            res.append(m.groups())
    return res


def abs_paths(out, cwd):
    """absolute paths of results for the old-default / --abs forms (relative ones resolved against cwd)."""
    ps = []
    for loc, *_ in headers(out):
        p = Path(loc)
        ps.append(str(p if p.is_absolute() else Path(cwd) / p))
    return ps


CONFIGS = [("old default", "old", []), ("old --abs", "old", ["--abs"]), ("new default", "new", []), ("new --abs", "new", ["--abs"]), ("new --handles", "new", ["--handles"])]
AUTO = ["--level", "auto", "--budget", "2000"]  # search-only flags go after the subcommand


def evaluate(bins, items, env, cwd_of):
    """items: [dict(id, query, pre, gold(set abs))]. Returns table rows and ranking checks."""
    tab = {}
    same_rank = True
    hit = 0
    mrr = 0.0
    for name, which, extra, tail in [(n, w, e, []) for n, w, e in CONFIGS] + [(n + " auto2000", w, e, AUTO) for n, w, e in CONFIGS]:
        toks = []
        for it in items:
            cwd = cwd_of(it)
            out = run([bins[which]] + it["pre"] + extra + ["search"] + tail + ["--limit", "8", it["query"]], env, cwd).stdout
            (HERE / "raw" / f"{re.sub(r'[^A-Za-z0-9]+', '_', name)}-{it['id']}.txt").write_text(out)
            toks.append(est(out))
            sig = [(a, b, r.split("  ")[1] if "  " in r else r) for _, a, b, r in headers(out)]
            if name == "new --abs":
                paths = abs_paths(out, cwd)
                rank = next((i for i, p in enumerate(paths[:5], 1) if p in it["gold"]), 0)
                it.setdefault("rank", rank)
                it["sig"] = sig
            if name in ("old default", "old --abs", "new default", "new --handles") or name.endswith("auto2000"):
                it.setdefault("sigs", {})[name] = sig
            it.setdefault("toks", {}).setdefault(name, []).append(est(out))
        tab[name] = sum(toks) / len(toks)
    for it in items:
        hit += bool(it["rank"])
        mrr += 1 / it["rank"] if it["rank"] else 0
        ref = it["sigs"]["old --abs"]
        for n, s in it["sigs"].items():
            # titles/lines of results, same order. Old and new differ only in path and tag text.
            if [(a, b, t) for a, b, t in s] != [(a, b, t) for a, b, t in ref] and "auto2000" not in n:
                same_rank = False
    return tab, hit, mrr / len(items), same_rank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--quad", default="/code/Projects/quad")
    a = ap.parse_args()
    bins = {"new": a.new, "old": a.old}
    root = Path(a.root).resolve()
    mp = m39.read_map(a.map)
    qs = json.loads((m39.HERE / "gold.json").read_text())
    tree = Path("/tmp/cr44/code/Projects/claude-doctor")  # root path length close to the real one
    m39.build_tree(root, "after", mp, tree)
    cache = Path(tempfile.mkdtemp(prefix="cr44-cache-", dir="/tmp"))
    env = dict(os.environ, CODERAG_CACHE=str(cache))
    m39.write_config(tree, "after")
    run([a.new, "gen"], env, tree)
    items = []
    for q in qs:
        gold = {str(tree / mp.get(g["path"], g["path"])) for g in q["gold"]}
        items.append(dict(id=q["id"], query=" ".join(q["terms"]), pre=[], gold=gold))
    tab1, h1, m1, ok1 = evaluate(bins, items, env, lambda it: tree)
    # pack queries from quad (project + pack layers; read-only; cache in /tmp)
    qcache = Path(tempfile.mkdtemp(prefix="cr44-quad-", dir="/tmp"))
    qenv = dict(os.environ, CODERAG_CACHE=str(qcache))
    run([a.new, "gen"], qenv, a.quad)
    packbase = None
    reg = run([a.new, "pack", "list"], qenv, a.quad).stdout
    (HERE / "raw" / "pack-list.txt").write_text(reg)
    for ln in reg.splitlines():
        if ln.startswith("luau-kb"):
            m = re.search(r"(/\S*luau-kb)", ln)
            packbase = Path(m.group(1)) if m else None
    packbase = packbase or Path("/code/Projects/claude-doctor/packs/luau-kb")
    pitems = [dict(id=f"p{i}", query=q, pre=["--layer", "project,pack"], gold={str(packbase / g) for g in gs}) for i, (q, _, gs) in enumerate(PACK_Q, 1)]
    tab2, h2, m2, ok2 = evaluate(bins, pitems, qenv, lambda it: Path(a.quad))
    out = []
    for title, tab, n, h, m, ok in (("12 questions", tab1, len(items), h1, m1, ok1), ("5 luau-kb queries from quad", tab2, len(pitems), h2, m2, ok2)):
        out += [f"## {title}: hit@5 {h}/{n}, MRR {m:.3f} (new --abs run), same ranking in all configs: {ok}", "", "| config | est tokens/query | vs old default | vs old --abs |", "|---|---|---|---|"]
        for k, v in tab.items():
            out.append(f"| {k} | {v:,.0f} | {v / tab['old default'] - 1:+.0%} | {v / tab['old --abs'] - 1:+.0%} |")
        out.append("")
    text = "\n".join(out)
    print(text)
    (HERE / "raw" / "summary.md").write_text(text)
    shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(qcache, ignore_errors=True)


if __name__ == "__main__":
    main()
