# 10 — 하네스 사용 흔적 채굴: 반복 지시, 정정, 작업 흐름, memory 감사

2026-11-10 작성. 원천은 모두 읽기 전용으로 다뤘다.

## 범위와 방법

- **history.jsonl**: 2,294줄, 기간은 2026-08-18 ~ 11-10.
  - 슬래시 명령만 있는 줄을 빼면 1,819개, 연속 중복을 빼면 1,759개다.
  - 근거 표기 `hL326`은 history.jsonl의 326번째 줄을 뜻한다.
- **세션 트랜스크립트**: `projects/*/` 아래 메인 27개, subagents 1,186개, 약 3.7GB.
  - 사용자 텍스트, tool_result의 거부·차단 문자열, tool_use 이름과 입력만 스크립트로 뽑았다.
  - quad의 오래된 세션은 트랜스크립트가 남아 있지 않다. 프롬프트 빈도는 history 기준으로, 이벤트 빈도는 트랜스크립트 기준으로 셌다.
- **auto memory**: 7개 프로젝트, 59개 파일.
- **판단 기록 파일**: 각 저장소의 `question.md`, `todos.md`, `HUMAN_TODO.md`.
- **빈도 표기**: "n / 세션 / 프로젝트" 순서다.
  - 키워드 정규식으로 셌기 때문에 근사치다. 설계 토론 속에 같은 단어가 섞인 경우도 들어 있다.
- **제외한 것**: `/tmp/*` 테스트 프로젝트(claude-doctor 실측용)와 이 세션 자신의 출력.

## 0. 상위 패턴 요약

| # | 패턴 | 규모 | 판정 | 우선 |
|---|---|---|---|---|
| A | 사용자가 컨텍스트 %를 직접 알려 주고 "compact 인자 써 줘"를 요청한다. 체크포인트, 핸드오버 점검, compact가 의식처럼 묶여 있다 | compact 64 / 9 / 4, %보고 27, `/compact` 58회 | **스킬** `/checkpoint`(compact 준비) + **훅**(컨텍스트 % 주입) + CLAUDE.md 1줄 | P1 |
| B | 예산, 모델, 병렬도를 매번 손으로 지시한다. 서브에이전트 폭주 사고($589)와 그 뒤의 정정이 있었다 | 모델·예산 지시 60+ / 6프로젝트, memory 9개 파일 | **사용자 CLAUDE.md**에 "효율 모드 기본값"을 둔다. 지금 정본의 "리뷰를 먼저 한다"와 충돌하므로 조정이 필요하다 | P1 |
| C | 한국어로 말해 달라는 정정이 반복된다. 서브에이전트 보고 직후에 영어가 새는 일이 많다 | 프롬프트 10 / 6 / 3, memory 2곳, 프로젝트 문서 6/7곳에 이미 있음 | **사용자 CLAUDE.md** + **훅**(PostToolUse Agent 리마인더) | P1 |
| D | 다른 저장소를 "보고 와"서 지식을 가져온다. Luau 타입 한계, agy 위임법, Studio·MCP 사용법, 툴링이 대상이다 | 52 / 15 / 7, 다른 저장소 이름 언급 약 100회 | **luau-kb 스킬**과 **/delegate**가 받는다. 상위·하위 프로젝트 피드백은 **새 스킬** | P1 |
| E | 리뷰를 "소진될 때까지" 돌리고, 외부자 시선이나 다른 모델 계열로 교차 검토한다 | 리뷰 48 / 12 / 7, 소진·수렴 44 / 13 / 8, 외부자 35 / 7 / 4 | 이미 `/audit`·`/debate`·`/delegate`가 있다. **빠진 것은 소진 종료 규칙과 가벼운 의견 청취** | P2 |
| F | 결정은 산문으로 받고 싶어 하며 몰아서 묻기를 원한다. "권고대로"로 답하는 경우가 많다 | "권고대로" 74, 몰아 묻기·인터랙티브 30 / 9 / 6, memory 4곳 | **사용자 CLAUDE.md** | P1 |
| G | Bash 위생 문제가 반복된다. `rm -rf $VAR`가 내장 검사에 막히고, `pgrep -f`가 자기 자신에 걸리고, Bash로 파일을 고친다 | 안전 검사 차단 22, `rm -rf $VAR` 468회, sed -i·python 쓰기 약 10.3k (Edit은 1.0k) | **사용자 rules/CLAUDE.md** + 기존 bash-bypass 훅 유지 | P2 |

---

## 1. 데이터 개요

### 프로젝트별 분포 (history)

| 프로젝트 | 프롬프트 | 세션 |
|---|---|---|
| quad | 1,462 | 36 |
| stl-luau | 272 | 3 |
| table-sim | 236 | 2 |
| devplorer | 188 | 4 |
| VideoSync | 40 | 3 |
| mrow | 34 | 1 |
| tbox | 17 | 1 |
| claude-doctor | 14 | 1 |
| quad-changelog-check | 10 | 1 |
| 기타 | 21 | — |

- 세션 하나가 매우 길다. stl-luau는 세션 3개에 272프롬프트다. quad 세션 하나는 디렉터리가 1.2GB다.
- 사용자는 세션을 길게 끌고 가면서 compact를 손으로 관리한다(→ 패턴 A).

### 많이 쓴 슬래시 명령 (history)

| 명령 | 횟수 |
|---|---|
| `/usage` | 142 |
| `/status` | 97 |
| `/compact` | 58 |
| `/tasks` | 40 |
| `/context` | 38 |
| `/model` | 27 |
| `/clear` | 16 |
| `/btw` | 7 |
| `/advisor` | 5 |
| `/code-review` (직접 입력) | 2 |

