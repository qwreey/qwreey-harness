# 19-02. 외부 사례 연구: 다른 사람들은 에이전트 하네스를 어떻게 운영하나

2026-11-10 작성. 외부 조사 4건 중 2번째다. 로컬은 읽기만 했다. 비교 대상은 다음 네 가지다.

- `PLAN.md`
- `home/.claude/`: CLAUDE.md 45줄, rules 2개, 훅 4개
- `luau-kb/`: 스킬 12개, AGENTS.md 15.6KB
- `audit/10`, `audit/16`, `audit/18`

## 근거 등급 표기

| 표기 | 뜻 |
|---|---|
| **[공식]** | 벤더 문서 원문을 이번에 직접 읽었다(code.claude.com, OpenAI, Gemini, Cline, Aider, Kiro, Cursor) |
| **[실측]** | 통제 조건이나 반복 측정이 있다. 논문 또는 수십 회 이상 돌린 평가 |
| **[소측]** | 개인이 재 본 소규모 측정. 수치는 있지만 표본이 작다 |
| **[일화]** | 개인 경험담이나 GitHub 이슈. 수치가 없거나 검증되지 않았다 |
| **(2차)** | 원문에 닿지 못해 2차 요약으로만 확인했다. 원문 표현은 다를 수 있다 |

날짜는 원문 게시일이다. 연도가 안 보이면 "연도 미표기"로 적었다.

---

## 0. 요약: 가장 중요한 외부 교훈

1. **스킬 자동 발동은 반반이다. 지식이 스킬에만 있으면 "보고 오기"는 사라지지 않는다.**
   - Vercel 평가: 56% 사례에서 스킬을 아예 부르지 않았다[실측].
   - Spence 평가: 훅이 없으면 Sonnet 4.5의 발동률은 50~55%다. 강제 평가 훅을 넣으면 100%다[소측].
   - 우리 실측(audit/16)에서도 frontend-design 자동 발동은 0/2였다.
   - luau-kb 스킬 12개의 발동 평가는 아직 하지 않았다(audit/05 §한계).
2. **상시 문서는 "목차"여야 한다. 개요·디렉터리 지도는 비용만 늘린다.**
   - ETH 논문: 컨텍스트 파일은 성공률을 거의 올리지 못했고 추론 비용은 20% 넘게 올렸다[실측].
   - OpenAI는 약 100줄짜리 AGENTS.md를 지도로만 쓰고, 지식은 `docs/`(system of record)에 둔다[일화(2차)].
   - Vercel은 40KB 문서를 8KB **색인**으로 줄였고, 그 색인이 100%를 냈다[실측].
3. **돈과 컨텍스트는 문장이 아니라 결정적 장치로 막는다.**
   - 공식 문서: CLAUDE.md는 "강제 설정이 아니라 맥락"이다. 막으려면 PreToolUse 훅을 쓰라고 한다[공식].
   - 서브에이전트 재귀 폭주와 상한 부재를 다룬 이슈가 여러 건 있다[일화].
   - Anthropic 자체 수치로 멀티에이전트는 채팅보다 약 15배, agent teams는 약 7배 토큰을 쓴다[실측/공식].
   - $589 사고 뒤에 둔 대응이 CLAUDE.md 문장뿐이라면 재발할 수 있다.
4. **compact로 오래 끄는 것보다 "기록하고 비우기(document & clear)"가 주류다.**
   - 공식: `/compact` 자체가 큰 요청이고, `/clear`는 비용이 0이다. 긴 세션은 요청마다 대화 전체를 다시 읽는다[공식].
   - audit/18에 따르면 우리 활성 세션의 맥락 중앙값은 26만~42만 토큰이다. 이 비용이 서브에이전트보다 클 수 있다[추정].
5. **교차 모델 검토는 효과가 있다. 다만 "토론"보다는 "독립 답변 + 구체적 실패 근거" 형태일 때다.**
   - 같은 계열끼리 토론하면 다수 의견에 동조하는 현상이 보고됐다. 토큰은 자기 교정보다 2~3배 든다[실측(프리프린트)].
   - 실무에서 잘 돌아간 형태는 다음과 같다[소측/일화].
     - 다른 회사 모델을 쓴다.
     - 초안 작성 맥락은 넘기지 않는다.
     - 차단(block) 판정에는 구체적인 실패 경로를 요구한다.
     - diff 크기와 위험 영역으로 걸러서 돌린다.
6. **모델 세대가 바뀌면 규칙의 절반이 빚이 된다.**
   - Anthropic은 Claude 5 세대에서 Claude Code 시스템 프롬프트를 80% 넘게 지웠다고 한다(2차).
   - Boris Cherny는 "반년마다 CLAUDE.md, 스킬, 훅을 지워 보라"고 권했다고 한다(2차).
   - 우리 규칙·훅 효과 실측의 일부는 haiku로 했다. 메인 모델(Opus 5.5)로 다시 재야 한다.

---

## 1. 사례

