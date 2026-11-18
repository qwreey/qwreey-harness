"""workspace 게이트, 지도 단위 테스트. 실행: python3 -I tests/test_workspace_gate.py  (모델 호출 없음)

다른 저장소는 `.git` 폴더만 흉내 낸다. 옛 작업공간 키는 두지 않는다(새로 설치한 동료와 같은 조건). 지도의 저장소는 가짜 설정 디렉터리의
projects/ 세션 기록 cwd 로 모은다.
"""
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
GATE = SCRIPTS / "workspace_gate.py"
MAP = ROOT / "skills" / "workspace" / "scripts" / "map.py"
sys.path.insert(0, str(SCRIPTS))
import wslib  # noqa: E402

# 분류기 시험의 가짜 작업 폴더. 아래 명령의 /code/Projects 를 이 폴더로 바꿔 돌린다.
FAKE = Path(tempfile.mkdtemp(prefix="ws-classify-")).resolve()
WS = str(FAKE / "work")
PROJ = WS + "/qwreey-harness"
for _n in ("qwreey-harness", "quad", "stl-luau", "rbvm", "tbox", "mrow", "coderag", "luau-kb", "vitrine"):
    os.makedirs(os.path.join(WS, _n, ".git"), exist_ok=True)

# 쓰기 10개, 읽기 10개, 다른 저장소와 무관한 5개(오탐 후보)
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
    "cd /code/Projects/quad && rm /code/Projects/qwreey-harness/tmp.txt",
]
NONE = [
    "cat README.md | head",
    "sed -i 's/a/b/' plugins/q/README.md",
    "cd /code/Projects/qwreey-harness && git commit -am x",
    "echo hi > /tmp/x.txt",
    "ls ~/.claude/rules/luau-core.md",
]


def classify(c):
    # 가짜 폴더가 시스템 임시 폴더 아래라 기본 제외를 끈 판정기로 본다(제외는 ScopeTest 와 Gate 가 따로 본다).
    return wslib.classify_bash(c.replace("/code/Projects", WS), PROJ, wslib.Scope(PROJ, exclude=[]))


