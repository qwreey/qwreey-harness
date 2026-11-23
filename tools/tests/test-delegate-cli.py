"""qwreey-delegate 드라이버(delegate.py)의 명령 시험. 실행: python3 -I tools/tests/test-delegate-cli.py

가짜 agy·codex·setpriv 로 run -> collect -> remove -> gc, list, 동시 실행 거절(에이전트 슬롯, uid 하나에 작업 하나), 인자 오류,
uid 대역(HARNESS_DELEGATE_UIDS)에서 빈 uid 고르기와 기기 전체 uid 잠금, 저장소 층의 setup, doctor 의 비밀 경로와 대역 점검, 작업 uid 가 심은 링크,
시간 초과와 신호, HARNESS_HEAVY_WRAP 를 본다. 모델 호출 없음.
RealUid 는 root 일 때만 진짜 setpriv 로 계정이 없는 시험 대역의 uid 아래 가짜 에이전트를 돌려 권한 문제를 드러낸다.
root 가 아니면 나머지는 uid 백엔드의 chown 단계만 빼고 돈다(delegate_fixture.launcher).
"""
import json
import os
import signal
import stat
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delegate_fixture import IS_ROOT, SCRIPTS, Fixture, git, is_account, key_of  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import delegate_isolation as iso  # noqa: E402
import delegate_workspace as ws  # noqa: E402


class Base(unittest.TestCase):
    real = False

    def setUp(self):
        self.f = Fixture(real_setpriv=self.real)

    def tearDown(self):
        self.f.cleanup()

    def ok(self, *args, **kw):
        p = self.f.drive(*args, **kw)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p

    def fails(self, code, *args, **kw):
        p = self.f.drive(*args, **kw)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p


class Arguments(Base):
    def test_usage(self):
        p = self.fails(2)
        self.assertIn("delegate.py run <agy|codex>", p.stdout)
        self.fails(2, "frob")

    def test_run_argument_errors(self):
        f = self.f
        cases = [
            (("run", "agy", "x"), "usage: run"),
            (("run", "gpt", "x", f.prompt), "backend must be agy|codex"),
            (("run", "agy", "Bad_Name", f.prompt), "name must match"),
            (("run", "agy", "x", f.tmp / "missing.md"), "prompt file not found"),
            (("run", "agy", "x", f.prompt, "--frob"), "unknown option --frob"),
            (("run", "agy", "x", f.prompt, "--repo"), "--repo needs a value"),
            (("run", "agy", "x", f.prompt, "--mode", "both"), "--mode must be worktree|empty"),
            (("run", "agy", "x", f.prompt, "--timeout", "0"), "--timeout must be a positive integer"),
            (("run", "agy", "x", f.prompt, "--repo", "nokey"), "unknown repository nokey"),
            (("run", "agy", "x", f.prompt, "--ref", "no-such-ref"), "commit not found"),
            (("collect", "agy", "nope"), "not found:"),
            (("remove", "codex", "nope", "--frob"), "unknown option"),
            (("gc", "--days", "x"), "--days must be a number"),
        ]
        for args, msg in cases:
            with self.subTest(args=args):
                p = self.fails(2, *args)
                self.assertIn(msg, p.stderr)
        self.assertFalse(f.base("agy").joinpath("x").exists(), "실패한 run 은 작업 사본을 남기지 않는다")
        self.assertFalse(f.rec("agy", "x").exists())

    def test_any_git_repository_without_registration(self):
        other = self.f.tmp / "other"
        other.mkdir()
        git("init", "-q", cwd=other)
        self.ok("list", cwd=other)
        plain = self.f.tmp / "plain"
        plain.mkdir()
        self.assertIn("is not a git repository", self.fails(2, "list", cwd=plain).stderr)

    def test_missing_agent_or_credentials_is_3(self):
        f = self.f
        p = self.fails(3, "run", "agy", "x", f.prompt, env=f.env(HARNESS_DELEGATE_AGY_BIN=str(f.tmp / "no-agy")))
        self.assertIn("agy not found", p.stderr)
        p = self.fails(3, "run", "codex", "x", f.prompt, env=f.env(HARNESS_DELEGATE_CODEX_HOME=str(f.tmp / "nowhere")))
        self.assertIn("codex credentials not found", p.stderr)

    def test_codex_worktree_refused_is_4(self):
        f = self.f
        p = self.fails(4, "run", "codex", "x", f.prompt, "--mode", "worktree")
        self.assertIn("HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access", p.stderr)
        p = self.fails(2, "run", "codex", "x", f.prompt, env=f.env(HARNESS_DELEGATE_CODEX_SANDBOX="off"))
        self.assertIn("HARNESS_DELEGATE_CODEX_SANDBOX must be one of", p.stderr)
        self.assertFalse(f.base("codex").joinpath("x").exists())

    def test_base_owned_by_someone_else_is_refused(self):
        if not IS_ROOT:
            self.skipTest("chown 이 필요하다")
        f = self.f
        base = f.base("agy")
        base.mkdir(parents=True)
        os.chown(base, f.uid, f.uid)
        p = self.fails(4, "run", "agy", "x", f.prompt)
        self.assertIn("must be a folder owned by uid 0", p.stderr)

    def test_register_is_a_no_op(self):
        # 세션이 읽은 SKILL 본문이 register 를 시킬 수 있다: 알리고 성공으로 끝낸다.
        p = self.ok("register", self.f.repo)
        self.assertIn("register is no longer needed", p.stdout)
        self.assertIn("HARNESS_DELEGATE_SETUP", p.stdout)


