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
- **§11 분리 실험 뒤 갱신: 검토를 두 도구로 나눈다.** advisor 와 리뷰어의 차이는 모델보다 주입된 맥락에서 왔다(방향만, 표본 작음).
  - `second-opinion:context`(대화를 이어받은 눈): 전환점에 쓴다. advisor 의 4건 중 완전 회수 3/12(감사형은 0/12). 기본은 fork 로, 30만 토큰 맥락에서 1회 약 $0.2~0.35 [추정]이다.
  - `second-opinion:audit`(diff 감사): 커밋 전, 반복 실패, 구현 검증에 쓴다. 실측 버그는 이쪽만 잡았다.
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

`drafts/second-opinion/skills/audit/scripts/advisor-stats.py --all`(§11 뒤 경로) 로 트랜스크립트 1,396개(서브에이전트 포함)를 읽기 전용으로 읽었다. 2.4초 걸렸다.

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
| `skills/audit/SKILL.md` | `home/.claude/skills/second-opinion/` | 시점·강도 표, 브리프 작성 규칙, 호출, 결과 처리(그대로 전달 + 받아들임/버림 + 원장), 측정 | - |
| `skills/audit/templates/brief.md` | 같은 곳 | 5~15줄 브리프 틀(종류, 범위, 목표, 제약, 기각된 갈래, 검증할 주장, 가장 자신 없는 곳) | - |
| `skills/audit/scripts/user-asks.py` | 같은 곳 | 트랜스크립트에서 사용자 원문만 추출. 일반 발언, 작업 중 추가 지시, 질문에 대한 답, 슬래시 명령을 뽑고 서브에이전트 보고·리마인더·compact 요약은 뺀다. 기준은 `plugins/session-log` 의 `classify` 를 옮긴 것이다. `--since-compact`, `--last`, `--claims` | 이 세션에서 실행: 36개 추출, compact 뒤 15개 |
| `skills/audit/scripts/advisor-stats.py` | 같은 곳 (또는 `/harness-doctor --usage`) | advisor 호출, 토글, 결과 종류, 토큰, API 환산 비용, 직후 메인 반응, `--ledger` 사람 판정 병합, `--subagent-costs` 비교 | 이 세션·전체로 실행(§1.3) |
| `skills/audit/scripts/review-ledger.py` | 같은 곳 | 검토 원장 `add`/`stats`. `~/.local/state/claude-second-opinion/ledger.jsonl` 에 저장(저장소 밖, append 만). 종류·검토자·트리거별 발견, 채택, 채택률 | 임시 디렉터리에서 add·stats 실행 |
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

## 9. 재현 실험 결과 (§8-1)

날짜 2026-11-10, claude 2.1.316. 리뷰어 초안(`drafts/second-opinion/agents/second-opinion-reviewer.md`)으로 advisor 호출 시점을 재현했다. 대상은 이 세션(c9a9e895) L2490, 커밋 `8039225` 직후다. 결과는 **opus 2회, sonnet 1회 모두 4건 중 완전히 잡은 것이 0건**이었다. 대신 셋 다 advisor 가 잡지 못한 다른 문제를 찾았다.

### 9.1 방법 [로컬]

- **시점 복원**
  - claude-doctor `8039225`, luau-kb `3ee4a16`(18:07, 호출 18:16:05 직전 커밋), coderag `1ae6265`(18:11)을 `/tmp/so-replay/<이름>` 에 복원했다.
  - `git worktree` 대신 독립 클론을 쓰고, `main` 외 ref 와 reflog 를 지웠다. worktree 는 저장소의 이후 ref 가 그대로 보여서 `git log --all` 로 미래 커밋을 볼 수 있기 때문이다.
  - 그 시점에 미커밋이던 `plugins/`(session-log 작업 중)와 luau-kb 의 미커밋 작업은 복원하지 못했다.
  - 실제 설치본 `~/.claude` 는 현재 상태를 그대로 썼다. hooks·CLAUDE.md 는 15:5x 이후 바뀌지 않아 그 시점과 같다. **예외는 settings.json 이다**(20:51 수정, `autoMode` 블록 추가). 이 차이는 §9.3 에 적었다.
- **누출 차단**: `--settings` 에 PreToolUse 가드를 걸었다.
  - 막은 것: 원본 저장소 3개, `~/.claude/projects`·`plugins` 등 런타임 상태, 넓은 경로를 재귀로 훑는 검색, 실제 홈으로의 `home-sync apply`
  - 나머지 읽기 전용 강제는 `drafts/agents/hooks/auditor-readonly-guard.py` 에 넘겼다.
  - 리뷰어가 막힌 경로에 접근하려 한 시도: sonnet 1회(`~/.claude/projects`), opus2 1회(재귀 검색)
- **실행**: `claude -p --agents <초안 JSON> --agent second-opinion-reviewer --model <opus|sonnet> --effort high --allowedTools Read Grep Glob Bash --no-session-persistence`
  - 초안 본문은 그대로 썼다. 바꾼 것은 추출 헬퍼 경로 하나뿐이다.
  - 사용자 원문은 리뷰어가 직접 뽑았다. 그 시점까지 자른 트랜스크립트에 `user-asks.py --transcript` 를 돌렸고, 34개가 나왔다.
