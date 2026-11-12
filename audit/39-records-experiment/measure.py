#!/usr/bin/env python3
"""Baseline/after measure of the locate step (no model calls).

python3 -I measure.py --root <repo> [--map move-map.tsv] [--coderag <bin>] [--phase before|after] [--out DIR]

phase before: corpus = audit, decisions, drafts, handoff, PLAN.md, .claude/sessions (current layout).
phase after:  corpus = .claude/** plus root PLAN.md. If --map is given and the root is not moved yet,
              the moved layout is simulated by copying files to their new paths under /tmp.
Gold paths are mapped through --map (old -> new) in the after phase.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

TEXT = {".md", ".toml", ".tsv", ".txt", ".json", ".py", ".sh", ".luau", ".fragment", ".template"}
BEFORE_ROOTS = ["audit", "decisions", "drafts", "handoff", "PLAN.md", ".claude/sessions"]
HERE = Path(__file__).resolve().parent


def read_map(p):
    m = {}
    if p:
        for ln in Path(p).read_text().splitlines():
            if ln.strip() and not ln.startswith("#"):
                c = ln.split("\t")
                if len(c) >= 2 and c[0] != "old_path":
                    m[c[0]] = c[1]
    return m


def is_text(p):
    return p.suffix in TEXT or p.name.endswith(".md")


def build_tree(root, phase, mp, dest):
    """Copy the corpus into dest; return nothing. Paths inside dest are the corpus-relative paths."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    def put(src, rel):
        if "/raw/" in "/" + rel or not is_text(src):
            return
        if rel.startswith(".claude/") and rel.split("/")[-1] in ("settings.json", "settings.local.json", "session-log.json", "conventions.json"):
            return
        t = dest / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, t)
    if phase == "before":
        for r in BEFORE_ROOTS:
            s = root / r
            if s.is_file():
                put(s, r)
            elif s.is_dir():
                for f in sorted(s.rglob("*")):
                    if f.is_file():
                        put(f, str(f.relative_to(root)))
    else:
        moved = (root / ".claude" / "audit").is_dir()
        if moved or not mp:
            s = root / ".claude"
            for f in sorted(s.rglob("*")):
                if f.is_file():
                    put(f, str(f.relative_to(root)))
            if (root / "PLAN.md").is_file():
                put(root / "PLAN.md", "PLAN.md")
        else:
            for old, new in mp.items():
                s = root / old
                if s.is_file():
                    put(s, new)
            for f in sorted((root / ".claude").rglob("*")):  # files already in place (sessions, README)
                if f.is_file():
                    rel = str(f.relative_to(root))
                    if not (dest / rel).exists():
                        put(f, rel)
            if (root / "PLAN.md").is_file() and "PLAN.md" not in mp:
                put(root / "PLAN.md", "PLAN.md")


def corpus_files(tree):
    return sorted(str(f.relative_to(tree)) for f in tree.rglob("*") if f.is_file() and f.name != "coderag.toml" and ".coderag" not in f.parts)


def grep_rank(tree, terms):
    pats = [t.lower() for t in terms]
    sc = []
    for rel in corpus_files(tree):
        try:
            txt = (tree / rel).read_text(errors="strict")
        except Exception:
            continue
        n = sum(1 for ln in txt.lower().splitlines() if any(p in ln for p in pats))
        if n:
            sc.append((-n, rel))
    sc.sort()
    return [r for _, r in sc]


def grep_bytes(tree, files):
    return sum((tree / f).stat().st_size for f in files)


CONF_BEFORE = '''[[contexts.docs]]
provider = ["markdown-frontmatter"]
{targets}
'''
def tgt(mod, src, excl=None):
    o = f"\n  options = {{ exclude = {json.dumps(excl)} }}" if excl else ""
    return f'  [[contexts.docs.targets]]\n  module = "{mod}"\n  source = "{src}"{o}\n'


def write_config(tree, phase):
    """before: one target per old root (+ root target for PLAN.md). after: implicit .claude config,
    plus a root target that only sees PLAN.md in the simulated tree."""
    if phase == "before":
        t = "".join(tgt(m, m) for m in ["audit", "decisions", "drafts", "handoff"])
        t += tgt("sessions", ".claude/sessions")
        t += tgt("root", ".", ["audit", "decisions", "drafts", "handoff", ".claude", "coderag.toml", ".coderag"])
        (tree / "coderag.toml").write_text(CONF_BEFORE.format(targets=t))
        return "explicit (per-root targets + root target for PLAN.md)"
    if (tree / "PLAN.md").exists():
        t = tgt(".claude", ".claude") + tgt("root", ".", [".claude", "coderag.toml", ".coderag"])
        (tree / "coderag.toml").write_text(CONF_BEFORE.format(targets=t))
        return "explicit (.claude + root target that sees PLAN.md); implicit config alone would miss root PLAN.md"
    return "implicit"


