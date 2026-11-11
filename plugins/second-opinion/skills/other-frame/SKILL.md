---
name: other-frame
description: User command. A heavier second opinion: a reviewer under a different system prompt reads a text copy of this conversation (from the last compact boundary) to catch what the main frame missed. 다른 프레임 검토, 다른 눈으로 한 번 더.
disable-model-invocation: true
argument-hint: "[sonnet|opus] [one-line note]"
---

# second-opinion:other-frame

## Call

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/other-frame/scripts/ask-other-frame.py" --model <sonnet|opus> --note "<one-line next step>"   # run in background
```

- `--model`: opus for high-tier work, sonnet otherwise. `--note`: one factual line about the next step; it reaches the reviewer as a claim.
- `scripts/render-transcript.py` builds the text copy: from the last compact boundary, tool results cut to the first 300 characters. Do not pass the copy through the Agent tool; retyping it costs main output tokens.
- The script installs the read-only guard (`hooks/auditor-readonly-guard.py`) itself via `--settings`.

## What comes back

An English report (`agents/other-frame.md`): items with what was missed, evidence (`[L<number>]` of the transcript), why it matters, severity (must / should / note), then "Before next step:" in at most 3 lines.

## After you get it

The user asked for this command, so show the report in full, in Korean, headed "other-frame 검토". Mark each finding accepted / rejected / needs check with evidence, and record it in the ledger (`--kind inherit --reviewer ctx-opus|ctx-sonnet` of `skills/fresh-advisor/scripts/review-ledger.py`).

Cost grows with the size of the conversation copy: about $1.25 on opus or $0.49 on sonnet at 132k tokens, so use opus for high-tier work and sonnet otherwise.
