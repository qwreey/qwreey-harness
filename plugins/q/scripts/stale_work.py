#!/usr/bin/env python3
"""오래 방치된 백그라운드 작업 알림. 사용: python3 -I stale_work.py  (stdin: 훅 JSON, 이벤트는 hook_event_name)

출처: Stop·SubagentStop 의 background_tasks. 실측한 필드(/tmp/sa-probe/hooks.jsonl 캡처): 항목은
{id, type, status: running, description, agent_type | name} 뿐이다. 시작 시각·출력 경로·pid 는 없다. type 은 캡처에서
subagent, workflow 였고, 셸은 이 훅이 낸 알림 문구에 "Background shell" 로 찍혀 shell 임을 안다. 그 밖의 값도 같은 길로 다룬다.
그래서 나이는 "이 훅이 처음 본 때"부터 센다(Stop 이 도는 동안만 관측 가능). 진척 신호는 작업 출력 파일의 크기·mtime 이다:
서브에이전트는 트랜스크립트(<메인 트랜스크립트 디렉터리>/<sid>/subagents/**/agent-<id>.jsonl), 그 밖의 작업(셸 등)은
Claude Code 가 쓰는 <tmp>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<id>.output(프로젝트 키 = 트랜스크립트가 있는 디렉터리 이름.
서브에이전트의 것은 트랜스크립트로 가는 심볼릭 링크다). 신호를 못 찾는 작업(workflow 등)은 멈춤 판정을 하지 않고 오래 실행만
본다(진척을 모르는 채로 멈췄다고 말하지 않는다). CPU 는 pid 가 없어 보지 못한다. monitor 는 뺀다.

판정(분 단위, 환경 변수로 바꿀 수 있다):
- 멈춤(stalled): 진척 없이 HARNESS_Q_STALE_IDLE_MIN(15) 이상이고 나이가 HARNESS_Q_STALE_AGE_MIN(30) 이상. 모델 warn + 사용자 줄.
- 오래 실행(long): 멈춤이 아니고 나이가 HARNESS_Q_STALE_LONG_MIN(120) 이상. 모델 warn + 사용자 줄.
문구는 확정하지 않는 질문형("멈췄거나 대기 중일 수 있음")이다. 두 문구 모두 끝난 일에 딸린 작업이나 조건을 기다리며 도는
루프면 멈추라(TaskStop)고 권하고, 언급하지 말라는 말은 쓰지 않는다: 자기 명령줄에 걸리는 `pgrep -f` 대기 루프가 몇 시간 남았는데
"필요할 때만 언급" 알림 하나로 묻힌 적이 있다. dedup 은 (세션, task id, 상태)마다 1회.

전달: Stop·SubagentStop 이 판정해 상태 파일($TMPDIR/claude-q-stale/<sid>.json)에 쌓고, Stop(메인)이 사용자 줄을 systemMessage 로 내고,
UserPromptSubmit 이 모델 문구를 additionalContext 로 준다. 실패는 삼킨다(fail-open). 끄기: q 옵션 harness_q_stale(/config), 또는 harness.env 나 환경 변수의 HARNESS_Q_STALE=off.
"""
import glob
import json
import os
import re
import sys
import tempfile
import time

TAG = "stale-work"
FINISHED_HINT = ("If it belongs to work that already finished or loops waiting on a condition, look at its command and output "
                 "and stop it (TaskStop) or tell the user")
STALLED_HINT = FINISHED_HINT + "; otherwise check its output or ask the user before stopping it."
LONG_HINT = FINISHED_HINT + "; otherwise mention it to the user in one line."


STALE_DEFAULTS = {"HARNESS_Q_STALE": "on"}  # 끄기 스위치. q 옵션(/config) 이름은 harness_q_stale


def switched_off():
    """끄기 스위치: 환경 변수가 이기고, 없으면 harness.env 층(q 옵션 포함). 로더를 못 읽으면 켠 채로 둔다."""
    v = os.environ.get("HARNESS_Q_STALE")
    if v is None:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
            import harness_env
            v = harness_env.load_layers(defaults=STALE_DEFAULTS).get("HARNESS_Q_STALE")
        except Exception:
            v = None
    return str(v or "").strip().lower() in ("off", "0", "no")


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


