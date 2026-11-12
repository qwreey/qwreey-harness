# Q 1라운드: 최소 변경, 작업 흐름 보존 (opus, 2026-11-11)

메인이 받은 보고를 옮긴 것이다(줄바꿈만 정리). 숫자는 .claude/audit/28 에서 왔다. [추론] 은 추론이라는 표시다.

## 1. 11개 질문
1. **고정 비용.**
   - apply 뒤 약 5.06k 이고, 그중 CLAUDE.md 가 3.4k(67%)다. 실제로 줄일 수 있는 것은 이 파일 하나뿐이다.
   - 같은 추정식으로 절별 추정을 내 보면 3,580 이다(실측 대비 +5.6%). 큰 절은 둘이다: "코드 리뷰와 second opinion" ~875, "모델 사용과 서브에이전트 비용" ~673.
   - 예산은 파일당 3k, 합계 8k 로 둔다. 8k 는 scan.py `TOTAL_BYTES_WARN` 20KB 를 0.47 tok/B 로 환산한 값이다.
   - 두 절을 rules 나 스킬로 옮기는 안은 사용자에게 제안만 한다. 영어로 바꾸는 것도 사용자 선택이다. 영어판을 한 번 재 보면($0.03) 판단할 수 있다.
2. **크기를 보이게 하는 법.**
   - 모델에게는 훅으로 보인다.
   - `/q:doctor` 의 `check_load` 표에는 토큰 열만 더한다.
   - statusline 과 커밋 점검에는 넣지 않는다.
   - 계산은 추정식으로 한다. API 키가 없고, 예산 판단에는 ±8% 로 충분하다.
3. **.claude/audit/.**
   - 자동으로 실리지 않으므로 세션 비용은 0 이다.
   - 공식 Read 는 한 번에 최대 25k 토큰을 돌려준다(tools-reference "Large files"). 그래서 "7만 토큰을 통째로" 읽는 일은 Read 한 번으로는 일어나지 않는다.
   - 옮기지도 보관하지도 않는다. 색인 `audit/README.md` 는 선택안으로 두고 사용자가 정한다.
4. **끝난 초안.**
   - 옮기지도 지우지도 않는다. 첫 줄에 `status: landed in <path>; not maintained` 를 단다.
   - 삭제 후보는 HUMAN_TODO 에 근거와 함께 올린다.
   - README 에 "이관하는 커밋에서 status 줄을 단다" 는 한 줄을 넣는다.
5. **PLAN/README/HUMAN_TODO.**
   - 셋 다 그대로 두고, 낡은 진술만 고친다: PLAN §0·P1, HUMAN_TODO 대기 목록, README 의 겹친 구절.
   - TODO.md 는 만들지 않는다. 없는 TODO.md 를 읽으라는 지시는 그때그때 쓴 프롬프트에서 나왔다. scan.py 안의 `TODO.md` 는 다른 저장소를 점검하는 코드라 정상이다.
   - HUMAN_TODO 와 handoff 의 중복은 그 줄을 고칠 때 줄인다.
6. **중복 정본.** 표본 9개에 대해 "어느 문서가 정본인가" 지도를 이 판결문에 적는다. 다른 문서는 고칠 때 그 정본을 가리키게 한다. 메모리에서 저장소로 옮긴 것은 의도한 것이다.
7. **설치 어긋남.** `home-sync.sh status` 가 이미 잡는다. doctor 에 같은 검사를 넣지 않는다. 사용자가 0005 를 apply 하고, HUMAN_TODO 를 사실대로 고친다.
8. **낡은 이름.**
   - 일부러 남긴 이름은 README 40행에 설명이 있다.
   - harness-doctor 를 함께 쓴 것은 이름 선택이므로 제안만 한다.
   - doctor 에 낡은 이름 검사를 넣지 않는다.
9. **위생.**
   - node_modules 는 처리됐다.
   - 히스토리는 다시 쓰지 않는다.
   - 빈 `home/.claude/skills/` 는 git 에 보이지 않으니 둔다.
10. **자기 위반.**
    - 라이브 오탐 2건은 패턴을 바꾸지 않고 의도된 예외로 둔다.
    - references 17건은 손댈 때 Stop 줄이 알린다.
    - 초안 41건은 `.claude/conventions.json` 의 `exclude: [".claude/research/drafts/**",".claude/audit/drafts/**"]` 로 끈다.
    - 코드 주석 범주는 재생으로 측정한다.
    - 큰 파일은 지금 나누지 않는다. 새 기능은 별도 모듈로 둔다.
