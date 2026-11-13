#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) 알림: auto memory 에 쓴 내용이 저장소 지식으로 보이면 알린다.

막지 않는다(decision 없음). additionalContext(level=warn)만 주입한다.

왜: auto memory(~/.claude/projects/<키>/memory/)는 이 컴퓨터에만 있다. 저장소에 실려야 할 지식(경로, 빌드·테스트 명령, 규약, 함정)이
  메모리에만 들어가면 다른 clone·다른 기기·동료에게 가지 않고, 폴더를 옮기면 키가 바뀌어 끊긴다(.claude/audit/23).
실측(2.1.316): 메모리 쓰기는 일반 Write 도구라 이 훅이 file_path 를 받는다. MEMORY.md 도 Write 로 쓰인다.
동작: file_path 가 auto memory 디렉터리 안(기본 <config>/projects/*/memory/ 또는 autoMemoryDirectory)일 때만, MEMORY.md 가 아닌 파일의
  디스크 내용을 memory_signals.py 로 분류한다. type: user 는 항상 조용하다. 환경 표현(sandbox, 이 기기 등)은 점수를 깎는다.
알림 중복: 같은 파일은 (session_id, 호출한 쪽, compact 회차)당 한 번. compact_epoch.py(이 플러그인 자기 회차)의 state_path 를 쓴다.
끄기: 환경 변수 MEMORY_PLACEMENT=off
"""
import json
import os
import sys
from pathlib import Path

NS = "claude-memory-placement"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import harness_nonce  # noqa: E402
import memory_signals  # noqa: E402


def seen_before(data, file_path):
    """True if this file was already reported in this (session, caller, compact epoch). Records it otherwise."""
    try:
        p = compact_epoch.state_path("qwreey-conventions", NS, data.get("session_id"), data.get("agent_id"))
    except Exception:
        return False
    try:
        state = json.loads(Path(p).read_text())
    except (OSError, ValueError):
        state = {}
    if file_path in state:
        return True
    state[file_path] = 1
    try:
        Path(p).write_text(json.dumps(state))
    except OSError:
        pass
    return False


def message(name, evidence, session_id=None):
    return (
        f'<harness-hook name="memory-placement" level="warn"{harness_nonce.attr(session_id)}>\n'
        f"Memory file {name} looks like repo knowledge ({evidence}). Auto memory is machine-local: it does not travel with the repo, "
        "to another clone or machine, or to teammates, and it detaches if the folder moves. "
        "Before continuing, propose moving the repo-specific part to the repo (CLAUDE.md, .claude/rules/<topic>.md, or docs/), "
        "or to the coderag project layer if the project uses it; toolkit-general facts belong in a shared pack, company-wide facts in coderag team. "
        "Ask the user before editing repo files; keep only personal preferences and this-machine/environment notes in memory. "
        "If this note is in fact personal or environment-specific, say so in one line and continue.\n"
        "</harness-hook>"
    )


def main():
    if os.environ.get("MEMORY_PLACEMENT") == "off":
        return 0
    try:
        data = json.load(sys.stdin)
        fp = (data.get("tool_input") or {}).get("file_path")
        if not fp or Path(fp).name == "MEMORY.md" or not fp.endswith(".md"):
            return 0
        ms = memory_signals
        if not ms.is_memory_path(fp, data.get("cwd")):
            return 0
        text = Path(fp).read_text(errors="replace")[:200_000]
        verdict, _score, sig, _type = ms.classify(text)
        if verdict != "repo" or seen_before(data, fp):
            return 0
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message(Path(fp).name, ms.describe(sig), data.get("session_id"))}}
        print(json.dumps(out))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
