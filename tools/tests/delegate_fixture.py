"""tools/tests/test-delegate-*.py 공용 준비물: 버릴 저장소, registry, 가짜 인증이 든 HOME, 가짜 agy·codex·setpriv.
모델을 부르지 않고 다른 uid 로도 돌리지 않는다. 가짜 setpriv 는 옵션을 버리고 호출한 사용자 그대로 명령을 실행한다.
"""
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "qwreey-delegate" / "skills" / "delegate" / "scripts"
CANON_HE = ROOT / "home" / ".claude" / "lib" / "harness_env.py"
IS_ROOT = os.geteuid() == 0

FAKE_SETPRIV = """#!/bin/sh
echo "$@" >> "{ctl}/setpriv.log"
while [ $# -gt 0 ]; do case "$1" in --*) shift ;; *) break ;; esac; done
if [ -e "{ctl}/deny" ] && [ "$1" = sh ]; then exit 1; fi
exec "$@"
"""

FAKE_AGY = """#!{py}
import json, os, sys, time
from pathlib import Path
ctl = Path({ctl!r})
cwd = Path.cwd()
(ctl / f"agy-{{os.getpid()}}.json").write_text(json.dumps({{"argv": sys.argv, "cwd": str(cwd), "env": dict(os.environ),
    "cwd_uid": os.stat(cwd).st_uid}}))
(ctl / "started").write_text("1")
if (ctl / "block").exists():
    for _ in range(600):
        if (ctl / "release").exists():
            break
        time.sleep(0.05)
conv = Path(os.environ["HOME"]) / ".gemini" / "antigravity-cli" / "brain" / "conv-task"
(conv / "scratch").mkdir(parents=True, exist_ok=True)
(conv / "scratch" / "probe.txt").write_text("probe output\\n")
(conv / ".system_generated" / "logs").mkdir(parents=True, exist_ok=True)
(conv / ".system_generated" / "logs" / "transcript.jsonl").write_text("{{}}\\n")
if (cwd / ".git").exists():
    (cwd / "REPORT.md").write_text("agy worktree report\\n")
    with open(cwd / "tracked.txt", "a") as f:
        f.write("changed by agy\\n")
    (cwd / "new-file.txt").write_text("new\\n")
print("agy stdout answer")
"""

FAKE_CODEX = """#!{py}
import json, os, sys
from pathlib import Path
ctl = Path({ctl!r})
prompt = sys.stdin.read()
args = sys.argv
(ctl / f"codex-{{os.getpid()}}.json").write_text(json.dumps({{"argv": args, "cwd": os.getcwd(), "env": dict(os.environ),
    "stdin": prompt}}))
out = args[args.index("-o") + 1]
Path(out).write_text("codex answer\\n")
print("codex log line")
"""


def free_uid(start=62900):
    uid = start
    while True:
        try:
            pwd.getpwuid(uid)
            uid += 1
        except KeyError:
            return uid


def git(*args, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout


class Fixture:
    """모든 것을 임시 폴더 하나 아래에 둔다. env() 는 드라이버를 돌릴 환경이다."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="delegate-test-"))
        self.ctl = self.tmp / "ctl"
        self.bin = self.tmp / "bin"
        self.home = self.tmp / "home"
        self.cfg = self.tmp / "cfg"
        self.ws = self.tmp / "ws"
        self.repo = self.ws / "proj"
        self.registry = self.tmp / "registry.tsv"
        self.uid = free_uid()
        for p in (self.ctl, self.bin, self.cfg, self.repo):
            p.mkdir(parents=True)
        self._fakes()
        self._home()
        git("init", "-q", "-b", "main", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("base\n")
        (self.repo / "AGENTS.md").write_text("# map\n")
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "base", cwd=self.repo)
        self.registry.write_text(f"# test registry\nproj\t{self.repo}\t{self.uid}\t-\ttest\n")
        self.user_env(f"HARNESS_DELEGATE_REGISTRY={self.registry}\nHARNESS_DELEGATE_AGY_BIN={self.bin / 'agy'}\n"
                      f"HARNESS_DELEGATE_CODEX_BIN={self.bin / 'codex'}\nHARNESS_HEAVY_WRAP=\n")
        self.prompt = self.tmp / "prompt.md"
        self.prompt.write_text("TASK BODY: say hello\n")

    def _fakes(self):
        for name, text in (("setpriv", FAKE_SETPRIV), ("agy", FAKE_AGY), ("codex", FAKE_CODEX)):
            p = self.bin / name
            p.write_text(text.format(ctl=str(self.ctl), py=sys.executable))
            p.chmod(0o755)

    def _home(self):
        a = self.home / ".gemini" / "antigravity-cli"
        (a / "brain" / "users-other-conv").mkdir(parents=True)
        (a / "brain" / "users-other-conv" / "secret.txt").write_text("user's own history\n")
        (a / "conversations").mkdir()
        (a / "antigravity-oauth-token").write_text("token\n")
        (a / "settings.json").write_text("{}\n")
        (a / "conversation_summaries.db-wal").write_text("x")
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "auth.json").write_text('{"token": 1}\n')
        (self.home / ".ssh").mkdir()
        (self.home / ".git-credentials").write_text("https://u:p@example.invalid\n")
        (self.cfg / ".credentials.json").write_text("{}\n")

    def user_env(self, text):
        (self.cfg / "harness.env").write_text(text)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("HARNESS_", "DELEGATE_")) and k not in (
                   "CLAUDE_PROJECT_DIR", "CODEX_HOME", "XDG_STATE_HOME", "CLAUDE_CONFIG_DIR")}
        env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), PATH=f"{self.bin}:/usr/bin:/bin",
                   LEAK_CANARY="must-not-reach-the-task")
        env.update(extra)
        return env

    def launcher(self):
        """드라이버 실행 경로. root 가 아니면 uid 백엔드의 root 전용 단계를 프로세스 안에서 바꿔 끼운다(제품 코드에는 이런 스위치가 없다)."""
        if IS_ROOT:
            return SCRIPTS / "delegate.py"
        p = self.tmp / "launch.py"
        p.write_text(f"""import sys
sys.path.insert(0, {str(SCRIPTS)!r})
import delegate_isolation as iso
iso.UidBackend.unavailable = lambda self: ""
iso.UidBackend.give = lambda self, *a: None
iso.UidBackend.take_back = lambda self, *a: None
import delegate
sys.exit(delegate.main(sys.argv[1:]))
""")
        return p

    def drive(self, *args, cwd=None, env=None, **popen):
        return subprocess.run([sys.executable, "-I", str(self.launcher()), *map(str, args)], cwd=cwd or self.repo,
                              env=env or self.env(), capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
                              **popen)

    def start(self, *args, env=None):
        return subprocess.Popen([sys.executable, "-I", str(self.launcher()), *map(str, args)], cwd=self.repo,
                                env=env or self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                stdin=subprocess.DEVNULL)

    def wait_for(self, path, seconds=30):
        end = time.time() + seconds
        while time.time() < end:
            if Path(path).exists():
                return True
            time.sleep(0.05)
        return False

    def calls(self, agent):
        return [json.loads(p.read_text()) for p in sorted(self.ctl.glob(f"{agent}-*.json"))]

    def base(self, agent):
        return self.ws / f"proj-{agent}"

    def cleanup(self):
        # worktree 는 시험 저장소에만 등록되므로 임시 폴더를 지우면 같이 사라진다.
        shutil.rmtree(self.tmp, ignore_errors=True)
