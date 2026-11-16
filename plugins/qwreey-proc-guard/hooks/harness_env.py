"""harness.env 읽기. 하네스 훅, 플러그인, /q:doctor, statusline 이 같이 쓴다(표준 라이브러리만).
@copy-of: home/.claude/lib/harness_env.py
정본은 claude-doctor 의 home/.claude/lib/harness_env.py(설치되면 ~/.claude/lib/harness_env.py)다. 플러그인은 설치된 정본을
먼저 쓰고(installed()), 없거나 load_layers 가 없는 옛 판이면 자기 옆의 바이트 같은 사본을 쓴다. 사본은 정본만 고친 뒤
python3 -I tools/sync-copies.py --apply 로 맞춘다.

파일 형식: 한 줄에 `KEY=VALUE`. `#` 로 시작하는 줄과 빈 줄은 무시한다.
- 값의 바깥 따옴표('…' 또는 "…")는 벗긴다. 줄 끝 주석은 따옴표 밖의 ` #` 부터다.
- `${NAME}` 과 `$NAME` 은 앞에서 정의한 키(아래 층 포함)나 환경 변수로 바꾼다. 맨 앞의 `~` 는 $HOME 이다.
- 셸로 source 하지 않는다(실행 없음). tools/home-sync.sh 도 같은 규칙으로 읽는다.

층(load_layers): 키마다 합치고 번호가 큰 층이 이긴다. 높은 층에 키가 있으면 빈 값이어도 그 값이다.
  1. DEFAULTS(+ 호출자 defaults)
  2. 사용자: $HARNESS_ENV, 없으면 호출자 후보, 없으면 <설정 디렉터리>/harness.env($CLAUDE_CONFIG_DIR 또는 ~/.claude)
  3. 저장소 공유: <project>/.claude/harness.env (커밋한다)
  4. 저장소 개인: <project>/.claude/harness.local.env (커밋하지 않는다. 저장소 .gitignore 에 넣는다)
  5. 프로세스 환경 변수
3, 4 층은 USER_ONLY 키(실행 경로, 기기 고유값, 보안 게이트)를 바꾸지 못한다.
<project> 는 호출자가 주거나, 안 주면 $CLAUDE_PROJECT_DIR(project_dir() 은 그것이 없을 때 훅 stdin 의 cwd). 없으면 3, 4 층이 없다.
HARNESS_ENV 는 사용자 층 파일 하나만 바꾼다. 저장소 층은 그대로 위에 얹힌다.
load(candidates) 는 사용자 층 하나만 읽는 옛 호출용이다.
"""
import os
import re
import sys
from pathlib import Path

