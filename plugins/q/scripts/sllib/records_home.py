"""기록 보관 위치(records home) 설정과 import 사본의 머리말.

설정은 저장소 안 `.claude/session-log.json` 에 둔다. 이유: 외부 저장소의 project.json 은 이 기계에만 있어 동료와 공유되지
않고, `.claude/conventions.json` 은 qwreey-conventions 플러그인의 스키마라 q 가 키를 얹으면 두 플러그인이 서로의 파일을
검증·덮어쓰게 된다. q 전용 파일이면 커밋하는 것만으로 팀이 같은 위치를 쓰고 소유도 분명하다.

  {"records_home": "docs/sessions"}   기록을 이 폴더(저장소 상대 경로)로 import 한다
  {"archive_only": true}             기록은 저장소 밖에만 두고 pending 알림을 끈다
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

FILE = ".claude/session-log.json"
DEFAULT_HOME = ".claude/records"
# 이미 있으면 기록 보관 위치로 제안할 만한 이력 폴더
HISTORY_CANDIDATES = ("handover", "handoff", "audit", "history", "docs/history", "docs/handoff")


def load(root: str | os.PathLike) -> dict:
    try:
        with open(os.path.join(str(root), FILE), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def archive_only(root) -> bool:
    return bool(load(root).get("archive_only"))


def home_rel(root) -> str | None:
    """설정된 보관 폴더(저장소 상대, 끝 `/` 없음). 없거나 저장소 밖을 가리키면 None."""
    h = load(root).get("records_home")
    if not isinstance(h, str) or not h.strip():
        return None
    p = os.path.normpath(h.strip())
    return None if os.path.isabs(p) or p == ".." or p.startswith("../") else p


def normalize(root, path: str) -> str:
    """사용자가 준 경로를 저장소 상대 경로로. 저장소 밖이면 ValueError."""
    p = os.path.normpath(path if os.path.isabs(path) else os.path.join(str(root), path))
    rel = os.path.relpath(p, os.path.normpath(str(root)))
    if rel == "." or rel == ".." or rel.startswith("../"):
        raise ValueError(f"저장소 안의 하위 폴더여야 한다: {path}")
    return rel


def save(root, *, home: str | None = None, archive: bool = False, unset: bool = False) -> dict:
    d = load(root)
    d.pop("records_home", None)
    d.pop("archive_only", None)
    if not unset:
        if archive:
            d["archive_only"] = True
        elif home:
            d["records_home"] = normalize(root, home)
    p = Path(root) / FILE
    if d:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif p.exists():
        p.unlink()
    return d


def history_dirs(root) -> list[str]:
    return [c + "/" for c in HISTORY_CANDIDATES if os.path.isdir(os.path.join(str(root), c))]


def is_under(path: str, directory: str) -> bool:
    p, d = os.path.normpath(path), os.path.normpath(directory)
    return p == d or p.startswith(d + os.sep)


# ---- import 사본의 머리말 ----
FM_RX = re.compile(r"^---\n[\s\S]*?\n---\n")
HEAD_RX = re.compile(r"^## (.+?) · ", re.M)


def _fm(text: str, key: str) -> str:
    m = re.search(rf"^{key}: (.*)$", text, re.M)
    return m.group(1).strip().strip('"') if m else ""


def period(text: str) -> str:
    """절 머리(`## 2026-11-10 01:00–02:00 · 트리거`)에서 덮는 기간. 없으면 빈 문자열."""
    heads = HEAD_RX.findall(text)
    if not heads:
        return ""
    first, last = heads[0], heads[-1]
    start = first.split(" – ")[0] if " – " in first else first.split("–")[0]
    if " – " in last:
        end = last.split(" – ")[1]
    elif "–" in last:
        end = last[:10] + " " + last.split("–")[1] if len(last) > 10 else last
    else:
        end = last
    return start.strip() if start.strip() == end.strip() else f"{start.strip()} ~ {end.strip()}"


def with_header(text: str, rid: str) -> str:
    """frontmatter 바로 뒤에 두 줄 머리말을 끼운다(내용은 그대로). 기록은 스냅샷이고 낡았을 수 있다는 경고가 목적이다."""
    sid8 = (_fm(text, "session_id") or rid)[:8]
    src = _fm(text, "source_transcript") or "?"
    head = (f"> 세션 {sid8} 기록 · 기간 {period(text) or '?'} · 원본 트랜스크립트 {src}\n"
            "> 그 시점의 스냅샷이라 지금과 다를 수 있다. 결정이나 사실에 기대기 전에 현재 파일과 git log 로 확인한다.\n\n")
    m = FM_RX.match(text)
    return text[:m.end()] + "\n" + head + text[m.end():] if m else head + text
