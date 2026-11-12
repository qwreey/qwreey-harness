# 이동 후 측정, 커밋 D(색인과 폴더 status) 뒤

> Snapshot 2026-11-12. 커밋 C(끝난 문서 archive)와 D(.claude/README.md, 폴더 색인, 열린 draft 폴더의 status) 뒤 같은 명령으로 잰 값.

# After-move measure

Regenerate: `python3 -I measure.py --root <repo> --map move-map.tsv --coderag $HARNESS_CODERAG`

phase=after corpus_files=252 coderag_config=explicit (.claude + root target that sees PLAN.md); implicit config alone would miss root PLAN.md

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
| q09 | 1 | - | 3 |
| q10 | 1 | - | 1 |
| q11 | 1 | 4 | 5 |
| q12 | 1 | - | 4 |

| strategy | hit@5 | MRR | avg bytes of top-5 |
|---|---|---|---|
| grep | 7/12 | 0.375 | 250,577 |
| coderag | 10/12 | 0.649 | 11,494 |

coderag stale issues on the copy: 10
