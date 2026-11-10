# 18. 검토(second opinion) 운용 제안: advisor 대신 예측 가능한 독립 검토

날짜 2026-11-10, claude 2.1.316, 메인 opus 5.5. 이번에는 **제안만** 한다. 설정·CLAUDE.md·훅은 고치지 않았고 플러그인도 설치하지 않았다. 초안은 `drafts/second-opinion/`에만 있다.

표기
- [문서]: 공식 문서 원문으로 확인(code.claude.com advisor·hooks·sub-agents, platform.claude.com advisor-tool)
- [로컬]: 이 sandbox 의 트랜스크립트·설정·실행으로 확인
- [추정]: 계산이나 추론. 근거를 같이 적는다
- [미확인]: 문서와 로컬 어디서도 확인하지 못함

## 0. 요약

- **권장: advisor 는 끈 채로 두고, 새 컨텍스트 리뷰어 서브에이전트를 정해진 시점에 부른다.**
  - **언제**: 시점은 셋이다. 그중 잴 수 있는 두 개(같은 실패 2회, 큰 diff 커밋)는 훅이 알린다. 나머지 하나(접근 확정 전)는 메인이 판단한다.
  - **얼마나 세게**: 저장소 등급표(high=opus, mid=sonnet, low/off)로 정한다.
  - **무엇을 넘기나**: 리뷰어는 사용자 원문을 트랜스크립트에서 직접 뽑아 본다. 메인은 목표·제약·"검증할 주장"만 넘긴다.
  - **결과**: 요약하지 않고 그대로 전달한다. 받아들였는지는 원장에 남겨 효과를 잰다.
- **advisor 를 기본으로 쓰지 않는 이유 세 가지** (모두 이 환경에서 잰 값이다)
  1. **사용자가 조언을 읽을 수 없다.** 메인이 Opus 5/5.5 면 advisor 로 고를 수 있는 모델(Fable, Opus 5 이상)은 모두 조언을 **암호화**해 돌려준다(`advisor_redacted_result`). 트랜스크립트에는 암호문만 남는다. 지금까지 기록된 18건이 전부 그랬다. 결론을 "그대로 전달"할 수가 없다.
  2. **이 사용자의 세션에서는 비싸다.** 호출마다 대화 전체를 캐시 없이 다시 읽는다. 활발한 저장소의 메인 세션 맥락은 중앙값 26만~42만, p90 은 45만~81만 토큰이다. 그래서 Opus 5.5 advisor 는 한 번에 API 환산 $1.0~3.3 이 든다. 서브에이전트도 advisor 를 물려받는다. 이 세션에서는 14분 동안 4건, $4.73 이 나왔다.
  3. **언제 부를지 예측이 안 된다.** 시점은 모델이 정한다. 주입되는 시스템 리마인더는 "긴 작업에서는 최소 두 번" 부르라고 권한다. 횟수를 제한하는 설정은 없다.
- **advisor 가 잘한 것도 인정한다.** 지금까지 advisor 가 잡은 것은 모두 진짜였다.
  - 이 세션에서 4건
  - vitrine: nonce 재사용, CSRF
  - 대부분 "대화에서 한 말과 실제로 한 일의 차이"였다.

  리뷰어 설계는 이 강점을 메우는 데 맞췄다. 사용자 원문을 직접 추출하고, 메인이 하려는 말을 "검증할 주장"으로 넘긴다. 첫 단계로 같은 시점을 리뷰어로 재현해 4건을 다시 잡는지 재 보자고 제안한다(§8).
- **예상 비용** [추정]
  - 제안안(훅 알림을 전부 따랐을 때): 저장소 전체 합산 하루 $3~5(API 환산).
  - advisor 상시: 활성 세션 1시간에 $3~6, 여기에 서브에이전트 몫이 더해진다.

## 1. 확인된 사실

### 1.1 advisor 사실 대조 (과제에 적힌 내용 ↔ 확인)