- 한도와 상태를 확인하는 명령(`/usage`, `/status`, `/context`, `/tasks`)이 317회다. 예산과 컨텍스트에 대한 불안이 그만큼 크다는 신호다.

---

## 2. 반복 지시와 정정

### 2.1 컨텍스트 관리 의식 — compact 인자 요청 [P1]

- **패턴**: 사용자가 `/context`를 보고 "83% 썼어, compact 인자 줄래?"라고 말한다.
  - 이때 체크포인트, 세션 기록, 핸드오버 점검을 함께 요구한다.
  - 인자에 담을 것은 "잊을 것 / 잊지 말 것 / 다음 할 일"이라고 매번 설명한다.
- **빈도와 분포**
  - compact 관련: 64 / 9 / 4 (quad 49, stl-luau 9, mrow 4, tbox 2)
  - 사용자가 직접 % 를 보고: 27회
  - 체크포인트: 16회
  - 핸드오버: 22 / 13 / 4
- **근거**
  - hL326 "Context is 83% full 이야 … compact 에 넣을 인자를 알려주면"
  - hL488 "체크포인트 찍었으니 핸드오버 점검하고 compact 인자 써줄래?" (같은 문장이 hL479, hL500에도 반복된다)
  - hL1210 "끝냈는것. 다음 할것과 기억해야할것. 그리고 잊어야할것"
  - hL1208 (tbox) 자동 compact가 먼저 일어나 "잊은거 있는지 좀 볼래?"
  - hL1015 (mrow) 사용자가 "97% 넘어가면 auto compact … 맥락이 소실될 수 있어"라고 모델에게 가르친다
- **원인**
  - 모델이 받는 `total_tokens_reminder`는 전체 토큰 예산("N tokens left")이고 컨텍스트 창 %가 아니다.
  - 그래서 모델은 자기 컨텍스트 상태를 모른다. 사용자가 중계하는 수밖에 없다.
- **판정**
  - 스킬 `/checkpoint`: 체크포인트 → 기록 → 핸드오버 점검 → compact 인자 초안. 모델이 먼저 제안할 수 있게 한다.
  - 훅: 컨텍스트 %를 주입한다(§8.3 H1).
  - 사용자 CLAUDE.md: "작업 단위가 끝났을 때나 70%를 넘었을 때 먼저 제안한다" 1줄.

### 2.2 예산·모델·병렬도 지시 [P1]

- **패턴**: 세션마다 "sonnet 몇 개까지", "opus는 판정에만", "fable 쓰지 마", "한 번에 하나", "주간 한도 널널/빠듯"을 다시 말한다.
- **빈도와 분포**
  - 모델 지정: 129 / 22
  - 예산·한도: 25 / 10 / 5
  - 수량 지정: 19 / 8 / 6
  - fable: 13 / 6 / 3
  - memory: quad 4개, stl-luau 2개, table-sim 2개, tbox 1개, devplorer 1개 파일
- **근거**
  - hL224 code-review가 fable 서브에이전트를 포크해 "$589" 사고
  - hL49 "병렬 에이전트를 덜 써줘. 한 턴에 하나씩만"
  - hL1012 (mrow) "문서 읽는데 모두 opus 5.5 를 쓰거나 하지는 마"
  - hL2021 "토큰 한도 널널하다 했던거 아직도 유효함? 지금은 좀 효율적으로"
  - hL2022 (devplorer) "코드 리뷰에 opus 까지 써야할까"
- **판정**: 사용자 CLAUDE.md의 "모델 사용" 절을 확장한다(§8.1 후보 3).
- **충돌**: 지금 정본 `home/.claude/CLAUDE.md:32-42` "코드 리뷰 — 시킬 때를 기다리지 말고 먼저 한다"가 아래 memory와 부딪힌다.
  - quad `feedback-token-efficiency-2026-10-21.md`: "`/code-review`는 큰 변경에만 … 작은 diff엔 안 돌림"
  - devplorer `feedback-review-model.md`: "리뷰는 sonnet, opus는 요청 시만"
  - 정본에 "규모 기준, 강도 medium 이하, sonnet 기본"을 붙여야 한다. 그러지 않으면 사고가 다시 날 수 있다.

### 2.3 언어 — 한국어 [P1]

- **패턴**: 사용자가 보는 글이 영어로 나가면 정정한다. 서브에이전트나 외부 모델 보고를 옮긴 직후에 주로 일어난다.
- **빈도와 분포**
  - 프롬프트: 10 / 6 / 3 (quad hL98, stl-luau hL1563·hL1600, devplorer 5회)
  - memory: quad `feedback-quad-collaboration-style.md`(2026-08-12 추가분), devplorer `feedback-korean.md`
  - 프로젝트 문서: 7개 중 6개(quad, stl, devplorer, table-sim, tbox, rbvm)에 이미 한국어 규칙이 있다
- **근거**
  - hL1563 "내가 보게 되는 메시지는 한국어로 해줘 … Round 1 of ... 부분이 영어인데"
  - quad memory: "CLAUDE.md already states … but I drifted into English"
- **판정**
  - 사용자 CLAUDE.md로 올린다. 지금 정본에는 없다.
  - 규칙만으로는 새는 것을 막지 못했다는 근거가 있다(quad는 CLAUDE.md에 규칙이 있는데도 샜다). 그래서 PostToolUse(Agent) 훅 리마인더를 함께 둔다(§8.3 H2).
  - 승격한 뒤에는 각 프로젝트의 중복 서술을 1줄 포인터로 줄인다.

### 2.4 결정을 구하는 형식 [P1]

