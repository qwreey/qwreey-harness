---
name: away
description: 자리 비움 — 사용량 예산과 동시 서브에이전트 수를 정해 둔다
argument-hint: "[budget: 30% | 30%w | 30%5h | $5 | 6a] [slots: 2]  |  status | off | reset"
disable-model-invocation: true
allowed-tools: Bash(python3 *subagent_ledger.py *)
---

# away

Below is the result of running `/q:away` (if output is already there, do not run it again; if only a run instruction is there, run that command once).

!`python3 "${CLAUDE_SKILL_DIR}/../../scripts/subagent_ledger.py" away ${CLAUDE_SESSION_ID} $ARGUMENTS`

Two stages: at the budget (stage 1) subagents run `HARNESS_AWAY_OVER_SLOTS` at a time; at `HARNESS_AWAY_STAGE2_MULT` times the budget (stage 2) new subagents and Workflows are refused until the user returns. The hook messages say what to do at each stage.

## What to do
1. Relay the result above to the user in one or two lines. If it was an error, give the format (`/q:away [예산] [슬롯]`).
2. If the result carries a marker:
   - `[plan-unknown]` / `[no-limits]`: the limit % could not be read, so USD was turned on. Ask the user once for their plan (subscription: `/q:away 30%`; pay-as-you-go: USD). If they are on a subscription but no value appears, tell them to check that the statusline is configured. To stop asking every time, only suggest putting `HARNESS_AWAY_PLAN=pct` (or `usd`) in `~/.claude/harness.env`; do not write it yourself.
   - `[window-missing]`: tell them the plan lacks that window, so the available window was used.

## Arguments
- Budget: `30%` limit percentage points (tightest window), `30%w` weekly only (use this on plans without a 5-hour window), `30%5h` 5-hour only, `$5` or `5` USD at API list price (main + subagents, since `/q:away`), `6a` six subagents.
  If omitted: `HARNESS_AWAY_BUDGET_PCT` (30%) when limit values are being received, else `HARNESS_AWAY_BUDGET_USD` (20).
- Slots: concurrent subagents. If omitted, `HARNESS_AWAY_SLOTS` (default 2). Once the budget is exceeded, `HARNESS_AWAY_OVER_SLOTS` (default 1).
- `status` current state, `off` turn off (= `/q:back`), `reset` clear the slot counter (when the count drifted).
- The limit % comes from statusline input. If the statusline has not refreshed for over 10 minutes, the USD guard backs it up.
