"""python 훅과 그것을 바꿀 실행 형식(Rust 바이너리 등)에 같은 입력을 넣어 종료 코드와 stdout 을 바이트로 대조한다. 표준 라이브러리만 쓴다.

실행:
  python3 -I tools/tests/hook-parity.py --map MAP.json [--from-transcripts N] [--no-cases] [--case 이름 ...]
  python3 -I tools/tests/hook-parity.py --identity qwreey-proc-guard   (python 을 실행 형식의 python 으로: 대조기 확인, 비결정 훅 찾기)

대조표(MAP.json)는 항목 목록이다:
  [{"hook": "plugins/<p>/hooks/x.py", "argv": [...], "exec": ["${CLAUDE_PLUGIN_ROOT}/native/<바이너리>", "hook", "<이벤트>"]}]
- argv 가 있으면 그 인자로 부른 경우만 맞고 exec 를 그대로 쓴다. 없으면 어떤 인자든 맞고 그 인자를 exec 뒤에 붙인다.
- exec 는 hook_sandbox 의 Sandbox.run_argv 로 셸 없이 띄운다. ${CLAUDE_PLUGIN_ROOT} 는 hook 이 든 플러그인 폴더다.
- --identity 는 그 플러그인(이름 또는 all)의 .py 마다 [<이 python>, "-I", "-X", "utf8", "${CLAUDE_PLUGIN_ROOT}/<경로>"] 항목을 만든다
  (python 쪽 run() 과 같은 sys.executable).

입력:
- hook-replay 사례(tools/tests/hook-replay/cases, 형식은 test-hook-replay.py 머리): 대조표의 훅을 부르는 사례마다 같은 샌드박스 둘을 새로
  만들어 hook_sandbox.replay() 로 파일, 준비 명령, 단계를 차례로 놓는다(test-hook-replay.py 와 같은 정의). 맞는 단계는 한쪽은 python,
  다른 쪽은 exec 로 돌리고, 나머지 훅 단계는 양쪽 모두 python 으로 돌려 뒤 단계가 보는 상태를 맞춘다.
- --from-transcripts N: ~/.claude/projects/*/*.jsonl(읽기만)에서 대조표 훅이 hooks.json 에 걸린 도구(matcher)의 최근 호출 N 개로
  PreToolUse, PostToolUse(실패한 호출은 PostToolUseFailure) 입력을 만든다. 호출과 훅마다 새 샌드박스 둘에서 Pre 다음 Post 를 차례로
  돈다. cwd 는 샌드박스 저장소이고, transcript_path 는 없는 경로다: 실제 트랜스크립트를 주면 session-log 가 요약을 떼어 띄워 실제 claude -p 가 돈 적이 있다.

환경: 어느 쪽이든 Claude Code 처럼 CLAUDE_PLUGIN_ROOT, CLAUDE_PLUGIN_DATA, CLAUDE_PROJECT_DIR 을 단다(Sandbox.plugin_env, env).
평소에는 이 저장소의 플러그인 폴더와 <cfg>/plugins/data/<이름>-<마켓>, HOOK_SANDBOX_PLUGIN_COPY=1 이면 설치본 사본. test-hook-replay.py 는
평소 모드에서 이 둘을 달지 않으므로 여기 python 쪽 출력이 그 시험과 다를 수 있다(대조는 양쪽이 같은 조건이면 된다).

비교: 양쪽 stdout 을 각자의 샌드박스로 normalize() 한 뒤 바이트로, 그리고 종료 코드. stderr 차이는 따로 알리고 어긋남으로 세지 않는다.
어긋나면 짧은 unified diff 를 보이고 exit 1. 입력이 하나도 없거나 대조표가 틀리면 exit 2.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hook_sandbox import PYTHON_HOOK, ROOT, Sandbox, SetupFailed, plugin_of, replay  # noqa: E402
from usage_bench import matches  # noqa: E402
from usage_scan import load_hook_entries, native_alias  # noqa: E402

CASES = Path(__file__).resolve().parent / "hook-replay" / "cases"
PROJECTS = Path.home() / ".claude" / "projects"
TOOL_EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure")
DIFF_LINES = 40
PREFIX = "hook-parity-"  # 양쪽 샌드박스 경로의 길이를 같게 둔다


class Entry:
    """대조표 항목 하나: python 훅(과 인자)을 바꿀 exec argv."""

    def __init__(self, hook, exec_argv, argv=None):
        self.hook = Path(hook).as_posix()
        self.exec = list(exec_argv)
        self.argv = None if argv is None else list(argv)
        parts = self.hook.split("/")
        if len(parts) < 3 or parts[0] not in ("plugins", "packs") or not (ROOT / self.hook).is_file():
            raise ValueError("hook must be a script under plugins/ or packs/: %s" % hook)
        if not self.exec or not all(isinstance(a, str) for a in self.exec):
            raise ValueError("exec must be a non-empty list of strings: %s" % hook)
        self.plugin = "/".join(parts[:2])

    def matches(self, hook, argv):
        return Path(hook).as_posix() == self.hook and (self.argv is None or list(argv) == self.argv)

    def command(self, argv):
        return self.exec if self.argv is not None else self.exec + list(argv)

    def name(self):
        return self.hook.rsplit("/", 1)[-1]


def load_map(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("the map is a JSON list of {hook, argv?, exec}")
    return [Entry(e["hook"], e["exec"], e.get("argv")) for e in data]


def identity_map(names):
    """플러그인마다 그 안의 .py 를 실행 형식의 python 으로 부르는 항목. names 에 all 이 있으면 모든 플러그인과 팩."""
    dirs = sorted(p.parent.parent for p in list(ROOT.glob("plugins/*/.claude-plugin/plugin.json")) + list(ROOT.glob("packs/*/.claude-plugin/plugin.json")))
    if "all" not in names:
        dirs = [d for d in dirs if d.name in names or d.relative_to(ROOT).as_posix() in names]
    out = []
    for d in dirs:
        for script in sorted(d.rglob("*.py")):
            rel = script.relative_to(d).as_posix()
            if "__pycache__" in rel or rel.startswith("tests/"):
                continue
            out.append(Entry(script.relative_to(ROOT).as_posix(), [sys.executable, "-I", "-X", "utf8", "${CLAUDE_PLUGIN_ROOT}/" + rel]))
    return out


def find(entries, hook, argv):
    return next((e for e in entries if e.matches(hook, argv)), None)


# 비교와 보고

def readable(stdout):
    """diff 용 줄들. JSON 이면 칸 경로마다 한 줄, 여러 줄 글은 줄마다 '| ' 를 단다."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout.splitlines()
    lines = []

    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, "%s.%s" % (path, k) if path else k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, "%s[%d]" % (path, i))
        elif isinstance(value, str) and "\n" in value:
            lines.append(path + ":")
            lines.extend("  | " + line for line in value.split("\n"))
        else:
            lines.append("%s: %s" % (path, json.dumps(value, ensure_ascii=False)))

    walk(data, "")
    return lines