- **패턴**: 결정은 주제별 산문으로 받고 싶어 한다(상황 → 문제 → 갈래와 대가 → 권고). 번호 나열은 싫어하고, 몰아서 묻기를 원한다.
  - 자유서술로 답하면 그것이 곧 결정이다. "권고대로"로 답하는 일이 많다.
- **빈도와 분포**
  - "권고대로·추천대로": 74 / 10 / 4
  - 몰아 묻기·인터랙티브 진행: 30 / 9 / 6
  - memory: quad 2개, devplorer 1개(quad에서 복사), tbox 1개, stl-luau 1개
- **근거**
  - hL1005 "결정 작업들은 메인의 세부 의견과 결정에 필요한 재료, 풀어서 보기 좋게"
  - hL980 "하나에 여럿이 묶여서 읽기가 어렵네"
  - hL1065 (tbox) "내 의견이 필요한게 있다면 지금 몰아서 물어볼래?"
  - hL925 (stl) "ui에 쓰는건 하지 말고, 프롬프트 답해나갈 수 있게" (AskUserQuestion이 나중에 다시 보기 어렵다는 이유)
- **판정**: 사용자 CLAUDE.md로 올린다. devplorer와 quad memory는 승격한 뒤 정리한다.

### 2.5 판단 기록 파일 규약 (사실상의 표준) [P2]

- **패턴**: 다섯 저장소가 같은 꼴을 쓴다.
  - `.claude/question.md`: 열린 질문만 둔다. 권고를 함께 적고, 해소되면 `base/`나 `archive/`로 옮긴다.
  - `.claude/todos.md`
  - `HUMAN_TODO.md`: 사람만 할 수 있는 일
  - `.claude/base/`: 확정된 설계
- **분포**
  - question.md: quad, stl, table-sim, devplorer, moonwave
  - HUMAN_TODO: quad(67KB), table-sim(30KB), rbvm, devplorer, claude-doctor
- **함께 나온 정정**
  - hL1408 (table-sim) "내가 말했던것, 특히 작업 도중 말해버렸던것들 검토 다 되었는지 볼래?"
  - hL708 (quad) "이전에 말했던것 같은데 적용이 없는걸 발견했어"
  - 작업 도중에 한 지시가 compact를 거치며 사라진다. 트랜스크립트에는 `queued_command` 첨부가 1,856건 있다.
- **판정**
  - 사용자 CLAUDE.md에 파일 이름과 역할을 4줄로 적는다.
  - 대조 절차는 `/handover` 스킬에 둔다. history.jsonl에서 이번 세션의 사용자 지시를 뽑아 반영 여부를 대조하는 스크립트를 함께 둔다.

### 2.6 사용자 메시지 표지 [P3]

- **패턴**
  - "천천히 읽어도 돼:"로 시작하는 비동기 메시지가 있다(8 / 5 / 3). `/btw`도 7회 썼다.
  - 자기 일정을 알린다. "자러 가", "밥먹고", "4시까지"(16 / 7 / 5).
- **판정**: 사용자 CLAUDE.md 1줄. "천천히 읽어도 돼 = 지금 작업을 끊지 말고 todos에 적은 뒤 이어서. 시각은 KST."

---

## 3. 프로젝트 간 참조

### 빈도

- "보고 와 / 가져와 / 참고해 / 다른 경로": 52 / 15 / 7
- 다른 저장소 이름 언급 (출발 → 대상)

| 출발 → 대상 | 횟수 |
|---|---|
| stl-luau → quad | 18 |
| quad → devui·devplorer | 30 |
| table-sim → quad | 8 |
| devplorer → quad | 8 |
| mrow → quad·stl | 6 |
| rbvm → 4곳 | 4 |
| table-sim → stl | 3 |

### 무엇을 가지러 갔나 (→ luau-kb에 있어야 할 것)

| 가져간 지식 | 근거 (출발 → 대상) | 받을 곳 |
|---|---|---|
| `--!strict` 타입 검사 방식, 타입 한계와 "too complex" 한도 플래그 | hL185, hL900, hL906, hL1622 (stl → quad) | luau-types, luau-verify |
| require 사실(`@self`) | hL925 (stl → quad `.claude` grep) | luau-verify 또는 roblox-luau |
| Brand / Marker / `Marker.toXXX` 패턴, 제네릭 연구 | hL1138, hL1191, hL2225, hL2275 (stl → quad) | luau-types references (패턴 절) |
| Studio = luau-lsp (에러 번호까지 같다) | hL1624 (stl → quad 실측), stl memory `studio-is-luau-lsp` | luau-verify |
| 성능 실측 안전 한도(무한 clone 스래싱 사고) | hL2137 (quad → stl) | luau-perf + heavy-proc 훅 |
| agy(Gemini) 위임 설정, uid 분리 | hL1018, hL1150, hL1201, hL1431, hL1714 (stl·tbox·table-sim·mrow → quad) | `/delegate` (이미 초안 있음) |
| Studio sync, MCP 사용법, 코드리뷰 방식, 컨벤션 | hL1824 (devplorer → 전체), hL1164 (rbvm → tbox·quad·stl·mrow) | roblox-luau, `/new-luau-project` |
| pesde + mise 툴링 | hL92 (quad → tbox), hL1082 (tbox) | `/new-luau-project`, luau-verify |
| quad UI 사용법 | hL1296 (table-sim, `quad-ui-dev` 스킬 복사본) | quad 프로젝트 스킬을 소비자에게 배포 |
| 주변 Luau 프로젝트를 근거로 한 조언 보고서 | hL1011 (mrow), hL1164 (rbvm) | luau-kb가 생기면 대부분 해소된다 |

