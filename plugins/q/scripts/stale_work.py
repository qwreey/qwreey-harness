#!/usr/bin/env python3
"""오래 방치된 백그라운드 작업 알림. 사용: python3 -I stale_work.py  (stdin: 훅 JSON, 이벤트는 hook_event_name)

출처: Stop·SubagentStop 의 background_tasks. 실측한 필드(/tmp/sa-probe/hooks.jsonl 캡처): 항목은
{id, type: subagent|workflow, status: running, description, agent_type | name} 뿐이다. 시작 시각·출력 경로·pid 는 없다.
그래서 나이는 "이 훅이 처음 본 때"부터 센다(Stop 이 도는 동안만 관측 가능). 진척 신호는 서브에이전트의 트랜스크립트
(<메인 트랜스크립트 디렉터리>/<sid>/subagents/**/agent-<id>.jsonl) 의 크기·mtime 이다. 신호를 못 찾는 작업(workflow 등)은
멈춤 판정을 하지 않고 오래 실행만 본다(진척을 모르는 채로 멈췄다고 말하지 않는다). CPU 는 pid 가 없어 보지 못한다. monitor 는 뺀다.

판정(분 단위, 환경 변수로 바꿀 수 있다):
- 멈춤(stalled): 진척 없이 HARNESS_Q_STALE_IDLE_MIN(15) 이상이고 나이가 HARNESS_Q_STALE_AGE_MIN(30) 이상. 모델 warn + 사용자 줄.
- 오래 실행(long): 멈춤이 아니고 나이가 HARNESS_Q_STALE_LONG_MIN(120) 이상. 모델 info + 사용자 줄.
문구는 확정하지 않는 질문형("멈췄거나 대기 중일 수 있음")이다. dedup 은 (세션, task id, 상태)마다 1회.

전달: Stop·SubagentStop 이 판정해 상태 파일($TMPDIR/claude-q-stale/<sid>.json)에 쌓고, Stop(메인)이 사용자 줄을 systemMessage 로 내고,
UserPromptSubmit 이 모델 문구를 additionalContext 로 준다. 실패는 삼킨다(fail-open). 끄기: HARNESS_Q_STALE=off.
"""
import glob
import json
import os
import re
import sys
import tempfile
import time

TAG = "stale-work"


def env_min(name, default):
    try:
        return float(os.environ.get(name, default)) * 60
    except ValueError:
        return default * 60


def state_file(sid):
    return os.path.join(tempfile.gettempdir(), "claude-q-stale", re.sub(r"[^\w-]", "", str(sid or "nosession")) + ".json")


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        if isinstance(v, dict):
            return v
    except (OSError, ValueError):
        pass
    return {"tasks": {}, "model": [], "user": []}


def save(path, st):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, path)


def signal(task, data):
    """진척 신호 [크기, mtime] 또는 None(알 수 없음)."""
    tid = re.sub(r"[^\w-]", "", str(task.get("id") or ""))
    paths = []
    for key in ("output_file", "outputFile", "output_path"):  # 캡처에는 없지만 있으면 가장 직접적인 신호
        if isinstance(task.get(key), str):
            paths.append(task[key])
    tp = data.get("transcript_path")
    if tp and tid and task.get("type") == "subagent":
        base = os.path.join(os.path.splitext(tp)[0], "subagents")
        paths.append(os.path.join(base, "agent-%s.jsonl" % tid))
        paths += glob.glob(os.path.join(base, "workflows", "*", "agent-%s.jsonl" % tid))
    for p in paths:
        try:
            s = os.stat(p)
            return [s.st_size, s.st_mtime]
        except OSError:
            continue
    return None


