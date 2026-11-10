#!/bin/bash
# 실측용: 훅 stdin 과 일부 환경 변수를 /tmp/sl-work/dump/ 에 덤프한다. SessionEnd 에서는 분리 실행 생존 시험도 한다.
# dump hook stdin + selected env to /tmp/sl-work/dump/<event>-<ns>.json
in=$(cat)
ev=$(printf '%s' "$in" | python3 -I -c 'import json,sys;print(json.load(sys.stdin).get("hook_event_name","x"))' 2>/dev/null || echo x)
ts=$(date +%s%N)
printf '%s' "$in" > /tmp/sl-work/dump/$ev-$ts.json
env | grep -E '^(CLAUDE_PROJECT_DIR|CLAUDE_CODE_SESSION_ID|CLAUDECODE|CLAUDE_CODE_ENTRYPOINT|CLAUDE_PLUGIN_DATA|SL_NESTED|PWD)=' > /tmp/sl-work/dump/$ev-$ts.env
# detach test on SessionEnd: setsid child survives?
if [ "$ev" = SessionEnd ]; then
  ( sleep 8; echo alive > /tmp/sl-work/dump/plainbg-$ts.txt ) >/dev/null 2>&1 &
  setsid -f bash -c "sleep 8; echo alive > /tmp/sl-work/dump/setsid-$ts.txt" </dev/null >/dev/null 2>&1
fi
exit 0