class LifecycleChecks:
    """Base 를 물려받는 클래스에 섞는다: 가짜 setpriv 와 진짜 setpriv 에서 같은 흐름을 본다."""

    def check_agy_worktree(self):
        f = self.f
        p = self.ok("run", "agy", "t1", f.prompt, "--keep", env=f.env(SOME_TOKEN="secret"))
        base = f.base("agy")
        wt, home, rec = base / "t1", base / ".homes" / "t1", f.rec("agy", "t1")
        self.assertIn("main repo: unchanged", p.stdout)
        self.assertIn(" M tracked.txt", p.stdout)
        self.assertIn("?? new-file.txt", p.stdout)
        self.assertNotIn("REPORT.md", p.stdout.split("worktree changes:")[1].split("report:")[0])
        self.assertIn(f"report: {rec / 'report.md'}", p.stdout, "읽을 보고서는 root 소유 기록 안의 사본")
        self.assertEqual((rec / "report.md").read_text(), "agy worktree report\n")
        self.assertIn(f"next: main reads and verifies -> delegate.py collect agy t1 --repo {f.key}", p.stdout)

        (call,) = f.calls("agy")
        argv = call["argv"]
        self.assertEqual(argv[1:3], ["--model", "gemini-4-hydrogen-high"])
        self.assertNotIn("--dangerously-skip-permissions", argv, "기본 프리셋의 headless 거절을 끄지 않는다")
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertIn("command(*)", settings["permissions"]["allow"], "uid 격리 아래 worktree 는 셸을 연다")
        self.assertTrue(any(r.startswith("write_file(") and r.rstrip(")").endswith("/t1") for r in settings["permissions"]["allow"]),
                        "permissions 를 넘기면 프리셋의 작업 폴더 쓰기 허용이 빠지므로 작업 폴더를 명시로 연다")
        self.assertNotIn("command(*)", settings["permissions"]["deny"])
        self.assertEqual(call["env"]["TMPDIR"], str(home / ".tmp"))
        self.assertEqual(argv[argv.index("--print-timeout") + 1], "3600s")
        prompt = argv[argv.index("-p") + 1]
        self.assertIn(f"git worktree `{wt}`", prompt, "머리말의 {{WT}} 를 채운다")
        self.assertIn(f"`{wt / 'REPORT.md'}`", prompt)
        self.assertTrue(prompt.endswith("TASK BODY: say hello\n"))
        self.assertEqual(call["cwd"], str(wt))
        env = call["env"]
        self.assertEqual(env["HOME"], str(home))
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], str(base / ".hooks"))
        self.assertNotIn("SOME_TOKEN", env, "빈 환경에서 시작한다")
        self.assertNotIn("LEAK_CANARY", env)
        self.assertTrue(env["PATH"].endswith("/usr/bin:/bin"))
        if IS_ROOT:
            self.assertEqual(call["cwd_uid"], f.uid, "worktree 는 작업 uid 소유")
        if self.real:
            self.assertEqual(call["uid"], f.uid, "진짜 setpriv 아래에서 작업 uid 로 돈다")

        gem = home / ".gemini" / "antigravity-cli"
        self.assertTrue((gem / "antigravity-oauth-token").is_file())
        self.assertTrue((gem / "settings.json").is_file())
        self.assertFalse((gem / "brain" / "users-other-conv").exists(), "사용자의 다른 대화는 복사하지 않는다")
        self.assertFalse((gem / "conversations").exists())
        self.assertFalse((gem / "conversation_summaries.db-wal").exists())

        state = json.loads((rec / "state.json").read_text())
        self.assertEqual((state["agent"], state["mode"], state["isolation"], state["rc"], state["collected"]),
                         ("agy", "worktree", "uid", 0, None))
        self.assertEqual(state["commit"], git("rev-parse", "HEAD", cwd=f.repo).strip())
        self.assertEqual((rec / "exit").read_text(), "0\n")
        self.assertIn("mode: worktree", (rec / "meta.txt").read_text())
        self.assertEqual(sorted(os.listdir(wt / ".delegate")), [], "작업 쪽 폴더에 root 가 기록을 쓰지 않는다")
        if IS_ROOT:
            for p in [rec] + list(rec.iterdir()):
                st = p.lstat()
                self.assertEqual(st.st_uid, 0, p)
                self.assertEqual(stat.S_IMODE(st.st_mode), 0o700 if p.is_dir() else 0o600, p)
        self.assertTrue((base / ".hooks" / "pre-push").stat().st_mode & 0o111)

        self.assertRegex(self.ok("list").stdout, r"\n  t1 +finished ")
        self.assertIn("not collected yet", self.fails(2, "remove", "agy", "t1").stderr)

        p = self.ok("collect", "agy", "t1")
        out = f.out("t1")
        self.assertEqual((out / "report.md").read_text(), "agy worktree report\n")
        for name in ("prompt.md", "meta.txt", "guard.txt", "stdout.txt", "exit", "state.json"):
            self.assertTrue((out / name).is_file(), name)
        patch = (out / "diff.patch").read_text()
        self.assertIn("+changed by agy", patch)
        self.assertIn("new-file.txt", patch)
        self.assertNotIn("REPORT.md", patch)
        self.assertNotIn(".delegate", patch)
        self.assertEqual((out / "agy" / "conv-task" / "scratch" / "probe.txt").read_text(), "probe output\n")
        self.assertTrue((out / "agy" / "conv-task" / "transcript.jsonl").is_file())
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        for p in out.rglob("*"):
            self.assertEqual(stat.S_IMODE(p.lstat().st_mode), 0o700 if p.is_dir() else 0o600, p)
        self.assertEqual(json.loads((rec / "state.json").read_text())["collected"], str(out))

        listing = self.ok("list").stdout
        self.assertRegex(listing, r"\n  t1 +collected ")
        self.assertIn(f"== {f.runs} (", listing)
        self.assertIn(f"  {out.name}", listing)

        self.ok("remove", "agy", "t1")
        self.assertFalse(wt.exists())
        self.assertFalse(home.exists())
        self.assertFalse(rec.exists())
        self.assertNotIn(str(wt), git("worktree", "list", cwd=f.repo))
        self.assertFalse((f.repo / ".git" / "worktrees" / "t1").exists())
        self.assertTrue(out.is_dir(), "remove 는 runs/ 기록을 남긴다")

    def check_planted_links_worktree(self):
        f = self.f
        (f.ctl / "plant").write_text("1")
        self.ok("run", "agy", "t1", f.prompt)  # 자동 수집과 정리까지
        out = f.out("t1")
        self.assertEqual((out / "report.md").read_text(), "agy stdout answer",
                         "링크인 REPORT.md 는 읽지 않고 JSON 의 response 를 쓴다")
        self.assertFalse((out / "agy").exists(), "링크인 brain 을 따라가지 않는다")
        self.assertFalse((f.base("agy") / "t1").exists())
        self.assert_untouched()

    def check_planted_links_home(self):
        f = self.f
        (f.ctl / "plant-home").write_text("1")
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty")
        out = f.out("e1")
        self.assertIn(f"report: {out / 'report.md'}", p.stdout)
        self.assertEqual((out / "report.md").read_text(), "agy stdout answer", "링크인 report.md 대신 JSON 의 response")
        self.assertFalse((out / "agy").exists(), "링크인 .gemini 를 따라가지 않는다")
        self.assert_untouched()

    def assert_untouched(self):
        f = self.f
        self.assertEqual(os.listdir(f.victim), [], "root 가 심긴 링크 너머에 쓰지 않았다")
        self.assertEqual(f.secret.read_text(), "ROOTSECRET\n")
        self.assertTrue((f.victim_brain / "conv-x" / "scratch" / "stolen.txt").is_file(), "링크 너머를 지우지 않았다")
        if IS_ROOT:
            for p in (f.secret, f.victim, f.victim_brain, f.victim_gemini):
                self.assertEqual(p.lstat().st_uid, 0, f"{p} 의 소유자가 바뀌었다")
        if f.runs.is_dir():
            self.assertEqual(f.leaked(f.runs), [], "비밀 내용이 runs/ 에 복사됐다")
        for agent in ("agy", "codex"):
            if f.base(agent).joinpath(".runs").is_dir():
                self.assertEqual(f.leaked(f.base(agent) / ".runs"), [])

    def check_committed_link_is_not_chowned(self):
        f = self.f
        os.symlink(f.secret, f.repo / "link-to-secret")
        git("add", "link-to-secret", cwd=f.repo)
        git("commit", "-q", "-m", "link", cwd=f.repo)
        self.ok("run", "agy", "t1", f.prompt, "--keep")
        self.assertEqual(f.secret.lstat().st_uid, 0, "저장소가 커밋한 링크의 대상을 작업 uid 에 넘기지 않는다")
        if IS_ROOT:
            self.assertEqual((f.base("agy") / "t1" / "link-to-secret").lstat().st_uid, f.uid)


    def check_leftover_home_is_replaced(self):
        # uid 는 실행마다 다르다. 같은 이름의 HOME 이 다른 uid 소유로 남아 있어도 새 작업은 새로 만든 HOME 만 받는다.
        f = self.f
        old = f.base("agy") / ".homes" / "t1"
        old.mkdir(parents=True)
        (old / "stale").write_text("left by another uid\n")
        os.symlink(f.secret, old / "link-to-secret")
        if IS_ROOT:
            for p in (old, old / "stale"):
                os.chown(p, f.uid2, f.uid2)

        self.ok("run", "agy", "t1", f.prompt, "--keep")
        self.assertFalse((old / "stale").exists(), "남은 HOME 은 지우고 새로 만든다")
        self.assertFalse(os.path.lexists(old / "link-to-secret"))
        self.assertEqual(f.secret.read_text(), "ROOTSECRET\n")
        if IS_ROOT:
            self.assertEqual(old.lstat().st_uid, f.uid, "새 HOME 은 이번 작업 uid 소유")
            self.assertEqual(f.secret.lstat().st_uid, 0)

    def check_setup_runs_as_the_task(self):
        f = self.f
        # 저장소 층(커밋되는 .claude/harness.env)의 줄. $SECRET_SETUP 은 드라이버 환경에서 풀리지 않고 작업의 빈 환경에서 풀린다.
        f.repo_env('HARNESS_DELEGATE_SETUP=id -u > setup-uid; env > setup-env; echo "$SECRET_SETUP" > setup-secret\n')
        p = self.ok("run", "agy", "t1", f.prompt, "--keep", env=f.env(SECRET_SETUP="leak"))
        self.assertNotIn("setup failed", p.stderr)
        wt = f.base("agy") / "t1"
        if self.real:
            self.assertEqual((wt / "setup-uid").read_text().strip(), str(f.uid), "setup 은 작업 uid 로 돈다")
        self.assertEqual((wt / "setup-secret").read_text(), "\n", "setup 은 빈 환경에서 돌고 드라이버 환경으로 풀지 않는다")
        self.assertIn("main repo: unchanged", p.stdout)
        # empty 모드에는 setup 이 없다
        self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", "--keep")
        self.assertFalse((f.base("agy") / "e1" / "setup-uid").exists())
        self.assertIn(f"HOME={f.base('agy') / '.homes' / 't1'}", (wt / "setup-env").read_text())


    def check_setup_with_mise(self):
        f = self.f
        misebin, tools, data = f.fake_mise()
        f.user_env((f.cfg / "harness.env").read_text() + f"HARNESS_TOOL_INSTALLS={data / 'installs'}\n")
        f.repo_env("HARNESS_DELEGATE_SETUP=timeout 300 mise exec -- pesde install\n", local=True)
        env = f.env(PATH=f"{f.bin}:{misebin}:/usr/bin:/bin" + (":/usr/sbin:/sbin" if self.real else ""))
        p = self.ok("run", "agy", "t1", f.prompt, "--keep", env=env)
        self.assertNotIn("setup failed", p.stderr)
        wt = f.base("agy") / "t1"
        self.assertTrue((wt / "pesde-installed").exists())
        self.assertEqual((wt / "setup-path").read_text().strip(), f"{tools}:{misebin}:/usr/bin:/bin")
        self.assertEqual((wt / "setup-mise-data").read_text().strip(), str(data))
        if self.real:
            self.assertEqual((wt / "setup-uid").read_text().strip(), str(f.uid))
        agent_env = f.calls("agy")[0]["env"]
        self.assertEqual(agent_env["PATH"], f"{tools}:/usr/bin:/bin", "에이전트 PATH 에는 mise 가 없다")
        self.assertNotIn("MISE_DATA_DIR", agent_env)