- **브리프**(템플릿 꼴, 약 25줄)
  - 넣은 것
    - 종류 `done`, 목표("apply 안내 직전 최종 점검"), 제약
    - 병행 작업 한 줄: session-log 플러그인과 luau-kb 재편, "이 검토 범위 밖"
    - 검증할 주장 5개: 메인이 L2510 에서 실제로 한 말에서 advisor 영향분을 뺀 것
    - 가장 자신 없는 곳: "auto-compact 미실측". 핸드백 보고에 이미 있던 내용이다
  - **advisor 의 4건은 넣지 않았다.**
  - 원문: `/tmp/so-replay-kit/brief.md`

### 9.2 4건 회수

| advisor 가 잡은 것 | opus #1 | opus #2 | sonnet #1 |
|---|---|---|---|
| 1. home-sync 가 MANIFEST 에서 빠진 항목(고아 링크)을 정리하지 않음 | 부분(약): `roblox-luau` 링크 대상이 없다는 것만 "참고"로 적음. 정리 기능이 없다는 데까지는 가지 않음 | 못 잡음(링크는 안 봤다고 적음) | 못 잡음 |
| 2. 훅이 import 하는 `lib/*` 와 MANIFEST 대조 | 부분: 새 lib 가 MANIFEST 에 있다고 확인함. import 의존과 고장 양상은 짚지 않음 | 부분: 같음. 설치본에 `lib/` 가 없다는 점은 봄 | 부분(약): "새 훅 2개는 MANIFEST 에 있다"까지만 |
| 3. 사용자 레벨 symlink rules(paths 있음)가 실제로 로드되는지 아무도 재지 않음 | 못 잡음 | 못 잡음 | 못 잡음 |
| 4. session-log 의 SessionStart·UPS 주입은 user turn 이라 래퍼 필수, 인계 텍스트가 주입 경로가 됨 | 못 잡음 | 못 잡음 | 못 잡음 |
| (덧) auto-compact 미검증이지만 apply 를 막을 사유는 아님 | 잡음. 바이너리를 정적으로 읽어 "같은 경로일 가능성"까지 감 | 잡음 | 잡음. 확인할 로그를 남기자고 제안함 |
| (덧) rules 언어 질문이 미결 | 못 잡음 | 못 잡음 | 못 잡음 |

- 2번은 결과가 "문제 없음"인 점검이다. advisor 도 점검을 권했을 뿐이고, 메인이 확인해 보니 모두 들어 있었다(L2505). 그래서 MANIFEST 등재를 직접 확인한 것은 "부분"으로 쳤다.
- "덧"의 auto-compact 는 브리프의 "가장 자신 없는 곳"에 있었으니 회수로 치지 않는다.
- **놓친 이유** [추정]
  - 4번과 rules 질문은 브리프가 "범위 밖"이라고 적은 영역(session-log)에 있거나, 대화 흐름에만 있었다(메인이 사용자에게 던질 질문).
  - 3번은 diff 에 없는 "아직 아무도 재지 않은 전제"다. 사용자 원문에서 rules 자동 로드를 물은 곳(L349)에서 출발해 따라가야 나온다.
  - advisor 는 대화 전체를 봐서 이것들이 보였다. 리뷰어는 브리프·diff·사용자 원문만 봤고, 브리프가 범위를 좁혔다.

### 9.3 새 발견 (advisor 가 언급하지 않은 것)

