#!/usr/bin/env python3
"""세션 트랜스크립트(JSONL)를 요약 모델에 넘길 짧은 텍스트로 줄인다. (프로토타입)

- 바이트 오프셋부터 읽는다(증분). 마지막 줄이 아직 '\n' 으로 끝나지 않았으면 읽지 않고 남긴다
  (트랜스크립트는 비동기로 써져 훅 시점에 마지막 줄이 덜 써졌을 수 있다).
- 남기는 것: 사람 발언(typed + 작업 중 큐에 넣은 발언), 어시스턴트 text, 도구 호출 한 줄 요약,
  AskUserQuestion 의 답, 오류 tool_result 앞부분, 서브에이전트 보고(앞부분), git commit 메시지.
- 버리는 것: thinking, 일반 tool_result, system-reminder 류 attachment, compact 요약(이전 기록과 중복),
  task-notification, 메타 레코드(mode, ai-title, cost-state ...).
- 각 줄에 원본 줄 번호 `L<n>` 을 붙인다. 요약이 근거 줄을 인용하게 하고 verify.py 가 그 줄과 대조한다.
- 자격 증명처럼 보이는 문자열은 여기서 마스킹한다(요약 모델에 넘기기 전).

사용: python3 -I extract.py <transcript.jsonl> [--from-byte N] [--max-chars N] [--json]
출력: 텍스트(stdout). --json 이면 {"text","start_byte","end_byte","end_line","counts"}.
"""
from __future__ import annotations

import json
import re
import sys

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
    return s if len(s) <= n else s[:n] + f" …(+{len(s) - n}자)"

def one_line(s: str, n: int) -> str:
    return clip(" ".join(s.split()), n)

def is_reminderish(s: str) -> bool:
    return s.lstrip().startswith(("<system-reminder>", "<command-", "<local-command", "<task-notification>", "Caveat:"))

GIT_COMMIT_RX = re.compile(r"git\b[^\n|;&]*\bcommit\b")

