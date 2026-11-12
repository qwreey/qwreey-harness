# 24. 스킬 감사: 공식 모범 사례와 공식 스킬 짜임 대비

작성일 2026-11-11. 읽기 전용 감사다. 스킬 파일은 고치지 않았고, 시안(§5)은 이 문서 안에만 있다.
표시: **[확인]** 문서·파일에서 직접 읽음, **[측정]** 이 감사에서 센 값, **[추정]** 공식 자료에 없어 추론함, **[미확인]** 자료가 없음.

## 1. 공식 기준 요약

출처
- A: `/tmp/ccdocs/skills.md` (code.claude.com/docs 의 skills 문서 사본)
- B: platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (WebFetch 로 전문 읽음)
- C: 설치된 `skill-creator` SKILL.md (`/code/.claude/skills/synced/*/skill-creator/`)

| 항목 | 기준 | 출처 |
|---|---|---|
| description 역할 | "무엇을 하는가 + 언제 쓰는가"를 둘 다. 스킬 선택의 핵심이고, 본문은 구현 세부를 맡는다. 모호한 서술("Helps with documents")은 나쁜 예 | B "Writing effective descriptions" |
| 문체 | **항상 3인칭**. "I can help you…", "You can use this…" 는 피한다. description 이 시스템 프롬프트에 주입되어 시점이 섞이면 발견에 문제가 생긴다 | B (Warning 블록) |
| 길이 | API/claude.ai: description 최대 1,024자, name 64자(소문자·숫자·하이픈), XML 태그 금지. Claude Code: description+`when_to_use` 합쳐 1,536자에서 잘리고, 핵심 용례를 앞에 둔다. 전체 목록은 컨텍스트의 1% 예산이라 넘치면 덜 쓰는 스킬의 description 부터 빠진다 | B "Skill structure", A "Frontmatter reference", "Skill descriptions are cut short" |
| 트리거 키워드 | 구체적 용어, 파일 확장자, 사용자가 쓸 법한 말을 넣는다. skill-creator 는 과소 발동을 막으려고 약간 "pushy" 하게 쓰라고 한다 | B 예시, C "Write the SKILL.md" |
| 본문 길이 | SKILL.md 본문 500줄 미만. 넘으면 나눈다 | A, B "Token budgets", C |
| 간결성 | "Claude 는 이미 똑똑하다. 모델이 모르는 것만 넣는다. 이 문단이 토큰 값을 하는가?" | B "Concise is key" |
| Progressive disclosure | SKILL.md 는 목차·개요, 세부는 별도 파일. **참조는 SKILL.md 에서 한 단계 깊이만**. 100줄 넘는 참조 파일은 맨 위에 목차 | B |
| 자유도 | 취약한 작업은 정확한 스크립트·절차(낮은 자유도), 맥락 의존 작업은 지침(높은 자유도) | B |
| 시간에 민감한 정보 | 쓰지 않는다. 필요하면 "old patterns" 접이식 절로 | B "Avoid time-sensitive information" |
| 용어 | 한 개념에 한 용어 | B |
| 이유 설명 | skill-creator 는 "무엇을 왜 하는지(why)를 설명하라, 대문자 MUST 는 노란 깃발"이라고 한다. 즉 **작업을 올바르게 하는 데 필요한 이유**는 환영한다. 설계 이력·실험 결과를 요구하지는 않는다 | C "Explain the why" (줄 323) |
| 문체 | 지시는 명령형(imperative) | C "Writing Patterns" |
| frontmatter | Claude Code 에서 모든 필드는 선택, `description` 만 권장. `disable-model-invocation: true` 는 부작용이 있거나 시점을 사용자가 통제할 워크플로(`/commit`, `/deploy`)용. `user-invocable: false` 는 사용자가 직접 부를 의미가 없는 배경 지식용. `allowed-tools` 는 그 턴 동안 권한 프롬프트만 면제(도구 제한 아님). claude.ai/API 로 올릴 때는 `argument-hint` 같은 필드가 거부될 수 있다 | A "Frontmatter reference", "Control who invokes", "Using skill frontmatter outside Claude Code" |
| 평가 | 평가를 먼저 만들고, 스킬 유무 기준선과 비교하고, Haiku·Sonnet·Opus 로 시험한다. skill-creator 는 should/should-not trigger 질의로 description 을 최적화하고(60/40 학습·시험 분할, 질의당 3회), `/skill-doctor` 는 스킬별 컨텍스트 비용과 사용 빈도를 낸다 | A "Evaluate and iterate", B "Build evaluations first", C "Description Optimization" |
| 언어 | **공식 문서 어디에도 언어 요구·권고가 없다 [미확인]**. A, B, C 모두 영어로 쓰였고 description 규칙은 언어 중립이다 | A, B, C 에서 검색 |

한 가지 주의: 문서가 말하는 skill 은 "스킬이 로드될 때만 읽히는 본문"과 "항상 목록에 올라가는 description" 두 층이다. 이 구분이 아래 모든 판단의 축이다. description 은 **모든 턴 모든 세션**에서 비용을 내고, 본문은 호출될 때만 낸다(A "Skill content lifecycle", "Find unused skills").

## 2. 공식 스킬 짜임의 공통 패턴

대상은 이 환경에 설치된 Anthropic 스킬 14개(`/code/.claude/skills/synced/*/`, claude.ai 동기화본): artifact-emulator, built-in-browser, chrome-browser, computer-use, deep-research, docs, docx, google-workspace, import-memory, morning, pdf, pptx, skill-creator, xlsx. `update-config` 등 번들 스킬은 파일로 존재하지 않아 못 봤다 [미확인]. 모두 [측정].

