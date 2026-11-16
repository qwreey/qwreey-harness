"""harness.env 읽기. 하네스 훅, 플러그인, /q:doctor, statusline 이 같이 쓴다(표준 라이브러리만).
@copy-of: home/.claude/lib/harness_env.py
정본은 claude-doctor 의 home/.claude/lib/harness_env.py(설치되면 ~/.claude/lib/harness_env.py)다. 플러그인은 늘 자기 옆의 바이트 같은
사본을 쓴다: 설치본은 home-sync apply 때만 바뀌어 플러그인보다 옛 판일 수 있고, 옛 판은 플러그인의 user_only 를 모른다.
설치본은 같은 home/ 에서 함께 설치되는 스크립트(statusline)만 읽는다. 사본은 정본만 고친 뒤 python3 -I tools/sync-copies.py --apply 로 맞춘다.

이 모듈은 방식(파일 형식, 층, 저장소 층 막기)과 여러 플러그인이 같이 읽는 키만 안다. 한 플러그인만 읽는 키의 기본값과
사용자 전용 여부는 그 플러그인이 읽는 곳 옆에 두고 load_layers(defaults=, user_only=) 로 넘긴다.
사용자가 키를 읽는 곳은 home/.claude/harness.env 의 주석이다.

파일 형식: 한 줄에 `KEY=VALUE`. `#` 로 시작하는 줄과 빈 줄은 무시한다.
- 값의 바깥 따옴표('…' 또는 "…")는 벗긴다. 줄 끝 주석은 따옴표 밖의 ` #` 부터다.
- `${NAME}` 과 `$NAME` 은 앞에서 정의한 키(아래 층 포함)나 환경 변수로 바꾼다. 맨 앞의 `~` 는 $HOME 이다.
- 셸로 source 하지 않는다(실행 없음). tools/home-sync.sh 도 같은 규칙으로 읽는다.

층(load_layers): 키마다 합치고 번호가 큰 층이 이긴다. 높은 층에 키가 있으면 빈 값이어도 그 값이다.
  1. DEFAULTS + 호출자 defaults(값의 `~` 와 `$NAME` 은 여기서 푼다)
  2. 사용자: $HARNESS_ENV, 없으면 호출자 후보, 없으면 <설정 디렉터리>/harness.env($CLAUDE_CONFIG_DIR 또는 ~/.claude)
  3. 저장소 공유: <project>/.claude/harness.env (커밋한다)
  4. 저장소 개인: <project>/.claude/harness.local.env (커밋하지 않는다. 저장소 .gitignore 에 넣는다)
  5. 프로세스 환경 변수
3, 4 층은 USER_ONLY, LEGACY_USER_ONLY 와 호출자 user_only 의 키(실행 경로, 기기 고유값, 보안 게이트)를 바꾸지 못한다.
<project> 는 호출자가 주거나, 안 주면 $CLAUDE_PROJECT_DIR(project_dir() 은 그것이 없을 때 훅 stdin 의 cwd). 없으면 3, 4 층이 없다.
HARNESS_ENV 는 사용자 층 파일 하나만 바꾼다. 저장소 층은 그대로 위에 얹힌다.
load(candidates) 는 사용자 층 하나만 읽는 옛 호출용이다.
"""
import os
import re
from pathlib import Path

# 여러 플러그인이 읽는 키만. 한 플러그인만 읽는 키는 그 플러그인이 정한다(tools/tests/test-harness-env-owners.py 가 겹침을 본다).
DEFAULTS = {
    # 형제 저장소들이 있는 작업공간 루트. 비면 호출자가 정한다(claude-doctor 의 부모 디렉터리).
    "HARNESS_WORKSPACE": "",
    # claude-doctor 클론 위치. 비면 호출자가 스크립트 위치로 정한다.
    "HARNESS_DOCTOR_ROOT": "",
    # 툴체인 설치 경로(mise installs). shim 이 실패할 때 직접 부를 곳.
    "HARNESS_TOOL_INSTALLS": "~/.local/share/mise/installs",
    # 무거운 실행 래퍼(heavy_wrap). 키가 없으면 auto(choom 이 PATH 에 있으면 `choom -n 1000 --`), 빈 값이면 끔.
    "HARNESS_HEAVY_WRAP": "auto",
    # 켤 툴킷(공백 구분). 비면 전부. /q:doctor 는 이 목록 안에서 저장소마다 자동 감지한다.
    "HARNESS_TOOLKITS": "",
    # 위임(agy, codex) uid 표 위치(위임 드라이버, /q:doctor 의 uid 충돌 검사). 비면 저장소 안의 사본.
    "HARNESS_DELEGATE_REGISTRY": "",
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
# 저장소 층이 바꾸지 못하는 키 가운데 여러 플러그인이 읽는 것: 실행할 프로그램과 경로, 기기 고유값. 클론한 저장소가 커밋해 둔
# 파일(harness.local.env 도 커밋될 수 있다)로 남의 하네스가 이것을 바꾸면 안 된다. 사용자 층과 환경 변수만 정한다.
# HARNESS_CODERAG 는 /q:doctor 가 읽고 qwreey-sessions:recall 이 모델에게 사용자 harness.env 에서 읽게 한다.
USER_ONLY = frozenset({
    "HARNESS_WORKSPACE", "HARNESS_DOCTOR_ROOT", "HARNESS_TOOL_INSTALLS", "HARNESS_HEAVY_WRAP", "HARNESS_DELEGATE_REGISTRY",
    "HARNESS_CODERAG",
})
# 이 판보다 옛 플러그인은 installed() 로 이 설치본을 읽고 user_only 를 넘기지 않아, 예전 로더가 막던 키를 여기서 대신 막는다. 설치된 플러그인 가운데 이 판보다 옛것이 없으면 지운다.
LEGACY_USER_ONLY = frozenset({
    "HARNESS_AGENT_PUSH", "HARNESS_LUAU_KB", "HARNESS_ROBLOX_DOCS_CACHE", "HARNESS_WORKSPACE_GATE",
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
    vals = {k: expand(v, {}) for k, v in {**DEFAULTS, **(defaults or {})}.items()}
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


def load_layers(project=None, candidates=None, defaults=None, user_only=()):
    """모든 층을 합친 {키: 값}. '_file' 은 읽은 사용자 층 파일(또는 ''), '_files' 는 읽은 파일 전부(낮은 층부터, 공백 구분).
    defaults 는 호출자 키의 기본값, user_only 는 저장소 층이 바꾸지 못할 호출자 키(USER_ONLY 에 더해진다)."""
    vals = _base(defaults)
    user, repo = layer_files(project, candidates)
    user = user if user and _read(vals, user) else None
    skip = USER_ONLY | LEGACY_USER_ONLY | frozenset(user_only)
    read = ([user] if user else []) + [f for f in repo if _read(vals, f, skip)]
    vals["_file"] = str(user) if user else ""
    vals["_files"] = " ".join(str(f) for f in read)
    return vals


def heavy_wrap(vals):
    """무거운 실행 래퍼 argv 목록. 끔이거나 실행 파일이 없으면 []."""
    import shutil  # 여기서만 쓴다. 훅마다 모듈을 읽으므로 import 비용(수 ms)을 아낀다
    w = vals.get("HARNESS_HEAVY_WRAP", "auto").strip()
    if w == "auto":
        w = "choom -n 1000 --" if shutil.which("choom") else ""
    argv = w.split()
    return argv if argv and shutil.which(argv[0]) else []
