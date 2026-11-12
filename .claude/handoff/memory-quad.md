# quad 세션에게: 메모리 분류 인계 (읽기 전용 감사)

claude-doctor 의 `audit/23-memory-portability.md` §6 에서 나왔다. `/code/.claude/projects/-code-Projects-quad/memory/` 의 항목을 읽기만 했고 아무것도 고치거나 옮기지 않았다.
저장소 밖(`~/.claude`)에 있는 메모리는 다른 clone, 다른 기기, 동료에게 가지 않는다. 아래 `저장소로`·`pack으로` 항목은 그쪽으로 옮기자는 제안이고, 반영 여부와 문구는 이 저장소 세션과 사용자가 정한다.

요약: 유지 10, 저장소로 8, pack으로 2, 낡음 1 (총 21). 분류는 자동 신호(`lib/memory_signals.py`)가 아니라 원문을 읽고 사람이 판단했다.

| 메모리 파일 | 분류 | 이유 | 제안 |
|---|---|---|---|
| `feedback-decision-presentation-style.md` | 유지 | 사용자 읽기 방식(개인 성향). devplorer 에도 같은 항목이 있다 | 전역 CLAUDE.md 후보(중복 제거) |
| `feedback-git-trailer-hook.md` | 유지 | sandbox git 훅 동작(환경) | - |
| `feedback-pgrep-self-match.md` | 유지 | Bash 도구 동작에 관한 환경 함정 | - |
| `feedback-never-stop-background-tasks-unasked.md` | 유지 | 사용자 선호(TaskStop 은 묻고) | 전역 CLAUDE.md 후보 |
| `feedback-background-agent-completion-signal.md` | 유지 | 하네스 동작 지식. quad 한정이 아니다 | 전역 CLAUDE.md 후보 |
| `feedback-subagent-tab-messages.md` | 유지 | 하네스·사용자 습관 | - |
| `feedback-token-efficiency-2026-10-21.md` | 유지 | 사용자의 비용 선호. 날짜 기준이라 갱신 필요 | - |
| `user-timezone-and-overnight-runs.md` | 유지 | KST 는 유지. 2026-08 밤샘 허용 범위는 일회성이라 낡음 | 밤샘 부분만 정리 제안 |
| `reference-codex-delegation.md` | 유지 | codex 는 이 sandbox 의 환경. 버전 경로는 낡기 쉬움 | `mise which codex` 로 바꾸는 한 줄 제안 |
| `reference-quad-scratch-refs.md` | 유지 | 레포 밖 스크래치 자리(이 sandbox 전용) | - |
| `git-remote-push-policy.md` | 저장소로 | quad 의 원격 3개와 push 규칙은 이 레포를 여는 누구에게나 필요하다. 메모리만 있으면 다른 clone 에 없다 | quad CLAUDE.md 나 SAFETY.md 에 원격 표 추가 |
| `project-quad-docs-site-tooling.md` | 저장소로 | docs/site 의 dev 서버·build 순서·npm ci 게이트는 순수 저장소 규약이다 | docs/site/CLAUDE.md 또는 `.claude/rules/docs-site.md`(paths: docs/site/**) |
| `project-devplorer-devui-consumer.md` | 저장소로 | devui 소비자와 가져올 부품 계획. ROADMAP.md 백로그가 정본이라고 적혀 있다 | ROADMAP.md 백로그에 흡수 |
| `feedback-session-operating-constraints.md` | 저장소로 | git stash 금지·devui 테스트 게이트는 저장소 규약. ulimit·choom 은 환경이라 메모리에 남겨도 된다 | `.claude/conventions.md` 에 병합 |
| `feedback-model-choice-for-reflection.md` | 저장소로 | base/ 반영 때 모델 하한은 이 레포 작업 규약. 일부(2026-09-28 모델 변경)는 낡음 | `.claude/conventions.md` |
| `feedback-agy-cross-family-review.md` | 저장소로 | 프로젝트 skill `delegate-agy` 와 `.claude/tools/agy-delegate.sh` 가 이미 있다. 쓰는 시점 판단은 그쪽에 합친다 | delegate-agy SKILL.md 에 병합 |
| `feedback-quad-collaboration-style.md` | 저장소로 | 12.6KB 혼합: 사용자와 상의하는 방식은 메모리, 문서 코퍼스 재편 규약과 생명주기·GC 일반화 금지는 저장소 지식 | 상의 방식만 남기고 나머지를 `.claude/conventions.md`/base 로 분리 |
| `reference-quad-safety-constraints.md` | 저장소로 | SAFETY.md 두 제약은 이미 저장소에 있어 중복. Studio MCP 가 샌드박스라는 환경 사실만 메모리에 남긴다 | 중복 부분 삭제 제안 |
| `feedback-roblox-image-asset-id.md` | pack으로 | 데칼 id 와 이미지 id 구분은 Roblox 일반 함정 | luau-kb 스킬/스니펫 |
| `reference-studio-mcp-input.md` | pack으로 | Studio MCP 입력·싱크 요령은 Roblox 툴킷 일반 지식(좌표 인셋 58 등). 환경 부분(포트, studio-sync)은 유지 | luau-kb 에 Studio MCP 절 |
| `project-quad-v2-rewrite.md` | 낡음 | 스스로 'CLAUDE.md 가 정본, 여기서 중복하지 않는다' 고 쓴 포인터. 2026-08-11 이후 갱신 없음 | 삭제 제안(MEMORY.md 줄 포함) |

## 옮기는 순서(제안)
1. `저장소로` 항목을 CLAUDE.md, `.claude/rules/`, docs 중 맞는 곳에 쓴다(메모리 원문을 복사하지 말고 지금 사실로 확인해서 쓴다).
2. 옮긴 뒤 해당 메모리 파일과 MEMORY.md 줄을 정리한다(삭제는 사용자가 승인한 것만).
3. `pack으로` 는 luau-kb 담당 세션에 전달한다.
4. `낡음` 은 사용자에게 지울지 묻는다.