| 항목 | 관찰 |
|---|---|
| description 길이 | 139~1,007자, 중앙값 약 800자. 14개 중 8개가 750자 이상 (`docs` 1,007, `computer-use` 938, `docx` 936, `xlsx` 952, `pptx` 962, `google-workspace` 947). **우리 description 이 짧아서가 아니라 길다는 점이 문제가 아니다.** 공식도 길다. 차이는 내용이다(아래) |
| description 문체 | 영어. "Use this skill whenever the user wants to…", "Triggers include: …". 즉 **2인칭 명령형 "Use this skill"** 이 다수이고(pdf, docx, xlsx, deep-research), 일부는 "Read this skill before the first step that…". 모범 사례의 3인칭 권고와 공식 스킬 자체도 완전히 일치하지는 않는다. 공통점은 주어가 스킬이 아니라 **발동 조건** 이라는 것 |
| description 내용 | 구성은 항상 (1) 무엇에 쓰는지 한두 문장 (2) 트리거 목록: 확장자, 사용자가 쓰는 말("Word doc", ".docx", "casually like 'the xlsx in my downloads'") (3) **부정 조건**("Do NOT use for PDFs, spreadsheets…"). 비용·실험 수치·다른 스킬과의 비교 이력·"잘 잡는 것/못 잡는 것"은 없다 |
| 본문 구성 | 개요 한 줄 → 접근 선택 표/결정 규칙 → 절차 → 함정(gotchas). pdf 314줄(+REFERENCE.md, FORMS.md), xlsx 99줄, docx 95줄, skill-creator 506줄, pptx 273줄. 500줄 이하가 지켜진다(skill-creator 는 506으로 살짝 넘음) |
| 이유 서술 | 있되 **작업상의 이유**만: "`_xlfn.` 접두가 필요한 이유는 openpyxl 이 수식을 XML 에 그대로 쓰기 때문", 로그인은 "사용자의 것"이라서 로그아웃 금지. 설계 결정 이력, 실험 결과, audit 참조, 날짜, "사용자 결정" 서술은 14개 어디에도 없다. `grep` 으로 연도·experiment·measured 를 찾았을 때 xlsx 의 인용 예시 한 줄뿐 |
| 문체 | 지시형. 일부 스킬(built-in-browser, chrome-browser)은 "Claude calls …" 같은 서술형 3인칭이지만 그것도 행동 규정이다 |
| references 분리 | pdf: SKILL.md 가 FORMS.md, REFERENCE.md 를 한 단계 깊이로 가리킴. skill-creator: `references/schemas.md`, `agents/*.md`. docx/xlsx 는 SKILL.md 하나로 완결. 큰 변형(변형별 파일)은 모범 사례의 "Domain organization" 대로 |
| frontmatter | `name`, `description`, `license`, `compatibility`(환경 요건) 만 쓴다. `argument-hint`, `disable-model-invocation`, `allowed-tools` 는 claude.ai 동기화본에는 없다. 업로드 형식이 허용 필드를 제한하는 탓일 수 있다 [추정] |
| 언어 | **14개 전부 영어**, 한글 포함 0개 [측정]. 다만 이 14개는 Anthropic 이 영어 사용자·영어 모델 기준으로 만든 것이라 "영어가 권고"의 증거가 아니라 "한국어 사례가 없다"의 증거일 뿐이다 |

요약: 공식 스킬은 **description = 발동 조건 + 부정 조건, 본문 = 실행 지시 + 작업상의 이유**다. 설계 근거와 이력은 스킬 밖에 있다.

## 3. 스킬별 표

측정 방법: `description` 글자 수, 본문 줄 수(frontmatter 제외), "이력 신호"(`audit/NN`·날짜·`사용자 결정`·`D-NN`·`실측`·`근거는`·`이 사용자` 같은 표현의 개수, 정규식 근사). `§N` 은 references 로 가는 길 안내(공식 권장 패턴)라서 이력 신호에서 뺐다. luau-kb 12개는 SKILL.md 본문을 훑었고(luau-types, luau-style, luau-perf, luau-testing 은 앞부분 읽음, 나머지는 지표 위주) references 는 표본으로 `luau-types/references` 행 수만 확인했다(1,421줄, 길이 자체는 한 단계 깊이라 문제 없음).

심각도: 높음 = 발동률 또는 매 턴 비용에 직접 영향 / 본문 상당 부분이 실행과 무관. 중간 = 손봐야 하나 동작 영향 작음. 낮음 = 취향·정리.

### 3.1 second-opinion

| 대상 | desc 자수 | 본문 줄 | 이력 신호 | 문제 | 심각도 | 고칠 방향 |
|---|---|---|---|---|---|---|
| `second-opinion:context` | 448 (한글 248) | 81 | 9 (다른 §/수치 표기 포함 약 35) | (1) description 에 **비용($0.5~0.6, 30만 토큰 opus)과 "잘 잡는 것/못 잡는 것" 평가문**이 들어감. 모든 세션이 지불하는 자리에 설계 평가가 있음. (2) 본문 첫 절이 **"근거는 audit/18 §11·§12 다"** 로 시작해 실험 요지 5줄(0/6, 4/8, 3/12…)이 실행 지시보다 먼저 옴. (3) 후행 프롬프트 뒤 "실험(§12)에서는 … 5회 한도는 그대로 재지 않았다", "§11.2 의 주장 목록 효과와 같다" 등 `§` 인용이 이유 칸에 흩어짐. (4) 비용 절이 실측 수치 나열. (5) 한국어 description 이라 영어 모델용 텍스트 정책과 불일치 | 높음 | §5 시안: description 을 "무엇+언제+부정 조건" 으로, 근거·실험은 `references/rationale.md`, 비용은 한 줄 요약만 본문에 |
| `second-opinion:audit` | 533 (한글 244) | 69 | 6 | context 와 같은 구조. description 에 비용($1.0~1.2, sonnet 약 $0.4, 2~3분)과 "잘 잡는 것/못 잡는 것", "advisor 는 평소에 쓰지 않는다" 같은 **정책 논쟁**이 섞임. 본문 앞부분에 `audit/18` §1·§3.3·§9·§11 인용 3곳(advisor 암호화, 가격 대비 효용). 비용 절(§5)에 실측 | 높음 | context 와 같은 방식. advisor 정책 문장은 CLAUDE.md/rules 가 정본이므로 스킬에서는 한 줄 포인터만 |
| `agents/reviewer.md` | 약 170 | (66) | - | description 은 "무엇+누가 부르는가" 로 좋다. 모델용 본문이 한국어 | 낮음 | 언어 정책 적용 시 영어 전환 대상 |
| `agents/other-frame.md` | 약 150 | (30) | 2 (`audit/18 §11` 인용: "이 경로가 강했던 것") | 본문에 "특히 볼 곳 (audit/18 §11 에서 이 경로가 강했던 것)" 이력 괄호. 지시 자체는 유효 | 낮음 | 괄호 제거, 한국어 출력 지시는 유지 |

