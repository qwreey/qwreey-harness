"""qwreey-conventions 훅의 환경 읽기. tools/tests/test-coderag-rules-parity.py 가 rules_inject.py 와 함께 임시 팩 디렉터리에 복사해 쓴다.

이 플러그인 훅의 공용 작은 도구: 끄기 스위치(환경 변수 또는 harness.env)와 설정 위치. 표준 라이브러리만 쓴다.

harness.env 는 `KEY=VALUE` 줄이고 같은 이름의 환경 변수가 이긴다. 플러그인은 하네스 lib 를 import 하지 않으므로(각자 따로 설치)
필요한 부분만 여기서 직접 읽는다. 읽기 실패는 "켜짐"으로 본다(훅은 세션을 막지 않는다).
"""
import os


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def env_value(name):
    v = os.environ.get(name)
    if v is not None:
        return v.strip()
    try:
        with open(os.path.join(config_dir(), "harness.env"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(name + "="):
                    return line[len(name) + 1:].strip().strip("'\"")
    except OSError:
        pass
    return ""


def is_off(name):
    return env_value(name).lower() == "off"