| 발견 | 누가 | 확인 |
|---|---|---|
| **apply 하면 설치본 settings.json 의 `autoMode.environment`(25항목)가 사라진다.** `apply` 는 파일을 통째로 `cp` 한다(`.bak` 은 남는다) | 셋 다. opus 둘은 "반드시", sonnet 은 "권장" | **재현 시점의 발견으로는 무효다.** 설치본은 20:51 에 수정됐고, 호출 시점(18:16) 이전 트랜스크립트에는 설정 키로서의 `autoMode` 가 없다. 대신 **지금은 맞다.** 정본 HEAD 에 `autoMode` 0건, 설치본 1건, `tools/home-sync.sh:168` 은 `cp -p`. 다음 apply 전에 사용자가 정해야 한다 |
| compact 회차가 오르면 structure-reminder 의 "성장" 기준점이 새로 잡혀, 조금씩 늘어나는 파일의 성장 알림이 사라진다. 알림 문구의 "this session"도 실제와 다르다 | opus #1(프로브로 재현, 권장), sonnet(참고) | 재현했다. 999→1199줄에서 rearm 이 없으면 `grew 799 -> 1199 (+400) this session`, rearm 이 있으면 warn 만 나온다. audit/17 §5 와 HOOK-MESSAGES.md 에 "참고"로 적힌 절충이다. 다만 이 훅이 생긴 이유(692→4,101줄)와 부딪힌다는 점은 처음 지적됐다. 지금 HEAD 의 `structure-reminder.py:245-251` 도 같은 코드다 |
| apply 범위가 이번 커밋보다 크다. structure-reminder 가 처음 켜지고, rules 2개·harness.env·lib·CLAUDE.md 전면 교체가 함께 들어간다 | opus #2, sonnet | 맞다. 설치본 hooks 에는 2개만 있고 `lib/`·`rules/` 는 없다 |
| HOOK-MESSAGES.md 와 audit/17 은 배경을 "2줄"이라고 적었는데, CLAUDE.md 에 들어간 것은 1줄이다(효과 실측은 2줄로 함) | opus 둘 | 맞다(`audit/17:36,51`, `HOOK-MESSAGES.md:9`) |
| SessionStart 출력 위치를 audit/17 표와 HOOK-MESSAGES.md 가 다르게 적었다 | 셋 다 | 문서 표현만 어긋남. 결론(래퍼 필요)은 같다 |
| 서브에이전트에서 compact 하면 SessionStart 가 불리지 않아 회차가 오르지 않는다 | opus #1 | 바이너리를 정적으로 읽은 결과다. 미실측 |
| HOOK-MESSAGES.md 는 MANIFEST 밖이라(의도) 다른 저장소 세션이 규약을 찾을 길이 없다 | opus #2 | 맞다. 영향 판단은 사용자 몫 |
| 그 밖에: 안 쓰는 `sid` 변수, heavy-proc-guard·bypass 자동 테스트 없음, 회차 상태 파일 정리 없음 | opus #2, sonnet | 참고 수준 |

### 9.4 비용과 시간 (API 환산, `total_cost_usd`)

| 실행 | 비용 | 시간 | 턴 | 판정 |
|---|---|---|---|---|
| advisor 1회(원래) | $1.33 | 약 66초 | — | — |
| opus #1 | $1.17 | 210초 | 29 | 고친 뒤 진행 |
| opus #2 | $0.96 | 198초 | 21 | 고친 뒤 진행 |
| sonnet #1 | $0.42 | 103초 | 16 | 고친 뒤 진행 |
| 합계(스모크 haiku $0.003 포함) | $2.55 | | | 상한 $4 안 |

### 9.5 해석

- **"리뷰어로 advisor 를 대체해도 된다"는 이번 실험으로는 뒷받침되지 않는다.** advisor 의 강점은 대화에만 있던 맥락을 쓰는 데 있었다(진행 중인 다른 작업에 미칠 영향, 아직 재지 않은 전제, 사용자에게 걸린 질문). 리뷰어는 이 셋을 하나도 회수하지 못했다.
- **리뷰어도 쓸모가 있었다.** 리뷰어의 강점은 실측이다. 프로브, 바이너리 grep, 정본과 설치본 diff 를 직접 돌렸다. 그 결과 advisor 가 놓친 진짜 문제를 찾았다. 하나는 성장 알림이 사라지는 문제(재현함)이고, 다른 하나는 apply 범위다. `autoMode` 는 재현 오염이지만 지금 시점에서는 맞는 경고다. advisor 와 리뷰어가 잡는 문제는 겹치지 않고 서로를 보완했다.
- **opus 와 sonnet**
  - 4건 회수: 차이가 없었다.
  - 새 발견: opus 가 깊었다. opus #1 은 프로브로 재현했고 "반드시"와 "권장"을 갈랐다. sonnet 은 같은 문제를 "참고"로만 적었다.
  - 비용: sonnet 은 opus 의 약 40%, 시간은 절반이었다.
  - "기본 sonnet, high 만 opus"(§8-6)와 어긋나지 않는다.
- **브리프에 반영할 것**: 맥락 손실을 줄이려면 다음 두 가지가 필요하다.
  - **병행 작업을 "범위 밖"으로 적지 말고 "이 변경이 영향을 줄 수 있는 곳"으로 넘긴다.** 이번에 4번을 놓친 직접 원인으로 보인다.
  - `user-asks.py --claims` 로 메인의 미결 질문과 약속을 함께 넘긴다.
  - 이 두 가지를 넣고 다시 재 볼지는 사용자 결정이다. 같은 방법이면 1회에 $0.4~1.2 다.
- **이 실험의 한계**
  - 시점마다 1~2회만 돌렸다.
  - 미커밋 `plugins/` 와 그 시점의 설치본 settings.json 은 복원하지 못했다.
  - 판정(완전/부분/못 잡음)은 메인 한 사람이 매겼다.

산출물(커밋하지 않음)
- 키트: `/tmp/so-replay-kit/`(브리프, 가드, 에이전트 JSON, 자른 트랜스크립트)
- 원시 출력: `/tmp/so-replay-out/{opus1,opus2,sonnet1}.jsonl`
- 임시 프로젝트 키 `~/.claude/projects/-tmp-so-replay-claude-doctor/`: `--no-session-persistence` 를 줬는데도 tool-results 1개가 남았다

## 10. 적용 순서 (승인 뒤)