| 과제의 서술 | 확인 | 보충·정정 |
|---|---|---|
| 서버 측 도구. 모델은 사용자, 호출 시점은 Claude | [문서][로컬] | 도구 정의(로컬 `api-request-shape`): `{"type":"advisor_20260301","name":"advisor","model":"claude-opus-5-5","defer_loading":true}`. `max_uses`·`caching`·`max_tokens` 를 보내지 않는다 |
| 대화 전체를 받는다 | [문서][로컬] | 호출 시점 메인 맥락 317,328 → advisor 입력 300,763 토큰 |
| Opus 5/5.5 메인 → Fable 또는 Opus 5 이상만 | [문서] | 표의 "Opus 5 or Opus 5.5 → Fable, Opus 5 or later" 와 같다. 더 낮은 advisor 를 고르면 붙지 않는다 |
| Opus+Opus 는 "비용보다 독립 검증이 중요한 고위험" | [문서] | 원문: "A second Opus reviews the first. Useful for high-stakes tasks where an independent check matters more than cost" |
| 대화 읽기는 캐시되지 않는다 | [문서][로컬] | advisor 반복 `cache_read_input_tokens: 0`. API 에는 advisor 용 `caching` 이 있고 "호출 3회부터 본전"이지만 Claude Code 는 켜지 않는다 [로컬: 도구 정의] |
| 구독은 사용량 한도에 포함 | [문서] | 일부 플랜은 Fable advisor 를 usage credits 로 청구하고, `/model fable` 로 한 번 동의해야 한다 |
| 호출 횟수를 제한·강제하는 설정 없음 | [문서] | API 의 `max_uses` 는 **턴당** 상한이고, Claude Code 는 노출하지 않는다. 대화 단위 상한은 API 에도 없다 |
| `/advisor <model>`, `/advisor off`, `advisorModel`, `--advisor`, `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` | [문서] | `--advisor` 는 `--help` 에 없다. env 로 끄면 `--advisor` 도 효과가 없다. `DISABLE_TELEMETRY` 처럼 플래그 가져오기를 끄는 변수가 있어도 꺼진다 |
| 서브에이전트가 물려받는다 | [문서][로컬] | 이 세션 서브에이전트 3개가 각자 opus advisor 를 불렀다. `/advisor opus`·`off` 는 **이미 실행 중인** 서브에이전트에도 즉시 들어갔다(서브에이전트 트랜스크립트에 `advisor_tool` add/remove 첨부) |
| 토글해도 메인 prompt cache 유지 | [문서][로컬] | 로컬: 도구는 처음부터 `defer_loading` 으로 정의에 있었고, 켤 때 `tool_reference` 로만 로드됐다. 접두가 바뀌지 않으니 문서 설명과 맞는다 |
| Reviewed / Declined / Unavailable, Ctrl+O, `/usage` | [문서] | 문서: Ctrl+O 는 "readable guidance 를 돌려줬을 때" 읽힌다. Opus 5/5.5·Fable advisor 는 암호화 결과만 주므로 **이 조합에서 Ctrl+O 로 본문을 볼 수 있는지 [미확인]**(UI 확인 필요). 트랜스크립트에는 본문이 없다 [로컬] |

더 확인한 것
- **조언 암호화** [문서]: platform 문서는 Opus 5.5, Opus 5, Fable, Sonnet 5.5, Haiku 5.5 advisor 가 `advisor_redacted_result` 를 돌려준다고 한다. 평문(`advisor_result`)은 Opus 4.8 같은 구형만 준다. 그런데 Opus 5.5 메인에는 구형 advisor 를 붙일 수 없다. 그래서 **이 사용자 구성에서는 조언 본문을 읽을 방법이 없다**.
- **호출을 권하는 주입문** [로컬, 트랜스크립트 L2469 `rendered`]: 요지는 다음과 같다.
  - "실질 작업 전에 부르라."
  - "완료라고 믿을 때, 막혔을 때, 접근을 바꾸려 할 때 부르라."
  - "몇 단계 넘는 작업에서는 접근 확정 전 한 번, 완료 선언 전 한 번은 최소로 부르라."
  - 사용자 지시가 이보다 우선하는지는 [미확인]이다. 문서는 "지시문으로 더 자주/덜 부르게 할 수 있다"고만 한다.
- **실패 결과** [문서]: `advisor_tool_result_error`. `error_code` 는 overloaded, prompt_too_long 등이다. 요청은 실패하지 않고 메인이 그대로 진행한다.

### 1.2 트랜스크립트(jsonl) 스키마 — advisor 관련 [로컬]

| 레코드 | 모양 | 비고 |
|---|---|---|
| 켜고 끔 | `type:"attachment"`, `attachment:{type:"advisor_tool", available, model, toolChange:"add"\|"remove"}` | `rendered` 에 위 주입문이 있다 |
| 호출 | `type:"assistant"`, content 블록 `{type:"server_tool_use", id:"srvtoolu_…", name:"advisor", input:{}}` | |
| 결과 | 같은 메시지의 다음 레코드, `{type:"advisor_tool_result", tool_use_id, content:{type:"advisor_redacted_result", encrypted_content}}` | 블록마다 레코드가 따로라서 usage 가 중복 기록된다 → `message.id` 로 중복을 없앤다 |
| 토큰 | `message.usage.iterations[]` 중 `{type:"advisor_message", model, input_tokens, output_tokens, cache_*}` | top-level usage 에는 합산되지 않는다 [문서] |
| 메타 | 모든 assistant 레코드에 `advisorModel` 필드 | 도구가 꺼져 있어도 있다. "켜짐"의 근거로 쓰지 않는다 |
| 사본 | `api-request-blob`·`api-request-shape` 에도 같은 블록 | 요청 사본이다. 세지 않는다 |

- 결과 블록이 없는 호출도 있다(vitrine 1건, 중단으로 추정).
- 8월 sonnet-5 서브에이전트의 호출 5건은 `iterations` 에 advisor 토큰이 없다. 버전 차이로 보이며 [미확인]. 그래서 집계 비용은 하한이다.
- "Declined" 가 jsonl 에 어떤 모양으로 남는지는 관측된 사례가 없다 [미확인].

### 1.3 advisor 실적: 집계 스크립트를 실제로 돌린 결과 [로컬]

`drafts/second-opinion/skills/second-opinion/scripts/advisor-stats.py --all` 로 트랜스크립트 1,396개(서브에이전트 포함)를 읽기 전용으로 읽었다. 2.4초 걸렸다.

