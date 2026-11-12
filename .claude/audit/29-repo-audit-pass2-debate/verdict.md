# 판결: claude-doctor 2패스 (중재자: 메인, 2026-11-11)

토론 기록은 r1-P, r1-Q, r2-P, r2-Q 에 있다. 1패스 측정은 .claude/audit/28 에 있다. 이 판결은 사용자가 확정하기 전까지 안이다.

## 합의된 것 (그대로 채택)
- **베이스라인 훅.**
  - qwreey-conventions 안에 별도 모듈 `hooks/loadcost.py` 로 둔다. 기존 프로세스가 불러 쓴다.
  - 이번 세션에 실린 집합은 공식 `InstructionsLoaded` 기록으로 판단한다. 기록이 없으면 위치 규칙으로 판단하고 `loads where installed` 라고 쓴다.
  - 문구는 실린 경로에 따라 정한다. 상시 문서에는 `every session and every subagent except Explore/Plan` 을 적는다.
  - 토큰은 추정식 `1.72 x Hangul + 0.376 x other` 로 계산한다(+-8%). 상수는 한 곳에 두고 테스트로 고정한다.
  - 소음: 파일마다 세션의 첫 편집에서 낸다. 다시 내는 것은 문턱을 위로 넘을 때와 +0.5k 늘었을 때뿐이다. 3회 뒤에는 축약한다.
  - 추가한 줄에 없는 경로가 있으면 덧붙인다. 기존 줄의 죽은 경로는 Stop 사용자 줄의 범주로 넣는다.
- **역방향 stale 검사.**
  - 모델 알림: `if` 핸들러 `Bash(mv|git mv|rm|git rm *)` 에서 낸다.
  - 놓친 이동(스크립트, home-sync, 브랜치 전환): Stop 에서 다시 stat 해서 사용자 줄 범주로 보인다.
  - 알리지 않는 것: 처음부터 없던 경로, glob, `<...>`, URL, audit·drafts·handoff 쪽 참조.
- **.claude/audit/.**
  - 옮기지 않는다.
  - `audit/INDEX.md` 를 생성한다. 한 줄에 번호, 상태(live, superseded by N, history), 결론이 지금 있는 곳을 적는다.
  - frontmatter 는 미룬다. coderag project 계층에 audit 를 그대로 색인해 과거 질문 3개로 시험한 뒤 정한다.
- **drafts.**
  - 끝난 초안에는 첫 줄 `status: landed in <path>; not maintained` 를 단다.
  - `.claude/conventions.json` 에서 drafts 를 exclude 한다.
  - `git mv` 는 사용자 승인 뒤에 한다.
- **PLAN, README, HUMAN_TODO.** 그대로 두고 낡은 문장만 고친다. TODO.md 는 만들지 않는다.
- **advisor 비용 고지.** advisor 가 돈 턴의 Stop 에서 한 줄을 낸다. 출처는 transcript usage(`subagent_ledger.scan`)다. 문구 `이번 턴 advisor 2회: $0.81, 5분 40초 (sonnet, 입력 96k 토큰)`.
- **설치 어긋남 고지.**
  - claude-doctor 에서만, SessionStart systemMessage 로 낸다.
  - `home-sync status` 결과의 해시가 바뀌면 내고, 그대로면 하루 한 번 낸다.
  - 근거:
    - 사용자가 두 번 몰랐다.
    - 지금 설치된 CLAUDE.md 36~37행이 없어진 `second-opinion:audit`/`context` 를 매 세션 부르라고 지시하고 있다(메인 확인).
- **오래 방치된 작업.**
  - q 플러그인에 둔다.
  - 출처: Stop·SubagentStop 의 `background_tasks`.
  - 진척 신호: 출력 크기와 mtime, CPU, transcript mtime.
  - 판정:
    - 멈춤: 진척 없이 15~20분, 나이 30분 이상. 모델 warn 과 사용자 줄을 낸다.
    - 오래 실행: 진척이 있고 2시간 이상. info 로 1회 낸다.
  - monitor 는 뺀다.
  - 전달: 모델은 UserPromptSubmit, 사용자는 Stop systemMessage.
  - dedupe 는 (세션, task id, 상태)마다 1회다.
  - 문구는 "멈췄거나 대기 중" 으로 확정하지 않는 질문형으로 쓴다.
  - 보지 못하는 것은 r2 두 쪽 목록과 같다.

