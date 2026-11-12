"""Write English-variant replacement files into /tmp/cr45/over-<mode>/{doc,pack}/<rel>.
mode d  : frontmatter description of doc-level results only (what the task literally asks)
mode s  : d + `summary:` meta line under every shown section heading (what result lines really show)
mode sk : s + Korean key terms added to doc `keywords` (variant 4b)
python3 -I build_over.py <d|s|sk>"""
import json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from translations import T, KW
from common import RAW

mode = sys.argv[1]
items = json.load(open(RAW / "to-translate.json"))
base = Path("/tmp/cr45/base")
roots = {"doc": base / "code/Projects/claude-doctor", "pack": base / "luau-kb"}
out = Path(f"/tmp/cr45/over-{mode}")
shutil.rmtree(out, ignore_errors=True)
q = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

def split_fm(text):
    if text.startswith("---\n"):
        e = text.find("\n---", 4)
        if e > 0:
            return text[4:e].split("\n"), text[e + 4:].lstrip("\n") if False else text[e + 4:]
    return None, text

def set_fm(text, desc, kws):
    fm, rest = split_fm(text)
    if fm is None:
        fm = []
        rest = "\n" + text
    # drop old description key (and its continuation lines)
    new, skip = [], False
    for ln in fm:
        if re.match(r"^description\s*:", ln):
            skip = True; continue
        if skip and re.match(r"^[A-Za-z_][\w-]*\s*:", ln): skip = False
        if skip and (ln.startswith(" ") or ln.startswith("\t") or not ln.strip()): continue
        skip = False
        new.append(ln)
    new.append(f"description: {q(desc)}")
    if kws:
        idx = next((i for i, l in enumerate(new) if re.match(r"^keywords\s*:", l)), None)
        add = [f"  - {q(k)}" for k in kws]
        if idx is None:
            new += ["keywords:"] + add
        else:
            if new[idx].strip() != "keywords:":  # inline form
                v = new[idx].split(":", 1)[1].strip()
                if v.startswith("["):
                    new[idx] = new[idx].rstrip()[:-1] + ", " + ", ".join(q(k) for k in kws) + "]"
                    add = []
            j = idx + 1
            while j < len(new) and re.match(r"^\s+-", new[j]): j += 1
            new[j:j] = add
    return "---\n" + "\n".join(new) + "\n---" + rest

files = {}
for it in items:
    n = it["n"]
    if n in (1, 81) or n not in T: continue
    files.setdefault((it["set"], it["rel"]), []).append(it)

for (st, rel), its in files.items():
    src = roots[st] / rel
    text = src.read_text()
    secs = sorted([i for i in its if i["sec"]], key=lambda i: -i["start"])
    docs = [i for i in its if not i["sec"]]
    if mode in ("s", "sk"):
        lines = text.split("\n")
        for i in secs:
            k = i["start"] - 1
            assert lines[k].lstrip().startswith("#"), (rel, i["start"], lines[k])
            lines.insert(k + 1, "summary: " + T[i["n"]])
        text = "\n".join(lines)
    if docs:
        d = docs[0]
        text = set_fm(text, T[d["n"]], KW.get(d["n"]) if mode == "sk" else None)
    t = out / st / rel
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(text)
print(mode, len(files), "files")
