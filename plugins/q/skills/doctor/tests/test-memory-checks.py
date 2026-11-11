#!/usr/bin/env python3
"""doctor 항목 10(memory_checks.py, memory_move.py) 회귀. 실행: python3 -I test-memory-checks.py  (exit 0 = 통과)

임시 config(projects/<키>/memory)와 임시 작업 트리로 MEM-ORPHAN(짝 후보), MEM-REPO, MEM-SIZE 와 옮기기 dry-run/apply 를 본다. 실제 ~/.claude 는 읽지 않는다.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
LIB = SCRIPTS  # memory_signals.py 사본이 scan.py 옆에 있다


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ms = load(os.path.join(LIB, "memory_signals.py"), "memory_signals")
mc = load(os.path.join(SCRIPTS, "memory_checks.py"), "memory_checks")
T = tempfile.mkdtemp(prefix="mem-doctor-")
CFG = os.path.join(T, "cfg")
WORK = os.path.join(T, "work")
res = []
found = []


def check(name, ok):
    res.append((name, bool(ok)))


def add(item, sev, code, where, msg, ref=None):
    found.append((sev, code, str(where), msg))


def mem(path_for_key, files, jsonl_cwd=None):
    d = os.path.join(CFG, "projects", ms.key_of(path_for_key), "memory")
    os.makedirs(d, exist_ok=True)
    for n, t in files.items():
        open(os.path.join(d, n), "w").write(t)
    if jsonl_cwd:
        open(os.path.join(os.path.dirname(d), "s.jsonl"), "w").write('{"type":"user","cwd":"%s"}\n' % jsonl_cwd)
    return d


REPO_NOTE = "---\nname: b\ntype: project\n---\nIn this repo build with `make all`; parser is src/parser.py\n"
PERS_NOTE = "---\nname: u\ntype: user\n---\nPrefers terse replies.\n"

new_repo = os.path.join(WORK, "game")
os.makedirs(os.path.join(new_repo, ".git"))
old_path = os.path.join(T, "old-place", "game")  # gone
mem(new_repo, {"MEMORY.md": "- [p](p.md)\n", "p.md": PERS_NOTE})
mem(old_path, {"MEMORY.md": "- [b](b.md)\n", "b.md": REPO_NOTE}, jsonl_cwd=old_path)
mem(os.path.join(T, "scratch", "gone-x"), {"MEMORY.md": "- x\n"})  # orphan, no candidate
big = "".join(f"- [n{i}](n{i}.md) entry\n" for i in range(210))
mem(os.path.join(WORK, "big"), {"MEMORY.md": big})
os.makedirs(os.path.join(WORK, "big"))
near = "".join(f"- [n{i}](n{i}.md) entry\n" for i in range(165))
mem(os.path.join(WORK, "near"), {"MEMORY.md": near})
os.makedirs(os.path.join(WORK, "near"))
mem(os.path.join(WORK, "emptyonly"), {})  # empty memory dir: ignored
os.makedirs(os.path.join(CFG, "projects", "-nomem", "memory"))

# user mode: all keys
mc.run(add, ms, CFG, user=True)
orph = [f for f in found if f[1] == "MEM-ORPHAN"]
check("user mode: 2 orphans with memory", len(orph) == 2)
check("orphan pairs by dir name", any("game" in f[3] and new_repo in f[3] for f in orph))
check("orphan without candidate says so", any("짝 후보 없음" in f[3] for f in orph))
check("MEM-REPO found for orphan note", any(f[1] == "MEM-REPO" and "b.md" in f[2] for f in found))
check("personal note not flagged", not any(f[1] == "MEM-REPO" and "p.md" in f[2] for f in found))
check("MEM-SIZE over limit warns", any(f[1] == "MEM-SIZE" and f[0] == "경고" and "/big" not in f[2] and "-big" in f[2] for f in found))
check("MEM-SIZE near limit is info", any(f[1] == "MEM-SIZE" and f[0] == "정보" and "-near" in f[2] for f in found))
check("empty memory dir ignored", not any("emptyonly" in f[2] or "-nomem" in f[2] for f in found))

# repo mode: only this repo's key + orphans pairing to it
found.clear()
mc.run(add, ms, CFG, repo=Path(new_repo))
check("repo mode reports paired orphan", any(f[1] == "MEM-ORPHAN" and "b.md" not in f[2] for f in found))
check("repo mode skips unrelated keys", not any("-big" in f[2] or "-near" in f[2] for f in found))

# move tool: dry-run default, then apply
MOVE = os.path.join(SCRIPTS, "memory_move.py")
proj = os.path.join(CFG, "projects")
old_key = ms.key_of(old_path)
dst_dir = os.path.join(proj, ms.key_of(new_repo), "memory")
before = sorted(os.listdir(dst_dir))
p = subprocess.run([sys.executable, "-I", MOVE, f"--from-key={old_key}", "--to", new_repo, "--projects", proj], capture_output=True, text=True)
check("dry-run writes nothing", p.returncode == 0 and sorted(os.listdir(dst_dir)) == before and "dry-run" in p.stdout)
p = subprocess.run([sys.executable, "-I", MOVE, f"--from-key={old_key}", "--to", new_repo, "--projects", proj, "--apply"], capture_output=True, text=True)
check("apply copies new file", p.returncode == 0 and os.path.isfile(os.path.join(dst_dir, "b.md")))
check("apply keeps source", os.path.isfile(os.path.join(proj, old_key, "memory", "b.md")))
check("apply appends MEMORY.md line", "- [b](b.md)" in open(os.path.join(dst_dir, "MEMORY.md")).read() and "- [p](p.md)" in open(os.path.join(dst_dir, "MEMORY.md")).read())
open(os.path.join(proj, old_key, "memory", "p.md"), "w").write("different\n")
p = subprocess.run([sys.executable, "-I", MOVE, f"--from-key={old_key}", "--to", new_repo, "--projects", proj, "--apply"], capture_output=True, text=True)
check("conflict never overwrites", open(os.path.join(dst_dir, "p.md")).read() == PERS_NOTE and any(n.startswith("p.from-") for n in os.listdir(dst_dir)))
p = subprocess.run([sys.executable, "-I", MOVE, f"--from-key={old_key}", "--to", new_repo, "--projects", proj, "--apply"], capture_output=True, text=True)
check("rerun is idempotent", "copy " not in p.stdout.replace("copy-as", ""))

bad = [n for n, ok in res if not ok]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
print(f"{len(res) - len(bad)}/{len(res)}")
sys.exit(1 if bad else 0)
