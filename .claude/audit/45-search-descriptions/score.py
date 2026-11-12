"""Score pick-*.json against gold. python3 -I score.py"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import setup as S
items = S.queries()
base = Path("/tmp/cr45/base")
VARS = ["1_current", "2_top3", "3_cap60", "0_title_only", "4S_EN_cap120", "4S_EN_cap200"]
cost = 0; res = {}
for v in VARS:
    for it in items:
        j = json.loads((RAW / f"pick-{v}-{it['id']}.json").read_text())
        cost += j.get("total_cost_usd", 0)
        ans = (j.get("result") or "").strip()
        out = (RAW / f"v-{v}-{it['id']}.txt").read_text()
        leg = legend_of(out)
        bt = Path("/tmp/cr45/ens") if v.startswith("4S") else base
        pref = str(bt / "code/Projects/claude-doctor/") if it["set"] == "doc" else str(bt / "luau-kb/")
        picked = None; docs = []
        for loc in result_locs(out):
            d = doc_of(loc, leg); rel = d[len(pref):].lstrip("/") if d.startswith(pref) else d
            docs.append(rel)
        # match answer to the longest listed path contained in it
        a2 = ans.replace("`", "")
        cand = [(len(l.rsplit(":", 1)[0]), l) for l in result_locs(out) if l.rsplit(":", 1)[0] in a2 or doc_of(l, leg) in a2]
        if cand:
            loc = max(cand)[1]; d = doc_of(loc, leg); picked = d[len(pref):].lstrip("/") if d.startswith(pref) else d
        ing = any(d in it["gold"] for d in docs)
        res[(v, it["id"])] = (picked in it["gold"] if picked else False, ing, ans, picked)
print(f"cost of pick calls: ${cost:.2f}")
for grp in ("doc", "pack", "all"):
    ids = [i["id"] for i in items if grp == "all" or i["set"] == grp]
    print(f"\n{grp} ({len(ids)} q)")
    print("| variant | correct | gold shown in top8 | correct / gold shown |\n|---|---|---|---|")
    for v in VARS:
        c = sum(res[(v, i)][0] for i in ids); g = sum(res[(v, i)][1] for i in ids)
        cg = sum(res[(v, i)][0] and res[(v, i)][1] for i in ids)
        print(f"| {v} | {c}/{len(ids)} | {g} | {cg}/{g} |")
print("\nper question (V=picked gold, x=wrong, -=gold not shown):")
for i in items:
    row = []
    for v in VARS:
        ok, ing, ans, p = res[(v, i["id"])]
        row.append("V" if ok else ("x" if ing else "-"))
    print(i["id"], " ".join(row), "|", [res[(v, i['id'])][3] and res[(v, i['id'])][3][-40:] for v in VARS[:1] + VARS[4:5]])
unmatched = [(k, r[2][:80]) for k, r in res.items() if r[3] is None]
print("unmatched answers:", unmatched)
