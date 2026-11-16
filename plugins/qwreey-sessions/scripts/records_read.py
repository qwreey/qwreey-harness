#!/usr/bin/env python3
"""기록 읽기 훅. 사용: python3 -I records_read.py [PreToolUse|PostToolUse]  (인자 없으면 PostToolUse)

기록은 그 시점의 스냅숏이라 낡았을 수 있고, 큰 기록을 통째로 읽으면 맥락을 크게 차지한다.
- PreToolUse(Read): 기록(외부 저장소의 세션 기록, 저장소 보관 폴더, 어느 저장소든 `.claude/` 의 스냅숏 폴더)을 offset, limit
  없이 Read 하는데 파일이 SESSION_LOG_READ_GATE_KB(기본 32KiB) 이상이면 deny 하고 부분 읽기를 안내한다. 막는 것은 그 호출뿐이라
  통째가 필요하면 offset/limit 으로 나눠 읽으면 된다. 살아 있는 문서(plan, base, research, archive), CLAUDE.md, 코드는 막지 않는다.
- PostToolUse(Read|Grep): 세션 기록(외부 저장소, 저장소 보관 폴더)을 읽으면 스냅숏 경고를 (session_id, agent_id 또는 main,
  compact 회차)마다 한 번 싣는다. 큰 기록 통째 읽기는 PreToolUse 가 이미 막았으므로 여기서 다시 말하지 않는다.
모든 Read 에서 불리므로 문자열 검사를 먼저 하고 stat 은 기록 경로일 때만 한다. 오류는 모두 통과(fail-open), 항상 exit 0.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Read 가 offset/limit 으로 나눠 읽지 못하는 파일(그림은 통째로, PDF 는 pages 로 읽는다). 막으면 읽을 길이 없다.
NOT_TEXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".ipynb"})


def in_records_home(data: dict, path: str) -> bool:
    """저장소에 정해 둔 보관 폴더(.claude/session-log.json 의 records_home) 아래인가."""
    from sllib import records_home
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
    if not root or not path.startswith(os.path.normpath(root) + os.sep):
        return False
    home = records_home.home_rel(root)
    return bool(home) and records_home.is_under(path, os.path.join(os.path.normpath(root), home))


def gate(data: dict, inp: dict, path: str) -> None:
    if data.get("tool_name") != "Read" or inp.get("offset") is not None or inp.get("limit") is not None or inp.get("pages"):
        return
    if os.path.splitext(path)[1].lower() in NOT_TEXT:
        return
    from sllib import config, messages, records_home
    if config.disabled() or config.read_gate_off():
        return
    store = records_home.is_under(path, str(config.home()))
    config_dirs = (str(config.claude_config_dir()), os.path.join(os.path.expanduser("~"), ".claude"))
    if not store and not records_home.is_snapshot(path, config_dirs) and not in_records_home(data, path):
        return
    gate_kb = config.num("SESSION_LOG_READ_GATE_KB")
    if gate_kb <= 0:
        return
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size < gate_kb * 1024:
        return
    import shutil
    text = messages.record_read_gate(int(size // 1024), int(gate_kb), path, coderag=not store and bool(shutil.which("coderag")))
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": messages.wrap(text, "action", data.get("session_id"))}}, sys.stdout)


def notice(data: dict, path: str) -> None:
    from sllib import config, messages, records_home
    if config.disabled():
        return
    if not records_home.is_under(path, str(config.home())) and not in_records_home(data, path):
        return
    sid = data.get("session_id") or ""
    if not sid:
        return
    import compact_epoch
    marker = compact_epoch.state_path("qwreey-sessions", "claude-sessions-records-read", sid, data.get("agent_id"))
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return  # 이미 알렸거나 표식을 못 만든다: 매번 나가는 것보다 한 번 빠지는 편이 낫다
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": messages.wrap(messages.RECORD_READ, "info", sid)}}, sys.stdout)


def main(event: str) -> None:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    inp = data.get("tool_input") if isinstance(data, dict) else None
    if not isinstance(inp, dict):
        return
    path = inp.get("file_path") or inp.get("path") or ""
    if not isinstance(path, str) or not path.startswith("/") or os.environ.get("SESSION_LOG_NESTED"):
        return
    path = os.path.normpath(path)
    if event == "PreToolUse":
        gate(data, inp, path)
    else:
        notice(data, path)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "PostToolUse")
    except Exception:
        pass
    sys.exit(0)
