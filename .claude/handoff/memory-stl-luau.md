# stl-luau 세션에게: 메모리 분류 인계 (읽기 전용 감사)

claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-stl-luau/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다.
저장소 밖(`~/.claude`)에 있는 메모리는 다른 clone, 다른 기기, 동료에게 가지 않는다. 아래 `저장소로`·`pack으로` 항목은 그쪽으로 옮기자는 제안이고, 반영 여부와 문구는 이 저장소 세션과 사용자가 정한다.

요약: 유지 4, 저장소로 6, pack으로 1, 낡음 0 (총 11). 분류는 자동 신호(`lib/memory_signals.py`)가 아니라 원문을 읽고 사람이 판단했다.

| 메모리 파일 | 분류 | 이유 | 제안 |
|---|---|---|---|
| `agy-budget-generous.md` | 유지 | 한도 상황은 자주 바뀌는 사용자 사정. 이름('generous')과 내용(빠듯함)이 어긋나 혼동 소지 | - |
| `agy-is-second-opinion.md` | 유지 | 사용자 선호(Gemini 는 다른 시선용) | - |
| `autonomous-run-budget.md` | 유지 | 자리 비움 때의 사용자 선호. question.md·todos.md 는 포인터 수준 | - |
| `subagent-keep-artifacts.md` | 유지 | 서브에이전트 운용 선호 | - |
| `dx-before-micro-optimization.md` | 저장소로 | stl 설계 원칙(DX 우선). 이 레포에 기여하는 누구에게나 해당 | CLAUDE.md 설계 원칙 절 |
| `give-named-frame.md` | 저장소로 | 라이브러리 설계 원칙(이름 있는 틀을 준다) | CLAUDE.md 설계 원칙 절 |
| `luau-run-resource-caps.md` | 저장소로 | `luau` 실행 시 ulimit·timeout 규약과 check.sh 상한. 사고 근거는 환경이지만 규약 자체는 저장소 것 | CLAUDE.md 또는 `.claude/rules/run-limits.md` |
| `real-consumer.md` | 저장소로 | stl 의 실사용처와 검증 방침(프로젝트 맥락) | CLAUDE.md 프로젝트 목적 절 |
| `trait-shelved-classes-target.md` | 저장소로 | 2026-11-09 방향 결정(stl-trait 분리, 클래스 탑승). 결정 기록이다 | decisions 문서 또는 question.md 정본 |
| `types-separate-from-runtime.md` | 저장소로 | 타입과 런타임을 분리한다는 설계 결정 | decisions 문서 |
| `studio-is-luau-lsp.md` | pack으로 | Studio 타입 검사는 luau-lsp 와 같다는 일반 Luau/Roblox 지식 | luau-kb |

## 옮기는 순서(제안)
1. `저장소로` 항목을 CLAUDE.md, `.claude/rules/`, docs 중 맞는 곳에 쓴다(메모리 원문을 복사하지 말고 지금 사실로 확인해서 쓴다).
2. 옮긴 뒤 해당 메모리 파일과 MEMORY.md 줄을 정리한다(삭제는 사용자가 승인한 것만).
3. `pack으로` 는 luau-kb 담당 세션에 전달한다.
4. `낡음` 은 사용자에게 지울지 묻는다.
