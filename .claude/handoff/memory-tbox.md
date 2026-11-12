# tbox 세션에게: 메모리 분류 인계 (읽기 전용 감사)

claude-doctor 의 `audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-tbox/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다.
저장소 밖(`~/.claude`)에 있는 메모리는 다른 clone, 다른 기기, 동료에게 가지 않는다. 아래 `저장소로`·`pack으로` 항목은 그쪽으로 옮기자는 제안이고, 반영 여부와 문구는 이 저장소 세션과 사용자가 정한다.

요약: 유지 1, 저장소로 2, pack으로 0, 낡음 0 (총 3). 분류는 자동 신호(`lib/memory_signals.py`)가 아니라 원문을 읽고 사람이 판단했다.

| 메모리 파일 | 분류 | 이유 | 제안 |
|---|---|---|---|
| `tbox-tooling-gotchas.md` | 유지 | mise trust·Studio MCP 한계·lute vs luau 는 로컬 환경 사실. lute vs luau 는 pack 후보 | lute 부분만 luau-kb 검토 |
| `design-before-breaking.md` | 저장소로 | 깨지는 변경을 부를 기능은 종이 설계 먼저. 프로젝트 설계 원칙 | CLAUDE.md |
| `testing-work-policy.md` | 저장소로 | test-todo.md 작업 방식(버그 즉시 수정, 항목마다 main 커밋, 서브에이전트 3개 이하) | CLAUDE.md 또는 packages/tbox/test-todo.md 머리 |

## 옮기는 순서(제안)
1. `저장소로` 항목을 CLAUDE.md, `.claude/rules/`, docs 중 맞는 곳에 쓴다(메모리 원문을 복사하지 말고 지금 사실로 확인해서 쓴다).
2. 옮긴 뒤 해당 메모리 파일과 MEMORY.md 줄을 정리한다(삭제는 사용자가 승인한 것만).
3. `pack으로` 는 luau-kb 담당 세션에 전달한다.
4. `낡음` 은 사용자에게 지울지 묻는다.
