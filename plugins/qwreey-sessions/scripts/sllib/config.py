"""설정 읽기. 우선순위: 환경 변수 > harness.env 층 > DEFAULTS. 이 모듈의 키(DEFAULTS)만 읽는다.

harness.env 층은 scripts/harness_env.py(하네스 정본 home/.claude/lib/harness_env.py 의 사본)의
load_layers 다: 사용자($HARNESS_ENV, 없으면 $CLAUDE_CONFIG_DIR 또는 ~/.claude 의 harness.env) < 플러그인 옵션
(settings.json pluginConfigs, plugin.json userConfig 에 둔 키만) < 저장소($CLAUDE_PROJECT_DIR) .claude/harness.env
< .claude/harness.local.env. USER_ONLY 의 키는 저장소 층이 바꾸지 못한다.
userConfig 의 default 는 여기 DEFAULTS 와 같아야 한다(tools/tests/test-plugin-userconfig.py). 켜고 끄는 키는 on/off 를 받는다:
옵션의 boolean 이 on/off 로 들어온다.
파일이 없어도 플러그인은 기본값으로 돈다(툴킷, 하네스 무관).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

DEFAULTS = {
    "SESSION_LOG": "on",                 # off(또는 0, false, no) 면 모든 훅이 아무것도 안 한다(옵션 session_log)
    "SESSION_LOG_DISABLE": "off",        # 옛 끄기 키. userConfig 에는 없고, 이미 적어 둔 harness.env, 환경 변수의 on(또는 1)이 계속 끄게 읽는다
    "SESSION_LOG_RECORD_NONINTERACTIVE": "",  # 1 이면 claude -p, SDK 로 도는 세션도 기록한다(기본은 건너뜀: 프로브 실행이 쓰레기 기록을 만든다)
    "SESSION_LOG_HOME": "",              # 외부 저장소 루트. 비면 ${XDG_DATA_HOME:-~/.local/share}/session-log
    "SESSION_LOG_MODEL": "haiku",        # 요약 모델(claude -p --model 값)
    "SESSION_LOG_CLAUDE": "claude",      # claude 실행 파일
    "SESSION_LOG_COOLDOWN_MIN": "20",    # 중간 트리거 쿨다운(분)
    "SESSION_LOG_GROW_KB": "512",        # 중간 트리거: 트랜스크립트가 지난 위치보다 이만큼 자라야 함
    "SESSION_LOG_CHUNK_CHARS": "90000",  # 구간 하나(요약 호출 하나)의 줄인 텍스트 상한
    "SESSION_LOG_MIN_CHARS": "3000",     # 일반 flush 최소 분량(미만이면 다음에 합친다)
    "SESSION_LOG_FORCE_MIN_CHARS": "500",  # 강제 flush(PreCompact, SessionEnd, 수동) 최소 분량
    "SESSION_LOG_CALL_TIMEOUT": "300",   # 요약 호출 하나의 시간 상한(초)
    "SESSION_LOG_MAX_PARALLEL": "2",     # 기계 전체 동시 요약 상한
    "SESSION_LOG_HANDOVER_CHARS": "800",     # SessionStart 인계 상한
    "SESSION_LOG_HANDOVER_MAX_DAYS": "3",    # 마지막 절이 이보다 오래되면 인계하지 않는다(소급 기록 등)
    "SESSION_LOG_HANDOVER_LAG_LINES": "400",  # 마지막 절 끝줄이 트랜스크립트 끝보다 이만큼 넘게 뒤처지면 미해결을 보이지 않는다(요약은 512KB 자랄 때마다라 평소 뒤처짐은 수백 줄 이하, 낡은 항목은 이미 해결됐을 수 있다)
    "SESSION_LOG_HANDOVER_LIVE_MIN": "10",   # 다른 세션 트랜스크립트가 이 분 안에 바뀌었으면 아직 일하는 중이라 인계하지 않는다
    "SESSION_LOG_PRECOMPACT_CHARS": "3000",  # PreCompact 상기 주입 상한
    "SESSION_LOG_COMPACT_INSTRUCTIONS": "on",  # off 면 PreCompact 에서 요약기에게 남길 것, 뺄 것 두 줄을 내지 않는다
    "SESSION_LOG_COMPACT_ANCHORS": "on",   # off 면 compact 뒤에 요약된 구간의 사용자 원문, 식별자 목록을 다시 넣지 않는다
    "SESSION_LOG_COMPACT_ANCHORS_CHARS": "8000",  # 그것을 포함한 SessionStart(compact) 출력 전체의 목표 길이. 9000 을 넘기면 9000(CC 가 10,000자 넘는 훅 출력을 미리보기로 바꾼다)
    "SESSION_LOG_PENDING_STRONG_COUNT": "5",  # pending 이 이 개수 이상이면 강한 문구
    "SESSION_LOG_PENDING_STRONG_DAYS": "7",   # 가장 오래된 pending 이 이 일수 이상이면 강한 문구
    "SESSION_LOG_HOME_NUDGE_COUNT": "3",     # 보관 위치가 없고 pending 이 이 개수 이상이면 위치를 정하자고 제안한다(세션 하나가 기록 하나라 세 번 쌓였다면 우연이 아니다)
    "SESSION_LOG_HOME_NUDGE_DAYS": "3",      # 또는 가장 오래된 pending 이 이 일수 이상이면(주중 작업이 한 바퀴 돈 셈)
    "SESSION_LOG_READ_GATE": "on",           # off 면 큰 기록 통째 Read 를 막지 않는다
    "SESSION_LOG_READ_GATE_KB": "32",        # 기록(세션 기록, .claude 스냅숏 폴더)을 offset, limit 없이 Read 할 때 이 크기(KiB) 이상이면 막고 부분 읽기를 안내한다. 훨씬 낮추면 막힌 뒤 나눠 읽는 비용이 더 커진다
    "SESSION_LOG_RECORD_MAX_KB": "64",   # 기록 파일이 이보다 크면 -2, -3 으로 나눈다
}
# 저장소 층이 바꾸지 못하는 키: 기록을 쓸 곳과 실행할 claude. 클론한 저장소가 커밋한 파일로 기록을 빼돌리거나 다른 프로그램을 돌리면 안 된다.
USER_ONLY = frozenset({"SESSION_LOG_HOME", "SESSION_LOG_CLAUDE"})


def _read_harness_env() -> dict:
    """harness.env 층. 실패하면 {}(기본값으로 돈다). 설치된 ~/.claude/lib 판은 옛 판일 수 있어 USER_ONLY 를 모르므로 늘 옆 사본을 쓴다."""
    try:
        spec = importlib.util.spec_from_file_location("_sl_harness_env", Path(__file__).resolve().parent.parent / "harness_env.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.load_layers(user_only=USER_ONLY)
    except Exception:
        return {}


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
    """세션 기록이 꺼졌나: SESSION_LOG 가 꺼짐 값이거나, 옛 키 SESSION_LOG_DISABLE 이 켜짐 값이면."""
    if get("SESSION_LOG").strip().lower() in ("off", "0", "false", "no"):
        return True
    return get("SESSION_LOG_DISABLE").strip().lower() in ("1", "true", "yes", "on")


def anchors_off() -> bool:
    return get("SESSION_LOG_COMPACT_ANCHORS").strip().lower() in ("off", "0", "false", "no")


def read_gate_off() -> bool:
    return get("SESSION_LOG_READ_GATE").strip().lower() in ("off", "0", "false", "no")


def skip_noninteractive() -> bool:
    """claude -p 와 SDK 세션은 CLAUDE_CODE_ENTRYPOINT 가 sdk-cli, sdk-ts, sdk-py 로 시작한다(실측: -p 는 sdk-cli, 대화형은 cli).
    사람과 대화하지 않는 실행은 기록할 맥락이 아니다. SESSION_LOG_RECORD_NONINTERACTIVE=1 로 되돌린다."""
    if get("SESSION_LOG_RECORD_NONINTERACTIVE").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk")


def home() -> Path:
    h = get("SESSION_LOG_HOME").strip()
    if h:
        return Path(os.path.expanduser(h))
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(xdg) / "session-log"


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"))