### 또 하나의 흐름: 상위·하위 피드백 왕복 [P2]

- **패턴**: 소비자 프로젝트(devplorer, table-sim)가 `.claude/feedback/<상위>-upstream-<날짜>.md`를 쓴다. 상위(quad) 세션이 그것을 읽는다. 사용자가 두 세션 사이에서 손으로 중계한다.
- **근거**
  - hL1872 "devplorer 쪽에서 quad의 한계를 … 정리해달라고 할 프롬프트를 써볼래?"
  - hL1880, hL2069, hL2102 ("quad 작업자가 정리한 것이야")
  - hL1400 (table-sim) "quad쪽에 해달라 요청해볼게"
- **판정**: 새 스킬 `/upstream-feedback`(§8.2). 쓰는 쪽은 형식을 정해 파일을 쓰고, 읽는 쪽은 미처리 목록을 본다. 형제 저장소 지도에 "피드백 위치" 1줄을 더한다.

---

## 4. 반복 작업 흐름 — 기존 초안과 비교

| 흐름 | 손으로 지시한 빈도 | 기존 초안 | 빠진 것 |
|---|---|---|---|
| 체크포인트 → 핸드오버 점검 → compact 인자 | 64 / 9 / 4 | 없음. stl-luau-doctor에 `handover`가 있지만 stl 전용이고 사용자 호출 전용이다 | 사용자 레벨 `/checkpoint`, 일반화한 `/handover` |
| 리뷰를 "소진·수렴할 때까지" 다패스 | 44 / 13 / 8 | `/audit`: `--rounds N`(기본 3), `--serial` | **종료 조건이 "라운드 수"뿐이다.** 사용자의 기준은 "새 항목 0건"이다(hL1164, hL662, hL1081). 또 `/audit`은 기본이 병렬 3인데, 자율 구간은 하나씩이라는 memory(stl `autonomous-run-budget`, table-sim `review-loop-one-agent`)와 맞지 않는다 |
| agy가 찾고 → sonnet이 거르고 → 메인이 고치는 순차 루프 | table-sim hL1610, memory | `/delegate`는 좁은 질문 하나만 다룬다. stl memory "agy는 정규 라운드에 세우지 말 것"과 table-sim 방식이 **모순**이다 | 정책을 하나로 정한다(§6 모순 3) |
| "sonnet 외부자/내부자 시선"으로 이름·표현 객관 평가 | 35 / 7 / 4 (quad 24) | `/debate` (A)형이 덮는다. 다만 사용자 호출 전용이고 무겁다 | 가벼운 모드를 둔다(`/debate --quick`, 모델 호출 허용). 아니면 `/delegate`에 "세 계열 이름 대조" 템플릿을 둔다 |
| 다른 모델 계열(agy, codex) 위임 | agy 20 / 6, gemini 46 / 10 / 7, codex 5 | `/delegate` | 프로젝트마다 다른 허용 모델과 effort를 registry에 모은다. codex effort가 quad는 medium, devplorer는 high로 다르다 |
| 밤샘·자리 비움 자율 구간 | 16 / 7 / 5, cron·loop 25 / 11 / 5 | 없음 | 새 스킬 `/overnight`(§8.2) |
| 새 Luau 프로젝트 착수 때 형제 저장소 참고 | table-sim hL1296, devplorer hL1822·1824, rbvm hL1164, mrow hL1011 | PLAN의 `/new-luau-project` (P4) | 근거가 충분하다. 우선순위를 올려도 된다 |
| 릴리스(changelog, pesde publish, 태그, 문서 배포) | 43 / 10 / 4, quad가 31 | 없음 | quad 프로젝트 스킬 `/release`(사용자 레벨 불필요) |
| 문서 감사 | quad 위주 | `docs-auditor` 초안, stl-luau-doctor `doc-audit` | 충분하다 |
| 하네스 진단 | — | `/harness-doctor` | **auto memory 감사**(중복, 모순, 승격 후보)와 **사용 흔적 채굴**(이 보고서의 방법) 모드가 없다. `--usage` 모드와 스크립트를 넣을 만하다 |
| Q/H 번호 원장, 라운드 문서, 몰아서 답하기 | quad 22 / 9 | — | quad 프로젝트 규약으로 충분하다 |

---

## 5. 불만·좌절 신호와 막을 장치

사용자의 어조는 대체로 차분하다. 감정 표지(`ㅡㅡ`, `;;`, `제발`)는 1건뿐이다. 그래서 아래 유형은 정정 문장과 이벤트를 근거로 분류했다.