DEFAULTS = {
    # 형제 저장소들이 있는 작업공간 루트. 비면 호출자가 정한다(claude-doctor 의 부모 디렉터리).
    "HARNESS_WORKSPACE": "",
    # claude-doctor 클론 위치. 비면 호출자가 스크립트 위치로 정한다.
    "HARNESS_DOCTOR_ROOT": "",
    # 툴체인 설치 경로(mise installs). shim 이 실패할 때 직접 부를 곳.
    "HARNESS_TOOL_INSTALLS": "~/.local/share/mise/installs",
    # 무거운 실행 래퍼. 키가 없으면 auto(choom 이 PATH 에 있으면 `choom -n 1000 --`), 빈 값이면 끔.
    "HARNESS_HEAVY_WRAP": "auto",
    # 무거운 실행 판정에 더할 실행기, 키워드(공백 구분). 툴킷 기본표(heavy-proc-guard)에 더해진다.
    "HARNESS_HEAVY_EXECUTORS": "",
    "HARNESS_HEAVY_KEYWORDS": "",
    # 켤 툴킷(공백 구분). 비면 전부. /q:doctor 는 이 목록 안에서 저장소마다 자동 감지한다.
    "HARNESS_TOOLKITS": "",
    # 위임(agy, codex) uid 표 위치. 비면 uid 충돌 검사는 저장소 안의 사본만 본다.
    "HARNESS_DELEGATE_REGISTRY": "",
    # 위임 실행 파일. 비면 PATH 의 agy/codex(mise shim 은 빈 환경에서 돌지 않아 건너뜀), 없으면 HARNESS_TOOL_INSTALLS 아래.
    "HARNESS_DELEGATE_AGY_BIN": "",
    "HARNESS_DELEGATE_CODEX_BIN": "",
    # 위임 인증 원본. agy 는 이 폴더를, codex 는 이 폴더의 auth.json 을 작업마다 복사한다. codex 가 비면 $CODEX_HOME, 없으면 ~/.codex.
    "HARNESS_DELEGATE_AGY_HOME": "~/.gemini",
    "HARNESS_DELEGATE_CODEX_HOME": "",
    # agy worktree 를 여는 격리: uid(root 의 uid 격리가 있을 때만) | sandbox(agy 셸 샌드박스만으로도 연다. 파일 도구는 갇히지 않는다).
    "HARNESS_DELEGATE_AGY_WORKTREE": "uid",
    # 격리(uid)가 없을 때의 agy: 빈 값이면 끔, allow 면 empty 만 연다(파일 도구가 사용자 권한으로 HOME 비밀을 읽고 밖에 쓴다).
    "HARNESS_DELEGATE_AGY_UNISOLATED": "",
    # codex 샌드박스. 비면 드라이버 기본(read-only). danger-full-access 는 uid 격리가 있을 때만 받는다.
    "HARNESS_DELEGATE_CODEX_SANDBOX": "",
    # 비어 있지 않으면 위임 작업에 빈 환경 대신 지금 환경을 넘긴다(토큰 같은 변수가 샐 수 있다).
    "HARNESS_DELEGATE_KEEP_ENV": "",
    # 위임 상태 폴더(작업 폴더 work/, 결과 runs/, 동시 실행 슬롯과 잠금). 비면 플랫폼 상태 폴더(Linux ~/.local/state/qwreey-delegate).
    "HARNESS_DELEGATE_STATE": "",
    # gc 가 지우는 위임 결과(<상태 폴더>/runs/)의 나이(일). 모든 저장소의 결과를 지우므로 사용자만 정한다.
    "HARNESS_DELEGATE_RUNS_DAYS": "14",
    # 에이전트마다 동시에 도는 위임 수, 모든 저장소 합계. 토큰 한도가 사용자 구독 단위라서.
    "HARNESS_DELEGATE_MAX_CONCURRENT": "1",
    # 위임 기본 모델(run --model 이 이긴다). 저장소 층이 정해도 격리와 무관하다.
    "HARNESS_DELEGATE_AGY_MODEL": "gemini-3.8-flash-high",
    "HARNESS_DELEGATE_CODEX_MODEL": "gpt-6-luna",
    # empty 모드에 파일을 넣을 때 더 거를 이름(공백 구분 glob). 기본 목록에 더해질 뿐이라 저장소 층도 정할 수 있다.
    "HARNESS_DELEGATE_SECRET_GLOBS": "",
    # 에이전트 git push 정책: normal(에이전트 push 가 정상 흐름) | deny | 빈 값(모름).
    "HARNESS_AGENT_PUSH": "",
}

_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _value(raw):
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        q = raw[0]
        end = raw.find(q, 1)
        return raw[1:end] if end > 0 else raw[1:]
    m = re.search(r"\s#", raw)
    return (raw[: m.start()] if m else raw).strip()


def expand(s, scope):
    s = _REF.sub(lambda m: scope.get(m.group(1) or m.group(2), os.environ.get(m.group(1) or m.group(2), "")), s)
    return os.path.expanduser(s) if s.startswith("~") else s


def parse(text, base=None):
    scope = dict(base or {})
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _KEY.match(line)
        if not m:
            continue
        key = m.group(1)
        val = os.environ[key] if key in os.environ else expand(_value(m.group(2)), scope)  # 환경 변수가 이긴다
        scope[key] = out[key] = val
    return out


PROJECT_FILES = (".claude/harness.env", ".claude/harness.local.env")  # 저장소 층, 뒤가 이긴다
# 저장소 층이 바꾸지 못하는 키: 실행할 프로그램과 경로, 기기 고유값, 보안 게이트. 클론한 저장소가 커밋해 둔 파일(harness.local.env 도
# 커밋될 수 있다)로 남의 하네스가 이것을 바꾸면 안 된다. 사용자 층과 환경 변수만 정한다.
USER_ONLY = frozenset({
    "HARNESS_WORKSPACE", "HARNESS_DOCTOR_ROOT", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP", "HARNESS_DELEGATE_REGISTRY",
    "HARNESS_AGENT_PUSH", "HARNESS_CODERAG", "HARNESS_LUAU_KB", "HARNESS_ROBLOX_DOCS_CACHE", "HARNESS_WORKSPACE_GATE",
    "SESSION_LOG_HOME", "SESSION_LOG_CLAUDE",
    "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_AGY_HOME", "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE", "HARNESS_DELEGATE_AGY_UNISOLATED", "HARNESS_DELEGATE_CODEX_SANDBOX", "HARNESS_DELEGATE_KEEP_ENV", "HARNESS_DELEGATE_STATE",
    "HARNESS_DELEGATE_MAX_CONCURRENT", "HARNESS_DELEGATE_RUNS_DAYS",
})