### 1.1 상시 지시 파일(CLAUDE.md, AGENTS.md)의 크기와 내용

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Claude Code 공식 memory 문서 | 2026-11 열람 | 파일당 200줄 미만을 목표로 한다. import는 정리에는 도움이 되지만 컨텍스트 비용은 줄이지 못한다. 서로 모순되면 "임의로 하나를 고를 수 있다". 주기적으로 `/doctor prompt-audit`를 돌리라고 한다 | [공식] |
| HumanLayer "Writing a good CLAUDE.md" | 2025-11-25 | 모델이 안정적으로 따르는 지시는 150~200개이고, 시스템 프롬프트가 이미 약 50개를 쓴다. 자기네 루트 파일은 60줄 미만이다. `/init` 자동 생성은 쓰지 말라고 한다. 린터 일은 LLM에게 시키지 말고 Stop 훅으로 돌리라고 한다 | [일화] (지시 수 수치는 외부 연구 인용) |
| Shrivu Shankar "How I use every Claude Code feature" | 2025-11-02 | 모노레포 루트 파일은 13KB이고 세션 시작 시 약 20k 토큰을 쓴다. 엔지니어 30% 이상이 쓰는 도구만 적는다. `@`-import는 매번 통째로 들어오므로 피한다. 대신 "언제, 왜 읽을지"를 적는다 | [일화] |
| Boris Cherny(Claude Code 제작자) 워크플로 | 2026-01 (InfoQ 01-10) | 팀 CLAUDE.md는 약 2.5k 토큰이다. Claude가 틀릴 때마다 한 줄씩 더하고, PR 리뷰 중에 `@claude`로 반영한다. 본인은 "커스터마이즈를 별로 안 한다" | [일화(2차)] |
| Mitchell Hashimoto "My AI Adoption Journey" | 2026-02-05 | "Engineer the harness": 에이전트가 실수할 때마다 재발하지 않게 고친다. Ghostty AGENTS.md의 각 줄은 과거의 특정 실패 하나에 대응한다. 스크립트 도구를 만들고 그 존재를 AGENTS.md에 적는다 | [일화] |
| OpenAI "Harness engineering" | 2026-02-11 | AGENTS.md는 약 100줄짜리 지도다. 지식은 `docs/`를 system of record로 둔다. 문서 정원사(doc-gardening) 에이전트가 낡은 문서를 찾아 PR을 연다. 규칙은 커스텀 린터와 구조 테스트로 강제하고, 린트 메시지에 고치는 법을 넣는다. 큰 단일 파일은 실패했다고 한다 | [일화(2차)] (원문 403) |
| ETH Zurich, arXiv 2602.11988 | 2026-02 | Claude Code, Codex, Qwen Code로 실제 이슈를 풀게 했다. LLM이 생성한 컨텍스트 파일은 성공률을 약 3% 떨어뜨리고 비용을 20% 넘게 올렸다. 사람이 쓴 파일도 이득이 약 4%로 미미했다. 디렉터리 개요는 파일 찾기를 빠르게 하지 못했다. 에이전트는 지시를 **따르기는 했다**(테스트를 더 돌리고 검색을 더 함) | [실측(2차)] |
| Vercel "AGENTS.md outperforms skills" | 2026-01-27 | Next.js 16 API 평가에서 기준선 53%, 스킬(기본) 53%, 스킬+명시 지시 79%, AGENTS.md 색인(8KB, 40KB에서 압축) 100%였다 | [실측] (자사 과제 한정) |
| Charlie Hills "Delete your CLAUDE.md", Reporails "Opus 5: Delete your CLAUDE.md?" | 2026-08-09, 2026-08-06 | Cherny가 YC 인터뷰에서 "반년마다 CLAUDE.md, 스킬, 훅을 지워 보라"고 말하고, 시스템 프롬프트 80% 삭제를 언급했다고 전한다. Reporails는 반론한다. 무작정 지우지 말고 진단하라, 훅 같은 결정적 게이트는 남기라는 것이다 | [일화(2차)] |
| "Context engineering for Claude 5" (Thariq, X 게시를 전한 글) | 2026-07-24 | CLAUDE.md에는 목적과 코드에서 추론할 수 없는 함정만 둔다. 절차는 스킬로 옮긴다. 코드를 보면 따를 규칙은 지운다. 예시보다 인터페이스를 쓴다 | [일화(2차)] |

### 1.2 스킬 발동

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Vercel (위) | 2026-01-27 | 56% 사례에서 스킬을 부르지 않았다. 명시 지시를 넣으면 발동은 95% 이상이지만 문구에 민감했다. "MUST invoke"는 프로젝트 맥락을 놓치게 했고, "먼저 탐색한 뒤 invoke"가 나았다 | [실측] |
| Scott Spence, 샌드박스 평가 | 2026-02-08 | Sonnet 4.5, 프롬프트 22개 × 2회. 훅 없음 55/50%, 단순 지시 59/50%, 강제 평가(UserPromptSubmit에서 스킬마다 YES/NO를 쓰게 함) 100/100%, LLM 사전 분류 100/100%, 내장 prompt 훅 55/41%. 발동만 되면 선택은 늘 맞았다. 문제는 발동이지 선택이 아니다. 개념적 표현으로 물으면 발동하지 않았다 | [소측] |
| Spence, 앞선 글 | 2025-11 | 전역 4/10, 로컬 5/10으로 "동전 던지기"였다 | [소측] |
| Superpowers(Jesse Vincent) | 2025-10-09 | SessionStart 훅으로 "너에게는 스킬이 있다"를 주입했다. 이후 Codex 쪽에서는 이 훅을 뺐다. Codex는 스킬을 스스로 잘 부르고, 훅이 오히려 UX를 해쳤다는 이유다 | [일화(2차)] |
| claude-code 이슈 #46952 | 연도 미표기 | 발동이 의미 매칭보다 키워드 겹침에 가깝다는 보고 | [일화] |

### 1.3 훅

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| "I built 11 Claude Code hooks, six were dead within 24h" | 연도 미표기(4-05) | 죽은 훅: 테스트 러너(저장마다 4~8초), 린트(타입 검사와 중복), **컨텍스트 경고(20분마다 울려서 훅 출력을 무시하는 습관을 들였다)**, 커밋 메시지 강제. 산 훅: git guard, 비밀 스캐너, 배포 guard. "조용하다가 중요할 때만 말하는 훅이 살아남는다" | [일화] |
| "Three PreToolUse hooks I stopped using" | 연도 미표기(6-02) | 모든 Read에 맥락을 주입하던 훅은 가장 비쌌고 모델이 무시했다. `.claude/docs/` 목록을 SessionStart에 한 번 보여 주는 방식으로 바꿨다. 매 호출 경로 검사 훅은 "모델이 경로를 위장하도록 가르쳤다". 남긴 것: SessionStart 점검, 파괴적 Bash 차단 | [일화] |
| Shrivu | 2025-11-02 | 차단은 커밋 시점(block-at-submit)에 한다. 쓰기 시점 차단은 계획 중간에 에이전트를 혼란시킨다. 힌트 훅은 막지 않는다 | [일화] |
| Blake Crosley | 연도 미표기 | 훅 95개. 모두 사고 하나에서 생겼다. "좋은 훅은 계획이 아니라 사고에서 나온다" | [일화] |
| claude-code 이슈 #3523 등 | 2025 | 훅 설정이 세션 중 중복 누적되어 느려지거나, settings.local.json에 훅 수천 개가 쌓인 사례 | [일화] |
| Boris Cherny | 2026-01 | PostToolUse 포맷 훅 하나(`bun run format || true`)와 `/permissions` 사전 허용 | [일화(2차)] |

