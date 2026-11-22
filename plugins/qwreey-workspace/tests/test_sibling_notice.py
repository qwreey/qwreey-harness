"""형제 저장소 내부 경로 알림(scripts/sibling_notice.py) 단위 테스트. 실행: python3 -I tests/test_sibling_notice.py  (모델 호출 없음)"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "sibling_notice.py"
# HOOK_TEST_BIN=<바이너리> 면 훅을 python 스크립트 대신 `<바이너리> hook sibling-notice` 로 돌린다(Rust 판, crates/qwreey-workspace).
# Units 와 siblings() 시험은 python 함수를 그대로 부른다.
BIN = os.environ.get("HOOK_TEST_BIN")
CMD = [BIN, "hook", "sibling-notice"] if BIN else [sys.executable, "-I", str(SCRIPT)]
sys.path.insert(0, str(SCRIPTS))
import sibling_notice as sn  # noqa: E402

TAG = r'^<harness-hook name="sibling-internals" level="info" nonce="[0-9a-f]{12}">\n'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = Path(self.tmp.name)
        self.ws = t / "ws"
        self.mine = self.ws / "mine"
        (self.mine / ".git").mkdir(parents=True)
        (self.mine / ".claude" / "research").mkdir(parents=True)
        for n in ("other", "x-kb", "test"):
            (self.ws / n / ".git").mkdir(parents=True)
        (self.ws / "other" / "src").mkdir()
        (self.ws / "other" / "src" / "engine.py").write_text("x = 1\n")
        (self.ws / "test" / "README.md").write_text("t\n")
        (self.ws / "plain").mkdir()  # .git 없음: 저장소가 아니다
        (self.ws / "plain" / "a.txt").write_text("a\n")
        (t / "cfg").mkdir()
        (t / "tmp").mkdir()
        (t / "salt").write_text("00" * 32)
        # 옛 작업공간 키 없이(새로 설치한 동료와 같은 조건) 세션 기록의 cwd 로 다른 저장소를 찾는다. plain 은 저장소가 아니다.
        for n in ("mine", "other", "x-kb", "test", "plain"):
            self.session(self.ws / n)

    def session(self, cwd):
        d = self.t / "cfg" / "projects" / ("-" + str(cwd).strip("/").replace("/", "-"))
        d.mkdir(parents=True, exist_ok=True)
        (d / "s.jsonl").write_text(json.dumps({"type": "user", "cwd": str(cwd)}) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_", "CLAUDE_"))}
        e.update(TMPDIR=str(self.t / "tmp"), CLAUDE_CONFIG_DIR=str(self.t / "cfg"),
                 CLAUDE_PROJECT_DIR=str(self.mine), QWREEY_HARNESS_SALT_FILE=str(self.t / "salt"), HARNESS_ENV="/nonexistent")
        e.update(kw)
        return e

    def run_hook(self, tool, ti, sid="s1", **kw):
        data = {"session_id": sid, "cwd": str(self.mine), "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": ti}
        r = subprocess.run(CMD, input=json.dumps(data), capture_output=True, text=True,
                           env=self.env(**kw), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else None

    def write(self, rel, content, **kw):
        return self.run_hook("Write", {"file_path": str(self.mine / rel), "content": content}, **kw)


class Fires(Base):
    def test_absolute_path(self):
        out = self.write(".claude/research/a.md", "See %s/other/src/engine.py for the loop.\n" % self.ws)
        self.assertRegex(out, TAG)
        self.assertIn("1 internal path of sibling repo `other`", out)
        self.assertIn("at least as public as this repo (remote, LICENSE)", out)

    def test_relative_forms_and_count(self):
        text = "Uses `../other/src/engine.py` and `../../other/docs/x.md`, also `other/src/engine.py:12`.\n"
        out = self.write(".claude/research/b.md", text)
        self.assertIn("2 internal paths of sibling repo `other` (e.g. `../other/src/engine.py`)", out)

    def test_two_siblings(self):
        out = self.write(".claude/research/c.md", "`other/src/engine.py` and `../x-kb/skills/a.md`\n")
        self.assertIn("sibling repos `other` (1, e.g. `other/src/engine.py`), `x-kb` (1, e.g. `../x-kb/skills/a.md`)", out)

    def test_edit_and_multiedit(self):
        f = str(self.mine / ".claude" / "research" / "d.md")
        self.assertIsNotNone(self.run_hook("Edit", {"file_path": f, "old_string": "a", "new_string": "other/src/engine.py"}))
        f2 = str(self.mine / ".claude" / "research" / "e.md")
        self.assertIsNotNone(self.run_hook("MultiEdit", {"file_path": f2, "edits": [{"old_string": "a", "new_string": "b"},
                                                                                   {"old_string": "c", "new_string": "../other/x"}]}))

    def test_once_per_file_and_sibling(self):
        self.assertIsNotNone(self.write(".claude/research/a.md", "../other/a\n"))
        self.assertIsNone(self.write(".claude/research/a.md", "../other/b\n"))
        self.assertIsNotNone(self.write(".claude/research/b.md", "../other/a\n"))
        self.assertIsNotNone(self.write(".claude/research/a.md", "../x-kb/a\n"))
        self.assertIsNotNone(self.write(".claude/research/a.md", "../other/a\n", sid="s2"))

    def test_worktree_records(self):
        wt = self.mine / ".claude" / "worktrees" / "w1"
        (wt / ".claude").mkdir(parents=True)
        (wt / ".git").write_text("gitdir: %s/.git/worktrees/w1\n" % self.mine)
        self.assertIsNotNone(self.write(".claude/worktrees/w1/.claude/audit/a.md", "../other/a\n"))
        self.assertIsNotNone(self.run_hook("Write", {"file_path": str(wt / ".claude" / "x.md"), "content": "../other/a\n"},
                                           CLAUDE_PROJECT_DIR=str(wt)))


class Silent(Base):
    def test_bare_name(self):
        self.assertIsNone(self.write(".claude/research/a.md", "The other repo and x-kb do this; see `other`.\n"))

    def test_missing_relative_path(self):
        self.assertIsNone(self.write(".claude/research/a.md", "other/does/not/exist.py and test/nothing\n"))

    def test_relative_path_that_is_also_ours(self):
        (self.mine / "test").mkdir()
        (self.mine / "test" / "README.md").write_text("ours\n")
        self.assertIsNone(self.write(".claude/research/a.md", "See test/README.md.\n"))

    def test_outside_records(self):
        self.assertIsNone(self.write("docs/a.md", "../other/src/engine.py\n"))
        self.assertIsNone(self.write("CLAUDE.md", "../other/src/engine.py\n"))

    def test_skipped_claude_dirs(self):
        for rel in ("rules/a.md", "skills/s/SKILL.md", "agents/a.md", "commands/c.md", "hooks/h.py", "settings.json",
                    "settings.local.json", "harness.env", "worktrees/w1/src/a.py"):
            self.assertIsNone(self.write(".claude/" + rel, "../other/src/engine.py\n"), rel)

    def test_own_repo_and_non_repo(self):
        self.assertIsNone(self.write(".claude/research/a.md", "%s/mine/src/a.py and ../mine/b and ../plain/a.txt\n" % self.ws))

    def test_same_repo_worktree_folder(self):
        wt = self.ws / "mine-wt"
        wt.mkdir()
        (self.mine / ".git" / "worktrees" / "mine-wt").mkdir(parents=True)
        (wt / ".git").write_text("gitdir: %s/.git/worktrees/mine-wt\n" % self.mine)
        self.session(wt)
        self.assertIsNone(self.write(".claude/research/a.md", "../mine-wt/src/a.py\n"))

    def test_sibling_in_another_folder(self):
        far = self.t / "Documents" / "far"
        (far / ".git").mkdir(parents=True)
        (far / "lib").mkdir()
        (far / "lib" / "x.py").write_text("x\n")
        self.session(far)
        out = self.write(".claude/research/a.md", "See %s/lib/x.py and far/lib/x.py.\n" % far)
        self.assertIn("1 internal path of sibling repo `far`", out)

    def test_same_name_prefers_same_folder(self):
        dup = self.t / "elsewhere" / "other"
        (dup / ".git").mkdir(parents=True)
        self.session(dup)
        self.assertEqual(sn.siblings(str(self.mine), [str(dup), str(self.ws / "other")])["other"], str(self.ws / "other"))
        self.assertEqual(sn.siblings(str(self.mine), [str(dup)])["other"], str(dup))

    def test_url_and_nested_path(self):
        self.assertIsNone(self.write(".claude/research/a.md", "https://github.com/u/other/src/engine.py and tools/other/src/engine.py\n"))

    def test_off_switches(self):
        self.assertIsNone(self.write(".claude/research/a.md", "../other/a\n", HARNESS_WORKSPACE_SIBLING_NOTICE="off"))
        (self.t / "cfg" / "settings.json").write_text(json.dumps({"pluginConfigs": {"qwreey-workspace@m": {
            "options": {"harness_workspace_sibling_notice": False}}}}))
        self.assertIsNone(self.write(".claude/research/a.md", "../other/a\n"), "/config 옵션으로 끈다")
        (self.t / "cfg" / "settings.json").unlink()
        (self.mine / ".claude" / "harness.env").write_text("HARNESS_WORKSPACE_SIBLING_NOTICE=off\n")
        self.assertIsNone(self.write(".claude/research/a.md", "../other/a\n"))

    def test_no_other_repo_known(self):
        shutil.rmtree(self.t / "cfg" / "projects")
        self.assertIsNone(self.write(".claude/research/a.md", "../other/a\n"))

    def test_excluded_repo(self):
        (self.t / "cfg" / "settings.json").write_text(json.dumps({"pluginConfigs": {"qwreey-workspace@m": {
            "options": {"harness_workspace_exclude": str(self.ws / "other")}}}}))
        self.assertIsNone(self.write(".claude/research/a.md", "../other/a\n"))
        self.assertIsNotNone(self.write(".claude/research/a.md", "../x-kb/a\n"))

    def test_other_tools_and_bad_input(self):
        self.assertIsNone(self.run_hook("Read", {"file_path": str(self.mine / ".claude" / "a.md")}))
        r = subprocess.run(CMD, input="not json", capture_output=True, text=True, env=self.env(), timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class Units(unittest.TestCase):
    def test_records_rel(self):
        p = "/w/mine"
        self.assertEqual(sn.records_rel("/w/mine/.claude/audit/a.md", p), "audit/a.md")
        self.assertIsNone(sn.records_rel("/w/mine/.claude/rules/a.md", p))
        self.assertIsNone(sn.records_rel("/w/mine/src/a.md", p))
        self.assertIsNone(sn.records_rel("/w/other/.claude/a.md", p))
        self.assertEqual(sn.records_rel("/w/mine/.claude/worktrees/w1/.claude/plan/q.md", p), "plan/q.md")
        self.assertIsNone(sn.records_rel("/w/mine/.claude/worktrees/w1/src/a.py", p))

    def test_example_truncated(self):
        msg = sn.message([("other", [("x", "../other/" + "a" * 200)])])
        self.assertIn("...`)", msg)


if __name__ == "__main__":
    unittest.main()