class Classifier(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(FAKE, ignore_errors=True)

    def test_writes(self):
        for c in WRITES:
            self.assertEqual(classify(c)[0], "write", c)

    def test_reads(self):
        for c in READS:
            self.assertEqual(classify(c)[0], "read", c)

    def test_none(self):
        for c in NONE:
            self.assertEqual(classify(c)[0], None, c)

    def test_names_the_repo_root(self):
        self.assertEqual(classify("rm -rf /code/Projects/tbox/build/x"), ("write", WS + "/tbox"))


class ScopeTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="ws-scope-")).resolve()
        for rel in ("a/mine", "b/other", "scratch/s", "a/mine/vendor/lib"):
            (self.t / rel / ".git").mkdir(parents=True)
        wt = self.t / "elsewhere" / "mine-wt"
        wt.mkdir(parents=True)
        admin = self.t / "a" / "mine" / ".git" / "worktrees" / "mine-wt"
        admin.mkdir(parents=True)
        (wt / ".git").write_text("gitdir: %s\n" % admin)
        self.wt = str(wt)

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_judgement(self):
        sc = wslib.Scope(str(self.t / "a" / "mine"), exclude=[str(self.t / "scratch")])
        self.assertEqual(sc.sibling(str(self.t / "b" / "other" / "x.py")), str(self.t / "b" / "other"), "다른 폴더에 있어도 다른 저장소")
        self.assertIsNone(sc.sibling(str(self.t / "a" / "mine" / "x.py")))
        self.assertIsNone(sc.sibling(str(self.t / "a" / "mine" / "vendor" / "lib" / "x")), "이 저장소 안에 든 저장소는 이 저장소 쪽")
        self.assertIsNone(sc.sibling(self.wt + "/x.py"), "같은 저장소의 worktree 는 이 저장소")
        self.assertIsNone(sc.sibling(str(self.t / "scratch" / "s" / "x")), "뺀 저장소는 다른 저장소가 아니다")
        self.assertIsNone(sc.sibling(str(self.t / "b" / "plain.txt")), "저장소 밖 경로")
        from_wt = wslib.Scope(self.wt, exclude=[])
        self.assertIsNone(from_wt.sibling(str(self.t / "a" / "mine" / "x.py")), "worktree 세션에서 본 저장소는 같은 저장소")
        self.assertEqual(from_wt.sibling(str(self.t / "b" / "other")), str(self.t / "b" / "other"))

    def test_dotfiles_home_and_config_are_not_other_repos(self):
        # 홈이나 ~/.claude 를 git 으로 관리하는 사람(dotfiles)도 memory, 계획, 설정 쓰기가 스킬 전에 막히지 않아야 한다.
        home, cfg = self.t / "home", self.t / "home" / ".claude"
        (cfg / ".git").mkdir(parents=True)
        old = {k: os.environ.get(k) for k in ("HOME", "CLAUDE_CONFIG_DIR")}
        try:
            os.environ["HOME"] = str(home)
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            sc = wslib.Scope(str(self.t / "a" / "mine"), exclude=[])
            self.assertIsNone(sc.sibling(str(cfg / "projects" / "p" / "memory" / "MEMORY.md")), "~/.claude 저장소")
            (home / ".git").mkdir()
            (cfg / ".git").rmdir()
            sc = wslib.Scope(str(self.t / "a" / "mine"), exclude=[])
            self.assertIsNone(sc.sibling(str(home / "notes.txt")), "홈 저장소")
            self.assertEqual(sc.sibling(str(self.t / "b" / "other" / "x")), str(self.t / "b" / "other"), "다른 저장소는 그대로")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_inside_handles_case_and_separators(self):
        self.assertTrue(wslib.inside(os.path.join("r", "a", "x"), os.path.join("r", "a")))
        self.assertTrue(wslib.inside("r/a/x", "r/a/"))
        self.assertFalse(wslib.inside("r/ab/x", "r/a"))

    def test_list_keys_are_user_only(self):
        # 저장소 제외를 저장소 층이 정하면 클론한 저장소가 게이트를 비켜 간다. 리터럴로 적은 사본이 known_repos 와 어긋나지 않게.
        self.assertLessEqual(wslib.known_repos.KNOWN_REPOS_USER_ONLY, wslib.ENV_USER_ONLY)

    def test_settings_read_lazily(self):
        calls = []
        sc = wslib.Scope(str(self.t / "a" / "mine"), load=lambda: calls.append(1) or {"HARNESS_WORKSPACE_EXCLUDE": str(self.t / "b")})
        self.assertIsNone(sc.sibling(str(self.t / "a" / "mine" / "x.py")))
        self.assertEqual(calls, [], "이 저장소 안 경로는 설정을 읽지 않는다")
        self.assertIsNone(sc.sibling(str(self.t / "b" / "other" / "x")), "사용자 제외")
        self.assertEqual(calls, [1])
        self.assertIn(tempfile.gettempdir(), sc.exclude(), "기본 제외")


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
        for n in ("mine", "other", "x-kb"):
            self.session(self.ws / n)

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, cwd):
        """가짜 설정 디렉터리의 projects/ 에 cwd 가 든 세션 기록 하나(지도와 알림이 저장소를 찾는 곳)."""
        d = self.t / "cfg" / "projects" / ("-" + str(cwd).strip("/").replace("/", "-"))
        d.mkdir(parents=True, exist_ok=True)
        (d / "s.jsonl").write_text(json.dumps({"type": "user", "cwd": str(cwd)}) + "\n")

    def options(self, **opts):
        (self.t / "cfg" / "settings.json").write_text(json.dumps({"pluginConfigs": {"qwreey-workspace@m": {"options": opts}}}))

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        e.pop("CLAUDE_PLUGIN_DATA", None)
        e.update(TMPDIR=str(self.t / "tmp"), CLAUDE_CONFIG_DIR=str(self.t / "cfg"), HARNESS_ENV=str(self.t / "no-user.env"),
                 CLAUDE_PROJECT_DIR=self.proj, QWREEY_HARNESS_SALT_FILE=str(self.t / "salt"))  # nonce 는 고정 salt 로
        (self.t / "salt").write_text("00" * 32)
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
            self.assertRegex(reason, r'^<harness-hook name="workspace-gate" level="action" nonce="[0-9a-f]{12}">\n')
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

    def test_read_notes_once(self):
        out = self.pre("Read", {"file_path": self.sibling()})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertRegex(ctx, r'^<harness-hook name="workspace-gate" level="info" nonce="[0-9a-f]{12}">\n')
        self.assertIn("qwreey-workspace:workspace", ctx)
        self.assertIn("Reading `%s` is fine" % (self.ws / "other"), ctx)
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

    def test_repo_anywhere_without_workspace(self):
        far = self.t / "Documents" / "far"
        (far / ".git").mkdir(parents=True)
        out = self.pre("Write", {"file_path": str(far / "a.txt")})
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("This changes the repo `%s`" % far, out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.pre("Write", {"file_path": str(self.t / "Documents" / "notes.txt")}), "저장소 밖은 막지 않는다")
        out = self.pre("Write", {"file_path": str(far / "b.txt")}, HOME=str(self.t))
        self.assertIn("This changes the repo `~/Documents/far`", out["hookSpecificOutput"]["permissionDecisionReason"], "홈 아래는 ~/ 꼴")

    def test_off_switch(self):
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}, HARNESS_WORKSPACE_GATE="off"))
        self.options(harness_workspace_gate=False)
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}), "/config 옵션으로 끈다")
        self.options(harness_workspace_gate=True)
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")

    def test_excluded_repos_pass(self):
        self.options(harness_workspace_exclude=str(self.ws / "other"))
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}))
        scratch = self.t / "tmp" / "scratch"
        (scratch / ".git").mkdir(parents=True)
        self.assertIsNone(self.pre("Write", {"file_path": str(scratch / "a")}), "시스템 임시 폴더(TMPDIR) 아래는 기본 제외")

    def test_repo_layers_cannot_exclude(self):
        claude = Path(self.proj) / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / "harness.local.env").write_text("HARNESS_WORKSPACE_EXCLUDE=%s\n" % self.ws)
        self.assertEqual(self.decision(self.pre("Write", {"file_path": self.sibling()})), "deny")

    def test_harness_env_file_switch(self):
        (self.t / "cfg" / "harness.env").write_text("HARNESS_WORKSPACE_GATE=off\n")
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}, HARNESS_ENV=str(self.t / "cfg" / "harness.env")))

    def test_repo_layers_cannot_open_the_gate(self):
        # 게이트 스위치는 사용자 전용: 저장소가 커밋한 파일로 끌 수 없다. 설치된 lib 가 막지 않는 옛 판이어도 같다.
        (self.t / "cfg" / "lib").mkdir()
        (self.t / "cfg" / "lib" / "harness_env.py").write_text((ROOT.parent.parent / "home/.claude/lib/harness_env.py").read_text()
                                                              + "\nUSER_ONLY = frozenset()\nLEGACY_USER_ONLY = frozenset()\n")
        claude = Path(self.proj) / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / "harness.env").write_text("HARNESS_WORKSPACE_GATE=off\n")
        (claude / "harness.local.env").write_text("HARNESS_WORKSPACE_GATE=off\n")
        self.assertIsNotNone(self.pre("Write", {"file_path": self.sibling()}))
        (self.t / "cfg" / "harness.env").write_text("HARNESS_WORKSPACE_GATE=off\n")
        self.assertIsNone(self.pre("Write", {"file_path": self.sibling()}, HARNESS_ENV=str(self.t / "cfg" / "harness.env")), "사용자 층은 끈다")

    def test_symlink_path_not_sibling(self):
        # 홈의 rules 파일은 다른 저장소로 이어진 symlink 일 수 있다. normpath 만 쓰므로 다른 저장소 경로가 아니다.
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
        self.assertEqual(lines[0], "Repos on this machine (3; `*-kb` first):")
        self.assertEqual(lines[1], "- x-kb `%s`: Knowledge." % (self.ws / "x-kb"), out)
        self.assertIn("- mine `%s` (this session's repo)" % (self.ws / "mine"), out)
        self.assertIn("- other `%s`: Other repo does things." % (self.ws / "other"), out)
        self.assertNotIn("# Other", out)

    def test_extra_exclude_and_home(self):
        home = self.t / "home"
        r = home / "Documents" / "proj"
        (r / ".git").mkdir(parents=True)
        self.options(harness_workspace_extra="~/Documents", harness_workspace_exclude=str(self.ws / "other"))
        out = self.run_map(HOME=str(home))
        self.assertIn("- proj `~/Documents/proj`", out)
        self.assertNotIn("- other", out)

    def test_legacy_workspace(self):
        shutil.rmtree(self.t / "cfg" / "projects")
        (self.ws / "legacy" / ".git").mkdir(parents=True)
        self.assertIn("- legacy `", self.run_map(HARNESS_WORKSPACE=str(self.ws)))

    def test_nothing_known(self):
        shutil.rmtree(self.t / "cfg" / "projects")
        self.assertTrue(self.run_map().startswith("No other repos known yet."))
        self.session(self.ws / "mine")
        self.assertTrue(self.run_map().startswith("No other repos known yet."), "이 저장소만 있으면 다른 저장소가 없다")

    def test_first_line_cap_and_fallback(self):
        head = "- other `%s`: " % (self.ws / "other")
        (self.ws / "other" / "CLAUDE.md").write_text("# T\n\n" + "a" * 300 + "\n")
        self.assertIn(head + "a" * 120 + "\n", self.run_map() + "\n")
        (self.ws / "other" / "CLAUDE.md").write_text("# only title\n")
        (self.ws / "other" / "README.md").write_text("---\nx: y\n---\n# R\n\nFrom readme.\n")
        self.assertIn(head + "From readme.", self.run_map())


if __name__ == "__main__":
    unittest.main()
