#!/usr/bin/env python3
"""settings-migrate.py 테스트. 실행: python3 tools/tests/test-settings-migrate.py"""
import importlib.util, json, os, subprocess, sys, tempfile, unittest, unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "settings-migrate.py")
spec = importlib.util.spec_from_file_location("sm", MOD)
sm = importlib.util.module_from_spec(spec); spec.loader.exec_module(sm)
HOOK = "python3 $HOME/.claude/hooks/a.py"


class Env:
    def __init__(self, tc, settings=None, migs=()):
        self.d = tempfile.mkdtemp(); tc.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))
        self.s = os.path.join(self.d, "settings.json"); self.m = os.path.join(self.d, "migs"); self.r = os.path.join(self.d, ".rec")
        os.makedirs(self.m)
        if settings is not None:
            with open(self.s, "w") as f:
                f.write(settings if isinstance(settings, str) else json.dumps(settings))
        for i, m in enumerate(migs):
            self.add(m)

    def add(self, m):
        with open(os.path.join(self.m, m["id"] + ".json"), "w") as f:
            json.dump(m, f)

    def run(self, *extra):
        return sm.main(["run", "--settings", self.s, "--dir", self.m, "--records", self.r, "--quiet", *extra])

    def get(self):
        return json.load(open(self.s))

    def recs(self):
        return open(self.r).read().split() if os.path.exists(self.r) else []


def mig(id, *ops):
    return {"id": id, "why": "t", "ops": list(ops)}


def enable(p, v=True, **kw):
    return {"op": "set", "path": ["enabledPlugins", p], "value": v, **kw}


