"""usage-report.py --time-hooks: 도구 호출마다 도는 훅을 버리는 샌드박스에서 돌려 시간을 잰다. 표준 라이브러리만 쓴다.

트랜스크립트에는 아무것도 찍지 않은 훅의 실행이 남지 않으므로, 그 비용을 여기서 흉내로 잰다.
hooks.json 의 PreToolUse, PostToolUse, PostToolBatch 훅마다 작은 실제 꼴 입력(Bash `ls`, 저장소 파일 Read, Edit)을 주어
`sh -c <command>` 로 N 번 돌린다(Claude Code 처럼 셸이 ${CLAUDE_PLUGIN_ROOT} 를 펼친다). 시간은 프로세스 시작부터 끝까지다.

샌드박스는 tools/tests/hook_sandbox.py 의 것이다: TMPDIR, HOME, CLAUDE_CONFIG_DIR, XDG 폴더, session-log 저장소가 모두 임시 폴더 안이고
프로젝트 저장소도 임시 git 저장소다. 그 위에 CLAUDE_PLUGIN_DATA, CODERAG_HOME 도 임시 폴더로 둔다. 끝나면 떼어 낸 워커를 기다렸다가 지운다.
command 훅이 아닌 것(prompt, agent, http: 모델이나 네트워크를 부른다)과 플러그인 밖 경로를 부르는 command 는 돌리지 않고 이유와 함께 적는다.

Claude Code 는 한 이벤트에 걸린 훅을 나란히 돌리므로, 도구 호출 하나가 기다리는 시간은 이벤트마다 가장 느린 훅에 가깝고(wall),
CPU 로 치르는 몫은 합(sum)에 가깝다. 둘 다 적는다. 같은 세션 id 로 되풀이하므로 p50 은 첫 실행 뒤의 평소 상태, max 는 첫 실행을 포함한다.
"""
import json
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "tests"))
sys.path.insert(0, str(ROOT / "tools"))
import usage_scan as us  # noqa: E402
from hook_sandbox import Sandbox  # noqa: E402

BENCH_EVENTS = ("PreToolUse", "PostToolUse", "PostToolBatch")
SAMPLE = "src/app.py"
SAMPLE_TEXT = "def total(items):\n    return sum(items)\n\n\nx = 2\n"
DEFAULT_TIMEOUT_S = 30


def tool_calls(sb):
    """흉내 낼 도구 호출: {도구 이름: (tool_input, tool_response)}."""
    path = str(sb.repo / SAMPLE)
    return {
        "Bash": ({"command": "ls", "description": "List files"},
                 {"stdout": "README.md\nsrc\n", "stderr": "", "interrupted": False, "isImage": False}),
        "Read": ({"file_path": path},
                 {"type": "text", "file": {"filePath": path, "content": SAMPLE_TEXT, "numLines": 5, "startLine": 1, "totalLines": 5}}),
        "Edit": ({"file_path": path, "old_string": "x = 1", "new_string": "x = 2", "replace_all": False},
                 {"filePath": path, "oldString": "x = 1", "newString": "x = 2", "structuredPatch": [], "userModified": False}),
    }


def payload(sb, event, tool, call):
    """이벤트 하나의 stdin JSON. PostToolBatch 는 호출 하나짜리 묶음이다."""
    tool_input, response = call
    base = {"session_id": "bench", "transcript_path": str(sb.tmp / "transcript.jsonl"), "cwd": str(sb.repo),
            "permission_mode": "default", "hook_event_name": event}
    one = {"tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_bench_" + tool}
    if event == "PreToolUse":
        return {**base, **one}
    if event == "PostToolUse":
        return {**base, **one, "tool_response": response}
    return {**base, "tool_calls": [{**one, "tool_response": response}]}


def matches(matcher, tool):
    """hooks.json matcher 가 도구 이름에 걸리는지. 비었거나 * 이면 모두."""
    if not matcher or matcher == "*":
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return matcher == tool


def skip_reason(entry):
    """돌리지 않을 훅이면 그 이유, 돌릴 훅이면 None."""
    if entry["type"] != "command":
        return "type %s calls a model or the network" % us.safe(entry["type"])
    if "CLAUDE_PLUGIN_ROOT" not in entry["command"]:
        return "command runs outside the plugin root"
    return None


def prepare(sb):
    """샌드박스 저장소에 표본 파일과 첫 커밋, 짧은 트랜스크립트를 둔다."""
    sb.write(SAMPLE, SAMPLE_TEXT)
    sb.write("README.md", "# Bench\n\nA small repo for hook timing.\n")
    sb.git("add", ".")
    sb.git("commit", "-qm", "init")
    lines = [{"type": "user", "message": {"role": "user", "content": "파일 목록 보여줘"}},
             {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "목록을 봅니다."}]}}]
    (sb.tmp / "transcript.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")


