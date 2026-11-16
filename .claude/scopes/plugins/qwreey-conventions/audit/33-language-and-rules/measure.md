# 33 언어 이탈과 규칙 배치: 실측

측정일 2026-11-11. 읽기 전용. 스크립트는 `/tmp/measure-lang/`(turns.py, dist.py, ctx.py, hk.py)에 두었고 저장소에는 없다.

## A. 언어 이탈

### A1. 데이터와 측정 방법

| 항목 | 값 |
|---|---|
| 대상 | `/code/.claude/projects/*/*.jsonl` 327개 중 메인 세션만(`subagents/` 제외, `isSidechain` 제외) |
| 사용자 프롬프트 | `type=user`, tool_result 아님, `isMeta` 아님, `origin.kind` 가 human 또는 없음, `<` 로 시작하지 않음(task-notification, command 제외), "This session is being continued" 제외, 한글 포함 |
| 응답 | 그 턴(다음 실제 프롬프트 전까지)의 마지막 비어 있지 않은 assistant text 블록 |
| 중복 제거 | resume·fork 로 같은 턴이 여러 파일에 복제되어 (프롬프트+응답) md5 로 제거. 1,551턴 -> 1,264턴 |
| 지표 | 코드 펜스, 인라인 코드, URL, 경로·식별자류 토큰(`/ _ . : - = <>` 등 포함, camelCase, 대문자 약어, 숫자 섞임) 제거 뒤 한글/(한글+라틴) |
| 언어 설정 | 이탈 세션 7개 모두 `language: 한국어` attachment 가 있다(세션당 2~19회). 설정이 빠진 세션이 아니다 |

### A2. 분포 (n=1,264, 글자 없는 4건 제외 1,260)

| 분위 | 비율 |
|---|---|
| p1 | 0.00 |
| p5 | 0.72 |
| p10 | 0.78 |
| p25 | 0.85 |
| p50 | 0.90 |
| p90 | 0.98 |

히스토그램(0.1 단위 칸): 0.0대 39, 0.4대 2, 0.5대 3, 0.6대 13, 0.7대 110, 0.8대 475, 0.9대 618. **0.06 ~ 0.48 사이에는 한 건도 없다**(쌍봉).

| 임계 | 미만 건수 | 중앙 길이(자) | 300자 이상 | 800자 이상 |
|---|---|---|---|---|
| 0.2 | 39 | 1,363 | 28 | 24 |
| 0.35 | 39 | 1,363 | 28 | 24 |
| 0.5 | 41 | 1,375 | 30 | 26 |
| 0.7 | 57 | 1,301 | 44 | 35 |

전체 응답 길이 분위(p10/25/50/75/90): 464 / 852 / 1,371 / 1,944 / 2,548자.

### A3. 손검증 (r<0.7 중 16건)

| # | 세션:턴 | r | 길이 | 판정 | 비고 |
|---|---|---|---|---|---|
| 1 | devplorer 34c828d8:2 | 0.00 | 3,436 | 진짜 영어 | 전부 영어 보고 |
| 2 | devplorer 8fb4e0b8:14 | 0.00 | 33 | 진짜 영어 | "Now writing the replacement code." 짧은 서술 |
| 3 | mrow aa399095:3 | 0.00 | 181 | 진짜 영어 | 세션 첫머리부터 영어 |
| 4 | mrow aa399095:5 | 0.06 | 1,565 | 진짜 영어 | 링크·식별자만 한글 아님, 본문 영어 |
| 5 | mrow aa399095:11 | 0.01 | 2,081 | 진짜 영어 | 코드 펜스 안 한글 주석만 있고 설명은 영어 |
| 6 | mrow aa399095:19 | 0.00 | 996 | 진짜 영어 | `/compact` 인자만 한글, 안내 문장은 영어 |
| 7 | quad 375233bc:106 | 0.00 | 333 | 진짜 영어 | 라운드 보고 |
| 8 | quad 58bd1a5b:14 | 0.00 | 3,099 | 진짜 영어 | |
| 9 | quietcode 63cdd9e3:0 | 0.00 | 2,330 | 진짜 영어 | |
| 10 | quietcode 63cdd9e3:7 | 0.00 | 1,821 | 진짜 영어 | 사용자 "그리고 음, 영어임." 에 대한 응답조차 영어("Again, I'm sorry for writing in English.") |
| 11 | claude-doctor c9a9e895:51 | 0.00 | 22 | 오탐 | "No response requested." 하네스 문구. 같은 문구가 3개 세션에 있다 |
| 12 | quad 58bd1a5b:23 | 0.00 | 5 | 오탐 | 응답이 "round" 한 단어 |
| 13 | crg m2b 9cec5d5f:0 | 0.52 | 166 | 오탐 | 경로 나열 형식의 도구 출력(하네스 실험 세션) |
| 14 | claude-doctor c9a9e895:70 | 0.57 | 2,056 | 오탐 | 한글 문장에 영어 인용(스킬 description 영어 문구) 다량 |
| 15 | quad 375233bc:22 | 0.68 | 1,086 | 오탐 | 한글 응답에 식별자·영어 항목명 |
| 16 | claude-doctor c9a9e895:71 | 0.49 | 2,680 | 오탐 | 한글 토론 요약, 영어 인용 다량 |

