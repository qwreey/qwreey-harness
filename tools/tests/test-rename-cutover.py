#!/usr/bin/env python3
"""tools/rename-cutover.sh 테스트: 임시 폴더의 가짜 저장소, 설정 폴더, session-log, coderag 설정과 claude 흉내로 돌린다.

실제 ~/.claude 나 저장소 폴더는 건드리지 않는다(HOME, CLAUDE_CONFIG_DIR, RENAME_OLD_ROOT 를 모두 임시 폴더로).
실행: python3 -I tools/tests/test-rename-cutover.py
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "rename-cutover.sh"
OLD_M, NEW_M = "claude-doctor-market", "qwreey-harness"
SHIM = "plugins/qwreey-conventions/hooks/reply_language.py"
SHIM_TODO = "- [ ] 모든 세션이 다시 실은 뒤 `plugins/qwreey-conventions/hooks/reply_language.py` 껍데기를 지운다\n"
SHIM_DOC = " `reply_language.py` is an unregistered no-op shim (the reply-language check lives in `plugins/qwreey-reply-language`): sessions loaded with the old `hooks.json` still call this path."
STATE = ".rename-cutover-plugins"
SNAP = STATE + ".settings.json"
B_MARK = ".rename-cutover-b"

# claude CLI 흉내. 실제 CLI(2.1.316)를 버리는 설정 폴더에서 잰 동작을 따른다(rename-cutover.sh 머리 주석):
#   marketplace remove: 그 마켓의 설치본, enabledPlugins/pluginConfigs 키, extraKnownMarketplaces 항목, 데이터 폴더를 지움. 없으면 exit 1
#   marketplace add: known_marketplaces 와 extraKnownMarketplaces 를 씀
#   install: enabledPlugins 를 defaultEnabled 값(없으면 true)으로 덮음, pluginConfigs 는 그대로. 없는 플러그인이면 exit 1
# STUB_FAIL_ONCE, STUB_KILL_ONCE 파일에 적힌 id 의 install 은 한 번만 실패하거나 스크립트(부모 bash)를 SIGKILL 한다
STUB_CLAUDE = r'''#!/usr/bin/env python3
import json, os, shutil, signal, sys
cfg = os.environ["CLAUDE_CONFIG_DIR"]
open(os.environ["STUB_CLAUDE_LOG"], "a").write(" ".join(sys.argv[1:]) + "\n")
km_p, ip_p, st_p = (os.path.join(cfg, *p) for p in (("plugins", "known_marketplaces.json"), ("plugins", "installed_plugins.json"), ("settings.json",)))
def load(p, d):
    try: return json.load(open(p))
    except (OSError, ValueError): return d
def once(env, id):
    p = os.environ.get(env)
    if p and os.path.exists(p) and open(p).read().strip() == id:
        os.remove(p); return True
    return False
km, ip, st = load(km_p, {}), load(ip_p, {"version": 2, "plugins": {}}), load(st_p, {})
a = [x for x in sys.argv[1:] if x != "--json"]
if a[:3] == ["plugin", "marketplace", "remove"]:
    if a[3] not in km:
        print(f"Marketplace '{a[3]}' not found", file=sys.stderr); sys.exit(1)
    del km[a[3]]
    st.get("extraKnownMarketplaces", {}).pop(a[3], None)
    for k in [k for k in ip["plugins"] if k.endswith("@" + a[3])]:
        del ip["plugins"][k]
        for sk in ("enabledPlugins", "pluginConfigs"):
            st.get(sk, {}).pop(k, None)
        shutil.rmtree(os.path.join(cfg, "plugins", "data", k.replace("@", "-")), ignore_errors=True)
elif a[:3] == ["plugin", "marketplace", "add"]:
    name = json.load(open(os.path.join(a[3], ".claude-plugin", "marketplace.json")))["name"]
    km[name] = {"source": {"source": "directory", "path": a[3]}, "installLocation": a[3]}
    st.setdefault("extraKnownMarketplaces", {})[name] = {"source": {"source": "directory", "path": a[3]}}
elif a[:2] == ["plugin", "install"]:
    if once("STUB_FAIL_ONCE", a[2]):
        print("install failed", file=sys.stderr); sys.exit(1)
    if once("STUB_KILL_ONCE", a[2]):
        os.kill(os.getppid(), signal.SIGKILL); sys.exit(1)
    name, _, m = a[2].rpartition("@")
    if m not in km:
        print(f"marketplace {m} not found", file=sys.stderr); sys.exit(1)
    root = km[m]["installLocation"]
    src = [p for p in json.load(open(os.path.join(root, ".claude-plugin", "marketplace.json")))["plugins"] if p["name"] == name][0]["source"]
    pj = json.load(open(os.path.join(root, src, ".claude-plugin", "plugin.json")))
    ip["plugins"][a[2]] = [{"scope": "user"}]
    st.setdefault("enabledPlugins", {})[a[2]] = pj.get("defaultEnabled", True)
elif a[:2] == ["plugin", "list"]:
    print(json.dumps([{"id": k} for k in ip["plugins"]]))
json.dump(km, open(km_p, "w")); json.dump(ip, open(ip_p, "w")); json.dump(st, open(st_p, "w"))
'''


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def key_of(p):
    return "".join(c if c.isascii() and c.isalnum() else "-" for c in str(p))


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class Fake:
    """가짜 기계 하나: 저장소(main + 전환 브랜치), 설정 폴더, session-log, coderag 설정, claude 흉내."""

    def __init__(self, tc, enabled=None):
        self.t = Path(tempfile.mkdtemp(prefix="rename-cutover-")).resolve()
        tc.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        self.old = self.t / "Projects" / "claude-doctor"
        self.new = self.t / "Projects" / "qwreey-harness"
        self.cfg = self.t / "cfg"
        self.home = self.t / "home"
        self.hooks = self.t / "git-hooks"
        self.make_repo()
        self.make_config(enabled)
        self.make_bin()

    def make_repo(self):
        r = self.old
        # main: 이 저장소의 home-sync 와 마이그레이션 0001-0009, 플러그인 둘(하나는 기본 꺼짐 팩), 껍데기
        shutil.copytree(ROOT / "tools", r / "tools", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        shutil.copytree(ROOT / "home", r / "home")
        os.remove(r / "home" / "settings-migrations" / "0010-qwreey-harness-market.json")
        write(r / ".claude-plugin" / "marketplace.json", json.dumps({"name": OLD_M, "plugins": [
            {"name": "q", "source": "./plugins/q"}, {"name": "web-security", "source": "./packs/web-security"}]}))
        write(r / "plugins" / "q" / ".claude-plugin" / "plugin.json", '{"name": "q", "version": "1.0.0"}')
        write(r / "packs" / "web-security" / ".claude-plugin" / "plugin.json", '{"name": "web-security", "version": "1.0.0", "defaultEnabled": false}')
        write(r / SHIM, "import sys\n")
        write(r / "plugins" / "qwreey-conventions" / "CLAUDE.md", "- `hooks/hooks.json`: hooks." + SHIM_DOC + "\n")
        write(r / "HUMAN_TODO.md", "# todo\n" + SHIM_TODO + "- [ ] 다른 일\n")

        # main 커밋. 훅은 저장소 밖 빈 폴더로: 기계의 전역 core.hooksPath 에 기대지 않고, 시험이 pre-commit 을 넣을 수 있게
        git(self.t, "init", "-q", "-b", "main", str(r))
        git(r, "config", "user.name", "t"); git(r, "config", "user.email", "t@example.invalid")
        self.hooks.mkdir()
        git(r, "config", "core.hooksPath", str(self.hooks))
        git(r, "add", "-A"); git(r, "commit", "-q", "-m", "main")

        # 전환 브랜치: 마켓 이름과 마이그레이션 0010
        git(r, "checkout", "-q", "-b", "rename-qwreey-harness")
        shutil.copy(ROOT / "home" / "settings-migrations" / "0010-qwreey-harness-market.json", r / "home" / "settings-migrations")
        m = json.loads((r / ".claude-plugin" / "marketplace.json").read_text()); m["name"] = NEW_M
        write(r / ".claude-plugin" / "marketplace.json", json.dumps(m))
        git(r, "add", "-A"); git(r, "commit", "-q", "-m", "rename")
        git(r, "checkout", "-q", "main")

    def make_config(self, enabled):
        c = self.cfg
        write(c / "settings.json", json.dumps({
            "extraKnownMarketplaces": {OLD_M: {"source": {"source": "directory", "path": str(self.old)}}},
            "enabledPlugins": enabled if enabled is not None else {"q@" + OLD_M: True, "other@x": True},
            "pluginConfigs": {"q@" + OLD_M: {"options": {"k": 1}}, "other@x": {"options": {"o": 2}}}}))

        # 0001-0009 는 적용된 것으로: home-sync 가 0010 만 돌린다
        mids = sorted(p.stem for p in (ROOT / "home" / "settings-migrations").glob("000*.json"))
        write(c / ".home-sync-migrations", "\n".join(mids) + "\n")

        # 옛 마켓의 설치본 둘과 데이터 폴더, 옛 경로를 적은 workspace 캐시
        write(c / "plugins" / "known_marketplaces.json", json.dumps({OLD_M: {"source": {"source": "directory", "path": str(self.old)}, "installLocation": str(self.old)}}))
        write(c / "plugins" / "installed_plugins.json", json.dumps({"version": 2, "plugins": {"q@" + OLD_M: [{"scope": "user"}], "web-security@" + OLD_M: [{"scope": "user"}]}}))
        write(c / "plugins" / "data" / ("q-" + OLD_M) / "state.json", "{}")
        (c / "plugins" / "data" / ("web-security-" + OLD_M)).mkdir()
        write(c / "plugins" / "data" / ("qwreey-workspace-" + OLD_M) / "known_repos.json", json.dumps({"repos": [str(self.old)]}))

        # 경로 이름 폴더와 coderag 사용자 설정
        write(c / "projects" / key_of(self.old) / "memory" / "MEMORY.md", "- memory\n")
        sl = self.home / ".local" / "share" / "session-log" / key_of(self.old)
        write(sl / "project.json", json.dumps({"root": str(self.old), "key": key_of(self.old)}))
        write(self.home / ".coderag" / "coderag.toml", f'# 주석 {self.old}\n[[packs]]\nname = "luau-kb"\npath = "{self.old}/packs/luau-kb"\n')

        # CLAUDE_CONFIG_DIR 아래의 전역 설정(옛 폴더의 신뢰 항목)과 지난 세션의 dev-mods 링크
        write(c / ".claude.json", json.dumps({"projects": {str(self.old): {"hasTrustDialogAccepted": True}}}))
        (c / "dev-mods" / "sid-1").mkdir(parents=True)
        os.symlink(self.old / "plugins" / "qwreey-desk", c / "dev-mods" / "sid-1" / "qwreey-desk")

    def make_bin(self):
        b = self.t / "bin"
        write(b / "claude", STUB_CLAUDE); os.chmod(b / "claude", 0o755)
        # 기본은 실행 중인 claude 없음. live 파일이 있으면 그 내용(비면 세션 하나)을 찍는다
        pgrep = '#!/bin/sh\n[ -f "$STUB_LIVE" ] || exit 1\n[ -s "$STUB_LIVE" ] && cat "$STUB_LIVE" || echo "123 claude --session-id x"\n'
        write(b / "pgrep", pgrep); os.chmod(b / "pgrep", 0o755)
        # claude 가 없는 PATH 용: pgrep 흉내만
        nb = self.t / "bin-noclaude"
        write(nb / "pgrep", pgrep); os.chmod(nb / "pgrep", 0o755)

    def run(self, *args, live=None, no_claude=False, **env_extra):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_HOME", "XDG_DATA_HOME", "SESSION_LOG_HOME", "CODERAG_HOME", "HARNESS_ENV", "RENAME_ALLOW_LIVE")}
        if no_claude:
            # 실제 claude 가 있는 PATH 항목도 뺀다
            rest = [d for d in os.environ["PATH"].split(os.pathsep) if not os.access(os.path.join(d, "claude"), os.X_OK)]
            path = os.pathsep.join([str(self.t / "bin-noclaude"), *rest])
        else:
            path = f"{self.t / 'bin'}:{os.environ['PATH']}"
        env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), RENAME_OLD_ROOT=str(self.old),
                   STUB_CLAUDE_LOG=str(self.t / "claude.log"), STUB_LIVE=str(self.t / "live"), PATH=path)
        env.update(env_extra)
        (self.t / "live").unlink(missing_ok=True)
        if live is not None:
            write(self.t / "live", live)
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.t, env=env, capture_output=True, text=True)

    def snapshot(self):
        """바뀌었는지 볼 파일 목록과 내용(.git 밖)."""
        out = {}
        for p in sorted(self.t.rglob("*")):
            if p.is_file() and ".git" not in p.parts and p.name not in ("claude.log", "live"):
                out[str(p.relative_to(self.t))] = p.read_bytes()
        return out

    def settings(self):
        return json.loads((self.cfg / "settings.json").read_text())

    def once(self, name, plugin_id):
        """STUB_FAIL_ONCE / STUB_KILL_ONCE 로 넘길 파일."""
        p = self.t / name
        write(p, plugin_id)
        return str(p)


class T(unittest.TestCase):
    def test_dry_run_changes_nothing(self):
        f = Fake(self)
        before, head = f.snapshot(), git(f.old, "rev-parse", "HEAD")
        r = f.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(f.snapshot(), before)
        self.assertEqual(git(f.old, "rev-parse", "HEAD"), head)
        for s in ("== a.", "== c.", "== e.", "== g.", "== h.", f"merge --ff-only rename-qwreey-harness", "dry-run 끝",
                  f'+    "q@{NEW_M}": true', f"claude plugin install q@{NEW_M} --scope user", "백업", SNAP):
            self.assertIn(s, r.stdout)

    def test_apply_then_rerun(self):
        f = Fake(self)
        r = f.run("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        # 저장소: 옮겨졌고, 병합됐고, 껍데기와 그 할 일 줄, 설명 문장이 한 커밋으로 빠졌다
        self.assertFalse(f.old.exists())
        self.assertTrue((f.new / "home" / "settings-migrations" / "0010-qwreey-harness-market.json").exists())
        self.assertFalse((f.new / SHIM).exists())
        self.assertNotIn("reply_language.py", (f.new / "HUMAN_TODO.md").read_text())
        self.assertIn("- [ ] 다른 일", (f.new / "HUMAN_TODO.md").read_text())
        self.assertNotIn("shim", (f.new / "plugins" / "qwreey-conventions" / "CLAUDE.md").read_text())
        self.assertEqual(git(f.new, "status", "--porcelain"), "")

        # settings: 마켓 선언과 키가 옮겨졌고, install 이 켠 팩은 원래대로(키 없음), 플러그인 옵션은 그대로
        s = f.settings()
        self.assertEqual(s["extraKnownMarketplaces"], {NEW_M: {"source": {"source": "directory", "path": str(f.new)}}})
        self.assertEqual(s["enabledPlugins"], {"q@" + NEW_M: True, "other@x": True})
        self.assertEqual(s["pluginConfigs"], {"q@" + NEW_M: {"options": {"k": 1}}, "other@x": {"options": {"o": 2}}})

        # g 의 백업 셋. settings 는 f(마이그레이션 전)와 g(마이그레이션 뒤) 두 벌이 같은 초에 생겨도 둘 다 남는다
        for n in ("plugins/installed_plugins.json", "plugins/known_marketplaces.json"):
            self.assertEqual(len(list(f.cfg.glob(n + ".bak-*"))), 1, n)
        baks = [p.read_text() for p in f.cfg.glob("settings.json.bak-*")]
        self.assertEqual(len(baks), 2)
        self.assertTrue(any(OLD_M in b for b in baks) and any(f'"q@{NEW_M}"' in b for b in baks))
        # 다시 돌리기용 상태는 끝나면 지운다
        for n in (STATE, SNAP, B_MARK):
            self.assertFalse((f.cfg / n).exists(), n)

        # 데이터 폴더는 remove 전에 옮겨져 남았다
        data = f.cfg / "plugins" / "data"
        self.assertTrue((data / ("q-" + NEW_M) / "state.json").exists())
        self.assertFalse((data / ("q-" + OLD_M)).exists())
        installed = json.loads((f.cfg / "plugins" / "installed_plugins.json").read_text())["plugins"]
        self.assertEqual(sorted(installed), ["q@" + NEW_M, "web-security@" + NEW_M])

        # 경로 이름 폴더와 project.json, coderag 설정(백업 남김, 주석은 그대로)
        self.assertTrue((f.cfg / "projects" / key_of(f.new) / "memory" / "MEMORY.md").exists())
        pj = json.loads((f.home / ".local/share/session-log" / key_of(f.new) / "project.json").read_text())
        self.assertEqual(pj, {"root": str(f.new), "key": key_of(f.new)})
        toml = (f.home / ".coderag" / "coderag.toml").read_text()
        self.assertIn(f'path = "{f.new}/packs/luau-kb"', toml)
        self.assertIn(f"# 주석 {f.old}", toml)
        self.assertTrue(list((f.home / ".coderag").glob("coderag.toml.bak-*")))

        # h 는 보이기만: .claude.json 의 옛 projects 항목, dev-mods 링크, 옛 경로가 남은 캐시
        h = r.stdout[r.stdout.index("== h."):]
        self.assertIn(f'projects["{f.old}"]', h)
        self.assertIn("신뢰 대화", h)
        self.assertIn(f"rm {f.cfg}/dev-mods/sid-1/qwreey-desk", h)
        self.assertIn(f"qwreey-workspace-{NEW_M}/known_repos.json (qwreey-workspace", h)
        self.assertTrue((f.cfg / "dev-mods" / "sid-1" / "qwreey-desk").is_symlink())
        self.assertIn(str(f.old), (f.cfg / ".claude.json").read_text())

        # CLI 순서: 옛 마켓 remove 가 add, install 보다 먼저
        log = (f.t / "claude.log").read_text().splitlines()
        self.assertLess(log.index(f"plugin marketplace remove {OLD_M}"), log.index(f"plugin marketplace add {f.new}"))
        self.assertIn(f"plugin install q@{NEW_M} --scope user", log)

        # 다시 돌리면 끝난 단계는 건너뛰고 바뀌는 것이 없다(백업도 새로 만들지 않는다)
        before, head = f.snapshot(), git(f.new, "rev-parse", "HEAD")
        r2 = f.run("--apply")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("이미 병합됨", r2.stdout)
        self.assertIn("이미 옮겼다", r2.stdout)
        self.assertEqual(git(f.new, "rev-parse", "HEAD"), head)
        self.assertEqual(f.snapshot(), before)

    def test_main_moved_makes_merge_commit(self):
        f = Fake(self)
        write(f.old / "NOTE.md", "main moved\n")
        git(f.old, "add", "NOTE.md"); git(f.old, "commit", "-q", "-m", "moved")
        r = f.run("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((f.new / "NOTE.md").exists())
        self.assertEqual(len(git(f.new, "log", "-1", "--format=%P", "HEAD~1").split()), 2)

    def test_b_commit_fails_then_rerun(self):
        # pre-commit 훅이 b 의 커밋을 막으면 b 는 HEAD 로 되돌리고 멈춘다. 다음 실행이 깨끗한 트리 검사에 막히지 않는다
        f = Fake(self)
        write(f.hooks / "pre-commit", "#!/bin/sh\necho no >&2\nexit 1\n"); os.chmod(f.hooks / "pre-commit", 0o755)
        r = f.run("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("b 실패", r.stderr)
        self.assertEqual(git(f.old, "status", "--porcelain"), "")
        self.assertTrue((f.old / SHIM).exists())
        self.assertIn("reply_language.py", (f.old / "HUMAN_TODO.md").read_text())
        self.assertTrue((f.old / "home" / "settings-migrations" / "0010-qwreey-harness-market.json").exists())  # a 는 끝났다
        self.assertFalse(f.new.exists())
        self.assertFalse((f.cfg / B_MARK).exists())
        self.assertFalse((f.t / "claude.log").exists())

        (f.hooks / "pre-commit").unlink()
        r2 = f.run("--apply")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("이미 병합됨", r2.stdout)
        self.assertFalse((f.new / SHIM).exists())
        self.assertEqual(git(f.new, "status", "--porcelain"), "")
        self.assertIn("껍데기를 지움", git(f.new, "log", "-1", "--format=%s"))

    def test_b_interrupted_resumes(self):
        # b 도중 끊긴 것(표시 파일, b 의 파일만 바뀜)은 사전 검사가 받고 b 가 HEAD 로 되돌린 뒤 다시 한다
        f = Fake(self)
        git(f.old, "rm", "-q", SHIM)
        write(f.old / "HUMAN_TODO.md", "# todo\n- [ ] 다른 일\n")
        write(f.cfg / B_MARK, "")
        r = f.run("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("b 도중에 멈췄다", r.stdout)
        self.assertFalse((f.new / SHIM).exists())
        self.assertEqual(git(f.new, "status", "--porcelain"), "")
        self.assertFalse((f.cfg / B_MARK).exists())

    def test_install_fails_once_then_rerun(self):
        # 사용자가 끈 q 와 enabledPlugins 에 없는 팩: install 이 덮어도 실패한 실행과 다시 돌린 실행 모두 원래 값으로
        f = Fake(self, enabled={"q@" + OLD_M: False, "other@x": True})
        want = {"q@" + NEW_M: False, "other@x": True}
        fail = f.once("fail-once", "web-security@" + NEW_M)
        r = f.run("--apply", STUB_FAIL_ONCE=fail)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("install 실패: web-security@" + NEW_M, r.stderr)
        self.assertEqual(f.settings()["enabledPlugins"], want)
        self.assertTrue((f.cfg / STATE).exists() and (f.cfg / SNAP).exists())

        r2 = f.run("--apply")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        s = f.settings()
        self.assertEqual(s["enabledPlugins"], want)
        self.assertEqual(s["pluginConfigs"], {"q@" + NEW_M: {"options": {"k": 1}}, "other@x": {"options": {"o": 2}}})
        self.assertFalse((f.cfg / STATE).exists() or (f.cfg / SNAP).exists())

    def test_interrupted_g_rerun_uses_first_snapshot(self):
        # g 가 install 도중 죽으면(되돌리기 전) settings 에는 install 이 켠 값이 남는다. 다시 돌린 실행이 그 값을
        # 기준으로 삼지 않고 첫 실행의 스냅숏으로 되돌린다
        f = Fake(self, enabled={"q@" + OLD_M: False, "other@x": True})
        kill = f.once("kill-once", "web-security@" + NEW_M)
        r = f.run("--apply", STUB_KILL_ONCE=kill)
        self.assertEqual(r.returncode, -9, r.stdout + r.stderr)
        self.assertEqual(f.settings()["enabledPlugins"]["q@" + NEW_M], True)  # install 이 덮은 채로 남음
        self.assertTrue((f.cfg / STATE).exists() and (f.cfg / SNAP).exists())

        r2 = f.run("--apply")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("앞선 실행이 적어 둠", r2.stdout)
        s = f.settings()
        self.assertEqual(s["enabledPlugins"], {"q@" + NEW_M: False, "other@x": True})
        self.assertNotIn("web-security@" + NEW_M, s["enabledPlugins"])
        self.assertEqual(s["pluginConfigs"]["q@" + NEW_M], {"options": {"k": 1}})
        installed = json.loads((f.cfg / "plugins" / "installed_plugins.json").read_text())["plugins"]
        self.assertEqual(sorted(installed), ["q@" + NEW_M, "web-security@" + NEW_M])
        self.assertFalse((f.cfg / STATE).exists() or (f.cfg / SNAP).exists())

    def test_live_transient_daemon_hint(self):
        f = Fake(self)
        pid = dead_pid()
        line = f'777 /x/claude daemon run --origin transient --spawned-by {{"label":"claude","cwd":"/x","pid":{pid}}}\n'
        r = f.run("--apply", live=line)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f"pid 777: 띄운 세션(pid {pid})이 이미 없는 transient daemon", r.stdout)
        self.assertIn("claude daemon stop --any", r.stdout)

    def test_refusals_change_nothing(self):
        def dirty_with_mark(f):
            git(f.old, "rm", "-q", SHIM)
            write(f.old / "README.md", "user edit\n"); git(f.old, "add", "README.md")
            write(f.cfg / B_MARK, "")

        cases = {
            "live": lambda f: None,
            "dirty": lambda f: write(f.old / "HUMAN_TODO.md", "changed\n"),
            "dirty beyond b": dirty_with_mark,
            "worktree": lambda f: git(f.old, "worktree", "add", "-q", str(f.t / "wt"), "-b", "wt"),
            "data target": lambda f: (f.cfg / "plugins" / "data" / ("q-" + NEW_M)).mkdir(),
            "key target": lambda f: (f.cfg / "projects" / key_of(f.new)).mkdir(),
            "no branch": lambda f: git(f.old, "branch", "-q", "-D", "rename-qwreey-harness"),
            "no claude": lambda f: None,
        }

        # 막히면 아무것도 바뀌지 않고 claude 도 부르지 않는다
        for name, spoil in cases.items():
            with self.subTest(name):
                f = Fake(self)
                spoil(f)
                before = f.snapshot()
                r = f.run("--apply", live="" if name == "live" else None, no_claude=(name == "no claude"))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("중단", r.stderr)
                self.assertEqual(f.snapshot(), before)
                self.assertTrue(f.old.exists())
                self.assertFalse((f.t / "claude.log").exists())
                if name == "no claude":
                    self.assertIn("claude 가 PATH 에 없다", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