def minutes(sec):
    return max(1, int(sec // 60))


def label(task):
    d = str(task.get("description") or task.get("name") or "")[:60]
    return "%s \"%s\" (id %s)" % (task.get("type", "task"), d, str(task.get("id", ""))[:12])


def evaluate(st, data, now):
    """상태 파일을 갱신하고 새로 알릴 (모델 문구, 사용자 줄)을 st 의 큐에 쌓는다."""
    bg = data.get("background_tasks")
    if not isinstance(bg, list):
        return
    idle_s, age_s, long_s = env_min("HARNESS_Q_STALE_IDLE_MIN", 15), env_min("HARNESS_Q_STALE_AGE_MIN", 30), env_min("HARNESS_Q_STALE_LONG_MIN", 120)
    me = data.get("agent_id")  # SubagentStop 의 목록에는 방금 끝난 자기 자신이 아직 있다
    live = [t for t in bg if isinstance(t, dict) and t.get("status") == "running" and t.get("type") != "monitor"
            and t.get("id") and t.get("id") != me]
    tasks = st.setdefault("tasks", {})
    for gone in [k for k in tasks if k not in {t["id"] for t in live}]:
        del tasks[gone]
    for t in live:
        rec = tasks.setdefault(t["id"], {"first": now, "prog": now, "sig": None, "done": []})
        sig = signal(t, data)
        if sig is not None and sig != rec.get("sig"):
            # 처음 본 신호는 파일 mtime 을 진척 시각으로 쓴다(이미 오래 조용한 작업을 늦게 발견한 경우)
            rec["prog"] = now if rec.get("sig") is not None else min(now, sig[1])
        rec["sig"] = sig
        age, idle = now - rec["first"], now - rec["prog"]
        if sig is not None and idle >= idle_s and age >= age_s:
            state = "stalled"
        elif age >= long_s:
            state = "long"
        else:
            continue
        if state in rec["done"]:
            continue
        rec["done"].append(state)
        if state == "stalled":
            st["model"].append(("warn", "Background %s shows no output or transcript change for about %d min (watched for %d min). "
                                "It may be stalled or waiting on something; this is a guess from file timestamps. Check its output or ask the user before stopping it."
                                % (label(t), minutes(idle), minutes(age))))
            st["user"].append("백그라운드 작업 %s 이(가) 약 %d분째 출력 변화가 없습니다. 멈췄거나 대기 중일 수 있습니다."
                              % (label(t), minutes(idle)))
        else:
            st["model"].append(("info", "Background %s has been running for about %d min%s. Mention it to the user only if it matters for the current work."
                                % (label(t), minutes(age), "" if sig is None else " and is still showing progress")))
            st["user"].append("백그라운드 작업 %s 이(가) %d분 넘게 실행 중입니다%s."
                              % (label(t), minutes(age), "" if sig is None else "(진척은 있음)"))


def wrap(items):
    out, by = [], {}
    for lv, tx in items:
        by.setdefault(lv, []).append(tx)
    for lv in ("action", "warn", "info"):
        if lv in by:
            out.append('<harness-hook name="%s" level="%s">\n%s\n</harness-hook>' % (TAG, lv, "\n".join(by[lv])))
    return "\n".join(out)


def main():
    if os.environ.get("HARNESS_Q_STALE", "").lower() in ("off", "0", "no"):
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    ev, sp, now = data.get("hook_event_name"), state_file(data.get("session_id")), time.time()
    if ev == "UserPromptSubmit":
        if data.get("agent_id") or not os.path.exists(sp):
            return
        st = load(sp)
        if not st.get("model"):
            return
        text = wrap([tuple(x) for x in st["model"]])
        st["model"] = []
        save(sp, st)
        json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}, sys.stdout, ensure_ascii=False)
    elif ev in ("Stop", "SubagentStop"):
        if not isinstance(data.get("background_tasks"), list):
            return
        st = load(sp)
        before = json.dumps(st, sort_keys=True)
        evaluate(st, data, now)
        out = None
        if ev == "Stop" and not data.get("agent_id") and st.get("user"):
            out = {"systemMessage": "\n".join(st["user"])}
            st["user"] = []
        if json.dumps(st, sort_keys=True) != before:
            save(sp, st)
        if out:
            json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