관찰:

- 오탐은 두 종류다. (1) 영어 글자 20개 미만의 초단문(`No response requested.`, `round`, 5~22자). (2) 0.48~0.7 대의 한글 응답에 영어 인용·표가 섞인 것. 진짜 영어는 모두 r<=0.06 이다.
- 진짜 영어 중 짧은 것도 있다: 33, 67, 71, 88, 91자(라틴 24~57자). 그래서 길이만으로 "짧으면 무시"는 못 쓴다.
- 진짜 영어의 한글 잔량은 코드 펜스 안 한글 주석이나 `/compact` 인자 같은 것이다. 펜스·인라인 코드 제거 뒤에도 r 이 0.06 을 넘지 않았다.

**진짜 이탈 정의**: r<0.2, 라틴 글자 20개 이상, 응답 30자 이상, `No response requested.` 제외, 하네스 실험 세션(`-tmp-crg`) 제외. 결과 **35건 / 1,264턴 = 2.8%**, 7개 세션.

길이별(진짜 이탈 35건): 150자 미만 6, 150~400 2, 400~1,000 5, 1,000~2,000 12, 2,000 이상 10. 즉 **77%가 1,000자 이상**이고 짧은 것은 17%다.

### A4. 앞선 맥락

방법: 이탈 턴의 이벤트(그 턴과, 그 턴 직전 compact 경계)에서 범주 플래그를 세고, 정상 턴(r>=0.5, n=1,219)과 비교했다.

| 범주 | 이탈 35건 | 정상 1,219건 | 그 범주 턴의 이탈률 |
|---|---|---|---|
| Agent/Task/SubagentHandback 호출 | 20 (57%) | 375 (31%) | 5.0% |
| task-notification 도착 | 6 (17%) | 129 (11%) | 4.4% |
| 긴 영어 tool_result(3,000자 초과, 한글 2% 미만) | 16 (46%) | 296 (24%) | 5.1% |
| 영어 hook additionalContext | 4 (11%) | 67 (5%) | 5.6% |
| 스킬 로드 | 3 (9%) | 82 (7%) | 3.5% |
| compact 경계 | 6 (17%) | 147 (12%) | 3.9% |
| 위 여섯 범주 모두 없음 | 8 (23%) | - | - |
| 도구 호출 10회 이상 | 20 (57%) | 498 (41%) | 약 3.9% |
| 도구 호출 0회 | 0 | 121 (10%) | 0% |
| 턴 중앙 도구 호출 수 | 17 | 7 | - |

해석:

- 어느 범주도 이탈을 가르지 못한다. 범주 안의 이탈률은 3.5~5.6% 로 전체 2.8% 와 비슷하다. 에이전트 결과와 긴 영어 tool_result 가 가장 두드러지지만(각 약 2배) 표본이 작다.
- **긴 작업 턴**(도구 호출이 많고 영어 출력이 쌓인 뒤의 최종 보고)이 공통점이다. 도구 없이 답한 턴은 이탈 0건이다. quietcode 응답 스스로도 "Both slips happened in the final report after a long run of work" 라고 적었다.
- hook additionalContext 는 이탈 턴 4건뿐이다. 훅 주입을 주원인으로 보기는 어렵다.
- 한계: 맥락 창 안의 영어 지시 파일(CLAUDE.md, 규칙)과 시스템 프롬프트 비중은 트랜스크립트로 재지 못했다. 영어 attachment 의 양은 세지 않았다.

