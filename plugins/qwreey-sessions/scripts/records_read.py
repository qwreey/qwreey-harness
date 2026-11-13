#!/usr/bin/env python3
"""PostToolUse(Read|Grep): 세션 기록을 읽었을 때 스냅샷 경고를 한 번 싣는다. 사용: python3 -I records_read.py

기록 읽기는 무겁고 느려서 특정한 필요가 있을 때만 해야 하고, 기록은 그 시점의 스냅샷이라 낡았을 수 있다.
모든 Read 에서 불리므로 경로를 문자열로만 먼저 가린다: 외부 저장소 아래이거나 이 저장소의 보관 폴더 아래가 아니면 바로 끝난다.
dedup 은 (session_id, agent_id 또는 main, compact 회차) 마다 한 번(스냅샷 경고). 큰 기록을 offset 과 limit 없이 읽으면
그때마다 검색 먼저 안내를 한다(그 읽기 자체가 낭비를 반복하는 것이라서). 항상 exit 0.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main() -> None:
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
    from sllib import config, messages, records_home  # 가볍다: 표준 라이브러리만
    if config.disabled():
        return
    path = os.path.normpath(path)
    hit = records_home.is_under(path, str(config.home()))
    if not hit:
        root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
        if not root or not path.startswith(os.path.normpath(root) + os.sep):
            return
        home = records_home.home_rel(root)
        if not home or not records_home.is_under(path, os.path.join(os.path.normpath(root), home)):
            return
    sid = data.get("session_id") or ""
    if not sid:
        return
    out = []
    large = False
    if data.get("tool_name") == "Read" and inp.get("offset") is None and inp.get("limit") is None:
        try:
            kb = os.path.getsize(path) / 1024
        except OSError:
            kb = 0
        if kb > config.num("SESSION_LOG_READ_WARN_KB"):
            large = True
            out.append(messages.RECORD_READ_LARGE.format(kb=int(kb)))
    import compact_epoch
    marker = compact_epoch.state_path("qwreey-sessions", "claude-sessions-records-read", sid, data.get("agent_id"))
    first = False
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        first = True
    except FileExistsError:
        pass
    except OSError:
        first = not large  # 표식을 못 만들면 한 번이 아니라 매번 나가는 것을 피한다
    if first and not large:
        out.append(messages.RECORD_READ)
    if out:
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                          "additionalContext": messages.wrap("\n".join(out), "info")}}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