1. §8-1 재현 실험(리뷰어 초안을 임시로 `--agents` 나 `/tmp` 프로젝트에 두고 1회).
2. 리뷰어, 스킬, 스크립트를 `home/.claude/` 정본으로 옮기고 MANIFEST 에 추가한다. `HOOK-MESSAGES.md` 배정 표도 갱신한다.
3. 훅과 harness.env 조각을 합치고 테스트를 `home/.claude/hooks/tests/` 로 옮긴다. 사용자가 `tools/home-sync.sh diff` → `apply` 한다.
4. 2주 뒤 `review-ledger.py stats` 와 `/usage` 로 임계와 등급을 조정한다. 채택률이 낮은 트리거는 끈다.

## 11. 분리 실험: 맥락 계승형과 감사형

날짜 2026-11-10, claude 2.1.316. 사용자 가설은 "advisor 와 리뷰어의 차이는 모델이 아니라 **주입된 맥락**에서 온다"였다. §9 와 같은 시점(c9a9e895 L2490, `8039225` 직후)에서 주는 것만 바꿔 재 봤다. 결과는 **방향상 가설과 맞다.** 대화를 받은 쪽은 advisor 4건 중 일부를 다시 잡았고, diff 를 받은 쪽은 실측 버그를 잡았다. 둘이 잡은 것은 거의 겹치지 않았다.

### 11.1 조건 [로컬]

| 조건 | 받는 것 | 시스템 프롬프트 | 모델·횟수 | 첫 호출 맥락 |
|---|---|---|---|---|
| **A 맥락 계승형(다른 프레임)** | 대화 사본. diff·파일 목록은 주지 않고 읽기 도구는 준다 | `claude -p --agent` 의 짧은 조언자 프롬프트 | opus 2, sonnet 1 | 132k 토큰 |
| **A' fork** | 세션 자체를 그 시점에서 이어받고 질문 블록 하나를 붙임 | 세션에 기록된 메인의 것 그대로 | opus 1 | 302k 토큰 |
| **B 감사형** | §9 그대로(브리프 25줄, diff·파일, 사용자 원문 추출). 다시 돌리지 않음 | 리뷰어 초안 | opus 2, sonnet 1 | 약 6만 + 리뷰어가 읽은 것 |

- **A 의 대화 사본**: 자른 트랜스크립트의 마지막 compact 경계(L1488)부터 L2488 까지 옮겼다(`drafts/second-opinion/skills/context/scripts/render-transcript.py`).
  - 그대로 넣은 것: compact 요약, 사용자 메시지, 메인 응답, 서브에이전트 보고·훅 주입 전문, 도구 호출 요약
  - 줄인 것: 도구 결과는 앞 300자만 남겼다. 그래서 advisor 가 본 317k 가 132k 로 줄었다.
- **A' 만드는 법**
  - 세션 jsonl 을 L2488 까지 잘라 새 ID 로 임시 프로젝트 키(`-tmp-so-replay-claude-doctor`)에 복사했다. `sessionId` 필드도 바꿨다(`/tmp/so-ctx-kit/make-fork.py`).
  - `claude -p --resume <ID> --fork-session` 으로 이어받았다. 기록된 system prompt snapshot 이 그대로 쓰였다.
  - 결과: **된다.** haiku 스모크에서 이어받은 맥락으로 첫 요청과 마지막 도구 호출을 정확히 답했다.
- **공통 조건**
  - 질문 하나: "다음 단계로 넘어가기 전에 이 흐름에서 놓친 것, 잘못된 전제, 확인 안 한 가정은?" 출력 틀(항목, 근거, 반드시/권장/참고, 할 일 3줄)은 A 와 A' 가 같다.
  - effort high. 시점 사본 `/tmp/so-replay/*`(§9 와 같은 커밋으로 다시 복원)을 썼다.
  - 누출 가드는 §9 가드에 이번 실험 산출물 경로 차단을 더했다.
  - A·A' 에는 비용 때문에 "도구는 10회 이내" 를 적었다. B 에는 그런 제한이 없었다.
- **A' 질문 블록에 들어간 재현 환경 안내**: 사본 경로와 "진행 중이던 서브에이전트는 응답하지 않는다"를 적었다. 뒤 문장이 A' 의 해석을 오염시켰다(§11.4).

### 11.2 advisor 4건 회수

