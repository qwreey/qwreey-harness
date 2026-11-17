"""qwreey-conventions 훅의 환경 읽기. tools/tests/test-coderag-rules-parity.py 가 rules_inject.py 와 함께 임시 팩 디렉터리에 복사해 쓴다.

이 플러그인 훅의 공용 작은 도구: 끄기 스위치(환경 변수 또는 harness.env 층)와 설정 위치. 표준 라이브러리만 쓴다.

harness.env 층은 옆의 harness_env.py(하네스 정본의 사본)의 load_layers 로 읽는다:
사용자 ~/.claude/harness.env < 이 플러그인 옵션(/config, plugin.json userConfig) < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
저장소는 $CLAUDE_PROJECT_DIR 다. 읽기 실패는 "켜짐"으로 본다(훅은 세션을 막지 않는다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다

# 이 플러그인만 읽는 harness.env 키의 기본값(tools/tests/test-harness-env-owners.py 가 주인을 본다). 저장소 층도 바꿀 수 있다:
# 개인 취향 규약이라 사용자가 자기 층에서 켜고, 저장소가 팀 공유 층에서 끈다.
# 키 셋은 userConfig 옵션(harness_readable_code 등)이기도 해서 plugin.json 의 default 와 같아야 한다(tools/tests/test-plugin-userconfig.py).
ENV_DEFAULTS = {
    # rules/readable-code.md 주입과 conventions-check 의 layout 알림. `on` 일 때만 켜진다.
    "HARNESS_READABLE_CODE": "off",
    # rules/ 주입(rules_inject, bash_writes). `off` 일 때만 꺼진다.
    "HARNESS_CONVENTIONS_RULES": "on",
    # 답변 언어 이탈 감지(reply_language). `off` 일 때만 꺼진다.
    "HARNESS_REPLY_LANGUAGE": "on",
    # 훅별 끄기 스위치. `off` 일 때만 꺼진다.
    "CONVENTIONS_CHECK": "on",  # conventions-check, reuse-check, bash_writes 의 줄 검사
    "STRUCTURE_REMINDER": "on",
    "MEMORY_PLACEMENT": "on",
}

_VALS = None


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def _layers():
    global _VALS
    if _VALS is None:
        try:
            import harness_env
            _VALS = harness_env.load_layers(defaults=ENV_DEFAULTS)
        except Exception:
            _VALS = {}
    return _VALS


def env_value(name):
    v = os.environ.get(name)
    if v is not None:
        return v.strip()
    return str(_layers().get(name, "")).strip()


def is_off(name):
    return env_value(name).lower() == "off"


def is_on(name):
    """켜기 스위치(기본 꺼짐)가 켜졌나: 값이 정확히 `on` 일 때만."""
    return env_value(name).lower() == "on"