class Lifecycle(Base, LifecycleChecks):
    def test_leftover_home_is_replaced(self):
        self.check_leftover_home_is_replaced()

    def test_setup_runs_as_the_task(self):
        self.check_setup_runs_as_the_task()

    def test_setup_gets_mise(self):
        self.check_setup_with_mise()

    def test_agy_worktree_run_collect_remove(self):
        self.check_agy_worktree()
        log = (self.f.ctl / "setpriv.log").read_text()
        self.assertIn(f"--no-new-privs --inh-caps=-all --bounding-set=-all --reuid={self.f.uid} --regid={self.f.uid} "
                      f"--clear-groups", log)

    def test_planted_links_in_worktree(self):
        self.check_planted_links_worktree()

    def test_planted_links_in_home(self):
        self.check_planted_links_home()

    def test_committed_link_is_not_chowned(self):
        if not IS_ROOT:
            self.skipTest("chown 이 필요하다")
        self.check_committed_link_is_not_chowned()

    def test_codex_empty_run_and_gc(self):
        f = self.f
        p = self.ok("run", "codex", "c1", f.prompt, "--keep")
        base = f.base("codex")
        wt, home, rec = base / "c1", base / ".homes" / "c1", f.rec("codex", "c1")
        self.assertIn(f"report: {rec / 'report.md'}", p.stdout, "--keep 이면 기록 안의 사본을 알린다")
        self.assertNotIn("worktree changes", p.stdout)
        self.assertEqual((rec / "report.md").read_text(), "codex answer\n")
        (call,) = f.calls("codex")
        argv = call["argv"]
        self.assertEqual(argv[1:3], ["exec", "-m"])
        self.assertEqual(argv[3], "gpt-6-luna")
        self.assertIn("model_reasoning_effort=medium", argv)
        self.assertEqual(argv[argv.index("-s") + 1], "read-only")
        self.assertIn("--ignore-user-config", argv)
        self.assertEqual(argv[argv.index("-C") + 1], str(wt))
        self.assertEqual(argv[argv.index("-o") + 1], str(wt / ".delegate" / "report.md"))
        self.assertEqual(argv[-1], "-")
        self.assertTrue(call["stdin"].endswith("TASK BODY: say hello\n"))
        self.assertIn("The working directory is empty", call["stdin"])
        self.assertEqual(call["env"]["CODEX_HOME"], str(home / ".codex"))
        self.assertEqual((home / ".codex" / "auth.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(wt.iterdir()), [wt / ".delegate"], "empty 모드는 빈 폴더")

        (base / ".homes" / "orphan").mkdir()
        f.runs.mkdir(parents=True, exist_ok=True)
        old = f.runs / "20200101-0000-old"
        old.mkdir()
        month_ago = time.time() - 30 * 86400
        os.utime(old, (month_ago, month_ago))
        p = self.ok("gc")
        self.assertIn("(preview", p.stdout)
        self.assertIn(f"delete     work/{f.key}-codex/c1 (finished, collected first)", p.stdout)
        self.assertIn(f"delete     work/{f.key}-codex/.homes/orphan", p.stdout)
        self.assertIn(f"delete     runs/{f.key}/20200101-0000-old (results, 30d old; older than 14d)", p.stdout)
        self.assertTrue(wt.exists() and old.exists(), "미리보기는 지우지 않는다")
        self.assertNotIn("20200101-0000-old", self.ok("gc", "--days", "60").stdout)
        f.user_env((f.cfg / "harness.env").read_text() + "HARNESS_DELEGATE_RUNS_DAYS=60\n")
        self.assertNotIn("20200101-0000-old", self.ok("gc").stdout, "HARNESS_DELEGATE_RUNS_DAYS 가 기본 14일을 바꾼다")
        p = self.ok("gc", "--apply", "--days", "14")
        self.assertIn(f"collected  work/{f.key}-codex/c1 -> ", p.stdout)
        self.assertFalse(wt.exists())
        self.assertFalse(rec.exists())
        self.assertFalse((base / ".homes" / "orphan").exists())
        self.assertFalse(old.exists())
        self.assertEqual((f.out("c1") / "report.md").read_text(), "codex answer\n", "지우기 전에 결과를 모았다")

    def test_run_collects_and_cleans_up(self):
        f = self.f
        p = self.ok("run", "agy", "t1", f.prompt)
        out = f.out("t1")
        self.assertIn(f"collected: {out} (workspace removed)", p.stdout)
        self.assertIn(f"report: {out / 'report.md'}", p.stdout)
        self.assertNotIn("next: main reads and verifies ->", p.stdout)
        self.assertEqual((out / "report.md").read_text(), "agy worktree report\n")
        self.assertIn("+changed by agy", (out / "diff.patch").read_text())
        self.assertTrue((out / "agy" / "conv-task" / "scratch" / "probe.txt").is_file())
        for name in ("prompt.md", "meta.txt", "guard.txt", "stdout.txt", "stderr.txt", "exit", "state.json"):
            self.assertTrue((out / name).is_file(), name)
        base = f.base("agy")
        for gone in (base / "t1", base / ".homes" / "t1", f.rec("agy", "t1"), f.repo / ".git" / "worktrees" / "t1"):
            self.assertFalse(gone.exists(), gone)
        self.assertEqual(git("worktree", "list", "--porcelain", cwd=f.repo).count("worktree "), 1)
        self.assertEqual(sorted(p.name for p in f.ws.iterdir()), ["proj"], "저장소 옆에 아무것도 만들지 않는다")
        if IS_ROOT:
            for d, mode in ((f.state, 0o711), (f.state / "work", 0o711), (base, 0o711), (f.state / "runs", 0o700),
                            (f.runs, 0o700), (out, 0o700)):
                self.assertEqual(stat.S_IMODE(d.stat().st_mode), mode, d)

    def test_failed_collect_keeps_the_workspace(self):
        f = self.f
        (f.ctl / "fail-git").write_text("1")
        p = self.ok("run", "agy", "t1", f.prompt)
        wt = f.base("agy") / "t1"
        self.assertIn(f"kept: {wt} - automatic collect failed, so nothing was deleted: diff.patch not made", p.stdout)
        self.assertIn(f"report: {f.rec('agy', 't1') / 'report.md'}", p.stdout)
        self.assertIn("next: main reads and verifies -> delegate.py collect agy t1", p.stdout)
        self.assertTrue(wt.is_dir() and (f.base("agy") / ".homes" / "t1").is_dir())
        self.assertIsNone(json.loads((f.rec("agy", "t1") / "state.json").read_text())["collected"])
        (f.ctl / "fail-git").unlink()
        self.ok("collect", "agy", "t1")
        self.ok("remove", "agy", "t1")
        self.assertFalse(wt.exists())

    def test_agy_empty_falls_back_to_stdout(self):
        f = self.f
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", "--model", "m-x", "--timeout", "30")
        self.assertNotIn("warning", p.stderr)
        out = f.out("e1")
        self.assertEqual((out / "report.md").read_text(), "agy stdout answer")
        self.assertIn("some log line", (out / "stderr.txt").read_text(), "stderr 는 따로")
        argv = f.calls("agy")[0]["argv"]
        self.assertEqual((argv[2], argv[argv.index("--print-timeout") + 1]), ("m-x", "30s"))

    def test_agy_settings_per_mode_and_temp_folders(self):
        f = self.f
        systmp = f.tmp / "systmp"
        systmp.mkdir()
        env = f.env(TMPDIR=str(systmp))
        self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", env=env)
        self.ok("run", "agy", "w1", f.prompt, env=env)
        empty, wt = (json.loads(c["argv"][c["argv"].index("--settings") + 1])["permissions"] for c in f.calls("agy"))
        tmp_rules = ["read_file(/tmp)", "write_file(/tmp)", f"read_file({systmp})", f"write_file({systmp})"]
        self.assertEqual(empty["deny"], tmp_rules + ["command(*)"], "empty 는 셸도 거절")
        self.assertEqual(wt["deny"], tmp_rules)

        def ws_rules(allow, name):
            return {r.split("(")[0] for r in allow if r.rstrip(")").endswith("/" + name)}
        self.assertEqual(ws_rules(empty["allow"], "e1"), {"read_file", "write_file"}, "empty 도 작업 폴더에 보고서를 쓴다")
        self.assertNotIn("command(*)", empty["allow"])
        self.assertEqual(ws_rules(wt["allow"], "w1"), {"read_file", "write_file"})
        self.assertIn("command(*)", wt["allow"])
        for c in f.calls("agy"):
            self.assertNotIn("--dangerously-skip-permissions", c["argv"])
        self.assertIn('agy-settings: {"permissions":{"deny":["read_file(/tmp)"', (f.out("e1") / "meta.txt").read_text())
        p = self.ok("doctor", env=env)
        self.assertIn(f"  INFO agy file tools denied in temp folders: /tmp {systmp}", p.stdout)
        self.assertIn(f"  INFO work folders {f.state / 'work' / (f.key + '-<agent>')}, results {f.runs}", p.stdout)

    def test_work_folder_under_a_denied_temp_folder_is_refused(self):
        f = self.f
        under_tmp = Path(tempfile.mkdtemp(prefix="delegate-state-", dir="/tmp"))
        try:
            env = f.env(HARNESS_DELEGATE_STATE=str(under_tmp / "state"))
            p = self.fails(4, "run", "agy", "x", f.prompt, env=env)
            self.assertIn("temp folder /tmp holds the workspace", p.stderr)
            self.assertIn("HARNESS_DELEGATE_STATE", p.stderr)
            self.assertFalse((under_tmp / "state").exists(), "거절 전에는 아무것도 만들지 않는다")
            self.ok("run", "codex", "c1", f.prompt, env=env)  # codex 에는 임시 폴더 거절 정책이 없다
            p = self.ok("doctor", env=env)
            self.assertIn("  FAIL agy temp folder /tmp holds the workspace", p.stdout)
        finally:
            shutil.rmtree(under_tmp, ignore_errors=True)

    def test_agy_denial_is_reported(self):
        f = self.f
        (f.ctl / "agy-denied").write_text("1")
        p = self.ok("run", "agy", "d1", f.prompt, "--mode", "empty")
        out = f.out("d1")
        self.assertIn("report: MISSING - agy ended the turn with an empty answer after it was denied read_file, command",
                      p.stdout)
        self.assertIn("agy denied: read_file, command", (out / "guard.txt").read_text())
        self.assertIn("agy-denied: read_file, command", (out / "meta.txt").read_text())
        self.assertEqual(json.loads((out / "state.json").read_text())["denied"], ["read_file", "command"])
        self.assertIn("auto-denied", (out / "stderr.txt").read_text())

    def test_codex_gets_task_tmpdir(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt, "--keep")
        home = f.base("codex") / ".homes" / "c1"
        self.assertEqual(f.calls("codex")[0]["env"]["TMPDIR"], str(home / ".tmp"))
        self.assertTrue((home / ".tmp").is_dir())
        if IS_ROOT:
            self.assertEqual((home / ".tmp").lstat().st_uid, f.uid)
        self.assertNotIn("--settings", f.calls("codex")[0]["argv"])

    def test_existing_name_refused(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt, "--keep")
        self.assertIn("already exists", self.fails(2, "run", "codex", "c1", f.prompt).stderr)

    def test_heavy_wrap_goes_in_front_of_setpriv(self):
        f = self.f
        wrap = f.bin / "wrap"
        wrap.write_text(f'#!/bin/sh\nprintf "%s " "$@" > "{f.ctl}/wrap.log"\nwhile [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n')
        wrap.chmod(0o755)
        f.user_env((f.cfg / "harness.env").read_text() + "HARNESS_HEAVY_WRAP=wrap -n 7 --\n")
        self.ok("run", "agy", "w1", f.prompt, "--mode", "empty")
        want = (f"-n 7 -- {f.bin / 'setpriv'} --no-new-privs --inh-caps=-all --bounding-set=-all --reuid={f.uid} "
                f"--regid={f.uid} --clear-groups {f.bin / 'agy'} --model gemini-4-hydrogen-high")
        self.assertTrue((f.ctl / "wrap.log").read_text().startswith(want), (f.ctl / "wrap.log").read_text())

    def make_legacy(self):
        """저장소 옆 옛 자리의 작업들: delegate.sh 꼴(기록이 .delegate/ 안)과 링크로 된 .delegate."""
        f = self.f
        old = f.legacy_base("agy") / "old-done" / ".delegate"
        old.mkdir(parents=True)
        (old / "exit").write_text("0\n")
        (old / "collected").write_text("/somewhere\n")
        fin = f.legacy_base("agy") / "old-fin" / ".delegate"
        fin.mkdir(parents=True)
        (fin / "exit").write_text("1\n")
        (fin / "report.md").write_text("old report\n")
        (f.legacy_base("agy") / "old-link").mkdir()
        os.symlink(old, f.legacy_base("agy") / "old-link" / ".delegate")
        rec = f.legacy_base("codex") / "old-record"
        rec.mkdir(parents=True)
        (rec / "answer.md").write_text("x")
        return old, fin

    def test_list_across_runs_and_shell_shaped_workspaces(self):
        f = self.f
        self.ok("run", "agy", "a1", f.prompt, "--keep")
        self.ok("run", "codex", "c1", f.prompt, "--keep")
        self.ok("collect", "codex", "c1")
        old, fin = self.make_legacy()
        p = self.ok("list", "--all")
        for name, state in (("a1", "finished"), ("old-done", "collected"), ("old-fin", "finished"), ("c1", "collected"),
                            ("old-record", "legacy-record"), ("old-link", "unknown")):
            self.assertRegex(p.stdout, rf"\n  {name} +{state} ")
        for base in (f.legacy_base("agy"), f.legacy_base("codex"), f.base("agy"), f.base("codex"), f.runs):
            self.assertIn(f"== {base} (", p.stdout)
        self.assertLess(p.stdout.index(f"== {f.legacy_base('agy')}"), p.stdout.index(f"== {f.base('agy')}"),
                        "옛 자리 부분은 delegate.sh 의 list 와 같은 꼴로 먼저")
        self.assertIn("not collected yet", self.fails(2, "remove", "agy", "old-fin").stderr)
        self.ok("collect", "agy", "old-fin")
        self.assertEqual((f.out("old-fin") / "report.md").read_text(), "old report\n")
        self.assertEqual(sorted(os.listdir(fin)), ["exit", "report.md"], "옛 작업 사본에 쓰지 않는다")
        self.ok("remove", "agy", "old-fin")
        self.ok("remove", "agy", "old-done")
        self.assertTrue(f.legacy_base("agy").joinpath("old-link").exists())

    def test_gc_never_deletes_the_legacy_location(self):
        f = self.f
        old, fin = self.make_legacy()
        (f.legacy_base("agy") / ".homes" / "gone").mkdir(parents=True)
        p = self.ok("gc", "--apply", "--days", "0")
        self.assertIn(f"legacy     {f.legacy_base('agy')} (older location; gc lists it but never deletes there", p.stdout)
        self.assertIn("  stale    proj-agy/old-done (0d, ", p.stdout)
        self.assertIn("collected - remove it", p.stdout)
        self.assertIn("  stale    proj-agy/.homes/gone (HOME without an owner", p.stdout)
        for kept in (old, fin, f.legacy_base("agy") / ".homes" / "gone", f.legacy_base("codex") / "old-record"):
            self.assertTrue(kept.exists(), kept)


class Concurrency(Base):
    def test_live_shell_run_counts(self):
        f = self.f
        other = f.add_repo("proj2")
        self.ok("run", "codex", "z", f.prompt, cwd=other)  # 한 번 돈 저장소만 셈에 든다(<상태>/repos/)
        # delegate.sh 의 살아 있는 작업: pid 파일만 있고 기록 폴더가 없음. 이 시험 프로세스의 pid 로 흉내.
        live = f.ws / "proj2-agy" / "sh-run" / ".delegate"
        live.mkdir(parents=True)
        (live / "pid").write_text(f"{os.getpid()}\n")
        p = self.fails(5, "run", "agy", "x", f.prompt)
        self.assertIn("1 agy task(s) already running (limit 1, HARNESS_DELEGATE_MAX_CONCURRENT", p.stderr)
        self.assertFalse((f.base("agy") / "x").exists())
        self.assertRegex(self.ok("list", "--repo", "proj2").stdout, r"\n  sh-run +running ")
        self.ok("run", "codex", "x", f.prompt)  # 한도는 에이전트마다

    def test_running_driver_holds_a_slot_and_its_uid(self):
        f = self.f
        other = f.add_repo("proj2")
        (f.ctl / "block").write_text("1")
        a = f.start("run", "agy", "a1", f.prompt)
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"), "가짜 agy 가 시작하지 않았다")
            p = self.fails(5, "run", "agy", "a2", f.prompt, "--repo", other)
            self.assertIn("1 agy task(s) already running", p.stderr)
            self.ok("run", "codex", "c1", f.prompt)  # 다른 에이전트는 대역의 다음 uid 로 나란히 돈다
            self.assertEqual(f.setpriv_uids()[-1], f.uid2)
            self.assertRegex(self.ok("list").stdout, r"\n  a1 +running ")
            self.assertIn("still running: agy/a1", self.fails(2, "collect", "agy", "a1").stderr)
            self.assertIn("still running", self.fails(2, "remove", "agy", "a1", "--discard").stderr)
            (f.ctl / "started").unlink()
            # 한도 2 면 다른 저장소의 둘째가 첫째와 다른 uid 로 돈다(첫째는 아직 막혀 있을 수 있다).
            (f.ctl / "release").write_text("1")
            b = f.drive("run", "agy", "a2", f.prompt, "--repo", other, env=f.env(HARNESS_DELEGATE_MAX_CONCURRENT="2"))
            self.assertEqual(b.returncode, 0, b.stderr)
        finally:
            (f.ctl / "release").write_text("1")
            out, err = a.communicate(timeout=60)
        self.assertEqual(a.returncode, 0, out + err)
        self.assertEqual(f.setpriv_uids()[0], f.uid, "첫 작업은 대역의 첫 uid")
        self.assertTrue((f.out("a1") / "report.md").is_file(), "끝난 뒤 스스로 모으고 정리했다")
        self.assertNotRegex(self.ok("list").stdout, r"\n  a1 +")

    def test_task_written_pid_does_not_fake_running(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt, "--keep")
        # 작업 uid 는 자기 .delegate/ 에 무엇이든 쓴다. 기록 폴더가 있으면 그것만 본다.
        (f.base("codex") / "c1" / ".delegate" / "pid").write_text(f"{os.getpid()}\n")
        (f.base("codex") / "c1" / ".delegate" / "collected").write_text("x\n")
        self.assertRegex(self.ok("list").stdout, r"\n  c1 +finished ")
        self.assertIn("not collected yet", self.fails(2, "remove", "codex", "c1").stderr)
        self.ok("run", "codex", "c2", f.prompt)


def account_then_free(kind):
    """(계정 번호, 그다음 빈 번호): kind 'user' 는 /etc/passwd, 'group' 은 /etc/group 에만 있는 번호. 없으면 None."""
    import grp
    import pwd
    ids = sorted({e.pw_uid for e in pwd.getpwall()} if kind == "user"
                 else {g.gr_gid for g in grp.getgrall()} - {e.pw_uid for e in pwd.getpwall()})
    for u in ids:
        if u > 0 and not is_account(u + 1):
            return u, u + 1
    return None


class UidRange(Base):
    """HARNESS_DELEGATE_UIDS: 실행마다 대역에서 비어 있는 첫 uid 를 쓴다."""

    def hold(self, *uids, state=None):
        """이 시험 프로세스가 uid 잠금을 쥔다(살아 있는 다른 작업 흉내). 잠금 fd 목록."""
        state = state or self.f.state
        state.mkdir(parents=True, exist_ok=True)
        fds = [ws.take_uid_lock(state, u) for u in uids]
        self.assertNotIn(None, fds, "시험 대역의 uid 를 다른 프로세스가 쥐고 있다")
        return fds

    def release(self, fds):
        for fd in fds:
            os.close(fd)

    def test_first_free_uid_and_locked_uid_skipped(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        self.assertEqual(f.setpriv_uids()[-1], f.uid, "대역의 첫 uid")
        fds = self.hold(f.uid)
        try:
            self.ok("run", "codex", "c2", f.prompt)
            self.assertEqual(f.setpriv_uids()[-1], f.uid2, "다른 작업이 잠근 uid 는 건너뛴다")
        finally:
            self.release(fds)
        self.ok("run", "codex", "c3", f.prompt)
        self.assertEqual(f.setpriv_uids()[-1], f.uid, "끝난 작업의 uid 는 다시 쓴다")

    def test_range_exhausted_is_5(self):
        f = self.f
        fds = self.hold(*range(f.first_uid, f.last_uid + 1))
        try:
            p = self.fails(5, "run", "codex", "c1", f.prompt)
            self.assertIn(f"no free uid in HARNESS_DELEGATE_UIDS {f.first_uid}-{f.last_uid}: 4 running", p.stderr)
            self.assertFalse((f.base("codex") / "c1").exists())
            self.assertFalse(f.rec("codex", "c1").exists())
        finally:
            self.release(fds)

    def test_account_ids_skipped(self):
        f = self.f
        for kind in ("user", "group"):
            pair = account_then_free(kind)
            if pair is None:
                continue
            with self.subTest(kind=kind):
                taken, free = pair
                env = f.env()

                # The account id is skipped
                f.user_env((f.cfg / "harness.env").read_text() + f"HARNESS_DELEGATE_UIDS={taken}-{free}\n")
                self.ok("run", "codex", f"c-{kind}", f.prompt, env=env)
                self.assertEqual(f.setpriv_uids()[-1], free, f"실제 {kind} 번호는 건너뛴다")

                # A range of accounts only is refused
                f.user_env((f.cfg / "harness.env").read_text() + f"HARNESS_DELEGATE_UIDS={taken}-{taken}\n")
                p = self.fails(4, "run", "codex", f"d-{kind}", f.prompt, env=env)
                self.assertIn("1 are real users or groups", p.stderr)
                doc = self.ok("doctor", env=env).stdout
                self.assertIn(f"  FAIL real accounts in the range, skipped: {taken} ({kind})", doc)

    def test_invalid_range_is_2(self):
        f = self.f
        for bad in ("abc", "", "5-2", "0-3", "61000-", f"1-{ws.MAX_UID_RANGE + 1}"):
            with self.subTest(bad=bad):
                p = self.fails(2, "run", "codex", "c1", f.prompt, env=f.env(HARNESS_DELEGATE_UIDS=bad))
                self.assertIn("HARNESS_DELEGATE_UIDS must be a range of unused ids like 61100-61115", p.stderr)
                doc = self.ok("doctor", env=f.env(HARNESS_DELEGATE_UIDS=bad)).stdout
                self.assertIn("  FAIL HARNESS_DELEGATE_UIDS must be a range", doc)
        self.assertFalse(f.base("codex").exists(), "거절 전에는 작업 폴더를 만들지 않는다")

    def test_repo_layer_cannot_change_the_range(self):
        f = self.f
        f.repo_env(f"HARNESS_DELEGATE_UIDS={f.last_uid}-{f.last_uid}\n")
        f.repo_env("HARNESS_DELEGATE_UIDS=abc\n", local=True)
        self.ok("run", "codex", "c1", f.prompt)
        self.assertEqual(f.setpriv_uids()[-1], f.uid)

    def test_uncollected_work_folder_holds_its_uid(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt, "--keep")
        self.ok("run", "codex", "c2", f.prompt)
        self.assertEqual(f.setpriv_uids()[-1], f.uid2, "모으지 않은 작업 폴더의 uid 는 새 작업에 주지 않는다")
        self.assertIn(f"  INFO held by uncollected work folders until collect/remove or gc: {f.uid}", self.ok("doctor").stdout)
        self.ok("collect", "codex", "c1")
        self.ok("run", "codex", "c3", f.prompt)
        self.assertEqual(f.setpriv_uids()[-1], f.uid, "모은 뒤에는 다시 쓴다")
        self.ok("remove", "codex", "c1")

    def test_record_kept_between_scan_and_lock(self):
        # 훑은 뒤 잠그기 전에, 그 uid 를 쥐던 실행이 --keep 으로 끝나 모으지 않은 기록을 남기는 순서
        f = self.f
        f.state.mkdir(parents=True, exist_ok=True)
        rec = f.state / "work" / "other-agy" / ws.RECORDS / "kept"
        real_lock = ws.take_uid_lock

        def keep_then_lock(state_dir, uid):
            if not rec.exists():
                rec.mkdir(parents=True)
                (rec / ws.STATE_FILE).write_text(json.dumps({"uid": uid, "finished": "x", "collected": None}))
            return real_lock(state_dir, uid)

        with mock.patch.object(ws, "take_uid_lock", keep_then_lock):
            uid, fd = ws.take_uid(f.state, f.first_uid, f.last_uid)
        os.close(fd)
        self.assertEqual(uid, f.uid2, "잠근 뒤 다시 보아 모으지 않은 작업 폴더의 uid 는 놓는다")

    def test_uid_lock_is_machine_wide(self):
        if not IS_ROOT:
            self.skipTest("/run 아래 잠금은 root 만 만든다")
        f = self.f
        st = os.lstat(ws.UID_LOCK_DIR)
        self.assertEqual((st.st_uid, stat.S_IMODE(st.st_mode)), (0, 0o700))

        # 상태 폴더가 다른 실행이 쥔 uid 도 건너뛴다(시작할 때 그 uid 의 프로세스를 모두 죽이므로)
        fds = self.hold(f.uid, state=f.tmp / "other-state")
        try:
            self.ok("run", "codex", "c1", f.prompt)
            self.assertEqual(f.setpriv_uids()[-1], f.uid2)
        finally:
            self.release(fds)
        self.assertFalse((f.state / "uids" / f"{f.uid}.lock").exists(), "잠금은 상태 폴더가 아닌 /run 에 있다")
        self.assertIn(f"  ok   uid locks in {ws.UID_LOCK_DIR} (machine-wide)", self.ok("doctor").stdout)

    def test_uid_locks_fall_back_to_the_state_folder(self):
        # /run 을 쓸 수 없으면(남도 쓰는 /run 흉내) 상태 폴더의 uids/ 에 잠근다
        f = self.f
        fake_run = f.tmp / "run"
        fake_run.mkdir(mode=0o777)
        fake_run.chmod(0o777)
        f.state.mkdir(parents=True)
        with mock.patch.object(ws, "UID_LOCK_DIR", fake_run / "qwreey-delegate" / "uids"):
            self.assertIsNone(ws.machine_uid_lock_dir())
            fd = ws.take_uid_lock(f.state, f.uid)
        try:
            self.assertTrue((f.state / "uids" / f"{f.uid}.lock").is_file())
            self.assertFalse((fake_run / "qwreey-delegate").exists())
        finally:
            os.close(fd)

    def test_state_folder_lock_of_an_older_driver_counts(self):
        # 잠금이 /run 으로 옮기기 전에 시작한 드라이버는 상태 폴더의 잠금을 쥐고 끝날 때까지 돈다
        f = self.f
        (f.state / "uids").mkdir(parents=True)
        fd = ws.take_lock(f.state / "uids" / f"{f.uid}.lock")
        try:
            self.ok("run", "codex", "c1", f.prompt)
            self.assertEqual(f.setpriv_uids()[-1], f.uid2)
        finally:
            os.close(fd)

    def test_collect_and_remove_hold_the_uid(self):
        # 모으기는 그 uid 로 git 을 돌리고 그 uid 의 프로세스를 끝낸다. 다른 실행이 그 uid 를 쥐는 동안에는 거절한다
        f = self.f
        self.ok("run", "agy", "a1", f.prompt, "--keep")
        calls = len(f.setpriv_uids())

        # Refused while another run holds the uid
        fds = self.hold(f.uid, state=f.tmp / "other-state")
        try:
            for cmd in (("collect", "agy", "a1"), ("remove", "agy", "a1", "--discard")):
                with self.subTest(cmd=cmd[0]):
                    p = self.fails(5, *cmd)
                    self.assertIn(f"uid {f.uid} is in use by a running task", p.stderr)
            p = self.ok("gc", "--apply")
            self.assertIn(f"held       work/{f.key}-agy/a1 (uid {f.uid} is in use by a running task", p.stdout)
            self.assertEqual(len(f.setpriv_uids()), calls, "쥔 uid 로는 아무것도 돌리지 않는다")
            self.assertTrue((f.base("agy") / "a1").is_dir())
        finally:
            self.release(fds)

        # Goes through once the uid is free
        self.ok("collect", "agy", "a1")
        self.assertEqual(f.setpriv_uids()[-1], f.uid, "놓인 뒤에는 그 uid 로 diff 를 만든다")
        self.ok("remove", "agy", "a1")

    def test_repo_by_key_and_name(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        for sel in (f.key, "proj", str(f.repo)):
            with self.subTest(sel=sel):
                self.assertIn(f"== {f.runs} (", self.ok("list", "--repo", sel).stdout)

        # Another repository with the same folder name
        twin = f.tmp / "elsewhere" / "proj"
        twin.mkdir(parents=True)
        git("init", "-q", cwd=twin)
        git("-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "base", cwd=twin)
        self.ok("run", "codex", "c2", f.prompt, cwd=twin)
        self.assertNotEqual(key_of(twin), f.key, "같은 폴더 이름의 두 저장소는 키가 다르다")

        self.assertIn("names several repositories", self.fails(2, "list", "--repo", "proj").stderr)
        self.assertIn(f"== {f.state / 'runs' / key_of(twin)} (", self.ok("list", "--repo", key_of(twin)).stdout)
        listing = self.ok("list", "--all").stdout
        self.assertIn(f"== {f.runs} (", listing)
        self.assertIn(f"== {f.state / 'runs' / key_of(twin)} (", listing)

    def test_folders_of_no_known_repository(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        old_work = f.state / "work" / "proj-agy" / "w1"  # 폴더 이름만인 키: 아는 저장소의 키가 아니다
        old_work.mkdir(parents=True)
        old_runs = f.state / "runs" / "proj" / "20200101-0000-r"
        old_runs.mkdir(parents=True)
        month_ago = time.time() - 30 * 86400
        os.utime(old_runs, (month_ago, month_ago))

        listing = self.ok("list", "--all").stdout
        self.assertIn(f"== {f.state / 'work' / 'proj-agy'} (", listing)
        self.assertIn("no known repository)", listing)

        p = self.ok("gc", "--all", "--apply")
        self.assertIn("unknown    work/proj-agy (no known repository", p.stdout)
        self.assertIn("delete     runs/proj/20200101-0000-r (results, 30d old; older than 14d)", p.stdout)
        self.assertTrue(old_work.is_dir(), "알 수 없는 작업 폴더는 지우지 않는다")
        self.assertFalse(old_runs.exists(), "보존 기간이 지난 결과는 지운다")
        self.assertTrue(f.out("c1").is_dir())


class Signals(Base):
    def test_second_signal_does_not_cut_the_record(self):
        f = self.f
        (f.ctl / "block").write_text("1")
        (f.ctl / "trap").write_text("1")
        a = f.start("run", "agy", "s1", f.prompt, "--mode", "empty")
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"))
            a.send_signal(signal.SIGTERM)
            time.sleep(0.4)  # 가짜 agy 가 SIGTERM 을 받고 1초 동안 끝나는 중
            a.send_signal(signal.SIGTERM)
            out, err = a.communicate(timeout=60)
        finally:
            (f.ctl / "release").write_text("1")
        self.assertEqual(a.returncode, 0, out + err)
        self.assertIn("exit: 143", out)
        self.assertTrue((f.ctl / "trapped").exists(), "작업은 SIGTERM 을 받고 끝났다")
        state = json.loads((f.out("s1") / "state.json").read_text())
        self.assertEqual(state["rc"], 143)
        self.assertTrue(state["finished"])

    def test_timeout_kills_the_process_group(self):
        f = self.f
        pidfile = f.tmp / "bg.pid"

        class Stop:
            signum = None

        t0 = time.monotonic()
        rc = iso.run_task(["sh", "-c", f'sleep 100 & echo $! > "{pidfile}"; sleep 100'], f.tmp, dict(os.environ),
                          f.tmp / "out.txt", 1, Stop())
        self.assertEqual(rc, iso.TIMEOUT_RC)
        self.assertLess(time.monotonic() - t0, 15)
        pid = int(pidfile.read_text())
        time.sleep(0.2)
        self.assertFalse(alive(pid), "그룹 안의 자식도 끝났다")


def alive(pid):
    try:
        with open(f"/proc/{pid}/status") as fh:
            return not any(ln.startswith("State:") and "Z" in ln.split()[1] for ln in fh)
    except OSError:
        return False


class Doctor(Base):
    def test_secret_probes_follow_home_and_config_dir(self):
        f = self.f
        (f.ctl / "deny").write_text("1")
        p = self.ok("doctor")
        secrets = [f.cfg / ".credentials.json", f.home / ".git-credentials", f.home / ".ssh"]
        for s in secrets:
            self.assertIn(f"  ok   cannot read: {s}", p.stdout)
        self.assertIn("  ok   uid cannot write the main working tree", p.stdout)
        self.assertIn(f"  ok   setpriv {f.bin / 'setpriv'} --no-new-privs --inh-caps=-all --bounding-set=-all", p.stdout)
        self.assertNotIn("/code/.", p.stdout.split("== proj")[1], "고정 /code 경로를 보지 않는다")
        (f.ctl / "deny").unlink()
        p = self.ok("doctor", "--all")
        for s in secrets:
            self.assertIn(f"  FAIL uid can read a secret: {s}", p.stdout)
        self.assertIn("  FAIL uid can write the main working tree", p.stdout)
        self.assertIn(f"  ok   agy {f.bin / 'agy'}", p.stdout)
        self.assertIn("  ok   no uid in the range is in /etc/passwd or /etc/group", p.stdout)
        self.assertIn(f"  INFO task uids {f.first_uid}-{f.last_uid} (HARNESS_DELEGATE_UIDS): 4 usable", p.stdout)
        self.assertIn(f"  -- uid {f.uid}", p.stdout)
        self.assertIn("  ok   AGENTS.md present", p.stdout)

    def test_main_tree_file_owned_by_a_task_uid(self):
        if not IS_ROOT:
            self.skipTest("chown 이 필요하다")
        f = self.f
        self.assertIn("  ok   no file in the main working tree belongs to a task uid", self.ok("doctor").stdout)
        # 작업 uid 로 깐 패키지가 하드 링크로 메인 트리에 남은 경우를 흉내
        planted = f.repo / "pkg" / "dep.luau"
        planted.parent.mkdir()
        planted.write_text("x\n")
        os.chown(planted, f.last_uid, f.last_uid)
        p = self.ok("doctor")
        self.assertIn(f"  FAIL 1 file(s) in the main working tree belong to a task uid, so a delegation can change them: {planted}",
                      p.stdout)

        # 옛 표의 uid 는 대역 밖이어도 알린다(대역을 넓히면 다시 위임에 넘어간다)
        os.chown(planted, 61001, 61001)
        p = self.ok("doctor")
        self.assertIn("  ok   no file in the main working tree belongs to a task uid", p.stdout)
        self.assertIn(f"  WARN 1 file(s) in the main working tree belong to uid(s) 61001 of the old per-repository table, "
                      f"outside the range: {planted} - chown them back", p.stdout)

    def test_range_over_the_old_table_warned(self):
        f = self.f
        self.assertNotIn("old per-repository table", self.ok("doctor").stdout)
        if any(is_account(u) for u in range(61004, 61008)):
            self.skipTest("61004-61007 에 실제 계정이 있다")
        p = self.ok("doctor", env=f.env(HARNESS_DELEGATE_UIDS="61004-61007"))
        self.assertIn("  WARN the range includes uid(s) 61004 61005 of the old per-repository table", p.stdout)

    def test_setup_and_collisions_reported(self):
        f = self.f
        self.assertIn("  setup: (none - HARNESS_DELEGATE_SETUP in the repository layer)", self.ok("doctor").stdout)
        f.repo_env("HARNESS_DELEGATE_SETUP=make deps\n")
        self.assertIn("  setup: make deps", self.ok("doctor").stdout)
        pair = account_then_free("user")
        if pair:
            taken, free = pair
            p = self.ok("doctor", env=f.env(HARNESS_DELEGATE_UIDS=f"{taken}-{free}"))
            self.assertIn(f"  WARN real accounts in the range, skipped: {taken} (user)", p.stdout)
            self.assertIn(f"  -- uid {free}", p.stdout, "건너뛴 uid 가 아닌 첫 빈 uid 로 잰다")


@unittest.skipUnless(IS_ROOT, "진짜 setpriv 로 다른 uid 아래 돌리려면 root 가 필요하다")
class RealUid(Base, LifecycleChecks):
    real = True

    def test_agy_worktree_run_collect_remove(self):
        self.check_agy_worktree()

    def test_planted_links_in_worktree(self):
        self.check_planted_links_worktree()

    def test_planted_links_in_home(self):
        self.check_planted_links_home()

    def test_committed_link_is_not_chowned(self):
        self.check_committed_link_is_not_chowned()

    def test_setup_runs_as_the_task(self):
        self.check_setup_runs_as_the_task()

    def test_setup_gets_mise(self):
        self.check_setup_with_mise()

    def test_leftover_home_is_replaced(self):
        self.check_leftover_home_is_replaced()

    def test_codex_empty_runs_as_the_task_uid(self):
        p = self.ok("run", "codex", "c1", self.f.prompt, "--keep")
        self.assertIn("codex answer", (self.f.rec("codex", "c1") / "report.md").read_text(), p.stdout)
        self.assertEqual(self.f.calls("codex")[0]["uid"], self.f.uid)
        self.assertEqual((self.f.base("codex") / "c1").lstat().st_uid, self.f.uid)
        self.ok("collect", "codex", "c1")
        self.ok("remove", "codex", "c1")

    def test_agy_and_codex_of_one_repo_in_parallel(self):
        f = self.f
        (f.ctl / "block").write_text("1")
        a = f.start("run", "agy", "a1", f.prompt)
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"))
            self.ok("run", "codex", "c1", f.prompt)
        finally:
            (f.ctl / "release").write_text("1")
            out, err = a.communicate(timeout=60)
        self.assertEqual(a.returncode, 0, out + err)
        self.assertEqual({c["uid"] for c in f.calls("agy") + f.calls("codex")}, {f.uid, f.uid2})

    def test_process_that_left_the_group_is_killed(self):
        f = self.f
        (f.ctl / "survivor").write_text("1")
        p = self.ok("run", "agy", "t1", f.prompt, "--mode", "empty")
        pid = int((f.ctl / "survivor.pid").read_text())
        self.assertIn("task processes left after the run: 1 killed", p.stdout)
        time.sleep(0.2)
        self.assertFalse(alive(pid), "setsid 로 그룹을 벗어난 작업 프로세스도 끝났다")

    def test_doctor_probes_as_the_uid(self):
        p = self.ok("doctor")
        for s in (self.f.cfg / ".credentials.json", self.f.home / ".git-credentials", self.f.home / ".ssh"):
            self.assertIn(f"  ok   cannot read: {s}", p.stdout)
        self.assertIn("  ok   uid cannot write the main working tree", p.stdout)


if __name__ == "__main__":
    unittest.main()
