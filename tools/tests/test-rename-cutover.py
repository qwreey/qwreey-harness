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

# claude CLI 흉내: 인자를 적고, 실제 CLI 처럼 remove 는 그 마켓의 설치본과 데이터 폴더를 지우고 install 은 enabledPlugins 를 덮는다
STUB_CLAUDE = r'''#!/usr/bin/env python3
import json, os, shutil, sys
cfg = os.environ["CLAUDE_CONFIG_DIR"]
open(os.environ["STUB_CLAUDE_LOG"], "a").write(" ".join(sys.argv[1:]) + "\n")
km_p, ip_p, st_p = (os.path.join(cfg, *p) for p in (("plugins", "known_marketplaces.json"), ("plugins", "installed_plugins.json"), ("settings.json",)))
def load(p, d):
    try: return json.load(open(p))
    except (OSError, ValueError): return d
km, ip, st = load(km_p, {}), load(ip_p, {"version": 2, "plugins": {}}), load(st_p, {})
a = [x for x in sys.argv[1:] if x != "--json"]
if a[:3] == ["plugin", "marketplace", "remove"]:
    del km[a[3]]
    for k in [k for k in ip["plugins"] if k.endswith("@" + a[3])]:
        del ip["plugins"][k]
        shutil.rmtree(os.path.join(cfg, "plugins", "data", k.replace("@", "-")), ignore_errors=True)
elif a[:3] == ["plugin", "marketplace", "add"]:
    name = json.load(open(os.path.join(a[3], ".claude-plugin", "marketplace.json")))["name"]
    km[name] = {"source": {"source": "directory", "path": a[3]}, "installLocation": a[3]}
elif a[:2] == ["plugin", "install"]:
    name, _, m = a[2].rpartition("@")
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


class Fake:
    """가짜 기계 하나: 저장소(main + 전환 브랜치), 설정 폴더, session-log, coderag 설정, claude 흉내."""

    def __init__(self, tc):
        self.t = Path(tempfile.mkdtemp(prefix="rename-cutover-")).resolve()
        tc.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        self.old = self.t / "Projects" / "claude-doctor"
        self.new = self.t / "Projects" / "qwreey-harness"
        self.cfg = self.t / "cfg"
        self.home = self.t / "home"
        self.make_repo()
        self.make_config()
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

        # main 커밋
        git(self.t, "init", "-q", "-b", "main", str(r))
        git(r, "config", "user.name", "t"); git(r, "config", "user.email", "t@example.invalid")
        git(r, "add", "-A"); git(r, "commit", "-q", "-m", "main")

        # 전환 브랜치: 마켓 이름과 마이그레이션 0010
        git(r, "checkout", "-q", "-b", "rename-qwreey-harness")
        shutil.copy(ROOT / "home" / "settings-migrations" / "0010-qwreey-harness-market.json", r / "home" / "settings-migrations")
        m = json.loads((r / ".claude-plugin" / "marketplace.json").read_text()); m["name"] = NEW_M
        write(r / ".claude-plugin" / "marketplace.json", json.dumps(m))
        git(r, "add", "-A"); git(r, "commit", "-q", "-m", "rename")
        git(r, "checkout", "-q", "main")

    def make_config(self):
        c = self.cfg
        write(c / "settings.json", json.dumps({
            "extraKnownMarketplaces": {OLD_M: {"source": {"source": "directory", "path": str(self.old)}}},
            "enabledPlugins": {"q@" + OLD_M: True, "other@x": True},
            "pluginConfigs": {"q@" + OLD_M: {"options": {"k": 1}}}}))

        # 0001-0009 는 적용된 것으로: home-sync 가 0010 만 돌린다
        mids = sorted(p.stem for p in (ROOT / "home" / "settings-migrations").glob("000*.json"))
        write(c / ".home-sync-migrations", "\n".join(mids) + "\n")

        # 옛 마켓의 설치본 둘과 데이터 폴더
        write(c / "plugins" / "known_marketplaces.json", json.dumps({OLD_M: {"source": {"source": "directory", "path": str(self.old)}, "installLocation": str(self.old)}}))
        write(c / "plugins" / "installed_plugins.json", json.dumps({"version": 2, "plugins": {"q@" + OLD_M: [{"scope": "user"}], "web-security@" + OLD_M: [{"scope": "user"}]}}))
        write(c / "plugins" / "data" / ("q-" + OLD_M) / "state.json", "{}")
        (c / "plugins" / "data" / ("web-security-" + OLD_M)).mkdir()

        # 경로 이름 폴더와 coderag 사용자 설정
        write(c / "projects" / key_of(self.old) / "memory" / "MEMORY.md", "- memory\n")
        sl = self.home / ".local" / "share" / "session-log" / key_of(self.old)
        write(sl / "project.json", json.dumps({"root": str(self.old), "key": key_of(self.old)}))
        write(self.home / ".coderag" / "coderag.toml", f'# 주석 {self.old}\n[[packs]]\nname = "luau-kb"\npath = "{self.old}/packs/luau-kb"\n')

    def make_bin(self):
        b = self.t / "bin"
        write(b / "claude", STUB_CLAUDE); os.chmod(b / "claude", 0o755)
        # 기본은 실행 중인 claude 없음. live=True 면 하나 있는 것처럼
        write(b / "pgrep", '#!/bin/sh\n[ -f "$STUB_LIVE" ] && { echo "123 claude --session-id x"; exit 0; }\nexit 1\n'); os.chmod(b / "pgrep", 0o755)

    def run(self, *args, live=False):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_HOME", "XDG_DATA_HOME", "SESSION_LOG_HOME", "CODERAG_HOME", "HARNESS_ENV", "RENAME_ALLOW_LIVE")}
        env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), RENAME_OLD_ROOT=str(self.old),
                   STUB_CLAUDE_LOG=str(self.t / "claude.log"), STUB_LIVE=str(self.t / "live"),
                   PATH=f"{self.t / 'bin'}:{os.environ['PATH']}")
        (self.t / "live").unlink(missing_ok=True)
        if live:
            (self.t / "live").touch()
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


class T(unittest.TestCase):
    def test_dry_run_changes_nothing(self):
        f = Fake(self)
        before, head = f.snapshot(), git(f.old, "rev-parse", "HEAD")
        r = f.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(f.snapshot(), before)
        self.assertEqual(git(f.old, "rev-parse", "HEAD"), head)
        for s in ("== a.", "== c.", "== e.", "== g.", "== h.", f"merge --ff-only rename-qwreey-harness", "dry-run 끝",
                  f'+    "q@{NEW_M}": true', f"claude plugin install q@{NEW_M} --scope user"):
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

        # settings: 마켓 선언과 키가 옮겨졌고, install 이 켠 팩은 원래대로(키 없음)
        s = f.settings()
        self.assertEqual(s["extraKnownMarketplaces"], {NEW_M: {"source": {"source": "directory", "path": str(f.new)}}})
        self.assertEqual(s["enabledPlugins"], {"q@" + NEW_M: True, "other@x": True})
        self.assertEqual(s["pluginConfigs"], {"q@" + NEW_M: {"options": {"k": 1}}})

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

        # CLI 순서: 옛 마켓 remove 가 add, install 보다 먼저
        log = (f.t / "claude.log").read_text().splitlines()
        self.assertLess(log.index(f"plugin marketplace remove {OLD_M}"), log.index(f"plugin marketplace add {f.new}"))
        self.assertIn(f"plugin install q@{NEW_M} --scope user", log)

        # 다시 돌리면 끝난 단계는 건너뛰고 바뀌는 것이 없다
        before, head = f.snapshot(), git(f.new, "rev-parse", "HEAD")
        r2 = f.run("--apply")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("이미 병합됨", r2.stdout)
        self.assertIn("이미 옮겼다", r2.stdout)
        self.assertEqual(git(f.new, "rev-parse", "HEAD"), head)
        after = f.snapshot()
        self.assertEqual({k for k in after if ".bak-" not in k}, {k for k in before if ".bak-" not in k})

    def test_main_moved_makes_merge_commit(self):
        f = Fake(self)
        write(f.old / "NOTE.md", "main moved\n")
        git(f.old, "add", "NOTE.md"); git(f.old, "commit", "-q", "-m", "moved")
        r = f.run("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((f.new / "NOTE.md").exists())
        self.assertEqual(len(git(f.new, "log", "-1", "--format=%P", "HEAD~1").split()), 2)

    def test_refusals_change_nothing(self):
        cases = {
            "live": lambda f: None,
            "dirty": lambda f: write(f.old / "HUMAN_TODO.md", "changed\n"),
            "worktree": lambda f: git(f.old, "worktree", "add", "-q", str(f.t / "wt"), "-b", "wt"),
            "data target": lambda f: (f.cfg / "plugins" / "data" / ("q-" + NEW_M)).mkdir(),
            "key target": lambda f: (f.cfg / "projects" / key_of(f.new)).mkdir(),
            "no branch": lambda f: git(f.old, "branch", "-q", "-D", "rename-qwreey-harness"),
        }

        # 막히면 아무것도 바뀌지 않고 claude 도 부르지 않는다
        for name, spoil in cases.items():
            with self.subTest(name):
                f = Fake(self)
                spoil(f)
                before = f.snapshot()
                r = f.run("--apply", live=(name == "live"))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("중단", r.stderr)
                self.assertEqual(f.snapshot(), before)
                self.assertTrue(f.old.exists())
                self.assertFalse((f.t / "claude.log").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
