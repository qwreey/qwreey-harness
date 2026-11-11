#!/usr/bin/env python3
"""workspace 게이트. 사용: python3 -I workspace_gate.py <PreToolUse|PostToolUse|UserPromptExpansion>  (stdin: 훅 JSON)

규칙(사용자 CLAUDE.md): 이 세션의 저장소가 아닌 `HARNESS_WORKSPACE/<X>` 는 읽기 전용이고 고치기 전에 묻는다.
- 쓰기(Edit|Write|MultiEdit|NotebookEdit, 쓰기로 분류된 Bash)가 형제 저장소를 건드리고, (세션, agent_id, compact 회차)에
  q:workspace 스킬 로드 표시가 없으면 deny(level=action). PreToolUse additionalContext 는 도구가 실행된 뒤에 들어오므로
  알림만으로는 첫 쓰기를 막지 못한다(audit/31).
- 읽기(Read|Grep|Glob, 그 밖의 Bash)는 compact 회차마다 한 번 warn 만 한다.
- 로드 표시: PostToolUse(Skill) 의 tool_input.skill 이 `q:workspace`(플러그인 스킬은 `<플러그인>:<스킬>`, audit/31 probes.md §1),
  슬래시로 치면 UserPromptExpansion 의 command_name.
- compact 회차: compact_epoch.py(q 자기 것, $TMPDIR/claude-q-epoch/<sid>)를 읽기만 한다. 올리는 쪽은 PreCompact 의 hook.py 다.
- 예외는 통과(fail-open). deny 는 $TMPDIR/claude-workspace-gate/deny.log 에 남긴다.
- 끄기: HARNESS_WORKSPACE_GATE=off(환경 변수 또는 harness.env), HARNESS_WORKSPACE 가 비어 있어도 꺼진다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compact_epoch  # noqa: E402
import wslib  # noqa: E402

NS = "claude-workspace-gate"
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
SKILL_RX = re.compile(r"^(?:[\w.-]+:)?workspace$")

DENY = ('<harness-hook name="workspace-gate" level="action">\n'
        "This changes the sibling repo `{x}`, which is outside this session's repo. Repos other than this session's are "
        "read-only unless the user approves a change; other sessions may be working there, and `.claude/worktrees/*` "
        "entries must not be deleted before checking the lock file and live sessions. "
        "Load the q:workspace skill (Skill tool), then retry; if the user has not approved this change, ask first.\n"
        "</harness-hook>")
WARN = ('<harness-hook name="workspace-gate" level="warn">\n'
        "This touches the sibling repo `{x}`. Repos other than this session's are read-only unless the user approves a "
        "change, and other sessions may be working there. The q:workspace skill lists the repos and has the live-session "
        "check; load it before changing anything there.\n"
        "</harness-hook>")


def _sid(s) -> str:
    return re.sub(r"[^\w-]", "", str(s or "nosession"))


def _epoch(sid) -> int:
    return compact_epoch.epoch("q", sid)


def state_file(data) -> str:
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    who = f".a{_sid(data['agent_id'])}" if data.get("agent_id") else ""
    return os.path.join(d, f"{_sid(data.get('session_id'))}.c{_epoch(data.get('session_id'))}{who}.json")


def read_state(p) -> dict:
    try:
        return json.load(open(p))
    except Exception:
        return {}


def write_state(p, st) -> None:
    try:
        json.dump(st, open(p, "w"))
    except OSError:
        pass


def log_deny(data, x, what) -> None:
    try:
        d = os.path.join(tempfile.gettempdir(), NS)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "deny.log"), "a") as f:
            f.write(f"{time.strftime('%F %T')} sid={data.get('session_id')} agent={data.get('agent_id')} repo={x} {what}\n")
    except OSError:
        pass


def paths_of(tool, ti, cwd):
    out = []
    for k in ("file_path", "notebook_path", "path"):
        if ti.get(k):
            out.append(str(ti[k]))
    for k in ("pattern", "glob"):
        v = str(ti.get(k) or "")
        if tool in READ_TOOLS and (v.startswith(("/", "~"))):
            out.append(v)
    return [wslib.norm(p, cwd) for p in out]


def judge(data, ws, project):
    """(kind, X, 설명). 형제 저장소를 건드리지 않으면 (None, None, "")."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd") or project
    if tool == "Bash":
        k, x = wslib.classify_bash(ti.get("command") or "", cwd, ws, project)
        return k, x, (ti.get("command") or "")[:200]
    kind = "write" if tool in WRITE_TOOLS else "read" if tool in READ_TOOLS else None
    if not kind:
        return None, None, ""
    for p in paths_of(tool, ti, cwd):
        x = wslib.sibling_of(p, ws, project)
        if x:
            return kind, x, f"{tool} {p}"
    return None, None, ""


def pre(data) -> None:
    vals = wslib.load_env()
    ws = wslib.workspace(vals)
    if not ws or wslib.setting("HARNESS_WORKSPACE_GATE", vals).strip().lower() == "off":
        return
    project = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "")
    kind, x, what = judge(data, ws, project)
    if not kind:
        return
    sp = state_file(data)
    st = read_state(sp)
    if kind == "write":
        if st.get("loaded"):
            return
        log_deny(data, x, what)
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": DENY.format(x=x)}}, sys.stdout)
        return
    if st.get("loaded") or st.get("warned"):
        return
    st["warned"] = True
    write_state(sp, st)
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": WARN.format(x=x)}}, sys.stdout)


def mark_loaded(data) -> None:
    sp = state_file(data)
    st = read_state(sp)
    st["loaded"] = True
    write_state(sp, st)


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
        if event == "PreToolUse":
            pre(data)
        elif event == "PostToolUse":
            if data.get("tool_name") == "Skill" and SKILL_RX.match(str((data.get("tool_input") or {}).get("skill") or "")):
                mark_loaded(data)
        elif event == "UserPromptExpansion":
            if SKILL_RX.match(str(data.get("command_name") or "")):
                mark_loaded(data)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