## 갈린 것과 판결
- **(a) 예산.** 두 토론자가 2라운드에서 서로의 안으로 넘어갔다. P 는 8k/3k 를, Q 는 5k/2.5k 를 받았다. 판결은 **Q 의 최종안(합계 5k, 파일 2.5k, 조건부 rule 2.5k, 스킬 본문 5k)** 이다.
  - P 가 양보한 이유는 "5k 이면 apply 직후부터 늘 켜진다" 였다. 사용자 줄을 이번 세션의 편집이 넘겼을 때만 내면(edge) 해결된다.
  - 모델 알림은 CLAUDE.md 를 편집할 때마다 "넘음" 을 보인다. 이것은 의도된 압력이다. 줄일 수 있는 것이 그 파일(3.4k)뿐이기 때문이다.
  - 서브에이전트 배수(공식) 때문에 느슨한 8k 는 맞지 않다.
  - 스킬 본문 5k 는 공식의 압축 뒤 재주입 한계라는 기능 근거가 있다. 2.5k 는 근거가 없다.
  - `.claude/conventions.json` 의 `load_budget` 로 저장소마다 바꿀 수 있다.
- **(b) 큰 파일 읽기.** 실시간 고지는 하지 않는다. Q 의 실측이 근거다: 2만 이상 66건이 전부 서브에이전트였고 대부분 시킨 읽기였다.
  - 누적 상위는 비용 기록과 doctor 에 남긴다.
  - 메인 한 파일 누적이 2만을 넘으면 Stop 사용자 줄 범주로 넣는다.
  - P 의 `allow_large` 지적(한 번에 통째로 읽을 수 있다)은 사실이다. 그래서 집계는 Read 횟수가 아니라 누적으로 센다.
- **(d) 프로젝트 CLAUDE.md.** 0.6k 이하, 영어, 포인터만 둔다. 담을 것:
  - INDEX, PLAN, HUMAN_TODO 의 위치
  - "이력 문서는 INDEX 와 해당 절만 읽는다"
  - drafts status 규칙

  이 파일은 이 저장소 모든 세션의 상시 비용이므로 사용자가 정한다.

## 순서 (각 단계 커밋 하나, 되돌릴 수 있음)
0. 실측($0~0.03):
   - 50커밋 재생에 load 범주를 얹어 알림 수를 센다.
   - 셸 지속 시간 분포
   - Stop 의 `background_tasks` 와 Bash tool_response 필드
   - fork agent_type
   - 세션당 서브에이전트 수
   - systemMessage UI
   - home-sync status 시간
   - home CLAUDE.md 영어판 크기
1. 낡은 문장(PLAN §0·P1, HUMAN_TODO, README, D-10), `conventions.json`(drafts exclude, load_budget), 초안 status 줄
2. `audit/INDEX.md` 생성 스크립트와 결과
3. 추정식 두 벌, 테스트, doctor 토큰 열
4. load 범주, InstructionsLoaded 기록
5. 역방향
6. 오래 방치된 작업(q)
7. advisor 비용 줄
8. 설치 어긋남 SessionStart 줄
9. 프로젝트 CLAUDE.md(사용자 확정 뒤)

## 사용자에게 제안만 할 것
- home CLAUDE.md 의 두 절("코드 리뷰와 second opinion" ~0.9k, "모델 사용과 서브에이전트 비용" ~0.7k)을 rules 나 스킬로 옮기기
- 영어판 전환(0단계 실측 뒤)
- reviewer `omitClaudeMd`(약 3.4k/회. 단 reviewer 가 사용자 규칙을 필요로 하는지 먼저 확인)
- 초안 3개 `git mv`
- PLAN 나누기
- conventions-check.py(883줄)와 scan.py(1,203줄) 분리
- harness-doctor 이름
- 메모리 인덱스 줄이기
