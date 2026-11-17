#!/usr/bin/env python3
"""workspace 게이트. 사용: python3 -I workspace_gate.py <PreToolUse|PostToolUse|UserPromptExpansion>  (stdin: 훅 JSON)

규칙(qwreey-workspace 규약 context/ambient.md): 이 세션의 저장소가 아닌 다른 git 저장소는 읽기 전용이고 고치기 전에 묻는다.
- 다른 저장소: 대상 경로가 CLAUDE_PROJECT_DIR(없으면 cwd)의 저장소(worktree 는 본 저장소로 합친다) 밖이고 위로 올라가 `.git` 을
  만나는 것(wslib.Scope). 목록은 쓰지 않는다. 임시 폴더, ~/.cache 와 사용자가 뺀 저장소(HARNESS_WORKSPACE_EXCLUDE)는 다른 저장소가 아니다.
- 쓰기(Edit|Write|MultiEdit|NotebookEdit, 쓰기로 분류된 Bash)가 다른 저장소를 건드리고, (세션, agent_id, compact 회차)에
  qwreey-workspace:workspace 스킬 로드 표시가 없으면 deny(level=action). PreToolUse additionalContext 는 도구가 실행된 뒤에 들어오므로
  알림만으로는 첫 쓰기를 막지 못한다(.claude/audit/31).
- 읽기(Read|Grep|Glob, 그 밖의 Bash)는 compact 회차마다 한 번 info 만 낸다.
- 로드 표시: PostToolUse(Skill) 의 tool_input.skill 이 `qwreey-workspace:workspace`(플러그인 스킬은 `<플러그인>:<스킬>`, .claude/audit/31 probes.md §1),
  슬래시로 치면 UserPromptExpansion 의 command_name.
- compact 회차: compact_epoch.py(qwreey-workspace 자기 것, $TMPDIR/claude-qwreey-workspace-epoch/<sid>)를 읽기만 한다. 올리는 쪽은 PreCompact 훅(compact_epoch.py qwreey-workspace)이다.
- 예외는 통과(fail-open). deny 는 $TMPDIR/claude-workspace-gate/deny.log 에 남긴다.
- 끄기: HARNESS_WORKSPACE_GATE=off(옵션 harness_workspace_gate, 사용자 harness.env, 환경 변수. 저장소 층은 못 바꾼다).
- 비용: Edit, Read, Bash 마다 돈다. 이 세션 저장소 안 경로만 만지는 호출은 경로마다 위로 걸으며 `.git` 을 stat 할 뿐 설정도 상태 파일도
  읽지 않는다. 설정, nonce, compact 회차 모듈과 tempfile 은 다른 저장소 후보가 나온 뒤에만 읽는다.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wslib  # noqa: E402

NS = "claude-workspace-gate"
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
SKILL_RX = re.compile(r"^(?:[\w.-]+:)?workspace$")

DENY = ('<harness-hook name="workspace-gate" level="action"{nonce}>\n'
        "This changes the repo `{x}`, which is outside this session's repo. Repos other than this session's are "
        "read-only unless the user approves a change; other sessions may be working there, and `.claude/worktrees/*` "
        "entries must not be deleted before checking the lock file and live sessions. "
        "Load the qwreey-workspace:workspace skill (Skill tool), then retry; if the user has not approved this change, ask first.\n"
        "</harness-hook>")
READ_INFO = ('<harness-hook name="workspace-gate" level="info"{nonce}>\n'
             "Reading `{x}` is fine; changing it needs the user's approval and the qwreey-workspace:workspace skill first.\n"
             "</harness-hook>")


def _sid(s) -> str:
    return re.sub(r"[^\w-]", "", str(s or "nosession"))


def _epoch(sid) -> int:
    import compact_epoch
    return compact_epoch.epoch("qwreey-workspace", sid)


def _nonce(data) -> str:
    import harness_nonce
    return harness_nonce.attr(data.get("session_id"))


def _state_dir() -> str:
    import tempfile  # import 가 10 ms 가까이 든다. 다른 저장소를 건드릴 때만 낸다
    return os.path.join(tempfile.gettempdir(), NS)


def state_file(data) -> str:
    d = _state_dir()
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
    import time
    try:
        d = _state_dir()
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


def judge(data, scope):
    """(kind, X, 설명). X 는 다른 저장소 루트. 다른 저장소를 건드리지 않으면 (None, None, "")."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd") or scope.project
    if tool == "Bash":
        k, x = wslib.classify_bash(ti.get("command") or "", cwd, scope)
        return k, x, (ti.get("command") or "")[:200]
    kind = "write" if tool in WRITE_TOOLS else "read" if tool in READ_TOOLS else None
    if not kind:
        return None, None, ""
    for p in paths_of(tool, ti, cwd):
        x = scope.sibling(p)
        if x:
            return kind, x, f"{tool} {p}"
    return None, None, ""


def pre(data) -> None:
    tool = data.get("tool_name") or ""
    if tool != "Bash" and tool not in WRITE_TOOLS and tool not in READ_TOOLS:
        return
    project = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "")
    scope = wslib.Scope(project, load=lambda: wslib.load_env(data.get("cwd")))
    kind, x, what = judge(data, scope)
    if not kind or wslib.is_off("HARNESS_WORKSPACE_GATE", scope.settings()):
        return
    sp = state_file(data)
    st = read_state(sp)
    if kind == "write":
        if st.get("loaded"):
            return
        log_deny(data, x, what)
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": DENY.format(x=wslib.shown(x), nonce=_nonce(data))}}, sys.stdout)
        return
    if st.get("loaded") or st.get("warned"):
        return
    st["warned"] = True
    write_state(sp, st)
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": READ_INFO.format(x=wslib.shown(x), nonce=_nonce(data))}}, sys.stdout)


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
