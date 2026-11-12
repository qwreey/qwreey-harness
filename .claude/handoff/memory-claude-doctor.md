# claude-doctor 세션에게: 메모리 분류 인계 (읽기 전용 감사)

claude-doctor 의 `audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-claude-doctor/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다.
저장소 밖(`~/.claude`)에 있는 메모리는 다른 clone, 다른 기기, 동료에게 가지 않는다. 아래 `저장소로`·`pack으로` 항목은 그쪽으로 옮기자는 제안이고, 반영 여부와 문구는 이 저장소 세션과 사용자가 정한다.

요약: 유지 6, 저장소로 4, pack으로 0, 낡음 2 (총 12). 분류는 자동 신호(`lib/memory_signals.py`)가 아니라 원문을 읽고 사람이 판단했다.

| 메모리 파일 | 분류 | 이유 | 제안 |
|---|---|---|---|
| `env-agents.md` | 유지 | 이 sandbox 의 agy·codex 환경 | - |
| `git-workflow-sandbox.md` | 유지 | sandbox git 계정 흐름(환경·사용자 흐름) | - |
| `model-usage-policy.md` | 유지 | 사용자 발언 기반 모델 사용 선호 | 회사 배포 시 CLAUDE.md 로 옮길지 별도 판단 |
| `propose-dont-overwrite-user-choices.md` | 유지 | 사용자 성향 | - |
| `user-company-rollout.md` | 유지 | 사용자 배경과 회사 배포 맥락. 회사 요구 중 하네스 설계에 쓰는 부분은 PLAN.md 에 반영돼 있는지 확인 | - |
| `user-ergonomics-axis.md` | 유지 | 사용자 시각 선호(statusline, nerd font). 설계 결론은 audit/22 | - |
| `harness-direction.md` | 저장소로 | 하네스 재구성 방향 결정. decisions/ 와 PLAN.md 가 정본이어야 한다 | PLAN.md / decisions |
| `harness-toolkit-agnostic.md` | 저장소로 | 공통 코어 + 툴킷 자리 설계 원칙 | PLAN.md / README |
| `cost-fanout-policy.md` | 저장소로 | 정책은 home/.claude/CLAUDE.md 와 subagent-slots 훅으로 이미 구현됨. 메모리는 사용자 의도의 근거 기록 | HOOK-MESSAGES 또는 decisions 에 근거 한 단락, 메모리는 삭제 제안 |
| `second-opinion-policy.md` | 저장소로 | CLAUDE.md 코드 리뷰 절에 반영됨(중복) | 삭제 제안 |
| `home-claude-sync.md` | 낡음 | `/code/.claude/CLAUDE.md` 의 'home 정본' 절과 같은 내용(중복) | 삭제 제안 |
| `live-sessions-caution.md` | 낡음 | 전역 CLAUDE.md 에 '실행 중 세션' 지침이 있고, 본문은 2026-11-10 시점 스냅샷 | 삭제 제안 |

## 옮기는 순서(제안)
1. `저장소로` 항목을 CLAUDE.md, `.claude/rules/`, docs 중 맞는 곳에 쓴다(메모리 원문을 복사하지 말고 지금 사실로 확인해서 쓴다).
2. 옮긴 뒤 해당 메모리 파일과 MEMORY.md 줄을 정리한다(삭제는 사용자가 승인한 것만).
3. `pack으로` 는 luau-kb 담당 세션에 전달한다.
4. `낡음` 은 사용자에게 지울지 묻는다.
