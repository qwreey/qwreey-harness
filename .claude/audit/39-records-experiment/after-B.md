# After B (real layout, paths fixed)

Command: `choom -n 1000 -- timeout 600 python3 -I measure.py --root <repo> --map move-map.tsv --coderag <bin>`. measure.py needed no change; it also rewrote after.md, which was restored from git (after.md is the simulated-move result).

# After-move measure

Regenerate: `python3 -I measure.py --root <repo> --map move-map.tsv --coderag $HARNESS_CODERAG`

phase=after corpus_files=238 coderag_config=explicit (.claude + root target that sees PLAN.md); implicit config alone would miss root PLAN.md

| id | gold | grep rank | coderag rank |
|---|---|---|---|
| q01 | 1 | 1 | 1 |
| q02 | 1 | 2 | 1 |
| q03 | 1 | 2 | - |
| q04 | 1 | - | 1 |
| q05 | 1 | - | - |
| q06 | 3 | 1 | 1 |
| q07 | 1 | 4 | 1 |
| q08 | 1 | 1 | 1 |
| q09 | 1 | - | - |
| q10 | 1 | - | 1 |
| q11 | 1 | 4 | - |
| q12 | 1 | - | 4 |

| strategy | hit@5 | MRR | avg bytes of top-5 |
|---|---|---|---|
| grep | 7/12 | 0.375 | 250,103 |
| coderag | 8/12 | 0.604 | 12,205 |

coderag stale issues on the copy: 11

## Comparison

| | grep hit@5 | grep MRR | coderag hit@5 | coderag MRR | stale |
|---|---|---|---|---|---|
| baseline (before move) | 7/12 | 0.382 | 9/12 | 0.688 | 12 |
| after.md (simulated move) | 7/12 | 0.382 | 8/12 | 0.604 | see after.md |
| after B (real) | 7/12 | 0.375 | 8/12 | 0.604 | 11 |

Differences vs baseline: coderag q09 hit at rank 1 before, now a miss (same as the simulated move, so caused by the layout, not by path fixes); grep q11 rank 3 -> 4 (more files now match under .claude/). Everything else is the same.
