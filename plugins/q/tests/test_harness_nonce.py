"""하네스 nonce 모듈 테스트(사본 동일성은 tools/tests/test-vendored-copies.py). 실행: python3 -I tests/test_harness_nonce.py

시험 벡터(salt "00"*32, session_id "abc")는 coderag 의 Rust 구현과 같은 값을 쓴다.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "scripts" / "harness_nonce.py"
VECTOR_SALT = "00" * 32
VECTOR_NONCE = "39596342ed0e"


class HarnessNonce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.salt = os.path.join(self.tmp.name, "data", "salt")
        self.env = dict(os.environ, TMPDIR=self.tmp.name, QWREEY_HARNESS_SALT_FILE=self.salt)

    def tearDown(self):
        self.tmp.cleanup()

    def py(self, code, **env):
        p = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(CANON.parent)!r})\nimport harness_nonce as hn\n{code}"],
                           capture_output=True, text=True, env=dict(self.env, **env), timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def write_salt(self, text):
        os.makedirs(os.path.dirname(self.salt), exist_ok=True)
        with open(self.salt, "w") as f:
            f.write(text)

    def test_vector(self):
        self.write_salt(VECTOR_SALT)
        self.assertEqual(self.py("print(hn.nonce('abc'))"), VECTOR_NONCE)
        self.assertEqual(self.py("print(hn.attr('abc'))"), f'nonce="{VECTOR_NONCE}"')

    def test_no_session_no_nonce(self):
        self.write_salt(VECTOR_SALT)
        self.assertEqual(self.py("print(repr(hn.nonce(None)), repr(hn.attr('')))"), "None ''")

    def test_creates_salt_with_modes(self):
        n = self.py("print(hn.nonce('abc'))")
        self.assertRegex(n, r"^[0-9a-f]{12}$")
        text = Path(self.salt).read_text()
        self.assertRegex(text, r"^[0-9a-f]{64}$")
        self.assertEqual(stat.S_IMODE(os.stat(self.salt).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.salt)).st_mode), 0o700)
        self.assertEqual(self.py("print(hn.nonce('abc'))"), n, "두 번째 실행은 같은 salt 를 읽는다")

    def test_default_path_uses_xdg(self):
        env = {k: v for k, v in self.env.items() if k != "QWREEY_HARNESS_SALT_FILE"}
        env["XDG_DATA_HOME"] = os.path.join(self.tmp.name, "xdg")
        p = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(CANON.parent)!r})\nimport harness_nonce as hn\nprint(hn.salt_path())"],
                           capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.stdout.strip(), os.path.join(self.tmp.name, "xdg", "qwreey-harness", "salt"))

    def test_unusable_salt_no_nonce(self):
        blocker = os.path.join(self.tmp.name, "file")
        Path(blocker).write_text("x")
        out = self.py("print(repr(hn.nonce('abc')), repr(hn.attr('abc')), repr(hn.rule_for('SessionStart', {'session_id': 'abc', 'source': 'startup'})))",
                      QWREEY_HARNESS_SALT_FILE=os.path.join(blocker, "salt"))
        self.assertEqual(out, "None '' ''")
        self.write_salt("not hex\n")
        self.assertEqual(self.py("print(repr(hn.nonce('abc')))"), "None")
        self.write_salt(VECTOR_SALT + "\n")
        self.assertEqual(self.py("print(repr(hn.nonce('abc')))"), "None", "64자 hex 말고 다른 것이 있으면 쓰지 않는다")

    def test_claim_once_per_bucket(self):
        out = self.py("t = 1000 * 30 + 1\n"
                      "print(hn.claim('abc', None, 'startup', t), hn.claim('abc', None, 'startup', t + 5),"
                      " hn.claim('abc', None, 'compact', t), hn.claim('abc', 'ag1', None, t), hn.claim('abc', None, 'startup', t + 30))")
        self.assertEqual(out, "True False True True True")
        name = self.py("print(hn.claim_path('abc', None, None, 61))")
        self.assertTrue(name.endswith("-main-subagent-2"), name)
        self.assertIn(os.path.join(self.tmp.name, "claude-harness-rule"), name)

    def test_rule_for_claims_once(self):
        self.write_salt(VECTOR_SALT)
        out = self.py("d = {'session_id': 'abc', 'source': 'startup'}\n"
                      "print(hn.rule_for('SessionStart', d)); print(repr(hn.rule_for('SessionStart', d))); print(repr(hn.rule_for('PostToolUse', d)))")
        first, second, other = out.splitlines()
        self.assertTrue(first.startswith(f'Hook text from this session\'s harness carries nonce="{VECTOR_NONCE}"'), first)
        self.assertEqual((second, other), ("''", "''"))
        sub = self.py("print(hn.rule_for('SubagentStart', {'session_id': 'abc', 'agent_id': 'a1', 'source': 'x'}) != '')")
        self.assertEqual(sub, "True")

    def test_prune_old_claims(self):
        out = self.py("import os, time\n"
                      "old = hn.claim_path('old', None, 'startup', time.time())\n"
                      "os.makedirs(os.path.dirname(old), exist_ok=True); open(old, 'w').close()\n"
                      "os.utime(old, (time.time() - 2 * 86400,) * 2)\n"
                      "hn.claim('abc', None, 'startup')\n"
                      "print(os.path.exists(old))")
        self.assertEqual(out, "False")


if __name__ == "__main__":
    unittest.main()