RES = re.compile(r"^(/\S+?):(\d+)-(\d+)\s")


def run(cmd, env, cwd):
    return subprocess.run(["choom", "-n", "1000", "--", "timeout", "600"] + cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def coderag_eval(binp, tree, qs, outdir, phase):
    cache = Path(tempfile.mkdtemp(prefix="cr-cache-", dir="/tmp"))
    env = dict(os.environ, CODERAG_CACHE=str(cache))
    note = write_config(tree, phase)
    g = run([binp, "gen"], env, tree)
    (outdir / "coderag-gen.txt").write_text(g.stdout + g.stderr)
    st = run([binp, "stale"], env, tree)
    (outdir / "coderag-stale.txt").write_text(st.stdout + st.stderr)
    m = re.search(r"stale (\d+)건", st.stdout)
    stale = int(m.group(1)) if m else None
    res = {}
    for q in qs:
        r = run([binp, "search", "--abs", "--all", "--limit", "30"] + [" ".join(q["terms"])], env, tree)
        (outdir / f"coderag-{q['id']}.txt").write_text(r.stdout + r.stderr)
        files, byts = [], {}
        for ln in r.stdout.splitlines():
            m = RES.match(ln)
            if not m:
                continue
            p, a, b = m.group(1), int(m.group(2)), int(m.group(3))
            rel = os.path.relpath(p, tree)
            if rel not in byts:
                byts[rel] = 0
                files.append(rel)
            if len(files) <= 5 or rel in files[:5]:
                try:
                    lines = (tree / rel).read_text().splitlines(keepends=True)
                    byts[rel] += len("".join(lines[a - 1:b]).encode())
                except Exception:
                    pass
        top = files[:5]
        res[q["id"]] = (top, sum(byts[f] for f in top))
    shutil.rmtree(cache, ignore_errors=True)
    return res, stale, note


def score(top, goldset):
    for i, f in enumerate(top, 1):
        if f in goldset:
            return i
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--map")
    ap.add_argument("--coderag")
    ap.add_argument("--phase", choices=["before", "after"], default=None)
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    root = Path(a.root).resolve()
    out = Path(a.out)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    mp = read_map(a.map)
    phase = a.phase or ("after" if (root / ".claude" / "audit").is_dir() else "before")
    qs = json.loads((HERE / "gold.json").read_text())
    tree = Path("/tmp") / f"records-exp-{phase}"
    build_tree(root, phase, mp, tree)
    nfiles = len(corpus_files(tree))
    rows = {}
    gres = {}
    for q in qs:
        gold = {(mp.get(g["path"], g["path"]) if phase == "after" else g["path"]) for g in q["gold"]}
        top = grep_rank(tree, q["terms"])[:5]
        gres[q["id"]] = (top, grep_bytes(tree, top), gold)
    strategies = {"grep": {k: (v[0], v[1]) for k, v in gres.items()}}
    stale = None
    note = ""
    if a.coderag:
        cres, stale, note = coderag_eval(a.coderag, tree, qs, raw, phase)
        strategies["coderag"] = cres
    lines = [f"phase={phase} corpus_files={nfiles} coderag_config={note or '-'}", ""]
    lines.append("| id | gold | " + " | ".join(f"{s} rank" for s in strategies) + " |")
    lines.append("|---|---|" + "---|" * len(strategies))
    summ = {}
    for s, res in strategies.items():
        hits = 0
        mrr = 0.0
        by = 0
        for q in qs:
            top, b = res[q["id"]]
            r = score(top, gres[q["id"]][2])
            hits += bool(r)
            mrr += 1 / r if r else 0
            by += b
            rows.setdefault(q["id"], {})[s] = r
        summ[s] = (hits, mrr / len(qs), by / len(qs))
    for q in qs:
        lines.append(f"| {q['id']} | {len(q['gold'])} | " + " | ".join(str(rows[q['id']][s] or "-") for s in strategies) + " |")
    lines += ["", "| strategy | hit@5 | MRR | avg bytes of top-5 |", "|---|---|---|---|"]
    for s, (h, m, b) in summ.items():
        lines.append(f"| {s} | {h}/{len(qs)} | {m:.3f} | {b:,.0f} |")
    if stale is not None:
        lines.append(f"\ncoderag stale issues on the copy: {stale}")
    text = "\n".join(lines)
    print(text)
    (raw / f"top5-{phase}.json").write_text(json.dumps({s: {k: v[0] for k, v in r.items()} for s, r in strategies.items()}, ensure_ascii=False, indent=1))
    (out / f"{'baseline' if phase == 'before' else 'after'}.md").write_text(
        f"# {'Baseline' if phase == 'before' else 'After-move'} measure\n\nRegenerate: `python3 -I measure.py --root <repo>{' --map move-map.tsv' if a.map else ''} --coderag $HARNESS_CODERAG`\n\n" + text + "\n")


if __name__ == "__main__":
    main()
