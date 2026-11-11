#!/usr/bin/env bash
# session-log e2e: 임시 git 프로젝트에서 claude -p --plugin-dir 로 실제 훅을 돌린다(실제 haiku 호출, 수 센트).
# 확인: SessionStart 주입 / SessionEnd 분리 실행 → 요약 / /compact 유도 → PreCompact 주입·PostCompact 보관·SessionStart(compact) 재알림
#       / 다음 턴 요약 완료 알림(UserPromptSubmit) / git commit 직전 pending 알림(PreToolUse) / (선택) auto compact
# 사용: tests/e2e.sh [--auto-compact]   결과: $T/report.json, 모델이 본 문자열은 트랜스크립트에서 뽑는다.
set -u
PLUG=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d /tmp/sl-e2e.XXXX)
P=$T/proj; mkdir -p "$P"; git init -q "$P"; git -C "$P" config user.email e2e@example.invalid; git -C "$P" config user.name e2e
export SESSION_LOG_RECORD_NONINTERACTIVE=1 SESSION_LOG_HOME=$T/store SESSION_LOG_FORCE_MIN_CHARS=100 XDG_RUNTIME_DIR=$T  # 슬롯 잠금도 격리(소급과 겹치지 않게)
CLEAN=(env -u CLAUDECODE -u CLAUDE_PROJECT_DIR -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SSE_PORT)
CL=("${CLEAN[@]}" claude -p --plugin-dir "$PLUG" --model haiku --output-format json)
log() { echo "[e2e] $*" >&2; }

# 0. 앞선 세션 기록 하나를 심는다(가짜 요약기, 비용 0) → pending 1, 인계 원천
python3 -I - "$T" "$P" <<'EOF'
import json, sys
T, P = sys.argv[1:3]
L = lambda **o: json.dumps(o, ensure_ascii=False) + "\n"
with open(f"{T}/seed-0000-1111.jsonl", "w") as f:
    f.write(L(type="user", origin={"kind": "human"}, timestamp="2026-11-09T01:00:00Z", cwd=P,
              message={"content": "API 서버 포트는 8443 으로 하고 prod 는 건드리지 마. 다음엔 TLS 설정을 끝내자. " * 3}))
    f.write(L(type="assistant", timestamp="2026-11-09T01:05:00Z", message={"content": [{"type": "text", "text": "알겠다. TLS 는 다음 세션에서 한다."}]}))
EOF
SESSION_LOG_CLAUDE=$PLUG/tests/fixtures/fake_claude.py python3 -I "$PLUG/scripts/cli.py" --project "$P" flush --transcript "$T/seed-0000-1111.jsonl" --trigger seed --force --wait >/dev/null

cd "$P"
# 1. 첫 실행: SessionStart 주입, bin/ PATH 여부, SessionEnd 분리 요약
t0=$(date +%s)
echo "Note for later: the deploy port is 8443 and we must never touch prod; the next task is writing tls.conf. Reply with one sentence. Then run the shell command 'session-log pending' and quote its first output line." | "${CL[@]}" --allowedTools Bash >"$T/run1.json"
[ -s "$T/run1.json" ] || { log "run1 failed"; exit 1; }
SID=$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["session_id"])' "$T/run1.json")
log "run1 session $SID ($(( $(date +%s)-t0 ))s)"
TP=$(ls ~/.claude/projects/*/"$SID".jsonl)
# SessionEnd 분리 프로세스가 요약을 끝낼 때까지(최대 240초)
for i in $(seq 1 120); do grep -q "\"session_id\": \"$SID\"" "$T"/store/*/index.json 2>/dev/null && break; sleep 2; done
t_flush1=$(( $(date +%s)-t0 ))
log "SessionEnd flush done at +${t_flush1}s"

# 2. /compact 유도
t1=$(date +%s)
echo "/compact keep the deploy port" | "${CL[@]}" --resume "$SID" >"$T/run2.json"
log "run2 compact ($(( $(date +%s)-t1 ))s)"
sleep 3

# 3. 다음 턴: 요약 완료 알림 + commit 직전 pending 알림
t2=$(date +%s)
echo "Run these two shell commands one after another, separately: first 'session-log flush --force --wait', then 'git commit --allow-empty -m e2e-commit'. Then reply 'done'." | "${CL[@]}" --resume "$SID" --allowedTools Bash >"$T/run3.json"
log "run3 commit ($(( $(date +%s)-t2 ))s)"

# 4. (선택) auto compact 유도
if [ "${1:-}" = "--auto-compact" ]; then
  t3=$(date +%s)
  echo "Reply with the single word ok." | CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=1 "${CL[@]}" --resume "$SID" >"$T/run4.json"
  log "run4 auto-compact attempt ($(( $(date +%s)-t3 ))s)"
fi
sleep 5
for i in $(seq 1 90); do pgrep -f "cli.py flush --session $SID" >/dev/null || break; sleep 2; done

python3 -I - "$T" "$SID" "$TP" "$t_flush1" <<'EOF'
import json, sys, glob, os, re
T, SID, TP, tf = sys.argv[1:5]
store = glob.glob(f"{T}/store/*")[0]
recs = [json.loads(l) for l in open(TP)]
def texts(o):
    out = []
    def walk(x):
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict): [walk(v) for v in x.values()]
        elif isinstance(x, list): [walk(v) for v in x]
    walk(o); return out