def time_command(sb, command, stdin, env, timeout):
    """명령 한 번을 sh -c 로 돌려 (밀리초, 종료 코드 또는 "timeout", stdout 이 비지 않았는지)."""
    started = time.perf_counter()
    try:
        p = subprocess.run(["sh", "-c", command], input=stdin, capture_output=True, text=True, env=env,
                           cwd=str(sb.repo), timeout=timeout)
        rc, spoke = p.returncode, bool(p.stdout.strip()) or p.returncode == 2
    except subprocess.TimeoutExpired:
        rc, spoke = "timeout", False
    return (time.perf_counter() - started) * 1000, rc, spoke


def bench(roots, runs):
    """roots 의 훅을 도구마다 runs 번 돌린 결과 dict(usage-report.py --time-hooks --json 이 그대로 찍는다)."""
    entries = [e for e in us.load_hook_entries(roots) if e["event"] in BENCH_EVENTS]
    skipped = [{"hook": "%s:%s" % (e["plugin"], e["event"]), "reason": skip_reason(e)} for e in entries if skip_reason(e)]
    entries = [e for e in entries if not skip_reason(e)]
    rows = []
    with Sandbox(prefix="usage-bench-") as sb:
        prepare(sb)
        calls = tool_calls(sb)

        # 인터프리터 바닥값: 아무 일도 하지 않는 python3 한 번
        floor = [time_command(sb, "python3 -I -X utf8 -c pass", "", sb.env(), DEFAULT_TIMEOUT_S)[0] for _ in range(runs)]

        for e in entries:
            _, rel, args = us.command_id(" ".join([e["command"], *e["args"]]))
            label = us.hook_label(e["plugin"], rel, args)
            command = " ".join([e["command"], *(shlex.quote(a) for a in e["args"])])
            env = sb.env({"CLAUDE_PLUGIN_ROOT": str(e["root"]), "CLAUDE_PLUGIN_DATA": str(sb.root / "plugin-data" / e["plugin"]),
                          "CODERAG_HOME": str(sb.root / "coderag-home")})
            for tool, call in calls.items():
                if not matches(e["matcher"], tool):
                    continue
                stdin = json.dumps(payload(sb, e["event"], tool, call), ensure_ascii=False)
                timed = [time_command(sb, command, stdin, env, e["timeout"] or DEFAULT_TIMEOUT_S) for _ in range(runs)]
                ms = [t for t, _, _ in timed]
                rows.append({"hook": label, "event": e["event"], "tool": tool, "async": e["async"], "p50_ms": us.pct(ms, 0.5),
                             "max_ms": max(ms), "spoke": sum(1 for _, _, s in timed if s), "runs": runs,
                             "exit": dict(Counter(str(rc) for _, rc, _ in timed))})
    return {"runs": runs, "python_floor_ms": {"p50": us.pct(floor, 0.5), "max": max(floor)}, "hooks": rows,
            "per_tool": per_tool(rows), "skipped": skipped}


def per_tool(rows):
    """도구마다, 이벤트마다 훅 수와 p50 의 합(CPU 몫)과 최댓값(나란히 돌 때 기다리는 시간). async 훅은 빼고 센다."""
    out = {}
    for r in rows:
        if r["async"]:
            continue
        cell = out.setdefault(r["tool"], {}).setdefault(r["event"], {"hooks": 0, "sum_ms": 0.0, "wall_ms": 0.0})
        cell["hooks"] += 1
        cell["sum_ms"] += r["p50_ms"]
        cell["wall_ms"] = max(cell["wall_ms"], r["p50_ms"])
    return out


def markdown(result):
    """bench 결과를 Markdown 줄들로."""
    fl = result["python_floor_ms"]
    out = ["# Hook bench (%d runs each, temp sandbox)" % result["runs"], "",
           "- python3 startup floor: p50 %.0f ms, max %.0f ms" % (fl["p50"], fl["max"]), ""]

    # 도구 호출 하나가 치르는 몫
    out += ["## Per tool call (p50)", ""]
    for tool, events in result["per_tool"].items():
        parts = ["%s %d hooks: sum %.0f ms, wall %.0f ms" % (ev, events[ev]["hooks"], events[ev]["sum_ms"], events[ev]["wall_ms"])
                 for ev in BENCH_EVENTS if ev in events]
        out.append("- %s: %s" % (tool, "; ".join(parts)))

    out += ["", "## Per hook", "", "| hook | event | tool | p50 ms | max ms | spoke | exit |", "|---|---|---|---|---|---|---|"]
    for r in sorted(result["hooks"], key=lambda r: (r["tool"], BENCH_EVENTS.index(r["event"]), -r["p50_ms"])):
        exits = ", ".join("%s x%d" % kv for kv in sorted(r["exit"].items()))
        out.append("| %s%s | %s | %s | %.0f | %.0f | %d/%d | %s |" % (r["hook"], " (async)" if r["async"] else "", r["event"],
                                                                    r["tool"], r["p50_ms"], r["max_ms"], r["spoke"], r["runs"], exits))
    out += ["", "Skipped: " + ("; ".join("%s (%s)" % (s["hook"], s["reason"]) for s in result["skipped"]) or "none")]
    return out