- 호출 18건(서브에이전트 8건). 결과는 암호화 17건, 결과 없음 1건.
- advisor 입력 2,439,266 토큰, 출력 91,551 토큰. API 환산 **$13.30**(토큰이 기록되지 않은 6건은 빠짐).

| 세션 | 호출 | 메인 맥락 → advisor 입력 | 1회 $ | 직후 메인 반응 (발췌) |
|---|---|---|---|---|
| vitrine 08-28 (opus 5) | 메인 3 + 중단 1 + 서브 5 | 52k / 181k / 553k | 0.41 / 1.05 / 2.80 | "네 가지 다 타당합니다. 특히 nonce 재사용 규칙 누락은 치명적", "다섯 가지 모두 타당합니다 … 3번은 실제 CSRF 문제" |
| stl-luau 08-31 (opus 5) | 메인 5 (1시간 51분) | 59k → 246k | 0.43 ~ 1.27 | "advisor 지적 두 가지를 검증하겠습니다" |
| claude-doctor 11-10 (opus 5.5) | 메인 1 + 서브 3 (14분) | 317k | 1.33 | 사용자 메모 기준으로 놓친 것 4건(home-sync 가 빠진 링크를 정리하지 않음, lib 의 MANIFEST 포함 여부, symlink rules 로드를 아무도 재지 않음, 세션 기록 주입 경로의 위험) |

이 세션 메인의 1회 호출은 **커밋 직후**였다(L2485 commit → L2489 advisor). 주입문이 말한 "완료라고 믿을 때"의 시점이다.

### 1.4 프로젝트 현황 [로컬]

메인 세션 맥락은 assistant 메시지마다 `iterations[0]` 의 input + cache_read + cache_creation 을 합한 값이다. 30일 커밋은 2026-10-11 이후, 머지를 뺀 수다.

| 저장소 | 성격(지도·audit/03·04) | 30일 커밋 | 메인 맥락 중앙 / p90 / 최대 (k) | 기존 검토 장치 |
|---|---|---|---|---|
| quad | 게시된 UI 렌더러(4.x), 타입 한계 연구 | 274 | 307~412 / 448~734 / 964 | quad-doc-auditor 등 에이전트 2, review-round, codex/agy 위임 |
| stl-luau | 표준 라이브러리, 성능 실측 | 271 | 424 / 812 / 970 | agy 위임, trait-debate |
| table-sim | 앱 | 298 | 392 / 772 / 966 | agy 위임 |
| devplorer | 도구 | 258 | 281~285 / 496~511 / 567 | memory "리뷰는 sonnet, opus 는 요청 시만" |
| tbox | 도구 | 5 | 364 / 811 / 965 | agy 위임 |
| vitrine | web, 암호·인증 | 0 (8월) | 398 / 585 / 618 | - |
| rbvm | 엔진 VM | 0 | 362 / 453 / 475 | 감사 에이전트 2 |
| mrow, moonwave-luau | 소규모 | 0 | 419 / 632 / 681 (mrow) | - |
| claude-doctor | 하네스 정본. `~/.claude` 를 통해 모든 세션에 퍼짐 | 25 | 263 / 410 / 465 | drafts/agents, delegate, debate |
| coderag, luau-kb | rust 도구 / 지식 정본 | 14 / 20 | - | - |

- 세션이 매우 길다. 재개를 포함하면 수백 시간이고, compact 가 7~24번 일어났다. 이제 opus 5.5 의 `autoCompactWindow` 를 500,000 으로 두었으므로, 새 세션의 맥락은 약 50만에서 멈춘다.
- **plan mode 는 쓰지 않는다.** `/tmp` 를 뺀 트랜스크립트 전체에서 `ExitPlanMode` 호출이 0회다. 그래서 "접근 확정 전"을 plan 훅에 맡길 수 없다.
- 반복 실패가 실제로 얼마나 나는지도 쟀다(메인 세션만, 아래 훅의 서명 규칙을 그대로 썼다). 같은 서명이 2회에 닿은 경우는 세션당 0~15회였다. 몇 주에 걸친 세션 기준이다. 대부분의 실행은 서브에이전트에서 일어난다.

### 1.5 현재 설정 [로컬]

- 실제 `~/.claude/settings.json`(`/code/.claude`)
  - **`advisorModel` 이 없다.** 09:29 에 `/advisor off` 를 실행해 트랜스크립트에 remove 첨부가 남았다.
  - `model: opus`, effort `high`, `defaultMode: auto`
  - 훅은 PreToolUse(Bash) 2개다. 정본 `home/.claude/settings.json` 에는 PostToolUse·SessionStart 훅이 더 있고, 아직 apply 하지 않았다.
- 프로젝트 settings 에는 advisor 가 없다(quad `quad-doc-auditor.md` 본문에 단어만 나온다).
- 사용자 레벨 agents 는 없다. 감사자 5개는 `drafts/agents` 에 있다(sonnet 기본, 읽기 전용 3중 장치).
- 정본 CLAUDE.md 의 "코드 리뷰 — 먼저 한다" 절은 프로젝트 memory 의 예산 규칙과 부딪힌다고 이미 지적됐다(audit/10 §2.2).
  - quad: "작은 diff 엔 안 돌림"
  - devplorer: "리뷰는 sonnet"
  - $589 fable 팬아웃 사고가 있었다.
