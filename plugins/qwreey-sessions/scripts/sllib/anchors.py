"""compact 뒤에 다시 싣는 닻: 방금 요약된 구간의 사용자 발화 원문(A), 기계로 뽑은 식별자(B), 트랜스크립트 검색 요령 한 줄(C).

왜: 긴 구간(수십만 토큰)의 CC compact 요약은 오류 문구, 경로, 사용자 원문 같은 정확한 값을 잃는다. 원문과 식별자를
다시 넣으면 도구 없이 답할 수 있다. 모델 호출 없이 트랜스크립트만 읽는다.

구간 찾기
- 1차: 줄을 바이트로 훑어 줄 시작 위치와 compact_boundary 줄만 안다(경계 줄만 JSON 으로 푼다).
- SessionStart(compact) 훅은 새 경계가 파일에 쓰이기 전에 도는 일이 많다(실측: 훅 기록의 시각이 경계보다 앞선다).
  그래서 마지막 경계 뒤에 대화(어시스턴트 응답, 사람 발화)가 있으면 그 경계는 지난 compact 의 것이고 구간은 그 경계부터 파일 끝이다.
  대화가 없으면 마지막 경계가 방금 쓰인 것이고 구간은 그 앞 경계부터 마지막 경계까지다.
- 경계의 preservedSegment(compact 가 원문 그대로 남긴 꼬리)는 경계 앞에 있다. 시작 경계의 꼬리는 이번 compact 가 요약했으므로 구간에
  넣고, 끝 경계가 있으면 그 꼬리(preservedMessages)는 아직 맥락에 있으므로 뺀다. 끝 경계가 아직 없으면 뺄 꼬리를 모른다.
- B 는 메인 세션의 도구 호출만 본다. 서브에이전트가 고친 파일과 만든 커밋은 서브에이전트 트랜스크립트에 있어 빠진다.

Ref: .claude/scopes/plugins/qwreey-sessions/audit/61-compact-recovery-probe/summary.md
"""
from __future__ import annotations

import json
import os
import re
import time
from array import array

from . import extract as ex, messages
from .brief import fit
from .paths import short_home
from .redact import redact
from .store import escape_tags

CEILING = 9000          # CC 는 10,000자 넘는 훅 맥락을 미리보기로 바꾼다. SessionStart 출력 전체가 이 아래여야 한다
MIN_BUDGET = 600        # 이보다 작으면 제목뿐이라 넣을 값어치가 없다
PASTE_CAP = 1500        # 발화 하나의 상한. 붙여 넣은 로그가 나머지를 밀어내지 못하게 한다
FLOOR_CAP = 120         # 이보다 짧게 자른 인용은 쓸모가 없다. 그때는 오래된 발화부터 뺀다
TIME_LIMIT_S = 4.0      # SessionStart 훅 시간 상한은 10초다. 그보다 훨씬 먼저 조용히 포기한다
DEDUP_WINDOW = 8        # 큐에 들어간 프롬프트는 몇 항목 뒤에 사용자 레코드로 다시 나온다
BOUNDARY = b'"compact_boundary"'
EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
SHARES = (("files", 0.16), ("commits", 0.14), ("errors", 0.12), ("ids", 0.08))

COMMAND_RX = re.compile(r"<command-name>\s*([^<]*?)\s*</command-name>")
ARGS_RX = re.compile(r"<command-args>([\s\S]*?)</command-args>")
BASH_INPUT_RX = re.compile(r"<bash-input>([\s\S]*?)</bash-input>")
REMINDER_RX = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>")
MACHINE_PREFIXES = ("[Request interrupted by user", "This session is being continued from a previous conversation",
                    "<bash-stdout", "<bash-stderr")
