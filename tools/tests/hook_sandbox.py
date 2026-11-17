"""이 저장소의 훅 스크립트를 하위 프로세스로 돌리는 버리는 샌드박스. tools/regen-prompt-surface.py 와
tools/tests/test-hook-replay.py 가 함께 쓴다. 표준 라이브러리만 쓴다.

훅은 hooks.json 처럼 늘 `python3 -I -X utf8 <스크립트>` 에 stdin JSON 으로 부른다(HOOK_SANDBOX_SIMWIN=1 이면 simwin.py 를 거쳐 Windows 흉내로). 그래서 스크립트 경로와 출력을 지키는 리팩터(파일 나누기 등)는
이 호출을 깨지 않는다. 훅이 닿는 상태 위치는 모두 샌드박스 안으로 돌린다: TMPDIR, HOME, CLAUDE_CONFIG_DIR, XDG 폴더, session-log 저장소,
nonce salt(고정 값이라 태그의 nonce 가 실행마다 같다).

샌드박스 배치:
  tmp/   TMPDIR           home/  HOME            cfg/   CLAUDE_CONFIG_DIR     store/  SESSION_LOG_HOME
  ws/    workspace 루트   ws/mine  프로젝트 저장소(git init, .claude/)          ws/other, ws/x-kb  형제 저장소
subst() 가 펼치는 자리 표시: {repo} {ws} {tmp} {home} {cfg} {store} {sandbox} {root}(이 저장소) {uid}.

설치본 흉내(HOOK_SANDBOX_PLUGIN_COPY=1): 동료는 GitHub 마켓에서 받은 cache 사본으로 훅을 돌린다. 그 조건을 흉내 내려고 프로세스마다
한 번 plugins/*, packs/* 를 저장소 밖 임시 폴더의 cache/<마켓>/<이름>/<버전>/ 으로 플러그인마다 따로 복사하고(설치본은 서로 옆에 있지
않다), 훅을 그 사본에서 돌린다. CLAUDE_PLUGIN_ROOT 는 사본 폴더, CLAUDE_PLUGIN_DATA 는 <cfg>/plugins/data/<이름>-<마켓>(사례가 정하면 그 값).
출력의 사본 경로는 normalize() 가 <root>/plugins/<이름> 꼴로 되돌려, 경로 글자만 다른 것은 어긋남으로 세지 않는다.
"""
import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SALT = "00" * 32
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# 훅 JSON 출력에서 모델(systemMessage 는 사용자)에게 가는 칸, 보이는 순서대로.
TEXT_FIELDS = (("hookSpecificOutput", "additionalContext"), ("hookSpecificOutput", "permissionDecisionReason"),
               (None, "reason"), (None, "systemMessage"))


def nonce(session_id):
    return hashlib.sha256((SALT + ":" + session_id).encode()).hexdigest()[:12]


PLUGIN_COPY = os.environ.get("HOOK_SANDBOX_PLUGIN_COPY") == "1"
_INSTALL = {}


