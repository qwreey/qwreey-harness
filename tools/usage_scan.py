"""usage-report.py 가 쓰는 트랜스크립트 읽기와 집계. 표준 라이브러리만 쓴다.

Claude Code 의 세션 트랜스크립트(<설정 폴더>/projects/<키>/<세션>.jsonl, 서브에이전트는 <세션>/subagents/**/agent-*.jsonl 과
옆의 .meta.json)에서 훅이 남긴 줄과 토큰 사용량만 골라 이름, 횟수, 크기, 시간으로 줄인다. 글 내용은 결과에 남기지 않는다.

읽는 줄(2026-11 Claude Code 2.1.3xx 실측 꼴)
  attachment.hook_success             출력이 있던 훅 한 번: command, durationMs, exitCode, stdout. 아무것도 찍지 않은 훅은 남지 않는다
  attachment.hook_additional_context  모델에게 간 글: content(훅마다 한 항목). UserPromptSubmit 은 이것만 남고 hook_success 가 없다
  attachment.hook_system_message      사용자에게 보인 systemMessage(Stop 의 알림 등)
  attachment.hook_non_blocking_error  실패한 훅(exitCode, durationMs). hook_blocking_error 는 blockingError.command 만 있다
  system/stop_hook_summary            Stop 훅 전부의 command 와 durationMs. 조용한 Stop 훅도 여기에는 남는다
  user tool_result(is_error)          "PreToolUse:<도구> hook error: ..." 로 시작하면 exit 2 거부. 뒤에 "[명령]: " 이 붙기도 한다
  assistant message.usage             턴마다 토큰. 한 메시지가 내용 블록마다 줄로 나뉘어 같은 id 로 되풀이되므로 id 로 한 번만 센다
"""
import json
import math
import os
import re
from collections import Counter, defaultdict

# 시험 실행(probe)이 만드는 프로젝트 키. --include-probes 로 넣는다
PROBE_PREFIXES = ("-tmp", "-var-tmp", "-code--cache")
LEVELS = ("info", "warn", "action")
USAGE_FIELDS = (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                ("cache_creation", "cache_creation_input_tokens"), ("output", "output_tokens"))
# 줄을 json.loads 하기 전의 값싼 거름. 문자열 값 안의 따옴표는 \" 로 적히므로 '"usage"' 는 실제 usage 키에만 걸린다
MARKERS = ('"hook_', "stop_hook_summary", " hook error", '"usage"')

OPEN_TAG = re.compile(r'<(harness-hook|plugin)\s+name="([^"]{0,80})"([^>]{0,200})>')
LEVEL_ATTR = re.compile(r'\blevel="([a-z|]{1,20})"')
SAFE_NAME = re.compile(r"[A-Za-z0-9_.:@/+-]{1,64}\Z")
DENY_HEAD = re.compile(r"(\w+)(?::([\w.-]{1,40}))? hook error: ")
DENY_COMMAND = re.compile(r"\[([^\]\n]{1,400})\]: ")
DENY_NAME = re.compile(r"([a-z][\w-]{2,40}): ")
DENY_ORIGIN = re.compile(r"This hook comes from the ([\w.-]{1,64})@[\w.-]{1,64} plugin")
# 훅 스크립트가 아예 돌지 못하면 stderr 가 "python3: can't open file ..." 꼴이라 이 이름은 훅 이름이 아니다
INTERPRETERS = ("python3", "python", "bash", "sh", "node", "env")
ROOT_SCRIPT = re.compile(r'\$\{?CLAUDE_PLUGIN_ROOT\}?/([^\s"\']+)["\']?(.*)')
CACHE_SCRIPT = re.compile(r'/plugins/cache/[^/\s"]+/([\w.-]+)/[^/\s"]+/([^\s"\']+)["\']?(.*)')
SOURCE_SCRIPT = re.compile(r'/plugins/([\w.-]+)/([^\s"\']+)["\']?(.*)')
USER_SCRIPT = re.compile(r'(?:\$HOME|\$\{HOME\}|~)/\.claude/(hooks/[^\s"\']+)["\']?(.*)')
NATIVE_BIN = re.compile(r"native/([\w.-]+?)(?:\.exe)?\Z")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NATIVE = {}