- 환경 변수 [로컬]: 서브에이전트의 Bash 에도 `CLAUDE_CODE_SESSION_ID=<부모 세션>` 이 있다. 리뷰어는 이 값으로 메인 트랜스크립트를 찾는다. 문서에는 없는 동작이라 버전마다 확인한다.

## 2. 세 방식 비교 (trade-off)

1회 비용은 API 환산이다(Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Fable 5.1 $10/$50 per MTok). 구독에서는 이 비율대로 한도가 깎인다고 본다 [추정].

| | advisor Opus 5.5 | advisor Fable | 리뷰어 opus (제안) | 리뷰어 sonnet (제안) | `/debate`·`delegate`(Codex/Gemini) | 검토 없음 |
|---|---|---|---|---|---|---|
| 독립성 | 낮음. 같은 대화를 보고 메인 관점에 끌린다 | 낮음 | 높음. 빈 맥락, 사용자 원문부터 읽음 | 높음 | 가장 높음(다른 회사 모델) | - |
| 맥락 정확도 | 가장 높음(대화 전체) | 가장 높음 | 중간. 원문·diff·주장은 보지만 대화로만 합의된 것은 못 봄 | 중간 | 낮음(브리프만, codex 는 파일을 못 읽음) | - |
| 시점 예측성 | 낮음(모델 판단, 상한 없음) | 낮음 | 높음(훅 2시점 + 규칙 1시점) | 높음 | 사용자 호출 | - |
| 결과를 볼 수 있나 | **아니오(암호화)** | **아니오** | 예, 그대로 전달 | 예 | 예 | - |
| 1회 비용 (메인 맥락 30만) | ≈ $1.35 | ≈ $3.35 | $0.5~1.5 (이 세션 opus Explore 8~21턴 실측 $0.48~1.47) | $0.2~0.6 (sonnet 6~16턴 실측 $0.17~0.58) | 외부 구독 | 0 |
| 비용이 비례하는 것 | **메인 맥락 길이 × 호출 수 × 서브에이전트 수** | 같음 ×2.5 | 검토 범위 | 검토 범위 | 브리프 | - |
| 흔한 실패 | 맥락에 묻힌 오류에 함께 넘어감, 조언을 확인할 수 없음 | 같음 + Fable 동의 필요 | 대화에만 있던 합의를 모름, 범위 밖 놓침 | 깊은 추론 약함 | 맥락 부족으로 일반론 | 사용자가 찾게 됨 |

손익분기 [추정]
- advisor Opus 5.5 의 1회 비용은 대략 `4 × 맥락(M) + 0.15` 달러다.
  - 맥락 10만이면 $0.55, 30만이면 $1.35, 50만이면 $2.15.
- 리뷰어 opus 는 메인 맥락과 무관하게 $0.5~1.5 다. 그래서 **메인 맥락이 20만~30만을 넘으면 advisor 가 1회당 더 비싸다.**
- 이 사용자 세션의 맥락 중앙값은 26만~42만이므로 대부분 손익분기 위에 있다.
- 게다가 advisor 는 작업마다 두 번 이상 불리고 서브에이전트로 곱해진다.

리뷰어가 advisor 보다 약한 곳과 그 보완
- 이 세션에서 advisor 가 잡은 4건은 "정본·사본 동기화, 아무도 재지 않은 주장, 주입 경로" 같은 종류였다. 대화 전체를 봐야 보이는 것들이다.
- 보완 1: `user-asks.py`. 사용자 원문, 작업 중에 끼워 넣은 지시, 질문에 대한 답을 원문 그대로 뽑는다.
- 보완 2: 브리프의 "검증할 주장"과 "가장 자신 없는 곳". 메인이 하려는 말을 반증 대상으로 넘긴다.
- 보완 3: 필요하면 `user-asks.py --claims K` 로 메인의 마지막 응답 K 개를 "근거 아님" 표시를 붙여 준다.
- 남는 구멍: 메인 산문에서만 합의되고 파일·사용자 원문에 없는 결정은 놓칠 수 있다. 이 구멍이 실제로 얼마나 큰지는 §8-1 의 재현 실험으로 잰다.

## 3. 사용 기준 (예측 가능한 규칙)

### 3.1 저장소 등급 (`HARNESS_REVIEW_TIERS`, 초안 `home/harness.env.fragment`)

| 등급 | 저장소 | 근거 |
|---|---|---|
| high | quad, stl-luau, vitrine, claude-doctor | 게시된 공개 API, 성능 주장, 보안·암호, 모든 세션에 퍼지는 하네스 정본. advisor 가 실제 결함을 잡은 곳(vitrine, claude-doctor) |
| mid | table-sim, devplorer, tbox, rbvm, coderag, VideoSync | 활발한 앱·도구. 결함이 해당 저장소 안에 머문다. devplorer memory "리뷰는 sonnet" |
| low | luau-kb, moonwave-luau, mrow | 문서·지식 위주, 소규모 |
| off(기본) | `-agy`, `-codex`, `-scratch`, `-proto`, `/tmp` 실험 | 위임 작업장이나 실험 |

### 3.2 작업 유형 × 등급

