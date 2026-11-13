"""tools/sync-copies.py on fixture repos in a temp dir. Run: python3 -I tools/tests/test-sync-copies.py

Fixture lines are built from lists of quoted strings so this file holds no marker line of its own (the tool scans tools/).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "sync-copies.py"
VALUE = 'say "hi"\\path\n\tdone {nonce} é'


def lines(*xs):
    return "\n".join(xs) + "\n"


class SyncCopies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Path(self.tmp.name) / "a"
        self.b = Path(self.tmp.name) / "b"
        for r in (self.a, self.b):
            (r / ".git").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, repo, rel, text):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_tool(self, *args):
        return subprocess.run([sys.executable, "-I", str(TOOL), *args, "--root", str(self.a), "--root", str(self.b)],
                              capture_output=True, text=True)

    def canon_texts(self):
        self.put(self.a, "lib/texts.py", lines(
            "# @start-replace: lib/texts.py#GREETING",
            "GREETING = ('say \"hi\"\\\\path\\n'",
            "            '\\tdone {nonce} é')",
            "# @end-replace",
            "# @start-replace: lib/texts.py#BLOCK",
            "def helper(x):",
            "    return x + 1",
            "",
            "# @end-replace",
        ))

    def test_whole_file_copy(self):
        canon = lines('"""Helper.', "@copy-of: lib/h.py", '"""', "X = 2")
        self.put(self.a, "lib/h.py", canon)
        cp = self.put(self.a, "plugins/p/h.py", lines('"""Helper.', "@copy-of: lib/h.py", '"""', "X = 1"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("plugins/p/h.py", r.stdout)
        self.assertEqual(cp.read_text(encoding="utf-8"), lines('"""Helper.', "@copy-of: lib/h.py", '"""', "X = 1"), "--check must not write")
        self.assertEqual(self.run_tool("--apply").returncode, 0)
        self.assertEqual(cp.read_text(encoding="utf-8"), canon)
        self.assertEqual(self.run_tool("--check").returncode, 0)

    def test_verbatim_region_reindents_and_keeps_outside(self):
        self.canon_texts()
        before = lines("import os", "class K:", "    # @start-replace: lib/texts.py#BLOCK", "    stale = 1", "    # @end-replace", "    tail = 3")
        cp = self.put(self.a, "plugins/p/k.py", before)
        self.assertEqual(self.run_tool("--apply").returncode, 0)
        self.assertEqual(cp.read_text(encoding="utf-8"), lines(
            "import os", "class K:", "    # @start-replace: lib/texts.py#BLOCK",
            "    def helper(x):", "        return x + 1", "", "    # @end-replace", "    tail = 3"))
        self.assertEqual(self.run_tool("--check").returncode, 0)

    def test_value_string_into_python(self):
        self.canon_texts()
        cp = self.put(self.a, "plugins/p/v.py", lines(
            "A = 1",
            "# @start-replace: lib/texts.py#GREETING value=string template=\"G = {value}\"",
            "G = 'old'",
            "# @end-replace"))
        self.assertEqual(self.run_tool("--apply").returncode, 0, self.run_tool().stderr)
        ns = {}
        exec(cp.read_text(encoding="utf-8"), ns)
        self.assertEqual(ns["G"], VALUE)
        self.assertTrue(cp.read_text(encoding="utf-8").startswith("A = 1\n"))

    def test_value_string_into_rust_in_other_repo(self):
        self.canon_texts()
        cp = self.put(self.b, "crates/x/src/lib.rs", lines(
            "/// Greeting.",
            "// @start-replace: ../a/lib/texts.py#GREETING value=string template=\"pub const G: &str = {value};\"",
            "pub const G: &str = \"old\";",
            "// @end-replace",
            "fn main() {}"))
        r = self.run_tool("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = cp.read_text(encoding="utf-8").split("\n")[2]
        self.assertEqual(got, 'pub const G: &str = "say \\"hi\\"\\\\path\\n\\tdone {nonce} é";')

    def test_unpaired_marker_is_an_error(self):
        self.canon_texts()
        self.put(self.a, "plugins/p/u.py", lines("# @start-replace: lib/texts.py#BLOCK", "x = 1"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("without an end-replace", r.stderr)
        self.put(self.a, "plugins/p/u.py", lines("x = 1", "-- @end-replace"))
        self.assertEqual(self.run_tool().returncode, 2)

    def test_missing_canon_is_an_error(self):
        self.canon_texts()
        self.put(self.a, "plugins/p/m.py", lines("# @start-replace: lib/nope.py#BLOCK", "# @end-replace"))
        r = self.run_tool("--apply")
        self.assertEqual(r.returncode, 2)
        self.assertIn("canon file lib/nope.py not found", r.stderr)
        self.put(self.a, "plugins/p/m.py", lines("# @start-replace: lib/texts.py#NOPE", "# @end-replace"))
        r = self.run_tool("--apply")
        self.assertEqual(r.returncode, 2)
        self.assertIn("canon region lib/texts.py#NOPE not found", r.stderr)
        self.put(self.a, "plugins/p/m.py", lines('"""@copy-of: lib/gone.py"""'))
        self.assertEqual(self.run_tool("--check").returncode, 2)

    def test_duplicate_name_and_copy_of_copy_are_errors(self):
        self.canon_texts()
        self.put(self.a, "plugins/p/d.py", lines("# @start-replace: lib/texts.py#BLOCK", "# @end-replace",
                                                 "# @start-replace: lib/texts.py#BLOCK", "# @end-replace"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("duplicate region name BLOCK", r.stderr)
        os.remove(self.a / "plugins/p/d.py")
        self.put(self.a, "plugins/p/mid.py", lines("# @start-replace: lib/texts.py#BLOCK", "# @end-replace"))
        self.put(self.a, "plugins/p/end.py", lines("# @start-replace: plugins/p/mid.py#BLOCK", "# @end-replace"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("is itself a copy", r.stderr)

    def test_value_string_needs_one_literal(self):
        self.canon_texts()
        self.put(self.a, "plugins/p/w.py", lines("# @start-replace: lib/texts.py#BLOCK value=string", "# @end-replace"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one string literal", r.stderr)


if __name__ == "__main__":
    unittest.main()
