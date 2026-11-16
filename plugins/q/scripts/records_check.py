#!/usr/bin/env python3
"""Check agent records under a repo's records homes against the coderag:agent-records convention.
Usage: python3 -I records_check.py [--root <repo>] [--json] [--strict]
Exit 0 always, except 2 with --strict when there are findings above info level.

Records homes, scopes and record kinds follow coderag's classification (coderag-core records.rs and records/homes.rs):
the top `.claude/` and every `<dir>/.claude/` with a README.md that is not excluded, shipped, vendored or another project;
inside a home, `scopes/<repo path>/` and the older `packs/<pack>/` mirror a part of the repo, and the folder after the
scope decides the kind. Living folders (plan, base, research, declared living) and archive/ are checked; snapshot folders
(audit, handoff, sessions, session, declared snapshot) are only measured for size, because snapshots are never edited and
their links are frozen. The status grammar is implemented once here; coderag tests reuse tests/records-fixtures.

why not call the coderag binary: q:doctor runs this on machines where coderag is not built, coderag has no command that
prints per-file classification without an index, and the status-line, index and link checks here are not in coderag lint.
tests/test_records_check.py compares the copied lists with the coderag source and the classification with
`coderag list --json` when they are present.
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11: no declarations, built-in folders only
    tomllib = None

# Folder name -> record kind, as coderag-core Folders::folder_kind (compared in tests).
BUILTIN_KINDS = {"plan": "living", "base": "living", "research": "living",
                 "audit": "snapshot", "handoff": "snapshot", "sessions": "snapshot", "session": "snapshot",
                 "archive": "archive"}
# Inside a home, scopes/<repo path>/ mirrors a part of the repo; packs/<pack>/ is the older form of scopes/packs/<pack>/.
SCOPES_DIR = "scopes"
PACKS_DIR = "packs"
# @copy-of: coderag:crates/coderag-core/src/records.rs#NON_RECORD_DIRS
NON_RECORD_DIRS = {"rules", "skills", "agents", "commands", "output-styles", "hooks", "agent-memory", "worktrees",
                   "plugins", "projects", "memory", "plans", "todos", "raw"}
# @copy-of: coderag:crates/coderag-core/src/records.rs#NON_RECORD_FILES
NON_RECORD_FILES = {"CLAUDE.md", "SKILL.md", "AGENTS.md", "MEMORY.md", "GEMINI.md"}
# @copy-of: coderag:crates/coderag-mdfm/src/lib.rs#DEFAULT_EXCLUDES
DEFAULT_EXCLUDES = ("node_modules", "worktrees", "target")
# @copy-of: coderag:crates/coderag-core/src/records/homes.rs#DEFAULT_HOME_EXCLUDES
DEFAULT_HOME_EXCLUDES = ("vendor", "vendored", "third_party", "third-party", "refs", "dist", "build", "fixtures",
                         "*-fixtures", "*_fixtures", "__fixtures__", "testdata")
# @copy-of: coderag:crates/coderag-core/src/records/homes.rs#DEFAULT_SHIPPED_MARKERS
DEFAULT_SHIPPED_MARKERS = (".claude-plugin/plugin.json",)
# @copy-of: coderag:crates/coderag-core/src/records/homes.rs#VENDOR_ATTRS
VENDOR_ATTRS = ("linguist-vendored", "linguist-generated")
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


def records_cfg(root):
    """The [records] table of <root>/coderag.toml, or {} when it is missing or unreadable."""
    if tomllib is None:
        return {}
    try:
        with open(os.path.join(root, "coderag.toml"), "rb") as f:
            rec = tomllib.load(f).get("records", {})
    except (OSError, ValueError, AttributeError, TypeError):
        return {}
    return rec if isinstance(rec, dict) else {}


def declared_folders(root, cfg=None):
    """{folder: "living"|"snapshot"} from [records.folders]. Invalid entries are ignored."""
    folders = (records_cfg(root) if cfg is None else cfg).get("folders", {})
    if not isinstance(folders, dict):
        return {}
    return {str(k).strip("/"): v for k, v in folders.items() if v in ("living", "snapshot")}


def cfg_list(cfg, key):
    v = cfg.get(key, [])
    return [str(x) for x in v] if isinstance(v, list) else []


class Folders:
    """Record kind and scope of a path inside one home, as coderag-core records::Folders (with `at(base)`)."""

    def __init__(self, declared, base):
        self.declared = declared
        self.base = base

    def kind(self, folder):
        return self.declared.get(folder) or BUILTIN_KINDS.get(folder, "unknown")

    def split_scope(self, dirs):
        """(scope, rest): the scope path ends before the first record folder name; with none, at the longest leading
        part that exists in the repo under the home's folder, else it is the whole path. A repo path such as
        plugins/q/skills names repo folders, so non-record names do not end it."""
        if dirs[:1] == [PACKS_DIR] and len(dirs) >= 2:
            tail = dirs
        elif dirs[:1] == [SCOPES_DIR]:
            tail = dirs[1:]
        else:
            return "", dirs
        at = next((i for i, p in enumerate(tail) if self.kind(p) != "unknown"), None)
        if at is None:
            at = self.existing_prefix(tail) or len(tail)
        return "/".join(tail[:at]), tail[at:]

    def existing_prefix(self, tail):
        d, n = self.base, 0
        for p in tail:
            d = os.path.join(d, p)
            if not os.path.isdir(d):
                break
            n += 1
        return n

    def classify(self, rel):
        """(scope, kind, head) for a path relative to the home's .claude, or None when it is not a record.
        kind: living | snapshot | archive | index | unknown. head is the path up to the record folder ("" without one)."""
        parts = [p for p in rel.split("/") if p]
        if not parts:
            return None
        name, dirs = parts[-1], parts[:-1]
        if not name.endswith(".md") or name in NON_RECORD_FILES or "raw" in dirs:
            return None
        scope, rest = self.split_scope(dirs)
        if rest and rest[0] in NON_RECORD_DIRS:
            return None
        kind = self.kind(rest[0]) if rest else "unknown"
        head = "/".join(dirs[:len(dirs) - len(rest) + 1]) if rest else ""
        if name == "README.md" and kind != "snapshot":
            return scope, "index", head
        return scope, kind, head


def join_scope(a, b):
    return "%s/%s" % (a, b) if a and b else (a or b)


def name_matches(pattern, name):
    """`*x` matches a suffix, `x*` a prefix, else the whole name (coderag_mdfm::name_matches)."""
    if pattern.startswith("*"):
        return name.endswith(pattern[1:])
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    return name == pattern


def is_config_marker(path):
    text = read(path)
    if text is None:
        return False
    try:
        if path.endswith(".json"):
            return isinstance(json.loads(text), dict)
        if tomllib is None:
            return True
        tomllib.loads(text)
        return True
    except ValueError:
        return False


def nearest_root(start):
    """First ancestor with .git or a coderag marker (a .coderag/ that is not the user's, or a readable config)."""
    homes = [os.path.realpath(h) for h in (os.environ.get("CODERAG_HOME"), os.path.join(os.path.expanduser("~"), ".coderag")) if h]
    d = start
    while True:
        marker = os.path.join(d, ".coderag")
        if (os.path.exists(os.path.join(d, ".git"))
                or (os.path.isdir(marker) and os.path.realpath(marker) not in homes)
                or is_config_marker(os.path.join(d, "coderag.toml")) or is_config_marker(os.path.join(d, "coderag.json"))):
            return d
        up = os.path.dirname(d)
        if up == d:
            return start
        d = up


def git(project, args):
    try:
        p = subprocess.run(["git", "-C", project] + args, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def home_rejected(project, d, excludes, shipped):
    """Why <project>/<d>/.claude is not a records home (records/homes.rs check_home), or None when it is one."""
    for c in d.split("/"):
        if c.startswith(".") or any(name_matches(e, c) for e in excludes):
            return "excluded"
    parts = d.split("/")
    for n in range(1, len(parts) + 1):
        if any(os.path.isfile(os.path.join(project, *parts[:n], m)) for m in shipped):
            return "shipped"
    if nearest_root(os.path.join(project, d)) != project:
        return "other project"
    if not os.path.isfile(os.path.join(project, d, ".claude", "README.md")):
        return "no README"
    return None


def walk_candidates(project, excludes):
    out = []
    for dp, dns, _ in os.walk(project):
        dns[:] = sorted(x for x in dns if not (x.startswith(".") or any(name_matches(e, x) for e in excludes)))
        if dp != project and os.path.isfile(os.path.join(dp, ".claude", "README.md")):
            out.append(os.path.relpath(dp, project).replace(os.sep, "/"))
    return out


def discover_homes(project, cfg):
    """[(dir, abs .claude)]: the top home first (dir ""), then co-located homes by path (records/homes.rs discover_homes)."""
    out = [("", os.path.join(project, ".claude"))] if os.path.isdir(os.path.join(project, ".claude")) else []
    excludes = list(DEFAULT_EXCLUDES) + list(DEFAULT_HOME_EXCLUDES) + cfg_list(cfg, "exclude")
    shipped = list(DEFAULT_SHIPPED_MARKERS) + cfg_list(cfg, "shipped")
    suffix = "/.claude/README.md"
    listed = git(project, ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/.claude/README.md"])
    if listed is None:
        dirs = walk_candidates(project, excludes)
    else:
        dirs = [s[:-len(suffix)] for s in listed.decode("utf-8", "replace").split("\0") if s.endswith(suffix)]
    dirs = [d for d in sorted(set(dirs)) if home_rejected(project, d, excludes, shipped) is None]
    if listed is not None and dirs:
        attrs = git(project, ["check-attr", "-z"] + list(VENDOR_ATTRS) + ["--"] + [d + suffix for d in dirs])
        f = (attrs or b"").decode("utf-8", "replace").split("\0")
        bad = {f[i][:-len(suffix)] for i in range(0, len(f) - 2, 3) if f[i + 2] in ("set", "true")}
        dirs = [d for d in dirs if d not in bad]
    return out + [(d, os.path.join(project, d, ".claude")) for d in dirs]


def home_markdown(claude):
    """.md paths relative to a home, as coderag's walk: dot folders are skipped except inside a scope mirror (.git always)."""
    out = []
    for dp, dns, fns in os.walk(claude):
        rel = os.path.relpath(dp, claude).replace(os.sep, "/")
        rel = "" if rel == "." else rel + "/"
        mirror = rel.split("/", 1)[0] in (SCOPES_DIR, PACKS_DIR)
        dns[:] = sorted(x for x in dns if x not in DEFAULT_EXCLUDES and (not x.startswith(".") or (mirror and x != ".git")))
        out += [rel + fn for fn in sorted(fns) if fn.lower().endswith(".md")]
    return out


def gitignored_raw(*dirs):
    """True when a .gitignore in one of dirs mentions a raw/ pattern. Plain text parse: no git needed, fixture-safe."""
    for d in dirs:
        lines = (read(os.path.join(d, ".gitignore")) or "").splitlines()
        if any(re.search(r"(^|/)raw/?$", l.strip()) for l in lines if l.strip() and not l.startswith("#")):
            return True
    return False


def folder_status(path, folder_dir):
    """True when a README.md between the doc's folder and its record folder (exclusive) carries a status line."""
    d = os.path.dirname(path)
    while d != folder_dir and d.startswith(folder_dir + os.sep):
        readme = os.path.join(d, "README.md")
        if readme != path and os.path.isfile(readme):
            text = read(readme)
            if text is not None and read_status(text)[0] is not None:
                return True
        d = os.path.dirname(d)
    return False


def check_doc(add, path, in_archive, folder_dir, cands_base):
    text = read(path)
    if text is None:
        return
    fm, _ = split_frontmatter(text)
    # Only the shape is checked here; whether coderag supports the number is coderag's call (coderag lint).
    if fm is not None and "format" in fm and not re.fullmatch(r"[1-9][0-9]*", fm["format"].strip()):
        add("REC-FORMAT-BAD", "warn", path, "format %r is not a positive integer" % fm["format"])
    value, sup_by = read_status(text)
    if value is None:
        # A folder's README status covers the files in that folder, and a file under archive/ is closed by
        # where it is; flagging those would bury the docs that really lack a status.
        if not in_archive and not folder_status(path, folder_dir):
            add("REC-STATUS-MISSING", "info", path, "living doc has no status line (frontmatter or first line)")
        state = None
    else:
        state, kind, target, _note = parse_status(value, sup_by)
        if state is None:
            add("REC-STATUS-BAD", "warn", path, kind)
        elif target and ("/" in target or target.endswith(".md")):
            cands = [os.path.join(os.path.dirname(path), target)] + [os.path.join(b, target) for b in cands_base]
            if not any(os.path.exists(c) for c in cands):
                add("REC-TARGET-MISSING", "warn", path, "status target %s does not exist" % target)
    if state and state != "active" and not in_archive:
        add("REC-CLOSED-OUTSIDE-ARCHIVE", "warn", path,
            "status %s (not active) but not under archive/: git mv to archive/<origin>/ in the same commit, or set it back to active if it is still a current source" % state)
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
                add("REC-INDEX-MISSING", "warn", path, "not listed in %s" % readme)


def check_sizes(add, claude, folders):
    """File sizes, per record folder totals (each scope's folders apart), and raw/ dirs found."""
    raw_dirs, totals = [], {}
    for dp, dns, fns in os.walk(claude):
        rel = os.path.relpath(dp, claude).replace(os.sep, "/")
        dirs = [] if rel == "." else rel.split("/")
        if dirs and dirs[-1] == "raw":
            raw_dirs.append(dp)
            dns[:] = []
            continue
        _scope, rest = folders.split_scope(dirs)
        if rest and rest[0] in NON_RECORD_DIRS:
            dns[:] = []
            continue
        dns[:] = sorted(d for d in dns if d not in SIZE_SKIP)
        key = os.path.join(claude, *dirs[:len(dirs) - len(rest) + 1]) if rest else None
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.islink(p) or not os.path.isfile(p):
                    continue
                size = os.path.getsize(p)
            except OSError:
                continue
            if size > FILE_LIMIT:
                add("REC-SIZE-FILE", "warn", p, "%d KB (limit %d KB)" % (size // 1024, FILE_LIMIT // 1024))
            if key:
                totals[key] = totals.get(key, 0) + size
    for d, total in sorted(totals.items()):
        if total > DIR_LIMIT:
            add("REC-SIZE-DIR", "warn", d, "%.1f MB (limit %d MB)" % (total / 1048576, DIR_LIMIT // 1048576))
    return raw_dirs


def records(root):
    """[(abs path, project-relative scope, kind, head)] of every record in every home of root, as coderag classifies them."""
    root = os.path.abspath(root)
    cfg = records_cfg(root)
    declared = declared_folders(root, cfg)
    out = []
    for d, claude in discover_homes(root, cfg):
        folders = Folders(declared, os.path.dirname(claude))
        for rel in home_markdown(claude):
            r = folders.classify(rel)
            if r:
                out.append((os.path.join(claude, *rel.split("/")), join_scope(d, r[0]), r[1], r[2]))
    return out


def check(root):
    root = os.path.abspath(root)
    F = []

    def add(code, sev, path, msg):
        F.append({"code": code, "severity": sev, "path": os.path.relpath(path, root) if path else "", "message": msg})

    cfg = records_cfg(root)
    declared = declared_folders(root, cfg)
    for d, claude in discover_homes(root, cfg):
        folders = Folders(declared, os.path.dirname(claude))
        for rel in home_markdown(claude):
            r = folders.classify(rel)
            if not r or r[1] not in ("living", "archive"):
                continue
            path = os.path.join(claude, *rel.split("/"))
            check_doc(add, path, r[1] == "archive", os.path.join(claude, *r[2].split("/")),
                      [claude, os.path.dirname(claude), root])
        raw_dirs = check_sizes(add, claude, folders)
        if raw_dirs and not gitignored_raw(root, os.path.dirname(claude)):
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