| advisor 가 잡은 것 | B o1 | B o2 | B s1 | A o1 | A o2 | A s1 | A' |
|---|---|---|---|---|---|---|---|
| 1. home-sync 가 고아 링크를 정리하지 않음 | 부분(약) | 못 | 못 | 부분: `roblox-luau` 링크 대상이 사라짐. "링크 대상 존재 검사"를 status 에 넣자 | 부분: "apply 는 대상 없는 링크를 건너뛰기만 한다", 재편 뒤 링크 정리 | 못 | 부분: MANIFEST 가 사라진 스킬을 가리킴 |
| 2. 훅의 `lib/*` import 와 MANIFEST 대조 | 부분 | 부분 | 부분(약) | 못 | 못 | 못 | 못 |
| 3. 사용자 레벨 symlink rules(paths) 로드를 아무도 재지 않음 | 못 | 못 | 못 | 못 | 못 | **완전**(반드시. apply 직후 `InstructionsLoaded` 로 확인) | **완전**(권장) |
| 4. session-log 의 SessionStart·UPS 주입은 user turn 이라 래퍼 필수 | 못 | 못 | 못 | **완전**: 인계 800자가 태그 없이 user turn 에 들어가 사용자 지시처럼 읽힌다. 플러그인이 따로 구현해야 한다 | **완전**: 태그 뜻이 정본 CLAUDE.md 에만 있다. 플러그인 메시지가 스스로 뜻을 밝혀야 한다 | 못 | 못 |
| (덧) rules 언어 질문 미결 | 못 | 못 | 못 | 잡음 | 잡음 | 못 | 잡음 |
| (덧) auto-compact 미검증 | 잡음 | 잡음 | 잡음 | 잡음 | 잡음 | 잡음 | 잡음 |

auto-compact 는 B 의 브리프와 A·A' 의 대화에 이미 적혀 있었다. 그래서 회수로 치지 않는다.

| 집계 (4건 × 실행) | B | A | A' |
|---|---|---|---|
| 완전 | 0/12, Wilson 95% [0.00, 0.24] | 3/12 [0.09, 0.53] | 1/4 [0.05, 0.70] |
| 부분 이상 | 4/12 [0.14, 0.61] | 5/12 [0.19, 0.68] | 2/4 [0.15, 0.85] |
| 하나라도 완전히 잡은 실행 | 0/3 | 3/3 | 1/1 |

- **방향만 읽는다.** 한 실행의 네 항목은 서로 독립이 아니다. 구간도 겹친다.
- B 가 A 보다 나은 것은 2번 하나다. B 브리프의 주장 5("새 파일은 모두 MANIFEST 에 올렸다")가 리뷰어를 MANIFEST 쪽으로 보냈다. A 에는 주장 목록이 없어서 아무도 보지 않았다. 이것도 "주입한 것이 주의를 정한다"는 가설과 같은 방향이다.

### 11.3 조건별 고유 발견과 성격

| 발견 | 누가 | 성격 | 확인 |
|---|---|---|---|
| **dedup 키 `(session_id, compact 회차)` 에 서브에이전트 구분이 없다.** 메인과 서브에이전트가 "세션당 1회" 알림 상태를 공유한다 | **A 3/3**(o1·o2 반드시/권장, s1 권장), B 0/3, A' 0/1 | 구현. 흐름에서 끌어냈다: "쓰기는 대부분 서브에이전트가 하는데 실측은 `-p` 단일 세션에서만 했다" | **실측으로 맞다.** haiku 프로브에서 서브에이전트 PreToolUse 입력의 `session_id` 는 부모와 같았고 `agent_id` 만 달랐다. `transcript_path` 도 부모 것이었다. 지금 정본 `home/.claude/lib/compact_epoch.py` 도 `session_id` 만 쓴다. **지금도 유효하다.** `home/` 은 다른 에이전트가 작업 중이라 고치지 않았다 |
| 소급 요약 에이전트가 다른 저장소에 파일을 썼을 수 있다. 첫 지시 뒤에 "외부로" 정정했지만 메시지 전달에 시차가 있다 | A o2, A' | 범위 밖 영향 | 미확인. 그 시점의 `plugins/` 를 복원하지 못했다 |
| 소급 대상 수가 맞지 않는다(27 대 141). 실험 잔재(`-tmp-*`)와 서브에이전트를 뺄 기준이 없다 | A o2, A s1 | 전제 | 미확인 |
| PreCompact stdout 은 작업 모델이 아니라 요약기로 간다. 그래서 "compact 직전 상기" 약속이 모델에 닿는지 모른다 | A o2 | 전제·흐름 | `audit/17:16` 의 "미확인" 표기와 맞다 |
| description 상한이 1024자와 1,536자 두 개다 | A o1 | 전제 | 둘 다 맞을 수 있다(명세 상한과 목록에서 잘리는 길이) |
| `git add home` 습관. 병행 작업 커밋이 섞인 전례가 있다 | A o1 | 흐름 | 8039225 에는 섞이지 않았다 |
| `cleanupPeriodDays` 는 apply 전에는 효력이 없다. 12-03 전에 apply 해야 한다 | A o1, A' | 범위 밖 영향 | 추정 |
| coderag 의 SessionStart `gen` 이 프로젝트가 정한 실행 파일을 신뢰 확인 없이 돌릴 수 있다 | A s1 | 범위 밖 영향(보안) | 설계 문서 줄 번호까지 확인. 동작은 미실측 |
| session-log 가 따로 띄우는 `claude -p` 에 `choom` 이 없다 | A s1 | 범위 밖 영향 | 설계 문서 grep 0건 |
| 인증 배지 범위(Anthropic 검토인지 partner 검토인지)가 사용자 보고에서 빠졌다 | A s1 | 흐름 | - |
| 마켓 설치와 MANIFEST 링크로 스킬이 두 번 노출될 수 있다 | A' | 범위 밖 영향 | 추정 |
| 설치하지 않은 `session-report` 를 `enabledPlugins` 에 켜 두었다 | A o2, A' | 전제 | - |
| (B 쪽) structure-reminder 성장 알림 소실(재현한 버그) | B o1·s1 | 구현·실측 | A·A' 는 0/4 |
| (B 쪽) apply 범위가 이번 커밋보다 크다 | B o2·s1 | 범위 밖 영향 | A 에서는 o2 만 부분으로 잡았다(반영 대기 목록을 나열) |
| (B 쪽) 문서 "2줄" 대 실제 1줄, SessionStart 출력 위치 표기 차이 | B | 구현 | A·A' 0 |