11. **coderag.**
    - 지금은 frontmatter 규칙을 만들지 않는다.
    - project 계층에 audit/ 를 있는 그대로 색인하고, 과거 질문 3개로 찾히는지 시험한다.

## 2. 베이스라인 훅
qwreey-conventions 안에 별도 모듈 `hooks/loadcost.py` 를 두고 conventions-check 가 불러 쓴다. 프로세스는 늘지 않는다.

**범위와 표현**
- 이번 세션에 실제로 실린 집합을 기준으로 삼는다.
  - 공식 `InstructionsLoaded`(비동기, `load_reason`·`globs`·`parent_file_path`)를 받는 작은 훅이 상태 파일에 기록한다.
  - @import 를 따로 구현하지 않는다.
- 기록에 없는 문서는 위치 규칙으로 판단한다. 이때는 "loads where installed" 라고 쓴다. 정본 `home/.claude/CLAUDE.md` 는 이 세션에 실리지 않으므로 "every session" 이라고 쓰면 틀린다.
- 문구는 실린 경로에 따라 다르다.
  - session_start, include: `loads into every session`
  - path_glob_match: `loads when files matching <globs> are read`
- MEMORY.md 는 토큰 줄만 낸다(크기 경고는 공식이 이미 낸다).
- SKILL.md 는 description 이 바뀐 편집에서만, 1,536자 상한 대비 사용량을 낸다. 본문 편집에는 내지 않는다.

**문턱**
- 파일 3k, 합계 8k. 저장소마다 `.claude/conventions.json` 의 `load_budget` 로 바꿀 수 있다.
- 넘으면 가장 큰 H2 절 2개를 후보로 붙인다.

**문구**
```
<harness-hook name="qwreey-conventions" level="info">CLAUDE.md loads into every session: ~3.4k tokens (+0.1k this edit; always-loaded docs ~5.1k). Lines that name files, commands, counts or versions must still be true. Knowledge needed only sometimes belongs in a reference, a paths-scoped rule or coderag; see qwreey-conventions:agent-docs.</harness-hook>
```
- 넘을 때 덧붙인다: ` Over the 3k per-file budget; split candidates: "코드 리뷰와 second opinion" ~0.9k, "모델 사용과 서브에이전트 비용" ~0.7k.`
- 추가한 줄이 없는 경로를 가리키면 덧붙인다: ` Named paths that do not exist: L12 `tools/run_opt.sh`.`
- 경로는 문서 디렉터리, 상위 디렉터리, 홈 순서로 찾는다. glob, `<...>`, `$VAR`, URL 은 건너뛴다.
- 기존 줄의 죽은 경로는 모델에게 내지 않는다. Stop 사용자 줄에 범주 "없는 경로 N" 으로 더한다.

**역방향**
- `if` 핸들러 4개에서만 실행한다: `Bash(mv *)`, `Bash(git mv *)`, `Bash(rm *)`, `Bash(git rm *)`.
- 색인: 이번 세션에 실린 문서가 가리키는 경로 중 색인 시점에 존재한 것.
- 문구:
  ```
  CLAUDE.md L12 still names `tools/x.sh`, which this command removed or moved. Update that line in the same change.
  ```
- 4개 이상이면 묶어서 한 번만 낸다.
- 알리지 않는 경우: 일반 편집, 그 밖의 Bash, 처음부터 없던 경로, audit·drafts·handoff 쪽 참조, 이미 알린 경로, 브랜치 전환.

**토큰 계산**
- 추정식을 쓴다. 한글은 AC00-D7A3, 1100-11FF, 3130-318F 를 센다. 0.1k 단위로 반올림한다.
- 증감은 Edit 이면 old 와 new, Write 이면 originalFile 로 구한다.
- 상수는 한 곳에 둔다. q 플러그인과는 import 를 공유할 수 없으므로 함수를 두 벌 두고, 같은 값인지 테스트로 고정한다.

**소음 예산**
- 파일마다 세션의 첫 편집에만 낸다.
- 다시 내는 경우는 둘뿐이다: 문턱을 넘을 때, 그리고 마지막 알림보다 +0.5k 늘었을 때. 줄어든 경우는 내지 않는다.
- 처음 3회는 전문(약 90토큰)이고, 그 뒤는 약 25토큰으로 줄인다: `CLAUDE.md ~3.5k tokens (+0.1k).`
- 50커밋 재생으로 확정한다.