| 작업 | high | mid | low | 비고 |
|---|---|---|---|---|
| 조사·읽기·질문 답변 | 없음 | 없음 | 없음 | 검토할 산출물이 없다 |
| 문서만, 기계적 변경(이름 일괄 변경, 포맷) | 없음 | 없음 | 없음 | 훅 알림이 와도 한 줄로 사양 |
| 접근 확정 전: 되돌리기 어려운 설계, 공개 API·데이터 형식·보안, 여러 파일·여러 단계 | **opus 리뷰어 (plan)** | sonnet (plan) | 없음 | 메인 판단. 사용자가 plan mode 를 쓰지 않으므로 훅이 없다 |
| 같은 실패 2회 | opus (stuck) | sonnet | sonnet | 훅이 알림. 오류가 다음 행동을 정해 주면(오타, 파일 없음) 사양 |
| 완료·커밋 전, diff ≥ 임계(high 40줄, mid 200줄) | **opus (done)** | sonnet (done) | 없음 | 훅이 알림. 작업 단위당 1회 |
| 취향 판단(이름, API 모양), 근거가 팽팽함 | `/debate` | `/debate` | - | 다른 회사 모델. 사용자 확인 뒤 |
| 릴리스 전, 큰 구조 변경 뒤 | `/audit`(관점별), 웹은 `/security-review` | `/audit` | - | 기존 정본 "코드 리뷰" 절 |
| 사용자가 "검토 받아" | 등급대로 | 등급대로 | sonnet | |

- 예산 지침이 우선한다. 프로젝트 CLAUDE.md·memory 가 더 좁으면 한 단계 낮추고 그렇다고 밝힌다.
- 검토 강도는 등급이 정한다. 시점이 왔다고 감사를 대규모로 키우지 않는다(정본 "코드 리뷰" 절 마지막 줄과 같다).

### 3.3 advisor 를 쓰는 예외 (사용자가 명시할 때만)

- 대상: 맥락이 짧고(15만 미만) 대화 맥락이 결정적인 고위험 세션. 예: 처음부터 설계를 함께 잡는 새 세션.
- 방법: `claude --advisor opus` 로 **그 세션에만** 켠다. `/advisor opus` 는 사용자 설정에 저장돼 다음 세션까지 켜지므로 쓰지 않는다.
- Fable advisor 는 권하지 않는다. 비용이 2.5배이고, 역시 암호화되며, 별도 동의가 필요하다.
- advisor 를 켠 세션에서는 서브에이전트를 많이 띄우기 전에 끈다. 실행 중인 서브에이전트에도 바로 적용된다 [로컬].

## 4. 도구화 조사

### 4.1 호출 시점에 쓸 수 있는 훅 이벤트 [문서]

| 이벤트 | 쓸 수 있는 것 | 채택 |
|---|---|---|
| `PostToolUseFailure` | 입력 `tool_name, tool_input, error, is_interrupt, duration_ms`. `additionalContext` 는 모델에게 간다. 문서 권고는 "`Exit code N` 첫 줄과 tool_name 으로 키를 잡고, 나머지는 표시용". Bash 0 아닌 종료도 여기로 온다(문서 예: npm test) | **채택**: 같은 서명 2회째에 stuck 알림 |
| `PreToolUse` (matcher `Bash`) | `git commit` 직전. staged diff 를 읽어 크기를 잰다 | **채택**: done 알림(막지 않음) |
| `SubagentStop` (matcher = agent_type) | 리뷰어가 끝난 시각을 기록. 입력에 `agent_type, last_assistant_message, agent_transcript_path` | **채택**: 최근에 검토했으면 알림 생략 |
| `Stop` | `stop_hook_active`, 8회 연속 계속 상한. `additionalContext` 를 내면 대화가 이어진다 | 선택(기본 끔): 턴마다 끼어드는 비용이 있다 |
| `PreToolUse` (matcher `ExitPlanMode`) | 하네스가 계획 본문을 `tool_input` 에 넣어 준다. deny + 표시 줄로 재시도(pghqdev 방식) | 선택(기본 끔): plan mode 사용 0회 |
| `type:"agent"` 훅 (Stop 등) | 서브에이전트가 최대 50턴 돌며 검증하고 `{ok, reason}` 을 낸다. 기본 timeout 60초, 기본 모델은 "background" 모델이며 `model` 로 바꿀 수 있다 | **채택하지 않음**(아래) |
| `UserPromptSubmit`, `PostToolBatch` | 맥락 주입 | 쓰지 않음 |

agent 훅을 쓰지 않는 이유
- 실험 기능이다.
- Stop 은 matcher 가 없어 **턴마다** 서브에이전트가 돈다. 거르는 장치가 없다.
- 결과가 `reason` 한 줄로만 돌아온다. 그러면 원문 전달도, 원장 기록도 할 수 없다.
- 지금의 command 훅이 "알림 → 메인이 리뷰어 호출"로 같은 시점을 더 싸게 잡는다.
- 다만 원장 데이터가 쌓인 뒤 high 저장소에서 A/B 비교 후보로는 남긴다.

### 4.2 디렉터리·작업 유형별로 advisor 를 켜고 끄기