### 3.2 q 플러그인

| 대상 | desc 자수 | 본문 줄 | 이력 신호 | 문제 | 심각도 | 고칠 방향 |
|---|---|---|---|---|---|---|
| `q:start` | 137 | 116 | 0 | 줄 수가 가장 큼. 4단계 온보딩 대화 진행 지침이라 본문이 길 이유는 있고 `references/`·`templates/` 로 이미 분리됨. 본문 중 교육 문구가 SKILL.md 에 인라인인지는 전수 확인 못 함 | 낮음 | 현 구조 유지. 120줄 안에서 references 로 더 보낼 인라인 교육 문구가 있는지만 점검 |
| `q:doctor` | 301 | 86 | 1 | description 이 검사 항목 괄호 목록으로 길고 한국어. 본문은 지시형(원칙 6개, 예외 없음)으로 공식 패턴에 가장 가깝다. `disable-model-invocation: true` 적절(수정 승인 흐름) | 낮음 | 언어만(영어 전환 시). 괄호 목록은 references 로 |
| `q:away` | 114 | 37 | 2 | 본문에 "쉬운 설명(사용자에게 물으면 이대로)" 블록이 있음. 이는 모델용 지시가 아니라 **사용자용 안내문 원고**라서 한국어가 맞다(사용자에게 그대로 전달). 말미 `audit/21` 포인터 1줄은 무해. `disable-model-invocation` + `allowed-tools` 사용 기준에 정확히 맞음 | 낮음 | 현 상태 유지. 사용자 전달용 문구는 한국어 유지를 명시 |
| `q:back` | 80 | 11 | 1 | 문제 없음. 짧고 frontmatter 적절 | 없음 | - |
| `q:checkpoint` | 300 (영어) | 21 | 1 | **이미 영어**이고 "무엇+언제"가 맞다(`Use before /compact, before a handover…`). 3인칭이 아니라 명령형 "Flush…" 로 시작하지만 공식 패턴과 같은 급. 본문도 번호 절차+Notes | 없음 | 참조 모범. 같은 플러그인 안에서 `import` 와 함께 영어이고 나머지는 한국어라 **언어가 섞임** |
| `q:import` | 304 (영어) | 25 | 1 | checkpoint 와 같음 | 없음 | 참조 모범 |

### 3.3 luau-kb

공통 문제 두 가지가 12개 전체에 걸쳐 있다.
(a) **description 이 "무엇"을 서술하는 데 600~900자를 씀**: 주제 키워드 나열(예: luau-testing 의 괄호 속 괄호). 공식 패턴의 "한두 문장 + 트리거 목록" 대신 **목차 전체**가 들어갔다. 이는 확인한 본문 라우팅 표와 중복이다. 한 스킬당 모든 세션에서 약 600~900자를 냄.
(b) 한국어, 그리고 조사형 서술("…를 다룬다") 이라 3인칭 서술형으로는 규칙에 맞지만, 명령/조건("쓴다") 이 뒤섞임. 문제는 시점이 아니라 길이와 언어다.

| 대상 | desc 자수 | 본문 줄 | 이력 신호 | 문제 | 심각도 | 고칠 방향 |
|---|---|---|---|---|---|---|
| `luau-testing` | **892** (한글 386) | 57 | 5 | 1,024 상한에 가장 가까움(API 업로드 시 위험). 마지막에 "**이 사용자 저장소들의 실제 테스트 방식**" 같은 환경 종속·시점 종속 서술("현황"). description 이 주제 12개 나열 | 높음 | 300~500자로. 주제 나열은 SKILL.md 라우팅 표에 이미 있음 |
| `luau-verify` | 771 | 56 | 6 | 도구 버전("0.734/0.742"), 정책 ID("D-01"), 스니펫 표식 8개를 description 에 나열. 시간에 민감한 정보(B "Avoid time-sensitive") | 높음 | 버전·D-NN·표식 목록은 본문/references 로. description 은 "검증 절차와 도구 호출법 + 언제" |
| `luau-types` | 729 | 78 | 6 | description 에 버전("0.734 와 0.742 사이"), 용어 20여 개 나열. 본문에 `D-04` 정책 ID, `luau-lsp 1.69.0` 같은 버전 특정 서술. 본문은 결정 트리+라우팅 표라서 구조는 공식의 "Pattern 2" 에 가깝고 좋음 | 높음(desc) / 중간(본문) | description 축소, 버전·D-NN 은 references 로 |
| `luau-perf` | 703 | 46 | 3 | description 에 "luau 0.742 의 -O1·-O2·--codegen 세 모드로 다시 잰 비율" 같은 측정 방법·버전 서술. 본문 말미에 **절대 경로** `/code/Projects/luau-kb/bench/*.luau`, 결과 파일명 `results/2026-11-10.tsv`(날짜), 원천 `audit/08`·`09` 인용(줄 56·59) | 중간~높음 | 경로·날짜·원천은 references 의 출처 절로. 플러그인 설치 시 절대 경로는 깨짐 |
| `luau-style` | 679 | 83 | 4 | description 마지막에 이웃 스킬 5개를 가리키는 "다른 스킬이 다룬다" 문장 길이 약 200자. 본문 83줄 중 앞부분은 판단 트리(좋음). "결정 상태(확정/제안)" 같은 저장소 정책 상태를 스킬이 들고 있음 | 중간 | 이웃 스킬 안내는 짧게(1줄). 결정 상태는 `references/project-overrides.md`(이미 있음)에만 |
| `luau-upstream` | 603 | 58 | 3 | 주제 자체가 "빠르게 바뀌는 생태계"라 시간 민감 내용이 본질이다. description 이 "luau 주간 릴리스, rfcs, luau-lsp, StyLua, rojo, FFlag…" 로 길다 | 중간 | 시간 민감 부분(현재 진행 중인 변화 요약)을 references 로 분리해 본문은 절차(감시·bug-scan)만 |
| `roblox-engine` | 620 | 43 | 2 | description 에 API 이름 나열 18개 이상. 본문은 라우팅 표 위주로 양호 | 중간 | 주제 5~6개로 축약 |
| `luau-runtime` | 490 | 41 | 1 | 괄호 속 증상 서술("ephemeron 없음 — 값이 키를 잡으면 영구 잔존…")이 description 에 들어 있음. 이는 본문 내용 | 중간 | 증상 서술은 본문으로 |
| `luau-roblox` | 409 | 40 | 4 | 양호. 부정 조건("엔진 동작은 roblox-*") 이 있어 공식 패턴과 일치 | 낮음 | 언어 정책 외 변경 없음 |
| `roblox-net` | 317 | 35 | 1 | 길이·구성 양호(무엇+언제). 한국어 | 낮음 | 언어 정책만 |
| `roblox-world` | 301 | 31 | 1 | 양호 | 낮음 | 언어 정책만 |
| `roblox-docs` | 262 | 43 | 2 | 양호. 도구 사용법 스킬이라 description 이 "무엇+언제" 로 짧음 | 낮음 | 언어 정책만 |

