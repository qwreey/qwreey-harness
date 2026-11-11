---
name: fresh-advisor
description: A self-check you run on your own initiative, for your own use: spawns a read-only reviewer in a new context that gets your claims in a short brief, reads the changes and the user's own words itself, and tries to refute what you say is done or true. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Reach for it whenever you want your claims tested by someone who does not share your assumptions. 커밋 전 검토, 완료 전 검증.
argument-hint: "[plan|stuck|done] [scope or one-line note]"
---

# second-opinion:fresh-advisor

## Call

```
Agent(subagent_type="second-opinion:reviewer", model="<opus|sonnet>",
      description="second opinion: <plan|stuck|done>", prompt=<brief>)
```

- `model` follows the repo tier, read from `HARNESS_REVIEW_TIERS` in `~/.claude/harness.env` (else `HARNESS_REVIEW_DEFAULT`, else `mid`). The plugin hooks use the same table. The frontmatter default is opus. Never haiku: the judgment stays in the result.

| kind | high | mid | low |
|---|---|---|---|
| `plan`: before locking an approach (hard to undo, public API / data format / security, multi-step) | opus | sonnet | skip |
| `stuck`: same failure twice | opus | sonnet | sonnet |
| `done`: before completion or commit, diff above threshold | opus | sonnet | skip |

- If the user narrowed the budget (project CLAUDE.md or memory), lower one step (opus to sonnet, sonnet to skip) and say so.
- One `done` review per work unit. Re-run after fixing only if a `must` finding was fixed, and only for that scope.
- It may run in the background, but for `done` do not declare completion before the result arrives. If the reviewer fails or hits maxTurns, tell the user "review incomplete" and do not relaunch it.
- The built-in `advisor` tool is not involved.

## Write the brief

Fill `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/templates/brief.md` in English, 5-15 lines. The reviewer starts with no context, so the brief carries only what it cannot find itself.
- Include: the goal of this work unit, constraints, scope (git range, paths, plan file), **claims to verify** (what you are about to tell the user is done / works / safe), approaches already rejected, the transcript path if you know it.
- Leave out your summary of the user's requirements, the reasoning behind your conclusion (it anchors the reviewer), and pasted file contents. The reviewer reads the user's original messages and the files itself.
- Include the part you are least sure about; that is the reason for the review.
- Parallel work goes in as "places this change may affect", never as "out of scope".
- If the user asked something you have not answered, add it in one line (`python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/user-asks.py" --claims 3` can extract it).

## What comes back

An English report: a verdict (proceed / proceed after fixes / rethink), findings by severity (must / should / note) with evidence and "how verified or inferred", a table matching the user's requirements, a table checking each claim, and what it could not see. "No findings" is stated with the range it looked at.

## After you get it

1. Decide each finding: accepted / rejected / needs check. Give evidence for a rejection (file:line, run output). When the reviewer's evidence and yours conflict, settle it by running something.
2. You called it yourself (including on a hook notice): act on it and tell the user in 1-3 lines what you accepted and rejected. The full report stays in the transcript.
   The user asked for it: show the report in full, in Korean, then your judgment below it, separately. Quote the user's own words in their original language.
3. Record it. `--trigger` is `hook:<commit|stop|failure|plan>` for a hook notice, `self` if you decided, `user` if the user asked. Verdicts: 진행 | 고친뒤진행 | 다시생각 | 발견없음 | 실패.

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/review-ledger.py" add --kind done --reviewer opus-sub \
  --trigger hook:commit --verdict 고친뒤진행 --found 4 --adopted 3 --must 1 --note "MANIFEST missing"
```

Stats: `review-ledger.py stats`, `advisor-stats.py --all` (advisor usage and cost), `user-asks.py [--since-compact] [--last N] [--claims K]` (the user's original messages), all in `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/`.

Rationale, cost, and measurements: `references/rationale.md`.