### 1.4 서브에이전트, 멀티에이전트, 비용

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Claude Code 공식 비용 문서 | 2026-11 열람 | 기업 평균은 활성일당 약 $13, 90%가 $30 미만이다. agent teams는 plan mode 기준 약 7배다. 긴 세션은 요청마다 대화 전체를 cached rate로 다시 읽는다. `/compact`는 그 자체로 큰 요청이고 `/clear`는 0이다. `/usage`가 스킬, 서브에이전트, MCP별 사용 비중과 권고를 보여 주고(`f`로 적용), `/insights`가 세션 습관을 보고한다. `--max-budget-usd`가 있다 | [공식] |
| Anthropic 멀티에이전트 리서치 시스템 | 2025-06-13 | 에이전트는 채팅의 약 4배, 멀티에이전트는 약 15배 토큰을 쓴다. 성능 분산의 80%를 토큰 사용량이 설명한다 | [실측(2차)] |
| Cognition "Don't Build Multi-Agents" | 2025-06-12 | 쓰기가 많은 코딩에서 멀티에이전트는 맥락이 끊겨 취약하다. 전체 트레이스를 공유하라고 한다. 2026-04 후속 글도 "대부분은 여전히 하지 말라"는 입장이다 | [일화] |
| Shrivu | 2025-11-02 | 커스텀 서브에이전트는 "취약하다". 맥락을 숨기고 사람이 정한 경직된 흐름을 강요한다. 대신 내장 Task로 일반 에이전트를 복제한다(Master-Clone) | [일화] |
| claude-code 이슈 #68619, #82565, #69578, #72861, #94013 | 2026 | 서브에이전트 재귀 50단계, 3개 요청에 24개 실행, 백그라운드 3개가 승인 없이 1.7M 토큰, Max 플랜 초과 과금 $27.6. 공통 요청은 "토큰·시간 상한과 kill switch" | [일화] |
| Anthropic 주간 한도 도입 | 2025-07-28 발표, 08-28 시행 | "24/7로 돌리는" 사용자와 다중 인스턴스 사용자가 원인으로 지목됐다 | [공식(2차 보도)] |
| Steve Yegge, Gas Town | 2026-01 | 다수의 Claude Code를 오케스트레이션했다. "하루 수백 달러", 출시 주에 계정 3개, Max가 바닥나면 Codex로 대체. 이후 모델 교체(Opus 4.7)와 함께 "솔기가 터졌다"고 한다 | [일화(2차)] |
| METR RCT | 2025-07-10 | 숙련 OSS 개발자 16명, 과제 246개. AI를 쓰면 19% 느렸는데 본인들은 20% 빨랐다고 믿었다 | [실측] (초기 2025 도구) |

### 1.5 병렬 세션과 worktree

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Boris Cherny | 2026-01 | 로컬 5개(탭 번호, 시스템 알림)와 웹 5~10개. worktree가 아닌 **별도 checkout**을 쓴다. 세션의 10~20%는 버린다 | [일화(2차)] |
| Simon Willison "Embracing the parallel coding agent lifestyle" | 2025-10-05 | 서로 다른 디렉터리에서 에이전트 3~4개. 리서치·PoC·작은 수정·명세가 분명한 작업에 맞다 | [일화] |
| Mitchell Hashimoto | 2026-02-05 | 병렬은 아직 하지 않는다. 에이전트 하나만 백그라운드로 돌리고 데스크톱 알림은 껐다. 쉬는 틈에 본인이 확인한다. 하루 마지막 30분에 리서치·트리아지 에이전트를 띄워 "다음 날 아침 출발점"을 만든다 | [일화] |
| 여러 worktree 가이드 | 2026 | 지속 가능한 상한은 2~3개라는 의견이 많다. 실제 상한은 git이 아니라 리뷰 대역폭이다 | [일화] |
| Trigger.dev "We ditched worktrees" | 연도 미표기(4-16) | worktree는 소스만 격리하고 포트, DB, 서비스, `node_modules`, 설치 시간은 격리하지 못한다. GitButler 가상 브랜치와 약 150줄짜리 스킬로 바꿨다 | [일화] |
| worktree 정리 문제 | 2026 | "3주면 낡은 worktree 20개". Cursor 포럼에는 2GB 저장소에서 worktree 2개가 9.82GB를 쓴 사례가 있다. 처방: 병합 직후 제거, `git worktree prune`, 공유 캐시(pnpm store, `CARGO_TARGET_DIR`) | [일화] |

