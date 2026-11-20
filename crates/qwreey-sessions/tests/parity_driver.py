"""qwreey-sessions 조각 대조 시험(tests/parity_sessions.rs)의 python 쪽. 표준 라이브러리만 쓴다.

stdin: {"repo": <저장소 루트>, "cases": [{"op": ..., "args": ...}, ...]}
stdout: 경우마다 결과 하나씩 담은 JSON 목록. plugins/qwreey-sessions/scripts 의 sllib 을 그대로 불러 부른다.
"""
import json
import os
import sys
from datetime import date


def run(case):
    op, a = case["op"], case.get("args")
    from sllib import config, messages, paths, records_home
    from pathlib import Path

    if op == "defaults":
        return {"defaults": config.DEFAULTS, "user_only": sorted(config.USER_ONLY)}
    if op == "kinds":
        return {"kinds": records_home.BUILTIN_KINDS, "scopes": list(records_home.SCOPE_DIRS),
                "history": list(records_home.HISTORY_CANDIDATES)}
    if op == "fromisoformat":
        out = []
        for s in a:
            try:
                out.append(date.fromisoformat(s).toordinal())
            except ValueError:
                out.append(None)
        return out
    if op == "resolve":
        return [str(Path(p).resolve()) for p in a]
    if op == "project_root":
        return [str(paths.project_root(p)) for p in a]
    if op == "splitext":
        return [os.path.splitext(p)[1] for p in a]
    if op == "join":
        return [os.path.join(x, y) for x, y in a]
    if op == "pathlib_join":
        return [str(Path(x) / y) for x, y in a]
    if op == "int":
        out = []
        for s in a:
            try:
                out.append(str(int(s)))
            except ValueError:
                out.append(None)
        return out
    if op == "snapshot":
        return [records_home.is_snapshot(p, skips) for p, skips in a]
    if op == "under":
        return [records_home.is_under(p, d) for p, d in a]
    if op == "dumps_indent":
        return json.dumps(a, ensure_ascii=False, indent=1)
    if op == "messages":
        return {
            "pending": [messages.pending(*args) for args in a["pending"]],
            "propose": [messages.pending_propose(*args) for args in a["propose"]],
            "gate": [messages.record_read_gate(*args) for args in a["gate"]],
            "started": [messages.started(*args) for args in a["started"]],
            "saved": [messages.saved(*args) for args in a["saved"]],
            "record_read": messages.RECORD_READ,
        }
    raise ValueError("unknown op %r" % op)


def main():
    req = json.load(sys.stdin)
    sys.path.insert(0, os.path.join(req["repo"], "plugins", "qwreey-sessions", "scripts"))
    json.dump([run(c) for c in req["cases"]], sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