def short_diff(a_lines, b_lines, a_name="python", b_name="exec"):
    diff = list(difflib.unified_diff(a_lines, b_lines, a_name, b_name, n=2, lineterm=""))
    if len(diff) > DIFF_LINES:
        diff = diff[:DIFF_LINES] + ["... (%d more diff lines)" % (len(diff) - DIFF_LINES)]
    return diff


def compare(label, a, b):
    """a, b 는 (exit, 정규화한 stdout, 정규화한 stderr). {"label", "same", "stderr_same", "detail": [줄]} 을 돌려준다."""
    a_rc, a_out, a_err = a
    b_rc, b_out, b_err = b
    same = a_rc == b_rc and a_out == b_out
    detail = []

    # stdout, 종료 코드 차이 풀어 쓰기
    if a_rc != b_rc:
        detail.append("exit %d (python) vs %d (exec)" % (a_rc, b_rc))
    if a_out != b_out:
        a_lines, b_lines = readable(a_out), readable(b_out)
        if a_lines == b_lines:
            detail.append("same fields, bytes differ (key order, spacing or escapes):")
            a_lines, b_lines = [repr(x) for x in a_out.splitlines()], [repr(x) for x in b_out.splitlines()]
        detail.extend(short_diff(a_lines, b_lines))

    # stderr 는 판정과 따로 알리기
    if a_err != b_err:
        detail.append("stderr differs:")
        detail.extend(short_diff(a_err.splitlines(), b_err.splitlines()))
    return {"label": label, "same": same, "stderr_same": a_err == b_err, "detail": detail}


# uuid4 는 실행마다 다르다(track-reviewer 의 run id). 양쪽 모두 자리 표시로 바꿔 비교한다
UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


def captured(sb, result):
    def norm(text):
        return UUID4.sub("<uuid4>", sb.normalize(text))
    return result.rc, norm(result.stdout), norm(result.stderr)


# hook-replay 사례

def play(case, sb, entries, side):
    """사례 하나를 sb 에서 돌린다. 대조표에 맞는 단계의 [(단계 번호, 훅 이름, (exit, stdout, stderr))] 와 오류 글(없으면 None)."""
    out = []
    try:
        for i, step, payload, env in replay(case, sb):
            if payload is None or not (ROOT / step["hook"]).is_file():
                continue
            argv = step.get("argv") or []
            entry = find(entries, step["hook"], argv)
            result = run_side(sb, step["hook"], argv, payload, env, entry if side == "exec" else None)
            if entry:
                out.append((i, entry.name(), captured(sb, result)))
    except SetupFailed as e:
        return [], str(e)
    return out, None