| 유형 | 근거 | 빈도 | 막을 장치 |
|---|---|---|---|
| 서브에이전트, 리뷰 포크 폭주로 토큰 과소비 | hL220·hL224 ($589), hL398 "또 fable 여럿으로 나뉘었네 … 컨벤션 상 하지 말기로", hL44, hL2022 | 정정 8+, 4프로젝트 | **rules**(효율 기본값) + `/code-review` 호출 기준을 정본에 명시. 훅으로 막기는 어렵다(Agent 수를 세는 PreToolUse 훅은 가능하지만 오탐 위험이 있다) |
| 묻지 않고 백그라운드 작업 중단 | hL400 "멈추는것도 유저 물어보고 해야하는데" | 1회지만 손실이 크다. memory 2곳 | **rules**. 선택적으로 TaskStop에 PreToolUse 훅(ask) |
| 백그라운드 완료를 잘못 판정 | hL361 "끝났는데 … 안 끝났다고 판단하게 되네" | memory 1 | **rules** 1줄 |
| 이전 지시 누락 (작업 중 말한 것, compact 뒤) | hL708·710, hL1408, hL161 "지워져서 다시 말하" | 4+ / 3프로젝트 | **스킬** `/handover`의 지시 대조 단계 + **rules**(작업 중 지시는 즉시 todos에) |
| 영어 출력 | §2.3 | 10 | **rules** + **훅** H2 |
| Studio를 사용자와 두고 다툼 (사용자가 켠 Play 중지, Play 중 sync) | devplorer: 중단 11회 중 Studio 관련 4회 ("테스트는 내가 할게. 싱크만", "studio 다시 열었어"), 거부한 tool_use 중 `start_stop_play` 2건, `studio-sync` 1건. quad memory "아무 플레이스에나 sync 금지" | 7+ / 2프로젝트 | **rules**(짧게) + **roblox-luau 스킬**(상세). 훅 후보: `start_stop_play`에 PreToolUse ask |
| 결정 질문이 읽기 어려움 | hL980, hL1005 | memory 4곳 | **rules** (§2.4) |
| 과잉 설계 (타입 오버엔지니어링) | hL2225 (stl) "너무 타입으로 터무니없이 오버엔지니어링" | stl memory 3개 | **luau-kb 스킬**(설계 원칙 절). 프로젝트 memory로 유지 |
| 권한 규칙이 작업 흐름을 막음 | hL2148 (devplorer) "permissions 로 제어한다는것 부터가 이상", claude-doctor memory `git-workflow-sandbox` | 2프로젝트 | 이미 처리 중(HUMAN_TODO "git push deny"). **사용자 CLAUDE.md**에 git 흐름을 1줄 적는다 |
| 내장 안전 검사 반복 차단 (`rm -rf $S/$v`) | 트랜스크립트 22회 (quad 12, stl 7, 그 밖 3). 같은 패턴 명령은 468회 | 22 | **rules** 1줄: "rm 대상은 리터럴 절대경로로" |
| auto 모드 분류기 차단 | 21회, 7프로젝트. Irreversible Local Destruction 6 (`git stash` 포함), Modify Shared Resources 3, Git Destructive 2, Self-Modification 1 등 | 21 | `git stash`·`checkout`·`restore` 금지를 **rules**로 둔다(quad memory 승격). 나머지는 정상 차단이다 |
| heavy-proc-guard 차단 | quad 29, table-sim 1. 이 세션에서 heredoc 안의 단어로 오탐 1건 | 31 | 훅 유지. **오탐 개선**: 명령 본문의 heredoc·문자열 리터럴은 판정에서 제외. 메시지에 `ulimit -c 0` 권고를 추가한다(quad와 mrow 저장소 루트에 `core.*` 덤프가 남아 있다) |
| 사용자의 도구 거부와 중단 | 거부 14 (quad 6, devplorer 7, mrow 1, stl 1), 중단 약 23 (devplorer 11, quad 8) | — | 대부분 Studio·sync·방향 수정이다. 위 항목에 흡수된다 |

---

## 6. auto memory 감사

### 6.1 사용자 레벨로 승격할 것

**승격 판단 기준**
- 두 개 이상의 프로젝트에 있거나,
- 환경 전역에 해당하는 사실(sandbox, 하네스 동작)이거나,
- 사용자 자신에 대한 사실일 때 승격한다.

| memory | 위치 | 이유 | 갈 곳 |
|---|---|---|---|
| 한국어 | devplorer `feedback-korean`, quad `collaboration-style` 일부 | 2곳 + 문서 6곳 | CLAUDE.md |
| 결정 형식 | quad `feedback-decision-presentation-style`, devplorer `feedback-decision-style`(복사본), tbox `testing-work-policy` 일부, stl `autonomous-run-budget` 일부 | 4곳 | CLAUDE.md |
| 백그라운드 작업을 묻지 않고 멈추지 않기 | quad `feedback-never-stop-background-tasks-unasked`, devplorer `feedback-review-model` 끝줄 | 2곳 | CLAUDE.md |
| 백그라운드 완료 판정 | quad `feedback-background-agent-completion-signal` | 하네스 동작 | CLAUDE.md 1줄 |
| 서브에이전트 탭에 사용자가 입력함 | quad `feedback-subagent-tab-messages` | 하네스 동작 | CLAUDE.md 1줄 (P3) |
| `pgrep -f` 자기 매치 | quad `feedback-pgrep-self-match` | 환경 전역 | rules. **정본 CLAUDE.md:18의 `pgrep -f claude` 예시와 모순**이다(자기 셸이 결과에 섞인다) |
| `git stash`·`checkout`·`restore` 금지 | quad `feedback-session-operating-constraints` | 공유 체크아웃이 전역 문제이고, 분류기도 차단한다 | CLAUDE.md |
| `ulimit -c 0` | 같은 파일 | 코어 덤프가 저장소를 오염시킨다 | heavy-proc 훅 메시지 |
| git 트레일러 자동 치환 | quad `feedback-git-trailer-hook` | sandbox 전역 훅 | CLAUDE.md 1줄 |
| push 흐름 (origin은 에이전트 계정, upstream은 사용자) | quad `git-remote-push-policy`, devplorer `feedback-agent-repo-push`, claude-doctor `git-workflow-sandbox` | 3곳 | CLAUDE.md 원칙 1줄. 원격 이름은 프로젝트에 남긴다 |
| 예산 기본값 | quad `feedback-token-efficiency-2026-10-21`, stl `autonomous-run-budget`, table-sim `review-loop-one-agent`·`subagent-model-mix`, tbox `testing-work-policy`, devplorer `feedback-review-model` | 6곳 | CLAUDE.md "모델 사용" 확장 |
| 서브에이전트 산출물 남기기 | stl `subagent-keep-artifacts` | 위임 일반 | CLAUDE.md 또는 `/delegate`·`/audit` |
| 사용자는 KST, 밤샘 허용 범위 | quad `user-timezone-and-overnight-runs` | 사용자 사실 | CLAUDE.md 1줄 + `/overnight` |
| 사용자 정체 (quad 저자, 숙련자) | devplorer `user-quad-author` | 사용자 사실 | CLAUDE.md 1줄 ("기초 설명 생략") |
| Studio 공유 규칙 (Play, sync, PlaceId 표) | devplorer `feedback-studio-play`, quad `reference-studio-mcp-input` | Studio 하나를 여러 프로젝트가 같이 쓴다 | CLAUDE.md 짧게 + roblox-luau 스킬 |
| Studio·Roblox 지식 (마우스 y-58, 데칼≠이미지 id, MCP 100KB 상한, studio=luau-lsp) | quad 2개, tbox `tbox-tooling-gotchas`, stl `studio-is-luau-lsp` | 지식 | luau-kb roblox-luau·luau-verify |
| 외부 모델 호출법과 허용 모델 | quad `reference-codex-delegation`·`feedback-agy-cross-family-review`, devplorer `feedback-outside-reviewers`, table-sim `no-gemini-for-audio` | 4곳 | `/delegate` registry와 references |
| 옮긴 뒤 이음매 감사 | devplorer `feedback-audit-after-move` | 감사 트리거 | `/audit` 0단계 표 |
| 라이브러리 설계 원칙 (이름 있는 틀을 준다, DX가 먼저, 타입과 런타임 분리, 깨지는 변경 전에 종이 설계) | stl 3개, tbox `design-before-breaking` | quad·stl·tbox 공통 기조 | luau-kb `luau-design` references (P3) |

