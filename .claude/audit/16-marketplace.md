# 16. 마켓플레이스 전수 조사: 공식 마켓 317개와 claude.com 디렉터리 3,638개

작성일 2026-11-10. 대상은 공식 마켓(`claude-plugins-official`)과 claude.com 마켓 디렉터리 전체다.
판정 기준은 바뀐 방향 셋이다. 하네스는 툴킷과 무관하고, 웹(블로그 react/astro, vitrine go+react)도 대상이며, 다른 sandbox로 옮길 수 있어야 한다.
이전 조사 `.claude/audit/02` §A는 공식 마켓 일부를 Luau 관점으로만 봤다. 이 문서가 그 판정을 대체한다(§5).

확인 방법 표기
- **열람**: 파일 원문을 직접 읽었다.
- **카탈로그**: 로컬 캐시에서 읽었다.
- **fetch**: WebFetch 요약이다. 원문 전체가 아니다.
- **실측**: `claude -p --model sonnet --plugin-dir <사본>`으로 돌렸다(§6).
- **정적**: 코드만 읽고 추정했다.

## 0. 원천과 범위

| 원천 | 내용 | 시점 |
|---|---|---|
| `/code/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` | 공식 마켓 목록 **317개**(`./plugins/` 40개는 Anthropic 제작, `./external_plugins/` 14개, 1개는 `command` 소스(xcode), 나머지 262개는 외부 저장소를 sha로 고정) | 클론 `.gcs-sha` = `dceb15d5` |
| `/code/.claude/plugins/plugin-catalog-cache.json` | 공식 마켓 315개의 설치 수(`unique_installs`), 상시·호출 시 토큰 추정(opus-4-7/sonnet-4-6 기준), 구성 요소 | 생성 2026-10-21, 설치 수 2026-10-16 |
| `/code/.claude/plugins/plugin-directory-cache-v2.json` | claude.com 디렉터리 **3,638개**. 항목마다 `checks.review` = `anthropic` 92 / `partner` 352 / `none` 3,194, `reviewed_commit` | 2026-11-10 08:23 |
| claude.com/ko/marketplace/plugins/<이름> | 배지 "**Anthropic 인증**", 설치 수, 출처 링크 | fetch 2026-11-10 |
| code.claude.com/docs `plugins/install`, `plugins/anthropic-marketplaces` | 마켓 종류, 범위(scope), 자동 갱신, `claude plugin details`의 Always-on | fetch 2026-11-10 |

### 0.1 공인 판정 규칙 (근거)

| 표기 | 조건 | 근거 |
|---|---|---|
| **공식** | Anthropic 제작. 공식 마켓 저장소 안 `./plugins/*` 이거나, 저자가 Anthropic인 `./external_plugins/{discord,fakechat,imessage,telegram}` | `marketplace.json`의 `source`·`author`, 디렉터리 `review.by.type = anthropic` |
| **공인** | 디렉터리 검토가 끝났다(`review.state = done`, `by.type = partner`). 웹 페이지에 "Anthropic 인증" 배지가 붙는다 | `plugin-directory-cache-v2.json`. 페이지 대조는 아래 |
| **서드파티** | 검토 `none`이거나 디렉터리에 없다. 공식 마켓에 실려 있어도 배지가 없다 | 같음 |

배지와 캐시 필드가 같은 것을 가리키는지는 페이지 넷으로 대조했다(fetch).

| 페이지 | 배지 | 캐시 `review` |
|---|---|---|
| security-guidance | 있음 | anthropic |
| context7 | 있음 | **partner** |
| remember | **없음** | none |
| mattpocock-skills | **없음** | none |

같은 페이지의 "기타 플러그인"(Superpowers, Playwright: partner)에도 배지가 있었다. 그래서 **배지는 anthropic 검토와 partner 검토를 함께 뜻한다.**

공식 문서는 이 배지를 "marks some plugins **Anthropic verified**"라고만 적는다. 그리고 공식 마켓을 "Plugins Anthropic maintains, plus plugins from partners and other authors"라고 설명한다(`plugins/anthropic-marketplaces`).
따라서 **공식 마켓에 실렸다는 사실만으로 공인은 아니다.** 공식 마켓 317개 가운데 검토 `none`이 55개, 디렉터리에 없는 것이 23개다.

주의: 인증은 특정 커밋(`reviewed_commit`)에 붙는다. 공식 마켓은 자동 갱신이 기본으로 켜져 있어서, 실제로 설치되는 것은 검토 이후 버전일 수 있다.
- 예: security-guidance는 `fa4eb543`(v2.0.17)에서 검토됐는데 클론은 v2.0.19다.
- 클론 대부분의 커밋(`dceb15d5`)은 검토 커밋과 같다.

## 1. 전체 목록

### 1.1 분류별 수

| 원천 | (a) 방향 직접 관련 | (b) 웹 툴킷 | (c) 범용 품질·보안 | (d) 무관 | 계 |
|---|---|---|---|---|---|
| 공식 마켓 | 18 | 12 | 23 | 264 | 317 |
| 디렉터리 검토(공식 마켓 밖) | 6 | 2 | 6 | 220 | 234 |
| 디렉터리 미검토(키워드, 중복 계수) | 349 | 101 | 226 | 2599 | 3194 |

분류 기준
- **(a) 방향 직접 관련**
  - 하네스 진단·관리, CLAUDE.md·규칙·훅 관리, 스킬·플러그인 제작
  - 세션 기억·관측, 문서·지식 주입, 코드 탐색(coderag와 겹침)
  - 다른 모델로 위임, 토론, 결정 기록
  - 우리 툴킷 언어(Luau, Rust)의 LSP
- **(b) 웹 툴킷**: 프론트 디자인, TS/Go LSP, 브라우저 검증, 웹 표준·접근성, 호스팅(쓸 때만)
- **(c) 범용 품질·보안**: 리뷰, 단순화, 정적·동적 보안 검사, 커밋 흐름
- **(d) 무관**: 특정 SaaS·업무 도메인(금융, 법률, CRM, 클라우드 콘솔, DB 호스팅 등), 수학, 학습 모드 등

### 1.2 공식 마켓 317개 (전부)

표 읽는 법
- **종류**: S=skill, A=agent, C=command, H=hook, M=MCP, L=LSP.
- **설치 수**: 카탈로그 값(2026-10-16)이다. 웹 페이지 값은 이와 다르다(예: security-guidance는 카탈로그 268,918, 페이지 241,800).
- **상시**: 카탈로그의 opus-4-7 기준 상시 토큰 추정이다. 훅 주입과 MCP 도구 스키마는 여기에 들어가지 않는다(§3.0).
- **한 줄 기능**: (a)(b)(c)는 한국어로 새로 썼다. (d)는 마켓 설명 원문을 줄여 그대로 둔다.
- **판정**: (a)(b)(c)에만 단다. 근거는 §2와 §3에 있다.