- advisor 를 저장소마다 켜는 방법은 프로젝트 `.claude/settings.json` 의 `advisorModel` 이다 [문서: 설정 파일]. 하지만 다른 저장소는 읽기 전용 원칙이고, 이 제안은 advisor 를 끄는 쪽이라 쓰지 않는다.
- 훅으로 세션 도중 advisor 를 켜고 끄는 API 는 찾지 못했다 [미확인]. `ConfigChange`·`PreModelSwitch` 는 모델 전환용이다.
- 그래서 "디렉터리별 조절"은 advisor 가 아니라 **리뷰어 등급표**로 한다. 훅이 `git rev-parse --git-common-dir` 로 저장소를 찾으므로 worktree 안에서도 본 저장소의 등급을 쓴다.

### 4.3 참고 플러그인에서 가져온 것 (읽기만 했고 설치·실행하지 않음)

| 플러그인 | 방식 | 가져온 것 / 다르게 한 것 |
|---|---|---|
| pandysp/second-opinion (`pandysp/claude-plugins` 마켓) | 채널 우선순위: 대화 전체를 읽는 advisor > 새 맥락 동급 서브에이전트(여럿) > "자기비판"이라고 밝힌 대체. 결과는 **흡수해서 자기 말로** 제시. "Hold the Line" 점검(원래 입장을 다시 말해 보고 반박인지 재정의인지 확인) | 채널 순서 대신 비용과 가시성 때문에 서브에이전트를 기본으로 했다. 결과는 사용자 요구대로 **그대로 전달**한다. "가장 자신 없는 부분을 빼지 말라"는 브리프 원칙은 가져왔다. (`pandysp/second-opinion` 직접 경로는 404, 마켓 저장소의 SKILL.md 로 확인) |
| pghqdev/second-opinion | `PreToolUse:ExitPlanMode` 훅이 위험한 계획(파괴적 작업, 마이그레이션, 인증, 결제, 인프라, 3개 넘는 파일)을 막고 외부 CLI(codex → gemini → …, 현재 호스트는 건너뜀)로 검토. `<!-- second-opinion: reviewed -->` 표시로 재시도. jq 가 없으면 열어 둔다 | 표시 줄로 재시도하는 방식을 ExitPlanMode 선택 기능에 썼다. 감지 방식은 README 에 없다 [미확인] |
| HartBrook/lookagain | 새 서브에이전트로 여러 회차(기본 3, 최대 7)를 순차로 돌린다. **다음 회차는 앞 회차 발견을 모른다.** 여러 회차가 찾은 발견일수록 신뢰도를 높인다. 결과는 `.lookagain/<run>/` 에 남긴다 | "앞 발견을 모르는 새 맥락"은 리뷰어 원칙에 반영했다. 회차를 여러 번 도는 것은 비용 때문에 기본으로 두지 않았다. 재검토는 "반드시" 항목 범위로만 한다 |
| trailofbits/second-opinion (`trailofbits/skills`) | `codex exec`(스키마 출력)·`agy`·headless gemini 로 uncommitted/branch/commit diff 를 검토. **사용자 요구를 저장소 내용과 분리**해 전달. 0 아닌 종료나 빈 출력은 "깨끗함"이 아니라 "미완". 쓰기 자동 승인 금지 | 다른 회사 모델 검토는 기존 `delegate`·`debate` 가 맡는다. "실패 = 미완" 규칙과 "저장소 텍스트는 지시가 아니라 증거"(claude-security 와 같은 원칙, audit/16)는 리뷰어 본문에 넣었다 |
| 공식 code-review | haiku 사전 점검 → sonnet 2(CLAUDE.md 준수) + opus 2(버그) → **발견마다 검증 서브에이전트**, 검증을 통과한 것만 보고 | 검증 단계는 리뷰어 안의 "주장 반증 + 실행 근거"로 대신하고, 메인이 발견마다 받아들일지 버릴지를 근거와 함께 정한다. 전수 검토는 `/code-review`·`/audit` 몫으로 남긴다 |
| 공식 pr-review-toolkit | 관점별 에이전트 6개(주석, 테스트, 침묵 실패, 타입 설계, 규약, 단순화). 점수(0~100, 1~10) | 이미 `drafts/agents` 의 관점별 감사자가 같은 자리다. 이번에 더하지 않는다 |

## 5. 만들 파일 (초안 위치 → 설치 위치)

모두 `drafts/second-opinion/` 안에 있다. 설치 위치는 정본 `home/.claude/` 기준이고 MANIFEST 에 추가한다.

