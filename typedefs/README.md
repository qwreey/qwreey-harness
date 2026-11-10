# typedefs — Roblox 전역 타입 정의

`globalTypes.d.luau` 는 `luau-lsp analyze --platform=roblox --definitions=<이 파일>` 로 Roblox 코드를 검사할 때 쓰는 정의 파일이다. `luau-analyze` 는 정의 파일을 읽지 못한다(luau-verify 스킬 `references/checkers.md`).

## 출처

| 항목 | 값 |
|---|---|
| 복사 원본 | `/code/Projects/quad/scripts/roblox-defs/globalTypes.d.luau` |
| 원본의 마지막 커밋 | quad `2ad2c03e` (2026-09-02) |
| 복사일 | 2026-11-10 |
| md5 | `be071eac475bc4bbc8ca99a08fcfdcc0` |
| 크기 | 806,997 바이트, 19,110 줄 |
| 확인 | luau-lsp 1.70.1 에서 `Instance.new("Part").Name` 을 `number` 에 대입하면 잡힘 |

## 다른 복제본과의 비교 (2026-11-10, md5)

quad 원본을 빼고 작업 트리 밖에 있는 복제본은 7개다.

| 경로 | md5 | 크기(바이트) | quad 원본과 |
|---|---|---|---|
| `devplorer/typedefs/globalTypes.d.luau` | `be071eac475bc4bbc8ca99a08fcfdcc0` | 806,997 | 같음 |
| `devplorer/vendor/quad/scripts/roblox-defs/globalTypes.d.luau` | `be071eac475bc4bbc8ca99a08fcfdcc0` | 806,997 | 같음 |
| `table-sim/<비공개>` | `be071eac475bc4bbc8ca99a08fcfdcc0` | 806,997 | 같음 |
| `table-sim/<비공개>` | `be071eac475bc4bbc8ca99a08fcfdcc0` | 806,997 | 같음 |
| `quad-agy/naming-1021e/scripts/roblox-defs/globalTypes.d.luau` | `be071eac475bc4bbc8ca99a08fcfdcc0` | 806,997 | 같음 |
| `rbvm/.claude/cache/globalTypes.d.luau` | `b1bcb06500f9f57825634af54618c80b` | 682,406 (17,057줄) | **다름** — rbvm 이 luau-lsp 레포에서 직접 받아 캐시한 판(`rbvm/.claude/tools/check.sh` 머리 주석) |
| `tbox/typedefs/roblox/globalTypes.None.d.luau` | `91f5a86197bb0f3c8fb277b02c445b30` | 643,708 (16,190줄) | **다름** — 보안 수준 `None` 판(파일명), 그 저장소의 luau-lsp 1.69.0 핀에 맞춘 것 |

- 이 밖에 `quad/.claude/worktrees/agent-*/scripts/roblox-defs/` 아래 사본 8개도 원본과 md5 가 같다. 작업 트리는 임시라 표에서 뺐다.
- `quad-changelog-check` 는 삭제되어 비교 대상이 아니다.
- 서로 다른 두 판(rbvm, tbox)은 클래스별 프로퍼티 수, deprecated 멤버, 이벤트 표현이 다를 수 있다. 정의 데이터에 따라 같은 코드의 진단이 달라진다(quad typing-limits 8.22, luau-types 스킬 `type-functions.md` §7).

## 단일 원천으로 쓰는 법 (제안, 미적용)

각 프로젝트의 사본은 이 파일을 가리키게 바꿀 수 있다(심볼릭 링크 또는 `--definitions=/code/Projects/luau-kb/typedefs/globalTypes.d.luau`). 다른 저장소는 수정하지 않았다. 판을 올릴 때는 이 README 의 md5 와 날짜를 갱신하고, Roblox 코드를 검사하는 각 프로젝트의 게이트를 다시 돌린다.