# git commit 의 "[branch hash] msg" 와, 커밋 뒤에 붙여 돌린 `git log --oneline` 의 "hash msg"
COMMIT_LINE_RX = re.compile(r"(?m)^(?:\[[^\]\s]+(?: \([^)]*\))? ([0-9a-f]{7,40})\]|([0-9a-f]{7,40})) (.+)$")
REDIRECT_RX = re.compile(r"(?:^|[\s;&|(])(?:[12]?>>?|&>>?)\s*([~/.\w][^\s;&|<>'\"()`]*)")
TEE_RX = re.compile(r"\btee\s+(?:-a\s+)?([~/.\w][^\s;&|<>'\"()`]*)")
EXIT_RX = re.compile(r"^Exit code \d+$")
TAG_RX = re.compile(r"</?[A-Za-z][\w-]*(?:\s[^<>]*)?>")
DID_RX = re.compile(r"(?<![A-Za-z0-9_])D\d{1,3}(?![A-Za-z0-9_])")
AUDIT_RX = re.compile(r"(?i)(?<![A-Za-z])audit[ #]?(\d{1,3})(?!\d)")
CLAUDE_TAIL_RX = re.compile(r"\.claude/[\w./-]*")
PATH_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.~-/")
SKIP_CLAUDE_SUBDIRS = (".claude/projects/", ".claude/worktrees/", ".claude/plugins/")


def _kind(o: dict):
    og = o.get("origin")
    return og.get("kind") if isinstance(og, dict) else None


def _content(o: dict):
    return (o.get("message") or {}).get("content")


def clean_user_text(text: str, kind) -> str | None:
    """사람이 친 글만 남긴다. 명령은 `/name args`, 셸 모드는 `! cmd`. 기계 글이면 None."""
    if not isinstance(text, str):
        return None
    m = COMMAND_RX.search(text)
    if m:
        a = ARGS_RX.search(text)
        args = " ".join((a.group(1) if a else "").split())
        if not args and kind != "human":
            return None  # CC 가 기록한 인자 없는 내장 명령(/compact, /reload-plugins, /plugin)
        return f"{m.group(1)} {args}".strip()
    m = BASH_INPUT_RX.search(text)
    if m:
        return "! " + m.group(1).strip()
    text = REMINDER_RX.sub("", text).strip()
    if not text or ex.is_reminderish(text) or text.startswith(MACHINE_PREFIXES) or text == "/compact":
        return None
    return text


DESK_LINE_RX = re.compile(r"^(?:D\d+ (?:→|->|=|:|코멘트:|메모:|더 논의:)|전체 메모:)")
DESK_LINE_CAP = 300
DESK_WRAP_RX = re.compile(r"^The [\w-]+ plugin sent a message:\n([\s\S]*?)\n\nThis is how Claude Code surfaces")


def desk_text(o: dict) -> str | None:
    """qwreey-desk 가 대신 낸 프롬프트에서 사용자 결정 줄만 `(desk) ` 짧은 꼴로. 다른 플러그인이거나 결정 줄이 없으면 None."""
    og = o.get("origin")
    if not (isinstance(og, dict) and og.get("kind") == "plugin" and og.get("name") == "qwreey-desk") or o.get("isMeta"):
        return None
    pp = o.get("pluginPrompt")
    text = pp.get("text") if isinstance(pp, dict) else None
    if not isinstance(text, str):
        c = _content(o)
        m = DESK_WRAP_RX.match(c) if isinstance(c, str) else None
        text = m.group(1) if m else None
    if not text:
        return None
    lines = [ln.strip()[:DESK_LINE_CAP] for ln in text.splitlines() if DESK_LINE_RX.match(ln.strip())]
    return "(desk) " + "\n".join(lines) if lines else None


def _user_record_text(o: dict) -> str | None:
    if o.get("isMeta") or o.get("isCompactSummary") or o.get("isSidechain"):
        return None
    kind = _kind(o)
    if kind not in (None, "human"):
        return None  # task-notification, peer(서브에이전트 보고, 다른 세션), plugin(플러그인이 대신 낸 프롬프트)
    c = _content(o)
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif isinstance(b, dict) and b.get("type") == "image":
                parts.append("[image]")
        c = "\n".join(parts)
    return clean_user_text(c, kind)


def _result_text(b: dict) -> str:
    c = b.get("content")
    return c if isinstance(c, str) else ex.text_of(c)


def _error_line(tool: str, body: str) -> str:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return ""
    if EXIT_RX.match(lines[0]) and len(lines) > 1:
        s = f"{lines[0]}: {lines[-1]}"  # 셸 오류는 마지막 줄(stderr, 예외)이 원인이다
    else:
        s = " ".join(lines[:2])
    s = " ".join(TAG_RX.sub(" ", s[:2000]).split())
    s = s if len(s) <= 180 else s[:179] + "…"
    return f"{tool}: {s}" if tool else s