### 6.2 모순

1. **push 정책**
   - quad, devplorer, claude-doctor는 "origin에는 자유롭게 push"다.
   - tbox `testing-work-policy`는 "do not push"(2026-09-30)다. rbvm과 table-sim의 settings에는 push deny가 있다.
   - 사용자 레벨에 기본값을 두고, 다른 프로젝트는 예외로 적어야 한다.
2. **agy 예산**
   - quad `feedback-agy-cross-family-review`: "agy 토큰 한도는 널널"(10-02)
   - stl `agy-budget-generous`: 이름과 달리 본문은 "빠듯함, 하나씩"(10-20)
   - 예산은 시점 발언이다. memory에 박지 말고 "기본은 효율, 완화는 그 세션 한정"으로 일반화한다.
3. **Gemini의 역할**
   - stl `agy-is-second-opinion`: "리뷰 라운드나 전수 감사에 세우지 말 것"
   - table-sim `review-loop-one-agent`: "agy가 보고 → sonnet이 거르고 → 메인이 고친다"(정규 루프)
   - `/delegate`에서 하나로 정해야 한다. 사용자의 가장 최근 발언(11-04, stl)은 전자다.
4. **fable**
   - table-sim `subagent-model-mix`: "다른 시선이 필요한 검토는 fable"
   - quad: fable 서브에이전트 포크 금지(hL503 "fable 은 쓰지 않아")
   - 메인 모델이 2026-09-28에 opus 5.5로 바뀌었으므로 table-sim 쪽이 낡았다.
5. **codex effort**: quad는 `model_reasoning_effort=medium`, devplorer는 "luna high만"이다.
6. **리뷰 시점**: 정본 CLAUDE.md "리뷰를 먼저 한다"와 quad·devplorer의 리뷰 억제 memory가 다르다(§2.2).

### 6.3 낡았거나 정리할 것

- quad `project-quad-v2-rewrite.md`: 2026-08-11 상태("M0은 시작 전")에 멈춰 있다. 지금 4.0.0이 나왔다. 삭제하거나 "상태는 CLAUDE.md" 포인터 한 줄로 줄인다.
- quad `feedback-quad-collaboration-style.md`: 12.6KB이고 덧붙인 절이 7개다. 일반 규칙(한국어, 몰아 묻기, "X가 이미 한다"는 열어 보고 확인, 핸드오버 자가 감사)은 승격하거나 스킬로 보내고, quad 고유 부분만 남긴다.
- quad `feedback-model-choice-for-reflection.md`: fable 시절의 문단이 남아 있다. 2026-09-28 갱신분만 남긴다.
- stl `agy-budget-generous.md`: 파일 이름이 본문과 반대다.
- claude-doctor `model-usage-policy`, `live-sessions-caution`, `home-claude-sync`: 정본 CLAUDE.md와 중복된다. 이 저장소의 memory이므로 해롭지는 않다. `git-workflow-sandbox`는 **정본에 없으니** 승격 대상이다.

---

## 7. 도구 사용 통계 (트랜스크립트, 메인과 서브에이전트 합계)

