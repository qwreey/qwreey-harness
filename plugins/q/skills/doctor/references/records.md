# 11. Agent records (REC-*)

Check: `python3 -I ${CLAUDE_SKILL_DIR}/../../scripts/records_check.py --root <path> [--json]` (read-only, skip for intake). `REC-` codes follow the `coderag:agent-records` skill.

- Report counts per code in item 11.
- `REC-CLOSED-OUTSIDE-ARCHIVE` (status already not active): list the files as one "move to archive" fix item.
  - Only after approval, in one commit: `git mv` plus link and README fixes. Never delete.
  - For each file say it can instead be set back to `active` if it is still a current source.
- Never propose closing a doc because its work is done; whether a doc is still a current source is the repo's call.
- `REC-STATUS-MISSING` on old docs is info: do not propose a backfill.
- `REC-FORMAT-BAD` (frontmatter `format` is not a positive integer) is a fix item: correct the value. Whether coderag supports that number is `coderag lint`'s call.
- A missing `format` on old records is not a finding.
- If the repo has coderag, also run `coderag static-gen --check` and `coderag stale` and report their lines in the same item.