class T(unittest.TestCase):
    def test_user_plugin_preserved_managed_added(self):
        e = Env(self, {"enabledPlugins": {"mine@x": True}}, [mig("0001-a", enable("m@claude-doctor-market"))])
        self.assertEqual(e.run(), 0)
        self.assertEqual(e.get()["enabledPlugins"], {"mine@x": True, "m@claude-doctor-market": True})

    def test_user_disabled_not_reenabled(self):
        e = Env(self, {}, [mig("0001-a", enable("m@claude-doctor-market"))])
        e.run()
        s = e.get(); s["enabledPlugins"]["m@claude-doctor-market"] = False
        open(e.s, "w").write(json.dumps(s))
        self.assertEqual(e.run(), 0)  # 이미 적용됨
        self.assertFalse(e.get()["enabledPlugins"]["m@claude-doctor-market"])
        # 새 마이그레이션이 다른 항목을 건드려도 꺼둔 값은 그대로
        e.add(mig("0002-b", enable("n@claude-doctor-market")))
        e.run()
        self.assertFalse(e.get()["enabledPlugins"]["m@claude-doctor-market"])
        self.assertTrue(e.get()["enabledPlugins"]["n@claude-doctor-market"])

    def test_permissions_add_remove(self):
        e = Env(self, {"permissions": {"allow": ["Bash(ls)", "Old"], "defaultMode": "auto"}},
                [mig("0001-a", {"op": "add", "path": "permissions.allow", "items": ["New", "Bash(ls)"]},
                     {"op": "remove", "path": "permissions.allow", "items": ["Old"]},
                     {"op": "add", "path": "permissions.deny", "items": ["X"]})])
        e.run()
        p = e.get()["permissions"]
        self.assertEqual(p["allow"], ["Bash(ls)", "New"]); self.assertEqual(p["deny"], ["X"]); self.assertEqual(p["defaultMode"], "auto")

    def test_hooks_user_kept_managed_upserted(self):
        user = {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}
        old = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /home/u/.claude/hooks/a.py", "timeout": 1}]}
        e = Env(self, {"hooks": {"PreToolUse": [user, old]}},
                [mig("0001-a", {"op": "hook-upsert", "event": "PreToolUse", "matcher": "Bash", "command": HOOK, "fields": {"timeout": 9}},
                     {"op": "hook-upsert", "event": "Stop", "command": HOOK})])
        with unittest.mock.patch.dict(os.environ, {"HOME": "/home/u"}):
            e.run()
        h = e.get()["hooks"]
        self.assertEqual(h["PreToolUse"][0], user)
        self.assertEqual(h["PreToolUse"][1]["hooks"], [{"type": "command", "command": HOOK, "timeout": 9}])  # 같은 command(HOME 풀어 비교) 교체
        self.assertEqual(h["Stop"], [{"hooks": [{"type": "command", "command": HOOK}]}])

    def test_hook_remove(self):
        g = {"hooks": [{"type": "command", "command": HOOK}]}
        e = Env(self, {"hooks": {"Stop": [g]}}, [mig("0001-a", {"op": "hook-remove", "event": "Stop", "command": HOOK})])
        e.run()
        self.assertNotIn("hooks", e.get())

    def test_hook_remove_by_command_across_groups_keeps_others(self):
        sub = "python3 $HOME/.claude/hooks/subagent-slots.py"
        mine = {"type": "command", "command": "mine.sh"}
        s = {"hooks": {"PostToolUse": [{"matcher": "Agent|Workflow", "hooks": [{"type": "command", "command": sub}, mine]},
                                       {"matcher": "*", "hooks": [{"type": "command", "command": sub}]}],
                       "Stop": [{"hooks": [{"type": "command", "command": sub}]}]},
             "statusLine": {"type": "command", "command": "python3 $HOME/.claude/statusline/harness-status.py"}}
        e = Env(self, s, [mig("0006-a", {"op": "hook-remove", "event": "PostToolUse", "command": sub},
                              {"op": "hook-remove", "event": "Stop", "command": sub},
                              {"op": "set", "path": ["enabledPlugins", "p@claude-doctor-market"], "value": True, "keep_existing": True})])
        e.run()
        out = e.get()
        self.assertEqual(out["hooks"], {"PostToolUse": [{"matcher": "Agent|Workflow", "hooks": [mine]}]})  # 같은 command 는 모든 그룹에서 빠지고 남의 훅, 빈 그룹 정리
        self.assertEqual(out["statusLine"], s["statusLine"])
        self.assertTrue(out["enabledPlugins"]["p@claude-doctor-market"])

    def test_unmanaged_top_keys_kept(self):
        auto = {"environment": ["x"]}
        e = Env(self, {"autoMode": auto, "theme": "dark"}, [mig("0001-a", {"op": "set", "path": "cleanupPeriodDays", "value": 5})])
        e.run()
        s = e.get(); self.assertEqual(s["autoMode"], auto); self.assertEqual(s["theme"], "dark"); self.assertEqual(s["cleanupPeriodDays"], 5)

    def test_keep_existing_and_delete(self):
        e = Env(self, {"a": 1, "b": 2}, [mig("0001-a", {"op": "set", "path": "a", "value": 9, "keep_existing": True}, {"op": "delete", "path": "b"})])
        e.run()
        self.assertEqual(e.get(), {"a": 1})

    def test_delete_if_value_only_when_equal(self):
        op = {"op": "delete", "path": ["enabledPlugins", "p@m"], "if_value": True}
        e = Env(self, {"enabledPlugins": {"p@m": True, "q@m": True}}, [mig("0001-a", op)])
        e.run()
        self.assertEqual(e.get(), {"enabledPlugins": {"q@m": True}})
        e = Env(self, {"enabledPlugins": {"p@m": False}}, [mig("0001-a", op)])
        e.run()
        self.assertEqual(e.get(), {"enabledPlugins": {"p@m": False}})  # 사용자가 끈 값은 둔다
        e = Env(self, {}, [mig("0001-a", op)])
        self.assertEqual(e.run(), 0)

    def test_idempotent_and_records(self):
        ms = [mig("0001-a", enable("m@claude-doctor-market"), {"op": "hook-upsert", "event": "Stop", "command": HOOK})]
        e = Env(self, {}, ms)
        e.run(); first = open(e.s).read()
        self.assertEqual(e.recs(), ["0001-a"])
        e.run(); self.assertEqual(open(e.s).read(), first); self.assertEqual(e.recs(), ["0001-a"])
        # 기록을 지워 다시 적용해도 결과 같음(연산 멱등)
        os.remove(e.r); e.run(); self.assertEqual(open(e.s).read(), first)
        self.assertEqual([f for f in os.listdir(e.d) if ".bak-" in f].__len__() <= 2, True)

    def test_first_apply_no_records_file_and_no_settings(self):
        e = Env(self, None, [mig("0001-a", {"op": "set", "path": "x", "value": 1})])
        self.assertFalse(os.path.exists(e.r))
        self.assertEqual(e.run(), 0); self.assertEqual(e.get(), {"x": 1})

    def test_failure_rolls_back_that_migration_only(self):
        e = Env(self, {"a": "str"}, [mig("0001-ok", {"op": "set", "path": "b", "value": 1}),
                                      mig("0002-bad", {"op": "set", "path": "c", "value": 1}, {"op": "set", "path": "a.deep", "value": 1}),
                                      mig("0003-later", {"op": "set", "path": "d", "value": 1})])
        self.assertEqual(e.run(), 1)
        self.assertEqual(e.get(), {"a": "str", "b": 1})  # 0002 의 앞 연산 c 도 되돌림, 0003 은 시도 안 함
        self.assertEqual(e.recs(), ["0001-ok"])

    def test_unknown_op_fails(self):
        e = Env(self, {}, [mig("0001-a", {"op": "bogus"})])
        self.assertEqual(e.run(), 1); self.assertEqual(e.recs(), [])

    def test_broken_json_aborts(self):
        e = Env(self, "{not json", [mig("0001-a", {"op": "set", "path": "x", "value": 1})])
        with self.assertRaises(SystemExit) as c:
            e.run()
        self.assertEqual(c.exception.code, 2)
        self.assertEqual(open(e.s).read(), "{not json")

    def test_dry_run_writes_nothing(self):
        e = Env(self, {}, [mig("0001-a", {"op": "set", "path": "x", "value": 1})])
        out = os.path.join(e.d, "out.json")
        e.run("--dry-run", "--out", out)
        self.assertEqual(e.get(), {}); self.assertEqual(e.recs(), []); self.assertEqual(json.load(open(out)), {"x": 1})

    def test_doctor_root_expanded(self):
        src = {"source": "directory", "path": "${HARNESS_DOCTOR_ROOT}"}
        m = mig("0001-a", {"op": "set", "path": ["extraKnownMarketplaces", "m"], "value": {"source": src}},
                {"op": "set", "path": "cmd", "value": "python3 ${HOME}/x ${OTHER}"})
        e = Env(self, {}, [m])
        e.run()
        root = os.path.dirname(os.path.dirname(os.path.abspath(MOD))).replace(os.sep, "/")
        self.assertEqual(e.get()["extraKnownMarketplaces"]["m"]["source"]["path"], root)
        self.assertEqual(e.get()["cmd"], "python3 ${HOME}/x ${OTHER}")  # 모르는 변수는 그대로
        # 환경 변수의 옛 HARNESS_DOCTOR_ROOT 는 쓰지 않는다: 적용하는 클론이 곧 정본이다
        e3 = Env(self, {}, [m])
        with unittest.mock.patch.dict(os.environ, {"HARNESS_DOCTOR_ROOT": "/elsewhere"}):
            e3.run()
        self.assertEqual(e3.get()["extraKnownMarketplaces"]["m"]["source"]["path"], root)
        e2 = Env(self, {}, [m])
        e2.run("--var", "HARNESS_DOCTOR_ROOT=C:/Users/u/Projects/claude-doctor")
        self.assertEqual(e2.get()["extraKnownMarketplaces"]["m"]["source"]["path"], "C:/Users/u/Projects/claude-doctor")
        with self.assertRaises(SystemExit):
            Env(self, {}, [m]).run("--var", "HOME=/x")

    def test_repo_migrations_carry_no_machine_path(self):
        d = os.path.join(HERE, "..", "..", "home", "settings-migrations")
        for f in sorted(os.listdir(d)):
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("/code/", text, f)

    def test_backup_made(self):
        e = Env(self, {"k": 1}, [mig("0001-a", {"op": "set", "path": "x", "value": 1})])
        e.run()
        self.assertTrue(any(".bak-" in f for f in os.listdir(e.d)))


if __name__ == "__main__":
    import unittest.mock
    unittest.main(verbosity=1)