종합: luau-kb 본문은 대체로 **지시형 + 라우팅 표** 라서 공식의 "목차+참조" 패턴과 맞는다. 본문 상한 500줄에는 모두 한참 못 미친다(31~83줄, [측정]). 병목은 description(`112~892자` 중 상위 7개가 600자 이상)이다.

## 4. 공통 개선 원칙 초안

1. **description 은 "무엇 + 언제 + 아닐 때" 만.** 목표 300~500자(상한은 Claude Code 1,536, API 1,024지만 상한은 목표가 아니다). 주제 키워드 나열, 비용·수치, "잘 잡는 것/못 잡는 것" 평가, 버전 번호, 정책 ID(D-NN)를 넣지 않는다. 근거: 모든 세션이 매 턴 낸다(A), 1%에 넘치면 덜 쓰는 스킬의 description 이 먼저 빠진다(A), 공식 예시는 한두 문장+트리거(B).
2. **SKILL.md 는 실행 지시만.** 설계 근거, 실험 수치, audit 인용, 날짜, "사용자 결정" 서술은 `references/rationale.md`(스킬 폴더 안, SKILL.md 에서 한 줄로 링크) 또는 audit 문서로 옮긴다. 단 **작업을 올바르게 하는 이유**(예: "범주 목록을 빼면 설계를 다시 열지 않는다")는 skill-creator 의 "Explain the why" 에 해당하므로 본문에 **한 문장**으로 남긴다. 판별 기준: "이 문장을 빼면 모델의 행동이 바뀌는가". 바뀌면 지시나 이유, 안 바뀌면 이력.
3. **비용은 한 줄 요약만 본문에** (비용 고지가 정책이므로 사용자 결정 지점에는 필요). 구성 내역(캐시 읽기 비율, TTL별 재작성 비용)은 rationale 로.
4. **시간 민감 정보는 본문 밖**: 버전 번호, 파일 날짜, 절대 경로. B 의 "old patterns" 처럼 references 의 출처·이력 절에 둔다.
5. **`§N` 라우팅은 유지**, `audit/NN §N` 근거 인용은 rationale 로. 전자는 공식이 권하는 progressive disclosure, 후자는 이력이다.
6. **참조는 한 단계 깊이, 100줄 넘는 reference 는 목차** (B). luau-kb 가 이미 지키고 있는지 표본 확인(`luau-types/references` 1,421줄 합계)은 했으나 개별 목차 유무는 미확인.
7. **frontmatter 기준**: `disable-model-invocation: true` 는 부작용·시점 통제가 필요한 워크플로(away, back, doctor, start 처럼 승인 흐름)에만. 지식 스킬(luau-kb)은 기본값. `allowed-tools` 는 그 스킬이 실제로 쓰는 명령에 한정(q:away 처럼 `Bash(python3 *subagent_ledger.py *)` 수준).
9. **Claude is smart: 나열 대신 원리.** 발동 상황을 "결론·결정·계획", "apply·install", "diff·코드" 처럼 늘어놓으면 오히려 좁아진다. 원리 한 줄로 넓게 쓰고, 선택지는 줄이고, 지시마다 이유를 설명한다(공식 best-practices, skill-creator "Explain the why"). "대화 전체를 읽는다" 같은 비싸 보이는 표현 대신 "prompt cache 와 함께 fork" 처럼 맥락으로 비용을 알린다.
10. **description 은 언제 + 무엇, 본문은 사용법.** 모델은 description 으로 부를지 정한 뒤 "어떻게 부르지?" 하고 본문을 연다. 본문에 "When" 절이나 description 을 되풀이하는 머리줄을 두지 않는다. description 은 skill-creator 가 말하듯 조금 pushy(undertriggering 방지)하게 쓴다.
11. **발동 조건은 에이전트 자신의 필요로.** "사용자가 기댈 것" 이 아니라 "내 생각에 다른 의견을 듣고 싶을 때, 놓친 것을 점검하고 싶을 때". 사용자 요청을 기다리지 않아도 된다고 적는다.
12. **모델 사이 텍스트는 영어, 사람에게 그대로 전할 문구만 한국어.** fork·리뷰어에게 주는 지시와 그 출력은 영어(메인이 읽고 쓸모 있어야 한다). 사용자에게 전할 때만 메인이 한국어로 옮긴다. 사용자 원문 인용은 원문 언어 그대로. 이전 "언어 정책 제안" 3번(후행 프롬프트 한국어 유지)은 §9 A/B 로 대체됐다.
13. **결과 처리**: 스스로 부른 검토는 메인이 확인해 받아들임/버림을 1~3줄로 알리고, 사용자가 요청한 검토는 전문을 보인다.
8. **평가**: 큰 개편 전에 should/should-not trigger 질의 20개 정도(영어 10, 한국어 10)를 skill-creator 의 description 최적화 방식으로 돌려 기준선을 만든다. `/skill-doctor` 로 컨텍스트 비용 상위를 확인한다. 현재 이 하네스에 이런 트리거 실측이 있는지(`/tmp/trig` 에 흔적)는 이 감사에서 읽지 않았다.

### 언어 정책 제안

사실 정리
- 공식 문서는 언어를 규정하지 않는다 [미확인]. 따라서 "영어여야 한다"는 규칙은 없다. 공식 스킬이 전부 영어인 것은 관례일 뿐이다.
- 이 하네스의 모델 주입 텍스트(훅 메시지, rules)는 이미 영어로 통일했다(사용자 결정).