def run_side(sb, hook, argv, payload, env, entry=None):
    """훅 하나를 python(entry 가 없으면) 또는 entry 의 exec 로 돌린다. 어느 쪽이든 Claude Code 처럼 플러그인 환경 변수를 단다."""
    plugin = plugin_of(hook)
    env = sb.plugin_env(plugin, env) if plugin else env
    if entry:
        return sb.run_argv(entry.command(argv), payload, entry.plugin, env=env)
    return sb.run(hook, payload, argv=argv, env=env)


def case_inputs(entries, names=None):
    """대조표의 훅을 부르는 사례 [(경로, 사례)]."""
    out = []
    for path in sorted(CASES.glob("*.json")):
        if names and path.name not in names and path.stem not in names:
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        if any("hook" in s and find(entries, s["hook"], s.get("argv") or []) for s in case.get("steps") or []):
            out.append((path, case))
    return out


def run_case(path, case, entries):
    with Sandbox(prefix=PREFIX) as a:
        a_out, a_err = play(case, a, entries, "python")
    with Sandbox(prefix=PREFIX) as b:
        b_out, b_err = play(case, b, entries, "exec")
    if a_err or b_err:
        return [{"label": "case %s" % path.name, "same": False, "stderr_same": True, "detail": [a_err or b_err]}]
    return [compare("case %s step %d %s" % (path.name, i, name), a_res, b_res) for (i, name, a_res), (_, _, b_res) in zip(a_out, b_out)]


# 트랜스크립트의 실제 입력

def registrations(entry):
    """entry 의 훅이 hooks.json 에 도구 이벤트로 걸린 [(이벤트, matcher, 인자)]."""
    out = []
    for h in load_hook_entries([ROOT / entry.plugin]):
        if h["type"] != "command" or h["event"] not in TOOL_EVENTS:
            continue
        script = registered_script(h)
        if not script or "%s/%s" % (entry.plugin, script[0]) != entry.hook:
            continue
        args = list(script[1])
        if entry.argv is None or args == entry.argv:
            out.append((h["event"], h["matcher"], args))
    return out


def registered_script(h):
    """hooks.json 항목이 부르는 python 스크립트 (플러그인 기준 경로, 인자), 없으면 None.

    Rust 바이너리(실행 형식)는 crates/*/parity-map.json 으로 그 바이너리가 대신하는 스크립트로 되돌린다."""
    m = PYTHON_HOOK.match(h["command"] or "")
    if m:
        return m.group(1), tuple(m.group(2).split())
    prefix = "${CLAUDE_PLUGIN_ROOT}/"
    if not h["args"] or not (h["command"] or "").startswith(prefix):
        return None
    rel, args = native_alias(h["command"][len(prefix):], tuple(h["args"]))
    return (rel, args) if rel.endswith(".py") else None


