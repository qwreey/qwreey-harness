#!/usr/bin/env python3
"""Level (L0/L1/L2) measure of `coderag search` (no model calls). Copy of audit/39 measure.py: tree building and
gold scoring are reused; the evaluation runs each question at several --level/--budget settings.

python3 -I measure.py --root <repo> --coderag <bin> [--old <bin>] [--out DIR] [--reps 3]

phase before: corpus = audit, decisions, drafts, handoff, PLAN.md, .claude/sessions (current layout).
phase after:  corpus = .claude/** plus root PLAN.md. If --map is given and the root is not moved yet,
              the moved layout is simulated by copying files to their new paths under /tmp.
Gold paths are mapped through --map (old -> new) in the after phase.
"""
import argparse, json, os, re, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

TEXT = {".md", ".toml", ".tsv", ".txt", ".json", ".py", ".sh", ".luau", ".fragment", ".template"}
BEFORE_ROOTS = ["audit", "decisions", "drafts", "handoff", "PLAN.md", ".claude/sessions"]
HERE = Path(__file__).resolve().parent
GOLD = HERE.parent / "39-records-experiment" / "gold.json"


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
BODY = re.compile(r"^  --- (/\S+?):(\d+)-(\d+) § ")
COEFF = (0.4, 1.6, 1.5)  # same coefficients as coderag docs::levels::estimate_output
SETTINGS = [("default", []), ("level0", ["--level", "0"]), ("level1", ["--level", "1"]), ("level2", ["--level", "2"])] + [
    (f"auto{b}", ["--level", "auto", "--budget", str(b)]) for b in (500, 1000, 2000, 4000)]
PACK_Q = [("luau-kb", "__index", "__index", ["skills/luau-perf/references/metatables.md"]),
          ("luau-kb", "table.freeze", "table.freeze", ["skills/luau-perf/references/metatables.md"]),
          ("luau-kb", "type function 제약", "type function", ["skills/luau-types/references/type-functions-limits.md"]),
          ("luau-kb", "debug.info", "debug.info", ["skills/luau-testing/references/optimize-levels.md", "skills/luau-style/references/errors.md"]),
          ("luau-kb", "generic 상한", "상한", ["skills/luau-types/references/generics.md"]),
          ("web-security", "SSRF redirect", "redirect", ["skills/hardening/references/outbound-connections.md"])]


