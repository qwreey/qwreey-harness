"""harness.env 읽기. 하네스 훅과 /q:doctor 가 같이 쓴다(표준 라이브러리만).

파일 형식: 한 줄에 `KEY=VALUE`. `#` 로 시작하는 줄과 빈 줄은 무시한다.
- 값의 바깥 따옴표('…' 또는 "…")는 벗긴다. 줄 끝 주석은 따옴표 밖의 ` #` 부터다.
- `${NAME}` 과 `$NAME` 은 앞에서 정의한 키나 환경 변수로 바꾼다. 맨 앞의 `~` 는 $HOME 이다.
- 셸로 source 하지 않는다(실행 없음). tools/home-sync.sh 도 같은 규칙으로 읽는다.

우선순위: 환경 변수 > 파일 > DEFAULTS. 파일 위치: $HARNESS_ENV, 없으면 호출자가 준 후보 순서.
"""
import os
import re
import shutil
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
    # 무거운 실행 판정에 더할 실행기·키워드(공백 구분). 툴킷 기본표(heavy-proc-guard)에 더해진다.
    "HARNESS_HEAVY_EXECUTORS": "",
    "HARNESS_HEAVY_KEYWORDS": "",
    # 켤 툴킷(공백 구분). 비면 전부. /q:doctor 는 이 목록 안에서 저장소마다 자동 감지한다.
    "HARNESS_TOOLKITS": "",
    # 위임(agy·codex) uid 표 위치. 비면 uid 충돌 검사는 저장소 안의 사본만 본다.
    "HARNESS_DELEGATE_REGISTRY": "",
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


def find_file(candidates):
    env = os.environ.get("HARNESS_ENV")
    for p in ([env] if env else []) + [str(c) for c in candidates]:
        if p and Path(p).is_file():
            return Path(p)
    return None


def load(candidates=(), defaults=None):
    """{키: 값} 과 '_file' (읽은 파일 경로 또는 '')."""
    vals = {k: expand(v, {}) for k, v in DEFAULTS.items()}
    vals.update(defaults or {})
    vals.update({k: os.environ[k] for k in vals if k in os.environ})
    f = find_file(candidates)
    if f:
        try:
            vals.update(parse(f.read_text(encoding="utf-8"), vals))
        except OSError:
            f = None
    vals["_file"] = str(f) if f else ""
    return vals


def heavy_wrap(vals):
    """무거운 실행 래퍼 argv 목록. 끔이거나 실행 파일이 없으면 []."""
    w = vals.get("HARNESS_HEAVY_WRAP", "auto").strip()
    if w == "auto":
        w = "choom -n 1000 --" if shutil.which("choom") else ""
    argv = w.split()
    return argv if argv and shutil.which(argv[0]) else []