## 3. 사용자 고지 (systemMessage), 순위순
1. **advisor 비용**
   - 출처: SubagentStop 의 `agent_transcript_path` 를 `subagent_ledger.scan` 으로 읽는다. message.id 마다 한 번 세며, `-p` 의 total_cost_usd 와 일치하는 것을 확인했다. 시간은 원장의 Start 부터 Stop 까지다.
   - 언제: advisor 가 돈 턴에만, Stop 에서 한 줄로 묶는다.
   - 문구: `이번 턴 advisor 2회: $0.81, 5분 40초 (sonnet, 입력 96k 토큰)`
   - 이유: 모델이 스스로 부르므로 사용자는 시작을 보지 못한다.
   - 미확인: fork 의 `agent_type` 값.
2. **죽은 경로**
   - 기존 Stop 줄에 범주로 더한다.
3. **상시 로드 예산 초과**
   - 언제: 합계가 8k 를 넘을 때만.
   - 문구: `상시 로드 문서가 예산을 넘음: 약 8.4k 토큰(예산 8k), 가장 큰 것 CLAUDE.md 3.4k. 정리는 요청하실 때만.`

버린 것:
- 매 세션 로드 요약: 잔소리가 된다.
- 설치 어긋남: home-sync 가 맡는다.
- 턴 비용: statusline 의 cost 와 겹친다.
- resume 비용.
- 복잡도를 늘 보이는 것: statusline 토글 제안으로 돌린다(quietcode-claude).

## 4. 최소 변경 (각 단계 커밋 하나, 되돌릴 수 있음)
1. 낡은 진술 고치기: PLAN §0·P1, HUMAN_TODO, README, D-10 의 `run_opt.sh`
2. `.claude/conventions.json` 에 drafts exclude
3. 추정식 함수(두 벌), 테스트, doctor 토큰 열
4. `loadcost.py`, InstructionsLoaded 기록 훅, Stop 줄에 "없는 경로" 범주
5. 역방향 `if` 핸들러 4개
6. qwreey-advisor Stop 비용 줄
7. 초안 status 줄, HUMAN_TODO 에 삭제 후보 제안
8. 정본 지도와 CLAUDE.md 두 절 이동안은 판결문에 제안으로만 적는다

## 5. 다른 저장소로 옮겨 가는 것
- 플러그인(설치하면 따라온다): 훅 3종, 추정식, 기본 예산, `exclude`·`load_budget`, doctor 토큰 열.
- agent-docs 스킬에 넣을 짧은 정리본:
  - 공식 200줄 권장
  - @import 는 비용을 줄이지 않는다
  - paths rules
  - "매번 실을 것은 매 턴 행동을 바꾸는 것뿐"
  - coderag 로 보낼 기준
- 이 저장소에만 해당: drafts 와 audit 처리, PLAN 문구, MANIFEST, 낡은 이름.
- 동료 배포: `CONVENTIONS_CHECK=off`, 한국어 한 줄, 보수적인 기본값(설치본 2.8k < 3k).

## 6. 실패 지점과 P 공격
**Q 안의 실패 지점**
- 추정식이 최대 ±12% 까지 흔들린다.
- 역방향 검사는 스크립트나 home-sync 가 옮긴 경우와 브랜치 전환을 놓친다.
- InstructionsLoaded 가 비동기라 경합이 생길 수 있다.
- audit 이 Grep 과 coderag 결과 위쪽에 섞이는 비용이 남는다(측정하지 않음).
- CLAUDE.md 는 사용자가 제안을 받아들일 때까지 3.4k 를 계속 쓴다.

**P 를 가장 강하게 세우면**
- 330파일 중 audit 와 drafts 가 65% 다. 한 번에 재구성하면 이후 비용이 영구히 준다.

**반박**
- 세션 비용에서 줄일 수 있는 것은 CLAUDE.md 뿐이다.
- 옮기면 깨지는 것이 많다: 이력 속 백틱 경로(이미 67건이 깨져 있다), 번호 인용 8곳, handoff 와 형제 세션의 참조. 역방향 훅이 대량 알림을 낸다.
- 사용자 신호 없는 일괄 정리와 사용자 문서 번역은 원칙에 어긋난다.

**P 에게서 받아들이는 것**: CLAUDE.md 줄이기(두 절, 약 1.5k), 초안 종료 표시, .gitignore.
