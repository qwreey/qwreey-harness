---
name: away
description: Declares the user is stepping away. Sets a usage budget (subscription %, USD, or agent count) and a concurrent subagent slot count; when the budget is exceeded subagents are queued, and at double the budget new subagents are halted. User-invoked only. 자리 비움, 한도 정해 두고 자리 비울게.
argument-hint: "[budget: 30% | 30%w | 30%5h | $5 | 6a] [slots: 2]  |  status | off | reset"
disable-model-invocation: true
allowed-tools: Bash(python3 *subagent_ledger.py *)
---

# away

Below is the result of running `/q:away` (if output is already there, do not run it again; if only a run instruction is there, run that command once).

!`python3 "${CLAUDE_SKILL_DIR}/../../scripts/subagent_ledger.py" away ${CLAUDE_SESSION_ID} $ARGUMENTS`

## Plain explanation (when the user asks, give this to them as written, in Korean)
자리를 비운 동안 "한도를 얼마나 쓰게 둘지" 정해 두는 기능이다.
- 정한 만큼 쓰면 1단계: 서브에이전트를 한 번에 하나씩만 돌린다(느려지지만 계속 간다).
- 정한 양의 두 배를 쓰면 2단계: 새 서브에이전트를 더 띄우지 않고, 지금까지 한 일을 파일에 적은 뒤 사용자가 올 때까지 기다린다.
- 돌아와서 `/q:back` 하면 얼마 썼는지, 1·2단계에 언제 닿았는지 요약한다.

예시
1. `/q:away 30%` : 지금부터 구독 한도(5시간·주간 중 먼저 닿는 쪽)를 30% 더 쓰면 1단계, 60% 면 2단계.
2. `/q:away 20%w` : 주간 한도만 보고 20%. 5시간 한도가 없는 요금제는 이 형태가 편하다(`30%5h` 는 5시간 창).
3. `/q:away $5` : 달러로 5(API 목록가 환산). API·종량제용. `6a` 는 서브에이전트 6개.

## What to do
1. Relay the result above to the user in one or two lines. If it was an error, give the format (`/q:away [예산] [슬롯]`).
2. If the result carries a marker:
   - `[plan-unknown]` / `[no-limits]`: the limit % could not be read, so USD was turned on. Ask the user once for their plan (subscription: `/q:away 30%`; pay-as-you-go: USD). If they are on a subscription but no value appears, tell them to check that the statusline is configured. To stop asking every time, only suggest putting `HARNESS_AWAY_PLAN=pct` (or `usd`) in `~/.claude/harness.env`; do not write it yourself.
   - `[window-missing]`: tell them the plan lacks that window, so the available window was used.
3. If it is on, behave as follows afterward:
   - Before launching subagents, look at the size of the remaining work and go through small passes in order (find -> review -> fix -> review).
   - A `queue: ...` rejection is not a failure. Wait for a running agent's completion notice, then launch the next one. Do not repeat the same call immediately.
   - When the budget-exceeded notice (stage 1) arrives, for each remaining task weigh "can sonnet do it, can it be split into a smaller pass" and write it in the next report.
   - On a `halt: ...` rejection (stage 2), launch no more subagents or Workflows. Write what was done, what is in progress, what is next, and what needs a user decision into the progress file (or session notes if none), then wait for the user. The session does not stop, so only finish the small task in hand.
   - When the user returns and runs `/q:back`, a summary appears.

## Arguments
- Budget: `30%` limit percentage points (tightest window), `30%w` weekly only, `30%5h` 5-hour only, `$5` or `5` USD (main + subagents, since `/q:away`), `6a` six subagents.
  If omitted: `HARNESS_AWAY_BUDGET_PCT` (30%) when limit values are being received, else `HARNESS_AWAY_BUDGET_USD` (20).
- Slots: concurrent subagents. If omitted, `HARNESS_AWAY_SLOTS` (default 2). Once the budget is exceeded, `HARNESS_AWAY_OVER_SLOTS` (default 1).
- `status` current state, `off` turn off (= `/q:back`), `reset` clear the slot counter (when the count drifted).
- The limit % comes from statusline input. If the statusline has not refreshed for over 10 minutes, the USD guard backs it up.
- Rationale: `references/rationale.md`.
