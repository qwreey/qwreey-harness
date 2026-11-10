#!/usr/bin/env python3
"""트랜스크립트 → 세션 기록 프로토타입. (실측용. 본 구현 아님)

사용:
  python3 -I summarize.py <transcript.jsonl> --model sonnet|haiku --out <dir> [--chunk-chars 90000] [--from-byte N]

- extract.py 로 줄인 텍스트를 --chunk-chars 단위(줄 경계)로 나눠 구간마다 한 번 요약한다.
  실제 훅에서도 트리거(PreCompact·SessionEnd·PostToolUse 쿨다운)마다 "지난 위치 이후" 한 구간을 요약해
  세션 파일에 절로 덧붙이는 꼴이라 같은 단위로 잰다.
- 요약 호출: claude -p, 도구 없음(--tools ""), 설정 원천 없음(--setting-sources "" → 사용자·프로젝트 훅이 안 걸림),
  세션 저장 안 함(--no-session-persistence), 빈 임시 cwd, SESSION_LOG_NESTED=1.
  모델은 텍스트만 돌려준다. 파일 쓰기는 이 스크립트가 한다.
- 출력: <out>/<session>.<model>.md (frontmatter + 구간별 절), <out>/<session>.<model>.metrics.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract as ex  # noqa: E402

def chunks(text: str, limit: int):
    cur, n = [], 0
    for line in text.split("\n"):
        if n + len(line) > limit and cur:
            yield "\n".join(cur); cur, n = [], 0
        cur.append(line); n += len(line) + 1
    if cur:
        yield "\n".join(cur)

def env_for_child():
    env = dict(os.environ)
    for k in list(env):
        if k == "CLAUDECODE" or k.startswith("CLAUDE_CODE_") or k in ("CLAUDE_PROJECT_DIR", "CLAUDE_PID", "CLAUDE_EFFORT"):
            env.pop(k, None)
    env["SESSION_LOG_NESTED"] = "1"
    return env

def call_model(prompt: str, model: str, timeout: int = 600):
    cwd = tempfile.mkdtemp(prefix="sl-sum-")
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "",
           "--setting-sources", "", "--no-session-persistence", "--strict-mcp-config",
           "--mcp-config", '{"mcpServers":{}}']
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, env=env_for_child(), timeout=timeout)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    wall = time.time() - t0
    try:
        d = json.loads(p.stdout)
    except Exception:
        return {"ok": False, "error": (p.stderr or p.stdout)[:500], "wall_s": wall}
    u = d.get("usage") or {}
    return {"ok": not d.get("is_error"), "result": d.get("result", ""), "cost_usd": d.get("total_cost_usd"),
            "wall_s": wall, "api_ms": d.get("duration_api_ms"),
            "in": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "out": u.get("output_tokens"), "model_usage": list((d.get("modelUsage") or {}).keys())}

# 출력이 프롬프트를 되풀이한 것이면(훅 차단·CLI 메시지 등) 버린다. remember 의 교훈.
ECHO_MARKERS = ["당신은 Claude Code 세션 기록을 쓰는 기록자다", "<transcript>", "출력 형식은 정확히"]

def valid(out: str) -> bool:
    return bool(out) and "## 요약" in out and not any(m in out for m in ECHO_MARKERS)

def main():
    a = sys.argv[1:]
    path = a[0]
    model = a[a.index("--model") + 1]
    outdir = a[a.index("--out") + 1]
    limit = int(a[a.index("--chunk-chars") + 1]) if "--chunk-chars" in a else 90000
    fb = int(a[a.index("--from-byte") + 1]) if "--from-byte" in a else 0
    os.makedirs(outdir, exist_ok=True)
    template = open(os.path.join(HERE, "prompt.md"), encoding="utf-8").read()
    r = ex.extract(path, fb)
    sid = os.path.basename(path).removesuffix(".jsonl")
    sections, metrics = [], []
    heads = {"description": [], "keywords": []}
    for i, ch in enumerate(chunks(r["text"], limit)):
        lines = re.findall(r"^\[L(\d+) (\S+ \S+)", ch, re.M)
        rng = f"L{lines[0][0]}–L{lines[-1][0]}, {lines[0][1]} ~ {lines[-1][1]}" if lines else "?"
        res = call_model(template.replace("{{TRANSCRIPT}}", ch), model)
        res.update({"chunk": i, "chars": len(ch), "range": rng})
        out = res.pop("result", "") if res.get("ok") else ""
        res["valid"] = valid(out)
        metrics.append(res)
        if not res["valid"]:
            sections.append(f"## 구간 {i + 1} ({rng})\n\n(요약 실패: {res.get('error', '형식 불일치')})\n")
            continue
        body = []
        for ln in out.strip().splitlines():
            if ln.startswith("description:"):
                heads["description"].append(ln.split(":", 1)[1].strip())
            elif ln.startswith("keywords:"):
                heads["keywords"] += [k.strip(" '\"") for k in ln.split(":", 1)[1].strip(" []").split(",") if k.strip()]
            else:
                body.append(re.sub(r"^## ", "### ", ln))
        sections.append(f"## 구간 {i + 1} ({rng})\n" + "\n".join(body).strip() + "\n")
    today = dt.date.today().isoformat()
    kw = list(dict.fromkeys(heads["keywords"]))[:12]
    fm = ["---", f"title: 세션 {sid[:8]}", f"description: {heads['description'][0] if heads['description'] else ''}",
          f"keywords: [{', '.join(kw)}]", "kind: session", "status: active", f"last_verified: {today}",
          f"session_id: {sid}", f"source_transcript: {path}", f"source_range: bytes {r['start_byte']}-{r['end_byte']}, lines 1-{r['end_line']}",
          f"summarizer: {model}", "---", ""]
    with open(os.path.join(outdir, f"{sid}.{model}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + f"# 세션 {sid[:8]}\n\n" + "\n".join(sections))
    tot = {"model": model, "session": sid, "extract_chars": len(r["text"]), "counts": r["counts"], "chunks": metrics,
           "cost_usd": sum(m.get("cost_usd") or 0 for m in metrics), "wall_s": sum(m["wall_s"] for m in metrics)}
    with open(os.path.join(outdir, f"{sid}.{model}.metrics.json"), "w") as f:
        json.dump(tot, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: tot[k] for k in ("model", "session", "extract_chars", "cost_usd", "wall_s")}), file=sys.stderr)

if __name__ == "__main__":
    main()
