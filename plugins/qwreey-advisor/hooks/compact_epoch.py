"""compact 회차: 플러그인마다 자기 회차를 갖는다. 표준 라이브러리만 쓴다.
정본: plugins/q/scripts/compact_epoch.py. qwreey-advisor/hooks, qwreey-conventions/hooks 의 사본은 이 파일과 바이트가 같아야 한다
(tests 가 비교한다). 고칠 때는 정본만 고치고 사본에 복사한다.

왜: "세션당 한 번 알린다" 류 훅은 session_id 로 dedup 하는데, compact 는 session_id 를 유지하면서 요약으로 이전 알림을 맥락에서
지운다. 그래서 dedup 단위는 (session_id, agent_id 또는 main, 회차)다. 회차 파일은 $TMPDIR/claude-<plugin>-epoch/<sid> 이고
플러그인끼리 공유하지 않는다(다른 플러그인·사용자 설정의 훅과 얽히지 않게).

언제 올리나: PreCompact(manual·auto). 같은 이벤트의 훅은 병렬이라 순서가 없으므로, 올리는 훅과 읽는 훅이 같은 이벤트에 있으면
경합한다. PreCompact 는 compact 보다 먼저 불리고 SessionStart(compact)·PostCompact 는 그 뒤라서, 읽는 쪽은 항상 올라간 값을 본다.
compact 가 취소되면 회차만 하나 올라 알림이 한 번 더 나간다(싸다). 서브에이전트(agent_id 가 있음)의 PreCompact 는 부모 맥락을
지우지 않으므로 올리지 않는다.

PreCompact 에 등록하는 법(자체 훅이 없는 플러그인): python3 -I compact_epoch.py <plugin>  (stdin: 훅 JSON). 항상 exit 0.
"""
import json
import os
import re
import sys
import tempfile


def _sid(value):
    return re.sub(r"[^\w-]", "", str(value or "nosession"))


def _plugin(plugin):
    return re.sub(r"[^\w-]", "", str(plugin))


def _epoch_path(plugin, session_id):
    return os.path.join(tempfile.gettempdir(), "claude-%s-epoch" % _plugin(plugin), _sid(session_id))


def epoch(plugin, session_id):
    try:
        with open(_epoch_path(plugin, session_id)) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def bump(plugin, session_id):
    """새 회차를 시작한다. 새 회차를 돌려준다. 쓰기 실패는 조용히 넘긴다(훅은 세션을 막지 않는다)."""
    n = epoch(plugin, session_id) + 1
    p = _epoch_path(plugin, session_id)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = "%s.%d.tmp" % (p, os.getpid())
        with open(tmp, "w") as f:
            f.write(str(n))
        os.replace(tmp, p)
    except OSError:
        pass
    return n


def bump_for_precompact(plugin, data):
    """PreCompact 페이로드(dict)를 받아 메인 대화의 compact 일 때만 올린다."""
    if isinstance(data, dict) and data.get("session_id") and not data.get("agent_id"):
        return bump(plugin, data["session_id"])
    return None


def state_path(plugin, namespace, session_id, agent_id=None):
    """이 회차의 dedup 상태 파일 경로(디렉터리를 만든다): $TMPDIR/<namespace>/<sid>.c<회차>[.a<agent_id>].json

    서브에이전트 안의 훅은 부모의 session_id 와 agent_id 를 받는다. 그래서 키는 (session_id, agent_id 또는 main, 회차)다:
    서브에이전트가 "회차당 한 번" 알림을 써 버려 메인 대화의 몫을 없애면 안 되고 그 반대도 마찬가지다."""
    d = os.path.join(tempfile.gettempdir(), namespace)
    os.makedirs(d, exist_ok=True)
    who = ".a%s" % _sid(agent_id) if agent_id else ""
    return os.path.join(d, "%s.c%d%s.json" % (_sid(session_id), epoch(plugin, session_id), who))


if __name__ == "__main__":
    try:
        bump_for_precompact(sys.argv[1], json.load(sys.stdin))
    except Exception:
        pass
    sys.exit(0)