def native_aliases():
    """Rust 훅 실행 형식 -> 그 훅이 대신하는 python 스크립트. crates/*/parity-map.json 에서 읽는다.

    {(바이너리 이름, exec 인자 tuple): (플러그인 기준 스크립트 경로, python 인자 tuple)}. 실사용 보고서가 python 시절 기준선과
    같은 이름으로 세도록 쓴다.
    """
    if _NATIVE:
        return _NATIVE

    # crate 마다 대조표 하나
    crates = os.path.join(REPO, "crates")
    for name in sorted(os.listdir(crates)) if os.path.isdir(crates) else []:
        try:
            with open(os.path.join(crates, name, "parity-map.json"), encoding="utf-8") as f:
                entries = json.load(f)
        except (OSError, ValueError):
            continue

        # 항목 키는 바이너리 이름과 exec 인자
        for e in entries if isinstance(entries, list) else []:
            m = NATIVE_BIN.search(str((e.get("exec") or [""])[0]))
            parts = str(e.get("hook", "")).split("/", 2)
            if m and len(parts) == 3:
                _NATIVE[(m.group(1), tuple(e["exec"][1:]))] = (parts[2], tuple(e.get("argv") or ()))
    return _NATIVE


def native_alias(rel, args):
    """rel 이 native/<바이너리> 이면 대조표로 python 스크립트 경로와 인자로 바꾼다. 대조표에 없으면 그대로."""
    m = NATIVE_BIN.search(rel)
    if not m:
        return rel, args

    # 긴 인자 머리부터 맞춰 본다(대조표에 argv 가 없는 항목은 남은 인자가 python 인자다)
    aliases = native_aliases()
    for cut in range(len(args), -1, -1):
        hit = aliases.get((m.group(1), tuple(args[:cut])))
        if hit:
            return hit[0], hit[1] + tuple(args[cut:])
    return rel, args


def safe(name):
    """이름으로 보일 만한 글자만 든 값이면 그대로, 아니면 "?". 보고서에 내용이 새지 않게 하는 마지막 거름이다."""
    return name if isinstance(name, str) and SAFE_NAME.match(name) else "?"


def est_tokens(text):
    """글의 토큰 수 추정. 글자마다 ASCII 0.4, 한글 음절 1.6, 그 밖 1.5 를 더한다."""
    # coderag 의 출력 크기 추정과 같은 계수(줄 번호 항은 뺀다). 혼합 글에서 +-10% 정도다
    ascii_n = hangul_n = 0
    for ch in text:
        if ch < "\x80":
            ascii_n += 1
        elif "가" <= ch <= "힣":
            hangul_n += 1
    return 0.4 * ascii_n + 1.6 * hangul_n + 1.5 * (len(text) - ascii_n - hangul_n)


def pct(values, q):
    """nearest-rank 백분위. 값이 없으면 None."""
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def blocks(text):
    """글을 최상위 태그 블록으로 나눈다: [(목소리, 수준, 조각)]. 태그 밖 글은 목소리 None.

    블록 안에 인용된 태그(q 의 규약이 설명하는 `<harness-hook name="...">` 같은 것)는 닫는 태그까지 건너뛰므로 세지 않는다.
    """
    out, pos = [], 0
    while True:
        m = OPEN_TAG.search(text, pos)
        start = m.start() if m else len(text)
        if text[pos:start].strip():
            out.append((None, None, text[pos:start]))
        if not m:
            return out

        kind, name, rest = m.groups()
        close = text.find("</%s>" % kind, m.end())
        end = close + len(kind) + 3 if close >= 0 else len(text)
        lv = LEVEL_ATTR.search(rest)
        level = lv.group(1) if lv and lv.group(1) in LEVELS else None
        voice = ("plugin " if kind == "plugin" else "") + safe(name)
        out.append((voice, level, text[m.start():end]))
        pos = end