def config_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def project_dir(cwd=None):
    """저장소 층의 루트: $CLAUDE_PROJECT_DIR, 없으면 cwd(훅 stdin 의 cwd), 둘 다 없으면 None."""
    p = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    return Path(p) if p else None


def find_file(candidates):
    env = os.environ.get("HARNESS_ENV")
    for p in ([env] if env else []) + [str(c) for c in candidates]:
        if p and Path(p).is_file():
            return Path(p)
    return None


def _base(defaults):
    vals = {k: expand(v, {}) for k, v in DEFAULTS.items()}
    vals.update(defaults or {})
    vals.update({k: os.environ[k] for k in vals if k in os.environ})
    return vals


def _read(vals, f, skip=frozenset()):
    try:
        vals.update({k: v for k, v in parse(f.read_text(encoding="utf-8"), vals).items() if k not in skip})
        return True
    except (OSError, UnicodeDecodeError):
        return False


def load(candidates=(), defaults=None):
    """사용자 층만: {키: 값} 과 '_file' (읽은 파일 경로 또는 '')."""
    vals = _base(defaults)
    f = find_file(candidates)
    if f and not _read(vals, f):
        f = None
    vals["_file"] = str(f) if f else ""
    return vals


def layer_files(project=None, candidates=None):
    """(사용자 층 파일 또는 None, 저장소 층 파일들 낮은 층부터).
    project 가 None 이면 $CLAUDE_PROJECT_DIR, 빈 값이면 저장소 층이 없다. candidates 가 None 이면 <설정 디렉터리>/harness.env."""
    user = find_file(candidates if candidates is not None else [config_dir() / "harness.env"])
    if project is None:
        project = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    repo = []
    for rel in PROJECT_FILES if project else ():
        p = Path(project) / rel
        # 저장소가 설정 디렉터리의 부모(~)이면 저장소 층이 사용자 파일과 같다. 두 번 읽지 않는다.
        if p.is_file() and not (user and p.resolve() == user.resolve()):
            repo.append(p)
    return user, repo


def load_layers(project=None, candidates=None, defaults=None):
    """모든 층을 합친 {키: 값}. '_file' 은 읽은 사용자 층 파일(또는 ''), '_files' 는 읽은 파일 전부(낮은 층부터, 공백 구분)."""
    vals = _base(defaults)
    user, repo = layer_files(project, candidates)
    user = user if user and _read(vals, user) else None
    read = ([user] if user else []) + [f for f in repo if _read(vals, f, USER_ONLY)]
    vals["_file"] = str(user) if user else ""
    vals["_files"] = " ".join(str(f) for f in read)
    return vals


def installed():
    """설치된 정본(<설정 디렉터리>/lib/harness_env.py)이 load_layers 를 가지면 그 모듈, 아니면 이 모듈."""
    p = config_dir() / "lib" / "harness_env.py"
    try:
        if p.is_file() and p.resolve() != Path(__file__).resolve():
            import importlib.util
            spec = importlib.util.spec_from_file_location("_harness_env_installed", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "load_layers"):
                return mod
    except Exception:
        pass
    me = sys.modules.get(__name__)
    if getattr(me, "load_layers", None) is load_layers:
        return me
    # spec_from_file_location 으로 sys.modules 에 올리지 않고 읽은 경우: 이 모듈의 이름들을 그대로 묶어 돌려준다.
    import types
    return types.SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith("__")})


def heavy_wrap(vals):
    """무거운 실행 래퍼 argv 목록. 끔이거나 실행 파일이 없으면 []."""
    import shutil  # 여기서만 쓴다. 훅마다 모듈을 읽으므로 import 비용(수 ms)을 아낀다
    w = vals.get("HARNESS_HEAVY_WRAP", "auto").strip()
    if w == "auto":
        w = "choom -n 1000 --" if shutil.which("choom") else ""
    argv = w.split()
    return argv if argv and shutil.which(argv[0]) else []