def calls_in(path):
    """트랜스크립트 하나의 도구 호출 [{"name", "input", "id", "result"?, "response"?, "is_error"}] (호출 순서)."""
    calls, by_id = [], {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return calls

    for line in text.splitlines():
        # 도구 블록이 없는 줄은 파싱 전에 거르기
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        content = (d.get("message") or {}).get("content") if isinstance(d, dict) else None

        # tool_use 와 tool_result 짝짓기
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and isinstance(block.get("input"), dict) and block.get("id") not in by_id:
                call = {"name": block.get("name"), "input": block["input"], "id": block.get("id"), "is_error": False}
                calls.append(call)
                by_id[call["id"]] = call
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                call = by_id[block["tool_use_id"]]
                call["result"] = block.get("content")
                call["response"] = d.get("toolUseResult", block.get("content"))
                call["is_error"] = bool(block.get("is_error"))
    return calls


def recent_calls(wanted, n, projects=PROJECTS):
    """wanted(도구 이름) 가 참인 최근 도구 호출 n 개, 새것부터. 트랜스크립트는 읽기만 한다.

    이어 간 세션은 앞 세션의 줄을 새 파일에 다시 적으므로 같은 호출 id 가 여러 파일에 있다. id 마다 하나만 두고, 결과가 있는 쪽을 쓴다.
    """
    files = sorted(projects.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out, seen = [], {}
    for f in files:
        for call in reversed(calls_in(f)):
            if not isinstance(call["name"], str) or not wanted(call["name"]):
                continue

            # id 마다 하나, 결과가 있는 쪽 남기기
            at = seen.get(call["id"])
            if at is not None:
                if "result" in call and "result" not in out[at]:
                    out[at] = call
            elif len(out) < n:
                seen[call["id"]] = len(out)
                out.append(call)

        if len(out) >= n:
            break
    return out


def result_text(content):
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def tool_payload(sb, event, call):
    """도구 호출 하나의 stdin JSON 글. 경로는 이 샌드박스의 것이고 transcript_path 는 없는 파일이다."""
    payload = {"session_id": "parity", "transcript_path": str(sb.root / "no-such-transcript.jsonl"), "cwd": str(sb.repo),
               "permission_mode": "default", "hook_event_name": event, "tool_name": call["name"], "tool_input": call["input"],
               "tool_use_id": call["id"]}
    if event == "PostToolUse":
        payload["tool_response"] = call.get("response")
    elif event == "PostToolUseFailure":
        payload.update(error=result_text(call.get("result")), is_interrupt=False)
    return json.dumps(payload, ensure_ascii=False)


def wants_event(event, call):
    if event == "PreToolUse":
        return True
    if "result" not in call:
        return False
    return call["is_error"] == (event == "PostToolUseFailure")


def transcript_inputs(entries, n, projects=PROJECTS):
    """[(entry, 호출, [(인자, 이벤트)])]. 호출은 대조표 훅의 matcher 에 걸리는 최근 n 개, 이벤트는 Pre 다음 Post 순서."""
    regs = [(e, r) for e in entries for r in registrations(e)]
    calls = recent_calls(lambda name: any(matches(m, name) for _, (_, m, _) in regs), n, projects) if regs else []
    out = []
    for call in calls:
        for entry in entries:
            events = [(args, event) for e, (event, m, args) in regs if e is entry and matches(m, call["name"]) and wants_event(event, call)]
            if events:
                out.append((entry, call, sorted(events, key=lambda x: TOOL_EVENTS.index(x[1]))))
    return out


def run_transcript_call(entry, call, events):
    """호출 하나의 이벤트들을 한 샌드박스에서 차례로 돌린다(Post 가 Pre 의 측정 같은 상태를 보게). 이벤트마다 비교 하나."""
    with Sandbox(prefix=PREFIX) as a:
        a_res = [captured(a, run_side(a, entry.hook, args, tool_payload(a, event, call), {})) for args, event in events]
    with Sandbox(prefix=PREFIX) as b:
        b_res = [captured(b, run_side(b, entry.hook, args, tool_payload(b, event, call), {}, entry)) for args, event in events]
    labels = ["transcript %s %s %s %s" % (event, call["name"], call["id"], entry.name()) for _, event in events]
    return [compare(label, x, y) for label, x, y in zip(labels, a_res, b_res)]


# 실행

def report(outcomes, write=print):
    differ = 0
    for o in outcomes:
        if not o["same"]:
            differ += 1
        state = "same" if o["same"] and o["stderr_same"] else "same, stderr differs" if o["same"] else "DIFFERENT"
        write("%-21s %s" % (state, o["label"]))
        for line in o["detail"]:
            write("    " + line)
    stderr_only = sum(1 for o in outcomes if o["same"] and not o["stderr_same"])
    write("%d inputs: %d same, %d different (%d same with stderr differences)" % (len(outcomes), len(outcomes) - differ, differ, stderr_only))
    return differ


def main(argv=None):
    ap = argparse.ArgumentParser(description="python 훅과 실행 형식의 대조(바이트)")
    ap.add_argument("--map", help="대조표 JSON 파일")
    ap.add_argument("--identity", nargs="+", metavar="PLUGIN", help="플러그인(이름, plugins/<이름> 또는 all)의 .py 를 실행 형식 python 으로")
    ap.add_argument("--case", nargs="+", help="이 사례만(파일 이름 또는 확장자 뺀 이름)")
    ap.add_argument("--no-cases", action="store_true", help="hook-replay 사례를 돌리지 않는다")
    ap.add_argument("--from-transcripts", type=int, default=0, metavar="N", help="최근 도구 호출 N 개를 실제 입력으로 더한다")
    ap.add_argument("--projects", default=str(PROJECTS), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    # 대조표 만들기
    try:
        entries = (load_map(args.map) if args.map else []) + (identity_map(args.identity) if args.identity else [])
    except (OSError, ValueError, KeyError) as e:
        print("bad map: %s" % e, file=sys.stderr)
        return 2
    if not entries:
        print("no map: give --map or --identity", file=sys.stderr)
        return 2

    # 입력마다 양쪽 돌리기
    outcomes = []
    if not args.no_cases:
        for path, case in case_inputs(entries, args.case):
            outcomes.extend(run_case(path, case, entries))
    if args.from_transcripts > 0:
        for entry, call, events in transcript_inputs(entries, args.from_transcripts, Path(args.projects)):
            outcomes.extend(run_transcript_call(entry, call, events))

    if not outcomes:
        print("no inputs call a mapped hook", file=sys.stderr)
        return 2
    return 1 if report(outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