def plugin_install():
    """설치본 흉내: {"base": 임시 폴더, "market": 마켓 이름, "dirs": {"plugins/<이름>": (사본 폴더, 이름)}}. 한 프로세스에 한 번 복사한다."""
    if _INSTALL:
        return _INSTALL
    base = Path(tempfile.mkdtemp(prefix="hook-sandbox-install-")).resolve()
    atexit.register(shutil.rmtree, str(base), True)
    try:
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["name"]
    except (OSError, ValueError, KeyError):
        market = "local"
    dirs = {}
    for manifest in sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json")) + sorted(ROOT.glob("packs/*/.claude-plugin/plugin.json")):
        src = manifest.parent.parent
        data = json.loads(manifest.read_text(encoding="utf-8"))
        dst = base / "cache" / market / data["name"] / str(data.get("version") or "0.0.0")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"))
        dirs[src.relative_to(ROOT).as_posix()] = (dst, data["name"])
    _INSTALL.update(base=base, market=market, dirs=dirs)
    return _INSTALL


def installed_script(script):
    """저장소 기준 스크립트 경로를 설치본 사본 안 경로로: (경로, 사본 플러그인 폴더, 이름). 플러그인 밖이면 None."""
    rel = Path(script).as_posix()
    for prefix, (dst, name) in plugin_install()["dirs"].items():
        if rel.startswith(prefix + "/"):
            return dst / rel[len(prefix) + 1:], dst, name
    return None


class Result:
    def __init__(self, rc, stdout, stderr):
        self.rc, self.stdout, self.stderr = rc, stdout, stderr

    def json(self):
        try:
            v = json.loads(self.stdout)
            return v if isinstance(v, dict) else None
        except ValueError:
            return None

    def fields(self):
        """출력에서 모델과 사용자에게 가는 글 [(칸 이름, 글)]. JSON 이 아닌 stdout 은 "stdout" 칸 하나."""
        if not self.stdout.strip():
            return []
        data = self.json()
        if data is None:
            return [("stdout", self.stdout.rstrip("\n"))]
        out = []
        for outer, key in TEXT_FIELDS:
            box = data.get(outer) if outer else data
            if isinstance(box, dict) and isinstance(box.get(key), str) and box[key]:
                out.append((key, box[key]))
        return out

    def text(self):
        """모델에게 가는 글을 모두 이은 것. 칸이 둘 이상이면 칸 이름을 머리에 단다."""
        parts = self.fields()
        if len(parts) == 1:
            return parts[0][1]
        return "\n".join("--- %s ---\n%s" % (k, v) for k, v in parts)

    def decision(self):
        data = self.json() or {}
        hso = data.get("hookSpecificOutput") if isinstance(data.get("hookSpecificOutput"), dict) else {}
        return hso.get("permissionDecision") or data.get("decision")


class Sandbox:
    def __init__(self, prefix="hook-sandbox-"):
        self.root = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        self.tmp = self.root / "tmp"
        self.home = self.root / "home"
        self.cfg = self.root / "cfg"
        self.store = self.root / "store"
        self.ws = self.root / "ws"
        self.repo = self.ws / "mine"
        for d in (self.tmp, self.home, self.cfg, self.store, self.repo / ".claude", self.ws / "other" / ".git", self.ws / "x-kb" / ".git"):
            d.mkdir(parents=True, exist_ok=True)
        (self.ws / "other" / "CLAUDE.md").write_text("# Other\n\nOther repo does things.\n", encoding="utf-8")
        (self.ws / "x-kb" / "README.md").write_text("# kb\nKnowledge.\n", encoding="utf-8")
        (self.root / "salt").write_text(SALT)
        self.git("init", "-q", ".")

    def detached(self):
        """명령줄에 샌드박스 경로가 든 다른 프로세스의 pid(훅이 setsid 로 떼어 낸 session-log 워커 등). /proc 이 없으면 []."""
        me, needle, out = os.getpid(), str(self.root).encode(), []
        try:
            pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
        except OSError:
            return out
        for pid in pids:
            try:
                with open("/proc/%d/cmdline" % pid, "rb") as f:
                    if pid != me and needle in f.read():
                        out.append(pid)
            except OSError:
                pass
        return out

    def close(self, wait_s=10.0):
        """떼어 낸 워커가 끝나기를 기다린 뒤 지운다. 먼저 지우면 워커가 지운 자리에 폴더를 다시 만든다."""
        end = time.time() + wait_s
        while self.detached() and time.time() < end:
            time.sleep(0.05)
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def places(self):
        return {"repo": str(self.repo), "ws": str(self.ws), "tmp": str(self.tmp), "home": str(self.home), "cfg": str(self.cfg),
                "store": str(self.store), "sandbox": str(self.root), "root": str(ROOT), "uid": str(os.getuid())}

    def subst(self, obj):
        if isinstance(obj, str):
            for k, v in self.places().items():
                obj = obj.replace("{%s}" % k, v)
            return obj
        if isinstance(obj, list):
            return [self.subst(x) for x in obj]
        if isinstance(obj, dict):
            return {self.subst(k): self.subst(v) for k, v in obj.items()}
        return obj

    def normalize(self, text):
        """기계마다 다른 경로를 자리 표시로 바꿔 실행과 기계를 넘어 비교할 수 있게 한다."""
        if PLUGIN_COPY:
            for prefix, (dst, _) in plugin_install()["dirs"].items():
                text = text.replace(str(dst), str(ROOT / prefix))
        text = text.replace(str(self.root), "<sandbox>").replace(str(ROOT), "<root>")
        return text.replace("claude-%d" % os.getuid(), "claude-<uid>")

    def env(self, extra=None):
        e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "HOME": str(self.home), "TMPDIR": str(self.tmp),
             "CLAUDE_CONFIG_DIR": str(self.cfg), "CLAUDE_PROJECT_DIR": str(self.repo),
             "QWREEY_HARNESS_SALT_FILE": str(self.root / "salt"), "XDG_RUNTIME_DIR": str(self.root),
             "XDG_DATA_HOME": str(self.home / ".local" / "share"), "XDG_CONFIG_HOME": str(self.home / ".config"),
             "SESSION_LOG_HOME": str(self.store), "SESSION_LOG_CLAUDE": "/bin/false", "HARNESS_ENV": "/nonexistent",
             "CLAUDE_CODE_ENTRYPOINT": "cli", **GIT_ENV}
        for k, v in (extra or {}).items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = self.subst(str(v))
        return e

    def path(self, rel):
        """자리 표시로 시작하면 펼친 절대 경로, 아니면 프로젝트 저장소 기준 경로."""
        s = self.subst(str(rel))
        return Path(s) if os.path.isabs(s) else self.repo / s

    def write(self, rel, content, mtime_ago=None):
        """파일을 쓴다. content 는 글, JSONL 로 쓸 목록, 또는 {"text"|"jsonl"|"repeat"(+"times"), "mtime_ago"} 꼴.
        repeat 는 글을 times 번 이어 쓴다(자리 표시를 펼치지 않는다). mtime_ago 초만큼 mtime 을 과거로 돌린다."""
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            mtime_ago = content.get("mtime_ago", mtime_ago)
            if "repeat" in content:
                content = content["repeat"] * int(content.get("times", 1))
            else:
                content = content.get("jsonl", content.get("text", ""))
        if isinstance(content, list):
            content = "".join(json.dumps(self.subst(x), ensure_ascii=False) + "\n" for x in content)
        else:
            content = self.subst(content)
        p.write_text(content, encoding="utf-8")
        if mtime_ago:
            t = time.time() - float(mtime_ago)
            os.utime(p, (t, t))
        return p

    def git(self, *args, cwd=None):
        subprocess.run(["git", *args], cwd=str(cwd or self.repo), check=True, capture_output=True, env=self.env())

    def sh(self, cmd, cwd=None, env=None):
        return subprocess.run(["bash", "-c", self.subst(cmd)], cwd=str(cwd or self.repo), capture_output=True, text=True,
                              env=self.env(env), timeout=30)

    def run(self, script, payload, argv=(), env=None, cwd=None, timeout=30):
        """훅 스크립트(이 저장소 기준 상대 경로 또는 절대 경로)를 payload 를 stdin 으로 주어 돌린다. Result 를 돌려준다."""
        path = Path(script) if os.path.isabs(script) else ROOT / script
        env = dict(env or {})
        hit = installed_script(script) if PLUGIN_COPY and not os.path.isabs(script) else None
        if hit:
            path, plugin_root, name = hit
            env.setdefault("CLAUDE_PLUGIN_ROOT", str(plugin_root))
            env.setdefault("CLAUDE_PLUGIN_DATA", str(self.cfg / "plugins" / "data" / ("%s-%s" % (name, plugin_install()["market"]))))
        stdin = payload if isinstance(payload, str) else json.dumps(self.subst(payload), ensure_ascii=False)
        shim = [str(Path(__file__).resolve().with_name("simwin.py"))] if os.environ.get("HOOK_SANDBOX_SIMWIN") == "1" else []
        p = subprocess.run([sys.executable, "-I", "-X", "utf8", *shim, str(path), *[self.subst(a) for a in argv]], input=stdin, capture_output=True,
                           text=True, env=self.env(env), cwd=str(cwd or self.repo), timeout=timeout)
        return Result(p.returncode, p.stdout, p.stderr)