### A5. 지속성

세션별 한글 프롬프트 턴 순서(E=이탈, k=정상, ?=판단 불가):

| 세션 | 패턴 | 형태 |
|---|---|---|
| mrow aa399095 | `EEEEEEEEEEEEEEEEEEEk` | 첫 턴부터 거의 전부(19/20). 세션 전체가 영어 모드 |
| quietcode 63cdd9e3 | `EkkEkEEk` | 지적 뒤에도 재발, 연속 2회 포함 |
| devplorer 8fb4e0b8 | `k...kEE` | 마지막 2턴 연속 |
| quad 58bd1a5b | `k...kEEk...` | 연속 2턴 뒤 회복 |
| devplorer 34c828d8 | 101턴 중 5회, 흩어짐 | 단발 |
| quad 375233bc | 439턴 중 1회 | 단발 |
| stl-luau 1cb06079 | 190턴 중 2회 | 단발 |

7개 중 4개는 **연속하거나 군집**이고 3개는 단발이다. 한 번 시작되면 다음 턴도 이어질 확률이 높다(이탈 35건 중 바로 다음 한글 턴도 이탈인 경우는 대부분 mrow 의 연속). 따라서 "다음 턴에 리마인더" 방식은 연속 이탈에는 유효하지만, 첫 이탈은 막지 못한다. 단발은 같은 턴에 고치는 편이 낫다.

### A6. 임계 제안

| 항목 | 제안 | 근거 |
|---|---|---|
| 비율 | r < 0.25 | 진짜 이탈 최대 0.06, 정상 최소 0.48. 0.1~0.45 빈 구간이 넓어 0.2 든 0.35 든 같은 결과(39건) |
| 최소 라틴 글자 | 20 이상 | 오탐 4건이 5~10자. 진짜 이탈은 24자 이상 |
| 예외 문구 | `No response requested.` | 하네스 고정 문구 3건 |
| block(재작성 요청) | 라틴 글자 20 이상이고 응답 1,000자 미만 | 재작성 비용이 작다. 35건 중 13건 |
| 주입(다음 턴 리마인더) | 1,000자 이상 | 장문은 재작성이 비싸다. 단 연속 이탈 때문에 `stop_hook_active` 가 아니라 세션 상태(직전 턴 이탈 여부)로 두 번째부터 강화 |
| 건너뜀 | 코드 펜스·인라인 코드·URL 제거 뒤 글자 20 미만 | 위와 같음 |

1,000자 경계는 표본이 작아(35건) 거친 값이다. 150~400자 구간은 2건뿐이라 이 구간 경계는 검증하지 못했다. block 은 Stop 훅 8회 연속 계속 제한(아래 A7) 안에서만 쓰고, `stop_hook_active` 가 true 이면 다시 block 하지 않는다.

### A7. Stop 입력 확인

| 질문 | 결과 | 근거 |
|---|---|---|
| `last_assistant_message` 가 Stop 입력에 있는가 | 있다 | 문서 + 디스크 실물(아래) |
| `stop_hook_active` 의미 | 이미 stop 훅 때문에 계속 중이면 true | 문서 |
| `CLAUDE_PLUGIN_DATA` 가 플러그인 훅에 설정되는가 | 설정된다(문서). 실물은 확인하지 못했다 | 문서 |
| 플러그인 스킬의 bash 주입에서 쓸 수 있는가 | 문서상 치환된다 | 스킬 문서 |

