#!/usr/bin/env python3
"""Bash 쓰기 검사(bash-bypass-reminder 의 PreToolUse 스냅숏 + bash_writes.py 의 PostToolUse) 회귀. 실행: python3 -I test-bash-writes.py (exit 0 = 통과)

임시 git 저장소에서 Pre 훅, 실제 명령(bash), Post 훅을 차례로 돌린다. 상태는 TMPDIR 로 격리한다.
BIG_REPO=<git 저장소 사본> 을 주면 그 저장소에서도 시간을 잰다. 파일 하나를 잠깐 만들었다 지우므로 버려도 되는 사본을 준다.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRE = os.path.join(ROOT, "hooks", "bash-bypass-reminder.py")
POST = os.path.join(ROOT, "hooks", "bash_writes.py")
CHECK = os.path.join(ROOT, "hooks", "conventions-check.py")
# HOOK_TEST_BIN=<바이너리> 면 세 훅을 python 스크립트 대신 `<바이너리> hook <이름>` 으로 돌린다(Rust 판, crates/qwreey-conventions).
# 바이너리는 이 플러그인의 native/ 에 있어야 한다(그 위의 rules/ 를 읽는다). HOOK_TEST_BIN_ONLY=<이름> 이면 그 훅만 바이너리로 돌려
# 한쪽의 Pre 와 다른 쪽의 Post 가 같은 스냅숏을 주고받는지 본다(예: bash-bypass-reminder 만 Rust, bash-writes 는 python).
BIN = os.environ.get("HOOK_TEST_BIN")
BIN_NAMES = {PRE: "bash-bypass-reminder", POST: "bash-writes", CHECK: "conventions-check"}
BIN_ONLY = os.environ.get("HOOK_TEST_BIN_ONLY")


def argv(script):
    name = BIN_NAMES.get(script)
    if BIN and name and BIN_ONLY in (None, "", name):
        return [BIN, "hook", name]
    return [sys.executable, "-I", script]
T = tempfile.mkdtemp(prefix="bashw-")
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
CFG = os.path.join(T, "cfg")
os.makedirs(CFG)
REPO = os.path.join(T, "repo")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
_n = [0]


def env_for(extra=None, proj=REPO):
    e = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG, CLAUDE_PROJECT_DIR=proj, HARNESS_READABLE_CODE="off", **GIT_ENV)
    for k in ("CONVENTIONS_CHECK", "HARNESS_CONVENTIONS_RULES", "REUSE_CHECK", "CLAUDE_PLUGIN_DATA"):
        e.pop(k, None)
    e.update(extra or {})
    return e


def sh(cmd, cwd=REPO):
    subprocess.run(["bash", "-c", cmd], cwd=cwd, check=True, capture_output=True, env=env_for())


def put(rel, text, repo=REPO):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def init_repo(path):
    os.makedirs(os.path.join(path, ".claude"), exist_ok=True)
    sh("git init -q . && git add -A && git commit -qm init --allow-empty", cwd=path)


def hook_raw(script, event, cmd, sid, tid, env=None, cwd=REPO, agent=None, extra=None):
    d = {"session_id": sid, "cwd": cwd, "hook_event_name": event, "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": tid}
    if agent:
        d["agent_id"] = agent
    d.update(extra or {})
    p = subprocess.run(argv(script), input=json.dumps(d), capture_output=True, text=True, env=env_for(env, proj=cwd), timeout=20)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else {}


def hook(script, event, cmd, sid, tid, env=None, cwd=REPO, agent=None, extra=None):
    return hook_raw(script, event, cmd, sid, tid, env, cwd, agent, extra).get("hookSpecificOutput", {}).get("additionalContext", "")


def bash(cmd, sid=None, env=None, cwd=REPO, agent=None):
    """Pre 훅, 명령, Post 훅을 돌리고 Post 의 additionalContext 를 돌려준다."""
    _n[0] += 1
    sid = sid or "s%d" % _n[0]
    tid = "toolu_%d" % _n[0]
    hook(PRE, "PreToolUse", cmd, sid, tid, env, cwd, agent)
    subprocess.run(["bash", "-c", cmd], cwd=cwd, capture_output=True, env=env_for(env, proj=cwd))
    return hook(POST, "PostToolUse", cmd, sid, tid, env, cwd, agent)


def edit(rel, old, new, sid):
    path = os.path.join(REPO, rel)
    text = open(path, encoding="utf-8").read().replace(old, new, 1)
    put(rel, text)
    d = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": "Edit",
         "tool_input": {"file_path": path, "old_string": old, "new_string": new}, "tool_response": {}}
    p = subprocess.run(argv(CHECK), input=json.dumps(d), capture_output=True, text=True, env=env_for(), timeout=10)
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else ""


def notice(ctx):
    m = re.search(r'<harness-hook name="qwreey-conventions" level="info" nonce="[0-9a-f]{12}">([^\n]*)</harness-hook>', ctx)
    return m.group(1) if m else ""


SNAP_DIR = os.path.join(T, "claude-conventions", "bash")


def snaps():
    return os.listdir(SNAP_DIR) if os.path.isdir(SNAP_DIR) else []


sys.path.insert(0, os.path.join(ROOT, "hooks"))
import bash_writes  # noqa: E402  (in-process checks of the helpers)


def commit(msg="c", repo=REPO):
    sh("git add -A && git commit -qm %s" % msg, cwd=repo)


MID = "·"
put("src/a.py", "def f():\n    # Keep the order stable for callers.\n    return 1\n")
put("src/old.py", "# old " + MID + " symbol stays\nx = 1\ny = 2\n")
put("src/b.luau", "local M = {}\nreturn M\n")
put("lib/canon.luau", '-- source\nlocal FORMS = { "coin", "stick", "back", "card" }\nreturn FORMS\n')
init_repo(REPO)


class Detects(unittest.TestCase):
    def test_heredoc_comment_with_middle_dot(self):
        c = bash("cat > src/new.py <<'EOF'\nx = 1\n# first " + MID + " second\nEOF")
        n = notice(c)
        self.assertIn("src/new.py may not follow the comment conventions", n)
        self.assertIn("L2 non-keyboard symbol: " + MID, n)
        self.assertIn('(use ",")', n)
        self.assertNotIn("skill", n)

    def test_sed_in_place_history_marker(self):
        c = bash("sed -i 's/# Keep the order stable for callers./# Keep the order stable (round 3, H-973)./' src/a.py")
        self.assertIn("src/a.py may not follow the comment conventions. L2 history marker", notice(c))
        sh("git checkout -q -- src/a.py")

    def test_interpreter_with_computed_path(self):
        # The path is built at run time, so only the git snapshot can find it.
        c = bash("python3 - <<'EOF'\nimport pathlib\np = pathlib.Path('src') / ('b' + '.luau')\np.write_text(p.read_text() + '-- used ' + chr(0x2192) + ' later\\n')\nEOF")
        self.assertIn("src/b.luau may not follow the comment conventions. L3 non-keyboard symbol", notice(c))
        sh("git checkout -q -- src/b.luau")

    def test_dirty_file_only_new_lines(self):
        sh("printf 'z = 3\\n' >> src/old.py")  # dirty before the command, with an old symbol on line 1
        c = bash("echo '# new " + "…" + " line' >> src/old.py")
        n = notice(c)
        self.assertIn("L5 non-keyboard symbol", n)
        self.assertNotIn("L1 ", n)
        sh("git checkout -q -- src/old.py")

    def test_command_that_commits(self):
        c = bash("sed -i 's/^x = 1$/x = 1  # moved in round 4/' src/old.py && git commit -qam wip")
        self.assertIn("L2 history marker", notice(c))
        sh("git reset -q --hard HEAD~1")

    def test_doc_file(self):
        c = bash("cat > CLAUDE.md <<'EOF'\n# Repo\n- Decided 2026-11-16 in audit/62.\nEOF")
        self.assertIn("CLAUDE.md may not follow the agent-doc conventions", notice(c))
        os.remove(os.path.join(REPO, "CLAUDE.md"))

    def test_layout_when_on(self):
        body = "".join("    v%d = %d\n" % (i, i) for i in range(18))
        c = bash("cat > src/long.py <<'EOF'\ndef build():\n" + body + "    return v0\nEOF", env={"HARNESS_READABLE_CODE": "on"})
        self.assertIn("src/long.py layout (readable-code)", notice(c))
        self.assertEqual(notice(bash("cat > src/long2.py <<'EOF'\ndef build():\n" + body + "    return v0\nEOF")), "")

    def test_copy_marker_through_reuse_check(self):
        c = bash("cat > src/copy.luau <<'EOF'\n-- @copy-of: lib/canon.luau#FORMS\nlocal FORMS = { \"coin\", \"stick\", \"back\", \"dice\" }\nEOF")
        self.assertIn("differs: missing", notice(c))


class Silent(unittest.TestCase):
    def test_read_only_commands(self):
        before = set(snaps())
        for cmd in ("cat src/a.py", "grep -n Keep src/a.py", "git diff > /tmp/bashw-x.diff", "ls src | head"):
            self.assertEqual(bash(cmd), "", cmd)
        self.assertEqual(set(snaps()), before)

    def test_rewrite_without_new_comment_lines(self):
        # Rewrites src/old.py (old symbol on line 1 kept, code lines swapped): nothing it added is a comment problem.
        c = bash("python3 - <<'EOF'\np = 'src/old.py'\nt = open(p).read().replace('x = 1\\ny = 2', 'y = 2\\nx = 1')\nopen(p, 'w').write(t)\nEOF")
        self.assertEqual(notice(c), "")
        sh("git checkout -q -- src/old.py")

    def test_skip_dirs_and_outside(self):
        for rel in ("node_modules/m/x.js", "vendor/v.py", "build/b.py"):
            self.assertEqual(notice(bash("mkdir -p %s && echo '// a %s b' > %s" % (os.path.dirname(rel), MID, rel))), "", rel)
        out = os.path.join(T, "outside.py")
        self.assertEqual(bash("echo '# a %s b' > %s" % (MID, out)), "")

    def test_worktree_rewrite_in_same_command(self):
        # git stash restores old text; with it in the command only named paths are compared.
        sh("printf '# stashed %s line\\n' >> src/a.py" % MID)
        c = bash("git stash -q && git stash pop -q")
        self.assertEqual(notice(c), "")
        sh("git checkout -q -- src/a.py")

    def test_off_switch(self):
        self.assertEqual(bash("echo '# a %s b' > src/off.py" % MID, env={"CONVENTIONS_CHECK": "off", "HARNESS_CONVENTIONS_RULES": "off"}), "")
        os.remove(os.path.join(REPO, "src", "off.py"))


class Dedup(unittest.TestCase):
    def test_later_edit_same_category(self):
        sid = "dd1"
        self.assertIn("non-keyboard symbol", notice(bash("echo '# one %s two' > src/d.py" % MID, sid=sid)))
        self.assertEqual(edit("src/d.py", "# one", "# three %s four\n# one" % MID, sid), "")
        self.assertIn("non-keyboard symbol", edit("src/d.py", "# three", "# five %s six\n# three" % MID, "dd2"))

    def test_second_bash_same_category(self):
        sid = "dd3"
        self.assertTrue(notice(bash("echo '# a %s b' > src/e.py" % MID, sid=sid)))
        self.assertEqual(notice(bash("echo '# c %s d' >> src/e.py" % MID, sid=sid)), "")
        self.assertTrue(notice(bash("echo '# c %s d' >> src/e.py" % MID, sid=sid, agent="ag1")))


class Rules(unittest.TestCase):
    def test_rules_once_per_context(self):
        sid = "rr1"
        c = bash("echo 'x = 1' > src/r.py", sid=sid)
        self.assertIn('<rule plugin="qwreey-conventions" name="comments">', c)
        self.assertIn("you wrote r.py", c)
        self.assertNotIn('name="comments"', bash("echo 'x = 2' > src/r2.py", sid=sid))
        self.assertIn('name="agent-docs"', bash("printf '# T\\n' > CLAUDE.md", sid=sid))
        os.remove(os.path.join(REPO, "CLAUDE.md"))

    def test_rules_off(self):
        c = bash("echo 'x = 1' > src/r3.py", env={"HARNESS_CONVENTIONS_RULES": "off"})
        self.assertNotIn("<rule ", c)

    def test_output_stays_under_budget(self):
        files = " ".join("src/m%d.py" % i for i in range(30))
        c = bash("for f in %s; do echo '# a %s b (round 2) \\u00b7' > $f; done; printf '# T\\n' > CLAUDE.md" % (files, MID))
        self.assertLessEqual(len(c), 9000)
        self.assertIn("conventions-scan.py scan", c)
        sh("rm -f src/m*.py CLAUDE.md")


class Overflow(unittest.TestCase):
    """More dirty entries than the snapshot records: unrecorded ones are never treated as changed."""

    def test_unrecorded_entries_are_not_changes(self):
        repo = os.path.join(T, "ov")
        put("b.py", "x = 1\n", repo)
        init_repo(repo)
        for i in range(450):
            put("scratch/s%d.py" % i, "# 2023-05-05 legacy (D-%d)\nv = %d\n" % (i, i), repo)
        c = bash("echo 'w = 1' >> b.py", cwd=repo)
        self.assertNotIn("scratch/", c)
        n = notice(bash("echo '# a %s b' >> b.py" % MID, cwd=repo))
        self.assertIn("b.py may not follow", n)
        self.assertNotIn("scratch/", n)

    def test_reads_are_capped_by_bytes_and_time(self):
        repo = os.path.join(T, "cap")
        put("a.py", "x = 1\n", repo)
        init_repo(repo)
        root, head = bash_writes.repo(repo)
        snap = {"root": root, "head": head, "wide": True, "dirty": {}, "texts": {}, "named": [], "overflow": False}
        for i in range(120):
            put("gen/g%d.py" % i, ("# line %d\n" % i) * 6000, repo)  # about 60 KB each, 7 MB in all
        got = []
        real = bash_writes._read

        def counting(path, cap):
            t = real(path, cap)
            got.append(len(t) if isinstance(t, str) else 0)
            return t
        bash_writes._read = counting
        try:
            bash_writes.changes(snap, deadline=time.monotonic() + 60)
            self.assertLessEqual(sum(got), bash_writes.TOTAL_MAX + bash_writes.CANDIDATE_MAX)
            got.clear()
            items, touched, unread = bash_writes.changes(snap, deadline=time.monotonic() - 1)
            self.assertEqual(sum(got), 0)
            self.assertEqual(items, [])
            self.assertEqual(len(unread), 120)  # handed to the "N more files" scan line, not dropped
        finally:
            bash_writes._read = real


class Failure(unittest.TestCase):
    def test_failed_command_is_checked(self):
        _n[0] += 1
        sid, tid = "pf%d" % _n[0], "toolu_pf%d" % _n[0]
        cmd = "cat > src/fail.py <<'EOF'\n# a %s b\nEOF\nfalse" % MID
        hook(PRE, "PreToolUse", cmd, sid, tid)
        subprocess.run(["bash", "-c", cmd], cwd=REPO, capture_output=True, env=env_for())
        out = hook_raw(POST, "PostToolUseFailure", cmd, sid, tid, extra={"error": "Exit code 1", "is_interrupt": False})
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUseFailure")
        self.assertIn("src/fail.py may not follow", out["hookSpecificOutput"]["additionalContext"])
        self.assertFalse([x for x in snaps() if tid in x])
        os.remove(os.path.join(REPO, "src", "fail.py"))

    def test_registered_on_failure(self):
        hooks = json.load(open(os.path.join(ROOT, "hooks", "hooks.json")))["hooks"]
        # python 판(bash_writes.py) 이나 Rust 판(native/qwreey-conventions hook bash-writes) 어느 쪽이든 된다
        regs = [" ".join([h["command"], *h.get("args", [])])
                for m in hooks.get("PostToolUseFailure", []) if m.get("matcher") == "Bash" for h in m["hooks"]]
        self.assertTrue(any("bash_writes.py" in c or c.endswith("hook bash-writes") for c in regs), regs)


class SnapshotFile(unittest.TestCase):
    def pre(self, cmd, cwd=REPO, sid="sf"):
        _n[0] += 1
        tid = "toolu_sf%d" % _n[0]
        hook(PRE, "PreToolUse", cmd, sid, tid, cwd=cwd)
        name = [x for x in snaps() if tid in x]
        return os.path.join(SNAP_DIR, name[0]) if name else None

    def test_named_files_bounded_and_private(self):
        repo = os.path.join(T, "bigf")
        for i in range(6):
            put("f%d.py" % i, "x = 1\n" * 150000, repo)  # 900 KB each
        init_repo(repo)
        fp = self.pre("sed -i 's/^x/y/' " + " ".join("f%d.py" % i for i in range(6)), cwd=repo)
        snap = json.load(open(fp))
        self.assertLessEqual(sum(len(t) for t in snap["texts"].values() if isinstance(t, str)), bash_writes.TOTAL_MAX)
        self.assertEqual(os.stat(fp).st_mode & 0o777, 0o600)
        os.remove(fp)

    def test_per_user_dir_without_tmpdir(self):
        e = env_for()
        e.pop("TMPDIR")
        code = "import sys; sys.path.insert(0, %r); import bash_writes; print(bash_writes.snap_dir())" % os.path.join(ROOT, "hooks")
        out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, env=e).stdout.strip()
        self.assertTrue(out.endswith(os.path.join("claude-conventions-%d" % os.getuid(), "bash")), out)

    def test_stale_snapshots_swept_on_pre(self):
        os.makedirs(SNAP_DIR, exist_ok=True)
        old, new = os.path.join(SNAP_DIR, "x.main.old.json"), os.path.join(SNAP_DIR, "x.main.new.json")
        for p in (old, new):
            open(p, "w").write("{}")
        os.utime(old, (time.time() - 7200, time.time() - 7200))
        os.utime(new, (time.time() - 1800, time.time() - 1800))
        hook(PRE, "PreToolUse", "cat src/a.py", "sw", "toolu_sw")
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))
        os.remove(new)

    def test_fifo_named_in_command(self):
        fifo = os.path.join(REPO, "src", "pipe.py")
        os.mkfifo(fifo)
        try:
            self.pre("sed -i 's/a/b/' src/pipe.py")  # hook() times out if the snapshot opens the FIFO
        finally:
            os.remove(fifo)

    def test_non_utf8_file_name_is_left_out(self):
        """UTF-8 이 아닌 이름의 파일은 스냅숏에서 빠지고, 스냅숏은 온전하며 다른 파일은 그대로 검사한다."""
        repo = os.path.join(T, "badname")
        put("src/a.py", "def f():\n    return 1\n", repo)
        init_repo(repo)
        with open(os.path.join(os.fsencode(repo), b"src", b"bad\xff.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        cmd = "sed -i 's/return 1/# one " + MID + " two\\n    return 1/' src/a.py"

        # The snapshot is valid UTF-8 JSON without the odd name
        fp = self.pre(cmd, cwd=repo, sid="nu1")
        with open(fp, encoding="utf-8") as f:
            snap = json.load(f)
        self.assertEqual(list(snap["dirty"]), [])
        os.remove(fp)

        # A full run still checks the file the command changed and leaves no snapshot
        c = bash(cmd, sid="nu2", cwd=repo)
        self.assertIn("src/a.py may not follow the comment conventions", notice(c))
        self.assertEqual([x for x in snaps() if x.startswith("nu2.")], [])

    def test_unreadable_snapshot_is_removed(self):
        """Post 는 읽지 못하는 스냅숏(쓰다 멈춘 것)도 지운다: 남으면 같은 세션의 다음 Bash 가 대기 중인 명령으로 본다."""
        os.makedirs(SNAP_DIR, exist_ok=True)
        for i, junk in enumerate((b'{"root": "/r", "dirty": {"a', b"\xff\xfe", b"[1, 2]")):
            fp = os.path.join(SNAP_DIR, "ur.main.toolu_ur%d.json" % i)
            with open(fp, "wb") as f:
                f.write(junk)
            self.assertEqual(hook(POST, "PostToolUse", "sed -i s/a/b/ x.py", "ur", "toolu_ur%d" % i), "")
            self.assertFalse(os.path.exists(fp), junk)


class GitAware(unittest.TestCase):
    def test_git_restore_of_named_path(self):
        put("src/g.py", "x = 1\n# 2023-05-05 legacy (D-12)\ny = 2\n")
        commit("g")
        sh("sed -i 2d src/g.py")
        c = bash("cd . && git checkout -- src/g.py && echo hi > notes.md")
        self.assertNotIn("src/g.py", notice(c))
        os.remove(os.path.join(REPO, "notes.md"))

    def test_git_rewrite_forms(self):
        for cmd in ("git -c core.x=y checkout -- a.py", "git --no-pager stash pop", "git -C sub reset --hard", "gh pr checkout 12",
                    "git -c a=b -C d restore x.py"):
            self.assertTrue(bash_writes.GIT_REWRITE.search(cmd), cmd)
        for cmd in ("git status", "git diff --stat", "echo checkout"):
            self.assertFalse(bash_writes.GIT_REWRITE.search(cmd), cmd)

    def test_moved_file_keeps_old_lines(self):
        put("src/mv1.py", "# 2023-05-05 legacy (D-12)\nx = 1\n")
        commit("mv")
        c = bash("mv src/mv1.py src/mv2.py && sed -i 's/x = 1/x = 2/' src/mv2.py")
        self.assertNotIn("history marker", notice(c))
        sh("rm -f src/mv2.py && git checkout -q -- src/mv1.py")

    def test_copied_file_only_new_lines(self):
        put("src/cp0.py", "# 2023-05-05 legacy (D-12)\nx = 1\n")
        commit("cp")
        n = notice(bash("cp src/cp0.py src/cp1.py; echo '# new %s line' >> src/cp1.py" % MID))
        self.assertIn("L3 non-keyboard symbol", n)
        self.assertNotIn("history marker", n)
        os.remove(os.path.join(REPO, "src", "cp1.py"))

    def test_blobs_skip_newline_paths(self):
        root, head = bash_writes.repo(REPO)
        got = bash_writes.blobs(root, head, ["x\ny.py", "src/a.py"])
        self.assertEqual(got["src/a.py"], open(os.path.join(REPO, "src", "a.py")).read())


class Concurrent(unittest.TestCase):
    def test_pending_snapshot_limits_to_named_paths(self):
        # Another Bash of this session is in flight: a file this command does not name is not attributed to it.
        os.makedirs(SNAP_DIR, exist_ok=True)
        other = os.path.join(SNAP_DIR, "cc1.main.toolu_other.json")
        open(other, "w").write("{}")
        try:
            c = bash("python3 - <<'EOF'\nimport pathlib\np = pathlib.Path('src') / ('cc' + '.luau')\np.write_text('-- used ' + chr(0x2192) + ' later\\n')\nEOF", sid="cc1")
            self.assertNotIn("src/cc.luau", notice(c))
        finally:
            os.remove(other)
            os.remove(os.path.join(REPO, "src", "cc.luau"))

    def test_parallel_posts_notice_once(self):
        for r in range(3):
            sid = "par%d" % r
            cmds = ["echo '# p%d %s q' >> src/par%d.py" % (k, MID, r) for k in range(2)]
            tids = ["toolu_par%d_%d" % (r, k) for k in range(2)]
            for cmd, tid in zip(cmds, tids):
                hook(PRE, "PreToolUse", cmd, sid, tid)
            for cmd in cmds:
                sh(cmd)
            procs = []
            for cmd, tid in zip(cmds, tids):
                d = {"session_id": sid, "cwd": REPO, "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": tid}
                p = subprocess.Popen(argv(POST), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env_for())
                p.stdin.write(json.dumps(d))
                p.stdin.close()
                procs.append(p)
            outs = [p.stdout.read() for p in procs]
            for p in procs:
                p.wait()
            self.assertEqual(sum("non-keyboard symbol" in o for o in outs), 1, outs)
            os.remove(os.path.join(REPO, "src", "par%d.py" % r))


class Budget(unittest.TestCase):
    def test_whole_output_under_budget(self):
        body = "".join("    v%d = %d  # step %d %s note (round %d) \\u00b7\n" % (i, i, i, MID, i) for i in range(30))
        files = []
        for i in range(12):
            files.append("src/bud%d.py" % i)
            put("gen_bud/bud%d.txt" % i, "def build_%d():\n%s    return v0\n\n\ndef other_%d():\n%s    return v1\n" % (i, body, i, body))
        c = bash("for i in $(seq 0 11); do cat gen_bud/bud$i.txt > src/bud$i.py; done", env={"HARNESS_READABLE_CODE": "on"})
        self.assertLessEqual(len(c), 9000)
        self.assertRegex(c, r"\d+ more files: run `python3 -I \S+conventions-scan.py scan [^`]*src/bud")
        sh("rm -rf gen_bud src/bud*.py")


def timed(fn, n=7):
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000)
    return statistics.median(xs)


class Timing(unittest.TestCase):
    def test_timing(self):
        repo = REPO
        big = os.environ.get("BIG_REPO")
        if big:
            repo = big
        _n[0] += 1
        noop = timed(lambda: hook(POST, "PostToolUse", "ls", "tm", "toolu_noop", cwd=repo))
        pre_ro = timed(lambda: hook(PRE, "PreToolUse", "cat README.md", "tm", "toolu_ro", cwd=repo))
        cmd = "echo '# timing line' >> tm_probe.py"
        pre_w, post_w = [], []
        for i in range(6):  # each round is a new session, so the rules are injected every time (the worst case)
            t = time.perf_counter()
            hook(PRE, "PreToolUse", cmd, "tm%d" % i, "toolu_w%d" % i, cwd=repo)
            pre_w.append((time.perf_counter() - t) * 1000)
            sh(cmd, cwd=repo)
            t = time.perf_counter()
            hook(POST, "PostToolUse", cmd, "tm%d" % i, "toolu_w%d" % i, cwd=repo)
            post_w.append((time.perf_counter() - t) * 1000)
        os.remove(os.path.join(repo, "tm_probe.py"))
        print("\ntiming (%s): Post no-op %.0f ms, Pre read-only %.0f ms, Pre write %.0f ms, Post write first %.0f ms, then median %.0f ms"
              % (big or "temp repo", noop, pre_ro, statistics.median(pre_w), post_w[0], statistics.median(post_w[1:])), file=sys.stderr)
        self.assertLess(noop, 300)


if __name__ == "__main__":
    unittest.main(verbosity=1)