| 분류 | 이름 | 제작자 | 종류 | 한 줄 기능 | 설치 수 | 상시 | 판정 |
|---|---|---|---|---|---|---|---|
| (a) | champion-kit | 공식 | SA | 사내 Claude Code 챔피언용 해커톤·오피스아워·성숙도 스킬 | - | - | 불필요 |
| (a) | claude-code-setup | 공식 | S | 코드베이스를 읽고 훅·스킬·MCP·서브에이전트 자동화를 유형별 1–2개 추천(읽기 전용) | 221,459 | 144 | 참고 |
| (a) | claude-md-management | 공식 | SC | CLAUDE.md 품질 감사(A–F 등급, 승인 후 수정) + /revise-claude-md 세션 학습 반영 | 314,007 | 180 | 중복+참고 |
| (a) | context7 | 공인 · Upstash | M | 원격 MCP로 라이브러리 버전별 문서·예제 조회(resolve-library-id, query-docs) | 441,485 | 0 | 도입 후보(웹)/참고(Luau) |
| (a) | dash0 | 서드파티 · Dash0 | SH | 세션 텔레메트리를 OpenTelemetry로 Dash0에 보내는 훅(전 이벤트) | 1,349 | 164 | 불필요 |
| (a) | hookify | 공식 | SACH | 대화 패턴·지시로 `.claude/hookify.*.local.md` 규칙을 만들고 모든 도구 호출에 python 훅으로 적용 | 63,891 | 297 | 중복 |
| (a) | langfuse-observability | 공인 · Langfuse | H | 세션 트레이스를 Langfuse로 내보내는 훅 | 1,087 | 0 | 불필요 |
| (a) | lua-lsp | 공식 | L | lua-language-server, `.lua` 전용 | 16,157 | 0 | 불필요 |
| (a) | lumen | 서드파티 · Ory Corp | SH | Go AST + 로컬 임베딩(Ollama) 의미 코드 검색 | 899 | 129 | 중복(coderag) |
| (a) | mattpocock-skills | 서드파티 · Matt Pocock | S | grilling·spec/ticket·TDD·리뷰·handoff 등 스킬 28개 | 66,640 | 1,654 | 불필요 |
| (a) | plugin-dev | 공식 | SAC | 플러그인·스킬·훅·MCP·에이전트 제작 스킬 7개 + validator·reviewer 에이전트 | 71,382 | 2,354 | 참고(일시 사용) |
| (a) | remember | 서드파티 | SCH | 대화를 일별 로그로 추출·요약·압축하는 세션 기억(훅 4종) | 63,089 | 78 | 목록만(다른 에이전트) |
| (a) | rust-analyzer-lsp | 공식 | L | rust-analyzer LSP(Rust 툴킷 = coderag) | 38,270 | 0 | 도입 후보(coderag) |
| (a) | serena | 공인 | M | LSP 기반 심볼 단위 코드 탐색·리팩터 MCP(uvx, git HEAD 미고정) | 89,689 | 0 | 중복(coderag) |
| (a) | session-report | 공식 | S | ~/.claude/projects 트랜스크립트로 토큰·캐시·서브에이전트·비싼 프롬프트 HTML 보고서 | 14,667 | 75 | 도입(claude-doctor local) |
| (a) | skill-creator | 공식 | S | 스킬 작성·평가·벤치마크·description 최적화 | 428,976 | 117 | 중복(세션 내장) |
| (a) | sourcegraph | 공인 | SM | Sourcegraph 원격 코드 검색·참조 추적 | 15,276 | 99 | 중복(coderag) |
| (a) | superpowers | 공인 | SH | 브레인스토밍·계획·TDD·서브에이전트 개발·리뷰·스킬 작성 워크플로 스킬 15개 + SessionStart 주입 | 1,123,984 | 851 | 참고 |
| (b) | chrome-devtools-mcp | 서드파티(디렉터리 없음) | SM | 실 Chrome 제어·성능 트레이스·네트워크 분석 MCP + 디버깅 스킬 7개 | 123,586 | 809 | 참고 |
| (b) | cloudflare | 공인 | SM | Workers·DO·Wrangler 스킬 + MCP | 24,560 | 1,036 | 불필요(호스팅 미정) |
| (b) | figma | 서드파티 | SM | Figma 디자인 읽기·코드 연결 MCP + 스킬 16개 | 184,171 | 2,422 | 불필요 |
| (b) | frontend-design | 공식 | S | AI 기본값을 피한 디자인 계획→브리프 대조→구현→자기 비평 | 1,266,133 | 83 | 도입(웹) |
| (b) | gopls-lsp | 공식 | L | gopls LSP(vitrine Go 백엔드) | 43,478 | 0 | 도입 후보(웹, 바이너리 필요) |
| (b) | modern-web-guidance | 서드파티(디렉터리 없음) · Google Chrome | S | 최신 웹 모범 사례·크롬 확장 가이드 스킬 | 2,295 | 751 | 참고 |
| (b) | netlify-skills | 서드파티 | SM | Netlify 함수·배포 스킬 + MCP(상시 3,253) | 5,337 | 3,253 | 불필요(호스팅 미정) |
| (b) | playground | 공식 | S | 단일 HTML 인터랙티브 탐색기 생성 | 69,562 | 96 | 불필요 |
| (b) | playwright | 공인 | M | Playwright 브라우저 자동화 MCP(npx @latest) | 358,117 | 0 | 불필요 |
| (b) | superdesign | 공인 · Superdesign dev, Inc. | S | Superdesign 캔버스에서 UI 디자인(외부 서비스) | 8,002 | 193 | 불필요 |
| (b) | typescript-lsp | 공식 | L | typescript-language-server LSP | 228,185 | 0 | 도입 후보(웹, 바이너리 필요) |
| (b) | vercel | 공인 | SHM | Vercel 배포·함수·캐시 스킬 + MCP + 훅(상시 4,222) | 292,985 | 4,222 | 불필요(호스팅 미정) |
| (c) | 42crunch-api-security-testing | 공인 · 42Crunch | S | OpenAPI 감사·스캔(42Crunch) | 3,474 | 979 | 불필요 |
| (c) | ai-plugins | 공인 | SAH | Endor Labs 공급망 스캔(endorctl) | 5,254 | 1,508 | 불필요 |
| (c) | aikido | 서드파티 | SM | Aikido SAST·비밀·IaC 스캔(MCP, 계정) | 10,363 | 534 | 불필요 |
| (c) | claude-security | 공식 | SAH | 다중 에이전트 전수 보안 스캔, 반증 검증, SARIF, 패치 제안 | 26,386 | 781 | 도입(웹, 수동)+참고 |
| (c) | code-modernization | 공식 | ACH | 레거시 평가·하드닝·이관 워크플로(에이전트 8, 명령 다수, 훅 5종) | 10,082 | 1,377 | 불필요 |
| (c) | code-review | 공식 | C | PR 다중 에이전트 리뷰 /code-review | 477,558 | 25 | 중복(내장) |
| (c) | code-simplifier | 공식 | A | 최근 수정 코드 단순화 에이전트(opus 고정, JS/React 전제) | 371,422 | 69 | 중복(/simplify) |
| (c) | coderabbit | 공인 | SAC | CodeRabbit 외부 AI 리뷰 | 34,733 | 278 | 중복 |
| (c) | commit-commands | 공식 | C | /commit, /commit-push-pr, /clean_gone | 178,476 | 108 | 불필요 |
| (c) | feature-dev | 공식 | AC | 탐색·설계·리뷰 3단계 기능 개발 | 269,187 | 243 | 불필요 |
| (c) | greptile | 공인 · Greptile | CM | Greptile PR 리뷰 MCP | 57,560 | 52 | 중복 |
| (c) | nightvision | 서드파티 | S | NightVision DAST | 2,292 | 554 | 불필요 |
| (c) | pr-review-toolkit | 공식 | AC | 관점별 PR 리뷰 에이전트 6개(silent-failure, type-design 등) | 123,475 | 2,038 | 참고 |
| (c) | pyright-lsp | 공식 | L | Pyright LSP(우리 Python 훅·도구) | 118,419 | 0 | 불필요(지금) |
| (c) | qodo | 공인 · Qodo | S | Qodo 코드 리뷰·표준 | 365 | 967 | 중복 |
| (c) | qodo-standards | 공인 · Qodo | S | Qodo 규칙 관리 | 74 | 293 | 불필요 |
| (c) | ralph-loop | 공식 | CH | Stop 훅으로 같은 프롬프트를 반복하는 루프 | 199,259 | 89 | 중복(/loop) |
| (c) | security-guidance | 공식 | H | 편집 시 정규식 경고 + Stop 때 diff LLM 리뷰 + 커밋 에이전트 리뷰 | 268,918 | 0 | 도입(웹 project) |
| (c) | semgrep | 공인 | SHM | Semgrep Guardian MCP + 훅(실시간 SAST) | 21,169 | 452 | 불필요(지금) |
| (c) | sonarqube | 서드파티 · SonarSource | SAH | SonarQube 규칙·품질 게이트 + 훅 | 8,855 | 750 | 불필요 |
| (c) | sonatype-guide | 공인 | SM | Sonatype 의존성 보안 MCP | 7,608 | 241 | 불필요 |
| (c) | stackhawk-api | 공인 · StackHawk | S | StackHawk 플랫폼 API 보고 | 194 | 235 | 불필요 |
| (c) | stackhawk-hawkscan | 공인 · StackHawk | SH | StackHawk DAST 실행·해석 | 232 | 362 | 불필요 |
| (d) | activecampaign | 공인 · ActiveCampaign | SACM | Marketing automation, CRM, and email marketing powered by ActiveCampaign. M… | 207 | 853 |  |
| (d) | adobe-for-creativity | 공인 · Adobe | SM | Harness Adobe's creative AI-powered tools to edit images, automate design w… | 3,986 | 4,053 |  |
| (d) | agent-sdk-dev | 공식 | AC | Development kit for working with the Claude Agent SDK | 67,988 | 238 |  |
| (d) | agentforce-adlc | 서드파티 | SAH | Agentforce Agent Development Life Cycle — author, discover, scaffold, deplo… | 1,536 | 1,128 |  |
| (d) | airtable | 공인 · Airtable | SM | Airtable is the database and operations layer for your agents — whether run… | 1,886 | 1,634 |  |
| (d) | airwallex-agentos | 공인 · Airwallex | SM | Bring Airwallex's global financial infrastructure to Claude. Orchestrate ac… | 447 | 995 |  |
| (d) | airwallex-dev | 공인 · Airwallex | SM | Build Airwallex payment integrations in your own codebase. Generates the ch… | 136 | 1,050 |  |
| (d) | aiven | 공인 · Aiven | SM | Easily deploy managed PostgreSQL (pg), Kafka, OpenSearch, Clickhouse and ot… | 177 | 226 |  |
| (d) | alloydb | 서드파티 · Google LLC | M | Create, connect, and interact with an AlloyDB for PostgreSQL database and d… | 1,110 | 0 |  |
| (d) | alloydb-omni | 서드파티 · Google LLC | SM | Create, connect, and interact with an AlloyDB Omni database and data. | 483 | 182 |  |
| (d) | altimate-code | 공인 · AltimateAI | SCH | Delegates dbt and warehouse work to altimate-code, a specialized CLI agent … | 212 | 921 |  |
| (d) | amazon-location-service | 공인 | SM | Guide developers through adding maps, places search, geocoding, routing, an… | 3,623 | 212 |  |
| (d) | amazon-selling-partner | 공인 · Amazon | SCM | Connect your Amazon Seller Central account to Claude. Ask about sales, inve… | 45 | 2,955 |  |
| (d) | amd-skills | 공인 · AMD | S | AMD's verified Agent Skills in one plugin: route image/audio through local … | 431 | 1,067 |  |
| (d) | amplitude | 공인 | SM | Use Amplitude as an expert analyst — instrument Amplitude, discover product… | 2,911 | 4,786 |  |
| (d) | apollo | 공인 · Apollo.io | SM | Prospect, enrich leads, load outreach sequences, and query sales analytics … | 1,857 | 320 |  |
| (d) | apollo-skills | 공인 · Apollo GraphQL | SML | Apollo GraphQL agent skills for Claude Code — Apollo Client, Server, Federa… | 1,135 | 2,200 |  |
| (d) | appwrite | 공인 · Appwrite | SCM | Appwrite tools for Claude Code, including SDK skills, Appwrite MCP servers,… | 1,017 | 1,225 |  |
| (d) | asana | 공인 | C | Asana project management integration. Connects Claude Code to Asana's V2 MC… | 11,369 | 52 |  |
| (d) | astronomer-data-agents | 서드파티 | SH | Data engineering for Apache Airflow and Astronomer. Author DAGs with best p… | 2,588 | 5,978 |  |
| (d) | atlan | 공인 | SM | Atlan data catalog plugin for Claude Code. Search, explore, govern, and man… | 2,167 | 259 |  |
| (d) | atlassian | 공인 | SM | Connect to Atlassian products including Jira and Confluence. Search and cre… | 105,141 | 1,070 |  |
| (d) | atlassian-twg-cli | 공인 · Atlassian | S | Teamwork Graph CLI is Atlassian's agent-first interface to your entire work… | 734 | 172 |  |
| (d) | atomic-agents | 서드파티 | - | Comprehensive development workflow for building AI agents with the Atomic A… | 19,931 | 0 |  |
| (d) | auth0 | 공인 · Auth0 | S | Enterprise-grade auth, easy to implement. Add login, SSO, MFA, and access c… | 6,408 | 264 |  |
| (d) | aws-agents | 공인 · Amazon Web Services | SM | Build, deploy, and operate AI agents on AWS. Skills for scaffolding agents … | 3,540 | 2,356 |  |
| (d) | aws-agents-for-devsecops | 공인 · Amazon Web Services | SCM | Investigate incidents, review code and execute UAT for release readiness, s… | 1,307 | 2,347 |  |
| (d) | aws-amplify | 공인 | SM | Build full-stack apps with AWS Amplify Gen 2 using guided workflows for aut… | 2,198 | 386 |  |
| (d) | aws-core | 공인 · Amazon Web Services | SHM | Build, deploy, and operate applications on AWS. Skills to author infrastruc… | 11,991 | 7,063 |  |
| (d) | aws-data-analytics | 공인 · Amazon Web Services | SM | Data lake, analytics, and ETL workflows with S3 Tables, AWS Glue, and Athen… | 2,535 | 4,079 |  |
| (d) | aws-serverless | 공인 | SHM | Design, build, deploy, test, and debug serverless applications with AWS Ser… | 9,867 | 1,363 |  |
| (d) | aws-startup-advisor | 공인 · Amazon Web Services | SACHM | Personalized AWS guidance built on patterns from 350,000+ startups. Get arc… | 1,490 | 5,398 |  |
| (d) | aws-transform | 공인 · Amazon Web Services | SM | Migrate, modernize, and upgrade codebases to AWS. Transforms .NET Framework… | 768 | 399 |  |
| (d) | azure | 서드파티 | SHM | Transform Claude into an Azure expert. This plugin integrates the Azure MCP… | 11,238 | 6,266 |  |
| (d) | azure-cosmos-db-assistant | 서드파티 | SAC | Expert assistant for Azure Cosmos DB — data modeling, query optimization, p… | 1,963 | 528 |  |
| (d) | azure-sql-developer | 서드파티 · Microsoft | S | Agent skills for Azure SQL Developer, the Azure SQL Database engine running… | 419 | 4,881 |  |
| (d) | base44 | 공인 | S | Build and deploy Base44 full-stack apps with CLI project management and Jav… | 2,184 | 1,156 |  |
| (d) | bigdata-com | 공인 · RavenPack | SM | Official Bigdata.com plugin providing financial research, analytics, and in… | 2,215 | 6,661 |  |
| (d) | bigquery-data-analytics | 서드파티 · Google LLC | SM | Connect, query, and generate data insights for BigQuery datasets and data. | 1,017 | 79 |  |
| (d) | blackrock-advisor-center-plugin | 공인 · BlackRock Advisor Center | SM | BlackRock Advisor Center 360° skills for financial advisors: portfolio revi… | 54 | 1,080 |  |
| (d) | boltz | 공인 · Boltz | S | Predict structures, screen molecules and proteins, and design binders with … | 392 | 813 |  |
| (d) | box | 공인 | S | Work with your Box content directly from Claude Code — search files, organi… | 1,681 | 1,028 |  |
| (d) | brightdata-plugin | 서드파티 | S | Web scraping, Google search, structured data extraction, and MCP server int… | 4,211 | 5,331 |  |
| (d) | browser-use | 공인 · Browser Use | M | Give Claude a real browser — your Chrome or a Browser Use Cloud browser. Us… | 8,646 | 0 |  |
| (d) | build-with-wordpress | 서드파티(디렉터리 없음) | SC | Craft production-grade WordPress sites and applications. Everything from th… | 1,182 | 227 |  |
| (d) | buildkite | 공인 · Buildkite | S | Official Buildkite skills for Claude Code, Cursor, and other AI coding agen… | 890 | 1,559 |  |
| (d) | canva | 공인 · Canva | SM | Create, edit, review, resize, and brand-check Canva designs with the Canva … | 2,935 | 786 |  |
| (d) | carbone-skill | 서드파티(디렉터리 없음) · Carbone | S | Official Carbone skill — complete templating language reference covering ta… | 513 | 384 |  |
| (d) | carta-cap-table | 공인 · Carta Engineering | SH | Carta Cap Table plugin — skills and hooks for querying cap tables, grants, … | 694 | 5,657 |  |
| (d) | carta-crm | 공인 · Carta Engineering | SH | Manage the Carta CRM conversationally — search, add, update, and enrich inv… | 580 | 4,196 |  |
| (d) | carta-investors | 공인 · Carta Engineering | SH | Carta Investors plugin — skills for querying investor data, performance ben… | 682 | 6,538 |  |
| (d) | catalyst-by-zoho | 공인 · Catalyst by Zoho | SCHM | Official Claude Code plugin for Catalyst by Zoho — full-stack serverless cl… | 272 | 3,299 |  |
| (d) | cds-mcp | 공인 · SAP SE | M | AI-assisted development of SAP Cloud Application Programming Model (CAP) pr… | 1,529 | 0 |  |
| (d) | chronograph-gp | 공인 · Chronograph | SA | Portfolio monitoring, valuations and analytics for private-capital GP teams… | 26 | 1,750 |  |
| (d) | chronograph-lp | 공인 · Chronograph | SA | Portfolio monitoring and analytics for private-capital LP teams using the C… | 31 | 1,370 |  |
| (d) | circle-skills | 공인 · Circle | SM | Ship stablecoin apps faster. Best-practice skills for USDC payments, cross-… | 695 | 4,176 |  |
| (d) | circleback | 공인 | M | Circleback conversational context integration. Search and access meetings, … | 12,752 | 0 |  |
| (d) | ckeditor | 서드파티 · CKEditor (CKSource) | S | Install, configure, and integrate CKEditor 5 (free and premium) in any Java… | 215 | 207 |  |
| (d) | clangd-lsp | 공식 | L | C/C++ language server (clangd) for code intelligence | 31,586 | 0 |  |
| (d) | clay | 서드파티(디렉터리 없음) · Clay | SH | Work with Clay from Claude Code: set up and sign in to the clay CLI, query … | 76 | 2,857 |  |
| (d) | clickhouse | 공인 · ClickHouse | SM | Connect Claude to your ClickHouse Cloud databases. Browse organizations, se… | 1,557 | 165 |  |
| (d) | clickhouse-best-practices | 공인 · ClickHouse Inc | S | 28 best practice rules for ClickHouse schema design, query optimization, an… | 1,219 | 2,141 |  |
| (d) | cloud-sql-mysql | 서드파티 · Google LLC | M | Connect and interact with a Cloud SQL for MySQL database and data. | 872 | 0 |  |
| (d) | cloud-sql-postgresql | 서드파티 · Google LLC | M | Create, connect, and interact with a Cloud SQL for PostgreSQL database and … | 3,339 | 0 |  |
| (d) | cloud-sql-sqlserver | 서드파티 · Google LLC | M | Connect to Cloud SQL for SQL Server | 681 | 0 |  |
| (d) | cloudinary | 공인 | S | Use Cloudinary directly in Claude. Manage assets, apply transformations, op… | 2,743 | 369 |  |
| (d) | cockroachdb | 서드파티 · Cockroach Labs | SAHM | Connect Claude Code directly to your CockroachDB clusters for hands-on data… | 2,350 | 5,191 |  |
| (d) | codspeed | 서드파티(디렉터리 없음) · CodSpeed | SM | CodSpeed is the all-in-one performance testing toolkit. Dive into benchmark… | 1,333 | 422 |  |
| (d) | confidence | 서드파티(디렉터리 없음) · Spotify Confidence | SCM | Access Confidence feature flags, experiments, and migration tools directly … | 433 | 2,419 |  |
| (d) | convex | 서드파티(디렉터리 없음) · Convex | SCHM | Official Convex plugin for Claude Code with bundled Convex skills, the conv… | 2,271 | 2,469 |  |
| (d) | crowdsec | 서드파티 · CrowdSec | S | Operational skill for installing, configuring, operating, and debugging Cro… | 291 | 480 |  |
| (d) | crowdstrike-falcon-foundry | 공인 · CrowdStrike | SH | CrowdStrike Falcon Foundry development skills for building cybersecurity ap… | 1,257 | 2,563 |  |
| (d) | crowdstrike-falcon-fusion | 공인 · CrowdStrike | SH | CrowdStrike Falcon Fusion skills for authoring, deploying, and executing Fu… | 194 | 1,152 |  |
| (d) | csharp-lsp | 공식 | L | C# language server for code intelligence | 47,889 | 0 |  |
| (d) | cwc-makers | 공식 | SC | Onboard a Code-with-Claude Makers Cardputer with one /maker-setup command —… | 939 | 409 |  |
| (d) | data | 서드파티 | SH | Data engineering for Apache Airflow and Astronomer. Author DAGs with best p… | 8,418 | 5,978 |  |
| (d) | data-agent-kit | 서드파티(디렉터리 없음) · Google LLC | SHM | This plugin provides a specialized suite of skills for data engineers and d… | - | 8,279 |  |
| (d) | data-engineering | 서드파티 | SH | Data engineering plugin - warehouse exploration, pipeline authoring, Airflo… | 20,165 | 5,978 |  |
| (d) | databases-on-aws | 공인 | SHM | Expert database guidance for the AWS database portfolio. Design schemas, ex… | 3,176 | 472 |  |
| (d) | databricks | 공인 · Databricks | SCH | Databricks skills for the CLI, Apps, Lakebase, Model Serving, Lakeflow Jobs… | 1,377 | 4,889 |  |
| (d) | datadog | 서드파티 · Datadog | SH | Use Datadog directly in Claude Code through a preconfigured Datadog MCP ser… | 28,706 | 633 |  |
| (d) | datahub-skills | 공인 · DataHub | SAC | DataHub development and interaction toolkit with connector planning, PR rev… | 801 | 3,544 |  |
| (d) | dataproc | 서드파티 · Google LLC | M | Manage Dataproc clusters and jobs. | 407 | 0 |  |
| (d) | datarobot-agent-skills | 공인 · DataRobot | S | DataRobot skills for AI/ML workflows — model training, deployment, predicti… | 1,594 | 2,664 |  |
| (d) | dataverse | 공인 | S | Agent skills for building on, analyzing, and managing Microsoft Dataverse —… | 3,569 | 1,101 |  |
| (d) | deepeval | 공인 · Confident AI | S | Skills for adding DeepEval evaluations, tracing, datasets, Confident AI rep… | 388 | 1,137 |  |
| (d) | deploy-on-aws | 공인 | SHM | Deploy applications to AWS with architecture recommendations, cost estimate… | 11,780 | 579 |  |
| (d) | desktop-commander | 공인 · Desktop Commander | S | MCP server for terminal commands, process management, and file operations a… | 9,290 | 1,579 |  |
| (d) | discord | 공식 | SM | Discord messaging bridge with built-in access control. Manage pairing, allo… | 35,849 | 160 |  |
| (d) | dominodatalab | 공인 · Domino Data Lab | SACM | Full Domino Data Lab platform support — workspaces, jobs, model deployment,… | 566 | 4,438 |  |
| (d) | dropbox | 공인 · Dropbox | SM | The Dropbox plugin for Claude connects your Dropbox files directly to Claud… | 527 | 552 |  |
| (d) | duckdb-skills | 서드파티 · DuckDB Foundation | S | DuckDB-powered skills for Claude Code: read any data file, attach and query… | 2,034 | 1,000 |  |
| (d) | duende-skills | 공인 · Duende Software | S | Duende development skills and agents for Claude Code — covering OAuth/OIDC … | 667 | 2,238 |  |
| (d) | dynatrace | 공인 · Dynatrace | SM | Dynatrace observability skills: DQL query patterns, application and infrast… | 96 | 8,311 |  |
| (d) | exa | 공인 · Exa | S | Exa AI web search, deep research, and content extraction. Provides MCP tool… | 7,308 | 193 |  |
| (d) | explanatory-output-style | 공식 | H | Adds educational insights about implementation choices and codebase pattern… | 66,990 | 0 |  |
| (d) | expo | 공인 | SHM | Official Expo skills for building, deploying, upgrading, and debugging Reac… | 20,895 | 4,203 |  |
| (d) | fakechat | 공식 | M | Localhost web chat for testing the channel notification flow. No tokens, no… | 8,536 | 0 |  |
| (d) | fastly-agent-toolkit | 서드파티 | S | Fastly development tools and platform skills | 3,504 | 2,510 |  |
| (d) | fiftyone | 서드파티 | SCM | Build high-quality datasets and computer vision models. Visualize datasets,… | 3,027 | 2,453 |  |
| (d) | firebase | 공인 | M | Google Firebase MCP integration. Manage Firestore databases, authentication… | 27,979 | 0 |  |
| (d) | firecrawl | 공인 | SM | Web scraping and crawling powered by Firecrawl. Turn any website into clean… | 43,157 | 231 |  |
| (d) | firestore-native | 서드파티 · Google LLC | M | Connect and interact with Firestore databases, collections, and documents. | 671 | 0 |  |
| (d) | forge-skills | 공인 · Atlassian | SM | Forge-focused skills and MCP configuration for Atlassian Forge: scaffold an… | 1,161 | 1,249 |  |
| (d) | fullstory | 공인 · Fullstory | SAM | Connect Claude to Fullstory to query behavioral analytics, session replays,… | 485 | 916 |  |
| (d) | gc-ai | 공인 · GC AI | SAM | Work in your GC AI legal knowledge base from Claude: upload documents, run … | 61 | 338 |  |
| (d) | github | 공인 | M | Official GitHub MCP server for repository management. Create issues, manage… | 345,391 | 0 |  |
| (d) | gitkraken | 공인 · GitKraken | - | Gives Claude access to your real Git and project context: commits, branches… | 726 | 0 |  |
| (d) | gitlab | 공인 | M | GitLab DevOps platform integration. Manage repositories, merge requests, CI… | 43,919 | 0 |  |
| (d) | google-cloud-storage | 서드파티 · Google LLC | S | Official Google Cloud Storage (GCS) plugin. Manage buckets and objects, tra… | 491 | 1,612 |  |
| (d) | govtribe | 서드파티 · GovTribe | SM | Government contracting research and capture workflows in Claude: opportunit… | 22 | 627 |  |
| (d) | grafana-assistant | 서드파티(디렉터리 없음) · Grafana | S | Skills and rules for developing and using the Grafana Assistant app and CLI… | 881 | 149 |  |
| (d) | grafana-cloud-mcp | 공인 · Grafana | SM | Hosted MCP server for AI-assisted Grafana Cloud observability — no local in… | 894 | 207 |  |
| (d) | grafana-mcp | 공인 · Grafana | SM | MCP server for AI-assisted Grafana dashboard, datasource, alerting, and inc… | 2,650 | 133 |  |
| (d) | growthbook | 공인 · GrowthBook | S | A suite of agent skills for the full GrowthBook feature flag and experiment… | 242 | 968 |  |
| (d) | honeycomb | 공인 · Honeycomb | SACHM | Skills, agents, and workflows for Honeycomb observability — query patterns,… | 444 | 3,413 |  |
| (d) | hostinger | 공인 · Hostinger | SM | Deploy, manage and monitor your Hostinger services directly from Claude Cod… | 1,682 | 852 |  |
| (d) | hubspot-sales | 공인 · HubSpot | SAM | Run your HubSpot sales workflow directly from Claude. Adds skills that cove… | 105 | 2,282 |  |
| (d) | huggingface-skills | 공인 | SM | Build, train, evaluate, and use open source AI models, datasets, and spaces… | 36,829 | 5,120 |  |
| (d) | hunter | 공인 · Hunter.io | SM | Find and verify professional email addresses, search contacts by domain, an… | 1,090 | 1,091 |  |
| (d) | hyperframes | 서드파티(디렉터리 없음) · HeyGen | S | HyperFrames by HeyGen. Write HTML, render video. Compositions, GSAP and run… | 4,062 | 3,942 |  |
| (d) | idmp-plugin | 공인 · TaosData | S | TDengine IDMP plugin with packaged skills for discovery, schema inspection,… | 264 | 1,645 |  |
| (d) | imessage | 공식 | SM | iMessage messaging bridge with built-in access control. Reads chat.db direc… | 17,409 | 159 |  |
| (d) | incident-io | 공인 · incident.io | SM | Work with incident.io from Claude: respond to and investigate incidents, ch… | 227 | 1,678 |  |
| (d) | informatica-for-claude-platform | 서드파티(디렉터리 없음) · Informatica | SM | Governed catalog discovery for Informatica Intelligent Data Management Clou… | 39 | 343 |  |
| (d) | intercom | 공인 | SM | Intercom integration for Claude Code. Search conversations, analyze custome… | 3,321 | 526 |  |
| (d) | intuit-quickbooks | 공인 · Intuit QuickBooks | S | QuickBooks business insights and actions: financial health briefings across… | 62 | 2,168 |  |
| (d) | jdtls-lsp | 공식 | L | Java language server (Eclipse JDT.LS) for code intelligence | 35,659 | 0 |  |
| (d) | jfrog | 공인 · JFrog Ltd. | SHM | Use the JFrog Platform from Claude Code: Artifactory repos and artifacts, s… | 494 | 1,658 |  |
| (d) | knowledge-catalog | 서드파티 · Google LLC | - | Connect to Knowledge Catalog to discover, manage, monitor, and govern data … | 1,070 | 0 |  |
| (d) | kotlin-lsp | 공식 | L | Kotlin language server for code intelligence | 25,668 | 0 |  |
| (d) | langfuse | 공인 · Langfuse | S | Skills for working with Langfuse, the open-source LLM engineering platform … | 994 | 416 |  |
| (d) | laravel-boost | 공인 | M | Laravel development toolkit MCP server. Provides intelligent assistance for… | 22,614 | 0 |  |
| (d) | leadfeeder | 공인 · Leadfeeder | SM | Turn website visitor signals into pipeline with Leadfeeder: daily visitor b… | 38 | 1,139 |  |
| (d) | learn-with-coursera | 공인 · Coursera | S | Turn any learning intent into a personalized Coursera experience. Asks thre… | 566 | 341 |  |
| (d) | learning-output-style | 공식 | H | Interactive learning mode that requests meaningful code contributions at de… | 43,728 | 0 |  |
| (d) | legalzoom | 공인 | SCM | Attorney guidance and legal tools for business and personal needs. AI-power… | 5,246 | 124 |  |
| (d) | linear | 공인 | M | Linear issue tracking integration. Create issues, manage projects, update s… | 52,791 | 0 |  |
| (d) | linq-alpha | 서드파티 · LinqAlpha | SM | LinqAlpha financial research in Claude: guided setup for the LinqAlpha conn… | 24 | 362 |  |
| (d) | liquid-lsp | 서드파티 · Shopify | L | LSP integration for Shopify Liquid templates via the Shopify CLI theme lang… | 2,370 | 0 |  |
| (d) | liquid-skills | 공인 · Shopify | S | Liquid language fundamentals, CSS/JS/HTML coding standards, and WCAG access… | 5,931 | 407 |  |
| (d) | logfire | 서드파티 · Pydantic | SCM | Add Logfire observability to Python applications with auto-instrumentation … | 1,528 | 1,436 |  |
| (d) | logrocket | 공인 · LogRocket | SM | Connect Claude Code to LogRocket to query session replays, metrics, issues,… | 440 | 93 |  |
| (d) | looker | 서드파티 · Google LLC | M | Connect to Looker and interact with your data using LookML. | 652 | 0 |  |
| (d) | lovable | 공인 · Lovable | CM | Build, iterate on, deploy, and manage Lovable apps from Claude Code. Bundle… | 1,858 | 95 |  |
| (d) | lusha | 공인 · Lusha | SM | Prospect, enrich, and build call-ready lead lists using Lusha's B2B intelli… | 444 | 830 |  |
| (d) | mapbox | 서드파티(디렉터리 없음) · Mapbox | SM | Mapbox skills and MCP servers for building location-aware applications with… | 1,243 | 1,661 |  |
| (d) | math-olympiad | 공식 | S | Solve competition math (IMO, Putnam, USAMO) with adversarial verification t… | 3,989 | 279 |  |
| (d) | math-proof | 공식 | SA | Two skills for hard mathematics problems, each ending in a self-contained p… | 12 | 558 |  |
| (d) | mcp-apps | 공인 · Anthropic / Model Context Protocol | S | Skills for creating MCP Apps with the MCP Apps SDK | 3,139 | 630 |  |
| (d) | mcp-server-dev | 공식 | S | Skills for designing and building MCP servers that work seamlessly with Cla… | 42,422 | 507 |  |
| (d) | mcp-tunnels | 공식 | C | Connect Claude to a private MCP server through an Anthropic MCP tunnel. The… | 2,268 | 83 |  |
| (d) | mercadopago | 공인 · Mercado Pago Developer Experience | SACHM | Mercado Pago full-product integration toolkit. One agent routes to four orc… | 1,381 | 738 |  |
| (d) | mergify | 서드파티 · Mergify | S | Skills for the Mergify CLI: manage merge queues, stacked pull requests, Tes… | 315 | 1,129 |  |
| (d) | microsoft-docs | 공인 | SM | Access official Microsoft documentation, API references, and code samples f… | 31,118 | 490 |  |
| (d) | migration-to-aws | 공인 · Amazon Web Services | SAM | Plan a migration from Google Cloud Platform (and OpenAI/Gemini AI workloads… | 2,696 | 3,624 |  |
| (d) | mintlify | 공인 | SM | Build beautiful documentation sites with Mintlify. Convert non-markdown fil… | 7,535 | 93 |  |
| (d) | miro | 서드파티 · Miro | SM | Secure access to Miro boards. Enables AI to read board context, create diag… | 6,291 | 321 |  |
| (d) | mlflow | 공인 · MLflow Team | SH | Skills for tracing, evaluating, and improving AI agents with MLflow. Suppor… | 410 | 1,994 |  |
| (d) | monday-crm | 공인 · monday.com | SM | Run your monday CRM in plain language. Build a pipeline from scratch, start… | 512 | 1,532 |  |
| (d) | mongodb | 공인 | SM | Official Claude plugin for MongoDB (MCP Server + Skills). Connect to databa… | 10,395 | 1,551 |  |
| (d) | mongodb-atlas | 공인 · MongoDB | SM | Connect to MongoDB Atlas clusters only through the Atlas Managed MCP Server… | 1,113 | 1,476 |  |
| (d) | neon | 공인 | S | Manage your Neon projects and databases with the neon-postgres agent skill … | 5,123 | 2,119 |  |
| (d) | netsuite-ai-companion | 공인 · Oracle NetSuite | S | Guides AI assistants that use the NetSuite AI Connector: tool-selection ord… | 94 | 120 |  |
| (d) | netsuite-finance-analyst | 공인 · Oracle NetSuite | S | Director-level finance analysis on live NetSuite data: financial reporting,… | 138 | 235 |  |
| (d) | netsuite-suitecloud | 공인 · Oracle NetSuite | S | Develop NetSuite SuiteCloud solutions with SuiteScript, SDF, and best pract… | 1,323 | 1,232 |  |
| (d) | newrelic | 공인 · New Relic | SM | New Relic observability intelligence for Claude Code. Investigate APM perfo… | 522 | 329 |  |
| (d) | nimble | 공인 | SCM | Nimble web data toolkit — search, extract, map, crawl the web and work with… | 3,153 | 4,807 |  |
| (d) | noibu | 공인 · Noibu | S | Built for ecommerce, the Noibu plugin bridges the gap between customer expe… | 152 | 1,155 |  |
| (d) | notion | 공인 | CM | Notion workspace integration. Search pages, create and update documents, ma… | - | 217 |  |
| (d) | nvidia-skills | 서드파티 · NVIDIA | S | Find the right NVIDIA skill for GPU acceleration, CUDA, AI agents, data loa… | 2,987 | 279 |  |
| (d) | oracle-ai-data-platform-workbench-databricks-migrator | 서드파티 · Oracle | SAC | Drive the Oracle AI Data Platform (AIDP) Databricks Migration Toolkit in na… | 295 | 2,405 |  |
| (d) | oracle-ai-data-platform-workbench-engineer-agent | 서드파티 · Oracle | SH | Oracle AI Data Platform (AIDP) Workbench engineer agent for Claude Code — a… | 386 | 6,612 |  |
| (d) | oracle-ai-data-platform-workbench-spark-connectors | 공인 · Oracle | S | Oracle AI Data Platform Workbench Spark connectors for Claude Code. 18 conn… | 1,135 | 4,573 |  |
| (d) | oracledb | 서드파티 · Google LLC | M | Connect, query, and interact with Oracle Databases and their data. | 835 | 0 |  |
| (d) | outputai | 공인 · Output.ai | SAH | Output.ai workflow development toolkit for Claude Code. Adds 5 specialist a… | 1,019 | 4,460 |  |
| (d) | pagerduty | 서드파티 | CM | Enhance code quality and security through PagerDuty risk scoring and incide… | 5,535 | 96 |  |
| (d) | paypal | 공인 · PayPal | SCHM | PayPal development plugin for Claude — integrate payments, subscriptions, i… | 357 | 906 |  |
| (d) | pendo-analytics | 서드파티(디렉터리 없음) · Pendo | SM | Bring Pendo product analytics into Claude Code: account health, feature ado… | 32 | 1,137 |  |
| (d) | pendo-guides | 서드파티(디렉터리 없음) · Pendo | S | Create production-ready Pendo in-app guides (walkthroughs, announcements, a… | 33 | 289 |  |
| (d) | pendo-orchestrate | 서드파티(디렉터리 없음) · Pendo | SM | Create, configure and edit draft Pendo Orchestrate email journeys, includin… | 30 | 160 |  |
| (d) | php-lsp | 공식 | L | PHP language server (Intelephense) for code intelligence | 35,091 | 0 |  |
| (d) | pigment | 공인 · Pigment | SM | Analyze business data and build custom Pigment models, metrics, and boards … | 842 | 3,866 |  |
| (d) | pinecone | 공인 | SCHM | Pinecone vector database integration. Streamline your Pinecone development … | 10,553 | 1,231 |  |
| (d) | pixeltable | 공인 · Pixeltable | SH | Build multimodal AI applications with Pixeltable -- tables, computed column… | 299 | 197 |  |
| (d) | planetscale | 공인 | SM | An authenticated hosted MCP server that accesses your PlanetScale organizat… | 2,959 | 1,510 |  |
| (d) | posthog | 공인 | SACHM | Access PostHog analytics, feature flags, experiments, error tracking, and i… | 14,795 | 29,370 |  |
| (d) | postiz | 서드파티 | S | Social media automation CLI for scheduling posts, managing integrations, up… | 3,980 | 191 |  |
| (d) | postman | 공인 | SHM | Work with Postman from your agent: bootstrap a repo's Postman setup, mock a… | 24,139 | 1,900 |  |
| (d) | preset-cli-skills | 공인 · Preset | S | Preset CLI skills for explicit shell, scripting, and CI/CD workflows driven… | 776 | 235 |  |
| (d) | prisma | 공인 | M | Prisma MCP integration for Postgres database management, schema migrations,… | 8,893 | 0 |  |
| (d) | project-artifact | 공식 | S | Generate and publish a living project status page — overview & success crit… | 2,063 | 315 |  |
| (d) | pydantic-ai | 서드파티 | S | Write accurate Pydantic AI code from the start. Up-to-date patterns, decisi… | 6,501 | 1,365 |  |
| (d) | qdrant-skills | 서드파티 · Qdrant | S | Agent skills for Qdrant vector search covering scaling, performance optimiz… | 2,074 | 2,333 |  |
| (d) | qt-development-skills | 공인 · Qt Group | SM | Agentic engineering skills for Qt software development — Qt C++/QML code re… | 3,523 | 2,205 |  |
| (d) | quarkus-agent | 서드파티 · Quarkus | M | MCP server for AI coding agents to create, manage, and interact with Quarku… | 1,317 | 0 |  |
| (d) | railway | 공인 | SHM | Deploy and manage apps, databases, and infrastructure on Railway. Covers pr… | 8,278 | 368 |  |
| (d) | rc | 서드파티(디렉터리 없음) | SM | Configure RevenueCat projects, apps, products, entitlements, and offerings … | 3,444 | 2,943 |  |
| (d) | receipts | 공식 | S | A personal Claude Code impact report for justifying your usage to a manager… | 718 | 216 |  |
| (d) | redis-development | 공인 · Redis | S | Redis development best practices — data structures, query engine, vector se… | 4,392 | 1,489 |  |
| (d) | render | 공인 · Render | SACHM | Deploy, debug, and monitor applications on Render. Includes skills, an agen… | 2,352 | 3,132 |  |
| (d) | resend | 공인 · Resend | SM | Agent skills for working with Resend to send and receive emails — email API… | 5,196 | 790 |  |
| (d) | revenuecat | 공인 | SM | Configure RevenueCat projects, apps, products, entitlements, and offerings … | 4,027 | 2,943 |  |
| (d) | rill | 공인 · Rill Data | SM | Skills for developing and querying projects in the Rill business intelligen… | 378 | 317 |  |
| (d) | rootly | 공인 · Rootly | SAHM | Full-lifecycle incident management: deploy safety, incident response, on-ca… | 827 | 1,310 |  |
| (d) | ruby-lsp | 공식 | L | Ruby language server for code intelligence and analysis | 9,774 | 0 |  |
| (d) | runway-api | 공인 · Runway | S | Get guidance for integrating video, image and audio generation with the Run… | 1,354 | 953 |  |
| (d) | sagemaker-ai | 공인 | SM | Build, train, and deploy AI models with deep AWS AI/ML expertise brought di… | 1,756 | 3,468 |  |
| (d) | salesforce-development | 공인 · Salesforce | SACHM | Build Salesforce apps and agents using these core building blocks: metadata… | 622 | 8,302 |  |
| (d) | sanity | 공인 · Sanity | SCM | Sanity content platform integration with MCP server, agent skills, and slas… | 2,629 | 1,726 |  |
| (d) | sap-cds-mcp | 공인 · SAP SE | M | AI-assisted development of SAP Cloud Application Programming Model (CAP) pr… | 787 | 0 |  |
| (d) | sap-fiori-mcp-server | 공인 · SAP SE | SM | MCP server for SAP Fiori development tools for Claude Code. Build and modif… | 849 | 967 |  |
| (d) | sap-hana-cli | 서드파티 · SAP SE | M | 150+ SAP HANA database tools for AI assistants. Query tables, import/export… | 352 | 0 |  |
| (d) | sap-mdk-server | 공인 · SAP SE | M | MCP server for SAP Mobile Development Kit (MDK). Build and modify MDK appli… | 959 | 0 |  |
| (d) | save-to-spotify | 공인 · Spotify | S | Create polished audio episodes with TTS narration, rich timelines, cover im… | 826 | 254 |  |
| (d) | scandit-sdk | 공인 · Scandit | S | AI agent skills for integrating the Scandit Data Capture SDK — product sele… | 117 | 15,671 |  |
| (d) | sentry | 공인 | S | Sentry error monitoring integration. Access error reports, analyze stack tr… | 42,036 | 1,069 |  |
| (d) | sentry-cli | 공인 · Sentry | S | Skills for using the Sentry CLI to interact with Sentry from the command li… | 3,153 | 93 |  |
| (d) | servicenow-sdk | 공인 · ServiceNow | S | Create, edit, and deploy ServiceNow applications with the Fluent SDK effort… | 1,707 | 145 |  |
| (d) | setup-agent-analytics | 서드파티(디렉터리 없음) · Pendo | S | Detect AI agents in your codebase and instrument them with Pendo Agent Anal… | 98 | 246 |  |
| (d) | setup-mcp-agent-analytics | 서드파티(디렉터리 없음) · Pendo | S | Detect an MCP server's language (Python, TypeScript or Go) and instrument i… | 87 | 384 |  |
| (d) | shippo | 공인 · Shippo | SM | Shippo connects you to USPS, UPS, FedEx, DHL, and 40+ carriers, so you can … | 192 | 832 |  |
| (d) | shopify-ai-toolkit | 공인 · Shopify | SH | Shopify's AI Toolkit provides 18 development skills for building on the Sho… | 14,999 | 570 |  |
| (d) | slack | 공인 | SCM | Slack workspace integration. Search messages, access channels, read threads… | 111,919 | 1,456 |  |
| (d) | snowflake-cortex-code | 공인 · Snowflake | SH | Automatically route Snowflake prompts from Claude Code to Cortex Code for e… | 2,363 | 307 |  |
| (d) | spanner | 서드파티 · Google LLC | M | Connect and interact with Spanner data using natural language. | 403 | 0 |  |
| (d) | spotify-ads-api | 공인 | SAH | Manage Spotify ad campaigns with natural language. Create campaigns, ad set… | 1,511 | 2,019 |  |
| (d) | streaming-skills-plugin | 공인 · Confluent | S | Skills for streaming application developers, covering Kafka and Flink clien… | 235 | 3,132 |  |
| (d) | stripe | 공인 | SACHM | Stripe development plugin for Claude | 87,174 | 2,157 |  |
| (d) | sumup | 공인 | SM | SumUp payment integrations across terminal and online checkout flows. Build… | 2,601 | 658 |  |
| (d) | supabase | 공인 | SM | Supabase MCP integration for database operations, authentication, storage, … | 126,512 | 639 |  |
| (d) | swift-lsp | 공식 | L | Swift language server (SourceKit-LSP) for code intelligence | 24,566 | 0 |  |
| (d) | synthflow | 공인 · Synthflow | SM | Connects Claude Code to the Synthflow AI voice-agent platform through its h… | 163 | 273 |  |
| (d) | tavily | 공인 · Tavily Team | S | Build AI applications with real-time web data using Tavily's search, extrac… | 881 | 1,188 |  |
| (d) | teamcity-cli | 공인 · JetBrains | S | Agent skill for interacting with TeamCity CI/CD using the teamcity CLI. Ena… | 764 | 259 |  |
| (d) | telegram | 공식 | SM | Telegram messaging bridge with built-in access control. Manage pairing, all… | 106,438 | 167 |  |
| (d) | terraform | 공인 · HashiCorp | M | The Terraform MCP Server provides seamless integration with Terraform ecosy… | 12,452 | 0 |  |
| (d) | togetherai-skills | 공인 · Together AI | S | Agent Skills for Together AI platform — inference, training, embeddings, au… | 798 | 2,012 |  |
| (d) | twilio-developer-kit | 공인 · Twilio | S | Twilio Skills provide procedural knowledge for AI coding agents — which API… | 2,434 | 8,834 |  |
| (d) | ui-theme-designer | 공인 · SAP SE | S | Plugin for coding agents working with UI theme designer. Bundles two skills… | 3,953 | 567 |  |
| (d) | ui5 | 공인 · SAP SE | SM | SAPUI5 / OpenUI5 plugin for coding agents. Create and validate UI5 projects… | 2,231 | 2,623 |  |
| (d) | ui5-modernization | 공인 · SAP SE | SM | Complete UI5 modernization toolkit with workflow and specialized fix patter… | 779 | 5,521 |  |
| (d) | ui5-typescript-conversion | 공인 · SAP SE | S | SAPUI5 / OpenUI5 plugin for coding agents. Convert JavaScript based UI5 pro… | 2,480 | 68 |  |
| (d) | unity | 공인 · Unity Technologies | S | Unity's official plugin for Claude Code, with curated skills for game devel… | 2,675 | 5,948 |  |
| (d) | unreal-engine-skills-for-claude-code | 공인 · Epic Games | SH | Control Unreal Editor directly from Claude Code via MCP. Hundreds of tools … | 3,642 | 1,316 |  |
| (d) | valtown | 공인 · Val Town | SM | Build and deploy on Val Town. Bundles the Val Town MCP server and platform … | 443 | 1,221 |  |
| (d) | vanguard-advisor-tools | 서드파티 · Vanguard | SM | Vanguard Advisor Tools for financial professionals: research and compare fu… | 55 | 318 |  |
| (d) | vanta | 공인 · Vanta | SM | The Vanta plugin connects Claude Code to Vanta's security and compliance pl… | 841 | 207 |  |
| (d) | vanta-mcp-plugin | 공인 · Vanta | SM | The Vanta plugin connects Claude Code to Vanta's security and compliance pl… | 3,866 | 207 |  |
| (d) | vibe-prospecting | 공인 · vibeprospecting.ai | SC | Vibe Prospecting connects Claude to live B2B company and contact data so us… | 1,302 | 156 |  |
| (d) | vsql-extension-builder | 공인 · VillageSQL | S | Builds a VillageSQL extension for MySQL end-to-end through a 7-phase person… | 258 | 289 |  |
| (d) | windsor-ai | 공인 · Windsor.ai | SACM | Connect Claude Code to 325+ business data sources via Windsor.ai. Query mar… | 2,220 | 172 |  |
| (d) | wingspan | 공인 · Wingspan | SM | Ask Claude about the contractors you pay through Wingspan, what you owe the… | 63 | 1,021 |  |
| (d) | wix | 공인 | SM | Build, manage, and deploy Wix sites and apps. CLI development skills for da… | 3,824 | 2,702 |  |
| (d) | workos | 공인 · WorkOS | S | WorkOS integration skills for AuthKit, SSO, Directory Sync, RBAC, Vault, Au… | 1,020 | 541 |  |
| (d) | xcode | 서드파티(디렉터리 없음) · Apple Inc. | ? | Work with Xcode projects from Claude Code: build, run, and test schemes, re… | - | - |  |
| (d) | youdotcom-agent-skills | 공인 · You.com | SM | You.com agent skills for web search, research with citations, and content e… | 1,947 | 234 |  |
| (d) | zapier | 공인 | SAM | Connect 8,000+ apps to your AI workflow. Discover, enable, and execute Zapi… | 3,797 | 658 |  |
| (d) | zilliz | 서드파티 · Zilliz | - | Zilliz Cloud management plugin with 14 skills covering cluster lifecycle, c… | 967 | 0 |  |
| (d) | zocks-advisor | 공인 · Zocks | SM | Seven skills for financial advisors built on Zocks meeting intelligence: cl… | 47 | 1,741 |  |
| (d) | zoom-plugin | 서드파티(디렉터리 없음) | SM | Claude plugin for planning, building, and debugging Zoom integrations acros… | 3,764 | 2,984 |  |
| (d) | zoominfo | 공인 · ZoomInfo | SM | Search companies and contacts, enrich leads, find lookalikes, and get AI-ra… | 2,632 | 6,719 |  |
| (d) | zscaler | 공인 · Zscaler | CM | Manage Zscaler cloud security platform including ZPA (private access), ZIA … | 1,608 | 919 |  |
| (d) | zyte-web-data | 공인 · Zyte | SH | Web scraping skills for Claude Code powered by the Zyte API — scrape sites,… | 402 | 738 |  |

제작자 분포: 공인 197, 서드파티 55, 공식 44, 서드파티(디렉터리 없음) 21.

### 1.3 디렉터리에만 있는 검토 항목 (anthropic 52 + partner 182)

공식 마켓 이름과 겹치지 않는 디렉터리 항목이다.
대부분 Cowork·claude.ai용 업무 플러그인이다(knowledge-work, financial-services, claude-for-legal, life-sciences 등).
Claude Code 설치 경로는 저장소마다 다르고, 공식 마켓으로는 설치되지 않는다.
(a)(b)(c)만 줄로 적고, (d)는 수만 센다.

| 분류 | 이름 | 검토 | 저장소 | 한 줄 기능 |
|---|---|---|---|---|
| (a) | ai-adoption | 공인 | techwolf-ai/ai-first-toolkit plugins/ai-adoption | token-doctor: Claude 기록으로 토큰 낭비 습관 진단 |
| (a) | ai-firstify | 공인 | techwolf-ai/ai-first-toolkit plugins/ai-firstify | AI-first 설계 원칙으로 프로젝트 감사·재설계 |
| (a) | cognee-memory | 공인 | topoteretes/cognee-integrations integrations/claude-code | 지식 그래프 기반 세션 기억 |
| (a) | engineering | 공식 | anthropics/knowledge-work-plugins engineering | 스탠드업·코드 리뷰·아키텍처·인시던트 등 엔지니어링 업무 스킬(ADR 전용 스킬은 안 보임) |
| (a) | plugin-management | 공식 | anthropics/knowledge-work-plugins cowork-plugin-management | 조직용 플러그인 생성·관리(Cowork) |
| (a) | productivity | 공식 | anthropics/knowledge-work-plugins productivity | 작업·일정 관리와 업무 맥락 기억 |
| (b) | axe-accessibility | 공인 | dequelabs/axe-accessibility  | Deque axe 접근성 검사·수정 |
| (b) | cypress | 공인 | cypress-io/ai-toolkit  | Cypress 테스트 생성·수정 |
| (c) | 1password | 공인 | 1password/1password-claude-plugin  | 비밀을 .env 대신 1Password에서 마운트 |
| (c) | arcjet | 공인 | arcjet/arcjet-plugin  | 런타임 보안(프롬프트 인젝션·봇·레이트 리밋) SDK |
| (c) | code-review-anthropics | 공식 | anthropics/claude-plugins-official plugins/code-review | 공식 code-review의 디렉터리 사본 |
| (c) | gen-sage | 공인 | gendigitalinc/sage  | 에이전트 탐지·대응(ADR) 안전 장치 |
| (c) | opsera-devsecops | 공인 | opsera-agents/opsera-devsecops  | DevSecOps 분석·스캔 |
| (c) | semgrep-guardian | 공인 | semgrep/mcp-marketplace plugin | 에이전트 생성 코드 Semgrep 스캔 |

(d) 220개: knowledge-work 업무(디자인·마케팅·영업·재무·법무·HR 등), financial-services, claude-for-legal, life-sciences 커넥터, SaaS 연동(Atlassian, Apify, monday, Tableau, Glean 등), 공식 마켓 항목의 별칭 사본(kotlin-lsp, swift-lsp, document-skills 등).

### 1.4 디렉터리 미검토 3,194개 (서드파티, 읽기만)

전부 서드파티라서 실행하지 않는다. 이름과 요약에 키워드를 걸어 1차 분류했다(카탈로그). 한 항목이 여러 묶음에 걸릴 수 있다.

| 묶음(키워드) | 적중 수 |
|---|---|
| (a) 하네스·CLAUDE.md·설정 감사 | 84 |
| (a) 세션 기억·인계 | 155 |
| (a) 다른 모델 위임(Codex·Gemini 등) | 45 |
| (a) 토론·적대 리뷰·위원회 | 51 |
| (a) 결정 기록(ADR) | 13 |
| (a) Roblox·Luau | 1 |
| (b) 웹 프론트(React·Astro·Next·접근성 등) | 101 |
| (c) 보안 | 149 |
| (c) 리뷰·단순화·린트 | 77 |
| 어느 묶음에도 안 걸림 → (d) | 2599 |
| 계 | 3194 |

이 가운데 우리 방향과 닮은 것은 §4에서 저장소 README를 읽어 비교했다(fetch).
나머지는 키워드 분류만 했다. 키워드에 안 걸린 항목은 전부 (d)로 셌다. 이 수는 정밀하지 않다.

## 2. 정밀 판정 — 특히 볼 다섯 축

### 2.1 보안 하드닝: security-guidance (공식, 열람 + 정적. 실행은 거부됨 §6)

**실제 동작** (`hooks/hooks.json`, `security_reminder_hook.py`, `patterns.py`, `README.md` 열람, v2.0.19, Apache-2.0)

| 이벤트 | 하는 일 | 비용·부작용 |
|---|---|---|
| SessionStart (timeout 180s) | `ensure_agent_sdk.py`: `claude-agent-sdk`를 시스템에서 찾고, 없으면 `<상태 디렉터리>/agent-sdk-venv`에 venv를 만들어 **PyPI에서 pip install** | 첫 세션 네트워크. 상태 디렉터리 기본은 `~/.claude/security/`이고 `SECURITY_WARNINGS_STATE_DIR`로 옮긴다 |
| UserPromptSubmit | 기준점 스냅샷: 임시 인덱스(`GIT_INDEX_FILE` 사본)로 `write-tree` + `commit-tree`를 만들어 SHA를 저장 | 프롬프트마다 저장소 `.git/objects`에 참조 없는 커밋이 하나씩 쌓인다(gc 대상). 사용자 인덱스는 건드리지 않는다 |
| PostToolUse `Edit\|Write\|MultiEdit\|NotebookEdit` | **층 1**: 정규식 25개. 걸리면 `additionalContext`로 경고를 주입 | 걸릴 때만 컨텍스트가 늘어난다. LLM 호출은 없다 |
| PostToolUse `Bash` 중 `git*commit*`·`git*push*`·`gt *` (asyncRewake) | **층 3**: Agent SDK로 내부 Claude Code를 띄워 Read·Grep·Glob으로 데이터 흐름을 추적하는 커밋 리뷰. 모델은 `opus` 별칭 | 커밋마다 Opus 여러 번 호출. 우리 sandbox는 에이전트가 자주 커밋한다(`HARNESS_AGENT_PUSH=normal`) |
| Stop (asyncRewake) | **층 2**: 기준점 이후 diff를 최신 Opus에 한 번 보내 리뷰. 높은 심각도만 되먹인다 | 턴마다 호출. README 예시는 `in=31994 out=3250 est_cost_usd=0.1930`이다. 구독이면 사용량 한도에서 빠진다 |

- **네트워크**: `api.anthropic.com`(`GET /v1/models`로 최신 Opus를 고르고 하루 캐시, 리뷰 본문 전송), PyPI.
- **보내는 데이터**: 바뀐 경로, diff 조각, 관련 파일 내용, `claude-security-guidance.md` 내용.
- **상시 컨텍스트**: 카탈로그 0토큰(훅뿐). 경고나 리뷰 결과가 나올 때만 늘어난다.
- **확장점**
  - `~/.claude/claude-security-guidance.md`(사용자), `<프로젝트>/.claude/claude-security-guidance.md`(커밋), `.local.md`
  - 모두 합쳐 8KB 상한이고 LLM 리뷰 프롬프트에 붙는다. "추가만 가능, 억제 불가"로 감싼다.
  - `security-patterns.{yaml,json}`로 사용자 정규식을 50개까지 더한다. ReDoS 검사가 있다.
- **켜고 끄기**: `ENABLE_STOP_REVIEW=0`, `ENABLE_COMMIT_REVIEW=0`, `ENABLE_PATTERN_RULES=0`, `SECURITY_REVIEW_MODEL`, `SG_AGENTIC_MODEL`.
  README는 "multi-agent / shared-worktree setups"에서 Stop 리뷰를 끄라고 직접 권한다. 다른 에이전트가 턴 사이에 HEAD를 옮기기 때문이다. 우리 환경이 바로 그 경우다.

**층 1 패턴 25개가 웹·Node·Python에 맞는 정도** (`patterns.py` 정적)

| 묶음 | 규칙 | 웹/Node 적합 | 오탐 가능성 |
|---|---|---|---|
| DOM XSS | `innerHTML_xss`, `outerHTML_xss`, `insertAdjacentHTML_xss`, `document_write_xss`, `react_dangerously_set_html` | 높음. JS/TS 확장자(`.js…/.vue/.svelte`)에서만 켜진다. **`.astro`는 목록에 없다** | 낮음~중간. 정적 문자열 대입도 걸린다(코드 주석에 #410 수정 이력) |
| 코드 주입 | `eval_injection`(문서 확장자 제외 전부), `new_function_injection`, `child_process_exec`(`exec(`, `execSync(`) | 높음 | `exec(` 정규식이 JS 안의 `RegExp.prototype.exec(`는 `.`이 앞에 있어 피한다. `eval(`은 `.luau`·`.go`에도 걸리지만 우리 코드에는 없다 |
| 공급망 | `script_src_without_sri`(외부 `<script src>`에 integrity 없음), `github_actions_workflow`(경로만 보고 늘 경고) | 중간 | 워크플로 규칙은 파일을 고칠 때마다 긴 경고를 붙인다. 우리는 GitHub Actions를 거의 안 쓴다 |
| TLS·암호 | `tls_verification_disabled`(Python `verify=False`, Node `rejectUnauthorized:false`, Go `InsecureSkipVerify`), `aes_ecb_mode`, `node_createcipher_no_iv` | 높음 | 테스트 코드의 `verify=False`가 걸린다 |
| Python 역직렬화·셸 | `pickle*`, `marshal`, `shelve`, `yaml.load`, `torch.load`, `os.system`, `subprocess(... shell=True)`, `xml_unsafe_parse`(`ET.parse` 등) | 높음 | `xml_unsafe_parse`가 신뢰하는 로컬 XML 파싱에도 걸린다 |
| Go | `go_exec_shell_injection`(`exec.Command("sh"…)`) | vitrine 백엔드에 해당 | 낮음 |

- **빠진 것**
  - SQL 문자열 조합, 경로 순회, 오픈 리다이렉트, SSRF, CORS `*`, 쿠키 플래그, CSP·보안 헤더, 하드코딩된 비밀
  - README는 비밀을 잡는다고 하지만 `patterns.py`에는 비밀 규칙이 없고, 층 2·3의 LLM 리뷰 몫이다.
  - 즉 **층 1은 위험 함수(sink) 경고뿐**이다. "웹에 닿는 도구의 하드닝"(인증, 레이트 리밋, 헤더, 입력 검증 경계, 비밀 관리)은 층 2·3만 다룬다.
- **우리 코드에 대한 정적 오탐 추정**
  - 저장소: claude-doctor, coderag, luau-kb의 `*.py`와 vitrine의 `web/src`, `scripts`, `*.go`
  - 위 정규식의 핵심 부분을 grep했더니 **0건**이었다.
  - 기존 코드에서는 조용하다. 경고는 새로 쓰는 코드에서만 나온다(실측 필요, §7).

**우리 쪽 수단과 비교**

| 수단 | 지시 없이 챙기게 하나 | 비용 | 툴킷 무관·이식성 | 한계 |
|---|---|---|---|---|
| security-guidance 층 1 | 예. 편집 직후 경고 | 편집마다 python 프로세스 1개(지연 미측정) | 플러그인 설치로 이식. Python 3.8+ 필요 | sink뿐. 설계 수준 하드닝은 없다 |
| security-guidance 층 2(Stop) | **예.** 턴이 끝날 때 diff를 독립 리뷰 | 턴마다 Opus 1회(약 0.19 USD 상당) | 같음 | 공유 worktree에서 오작동할 수 있다(README). Luau 저장소에서도 돈다 |
| security-guidance 층 3(commit) | 예 | 커밋마다 Opus 여러 회 | 같음 | 에이전트 커밋이 잦아 비용이 커진다 |
| 내장 `/security-review` | 아니오. 불러야 돈다 | 부를 때만 | 내장 | 이미 `home/.claude/CLAUDE.md` "코드 리뷰" 절에 있다 |
| 우리 `rules/web-security.md`(paths 조건부, 제안) | 예. 해당 파일을 다룰 때 체크리스트가 로드된다 | 로드될 때만 수백 토큰 | 정본 `home/` + MANIFEST로 이식 | 모델이 읽고도 무시할 수 있다(강제 아님) |
| 리마인더 훅(제안, `bash-bypass-reminder.py`와 같은 꼴) | 예. 네트워크 코드(fetch/http/listen) 편집을 감지해 체크리스트 한 줄 | 편집마다 python 1개 | 같음 | 규칙을 직접 유지보수해야 한다 |

**판정: 도입(웹 툴킷 프로젝트 범위) + 참고.**
- **어디에**: vitrine, 블로그, 웹·네트워크 도구 저장소의 `.claude/settings.json`(project 범위). 사용자 레벨은 아니다. 사용자 레벨이면 Luau 저장소에서도 턴마다 Stop 리뷰가 돈다.
- **처음 설정**
  - `env`: `ENABLE_COMMIT_REVIEW=0`. Stop 리뷰가 같은 diff를 이미 본다.
  - 다른 세션과 worktree를 공유하는 저장소에서는 `ENABLE_STOP_REVIEW=0`도 둔다.
  - `SECURITY_WARNINGS_STATE_DIR`는 기본(`~/.claude/security`)을 둘지 정한다.
- **우리 쪽에도 만든다**: `rules/web-security.md`. 하드닝 체크리스트(헤더, CSP, 인증 경계, 입력 검증, SSRF, 비밀, 레이트 리밋)를 `paths: ["**/*.{ts,tsx,js,mjs,astro,go,py}", "server/**"]`로 둔다. 플러그인이 sink만 보는 공백을 메우고, 플러그인이 없는 sandbox에도 이식된다.
- **결합**: `~/.claude/claude-security-guidance.md`를 정본 `home/.claude/`에 두고 MANIFEST에 올리는 안을 낸다. 우리 고유 규칙(에이전트 전용 git 계정, `.env` 위치 등)을 층 2 프롬프트에 넣는 자리다.
- 실측 전에는 비용과 오탐을 확정하지 않는다(§7-1).

**claude-security (공식, 열람)도 함께 본다.** 이것은 전수 스캔 도구다. 패턴 감시가 아니다.
- **구성**: 에이전트 9개(inventory → researcher → verifier → redactor → patch-generator/verifier)와 `workflows/scan.js`.
- **산출물**: 저장소 안 `CLAUDE-SECURITY-<시각>/`에 MD·JSONL·SARIF를 쓴다. 자체 `.gitignore`를 둔다.
- **훅**: 배너, 사용 지표, 60초 무응답 질문 닫기, `git push`·`gh pr create` 뒤 스캔 권유뿐이다. 감시 훅은 없다.
- **상시 비용**: 781토큰(카탈로그). 에이전트 description이 커서다.
- **판정**: 도입(웹 툴킷 프로젝트, 릴리스 전 수동 `/claude-security`) + 참고(§2.6).
- 상시 781토큰이 아까우면 project 범위로만 켠다.

### 2.2 문서·지식: context7 (공인, 열람 + fetch. 실행은 거부됨)

- **동작**: 원격 MCP 하나(`https://mcp.context7.com/mcp?client=claude-code-plugin`, http)뿐이다.
  - 도구는 둘이다: `resolve-library-id`, `query-docs`.
  - 익명으로 접속해 공용 레이트 리밋을 쓴다. `CONTEXT7_API_KEY`가 있으면 자기 할당량을 쓴다.
  - 스킬·훅이 없다. 카탈로그 상시는 0이다. MCP 도구 스키마는 도구 검색으로 지연 로드되므로 실제 상시 비용은 실측해야 한다(거부됨).
- **네트워크·개인정보**: 질문 문장과 라이브러리 이름이 Upstash로 간다.
- **라이선스**: 플러그인 디렉터리 `external_plugins/context7/`에는 LICENSE가 없다. 저장소 루트는 Apache-2.0이다(열람). 서버는 Upstash의 호스팅 서비스다.
- **Luau·Roblox 범위** (fetch, `https://context7.com/api/v1/search?query=luau`)
  - 다음이 색인돼 있다: `/luau-lang/luau`, `/luau-lang/site`, `/johnnymorganz/luau-lsp`(2026-10-20), `/roblox/creator-docs`(약 2.0M 토큰, 2026-11-10 갱신), `/luau-lang/lute`, `/lune-org/docs`, `/roblox/react-luau`, `/kampfkarren/kampfkarren-luau-guidelines`
  - 다만 **문서에 없는 최전선 지식**(타입 한계, `const`, 솔버 버그, FFlag 한도)은 없다. 이것은 luau-kb·coderag pack의 몫이다.
- **coderag 계층(`coderag/.claude/base/layers-and-packs.md` §13)과의 관계**

  | | coderag project / pack / global | context7 |
  |---|---|---|
  | 원천 | 우리 저장소 기록, 우리가 검증한 pack(luau-kb), 하네스 결정 | 외부 라이브러리 공식 문서·예제(업스트림 저장소에서 자동 수집) |
  | 검증 | 스니펫 검증, `status`·`applies_to`·`review_after`(§17–18) | 없음(수집 시점 그대로) |
  | 네트워크 | 조회 때 없음(§13.3 "조회 명령은 네트워크를 쓰지 않는다") | 매번 원격 |
  | 버전 | `applies_to`로 필터 | 라이브러리 ID에 버전(`/vercel/next.js/v15.1.8`) |

  **겹치지 않고 보완한다.** 순서는 "project → pack(luau-kb) → (없으면) context7 / Roblox `llms.txt`"가 맞다.
  coderag의 doc-locator(§20.1)가 pack에서 못 찾았을 때만 외부 문서로 넘어가라고 스킬 한 줄로 안내하면 된다.
  pack에 외부 문서를 복사하는 것은 버전 낡음 관리 부담만 늘린다.
- **판정**
  - **웹 툴킷: 도입 후보.** React·Vite·Astro 버전별 API 확인에 쓴다. project 범위로 켠다.
  - **Luau: 참고.** Roblox API는 `.claude/audit/02`의 `llms.txt` + `.md` 규칙과 기능이 겹친다. creator-docs 색인이 오늘 갱신된 것은 장점이다.
  - 상시 비용, 응답 크기, 익명 레이트 리밋은 실측 뒤 확정한다(§7-3).

### 2.3 품질: code-simplifier, code-review, pr-review-toolkit (공식, 열람 + 일부 실측)

| 플러그인 | 실제 내용 | 내장과의 관계 | 판정 |
|---|---|---|---|
| code-simplifier | 에이전트 1개. `model: opus` 고정. 본문에 "ES modules, `function` 키워드 선호, 명시적 반환 타입, React Props 타입" 같은 **JS/React 전제 규칙이 박혀 있다**. "proactively … without requiring explicit requests" | 내장 `/simplify`(diff 대상 재사용·단순화·효율, 수정 적용)와 목적이 같다. 실측(§6): 상시 **+77토큰**. vitrine 사본에서 "단순화해줘"라고 했을 때 메인이 직접 고쳤고 에이전트는 **불리지 않았다**(1/1) | **중복**(`/simplify`). Luau 저장소에서는 JS 전제 규칙이 오히려 해롭다 |
| code-review (플러그인) | 명령 1개 `/code-review`. PR용 다중 에이전트 + 신뢰도 점수 | 내장 `code-review` 스킬(강도 단계, `--fix`, `--comment`)이 상위 호환이다 | **중복** |
| pr-review-toolkit | 에이전트 6개: code-reviewer(opus), **silent-failure-hunter**, **type-design-analyzer**, comment-analyzer, pr-test-analyzer, code-simplifier + `/review-pr` | 감사 관점 분할이 우리 `.claude/research/drafts/agents`와 닮았다. 상시 **2,038토큰**(description에 예시가 길다) | **참고**: silent-failure(빈 catch, 조용한 폴백) 관점과 type-design(불변식 표현, 캡슐화) 관점을 우리 runtime·type auditor 체크리스트에 넣는다. 설치는 하지 않는다 |
| feature-dev, commit-commands | 3단계 기능 개발, 커밋 명령 | 우리 흐름과 겹친다 | 불필요(유지) |
| ralph-loop | Stop 훅으로 같은 프롬프트를 되먹이는 반복 | 내장 `/loop`와 겹친다 | **중복** |

### 2.4 프론트: frontend-design (공식, 열람 + 실측)

- **내용**: 스킬 1개(9KB). 주요 지시는 다음과 같다.
  - "AI가 만든 듯한 기본값" 다섯 가지를 피한다: 크림 배경 + 테라코타, 형광 액센트, 신문 레이아웃, SaaS 카드 키트, 대문자 eyebrow 라벨.
  - 계획(팔레트 4–6색, 서체, ASCII 와이어프레임) → 브리프 대조 → 구현 → 스크린샷 자기 비평의 2단계로 일한다.
  - 접근성 하한(포커스, reduced motion)을 지킨다.
  - **브리프와 기존 지시가 늘 이긴다.**
- **실측**(§6)
  - 상시 **+75토큰**.
  - vitrine 사본에서 디자인 계획을 묻는 프롬프트 두 개(한국어, 영어)에서 **자동 발동 0/2**였다.
  - 이름을 대면 `Skill(frontend-design:frontend-design)`이 바로 불린다(1/1).
  - 스킬 없이도 Sonnet은 기존 `styles.css` 토큰을 재사용하는 안을 냈다. 기존 디자인 시스템이 있는 앱에서는 이것이 맞다.
- **판정: 도입(웹 툴킷 프로필, 신규 UI·블로그 리디자인).**
  - 자동 발동을 믿지 않는다. 프로젝트 CLAUDE.md에 "새 화면·리디자인은 `/frontend-design:frontend-design`부터" 한 줄을 넣는다.
  - project 범위로 켜거나, 웹 툴킷 프로필의 enabledPlugins에 넣는다.
  - vitrine처럼 디자인 토큰이 이미 있으면 "기존 토큰 우선"이 브리프임을 같이 적는다.
- **같은 축의 다른 후보**

  | 플러그인 | 내용 | 판정 |
  |---|---|---|
  | typescript-lsp(공식) | 상시 0. `typescript-language-server` 바이너리가 없다(`which` 실패) | 도입 후보(웹). 바이너리를 설치한 뒤 실측 |
  | gopls-lsp(공식) | vitrine Go 백엔드용. `gopls` 없음 | 도입 후보(웹). 바이너리를 설치한 뒤 실측 |
  | modern-web-guidance(Google Chrome) | 디렉터리에 없어 서드파티 취급. 상시 751 | 참고. 내용을 web-kb 후보로 |
  | chrome-devtools-mcp(Google) | 디렉터리에 없음. 상시 809 | 참고 |
  | playwright(공인) | `npx @playwright/mcp@latest`로 **버전 고정 없음** | 불필요. 브라우저 검증은 내장 claude-in-chrome·built-in browser와 겹친다 |
  | axe-accessibility(디렉터리 partner) | 접근성 검사 | 참고(웹 툴킷 접근성 체크) |

### 2.5 세션 기억 (목록과 분류만, 다른 에이전트가 조사 중)

| 이름 | 공인 | 구성 | 비고 |
|---|---|---|---|
| remember(Digital-Process-Tools) | **서드파티**(공식 마켓에 있지만 배지 없음) | S1 C1, 훅 SessionStart·UserPromptSubmit·PostToolUse·SessionEnd. 설치 63,089 | 대화를 일별 로그로 압축 |
| claude-md-management `/revise-claude-md`(공식) | 공식 | 세션 학습을 CLAUDE.md에 한 줄씩 제안 | §2.6 |
| knowledge-work `productivity`(디렉터리 anthropic) | 공식 | 작업 맥락 기억(Cowork 위주) | (a) 목록만 |
| cognee-memory(디렉터리 partner) | 공인 | 지식 그래프 기억 | (a) 목록만 |
| 커뮤니티: Cairn Memory, recall, Exit Memory Update, session-handoff, FAF Skills, Chuck 등 155개 키워드 적중(§1.4) | 서드파티 | — | 목록만 |

### 2.6 우리와 유사한 것 — 하네스 진단, 감사, 위임, 토론, 결정 기록

| 우리 것 | 닮은 것 (공인 여부) | 배울 점 → 우리 어디에 |
|---|---|---|
| `home/.claude/skills/harness-doctor` (코어 + 툴킷 진단, 승인 후 수정) | **claude-md-management**(공식) `claude-md-improver`: A–F 등급, "보고서 먼저, 승인 후 수정". 실측 상시 +174 | 등급제는 우리 보고 형식에 맞지 않는다(코드별 판정이 낫다). `/revise-claude-md`의 **세션 끝 학습 포착**은 우리에게 없다. harness-doctor에 "세션 학습 → 어느 층(rules/skill/memory)에 둘지 제안" 단계를 더하는 안. 다만 이 도구는 CLAUDE.md에 **쌓는** 쪽이라 우리 방향(빼서 rules·스킬로)과 반대다. 그대로 쓰지 않는다 |
| 같음 | **claude-code-setup**(공식) `claude-automation-recommender`: 읽기 전용, 유형별 1–2개 추천, 웹 검색 | `references/{hooks-patterns,mcp-servers,plugins-reference}.md`를 harness-doctor `toolkits/web.md`의 "이후 채울 검사 후보" 원천으로 쓴다 |
| 같음 | **plugin-dev**(공식) plugin-validator·skill-reviewer 에이전트. 상시 **2,354토큰** | 상시로 켜지 않는다. luau-kb 플러그인 작업 때 `--plugin-dir`로 일시 사용. validator 체크리스트를 harness-doctor `skills.md`에 대조 |
| 같음 | neko-harness-doctor(서드파티, MIT, fetch): 7범주 25지표(`critical-rules-not-in-first-third`, `volatile-elements-not-at-tail`, `hook-missing-error-handling`), LLM 없는 결정적 스크립트, `--fix-mode propose` | 우리 scan.py와 같은 설계다(결정적 검사 + 모델 판정). **"중요 규칙이 앞 1/3에 있나", "자주 바뀌는 내용이 끝에 있나(프롬프트 캐시)"** 두 지표를 LOAD 계열 후보로 |
| 같음 | Harness Scope(서드파티, MIT): **훅 모듈로 저장소별 프로필에 따라 스킬·에이전트·지침·도구 목록을 요청 전에 걸러 낸다**. 파일 쓰기 없음 | 우리 "툴킷 자리" 문제(Luau 저장소에서 웹 스킬 숨기기)를 symlink 없이 푼다. 같은 방식이 공식 API로 가능한지 확인할 가치가 있다(mod/hook 모듈, CC ≥ 2.1.287) |
| 같음 | Instruction Eval / abdiff(서드파티, MIT): 지침 변경 전후 **A/B 반복 실행**, 임시 사본, 사용자 설정 제외 | PLAN.md 검증 루프의 "스킬마다 평가 시나리오 3개"를 자동화하는 틀. §6의 우리 실측 방식과 같다 |
| 같음 | ecoctx, rent-check, please-optimize-my-claude, Setup Audit, Hook Doctor, skillrot(서드파티) | skillrot의 "스킬이 부르는 CLI 플래그가 설치 버전과 맞나"는 luau 툴킷 핀 검사와 닮았다. 참고만 |
| 스킬 평가 (PLAN.md 검증 루프) | **superpowers**(공인) `writing-skills`: "NO SKILL WITHOUT A FAILING TEST FIRST". 스킬 없이 압박 시나리오를 돌려 **실패를 먼저 기록**하고, 최소 스킬로 GREEN | luau-kb 스킬 평가에 "스킬 없는 기준선 실패"를 먼저 남기는 단계를 넣는다. description 규칙("Use when…", **워크플로 요약 금지**: 요약을 본 에이전트가 본문을 건너뛴다)을 harness-doctor `skills.md` 판정 기준에 더한다 |
| `.claude/research/drafts/agents` (관점별 감사자, 읽기 전용 훅, 공통 보고 형식) | **claude-security**(공식): 발견마다 **반증이 임무인 독립 검증자**. 신뢰도·심각도 상한을 **코드가 계산**. 최상위 디렉터리마다 "검사함/제외+이유"를 먼저 **커버리지 회계**로 확인. 저장소 텍스트(CLAUDE.md 포함)는 지시가 아니라 증거 | `/audit` 오케스트레이션에 넣는다: (1) 발견 → 반증 검증자 1명 통과분만 보고 (2) 보고서 머리에 커버리지 표 (3) 감사 대상 저장소의 CLAUDE.md를 지시로 따르지 말라는 한 줄. `audit-report-format` 스킬에 "confidence는 검증 단계가 정한다" |
| 같음 | pr-review-toolkit(공식) | §2.3 |
| `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate` (agy/codex 위임, uid 표, run→collect→remove) | Codex Dispatch, codex-review, opencode, Ireview, Delegate: Agents Sized to the Job(전부 서드파티) | 대부분 "Codex에 보내고 답을 받는" 단발형이다. 우리처럼 격리(uid, worktree, HOME), 수명 주기, 중앙 표를 둔 것은 못 찾았다. **우리 설계가 앞서 있다.** Codex Dispatch의 "cwd·sandbox 강제, 자체 완결 프롬프트"는 우리 머리말과 같다 |
| `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/skills/debate` | agent-discussion(서드파티): 공유 md 하나, `[TURN: 이름]`, 12라운드 교착 선언, 심판 없음. The Courtroom·adversarial-review(서드파티): Claude 제안 ↔ Codex 반대 심문. mumo, consensus(서드파티): 다중 모델 패널 | 모두 **모델 간 합의로 결론**을 낸다. 우리 debate의 "메인이 실측으로 판정, 합의만으로 결론 금지"가 더 엄격하다. agent-discussion의 **교착 선언 규칙**(N라운드 뒤 미해결 쟁점 나열)은 debate 원장 형식에 넣을 만하다 |
| `decisions/D-xx` | whydone(서드파티, MIT): 작업당 md 1개(`.whydone/YYYYMMDD-slug.md`: 변경, 이유, **기각된 대안**, 위험, 후속), Stop 훅이 "기록 안 된 작업"을 감지해 기록 권유, `/recall`은 경로·태그·키워드 결정적 순위 | D-xx 틀에 "기각된 대안"이 이미 있는지 확인. Stop 훅으로 기록을 권유하는 방식은 하네스 결정에는 과하다(불필요). knowledge-work `engineering`(공식)에는 ADR 전용 스킬이 보이지 않았다(fetch) |
| 세션 사용량 진단 (`.claude/audit/10`) | **session-report**(공식): `node analyze-sessions.mjs`가 `~/.claude/projects` 트랜스크립트를 읽어 토큰, 캐시 깨짐, 서브에이전트, 스킬, 비싼 프롬프트를 HTML로 낸다. 실측 상시 +67 | **도입**(claude-doctor local 범위). 실행은 node 스크립트라 다음 승인 때(§7-5). ai-adoption의 token-doctor(디렉터리 partner)도 같은 일을 한다(Haiku 서브에이전트 분석) |

## 3. (a)(b)(c) 판정 요약과 비용 근거

### 3.0 컨텍스트 비용을 읽는 법

- 카탈로그 "상시"는 skill·agent·command description이다.
- 다음은 따로 든다.
  - **SessionStart 주입**: explanatory/learning-output-style은 고정 문단을 주입하고, superpowers는 `using-superpowers`를 주입한다.
  - **MCP 도구 스키마**: 지연 로드면 이름만 든다.
  - **훅이 걸릴 때의 `additionalContext`**
- 공식 문서는 설치 후 `claude plugin details <이름>`의 `Always-on` 줄을 정답으로 친다.
- 우리 실측은 같은 프롬프트("Reply with exactly: OK")로 기준선과 비교한 총 입력 토큰 차이다(§6).

### 3.1 판정표

| 판정 | 플러그인 | 어디에 / 무엇을 |
|---|---|---|
| **도입** | security-guidance | 웹 툴킷 프로젝트 `.claude/settings.json`(project). `ENABLE_COMMIT_REVIEW=0`부터 시작 |
| **도입** | frontend-design | 웹 툴킷 프로필(블로그, vitrine). 명시 호출 한 줄을 프로젝트 CLAUDE.md에 |
| **도입** | context7 | 웹 툴킷 프로필. 실측 후 확정 |
| **도입** | claude-security | 웹 툴킷 프로젝트, 릴리스 전 수동 |
| **도입** | session-report | claude-doctor local 범위. 하네스 사용량 진단 |
| **도입 후보** | typescript-lsp, gopls-lsp | 웹 툴킷. LSP 바이너리 설치가 먼저 |
| **도입 후보** | rust-analyzer-lsp | coderag(Rust 툴킷) project 범위. mise shim에 `rust-analyzer`가 있다 |
| **참고** | claude-code-setup, claude-md-management, plugin-dev, superpowers(writing-skills), pr-review-toolkit, claude-security(검증 설계), modern-web-guidance, chrome-devtools-mcp, axe-accessibility | §2.6 표의 "→ 우리 어디에" |
| **중복** | code-simplifier(`/simplify`), code-review(내장 `/code-review`), skill-creator(세션 내장 `anthropic-skills:skill-creator`), ralph-loop(`/loop`), coderabbit·greptile·qodo(내장 리뷰 + debate), lumen·serena·sourcegraph(coderag), hookify(우리가 훅을 직접 쓴다) | — |
| **불필요** | remember 외 기억 계열(다른 에이전트 판단 대기), mattpocock-skills(상시 1,654, 서드파티), playwright(@latest 미고정), lua-lsp(`.lua` 전용), langfuse-observability·dash0(외부 SaaS 텔레메트리), semgrep·sonarqube·aikido·sonatype·endor·42crunch·nightvision·stackhawk(SaaS 계정, 지금은 security-guidance + rules로 충분), vercel·cloudflare·netlify(호스팅을 정하기 전, vercel은 상시 4,222 + 훅), feature-dev, commit-commands, code-modernization(상시 1,377 + 훅 5종), github·gitlab(우리 원격은 자체 git 서버) | — |

## 4. 디렉터리·커뮤니티에서 따로 본 것 (서드파티, 읽기만)

| 이름 | 저장소 | 분류 | 본 것 | 메모 |
|---|---|---|---|---|
| neko-harness-doctor | aliksir/neko-harness-doctor | (a) | README(fetch) | §2.6 |
| Harness Scope | shimo4228/harness-scope | (a) | README(fetch) | §2.6 |
| Instruction Eval | 2ykwang/abdiff | (a) | README(fetch) | §2.6 |
| ecoctx | uchimata2/ecoctx | (a) | README(fetch) | 바이트로 상시 로드를 잰다. 토큰 환산은 없다 |
| agent-discussion | cyrusxyl/agent-discussion | (a) | README(fetch) | §2.6. 라이선스 종류 미기재 |
| whydone | chevgan/whydone | (a) | README(fetch) | §2.6 |
| roblox-dev | ivar-anon/roblox-dev | (a) Luau | README(fetch) | 스킬 7, 명령 3, 에이전트 1. setup이 **Wally·Selene**으로 스캐폴드한다. new solver와 `const`는 언급 없다. 우리(mise·pesde, selene 폐기)와 맞지 않는다. 불필요 |
| superpowers | obra/superpowers | (a) | writing-skills, hooks.json(fetch) | 공인. SessionStart(startup·clear·compact) 동기 훅으로 스킬 사용 지침을 주입. 의견이 강한 워크플로가 우리 규약과 부딪쳐 참고만 |
| ai-adoption(token-doctor) | techwolf-ai/ai-first-toolkit | (a) | 페이지(fetch) | 공인(partner). session-report와 같은 축 |
| Skill Discovery, Clawness, Chuck, meta-dev, claude-perfectionist, Setup Doctor, Claude Code Essentials Auditor, bake-claude-md-files | 각자 | (a) | 요약만(카탈로그) | 하네스 감사·규칙 주입 계열. 깊이 보지 않았다 |
| securitymaxxing, Verified Security Sweep, gen-sage, arcjet, 1password | 각자 | (c) | 요약만 | 1password(partner): `.env` 대신 비밀을 1Password에서 마운트. 우리 `.env` 정책 논의(MEMORY `git-workflow-sandbox`)와 닿는다. 참고 |
| fe-rail | sh5623/fe-rail | (b) | 요약만 | Next.js·Vite·Tailwind·shadcn 전용 하네스. 웹 툴킷 프로필 비교 대상 |

## 5. 이전 .claude/audit/02 판정 재검토

| 항목 | .claude/audit/02 | 이번 | 바뀐 이유 |
|---|---|---|---|
| security-guidance | 불필요("Luau 위주, 편집마다 비용") | **도입(웹 툴킷 project 범위) + 참고** | 웹이 대상에 들어왔다. 사용자가 하드닝을 매번 지시했다. 플러그인이 v2에서 층 3개(패턴, Stop LLM 리뷰, 커밋 리뷰)로 커졌다. Luau 저장소에는 켜지 않는다 |
| code-simplifier | 불필요(`simplify`와 중복) | **중복(유지)** + 근거 보강 | 실측 상시 +77, 자동 미발동. 본문이 JS/React 전제이고 `model: opus`로 고정돼 있다 |
| code-review(플러그인) | 불필요 | **중복(유지)** | 내장 스킬이 상위 호환 |
| claude-md-management | 검토 | **중복 + 참고** | harness-doctor가 생겼다. 쌓는 방향이 우리와 반대다. `/revise-claude-md`만 참고 |
| claude-code-setup | 검토 | **참고** | harness-doctor 웹 툴킷 후보의 원천 |
| plugin-dev | 검토(스킬 3개 이상이면) | **참고, 일시 사용** | luau-kb가 플러그인이 됐다. 상시 2,354토큰이라 늘 켜 두지 않는다 |
| hookify | 검토 | **중복** | 우리 훅을 직접 쓴다. 모든 도구 호출에 matcher 없는 python 훅 2개(Pre/Post)가 붙는다 |
| session-report | 즉시(진단 1회) | **도입(claude-doctor local)** | 같은 결론. 실측 상시 +67로 확인 |
| skill-creator | 즉시 | **중복(이미 내장)** | 세션에 `anthropic-skills:skill-creator`가 있다. 플러그인 설치는 불필요 |
| feature-dev, commit-commands, mcp-server-dev | 불필요 | 불필요(유지) | — |
| lua-lsp | 불필요 | 불필요(유지) | `.lua` 전용. luau-lsp 자체 LSP 플러그인이 맞다 |
| serena | 검토 불가 | **중복**(coderag) | `uvx --from git+…serena`로 **버전 고정이 없다**. `uvx`도 없다 |
| frontend-design, context7, claude-security, typescript-lsp, gopls-lsp | (보지 않음) | 도입 / 도입 후보 | 웹 툴킷 |
| document-skills | 불필요 | 불필요(유지) | 세션 내장으로 이미 있다 |

## 6. 이번에 한 실행 실측 (공인 확인분만)

사용자 범위 확장 지시(공인으로 확인된 것만 실측)에 따랐다.
- **방법**: `claude -p --model sonnet --output-format json|stream-json --plugin-dir /tmp/mkt16/plugins/<사본>`
- **작업 위치**: 임시 프로젝트 `/tmp/mkt16/empty`(git init)와 vitrine 사본 `/tmp/mkt16/vitrine`(`node_modules`, `.git`, `data` 제외 tar 복사, 새 git)
- `~/.claude`에는 설치하지 않았다. 사용자 레벨 설정·훅·CLAUDE.md는 기준선과 시험군에 똑같이 적용된다.

| 플러그인 (공인 근거) | 무엇을 | 결과 |
|---|---|---|
| 기준선 | 총 입력 토큰(입력 + 캐시 생성 + 캐시 읽기) | **23,595**(2회 같음) |
| frontend-design (anthropic 검토, `plugins/frontend-design`) | 상시 | **23,670 (+75)** |
| 같음 | 자동 발동: vitrine 사본, 한국어 "About 페이지 시각 디자인 방향 5줄" / 영어 "Build a new landing page UI… design plan" | **0/2** (도구 호출에 Skill 없음). 명시 호출 1/1 |
| code-simplifier (anthropic 검토) | 상시 | **23,672 (+77)** |
| 같음 | `sizeLabel`(중첩 삼항, 쓸모없는 null 검사) 단순화 요청 | 에이전트 **미발동**. 메인이 직접 Edit(이른 반환 + 상수). 결과는 동작을 보존했다 |
| claude-md-management (anthropic 검토) | 상시 | **23,769 (+174)** |
| session-report (anthropic 검토) | 상시 | **23,662 (+67)** |

카탈로그 추정(opus-4-7: 83 / 69 / 180 / 75)과 sonnet 실측이 ±10토큰 안에서 맞는다. **카탈로그 "상시" 값은 description 비용 추정으로 믿을 만하다.**

**auto 모드 분류기에 거부된 실행** (우회하지 않았다)

| 시도 | 거부 사유(분류기 원문) | 영향 |
|---|---|---|
| 6개 일괄 실행: frontend-design, code-simplifier, claude-md-management, session-report, context7, security-guidance. security-guidance 상태 디렉터리는 `/tmp`로 돌렸다 | `[Code from External]` | 이후 실행 코드가 없는 4개만 따로 재시도해 통과 |
| context7 단독(원격 MCP 접속) | `[Code from External]` | 상시 비용, MCP 응답 크기, Luau 검색 품질 미측정. Luau 색인 여부는 공개 검색 API를 fetch로 대신 확인했다(§2.2) |
| security-guidance | 위 일괄 실행에 포함돼 거부됐다. 단독으로 다시 시도하지 않았다 | 훅 지연, 오탐, Stop 리뷰 비용 미측정 |

판단: 분류기는 **실행 코드나 원격 연결을 가진 플러그인**(훅 스크립트, pip 설치, 원격 MCP)을 막았다. **마크다운만 있는 플러그인**(skill·agent·command)은 통과시켰다.
공인 여부와 관계없이 이렇게 갈렸다. 사용자가 해당 Bash 실행 규칙을 허용해야 §7-1·§7-3을 할 수 있다.

**부수 발견**: 우리 `heavy-proc-guard.py`의 오탐.
- 이 조사에서 python heredoc 안의 **데이터 문자열** `claude-perfectionist`가 키워드 `perf`에 걸렸다(`(?<![A-Za-z])perf`).
- 실행기(`python3`)가 같은 명령에 있으면 막힌다.
- heredoc·인자 문자열 안의 단어까지 보는 것은 오탐을 부른다. `home/.claude/hooks/heavy-proc-guard.py` 개선 후보로 넘긴다(이 문서에서는 고치지 않는다).

## 7. 실행이 필요한 실측 (사용자 승인 후)

도입 후보 상위 5개다. 공통 조건은 다음과 같다.
- `/tmp` 사본에서 하고, `claude -p --model sonnet --plugin-dir`를 쓴다.
- `--debug-file`로 훅 시각을 남긴다.
- `~/.claude`에는 쓰지 않는다. security-guidance는 `SECURITY_WARNINGS_STATE_DIR`와 `SECURITY_GUIDANCE_DEBUG_LOG`를 `/tmp`로 돌린다.

| # | 대상 | 무엇을 | 어떻게 | 판정 기준 |
|---|---|---|---|---|
| 1 | security-guidance | (가) SessionStart: venv·pip 시간, 네트워크 실패 시 동작<br>(나) 층 1: 편집당 훅 지연<br>(다) 층 1 오탐: vitrine 사본과 Luau 저장소 사본에 "평범한 기능 추가" 과제 5개씩<br>(라) 층 1 적중: 일부러 넣은 sink(innerHTML, `exec(`, `verify=False`, 외부 `<script src>`) 5개<br>(마) 층 2(Stop): 턴당 지연, 비용, 발견<br>(바) UserPromptSubmit 스냅샷: 큰 저장소(quad 사본)에서의 지연 | (가) `--debug-file` 시각, `<state>/log.txt`<br>(나) PostToolUse 시작~끝<br>(다)(라) 경고 수, 맞는 경고 수 세기<br>(마) 로그의 `Review usage:` 줄(`in/out/est_cost_usd`). vitrine 사본에 일부러 SSRF·하드코딩 키를 넣은 diff 3개, 깨끗한 diff 3개<br>(바) 시각 측정 | 편집당 지연 < 300ms. Luau 사본 오탐 0. 웹 오탐률 < 20%. Stop 리뷰가 심은 결함 3개 중 2개 이상을 잡는다. 턴당 비용을 사용자에게 보고하고 켤지 정한다 |
| 2 | frontend-design | 자동 발동률, 결과 차이 | 신규 UI 프롬프트 10개(한국어 5, 영어 5)로 발동률. 같은 브리프 3개를 스킬 있음·없음으로 만들어 스크린샷 비교(내장 브라우저). vitrine(기존 토큰)과 빈 Vite 앱(신규)을 나눈다 | 발동률이 낮으면(< 50%) 명시 호출 규칙만으로 운용. 기존 토큰을 깨는 안이 나오면 "기존 디자인 우선" 문구를 프로젝트 CLAUDE.md에 |
| 3 | context7 | 상시 비용(MCP 도구 스키마 지연 여부), 질의당 응답 토큰, 정확도, 익명 레이트 리밋 | 기준선 대비 총 입력 토큰. 질문 10개(React 19, Vite 6, Astro 5 API 5개 / Roblox API·luau-lsp 설정 5개)를 context7 있음·없음으로 답하게 하고 공식 문서와 대조 | 웹 질문 정확도가 오르고 응답 < 5k 토큰이면 웹 프로필에 도입. Luau 질문에서 luau-kb·`llms.txt`보다 낫지 않으면 Luau에는 넣지 않는다 |
| 4 | claude-security | 스캔 시간·토큰, 발견의 참·거짓 | vitrine 사본에 `/claude-security scan … at low`, 그다음 medium. 일부러 넣은 결함 3개 포함 | 심은 결함 회수율, 오탐 0~1개. 릴리스 전 수동 도구로 쓸 비용인지 판단 |
| 5 | typescript-lsp / gopls-lsp (+ session-report 실행) | LSP: 편집 후 진단 주입량, 지연, 메모리. session-report: 실행 시간과 산출 HTML이 `.claude/audit/10`과 맞는지 | LSP 바이너리를 `/tmp` 접두로 설치(`npm i --prefix /tmp/…`, `GOBIN=/tmp/…`)한 뒤 vitrine 사본에서 타입 오류 1개를 넣고 고치는 과제. `choom`으로 감싼다. session-report는 `node analyze-sessions.mjs --json --since 7d`를 한 번 돌린다 | LSP가 오류를 같은 턴에 잡고 메모리 < 1GB면 웹 프로필에 도입. session-report 수치가 `.claude/audit/10`과 크게 어긋나지 않으면 claude-doctor에서 정기 사용 |

## 8. 도입 제안 (정본 `home/.claude/settings.json`에는 쓰지 않는다)

**사용자 레벨 `enabledPlugins`**: 지금은 **더하지 않는다.** 이유는 다음과 같다.
- 후보가 모두 웹 툴킷용이거나 수동 실행용이다. 사용자 레벨에 두면 Luau 저장소에서도 상시 비용이나 Stop 리뷰가 붙는다.
- 다른 sandbox로 옮기기도 project 범위가 쉽다. `.claude/settings.json`과 함께 커밋되기 때문이다.

**대신 사용자 레벨 정본에 둘 것(제안)**
1. `home/.claude/rules/web-security.md` (paths 조건부): 하드닝 체크리스트. security-guidance가 없는 sandbox에서도 동작한다.
2. `home/.claude/claude-security-guidance.md`: security-guidance 층 2 프롬프트에 붙일 우리 고유 규칙. MANIFEST에 추가한다.
3. `home/.claude/CLAUDE.md` "코드 리뷰" 절에 한 줄: "웹·네트워크에 닿는 코드는 커밋 전 `/security-review`. 웹 툴킷 저장소는 security-guidance가 켜져 있다."

**웹 툴킷 프로필 (`.claude/settings.json`, project 범위) 초안**

```json
{
  "enabledPlugins": {
    "security-guidance@claude-plugins-official": true,
    "frontend-design@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "claude-security@claude-plugins-official": true
  },
  "env": {
    "ENABLE_COMMIT_REVIEW": "0"
  }
}
```

- typescript-lsp와 gopls-lsp는 §7-5 실측 뒤에 더한다.
- context7은 §7-3 뒤에 확정한다.
- 공유 worktree에서 여러 세션이 도는 저장소는 `"ENABLE_STOP_REVIEW": "0"`을 더한다.
- harness-doctor `toolkits/web.md`에 `WEB-PLUGINS` 검사를 더하는 안: 웹 툴킷 저장소에 이 프로필이 켜져 있는지 본다.

**claude-doctor 저장소 (local 범위)**: `session-report@claude-plugins-official`.

**Rust 툴킷(coderag, project 범위) 후보**: `rust-analyzer-lsp@claude-plugins-official`. 바이너리는 mise shim에 있다. 실측은 하지 않았다.

## 한계

- 디렉터리 3,194개 미검토 항목은 이름과 요약 키워드로만 분류했다. 본문을 본 것은 §4의 10여 개다.
- 실행 실측은 마크다운 전용 플러그인 4개만 했다. security-guidance와 context7은 분류기 거부로 정적 분석뿐이다.
- 설치 수는 카탈로그(2026-10-16)와 웹 페이지(2026-11-10) 값이 다르다. 표는 카탈로그 값이다.
- context7의 Luau 범위는 공개 검색 API 결과다. 실제 `query-docs` 응답 품질은 보지 않았다.
- remember 등 세션 기억 계열은 목록과 분류만 했다(다른 에이전트 담당).
