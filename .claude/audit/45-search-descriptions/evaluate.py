"""Run all variants (no model calls) and print token + ranking tables. Needs setup.py runs for base, end, ens, ensk first.
python3 -I evaluate.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import setup as S

items = S.queries()
def runs(tag, extra):
    meta = json.load(open(RAW / f"{tag}-meta.json")); base = Path(meta["base"])
    tree = base / "code/Projects/claude-doctor"; proj = base / "proj"
    e1 = dict(os.environ, CODERAG_CACHE=str(base / "cache1")); e2 = dict(os.environ, CODERAG_CACHE=str(base / "cache2"))
    outs = {}
    for it in items:
        if it["set"] == "doc":
            o = run([BIN, "search", "--limit", "8"] + extra + [it["query"]], e1, tree).stdout
        else:
            o = run([BIN, "--layer", "pack", "search", "--limit", "8"] + extra + [it["query"]], e2, proj).stdout
        outs[it["id"]] = o
    return outs, base

V = {}  # name -> (outs, base)
for name, tag, extra in [("1 current", "base", []), ("3 cap60", "base", ["--desc-max", "60"]), ("0 title-only", "base", ["--desc-max", "0"]),
                         ("4d desc EN, cap120", "end", []), ("4S EN, cap120", "ens", []), ("4S EN, cap200", "ens", ["--desc-max", "200"]),
                         ("4b EN+KO kw, cap120", "ensk", []), ("4b EN+KO kw, cap200", "ensk", ["--desc-max", "200"])]:
    V[name] = runs(tag, extra)
b = V["1 current"][0]
V["2 top3"] = ({k: v_top(o, 3) for k, o in b.items()}, V["1 current"][1])
for name, (outs, bs) in V.items():
    for k, o in outs.items():
        (RAW / f"v-{re.sub(r'[^A-Za-z0-9]+', '_', name)}-{k}.txt").write_text(o)

def rank(it, out, base):
    leg = legend_of(out)
    pref = str(base / "code/Projects/claude-doctor/") if it["set"] == "doc" else str(base / "luau-kb/")
    docs = []
    for loc in result_locs(out):
        d = doc_of(loc, leg)
        rel = d[len(pref):].lstrip("/") if d.startswith(pref) else d
        if rel not in docs: docs.append(rel)
    r = next((i for i, d in enumerate(docs, 1) if d in it["gold"]), 0)
    return r, docs

def table(group):
    its = [i for i in items if i["set"] == group]
    print(f"\n### {group} ({len(its)} queries): tokens/query, hit@5, MRR(top5), gold rank per query")
    rows = []
    order = ["1 current", "2 top3", "3 cap60", "0 title-only", "4d desc EN, cap120", "4S EN, cap120", "4S EN, cap200", "4b EN+KO kw, cap120", "4b EN+KO kw, cap200"]
    base_docs = {}
    for name in order:
        outs, bs = V[name]
        tk = sum(est(outs[i["id"]]) for i in its) / len(its)
        rk = []
        same = 0
        for i in its:
            r, docs = rank(i, outs[i["id"]], bs)
            rk.append(r)
            if name == "1 current": base_docs[i["id"]] = docs
            same += docs[:8] == base_docs[i["id"]][:8]
        hit = sum(1 for r in rk if 0 < r <= 5); mrr = sum(1 / r for r in rk if 0 < r <= 5) / len(its)
        rows.append((name, tk, hit, mrr, " ".join(str(r) for r in rk), same))
    t0 = rows[0][1]
    print("| variant | tok/query | vs 1 | hit@5 | MRR | same doc order as 1 | gold ranks |\n|---|---|---|---|---|---|---|")
    for n, tk, h, m, rk, s in rows:
        print(f"| {n} | {tk:,.0f} | {tk / t0 - 1:+.0%} | {h}/{len(its)} | {m:.3f} | {s}/{len(its)} | {rk} |")
table("doc"); table("pack")
