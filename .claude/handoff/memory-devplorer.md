# devplorer 세션에게: 메모리 분류 인계 (읽기 전용 감사)

claude-doctor 의 `.claude/audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-devplorer/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다.
저장소 밖(`~/.claude`)에 있는 메모리는 다른 clone, 다른 기기, 동료에게 가지 않는다. 아래 `저장소로`·`pack으로` 항목은 그쪽으로 옮기자는 제안이고, 반영 여부와 문구는 이 저장소 세션과 사용자가 정한다.

요약: 유지 6, 저장소로 2, pack으로 1, 낡음 1 (총 10). 분류는 자동 신호(`lib/memory_signals.py`)가 아니라 원문을 읽고 사람이 판단했다.

| 메모리 파일 | 분류 | 이유 | 제안 |
|---|---|---|---|
| `feedback-agent-repo-push.md` | 유지 | sandbox 의 git 원격 흐름(에이전트 계정). 환경·사용자 흐름 | - |
| `feedback-decision-style.md` | 유지 | quad 와 중복된 사용자 성향 | 전역 CLAUDE.md 후보 |
| `feedback-korean.md` | 유지 | 사용자 언어 선호 | - |
| `feedback-outside-reviewers.md` | 유지 | 허용 외부 모델(사용자 정책)과 이 작업 공간 호출법 | - |
| `feedback-subagent-worktree.md` | 유지 | 백그라운드 세션·worktree 하네스 동작 | - |
| `user-quad-author.md` | 유지 | 사용자 소개 | - |
| `devplorer-goal.md` | 저장소로 | 프로젝트 목적과 보안 제약(익스플로잇 경로 금지). 협업자가 반드시 알아야 한다 | CLAUDE.md 프로젝트 목적·보안 절 |
| `feedback-audit-after-move.md` | 저장소로 | 옮기거나 나눈 뒤 이음매 감사를 돌린다는 작업 규약 | `.claude/conventions.md` |
| `feedback-studio-play.md` | pack으로 | Studio Play 중에는 멈추거나 싱크하지 말 것. Roblox Studio MCP 일반 요령 | luau-kb(Studio MCP 절) |
| `feedback-review-model.md` | 낡음 | 리뷰 서브에이전트 모델 기본은 conventions.md '서브에이전트' 절에 이미 있다(중복) | 삭제 제안 |

## 옮기는 순서(제안)
1. `저장소로` 항목을 CLAUDE.md, `.claude/rules/`, docs 중 맞는 곳에 쓴다(메모리 원문을 복사하지 말고 지금 사실로 확인해서 쓴다).
2. 옮긴 뒤 해당 메모리 파일과 MEMORY.md 줄을 정리한다(삭제는 사용자가 승인한 것만).
3. `pack으로` 는 luau-kb 담당 세션에 전달한다.
4. `낡음` 은 사용자에게 지울지 묻는다.
