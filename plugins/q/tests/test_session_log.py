"""session-log 단위 테스트. 실행: python3 -I tests/test_session_log.py  (모델 호출 없음: fake_claude.py)"""
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
sys.path.insert(0, str(SCRIPTS))
FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_claude.py"


def rec(**o):
    return json.dumps(o, ensure_ascii=False) + "\n"


def human(text, ts="2026-11-10T01:00:00Z", cwd="/x"):
    return rec(type="user", origin={"kind": "human"}, promptSource="typed", timestamp=ts, cwd=cwd,
               message={"role": "user", "content": text})


def agent(text=None, tools=(), ts="2026-11-10T01:01:00Z"):
    c = ([{"type": "text", "text": text}] if text else []) + list(tools)
    return rec(type="assistant", timestamp=ts, message={"role": "assistant", "content": c})


def bash(cmd, i="t1"):
    return {"type": "tool_use", "id": i, "name": "Bash", "input": {"command": cmd, "description": "d"}}


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.home = t / "store"
        self.proj = t / "proj"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        self.tp = t / "sess-0001.jsonl"
        self.sid = "sess-0001-aaaa"
        self.tp = t / f"{self.sid}.jsonl"
        self.env = {"SESSION_LOG_HOME": str(self.home), "SESSION_LOG_CLAUDE": str(FAKE), "HARNESS_ENV": "/nonexistent",
                    "SESSION_LOG_MIN_CHARS": "10", "SESSION_LOG_FORCE_MIN_CHARS": "10",
                    "XDG_RUNTIME_DIR": str(t)}  # 기계 전체 슬롯 잠금도 격리
        self.old = {k: os.environ.get(k) for k in list(self.env) + ["FAKE_MODE", "CLAUDE_PROJECT_DIR", "SESSION_LOG_NESTED",
                                                                     "SESSION_LOG_PENDING_STRONG_COUNT", "SESSION_LOG_HANDOVER_MAX_DAYS"]}
        os.environ.update(self.env)
        os.environ.pop("SESSION_LOG_NESTED", None)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.proj)
        os.chmod(FAKE, 0o755)
        from sllib import config
        config._CACHE = None

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from sllib import config
        config._CACHE = None
        self.tmp.cleanup()

    def write(self, *lines, mode="w"):
        with open(self.tp, mode, encoding="utf-8") as f:
            f.write("".join(lines))

    def base_transcript(self):
        self.write(
            human("값을 4242 로 해 줘. 그리고 <b>태그</b> 는 조심", cwd=str(self.proj)),
            agent("알겠다", [bash("git commit -m 'feat: x'")]),
            rec(type="attachment", timestamp="2026-11-10T01:02:00Z",
                attachment={"type": "queued_command", "origin": {"kind": "human"}, "prompt": "작업 중 지시: 테스트도"}),
            rec(type="user", isMeta=True, message={"content": "<system-reminder>noise</system-reminder>"}),
            agent("토큰 sk-ant-abcdefghijklmnopqrstuvwxyz0123 을 썼다"),
        )

    def hook(self, event, payload, extra_env=None):
        env = dict(os.environ, **(extra_env or {}))
        p = subprocess.run([sys.executable, "-I", str(SCRIPTS / "hook.py"), event], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def store(self):
        from sllib.store import Store
        from sllib.paths import project_root
        return Store(project_root(self.proj))


class TestPaths(Env):
    def test_worktree_maps_to_main_checkout(self):
        from sllib.paths import project_key, project_root
        subprocess.run(["git", "-C", str(self.proj), "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q",
                        "--allow-empty", "-m", "init"], check=True)
        wt = Path(self.tmp.name) / "wt"
        subprocess.run(["git", "-C", str(self.proj), "worktree", "add", "-q", str(wt)], check=True)
        (wt / "sub").mkdir()
        self.assertEqual(project_root(wt / "sub"), self.proj.resolve())
        self.assertEqual(project_key(project_root(wt)), project_key(self.proj.resolve()))

    def test_non_git(self):
        from sllib.paths import project_root
        d = Path(self.tmp.name) / "plain"
        d.mkdir()
        self.assertEqual(project_root(d), d.resolve())


class TestExtract(Env):
    def test_extract_and_partial_line(self):
        from sllib import extract as ex
        self.base_transcript()
        with open(self.tp, "a") as f:
            f.write('{"type":"user","partial')  # 덜 써진 줄
        e = ex.extract(str(self.tp))
        texts = "\n".join(x.text for x in e.entries)
        self.assertIn("[L1 ", texts)
        self.assertIn("user] 값을 4242", texts)
        self.assertIn("[COMMIT] feat: x", texts)
        self.assertIn("user(queued)] 작업 중 지시", texts)
        self.assertNotIn("noise", texts)
        self.assertNotIn("sk-ant-abcdef", texts)
        self.assertIn("[MASKED:anthropic-key]", texts)
        self.assertEqual(e.end_line, 5)
        self.assertEqual(e.end_byte, len(self.tp.read_bytes().rsplit(b"\n", 1)[0]) + 1)
        # 오프셋부터 다시 읽으면 줄 번호가 이어진다
        e2 = ex.extract(str(self.tp), e.entries[1].end_byte, e.entries[1].end_line)
        self.assertEqual(e2.entries[0].line, 3)


class TestVerify(Env):
    def test_marks_and_drop(self):
        from sllib import verify
        src = {1: verify.norm("사용자: 값을 4242 로 해 줘"), 2: verify.norm("다른 줄 777 있음")}
        body = "\n".join([
            "### 사용자 지시와 정정",
            '- "값을 4242 로 해 줘" (L1) — ok',
            '- "지어낸 말입니다" (L1) — bad',
            "### 결정",
            "- 4242 확정 (L1)",
            "- 777 확정 (L1)",
            "- 31337 확정 (L1)",
            "- 범위 밖 (L99)",
        ])
        out, c = verify.check_section(body, src)
        self.assertNotIn("지어낸", out)
        self.assertEqual(c["dropped"], 1)
        self.assertEqual(c["quote_bad"], 1)
        self.assertIn("777 확정 (L1) ⚠근거 줄 다름", out)
        self.assertIn("31337 확정 (L1) ⚠원문 불일치", out)
        self.assertIn("범위 밖 (L99) ⚠근거 줄 없음", out)
        self.assertIn("- 4242 확정 (L1)\n", out + "\n")


class TestFlush(Env):
    def test_flush_writes_external_only(self):
        from sllib import worker
        self.base_transcript()
        st = self.store()
        r = worker.flush(st, self.sid, str(self.tp), "PreCompact(manual)", force=True)
        self.assertEqual(r["sections"], 1, r)
        self.assertEqual(list(p for p in self.proj.rglob("*") if ".git" not in p.parts), [])  # 저장소에는 아무것도 없다
        rid = r["rids"][0]
        text = st.record_path(rid).read_text()
        self.assertTrue(text.startswith("---\ntitle: "))
        self.assertIn("kind: session", text)
        self.assertIn(f"session_id: {self.sid}", text)
        self.assertIn("id: sess-000-1 · summary: fake summary", text.replace(self.sid[:8], "sess-000"))
        self.assertIn("note: L1–L5", text)
        self.assertNotIn("never said", text)  # 지어낸 인용은 뺐다
        self.assertIn("31337 로 정했다 (L1) ⚠원문 불일치", text)
        self.assertIn("quote_bad: 1", text)
        self.assertEqual(st.pending()[0]["rid"], rid)
        self.assertEqual(st.notice_seq(), 1)
        # 다시 돌려도 새 절 없음
        r2 = worker.flush(st, self.sid, str(self.tp), "SessionEnd", force=True)
        self.assertEqual(r2["sections"], 0)
        # 덧붙이면 두 번째 절
        self.write(human("두 번째 지시 8080 포트", ts="2026-11-10T02:00:00Z"), agent("ok", ts="2026-11-10T02:01:00Z"), mode="a")
        r3 = worker.flush(st, self.sid, str(self.tp), "SessionEnd", force=True)
        self.assertEqual(r3["sections"], 1)
        text = st.record_path(rid).read_text()
        self.assertIn(f"id: {self.sid[:8]}-2", text)
        self.assertIn("note: L6–L7", text)
        self.assertEqual(st.wstate(self.sid)["line"], 7)

    def test_echo_and_failure_keep_offset(self):
        from sllib import worker
        self.base_transcript()
        st = self.store()
        os.environ["FAKE_MODE"] = "echo"
        r = worker.flush(st, self.sid, str(self.tp), "x", force=True)
        self.assertEqual(r["sections"], 0)
        self.assertEqual(st.wstate(self.sid).get("offset", 0), 0)
        self.assertEqual(st.wstate(self.sid)["failures"], 1)
        os.environ["FAKE_MODE"] = "fail"
        worker.flush(st, self.sid, str(self.tp), "x", force=True)
        r = worker.flush(st, self.sid, str(self.tp), "x", force=True)  # 3회째 → 자리표시 절
        self.assertEqual(r["sections"], 1)
        self.assertIn("요약 실패", st.record_path(r["rids"][0]).read_text())
        self.assertGreater(st.wstate(self.sid)["offset"], 0)

    def test_lock_sets_pending(self):
        from sllib import worker
        from sllib.store import flocked
        self.base_transcript()
        st = self.store()
        st.ensure()
        with flocked(st.state / f"{self.sid}.lock"):
            r = worker.flush(st, self.sid, str(self.tp), "x", force=True)
        self.assertTrue(r.get("locked"))
        self.assertTrue((st.state / f"{self.sid}.pending").exists())

    def test_budget_stop(self):
        from sllib import worker
        self.base_transcript()
        r = worker.flush(self.store(), self.sid, str(self.tp), "backfill", force=True, budget_left=0.0)
        self.assertTrue(r.get("budget_stop"))
        self.assertEqual(r["calls"], 0)


class TestImport(Env):
    def test_import_and_dismiss(self):
        from sllib import worker
        self.base_transcript()
        st = self.store()
        rid = worker.flush(st, self.sid, str(self.tp), "x", force=True)["rids"][0]
        cli = [sys.executable, "-I", str(SCRIPTS / "cli.py"), "--project", str(self.proj)]
        out = subprocess.run(cli + ["pending"], capture_output=True, text=True).stdout
        self.assertIn(rid, out)
        self.assertIn("~", out)
        subprocess.run(cli + ["import", rid], check=True, capture_output=True)
        self.assertTrue((self.proj / ".claude/session" / f"{rid}.md").exists())
        self.assertEqual(st.index()[rid]["status"], "imported")
        self.assertEqual(st.pending(), [])
        # 가져간 뒤 새 절이 붙으면 다시 pending
        self.write(human("추가 1234", ts="2026-11-10T03:00:00Z"), mode="a")
        worker.flush(st, self.sid, str(self.tp), "x", force=True)
        self.assertEqual(len(st.pending()), 1)
        subprocess.run(cli + ["dismiss", rid], check=True, capture_output=True)
        self.assertEqual(st.pending(), [])


class TestHooks(Env):
    def payload(self, **kw):
        return dict(session_id=self.sid, transcript_path=str(self.tp), cwd=str(self.proj), **kw)

    def ctx(self, out):
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else ""

    def seed(self, n_other=1):
        from sllib import worker
        self.base_transcript()
        st = self.store()
        worker.flush(st, self.sid, str(self.tp), "x", force=True)
        return st

    def test_session_start_handover_and_pending_once(self):
        st = self.seed()
        out = self.ctx(self.hook("SessionStart", self.payload(source="resume")))
        self.assertIn('<harness-hook name="session-log" level="warn">', out)  # 인계(info)+pending(warn) → 한 태그, 높은 쪽
        self.assertEqual(out.count("<harness-hook"), 1)
        self.assertIn("Handover from this session", out)
        self.assertIn("‹system-reminder›", out)          # 태그 무력화
        self.assertNotIn("<system-reminder>", out)
        self.assertNotIn("99999", out)                    # ⚠ 항목은 넣지 않는다
        self.assertIn("1 auto-summarized session record pending import", out)
        self.assertNotIn("가짜 요약이다", out)            # 자유 텍스트 요약은 넣지 않는다
        self.assertLessEqual(len(out.split("</harness-hook>")[0]), 800 + 200)
        out2 = self.ctx(self.hook("SessionStart", self.payload(source="resume")))
        self.assertNotIn("pending import", out2)          # 같은 회차에는 한 번

    def test_pending_reappears_after_compact(self):
        st = self.seed()
        self.assertIn("pending import", self.ctx(self.hook("SessionStart", self.payload(source="startup"))))
        self.assertNotIn("pending import", self.ctx(self.hook("PreToolUse", self.payload(
            tool_name="Bash", tool_input={"command": "ls"}))))
        c1 = self.ctx(self.hook("PreToolUse", self.payload(tool_name="Bash", tool_input={"command": "git add -A && git commit -m x"})))
        self.assertIn("about to commit", c1)
        self.assertEqual(self.hook("PreToolUse", self.payload(tool_name="Bash", tool_input={"command": "git commit -m y"})), "")
        # compact: PreCompact → SessionStart(compact) → PostCompact
        pre = self.hook("PreCompact", self.payload(trigger="manual", custom_instructions=""), {"SESSION_LOG_CLAUDE": "/bin/false"})
        self.assertIn('level="warn"', pre)
        self.assertIn("Session-log reminder for this compaction", pre)
        self.assertIn("값을 4242 로 해 줘", pre)            # 대조를 통과한 사용자 인용
        ss = self.ctx(self.hook("SessionStart", self.payload(source="compact")))
        self.assertIn("pending import", ss)                 # compact 뒤 다시 나온다
        self.assertIn("Session log for this session", ss)
        self.hook("PostCompact", self.payload(trigger="manual", compact_summary="SUMMARY"))
        hs = st.hstate(self.sid)
        self.assertEqual(hs["epoch"], 1)                    # 한 compact 에 한 번만 오른다
        self.assertTrue((st.state / f"{self.sid}.compact-1.md").exists())
        c2 = self.ctx(self.hook("PreToolUse", self.payload(tool_name="Bash", tool_input={"command": "git commit -m z"})))
        self.assertIn("about to commit", c2)                # 새 회차라 commit 알림도 다시

    def test_saved_notice_delivered_once(self):
        st = self.seed()
        self.hook("SessionStart", self.payload(source="startup"))  # 커서를 현재로
        from sllib import worker
        self.write(human("새 지시 5555", ts="2026-11-10T04:00:00Z"), mode="a")
        worker.flush(st, self.sid, str(self.tp), "PostToolUse", force=True)
        out = self.ctx(self.hook("PostToolUse", self.payload(tool_name="Read")))
        self.assertIn('level="info"', out)
        self.assertIn("Session log: saved 1 new section", out)
        self.assertIn(str(Path("records")), out)
        self.assertEqual(self.ctx(self.hook("PostToolUse", self.payload(tool_name="Read"))), "")
        # 새 프로세스(resume)의 SessionStart 도 전하지 않은 완료 알림을 낸다
        self.write(human("또 지시 6666", ts="2026-11-10T05:00:00Z"), mode="a")
        worker.flush(st, self.sid, str(self.tp), "SessionEnd", force=True)
        self.assertIn("Session log: saved 1 new section", self.ctx(self.hook("SessionStart", self.payload(source="resume"))))

    def test_nested_and_subagent_noop(self):
        self.seed()
        self.assertEqual(self.hook("SessionStart", self.payload(source="resume"), {"SESSION_LOG_NESTED": "1"}), "")
        self.assertEqual(self.hook("SessionStart", self.payload(source="resume", agent_id="a1")), "")

    def test_stale_handover_skipped(self):
        self.seed()
        out = self.ctx(self.hook("SessionStart", self.payload(source="resume"), {"SESSION_LOG_HANDOVER_MAX_DAYS": "-1"}))
        self.assertNotIn("Handover from", out)
        self.assertIn("pending import", out)

    def test_strong_wording(self):
        self.seed()
        out = self.ctx(self.hook("SessionStart", self.payload(source="startup"), {"SESSION_LOG_PENDING_STRONG_COUNT": "1"}))
        self.assertIn('level="action"', out)
        self.assertIn("Import or dismiss them soon", out)

    def test_hook_speed(self):
        import time
        self.seed()
        t0 = time.time()
        for _ in range(5):
            self.hook("PostToolUse", self.payload(tool_name="Read"))
        self.assertLess((time.time() - t0) / 5, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=1)
