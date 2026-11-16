---
name: inherit-advisor
description: Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that knows how you got here, steps out of your role, and challenges your reasoning, not your diff. Reach for it whenever you want another view, and before you act on a conclusion that only you have checked and that would be costly to get wrong. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토.
argument-hint: "[reqs] [one-line note]"
---

# qwreey-advisor:inherit-advisor

## Call

```
Agent(subagent_type="fork", description="second opinion: inherit-advisor",
      prompt="[qwreey-advisor:inherit] Review only. Do not continue the work, edit files, or commit.\nnext: <one line: what you are about to do or say>")
```

A plugin hook expands this marker into the full review prompt (`templates/fork-prompt.md`). If the hook does not run, the marker still limits the fork to review, so do not paste the template by hand. The built-in `advisor` tool is not involved.

Which one: ask what you doubt. If it is whether your reasoning holds, inherit-advisor sees why you decided and costs little. If the framing itself may be wrong, or the step is hard to undo, fresh-advisor starts without your assumptions and reads the files and the user's words. Do not run both on the same point.

## Arguments

- `next:` one factual line about what you are about to do or say. Leave your suspicions out: the fork would look only there and skip the rest.
- `options: reqs` (optional; add it as a last line `options: reqs` in the prompt) adds a check of the user's messages against the result. It searches wider, so use it at a big turning point (after a compact, when pending decisions are being tidied) or when the user asks.
- Call it in the same turn, at the decision point, before the step it guards; the fork reuses the prompt cache only while it is warm. The fork runs on your model. A cold cache makes it re-write the whole context (about USD 1.5 more at 300k tokens on opus).
- Once per turning point.
- If the repo tier is `off` (`HARNESS_REVIEW_TIERS` in `~/.claude/harness.env`), the user has turned reviews off for that repo: call it only when they ask. Hooks do not block this skill, so this line is the only guard.

## What comes back

An English report written for you. Each item has what was missed, evidence, why it matters before the next step, and severity (must / should / note). Checked facts are separated from inference, and it ends with "Before next step:" in at most 3 lines. A category with nothing is marked n/a with a reason. A run costs about USD 0.5-0.6 at 300k tokens of context on opus, mostly cache reads, and the report (2-3k tokens) joins your context.

## How to read what comes back

The fork knows how you reached your conclusion, so its objections are made with that knowledge. When it agrees, check whether it only repeated your own reasoning.

## After you get it

1. Check each finding against the facts. Accept or reject it with evidence. A finding that contradicts what is verifiably done (says something is undone that is done) is rejected after you verify.
2. You called it yourself: act on it, and tell the user in 1-3 lines what you accepted and rejected. The full report stays in the transcript.
   If you are a subagent, put what you accepted and rejected in your report to your caller instead of telling the user.
   The user asked for it: show the report in full, in Korean, headed "inherit-advisor 검토(fork)", then mark each finding accepted / rejected / needs check.
3. Record it, so the user can see which triggers pay off (`--verdict` is one of 진행 | 고친뒤진행 | 다시생각 | 발견없음 | 실패; `--reviewer` is `fork` here). A hook already logged the run with verdict `미기록`; your row replaces it, so the count stays one:

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/review-ledger.py" add --kind inherit --reviewer fork --caller <main|subagent> --verdict <verdict> --found <N> --adopted <N>
```
