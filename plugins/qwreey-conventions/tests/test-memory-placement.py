#!/usr/bin/env python3
"""memory-placement 훅과 hooks/memory_signals.py 회귀. 실행: python3 -I test-memory-placement.py  (exit 0 = 통과)

임시 HOME(CLAUDE_CONFIG_DIR) 아래에 프로젝트 키 메모리 디렉터리를 만들고 훅에 PostToolUse JSON 을 넣는다. 상태는 TMPDIR 로 격리한다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "memory-placement.py")
T = tempfile.mkdtemp(prefix="mem-place-")
# nonce 는 고정 salt 로(실제 ~/.local/share 의 salt 를 쓰지 않게)
open(os.path.join(T, "salt"), "w").write("00" * 32)
os.environ["QWREEY_HARNESS_SALT_FILE"] = os.path.join(T, "salt")
CFG = os.path.join(T, "cfg")
MEM = os.path.join(CFG, "projects", "-tmp-demo", "memory")
os.makedirs(MEM)
res = []


def check(name, ok):
    res.append((name, bool(ok)))


def write(name, text):
    p = os.path.join(MEM, name)
    open(p, "w").write(text)
    return p


def call(path, sid="s1", agent=None, tool="Write", cwd=T, env_extra=None):
    d = {"session_id": sid, "cwd": cwd, "hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": path}}
    if agent:
        d["agent_id"] = agent
    env = dict(os.environ, TMPDIR=T, CLAUDE_CONFIG_DIR=CFG)
    env.pop("MEMORY_PLACEMENT", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(d), capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return ""
    ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert re.match(r'<harness-hook name="memory-placement" level="warn" nonce="[0-9a-f]{12}">\n', ctx) and ctx.endswith("\n</harness-hook>"), ctx
    return ctx


REPO_NOTE = """---
name: build
description: build info
metadata:
  type: project
---
In this repo, build with `make all` and tests run via `pytest tests/`. The parser lives in src/parser.py.
"""
USER_NOTE = """---
name: role
description: who the user is
type: user
---
The user is a senior engineer; in this repo they prefer terse answers. See src/main.py and `make all`.
"""
ENV_NOTE = """---
name: sandbox
description: sandbox facts
metadata:
  type: feedback
---
On this machine (the sandbox) the shim fails; call mise installs directly. Also uses tools/run.sh.
"""
FEEDBACK_PLAIN = """---
name: terse
description: tone
type: feedback
---
The user wants short answers without trailing summaries.
"""

p = write("build.md", REPO_NOTE)
c = call(p)
check("repo knowledge warns", "looks like repo knowledge" in c and "make all" in c)
check("level warn + moves hint", "CLAUDE.md" in c and "coderag" in c)
check("dedup same session/file", call(p) == "")
check("different agent_id warns again", "build.md" in call(p, agent="a1"))
check("different session warns again", "build.md" in call(p, sid="s2"))
check("type user is quiet", call(write("role.md", USER_NOTE)) == "")
check("environment note is quiet", call(write("sandbox.md", ENV_NOTE)) == "")
check("plain feedback is quiet", call(write("terse.md", FEEDBACK_PLAIN)) == "")
check("MEMORY.md never warns", call(write("MEMORY.md", "- [build](build.md) - `make all` in this repo, src/parser.py\n")) == "")
outside = os.path.join(T, "repo", "docs", "build.md")
os.makedirs(os.path.dirname(outside))
open(outside, "w").write(REPO_NOTE)
check("non-memory path ignored", call(outside) == "")
check("env switch off", call(p, sid="s3", env_extra={"MEMORY_PLACEMENT": "off"}) == "")
check("bad stdin is silent", subprocess.run([sys.executable, "-I", HOOK], input="not json", capture_output=True, text=True).returncode == 0)

# autoMemoryDirectory (absolute, project settings) counts as memory
custom = os.path.join(T, "custom-mem")
os.makedirs(os.path.join(T, "proj", ".claude"))
os.makedirs(custom)
open(os.path.join(T, "proj", ".claude", "settings.json"), "w").write(json.dumps({"autoMemoryDirectory": custom}))
cp = os.path.join(custom, "x.md")
open(cp, "w").write(REPO_NOTE)
check("autoMemoryDirectory honored", "x.md" in call(cp, sid="s4", cwd=os.path.join(T, "proj")))
check("relative autoMemoryDirectory not treated as memory", call(os.path.join(T, "proj", ".claude", "memory", "y.md"), sid="s5", cwd=os.path.join(T, "proj")) == "")

# lib: key rule and resolve_key
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import memory_signals as ms  # noqa: E402
check("key_of dot underscore", ms.key_of("/tmp/memexpA.dot_1") == "-tmp-memexpA-dot-1")
check("key_of hidden dir", ms.key_of("/code/.claude") == "-code--claude")
d = os.path.join(T, "a.b_c", "Repo-x")
os.makedirs(d)
check("resolve_key finds lossy path", str(ms.resolve_key(ms.key_of(d))) == d)
check("resolve_key none for missing", ms.resolve_key(ms.key_of(d) + "-gone") is None)

bad = [n for n, ok in res if not ok]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
print(f"{len(res) - len(bad)}/{len(res)}")
sys.exit(1 if bad else 0)
