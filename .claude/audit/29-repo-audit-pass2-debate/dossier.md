# 2패스 토론 자료: claude-doctor 저장소 개선과 "자동으로 실리는 문서" 베이스라인 훅 (2026-11-11)

## 읽을 것
- 1패스 결과(측정과 목록): `/code/Projects/claude-doctor/audit/28-repo-audit-pass1.md`. 판단의 근거는 이 문서의 숫자다.
- 저장소: `/code/Projects/claude-doctor`. README.md, PLAN.md, HUMAN_TODO.md, `home/`(사용자 레벨 정본), `plugins/`(q, qwreey-advisor, qwreey-conventions), `audit/`, `handoff/`, `decisions/`, `drafts/`, `intake/`, `tools/`
- 컨벤션 스킬과 훅: `plugins/qwreey-conventions/skills/agent-docs/SKILL.md`, `hooks/conventions-check.py`. 앞선 토론과 판결은 `.claude/audit/26-doc-hygiene-debate/verdict.md`, `r3-verdict.md`.
- 공식: code.claude.com/docs 의 memory(CLAUDE.md 권장, @import, rules), skills, costs(로컬 사본 `/tmp/ccdocs/*.md`).

## 사용자 의도 (원문 취지)
- CLAUDE.md, PLAN.md, TODO.md, `.claude/**/*.md` 같은 문서가 길어지는 문제가 있다. "이 길이면 매번 이만큼의 토큰을 쓴다" 를 알 수 있어야 한다. 나중에는 coderag 연계도 컨벤션에 들어갈 수 있다.
- 이 저장소가 복잡해져서 그런 것의 시험대가 된다. 여기서 찾은 개선 방법은 다른 저장소에도 적용될 수 있다. 전체 감사는 한 번도 하지 않았다.
- 스킬만으로는 부족하고 훅이 필요하다: "CLAUDE.md 에 include 로 실리는 것들을 편집할 때 stale 을 조심하도록 리마인드하거나, PostToolUse 로 안내할 수 있는 베이스라인이 필요하다."

## 메인이 쓴 베이스라인 훅 초안 (토론 대상)
1. 자동으로 실리는 문서를 고친 직후(PostToolUse) 한 줄을 낸다.
   - 대상: 모든 단계의 CLAUDE.md 와 @import 대상, paths 없는 rules(항상), paths 있는 rules(조건부), MEMORY.md, SKILL.md description
   - 예: `CLAUDE.md loads into every session: ~1.9k tokens (+120 this edit), 14% of the always-loaded ~13k. Check that lines naming files, commands, counts or versions are still true. Long knowledge belongs in references or coderag.`
   - 같은 편집에서 문서가 가리키는 경로 중 실제로 없는 것이 있으면 덧붙인다.
2. 반대 방향: 자동으로 실리는 문서에 적힌 경로를 색인해 두고, 그 파일이 옮겨지거나 지워지거나 이름이 바뀌면 알린다. 예: "CLAUDE.md L12 still names this path". 일반 편집에서는 알리지 않는다.
3. 크기 문턱은 1패스 측정값으로 정한다. 넘으면 같은 한 줄에 나눌 후보를 붙인다.
- 스킬(`qwreey-conventions:agent-docs`)에는 짧지만 강한 정리본을 둔다. 공식 권장 방향, 매번 실을 것과 필요할 때 읽을 것, coderag 로 옮기는 기준. 훅은 그 스킬을 가리킨다.

## 하네스 원칙 (지킬 것)
- 알림만 하고 막지 않는다. 일괄 정리는 사용자 신호가 있을 때만 한다. 저장소 규칙이 전역에 우선한다. 사용자 선택은 제안만 한다.
- 지우지 말고 보관한다(git 이력이 있어도 audit 등은 사용자 판단).
- 모델 사이의 텍스트는 영어로, 사용자에게 보이는 것은 한국어로 한다.
- 검토 기능은 모델이 스스로 부르는 도구로 만들고, 사용자 호출용 명령은 늘리지 않는다.
- 비용은 고지하고 줄 세우되 강제하지 않는다.

## 추가 쟁점: 훅이 사용자에게 직접 보이는 짧은 고지 (사용자 추가 요청)
- 확인된 사실: `systemMessage` 는 사용자에게 보이고 모델 맥락에는 들어가지 않는다(모델 비용 0). qwreey-conventions 의 Stop 훅이 이미 이 방식을 쓴다: "손댄 파일에 기존 주석 문제가 남아 있음: …". 대화형 UI 에서 어떻게 그려지는지는 아직 보지 못했다.
- 사용자 원문 취지: 사용자가 알아야 할 것은 짧게 고지하는 것이 좋고, 후보 조사도 넣어도 된다.
  - 예 1: advisor(qwreey-advisor)가 한 번 돌 때 쓴 예산과 걸린 시간. 이것을 알면 정량적으로 평가할 수 있다.
  - 예 2: 실리는 md 들의 복잡성. 모델이 비효율적으로 일하면 사용자도 나서서 개선해야 하므로 사용자도 고민해야 할 측면이다.
- 토론할 것:
  - 후보 목록
  - 사용자에게 보일 것과 모델에게 보일 것의 구분
  - 빈도와 소음 상한
  - 데이터 출처: SubagentStop 의 `agent_transcript_path` usage, statusline 의 `rate_limits`·`cost`, ledger 등
  - 문구 형식(한국어, 한 줄)

## 추가 쟁점 2 (2라운드에서 다룸): 오래 방치된 백그라운드 작업
- 사용자 원문 취지: 몇 시간째 방치된 shell task 나 멈춘 subagent 가 있어도 사용자가 말하지 않으면 모델이 모른 채 계속 둔다. 사용자가 "의도한 거 맞니?" 하고 물으면 의도하지 않은 경우도 있어서 끈다. 하네스는 따로 알리지 않는다.
- 실제 사례: 이 세션의 셸 하나가 2시간 48분 동안 멈춰 있었다. 원인은 `plugins/q/tests/fake_claude.py` 가 `tests/*.py` 일괄 실행에 섞여 stdin 을 기다린 것이다. 727a234 에서 고쳤다.
- 메인 초안:
  - 모델에게: UserPromptSubmit 에서 한 줄을 넣는다.
  - 사용자에게: Stop 에서 systemMessage 로 알린다.
  - 찾는 법: 세션 claude 프로세스의 자식 중 실행 시간이 문턱을 넘은 것, 그리고 출력 파일이 오래 갱신되지 않은 것을 찾는다. 서브에이전트는 transcript 의 mtime 으로 본다.
  - 같은 작업은 한 번만 알린다.
