"""workspace 게이트·지도 단위 테스트. 실행: python3 -I tests/test_workspace_gate.py  (모델 호출 없음)"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
GATE = SCRIPTS / "workspace_gate.py"
MAP = ROOT / "skills" / "workspace" / "scripts" / "map.py"
sys.path.insert(0, str(SCRIPTS))
import wslib  # noqa: E402

WS = "/code/Projects"
PROJ = "/code/Projects/claude-doctor"

# 쓰기 10개, 읽기 9개, 형제와 무관한 5개(오탐 후보)
WRITES = [
    "cd /code/Projects/quad && sed -i 's/a/b/' src/x.luau",
    "sed -i 's/a/b/' /code/Projects/stl-luau/README.md",
    "echo hi > /code/Projects/rbvm/notes.txt",
    "cd ../rbvm && echo hi >> NOTES",
    "rm -rf /code/Projects/tbox/build",
    "cd /code/Projects/mrow && git commit -am wip",
    "git -C /code/Projects/quad checkout -b x",
    "python3 -c \"open('/code/Projects/coderag/a.py','w').write('x')\"",
    "cp ./notes.md /code/Projects/luau-kb/notes.md",
    "cd /code/Projects/vitrine && touch foo.go",
]
READS = [
    "cat /code/Projects/quad/CLAUDE.md",
    "cd /code/Projects/rbvm && cat README.md",
    "ls /code/Projects/stl-luau",
    "git -C /code/Projects/quad log --oneline",
    "cd /code/Projects/mrow && git status && grep -rn foo src",
    "grep -rn foo /code/Projects/luau-kb/skills",
    "cp /code/Projects/quad/a.md /tmp/a.md",
    "sed -n 1,20p /code/Projects/rbvm/x.luau",
    "python3 /code/Projects/luau-kb/tools/x.py --list",
    # cwd is a sibling but the only write target is an absolute path in our own repo
    "cd /code/Projects/quad && rm /code/Projects/claude-doctor/tmp.txt",
]
NONE = [
    "cat README.md | head",
    "sed -i 's/a/b/' plugins/q/README.md",
    "cd /code/Projects/claude-doctor && git commit -am x",
    "echo hi > /tmp/x.txt",
    "ls ~/.claude/rules/luau-core.md",
]


class Classifier(unittest.TestCase):
    def test_writes(self):
        for c in WRITES:
            self.assertEqual(wslib.classify_bash(c, PROJ, WS, PROJ)[0], "write", c)

    def test_reads(self):
        for c in READS:
            self.assertEqual(wslib.classify_bash(c, PROJ, WS, PROJ)[0], "read", c)

    def test_none(self):
        for c in NONE:
            self.assertEqual(wslib.classify_bash(c, PROJ, WS, PROJ)[0], None, c)


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.ws = t / "ws"
        for n in ("mine", "other", "x-kb"):
            (self.ws / n / ".git").mkdir(parents=True)
        (self.ws / "other" / "CLAUDE.md").write_text("# Other\n\nOther repo does things.\n")
        (self.ws / "x-kb" / "README.md").write_text("# kb\nKnowledge.\n")
        self.t = t
        self.proj = str(self.ws / "mine")
        self.sid = "sess1"
        (t / "cfg").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        e.update(TMPDIR=str(self.t / "tmp"), CLAUDE_CONFIG_DIR=str(self.t / "cfg"), HARNESS_WORKSPACE=str(self.ws),
                 CLAUDE_PROJECT_DIR=self.proj)
        (self.t / "tmp").mkdir(exist_ok=True)
        e.update(kw)
        return e

    def run_gate(self, event, data, **kw):
        data = {"session_id": self.sid, "cwd": self.proj, **data}
        r = subprocess.run([sys.executable, "-I", str(GATE), event], input=json.dumps(data), capture_output=True, text=True,
                           env=self.env(**kw), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def precompact(self):
        """PreCompact 가 올리는 회차(PreCompact 훅이 같은 모듈로 올린다)를 흉내 낸다."""
        r = subprocess.run([sys.executable, "-I", str(SCRIPTS / "compact_epoch.py"), "qwreey-workspace"], input=json.dumps({"session_id": self.sid}),
                           capture_output=True, text=True, env=self.env(), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def pre(self, tool, ti, **kw):
        return self.run_gate("PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti}, **kw)

    def decision(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def sibling(self, rel="other/a.txt"):
        return str(self.ws / rel)

    def load_skill(self, **extra):
        self.run_gate("PostToolUse", {"tool_name": "Skill", "tool_input": {"skill": "qwreey-workspace:workspace"}, **extra})


class Gate(Env):
    def test_write_denied_until_loaded(self):
        for tool, ti in (("Edit", {"file_path": self.sibling()}), ("Write", {"file_path": self.sibling()}),
                         ("MultiEdit", {"file_path": self.sibling()}), ("NotebookEdit", {"notebook_path": self.sibling("other/n.ipynb")}),
                         ("Bash", {"command": f"sed -i s/a/b/ {self.sibling()}"})):
            out = self.pre(tool, ti)
            self.assertEqual(self.decision(out), "deny", tool)
            reason = out["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn('level="action"', reason)
            self.assertIn("qwreey-workspace:workspace skill (Skill tool), then retry", reason)
        self.load_skill()
        self.assertIsNone(self.pre("Edit", {"file_path": self.sibling()}))
        self.assertIn("deny.log", os.listdir(self.t / "tmp" / "claude-workspace-gate"))

    def test_slash_command_loads(self):
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")
        self.run_gate("UserPromptExpansion", {"expansion_type": "slash_command", "command_name": "qwreey-workspace:workspace"})
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}))

    def test_other_skill_does_not_load(self):
        self.run_gate("PostToolUse", {"tool_name": "Skill", "tool_input": {"skill": "q:back"}})
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")

    def sub_write(self):
        return self.run_gate("PreToolUse", {"agent_id": "a1", "tool_name": "Write", "tool_input": {"file_path": self.sibling()}})

    def test_agent_id_separate(self):
        self.load_skill()
        self.assertEqual(self.decision(self.sub_write()), "deny")
        self.load_skill(agent_id="a1")
        self.assertIsNone(self.sub_write())

    def test_read_warns_once(self):
        out = self.pre("Read", {"file_path": self.sibling()})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn('level="warn"', ctx)
        self.assertIn("qwreey-workspace:workspace", ctx)
        self.assertIsNone(self.pre("Grep", {"pattern": "x", "path": self.sibling("other")}))
        out = self.pre("Bash", {"command": f"cat {self.sibling()}"})
        self.assertIsNone(out)

    def test_read_never_denied(self):
        for tool, ti in (("Read", {"file_path": self.sibling()}), ("Glob", {"pattern": self.sibling("other/**/*.md")})):
            self.assertNotEqual(self.decision(self.pre(tool, ti)), "deny")

    def test_compact_resets(self):
        self.load_skill()
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}))
        self.precompact()
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")
        # warn 도 회차마다 다시
        self.precompact()
        self.assertIn("additionalContext", self.pre("Read", {"file_path": self.sibling()})["hookSpecificOutput"])
        self.precompact()
        self.assertIn("additionalContext", self.pre("Read", {"file_path": self.sibling()})["hookSpecificOutput"])

    def test_epoch_file_resets(self):
        self.load_skill()
        d = self.t / "tmp" / "claude-qwreey-workspace-epoch"
        d.mkdir(parents=True)
        (d / self.sid).write_text("1")
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")

    def test_own_repo_ignored(self):
        self.assertIsNone(self.pre("Write", {"file_path": str(self.ws / "mine" / "a.txt")}))
        self.assertIsNone(self.pre("Bash", {"command": f"rm -rf {self.ws}/mine/build"}))
        self.assertIsNone(self.pre("Bash", {"command": "cd ../mine && touch x"}))
        wt = str(self.ws / "mine" / ".claude" / "worktrees" / "w1")
        self.assertIsNone(self.pre("Write", {"file_path": wt + "/a.txt"}, CLAUDE_PROJECT_DIR=wt))
        self.assertIsNone(self.pre("Write", {"file_path": str(self.ws / "mine" / "a.txt")}, CLAUDE_PROJECT_DIR=wt))

    def test_off_switch(self):
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}, HARNESS_WORKSPACE_GATE="off"))
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}, HARNESS_WORKSPACE=""))

    def test_harness_env_file_switch(self):
        (self.t / "cfg" / "lib").mkdir()
        (self.t / "cfg" / "lib" / "harness_env.py").write_text((ROOT.parent.parent / "home/.claude/lib/harness_env.py").read_text())
        (self.t / "cfg" / "harness.env").write_text("HARNESS_WORKSPACE_GATE=off\n")
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}))

    def test_symlink_path_not_sibling(self):
        # 홈의 rules 파일은 형제 저장소로 이어진 symlink 일 수 있다. normpath 만 쓰므로 형제 경로가 아니다.
        real = self.ws / "other" / "rules"
        real.mkdir()
        (real / "luau-core.md").write_text("x")
        home = self.t / "home"
        (home / ".claude" / "rules").mkdir(parents=True)
        (home / ".claude" / "rules" / "luau-core.md").symlink_to(real / "luau-core.md")
        p = str(home / ".claude" / "rules" / "luau-core.md")
        self.assertIsNone(self.pre("Edit", {"file_path": p}))
        self.assertIsNone(self.pre("Bash", {"command": f"sed -i s/a/b/ {p}"}))
        self.assertIsNone(self.pre("Edit", {"file_path": "~/.claude/rules/luau-core.md"}, HOME=str(home)))

    def test_fail_open(self):
        r = subprocess.run([sys.executable, "-I", str(GATE), "PreToolUse"], input="not json", capture_output=True, text=True, env=self.env())
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_unrelated_tool(self):
        self.assertIsNone(self.run_gate("PreToolUse", {"tool_name": "WebFetch", "tool_input": {"url": "x"}}))


class MapTest(Env):
    def run_map(self, **kw):
        r = subprocess.run([sys.executable, "-I", str(MAP), self.proj], capture_output=True, text=True, env=self.env(**kw), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_map(self):
        out = self.run_map()
        lines = out.splitlines()
        self.assertTrue(lines[1].startswith("- x-kb: Knowledge."), out)
        self.assertIn("- mine (this session's repo)", out)
        self.assertIn("- other: Other repo does things.", out)
        self.assertNotIn("# Other", out)

    def test_not_configured(self):
        self.assertEqual(self.run_map(HARNESS_WORKSPACE="").strip(), "HARNESS_WORKSPACE not configured")

    def test_first_line_cap_and_fallback(self):
        (self.ws / "other" / "CLAUDE.md").write_text("# T\n\n" + "a" * 300 + "\n")
        self.assertIn("- other: " + "a" * 120 + "\n", self.run_map() + "\n")
        (self.ws / "other" / "CLAUDE.md").write_text("# only title\n")
        (self.ws / "other" / "README.md").write_text("---\nx: y\n---\n# R\n\nFrom readme.\n")
        self.assertIn("- other: From readme.", self.run_map())


if __name__ == "__main__":
    unittest.main()
