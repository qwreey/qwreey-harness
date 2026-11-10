"""트랜스크립트(JSONL)를 요약 모델에 넘길 짧은 텍스트로 줄인다.

- 바이트 오프셋부터 읽는다(증분). `\\n` 으로 끝나지 않은 마지막 줄은 남긴다(비동기로 써지는 중일 수 있다).
- 남김: 사람 발언(typed, 작업 중 큐), 어시스턴트 text, 도구 한 줄(Bash 앞부분, Edit/Write 경로, Agent 설명, git commit 메시지),
  AskUserQuestion 답, 도구 오류 앞부분, 서브에이전트 보고·다른 세션 메시지 앞부분, compact 경계.
- 버림: thinking, 일반 tool_result, reminder 류 attachment, compact 요약, task-notification, 메타 레코드.
- 항목마다 원본 줄 번호 `L<n>` 과 그 줄 끝의 바이트 위치를 둔다. 구간을 나눌 때 오프셋을 정확히 옮기기 위해서다.
- 자격 증명처럼 보이는 문자열은 마스킹한다(모델에 넘기기 전, 저장 전).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

MASKS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[MASKED:anthropic-key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "[MASKED:github-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"), "[MASKED:github-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[MASKED:aws-key]"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}"), "[MASKED:slack-token]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[MASKED:private-key]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "[MASKED:jwt]"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization|bearer)(\s*[:=]\s*|\s+)(['\"]?)[A-Za-z0-9_\-./+=]{16,}\3"),
     lambda m: f"{m.group(1)}{m.group(2)}[MASKED]"),
    (re.compile(r"(?i)\b(_ROBLOSECURITY|ROBLOSECURITY)=?[A-Za-z0-9_|\-]{20,}"), "[MASKED:roblox-cookie]"),
]


def mask(s: str) -> str:
    for rx, rep in MASKS:
        s = rx.sub(rep, s)
    return s


def clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + f" …(+{len(s) - n} chars)"


def one_line(s: str, n: int) -> str:
    return clip(" ".join(s.split()), n)


def is_reminderish(s: str) -> bool:
    return s.lstrip().startswith(("<system-reminder>", "<command-", "<local-command", "<task-notification>", "Caveat:"))


GIT_COMMIT_RX = re.compile(r"\bgit\b[^\n|;&]*\bcommit\b")


def tool_line(b: dict) -> str | None:
    name = b.get("name", "?")
    inp = b.get("input") or {}
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        if GIT_COMMIT_RX.search(cmd):
            m = re.search(r"-m\s+(\"|')([\s\S]*?)\1", cmd) or re.search(r"<<'?EOF'?\n([\s\S]*?)\nEOF", cmd)
            msg = m.group(m.lastindex) if m else cmd
            return "[COMMIT] " + one_line(msg.split("\n")[0], 200)
        d = inp.get("description")
        return "[Bash] " + one_line(cmd, 160) + (f"  # {one_line(str(d), 80)}" if d else "")
    if name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return f"[{name}] {inp.get('file_path') or inp.get('notebook_path', '?')}"
    if name in ("Read", "Glob", "Grep", "ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "Monitor"):
        return None
    if name in ("Agent", "Task"):
        return f"[Agent:{inp.get('subagent_type', '')}] {one_line(str(inp.get('description', '')), 80)} — {one_line(str(inp.get('prompt', '')), 240)}"
    if name == "SendMessage":
        return f"[SendMessage→{inp.get('to', '')}] {one_line(str(inp.get('message', '')), 200)}"
    if name == "AskUserQuestion":
        qs = inp.get("questions") or []
        return "[Ask] " + " / ".join(one_line(str(q.get("question", "")), 160) for q in qs if isinstance(q, dict))
    if name == "SubagentHandback":
        return "[Handback] " + clip(str(inp.get("message", "")), 1500)
    if name == "Skill":
        return f"[Skill] {inp.get('skill', '')} {one_line(str(inp.get('args', '')), 80)}".rstrip()
    return f"[{name}]"


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def _ts(o: dict) -> str:
    ts = o.get("timestamp") or ""
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return ts[5:16].replace("T", " ")


@dataclass
class Entry:
    line: int          # 원본 줄 번호(1부터)
    end_byte: int      # 이 줄 끝의 바이트 위치(다음 오프셋)
    ts: str            # 원본 timestamp(ISO)
    text: str
    human: bool = False
    human_text: str = ""
    end_line: int = 0  # end_byte 까지의 줄 수(뒤따르는 버린 줄 포함)


@dataclass
class Extract:
    entries: list[Entry] = field(default_factory=list)
    start_byte: int = 0
    end_byte: int = 0
    start_line: int = 0   # 오프셋 앞까지의 줄 수
    end_line: int = 0
    first_ts: str = ""
    last_ts: str = ""
    counts: dict = field(default_factory=dict)

    @property
    def chars(self) -> int:
        return sum(len(e.text) + 1 for e in self.entries)


def classify(o: dict, pending_tools: dict, counts: dict, line_no: int):
    """레코드 하나 → (출력 줄 | None, 사람 발언 원문 | None)."""
    t = o.get("type")
    tag = f"L{line_no} {_ts(o)}".rstrip()
    if t == "attachment":
        a = o.get("attachment") or {}
        if a.get("type") == "queued_command":
            og = a.get("origin") or {}
            p = a.get("prompt")
            if isinstance(og, dict) and og.get("kind") == "human" and isinstance(p, str):
                counts["human"] = counts.get("human", 0) + 1
                return f"[{tag} user(queued)] {clip(p, 2000)}", p
        return None, None
    if t == "user":
        og = o.get("origin") or {}
        kind = og.get("kind") if isinstance(og, dict) else None
        if o.get("isCompactSummary") or (o.get("isMeta") and kind != "peer"):
            return None, None
        c = (o.get("message") or {}).get("content")
        if isinstance(c, str):
            head = c[:600]
            if kind == "peer" or "[Subagent hand-back]" in head or "<cross-session-message" in head:
                if "[Subagent hand-back]" in head:
                    label = "subagent-report"
                    body = c.split("The report follows:", 1)[-1]
                    body = "\n".join(l[2:] if l.startswith("  ") else l for l in body.splitlines())
                else:
                    label = "peer-session"
                    m = re.search(r"from-name=\"([^\"]*)\"[^>]*>([\s\S]*?)</cross-session-message>", c)
                    body = f"({m.group(1)}) {m.group(2)}" if m else c
                body = re.sub(r"</?agent-message[^>]*>", "", body)
                counts["peer"] = counts.get("peer", 0) + 1
                return f"[{tag} {label}] {clip(body, 1500)}", None
            if kind == "task-notification" or is_reminderish(c):
                return None, None
            counts["human"] = counts.get("human", 0) + 1
            return f"[{tag} user] {clip(c, 3000)}", c
        if isinstance(c, list):
            parts, human = [], []
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and not is_reminderish(b.get("text", "")):
                    parts.append(clip(b["text"], 3000)); human.append(b["text"])
                    counts["human"] = counts.get("human", 0) + 1
                elif b.get("type") == "tool_result":
                    name = pending_tools.pop(b.get("tool_use_id"), "")
                    body = text_of(b.get("content"))
                    if name == "AskUserQuestion":
                        parts.append("[user answer] " + clip(body, 1000)); counts["ask_answer"] = counts.get("ask_answer", 0) + 1
                    elif b.get("is_error"):
                        parts.append("[tool error] " + one_line(body, 200)); counts["error"] = counts.get("error", 0) + 1
            if parts:
                who = "user" if human and len(parts) == len(human) else "user/tool"
                return f"[{tag} {who}] " + "\n".join(parts), ("\n".join(human) if human else None)
        return None, None
    if t == "assistant":
        if o.get("isSidechain"):
            return None, None
        c = (o.get("message") or {}).get("content")
        if isinstance(c, list):
            parts = []
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    parts.append(clip(b["text"], 4000))
                elif b.get("type") == "tool_use":
                    pending_tools[b.get("id")] = b.get("name")
                    ln = tool_line(b)
                    if ln:
                        parts.append(ln)
                        if ln.startswith("[COMMIT]"):
                            counts["commit"] = counts.get("commit", 0) + 1
            if parts:
                return f"[{tag} agent] " + "\n".join(parts), None
        return None, None
    if t == "system" and o.get("subtype") == "compact_boundary":
        cm = o.get("compactMetadata") or {}
        return f"[{tag} --- compact({cm.get('trigger')}, {cm.get('preTokens')} tokens) ---]", None
    return None, None


def count_lines(path: str, upto: int) -> int:
    n = 0
    with open(path, "rb") as g:
        left = upto
        while left > 0:
            b = g.read(min(left, 1 << 22))
            if not b:
                break
            n += b.count(b"\n"); left -= len(b)
    return n


def extract(path: str, from_byte: int = 0, start_line: int | None = None, to_byte: int | None = None) -> Extract:
    """from_byte 부터 to_byte(없으면 끝)까지. start_line 은 from_byte 앞의 줄 수(모르면 센다)."""
    if start_line is None:
        start_line = count_lines(path, from_byte) if from_byte else 0
    r = Extract(start_byte=from_byte, end_byte=from_byte, start_line=start_line, end_line=start_line)
    pending_tools: dict = {}
    pos, line_no = from_byte, start_line
    with open(path, "rb") as f:
        f.seek(from_byte)
        for raw in f:
            if not raw.endswith(b"\n"):
                break
            if to_byte is not None and pos >= to_byte:
                break
            line_no += 1
            pos += len(raw)
            r.end_byte, r.end_line = pos, line_no
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(o, dict):
                continue
            ts = o.get("timestamp") or ""
            if ts:
                r.first_ts = r.first_ts or ts
                r.last_ts = ts
            out, human = classify(o, pending_tools, r.counts, line_no)
            if out:
                r.entries.append(Entry(line_no, pos, ts, mask(out), human is not None, mask(human) if human else "", line_no))
            elif r.entries:
                r.entries[-1].end_byte = pos  # 버린 줄도 오프셋은 앞 항목에 붙여 넘긴다
                r.entries[-1].end_line = line_no
    return r


def chunks(entries: list[Entry], limit: int) -> list[list[Entry]]:
    out, cur, n = [], [], 0
    for e in entries:
        if n + len(e.text) > limit and cur:
            out.append(cur); cur, n = [], 0
        cur.append(e); n += len(e.text) + 1
    if cur:
        out.append(cur)
    return out


def first_timestamp(path: str, max_lines: int = 200) -> str:
    with open(path, "rb") as f:
        for i, raw in enumerate(f):
            if i >= max_lines:
                break
            try:
                ts = json.loads(raw).get("timestamp")
            except (ValueError, AttributeError):
                continue
            if ts:
                return ts
    return ""


def first_cwd(path: str, max_lines: int = 200) -> str:
    with open(path, "rb") as f:
        for i, raw in enumerate(f):
            if i >= max_lines:
                break
            try:
                c = json.loads(raw).get("cwd")
            except (ValueError, AttributeError):
                continue
            if c:
                return c
    return ""
