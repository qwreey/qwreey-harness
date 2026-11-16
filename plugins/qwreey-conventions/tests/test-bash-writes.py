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


def hook(script, event, cmd, sid, tid, env=None, cwd=REPO, agent=None):
    d = {"session_id": sid, "cwd": cwd, "hook_event_name": event, "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": tid}
    if agent:
        d["agent_id"] = agent
    p = subprocess.run([sys.executable, "-I", script], input=json.dumps(d), capture_output=True, text=True, env=env_for(env, proj=cwd), timeout=20)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else ""


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
    p = subprocess.run([sys.executable, "-I", CHECK], input=json.dumps(d), capture_output=True, text=True, env=env_for(), timeout=10)
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else ""


def notice(ctx):
    m = re.search(r'<harness-hook name="qwreey-conventions" level="info" nonce="[0-9a-f]{12}">([^\n]*)</harness-hook>', ctx)
    return m.group(1) if m else ""


def snaps():
    d = os.path.join(T, "claude-conventions", "bash")
    return os.listdir(d) if os.path.isdir(d) else []


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
