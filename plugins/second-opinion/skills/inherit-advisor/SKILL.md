---
name: inherit-advisor
description: Second opinion from a fork that has read this whole conversation and now acts as an independent reviewer, looking for what the flow missed, wrong premises, unchecked assumptions, counterexamples to the design just done. Call it right before telling the user a conclusion, decision, or direction change, before moving on after reporting a work unit done, and before hard-to-undo steps such as apply or install guidance. For code/diff correctness, see fresh-advisor. 한 번 더 봐줘, 다른 눈으로 검토, 맥락 검토.
argument-hint: "[reqs] [one-line note]"
---

# second-opinion:inherit-advisor

A fork of this session reviews the conversation as an independent reviewer. You pick it up yourself, the way you would an advisor, at the moments below. It does not call the built-in `advisor` tool. Rationale, measurements, cost: `references/rationale.md`.

## When

- About to tell the user a conclusion, a decision, or a change of direction.
- Reported a work unit as done and about to move to the next one.
- About to give apply, deploy, or install guidance, or any step that is hard to undo.
- Big turning point in a long session (right after compact, tidying pending decisions): add `options: reqs`.

Once per turning point. If the repo tier (`HARNESS_REVIEW_TIERS`) is `off`, call it only when the user asks.

## How

Send a short marker. A plugin hook replaces it with the full review prompt; the marker alone already tells the fork to review only.

```
Agent(subagent_type="fork", description="second opinion: inherit-advisor",
      prompt="[second-opinion:inherit] Review only. Do not continue the work, edit files, or commit.\nnext: <one line: what main is about to do or say>\noptions: reqs")
```

- `next:` is one line in Korean or English. Keep it factual; do not add suspicions from this session (the fork then looks only there).
- `options: reqs` adds the requirement check (re-read the user's messages and match each against the result). Add it only when the user asks for it, or at a big turning point.
- Call it right after your latest response while the cache is warm. The fork runs on the main model. Cost is about $0.5-0.6 per fork at 300k tokens on opus; tell the user when it is non-trivial.
- Template and option fragment: `templates/fork-prompt.md`, `templates/fork-prompt-reqs.md`. If the hook did not run, the marker's instruction still holds; do not paste the template by hand.

## Result

Head the report "inherit-advisor 검토(fork)" so it does not read as your own text. Show it to the user unsummarized, mark each finding accepted / rejected / needs check with evidence, then record it:

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/fresh-advisor/scripts/review-ledger.py" add --kind inherit --reviewer fork --verdict <...> --found N --adopted N
```

If a finding contradicts the facts (claims something undone that is done), verify, then reject it with evidence.
