"""외부 저장소: ${SESSION_LOG_HOME}/<project-key>/

  project.json             {"root": 저장소 본 체크아웃 경로, "key": …}
  records/<rid>.md         세션 기록(coderag frontmatter, kind: session). rid = <세션 시작일>-<sid 앞 8자>[-파트]
  index.json               rid → 상태(pending|imported|dismissed), 가져간 위치·커밋, 절 수, 검증 합계
  .state/<sid>.json        워커 상태(바이트 오프셋, 줄 수, 실패, 비용)
  .state/<sid>.hook.json   훅 상태(compact 회차, 알림 커서, 이미 한 알림)
  .state/<sid>.lock        워커 잠금(flock), <sid>.pending(잠금 못 잡은 요청)
  .state/<sid>.compact-<n>.md  PostCompact 의 compact_summary 보관
  .state/notices.jsonl, notice.seq   요약 완료 알림 큐
  .state/errors.log
저장소 안에는 아무것도 쓰지 않는다. 저장소로 옮기는 것은 `session-log import` 뿐이다.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

from . import config
from .paths import project_key, short_home


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path: Path, obj) -> None:
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=1))


@contextlib.contextmanager
def flocked(path: Path, blocking: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        f.close()


def yaml_str(s: str) -> str:
    return json.dumps(" ".join(str(s).split()), ensure_ascii=False)


def escape_tags(s: str) -> str:
    """주입할 문자열 안의 태그처럼 보이는 것을 무력화한다."""
    return s.replace("<", "‹").replace(">", "›")


class Store:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.key = project_key(self.root)
        self.dir = config.home() / self.key
        self.records = self.dir / "records"
        self.state = self.dir / ".state"

    # ---- 기본 ----
    def ensure(self) -> None:
        self.records.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(parents=True, exist_ok=True)
        pj = self.dir / "project.json"
        if not pj.exists():
            write_json(pj, {"root": str(self.root), "key": self.key})

    def exists(self) -> bool:
        return self.dir.is_dir()

    def wstate_path(self, sid: str) -> Path:
        return self.state / f"{sid}.json"

    def hstate_path(self, sid: str) -> Path:
        return self.state / f"{sid}.hook.json"

    def wstate(self, sid: str) -> dict:
        return read_json(self.wstate_path(sid))

    def save_wstate(self, sid: str, st: dict) -> None:
        write_json(self.wstate_path(sid), st)

    def hstate(self, sid: str) -> dict:
        return read_json(self.hstate_path(sid))

    def save_hstate(self, sid: str, st: dict) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        write_json(self.hstate_path(sid), st)

    def log_error(self, msg: str) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        with open(self.state / "errors.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")

    def errors_since(self, ts: float) -> int:
        p = self.state / "errors.log"
        try:
            if p.stat().st_mtime < ts:
                return 0
            n = 0
            for ln in p.read_text(encoding="utf-8").splitlines():
                try:
                    if datetime.fromisoformat(ln.split(" ", 1)[0]).timestamp() >= ts:
                        n += 1
                except ValueError:
                    pass
            return n
        except OSError:
            return 0

    # ---- index ----
    @contextlib.contextmanager
    def index_tx(self):
        self.ensure()
        with flocked(self.state / "index.lock"):
            idx = read_json(self.dir / "index.json", {})
            yield idx
            write_json(self.dir / "index.json", idx)

    def index(self) -> dict:
        return read_json(self.dir / "index.json", {})

    def record_path(self, rid: str) -> Path:
        return self.records / f"{rid}.md"

    @staticmethod
    def is_pending(e: dict) -> bool:
        if e.get("status") == "dismissed":
            return False
        if e.get("status") == "imported":
            return e.get("sections", 0) > e.get("imported_sections", 0)
        return True

    def pending(self) -> list[dict]:
        out = [dict(e, rid=rid) for rid, e in self.index().items() if self.is_pending(e)]
        out.sort(key=lambda e: e.get("created", ""))
        return out

    def pending_summary(self) -> tuple[int, str, int]:
        p = self.pending()
        if not p:
            return 0, "", 0
        oldest = p[0].get("created", "")[:10]
        try:
            days = (date.today() - date.fromisoformat(oldest)).days
        except ValueError:
            days = 0
        return len(p), oldest, days

    # ---- 알림 큐 ----
    def notice_seq(self) -> int:
        try:
            return int((self.state / "notice.seq").read_text().strip() or 0)
        except (OSError, ValueError):
            return 0

    def push_notice(self, notice: dict) -> None:
        self.ensure()
        with flocked(self.state / "notice.lock"):
            seq = self.notice_seq() + 1
            notice = dict(notice, seq=seq, ts=datetime.now().isoformat(timespec="seconds"))
            with open(self.state / "notices.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(notice, ensure_ascii=False) + "\n")
            atomic_write(self.state / "notice.seq", str(seq))

    def notices_after(self, seq: int) -> list[dict]:
        out = []
        try:
            with open(self.state / "notices.jsonl", encoding="utf-8") as f:
                for ln in f:
                    try:
                        n = json.loads(ln)
                    except ValueError:
                        continue
                    if n.get("seq", 0) > seq:
                        out.append(n)
        except OSError:
            pass
        return out

    # ---- 기록 파일 ----
    def append_section(self, sid: str, st: dict, section: str, desc: str, kws: list[str], counts: dict,
                       model: str, transcript: str) -> str:
        """세션 기록에 절 하나를 덧붙이고 index 를 갱신한다. 돌려주는 값은 rid."""
        self.ensure()
        max_bytes = int(config.num("SESSION_LOG_RECORD_MAX_KB") * 1024)
        start_day = (st.get("started") or datetime.now().isoformat())[:10]
        part = st.get("part", 1)
        rid = f"{start_day}-{sid[:8]}" + (f"-{part}" if part > 1 else "")
        path = self.record_path(rid)
        if path.exists() and path.stat().st_size > max_bytes:
            part += 1
            rid = f"{start_day}-{sid[:8]}-{part}"
            path = self.record_path(rid)
        st["part"] = part
        meta = st.setdefault("meta", {})
        pm = meta.setdefault(str(part), {"descs": [], "kws": [], "verify": {}, "sections": 0})
        if desc:
            pm["descs"].append(desc)
        pm["kws"] = list(dict.fromkeys(pm["kws"] + kws))[:12]
        for k, v in counts.items():
            pm["verify"][k] = pm["verify"].get(k, 0) + v
        pm["sections"] += 1
        body = ""
        if path.exists():
            text = path.read_text(encoding="utf-8")
            m = re.match(r"^---\n[\s\S]*?\n---\n", text)
            body = text[m.end():] if m else text
        if not body.strip():
            body = f"# 세션 {sid[:8]}" + (f" (파트 {part})" if part > 1 else "") + "\n"
        body = body.rstrip("\n") + "\n\n" + section.strip("\n") + "\n"
        v = pm["verify"]
        fm = [
            "---",
            f"title: {yaml_str(f'세션 {sid[:8]} — ' + (pm['descs'][0] if pm['descs'] else ''))}",
            f"description: {yaml_str((pm['descs'][-1] if pm['descs'] else '')[:120])}",
            "keywords: [" + ", ".join(yaml_str(k) for k in pm["kws"]) + "]",
            "kind: session",
            "status: active",
            f"last_verified: {date.today().isoformat()}",
            f"session_id: {sid}",
            f"project: {self.root.name}",
            f"project_root: {short_home(self.root)}",
            f"source_transcript: {short_home(transcript)}",
            f"summarizer: {model}",
            "verify: {" + ", ".join(f"{k}: {v.get(k, 0)}" for k in ("items", "num_missing", "quote_bad", "cite_off", "cite_bad", "dropped")) + "}",
        ]
        if part > 1:
            fm.append(f"part: {part}")
        fm.append("---")
        atomic_write(path, "\n".join(fm) + "\n" + body)
        now = datetime.now().isoformat(timespec="seconds")
        with self.index_tx() as idx:
            e = idx.setdefault(rid, {"session_id": sid, "file": f"records/{rid}.md", "created": now, "status": "pending"})
            e["updated"] = now
            e["sections"] = pm["sections"]
            e["description"] = pm["descs"][-1] if pm["descs"] else ""
            e["verify"] = dict(v)
            e["session_started"] = start_day
        return rid

    # ---- import / dismiss ----
    def resolve_commit(self, e: dict) -> str:
        to = e.get("imported_to")
        if not to or e.get("imported_commit"):
            return e.get("imported_commit", "")
        try:
            out = subprocess.run(["git", "-C", str(self.root), "log", "-1", "--format=%h", "--", to],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return out

    def mark(self, rid: str, **fields) -> None:
        with self.index_tx() as idx:
            if rid not in idx:
                raise KeyError(rid)
            idx[rid].update(fields)


def token_estimate(text: str) -> int:
    """coderag §21.2 추정식: 0.4×ASCII + 1.6×한글 음절 + 1.5×그 밖 + 3×줄."""
    a = h = o = 0
    for ch in text:
        c = ord(ch)
        if c < 128:
            a += 1
        elif 0xAC00 <= c <= 0xD7A3:
            h += 1
        else:
            o += 1
    return int(0.4 * a + 1.6 * h + 1.5 * o + 3 * text.count("\n"))


def fmt_tokens(n: int) -> str:
    return f"~{n / 1000:.1f}k"


def parse_sections(text: str) -> list[dict]:
    """기록 본문 → [{head, meta, parts: {절 이름: [항목]}}]."""
    out: list[dict] = []
    cur = None
    sub = None
    for ln in text.splitlines():
        if ln.startswith("## "):
            cur = {"head": ln[3:].strip(), "meta": "", "parts": {}}
            out.append(cur); sub = None
            continue
        if cur is None:
            continue
        if ln.startswith("id: ") and not cur["meta"]:
            cur["meta"] = ln
            continue
        if ln.startswith("### "):
            sub = ln[4:].strip(); cur["parts"][sub] = []
            continue
        if sub is not None and ln.strip():
            cur["parts"][sub].append(ln.rstrip())
    return out


def now_ts() -> float:
    return time.time()
