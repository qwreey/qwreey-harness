#!/usr/bin/env python3
"""Check agent records under <repo>/.claude against the qwreey-conventions:agent-records convention.
Usage: python3 -I records_check.py [--root <repo>] [--json] [--strict]
Exit 0 always, except 2 with --strict when there are findings above info level.

Living folders (plan, base, research, also under packs/<pack>/) are checked; snapshot folders (audit, handoff,
sessions, session) are only measured for size, because snapshots are never edited and their links are frozen.
Same grammar is implemented once here; coderag tests reuse tests/records-fixtures.
"""
import argparse
import json
import os
import re
import sys

LIVING = ("plan", "base", "research")
STATES = ("active", "landed", "superseded", "rejected", "archived")
FILE_LIMIT = 200 * 1024
DIR_LIMIT = 5 * 1024 * 1024
# worktrees hold whole checkouts of the repo; counting them would hide real growth
SIZE_SKIP = {"worktrees"}
LINK_RX = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
STATUS_RX = re.compile(r"^(\w+)(?:\s+(in|by)\s+([^;]+?))?\s*(?:;\s*(.*))?$")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def split_frontmatter(text):
    """(frontmatter dict of raw lines, body). Only simple `key: value` lines are read."""
    m = re.match(r"---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        k = re.match(r"^([A-Za-z_-]+):\s*(.*?)\s*$", line)
        if k:
            fm[k.group(1).replace("-", "_")] = k.group(2).strip("'\"")
    return fm, text[m.end():]


def read_status(text):
    """(status string or None, superseded_by or None). Frontmatter wins, else the first line."""
    fm, body = split_frontmatter(text)
    if fm is not None:
        if "status" in fm:
            return fm["status"], fm.get("superseded_by")
        return None, fm.get("superseded_by")
    first = text.lstrip("﻿").split("\n", 1)[0]
    m = re.match(r"^status:\s*(.*?)\s*$", first)
    return (m.group(1) if m else None), None


def parse_status(value, superseded_by=None):
    """(state, kind, target, note) or (None, error message, ...). `superseded_by: X` equals `superseded by X`."""
    m = STATUS_RX.match(value.strip())
    if not m:
        return None, "unparsable status %r" % value, None, None
    state, prep, target, note = m.groups()
    if state not in STATES:
        return None, "unknown state %r (use %s)" % (state, " | ".join(STATES)), None, None
    if state == "superseded" and not prep and superseded_by:
        prep, target = "by", superseded_by
    if state == "landed" and prep != "in":
        return None, "landed needs `in <path>`", None, None
    if state == "superseded" and prep != "by":
        return None, "superseded needs `by <path|id>`", None, None
    if state in ("active", "archived") and prep:
        return None, "%s takes no target" % state, None, None
    if state == "rejected" and prep == "in":
        return None, "rejected uses `by`, not `in`", None, None
    return state, prep, (target or "").strip() or None, note


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def living_docs(claude):
    """[(abs path, in_archive)] of *.md under living folders and packs, README excluded, raw/ skipped."""
    bases = [claude]
    packs = os.path.join(claude, "packs")
    if os.path.isdir(packs):
        bases += [os.path.join(packs, p) for p in sorted(os.listdir(packs))]
    out = []
    for base in bases:
        top = list(LIVING) + ["archive"]
        for name in top:
            d = os.path.join(base, name)
            for dp, dns, fns in os.walk(d):
                dns[:] = sorted(x for x in dns if x != "raw")
                for fn in sorted(fns):
                    if fn.endswith(".md") and fn != "README.md":
                        out.append((os.path.join(dp, fn), name == "archive"))
    return out


def gitignored_raw(root):
    """True when the repo's own .gitignore mentions a raw/ pattern. Plain text parse: no git needed, fixture-safe."""
    try:
        lines = (read(os.path.join(root, ".gitignore")) or "").splitlines()
    except OSError:
        return False
    return any(re.search(r"(^|/)raw/?$", l.strip()) for l in lines if l.strip() and not l.startswith("#"))


def folder_status(path, claude):
    """True when a README.md in the doc's folder or an ancestor below .claude/<top>/ carries a status line."""
    d = os.path.dirname(path)
    while os.path.dirname(d) != claude and d.startswith(claude + os.sep):
        readme = os.path.join(d, "README.md")
        if readme != path and os.path.isfile(readme):
            text = read(readme)
            if text is not None and read_status(text)[0] is not None:
                return True
        d = os.path.dirname(d)
    return False


def check(root):
    root = os.path.abspath(root)
    claude = os.path.join(root, ".claude")
    F = []

    def add(code, sev, path, msg):
        F.append({"code": code, "severity": sev, "path": os.path.relpath(path, root) if path else "", "message": msg})

    if not os.path.isdir(claude):
        return F
    for path, in_archive in living_docs(claude):
        text = read(path)
        if text is None:
            continue
        value, sup_by = read_status(text)
        if value is None:
            # A folder's README status covers the files in that folder, and a file under archive/ is finished by
            # where it is; flagging those would bury the docs that really lack a status.
            if not in_archive and not folder_status(path, claude):
                add("REC-STATUS-MISSING", "info", path, "living doc has no status line (frontmatter or first line)")
            state = None
        else:
            state, kind, target, _note = parse_status(value, sup_by)
            if state is None:
                add("REC-STATUS-BAD", "warn", path, kind)
            elif target and ("/" in target or target.endswith(".md")):
                cands = [os.path.join(os.path.dirname(path), target), os.path.join(claude, target), os.path.join(root, target)]
                if not any(os.path.exists(c) for c in cands):
                    add("REC-TARGET-MISSING", "warn", path, "status target %s does not exist" % target)
        if state and state != "active" and not in_archive:
            add("REC-FINISHED-OUTSIDE-ARCHIVE", "warn", path, "status %s but not under archive/" % state)
        if state == "active" and in_archive:
            add("REC-ACTIVE-IN-ARCHIVE", "warn", path, "active doc under archive/")
        if not in_archive:
            for tgt in LINK_RX.findall(strip_code(text)):
                t = tgt.split("#", 1)[0]
                if not t or re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) or t.startswith("<"):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), t))):
                    add("REC-LINK-BROKEN", "warn", path, "broken link %s" % tgt)
            readme = os.path.join(os.path.dirname(path), "README.md")
            if os.path.isfile(readme):
                idx = read(readme) or ""
                rel = os.path.relpath(path, os.path.dirname(readme))
                if rel not in idx and os.path.basename(path) not in idx:
                    add("REC-INDEX-MISSING", "warn", path, "not listed in %s" % os.path.relpath(readme, root))
    # sizes
    raw_dirs = []
    for dp, dns, fns in os.walk(claude):
        dns[:] = [d for d in dns if d not in SIZE_SKIP]
        if os.path.basename(dp) == "raw":
            raw_dirs.append(dp)
            dns[:] = []
            continue
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > FILE_LIMIT and not os.path.islink(p):
                    add("REC-SIZE-FILE", "warn", p, "%d KB (limit %d KB)" % (os.path.getsize(p) // 1024, FILE_LIMIT // 1024))
            except OSError:
                pass
    for name in sorted(os.listdir(claude)):
        d = os.path.join(claude, name)
        if not os.path.isdir(d) or name in SIZE_SKIP:
            continue
        total = 0
        for dp, dns, fns in os.walk(d):
            dns[:] = [x for x in dns if x != "raw"]
            total += sum(os.path.getsize(os.path.join(dp, f)) for f in fns if os.path.isfile(os.path.join(dp, f)))
        if total > DIR_LIMIT:
            add("REC-SIZE-DIR", "warn", d, "%.1f MB (limit %d MB)" % (total / 1048576, DIR_LIMIT // 1048576))
    if raw_dirs and not gitignored_raw(root):
        add("REC-RAW-NOT-IGNORED", "warn", raw_dirs[0], "raw/ present but .gitignore has no raw/ pattern (add `.claude/**/raw/`)")
    return F


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    F = check(a.root)
    if a.json:
        json.dump(F, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        counts = {}
        for f in F:
            counts[f["code"]] = counts.get(f["code"], 0) + 1
            print("%s %s %s: %s" % (f["severity"].upper(), f["code"], f["path"], f["message"]))
        print("records_check: %d findings %s" % (len(F), json.dumps(counts, sort_keys=True)))
    return 2 if a.strict and any(f["severity"] != "info" for f in F) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