**성향** (각 실행의 항목을 세 갈래로 나눔)

| | 전제·흐름 | 구현·실측 | 범위 밖 영향 | 도구 사용 |
|---|---|---|---|---|
| B (3회) | 적음(auto-compact 정도) | **대부분.** 프로브 재현, 바이너리 grep, 정본·설치본 diff | apply 범위, HOOK-MESSAGES 를 찾을 길 | 16~29턴 |
| A (3회) | **대부분.** 미결 질문, 지키지 않은 약속, 재지 않은 전제 | 서브에이전트 dedup 하나(3/3), sonnet 은 가드 테스트 하나 더 | 병행 작업 주입 경로, 다른 저장소, 보안·OOM | 3턴(Bash 2회) |
| A' (1회) | 열린 항목(rules 로드, auto-compact, 미결 질문) | 0 | **대부분.** 반쯤 된 재편, 다른 저장소 파일, 이중 노출 | 3턴(Bash 2회) |

### 11.4 A 와 A' — 같은 프레임의 사각지대가 보이는가 (방향만, A' 는 1회)

- **A' 는 메인의 자리에서 말했다.** 1인칭으로 썼다("저는 그 직전에 … 넘어갔습니다", "저는 사용자에게 '고친다'고 답했지만").
- **메인이 방금 끝낸 설계는 다시 열지 않았다.** A 는 3/3 이 서브에이전트 dedup 을, 2/3 이 session-log 주입 경로(4번)를 짚었다. 둘 다 메인이 바로 앞에서 "끝났다"고 본 설계를 의심하는 항목이다. A' 는 둘 다 짚지 않았다. "메인과 같은 사각지대가 이어진다"는 가설과 같은 방향이다.
- **A' 가 더 잘한 것은 세계의 상태와 열린 항목이다.**
  - 사본을 직접 열어 luau-kb 의 SKILL.md 없는 스킬 5개와 `roblox-luau` 참조 27개를 셌다.
  - 이중 노출 가능성을 짚었다.
  - rules 로드는 대화에 "재지 않았다"로 이미 적혀 있던 항목이다.
- **오염**
  - A' 의 1번("재편·세션 기록 에이전트가 끝나지 못했다")과 3번 일부는 재현 환경 탓이다.
  - 질문 블록의 "진행 중이던 서브에이전트는 응답하지 않는다"를 실패로 읽었다. 그 시점에 두 에이전트는 실제로 돌고 있었다.
  - 살아 있는 fork 에는 이 문장이 필요 없다.
- **섞인 변수**
  - A' 는 도구 결과 전문(302k)을 봤고, A 는 앞 300자만 봤다.
  - 시스템 프롬프트 차이와 입력 상세도 차이를 이 실험으로는 가를 수 없다.
- **다음 실험 후보**: 살아 있는 세션의 fork 에 역할 전환 문구("너는 이제 검토자다, 방금 설계를 남의 것처럼 의심하라")를 넣는다. 그러면 A 쪽 발견(서브에이전트 dedup, 주입 경로)을 회수하는지 본다. 초안 `skills/context/SKILL.md` §2 에 이 문구를 넣어 두었다. 1회 약 $0.2~0.35 다.

### 11.5 비용과 시간 (API 환산, `total_cost_usd`)

단가(/M 토큰)는 Claude Code 가 계산한 값을 역산해 확인했다. 실행 비용과 센트 단위까지 맞았다.

| | 입력 | 출력 | 캐시 읽기 | 5m 쓰기 | 1h 쓰기 |
|---|---|---|---|---|---|
| opus 5.5 | $4 | $20 | $0.20 | $5 | $8 |
| sonnet 5.5 | $2 | $10 | $0.10 | $2.5 | $4 |

- sonnet 캐시 읽기는 claude-api 스킬 표에 $0.20 으로 적혀 있다. 하지만 Claude Code 계산과 맞는 값은 $0.10 이다. 확인이 필요하다.
- Claude Code 는 기본으로 1h 로 쓴다. `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` 으로 바꿀 수 있다(haiku 로 확인).