def command_id(command):
    """훅 command 를 (플러그인 단서 또는 None, 플러그인 기준 경로, 인자 tuple) 로. 경로가 펼쳐진 꼴이면 플러그인 이름을 안다."""
    for rx, has_plugin in ((ROOT_SCRIPT, False), (CACHE_SCRIPT, True), (SOURCE_SCRIPT, True), (USER_SCRIPT, False)):
        m = rx.search(command or "")
        if m:
            plugin = m.group(1) if has_plugin else ("~/.claude" if rx is USER_SCRIPT else None)
            rel, rest = m.groups()[-2:]
            args = tuple(safe(a.strip("\"'")) for a in rest.split()[:3])
            rel, args = native_alias(rel, args)
            return plugin, safe(rel), args
    first = (command or "").split()
    return None, safe(os.path.basename(first[-1].strip("\"'"))) if first else "?", ()


def load_hook_entries(roots):
    """플러그인 폴더들의 hooks/hooks.json 에 적힌 훅 목록(type 이 command 가 아닌 것도 든다).

    항목 칸: plugin, root, event, matcher, type, command, args, timeout, async.
    """
    out = []
    for root in roots:
        # 플러그인 이름과 hooks.json 읽기
        try:
            manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            plugin = manifest.get("name") or root.name
        except (OSError, ValueError):
            plugin = root.name
        try:
            hooks = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8")).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            continue

        for event, groups in hooks.items():
            for group in groups:
                for h in group.get("hooks", []):
                    out.append({"plugin": plugin, "root": root, "event": event, "matcher": group.get("matcher"),
                                "type": h.get("type"), "command": h.get("command", ""), "args": h.get("args") or [],
                                "timeout": h.get("timeout"), "async": bool(h.get("async"))})
    return out


class Labeler:
    """훅 command 에 "플러그인:스크립트 인자" 이름을 붙인다. 플러그인은 hooks.json 대조, 펼쳐진 경로, 출력의 <plugin> 태그 순으로 찾는다."""

    def __init__(self, entries):
        self.exact = defaultdict(set)
        self.by_rel = defaultdict(set)
        self.by_stem = defaultdict(set)
        for e in entries:
            _, rel, args = command_id(" ".join([e["command"], *e["args"]]))
            self.exact[(rel, args)].add(e["plugin"])
            self.by_rel[rel].add(e["plugin"])
            self.by_stem[os.path.splitext(os.path.basename(rel))[0].replace("_", "-")].add(e["plugin"])

    def plugin_of_name(self, name):
        """훅 이름(heavy-proc-guard 등)과 같은 스크립트 이름을 가진 플러그인이 하나면 그 이름, 아니면 None."""
        cands = self.by_stem.get(name) or set()
        return next(iter(cands)) if len(cands) == 1 else None

    def resolve(self, command, voices=()):
        """(플러그인, 이름). 같은 스크립트 경로를 둘 이상의 플러그인이 쓰면 출력의 <plugin X> 목소리로 고르고, 못 고르면 "?"."""
        hint, rel, args = command_id(command)
        plugin = hint
        if plugin is None:
            cands = self.exact.get((rel, args)) or self.by_rel.get(rel) or set()
            named = [c for c in cands if "plugin " + c in voices]
            plugin = next(iter(cands)) if len(cands) == 1 else (named[0] if len(named) == 1 else "?")
        return plugin, hook_label(plugin, rel, args)


def hook_label(plugin, rel, args):
    """보고서의 훅 실행 이름: "플러그인:스크립트 인자"(예: q:ambient.py SessionStart)."""
    return "%s:%s" % (plugin, " ".join((os.path.basename(rel),) + tuple(args)))


