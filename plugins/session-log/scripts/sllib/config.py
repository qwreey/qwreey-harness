"""설정 읽기. 우선순위: 환경 변수 > harness.env > DEFAULTS.

harness.env 는 하네스(claude-doctor home/.claude)의 sandbox 고유값 파일이다. 있으면 SESSION_LOG_* 키만 읽는다.
없어도 플러그인은 기본값으로 돈다(툴킷·하네스 무관). 파일 위치: $HARNESS_ENV → $CLAUDE_CONFIG_DIR/harness.env
→ ~/.claude/harness.env. 파서는 같은 디렉터리의 lib/harness_env.py 가 있으면 그것을, 없으면 아래 작은 파서를 쓴다.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

DEFAULTS = {
    "SESSION_LOG_DISABLE": "",           # 1 이면 모든 훅이 아무것도 안 한다
    "SESSION_LOG_HOME": "",              # 외부 저장소 루트. 비면 ${XDG_DATA_HOME:-~/.local/share}/session-log
    "SESSION_LOG_MODEL": "haiku",        # 요약 모델(claude -p --model 값)
    "SESSION_LOG_CLAUDE": "claude",      # claude 실행 파일
    "SESSION_LOG_COOLDOWN_MIN": "20",    # 중간 트리거 쿨다운(분)
    "SESSION_LOG_GROW_KB": "512",        # 중간 트리거: 트랜스크립트가 지난 위치보다 이만큼 자라야 함
    "SESSION_LOG_CHUNK_CHARS": "90000",  # 구간 하나(요약 호출 하나)의 줄인 텍스트 상한
    "SESSION_LOG_MIN_CHARS": "3000",     # 일반 flush 최소 분량(미만이면 다음에 합친다)
    "SESSION_LOG_FORCE_MIN_CHARS": "500",  # 강제 flush(PreCompact·SessionEnd·수동) 최소 분량
    "SESSION_LOG_CALL_TIMEOUT": "300",   # 요약 호출 하나의 시간 상한(초)
    "SESSION_LOG_MAX_PARALLEL": "2",     # 기계 전체 동시 요약 상한
    "SESSION_LOG_HANDOVER_CHARS": "800",     # SessionStart 인계 상한
    "SESSION_LOG_HANDOVER_MAX_DAYS": "3",    # 마지막 절이 이보다 오래되면 인계하지 않는다(소급 기록 등)
    "SESSION_LOG_PRECOMPACT_CHARS": "3000",  # PreCompact 상기 주입 상한
    "SESSION_LOG_PENDING_STRONG_COUNT": "5",  # pending 이 이 개수 이상이면 강한 문구
    "SESSION_LOG_PENDING_STRONG_DAYS": "7",   # 가장 오래된 pending 이 이 일수 이상이면 강한 문구
    "SESSION_LOG_RECORD_MAX_KB": "64",   # 기록 파일이 이보다 크면 -2, -3 으로 나눈다
}


def _fallback_parse(text: str) -> dict:
    out: dict = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip()
        if v[:1] in ("'", '"') and v.endswith(v[0]) and len(v) > 1:
            v = v[1:-1]
        elif " #" in v:
            v = v.split(" #", 1)[0].strip()
        v = os.path.expandvars(v)
        out[k] = os.path.expanduser(v) if v.startswith("~") else v
    return out


def harness_env_file() -> Path | None:
    cands = [os.environ.get("HARNESS_ENV", "")]
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        cands.append(os.path.join(cfg, "harness.env"))
    cands.append(os.path.join(os.path.expanduser("~"), ".claude", "harness.env"))
    for c in cands:
        if c and os.path.isfile(c):
            return Path(c)
    return None


def _read_harness_env() -> dict:
    f = harness_env_file()
    if not f:
        return {}
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return {}
    lib = f.parent / "lib" / "harness_env.py"
    if lib.is_file():
        try:
            spec = importlib.util.spec_from_file_location("_sl_harness_env", lib)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod.parse(text)
        except Exception:
            pass
    return _fallback_parse(text)


_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    vals = dict(DEFAULTS)
    he = _read_harness_env()
    vals.update({k: v for k, v in he.items() if k in DEFAULTS})
    vals.update({k: os.environ[k] for k in DEFAULTS if k in os.environ})
    _CACHE = vals
    return vals


def get(key: str) -> str:
    return load()[key]


def num(key: str) -> float:
    try:
        return float(load()[key])
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def disabled() -> bool:
    return get("SESSION_LOG_DISABLE").strip().lower() in ("1", "true", "yes", "on")


def home() -> Path:
    h = get("SESSION_LOG_HOME").strip()
    if h:
        return Path(os.path.expanduser(h))
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(xdg) / "session-log"


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"))
