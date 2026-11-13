"""설치 어긋남·방치 작업 알림 테스트. 실행: timeout 120 python3 -I tests/test_notices.py  (모델 호출 없음)"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
DRIFT, STALE = SCRIPTS / "drift.py", SCRIPTS / "stale_work.py"


def run(script, payload, env, cwd=None):
    p = subprocess.run([sys.executable, "-I", str(script)], input=json.dumps(payload), capture_output=True, text=True,
                       env=env, cwd=cwd, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def wjson(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


class Drift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.cfg, self.proj, self.mk = t / "cfg", t / "proj", t / "market"
        self.proj.mkdir()
        self.env = {"PATH": os.environ["PATH"], "TMPDIR": str(t / "tmp"), "CLAUDE_CONFIG_DIR": str(self.cfg), "CLAUDE_PROJECT_DIR": str(self.proj)}
        (t / "tmp").mkdir()
        wjson(self.cfg / "settings.json", {"enabledPlugins": {"a@m": True, "b@m": True, "off@m": False, "x@gone": True}})
        wjson(self.cfg / "plugins" / "known_marketplaces.json", {"m": {"source": {"source": "directory", "path": str(self.mk)}, "installLocation": str(self.mk)}})
        wjson(self.mk / ".claude-plugin" / "marketplace.json", {"plugins": [
            {"name": "a", "source": "./plugins/a"}, {"name": "b", "source": "./plugins/b"}, {"name": "off", "source": "./plugins/off"},
            {"name": "ext", "source": {"source": "github", "repo": "x/y"}}]})
        for n, v in (("a", "0.5.1"), ("b", "1.0.0"), ("off", "9.0.0")):
            wjson(self.mk / "plugins" / n / ".claude-plugin" / "plugin.json", {"version": v})
        self.set_installed({"a@m": "0.5.0", "b@m": "1.0.0", "off@m": "1.0.0"})

    def tearDown(self):
        self.tmp.cleanup()

    def set_installed(self, vers):
        wjson(self.cfg / "plugins" / "installed_plugins.json", {"version": 2, "plugins": {k: [{"scope": "user", "version": v}] for k, v in vers.items()}})

    def start(self, **extra):
        return run(DRIFT, {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(self.proj), **extra}, {**self.env, **extra.pop("env", {})})

    def test_old_plugin_reported_once_per_day(self):
        out = self.start()
        msg = out["systemMessage"]
        self.assertIn("a 0.5.0 → 0.5.1", msg)
        self.assertIn("claude plugin update a@m", msg)
        self.assertNotIn("b 1.0.0", msg)      # 같은 버전
        self.assertNotIn("off", msg)          # 꺼 둔 플러그인
        self.assertIsNone(self.start())       # 같은 내용은 하루 한 번
        self.set_installed({"a@m": "0.4.0", "b@m": "1.0.0"})
        self.assertIn("0.4.0 → 0.5.1", self.start()["systemMessage"])  # 바뀌면 바로

    def test_no_drift_no_output_and_clear_rearms(self):
        self.set_installed({"a@m": "0.5.1", "b@m": "1.0.0"})
        self.assertIsNone(self.start())
        self.set_installed({"a@m": "0.5.0", "b@m": "1.0.0"})
        self.assertIsNotNone(self.start())

    def test_off_compact_subagent_and_garbage(self):
        self.assertIsNone(run(DRIFT, {"source": "startup"}, {**self.env, "HARNESS_Q_DRIFT": "off"}))
        self.assertIsNone(run(DRIFT, {"source": "compact", "cwd": str(self.proj)}, self.env))
        self.assertIsNone(run(DRIFT, {"source": "startup", "agent_id": "x"}, self.env))
        (self.cfg / "plugins" / "installed_plugins.json").write_text("{bad")
        self.assertIsNone(self.start())       # fail-open

    def test_home_sync_only_in_doctor_repo(self):
        self.set_installed({"a@m": "0.5.1", "b@m": "1.0.0"})
        self.assertIsNone(self.start())
        (self.proj / "tools").mkdir()
        (self.proj / "home").mkdir()
        (self.proj / "home" / "MANIFEST").write_text("")
        (self.proj / "tools" / "home-sync.sh").write_text(
            "echo 'CLAUDE.md                                다름 (정본이 더 새로움 → diff 후 apply)'\n"
            "echo 'settings.json                            6/8 적용, 미적용: 0007, 0008'\n"
            "echo 'harness.env                              같음'\n"
            "echo; echo '# 이전에 관리했지만 지금 MANIFEST 에 없음 [상태 파일] — 삭제는 사용자가 한다'\n"
            "echo 'rules/x.md                               링크 → /y'\n"
            "echo '  제안: rm /z'\n"
            "echo 'plugins: settings 에 켠 플러그인이 모두 설치돼 있다'\n")
        msg = self.start()["systemMessage"]
        self.assertIn("다른 파일 1개", msg)
        self.assertIn("미적용 마이그레이션 2개", msg)
        self.assertIn("고아 1개", msg)

    def test_home_sync_clean_is_silent(self):
        self.set_installed({"a@m": "0.5.1", "b@m": "1.0.0"})
        for d in ("tools", "home"):
            (self.proj / d).mkdir()
        (self.proj / "home" / "MANIFEST").write_text("")
        (self.proj / "tools" / "home-sync.sh").write_text("echo 'CLAUDE.md   같음'\necho '(고아 없음)'\necho 'plugins: ok'\n")
        self.assertIsNone(self.start())


class Stale(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.t = t
        (t / "tmp").mkdir()
        self.env = {"PATH": os.environ["PATH"], "TMPDIR": str(t / "tmp"),
                    "HARNESS_Q_STALE_IDLE_MIN": "0.05", "HARNESS_Q_STALE_AGE_MIN": "0.1", "HARNESS_Q_STALE_LONG_MIN": "0.15",
                    "QWREEY_HARNESS_SALT_FILE": str(t / "salt")}  # nonce 는 고정 salt 로
        (t / "salt").write_text("00" * 32)
        self.tp = t / "s1.jsonl"
        self.tp.write_text("")
        self.agent = t / "s1" / "subagents" / "agent-abc.jsonl"
        self.agent.parent.mkdir(parents=True)
        self.agent.write_text("x")
        os.utime(self.agent, (time.time() - 3600, time.time() - 3600))  # 이미 한 시간 조용함

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, ev, tasks, **kw):
        return {"hook_event_name": ev, "session_id": "s1", "transcript_path": str(self.tp), "background_tasks": tasks, **kw}

    SUB = {"id": "abc", "type": "subagent", "status": "running", "description": "slow review", "agent_type": "general-purpose"}

    def test_stalled_then_model_and_user_once(self):
        self.assertIsNone(run(STALE, self.payload("Stop", [self.SUB]), self.env))   # 막 봄: 나이 부족
        time.sleep(7)                                                                 # 나이 0.1분 = 6초
        out = run(STALE, self.payload("Stop", [self.SUB]), self.env)
        self.assertIn("멈췄거나 대기 중일 수 있습니다", out["systemMessage"])
        self.assertIn("slow review", out["systemMessage"])
        self.assertIsNone(run(STALE, self.payload("Stop", [self.SUB]), self.env))   # 상태당 한 번
        ctx = run(STALE, {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "hi"}, self.env)
        text = ctx["hookSpecificOutput"]["additionalContext"]
        self.assertRegex(text, r'<harness-hook name="stale-work" level="warn" nonce="[0-9a-f]{12}">\n')
        self.assertIn("may be stalled or waiting", text)
        self.assertIsNone(run(STALE, {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "hi"}, self.env))

    def test_workflow_without_signal_is_never_stalled_only_long(self):
        wf = {"id": "wg1", "type": "workflow", "status": "running", "name": "tiny"}
        run(STALE, self.payload("Stop", [wf]), self.env)
        time.sleep(10)                                                                # 나이 0.15분 = 9초
        out = run(STALE, self.payload("Stop", [wf]), self.env)
        self.assertIn("실행 중입니다", out["systemMessage"])
        self.assertNotIn("멈췄", out["systemMessage"])
        ctx = run(STALE, {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, self.env)
        self.assertIn('level="info"', ctx["hookSpecificOutput"]["additionalContext"])

    def test_progress_resets_and_exclusions(self):
        env = {**self.env, "HARNESS_Q_STALE_IDLE_MIN": "5", "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_LONG_MIN": "999"}
        os.utime(self.agent, None)                                                    # 방금 진척
        self.assertIsNone(run(STALE, self.payload("Stop", [self.SUB]), env))
        mon = {"id": "m1", "type": "monitor", "status": "running", "description": "watch"}
        self.assertIsNone(run(STALE, self.payload("Stop", [mon]), {**self.env, "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_IDLE_MIN": "0", "HARNESS_Q_STALE_LONG_MIN": "0"}))
        # SubagentStop 은 끝난 자기 자신을 세지 않고, 사용자 줄은 Stop 이 낸다
        e0 = {**self.env, "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_IDLE_MIN": "0"}
        self.assertIsNone(run(STALE, self.payload("SubagentStop", [self.SUB], agent_id="abc"), e0))
        self.assertIsNone(run(STALE, self.payload("SubagentStop", [self.SUB], agent_id="zzz"), e0))
        self.assertIn("systemMessage", run(STALE, self.payload("Stop", [self.SUB]), e0))

    def test_off_and_fail_open(self):
        e0 = {**self.env, "HARNESS_Q_STALE_AGE_MIN": "0", "HARNESS_Q_STALE_IDLE_MIN": "0", "HARNESS_Q_STALE": "off"}
        self.assertIsNone(run(STALE, self.payload("Stop", [self.SUB]), e0))
        self.assertIsNone(run(STALE, {"hook_event_name": "Stop", "session_id": "s1"}, self.env))
        self.assertIsNone(run(STALE, {"hook_event_name": "Stop", "session_id": "s1", "background_tasks": "x"}, self.env))
        self.assertIsNone(run(STALE, self.payload("Stop", []), self.env))


if __name__ == "__main__":
    unittest.main()
