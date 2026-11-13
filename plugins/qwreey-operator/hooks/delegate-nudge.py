#!/usr/bin/env python3
"""delegate-nudge: 메인 세션이 한 턴에 코드를 많이 직접 쓰면 백그라운드 서브에이전트 위임을 권한다(info, 막지 않음).

등록: PostToolUse(*) 와 UserPromptSubmit. 메시지 규약: home/.claude/HOOK-MESSAGES.md.
- 센다: 메인(입력에 agent_id 없음)의 Edit·Write·MultiEdit·NotebookEdit 와, 코드 경로에 쓰는 Bash(헤레독 `cat >`, `tee`, `sed -i`, `>` 리다이렉트).
  .md .json .toml .yaml .yml .txt(와 로그·csv 류)와 /tmp 아래 경로는 제외. 헤레독 본문 안의 `>` 는 보지 않는다. 정규식은 거칠다.
- 문턱: 한 턴(사용자 입력 사이)에 쓰기 12회 또는 서로 다른 파일 8개. 넘으면 턴당 한 번 알림.
- 리셋: UserPromptSubmit, Agent·Task·Workflow 호출. 직전 턴이 문턱을 넘었고 Agent 호출이 없었으면 UserPromptSubmit 이 이월 알림을 한 번 낸다.
- 상태: $TMPDIR/claude-qwreey-operator/<session_id>.json (세션당 한 파일, 작다). 끄기: HARNESS_OPERATOR_NUDGE=off.
- 어떤 실패도 조용히 exit 0 한다.
"""
import json
import os
import re
import sys
import tempfile

DEFAULT_WRITES = 12  # 정책: 환경 변수 HARNESS_OPERATOR_NUDGE_WRITES 로 바꾼다
DEFAULT_FILES = 8  # HARNESS_OPERATOR_NUDGE_FILES
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
RESET_TOOLS = {"Agent", "Task", "Workflow"}
NONCODE = {"md", "json", "toml", "yaml", "yml", "txt", "log", "out", "csv", "lock", "tmp"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
REDIRECT = re.compile(r"(?<![\d&>])>>?[ \t]*[\"']?([^\s\"'|;&<>()]+)")
TEE = re.compile(r"\btee\b((?:[ \t]+[^\s|;&<>]+)+)")
SED_I = re.compile(r"\bsed\b[^\n|;&]*?[ \t]-[a-zA-Z]*i\S*([^\n|;&]*)")
QUOTED = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'")
EXT = re.compile(r"\.([A-Za-z0-9]{1,6})$")

NUDGE = (
    "Main has written code {n} times across {m} files this turn without a subagent. If what remains is mostly "
    "implementation, a background subagent frees you to talk with the user; "
    "stay if it is nearly done or needs the user midway."
)
CARRY = (
    "Last turn main wrote code {n} times in {m} files directly. If this prompt continues that work and much "
    "implementation remains, consider handing it to a background subagent; carry on in main if it is nearly done."
)


def is_code(path):
    p = str(path or "").strip().strip("\"'")
    if not p or p.startswith("/dev/"):
        return False
    tmp = tempfile.gettempdir().rstrip("/")
    if p == "/tmp" or p.startswith("/tmp/") or p.startswith(tmp + "/"):
        return False
    m = EXT.search(p)
    return bool(m) and m.group(1).lower() not in NONCODE


def bash_paths(cmd):
    cmd = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd or "")
    # A `>` inside a quoted string (commit message, echo text) is not a redirect.
    found = [m.group(1) for m in REDIRECT.finditer(QUOTED.sub('""', cmd))]
    for m in TEE.finditer(cmd):
        found += [t for t in m.group(1).split() if not t.startswith("-")]
    for m in SED_I.finditer(cmd):
        found += [t for t in m.group(1).split() if not t.startswith("-")]
    return [p.strip("\"'") for p in found if is_code(p)]


def written_paths(data):
    tool, inp = data.get("tool_name"), data.get("tool_input") or {}
    if tool in WRITE_TOOLS:
        p = inp.get("file_path") or inp.get("notebook_path")
        return [p] if is_code(p) else []
    if tool == "Bash":
        return bash_paths(inp.get("command") or "")
    return []


def state_path(sid):
    return os.path.join(tempfile.gettempdir(), "claude-qwreey-operator", re.sub(r"[^\w-]", "", str(sid or "nosession")) + ".json")


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, st):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, path)


def threshold(name, default):
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def message(event, level, body):
    text = '<harness-hook name="delegate-nudge" level="%s">\n%s\n</harness-hook>' % (level, body)
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False)


def handle(data):
    if str(os.environ.get("HARNESS_OPERATOR_NUDGE", "")).strip().lower() in ("off", "0", "no"):
        return ""
    if data.get("agent_id"):
        return ""
    event, tool = data.get("hook_event_name"), data.get("tool_name")
    if event == "PostToolUse" and tool not in WRITE_TOOLS and tool != "Bash" and tool not in RESET_TOOLS:
        return ""  # 대부분의 도구 호출은 상태를 열지 않고 끝낸다
    path = state_path(data.get("session_id"))
    st = load(path)
    out = ""
    if event == "UserPromptSubmit":
        if st.get("crossed"):
            out = message(event, "info", CARRY.format(n=st.get("n", 0), m=len(st.get("files", []))))
        st = {}
    elif tool in RESET_TOOLS:
        st = {}
    else:
        paths = written_paths(data)
        if not paths:
            return ""
        files = set(st.get("files", [])) | set(paths)
        st["n"] = st.get("n", 0) + 1
        st["files"] = sorted(files)
        if not st.get("crossed") and (st["n"] >= threshold("HARNESS_OPERATOR_NUDGE_WRITES", DEFAULT_WRITES)
                                      or len(files) >= threshold("HARNESS_OPERATOR_NUDGE_FILES", DEFAULT_FILES)):
            st["crossed"] = True
            out = message(event, "info", NUDGE.format(n=st["n"], m=len(files)))
    if st or os.path.exists(path):
        save(path, st)
    return out


def main():
    try:
        data = json.load(sys.stdin)
        out = handle(data) if isinstance(data, dict) else ""
    except Exception:
        return 0
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
