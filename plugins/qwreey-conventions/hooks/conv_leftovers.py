"""conventions-check.py 의 Stop 보고용 "남은 기존 문제" 기록과 메시지. 검사 함수(check_lines, invisible_lines)는 호출한 쪽이 넘긴다(순환 import 를 피하려고)."""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conv_docs import doc_check, doc_class  # noqa: E402

NS = "claude-conventions"  # 상태 경로는 이름 변경 전과 같게 둔다


# ---------- 남은 기존 주석 보고 ----------
# 편집할 때마다 "이번에 추가하지 않은 줄"의 문제를 범주별로 세어 (세션, 호출한 쪽)별 파일에 조용히 쌓고,
# 메인 에이전트의 Stop 에서 사용자에게 한 줄(systemMessage)로 보여 준다. 모델 턴을 늘리지 않고 고치지도 않는다.
LEFT_LABEL = {"history marker": "이력", "Ref tail without a reason sentence": "이력", "non-keyboard symbol": "기호",
              "escaped character": "이스케이프", "invisible character": "보이지 않는 문자"}
LEFT_MAX_FILES = 5


def left_dir():
    import tempfile
    d = os.path.join(tempfile.gettempdir(), NS)
    os.makedirs(d, exist_ok=True)
    return d


def left_path(sid, agent_id, d=None):
    who = re.sub(r"[^\w-]", "", str(agent_id)) if agent_id else "main"
    return os.path.join(d or left_dir(), re.sub(r"[^\w-]", "", str(sid or "nosession")) + ".left." + who + ".json")


def record_leftovers(data, path, rel, kind, text, added, rows, cfg, pats, pub, check_lines, invisible_lines):
    """이번 편집에서 추가하지 않은 줄의 문제를 범주별 줄 수로 세어 쌓는다. 같은 파일은 마지막 편집 기준으로 덮어쓴다."""
    try:
        old = set(range(text.count("\n") + 1)) - added
        probs = check_lines(rows, old, pats, pub, cfg) if kind == "comment" else doc_check(text, old, rel, cfg, pats, pub)
        probs += [(ln, "invisible character") for ln in invisible_lines(text, old)]
        cnt = Counter()
        for ln, cat in set(probs):
            cnt[LEFT_LABEL.get(cat, cat)] += 1
        fp = left_path(data.get("session_id"), data.get("agent_id"))
        try:
            rec = json.load(open(fp))
        except Exception:
            rec = {}
        key = os.path.abspath(path)
        if cnt:
            import time
            rec[key] = {"rel": rel, "n": dict(cnt), "t": time.time()}
        elif key in rec:
            del rec[key]
        else:
            return
        data = json.dumps(rec, ensure_ascii=False).encode("utf-8")  # 서로게이트가 들면 여기서 끝나 옛 파일이 남는다
        with open(fp, "wb") as f:
            f.write(data)
    except Exception:
        pass


def _latest(pattern):
    """같은 파일의 여러 호출한 쪽 기록 중 가장 최근 것. {절대 경로: 기록}."""
    import glob
    best = {}
    for fp in glob.glob(pattern):
        try:
            for k, v in json.load(open(fp)).items():
                if k not in best or v["t"] > best[k]["t"]:
                    best[k] = v
        except Exception:
            continue
    return best


def leftover_message(sid, d=None):
    """세션의 모든 호출한 쪽 기록을 합쳐 사용자용 글. 첫 줄은 전부터 있던 문제(주석, 같은 목록), 둘째 줄은 원본과 달라진 사본. 없으면 None.
    같은 목록과 사본 기록은 reuse-check 가 따로 쓴다(두 훅이 한 파일을 동시에 고쳐 쓰지 않게)."""
    base = os.path.join(d or left_dir(), re.sub(r"[^\w-]", "", str(sid or "nosession")))
    left, reuse = _latest(base + ".left.*.json"), _latest(base + ".reuse.*.json")
    rows, diff = {}, []
    for k, v in left.items():
        if v["n"] and os.path.exists(k):
            rows[k] = (v["rel"], dict(v["n"]))
    for k, v in reuse.items():
        if not os.path.exists(k):
            continue
        if v.get("dup"):
            rows.setdefault(k, (v["rel"], {}))[1]["같은 목록이 두 곳"] = v["dup"]
        if v.get("differ"):
            diff.append((v["rel"], v["differ"]))
    order = ["이력", "기호", "이스케이프", "보이지 않는 문자", "같은 목록이 두 곳"]
    items = sorted(rows.values(), key=lambda r: r[0])  # 상대 경로만 견준다: 두 저장소의 같은 경로에서 dict 끼리 견주지 않게
    lines = []
    if items:
        shown = ", ".join(f"{rel}(" + ", ".join(f"{c} {n[c]}" for c in order if c in n) + ")" for rel, n in items[:LEFT_MAX_FILES])
        more = f" 외 {len(items) - LEFT_MAX_FILES}개" if len(items) > LEFT_MAX_FILES else ""
        cats = {c for _, n in items for c in n}
        is_doc = [bool(doc_class(rel)) for rel, n in items if set(n) - {"같은 목록이 두 곳"}]
        tools = (["주석은 /qwreey-conventions:comments-cleanup"] if not all(is_doc) else []) + (
            ["모델용 문서는 /qwreey-conventions:docs-cleanup"] if any(is_doc) else [])
        how = []
        if tools:
            how.append(", ".join(tools) + " 으로 정리합니다.")
        if "같은 목록이 두 곳" in cats:
            how.append('같은 목록은 "기존 문제도 정리해줘" 라고 하시면 됩니다.')
        lines.append(f'손댄 파일에 전부터 있던 문제: {shown}{more}. ' + " ".join(how))
    if diff:
        shown = ", ".join(f"{rel} {n}" for rel, n in sorted(diff)[:LEFT_MAX_FILES])
        more = f" 외 {len(diff) - LEFT_MAX_FILES}개" if len(diff) > LEFT_MAX_FILES else ""
        lines.append(f"사본이 원본과 다름: {shown}{more}. 동작이 달라질 수 있습니다.")
    return "\n".join(lines) or None


def report_leftovers(data):
    """Stop: 내용이 바뀌었을 때만 한 번 사용자에게 보인다(턴을 늘리지 않으려고 additionalContext 가 아니라 systemMessage)."""
    msg = leftover_message(data.get("session_id"))
    if not msg:
        return 0
    mark = os.path.join(left_dir(), re.sub(r"[^\w-]", "", str(data.get("session_id") or "nosession")) + ".reported.json")
    try:
        if json.load(open(mark)).get("msg") == msg:
            return 0
    except Exception:
        pass
    try:
        data = json.dumps({"msg": msg}, ensure_ascii=False).encode("utf-8")  # 서로게이트가 든 글은 표시를 남기지 않는다
        with open(mark, "wb") as f:
            f.write(data)
    except (OSError, UnicodeEncodeError):
        pass
    json.dump({"systemMessage": msg}, sys.stdout, ensure_ascii=False)
    return 0
