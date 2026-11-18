#!/usr/bin/env python3
"""아무것도 하지 않는 자리 표시: 입력을 읽고 출력 없이 exit 0. 답변 언어 검사는 qwreey-reply-language 플러그인이 한다.

왜 남기나: 이 플러그인을 다시 싣기 전의 세션은 옛 hooks.json 대로 이 경로를 UserPromptSubmit, Stop, PostToolBatch 에서 계속 부른다.
파일이 없으면 그 세션마다 훅 오류가 난다. 모든 세션이 플러그인을 다시 실은 뒤 지운다(HUMAN_TODO).
"""
import sys

try:
    sys.stdin.read()
except Exception:
    pass
sys.exit(0)
