---
name: fresh-advisor
description: Second opinion from a fresh, read-only reviewer (second-opinion:reviewer) that gets a brief of goal, constraints, and claims, then reads the diff, tests, and the user's original messages itself and tries to refute the claims. Call it yourself before committing or declaring work done, after the same failure happens twice, or before locking in a hard-to-undo approach; also on a second-opinion hook notice. For what the conversation missed, see inherit-advisor. 커밋 전 검토, 검토 받아, 완료 선언 전 검증.
argument-hint: "[plan|stuck|done] [scope or one-line note]"
---

# second-opinion:fresh-advisor

A fresh read-only reviewer (`second-opinion:reviewer`) refutes the diff and the claims. It does not call the built-in `advisor` tool. Rationale, cost, and measurements: `references/rationale.md`.
- **When**: the moment table below (hook notices + one main-agent judgment).
- **Who**: `second-opinion:reviewer` in a new context; strength fixed by repo tier.
- **What to pass**: a few lines of goal, constraints, and claims. The reviewer pulls the user's original messages from the transcript itself.
- **Result**: show it to the user unsummarized; record accepted and rejected findings in the ledger.

## 1. Moments and strength

The repo tier is in `~/.claude/harness.env` as `HARNESS_REVIEW_TIERS` (else `HARNESS_REVIEW_DEFAULT`, else `mid`). The plugin hooks use the same table.

| Moment (kind) | Who signals | high | mid | low |
|---|---|---|---|---|
| Before locking an approach (`plan`) - hard-to-undo design, public API/data format/security, multi-file or multi-step work | main judgment (hook if ExitPlanMode is used) | opus | sonnet | skip |
| Same failure twice (`stuck`) | hook `PostToolUseFailure` | opus | sonnet | sonnet |
| Before completion/commit (`done`) - diff above threshold | hook `PreToolUse(git commit)`, `Stop` | opus | sonnet | skip |

- Set the reviewer model in the call: `Agent(subagent_type="second-opinion:reviewer", model="sonnet")`. The frontmatter default is opus.
- Never use haiku (the judgment stays in the result).
- One `done` review per work unit. Re-run after fixing only if a "반드시" finding was fixed, and only for that scope.
- If the user narrowed the budget (project CLAUDE.md or memory), that wins: lower one step (opus to sonnet, sonnet to skip) and say so in the reply.

## 2. Write the brief (main agent, 5-15 lines)

Fill `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/templates/brief.md`.
- Include: goal in one or two lines, constraints, scope (`git` range, paths, plan file), **claims to verify** (what you are about to tell the user "done/works/safe"), approaches already rejected, transcript path (omit if unknown; the reviewer finds it via `CLAUDE_CODE_SESSION_ID`).
- Do not include: your summary of the user's requirements (the reviewer reads the originals), the reasoning behind your conclusion (anchoring), pasted file contents (the reviewer reads them).
- Do not leave out the part you are least sure about; that is the reason for the review.
- **Never list parallel work as "out of scope".** Pass it as "places this change may affect".
- If the user asked something you have not answered, add it in one line (`python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/user-asks.py" --claims 3` can extract it).

## 3. Call

```
Agent(subagent_type="second-opinion:reviewer", model="<opus|sonnet>",
      description="second opinion: <kind>", prompt=<brief>)
```
- May run in the background, but for `done` do not declare completion before the result arrives.
- If the reviewer fails or hits maxTurns, tell the user "review incomplete" and do not relaunch it (runaway guard).
- Cost: about $1 per opus run, $0.4 per sonnet run, 2-3 minutes. One `done` per work unit; not for dense calls.

## 4. Handle the result

1. Show the reviewer's report **verbatim** to the user (quote block or pasted as is). Put your own judgment below it, separately.
2. For each finding decide accepted / rejected / needs check; if rejected, give evidence (file:line, run output). When the reviewer's evidence and yours conflict, settle it by running something.
3. Record in the ledger:
   ```bash
   python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/review-ledger.py" add --kind done --reviewer opus-sub \
     --trigger hook:commit --verdict 고친뒤진행 --found 4 --adopted 3 --must 1 --note "MANIFEST 누락"
   ```
   Use `--trigger hook:<commit|stop|failure|plan>` for a hook notice, `self` if you decided, `user` if the user asked.

## 5. Measurement

Scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/`.
- `review-ledger.py stats`: findings, adoption rate, "no findings" rate by kind/reviewer/trigger.
- `advisor-stats.py --all`: advisor usage and cost, for comparison.
- `user-asks.py [--since-compact] [--last N] [--claims K]`: extract the user's original messages.
