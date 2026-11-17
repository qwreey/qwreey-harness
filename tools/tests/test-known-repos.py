"""lib/known_repos.py 시험. 실행: python3 -I tools/tests/test-known-repos.py  (모델 호출 없음, git 없이 .git 폴더와 파일만 흉내 낸다)

가짜 설정 디렉터리의 projects/<폴더>/<세션>.jsonl 에 cwd 줄을 두고, 저장소 루트 찾기, worktree 합치기, 없어진 경로 빼기,
extra 와 exclude, 기본 제외(임시 폴더, ~/.cache, .claude/worktrees), 옛 HARNESS_WORKSPACE 출처, 옵션 층(qwreey-workspace 옵션을 다른 플러그인 사본도 본다), 캐시 적중과 다시 읽기를 본다.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "lib" / "known_repos.py"
LOADER = ROOT / "home" / ".claude" / "lib" / "harness_env.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(LOADER.parent))  # options() 가 옆의 harness_env 를 import 한다(정본 자리에는 사본이 없다)
kr = load(CANON, "known_repos_under_test")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="known-repos-")).resolve()
        self.cfg = self.tmp / "cfg"
        (self.cfg / "projects").mkdir(parents=True)
        self.saved = dict(os.environ)
        for k in list(os.environ):
            if k.startswith(("HARNESS_", "CLAUDE_")):
                del os.environ[k]
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg)
        os.environ["HOME"] = str(self.tmp / "home")
        os.environ["HARNESS_ENV"] = str(self.tmp / "no-user-harness.env")
        # 시험 트리는 시스템 임시 폴더 아래라 기본 제외에 걸린다. 이 프로세스의 임시 폴더(gettempdir 가 기억하는 값)를 트리 안 한 곳으로 옮긴다.
        self.systmp = self.tmp / "systmp"
        self.systmp.mkdir()
        self.saved_tempdir = tempfile.tempdir
        tempfile.tempdir = str(self.systmp)
        os.environ["TMPDIR"] = str(self.systmp)  # 하위 프로세스도 같은 곳을 보게
        self.n = 0

    def tearDown(self):
        tempfile.tempdir = self.saved_tempdir
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def repo(self, rel):
        p = self.tmp / rel
        (p / ".git").mkdir(parents=True, exist_ok=True)
        return p

    def worktree(self, main, rel, name="wt"):
        """main 저장소의 worktree 흉내: <rel>/.git 파일이 <main>/.git/worktrees/<name> 을 가리킨다."""
        p = self.tmp / rel
        p.mkdir(parents=True, exist_ok=True)
        (main / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)
        (p / ".git").write_text("gitdir: %s\n" % (main / ".git" / "worktrees" / name), encoding="utf-8")
        return p

    def session(self, cwd, folder=None, head=None, age=0):
        """projects/<folder>/<n>.jsonl 에 cwd 줄을 쓴다. head 는 cwd 줄 앞에 둘 줄들."""
        self.n += 1
        folder = folder or "-" + str(cwd).strip("/").replace("/", "-")
        d = self.cfg / "projects" / folder
        d.mkdir(parents=True, exist_ok=True)
        lines = list(head or [{"type": "ai-title", "aiTitle": "x"}, {"type": "mode", "mode": "normal"}])
        if cwd is not None:
            lines.append({"type": "user", "cwd": str(cwd), "message": {"content": "hi"}})
        f = d / ("s%d.jsonl" % self.n)
        f.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        if age:
            t = time.time() - age
            os.utime(f, (t, t))
        return f

    def repos(self, **kw):
        kw.setdefault("extra", "")
        kw.setdefault("exclude", "")
        kw.setdefault("workspace", "")
        kw.setdefault("cache", "")
        return kr.repos(**kw)


class Sources(Base):
    def test_session_cwds(self):
        a = self.repo("p/a")
        b = self.repo("p/b")
        (b / "src" / "deep").mkdir(parents=True)
        self.session(a)
        self.session(b / "src" / "deep")
        self.session(self.tmp / "loose")  # 저장소가 아닌 cwd
        (self.tmp / "loose").mkdir()
        self.assertEqual(self.repos(), [str(a), str(b)], "하위 폴더 cwd 는 위로 올라가 저장소 루트로")

    def test_cwd_after_long_head_and_windows_escape(self):
        a = self.repo("p/a")
        self.session(a, head=[{"type": "summary", "text": "x" * 5000}] * 10)  # 첫 읽기(HEAD_FIRST) 너머의 cwd
        self.assertEqual(self.repos(), [str(a)])
        f = self.session(a, folder="-esc")
        f.write_text('{"cwd":"%s"}\n' % str(a).replace("/", "\\/"), encoding="utf-8")
        self.assertEqual(kr._cwd_of(str(f.parent)), str(a), "JSON escape 를 푼다")

    def test_latest_file_without_cwd_falls_back(self):
        a = self.repo("p/a")
        self.session(a, folder="-p-a", age=100)
        self.session(None, folder="-p-a")  # 막 시작해 cwd 줄이 아직 없는 최근 세션
        self.assertEqual(self.repos(), [str(a)])

    def test_missing_paths_are_dropped(self):
        a = self.repo("p/a")
        self.session(a)
        self.session(self.tmp / "p" / "gone")
        self.assertEqual(self.repos(), [str(a)])
        shutil.rmtree(a)
        self.assertEqual(self.repos(), [])

    def test_worktrees_fold_into_main(self):
        main = self.repo("p/main")
        wt = self.worktree(main, "p/main/.claude/worktrees/agent-1", "agent-1")
        outside = self.worktree(main, "elsewhere/main-wt", "main-wt")
        self.session(wt)
        (outside / "sub").mkdir()
        self.session(outside / "sub")
        self.assertEqual(self.repos(), [str(main)])
        self.assertEqual(kr.repo_root(str(outside / "sub")), str(main))

    def test_worktree_of_missing_main_is_dropped_and_submodule_kept(self):
        gone = self.tmp / "p" / "gone"
        wt = self.tmp / "p" / "wt"
        wt.mkdir(parents=True)
        (wt / ".git").write_text("gitdir: %s/.git/worktrees/wt\n" % gone, encoding="utf-8")
        self.assertIsNone(kr.repo_root(str(wt)))
        sup = self.repo("p/super")
        sub = sup / "mod"
        sub.mkdir()
        (sub / ".git").write_text("gitdir: ../.git/modules/mod\n", encoding="utf-8")
        self.assertEqual(kr.repo_root(str(sub)), str(sub), "서브모듈은 자기 저장소다")

    def test_extra_repo_or_parent_folder(self):
        one = self.repo("solo/one")
        two = self.repo("box/two")
        three = self.repo("box/three")
        (self.tmp / "box" / "plain").mkdir()
        main = self.repo("p/main")
        wt = self.worktree(main, "box/main-wt")
        got = self.repos(extra="%s; %s ;" % (one, self.tmp / "box"))
        self.assertEqual(got, sorted([str(one), str(two), str(three), str(main)]), "폴더는 바로 아래 자식 저장소, worktree 는 본 저장소로")
        self.assertNotIn(str(wt), got)
        self.assertEqual(self.repos(extra=str(self.tmp / "nowhere")), [])

    def test_extra_with_tilde(self):
        r = self.repo("home/Projects/r")
        self.assertEqual(self.repos(extra="~/Projects"), [str(r)])

    def test_legacy_workspace_children_only(self):
        ws = self.repo("ws")  # 작업공간 폴더 자체가 저장소여도 옛 뜻대로 자식만 본다
        a = self.repo("ws/a")
        self.assertEqual(self.repos(workspace=str(ws)), [str(a)])
        self.assertEqual(self.repos(extra=str(ws)), [str(ws)], "extra 는 저장소 자체를 넣는다")

    def test_exclude_paths_and_globs(self):
        a = self.repo("p/a")
        b = self.repo("p/b")
        t1 = self.repo("scratch/t1")
        t2 = self.repo("scratch/deep/t2")
        for r in (a, b, t1, t2):
            self.session(r)
        self.assertEqual(self.repos(exclude=str(self.tmp / "scratch")), [str(a), str(b)], "경로는 그 아래까지")
        self.assertEqual(self.repos(exclude="%s/scratch/*" % self.tmp), [str(a), str(b)], "glob 은 경로 전체에")
        self.assertEqual(self.repos(exclude="*/p/b;%s" % t1), [str(a), str(t2)])
        ab = self.repo("p/ab")
        self.session(ab)
        got = self.repos(exclude=str(a))
        self.assertIn(str(ab), got, "이름 앞부분만 같은 저장소(p/ab)는 p/a 경로 제외에 걸리지 않는다")
        self.assertNotIn(str(a), got)


class Defaults(Base):
    def test_scratch_places_are_dropped_from_sessions(self):
        a = self.repo("p/a")
        t = self.repo("systmp/scratch")
        c = self.repo("home/.cache/tool/clone")
        wt = self.repo("p/a/.claude/worktrees/w1/inner")  # worktree 아래 따로 만든 저장소
        for r in (a, t, c, wt):
            self.session(r)
        self.assertEqual(self.repos(), [str(a)])
        self.assertEqual(self.repos(defaults=[]), sorted(map(str, (a, t, c, wt))), "defaults=[] 면 기본 제외가 없다")
        self.assertEqual(kr.default_exclude()[:2], [str(self.systmp), str(self.tmp / "home" / ".cache")])

    def test_explicit_extra_is_kept(self):
        t = self.repo("systmp/kept")
        self.assertEqual(self.repos(extra=str(t)), [str(t)], "사람이 적은 저장소는 기본 제외에 걸지 않는다")
        self.assertEqual(self.repos(extra=str(t), exclude=str(t)), [], "사람이 적은 제외는 건다")

    def test_legacy_workspace_children_are_auto(self):
        a = self.repo("ws/a")
        self.repo("ws/a/.claude/worktrees/x")
        self.assertEqual(self.repos(workspace=str(self.tmp / "ws")), [str(a)])
        self.assertEqual(self.repos(workspace=str(self.systmp)), [])

    def test_excluded_rules(self):
        self.assertTrue(kr.excluded("/w/p/.claude/worktrees/x", ["*/.claude/worktrees/*"]))
        self.assertFalse(kr.excluded("/w/p", ["*/.claude/worktrees/*"]))
        self.assertTrue(kr.excluded("/w/tmp/x", ["/w/tmp"]))
        self.assertFalse(kr.excluded("/w/tmpx", ["/w/tmp"]))


class Options(Base):
    def test_values_from_layers(self):
        a = self.repo("x/a")
        b = self.repo("ws/b")
        (self.tmp / "user.env").write_text("HARNESS_WORKSPACE=%s\nHARNESS_WORKSPACE_EXTRA=%s\n" % (self.tmp / "ws", a), encoding="utf-8")
        os.environ["HARNESS_ENV"] = str(self.tmp / "user.env")
        self.assertEqual(kr.repos(cache=""), sorted([str(a), str(b)]))
        os.environ["HARNESS_WORKSPACE_EXCLUDE"] = str(b)
        self.assertEqual(kr.repos(cache=""), [str(a)], "환경 변수가 이긴다")
        self.assertEqual(kr.repos(cache="", exclude=""), sorted([str(a), str(b)]), "넘긴 값은 설정을 읽지 않는다")

    def test_repo_layers_cannot_change_the_list(self):
        a = self.repo("x/a")
        proj = self.repo("proj")
        (proj / ".claude").mkdir()
        (proj / ".claude" / "harness.env").write_text("HARNESS_WORKSPACE_EXTRA=%s\nHARNESS_WORKSPACE=%s\n" % (a, self.tmp / "x"), encoding="utf-8")
        os.environ["CLAUDE_PROJECT_DIR"] = str(proj)
        o = kr.options()
        self.assertEqual((o["HARNESS_WORKSPACE_EXTRA"], o["HARNESS_WORKSPACE"]), ("", ""))

    def test_workspace_plugin_options_seen_from_another_plugin(self):
        # 다른 플러그인에 둔 사본도 작업공간 플러그인의 옵션을 본다.
        a = self.repo("x/a")
        b = self.repo("x/b")
        plug = self.tmp / "plugins" / "qwreey-conventions"
        (plug / ".claude-plugin").mkdir(parents=True)
        (plug / ".claude-plugin" / "plugin.json").write_text('{"name": "qwreey-conventions"}', encoding="utf-8")
        (plug / "hooks").mkdir()
        shutil.copy(CANON, plug / "hooks" / "known_repos.py")
        shutil.copy(LOADER, plug / "hooks" / "harness_env.py")
        (self.cfg / "settings.json").write_text(json.dumps({"pluginConfigs": {
            "qwreey-workspace@mkt": {"options": {"harness_workspace_extra": str(a), "harness_workspace_exclude": "", "other": "x"}},
            "qwreey-conventions@mkt": {"options": {"harness_workspace_extra": str(b)}}}}), encoding="utf-8")
        code = ("import sys; sys.path.insert(0, %r); import known_repos, json; print(json.dumps(known_repos.repos(cache='')))"
                % str(plug / "hooks"))
        import subprocess
        p = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, env=dict(os.environ), timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), [str(a)], "qwreey-workspace 옵션을 읽고, 선언하지 않은 자기 옵션은 무시한다")


class Cache(Base):
    def test_hit_and_miss(self):
        cache = self.tmp / "data" / "known_repos.json"
        a = self.repo("p/a")
        self.session(a)
        self.assertEqual(self.repos(cache=str(cache)), [str(a)])
        data = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(data["repos"], [str(a)])
        # 적중: 캐시의 목록을 그대로 쓴다(결과를 바꿔 두면 바뀐 결과가 나온다).
        b = self.repo("p/b")
        data["repos"] = [str(a), str(b)]
        cache.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.repos(cache=str(cache)), [str(a), str(b)], "projects/ 가 그대로면 캐시를 쓴다")
        # 적중이어도 없어진 경로는 뺀다.
        shutil.rmtree(b)
        self.assertEqual(self.repos(cache=str(cache)), [str(a)])
        # 새 프로젝트 폴더가 생기면 다시 모은다.
        c = self.repo("p/c")
        self.session(c)
        self.assertEqual(self.repos(cache=str(cache)), [str(a), str(c)])
        # 옵션 값이 바뀌면 다시 모은다.
        d = self.repo("q/d")
        self.assertEqual(self.repos(cache=str(cache), extra=str(d)), [str(a), str(c), str(d)])
        self.assertEqual(self.repos(cache=str(cache), extra=str(d), exclude=str(a)), [str(c), str(d)])

    def test_changed_project_folder_is_reread_alone(self):
        cache = self.tmp / "known_repos.json"
        a = self.repo("p/a")
        b = self.repo("p/b")
        self.session(a, folder="-fa")
        self.session(b, folder="-fb")
        self.repos(cache=str(cache))
        data = json.loads(cache.read_text(encoding="utf-8"))
        data["dirs"]["-fa"][1] = str(b)  # 바뀌지 않은 폴더의 cwd 는 캐시에서 쓴다는 것을 보려고 일부러 틀린 값을 둔다
        data["repos"] = []
        cache.write_text(json.dumps(data), encoding="utf-8")
        c = self.repo("p/c")
        f = self.session(c, folder="-fb")
        t = time.time() + 5
        os.utime(f.parent, (t, t))
        self.assertEqual(self.repos(cache=str(cache)), [str(b), str(c)], "-fa 는 캐시의 cwd, -fb 만 다시 읽는다")

    def test_workspace_folder_change_is_seen(self):
        cache = self.tmp / "known_repos.json"
        ws = self.tmp / "ws"
        a = self.repo("ws/a")
        self.assertEqual(self.repos(cache=str(cache), workspace=str(ws)), [str(a)])
        b = self.repo("ws/b")
        t = time.time() + 5
        os.utime(ws, (t, t))
        self.assertEqual(self.repos(cache=str(cache), workspace=str(ws)), [str(a), str(b)], "작업공간 폴더 mtime 이 바뀌면 다시 모은다")

    def test_plugin_data_default_and_broken_cache(self):
        a = self.repo("p/a")
        self.session(a)
        os.environ["CLAUDE_PLUGIN_DATA"] = str(self.tmp / "pdata")
        self.assertEqual(kr.repos(extra="", exclude="", workspace=""), [str(a)])
        cache = self.tmp / "pdata" / "known_repos.json"
        self.assertTrue(cache.is_file(), "CLAUDE_PLUGIN_DATA 가 있으면 그 아래에 둔다")
        cache.write_text("{broken", encoding="utf-8")
        self.assertEqual(kr.repos(extra="", exclude="", workspace=""), [str(a)], "깨진 캐시는 없는 것과 같다")
        del os.environ["CLAUDE_PLUGIN_DATA"]
        cache.unlink()
        kr.repos(extra="", exclude="", workspace="")
        self.assertFalse(cache.exists(), "CLAUDE_PLUGIN_DATA 가 없으면 캐시를 쓰지 않는다")

    def test_no_projects_folder(self):
        shutil.rmtree(self.cfg / "projects")
        self.assertEqual(self.repos(), [])


if __name__ == "__main__":
    unittest.main()