### 1.6 장기 세션: compact, handover, memory bank

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Shrivu | 2025-11-02 | "자동 compact를 믿지 말라." 기본은 `/clear` 후 `/catchup`이다. 큰 작업은 계획과 진척을 .md에 적고 clear한 뒤 재개한다(Document & Clear) | [일화] |
| Anthropic "Effective harnesses for long-running agents" | 2025-11 | 초기화 에이전트가 `init.sh`, 진척 파일, 기능 목록(JSON, 200개 이상, 모두 failing으로 시작), 첫 커밋을 만든다. 이후 세션은 한 번에 기능 하나만 다룬다. 실패 양상은 한 번에 다 하려다 맥락 소진, 조기 완료 선언, 검증 없는 passing 표시였다. **JSON이 Markdown보다 모델에게 덜 덮어써진다** | [공식/소측] |
| Anthropic context engineering 글 | 2025-09 | compaction, 구조화 노트(NOTES.md, todo), 서브에이전트 요약 반환, just-in-time 로드 | [공식(2차)] |
| 공식 비용·memory 문서 | 2026-11 열람 | 초반의 상세 지시는 compact에서 사라질 수 있다. 지속 규칙은 CLAUDE.md에 둔다. CLAUDE.md의 "# Compact instructions" 절로 보존 대상을 지정한다. auto memory는 앞 200줄 또는 25KB까지만 로드된다 | [공식] |
| PreCompact 훅 + `/handover` 패턴, auto-clear 기능 요청(이슈 #90089) | 2026 | 자동 compact 직전에 HANDOVER.md를 쓰게 하는 훅이 퍼져 있다. "auto-compact 대신 handover 후 auto-clear" 요청도 열려 있다 | [일화] |
| Cline Memory Bank 공식 문서 | 2026-11 열람 | 파일 6개(projectbrief, productContext, activeContext, systemPatterns, techContext, progress). "모든 작업 시작 시 **모두** 읽어라." 폐기 표시는 없다 | [공식] |
| Juriy(kangax) "Memory bank and the many failures…" | 2025-04-11 | 혼란은 줄었다. 그러나 모델이 메모리를 건너뛰고 이미 지운 기능을 되살리려 한 사례가 있었다. 파일을 읽을 때마다 비용이 든다. 결국 사람이 준수를 강제해야 했다 | [소측] |
| Steve Yegge, Beads | 2025-10 | markdown 계획 파일 605개가 "부패 단계별로" 쌓였다. 에이전트는 계획을 갱신하지 않고, 병렬로 쓰면 충돌한다. 그래서 git 기반 구조화 이슈 트래커(JSONL)로 바꿨다. Claude Code Tasks에 영향을 줬다는 평이 있다 | [일화] |
| Kiro steering, spec-driven 비평(Böckeler) | 2025-10 | Kiro는 버그 수정 하나에 사용자 스토리 4개와 수용 기준 16개를 만들었다. 문서 무게가 작업 크기에 맞지 않는다는 비판이다 | [일화] |

### 1.7 교차 모델 검토와 토론

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Zack Proser "I make Codex review every diff Claude writes" | 2026-06-24 | 구조는 다음과 같다. **잡은 것**: 놓친 경계 조건, 인증 검사 위치 이동, 되돌릴 수 없는 마이그레이션 순서, 새 분기를 지워도 통과하는 테스트, 범위 이탈 | [소측/일화] |
| | | - Stop 훅에서 돌린다. 25줄 미만이고 핫패스가 아니면 건너뛴다. 인증, 결제, 마이그레이션, SQL은 항상 돈다. | |
| | | - 리뷰어는 초안 대화를 보지 않는다. JSON으로 verdict를 내고, block은 exit 2로 이어진다. | |
| | | - 형식 오류나 타임아웃이면 막는 쪽으로 실패한다(fail-closed). block에는 구체적 실패 경로를 요구한다. 두 모델이 엇갈리면 "투표가 아니라 그 줄을 직접 읽으라는 신호"로 본다. 10~30초 걸린다. | |
| 다른 cross-model review 글(dev.to, ClaudeFolio, skills.sh) | 2026 | 공통 주장은 다른 계열 모델은 맹점이 다르다는 것이다. 위양성 5~15%는 정상이니 triage가 필요하다. 두 모델이 맹점을 공유하면 둘 다 놓친다 | [일화] |
| Karpathy llm-council | 2025-11 | 각 모델이 먼저 독립 답변을 낸다. 서로의 답을 **익명화**해 순위를 매기고, chairman이 종합한다. "토요일 해킹" 수준이라고 본인이 밝혔다 | [일화] |
| 다중 에이전트 토론(MAD) 연구: Huang 외 2023, Smit 외 ICML 2024, Zhang 외 2025, "The Cost of Consensus" 2026 | 2023~2026 | 같은 응답 수의 self-consistency(다수결)를 안정적으로 이기지 못했다. 동질 에이전트는 다수 의견에 동조한다(채택률 최대 85.5%). 토큰은 2.1~3.4배다. **이종 모델**을 쓰면 낫다는 제안이 있다 | [실측] (수학·객관식 위주) |
| PAL(구 Zen) MCP | 2025~2026 | Claude에서 Gemini, Codex를 부르는 consensus·codereview 도구. 한 번에 5~20분 걸린다. 효과를 독립 평가한 자료는 찾지 못했다 | [일화] |
| Armin Ronacher "A year of vibes" | 2025-12-22 | Amp, Claude Code, Pi를 병행한다. Codex 리뷰는 로컬에서 돌린다. "Claude를 선호하는 근거는 vibes뿐" | [일화] |

### 1.8 공유 지식과 여러 저장소

| 사례 | 날짜 | 요지 | 근거 |
|---|---|---|---|
| Claude Code memory 문서: rules symlink | 2026-11 열람 | 사용자 레벨 `~/.claude/rules/`와 CLAUDE.md의 import는 승인 없이 신뢰한다(Cowork 데스크톱 세션은 예외로, 작업 디렉터리 밖 symlink를 건너뛴다). **프로젝트** `.claude/rules/`에서 밖을 가리키는 symlink는 외부 import로 취급한다. 승인이 필요하고, 승인한 뒤에도 **`paths`가 없는 것만** 로드된다. rule frontmatter에서 읽는 필드는 `paths` 하나뿐이다 | [공식] |
| Claude Code memory 문서: AGENTS.md | 2026-11 열람 | v2.1.277부터 AGENTS.md를 직접 읽는다. 다만 작업 디렉터리나 그 위에 CLAUDE.md가 있으면 CLAUDE.md만 읽는다(설정으로 둘 다 읽기 가능). `@AGENTS.md` import나 symlink로 하나의 원본을 공유하는 방법을 권한다 | [공식] |
| 스킬 공유 symlink 이슈 | 2026 | `skills/` 아래 디렉터리 단위 symlink는 재귀 탐색되지 않는다. 스킬마다 링크해야 한다. `.claude`가 symlink이면 자동완성 문제가 있다는 보고도 있다 | [일화] |
| OpenAI harness engineering | 2026-02-11 | 지식은 저장소 `docs/`에 버전 관리하고 문서 정원사 에이전트가 관리한다. 이 저장소를 지식의 기준(system of record)으로 삼는다 | [일화(2차)] |
| Agent Skills 공개 표준(agentskills.io) | 2025-12-18 | SKILL.md 형식이다. Codex(`~/.codex/skills`)와 Gemini CLI(`~/.gemini/skills`)도 읽는다고 보도됐다 | [일화(2차)] 공식 문서 미대조 |
| Anthropic 사내 팀 사례 | 2025-07-24 | 팀끼리 워크플로 시연 세션을 열어 관행을 퍼뜨렸다. 한 팀의 프롬프트는 약간만 고치면 다른 팀에서도 통했다 | [공식] |

### 1.9 다른 도구의 대응 개념

| 도구 | 상시 | 조건부 | 필요할 때 | 메모 |
|---|---|---|---|---|
| Claude Code | CLAUDE.md(계층), `~/.claude/rules` | `.claude/rules` + `paths` | 스킬, `@import` | AGENTS.md 직접 읽기(v2.1.277+), auto memory는 200줄/25KB [공식] |
| Codex CLI | AGENTS.md(전역 `~/.codex` + 루트부터 cwd까지, 디렉터리당 1개, `AGENTS.override.md` 우선) | 하위 디렉터리 AGENTS.md | 스킬(2차) | **합계 32KiB(`project_doc_max_bytes`)를 넘으면 나머지를 조용히 버린다** [공식] |
| Gemini CLI | GEMINI.md 계층(전역, 프로젝트, 하위) | — | — | `context.fileName`에 `["AGENTS.md","GEMINI.md"]`처럼 여러 이름을 줄 수 있다. 사본을 따로 두면 서로 어긋날 위험이 있다고 경고한다 [공식/2차] |
| Cursor | `.cursor/rules/*.mdc`의 `alwaysApply` | glob 자동 첨부 | description으로 에이전트가 요청, `@`수동 | `.cursorrules`는 레거시다. 3.0 빌드 하나에서 `alwaysApply`가 요청형으로 취급되는 버그가 있었다 [공식/일화] |
| Kiro | steering `inclusion: always` | `fileMatch` + 패턴 | `manual`(#이름) | 전역 `~/.kiro/steering`이 로드되지 않는 버그 보고가 있다(0.8.140) [공식/일화] |
| Cline | `.clinerules`, Memory Bank(전부 읽기) | — | — | 위 1.6 참조 |
| Aider | `--read CONVENTIONS.md`(읽기 전용, 캐시) | — | — | "짧고 구체적으로" [공식] |

- 모든 도구가 같은 3단(상시, 경로 조건부, 요청 시)으로 수렴했다.
- 우리 3층 구조(사용자 CLAUDE.md, rules+paths, 스킬)는 이 수렴과 같은 모양이다.
- 그리고 **조건부 로더에는 도구마다 버그가 있었다**(Cursor alwaysApply, Kiro 전역 steering). 한 번 실측한 결과가 업그레이드 뒤에도 유지된다고 가정하면 위험하다.

---

## 2. 패턴 정리

### 2.1 많이 쓰이고 효과가 보고된 것

| 패턴 | 누가 | 근거 강도 |
|---|---|---|
| 상시 파일은 짧게(60~200줄), 각 줄은 **실제 실패 하나**에 대응 | Hashimoto, Cherny, HumanLayer, 공식 | 일화 다수, ETH 실측이 간접 지지 |
| 상시에는 **색인**, 본문은 파일로 두고 필요할 때 읽기 | Vercel(실측), OpenAI, HumanLayer, Shrivu | 실측 1 + 일화 |
| 검증 수단을 에이전트 손에(테스트, 스크린샷, 로그 한 곳, 빠르고 명확한 에러) | Cherny("품질 2~3배", 미입증), Ronacher, Anthropic long-running | 일화 + 공식 |
| 결정적 게이트는 훅으로, 스타일은 문서로. 훅은 조용하게 | 훅 회고 3건, Shrivu, 공식 | 일화 |
| 계획 먼저(plan mode), 승인 후 실행 | Cherny, Shrivu, 공식 비용 문서 | 일화 + 공식 |
| clear + 진척 파일 재개(Document & Clear), 구조화 진척(JSON) | Shrivu, Anthropic long-running | 공식 소측 |
| 다른 회사 모델로 diff 리뷰. 초안 맥락은 숨기고, 크기·위험으로 거르고, 구체 근거를 요구 | Proser 외 다수 | 소측/일화, MAD 연구가 간접 지지 |
| CLI를 MCP보다 먼저 | Ronacher, Shrivu, 공식 비용 문서 | 일화 + 공식 |
| 병렬은 2~5개, 서로 다른 디렉터리·checkout, 알림을 쓰되 확인은 내가 정한 때 | Cherny, Willison, Hashimoto | 일화 |

### 2.2 유행했지만 버려지거나 후퇴한 것

| 패턴 | 왜 버려졌나 |
|---|---|
| **거대한 단일 CLAUDE.md/AGENTS.md** | 모든 작업의 맥락을 밀어낸다. 무관하다고 판단되면 무시된다. 모순이 생기면 임의로 하나를 고른다. ETH에서 비용 +20%. OpenAI는 "백과사전 대신 목차"로 바꿨다 |
| **`/init` 같은 자동 생성 컨텍스트 파일** | ETH: LLM 생성 파일은 성공률이 오히려 떨어졌다. HumanLayer: 가장 레버리지가 큰 파일을 자동 생성하지 말라 |
| **Memory Bank식 "매번 전부 읽기"** | 읽을 때마다 비용이 든다. 모델이 건너뛴다. 사람이 강제해야 한다. 구조화 트래커(Beads, Claude Code Tasks)나 auto memory 쪽으로 흐름이 옮겨 갔다. Cline 문서에는 여전히 남아 있다 |
| **markdown 계획 파일 무더기** | 갱신되지 않고 썩는다(Yegge 605개). 병렬로 쓰면 충돌한다. 상태는 JSON/JSONL로 옮기는 추세다 |
| **역할 페르소나 서브에이전트 수십~수백 개 모음** | Shrivu는 "취약하다"고 한다. Cognition은 쓰기 작업에서 맥락이 끊긴다고 한다. HN 의견도 "효과는 있으나 작다". 일반 에이전트 복제와 짧은 위임 쪽으로 이동했다 |
| **MCP로 모든 것 감싸기** | 도구 정의가 수만 토큰을 쓴다. Tool Search(지연 로드)가 나왔지만 CLI가 여전히 더 싸다(공식) |
| **많고 시끄러운 훅** | 컨텍스트 경고나 매 Read 주입 훅은 무시되거나 비싸서 하루 만에 꺼졌다. 꺼진 훅은 "지켜 주고 있다"는 착각을 남긴다 |
| **SessionStart로 스킬 존재를 강제 주입(Superpowers 초기)** | Codex에서는 오히려 UX를 해쳐서 뺐다. 모델이 좋아지면 강제 장치가 역효과를 낸다 |
| **대규모 오케스트레이션(Gas Town류)** | 비용이 하루 수백 달러이고 계정이 여럿 필요하다. 모델이 바뀌자 무너졌다 |
| **Spec-driven 중문서(Kiro spec, spec-kit)** | 작은 작업에도 무거운 문서를 만든다. 형식 표준도 없다(Böckeler) |
| **구세대 모델용 패치 규칙** | Claude 5 세대에서 시스템 프롬프트를 80% 지워도 손실이 없었다고 한다(2차). "IMPORTANT/MUST" 강조와 자기 검증 지시는 새 모델에서 과잉 검증을 부른다는 주장(2차) |

### 2.3 우리 상황과 비슷한 사례

| 사례 | 닮은 점 | 다른 점 | 가져올 것 |
|---|---|---|---|
| Steve Yegge (Gas Town, Beads) | 1인, 다중 에이전트, 다중 계정, 하루 종일 | 규모가 훨씬 크고 자동화가 극단적 | **경고 사례**다. 모델 교체에 취약했고 비용이 폭주했다. markdown 계획이 썩는다는 진단과 구조화 트래커 |
| Armin Ronacher | 1인 OSS 다수, 여러 에이전트(Amp, Claude, Pi)와 Codex 리뷰 | MCP를 거의 쓰지 않는다 | 로그 한 곳, Makefile 도구, 빠른 에러 |
| Mitchell Hashimoto | 1인 대형 OSS(Ghostty), 하네스 사고방식 | 병렬을 하지 않는다 | 각 규칙 줄은 실패 하나에 대응, 알림 끄기, 하루 끝 리서치 에이전트 |
| Boris Cherny | 하루 종일, 병렬 10~15개 | 팀 단위이고 커스터마이즈가 최소 | 세션의 10~20%는 버린다는 태도, 별도 checkout, 2.5k 토큰 CLAUDE.md |
| OpenAI harness engineering | 지식 저장소(system of record), 문서 정원사, 린터 강제 | 단일 대형 저장소 | luau-kb와 같은 발상이다. **문서 정원사**와 **린터 메시지 = 교정 지시**는 우리에게 아직 없다 |
| Shrivu (모노레포) | 감사, 리뷰, 많은 기능 실험 | 기업 팀 | 커스텀 명령이 많으면 안티패턴, Document & Clear, Master-Clone |

---

## 3. 우리 구성과 비교한 조언

### 3.1 잘 맞는 것 (외부 합의와 같은 방향)

- **사용자 CLAUDE.md 45줄과 경로 조건부 rules**: 공식(200줄 미만), HumanLayer(60줄 미만), Cursor, Kiro의 3단 구조와 같다.
- **luau-kb의 실행 가능한 스니펫 검증(`check_snippets.py`)**: 외부에서 이 수준의 "지식 회귀 테스트"는 찾지 못했다.
  - OpenAI의 린터·구조 테스트와 같은 발상이다. 지식 저장소 쪽으로는 우리가 앞서 있다.
- **스킬별 개별 symlink(MANIFEST)**: 디렉터리 단위 링크가 재귀 탐색되지 않는 함정을 이미 피했다.
  - 사용자 레벨 rules symlink는 공식적으로 승인 없이 로드된다.
- **bash-bypass 리마인더의 "같은 알림은 세션당 1회, 차단하지 않음"**: 살아남은 훅들의 특성("조용하다가 중요할 때만")과 같다.
- **audit/18의 리뷰어 설계**: 새 컨텍스트, 정해진 시점, 훅으로 알림, 결과를 그대로 전달. Proser식 교차 검토의 핵심과 겹친다.

### 3.2 과하게 했을 수 있는 것

1. **하네스를 다루는 작업 자체의 비중**
   - 규모: claude-doctor 감사 18건, home-sync, 마켓플레이스, session-log 플러그인, coderag 결정 49개, taxonomy.
   - 외부 신호
     - Cherny는 "커스터마이즈를 별로 안 한다".
     - Shrivu는 "커스텀 명령이 많으면 안티패턴"이라고 했다.
     - METR은 체감 속도와 실측 속도가 반대로 나왔다(+20% 체감, −19% 실측).
     - 반년마다 지워 보라는 권고도 있다.
   - 권고: 성과 지표 몇 개를 고정하고 재정비 전후를 비교한다. audit/10 스크립트를 월 1회 다시 돌리면 된다.
     - "보고 와" 횟수
     - 한국어 정정 횟수
     - 사용자가 직접 % 를 보고한 횟수
     - 서브에이전트 지출 비중(`/usage` attribution)
   - 지표가 움직이지 않으면 그 장치는 지운다.
2. **스킬 12개의 상시 description 약 7,000자**
   - 공식 권고에 비춰 과하지는 않다. 다만 한국어는 토큰 밀도가 높아 수천 토큰이 된다.
   - 발동 평가 없이 늘리면 "비용은 상시, 효과는 반반"이 된다(1.2).
   - 평가하기 전에는 스킬을 더 쪼개지 않는다.
3. **luau-kb `AGENTS.md` 15.6KB**
   - ETH 결과로 보면 개요·지도는 효과 없이 비용만 늘린다.
   - Codex는 합계 32KiB를 넘으면 조용히 잘라 버린다. 프로젝트 AGENTS.md까지 합치면 한도에 가까워질 수 있다.
   - 권고: 색인 형태(증상 → 파일 경로)로 줄인다. 아래 3.3-1 참조.
4. **"소진될 때까지" 리뷰와 3모델 토론**(audit/10 패턴 E)
   - 동질 토론은 동조로 수렴하고 토큰은 2~3배 든다(MAD 연구).
   - 리뷰어 위양성 5~15%는 정상이라는 보고가 있다. 소진할 때까지 돌리면 위양성 처리 비용이 커진다.
   - 권고: "소진" 대신 종료 규칙을 둔다. 예: 재현 가능한 실패 경로를 단 발견이 0건인 라운드가 나오면 멈춘다.

### 3.3 빠뜨린 것

1. **스킬 발동 측정과, 발동에 기대지 않는 경로**
   - "보고 오기 52회"를 해결하려고 지식을 스킬로 옮겼는데, 외부 실측은 자동 발동이 반반이다.
   - 싼 순서대로 셋을 권한다.
     - (a) 이미 `**/*.luau`로 로드되는 `rules/luau-core.md`에 **10~20줄짜리 색인**을 넣는다. 형식: "증상 → 스킬 또는 references 경로". Vercel식 압축 색인이고, .luau 파일을 읽을 때만 든다.
     - (b) 질문 20개로 발동률을 잰다. audit/05에서 계획만 하고 하지 않은 일이다. 메인 모델로 잰다.
     - (c) 발동률이 낮게 나오면 UserPromptSubmit 강제 평가 훅을 고려한다. 매 프롬프트 비용이 들고, Superpowers처럼 역효과가 날 수 있으니 측정 뒤에만 넣는다.
2. **돈에 대한 결정적 게이트**
   - $589 사고 뒤의 대응이 CLAUDE.md "모델 사용" 절과 memory뿐이다.
   - 공식 문서는 "막으려면 훅"이라고 한다. 이슈들은 "개수 상한은 있어도 토큰·시간 상한이 없다"고 지적한다.
   - 권고
     - PreToolUse(Agent) 훅으로 세션당 서브에이전트 생성 수와 opus/fable 지정을 센다. 기준을 넘으면 `action` 레벨로 확인을 받는다.
     - `claude -p` 위임에는 `--max-budget-usd`를 쓴다.
     - 훅의 matcher 이름과 동작은 구현 전에 확인해야 한다[미검증].
3. **context % 를 모델에게: 주기 경고가 아니라 문턱 1회**
   - audit/10 패턴 A의 원인은 모델이 자기 컨텍스트 % 를 모른다는 것이다.
   - 외부에서 가장 먼저 죽은 훅이 "20분마다 컨텍스트 경고"였다.
   - 권고: 문턱(예: 70%, 85%)마다 **한 번씩만** 알린다.
     - 70%에서 "작업 단위가 끝나면 Document & Clear를 제안하라".
     - 85%에서 "지금 handover 파일을 쓰라".
     - 사용자 쪽은 statusline의 `context_window.used_percentage`로 충분하다[공식].
4. **compact보다 clear + 진척 파일**
   - 우리 세션은 맥락 중앙값이 26만~42만 토큰이고 `/compact`를 58회 했다. 공식 문서상 이는 요청마다 다시 읽는 비용과 compact 요청 자체의 비용이다.
   - 외부 주류는 "작업 단위가 끝나면 진척을 파일에 쓰고 `/clear`, 새 세션은 파일과 `git log`로 재개"다.
   - `/checkpoint` 스킬을 만들 때 compact 인자 초안만이 아니라 **clear 경로를 기본으로** 제안하게 한다.
   - CLAUDE.md에 "# Compact instructions" 절을 두면 compact가 불가피할 때 보존 대상을 정할 수 있다[공식].
5. **작업 도중 지시를 즉시 구조화 기록**
   - 원인: compact를 거치며 사라지는 지시(audit/10 §2.5, `queued_command` 1,856건).
   - 외부 처방
     - Anthropic: 상태는 JSON으로 둔다. 덜 덮어써진다.
     - Yegge: markdown 계획은 썩는다.
   - 권고: 사용자 지시가 들어오면 바로 `.claude/todos.md`나 JSONL 한 줄에 쓰는 규칙을 둔다. 산문 파일(question.md)과 상태 파일을 분리한다.
   - 예: quad HUMAN_TODO 67KB는 Memory Bank가 실패한 방식과 같은 크기 문제다.
6. **AGENTS.md 단일 원본과 Gemini 설정**
   - P0에서 stl-luau GEMINI.md가 낡은 것을 발견했다. Gemini 문서가 경고한 "사본 어긋남"이 이미 일어났다.
   - Claude Code도 이제 AGENTS.md를 직접 읽는다(CLAUDE.md가 있으면 CLAUDE.md만).
   - 권고
     - 툴 공통 내용은 AGENTS.md 하나에 둔다.
     - Gemini는 `context.fileName: ["AGENTS.md","GEMINI.md"]`로 같은 원본을 읽게 한다.
     - CLAUDE.md는 `@AGENTS.md`와 Claude 전용 몇 줄로 줄인다.
     - Codex·Gemini가 SKILL.md를 읽는다면 luau-kb 스킬을 `~/.codex/skills`, `~/.gemini/skills`에도 링크해 병렬 AGENTS.md를 줄인다. 이 기능은 공식 문서로 확인해야 한다[2차].
7. **규칙·훅의 출처와 만료**
   - Hashimoto식으로 각 규칙 줄에 "막으려는 실패 + 근거 ID + 확인한 모델·버전"을 단다. coderag 설계의 `lifecycle`/`review_after`를 하네스 규칙에도 쓴다.
   - 모델이 바뀔 때마다 `/doctor prompt-audit`를 돌리고 핵심 실측을 다시 한다.
     - 예: bash-bypass의 `--!strict` 준수 실측은 haiku로 0/2 → 2/2였다. 메인 모델로 다시 잴 필요가 있다.
8. **문서 정원사**
   - luau-kb와 각 저장소 `.claude/base`가 낡는 것을 정기적으로 찾는 장치가 없다.
   - 저렴한 판: 기존 `/loop`이나 `schedule`로 주 1회 "references의 last-confirmed가 오래된 항목과 깨진 경로" 보고서만 만들게 한다. 쓰기 권한은 주지 않는다.

### 3.4 남들이 겪었고 우리가 곧 겪을 함정

| 함정 | 우리 쪽 징후 | 예방 |
|---|---|---|
| 조건부 로더가 업그레이드 뒤 조용히 바뀐다(Cursor alwaysApply 버그, Kiro 전역 steering 버그, Codex 32KiB 무음 절단) | rules 로드를 2026-11-10에 한 번 실측했다. Claude Code가 v2.1.3xx로 자주 오른다 | harness-doctor에 "rules·스킬 로드 회귀 점검"을 넣는다. 버전이 바뀔 때마다 돌린다 |
| 프로젝트 `.claude/rules`에 공유 rules를 symlink하면 `paths` 규칙이 로드되지 않는다 | 프로젝트별로 luau 규칙을 링크하려는 유혹(P3 다이어트) | 공유 rules는 사용자 레벨에만 둔다. 공식 문서에 명시돼 있다 |
| rule frontmatter의 `description`은 무시된다 | `code-structure.md`, `web-security.md`, `luau-core.md`가 description을 쓴다 | 모델에게 보여야 하는 설명이면 본문 첫 줄로 옮긴다(해는 없음) |
| 훅이 늘면서 무시하는 습관이 생긴다 | 훅 4개에 계획된 것이 더 있다(H1 컨텍스트 %, H2 한국어, second opinion 알림) | 훅마다 "1세션 최대 발화 수"를 정하고 발화 로그를 남긴다. 월 1회 발화 대비 효과를 본다. p95 지연도 잰다 |
| 병렬의 실제 상한은 리뷰 대역폭 | 동시 세션 여러 개, 감사·리뷰를 자주 돌림, "권고대로" 74회 | 동시 세션 수보다 "사람 검토 대기열" 길이를 본다. Cherny처럼 버리는 세션 10~20%를 정상으로 받아들인다 |
| worktree가 다시 쌓인다 | quad 14GB, devplorer 22개를 정리했다 | 병합 직후 제거. harness-doctor `worktrees.md`의 점검을 주기 실행. Rust는 `CARGO_TARGET_DIR`를 공유 |
| 오케스트레이션이 모델 교체에 깨진다 | delegate-agy, debate, audit 체계가 특정 모델 특성에 맞춰져 있다 | 위임 스킬에 모델 이름을 박지 말고 등급(high/mid/low)으로 쓴다. 이미 audit/18 방향이다 |
| 토론 결과를 "다수결"로 받는다 | 3모델 토론 | 첫 답은 서로 보지 않고 독립으로 낸다. 비교할 때 익명화한다(llm-council). 엇갈림은 투표가 아니라 직접 확인할 지점으로 본다 |

---

## 4. 한계

- 원문에 닿지 못해 2차 요약으로만 확인한 출처가 있다. 원문 수치와 표현은 다를 수 있다.
  - OpenAI harness engineering(403)
  - Boris Cherny X 스레드와 YC 인터뷰
  - Thariq의 Claude 5 context engineering
  - ETH 논문 본문
  - Agent Skills 표준의 Codex·Gemini 지원
- [소측]과 [실측]의 대부분은 특정 과제, 모델, 시점에 한정된다.
  - Vercel: Next.js 16
  - Spence: Svelte 스킬, Sonnet 4.5
  - MAD 연구: 수학·객관식
- Opus 5.5에서의 스킬 발동률은 외부 자료에 없다. 우리 실측이 필요하다.
- Reddit과 X 스레드 원문은 직접 열람하지 못했다. 미러와 정리 글로만 봤다.
- 조사 도구가 미국 기준 검색이라 일본·한국 커뮤니티 사례는 거의 다루지 못했다.

---

## 5. 출처 (열람일 2026-11-10)

### 공식 문서
- Claude Code memory: https://code.claude.com/docs/en/memory
- Claude Code costs: https://code.claude.com/docs/en/costs
- Claude Code statusline: https://code.claude.com/docs/en/statusline
- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Gemini CLI GEMINI.md: https://geminicli.com/docs/cli/gemini-md/
- Cline Memory Bank: https://docs.cline.bot/prompting/cline-memory-bank
- Aider conventions: https://aider.chat/docs/usage/conventions.html
- Kiro steering: https://kiro.dev/docs/steering/
- Cursor rules: https://docs.cursor.com/context/rules
- Anthropic, How Anthropic teams use Claude Code (2025-07-24): https://claude.com/blog/how-anthropic-teams-use-claude-code
- Anthropic, Effective harnesses for long-running agents (2025-11): https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, Claude Code best practices: https://www.anthropic.com/engineering/claude-code-best-practices
- AAIF / AGENTS.md 기증 (2025-12-09): https://openai.com/index/agentic-ai-foundation/

### 실측과 연구
- Vercel, AGENTS.md outperforms skills (2026-01-27): https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
- Scott Spence, Measuring skill activation with sandboxed evals (2026-02-08): https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals
- Scott Spence, Skills don't auto-activate (2025-11): https://scottspence.com/posts/claude-code-skills-dont-auto-activate
- ETH Zurich, Evaluating AGENTS.md, arXiv 2602.11988 (2026-02). 요약: https://the-decoder.com/context-files-for-coding-agents-often-dont-help-and-may-even-hurt-performance/ , https://infoq.com/news/2026/03/agents-context-file-value-review/
- Chroma, Context Rot (2025-07-14): https://trychroma.com/research/context-rot
- METR RCT (2025-07-10). 보도: https://www.theregister.com/2025/07/11/ai_code_tools_slow_down/
- Smit 외, Should we be going MAD? (ICML 2024): https://arxiv.org/html/2311.17371v3
- Zhang 외, If Multi-Agent Debate is the Answer, What is the Question? (2025-02): https://arxiv.org/abs/2502.08788
- Huang 외, LLMs Cannot Self-Correct Reasoning Yet (2023): https://arxiv.org/pdf/2310.01798
- The Cost of Consensus (2026, 프리프린트): https://arxiv.org/html/2605.00914

### 운영 회고와 일화
- Shrivu Shankar, How I use every Claude Code feature (2025-11-02): https://blog.sshh.io/p/how-i-use-every-claude-code-feature
- HumanLayer, Writing a good CLAUDE.md (2025-11-25): https://www.humanlayer.dev/blog/writing-a-good-claude-md
- InfoQ, Claude Code creator workflow (2026-01-10): https://www.infoq.com/news/2026/01/claude-code-creator-workflow
- Mitchell Hashimoto, My AI Adoption Journey (2026-02-05): https://mitchellh.com/writing/my-ai-adoption-journey
- OpenAI, Harness engineering (2026-02-11): https://openai.com/index/harness-engineering/ (403, 요약: https://www.ignorance.ai/p/the-emerging-harness-engineering 2026-02-22)
- Simon Willison, Embracing the parallel coding agent lifestyle (2025-10-05): https://simonwillison.net/2025/Oct/5/parallel-coding-agents/
- Armin Ronacher, Agentic coding recommendations (2025-06-12): https://lucumr.pocoo.org/2025/6/12/agentic-coding/
- Armin Ronacher, A year of vibes (2025-12-22): https://lucumr.pocoo.org/2025/12/22/a-year-of-vibes/
- Cognition, Don't Build Multi-Agents (2025-06): 정리 https://patmcguinness.substack.com/p/the-ai-agent-architecture-debate
- Juriy(kangax), Memory bank and the many failures of GenAI engineering (2025-04-11): https://kangax.substack.com/p/memory-bank-and-the-many-failures
- Steve Yegge, Introducing Beads (2025-10): https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a
- Gas Town 비평과 정리 (2026): https://www.todayintabs.com/p/all-gas-town-no-brakes-town , https://vanja.io/yegge-agent-city-four-claims/
- Birgitta Böckeler, Understanding Spec-Driven-Development (2025-10): https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- Zack Proser, I make Codex review every diff Claude writes (2026-06-24): https://zackproser.com/blog/codex-reviews-claudes-diffs
- Karpathy, llm-council (2025-11): https://github.com/karpathy/llm-council
- Superpowers (2025-10-09): https://blog.fsck.com/2025/10/09/superpowers
- 훅 회고: https://dev.to/rentierdigital/i-built-11-claude-code-hooks-six-were-dead-within-24-hours-245k , https://dev.to/uzoma_uche_3ec83974b4a8a5/three-pretooluse-hooks-i-stopped-using-and-what-replaced-them-5hg9
- Trigger.dev, We ditched worktrees: https://dev.to/maverickdotdev/we-ditched-worktrees-for-claude-code-heres-what-we-use-instead-5b22
- Charlie Hills, Delete your CLAUDE.md (2026-08-09): https://charliehills.substack.com/p/delete-your-claudemd
- Reporails, Opus 5: Delete your CLAUDE.md? (2026-08-06): https://dev.to/reporails/opus-5-delete-your-claudemd-9ga
- Claude 5 context engineering 정리 (2026-07-24): https://mager.co/blog/2026-07-24-context-engineering-claude-5/
- 서브에이전트 폭주 이슈: https://github.com/anthropics/claude-code/issues/68619 , https://claudeissues.com/issue/82565-general-purpose-subagents-recursively-spawn-3-requested-24-ran-80-of-tokens-wast , https://claudeissues.com/issue/94013-background-subagents-have-no-token-turn-or-time-cap-three-research-agents-consum
- 주간 한도 보도 (2025-07): https://venturebeat.com/ai/anthropic-throttles-claude-rate-limits-devs-call-foul
- 스킬 공유 symlink 이슈: https://claudeissues.com/issue/20755-feature-request-recursive-skill-discovery-in-claude-skills
- Kiro 전역 steering 버그: https://github.com/kirodotdev/Kiro/issues/6171
- Cursor alwaysApply 버그: https://forum.cursor.com/t/alwaysapply-true-rules-and-cursorrules-both-silently-treated-as-requestable-instead-of-auto-injected-cursor-3-0-16-macos/157431