영어 쪽 장점
- 토큰 효율이 좋다 [측정·추정]: 시안에서 같은 지시가 한글 약 2,150자(≈1.9k+ 토큰 추정)에서 영어로 약 0.7~0.8k 로 줄었다(§5). 모든 세션 description 은 특히 크다.
- 모델의 지시 이행 안정성은 영어가 높다는 것이 일반적 통념이지만, 이 감사에서 한국어 대 영어로 **측정하지 않았다** [추정].
- 공식 스킬·skill-creator 의 문체와 같아 도구(description 최적화 스크립트)가 가정한 입력과 맞는다.
- 하네스 전체가 영어로 통일되어 있어 스킬만 한국어이면 규칙이 갈린다.

한국어 쪽 장점·위험
- **발동률**: 스킬 선택은 모델이 description 과 사용자 메시지를 의미로 매칭한다. 사용자가 한국어로 말하는데 description 이 영어면 매칭이 약해질 가능성이 있다 [추정, 미측정]. 현대 모델은 교차 언어 매칭이 강하므로 큰 문제는 아닐 가능성이 높지만, 짧은 한국어 구어("한 번 더 봐줘")는 영어 description 과 거리가 멀 수 있다.
- 사용자가 직접 읽고 고치는 문서라 한국어가 편하다.
- 이 저장소에 이미 한국어 트리거 키워드 실험 흔적(`/tmp/trig`, `/tmp/kbneg`)이 있다. 결과를 이 감사에서 읽지 않았다 [미확인].

제안 (사용자가 결정할 것, 아래는 권고)
1. **본문과 에이전트 정의는 영어.** 모델만 읽는 텍스트이고 토큰·통일성 이득이 크고, 위험이 낮다.
2. **description 은 영어 본문 + 한국어 트리거 구절 1~3개**를 끝에 붙인 혼합("Triggers also on '한 번 더 봐줘'"). 발동률 우려를 싸게 막는다. 시안이 이 형태다. 이 혼합이 한국어 전용보다 발동률이 같거나 낫다는 것은 **추정**이므로, 적용 전에 §4-8 의 질의 세트로 확인한다.
3. **사용자에게 그대로 전달하는 문구와 실험으로 굳힌 프롬프트 원문은 한국어 유지.** 예: `q:away` 의 "쉬운 설명", context 의 후행 프롬프트(출력 "한국어" 지시 포함). 번역하면 실험으로 정한 동작이 바뀔 수 있다. 영어 전환 후에도 같은 효과인지는 별도 실험이 필요하고 이 감사의 범위가 아니다.
4. 응답 언어는 "사용자에게 보이는 최종 응답은 한국어"라는 한 줄을 스킬이 아니라 CLAUDE.md/rules 에 둔다(스킬마다 반복하지 않는다).
5. 전환 순서: second-opinion 2개 → q(이미 2개가 영어) → luau-kb. luau-kb 는 description 길이 정리와 같이 한 번에 한다(한 번만 건드린다).
- **부정 조건보다 언제·어떻게**: "쓰지 말 것" 을 늘어놓지 않고 "언제 부르는가" 와 "어떻게 부르는가" 를 중심으로 쓴다. 상대 스킬은 description 에 짧은 한 구절로만 가리킨다.
- **스킬 하나 = 한 가지**: 한 스킬이 여러 경로(fork, 다른 프레임)를 품지 않는다. 사용자 명령은 따로 두고 `disable-model-invocation` 을 건다.
- **수단이 아니라 목적 기준**: 이름과 구분을 "무엇을 확인받으려는가" 로 짓는다(`fresh-advisor`: diff·주장 반박, `inherit-advisor`: 대화 흐름의 빈 곳). 내장 `advisor` 도구와 헷갈리지 않게 본문에 "advisor 도구를 부르지 않는다" 를 한 줄 둔다.

## 5. 대표 시안: `second-opinion:context`

원칙대로 **형식과 배치만** 바꿨다.
- 바꾸지 않은 것: 후행 프롬프트 원문(한국어, 글자 그대로), "요구 대조" 한 줄 원문, 실행 절차, 명령줄, 가드, 모델 지시, 결과 처리 규칙.
- 옮긴 것: `audit/18` 근거 5줄 요지, "실험에서는 … 5회 한도는 그대로 재지 않았다", §11·§12 인용, 비용 구성 내역, 모델별 §11 결과 서술 -> `references/rationale.md`(실제 파일 생성은 하지 않음, 내용은 원본에서 그대로 이관).
- 남긴 이유 문장: "범주 목록을 빼지 않는다"(행동 지시), "범주 2 에 구체적 의심을 넣지 않는다 + 넣으면 그쪽만 본다"(행동 지시+이유 한 문장), 비용 한 줄(고지용).
- description: 비용·"잘 잡는 것/못 잡는 것" 제거, 영어, 3인칭 서술("Runs a second opinion…"), 부정 조건 한 문장, 한국어 트리거 3개.
- 한 가지 흔적 변경: 원본 "비용: …" description 의 수치가 빠지므로 비용 수치는 본문 한 줄(Cost:)로 옮겼다.

````markdown
---
name: context
description: Runs a second opinion that inherits the current conversation. Turns a fork of the session into an independent reviewer that looks for what the flow missed, wrong premises, unchecked assumptions, and counterexamples to the design just finished. Use at turning points on long sessions with many decisions - before moving to the next work unit, before telling the user to apply/deploy/install or confirming a decision, before changing direction or asking the user to decide, before merging parallel subagent results. Does not catch implementation bugs that need reproduction (use second-opinion:audit). Triggers also on "한 번 더 봐줘", "다른 눈으로 검토", "맥락 검토".
argument-hint: "[fork|other-frame] [one-line note]"
---

# second-opinion:context

A fork that has read this conversation reviews it as an independent reviewer. It complements `second-opinion:audit` (which refutes a diff); it does not replace it. Design basis and measurements: `references/rationale.md`.

## When to use