def tool_line(b: dict) -> str | None:
    name = b.get("name", "?")
    inp = b.get("input") or {}
    if name == "Bash":
        cmd = inp.get("command", "")
        if GIT_COMMIT_RX.search(cmd):
            m = re.search(r"-m\s+(\"|')([\s\S]*?)\1", cmd) or re.search(r"<<'?EOF'?\n([\s\S]*?)\nEOF", cmd)
            msg = (m.group(m.lastindex) if m else cmd)
            return "[COMMIT] " + one_line(msg.split("\n")[0], 200)
        d = inp.get("description")
        return "[Bash] " + one_line(cmd, 160) + (f"  # {one_line(d, 80)}" if d else "")
    if name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return f"[{name}] {inp.get('file_path') or inp.get('notebook_path', '?')}"
    if name in ("Read", "Glob", "Grep", "ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "Monitor"):
        return None  # 조사성 호출은 잡음
    if name in ("Agent", "Task"):
        return f"[Agent:{inp.get('subagent_type', '')}] {one_line(inp.get('description', ''), 80)} — {one_line(inp.get('prompt', ''), 240)}"
    if name == "SendMessage":
        return f"[SendMessage→{inp.get('to', '')}] {one_line(str(inp.get('message', '')), 200)}"
    if name == "AskUserQuestion":
        qs = inp.get("questions") or []
        return "[Ask] " + " / ".join(one_line(q.get("question", ""), 160) for q in qs if isinstance(q, dict))
    if name == "SubagentHandback":
        return "[Handback] " + clip(str(inp.get("message", "")), 1500)
    if name.startswith("mcp__"):
        return f"[{name}]"
    return f"[{name}]"

def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""

def extract(path: str, from_byte: int = 0, max_chars: int = 0):
    out: list[str] = []
    counts = {"human": 0, "assistant_text": 0, "tool": 0, "subagent_report": 0, "commit": 0, "ask_answer": 0, "error": 0}
    pending_tools: dict[str, str] = {}  # tool_use_id -> name (AskUserQuestion 답을 잡기 위해)
    total = 0
    with open(path, "rb") as f:
        f.seek(from_byte)
        pos = from_byte
        # 첫 줄 번호를 알려면 앞부분 줄 수를 세야 한다(프로토타입: 그냥 센다).
        line_no = 0
        if from_byte:
            with open(path, "rb") as g:
                line_no = g.read(from_byte).count(b"\n")
        end_line = line_no
        for raw in f:
            if not raw.endswith(b"\n"):
                break  # 덜 써진 마지막 줄은 다음 실행에서
            line_no += 1
            if max_chars and total > max_chars:
                break
            pos += len(raw)
            end_line = line_no
            try:
                o = json.loads(raw)
            except Exception:
                continue
            t = o.get("type")
            ts = (o.get("timestamp") or "")[5:16].replace("T", " ")
            tag = f"L{line_no} {ts}"
            emit = None
            if t == "attachment":
                a = o.get("attachment") or {}
                if a.get("type") == "queued_command":
                    og = a.get("origin") or {}
                    p = a.get("prompt")
                    if isinstance(og, dict) and og.get("kind") == "human" and isinstance(p, str):
                        emit = f"[{tag} 사람(작업 중)] {clip(p, 2000)}"; counts["human"] += 1
            elif t == "user":
                if o.get("isCompactSummary") or o.get("isMeta") and not (o.get("origin") or {}).get("kind") == "peer":
                    continue
                msg = o.get("message") or {}
                c = msg.get("content")
                og = o.get("origin") or {}
                kind = og.get("kind") if isinstance(og, dict) else None
                if isinstance(c, str):
                    if kind == "peer" or "[Subagent hand-back]" in c[:400] or "<cross-session-message" in c[:400]:
                        if "[Subagent hand-back]" in c[:600]:
                            label = "서브에이전트 보고"
                            body = c.split("The report follows:", 1)[-1]
                            body = "\n".join(l[2:] if l.startswith("  ") else l for l in body.splitlines())
                        else:
                            label = "다른 세션 메시지"
                            m = re.search(r"from-name=\"([^\"]*)\"[^>]*>([\s\S]*?)</cross-session-message>", c)
                            body = f"({m.group(1)}) {m.group(2)}" if m else c
                        body = re.sub(r"</?agent-message[^>]*>", "", body)
                        emit = f"[{tag} {label}] {clip(body, 1500)}"; counts["subagent_report"] += 1
                    elif kind == "task-notification" or is_reminderish(c):
                        continue
                    else:
                        emit = f"[{tag} 사람] {clip(c, 3000)}"; counts["human"] += 1
                elif isinstance(c, list):
                    parts = []
                    for b in c:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text" and not is_reminderish(b.get("text", "")):
                            parts.append(clip(b["text"], 3000)); counts["human"] += 1
                        elif b.get("type") == "tool_result":
                            name = pending_tools.pop(b.get("tool_use_id"), "")
                            body = text_of(b.get("content"))
                            if name == "AskUserQuestion":
                                parts.append("[사용자 답] " + clip(body, 1000)); counts["ask_answer"] += 1
                            elif b.get("is_error"):
                                parts.append("[도구 오류] " + one_line(body, 200)); counts["error"] += 1
                    if parts:
                        emit = f"[{tag} 사람/도구] " + "\n".join(parts)
            elif t == "assistant":
                if o.get("isSidechain"):
                    continue
                c = (o.get("message") or {}).get("content")
                if isinstance(c, list):
                    parts = []
                    for b in c:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text" and b.get("text", "").strip():
                            parts.append(clip(b["text"], 4000)); counts["assistant_text"] += 1
                        elif b.get("type") == "tool_use":
                            pending_tools[b.get("id")] = b.get("name")
                            ln = tool_line(b)
                            if ln:
                                parts.append(ln); counts["tool"] += 1
                                if ln.startswith("[COMMIT]"):
                                    counts["commit"] += 1
                    if parts:
                        emit = f"[{tag} 에이전트] " + "\n".join(parts)
            elif t == "system" and o.get("subtype") == "compact_boundary":
                cm = o.get("compactMetadata") or {}
                emit = f"[{tag} --- compact({cm.get('trigger')}, {cm.get('preTokens')} tokens) ---]"
            if emit:
                emit = mask(emit)
                out.append(emit)
                total += len(emit)
    return {"text": "\n".join(out), "start_byte": from_byte, "end_byte": pos, "end_line": end_line, "counts": counts}

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(2)
    path = args[0]
    fb = int(args[args.index("--from-byte") + 1]) if "--from-byte" in args else 0
    mc = int(args[args.index("--max-chars") + 1]) if "--max-chars" in args else 0
    r = extract(path, fb, mc)
    if "--json" in args:
        json.dump(r, sys.stdout, ensure_ascii=False)
    else:
        sys.stdout.write(r["text"] + "\n")
        sys.stderr.write(f"bytes {r['start_byte']}..{r['end_byte']} lines..{r['end_line']} chars {len(r['text'])} {r['counts']}\n")

if __name__ == "__main__":
    main()