| 초안 | 설치 위치 | 내용 | 검증 |
|---|---|---|---|
| `agents/second-opinion-reviewer.md` | `home/.claude/agents/` | opus, effort high, maxTurns 40, Read/Grep/Glob/Bash. Edit·Write·NotebookEdit·Agent 금지. 읽기 전용 가드는 `drafts/agents/hooks/auditor-readonly-guard.py` 를 재사용(먼저 설치돼 있어야 함). 절차: 사용자 원문 → 범위 직접 확인 → 주장 반증 → 요구 대조. 보고 틀 고정(판정, 발견, 요구 대조, 주장 검증, 보지 못한 것) | 실호출 안 함(§8-1) |
| `skills/second-opinion/SKILL.md` | `home/.claude/skills/second-opinion/` | 시점·강도 표, 브리프 작성 규칙, 호출, 결과 처리(그대로 전달 + 받아들임/버림 + 원장), 측정 | - |
| `skills/second-opinion/templates/brief.md` | 같은 곳 | 5~15줄 브리프 틀(종류, 범위, 목표, 제약, 기각된 갈래, 검증할 주장, 가장 자신 없는 곳) | - |
| `skills/second-opinion/scripts/user-asks.py` | 같은 곳 | 트랜스크립트에서 사용자 원문만 추출. 일반 발언, 작업 중 추가 지시, 질문에 대한 답, 슬래시 명령을 뽑고 서브에이전트 보고·리마인더·compact 요약은 뺀다. 기준은 `plugins/session-log` 의 `classify` 를 옮긴 것이다. `--since-compact`, `--last`, `--claims` | 이 세션에서 실행: 36개 추출, compact 뒤 15개 |
| `skills/second-opinion/scripts/advisor-stats.py` | 같은 곳 (또는 `/harness-doctor --usage`) | advisor 호출, 토글, 결과 종류, 토큰, API 환산 비용, 직후 메인 반응, `--ledger` 사람 판정 병합, `--subagent-costs` 비교 | 이 세션·전체로 실행(§1.3) |
| `skills/second-opinion/scripts/review-ledger.py` | 같은 곳 | 검토 원장 `add`/`stats`. `~/.local/state/claude-second-opinion/ledger.jsonl` 에 저장(저장소 밖, append 만). 종류·검토자·트리거별 발견, 채택, 채택률 | 임시 디렉터리에서 add·stats 실행 |
| `hooks/second-opinion-nudge.py` | `home/.claude/hooks/` | §4.1 채택 이벤트. 서브에이전트 안에서는 아무것도 하지 않음. dedup 은 session+compact 회차. done 알림 뒤 90분 쿨다운. `<harness-hook name="second-opinion" level="warn">` 영어 | `hooks/tests/test-second-opinion-nudge.py` **17/17 통과** |
| `home/settings.hooks.json` | `home/.claude/settings.json` 의 hooks 에 합침 | PreToolUse(Bash\|ExitPlanMode), PostToolUseFailure, SubagentStop(second-opinion-reviewer), Stop | JSON 문법만 확인 |
| `home/harness.env.fragment` | `home/.claude/harness.env` 에 덧붙임 | 등급표, 기본 off, 줄 임계, 쿨다운, Stop·Plan 스위치 | - |
| `home/CLAUDE.md.fragment.md` | `home/.claude/CLAUDE.md` | "검토(second opinion)" 5줄. 기존 "코드 리뷰" 절과 합칠지는 사용자 결정(§8) | - |
| (갱신) `home/.claude/HOOK-MESSAGES.md` "현재 배정" 표 | - | second-opinion: stuck 알림 warn, done 알림 warn, plan deny action | 아직 고치지 않음 |

## 6. 예상 비용 영향 [추정]

**제안안.** git 이력(최근 30일)으로 커밋 알림 횟수를 거꾸로 셌다.
- 셈법: 등급 임계 이상인 커밋 가운데 90분 안에 앞선 알림이 없던 것만 센다.
- 이 셈은 실제 알림 횟수의 **상한**이다. 메인이 사양해도 쿨다운이 걸리고, 서브에이전트의 커밋은 알리지 않기 때문이다.

| 저장소 | 등급 | 임계 이상 커밋 | 알림(90분 창) | 하루 | 리뷰어 | 하루 비용 |
|---|---|---|---|---|---|---|
| quad | high | 190 / 274 | 48 | 1.6 | opus ~$1 | ~$1.6 |
| stl-luau | high | 188 / 271 | 32 | 1.1 | opus | ~$1.1 |
| claude-doctor | high | 19 / 25 | 2 | 0.1 | opus | ~$0.1 |
| table-sim | mid | 122 / 298 | 24 | 0.8 | sonnet ~$0.4 | ~$0.3 |
| devplorer | mid | 105 / 258 | 21 | 0.7 | sonnet | ~$0.3 |
| tbox·coderag | mid | 13 / 19 | 3 | 0.1 | sonnet | ~$0.04 |

- stuck 알림: 메인 세션에서 같은 서명이 2회에 닿은 경우가 몇 주 동안 0~15회였다. 하루 0.5회 미만이므로 약 $0.2.
- plan(메인 판단): high 저장소에서 하루 0.5회로 잡으면 약 $0.5.
- **합계는 하루 약 $3~5(API 환산), 30일이면 $100~150 이다.** 알림을 사양하면 줄어든다.

**advisor 상시(비교).**
- 관측된 빈도: stl-luau 메인은 1시간 51분에 5회(시간당 약 2.7회), vitrine 은 2시간에 메인 3회와 서브에이전트 5회, claude-doctor 는 14분에 4회.
- 맥락 30만~50만에서 1회 $1.3~2.2 → 활성 1시간에 **메인만 $3~6**, 여기에 서브에이전트 몫이 더해진다.
- 한 저장소를 하루 4시간 활발히 쓰면 $12~24 이고, 저장소가 여럿이면 그만큼 곱해진다.

**메인 쪽 비용.** 훅 알림은 영어 2~3줄이다(약 80토큰). 리뷰어 보고를 그대로 붙이는 것은 1~3k 토큰이다. 리뷰어는 별도 맥락이라 메인의 캐시를 깨지 않는다.