| 실행 | 첫 호출 맥락 | 캐시 | 비용 | 시간 | 턴 |
|---|---|---|---|---|---|
| advisor(원래) | 317k | advisor 입력은 매번 캐시 없이(§1.3) | $1.33 | 66초 | - |
| B opus #1 / #2 / sonnet | 66k / 62k / 60k 쓰기 | 1h. 뒤 턴에서 자기 캐시를 1.27M / 0.91M / 0.61M 읽음 | $1.17 / $0.96 / $0.42 | 210 / 198 / 103초 | 29 / 21 / 16 |
| A opus #1 | 132k | 1h 쓰기 134k | $1.25 | 76초 | 3 |
| A opus #2 | 132k | **#1 의 1h 캐시를 132k 읽음.** 프롬프트를 바이트까지 같게 해 독립 표본을 하나 더 얻었다 | **$0.33** | 95초 | 3 |
| A sonnet | 132k | 5m 쓰기 139k | $0.49 | 100초 | 3 |
| A' opus(과거 시점 사본) | 302k | **차가움**: 5m 쓰기 306k. 2·3번째 호출은 302k·305k 를 읽음 | $1.77 | 63초 | 3 |
| 살아 있는 fork 프로브(이 세션, opus) | 139k | **읽기 139,375 / 새로 쓰기 109** | 약 $0.03 | 3초 | 1 |
| 기타: haiku 스모크 4회, 서브에이전트 훅 프로브 | | | 약 $0.03 | | |
| **이번 합계** | | | **약 $3.9** (상한 $4 안) | | |

- **과거 시점 fork 는 캐시가 차가울 수밖에 없다.**
  - 원래 세션은 그 뒤 12:31 에 다시 compact 됐다. 캐시 항목도 TTL 이 지났다.
  - 같은 자른 지점에서 fork 를 두 번 해도 두 번째는 시스템·도구 접두(16.7k)만 읽었다. 첫 fork 의 캐시 항목은 "대화 + 첫 질문" 끝에 걸렸기 때문이다.
  - 캐시 항목은 브레이크포인트에만 생긴다. 그래서 대화 끝에 항목이 있으려면 메인이 방금 그 접두로 요청을 보냈어야 한다. 살아 있는 세션은 늘 그렇다.
