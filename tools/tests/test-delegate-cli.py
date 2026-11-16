"""qwreey-delegate 드라이버(delegate.py)의 명령 시험. 실행: python3 -I tools/tests/test-delegate-cli.py

가짜 agy·codex·setpriv 로 run -> collect -> remove -> gc, list, 동시 실행 거절(에이전트 슬롯, uid 하나에 작업 하나), 인자 오류,
doctor 의 비밀 경로 점검, 작업 uid 가 심은 링크, 시간 초과와 신호, HARNESS_HEAVY_WRAP 를 본다. 모델 호출 없음.
RealUid 는 root 일 때만 진짜 setpriv 로 registry 에 없는 빈 uid 아래 가짜 에이전트를 돌려 권한 문제를 드러낸다.
root 가 아니면 나머지는 uid 백엔드의 chown 단계만 빼고 돈다(delegate_fixture.launcher).
"""
import json
import os
import signal
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delegate_fixture import IS_ROOT, SCRIPTS, Fixture, git  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import delegate_isolation as iso  # noqa: E402


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
        self.assertFalse(f.rec("agy", "x").exists())

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

    def test_base_owned_by_someone_else_is_refused(self):
        if not IS_ROOT:
            self.skipTest("chown 이 필요하다")
        f = self.f
        base = f.base("agy")
        base.mkdir()
        os.chown(base, f.uid, f.uid)
        p = self.fails(4, "run", "agy", "x", f.prompt)
        self.assertIn("must be a folder owned by uid 0", p.stderr)

    def test_register(self):
        f = self.f
        new = f.ws / "second"
        new.mkdir()
        git("init", "-q", cwd=new)
        p = self.ok("register", new)
        line = f.registry.read_text().splitlines()[-1].split("\t")
        self.assertEqual(line[:2], ["second", str(new)])
        self.assertEqual(line[3], "-")
        codex = int(line[5].removeprefix("codex="))
        self.assertGreaterEqual(int(line[2]), 61000)
        self.assertEqual(len({int(line[2]), codex, f.uid, f.codex_uid}), 4, "uid 는 저장소와 에이전트마다 하나")
        self.assertIn(f"registered: second {new} agy={line[2]} codex={codex}", p.stdout)
        self.assertIn("already registered", self.fails(2, "register", new).stderr)
        # 옛 꼴(uid 하나) 줄은 register 가 codex uid 를 채운다. 다른 줄과 메모는 그대로.
        old = f.add_repo("old", per_agent=False)
        before = f.registry.read_text().splitlines()
        p = self.ok("register", old)
        after = f.registry.read_text().splitlines()
        self.assertEqual(before[:-1], after[:-1])
        cols = after[-1].split("\t")
        self.assertEqual(cols[:4], before[-1].split("\t")[:4])
        self.assertEqual(cols[4], "-")
        self.assertRegex(cols[5], r"^codex=\d+$")
        self.assertIn(f"registered: old {old} {cols[5]}", p.stdout)
        self.assertIn("already registered", self.fails(2, "register", old).stderr)
        third = f.ws / "third"
        third.mkdir()
        git("init", "-q", cwd=third)
        self.assertIn("key already exists", self.fails(2, "register", third, "proj").stderr)
        self.assertIn("not a git repository", self.fails(2, "register", f.tmp).stderr)


