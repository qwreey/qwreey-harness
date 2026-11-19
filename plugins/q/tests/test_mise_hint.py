"""mise shim 안내 훅. 실행: python3 -I tests/test_mise_hint.py  (모델 호출 없음)

가짜 설치 폴더(<tmp>/installs/<도구>/<버전>/...)를 HARNESS_TOOL_INSTALLS 로 주고, 훅 입력의 error 에 mise 오류 글을 넣는다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HINT = Path(__file__).resolve().parent.parent / "scripts" / "mise-hint.py"
SID = "s-mise-test"
MISE_ERR = (
    "Exit code 1\n"
    "mise ERROR No version is set for shim: corepack\n"
    "Set a global default version with one of the following:\n"
    "mise use -g node@24.20.0\n"
)


def run(payload, env):
    p = subprocess.run([sys.executable, "-I", str(HINT)], input=json.dumps(payload) if not isinstance(payload, str) else payload,
                       capture_output=True, text=True, env=env, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else None


def exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


class MiseHint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.installs = t / "installs"
        exe(self.installs / "node" / "22.1.0" / "bin" / "corepack")
        exe(self.installs / "node" / "24.20.0" / "bin" / "corepack")
        exe(self.installs / "github-rojo-rbx-rojo" / "7.7.0" / "rojo")
        (self.installs / "github-rojo-rbx-rojo" / "latest").symlink_to("7.7.0")
        cfg = t / "cfg"
        cfg.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_", "MISE_")) and k != "CLAUDE_PROJECT_DIR"}
        self.env.update(TMPDIR=str(t), HOME=str(t), CLAUDE_CONFIG_DIR=str(cfg), QWREEY_HARNESS_SALT_FILE=str(t / "salt"))
        (cfg / "harness.env").write_text("HARNESS_TOOL_INSTALLS=%s\n" % self.installs)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, error=MISE_ERR, **kw):
        d = {"session_id": SID, "tool_name": "Bash", "hook_event_name": "PostToolUseFailure", "cwd": self.tmp.name, "error": error}
        d.update(kw)
        return d

    def test_suggested_version_first(self):
        c = run(self.payload(), self.env)
        self.assertIn('<harness-hook name="mise-hint" level="info" nonce="', c)
        first = str(self.installs / "node" / "24.20.0" / "bin" / "corepack")
        self.assertIn("Installed copies: `%s`, `%s`." % (first, self.installs / "node" / "22.1.0" / "bin" / "corepack"), c)
        self.assertIn("`mise exec node@24.20.0 -- corepack ...`", c)
        self.assertIn("ask before running it", c)

    def test_binary_at_version_root_and_alias_skipped(self):
        err = "mise ERROR No version is set for shim: rojo\n"
        c = run(self.payload(error=err), self.env)
        self.assertIn("`%s`." % (self.installs / "github-rojo-rbx-rojo" / "7.7.0" / "rojo"), c)
        self.assertNotIn("latest", c, "별칭 폴더(심볼릭 링크)는 건너뛴다")
        self.assertNotIn("mise exec", c, "제안 줄이 없으면 exec 예시도 없다")

    def test_post_tool_use_response_text(self):
        d = self.payload(error=None, hook_event_name="PostToolUse", tool_response={"stdout": "", "stderr": MISE_ERR})
        self.assertIn("corepack", run(d, self.env))

    def test_not_installed(self):
        err = "mise ERROR No version is set for shim: stylua\n"
        self.assertIn("`mise install` may be needed", run(self.payload(error=err), self.env))

    def test_silent_cases(self):
        self.assertIsNone(run(self.payload(error="Exit code 1\nsome other failure"), self.env))
        self.assertIsNone(run(self.payload(tool_name="Read"), self.env))
        self.assertIsNone(run("not json", self.env))
        (Path(self.env["CLAUDE_CONFIG_DIR"]) / "harness.env").write_text("HARNESS_TOOL_INSTALLS=%s/missing\n" % self.tmp.name)
        self.assertIn("`mise install` may be needed", run(self.payload(), self.env), "설치 폴더가 없어도 조용히 안내만")


if __name__ == "__main__":
    unittest.main()
