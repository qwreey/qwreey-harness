# 이동 후 측정, coderag 강등 한 번으로 고친 뒤

> Snapshot 2026-11-12. coderag b29e88a 다음 변경(끝난 문서 강등을 한 번만) 적용 후 같은 명령으로 잰 값. 직전 after-B.md 에서 q09(archive 로 간 session-log DESIGN.md)가 빠진 원인은 archive 폴더 문서가 is_archive_like 와 listed=false 로 점수를 두 번 반으로 나눈 것이었다.

# After-move measure

Regenerate: `python3 -I measure.py --root <repo> --map move-map.tsv --coderag $HARNESS_CODERAG`

phase=after corpus_files=239 coderag_config=explicit (.claude + root target that sees PLAN.md); implicit config alone would miss root PLAN.md

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
| q11 | 1 | 4 | - |
| q12 | 1 | - | 4 |

| strategy | hit@5 | MRR | avg bytes of top-5 |
|---|---|---|---|
| grep | 7/12 | 0.375 | 250,103 |
| coderag | 9/12 | 0.632 | 12,207 |

coderag stale issues on the copy: 11
