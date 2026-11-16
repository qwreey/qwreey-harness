"""오래된 worktree 알림(scripts/stale_worktrees.py) 단위 테스트. 실행: python3 -I tests/test_stale_worktrees.py  (모델 호출 없음)

임시 작업공간에 git 저장소와 worktree 를 만들고 커밋 시각(GIT_COMMITTER_DATE)과 mtime(os.utime)으로 나이를 맞춘다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "stale_worktrees.py"
CANON = ROOT.parent.parent / "home" / ".claude" / "lib" / "harness_env.py"
sys.path.insert(0, str(SCRIPTS))
import stale_worktrees as sw  # noqa: E402

DAY = 86400
NOW = time.time()
KEY = "HARNESS_WORKSPACE_STALE_WORKTREE_DAYS"


def git_env(when=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "HARNESS_"))}
    e.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
             GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    if when is not None:
        e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = "@%d +0000" % int(when)
    return e


class Base(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="ws-stalewt-"))
        self.ws = self.t / "ws"
        self.repo = self.ws / "repo"
        (self.t / "tmp").mkdir()
        (self.t / "cfg").mkdir()
        (self.t / "salt").write_text("00" * 32)
        self.repo.mkdir(parents=True)
        self.g("init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("a\n")
        self.g("add", "a.txt")
        self.g("commit", "-qm", "init", when=NOW - 100 * DAY)
        self.admin = Path(self.g("rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "worktrees"

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def g(self, *args, cwd=None, when=None):
        p = subprocess.run(["git", "-C", str(cwd or self.repo)] + list(args), capture_output=True, text=True, env=git_env(when), timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def add(self, rel, days, branch=None, commit_days=None):
        """worktree 를 만들고 나이를 days 로 맞춘다. commit_days 면 그 나이의 커밋을 하나 더 한다."""
        path = self.repo / rel if not rel.startswith("/") else Path(rel)
        branch = branch or "b-" + path.name
        self.g("worktree", "add", "-q", "-b", branch, str(path))
        if commit_days is not None:
            (path / "c.txt").write_text(branch)
            self.g("add", "c.txt", cwd=path)
            self.g("commit", "-qm", "c", cwd=path, when=NOW - commit_days * DAY)
        self.age(path, days)
        return path

    def age(self, path, days):
        ts = NOW - days * DAY
        adm = self.admin / path.name
        for p in (path, adm / "index", adm / "HEAD", adm / "logs" / "HEAD"):
            if p.exists():
                os.utime(p, (ts, ts))

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("HARNESS_", "GIT_")) and k != "CLAUDE_PROJECT_DIR"}
        e.update(TMPDIR=str(self.t / "tmp"), CLAUDE_CONFIG_DIR=str(self.t / "cfg"), HARNESS_WORKSPACE=str(self.ws),
                 QWREEY_HARNESS_SALT_FILE=str(self.t / "salt"))
        e.update(kw)
        return {k: v for k, v in e.items() if v is not None}

    def run_hook(self, sid="s1", cwd=None, extra=None, **kw):
        data = {"session_id": sid, "hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd or self.repo)}
        data.update(extra or {})
        p = subprocess.run([sys.executable, "-I", str(SCRIPT)], input=json.dumps(data), capture_output=True, text=True,
                           env=self.env(**kw), timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout:
            return ""
        out = json.loads(p.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        return out["additionalContext"]


class Scan(Base):
    def test_ages_locked_prunable_live(self):
        old = self.add(".claude/worktrees/agent-old", 40)
        self.add(".claude/worktrees/agent-new", 2)
        recent_commit = self.add(".claude/worktrees/agent-rc", 40, commit_days=1)
        locked = self.add(".claude/worktrees/agent-locked", 50)
        self.g("worktree", "lock", str(locked))
        sib = self.add(str(self.ws / "repo-side"), 20, branch="side")
        live = self.add(".claude/worktrees/agent-live", 60)
        gone = self.add(".claude/worktrees/agent-gone", 1)
        shutil.rmtree(gone)
        proc = self.t / "proc"
        for pid, comm, cwd in (("11", "claude", live / "sub"), ("12", "bash", sib), ("13", "codex", self.t)):
            (proc / pid).mkdir(parents=True)
            (proc / pid / "comm").write_text(comm + "\n")
            os.symlink(cwd, proc / pid / "cwd")
        (live / "sub").mkdir()
        self.age(live, 60)
        stale, gone_l, main = sw.scan(str(self.repo), NOW, 14, proc=str(proc))
        self.assertEqual(main, str(self.repo))
        self.assertEqual([w["path"] for w in stale], [str(old), str(sib)], "오래된 순, 잠금, 살아 있는 세션, 최근 커밋 제외")
        self.assertEqual(int(stale[0]["age"]), 40)
        self.assertEqual(stale[1]["branch"], "side")
        self.assertEqual([w["path"] for w in gone_l], [str(gone)], "prunable 은 나이와 무관")
        self.assertNotIn(str(recent_commit), [w["path"] for w in stale])

    def test_session_inside_a_worktree_skips_itself_and_main(self):
        a = self.add(".claude/worktrees/agent-a", 30)
        b = self.add(".claude/worktrees/agent-b", 30)
        stale, _, main = sw.scan(str(a), NOW, 14, proc=str(self.t / "noproc"))
        self.assertEqual(([w["path"] for w in stale], main), ([str(b)], str(self.repo)))

    def test_no_worktrees(self):
        self.assertEqual(sw.scan(str(self.repo), NOW, 14, proc=str(self.t / "noproc")), ([], [], ""))


class Hook(Base):
    def test_line_and_read_only(self):
        old = self.add(".claude/worktrees/agent-old", 40)
        (old / "a.txt").write_text("changed\n")
        self.age(old, 40)
        self.add(".claude/worktrees/agent-new", 1)
        gone = self.add(".claude/worktrees/agent-gone", 3)
        shutil.rmtree(gone)
        watched = [old, self.admin / "agent-old" / "index", self.admin / "agent-old" / "HEAD", self.repo / ".git" / "index"]
        before = [os.stat(p).st_mtime_ns for p in watched]
        ctx = self.run_hook()
        self.assertEqual([os.stat(p).st_mtime_ns for p in watched], before, "훅은 아무것도 쓰지 않는다(index 갱신 포함)")
        self.assertTrue(ctx.startswith('<harness-hook name="stale-worktrees" level="info" nonce="985461182738">\n'), ctx[:120])
        self.assertTrue(ctx.endswith("\n</harness-hook>"))
        self.assertIn("1 worktree untouched for 14+ days", ctx)
        self.assertIn("`.claude/worktrees/agent-old` (branch b-agent-old, 40 days, uncommitted changes)", ctx)
        self.assertIn("(prunable): `.claude/worktrees/agent-gone` (branch b-agent-gone)", ctx)
        self.assertIn("qwreey-workspace:workspace", ctx)
        self.assertNotIn("agent-new", ctx)
        for word in ("git worktree remove", "prune", "rm -rf"):
            self.assertNotIn(word, ctx, "지우는 명령을 내지 않는다")

    def test_more_than_shown(self):
        for i in range(5):
            self.add(".claude/worktrees/agent-%d" % i, 20 + i)
        ctx = self.run_hook()
        self.assertIn("5 worktrees untouched", ctx)
        self.assertIn("agent-4` (branch b-agent-4, 24 days)", ctx)
        self.assertIn("and 2 more", ctx)
        self.assertNotIn("agent-0`", ctx)

    def test_once_per_session_and_events(self):
        self.add(".claude/worktrees/agent-old", 40)
        self.assertEqual(self.run_hook(extra={"source": "compact"}), "", "compact 뒤에는 내지 않는다")
        self.assertEqual(self.run_hook(extra={"agent_id": "a1"}), "", "서브에이전트는 건너뛴다")
        self.assertEqual(self.run_hook(extra={"hook_event_name": "SubagentStart"}), "")
        self.assertIn("agent-old", self.run_hook())
        self.assertEqual(self.run_hook(extra={"source": "resume"}), "", "세션마다 한 번")
        self.assertIn("agent-old", self.run_hook(sid="s2", extra={"source": "clear"}))

    def test_switch_and_threshold(self):
        self.add(".claude/worktrees/agent-old", 20)
        for v in ("off", "0", "", "junk"):
            self.assertEqual(self.run_hook(sid="off-" + v, **{KEY: v}), "", v)
        self.assertEqual(self.run_hook(sid="t30", **{KEY: "30"}), "")
        self.assertIn("10+ days", self.run_hook(sid="t10", **{KEY: "10"}))

    def test_repo_layer_sets_threshold(self):
        self.add(".claude/worktrees/agent-old", 20)
        (self.repo / ".claude").mkdir(exist_ok=True)  # .claude/worktrees 가 이미 만들었다
        (self.repo / ".claude" / "harness.env").write_text(KEY + "=30\n")
        self.assertEqual(self.run_hook(sid="r1"), "")
        (self.repo / ".claude" / "harness.local.env").write_text(KEY + "=7\n")
        self.assertIn("7+ days", self.run_hook(sid="r2"))

    def test_older_installed_loader_is_not_used(self):
        # 설치된 ~/.claude/lib 판이 이 키를 몰라도 플러그인은 옆 사본과 자기 기본값을 쓴다.
        self.add(".claude/worktrees/agent-old", 20)
        lib = self.t / "cfg" / "lib"
        lib.mkdir()
        text = "".join(l for l in CANON.read_text(encoding="utf-8").splitlines(True) if KEY not in l)
        (lib / "harness_env.py").write_text(text, encoding="utf-8")
        self.assertIn("14+ days", self.run_hook())

    def test_quiet_without_workspace_or_repo(self):
        self.add(".claude/worktrees/agent-old", 40)
        self.assertEqual(self.run_hook(sid="w1", HARNESS_WORKSPACE=""), "", "작업공간이 없으면 플러그인은 아무것도 하지 않는다")
        self.assertEqual(self.run_hook(sid="w2", cwd=self.t), "", "git 저장소가 아니면 조용히")
        p = subprocess.run([sys.executable, "-I", str(SCRIPT)], input="not json", capture_output=True, text=True, env=self.env(), timeout=30)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_registered_in_hooks_json(self):
        groups = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["SessionStart"]
        hit = [g for g in groups if any("stale_worktrees.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(hit), 1)
        self.assertNotIn("compact", hit[0]["matcher"])
        self.assertEqual(sorted(hit[0]["matcher"].split("|")), ["clear", "resume", "startup"])


if __name__ == "__main__":
    unittest.main()