**구독 한도.** 달러는 상대 비교용이다. 실제 소비는 `/usage` 와 `review-ledger.py stats` 로 첫 2주를 본 뒤 임계를 조정한다.

## 7. 미확인 / 확인 필요

1. Opus 5/5.5 advisor 의 암호화 결과를 **Ctrl+O 로 볼 수 있는지**. 문서는 "readable guidance 가 있을 때"라고만 한다. UI 에서 한 번 확인해야 한다.
2. "Declined" 결과가 jsonl 에 어떤 블록으로 남는지. 관측 사례가 없다.
3. 8월 서브에이전트 advisor 호출에 `iterations` 토큰이 없던 이유(버전 차이 추정). 그래서 집계 비용은 하한이다.
4. 서브에이전트 frontmatter 의 `disallowedTools: advisor` 로 advisor 상속을 막을 수 있는지. 문서에 없다.
5. 사용자 지시("advisor 는 X 때만")가 주입문의 "최소 두 번"보다 우선하는지. 문서는 "지시로 더 자주/덜 부르게 할 수 있다"고만 한다.
6. `CLAUDE_CODE_SESSION_ID` 가 서브에이전트 Bash 에 들어오는 동작. 2.1.316 로컬에서만 확인했고 문서에는 없다. 없어도 브리프에 경로를 적거나 `--transcript` 로 대체할 수 있다.
7. `SubagentStop` 입력의 `session_id` 가 메인 세션 값인지. 다르면 "최근 검토 있음"을 인식하지 못해 알림이 한 번 더 나올 뿐이다. 적용한 뒤 상태 파일로 확인한다.
8. `PostToolUseFailure` 의 `error` 문자열 형식은 도구마다 다르다. 문서도 "첫 줄과 tool_name 외에는 안정적이지 않다"고 한다. 서명 정규화(숫자 → `#`)가 과하게 묶거나 덜 묶을 수 있으니 원장으로 조정한다.
9. 처음부터 advisor 도구가 `defer_loading` 으로 요청에 들어 있던 이유. 세션 시작 때 `advisorModel` 이 저장돼 있었는지는 기록이 없다.
10. 구독 플랜에서 advisor 와 서브에이전트 토큰이 한도에서 얼마나 깎이는지(가중치). 문서에는 "포함된다"만 있다.

## 8. 사용자 결정이 필요한 것

1. **재현 실험(약 $1~1.5)을 할지.** 이 세션의 advisor 호출 시점(커밋 `8039225` 직후)을 리뷰어 opus 로 재현해, 놓친 4건을 다시 잡는지 잰다.
   - 4건을 잡으면 advisor 를 대체해도 된다는 근거가 된다.
   - 놓치면 그 차이를 보고 브리프의 "검증할 주장"이나 `--claims` 를 기본으로 켤지 정한다.
2. **advisor 를 어떻게 끌지**
   - (a) 지금처럼 `advisorModel` 없이 둔다. 권장. `claude --advisor opus` 일회 사용이 가능하다.
   - (b) `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` 로 완전히 끈다. 실수로 켤 일은 없지만 일회 사용도 막힌다.
3. **등급표**(§3.1): 특히 claude-doctor 를 high 로 둘지, vitrine·VideoSync 처럼 활동이 없는 저장소를 지금 등급에 넣어 둘지.
4. **임계**: high 40줄, mid 200줄, 쿨다운 90분. 그리고 Stop 알림(기본 끔)을 2주 원장을 본 뒤 켤지.
5. **CLAUDE.md**
   - 새 "검토" 절(5줄)을 기존 "코드 리뷰 — 먼저 한다" 절과 **합칠지**, 따로 둘지.
   - 합치면 audit/10 §2.2 의 예산 충돌(규모 기준, sonnet 기본)도 같이 정리된다.
6. **리뷰어 기본 모델**: frontmatter 기본을 opus 로 둘지, sonnet 으로 두고 high 일 때만 호출 인자로 opus 를 줄지.
   - 감사자 설계(`drafts/agents` §5)는 "inherit 금지, 기본 sonnet, 깊을 때만 opus" 였다.
   - 일관성을 원하면 sonnet 기본이 맞다.
7. **설치 순서 의존**: 리뷰어의 읽기 전용 가드는 `drafts/agents/hooks/auditor-readonly-guard.py` 다. 감사 에이전트 묶음(`drafts/agents`, PLAN 의 감사 에이전트 항목)과 함께 들일지, 가드만 먼저 들여 리뷰어를 앞세울지.

## 9. 적용 순서 (승인 뒤)

1. §8-1 재현 실험(리뷰어 초안을 임시로 `--agents` 나 `/tmp` 프로젝트에 두고 1회).
2. 리뷰어, 스킬, 스크립트를 `home/.claude/` 정본으로 옮기고 MANIFEST 에 추가한다. `HOOK-MESSAGES.md` 배정 표도 갱신한다.
3. 훅과 harness.env 조각을 합치고 테스트를 `home/.claude/hooks/tests/` 로 옮긴다. 사용자가 `tools/home-sync.sh diff` → `apply` 한다.
4. 2주 뒤 `review-ledger.py stats` 와 `/usage` 로 임계와 등급을 조정한다. 채택률이 낮은 트리거는 끈다.
