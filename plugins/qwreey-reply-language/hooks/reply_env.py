"""qwreey-reply-language 훅의 환경 읽기: 끄기 스위치와 설정 위치. 표준 라이브러리만 쓴다.

harness.env 층은 옆의 harness_env.py(하네스 정본의 사본)의 load_layers 로 읽는다:
사용자 ~/.claude/harness.env < 이 플러그인 옵션(/config, plugin.json userConfig) < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
저장소는 $CLAUDE_PROJECT_DIR 다. 읽기 실패는 "켜짐"으로 본다(훅은 세션을 막지 않는다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다

# 이 플러그인만 읽는 harness.env 키의 기본값(tools/tests/test-harness-env-owners.py 가 주인을 본다). 사용자는 자기 층이나
# /config 에서 끄고, 저장소는 팀 공유 층에서 끈다. 키마다 같은 이름의 소문자 옵션이 plugin.json 에 있어서 그 기본값과
# 같아야 한다(tools/tests/test-plugin-userconfig.py).
ENV_DEFAULTS = {
    # 답변 언어 이탈 감지(reply_language). `off` 일 때만 꺼진다.
    "HARNESS_REPLY_LANGUAGE": "on",
}

_VALS = None


def config_dir():
    """Claude Code 설정 디렉터리: $CLAUDE_CONFIG_DIR, 없으면 ~/.claude."""
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
    """키의 값: 환경 변수가 이기고, 없으면 harness.env 층, 그것도 없으면 기본값."""
    v = os.environ.get(name)
    if v is not None:
        return v.strip()
    return str(_layers().get(name, ENV_DEFAULTS.get(name, ""))).strip()  # 층 읽기가 실패해도 기본값으로 돈다


def is_off(name):
    """끄기 스위치가 꺼졌나: 값이 `off` 일 때만 참이다."""
    return env_value(name).lower() == "off"
