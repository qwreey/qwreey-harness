#!/usr/bin/env python3
"""session-log 훅 입구. 사용: python3 -I hook.py <EventName>  (stdin: 훅 JSON)

훅은 판단만 한다(stat 몇 번, 작은 JSON 몇 개). 요약은 setsid 로 분리한 워커(cli.py flush)가 한다.
어떤 경우에도 exit 0 이고 메인 세션을 막지 않는다.

compact 회차: "세션당 같은 트리거로 1회" 알림의 dedup 키는 (session_id, 회차)다. compact 는 session_id 를 유지하지만
이전 알림을 맥락에서 지운다. 회차는 PreCompact 가 세운 표지를 SessionStart(compact)·PostCompact 중 먼저 온 쪽이
소비하며 1 올린다(순서와 무관, 한 compact 에 한 번). 표지가 없으면 최근 120초 안에 올린 적이 없을 때만 올린다.
규칙은 하네스 `~/.claude/lib/compact_epoch.py` 와 같지만 그 모듈을 import 하지 않는다(하네스 없는 환경에서도 돈다).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sllib import brief, config, messages  # noqa: E402
from sllib.paths import project_root, short_home  # noqa: E402
from sllib.store import Store  # noqa: E402

CLI = os.path.join(HERE, "cli.py")
COMMIT_RX = re.compile(r"(^|[;&|(\s])git(\s+-[Cc]\s+\S+)*\s+commit\b")
HANDOVER_RX = re.compile(r"^\s*/(handover|checkpoint)\b|\b(handover|핸드오버|인계)\b", re.I)


def emit_context(event: str, parts: list[tuple[str, str]]) -> None:
    text = messages.wrap_parts(parts)
    if text:
        json.dump({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, sys.stdout)


def spawn_flush(store: Store, sid: str, transcript: str, trigger: str, force: bool) -> None:
    args = [sys.executable, "-I", CLI, "flush", "--session", sid, "--transcript", transcript,
            "--project", str(store.root), "--trigger", trigger] + (["--force"] if force else [])
    setsid = shutil.which("setsid")
    if setsid:
        args = [setsid, "-f"] + args
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, start_new_session=not setsid, cwd="/")


# ---- compact 회차 ----
def bump_epoch(hs: dict) -> bool:
    now = time.time()
    if hs.get("compact_pending") or now - hs.get("bumped_at", 0) > 120:
        hs["epoch"] = hs.get("epoch", 0) + 1
        hs["bumped_at"] = now
        hs["compact_pending"] = False
        return True
    return False


def once(hs: dict, trigger: str) -> bool:
    """(session, 회차, 트리거) 마다 한 번만 True."""
    key = f"{trigger}@{hs.get('epoch', 0)}"
    done = hs.setdefault("reminded", [])
    if key in done:
        return False
    done.append(key)
    del done[:-50]
    return True


def pending_once(store: Store, hs: dict, trigger: str) -> tuple[str, str]:
    level, line = brief.pending_line(store, trigger)
    return (level, line) if line and once(hs, "pending:" + trigger) else (level, "")


def tick(store: Store, sid: str, transcript: str, hs: dict) -> list[tuple[str, str]]:
    """요약 완료 알림 전달 + 쿨다운 트리거."""
    out = []
    seq = store.notice_seq()
    if seq > hs.get("notice_seq", 0):
        line = brief.saved_line(store, store.notices_after(hs.get("notice_seq", 0)))
        hs["notice_seq"] = seq
        if line:
            out.append(("info", line))
    if transcript and os.path.isfile(transcript):
        ws = store.wstate(sid) if store.wstate_path(sid).exists() else {}
        now = time.time()
        last = max(ws.get("last_run", 0), hs.get("last_spawn", 0))
        grown = os.path.getsize(transcript) - ws.get("offset", 0)
        if now - last >= config.num("SESSION_LOG_COOLDOWN_MIN") * 60 and grown >= config.num("SESSION_LOG_GROW_KB") * 1024:
            spawn_flush(store, sid, transcript, "PostToolUse", False)
            hs["last_spawn"] = now
            out.append(("info", messages.started("periodic", ws.get("line", 0) + 1, None)))
    return out


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    if os.environ.get("SESSION_LOG_NESTED") or config.disabled():
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict) or data.get("agent_id"):
        return  # 서브에이전트 안의 훅은 무시
    sid = data.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
    if not sid:
        return
    transcript = data.get("transcript_path") or ""
    start = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    store = Store(project_root(start))
    hs = store.hstate(sid) if store.exists() else {}
    hs0 = json.dumps(hs, sort_keys=True)

    if event == "SessionStart":
        source = data.get("source", "startup")
        parts = []
        if source == "compact":
            bump_epoch(hs)
            rids = [r for r, e in store.index().items() if e.get("session_id") == sid] if store.exists() else []
            if rids:
                parts.append(("info", messages.after_compact(short_home(store.record_path(sorted(rids)[-1])), short_home(store.records))))
        elif store.exists():
            h = brief.handover(store, sid, source)
            if h:
                parts.append(("info", h))
        if store.exists():
            parts.append(pending_once(store, hs, "session_start"))
            errs = store.errors_since(hs.get("errors_checked", time.time() - 86400))
            hs["errors_checked"] = time.time()
            if errs:
                parts.append(("warn", messages.failed(errs, short_home(store.state / "errors.log"))))
            if source != "compact" and store.index():
                parts.append(("info", messages.records_hint(short_home(store.records))))
            seq = store.notice_seq()
            if seq > hs.get("notice_seq", 0):  # 아직 전하지 않은 요약 완료 알림
                parts.insert(0, ("info", brief.saved_line(store, store.notices_after(hs.get("notice_seq", 0)))))
            hs["notice_seq"] = seq
        emit_context(event, parts)

    elif event in ("PostToolUse", "UserPromptSubmit"):
        parts = tick(store, sid, transcript, hs)
        if event == "UserPromptSubmit" and HANDOVER_RX.search(str(data.get("prompt", ""))[:400]):
            parts.append(pending_once(store, hs, "handover"))
        emit_context(event, parts)

    elif event == "PreToolUse":
        tool, inp = data.get("tool_name"), data.get("tool_input") or {}
        trig = None
        if tool == "Bash" and COMMIT_RX.search(str(inp.get("command", ""))):
            trig = "commit"
        elif tool == "Skill" and re.search(r"handover|checkpoint", str(inp.get("skill", "")), re.I):
            trig = "handover"
        if trig and store.exists():
            emit_context(event, [pending_once(store, hs, trig)])

    elif event == "PreCompact":
        hs["compact_pending"] = True
        trig = data.get("trigger") or "auto"
        if transcript:
            store.ensure()
            spawn_flush(store, sid, transcript, f"PreCompact({trig})", True)
        if once(hs, "precompact"):
            text = brief.precompact(store, sid, transcript) if transcript else ""
            plv, p = brief.pending_line(store, "precompact")
            out = messages.wrap_parts([("warn", text), (plv, p)])
            if out:
                sys.stdout.write(out + "\n")

    elif event == "PostCompact":
        bump_epoch(hs)
        summ = data.get("compact_summary")
        if summ:
            store.ensure()
            (store.state / f"{sid}.compact-{hs.get('epoch', 0)}.md").write_text(summ, encoding="utf-8")

    elif event == "SessionEnd":
        if transcript:
            store.ensure()
            spawn_flush(store, sid, transcript, "SessionEnd", True)

    if json.dumps(hs, sort_keys=True) != hs0:
        store.save_hstate(sid, hs)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 훅은 절대 세션을 막지 않는다
        try:
            d = config.home()
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "hook-errors.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {sys.argv[1:]} {type(e).__name__}: {e}\n")
        except Exception:
            pass
    sys.exit(0)
