"""요약 호출과 출력 해석.

호출은 격리된 `claude -p` 하나다. 모델에게 도구를 주지 않는다(--tools ""). 파일 쓰기는 스크립트가 한다.
- --setting-sources "": 사용자·프로젝트 설정(훅·플러그인)을 싣지 않는다(실측 훅 0회).
- --no-session-persistence: 요약 호출의 트랜스크립트를 남기지 않는다(요약이 다시 요약 대상이 되지 않음).
- 빈 임시 cwd, 부모 세션 환경 변수(CLAUDECODE, CLAUDE_CODE_*) 제거, SESSION_LOG_NESTED=1(우리 훅은 이걸 보면 바로 끝난다).
API 직접 호출(backend=api)을 넣을 자리는 call_model 하나다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from . import config, messages

NESTED_ENV = "SESSION_LOG_NESTED"


def child_env() -> dict:
    env = dict(os.environ)
    for k in list(env):
        if k == "CLAUDECODE" or k.startswith("CLAUDE_CODE_") or k in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_ENV_FILE"):
            env.pop(k, None)
    env[NESTED_ENV] = "1"
    return env


def call_model(prompt: str, model: str, timeout: float) -> dict:
    cwd = tempfile.mkdtemp(prefix="sl-sum-")
    cmd = [config.get("SESSION_LOG_CLAUDE"), "-p", "--model", model, "--output-format", "json", "--tools", "",
           "--setting-sources", "", "--no-session-persistence", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, env=child_env(), timeout=timeout)
        stdout, stderr = p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout}s", "wall_s": time.time() - t0, "cost_usd": 0.0}
    except OSError as e:
        return {"ok": False, "error": str(e), "wall_s": time.time() - t0, "cost_usd": 0.0}
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    wall = time.time() - t0
    try:
        d = json.loads(stdout)
    except ValueError:
        return {"ok": False, "error": (stderr or stdout)[:500], "wall_s": wall, "cost_usd": 0.0}
    u = d.get("usage") or {}
    return {"ok": not d.get("is_error"), "result": d.get("result", ""), "cost_usd": float(d.get("total_cost_usd") or 0.0),
            "wall_s": wall, "error": "" if not d.get("is_error") else str(d.get("result", ""))[:500],
            "in_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "out_tokens": u.get("output_tokens", 0)}


HEADINGS = ["요약", "사용자 지시와 정정", "결정", "바뀐 파일과 커밋", "실측 수치", "실패한 시도", "미해결과 다음 단계"]


def valid(out: str) -> bool:
    return bool(out) and "## 요약" in out and not any(m in out for m in messages.ECHO_MARKERS)


def parse(out: str) -> tuple[str, list[str], str]:
    """모델 출력 → (description, keywords, 본문(### 절)). 머리 두 줄 앞의 잡말은 버린다."""
    desc, kws, body = "", [], []
    started = False
    for ln in out.strip().splitlines():
        s = ln.strip()
        if s.startswith("description:") and not desc:
            desc = s.split(":", 1)[1].strip().strip('"')
            continue
        if s.startswith("keywords:") and not kws:
            raw = s.split(":", 1)[1].strip().strip("[]")
            kws = [k.strip().strip("'\"`") for k in raw.split(",") if k.strip().strip("'\"`")]
            continue
        if s.startswith("## "):
            started = True
            body.append("### " + s[3:].strip())
            continue
        if started:
            body.append(ln.rstrip())
    text = "\n".join(body).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return desc[:200], kws[:8], text


def estimate_cost(chars: int, model: str) -> float:
    """사전 비용 추정(상한 쪽). .claude/scopes/plugins/qwreey-sessions/audit/15 §3.3: haiku 약 $0.24/1M자 + 호출당 오버헤드. sonnet 은 약 13배."""
    per_char = 0.24e-6 if "haiku" in model else 3.1e-6
    overhead = 0.004 if "haiku" in model else 0.02
    return chars * per_char * 1.5 + overhead
