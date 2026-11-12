"""records_check 테스트. 실행: timeout 120 python3 -I tests/test_records_check.py </dev/null"""
import os
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

    def test_cli(self):
        script = HERE.parent / "scripts" / "records_check.py"
        p = subprocess.run([sys.executable, "-I", str(script), "--root", self.root, "--json"], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertIn("REC-STATUS-BAD", p.stdout)
        p = subprocess.run([sys.executable, "-I", str(script), "--root", self.root, "--strict"], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 2)

    def test_no_claude_dir(self):
        self.assertEqual(rc.check(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
