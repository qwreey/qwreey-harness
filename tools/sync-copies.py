#!/usr/bin/env python3
"""Sync copies marked in comments with their canon. Standard library only.

Usage: python3 -I tools/sync-copies.py [--apply | --check] [--root DIR ...]
  default  print a diff of what --apply would write, exit 0
  --apply  write the copies
  --check  exit 1 if any copy differs from its canon
  --root   scan these repos whole instead of the defaults (tests, other repos)
Exit 2 on a marker error: missing canon file or region, unpaired markers, duplicate region names in one file,
a region whose canon is itself a copy, a whole-file canon that names another file.
Defaults: this repo's lib/, plugins/, packs/, tools/ and, when ../coderag exists, its crates/, harness/, conventions/.
Marker shapes: lib/copy_regions.py and lib/README.md.
"""
import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import copy_regions  # noqa: E402

HOME_DIRS = ("lib", "plugins", "packs", "tools")
SIBLINGS = {"coderag": ("crates", "harness", "conventions")}
# Markdown is left out: docs quote the marker shapes, and coderag syncs its own .md copies (tools/sync-harness.sh).
SUFFIX = {".py", ".sh", ".luau", ".lua", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".rs", ".toml", ".yml", ".yaml"}
SKIP = {".git", "__pycache__", "node_modules", "target", ".venv", "venv"}


def default_repos():
    repos = [(ROOT, HOME_DIRS)]
    for name, dirs in SIBLINGS.items():
        p = os.path.join(os.path.dirname(ROOT), name)
        if os.path.isdir(p):
            repos.append((p, dirs))
    return repos


def walk(repos):
    for root, dirs in repos:
        for top in dirs or ("",):
            base = os.path.join(root, top)
            for dp, dn, fn in os.walk(base):
                dn[:] = sorted(d for d in dn if d not in SKIP)
                for f in sorted(fn):
                    if os.path.splitext(f)[1] in SUFFIX:
                        yield os.path.join(dp, f)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def plan(repos):
    """({path: (old, new)} for files that change, [(path, line, message)] errors)."""
    roots = [r for r, _ in repos]
    texts, out, errors = {}, {}, []
    for p in walk(repos):
        try:
            texts[p] = read(p)
        except (OSError, UnicodeDecodeError):
            continue

    def get(p):
        return texts[p] if p in texts else read(p)

    new = {}
    for p, t in texts.items():
        if "@start-replace" not in t and "@end-replace" not in t:
            continue
        n, errs = copy_regions.sync_text(t, p, roots, get)
        errors += [(p, ln, msg) for ln, msg in errs]
        if n != t:
            new[p] = n
    for p, t in texts.items():
        tgt = copy_regions.file_copy_target(t)
        if not tgt:
            continue
        src = copy_regions.resolve(copy_regions.repo_root(p, roots), tgt)
        if src == os.path.normpath(p):
            continue
        try:
            stext = get(src)
        except (OSError, UnicodeDecodeError):
            errors.append((p, 1, "canon file %s not found" % tgt))
            continue
        own = copy_regions.file_copy_target(stext)
        if own and copy_regions.resolve(copy_regions.repo_root(src, roots), own) != src:
            errors.append((p, 1, "canon file %s is itself a copy of %s" % (tgt, own)))
            continue
        want = new.get(src, stext)
        if want != new.get(p, t):
            new[p] = want
    for p, n in new.items():
        if n != texts[p]:
            out[p] = (texts[p], n)
    return out, errors


def show(path):
    return os.path.relpath(path, ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sync copies marked with @copy-of and @start-replace/@end-replace.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--root", action="append", default=[])
    a = ap.parse_args(argv)
    repos = [(os.path.abspath(r), None) for r in a.root] if a.root else default_repos()
    changes, errors = plan(repos)
    for p, ln, msg in errors:
        print("%s:%d: %s" % (show(p), ln, msg), file=sys.stderr)
    if errors:
        return 2
    for p, (old, new) in sorted(changes.items()):
        if a.apply:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print("wrote %s" % show(p))
        elif a.check:
            print("differs: %s" % show(p))
        else:
            sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), show(p), show(p) + " (synced)"))
    if a.check and changes:
        print("%d copies differ from their canon. Edit the canon, then run: python3 -I tools/sync-copies.py --apply" % len(changes))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
