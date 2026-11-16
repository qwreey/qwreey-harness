"""handback_notice: 검토가 아닌 서브에이전트의 보고에 권고, 선택지, 열린 질문이 있으면 메인에게 info 한 줄을 낸다(보고마다 한 번).

메인이 서브에이전트의 추천안을 확인 없이 사용자에게 넘기면 그 안은 그 에이전트 혼자 본 것이다. 이 알림은 넘기기 전에
inherit-advisor 나 fresh-advisor 가 볼 수 있다는 것만 알린다.

전달 경로(실측, claude 2.1.316)
  - SubagentStop 이 먼저 돈다. 입력에 last_assistant_message 가 있고, SubagentHandback 으로 끝낸 에이전트는 보고가
    transcript 끝의 SubagentHandback 호출 입력(message)에 있다. 여기서 분류해 세션 상태 파일에 남긴다.
    메인이 띄운 것만(옆의 meta.json 에 parentAgentId 가 없고 spawnDepth 1) 대기로 둔다.
  - 메인이 쉬고 있으면 보고가 새 턴으로 들어오고 UserPromptSubmit 이 그 글(`<task-notification>` 의 <result>, 또는
    `<agent-message from="<id>">` 의 [Subagent hand-back])을 prompt 로 받는다. 이 경로는 prompt 를 직접 분류하므로 상태가 없어도 된다.
  - 메인이 일하는 중이면 보고가 다음 도구 결과와 함께 붙고 UserPromptSubmit 은 돌지 않는다. 그래서 메인의 PostToolBatch 가
    대기 중인 것을 낸다. 같은 묶음에서 메인이 리뷰어나 inherit-advisor fork 를 띄웠으면 이미 검토하는 중이라 내지 않는다.
분류는 기계적 휴리스틱이다: 제목 줄(마크다운 제목, 줄 전체 굵게, 콜론으로 끝나는 짧은 줄)의 권고, 제안, 열린 질문 같은 말이
하나라도 있거나, 본문 문구 신호가 둘 이상이면 낸다. 코드 블록은 보지 않는다.
토론 입장문(설명이 debate 나 토론으로 시작)은 메인이 종합할 재료라 내지 않는다. 이어 받은 에이전트는 보고 내용이 바뀌면 다시 본다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import textwrap
import time

try:
    import fcntl
except ImportError:  # Windows: 잠그지 않는다(같은 세션의 SubagentStop 이 겹칠 때만 한 줄을 잃을 수 있다)
    fcntl = None

NS = "claude-second-opinion"
KEEP_SECONDS = 3 * 24 * 3600  # 상태 파일에 남겨 둘 기간
TAIL_BYTES = 512 * 1024
FENCE = re.compile(r"```.*?```", re.S)
HEADLINE = re.compile(r"(?m)^\s{0,3}(?:(?:[-*]|\d+[.)])\s+)?(?:#{1,6}\s+(?P<h>[^\n]{1,80})|\*\*(?P<b>[^*\n]{1,80})\*\*:?\s*$|(?P<c>[^\n:]{1,50}):\s*$)")
HEAD_KEY = re.compile(
    r"(?i)\b(recommendations?|recommended|proposals?|proposed changes?|suggestions?|open questions?|questions? for (?:you|the user|main)|"
    r"decisions? (?:needed|pending|for (?:you|the user|main))|to decide|choices for (?:you|the user)|options for)\b|"
    r"(권고|추천|제안|선택지|결정 필요|필요한 결정|결정할|사용자 결정|미결|열린 질문|사용자에게 물을|사용자 질문|확인 대기)")
PHRASE = re.compile(
    r"(?i)\b(?:open questions?|recommendation)\s*:|"
    r"\b(?:I recommend|I'd recommend|my recommendation|your call|"
    r"the user(?:'s)? (?:to decide|decision|should decide|call)|for you to decide|needs? (?:your|the user's) (?:decision|confirmation|approval)|"
    r"pending (?:user )?(?:confirmation|decision)|awaiting (?:your |a )?decision|do you want)\b|\(recommended\)|"
    r"권장한다|권합니다|추천한다|추천합니다|제안한다|제안합니다|사용자 결정이? 필요|사용자 결정입니다|사용자가 정할|사용자 판단이? 필요|"
    r"결정이 필요|결정해 주|정해 주세요|어느 쪽[이을]|할까요\?")
QLINE = re.compile(r"(?m)^\s*(?:[-*]\s*|\|\s*)?(?:\*\*)?(?:Q\d+|Option [A-Z0-9]|선택지 ?\d|안 ?[A-D1-4][.):])")
HANDBACK = re.compile(r'<agent-message from="([^"]+)">\s*\[Subagent hand-back\]')
TASK = re.compile(r"<task-notification>\s*<task-id>([^<]+)</task-id>")
SUMMARY = re.compile(r'<summary>Agent "(.*?)" ')
STUB = "report was delivered to you as a message"  # SubagentHandback 을 쓴 에이전트의 task-notification 은 본문 대신 이 안내만 싣는다
REVIEW_TEXT = re.compile(r"\[qwreey-advisor run: |\[second opinion: |\[qwreey-advisor:inherit\]")
DEBATE = re.compile(r"(?i)^\s*(debate|토론)")  # qwreey-debate 스킬이 토론자 설명을 `debate:` 로 시작하게 한다


def signals(text: str) -> set[str]:
    text = FENCE.sub("", text or "")
    heads, phr = set(), set()
    for m in HEADLINE.finditer(text):
        k = HEAD_KEY.search(m.group("h") or m.group("b") or m.group("c") or "")
        if k:
            heads.add("head:" + (k.group(1) or k.group(2)).lower())
    for m in PHRASE.finditer(text):
        phr.add(re.sub(r"\s+", " ", m.group(0)).lower())
    if len(QLINE.findall(text)) >= 2:
        phr.add("qlines")
    return heads | phr


def carries_decisions(text: str) -> bool:
    s = signals(text)
    return any(x.startswith("head:") for x in s) or len(s) >= 2


def state_path(sid: str) -> str:
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^\w-]", "", sid or "nosession") + ".handbacks.json")


class State:
    """세션의 에이전트별 기록 {agent_id: {t, label, hit, pending, done}}. with 블록 동안 잠근다."""

    def __init__(self, sid: str):
        self.path = state_path(sid)
        self.agents: dict = {}
        self.dirty = False

    def __enter__(self):
        self.lock = open(self.path + ".lock", "a")
        if fcntl:
            fcntl.flock(self.lock, fcntl.LOCK_EX)
        try:
            self.agents = json.load(open(self.path)).get("agents", {})
        except (OSError, ValueError, AttributeError):
            self.agents = {}
        return self

    def __exit__(self, *exc):
        if self.dirty:
            now = time.time()
            keep = {k: v for k, v in self.agents.items() if now - v.get("t", now) < KEEP_SECONDS}
            tmp = self.path + ".tmp"
            json.dump({"agents": keep}, open(tmp, "w"))
            os.replace(tmp, self.path)
        self.lock.close()
        return False

    def put(self, aid: str, **kw):
        self.agents[aid] = {**self.agents.get(aid, {}), **kw}
        self.dirty = True


def has_state(sid: str) -> bool:
    return os.path.exists(state_path(sid))


def handback_message(tpath: str) -> str:
    """transcript 끝의 마지막 SubagentHandback 호출 입력(message). 없으면 빈 값."""
    try:
        with open(tpath or "", "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        if '"SubagentHandback"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for b in reversed((rec.get("message") or {}).get("content") or []):
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "SubagentHandback":
                return str((b.get("input") or {}).get("message") or "")
    return ""


def digest(text: str) -> str:
    return hashlib.sha1((text or "").strip().encode("utf-8", "replace")).hexdigest()[:12]


def label_of(meta: dict, data: dict) -> str:
    raw = meta.get("description") or data.get("agent_type") or "subagent"
    return re.sub(r"[`<>\"\n\r]", "", str(raw))[:60]


def on_stop(data: dict, meta: dict, review: bool, is_nested: bool | None) -> None:
    aid = str(data.get("agent_id") or "")
    if not aid:
        return
    text = "\n".join(x for x in (data.get("last_assistant_message") or "", handback_message(data.get("agent_transcript_path") or "")) if x)
    h = digest(text)
    with State(data.get("session_id") or "") as st:
        old = st.agents.get(aid, {})
        if old.get("done") and (old.get("review") or old.get("h") == h):  # 같은 보고는 한 번만, 이어 받아 새 보고면 다시 본다
            return
        if review:
            st.put(aid, t=time.time(), review=True, done=True)
            return
        if is_nested is not False:  # 일꾼이 띄운 것이거나 알 수 없음: 대기로 두지 않는다(메인의 UserPromptSubmit 경로는 그대로)
            return
        label = label_of(meta, data)
        st.agents[aid] = {"t": time.time(), "label": label, "h": h, "pending": True,
                          "hit": carries_decisions(text) and not DEBATE.search(label)}
        st.dirty = True


def parse_prompt(prompt: str) -> tuple[str, str, str] | None:
    """(agent_id, 보고 본문, 설명). 서브에이전트 보고가 아니면 None. 본문이 안내뿐이면 빈 값."""
    m = HANDBACK.search(prompt)
    if m:
        body = prompt[m.end():]
        body = body.split("The report follows:", 1)[-1]
        return m.group(1), textwrap.dedent(body.lstrip("\n")), ""
    m = TASK.search(prompt)
    if m and "<result>" in prompt:
        s = SUMMARY.search(prompt)
        body = prompt.split("<result>", 1)[1].rsplit("</result>", 1)[0]
        return m.group(1).strip(), ("" if STUB in body else body), (s.group(1) if s else "")
    return None


def due(entry: dict, reviewed_at: float) -> bool:
    return bool(entry.get("hit")) and not entry.get("done") and not entry.get("review") and reviewed_at < entry.get("t", 0)


def on_prompt(data: dict, reviewed_at: float) -> list[str]:
    """메인의 UserPromptSubmit. 이 prompt 가 서브에이전트 보고면 그 에이전트만 본다."""
    got = parse_prompt(str(data.get("prompt") or ""))
    if not got:
        return []
    aid, body, desc = got
    with State(data.get("session_id") or "") as st:
        e = st.agents.get(aid)
        hb = digest(body) if body else ""
        if e is not None and body and e.get("done") and not e.get("review") and e.get("hb") and e["hb"] != hb:
            e = None  # 이어 받은 에이전트의 새 보고(SubagentStop 이 다시 보지 못한 경우)
        if e is None:
            if not body:
                return []
            label = re.sub(r"[`<>\"\n\r]", "", desc)[:60] or "subagent"
            e = {"t": time.time(), "label": label,
                 "hit": carries_decisions(body) and not REVIEW_TEXT.search(body) and not DEBATE.search(label)}
        if hb:
            e = {**e, "hb": hb}
        if not due(e, reviewed_at):
            if not e.get("done") and (body or e.get("review")):
                st.put(aid, **{**e, "done": True})
            return []
        st.put(aid, **{**e, "done": True})
        return [e.get("label") or "subagent"]


def starts_review(call: dict) -> bool:
    ti = call.get("tool_input") or {}
    st = ti.get("subagent_type") or ""
    return st in ("qwreey-advisor:reviewer", "qwreey-advisor-reviewer") or (st == "fork" and str(ti.get("prompt") or "").startswith("[qwreey-advisor:inherit]"))


def on_batch(data: dict, reviewed_at: float) -> list[str]:
    """메인의 PostToolBatch. 일하는 중에 붙은 보고 가운데 아직 알리지 않은 것."""
    reviewing = any(starts_review(c) for c in data.get("tool_calls") or [] if isinstance(c, dict))
    out = []
    with State(data.get("session_id") or "") as st:
        for aid, e in list(st.agents.items()):
            if e.get("done") or not e.get("pending"):
                continue
            if due(e, reviewed_at) and not reviewing:
                out.append(e.get("label") or "subagent")
            st.put(aid, done=True)
    return out


def message(labels: list[str]) -> str:
    names = ", ".join(f'"{x}"' for x in labels)
    subj = f"The report from subagent {names} carries" if len(labels) == 1 else f"The reports from subagents {names} carry"
    return (f"{subj} recommendations, options or open questions. If you will pass them to the user to decide, they rest on that "
            f"agent's check alone; `qwreey-advisor:inherit-advisor` (tests your reasoning) or `qwreey-advisor:fresh-advisor` "
            f"(tests the framing) can look first. Skip this for facts you verified yourself or questions you only relay.")