def hook_output_texts(stdout):
    """hook_success stdout 에서 (모델에게 간 글, permissionDecision). JSON 이 아니면 stdout 전체가 모델에게 간 글이다."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout, None
    if not isinstance(data, dict):
        return "", None
    hso = data.get("hookSpecificOutput") if isinstance(data.get("hookSpecificOutput"), dict) else {}
    ctx = hso.get("additionalContext")
    return (ctx if isinstance(ctx, str) else ""), hso.get("permissionDecision")


def result_text(block):
    """tool_result 블록의 글. content 가 문자열이거나 {"text"} 목록이다."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(x.get("text", "") for x in content if isinstance(x, dict))
    return ""


def new_voice():
    """목소리(태그 이름) 하나의 집계 칸. owners 는 그 목소리를 낸 플러그인 후보다."""
    return {"spoke": 0, "levels": Counter(), "chars": [], "tokens": 0.0, "denies": 0, "events": Counter(), "owners": Counter()}


def new_run():
    """(훅 이름, 이벤트) 하나의 실행 시간 집계 칸. sources 는 어느 기록 줄에서 왔는지다."""
    return {"durations": [], "errors": 0, "sources": Counter()}


class Scan:
    """트랜스크립트 파일을 한 줄씩 읽어 훅, 상시 주입, 서브에이전트, 토큰 사용량을 모은다. 창은 줄 timestamp(UTC ISO 문자열)로 거른다."""

    def __init__(self, labeler, since_iso, until_iso):
        self.labeler = labeler
        self.since, self.until = since_iso, until_iso
        self.voices = defaultdict(new_voice)
        self.runs = defaultdict(new_run)
        self.denies = Counter()
        self.user_messages = defaultdict(list)
        self.sessions = {}
        self.agents = []
        self.prompt_chars = []
        self.later_starts = defaultdict(list)
        self.usage = {}
        self.files = self.bytes = 0

    # ---- 파일 ----

    def read_file(self, path, project, session=None, agent=None):
        """파일 하나를 읽는다. session 은 메인 트랜스크립트의 세션 기록 dict, agent 는 서브에이전트 기록 dict(둘 중 하나)."""
        owner = session if session is not None else agent
        state = {"owner": owner, "is_main": session is not None, "project": project, "start_source": None,
                 "success": {}, "sysmsg": {}}
        try:
            f = open(path, encoding="utf-8", errors="replace")
        except OSError:
            return
        self.files += 1
        with f:
            for line in f:
                self.bytes += len(line)
                if any(m in line for m in MARKERS):
                    self.read_line(line, state)

    def read_line(self, line, state):
        """창 안의 줄 하나를 종류에 맞는 처리로 넘긴다. 창 안 줄이 하나라도 있으면 그 세션(에이전트)을 active 로 표시한다."""
        try:
            d = json.loads(line)
        except ValueError:
            return
        ts = d.get("timestamp")
        if not isinstance(ts, str) or not self.since <= ts < self.until:
            return
        state["owner"]["active"] = True

        # 줄 종류마다 한 처리
        kind = d.get("type")
        if kind == "attachment" and isinstance(d.get("attachment"), dict):
            handler = ATTACHMENT_HANDLERS.get(d["attachment"].get("type"))
            if handler:
                handler(self, d["attachment"], state)
        elif kind == "system" and d.get("subtype") == "stop_hook_summary":
            self.on_stop_summary(d, state)
        elif kind == "user" and isinstance(d.get("message"), dict) and isinstance(d["message"].get("content"), list):
            self.on_tool_results(d["message"]["content"])
        elif kind == "assistant" and isinstance(d.get("message"), dict):
            self.on_assistant(d["message"], state)

    # ---- 훅 줄 ----

    def add_run(self, label, event, duration, source, error=False):
        """훅 실행 한 번(시간이 있으면 시간도)을 (이름, 이벤트) 칸에 더한다."""
        run = self.runs[(label, safe(event))]
        if isinstance(duration, (int, float)):
            run["durations"].append(duration)
        run["sources"][source] += 1
        run["errors"] += 1 if error else 0

    def speak(self, voice, level, text, event, deny=False, owner=None):
        """모델에게 간 글 한 조각을 목소리 칸에 더한다(횟수, 수준, 글자, 추정 토큰). owner 는 알면 그 플러그인."""
        v = self.voices[voice]
        if owner:
            v["owners"][owner] += 1
        v["spoke"] += 1
        v["levels"][level or "-"] += 1
        v["chars"].append(len(text))
        v["tokens"] += est_tokens(text)
        v["events"][safe(event)] += 1
        v["denies"] += 1 if deny else 0

    def on_success(self, a, state):
        """hook_success: 이름 붙이기, 실행 시간, JSON 거부, SessionStart 출처. 글은 뒤따르는 hook_additional_context 에서 센다."""
        event = a.get("hookEvent")
        ctx, decision = hook_output_texts(a.get("stdout") or "")
        voices = [v for v, _, _ in blocks(ctx) if v]
        plugin, label = self.labeler.resolve(a.get("command"), voices)
        for v in voices:
            self.voices[v]["owners"][plugin] += 1
        state["success"].setdefault(a.get("toolUseID"), []).append(label)
        state["sysmsg"][a.get("toolUseID")] = label

        # Stop 은 stop_hook_summary 가 조용한 훅까지 모두 적으므로 거기서만 시간을 센다
        if event != "Stop":
            self.add_run(label, event, a.get("durationMs"), "printed", a.get("exitCode") not in (0, None))
        if decision in ("deny", "ask"):
            tool = (a.get("hookName") or "").partition(":")[2]
            self.denies[(voices[0] if voices else label, safe(tool) if tool else "?", "json " + decision)] += 1
        if event == "SessionStart":
            state["start_source"] = safe((a.get("hookName") or "").partition(":")[2] or "?")

    def on_context(self, a, state):
        """hook_additional_context: 항목마다 최상위 태그 블록으로 나눠 목소리별로 센다. 태그 없는 글은 같은 호출의 훅 이름으로 묶는다."""
        event = a.get("hookEvent")
        items = [s for s in a.get("content") or [] if isinstance(s, str)]
        labels = state["success"].get(a.get("toolUseID")) or []
        untagged = "(untagged) " + (labels[0] if len(labels) == 1 else safe(event))
        untagged_owner = labels[0].partition(":")[0] if len(labels) == 1 else None
        by_voice = Counter()
        for item in items:
            for voice, level, text in blocks(item):
                self.speak(voice or untagged, level, text, event, owner=None if voice else untagged_owner)
                by_voice[voice or untagged] += len(text)
        self.always_on(event, sum(map(len, items)), by_voice, state)

    def always_on(self, event, chars, by_voice, state):
        """SessionStart(메인), SubagentStart(서브에이전트), UserPromptSubmit 에 실린 글자 수를 그 자리 기록에 더한다."""
        owner = state["owner"]
        if event == "SessionStart" and state["is_main"]:
            source = state["start_source"] or "?"
            if source == "startup":
                owner["startup_chars"] += chars
                owner["startup_voices"].update(by_voice)
            else:
                self.later_starts[source].append(chars)
        elif event == "SubagentStart" and not state["is_main"]:
            owner["start_chars"] += chars
            owner["start_voices"].update(by_voice)
        elif event == "UserPromptSubmit":
            self.prompt_chars.append(chars)

    def on_system_message(self, a, state):
        """hook_system_message: 사용자에게 보인 글의 횟수와 글자 수를 같은 호출의 훅 이름으로."""
        owner = state["sysmsg"].get(a.get("toolUseID")) or safe(a.get("hookName"))
        self.user_messages[owner].append(len(a.get("content") or ""))

    def on_error(self, a, state):
        """hook_non_blocking_error, hook_blocking_error: 실패 실행으로 세고, blocking 은 거부 표에도 넣는다."""
        command = a.get("command")
        if command is None and isinstance(a.get("blockingError"), dict):
            command = a["blockingError"].get("command")
        _, label = self.labeler.resolve(command)
        self.add_run(label, a.get("hookEvent"), a.get("durationMs"), a.get("type"), error=True)
        if a.get("type") == "hook_blocking_error":
            tool = (a.get("hookName") or "").partition(":")[2]
            self.denies[(label, safe(tool) if tool else "?", "blocking error")] += 1

    def on_stop_summary(self, d, state):
        """stop_hook_summary: Stop 훅마다 실행 시간 한 번. hookErrors 는 훅을 가리키지 않아 따로 센다."""
        for info in d.get("hookInfos") or []:
            if isinstance(info, dict):
                _, label = self.labeler.resolve(info.get("command"))
                self.add_run(label, "Stop", info.get("durationMs"), "stop summary")
        for _ in d.get("hookErrors") or []:
            self.add_run("?:stop summary", "Stop", None, "stop summary", error=True)

    def on_tool_results(self, content):
        """exit 2 거부: is_error 인 tool_result 가 "<이벤트>:<도구> hook error: " 로 시작한다.

        훅 이름은 태그, 글 머리의 "이름: "(인터프리터 이름은 빼고), "[명령]: " 순으로 찾는다. 플러그인은 Claude Code 가 붙이는
        "This hook comes from the <플러그인>@<마켓> plugin" 꼬리, 명령 경로, 같은 이름의 스크립트 순이다.
        """
        for block in content:
            if not (isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error")):
                continue
            text = result_text(block)
            head = DENY_HEAD.match(text)
            if not head:
                continue

            # 명령 머리 떼기
            rest = text[head.end():]
            plugin = label = None
            cmd = DENY_COMMAND.match(rest)
            if cmd:
                plugin, label = self.labeler.resolve(cmd.group(1))
                rest = rest[cmd.end():]

            # 거부한 훅 이름과 플러그인 찾기
            tagged = [(v, lv) for v, lv, _ in blocks(rest) if v]
            plain = DENY_NAME.match(rest)
            crashed = bool(plain) and plain.group(1) in INTERPRETERS
            plain = plain.group(1) if plain and not crashed else None
            voice, level = tagged[0] if tagged else (plain or label or "?", None)
            tail = DENY_ORIGIN.search(rest)
            owner = safe(tail.group(1)) if tail else plugin if plugin not in (None, "?") else self.labeler.plugin_of_name(voice)

            self.speak(voice, level, rest, head.group(1), deny=True, owner=owner)
            kind = "exit 2, interpreter error" if crashed else "exit 2"
            self.denies[(voice, safe(head.group(2)) if head.group(2) else "?", kind)] += 1

    # ---- 토큰 ----

    def on_assistant(self, message, state):
        """assistant 줄: message.id 마다 마지막 usage 를 남기고, 서브에이전트의 실제 모델을 처음 본 값으로 적는다."""
        # Claude Code 가 지어낸 메시지(오류 안내 등)는 API 호출이 아니라 토큰이 0 이다
        if message.get("model") == "<synthetic>":
            return
        mid, usage = message.get("id"), message.get("usage")
        model = safe(message.get("model"))
        owner = state["owner"]
        if not state["is_main"] and owner.get("model") is None and model != "?":
            owner["model"] = model
        if isinstance(mid, str) and isinstance(usage, dict):
            counts = {k: usage.get(src) if isinstance(usage.get(src), int) else 0 for k, src in USAGE_FIELDS}
            self.usage[mid] = (state["project"], model, owner, counts)


ATTACHMENT_HANDLERS = {
    "hook_success": Scan.on_success,
    "hook_additional_context": Scan.on_context,
    "hook_system_message": Scan.on_system_message,
    "hook_non_blocking_error": Scan.on_error,
    "hook_blocking_error": Scan.on_error,
}