| 범주 | 수치 | 해석 |
|---|---|---|
| Bash | 63,535 | Read 3,463 / Edit 1,040 / Write 2,007. Bash로 파일을 쓰는 명령(`sed -i`, python `open(..,'w')`)이 약 10.3k다. paths rules가 로드되지 않는 경로라서 bash-bypass-reminder 훅의 근거가 된다 |
| Studio MCP | `execute_luau` 3,191, `user_mouse_input` 2,080, `screen_capture` 1,762, `start_stop_play` 1,226 | Studio를 매우 많이 쓴다. 공유 규칙이 필요하다 |
| Studio MCP 내장 스킬 | `skill` 4, `list_skills` 1, `rojo_sync_guide` 9 | 거의 안 쓴다(PLAN §3과 일치) |
| Agent | 1,243 | general-purpose sonnet 415, opus 405, `quad-doc-auditor` 159, fork 49, Explore 19, haiku 4 |
| Skill 도구 | 32 | code-review 18, luau-types 7, delegate-agy 5, luau-verify 1, update-config 1 |
| 기타 | AskUserQuestion 42 (거부 1), ScheduleWakeup 72, Monitor 45, EnterWorktree 47, TaskStop 23 | — |
| Blender MCP | 약 330 | table-sim |
| 쓰지 않은 것 | `/simplify` 0, `/security-review` 0, `/loop` 0 (ScheduleWakeup은 직접 씀), fewer-permission-prompts 0, Studio 내장 스킬 대부분 | — |

정본 CLAUDE.md는 `/simplify`와 `/security-review`를 권한다. 실사용은 0이므로 권고를 유지할지 따로 판단해야 한다.

---

## 8. 정리

### 8.1 사용자 레벨 CLAUDE.md·rules 후보 10개

1. **언어**: 사용자가 보는 글(보고, 질문, 상태 안내)은 한국어로 쓴다. 서브에이전트나 외부 모델의 영어 보고를 옮길 때 특히 조심한다. 식별자와 명령은 원문 그대로 둔다. [CLAUDE.md] (§2.3)
2. **결정을 구하는 형식**: 문항마다 상황 → 문제 → 갈래와 대가 → 권고를 산문으로 쓴다. 번호 나열과 압축은 피한다. 결정은 떠나기 전이나 라운드 단위로 몰아서 묻는다. 자유서술 답이 곧 결정이다. "권고대로"는 각 항목의 권고를 채택한다는 뜻이다. [CLAUDE.md] (§2.4)
3. **예산 기본값은 효율 모드**
   - 작은 수정은 메인이 직접 한다.
   - 서브에이전트는 동시 2개 이하, 사용자가 자리를 비운 구간에는 1개다. 중첩 포크는 금지한다.
   - 리뷰와 감사는 sonnet이 기본이다. opus는 판정과 설계, 또는 사용자 요청 때 쓴다.
   - `/code-review`는 큰 변경에만 쓰고 강도는 medium 이하부터 시작한다.
   - 사용자의 "한도 널널" 발언은 그 세션에만 적용한다.
   - [CLAUDE.md "모델 사용"·"코드 리뷰" 절 수정] (§2.2, §6.2-6)
4. **백그라운드 작업**: 돌고 있는 작업은 묻지 않고 멈추지 않는다. 완료 판정은 알림의 status와 ListAgents로 하고 본문의 "대기 중"은 무시한다. [CLAUDE.md] (§5)
5. **컨텍스트 관리**: 작업 단위가 끝났거나 컨텍스트가 70%를 넘으면, 먼저 기록(todos, 세션 기록)을 남기고 compact 인자(남길 것 / 잊을 것 / 다음 할 일)를 제안한다. 상세는 `/checkpoint`. [CLAUDE.md 1줄 + 스킬] (§2.1)
6. **판단 기록 파일**: `.claude/todos.md`, `.claude/question.md`(열린 질문만, 권고 포함, 해소되면 base/·archive로), `HUMAN_TODO.md`(사람 몫), `.claude/base/`(확정 설계). 사용자가 작업 중에 한 지시는 바로 todos에 적는다. "천천히 읽어도 돼"는 지금 작업을 끊지 않는다는 표지다. [CLAUDE.md] (§2.5, §2.6)
7. **git**
   - `git stash`·`checkout`·`restore`를 쓰지 않는다. 대조는 `git show HEAD:<경로>`, `git diff HEAD --`로 한다.
   - origin(에이전트 계정)에는 push해도 된다. upstream과 GitHub는 사용자 몫이다.
   - 트레일러는 하네스 기본값 그대로 쓴다(sandbox 훅이 치환한다).
   - 프로젝트가 따로 정하면 그것이 우선한다.
   - [CLAUDE.md] (§6.1, §6.2-1)
8. **Bash 위생**
   - `rm -rf` 대상은 셸 변수가 아니라 리터럴 절대경로로 쓴다.
   - 프로세스 판정은 `pgrep -x`나 포트로 하고, 죽일 때는 pid로 한다(`-f`는 자기 셸에 걸린다).
   - 무거운 실행에는 choom, `ulimit -c 0`, timeout을 함께 건다.
   - 정본 CLAUDE.md:18의 `pgrep -f claude`도 고친다.
   - [rules 또는 CLAUDE.md "도구" 절] (§5)
9. **Roblox Studio는 공유 자원이다**
   - 사용자가 켠 Play는 멈추지 않는다. Play 중에는 sync하지 않는다.
   - sync 전에 `game.PlaceId`로 내 플레이스인지 확인한다.
   - 서브에이전트와는 lock으로 나눠 쓴다. 상세는 roblox-luau 스킬.
   - [CLAUDE.md 2줄] (§5)
10. **사용자와 위임**
    - 사용자는 KST에 있고 Roblox/Luau 숙련자다. 기초 설명은 생략한다.
    - 사용자의 지적은 액면 그대로 검증한다. "X가 이미 한다"고 쓰기 전에 X를 열어 본다.
    - 서브에이전트에게 맡긴 시제품과 프로브 파일은 지우지 말고 경로를 보고하게 한다.
    - [CLAUDE.md] (§6.1)

예비 후보
- 외부 모델은 발견이지 결정이 아니다. 이미 `/delegate`에 있다.
- "다른 저장소를 보러 가기 전에 luau-kb 스킬부터"는 이미 정본 :12에 있다.