| Moment | Path |
|---|---|
| Finished a work unit, about to move on | fork |
| About to propose a decision or direction change to the user | fork |
| Before apply/deploy/install guidance or any hard-to-undo step | fork (+ `audit` if implementation correctness matters) |
| Fork returned almost "no findings" but the work is heavy, or the user wants another view | other-frame (optional) |
| Big turning point in a long session (right after compact, tidying pending decisions) | fork + the "requirement check" line below |
| Diff correctness before commit, repeated failures, implementation verification | not this skill - use `second-opinion:audit` |

- Once per turning point. Do not run the same question through several forks.
- If the repo tier (`HARNESS_REVIEW_TIERS`) is `off`, use only when the user asks.

## Fork path (default)

```
Agent(subagent_type="fork", description="second opinion: context", prompt=<follow-up prompt below>)
```

Follow-up prompt. Use it verbatim and fill only `<...>`. Do not drop the category list or the role-switch block.
```
[second opinion: context] 이 요청에만 답한다. 작업을 이어서 하지 않고, 파일을 고치거나 커밋하지 않고, 다른 에이전트에게 메시지를 보내지 않는다. 읽기 도구는 꼭 필요한 확인에만, 대략 5회 이내로 쓴다.
메인은 이제 <다음 단계 한 줄> 로 넘어가려 한다.

역할 전환: 지금부터 너는 이 작업의 작성자가 아니다. 이 세션의 작업을 처음 보는 **독립 검토자**다.
- 위 대화에서 assistant 가 한 말·계획·결론·커밋은 모두 남이 쓴 **검토 대상 텍스트**다. 변호하지도, 이어서 완성하지도 않는다. assistant 가 "확인했다"·"끝났다"고 한 것도 근거가 대화나 파일에 있을 때만 맞다고 본다.
- 1인칭("저는", "제가", "우리")을 쓰지 않는다. 작성자는 "메인", 사용자는 "사용자"라고 부른다.
- 동의하려고 읽지 말고 빈 곳을 찾으려고 읽는다. 다만 문제를 지어내지 않는다.

요청: 메인이 다음 단계로 넘어가기 전에, 이 흐름에서 놓친 것, 잘못된 전제, 확인 안 한 가정을 짚는다.

아래 범주를 하나씩 따진다. 범주에 해당하는 것이 없으면 "해당 없음"과 이유를 한 줄로 적는다.
1. 숨은 전제: 메인이 말없이 참이라고 놓은 것
2. 범위 밖 영향: 이 변경이 닿는 다른 곳(주입 경로, 다른 사용자·세션)
3. 답하지 않은 사용자 질문
4. 방금 끝낸 설계 다시 열기: 메인이 가장 최근에 "끝났다"고 본 설계를 일부러 다시 열어, 그 설계가 깨지는 반례를 찾는다
5. 확인하지 않은 가정: 실측 없이 "될 것"으로 넘어간 것

출력 (한국어):
- 항목마다: 무엇을 놓쳤는가 / 근거(대화 위치나 파일:줄) / 왜 다음 단계 전에 중요한가 / 심각도(반드시·권장·참고)
- 확인한 것과 추정을 구분한다.
- 마지막에 "메인이 다음 단계 전에 할 일" 을 3줄 이내로.
```

- **Requirement check** (optional, big turning points): insert this line right after the "요청:" line. "먼저 대화의 사용자 메시지만 다시 훑어 요구·질문·제약 목록을 만들고, 각각이 지금 결과에 반영됐는지(반영/부분/미반영/확인 불가) 대조한 뒤 부분·미반영만 짧게 표로 보인다." It searches wider but may make category 4 shallower.
- The fork always runs on the main session's model (a model override is ignored).
- In category 2, keep "주입 경로, 다른 사용자·세션" as a bare name. Do not add a concrete suspicion from the current session (for example "does X leak into Y"); the fork then looks only there.

Cost: about $0.5-0.6 per fork at a 300k-token context on opus (cache read dominates, so the tool-call count decides cost). Call it right after the main response while the cache is warm; a cold cache adds about $1.5 (5m) to $2.4 (1h). The report (2-3k tokens) stays in main context. Tell the user when this is a non-trivial spend.

## other-frame path (optional)

Reads a text copy of the main conversation under a different system prompt (`agents/other-frame.md`).
```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/context/scripts/ask-other-frame.py" --model <sonnet|opus> --note "<one-line next step>"   # run in background
```
- `scripts/render-transcript.py` builds the copy: from the last compact boundary, tool results cut to the first 300 characters.
- Do not pass the copy through the Agent tool; retyping it costs main output tokens.
- The script installs the read-only guard (`hooks/auditor-readonly-guard.py`) itself via `--settings`.
- Cost: first call is a cache write, proportional to context. At 132k tokens: opus $1.25, sonnet $0.49; the same copy asked again within 1 hour on opus $0.33.
- Model: use opus for high-tier work.

## Handling the result

Same as `second-opinion:audit` section 4. Show the report to the user unsummarized, mark each finding accepted / rejected / needs check with evidence, and record it in the ledger (`--kind context --reviewer fork|ctx-opus|ctx-sonnet`).
- Head the report "context review (fork)" so it does not read as the main agent's own text.
- If a finding contradicts the facts (claims something undone that is done, treats running work as failed), verify, then reject it with evidence.
````

### 크기 비교 (시안 파일을 /tmp 에서 같은 방식으로 측정)

| 항목 | 원본 | 시안 | 변화 |
|---|---|---|---|
| 파일 줄 수(frontmatter 포함) | 92 | 78 | -15% |
| 본문 줄 수 | 81 | 73 | -10% |
| 파일 글자 수(문자) | 4,723 | 5,148 | **+9%** (영어가 같은 뜻에 글자가 더 듦) |
| 한글 글자 수 | 2,150 | 634 | -71% (남은 한글은 후행 프롬프트 원문과 트리거 구절) |
| description 글자 수 | 448 | 650 | +45% (한글 248자 → 16자) |
| 토큰 추정 | 약 2,650 | 약 1,820 | **약 -31%** |

토큰 추정은 한글 1자 ≈ 0.9 토큰, 그 외 4자 ≈ 1.1 토큰으로 둔 **거친 추정**이고 실제 토크나이저로 재지 않았다 [추정]. 글자 수가 늘어도 토큰은 줄어든다는 방향성만 믿는다.