def est_tokens(text):
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
    return subprocess.run(["choom", "-n", "1000", "--", "timeout", "600"] + cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def timed_search(binp, args, env, cwd, reps):
    """Run `reps` times; return (stdout of the last run, median wall seconds)."""
    ts = []
    out = ""
    for _ in range(reps):
        t = time.perf_counter()
        r = run([binp, "--abs"] + args, env, cwd)
        ts.append(time.perf_counter() - t)
        out = r.stdout
    return out, statistics.median(ts)


def parse(out):
    """Top-5 distinct docs from L0 headers, and the L2 body ranges per absolute path."""
    files, bodies = [], {}
    for ln in out.splitlines():
        m = RES.match(ln)
        if m and m.group(1) not in files:
            files.append(m.group(1))
        b = BODY.match(ln)
        if b:
            bodies.setdefault(b.group(1), []).append((int(b.group(2)), int(b.group(3))))
    levels = re.search(r"L0 (\d+) . L1 (\d+) . L2 (\d+)", out)
    return files, bodies, tuple(map(int, levels.groups())) if levels else None


def gold_lines(path, anchor):
    """1-based lines of the gold doc that contain the anchor text (heading text or a term)."""
    try:
        lines = path.read_text().splitlines()
    except Exception:
        return []
    a = anchor.lstrip("# ").strip().lower()
    return [i for i, l in enumerate(lines, 1) if a in l.lower()]


def reach(bodies, gold_abs, glines):
    """(strict, loose): strict = an L2 body of the gold doc covers a gold line; loose = the gold doc has any L2 body."""
    bs = bodies.get(gold_abs, [])
    return (any(a <= g <= b for a, b in bs for g in glines), bool(bs))


def evaluate(binp, cwd, env, items, reps):
    """items: [(id, query terms, gold abs paths, anchor lines {abs: [lines]})]. Returns {setting: rows}."""
    res = {}
    for name, extra in SETTINGS:
        rows = []
        for it in items:
            args = it["pre"] + ["search"] + extra + ["--limit", "8", it["query"]]
            out, sec = timed_search(binp, args, env, cwd, reps)
            files, bodies, lv = parse(out)
            top = files[:5]
            rank = next((i for i, f in enumerate(top, 1) if f in it["gold"]), 0)
            strict = loose = False
            for g in it["gold"]:
                s, l = reach(bodies, g, it["glines"].get(g, []))
                strict |= s if it["glines"].get(g) else l  # no resolvable gold line: fall back to any section
                loose |= l
            rows.append(dict(id=it["id"], rank=rank, bytes=len(out.encode()), tokens=est_tokens(out), sec=sec, strict=strict, loose=loose,
                             levels=lv, out=out))
        res[name] = rows
    return res


def summarize(res, n):
    lines = ["| setting | hit@5 | MRR | bytes/q | est tokens/q | gold L2 (strict) | gold L2 (any sec) | median ms | levels L0/L1/L2 per q |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, rows in res.items():
        hits = sum(1 for r in rows if r["rank"])
        mrr = sum(1 / r["rank"] for r in rows if r["rank"]) / n
        lv = [r["levels"] for r in rows if r["levels"]]
        lvs = "/".join(f"{sum(x[i] for x in lv) / len(lv):.1f}" for i in range(3)) if lv else "-"
        l2 = name.startswith("level2") or name.startswith("auto")
        st = f"{sum(r['strict'] for r in rows)}/{n}" if l2 else "-"
        lo = f"{sum(r['loose'] for r in rows)}/{n}" if l2 else "-"
        ms = statistics.median(r["sec"] for r in rows) * 1000
        lines.append(f"| {name} | {hits}/{n} | {mrr:.3f} | {statistics.mean(r['bytes'] for r in rows):,.0f} | {statistics.mean(r['tokens'] for r in rows):,.0f} | {st} | {lo} | {ms:.0f} | {lvs} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--coderag", required=True)
    ap.add_argument("--old", help="binary before the level change; its default output must equal the new default output")
    ap.add_argument("--out", default=str(HERE))
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    raw = Path(a.out) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    qs = json.loads(GOLD.read_text())
    tree = Path("/tmp") / "levels-exp-after"
    build_tree(root, "after", {}, tree)
    cache = Path(tempfile.mkdtemp(prefix="cr-cache-", dir="/tmp"))
    env = dict(os.environ, CODERAG_CACHE=str(cache))
    note = write_config(tree, "after")
    g = run([a.coderag, "gen"], env, tree)
    (raw / "gen.txt").write_text(g.stdout + g.stderr)
    items = []
    for q in qs:
        gold = {str(tree / x["path"]) if not x["path"].startswith(".claude/") else str(tree / x["path"]) for x in q["gold"]}
        gold = set()
        gl = {}
        for x in q["gold"]:
            p = x["path"] if x["path"].startswith(".claude/") else ".claude/" + x["path"]
            ap_ = str(tree / p)
            gold.add(ap_)
            gl.setdefault(ap_, []).extend(gold_lines(tree / p, x["anchor"]))
        items.append(dict(id=q["id"], query=" ".join(q["terms"]), gold=gold, glines=gl, pre=[]))
    res = evaluate(a.coderag, tree, env, items, a.reps)
    for name, rows in res.items():
        for r in rows:
            (raw / f"{name}-{r['id']}.txt").write_text(r["out"])
    text = [f"corpus_files={len(corpus_files(tree))} config={note}", "", "## 12 questions (audit/39 gold)", "", summarize(res, len(qs))]
    nolines = [r["id"] for r in res["default"] if not items[[i["id"] for i in items].index(r["id"])]["glines"]]
    miss = [(i["id"], p) for i in items for p, l in i["glines"].items() if not l]
    text.append(f"\ngold anchors with no matching line in the copy: {miss}")
    if a.old:
        same = 0
        for it in items:
            o, _ = timed_search(a.old, ["search", "--limit", "8", it["query"]], env, tree, 1)
            n, _ = timed_search(a.coderag, ["search", "--limit", "8", it["query"]], env, tree, 1)
            same += o == n
        text.append(f"default output byte-identical to old binary: {same}/{len(items)} questions")
    # per-question table for the highest-signal settings
    text += ["", "per question (rank of gold in top 5 / strict L2 reach / est tokens):", "", "| id | default | level1 | auto500 | auto1000 | auto2000 | auto4000 |", "|---|---|---|---|---|---|---|"]
    for k, it in enumerate(items):
        cells = []
        for name in ["default", "level1", "auto500", "auto1000", "auto2000", "auto4000"]:
            r = res[name][k]
            cells.append(f"{r['rank'] or '-'}/{'Y' if r['strict'] else 'n'}/{r['tokens']}")
        text.append(f"| {it['id']} | " + " | ".join(cells) + " |")
    # packs
    pitems = []
    for pack, qq, anchor, golds in PACK_Q:
        base = Path("/code/Projects/claude-doctor/packs") / pack
        gold = {str(base / x) for x in golds}
        gl = {str(base / x): gold_lines(base / x, anchor) for x in golds}
        pitems.append(dict(id=qq, query=qq, gold=gold, glines=gl, pre=["--pack", pack]))
    pcwd = Path(tempfile.mkdtemp(prefix="cr-pack-cwd-", dir="/tmp"))
    pcache = Path(tempfile.mkdtemp(prefix="cr-pack-cache-", dir="/tmp"))
    penv = dict(os.environ, CODERAG_CACHE=str(pcache))
    pres = {}
    for name, extra in SETTINGS:
        rows = []
        for it in pitems:
            args = it["pre"] + ["search"] + extra + ["--limit", "8", it["query"]]
            out, sec = timed_search(a.coderag, args, penv, pcwd, a.reps)
            files, bodies, lv = parse(out)
            top = files[:5]
            rank = next((i for i, f in enumerate(top, 1) if f in it["gold"]), 0)
            st = lo = False
            for gd in it["gold"]:
                s, l = reach(bodies, gd, it["glines"].get(gd, []))
                st |= s
                lo |= l
            rows.append(dict(id=it["id"], rank=rank, bytes=len(out.encode()), tokens=est_tokens(out), sec=sec, strict=st, loose=lo, levels=lv, out=out))
            (raw / f"pack-{name}-{re.sub(r'[^A-Za-z0-9]+', '_', it['id'])}.txt").write_text(out)
        pres[name] = rows
    text += ["", "## 6 pack queries (gold = doc chosen by grep, see README)", "", summarize(pres, len(pitems)), "",
             "| query | " + " | ".join(["default", "level1", "auto500", "auto1000", "auto2000", "auto4000"]) + " |", "|---|---|---|---|---|---|---|"]
    for k, it in enumerate(pitems):
        cells = []
        for name in ["default", "level1", "auto500", "auto1000", "auto2000", "auto4000"]:
            r = pres[name][k]
            cells.append(f"{r['rank'] or '-'}/{'Y' if r['strict'] else 'n'}/{r['tokens']}")
        text.append(f"| {it['query']} | " + " | ".join(cells) + " |")
    out = "\n".join(text)
    print(out)
    (raw / "summary.md").write_text(out + "\n")
    shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(pcache, ignore_errors=True)


if __name__ == "__main__":
    main()
