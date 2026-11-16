"""qwreey-conventions 훅의 환경 읽기. tools/tests/test-coderag-rules-parity.py 가 rules_inject.py 와 함께 임시 팩 디렉터리에 복사해 쓴다.

이 플러그인 훅의 공용 작은 도구: 끄기 스위치(환경 변수 또는 harness.env 층)와 설정 위치. 표준 라이브러리만 쓴다.

harness.env 층은 옆의 harness_env.py(하네스 정본의 사본)의 load_layers 로 읽는다:
사용자 ~/.claude/harness.env < 저장소 .claude/harness.env < 저장소 .claude/harness.local.env < 환경 변수.
저장소는 $CLAUDE_PROJECT_DIR 다. 읽기 실패는 "켜짐"으로 본다(훅은 세션을 막지 않는다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다

_VALS = None


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def _layers():
    global _VALS
    if _VALS is None:
        try:
            import harness_env
            _VALS = harness_env.load_layers()
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
