"""Build a measured corpus (claude-doctor .claude copy + luau-kb pack copy) under /tmp/cr45/<tag> and run
the 17 queries with the current default output. Optional overrides replace files in the copies before gen.
python3 -I setup.py <tag> [--over DIR]   (DIR holds replacement files: doc/<rel> and pack/<rel>)"""
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

def build(tag, over=None):
    base = Path("/tmp/cr45") / tag
    if base.exists(): shutil.rmtree(base)
    tree = base / "code/Projects/claude-doctor"
    mp = m39.read_map(m39.HERE / "move-map.tsv")
    m39.build_tree(DOCTOR, "after", mp, tree)
    pack = base / "luau-kb"
    shutil.copytree(DOCTOR / "packs/luau-kb", pack, ignore=shutil.ignore_patterns(".coderag", ".git"))
    if over:
        for kind, root in (("doc", tree), ("pack", pack)):
            d = Path(over) / kind
            if d.is_dir():
                for f in d.rglob("*"):
                    if f.is_file():
                        t = root / f.relative_to(d); t.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, t)
    m39.write_config(tree, "after")
    proj = base / "proj"; proj.mkdir()
    (proj / "coderag.toml").write_text(f'[[packs]]\nname = "luau-kb"\npath = "{pack}"\n')
    env1 = dict(os.environ, CODERAG_CACHE=str(base / "cache1"))
    env2 = dict(os.environ, CODERAG_CACHE=str(base / "cache2"))
    r = run([BIN, "gen"], env1, tree); r2 = run([BIN, "gen"], env2, proj)
    (RAW / f"gen-{tag}.txt").write_text(r.stdout + r.stderr + r2.stdout + r2.stderr)
    return base, tree, proj, env1, env2

def queries():
    qs = json.loads((m39.HERE / "gold.json").read_text())
    mp = m39.read_map(m39.HERE / "move-map.tsv")
    items = []
    for q in qs:
        items.append(dict(id=q["id"], question=q["question"], query=" ".join(q["terms"]), set="doc",
                          gold=[mp.get(g["path"], g["path"]) for g in q["gold"]]))
    for pid, qq, qu, g in PACK_Q:
        items.append(dict(id=pid, question=qu, query=qq, set="pack", gold=g))
    return items

def search_all(tag, items, base, tree, proj, env1, env2, extra=()):
    outs = {}
    for it in items:
        if it["set"] == "doc":
            o = run([BIN, "search", "--limit", "8", it["query"]], env1, tree).stdout
        else:
            o = run([BIN, "--layer", "pack", "search", "--limit", "8", it["query"]], env2, proj).stdout
        outs[it["id"]] = o
        (RAW / f"{tag}-{it['id']}.txt").write_text(o)
    return outs

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("tag"); ap.add_argument("--over")
    a = ap.parse_args()
    items = queries()
    base, tree, proj, e1, e2 = build(a.tag, a.over)
    outs = search_all(a.tag, items, base, tree, proj, e1, e2)
    json.dump(dict(items=items, base=str(base)), open(RAW / f"{a.tag}-meta.json", "w"), ensure_ascii=False, indent=1)
    print({k: est(v) for k, v in outs.items()})