def _config_dirs() -> tuple[str, ...]:
    from .config import claude_config_dir
    return ("~/.claude/", os.path.expanduser("~/.claude") + "/", str(claude_config_dir()) + "/")


def _claude_paths(text: str) -> list[str]:
    """`.claude/...` 경로들. 정규식 하나로 앞 디렉터리까지 잡으면 긴 글에서 되짚기가 제곱으로 늘어 `.claude/` 자리에서 양쪽으로 편다."""
    out, i = [], text.find(".claude/")
    while i != -1:
        m = CLAUDE_TAIL_RX.match(text, i)
        j = i
        while j > 0 and i - j < 200 and text[j - 1] in PATH_CHARS:
            j -= 1
        out.append(text[j:m.end()])
        i = text.find(".claude/", m.end())
    return out


def _bash_targets(cmd: str) -> list[str]:
    out = []
    for rx in (REDIRECT_RX, TEE_RX):
        for t in rx.findall(cmd):
            t = t.rstrip(".,:")
            if t.startswith("/dev/") or not ("/" in t or re.search(r"\.\w{1,8}$", t)):
                continue
            out.append(t)
    return out


class Collector:
    """구간의 레코드를 차례로 받아 A·B 재료를 모은다."""

    def __init__(self, exclude: frozenset = frozenset()):
        self.exclude = exclude
        self.users: list[tuple[int, str]] = []
        self.files: dict[str, None] = {}
        self.commits: dict[str, str] = {}
        self.errors: dict[str, None] = {}
        self.ids: dict[str, int] = {}
        self.tools: dict[str, tuple[str, dict]] = {}
        self.conversation = False

    def _user(self, line: int, text: str | None) -> None:
        if not text:
            return
        norm = " ".join(text.split())
        if any(norm == t for _, t in self.users[-DEDUP_WINDOW:]):
            return  # 큐에 들어간 프롬프트가 사용자 레코드로 다시 나온 것
        self.users.append((line, norm))
        self._ids(text)

    def _ids(self, text: str) -> None:
        found = DID_RX.findall(text) + [f"audit {n}" for n in AUDIT_RX.findall(text)]
        for p in _claude_paths(text):
            p = p.rstrip(".,:;")
            i = p.find(".claude/")
            if p.endswith(".claude/") or any(p[i:].startswith(s) for s in SKIP_CLAUDE_SUBDIRS) or p.startswith(_config_dirs()):
                continue  # Claude Code 설정 폴더(~/.claude)는 저장소 기록이 아니다
            found.append(p)
        for k in found:
            self.ids[k] = self.ids.get(k, 0) + 1

    def feed(self, o: dict, line: int) -> None:
        if o.get("uuid") in self.exclude:
            return
        t = o.get("type")
        if t == "attachment":
            a = o.get("attachment") or {}
            if a.get("type") == "queued_command":
                og = a.get("origin")
                if isinstance(og, dict) and og.get("kind") == "human":
                    self._user(line, clean_user_text(a.get("prompt"), "human"))
            return
        if t == "assistant":
            if o.get("isSidechain"):
                return
            self.conversation = True
            for b in _content(o) or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    self._ids(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    self.tools[b.get("id")] = (b.get("name") or "", b.get("input") or {})
            return
        if t != "user" or o.get("isSidechain"):
            return
        kind = _kind(o)
        if kind == "human" and not o.get("isMeta"):
            self.conversation = True
        c = _content(o)
        if kind == "plugin" and isinstance(c, str):
            self._ids(c)  # 플러그인이 대신 낸 프롬프트는 원문에 넣지 않고 id 만 본다. 데스크의 결정 줄만 짧게 A 에 넣는다
            self._user(line, desk_text(o))
            return
        if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    self._result(line, b)
            return
        self._user(line, _user_record_text(o))

    def _result(self, line: int, b: dict) -> None:
        name, inp = self.tools.pop(b.get("tool_use_id"), ("", {}))
        body = _result_text(b)
        if b.get("is_error"):
            e = _error_line(name, body)
            if e:
                self.errors.setdefault(e, None)
            return
        if name == "AskUserQuestion":
            self._user(line, "(answer) " + body.strip())
        elif name in EDIT_TOOLS:
            p = inp.get("file_path") or inp.get("notebook_path")
            if p:
                self.files.setdefault(str(p), None)
        elif name == "Bash":
            cmd = str(inp.get("command", ""))
            for p in _bash_targets(cmd):
                self.files.setdefault(p, None)
            if ex.GIT_COMMIT_RX.search(cmd):
                for h1, h2, msg in COMMIT_LINE_RX.findall(body):
                    self.commits.setdefault(h1 or h2, msg.strip())


# ---- 구간 ----
def _scan(f) -> tuple[array, list[tuple[int, dict]]]:
    """줄 시작 위치 전부와 경계 줄 (줄 번호 0부터, compactMetadata)."""
    starts, bounds, pos = array("q"), [], 0
    for raw in f:
        if not raw.endswith(b"\n"):
            break  # 쓰는 중인 마지막 줄
        starts.append(pos)
        if BOUNDARY in raw:
            try:
                o = json.loads(raw)
            except ValueError:
                o = None
            if isinstance(o, dict) and o.get("type") == "system" and o.get("subtype") == "compact_boundary":
                bounds.append((len(starts) - 1, o.get("compactMetadata") or {}))
        pos += len(raw)
    starts.append(pos)  # 끝
    return starts, bounds


def _head_line(f, starts: array, idx: int, meta: dict, deadline: float) -> int:
    """경계 idx 가 원문 그대로 남긴 꼬리의 첫 줄. 모르면 idx."""
    head = ((meta.get("preservedSegment") or {}).get("headUuid") or "")
    if not re.fullmatch(r"[\w-]{1,64}", head):
        return idx
    needle = re.compile(rb'"uuid":\s*"' + head.encode() + rb'"')  # "parentUuid" 는 앞 글자가 달라 걸리지 않는다
    for i in range(idx - 1, max(-1, idx - 3000), -1):
        if time.monotonic() > deadline:
            break
        f.seek(starts[i])
        if needle.search(f.readline()):
            return i
    return idx


def _feed(f, starts: array, lo: int, hi: int, col: Collector, deadline: float) -> bool:
    """줄 lo..hi-1 (0부터)을 col 에 넣는다. 시간이 넘으면 False."""
    if lo >= hi:
        return True
    f.seek(starts[lo])
    for i in range(lo, hi):
        raw = f.readline()
        if (i & 255) == 0 and time.monotonic() > deadline:
            return False
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if isinstance(o, dict):
            col.feed(o, i + 1)
    return True


def collect(path: str, deadline: float | None = None) -> Collector | None:
    """방금 요약된 구간을 모은다. 읽을 수 없거나 시간이 넘으면 None."""
    deadline = deadline or time.monotonic() + TIME_LIMIT_S
    with open(path, "rb") as f:
        starts, bounds = _scan(f)
        end = len(starts) - 1
        if not bounds:
            col = Collector()
            return col if _feed(f, starts, 0, end, col, deadline) else None
        last, meta = bounds[-1]
        # 마지막 경계가 지난 compact 의 것이라고 보고 그 뒤를 먼저 모은다. 그 뒤에 대화가 없으면 방금 쓰인 경계다.
        col = Collector()
        if not _feed(f, starts, _head_line(f, starts, last, meta, deadline), last, col, deadline):
            return None
        col.conversation = False
        if not _feed(f, starts, last + 1, end, col, deadline):
            return None
        if col.conversation:
            return col
        pm = (meta.get("preservedMessages") or {}).get("uuids") or []
        col = Collector(frozenset(u for u in pm if isinstance(u, str)))
        lo = _head_line(f, starts, *bounds[-2], deadline) if len(bounds) > 1 else 0
        return col if _feed(f, starts, lo, last, col, deadline) else None


# ---- 글 만들기 ----
def _rel(p: str, cwd: str) -> str:
    if cwd and p.startswith(cwd.rstrip("/") + "/"):
        return p[len(cwd.rstrip("/")) + 1:]
    return short_home(p)


def _safe(s: str, sid: str | None) -> str:
    """모델에게 다시 넣기 전: 자격 증명 마스킹, nonce 지우기, 태그 무력화(인용된 훅 태그는 데이터로 남는다)."""
    return escape_tags(redact(ex.mask(s), sid))


def _trim(s: str, cap: int) -> str:
    """앞 2/3 와 뒤 1/3 을 남긴다: 붙여 넣은 글 앞뒤에 사용자가 쓴 요청이 있는 일이 많다."""
    if len(s) <= cap:
        return s
    keep = max(cap - 3, 2)
    head = keep * 2 // 3
    return s[:head] + " … " + s[len(s) - (keep - head):]


def _quote(line: int, text: str) -> str:
    return f'- (L{line}) "{text}"'


def fit_users(users: list[tuple[int, str]], budget: int) -> str:
    """사용자 발화를 budget 자 안에. 모두를 같은 상한으로 고르게 줄이고(짧은 것은 그대로), 바닥 상한으로도 넘치면 오래된 것부터 뺀다."""
    head = messages.ANCHORS_USERS
    items = [(n, _trim(t, PASTE_CAP)) for n, t in users]
    if not items:
        return ""
    dropped = 0
    while items:
        omit = messages.anchors_omitted(dropped, items[0][0]) if dropped else ""
        room = budget - len(head) - 1 - (len(omit) + 1 if omit else 0) - sum(len(_quote(n, "")) + 1 for n, _ in items)
        if room >= sum(len(t) for _, t in items):
            cap = PASTE_CAP
            break
        lo, hi = 0, max(len(t) for _, t in items)
        while lo < hi:  # 합이 room 이하가 되는 가장 큰 상한
            mid = (lo + hi + 1) // 2
            if sum(min(len(t), mid) for _, t in items) <= room:
                lo = mid
            else:
                hi = mid - 1
        if lo >= FLOOR_CAP or len(items) == 1:
            cap = lo
            break
        items.pop(0)
        dropped += 1
    if not items:
        return ""
    lines = [head] + ([omit] if dropped else []) + [_quote(n, _trim(t, cap)) for n, t in items]
    return "\n".join(lines) if cap >= 20 else ""


def build(col: Collector, budget: int, cwd: str = "", sid: str | None = None) -> str:
    if budget < MIN_BUDGET or not (col.users or col.files or col.commits or col.errors):
        return ""
    head, search = messages.ANCHORS_HEAD, messages.ANCHORS_SEARCH
    rest = budget - len(head) - len(search) - 2
    ids = sorted(col.ids, key=lambda k: -col.ids[k])  # 많이 나온 것부터(같으면 처음 나온 순서)
    short = [i for i in ids if "/" not in i]
    files = sorted((_rel(p, cwd) for p in col.files), key=lambda p: p.startswith(("/", "~")))  # 저장소 안 파일을 먼저(순서는 유지)
    lists = {
        "files": [f"- {_safe(p, sid)}" for p in files],
        "commits": [f"- {h[:10]} {_safe(m if len(m) <= 100 else m[:99] + '…', sid)}" for h, m in col.commits.items()],
        "errors": [f"- {_safe(e, sid)}" for e in col.errors],
        "ids": ([f"- {_safe(', '.join(short[:40]), sid)}"] if short else [])
               + [f"- {_safe(_rel(i, cwd), sid)}" for i in ids if "/" in i],
    }
    titles = {"files": messages.ANCHORS_FILES, "commits": messages.ANCHORS_COMMITS,
              "errors": messages.ANCHORS_ERRORS, "ids": messages.ANCHORS_IDS}
    blocks = []
    for key, share in SHARES:
        if lists[key]:
            blocks.append(fit(titles[key], lists[key], int(rest * share)))
    users = [(n, _safe(t, sid)) for n, t in col.users]
    a = fit_users(users, rest - sum(len(b) + 1 for b in blocks))
    text = "\n".join(x for x in [head, a] + blocks + [search] if x)
    text = redact(text, sid)
    return text if len(text) <= budget else ""


def target_chars() -> int:
    """SessionStart(compact) 출력 전체의 목표 길이. 설정값이 CEILING 을 넘으면 CEILING(잘못된 값이면 기본값)."""
    from .config import num
    return max(0, min(int(num("SESSION_LOG_COMPACT_ANCHORS_CHARS")), CEILING))


def anchors(path: str, budget: int, cwd: str = "", sid: str | None = None) -> str:
    """실패하면 ""(훅은 막지 않는다)."""
    if budget < MIN_BUDGET or not path or not os.path.isfile(path):
        return ""
    col = collect(path)
    return build(col, budget, cwd, sid) if col else ""