class LifecycleChecks:
    """Base 를 물려받는 클래스에 섞는다: 가짜 setpriv 와 진짜 setpriv 에서 같은 흐름을 본다."""

    def check_agy_worktree(self):
        f = self.f
        p = self.ok("run", "agy", "t1", f.prompt, env=f.env(SOME_TOKEN="secret"))
        base = f.base("agy")
        wt, home, rec = base / "t1", base / ".homes" / "t1", f.rec("agy", "t1")
        self.assertIn("main repo: unchanged", p.stdout)
        self.assertIn(" M tracked.txt", p.stdout)
        self.assertIn("?? new-file.txt", p.stdout)
        self.assertNotIn("REPORT.md", p.stdout.split("worktree changes:")[1].split("report:")[0])
        self.assertIn(f"report: {rec / 'report.md'}", p.stdout, "읽을 보고서는 root 소유 기록 안의 사본")
        self.assertEqual((rec / "report.md").read_text(), "agy worktree report\n")
        self.assertIn("next: main reads and verifies -> delegate.py collect agy t1 --repo proj", p.stdout)

        (call,) = f.calls("agy")
        argv = call["argv"]
        self.assertEqual(argv[1:3], ["--model", "gemini-3.8-flash-high"])
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
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        for p in out.rglob("*"):
            self.assertEqual(stat.S_IMODE(p.lstat().st_mode), 0o700 if p.is_dir() else 0o600, p)
        self.assertEqual(json.loads((rec / "state.json").read_text())["collected"], str(out))

        listing = self.ok("list").stdout
        self.assertRegex(listing, r"\n  t1 +collected ")
        self.assertIn("runs/: 1", listing)

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
        p = self.ok("run", "agy", "t1", f.prompt)
        self.assertEqual((f.rec("agy", "t1") / "report.md").read_text(), "agy stdout answer",
                         "링크인 REPORT.md 는 읽지 않고 JSON 의 response 를 쓴다")
        self.ok("collect", "agy", "t1")
        self.assert_untouched()
        (out,) = list((f.base("agy") / "runs").iterdir())
        self.assertFalse((out / "agy").exists(), "링크인 brain 을 따라가지 않는다")
        self.ok("remove", "agy", "t1")
        self.assert_untouched()

    def check_planted_links_home(self):
        f = self.f
        (f.ctl / "plant-home").write_text("1")
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty")
        rec = f.rec("agy", "e1")
        self.assertIn(f"report: {rec / 'report.md'}", p.stdout)
        self.assertEqual((rec / "report.md").read_text(), "agy stdout answer", "링크인 report.md 대신 JSON 의 response")
        self.ok("collect", "agy", "e1")
        (out,) = list((f.base("agy") / "runs").iterdir())
        self.assertFalse((out / "agy").exists(), "링크인 .gemini 를 따라가지 않는다")
        self.assert_untouched()
        self.ok("remove", "agy", "e1")
        self.assert_untouched()

    def assert_untouched(self):
        f = self.f
        self.assertEqual(os.listdir(f.victim), [], "root 가 심긴 링크 너머에 쓰지 않았다")
        self.assertEqual(f.secret.read_text(), "ROOTSECRET\n")
        self.assertTrue((f.victim_brain / "conv-x" / "scratch" / "stolen.txt").is_file(), "링크 너머를 지우지 않았다")
        if IS_ROOT:
            for p in (f.secret, f.victim, f.victim_brain, f.victim_gemini):
                self.assertEqual(p.lstat().st_uid, 0, f"{p} 의 소유자가 바뀌었다")
        for agent in ("agy", "codex"):
            runs = f.base(agent) / "runs"
            if runs.is_dir():
                self.assertEqual(f.leaked(runs), [], "비밀 내용이 runs/ 에 복사됐다")
            if f.base(agent).joinpath(".runs").is_dir():
                self.assertEqual(f.leaked(f.base(agent) / ".runs"), [])

    def check_committed_link_is_not_chowned(self):
        f = self.f
        os.symlink(f.secret, f.repo / "link-to-secret")
        git("add", "link-to-secret", cwd=f.repo)
        git("commit", "-q", "-m", "link", cwd=f.repo)
        self.ok("run", "agy", "t1", f.prompt)
        self.assertEqual(f.secret.lstat().st_uid, 0, "저장소가 커밋한 링크의 대상을 작업 uid 에 넘기지 않는다")
        if IS_ROOT:
            self.assertEqual((f.base("agy") / "t1" / "link-to-secret").lstat().st_uid, f.uid)


    def check_setup_runs_as_the_task(self):
        f = self.f
        f.registry.write_text(f.registry.read_text().replace(
            "\t-\ttest", '\tid -u > setup-uid; env > setup-env; echo "$SECRET_SETUP" > setup-secret\ttest'))
        p = self.ok("run", "agy", "t1", f.prompt, env=f.env(SECRET_SETUP="leak"))
        self.assertNotIn("setup failed", p.stderr)
        wt = f.base("agy") / "t1"
        if self.real:
            self.assertEqual((wt / "setup-uid").read_text().strip(), str(f.uid), "setup 은 작업 uid 로 돈다")
        self.assertEqual((wt / "setup-secret").read_text(), "\n", "setup 은 빈 환경에서 돈다")
        self.assertIn(f"HOME={f.base('agy') / '.homes' / 't1'}", (wt / "setup-env").read_text())


    def check_setup_with_mise(self):
        f = self.f
        misebin, tools, data = f.fake_mise()
        f.user_env((f.cfg / "harness.env").read_text() + f"HARNESS_TOOL_INSTALLS={data / 'installs'}\n")
        f.registry.write_text(f.registry.read_text().replace("\t-\ttest", "\ttimeout 300 mise exec -- pesde install\ttest"))
        env = f.env(PATH=f"{f.bin}:{misebin}:/usr/bin:/bin" + (":/usr/sbin:/sbin" if self.real else ""))
        p = self.ok("run", "agy", "t1", f.prompt, env=env)
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
        p = self.ok("run", "codex", "c1", f.prompt)
        base = f.base("codex")
        wt, home, rec = base / "c1", base / ".homes" / "c1", f.rec("codex", "c1")
        self.assertIn(f"report: {rec / 'report.md'}", p.stdout)
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
        p = self.ok("gc", "--days", "0")
        self.assertIn("(preview", p.stdout)
        self.assertIn("check      proj-codex/c1 (finished but not collected, 0d)", p.stdout)
        self.assertIn("delete     proj-codex/.homes/orphan", p.stdout)
        self.assertNotIn("check      proj-codex/c1", self.ok("gc").stdout, "기본 14일 전에는 알리지 않는다")

        self.ok("collect", "codex", "c1")
        p = self.ok("gc")
        self.assertIn("delete     proj-codex/c1 (collected", p.stdout)
        self.assertTrue(wt.exists(), "미리보기는 지우지 않는다")
        self.ok("gc", "--apply")
        self.assertFalse(wt.exists())
        self.assertFalse(rec.exists())
        self.assertFalse((base / ".homes" / "orphan").exists())
        self.assertEqual(len(list((base / "runs").iterdir())), 1)

    def test_agy_empty_falls_back_to_stdout(self):
        f = self.f
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", "--model", "m-x", "--timeout", "30")
        self.assertIn("agy empty mode is unverified", p.stderr)
        self.assertEqual((f.rec("agy", "e1") / "report.md").read_text(), "agy stdout answer")
        self.assertIn("some log line", (f.rec("agy", "e1") / "stderr.txt").read_text(), "stderr 는 따로")
        argv = f.calls("agy")[0]["argv"]
        self.assertEqual((argv[2], argv[argv.index("--print-timeout") + 1]), ("m-x", "30s"))

    def test_agy_settings_per_mode_and_temp_folders(self):
        f = self.f
        systmp = f.tmp / "systmp"  # 작업 폴더를 품지 않는 임시 폴더. /tmp 는 시험 작업 폴더를 품어 거르지 못한다.
        systmp.mkdir()
        env = f.env(TMPDIR=str(systmp))
        p = self.ok("run", "agy", "e1", f.prompt, "--mode", "empty", env=env)
        self.ok("run", "agy", "w1", f.prompt, env=env)
        empty, wt = (json.loads(c["argv"][c["argv"].index("--settings") + 1])["permissions"] for c in f.calls("agy"))
        tmp_rules = [f"read_file({systmp})", f"write_file({systmp})"]
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
        self.assertIn("warning: temp folder /tmp holds the workspace, so it is not denied", p.stderr)
        self.assertIn("policy: temp folder /tmp holds the workspace", (f.rec("agy", "e1") / "guard.txt").read_text())
        meta = (f.rec("agy", "e1") / "meta.txt").read_text()
        self.assertIn('agy-settings: {"permissions":{"deny":[', meta)
        p = self.ok("doctor", env=env)
        self.assertIn(f"  INFO agy file tools denied in temp folders: {systmp}", p.stdout)
        self.assertIn("  WARN agy temp folder /tmp holds the workspace, so it is not denied", p.stdout)

    def test_agy_denial_is_reported(self):
        f = self.f
        (f.ctl / "agy-denied").write_text("1")
        p = self.ok("run", "agy", "d1", f.prompt, "--mode", "empty")
        rec = f.rec("agy", "d1")
        self.assertIn("report: MISSING - agy ended the turn with an empty answer after it was denied read_file, command",
                      p.stdout)
        self.assertIn("agy denied: read_file, command", (rec / "guard.txt").read_text())
        self.assertIn("agy-denied: read_file, command", (rec / "meta.txt").read_text())
        self.assertEqual(json.loads((rec / "state.json").read_text())["denied"], ["read_file", "command"])
        self.assertIn("auto-denied", (rec / "stderr.txt").read_text())
        self.ok("collect", "agy", "d1")
        (out,) = list((f.base("agy") / "runs").iterdir())
        self.assertTrue((out / "stderr.txt").is_file())

    def test_codex_gets_task_tmpdir(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        home = f.base("codex") / ".homes" / "c1"
        self.assertEqual(f.calls("codex")[0]["env"]["TMPDIR"], str(home / ".tmp"))
        self.assertTrue((home / ".tmp").is_dir())
        if IS_ROOT:
            self.assertEqual((home / ".tmp").lstat().st_uid, f.codex_uid)
        self.assertNotIn("--settings", f.calls("codex")[0]["argv"])

    def test_existing_name_refused(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        self.assertIn("already exists", self.fails(2, "run", "codex", "c1", f.prompt).stderr)

    def test_heavy_wrap_goes_in_front_of_setpriv(self):
        f = self.f
        wrap = f.bin / "wrap"
        wrap.write_text(f'#!/bin/sh\nprintf "%s " "$@" > "{f.ctl}/wrap.log"\nwhile [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n')
        wrap.chmod(0o755)
        f.user_env((f.cfg / "harness.env").read_text() + f"HARNESS_HEAVY_WRAP=wrap -n 7 --\n")
        self.ok("run", "agy", "w1", f.prompt, "--mode", "empty")
        want = (f"-n 7 -- {f.bin / 'setpriv'} --no-new-privs --inh-caps=-all --bounding-set=-all --reuid={f.uid} "
                f"--regid={f.uid} --clear-groups {f.bin / 'agy'} --model gemini-3.8-flash-high")
        self.assertTrue((f.ctl / "wrap.log").read_text().startswith(want), (f.ctl / "wrap.log").read_text())

    def test_list_across_runs_and_shell_shaped_workspaces(self):
        f = self.f
        self.ok("run", "agy", "a1", f.prompt)
        self.ok("run", "codex", "c1", f.prompt)
        self.ok("collect", "codex", "c1")
        # delegate.sh 가 만든 꼴: 기록이 작업 사본 안의 .delegate/ 에 pid/exit/collected 로만.
        old = f.base("agy") / "old-done" / ".delegate"
        old.mkdir(parents=True)
        (old / "exit").write_text("0\n")
        (old / "collected").write_text("/somewhere\n")
        fin = f.base("agy") / "old-fin" / ".delegate"
        fin.mkdir(parents=True)
        (fin / "exit").write_text("1\n")
        (fin / "report.md").write_text("old report\n")
        # 링크로 된 .delegate 는 읽지 않는다: collected 가 링크 너머에 있어도 unknown.
        (f.base("agy") / "old-link").mkdir()
        os.symlink(old, f.base("agy") / "old-link" / ".delegate")
        rec = f.base("codex") / "old-record"
        rec.mkdir()
        (rec / "answer.md").write_text("x")
        p = self.ok("list", "--all")
        for name, state in (("a1", "finished"), ("old-done", "collected"), ("old-fin", "finished"), ("c1", "collected"),
                            ("old-record", "legacy-record"), ("old-link", "unknown")):
            self.assertRegex(p.stdout, rf"\n  {name} +{state} ")
        self.assertIn(f"== {f.base('agy')} (", p.stdout)
        self.assertIn(f"== {f.base('codex')} (", p.stdout)
        self.assertIn("not collected yet", self.fails(2, "remove", "agy", "old-fin").stderr)
        self.ok("collect", "agy", "old-fin")
        out = [r for r in (f.base("agy") / "runs").iterdir() if r.name.endswith("-old-fin")][0]
        self.assertEqual((out / "report.md").read_text(), "old report\n")
        self.assertEqual(sorted(os.listdir(fin)), ["exit", "report.md"], "옛 작업 사본에 쓰지 않는다")
        self.ok("remove", "agy", "old-fin")
        self.ok("remove", "agy", "old-done")
        self.assertTrue(old.parent.parent.joinpath("old-link").exists())
        self.assertIn("old record proj-codex/old-record", self.ok("gc").stdout)


class Concurrency(Base):
    def test_live_shell_run_counts(self):
        f = self.f
        other = f.add_repo("proj2", per_agent=False)
        # delegate.sh 의 살아 있는 작업: pid 파일만 있고 기록 폴더가 없음. 이 시험 프로세스의 pid 로 흉내.
        live = f.ws / "proj2-agy" / "sh-run" / ".delegate"
        live.mkdir(parents=True)
        (live / "pid").write_text(f"{os.getpid()}\n")
        p = self.fails(5, "run", "agy", "x", f.prompt)
        self.assertIn("1 agy task(s) already running (limit 1, HARNESS_DELEGATE_MAX_CONCURRENT", p.stderr)
        self.assertFalse((f.base("agy") / "x").exists())
        self.assertRegex(self.ok("list", "--repo", "proj2").stdout, r"\n  sh-run +running ")
        self.ok("run", "codex", "x", f.prompt)  # 한도는 에이전트마다
        p = self.fails(5, "run", "codex", "y", f.prompt, cwd=other)
        self.assertIn("another task of uid", p.stderr, "옛 꼴 줄: delegate.sh 의 agy 작업과 codex 가 uid 를 나눈다")
        self.assertIn(f"register {other}' gives each agent its own uid", p.stderr)

    def test_running_driver_holds_a_slot_and_the_uid(self):
        f = self.f
        f.add_repo("proj2")
        (f.ctl / "block").write_text("1")
        a = f.start("run", "agy", "a1", f.prompt)
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"), "가짜 agy 가 시작하지 않았다")
            p = self.fails(5, "run", "agy", "a2", f.prompt, "--repo", "proj2")
            self.assertIn("1 agy task(s) already running", p.stderr)
            p = self.fails(5, "run", "agy", "a3", f.prompt, env=f.env(HARNESS_DELEGATE_MAX_CONCURRENT="2"))
            self.assertIn(f"another task of uid {f.uid} (proj) is running; one task per uid at a time", p.stderr,
                          "같은 저장소의 같은 에이전트는 한도가 남아도 uid 하나에 작업 하나")
            self.ok("run", "codex", "c1", f.prompt)  # 같은 저장소의 codex 는 자기 uid 로 나란히 돈다
            self.assertIn(f"--reuid={f.codex_uid} ", (f.ctl / "setpriv.log").read_text())
            self.assertRegex(self.ok("list").stdout, r"\n  a1 +running ")
            self.assertIn("still running: agy/a1", self.fails(2, "collect", "agy", "a1").stderr)
            self.assertIn("still running", self.fails(2, "remove", "agy", "a1", "--discard").stderr)
            (f.ctl / "started").unlink()
            # 한도 2 면 다른 저장소의 둘째가 돈다(첫째는 아직 막혀 있다).
            (f.ctl / "release").write_text("1")
            b = f.drive("run", "agy", "a2", f.prompt, "--repo", "proj2", env=f.env(HARNESS_DELEGATE_MAX_CONCURRENT="2"))
            self.assertEqual(b.returncode, 0, b.stderr)
        finally:
            (f.ctl / "release").write_text("1")
            out, err = a.communicate(timeout=60)
        self.assertEqual(a.returncode, 0, out + err)
        self.assertRegex(self.ok("list").stdout, r"\n  a1 +finished ")

    def test_task_written_pid_does_not_fake_running(self):
        f = self.f
        self.ok("run", "codex", "c1", f.prompt)
        # 작업 uid 는 자기 .delegate/ 에 무엇이든 쓴다. 기록 폴더가 있으면 그것만 본다.
        (f.base("codex") / "c1" / ".delegate" / "pid").write_text(f"{os.getpid()}\n")
        (f.base("codex") / "c1" / ".delegate" / "collected").write_text("x\n")
        self.assertRegex(self.ok("list").stdout, r"\n  c1 +finished ")
        self.assertIn("not collected yet", self.fails(2, "remove", "codex", "c1").stderr)
        self.ok("run", "codex", "c2", f.prompt)


    def test_old_row_shares_one_uid(self):
        f = self.f
        f.add_repo("shared", per_agent=False)
        (f.ctl / "block").write_text("1")
        a = f.start("run", "agy", "a1", f.prompt, "--repo", "shared")
        try:
            self.assertTrue(f.wait_for(f.ctl / "started"))
            p = self.fails(5, "run", "codex", "c1", f.prompt, "--repo", "shared")
            self.assertIn("agy and codex of shared share it", p.stderr)
        finally:
            (f.ctl / "release").write_text("1")
            a.communicate(timeout=60)
        self.assertIn("WARN agy and codex share uid", self.ok("doctor", "--repo", "shared").stdout)


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
        state = json.loads((f.rec("agy", "s1") / "state.json").read_text())
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
        self.assertIn("  ok   no duplicate uid", p.stdout)
        self.assertIn("  ok   AGENTS.md present", p.stdout)

    def test_duplicates_reported(self):
        f = self.f
        other = f.add_repo("proj3")
        f.registry.write_text(f.registry.read_text() + f"proj4\t{other}x\t62990\t-\t-\tcodex={f.codex_uid}\n")
        p = self.ok("doctor", "--repo", "proj")
        self.assertIn(f"  FAIL duplicate uid: {f.codex_uid}", p.stdout, "여섯째 열의 uid 도 센다")
        self.assertIn(f"== proj  root={f.repo}  agy={f.uid}  codex={f.codex_uid}", p.stdout)
        self.assertNotIn("WARN agy and codex share", p.stdout)
        f.registry.write_text(f.registry.read_text() + f"proj2\t{f.repo}\t{f.uid}\t-\n")
        p = self.ok("doctor", "--repo", "proj")
        self.assertRegex(p.stdout, rf"  FAIL duplicate uid: .*\b{f.uid}\b")
        self.assertIn(f"  FAIL duplicate root: {f.repo}", p.stdout)


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

    def test_codex_empty_runs_as_its_own_uid(self):
        p = self.ok("run", "codex", "c1", self.f.prompt)
        self.assertIn("codex answer", (self.f.rec("codex", "c1") / "report.md").read_text(), p.stdout)
        self.assertEqual(self.f.calls("codex")[0]["uid"], self.f.codex_uid)
        self.assertEqual((self.f.base("codex") / "c1").lstat().st_uid, self.f.codex_uid)
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
        self.assertEqual({c["uid"] for c in f.calls("agy") + f.calls("codex")}, {f.uid, f.codex_uid})

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
