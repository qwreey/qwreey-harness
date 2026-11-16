"""records_check 테스트. 실행: timeout 120 python3 -I tests/test_records_check.py </dev/null"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import records_check as rc  # noqa: E402

FIX = HERE / "records-fixtures"


def coderag_src():
    """The coderag checkout: $CODERAG_SRC, else a `coderag` sibling of an ancestor (works from worktrees too)."""
    env = os.environ.get("CODERAG_SRC")
    if env:
        return Path(env) if (Path(env) / "crates").is_dir() else None
    return next((a.parent / "coderag" for a in HERE.parents if (a.parent / "coderag" / "crates" / "coderag-core").is_dir()), None)


def coderag_bin():
    src = coderag_src()
    cands = [os.environ.get("CODERAG_BIN", "")] + ([str(src / "target" / k / "coderag") for k in ("release", "debug")] if src else [])
    return next((c for c in cands if c and os.access(c, os.X_OK)), None)


def put(root, rel, body="# t\n"):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


# Records homes and scopes, with the cases that must not be homes. Expected scope per record (None = not a record).
SCOPED = {
    ".claude/README.md": "", ".claude/plan/a.md": "", ".claude/packs/luau-kb/research/x.md": "packs/luau-kb",
    ".claude/packs/luau-kb/evals/e.md": "packs/luau-kb", ".claude/scopes/plugins/q/audit/3-x/a.md": "plugins/q",
    ".claude/scopes/plugins/q/evals/e.md": "plugins/q", ".claude/scopes/plugins/q/skills/doctor/plan/p.md": "plugins/q/skills/doctor",
    ".claude/scopes/plugins/q/archive/base/old.md": "plugins/q", ".claude/scopes/home/.claude/statusline/research/r.md": "home/.claude/statusline",
    ".claude/scopes/home/.claude/statusline/note.md": "home/.claude/statusline", ".claude/scopes/.github/plan/p.md": ".github",
    ".claude/.hidden/plan/h.md": None, ".claude/skills/s.md": None, ".claude/plan/raw/r.md": None, ".claude/scopes/plugins/q/plan/CLAUDE.md": None,
    "backend/.claude/README.md": "backend", "backend/.claude/base/b.md": "backend", "backend/.claude/scopes/api/plan/p.md": "backend/api",
    "frontend/.claude/base/f.md": None, "plugins/q/.claude/README.md": None, "plugins/q/.claude/plan/s.md": None,
    "vendor/x/.claude/README.md": None, "vendor/x/.claude/base/v.md": None, "gen/.claude/README.md": None, "gen/.claude/base/g.md": None,
    "ign/.claude/README.md": None, "ign/.claude/base/i.md": None, "a-fixtures/.claude/README.md": None, "a-fixtures/.claude/plan/f.md": None,
}


def build_scoped(root, git=True):
    for rel in SCOPED:
        put(root, rel)
    for rel in ["plugins/q/skills/doctor/SKILL.md", "home/.claude/statusline/x.sh", ".github/workflows/x.yml", "packs/luau-kb/README.md",
                "backend/api/x.txt"]:
        put(root, rel, "")
    put(root, "plugins/q/.claude-plugin/plugin.json", "{}")
    put(root, ".gitattributes", "gen/** linguist-generated\n")
    put(root, ".gitignore", "ign/\n")
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


def codes(findings):
    return {(f["code"], f["path"].replace("\\", "/").split(".claude/", 1)[-1]) for f in findings}


class Parse(unittest.TestCase):
    def test_forms(self):
        ok = ["active", "active; on hold until x", "landed in a/b.md", "landed in a/b.md; not maintained",
              "superseded by a.md", "superseded by D-12", "rejected", "rejected by D-07; too costly", "archived; done"]
        for v in ok:
            self.assertIsNotNone(rc.parse_status(v)[0], v)

    def test_bad(self):
        for v in ["paused", "landed", "superseded", "active in x", "rejected in x", "done"]:
            self.assertIsNone(rc.parse_status(v)[0], v)

    def test_superseded_key(self):
        self.assertEqual(rc.parse_status("superseded", "x.md")[0], "superseded")

    def test_read_status_places(self):
        self.assertEqual(rc.read_status("---\nstatus: active\n---\nbody")[0], "active")
        self.assertEqual(rc.read_status("status: landed in a.md\n# t")[0], "landed in a.md")
        self.assertIsNone(rc.read_status("# t\nstatus: active")[0])
        self.assertIsNone(rc.read_status("---\ntitle: x\n---\nstatus: active")[0])


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "repo")
        shutil.copytree(FIX, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_findings(self):
        got = codes(rc.check(self.root))
        for want in [("REC-STATUS-BAD", "plan/bad.md"), ("REC-STATUS-MISSING", "plan/nostatus.md"),
                     ("REC-CLOSED-OUTSIDE-ARCHIVE", "plan/landed.md"), ("REC-CLOSED-OUTSIDE-ARCHIVE", "plan/sup-key.md"),
                     ("REC-CLOSED-OUTSIDE-ARCHIVE", "plan/firstline.md"), ("REC-CLOSED-OUTSIDE-ARCHIVE", "plan/rejected.md"),
                     ("REC-INDEX-MISSING", "plan/unindexed.md"), ("REC-LINK-BROKEN", "plan/links.md"),
                     ("REC-RAW-NOT-IGNORED", "audit/01-snap/raw")]:
            self.assertIn(want, got)

    def test_no_false_positives(self):
        got = codes(rc.check(self.root))
        for p in ["plan/active.md", "plan/hold.md", "base/decision.md", "research/notes.md", "archive/plan/old.md"]:
            self.assertEqual({c for c, q in got if q == p}, set(), p)
        self.assertEqual({q for c, q in got if c == "REC-LINK-BROKEN"}, {"plan/links.md"})
        self.assertFalse(any(q.startswith("audit/") and c != "REC-RAW-NOT-IGNORED" for c, q in got))
        self.assertEqual(sum(1 for f in rc.check(self.root) if f["code"] == "REC-LINK-BROKEN"), 1)

    def test_format_key(self):
        plan = Path(self.root, ".claude", "plan")
        for i, (val, bad) in enumerate([("1", False), ("12", False), ("0", True), ("-1", True), ("one", True), ("1.5", True), ("", True)]):
            (plan / ("fmt%d.md" % i)).write_text("---\nformat: %s\ntitle: t\ndescription: d\nstatus: active\n---\nB\n" % val)
        got = {q for c, q in codes(rc.check(self.root)) if c == "REC-FORMAT-BAD"}
        self.assertEqual(got, {"plan/fmt2.md", "plan/fmt3.md", "plan/fmt4.md", "plan/fmt5.md", "plan/fmt6.md"})
        self.assertFalse(any(f["code"] == "REC-FORMAT-BAD" and f["severity"] != "warn" for f in rc.check(self.root)))
        # a record without the key (every old record) is not reported
        self.assertNotIn("plan/active.md", got)

    def test_raw_ignored(self):
        Path(self.root, ".gitignore").write_text(".claude/**/raw/\n")
        self.assertNotIn("REC-RAW-NOT-IGNORED", {f["code"] for f in rc.check(self.root)})

    def test_sizes(self):
        Path(self.root, ".claude", "base", "big.md").write_text("x" * (rc.FILE_LIMIT + 1))
        Path(self.root, ".claude", "audit", "01-snap", "raw", "huge.bin").write_bytes(b"x" * (rc.DIR_LIMIT + 1))
        got = {f["code"] for f in rc.check(self.root)}
        self.assertIn("REC-SIZE-FILE", got)
        self.assertNotIn("REC-SIZE-DIR", got)  # raw/ is not counted
        Path(self.root, ".claude", "base", "big2.bin").write_bytes(b"x" * (rc.DIR_LIMIT + 1))
        self.assertIn("REC-SIZE-DIR", {f["code"] for f in rc.check(self.root)})

    def _bad(self, folder):
        d = Path(self.root, ".claude", folder)
        d.mkdir(parents=True, exist_ok=True)
        (d / "x.md").write_text("status: paused\n# x\n")
        return "%s/x.md" % folder

    def test_declared_folders(self):
        living, snap, memory = self._bad("backlog"), self._bad("feedback"), self._bad("agent-memory")
        got = codes(rc.check(self.root))
        self.assertFalse({q for c, q in got} & {living, snap, memory}, "undeclared folders are not checked")
        toml = '[records.folders]\nbacklog = "living"\nfeedback = "snapshot"\nagent-memory = "living"\nbogus = "weird"\n'
        Path(self.root, "coderag.toml").write_text(toml)
        got = codes(rc.check(self.root))
        self.assertIn(("REC-STATUS-BAD", living), got)
        self.assertNotIn(("REC-STATUS-BAD", snap), got)
        self.assertNotIn(("REC-STATUS-BAD", memory), got, "non-record dirs cannot be declared living")
        # a built-in living folder declared snapshot is no longer checked
        Path(self.root, "coderag.toml").write_text('[records.folders]\nplan = "snapshot"\n')
        self.assertNotIn(("REC-STATUS-BAD", "plan/bad.md"), codes(rc.check(self.root)))

    def test_bad_toml_is_ignored(self):
        Path(self.root, "coderag.toml").write_text("[records.folders\nbacklog = ")
        self.assertIn(("REC-STATUS-BAD", "plan/bad.md"), codes(rc.check(self.root)))
        Path(self.root, "coderag.toml").write_text('records = "x"\n')
        self.assertIn(("REC-STATUS-BAD", "plan/bad.md"), codes(rc.check(self.root)))

    def test_non_record_dirs_not_sized(self):
        Path(self.root, ".claude", "agent-memory").mkdir()
        Path(self.root, ".claude", "agent-memory", "big.md").write_text("x" * (rc.FILE_LIMIT + 1))
        Path(self.root, ".claude", "skills").mkdir()
        Path(self.root, ".claude", "skills", "huge.bin").write_bytes(b"x" * (rc.DIR_LIMIT + 1))
        got = {f["code"] for f in rc.check(self.root)}
        self.assertNotIn("REC-SIZE-FILE", got)
        self.assertNotIn("REC-SIZE-DIR", got)

    def test_cli(self):
        script = HERE.parent / "scripts" / "records_check.py"
        p = subprocess.run([sys.executable, "-I", str(script), "--root", self.root, "--json"], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertIn("REC-STATUS-BAD", p.stdout)
        p = subprocess.run([sys.executable, "-I", str(script), "--root", self.root, "--strict"], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 2)

    def test_no_claude_dir(self):
        self.assertEqual(rc.check(self.tmp), [])


class Scopes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "repo")
        build_scoped(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def rels(self):
        return {os.path.relpath(p, self.root).replace(os.sep, "/"): s for p, s, _k, _h in rc.records(self.root)}

    def test_homes_and_scopes(self):
        self.assertEqual(self.rels(), {k: v for k, v in SCOPED.items() if v is not None})

    def test_without_git(self):
        shutil.rmtree(os.path.join(self.root, ".git"))
        put(self.root, "coderag.toml", "[records]\n")  # project boundary for co-located homes, as coderag nearest_root
        got = self.rels()
        self.assertEqual(got.get("backend/.claude/base/b.md"), "backend")
        self.assertNotIn("vendor/x/.claude/base/v.md", got)
        self.assertNotIn("plugins/q/.claude/plan/s.md", got)

    def test_nested_project_is_not_a_home(self):
        put(self.root, "sub/.claude/README.md")
        put(self.root, "sub/.claude/plan/n.md")
        put(self.root, "sub/coderag.toml", "")
        self.assertNotIn("sub/.claude/plan/n.md", self.rels())

    def test_declared_folder_ends_the_scope(self):
        put(self.root, ".claude/scopes/plugins/q/backlog/x.md", "status: paused\n")
        put(self.root, ".claude/scopes/plugins/q/wip/backlog/y.md", "status: paused\n")
        # undeclared: the scope ends at the longest existing repo path, and the folder after it is of unknown kind
        self.assertEqual(self.rels()[".claude/scopes/plugins/q/backlog/x.md"], "plugins/q")
        self.assertEqual(self.rels()[".claude/scopes/plugins/q/wip/backlog/y.md"], "plugins/q")
        self.assertNotIn("scopes/plugins/q/backlog/x.md", {q for _c, q in codes(rc.check(self.root))})
        put(self.root, "coderag.toml", '[records.folders]\nbacklog = "living"\n')
        self.assertEqual(self.rels()[".claude/scopes/plugins/q/backlog/x.md"], "plugins/q")
        self.assertEqual(self.rels()[".claude/scopes/plugins/q/wip/backlog/y.md"], "plugins/q/wip")
        self.assertIn(("REC-STATUS-BAD", "scopes/plugins/q/backlog/x.md"), codes(rc.check(self.root)))

    def test_checks_run_in_scopes_and_co_located_homes(self):
        bad = "status: paused\n# x\n"
        for rel in [".claude/scopes/plugins/q/plan/bad.md", ".claude/packs/luau-kb/research/bad.md",
                    ".claude/scopes/home/.claude/statusline/research/bad.md", "backend/.claude/base/bad.md",
                    "frontend/.claude/base/bad.md", "plugins/q/.claude/plan/bad.md", ".claude/scopes/plugins/q/audit/3-x/bad.md"]:
            put(self.root, rel, bad)
        put(self.root, ".claude/scopes/plugins/q/plan/landed.md", "status: landed in plugins/q/skills/doctor/SKILL.md\n")
        put(self.root, ".claude/scopes/plugins/q/archive/plan/gone.md", "status: archived\n")
        got = {(c, p) for c, p in ((f["code"], f["path"].replace(os.sep, "/")) for f in rc.check(self.root))}
        for p in [".claude/scopes/plugins/q/plan/bad.md", ".claude/packs/luau-kb/research/bad.md",
                  ".claude/scopes/home/.claude/statusline/research/bad.md", "backend/.claude/base/bad.md"]:
            self.assertIn(("REC-STATUS-BAD", p), got)
        flagged = {p for _c, p in got}
        for p in ["frontend/.claude/base/bad.md", "plugins/q/.claude/plan/bad.md", ".claude/scopes/plugins/q/audit/3-x/bad.md",
                  ".claude/scopes/plugins/q/archive/plan/gone.md"]:
            self.assertNotIn(p, flagged)
        self.assertIn(("REC-CLOSED-OUTSIDE-ARCHIVE", ".claude/scopes/plugins/q/plan/landed.md"), got)
        self.assertNotIn(("REC-TARGET-MISSING", ".claude/scopes/plugins/q/plan/landed.md"), got)

    def test_folder_status_stops_at_the_scoped_record_folder(self):
        put(self.root, ".claude/scopes/plugins/q/plan/README.md", "status: active\n- a\n")
        put(self.root, ".claude/scopes/plugins/q/plan/x.md", "# no status\n")
        put(self.root, ".claude/scopes/plugins/q/plan/sub/README.md", "status: active\n- y.md\n")
        put(self.root, ".claude/scopes/plugins/q/plan/sub/y.md", "# no status\n")
        missing = {p for c, p in codes(rc.check(self.root)) if c == "REC-STATUS-MISSING"}
        self.assertIn("scopes/plugins/q/plan/x.md", missing)
        self.assertNotIn("scopes/plugins/q/plan/sub/y.md", missing)

    def test_sizes_per_scope(self):
        shutil.rmtree(os.path.join(self.root, ".claude/plan/raw"))
        Path(self.root, ".claude/scopes/plugins/q/audit/3-x/big.bin").write_bytes(b"x" * (rc.DIR_LIMIT + 1))
        Path(self.root, ".claude/scopes/plugins/q/skills").mkdir(parents=True, exist_ok=True)
        dirs = {f["path"].replace(os.sep, "/") for f in rc.check(self.root) if f["code"] == "REC-SIZE-DIR"}
        self.assertEqual(dirs, {".claude/scopes/plugins/q/audit"})
        Path(self.root, ".claude/skills/huge.bin").write_bytes(b"x" * (rc.DIR_LIMIT + 1))
        Path(self.root, ".claude/scopes/plugins/q/audit/3-x/raw").mkdir()
        Path(self.root, ".claude/scopes/plugins/q/audit/3-x/raw/r.txt").write_text("x")
        got = {(f["code"], f["path"].replace(os.sep, "/")) for f in rc.check(self.root)}
        self.assertNotIn(("REC-SIZE-DIR", ".claude/skills"), got)
        self.assertIn(("REC-RAW-NOT-IGNORED", ".claude/scopes/plugins/q/audit/3-x/raw"), got)


def rust_strings(src, name):
    """Strings of the Rust `const <name>` list or string in src, or None when there is no such const."""
    m = re.search(r"const %s: &(?:\[&str\]|str) =\s*&?\[?(.*?)\]?;" % re.escape(name), src, re.S)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else None


@unittest.skipUnless(coderag_src(), "no coderag checkout (set CODERAG_SRC)")
class CopiesMatchCoderag(unittest.TestCase):
    """The @copy-of lists in records_check.py hold the same strings as their coderag source."""

    def src(self, rel):
        return (coderag_src() / rel).read_text(encoding="utf-8")

    def test_marked_copies(self):
        text = Path(rc.__file__).read_text(encoding="utf-8")
        marks = re.findall(r"# @copy-of: coderag:(\S+)#(\w+)\n(\w+) =", text)
        self.assertEqual(len(marks), 6)
        for rel, name, local in marks:
            self.assertEqual(name, local)
            want = rust_strings(self.src(rel), name)
            self.assertIsNotNone(want, "%s#%s" % (rel, name))
            self.assertEqual(sorted(getattr(rc, local)), sorted(want), name)

    def test_folder_kinds_and_scope_dirs(self):
        records = self.src("crates/coderag-core/src/records.rs")
        body = re.search(r"fn folder_kind\(.*?\n    \}\n", records, re.S).group(0)
        kinds = {}
        for names, kind in re.findall(r'((?:"[\w-]+"\s*\|?\s*)+)=>\s*RecordKind::(\w+)', body):
            for n in re.findall(r'"([\w-]+)"', names):
                kinds[n] = kind.lower()
        self.assertEqual(kinds, rc.BUILTIN_KINDS)
        walk = self.src("crates/coderag-mdfm/src/walk.rs")
        self.assertEqual(rust_strings(walk, "SCOPES_DIR"), [rc.SCOPES_DIR])
        self.assertEqual(rust_strings(walk, "PACKS_DIR"), [rc.PACKS_DIR])


@unittest.skipUnless(coderag_bin(), "no coderag binary (set CODERAG_BIN)")
class ParityWithCoderag(unittest.TestCase):
    """records() finds the same records with the same scopes as `coderag list` on one tree."""

    def test_same_records_and_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "repo")
            build_scoped(root)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.path.join(tmp, "home"),
                   "CODERAG_CACHE": os.path.join(tmp, "cache"), "CODERAG_HOME": os.path.join(tmp, "chome")}
            run = lambda *a: subprocess.run([coderag_bin(), *a], cwd=root, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(run("gen").returncode, 0)
            got = {}
            for module in (".claude", "backend/.claude"):
                p = run("list", module, "--json", "--all", "--layer", "project")
                self.assertEqual(p.returncode, 0, p.stderr)
                got.update({d["path"]: d["scope"] for d in json.loads(p.stdout)})
            mine = {os.path.relpath(p, root).replace(os.sep, "/"): s for p, s, _k, _h in rc.records(root)}
            self.assertEqual(mine, got)


if __name__ == "__main__":
    unittest.main()
