#!/usr/bin/env python3
"""ask-other-frame — second-opinion:other-frame 의 '다른 프레임' 경로.

메인 대화를 render-transcript.py 로 옮겨 플러그인의 other-frame 에이전트 본문(다른 시스템 프롬프트)을 단 `second-opinion-context` 로 `claude -p` 로 묻는다.
Agent 도구로 넘기지 않는 이유: 대화 사본(약 130k 토큰)을 메인이 프롬프트에
옮겨 적으면 그만큼이 메인의 출력 토큰이 된다. 파일로 넘기고 별도 프로세스가 읽게 한다.

사용 (메인이 Bash 로, 백그라운드 권장):
  ask-other-frame.py [--model sonnet|opus] [--note "메인 메모(주장)"] [--budget 1.0] [--ttl 5m] [--transcript P]
결과: stdout 에 조언 본문, 마지막 줄에 'cost=$… turns=… ctx_write=… ctx_read=…'. 임시 파일은 $TMPDIR/so-context-<pid>/ 에 남긴다.

비용: 맥락 132k 토큰. 첫 호출이 캐시 쓰기라 opus 1h $1.25, sonnet 5m $0.49. 같은 프롬프트를 1시간 안에 다시
물으면 opus $0.33(캐시 읽기). 그래서 --ttl 기본은 5m(한 번 묻고 끝낼 때 쓰기 단가가 싸다).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent.parent.parent  # 플러그인 루트(skills/other-frame/scripts 의 세 단계 위)
QUESTION = "질문: 다음 단계로 넘어가기 전에 이 흐름에서 놓친 것, 잘못된 전제, 확인 안 한 가정은?"


def agent_json(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.S)
    body = m.group(2).strip() if m else text
    return {"second-opinion-context": {
        "description": "메인 대화를 이어받아 놓친 것을 짚는 읽기 전용 조언자",
        "prompt": body, "tools": ["Read", "Grep", "Glob", "Bash"],
        "disallowedTools": ["Edit", "Write", "NotebookEdit", "Agent"], "effort": "high"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--note", default="")
    ap.add_argument("--budget", default="1.0")
    ap.add_argument("--ttl", default="5m")
    ap.add_argument("--transcript")
    ap.add_argument("--agent-md", default=str(PLUGIN / "agents" / "other-frame.md"))
    a = ap.parse_args()

    work = Path(tempfile.gettempdir()) / f"so-context-{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    rargs = [sys.executable, "-I", str(HERE / "render-transcript.py")]
    if a.transcript:
        rargs += ["--transcript", a.transcript]
    conv = subprocess.run(rargs, capture_output=True, text=True)
    if conv.returncode != 0:
        sys.stderr.write(conv.stderr)
        return conv.returncode
    prompt = f"<conversation>\n{conv.stdout}\n</conversation>\n\n"
    if a.note:
        prompt += f"메인의 메모(주장이다. 근거가 아니다): {a.note}\n\n"
    prompt += QUESTION + "\n"
    (work / "prompt.txt").write_text(prompt, encoding="utf-8")
    (work / "agents.json").write_text(json.dumps(agent_json(Path(a.agent_md)), ensure_ascii=False), encoding="utf-8")

    cmd = ["claude", "-p", "--agents", str(work / "agents.json"), "--agent", "second-opinion-context",
           "--model", a.model, "--effort", "high", "--allowedTools", "Read", "Grep", "Glob", "Bash",
           "--disallowedTools", "Edit", "Write", "NotebookEdit", "Agent",
           "--no-session-persistence", "--max-budget-usd", a.budget, "--output-format", "json"]
    guard = PLUGIN / "hooks" / "auditor-readonly-guard.py"  # 플러그인 에이전트 hooks 는 무시되므로 --settings 로 직접 건다
    if guard.exists():
        s = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": f"python3 -I {guard}"}]}]}}
        (work / "settings.json").write_text(json.dumps(s), encoding="utf-8")
        cmd += ["--settings", str(work / "settings.json")]
    wrap = os.environ.get("HARNESS_HEAVY_WRAP", "")
    if wrap and shutil.which(wrap.split()[0]):
        cmd = wrap.split() + ["--"] + cmd
    env = dict(os.environ, CLAUDE_CODE_PROMPT_CACHE_TTL=a.ttl)
    with open(work / "prompt.txt", encoding="utf-8") as fin:
        r = subprocess.run(cmd, stdin=fin, capture_output=True, text=True, env=env)
    (work / "out.json").write_text(r.stdout, encoding="utf-8")
    try:
        d = json.loads(r.stdout)
    except ValueError:
        sys.stderr.write(r.stderr or r.stdout[:2000])
        return 1
    print(d.get("result", ""))
    u = d.get("usage") or {}
    mu = next(iter((d.get("modelUsage") or {}).values()), {})
    print(f"\ncost=${d.get('total_cost_usd', 0):.2f} turns={d.get('num_turns')} "
          f"ctx_write={mu.get('cacheCreationInputTokens', u.get('cache_creation_input_tokens'))} "
          f"ctx_read={mu.get('cacheReadInputTokens', u.get('cache_read_input_tokens'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