문서 인용(https://code.claude.com/docs/en/hooks.md, Stop input 절):

> In addition to the common input fields, Stop hooks receive `stop_hook_active`, `last_assistant_message`, `background_tasks`, and `session_crons`. The `stop_hook_active` field is `true` when Claude Code is already continuing as a result of a stop hook. Check this value or process the transcript to avoid blocking on a condition that will never resolve.

> The `last_assistant_message` field contains the text content of Claude's final response, so hooks can access it without parsing the transcript file. [...] the transcript file isn't guaranteed to include the final message at Stop time on all versions.

> Claude Code applies an 8-consecutive-continuation cap: after stop hooks have continued the turn eight times in a row, Claude Code overrides the next block and ends the turn. The count of consecutive continuations resets each time Claude calls a tool.

`decision: "block"` 은 `reason` 필수. `hookSpecificOutput.additionalContext` 는 "Non-error feedback for Claude. The conversation continues so Claude can act on it", 같은 8회 상한과 `stop_hook_active` 보호를 받는다. 곧 additionalContext 도 턴을 이어 가므로 "다음 턴에 주입"이 아니라 **같은 턴 계속**이다. 다음 사용자 턴에 넣으려면 상태 파일에 적고 UserPromptSubmit 훅에서 주입해야 한다(미실측 설계).

환경 변수(hooks.md): "both export them as the environment variables `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, and `CLAUDE_PLUGIN_DATA` on the spawned process". 스킬 문서(skills.md): "`${CLAUDE_PLUGIN_DATA}` ... Substituted only in plugin skills." 그리고 "In a plugin skill, Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` in the same two places"(스킬 본문, `allowed-tools` Bash 규칙). 스킬이 띄운 bash 의 환경 변수로 주어지는지는 문서에 없다. 본문 치환만 보증된다.

디스크 실물: `/tmp/sa-probe/hooks.jsonl` 의 Stop 기록에 `"hook_event_name": "Stop", "stop_hook_active": false, "last_assistant_message": "백그라운드 에이전트 2개와 워크플로우가..."` 가 있다. 그 기록은 `transcript_path`, `prompt_id`, `permission_mode`, `effort`, `background_tasks` 도 담는다. 훅 입력에서 환경 변수는 덤프하지 않았으므로 `CLAUDE_PLUGIN_DATA` 실측은 못 했다. q 플러그인 README 는 의도적으로 `CLAUDE_PLUGIN_DATA` 를 쓰지 않는다고 적는다.

참고: `plugins/qwreey-conventions/hooks/hooks.json` 에 이미 Stop 훅(`conventions-check.py`)이 있고 systemMessage 만 쓴다. 언어 훅은 별도 스크립트로 같은 Stop 배열에 더하면 된다.

## B. 규칙 근거

### B1. 규칙별 표

토큰 = 1.72 x 한글 글자 + 0.376 x 나머지 글자(frontmatter 포함, 파일 전체). 바이트는 `wc -c`. 설치본 `/code/.claude/rules/` 와 `home/.claude/rules/` 는 같은 크기다.

| 규칙 | 바이트 | 토큰 | 로드 | 겹치는 훅·스킬 | 훅 발동 근거 |
|---|---|---|---|---|---|
| code-structure | 2,675 | 1,022 | 경로 조건부: luau·lua·ts·tsx·js·jsx·mjs·astro·rs·py·go·kt | `structure-reminder.py`(PostToolUse Write·Edit·Bash): 800/1,500줄, 증가, flat 폴더, family 접두 알림 | 아래 B2 |
| agent-docs | 842 | 317 | 경로 조건부: CLAUDE.md, SKILL.md, agents/*.md, rules, skills/**/*.md | `conventions-check.py` 문서 절(날짜, audit 경로, 결정 문구, 실측 표지 등) + 스킬 `qwreey-conventions:agent-docs` | 알림 0건 기록 |
| comments | 1,210 | 455 | 경로 조건부: 소스 확장자 14종 | `conventions-check.py` 주석 절(이력, 비키보드 기호, 이스케이프, 보이지 않는 문자, 언어 불일치) + 스킬 `comments` | 알림 0건 기록 |
| memory | 1,432 | 538 | 경로 조건부: MEMORY.md, memory/*.md | `memory-placement.py`(PostToolUse Write, memory 디렉터리 안, 점수화 `memory_signals.py`) | 알림 0건 기록 |
| web-security | 1,949 | 747 | 경로 조건부: ts·tsx·js·jsx·mjs·cjs·astro | 없음(내장 `/security-review` 만. 규칙 마지막 줄이 가리킴) | 해당 훅 없음 |
| luau-core(링크) | 6,816 | 2,538 | 경로 조건부: `*.luau` | 각 줄이 `luau-style` 스킬 references 로 연결. 훅은 주석 언어 검사뿐 | 해당 훅 없음 |

모든 규칙이 `paths:` 조건부이고 무조건 상시 규칙은 없다. 사용자 CLAUDE.md 는 별도(662 토큰).

규칙이 실제 로드된 횟수(`nested_memory`·`instructions` attachment 중 `rules/` 경로, 전 프로젝트): luau-core 16, code-structure 11, comments 10, web-security 1, agent-docs 1, memory 0(`mem.md` 1 은 다른 규칙). 파일 확장자가 넓은 규칙일수록 자주 로드되고, 한 세션에서 `.luau` 를 한 번 읽으면 2,538토큰이 상주한다.

### B2. 훅 알림 수(프록시)

방법: 전 프로젝트의 메인과 서브에이전트 트랜스크립트에서 `hook_additional_context` attachment 를 `toolUseID` 로 중복 제거해 `name` 별로 센다.

| 훅 이름 | 건수 | 세션 수 | 비고 |
|---|---|---|---|
| structure-reminder | 12 (warn 10, action 2) | 10 | 대부분 claude-doctor 서브에이전트가 `conventions-check.py`(879~883줄), 다른 파일 1,188~1,203줄을 편집할 때. `action`(1,500줄 이상) 2건은 직후 Bash 만 이어짐 |
| conventions | 0 | 0 | 본문에 이름이 나오는 파일은 있지만 attachment 알림은 없음. 훅이 최근 플러그인으로 옮겨졌고 이전 형식은 따로 세지 못했다 |
| memory-placement | 0 | 0 | 같음 |
| bash-bypass-reminder | 156 (warn 83, 형식 없음 42, info 31) | 52 | 참고용. 규칙 로드 안내 포함 |

발동 뒤 시정 여부: structure-reminder 의 800줄 경고 8건 중 이어진 편집은 분리를 하지 않고 같은 파일에 계속 덧붙이거나 Bash 로 넘어갔다(다음 도구 호출 4개로 본 것이라 확정 아님). **conventions·memory-placement 는 위반 후 시정 근거를 모으지 못했다.** 표본이 적어서 "훅이 발동하는데 모델이 무시한다"와 "거의 발동하지 않는다" 중 어느 쪽인지는 이 자료로 가를 수 없다.

### B3. 판단 시험별 초안(근거 약함, 사용자 판단용)

| 규칙 | 상시 로드 필요? | 이유 |
|---|---|---|
| web-security | 유지 | 조용히 실패하고 비싸다. 겹치는 훅 없음. 747토큰, ts·js 에 한정 |
| code-structure | 축소 후보 | 숫자 기준은 훅이 이미 알린다(겹침). 분리 방법·폴더·이름 지침은 알림 시점에 훅이 가리킬 수 있다. 가장 크게 상주(1,022, 12개 확장자) |
| luau-core | 분할 후보 | 2,538토큰으로 최대. 줄마다 스킬 링크가 있어 근거는 스킬이 가진다. `local const`, `pcall(f(x))` 같은 함정은 조용히 실패하므로 남기고 나머지는 스킬로 |
| agent-docs, comments | 축소 후보 | 훅(`conventions-check`)과 스킬이 같은 내용을 가진다. 훅 알림이 이름 지은 스킬을 읽게 하므로 규칙은 중복. 단 conventions 알림 발동 실물이 0건이라 확인 필요 |
| memory | 축소 후보 | `memory-placement` 가 Write 시점에 같은 판단을 한다. 로드 0회 |

위는 겹침과 크기에 근거한 초안이고, "모델이 어차피 하는지"는 측정하지 못했다.

## 검증하지 못한 것

- 영어 지시 파일·시스템 프롬프트가 이탈에 주는 기여(트랜스크립트에 영어 비중 없음).
- `CLAUDE_PLUGIN_DATA` 실제 값과 스킬 bash 환경 변수 여부.
- conventions·memory-placement 알림과 시정(발동 기록 0건). 이전 형식 알림은 세지 않았다.
- 150~400자 구간 임계. 표본 2건.
- r 지표의 영어 인용 한글 응답 오탐은 0.48 이상에서만 확인. 영어 비중이 더 높은 정상 응답이 있으면 0.25 는 더 낮출 필요가 있다.
- 이탈 35건 중 일부는 사용자 프롬프트가 영어 자료를 요청한 경우일 수 있다. 개별 프롬프트 의도는 읽지 않았다.