### 8.2 새 스킬 후보

| 스킬 | 호출 | 내용 | 근거 |
|---|---|---|---|
| `/checkpoint` (compact 준비) | 사용자와 모델 모두 | (1) todos와 세션 기록 갱신 (2) 커밋할 것 정리 (3) 핸드오버 누락 점검 (4) compact 인자 초안: 끝낸 것 / 다음 할 것 / 꼭 기억할 것 / 잊어도 될 것(세부 도구 호출 등) | §2.1, 64회 / 4프로젝트 |
| `/handover` (일반화) | 사용자 | stl-luau-doctor `handover` 기반. **history.jsonl에서 이번 세션의 사용자 지시를 뽑아 todos·question과 대조하는 스크립트**를 더한다. "해소됨"이라고 적은 항목에 검증 산출물이 있는지 자가 감사한다(quad memory 2026-08-12) | §2.5, 22 + 9 / 4프로젝트 |
| `/overnight` (자율 구간 설정) | 사용자 | 떠나기 전에 결정을 몰아 묻는다 → 예산과 동시 실행 수를 확인한다 → 순차 리뷰 루프와 cron·ScheduleWakeup을 건다 → "자고 일어나서 볼 것" 표를 남긴다 → 치명적인 것이 나오면 멈춘다 | 16 / 7 / 5, cron 25 / 11 / 5, memory 3 |
| `/upstream-feedback` | 사용자 | 소비자 쪽: 정한 형식(한계, DX, 필요한 부품, 재현)으로 `.claude/feedback/<상위>-upstream-<날짜>.md`를 쓴다. 상위 쪽: 소비자 저장소의 feedback 폴더를 읽기 전용으로 모아 미처리 목록을 만든다 | §3, 8 / 3프로젝트 |
| `/audit` 보강 | — | `--until-exhausted`(새 발견 0건이면 종료, 상한 N). 자율 구간에서는 기본을 `--serial`로 바꾼다. 다른 계열 필터 단계는 선택 사항으로 둔다 | §4 |
| `/debate --quick` 또는 `/delegate` 이름 대조 템플릿 | 모델 호출 허용 | sonnet, luna, flash에 같은 질문을 던지고 표로 대조한다. 토론 단계는 없다 | 외부자 시선 35 / 7 / 4 |
| `/harness-doctor --usage` | 사용자 | 이 보고서의 방법을 스크립트로 만든다. history 키워드 빈도, 거부·차단 이벤트, memory 중복·모순·승격 후보 | 이 보고서 |
| `/new-luau-project` (PLAN P4) | 사용자 | 근거가 충분하다. rbvm, devplorer, table-sim, mrow 착수 때마다 "주변 보고 와"를 했다 | §3 |
| quad `/release` (프로젝트) | 사용자 | changelog → 버전 → pesde publish(429 재시도) → 태그 → 문서 배포(check-mermaid) | 43 / 10, quad 31 |

### 8.3 훅 후보

| ID | 이벤트 | 동작 | 막는 패턴 | 비고 |
|---|---|---|---|---|
| H1 | UserPromptSubmit (+ 선택적으로 PostToolUse) | `transcript_path`에서 마지막 assistant usage(input + cache)를 읽어 컨텍스트 %를 계산한다. 60, 75, 90%를 넘으면 `additionalContext`로 "체크포인트와 compact 준비를 제안하라"를 넣는다. 구간마다 1회 | 사용자의 % 중계(§2.1) | 상태줄에도 같은 값을 보이면 `/context` 확인도 줄어든다 |
| H2 | PostToolUse matcher `Agent\|Task` (+ SubagentStop) | `additionalContext`: "이 보고를 사용자에게 옮길 때는 한국어로, 산문으로" | 영어 출력(§2.3) | 세션당 N회로 제한한다 |
| H3 | PreToolUse matcher `TaskStop` | `permissionDecision: ask`. 사용자 확인 없이 백그라운드를 죽이지 못하게 한다 | §5 사고 | auto 모드에서 ask가 어떻게 동작하는지 실측이 필요하다 |
| H4 | PreToolUse `mcp__roblox-studio__start_stop_play` | Play 상태를 확인하라는 리마인더(`additionalContext`). 막지는 않는다 | Studio 다툼(§5) | 상태 조회는 훅 안에서 못 하므로 리마인더만 준다 |
| H5 | heavy-proc-guard 개선 | heredoc과 따옴표 안의 문자열은 판정에서 뺀다(이 세션의 오탐). 메시지에 `ulimit -c 0`을 추가한다 | 오탐, 코어 덤프 오염 | 기존 훅 수정 |
| H6 | PreToolUse Bash `rm -rf\s+"?\$` | 리터럴 경로를 쓰라는 리마인더 | 내장 안전 검사 22회 | 내장 검사가 이미 막으므로 우선순위는 낮다(rules 1줄로 충분할 수 있다) |
| (유지) | bash-bypass-reminder | 그대로 둔다 | Bash 파일 쓰기 약 10.3k | 근거 수치가 확인됐다 |

---

## 부록: 재현

- 추출 스크립트는 `/tmp/um/`에 임시로 있다(`ex.py`, `kw.py`, `ph.py`, `show.py`, `den2.py`, `byp.py`). `/harness-doctor --usage`를 만들 때 `scripts/`로 옮길 것.
- 개인정보
  - history 원문에는 자격 증명처럼 보이는 문자열이 섞여 있다(예: hL237 근처). 이 보고서에는 옮기지 않았다.
  - 스크립트로 다시 뽑을 때 출력 마스킹이 필요하다.
