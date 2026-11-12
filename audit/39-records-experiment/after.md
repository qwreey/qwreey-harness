# After-move measure

Regenerate: `python3 -I measure.py --root <repo> --map move-map.tsv --coderag $HARNESS_CODERAG`

phase=after corpus_files=232 coderag_config=explicit (.claude + root target that sees PLAN.md); implicit config alone would miss root PLAN.md

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
| q11 | 1 | 3 | - |
| q12 | 1 | - | 4 |

| strategy | hit@5 | MRR | avg bytes of top-5 |
|---|---|---|---|
| grep | 7/12 | 0.382 | 259,651 |
| coderag | 8/12 | 0.604 | 12,202 |

coderag stale issues on the copy: 11