def task_roots():
    """Claude Code 작업 출력의 루트 후보. 훅이 받은 TMPDIR 이 Claude Code 의 것과 다를 수 있어 /tmp 도 본다."""
    roots = []
    for r in (os.environ.get("CLAUDE_CODE_TMPDIR"), tempfile.gettempdir(), "/tmp"):
        if r and r not in roots:
            roots.append(r)
    return roots


def task_output_paths(tid, data):
    """<루트>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<tid>.output 후보. uid 가 없는 플랫폼은 claude-* 를 훑는다."""
    tp = data.get("transcript_path")
    sid = re.sub(r"[^\w-]", "", str(data.get("session_id") or ""))
    key = os.path.basename(os.path.dirname(tp)) if isinstance(tp, str) else ""
    if not (tid and sid and key):
        return []
    owner = "claude-%d" % os.getuid() if hasattr(os, "getuid") else "claude-*"
    rel = os.path.join(owner, glob.escape(key), sid, "tasks", "%s.output" % tid)
    out = []
    for r in task_roots():
        out += sorted(glob.glob(os.path.join(glob.escape(r), rel)))
    return out


def signal(task, data):
    """진척 신호 [크기, mtime, 알림에 실을 출력 경로 또는 None] 또는 None(알 수 없음)."""
    tid = re.sub(r"[^\w-]", "", str(task.get("id") or ""))
    sub = task.get("type") == "subagent"
    paths = []
    for key in ("output_file", "outputFile", "output_path"):  # 캡처에는 없지만 있으면 가장 직접적인 신호
        if isinstance(task.get(key), str):
            paths.append(task[key])
    tp = data.get("transcript_path")
    if tp and tid and sub:
        base = os.path.join(os.path.splitext(tp)[0], "subagents")
        paths.append(os.path.join(base, "agent-%s.jsonl" % tid))
        paths += glob.glob(os.path.join(base, "workflows", "*", "agent-%s.jsonl" % tid))
    paths += task_output_paths(tid, data)
    for p in paths:
        try:
            s = os.stat(p)
        except OSError:
            continue
        # 서브에이전트의 출력은 트랜스크립트라 모델이 읽을 것이 아니다. 셸 등은 경로를 알려 주면 바로 열어 볼 수 있다.
        return [s.st_size, s.st_mtime, None if sub else p]
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
        prev = rec.get("sig")
        if sig is not None and (prev is None or sig[:2] != prev[:2]):
            # 처음 본 신호는 파일 mtime 을 진척 시각으로 쓴다(이미 오래 조용한 작업을 늦게 발견한 경우)
            rec["prog"] = now if prev is not None else min(now, sig[1])
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
        out = " Output file: %s." % sig[2] if sig is not None and len(sig) > 2 and sig[2] else ""
        if state == "stalled":
            st["model"].append(("warn", "Background %s shows no output or transcript change for about %d min (watched for %d min). "
                                "It may be stalled or waiting on something; this is a guess from file timestamps.%s %s"
                                % (label(t), minutes(idle), minutes(age), out, STALLED_HINT)))
            st["user"].append("백그라운드 작업 %s 이(가) 약 %d분째 출력 변화가 없습니다. 멈췄거나 대기 중일 수 있습니다."
                              % (label(t), minutes(idle)))
        else:
            st["model"].append(("warn", "Background %s has been running for about %d min%s.%s %s"
                                % (label(t), minutes(age), "" if sig is None else " and is still showing progress", out, LONG_HINT)))
            st["user"].append("백그라운드 작업 %s 이(가) %d분 넘게 실행 중입니다%s."
                              % (label(t), minutes(age), "" if sig is None else "(진척은 있음)"))


def wrap(items, session_id=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
    import harness_nonce
    out, by = [], {}
    for lv, tx in items:
        by.setdefault(lv, []).append(tx)
    for lv in ("action", "warn", "info"):
        if lv in by:
            out.append('<harness-hook name="%s" level="%s"%s>\n%s\n</harness-hook>' % (TAG, lv, harness_nonce.attr(session_id), "\n".join(by[lv])))
    return "\n".join(out)


def main():
    if switched_off():
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
        text = wrap([tuple(x) for x in st["model"]], data.get("session_id"))
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
