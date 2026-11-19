# Hook bench (3 runs each, temp sandbox)

- python3 startup floor: p50 11 ms, max 12 ms

## Per tool call (p50)

- Bash: PreToolUse 9 hooks: sum 256 ms, wall 46 ms; PostToolUse 7 hooks: sum 200 ms, wall 49 ms; PostToolBatch 2 hooks: sum 77 ms, wall 41 ms
- Read: PreToolUse 2 hooks: sum 43 ms, wall 23 ms; PostToolUse 6 hooks: sum 150 ms, wall 45 ms; PostToolBatch 2 hooks: sum 77 ms, wall 39 ms
- Edit: PreToolUse 2 hooks: sum 43 ms, wall 22 ms; PostToolUse 11 hooks: sum 330 ms, wall 48 ms; PostToolBatch 2 hooks: sum 75 ms, wall 40 ms

## Per hook

| hook | event | tool | p50 ms | max ms | spoke | exit |
|---|---|---|---|---|---|---|
| qwreey-sessions:hook.py PreToolUse | PreToolUse | Bash | 46 | 49 | 0/3 | 0 x3 |
| qwreey-advisor:second-opinion-nudge.py | PreToolUse | Bash | 44 | 44 | 0/3 | 0 x3 |
| qwreey-proc-guard:resource-guard.py | PreToolUse | Bash | 35 | 37 | 0/3 | 0 x3 |
| qwreey-conventions:bash-bypass-reminder.py | PreToolUse | Bash | 34 | 35 | 0/3 | 0 x3 |
| qwreey-proc-guard:heavy-proc-guard.py | PreToolUse | Bash | 24 | 26 | 0/3 | 0 x3 |
| qwreey-advisor:readonly-for-reviewers.py | PreToolUse | Bash | 21 | 22 | 0/3 | 0 x3 |
| qwreey-workspace:workspace_gate.py PreToolUse | PreToolUse | Bash | 21 | 22 | 0/3 | 0 x3 |
| qwreey-proc-guard:self-match-guard.py | PreToolUse | Bash | 21 | 21 | 0/3 | 0 x3 |
| coderag:coderag hook pre-bash | PreToolUse | Bash | 11 | 12 | 0/3 | 0 x3 |
| qwreey-sessions:hook.py PostToolUse | PostToolUse | Bash | 49 | 49 | 0/3 | 0 x3 |
| qwreey-conventions:structure-reminder.py | PostToolUse | Bash | 34 | 35 | 0/3 | 0 x3 |
| qwreey-proc-guard:resource-guard.py | PostToolUse | Bash | 33 | 34 | 0/3 | 0 x3 |
| qwreey-conventions:bash_writes.py | PostToolUse | Bash | 29 | 30 | 0/3 | 0 x3 |
| qwreey-operator:delegate-nudge.py | PostToolUse | Bash | 29 | 29 | 0/3 | 0 x3 |
| q:subagent-slots.py | PostToolUse | Bash | 14 | 15 | 0/3 | 0 x3 |
| coderag:coderag hook post-tool | PostToolUse | Bash | 11 | 12 | 0/3 | 0 x3 |
| qwreey-advisor:second-opinion-nudge.py | PostToolBatch | Bash | 41 | 45 | 0/3 | 0 x3 |
| qwreey-reply-language:reply_language.py | PostToolBatch | Bash | 36 | 44 | 0/3 | 0 x3 |
| qwreey-advisor:readonly-for-reviewers.py | PreToolUse | Edit | 22 | 23 | 0/3 | 0 x3 |
| qwreey-workspace:workspace_gate.py PreToolUse | PreToolUse | Edit | 20 | 21 | 0/3 | 0 x3 |
| qwreey-sessions:hook.py PostToolUse | PostToolUse | Edit | 48 | 50 | 0/3 | 0 x3 |
| qwreey-conventions:reuse-check.py | PostToolUse | Edit | 47 | 49 | 0/3 | 0 x3 |
| qwreey-conventions:conventions-check.py | PostToolUse | Edit | 42 | 42 | 0/3 | 0 x3 |
| qwreey-conventions:structure-reminder.py | PostToolUse | Edit | 34 | 34 | 0/3 | 0 x3 |
| qwreey-conventions:memory-placement.py | PostToolUse | Edit | 33 | 33 | 0/3 | 0 x3 |
| qwreey-workspace:sibling_notice.py | PostToolUse | Edit | 32 | 33 | 0/3 | 0 x3 |
| qwreey-conventions:rules_inject.py | PostToolUse | Edit | 29 | 33 | 0/3 | 0 x3 |
| qwreey-operator:delegate-nudge.py | PostToolUse | Edit | 29 | 29 | 0/3 | 0 x3 |
| q:subagent-slots.py | PostToolUse | Edit | 14 | 15 | 0/3 | 0 x3 |
| coderag:coderag hook post-tool | PostToolUse | Edit | 11 | 11 | 0/3 | 0 x3 |
| coderag:coderag hook post-edit | PostToolUse | Edit | 11 | 11 | 0/3 | 0 x3 |
| qwreey-advisor:second-opinion-nudge.py | PostToolBatch | Edit | 40 | 43 | 0/3 | 0 x3 |
| qwreey-reply-language:reply_language.py | PostToolBatch | Edit | 35 | 37 | 0/3 | 0 x3 |
| qwreey-sessions:records_read.py PreToolUse | PreToolUse | Read | 23 | 24 | 0/3 | 0 x3 |
| qwreey-workspace:workspace_gate.py PreToolUse | PreToolUse | Read | 19 | 20 | 0/3 | 0 x3 |
| qwreey-sessions:hook.py PostToolUse | PostToolUse | Read | 45 | 49 | 0/3 | 0 x3 |
| qwreey-conventions:rules_inject.py | PostToolUse | Read | 30 | 36 | 1/3 | 0 x3 |
| qwreey-operator:delegate-nudge.py | PostToolUse | Read | 26 | 28 | 0/3 | 0 x3 |
| qwreey-sessions:records_read.py PostToolUse | PostToolUse | Read | 22 | 24 | 0/3 | 0 x3 |
| q:subagent-slots.py | PostToolUse | Read | 15 | 15 | 0/3 | 0 x3 |
| coderag:coderag hook post-tool | PostToolUse | Read | 11 | 11 | 0/3 | 0 x3 |
| qwreey-advisor:second-opinion-nudge.py | PostToolBatch | Read | 39 | 40 | 0/3 | 0 x3 |
| qwreey-reply-language:reply_language.py | PostToolBatch | Read | 38 | 39 | 0/3 | 0 x3 |

Skipped: none
