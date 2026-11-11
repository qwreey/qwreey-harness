---
name: other-frame
description: User command. Runs a heavier second opinion that reads a text copy of this conversation (from the last compact boundary, tool results trimmed) under a different system prompt, via the other-frame agent, to catch what the main frame missed. Run it when the user asks for another angle on a long session, or when an inherit-advisor fork returned almost nothing on heavy work. 다른 프레임 검토, 다른 눈으로 한 번 더.
disable-model-invocation: true
argument-hint: "[sonnet|opus] [one-line note]"
---

# second-opinion:other-frame

Reads a text copy of the main conversation under a different system prompt (`agents/other-frame.md`). It does not call the built-in `advisor` tool. Rationale, cost, measurements: `references/rationale.md`.

## How

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/other-frame/scripts/ask-other-frame.py" --model <sonnet|opus> --note "<one-line next step>"   # run in background
```
- `scripts/render-transcript.py` builds the copy: from the last compact boundary, tool results cut to the first 300 characters.
- Do not pass the copy through the Agent tool; retyping it costs main output tokens.
- The script installs the read-only guard (`hooks/auditor-readonly-guard.py`) itself via `--settings`.
- Cost: first call is a cache write, proportional to context (132k tokens: opus about $1.25, sonnet about $0.49). Use opus for high-tier work.

## Result

Show the report to the user unsummarized, mark each finding accepted / rejected / needs check with evidence, and record it in the ledger (`--kind inherit --reviewer ctx-opus|ctx-sonnet` of `skills/fresh-advisor/scripts/review-ledger.py`). Head it "other-frame 검토".
