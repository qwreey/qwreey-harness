"""qwreey-delegate 드라이버(delegate.py)의 명령 시험. 실행: python3 -I tools/tests/test-delegate-cli.py

가짜 agy·codex·setpriv 로 run -> collect -> remove -> gc, list, 동시 실행 거절, 인자 오류, doctor 의 비밀 경로 점검을 본다.
모델 호출 없음, 다른 uid 로 실행 없음. root 가 아니면 uid 백엔드의 chown 단계만 빼고 돈다(delegate_fixture.launcher).
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delegate_fixture import IS_ROOT, Fixture, git  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

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
            (("run", "agy", "x", f.prompt, "--repo", "nokey"), "repository not in the registry"),
            (("run", "agy", "x", f.prompt, "--ref", "no-such-ref"), "commit not found"),
            (("collect", "agy", "nope"), "not found:"),
            (("remove", "codex", "nope", "--frob"), "unknown option"),
            (("gc", "--days", "x"), "--days must be a number"),
            (("register",), "usage: register"),
        ]
        for args, msg in cases:
            with self.subTest(args=args):
                p = self.fails(2, *args)
                self.assertIn(msg, p.stderr)
        self.assertFalse(f.base("agy").joinpath("x").exists(), "실패한 run 은 작업 사본을 남기지 않는다")

    def test_outside_a_registered_repo(self):
        other = self.f.tmp / "other"
        other.mkdir()
        git("init", "-q", cwd=other)
        p = self.fails(2, "list", cwd=other)
        self.assertIn("repository not in the registry", p.stderr)

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

    def test_register(self):
        f = self.f
        new = f.ws / "second"
        new.mkdir()
        git("init", "-q", cwd=new)
        p = self.ok("register", new)
        line = f.registry.read_text().splitlines()[-1].split("\t")
        self.assertEqual(line[:2], ["second", str(new)])
        self.assertGreaterEqual(int(line[2]), 61000)
        self.assertNotEqual(int(line[2]), f.uid)
        self.assertIn(f"registered: second {new} uid={line[2]}", p.stdout)
        self.assertIn("already registered", self.fails(2, "register", new).stderr)
        third = f.ws / "third"
        third.mkdir()
        git("init", "-q", cwd=third)
        self.assertIn("key already exists", self.fails(2, "register", third, "proj").stderr)
        self.assertIn("not a git repository", self.fails(2, "register", f.tmp).stderr)


class Lifecycle(Base):
    def test_agy_worktree_run_collect_remove(self):
        f = self.f
        p = self.ok("run", "agy", "t1", f.prompt, env=f.env(SOME_TOKEN="secret"))
        base = f.base("agy")
        wt, d, home = base / "t1", base / "t1" / ".delegate", base / ".homes" / "t1"
        self.assertIn("main repo: unchanged", p.stdout)
        self.assertIn(" M tracked.txt", p.stdout)
        self.assertIn("?? new-file.txt", p.stdout)
        self.assertNotIn("REPORT.md", p.stdout.split("worktree changes:")[1].split("report:")[0])
        self.assertIn(f"report: {wt / 'REPORT.md'}", p.stdout)
        self.assertIn("next: main reads and verifies -> delegate.py collect agy t1 --repo proj", p.stdout)

        (call,) = f.calls("agy")
        argv = call["argv"]
        self.assertEqual(argv[1:3], ["--model", "gemini-3.8-flash-high"])
        self.assertIn("--dangerously-skip-permissions", argv)
        self.assertEqual(argv[argv.index("--print-timeout") + 1], "3600s")
        prompt = argv[argv.index("-p") + 1]
        self.assertIn(f"git worktree `{wt}`", prompt, "머리말의 {{WT}} 를 채운다")
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
            log = (f.ctl / "setpriv.log").read_text()
            self.assertIn(f"--reuid={f.uid} --regid={f.uid} --clear-groups", log)

        gem = home / ".gemini" / "antigravity-cli"
        self.assertTrue((gem / "antigravity-oauth-token").is_file())
        self.assertTrue((gem / "settings.json").is_file())
        self.assertFalse((gem / "brain" / "users-other-conv").exists(), "사용자의 다른 대화는 복사하지 않는다")
        self.assertFalse((gem / "conversations").exists())
        self.assertFalse((gem / "conversation_summaries.db-wal").exists())

        state = json.loads((d / "state.json").read_text())
        self.assertEqual((state["agent"], state["mode"], state["isolation"], state["rc"], state["collected"]),
                         ("agy", "worktree", "uid", 0, None))
        self.assertEqual(state["commit"], git("rev-parse", "HEAD", cwd=f.repo).strip())
        self.assertEqual((d / "exit").read_text(), "0\n", "delegate.sh 가 읽는 exit 파일")
        self.assertFalse((d / "pid").exists())
        self.assertIn("mode: worktree", (d / "meta.txt").read_text())
        self.assertTrue((base / ".hooks" / "pre-push").stat().st_mode & 0o111)

        self.assertIn("t1                           finished", self.ok("list").stdout)
        self.assertIn("not collected yet", self.fails(2, "remove", "agy", "t1").stderr)

        p = self.ok("collect", "agy", "t1")
        (out,) = list((base / "runs").iterdir())
        self.assertTrue(out.name.endswith("-t1"))
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
        self.assertEqual((d / "collected").read_text().strip(), str(out))
        self.assertEqual(json.loads((d / "state.json").read_text())["collected"], str(out))

        listing = self.ok("list").stdout
        self.assertIn("t1                           collected", listing)
        self.assertIn("runs/: 1", listing)

        self.ok("remove", "agy", "t1")
        self.assertFalse(wt.exists())
        self.assertFalse(home.exists())
        self.assertNotIn(str(wt), git("worktree", "list", cwd=f.repo))
        self.assertTrue(out.is_dir(), "remove 는 runs/ 기록을 남긴다")

    def test_codex_empty_run_and_gc(self):
        f = self.f
        p = self.ok("run", "codex", "c1", f.prompt)
        base = f.base("codex")
        d, home = base / "c1" / ".delegate", base / ".homes" / "c1"
        self.assertIn(f"report: {d / 'report.md'}", p.stdout)
        self.assertNotIn("worktree changes", p.stdout)
        self.assertEqual((d / "report.md").read_text(), "codex answer\n")
        (call,) = f.calls("codex")
        argv = call["argv"]
        self.assertEqual(argv[1:3], ["exec", "-m"])
        self.assertEqual(argv[3], "gpt-6-luna")
        self.assertIn("model_reasoning_effort=medium", argv)
        self.assertEqual(argv[argv.index("-s") + 1], "read-only")
        self.assertIn("--ignore-user-config", argv)
        self.assertEqual(argv[argv.index("-C") + 1], str(base / "c1"))
        self.assertEqual(argv[argv.index("-o") + 1], str(d / "report.md"))
        self.assertEqual(argv[-1], "-")
        self.assertTrue(call["stdin"].endswith("TASK BODY: say hello\n"))
        self.assertIn("The working directory is empty", call["stdin"])
        self.assertEqual(call["env"]["CODEX_HOME"], str(home / ".codex"))
        self.assertEqual((home / ".codex" / "auth.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(list((base / "c1").iterdir()), [d], "empty 모드는 빈 폴더")

        (base / ".homes" / "orphan").mkdir()
        p = self.ok("gc", "--days", "0")
        self.assertIn("(preview", p.stdout)
        self.assertIn("check      proj-codex/c1 (finished but not collected, 0d)", p.stdout)
        self.assertIn("delete     proj-codex/.homes/orphan", p.stdout)
        self.assertNotIn("check      proj-codex/c1", self.ok("gc").stdout, "기본 14일 전에는 알리지 않는다")

        self.ok("collect", "codex", "c1")
        p = self.ok("gc")
        self.assertIn("delete     proj-codex/c1 (collected", p.stdout)
        self.assertTrue((base / "c1").exists(), "미리보기는 지우지 않는다")
        self.ok("gc", "--apply")
        self.assertFalse((base / "c1").exists())
        self.assertFalse((base / ".homes" / "orphan").exists())
        self.assertEqual(len(list((base / "runs").iterdir())), 1)

    def test_agy_empty_falls_back_to_stdout(self):
        f = self.f
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", "--model", "m-x", "--timeout", "30")
        self.assertIn("agy empty mode is unverified", p.stderr)
        d = f.base("agy") / "e1" / ".delegate"
        self.assertEqual((d / "report.md").read_text(), "agy stdout answer\n")
        argv = f.calls("agy")[0]["argv"]
        self.assertEqual((argv[2], argv[argv.index("--print-timeout") + 1]), ("m-x", "30s"))

    def test_existing_name_refused(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        self.assertIn("already exists", self.fails(2, "run", "codex", "c1", f.prompt).stderr)

    def test_list_across_runs_and_shell_shaped_workspaces(self):
        f = self.f
        self.ok("run", "agy", "a1", f.prompt)
        self.ok("run", "codex", "c1", f.prompt)
        self.ok("collect", "codex", "c1")
        # delegate.sh 가 만든 꼴: state.json 없이 pid/exit/collected 만.
        old = f.base("agy") / "old-done" / ".delegate"
        old.mkdir(parents=True)
        (old / "exit").write_text("0\n")
        (old / "collected").write_text("/somewhere\n")
        fin = f.base("agy") / "old-fin" / ".delegate"
        fin.mkdir(parents=True)
        (fin / "exit").write_text("1\n")
        rec = f.base("codex") / "old-record"
        rec.mkdir()
        (rec / "answer.md").write_text("x")
        p = self.ok("list", "--all")
        for name, state in (("a1", "finished"), ("old-done", "collected"), ("old-fin", "finished"), ("c1", "collected"),
                            ("old-record", "legacy-record")):
            self.assertRegex(p.stdout, rf"\n  {name} +{state} ")
        self.assertIn(f"== {f.base('agy')} (", p.stdout)
        self.assertIn(f"== {f.base('codex')} (", p.stdout)
        self.assertIn("not collected yet", self.fails(2, "remove", "agy", "old-fin").stderr)
        self.ok("remove", "agy", "old-done")
        self.ok("remove", "agy", "old-fin", "--discard")
        self.assertIn("old record proj-codex/old-record", self.ok("gc").stdout)


class Concurrency(Base):
    def test_live_shell_run_counts(self):
        f = self.f
        # delegate.sh 의 살아 있는 작업: pid 파일만 있고 state.json 없음. 이 시험 프로세스의 pid 로 흉내.
        live = f.base("agy") / "sh-run" / ".delegate"
        live.mkdir(parents=True)
        (live / "pid").write_text(f"{os.getpid()}\n")
        p = self.fails(5, "run", "agy", "x", f.prompt)
        self.assertIn("1 agy task(s) already running (limit 1, HARNESS_DELEGATE_MAX_CONCURRENT", p.stderr)
        self.assertFalse((f.base("agy") / "x").exists())
        self.assertRegex(self.ok("list").stdout, r"\n  sh-run +running ")
        self.ok("run", "codex", "x", f.prompt)  # 한도는 에이전트마다

    def test_running_driver_holds_a_slot(self):
        f = self.f
        (f.ctl / "block").write_text("1")
        a = f.start("run", "agy", "a1", f.prompt)
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"), "가짜 agy 가 시작하지 않았다")
            p = self.fails(5, "run", "agy", "a2", f.prompt)
            self.assertIn("1 agy task(s) already running", p.stderr)
            self.assertRegex(self.ok("list").stdout, r"\n  a1 +running ")
            self.assertIn("still running: agy/a1", self.fails(2, "collect", "agy", "a1").stderr)
            self.assertIn("still running", self.fails(2, "remove", "agy", "a1", "--discard").stderr)
            (f.ctl / "started").unlink()
            # 한도 2 면 둘째가 돈다(첫째는 아직 막혀 있다): 슬롯이 실행 중인 작업 수를 센다.
            (f.ctl / "release").write_text("1")
            b = self.f.drive("run", "agy", "a2", f.prompt, env=f.env(HARNESS_DELEGATE_MAX_CONCURRENT="2"))
            self.assertEqual(b.returncode, 0, b.stderr)
        finally:
            (f.ctl / "release").write_text("1")
            out, err = a.communicate(timeout=60)
        self.assertEqual(a.returncode, 0, out + err)
        self.assertRegex(self.ok("list").stdout, r"\n  a1 +finished ")

    def test_stale_pid_of_a_driver_run_is_not_running(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        d = f.base("codex") / "c1" / ".delegate"
        # 비정상 종료 뒤 남은 pid 파일이 다른 살아 있는 프로세스를 가리켜도 실행 잠금이 비었으면 실행 중이 아니다.
        (d / "pid").write_text(f"{os.getpid()}\n")
        self.assertRegex(self.ok("list").stdout, r"\n  c1 +finished ")
        self.ok("run", "codex", "c2", f.prompt)


class Doctor(Base):
    def test_secret_probes_follow_home_and_config_dir(self):
        f = self.f
        (f.ctl / "deny").write_text("1")
        p = self.ok("doctor")
        secrets = [f.cfg / ".credentials.json", f.home / ".git-credentials", f.home / ".ssh"]
        for s in secrets:
            self.assertIn(f"  ok   cannot read: {s}", p.stdout)
        self.assertIn("  ok   uid cannot write the main working tree", p.stdout)
        self.assertNotIn("/code/.", p.stdout.split("== proj")[1], "고정 /code 경로를 보지 않는다")
        (f.ctl / "deny").unlink()
        p = self.ok("doctor", "--all")
        for s in secrets:
            self.assertIn(f"  FAIL uid can read a secret: {s}", p.stdout)
        self.assertIn("  FAIL uid can write the main working tree", p.stdout)
        self.assertIn(f"  ok   agy {f.bin / 'agy'}", p.stdout)
        self.assertIn("  ok   no duplicate uid", p.stdout)
        self.assertIn("  ok   AGENTS.md present", p.stdout)

    def test_duplicates_reported(self):
        f = self.f
        f.registry.write_text(f.registry.read_text() + f"proj2\t{f.repo}\t{f.uid}\t-\n")
        p = self.ok("doctor", "--repo", "proj")
        self.assertIn(f"  FAIL duplicate uid: {f.uid}", p.stdout)
        self.assertIn(f"  FAIL duplicate root: {f.repo}", p.stdout)


if __name__ == "__main__":
    unittest.main()
