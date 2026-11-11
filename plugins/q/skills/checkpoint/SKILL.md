---
name: checkpoint
description: Flush the automatic session log now (summarize everything since the last saved point), then show only the new open items and user directives, and draft /compact arguments from the record instead of from memory. Use before /compact, before a handover, or when the user asks to save/record the session.
---

# /q:checkpoint — save the session log now

The session-log hooks (part of the `q` plugin) summarize this session in the background on its own (PreCompact, SessionEnd, every ~20 min of growth).
Use this skill when you want a checkpoint **now**.

1. Flush synchronously (takes ~30–120 s; model: haiku, no tools):
   ```bash
   session-log flush --force --wait 2>/dev/null || "${CLAUDE_PLUGIN_ROOT}/bin/session-log" flush --force --wait
   ```
   The JSON line reports `sections`, `records` (paths outside the repo), `flagged` (items that failed the source check, marked ⚠).
2. Read **only** the newest section's `### 사용자 지시와 정정` and `### 미해결과 다음 단계`:
   `session-log show <rid> --section <N>` (N = last section; `session-log pending` lists rids).
   Do not read the whole record into context.
3. Draft a `/compact` argument from it: keep (user directives verbatim, open items), drop (finished exploration), next step.
   Show it to the user; do not run /compact yourself unless asked.
4. If a user directive repeats across sections, you may *suggest* it as a memory entry. Do not write memory without the user's approval.

Notes
- Items marked `⚠원문 불일치` / `⚠근거 줄 다름` failed the mechanical check against the transcript. Check the cited `(L…)` line in the transcript before relying on them.
- The record lives outside the repo until imported. To bring it into the repo, use /q:import.