- **살아 있는 세션에서 fork 했을 때의 추정**
  - 가정: 메인이 방금 응답해 접두가 캐시에 있다. fork 는 같은 모델(opus)이다. 새로 쓰는 토큰은 2k(메인의 Agent 호출 턴 + 질문 블록)다. 출력은 6k(A' 실측 6,165, thinking 포함)다.
  - 도구 없이 한 번: 317k × $0.20 = $0.063, 쓰기 2k × $8 = $0.016, 출력 6k × $20 = $0.12. 합계 **약 $0.20**.
  - A' 처럼 도구 2회(호출 3번): 호출마다 약 $0.06 의 읽기와 약 $0.02 의 쓰기가 더해진다. 합계 **약 $0.35**.
  - 교차 확인: A' 실측 $1.77 에서 차가운 쓰기 301,779 토큰을 읽기 단가로 바꾸면 약 $0.32 다. 위 추정과 맞다.
  - 비교: advisor 는 같은 317k 에서 $1.33 이다. fork 는 그 **약 1/4~1/6** 이다.
- **fork 의 조건**
  - fork 는 메인 모델로만 돈다(모델 지정이 무시된다). sonnet 으로 싸게 할 수 없다.
  - 메인이 TTL 넘게 쉬면 캐시가 식는다. 메인은 1h, 이 세션의 서브에이전트는 5m 로 쓰고 있었다. 그러면 30만 토큰에서 opus $1.5~2.4 로 뛴다.
  - fork 의 보고는 메인 맥락에 남아 이후 매 턴 읽힌다. 짧게 받아야 한다.
- **A(다른 프레임)의 비용은 사본 크기에 비례한다.** 132k 기준 opus $1.25(1h) 또는 약 $0.8(5m), sonnet $0.49 다. 1시간 안에 같은 사본으로 다시 물으면 $0.33 이다. 시점이 바뀌면 사본이 달라져 다시 써야 한다.
- **결론: fork 를 전환점마다 촘촘하게 쓰는 운용은 비용상 성립한다.** 30만 토큰 맥락에서 1회 $0.2~0.35 이므로 세션당 10회여도 $2~3.5 다. advisor 2~3회 값이다. 단 메인이 방금 응답한 직후에 불러야 하고, 같은 프레임의 사각지대(§11.4)가 있으니 무거운 전환점에는 A 를 섞는다. [추정, 근거는 위 실측 단가와 살아 있는 fork 프로브]

### 11.6 해석과 도구 분리

- **가설은 방향상 맞다.** 같은 시점, 같은 모델에서 주입만 바꿨는데 회수한 문제의 종류가 갈렸다.
  - B 는 주장 목록이 가리킨 곳과 실측할 수 있는 구현으로 갔다.
  - A 는 대화에만 있던 것으로 갔다: 주입 경로, 미결 질문, 다른 실행 경로.
- **A 도 advisor 를 다 재현하지는 못했다**(완전 3/12, 2번은 0). advisor 의 4건은 정답지가 아니다. A 와 B 모두 advisor 가 못 잡은 실재 문제를 찾았다.
  - A: 서브에이전트 dedup(실측으로 맞음, 지금도 유효)
  - B: 성장 알림 소실(재현함)
- **그래서 두 도구로 나눈다**(초안 `drafts/second-opinion/`)
  - `second-opinion:context`: 대화를 이어받은 눈
    - 쓰는 때: 작업 단위를 끝내고 넘어가기 직전, 결정·방향을 사용자에게 제안하기 직전, 병행 결과를 합치기 직전. 기본은 fork 다.
    - apply·배포처럼 되돌리기 어려운 확정 직전이나 fork 가 "문제 없음"으로 돌아왔을 때는 다른 프레임(A, `ask-other-frame.py`)으로 부른다.
  - `second-opinion:audit`: 지금의 리뷰어
    - 쓰는 때: 커밋·완료 전 diff, 같은 실패 2회, 구현 검증, 접근 확정 전.
    - 브리프는 §9.5 대로 고쳤다. 병행 작업은 "영향받을 수 있는 곳"으로 넘기고, 미결 질문 줄을 더했다.
- **모델**(A, 각 1~2회라 방향만)
  - opus 는 2회 모두 4번을 잡았고 sonnet 은 못 잡았다.
  - sonnet 은 대신 범위 밖 위험(coderag 실행 신뢰, OOM)을 찾았다.
  - 다른 프레임 경로는 high 등급에서 opus, 그 밖에서는 sonnet 으로 초안을 썼다.

### 11.7 한계

- 실행 수는 A 3회, A' 1회, B 3회다. 한 실행 안의 발견은 서로 독립이 아니다.
- 판정(완전/부분/못 잡음)은 이 실험을 돌린 에이전트 한 명이 매겼다. B 판정은 §9 의 것을 그대로 썼다.
- A' 는 재현 환경 문구에 오염됐다(§11.4). 그래서 살아 있는 fork 의 품질을 대표하지 않는다. 살아 있는 fork 는 캐시만 쟀고 품질은 재지 않았다.
- A 와 A' 사이에는 시스템 프롬프트 차이와 렌더링 차이(도구 결과 300자)가 섞여 있다.
- A·A' 는 도구 10회 권고가 있었고 B 는 없었다. 그래서 A 의 실측 부족에는 이 권고 탓도 있을 수 있다.
- 그 시점에 미커밋이던 `plugins/` 와 그 시점의 설치본 settings.json 은 §9 처럼 복원하지 못했다.
- sonnet 캐시 읽기 단가는 문서($0.20)와 계산($0.10)이 다르다.

### 11.8 산출물과 생성 목록

- **초안**(`drafts/second-opinion/`, 커밋하지 않음)
  - 새로 만든 것
    - `skills/context/SKILL.md`
    - `skills/context/scripts/render-transcript.py`: 실험 렌더러와 출력이 바이트까지 같은지 확인했다
    - `skills/context/scripts/ask-other-frame.py`: 가짜 `claude` 로 인자와 입력만 확인했다
    - `agents/second-opinion-context.md`
  - 옮긴 것: `skills/second-opinion/` → `skills/audit/`. SKILL.md 의 description, 비용 절, 브리프 원칙과 `templates/brief.md` 의 병행 작업·미결 질문 줄을 고쳤다.
  - 고친 것: `agents/second-opinion-reviewer.md` 의 스크립트 경로, `home/CLAUDE.md.fragment.md`(두 갈래). 훅 테스트는 17/17 이다.
  - 이름은 플러그인 이름공간(`second-opinion:context`, `second-opinion:audit`)을 전제로 했다. 사용자 레벨 skills 에 그대로 두면 `audit` 이 기존 `/audit` 과 겹친다. 설치 형태는 사용자 결정이다(플러그인으로 낼지, 이름을 바꿀지).
- **키트와 원시 출력**(`/tmp`, 커밋하지 않음)
  - 키트: `/tmp/so-ctx-kit/`(렌더러, `make-fork.py`, 가드, 에이전트 JSON, 질문 블록)
  - 출력: `/tmp/so-ctx-out/{opus1,opus2,sonnet1,aprime}.jsonl`
  - 시점 사본: `/tmp/so-replay/{claude-doctor,luau-kb,coderag}`
- **실제 `~/.claude/projects` 에 만든 것**(임시 키만, 원본 세션은 읽기만 함)
  - `-tmp-so-replay-claude-doctor/`(§9 때 만든 키)
    - 자른 사본: `912a230c….jsonl`(37줄, 스모크), `ac104a67….jsonl`(2488줄, 7.1MB)
    - fork 결과: `82117d12…`, `9112c8a1…`, `21ca52bc…`, `381c45ca…`(haiku 스모크), `535a4e25…`(A')
    - `memory/` 디렉터리도 있다(자동 생성으로 보임, 확인 안 함)
  - `-tmp-so-ctx-probe/`(새 키): `fa969e79…/`(서브에이전트 훅 프로브), `memory/`
