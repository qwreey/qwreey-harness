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
if [ "$1" = --help ]; then echo "--no-new-privs --inh-caps --bounding-set --reuid --regid --clear-groups"; exit 0; fi
echo "$@" >> "{ctl}/setpriv.log"
while [ $# -gt 0 ]; do case "$1" in --*) shift ;; *) break ;; esac; done
if [ -e "{ctl}/deny" ] && [ "$1" = sh ]; then exit 1; fi
exec "$@"
"""

FAKE_AGY = """#!{py}
import json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
ctl = Path({ctl!r})
cwd = Path.cwd()
home = Path(os.environ["HOME"])
(ctl / f"agy-{{os.getpid()}}.json").write_text(json.dumps({{"argv": sys.argv, "cwd": str(cwd), "env": dict(os.environ),
    "cwd_uid": os.stat(cwd).st_uid, "uid": os.getuid()}}))
if (ctl / "trap").exists():
    def slow_exit(*_):
        time.sleep(1)
        (ctl / "trapped").write_text("1")
        sys.exit(0)
    signal.signal(signal.SIGTERM, slow_exit)
if (ctl / "survivor").exists():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"], start_new_session=True)
    (ctl / "survivor.pid").write_text(str(p.pid))
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
if (ctl / "plant").exists():
    # 작업 uid 가 할 수 있는 바꿔치기: 보고서를 비밀로 가는 링크로, .delegate 와 brain 을 root 폴더로 가는 링크로.
    if (cwd / "REPORT.md").exists() or (cwd / ".git").exists():
        (cwd / "REPORT.md").unlink(missing_ok=True)
        os.symlink({secret!r}, cwd / "REPORT.md")
    shutil.rmtree(cwd / ".delegate")
    os.symlink({victim!r}, cwd / ".delegate")
    brain = home / ".gemini" / "antigravity-cli" / "brain"
    shutil.rmtree(brain)
    os.symlink({victim_brain!r}, brain)
if (ctl / "plant-home").exists():
    (cwd / ".delegate" / "report.md").unlink(missing_ok=True)
    os.symlink({secret!r}, cwd / ".delegate" / "report.md")
    shutil.rmtree(home / ".gemini")
    os.symlink({victim_gemini!r}, home / ".gemini")
if (ctl / "agy-denied").exists():
    # 실측한 headless 거절의 꼴: 빈 답, denied_actions, stderr 의 안내.
    print("headless mode cannot prompt for tool confirmation; auto-denied", file=sys.stderr)
    print(json.dumps({{"status": "SUCCESS", "response": "", "denied_actions": [
        {{"action": "read_file", "display_name": "ReadFile"}}, {{"action": "command", "display_name": "Bash"}}]}}))
elif "--output-format" in sys.argv and sys.argv[sys.argv.index("--output-format") + 1] == "json":
    print("some log line", file=sys.stderr)
    print(json.dumps({{"status": "SUCCESS", "response": "agy stdout answer", "num_turns": 1}}))
else:
    print("agy stdout answer")
"""

FAKE_CODEX = """#!{py}
import json, os, sys
from pathlib import Path
ctl = Path({ctl!r})
prompt = sys.stdin.read()
args = sys.argv
(ctl / f"codex-{{os.getpid()}}.json").write_text(json.dumps({{"argv": args, "cwd": os.getcwd(), "env": dict(os.environ),
    "stdin": prompt, "uid": os.getuid()}}))
if (ctl / "block-codex").exists():
    import time
    (ctl / "codex-started").write_text("1")
    for _ in range(600):
        if (ctl / "release").exists():
            break
        time.sleep(0.05)
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

    def __init__(self, real_setpriv=False):
        self.real = real_setpriv
        self.tmp = Path(tempfile.mkdtemp(prefix="delegate-test-"))
        self.ctl = self.tmp / "ctl"
        self.bin = self.tmp / "bin"
        self.home = self.tmp / "home"
        self.cfg = self.tmp / "cfg"
        self.ws = self.tmp / "ws"
        self.repo = self.ws / "proj"
        self.registry = self.tmp / "registry.tsv"
        self.uid = free_uid()
        self.codex_uid = free_uid(self.uid + 1)
        for p in (self.ctl, self.bin, self.cfg, self.repo):
            p.mkdir(parents=True)
        self._victims()
        if self.real:
            # 진짜 setpriv 아래의 가짜 에이전트(작업 uid)가 실행 파일을 읽고 ctl 에 기록할 수 있게.
            for p in (self.tmp, self.ws, self.repo, self.bin):
                p.chmod(0o755)
            self.ctl.chmod(0o777)
        self._fakes()
        self._home()
        git("init", "-q", "-b", "main", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("base\n")
        (self.repo / "AGENTS.md").write_text("# map\n")
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "base", cwd=self.repo)
        self.registry.write_text(f"# test registry\nproj\t{self.repo}\t{self.uid}\t-\ttest\tcodex={self.codex_uid}\n")
        self.user_env(f"HARNESS_DELEGATE_REGISTRY={self.registry}\nHARNESS_DELEGATE_AGY_BIN={self.bin / 'agy'}\n"
                      f"HARNESS_DELEGATE_CODEX_BIN={self.bin / 'codex'}\nHARNESS_HEAVY_WRAP=\n")
        self.prompt = self.tmp / "prompt.md"
        self.prompt.write_text("TASK BODY: say hello\n")

    def _victims(self):
        """root 만 읽는 비밀 파일과 폴더. 드라이버가 링크를 따라가면 시험이 알아챈다."""
        self.secret = self.tmp / "secret.txt"
        self.secret.write_text("ROOTSECRET\n")
        self.secret.chmod(0o600)
        self.victim = self.tmp / "victim"
        self.victim.mkdir(mode=0o700)
        for top in (self.tmp / "victim-brain", self.tmp / "victim-gemini" / "antigravity-cli" / "brain"):
            (top / "conv-x" / "scratch").mkdir(parents=True)
            (top / "conv-x" / "scratch" / "stolen.txt").write_text("ROOTSECRET\n")
        self.victim_brain = self.tmp / "victim-brain"
        self.victim_gemini = self.tmp / "victim-gemini"
        for p in (self.tmp / "victim-brain", self.tmp / "victim-gemini"):
            p.chmod(0o700)

    def _fakes(self):
        names = (("agy", FAKE_AGY), ("codex", FAKE_CODEX)) + (() if self.real else (("setpriv", FAKE_SETPRIV),))
        for name, text in names:
            p = self.bin / name
            p.write_text(text.format(ctl=str(self.ctl), py=sys.executable, secret=str(self.secret),
                                     victim=str(self.victim), victim_brain=str(self.victim_brain),
                                     victim_gemini=str(self.victim_gemini)))
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
        (self.home / ".ssh").mkdir(mode=0o700)
        (self.home / ".git-credentials").write_text("https://u:p@example.invalid\n")
        (self.cfg / ".credentials.json").write_text("{}\n")
        # 실제 비밀 파일처럼 소유자만 읽는다. 진짜 setpriv 시험의 doctor 가 이 권한을 잰다.
        for p in (self.home / ".git-credentials", self.cfg / ".credentials.json", self.home / ".codex" / "auth.json"):
            p.chmod(0o600)

    def user_env(self, text):
        (self.cfg / "harness.env").write_text(text)

    def add_repo(self, key, per_agent=True):
        """registry 에 저장소 하나를 더한다(다른 uid). per_agent=False 는 옛 꼴(agy, codex 가 uid 하나). 그 저장소 경로."""
        repo = self.ws / key
        repo.mkdir()
        if self.real:
            repo.chmod(0o755)
        git("init", "-q", "-b", "main", cwd=repo)
        (repo / "f.txt").write_text("x\n")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "base", cwd=repo)
        used = [int(u) for ln in self.registry.read_text().splitlines() if not ln.startswith("#")
                for u in [ln.split("\t")[2]] + [x.split("=")[1] for x in (ln.split("\t") + [""] * 6)[5].split(",") if x]]
        uid = free_uid(max(used) + 1)
        extra = f"\t-\tcodex={free_uid(uid + 1)}" if per_agent else ""
        with open(self.registry, "a") as f:
            f.write(f"{key}\t{repo}\t{uid}\t-{extra}\n")
        return repo

    def fake_mise(self):
        """가짜 mise(ls --current --json, bin-paths, exec)와 그것이 고정하는 가짜 pesde. (mise 폴더, 도구 폴더, 데이터 폴더)."""
        misebin, tools, data = self.tmp / "misebin", self.tmp / "tools" / "pesde" / "bin", self.tmp / "misedata"
        for p in (misebin, tools, data / "installs"):
            p.mkdir(parents=True)
        (misebin / "mise").write_text(f"""#!{sys.executable}
import json, os, sys
a = sys.argv[1:]
if a[:3] == ["ls", "--current", "--json"]:
    print(json.dumps({{"pesde": [{{"installed": True, "source": {{"path": os.path.join(os.getcwd(), "mise.toml")}}}}]}}))
elif a[:1] == ["bin-paths"]:
    print({str(tools)!r})
elif a[:1] == ["exec"]:
    i = a.index("--")
    os.execvp(a[i + 1], a[i + 1:])
""")
        (tools / "pesde").write_text('#!/bin/sh\necho "$PATH" > setup-path\necho "$MISE_DATA_DIR" > setup-mise-data\n'
                                     'id -u > setup-uid\ntouch pesde-installed\n')
        for p in (misebin / "mise", tools / "pesde"):
            p.chmod(0o755)
        if self.real:
            for p in (self.tmp / "tools", self.tmp / "tools" / "pesde", tools, misebin):
                p.chmod(0o755)
        return misebin, tools, data

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("HARNESS_", "DELEGATE_")) and k not in (
                   "CLAUDE_PROJECT_DIR", "CODEX_HOME", "XDG_STATE_HOME", "CLAUDE_CONFIG_DIR")}
        path = f"{self.bin}:/usr/bin:/bin" + (":/usr/sbin:/sbin" if self.real else "")
        env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg), PATH=path,
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

    def rec(self, agent, name):
        return self.base(agent) / ".runs" / name

    def leaked(self, top):
        """top 아래 파일 중 비밀 내용이 든 것(링크는 따라가지 않는다)."""
        hits = []
        for p in Path(top).rglob("*"):
            if p.is_file() and not p.is_symlink() and b"ROOTSECRET" in p.read_bytes():
                hits.append(p)
        return hits

    def cleanup(self):
        # worktree 는 시험 저장소에만 등록되므로 임시 폴더를 지우면 같이 사라진다.
        shutil.rmtree(self.tmp, ignore_errors=True)
