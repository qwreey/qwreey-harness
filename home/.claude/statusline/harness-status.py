#!/usr/bin/env python3
"""statusline: 컨텍스트 %, 세션 비용, 실행 중 서브에이전트(모델별), away 상태와 남은 예산을 한 줄로.

settings.json: "statusLine": {"type": "command", "command": "python3 $HOME/.claude/statusline/harness-status.py", "refreshInterval": 10}
- 읽기 전용. 잠금을 잡지 않고 원장(lib/subagent_ledger.py) 파일을 읽기만 한다. 실패하면 모델·컨텍스트만 낸다.
- 비용은 cost.total_cost_usd(목록가 환산, 서브에이전트 포함 — audit/21 실측)를 쓴다. away 예산은 원장 기준이다.
- refreshInterval: 메인이 백그라운드 에이전트를 기다리며 쉬는 동안에도 실행 중 수가 갱신되게 한다(문서 권고).
예: `Opus ctx 34% · $12.40 · agents 2 (opus 1, sonnet 1) · AWAY $3.10/$15 slots 2`
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        d = {}
    parts = []
    model = (d.get("model") or {}).get("display_name") or ""
    pct = (d.get("context_window") or {}).get("used_percentage")
    parts.append(f"{model} ctx {pct:.0f}%".strip() if isinstance(pct, (int, float)) else model)
    cost = (d.get("cost") or {}).get("total_cost_usd")
    if isinstance(cost, (int, float)):
        parts.append(f"${cost:.2f}")
    try:
        spec = importlib.util.spec_from_file_location("subagent_ledger", HOME / "lib" / "subagent_ledger.py")
        L = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(L)
        st = L.read(d.get("session_id"))
        now = time.time()
        ttl = float(L.CFG_DEFAULTS["HARNESS_SLOTS_RESERVE_SEC"])
        items = list(st["running"].values()) + [r for r in st["reserved"].values() if now - r.get("t", 0) <= ttl]
        if items:
            parts.append(f"agents {len(items)} (" + ", ".join(f"{f} {n}" for f, n in L.by_family(items).items()) + ")")
        a = st.get("away") or {}
        if a.get("on"):
            spent, spawned, over = L.away_status(st)
            if a.get("budget_agents") is not None:
                b = f"{spawned}/{a['budget_agents']} agents"
            else:
                b = f"${spent:.2f}/${a.get('budget_usd', 0):g}"
            slots = a.get("over_slots", 1) if over else a.get("slots")
            q = f" queued {a['queued']}" if a.get("queued") else ""
            parts.append(f"AWAY {'OVER ' if over else ''}{b} slots {slots}{q}")
    except Exception:
        pass
    print(" · ".join(p for p in parts if p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