정직한 평가
- 줄 수와 파일 크기의 절감이 **크지 않다**. 후행 프롬프트(약 25줄)가 파일의 큰 몫이고, 이는 동작이라 못 건드린다. 이 시안의 이득은 크기보다 (1) 근거 5줄 + 실험 서술 약 10줄 + 비용 구성 약 6줄을 본문 밖(rationale)으로 뺌, (2) description 에서 비용·평가문을 뺌, (3) 영어 전환으로 토큰 절감이다.
- description 은 오히려 길어졌다(650자). 영어가 길고 트리거를 더 구체적으로 적었기 때문이다. 공식 중앙값(약 800자)보다는 짧지만 §4-1 의 목표(300~500)에는 못 미친다. 줄이려면 "Use at turning points…" 열거를 두 항목으로 줄이면 된다(예: 약 480자). 시안은 동작 보존을 우선해 열거를 그대로 두었다.
- 비용 절은 한 줄로 줄였지만 비용 고지 정책 때문에 완전히 빼지는 않았다.

## 6. 읽지 못했거나 불확실한 것

- `update-config` 등 번들 스킬의 실제 SKILL.md 는 파일로 없어서 못 봤다. 공식 스킬 표본은 claude.ai 동기화본 14개다.
- luau-kb 의 references 는 합계 줄 수만 확인했다. 개별 파일의 목차 유무, 깊이 위반 여부는 미확인.
- luau-kb 본문은 4개(types, style, perf, testing)만 앞부분을 읽었고 나머지 8개는 지표와 라우팅 표 위주로 판단했다.
- q:start 본문 120줄 중 인라인 교육 문구의 분량은 전수 확인하지 않았다.
- 한국어 vs 영어 발동률은 실측이 없다. `/tmp/trig`, `/tmp/kbneg` 에 이전 트리거 실험 흔적이 있으나 읽지 않았다. 언어 정책 적용 전에 확인할 것.
- 이력 신호는 정규식 근사라 스킬 간 비교용이고 정확한 개수가 아니다.
- 코드 블록 안 후행 프롬프트와 "요구 대조" 문장은 동작이므로 시안에서 번역·수정하지 않았다.

## 7. 1단계 적용 결과 (2026-11-11)

적용 범위: `second-opinion` 의 context·audit·에이전트 2개, `q` 의 start·doctor·away·back(checkpoint·import 는 description 만 점검, 변경 없음). luau-kb 는 범위 밖.

| 스킬 | description 전→후(자) | SKILL.md 줄 전→후 | rationale 신설 |
|---|---|---|---|
| second-opinion:context | 448 → 475 | 92 → 78 | `references/rationale.md` (근거·실험·비용 전부) |
| second-opinion:audit | 533 → 482 | 81 → 67 | `references/rationale.md` (advisor 비교·비용·측정) |
| q:start | 137 → 355 | 122 → 120 | `references/rationale.md` (동의 원칙·설계 이유) |
| q:doctor | 301 → 371 | 92 → 88 | 없음(옮길 근거가 없었음) |
| q:away | 114 → 275 | 44 → 44 | `references/rationale.md` (audit/21 포인터·언어 이유) |
| q:back | 80 → 186 | 17 → 18 | 없음 |
| q:checkpoint, q:import | 300, 304 | 25, 29 | 변경 없음 |
| agents/reviewer, other-frame | 영어화(본문 66→66, 30→28줄) | - | other-frame "볼 곳"의 근거는 context rationale 에 |

- 한국어로 남긴 것: context 후행 프롬프트 원문과 "요구 대조" 줄(verbatim 지시로 감쌈), 에이전트 보고 틀(사용자에게 그대로 전달), start 의 질문·체크리스트 표·제안 틀·안내문, away 의 "쉬운 설명", doctor 보고 형식의 상태 어휘, 각 description 끝의 한국어 트리거.
- 일부 description 이 길어진 이유: 한국어 한 구절이 영어로 늘었고, 사용자 호출 전용 스킬에는 "User-invoked only" 와 트리거를 붙였다. 모두 500자 이하.
- 검증: `claude plugin validate` q, second-opinion, 마켓 전체 통과. 훅·가드·doctor·session_log 테스트는 적용 전과 동일 통과(second-opinion 20/20·9/9, home hooks 52/26/18/72/132, doctor 16/16, session_log OK).
- 발동 점검(sonnet, `-p`, 합계 약 $0.9): 새 description 으로 "이 diff 커밋 전에 검토해 줘"(2종 질문)와 "완료 선언 전 독립 검증" 은 `second-opinion:audit` 을 **부르지 않았다**(0/2, 모델이 직접 git diff 로 검토). 무관 질문(파이썬 리스트)은 호출 없음(음성 통과). 변경 전 description 으로도 같은 질문에서 호출되지 않았다(0/1). 즉 이번 변경이 발동률을 떨어뜨린 근거는 없으나, 원래 `-p` 단발 질문에서는 이 스킬이 잘 안 불린다. 표본이 작아 결론이 아니다. 발동률 개선은 CLAUDE.md 시점 안내와 훅 알림(`<harness-hook name="second-opinion">`)에 기대고 있고, description 만으로는 부족할 수 있다. 별도 발동 실험이 필요하다.

## 8. 2단계 재구성 결과 (2026-11-11)

목적 기준으로 `second-opinion` 을 다시 나눴다: `context`+`audit` -> `inherit-advisor` / `fresh-advisor` / `other-frame`(사용자 명령).

