Kind: <plan | stuck | done>
Repo: <absolute path>        Scope: <e.g. git diff HEAD~3..HEAD, a path list, or a plan file path>
Files I changed: <list. The working tree may hold other sessions' changes; the reviewer treats changes outside this list as context, not findings>
Transcript: <path if known. If not, delete this line (the reviewer finds it via CLAUDE_CODE_SESSION_ID)>

Goal: <one or two lines. The goal of this work unit, not a summary of the user's requirements>
Constraints: <what must hold. e.g. keep the public API, other repos read-only, ~/.claude only via the canonical source>
Approach (plan): <the approach I am about to lock in, and the alternatives I dropped>
Rejected approaches: <do not bring these back. "none" if none>
Parallel work that may be affected: <one line per other agent or session. Never write "out of scope". "none" if none>
Unanswered questions: <what I asked the user and got no answer to. "none" if none>

Claims to verify (what I am about to tell the user):
1. <e.g. "all 4 tests pass">
2. <e.g. "every new file is listed in MANIFEST">
3. <e.g. "the notice reappears after compact (checked only with a manual /compact)">

Least sure about: <one line. Never leave it blank>
(stuck only) Repeated failure: <command and first line of the error>; my current hypothesis: <one line>