seen = []
for i, r in enumerate(recs, 1):
    for s in texts(r):
        for m in re.finditer(r'<harness-hook name="session-log"[^>]*>[\s\S]*?</harness-hook>', s):
            seen.append((i, r.get("type"), (r.get("attachment") or {}).get("type") or r.get("subtype") or "", m.group(0)))
uniq = []
for x in seen:
    if x[3] not in [u[3] for u in uniq]: uniq.append(x)
cost = {}
for k in ("run1", "run2", "run3", "run4"):
    p = f"{T}/{k}.json"
    if os.path.exists(p):
        try: d = json.load(open(p)); cost[k] = {"usd": d.get("total_cost_usd"), "ms": d.get("duration_ms"), "is_error": d.get("is_error"), "result": str(d.get("result"))[:200]}
        except Exception as e: cost[k] = {"error": str(e)}
ws = json.load(open(f"{store}/.state/{SID}.json")) if os.path.exists(f"{store}/.state/{SID}.json") else {}
hs = json.load(open(f"{store}/.state/{SID}.hook.json")) if os.path.exists(f"{store}/.state/{SID}.hook.json") else {}
compacts = sorted(glob.glob(f"{store}/.state/{SID}.compact-*.md"))
csum = open(compacts[-1]).read() if compacts else ""
boundaries = [ (r.get("compactMetadata") or {}).get("trigger") for r in recs if r.get("subtype") == "compact_boundary"]
bash_out = [s for r in recs if r.get("type") == "user" for s in texts(r) if "pending" in s and ("rid" in s or "records" in s or "~" in s)][:2]
rep = {
  "store": store, "session": SID, "transcript": TP,
  "injections_seen_by_model": [{"line": u[0], "type": u[1], "sub": u[2], "text": u[3]} for u in uniq],
  "checks": {
    "sessionstart_injection": any("Handover from session" in u[3] or "pending import" in u[3] for u in uniq),
    "saved_notice": any("Session log: saved" in u[3] for u in uniq),
    "commit_notice": any("about to commit" in u[3] for u in uniq),
    "after_compact_notice": any("Session log for this session" in u[3] for u in uniq),
    "precompact_in_compact_summary": ("records/" in csum) or ("session-log" in csum),
    "compact_boundaries": boundaries,
    "epoch": open(f"{os.environ.get('TMPDIR', '/tmp')}/claude-q-epoch/{SID}").read() if os.path.exists(f"{os.environ.get('TMPDIR', '/tmp')}/claude-q-epoch/{SID}") else None, "reminded": hs.get("reminded"),
    "worker_sections": ws.get("sections"), "worker_cost_usd": ws.get("cost_usd"),
    "sessionend_flush_wall_s": int(tf),
    "bin_on_path": bash_out,
  },
  "runs": cost,
  "repo_files": [p for p in glob.glob(f"{T}/proj/**", recursive=True) if "/.git" not in p and os.path.isfile(p)],
  "compact_summary_tail": csum[-600:],
}
json.dump(rep, open(f"{T}/report.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(rep, ensure_ascii=False, indent=1))
EOF
echo "T=$T"