- **fork 후행 프롬프트 훅 펼침(B안) 실측**(sonnet `-p`, 비용 약 $0.1): PreToolUse matcher `Agent`(입력의 `tool_name` 도 `Agent`)가 `subagent_type="fork"` 호출에 걸린다. `permissionDecision: "allow"` 와 `updatedInput`(전체 입력 객체)을 주면 fork 가 바뀐 prompt 를 받았다(마커 응답으로 확인). 메인 트랜스크립트의 tool_use 에는 모델이 쓴 원래 표지가 남고, fork 트랜스크립트에는 바뀐 prompt 가 들어간다. 공식 문서: `permissionDecision` 없이 `updatedInput` 만 주면 auto 모드가 바뀐 호출을 거절할 수 있다. 그래서 B안 채택. `Task` matcher 는 같이 걸어 두었으나(구버전 이름) 단독 실측은 하지 않았다.
- **구조**: 표지(`[second-opinion:inherit] Review only...` + `next:` + `options: reqs`)를 메인이 보내고 `hooks/expand-inherit-prompt.py` 가 `templates/fork-prompt.md`(원문 그대로) 로 바꾼다. 표지가 아니거나 템플릿이 없으면 통과(표지 자체가 검토 전용 지시).
- **발동 점검**(sonnet `-p`, 맥락 있는 조건, 약 $0.19): "동료 머신에 설치해도 되는가" 결론 직전에 모델이 `inherit-advisor` 를 스스로 불렀고, 표지 형식의 Agent 호출을 보냈으며, fork 트랜스크립트에서 템플릿 전문(역할 전환 + `next` 채움)을 확인했다(1/1, 표본 1).
- **전후 크기**(description 자 / SKILL.md 줄): context 475/78 -> inherit-advisor 500 이하/42, audit 482/67 -> fresh-advisor 489/65, other-frame 신설 398/24. inherit-advisor 는 후행 프롬프트 원문과 요구 대조 줄이 `templates/` 로 나가 본문이 줄었다.
- 동작은 바꾸지 않았다(리뷰어 절차, ledger, 가드, nudge 시점). nudge 훅 메시지의 스킬 이름만 새 이름으로 바꿨고, ledger 는 옛 `--kind context|audit` 를 계속 받는다(`inherit` 추가).

## 9. 3단계 결과 (2026-11-11)

범위: `plugins/second-opinion` 의 fork·리뷰어 지시·출력 영어화, 본문 사용법화, CLAUDE.md 정본의 second opinion 절, 이 문서. 커밋하지 않았다.

**A/B: fork 후행 템플릿, 한국어 V2 대 영어판** (sonnet, `claude -p --resume --fork-session`, 도구 없음, 각 2회)
- 장면: §12 의 원본 장면(30만 토큰 사본)은 재현할 수 없어 비슷한 합성 장면을 새로 만들었다(`/code/.cache/so-ab/w/scene.md`). 사용자가 훅의 `seen.json` 중복 방지 설계를 맡기고, 메인이 "설계 끝, 로컬 테스트 통과"로 말한 뒤 동료 배포 안내를 쓰려는 지점. 심은 약점: 읽기-수정-쓰기 경합(방금 끝낸 설계의 반례), 근거 없는 "테스트 통과", 답 못 받은 Windows 질문, 24시간 TTL 임의 결정. 한계: 도구 없음(도구 호출 수는 못 잼), 메인의 마지막 응답이 이미 일부 약점을 스스로 적었다, 판정은 같은 에이전트 한 명이 매겼고 표본이 작다. 방향만 읽는다.

| 판 | 끝난 설계를 다시 여는가 | 1인칭·변호 | 심은 약점 회수 | 출력 토큰 | 비용 |
|---|---|---|---|---|---|
| ko-1 | 예(경합 3종) | 없음 | 4/4 + 자리표시자 | 3,887 | $0.083 |
| ko-2 | 예(경합 4종) | 없음 | 4/4 + 자리표시자 | 4,325 | $0.088 |
| en-1 | 예(갱신 유실, 동시 중복) | 없음 | 4/4 + 자리표시자 | 2,220 | $0.065 |
| en-2 | 예(갱신 유실, 동시 중복, Windows) | 없음 | 4/4 + 자리표시자 | 2,156 | $0.055 |

- 핵심 효과는 같았고 영어판은 출력 토큰이 약 절반, 비용은 약 25~30% 낮았다. 영어판을 채택한다. 비용 하락은 출력 길이가 줄어서이며, 맥락이 큰 실제 fork 에서는 캐시 읽기가 비용 대부분이라 차이가 더 작을 것이다(추정).
- 합계(A/B 4회 + 장면 준비 + 끝에서 끝까지 시도): 약 $0.9, 상한 $2 이내.

**끝에서 끝까지**
- 맥락이 있는 합성 대화 3종과 실제 파일을 읽는 장면 1종(`-p`, sonnet, `--plugin-dir`)에서 모델은 `inherit-advisor` 를 **스스로 부르지 않았다**(0/4). 매번 직접 약점을 짚고 "설치 보류" 로 결론 냈다. 즉 이 장면들은 모델이 혼자 풀 수 있어 발동 필요가 생기지 않았다. 자발 발동 확인은 이번에 못 했다(§8 의 1/1 과 합쳐도 표본 1).
- 지시로 부르게 한 경로(skill 호출 지시): Skill -> 표지 Agent(fork) 호출 -> 훅이 영어 템플릿으로 펼침(fork 트랜스크립트에서 "Role switch" 확인) -> 결과 처리와 ledger 호출까지 동작. 모델이 ledger `--verdict partial` 을 써서(허용값 아님) 본문에 허용값을 적었다.

**전후 크기** (SKILL.md 줄 / description 자는 최종본 기준)
- inherit-advisor 42 -> 40, fresh-advisor 65 -> 56, other-frame 24 -> 28(호출·돌아오는 것·받은 뒤 구조를 갖춰 늘었다), agents/reviewer 63 -> 63, agents/other-frame 27 -> 27, brief.md 17 -> 17(영어).
- 본문에서 "When" 절, 비용 수치(rationale 로), description 되풀이 머리줄을 뺐다. description 에서 서로를 가리키는 문장을 뺐다.

**동작 변경 없음**: 가드, nudge 시점, ledger, 스크립트 옵션. 예외 하나: nudge 훅 메시지의 "relay its report verbatim" 을 "handle its findings as the skill says" 로 바꿨다(결과 처리 규칙과 충돌해서).

**luau-kb(고치지 않음), 이 원칙으로 다시 볼 곳**
- 12개 스킬 전부(`/code/Projects/luau-kb/skills/*/SKILL.md`)의 description: 나열형 상황·키워드가 많은지(원칙 9), pushy 한지(10), 에이전트의 필요 기준인지(11).
- 본문 머리의 "When to use" 류 절과 description 되풀이(원칙 10).
- 언어 정책(원칙 12): 스킬 전환 순서의 마지막 단계에서 영어/한국어 혼합 정리.
