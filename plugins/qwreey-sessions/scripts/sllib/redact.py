"""세션 기록 밖으로 나가는 글에서 하네스 nonce 를 지운다. 기록을 쓰는 곳은 모두 이 함수를 거친다.

왜: 세션은 며칠씩 이어지므로 커밋된 기록에 적힌 nonce 는 아직 살아 있을 수 있다. 그 값을 아는 사람은 이 세션의 훅 태그를
흉내 낼 수 있다. 요약기는 트랜스크립트에 실린 태그와 규칙 줄을 옮겨 적을 수 있으므로 쓰는 순간에 지운다.
규칙(nonce="<hex>" 를 nonce="redacted" 로, 규칙 줄은 통째로, session_id 를 주면 그 세션의 nonce 값 자체도)은
harness_nonce.redact_text 에 있다.
"""
from __future__ import annotations

import os
import sys


def redact(text, session_id=None):
    try:
        import harness_nonce
    except ImportError:
        # python3 -I 로 실행한 cli.py 는 스크립트 디렉터리가 sys.path 에 없다
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import harness_nonce
    return harness_nonce.redact_text(text, session_id)
