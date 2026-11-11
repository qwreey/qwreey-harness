---
name: fresh-advisor
description: Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the user's own words and the files itself, without your assumptions, and tries to refute your view. Where a code review hunts defects in a diff, this tests your approach or claims against what the user asked. Reach for it before you lock in an approach or tell the user work is done, when only you have checked that view; no one needs to ask. 접근 확정 전 검토, 완료 전 검증.
argument-hint: "[plan|stuck|done] [scope or one-line note]"
---

# second-opinion:fresh-advisor

## Call

```
Agent(subagent_type="second-opinion:reviewer", model="<opus|sonnet>",
      description="second opinion: <plan|stuck|done>", prompt=<brief>)
```

- Always pass `model`, following the repo tier: read `HARNESS_REVIEW_TIERS` in `~/.claude/harness.env` (else `HARNESS_REVIEW_DEFAULT`, else `mid`). Never haiku: the judgment stays in the result.

| kind | high | mid | low |
|---|---|---|---|
| `plan`: before locking an approach (hard to undo, public API / data format / security, multi-step) | opus | sonnet | skip |
| `stuck`: same failure twice | opus | sonnet | sonnet |
| `done`: before telling the user it is done: what you said versus what you did, against the user's request | opus | sonnet | skip |

- `skip` means do not call it on your own; call it when the user asks.
- If the user narrowed the budget (project CLAUDE.md or memory), lower one step (opus to sonnet, sonnet to skip) and say so.
- Defects in a diff (bugs, missing tests, style) belong to `/code-review`; this skill checks claims and approaches, and does not replace it.
- One `done` review per work unit. Re-run after fixing only if a `must` finding was fixed, and only for that scope.
- A review costs about $1 on opus and $0.4 on sonnet, and takes 2-3 minutes, so it is not for frequent calls.
- It may run in the background, but for `done` do not declare completion before the result arrives. If the reviewer fails or hits maxTurns, do not relaunch it: a relaunch repeats the full cost and can chain. Tell the user "review incomplete: <what was not seen>". If it returns a partial report, handle only the findings from the range it read and add the same line.
- The built-in `advisor` tool is not involved.

Which one (against inherit-advisor): ask what you doubt. If it is whether your reasoning holds, inherit-advisor sees why you decided and costs little. If the framing itself may be wrong, or the step is hard to undo, fresh-advisor starts without your assumptions and reads the files and the user's words. Do not run both on the same point.

## Write the brief

Fill `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/templates/brief.md` in English, 5-15 lines. The reviewer starts with no context, so the brief carries only what it cannot find itself.
- Include: the goal of this work unit, constraints, scope (git range, paths, plan file), **the files you changed** (the working tree may also hold other sessions' changes), **claims to verify** (what you are about to tell the user is done / works / safe; for `plan`, state the approach itself and the alternatives you dropped; for `stuck`, your current hypothesis), approaches already rejected, and the transcript path if you know it.
- Leave out your summary of the user's requirements, the reasoning behind your conclusion (it anchors the reviewer), and pasted file contents. The reviewer reads the user's original messages and the files itself.
- Include the part you are least sure about: the reviewer cannot see your doubts otherwise.
- Parallel work goes in as "places this change may affect", never as "out of scope".
- If the user asked something you have not answered, add it in one line (`python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/user-asks.py" --claims 3` can extract it).
- Scratch: a hook appends a run line with the reviewer's scratch directory to the prompt; leave it out of the brief.

## What comes back

An English report: a verdict (proceed / proceed after fixes / rethink), findings by severity (must / should / note) with evidence and "how verified or inferred", a table matching the user's requirements, a table checking each claim, and what it could not see. "No findings" is stated with the range it looked at.

## How to read what comes back

The reviewer sees without your assumptions, but it does not know how you reached your conclusion. An objection may lean on something you already considered and ruled out. Before accepting it, check whether your own reasoning already answers it. If it does, reject it on that ground and note in the brief that the part was missing.

## After you get it

1. Decide each finding: accepted / rejected / needs check. Give evidence for a rejection (file:line, run output). When the reviewer's evidence and yours conflict, settle it by running something.
2. You called it yourself (including on a hook notice): act on it and tell the user in 1-3 lines what you accepted and rejected. The full report stays in the transcript.
   If you are a subagent, put what you accepted and rejected in your report to your caller instead of telling the user.
   The user asked for it: show the report in full, in Korean, then your judgment below it, separately. Quote the user's own words in their original language.
3. Record it, so the user can see which triggers and reviewers pay off. `--trigger` is `hook:<commit|stop|failure|plan>` for a hook notice, `self` if you decided, `user` if the user asked. `--reviewer` is one of `opus-sub | sonnet-sub | fork | ctx-opus | ctx-sonnet | codex | agy | advisor-opus | advisor-fable`. `--caller` is `main` if you are the main agent, `subagent` if you are a subagent. Verdicts: 진행 | 고친뒤진행 | 다시생각 | 발견없음 | 실패.

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/review-ledger.py" add --kind <plan|stuck|done> --reviewer <opus-sub|sonnet-sub> \
  --caller <main|subagent> --trigger <hook:commit|self|user> --verdict <verdict> --found <N> --adopted <N> --must <N> --note "<one line>"
```

`review-ledger.py stats`, `advisor-stats.py --all` (advisor usage and cost), and `user-asks.py [--since-compact] [--last N] [--claims K]` (the user's original messages) are in `${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/`.
