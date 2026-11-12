---
title: 외부 조사 3/4 — 에이전트용 지식 검색·세션 기억 도구의 지형과 coderag·session-log·luau-kb 의 위치
description: Context7·Serena·aider·Sourcegraph·DeepWiki·llms.txt·docs MCP, claude-mem·Copilot Memory·Cursor·Cline·mem0·Letta·Claude Code auto memory, doctest 류, 버전 메타를 조사하고 우리 셋과 대조해 재발명 위험·차별점·채택할 표준·드러난 약점으로 판정한다. coderag 의 MCP 노출 근거 포함
keywords: [외부 조사, Context7, Serena, aider repo-map, llms.txt, MCP, claude-mem, Copilot Memory, auto memory, Agent Skills, AGENTS.md, twoslash, xfail strict, applies_to, 재발명]
kind: research
status: active
last_verified: 2026-11-10
---
# 외부 조사 3/4 — 에이전트용 지식 검색·세션 기억 도구의 지형

- 조사일: 2026-11-10. WebSearch/WebFetch 만 썼다. 외부 코드는 받지도 실행하지도 않았다.
- 로컬은 읽기만 했다. 대상: `coderag`(README, `tech-design.md` §0·§11·§13·§16·§18–§20), `claude-doctor/plugins/session-log/README.md`, `.claude/archive/research/drafts/session-log/DESIGN.md`, `luau-kb`(README, AGENTS.md, `snippet-markers.md`, `roblox-docs/SKILL.md`, SKILL.md frontmatter 12개).
- 표기
  - **[1차]**: 공급자 본인의 문서·블로그·저장소를 직접 열어 확인했다.
  - **[2차]**: 검색 요약이나 제3자 글로만 확인했다.
  - **미확인**: 1차 출처를 열지 못했다.
- 이미 조사한 것은 반복하지 않는다. remember 는 `.claude/audit/15` §1, Roblox `llms.txt` 와 Studio MCP 는 `.claude/audit/02` 에 있다.

---

## 0. 요약

| 판정 | 항목 |
|---|---|
| **재발명 위험** | ① session-log 의 뼈대(훅 → 백그라운드 요약 → 로컬 저장 → SessionStart 색인 → 검색·상세)는 **claude-mem** 과 같다. ② `roblox_docs.py` 와 coderag 의 문서 조회는 **docs MCP 류**(Context7, arabold docs-mcp-server, 커뮤니티 Roblox Docs MCP)와 겹친다. ③ coderag 의 코드 표면 프로바이더(TS `.d.ts`, 이후 Luau)는 **Serena(LSP, Luau 지원 명시)** 나 aider repo-map 과 겹친다 |
| **진짜 차별점** | ① 지식 주장마다 **실행 가능한 재현 + 버전 조건 표식 + 다중 버전 행렬**이 있다(`bug-present` 로 상류 수정 감지). 에이전트 지식 도구 가운데 이런 것은 찾지 못했다. ② **주장 단위 `applies_to`**(여러 도구 버전을 AND/OR)를 **프로젝트 핀에서 자동으로 읽고**, 맞지 않으면 숨기지 않고 강등한다. ③ 세션 기록을 **원문 줄과 기계 대조**하고, 저장소 에이전트가 **골라 받아 커밋**한다. 외부에서 가장 가까운 것은 Copilot Memory 의 "인용 + 사용 시점 검증"이다 |
| **채택할 표준** | ① **Agent Skills 사양**(agentskills.io). luau-kb SKILL.md 12개는 이미 맞는다. Codex·Gemini CLI 가 `~/.agents/skills` 에서 바로 읽는다. ② **AGENTS.md + 압축 색인 패턴**(Vercel `agents-md`). coderag §19 T2 와 같은 생각이다. ③ **MCP stdio 얇은 어댑터**. 도구 2–3개, CLI 와 같은 출력. Claude·Codex·Gemini 가 모두 stdio MCP 를 읽는다 |
| **외부에서 드러난 약점** | ① 스킬이 자동 호출되지 않는다. Vercel 평가에서 56% 가 미호출이었다. coderag §19 D19-3 "claude-md 에는 넣지 않음"의 전제가 흔들린다. ② 문서를 통한 지시 주입(Context7 ContextCrush·CVE-2026-75130). git pack → AGENTS.md T1 이 같은 표면이 된다. ③ 기억의 근거가 썩는다. session-log 의 `(L…)` 인용은 트랜스크립트 30일 정리 뒤 확인할 수 없다 |

---

## 1. 외부 지형

### 1.1 코드·문서 검색

| 도구 | 무엇 | 노출 | 우리와 닿는 점 | 출처 |
|---|---|---|---|---|
| **Context7** (Upstash) | 커뮤니티가 등록한 라이브러리 문서를 서버에서 색인한다. 도구는 `resolve-library-id`(이름 → ID)와 `query-docs`(ID + 질의)다. 버전은 프롬프트에 적으면 맞춘다("Next.js 16 …"). 옛 ID 형식은 `/org/project/version` | **MCP 와 "CLI + Skills" 두 모드**(`ctx7 library`, `ctx7 docs`). 서버 소스는 MIT, 백엔드·파서·크롤러는 비공개 | 같은 지식을 CLI·스킬과 MCP 로 이중 노출한 선례(§3). 버전 지정이 질의 문자열 수준이다(우리는 핀 자동 읽기) | [1차] https://github.com/upstash/context7 (2026-11-10 열람) |
| Context7 보안 사고 | **ContextCrush**(Noma Labs). 라이브러리를 등록하고 "Custom Rules" 에 지시를 넣으면 조회 때 에이전트에게 들어간다. Upstash 가 2026-02-23 에 고쳤다는 보도가 있다. **CVE-2026-75130**(2026-08-18 공개)은 "Custom AI Instructions" 를 통한 주입이고, 대상은 ≤2.1.2, 영향은 자격 증명 유출과 파일 삭제다. CVSS 와 수정 여부는 출처마다 다르다 | — | §4 약점 ② | [2차] https://www.pointguardai.com/ai-security-incidents/contextcrush-flaw-turns-ai-documentation-into-malicious-instructions , https://nvd.nist.gov/vuln/detail/CVE-2026-75130 (NVD 원문 **미확인**) |
| **Serena** (Oraios) | LSP 기반 심볼 도구: find symbol, overview, references, declaration, implementation, rename, 본문 교체. 메모리 기능(세션 간 공유)이 있다. 지원 언어 40여 개에 **Lua·Luau 명시**. Claude Code 안에서는 기본 파일·셸 도구를 끈다 | MCP(stdio 또는 HTTP) | coderag 의 "코드 표면" 축과 겹친다. Luau 는 luau-lsp 를 쓸 가능성이 크다(**미확인**) | [1차] https://github.com/oraios/serena (2026-11-10 열람) |
| **aider repo-map** | 파일·핵심 심볼·시그니처의 요약 지도. 의존 그래프로 순위를 매겨 **토큰 예산**(`--map-tokens`, 기본 1k)에 맞춘다. 대화 상태에 따라 늘었다 줄었다 한다. tree-sitter + PageRank 는 [2차] | 내장(요청마다 동봉). 포크·포트가 MCP 로 낸다(RepoMapper 등) | coderag 절 단위 읽기·`~토큰` 표시와 같은 문제의식(예산 안의 지도) | [1차] https://aider.chat/docs/repomap.html (날짜 미표기) / [2차] https://www.agentpatterns.ai/context-engineering/repository-map-pattern/ |
| **Sourcegraph** | Cody Free/Pro/Enterprise Starter 는 2025-07-23 에 끝났다(Amp 로 이동). MCP 서버는 `keyword_search`, `nls_search`, `read_file`(startLine/endLine), `go_to_definition`, `find_references`, Deep Search 를 낸다. 문서는 "experimental" 이라 한다. Enterprise 전용이라는 보도가 있다 | MCP(인스턴스 `/.api/mcp`) | 키워드 검색과 자연어 검색을 나눈 것, 줄 범위로 읽기 | [1차] https://sourcegraph.com/blog/changes-to-cody-free-pro-and-enterprise-starter-plans , [2차] https://7.6.sourcegraph.com/api/mcp.md (가격·Enterprise 전용은 **미확인**) |
| **DeepWiki** (Cognition) | 공개 저장소의 자동 생성 위키. MCP 도구는 `read_wiki_structure`, `read_wiki_contents`, `ask_question`. 공개 저장소는 인증이 없고 비공개 저장소는 Devin 계정이 필요하다 | 원격 MCP(`mcp.deepwiki.com/mcp`) | 구조(목차) → 내용 → 질문의 단계 = 우리 `get --sections` → `--section` | [1차] https://cognition.com/blog/deepwiki-mcp-server (2025-05-22) |
| **docs MCP 류** | arabold **docs-mcp-server**("Grounded Docs"): 웹·GitHub·npm·PyPI·로컬 폴더를 **버전별로** 색인한다(`react@18.2.0`). 임베딩은 선택. **Mintlify**: 문서 사이트마다 `/mcp` 서버, `llms.txt`(10만 자 상한, 넘으면 분할), `llms-full.txt` 를 자동 생성한다. **zilliz claude-context**: AST 청킹, BM25 + 벡터, Merkle 트리 증분 색인, Milvus | MCP | 문서 루트 → 색인 → 검색의 일반형. 버전별 색인은 우리 pack rev 키와 비슷하다 | [2차] https://github.com/arabold/docs-mcp-server , [2차] https://www.mintlify.com/docs/ai/model-context-protocol (2025-03-06 블로그), [2차] https://docsearch.algolia.com/mcp/docs/repo/zilliztech/claude-context |
| Roblox 쪽 커뮤니티 | **Roblox Docs MCP**(nhattamgithub): API 참조, FastFlags, Open Cloud, Luau 문서, DevForum 을 조회한다. rbxdev-ls 는 Luau LSP + MCP 다 | MCP | `roblox_docs.py` 와 직접 겹친다. 품질·유지 상태는 **미확인** | [2차] https://lobehub.com/fr/mcp/nhattamgithub-mcp-roblox-docs |
| **llms.txt** | Jeremy Howard 가 2024-09-03 에 제안했다. H1(필수), 인용 요약, H2 링크 목록, 건너뛰어도 되는 `## Optional`, 페이지마다 `.md` 짝. 채택은 늘었지만 Ahrefs(13.7만 사이트)는 97% 가 AI 요청을 한 번도 받지 않았다고 했다. Google 은 지원 계획이 없다고 했다 | 정적 파일 | 크롤러용으로는 효과가 없다. **에이전트가 직접 가져오는 문서 진입점**으로만 의미가 있다(Roblox·Claude Code 문서가 머리에 "llms.txt 부터" 를 둔다) | [1차] https://llmstxt.org/ , [2차] https://ahrefs.com/blog/llmstxt-study/ (날짜 **미확인**) |
| **Claude Code 자신** | 초기에는 로컬 벡터 DB RAG 를 썼고 agentic search(glob/grep)로 바꿨다는 Boris Cherny 의 발언이 전해진다 | — | coderag "임베딩 없음, 결정적 랭킹" 의 방향과 같다 | [2차] https://smartscope.blog/en/ai-development/practices/rag-debate-agentic-search-code-exploration/ (1차 발언 **미확인**) |

### 1.2 세션 기억

| 도구 | 방식 | 우리와 닿는 점 | 출처 |
|---|---|---|---|
| **claude-mem** (thedotmack) | 훅 9종(SessionStart … PostToolUse … SessionEnd). 두 번째 에이전트(observer, Agent SDK)가 도구 활동을 짧은 observation 으로 만들고, 끝나면 요약한다. SQLite(FTS5) + Chroma 벡터. SessionStart 에 계층형 색인을 주입한다(층마다 토큰 비용 표시). 검색은 3단계(`search` → `timeline` → `get_observations`)이고 "~10x 절약"이라 한다. `<private>` 태그는 저장하지 않는다. Apache-2.0, v15.15.1, 별 약 11.6만. **익명 원격 측정 기본 켜짐**, 선택적 클라우드 동기화, README 에 제3자 토큰 홍보가 있다 | session-log 와 파이프라인이 거의 같다. 다른 점: 원문 대조 없음, 저장소로 받아 가는 흐름 없음, 벡터 DB·Node 워커 의존 | [1차] https://github.com/thedotmack/claude-mem (2026-11-10 열람) |
| **GitHub Copilot Memory** | 에이전트가 도구 호출로 사실과 **코드 위치 인용**을 함께 저장한다. 쓰기 전에 **현재 브랜치에 대고 인용을 확인**하고(just-in-time), 틀리면 고쳐 다시 저장하고, 맞으면 다시 저장해 시각을 갱신한다. 28일 동안 쓰이지 않으면 지운다. 적대적 기억(틀린 사실, 엉뚱한 인용)을 심어 시험했더니 "self-healed". 효과: coding agent PR 병합률 83→90%, code review 정밀도 +3%·재현율 +4%. 오프라인 큐레이션은 비용 때문에 거절했다. 여러 에이전트가 공유한다 | session-log 의 "원문 줄 대조" 와 같은 철학이다. 다른 점: 인용 대상이 **사라지지 않는 코드**이고, 검증 시점이 **읽을 때**다 | [1차] https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/ (2026-01-15), [2차] https://docs.github.com/en/copilot/concepts/agents/copilot-memory (28일) |
| **Claude Code auto memory** | `~/.claude/projects/<project>/memory/`(git 기준이라 worktree 공유, 기기 로컬). `MEMORY.md` 색인의 처음 **200줄 또는 25KB** 를 매 세션 로드한다. 주제 파일 frontmatter `type`: user·feedback·project·reference. "코드에서 유도 가능한 것은 저장하지 않는다". 트랜스크립트 정리(`cleanupPeriodDays`)에서 제외된다. CLAUDE.md `@import` 는 4단계까지 | session-log 는 시간순 기록, auto memory 는 오래 가는 사실이다. DESIGN §9 의 분담과 같다 | [1차] https://code.claude.com/docs/en/memory (2026-11-10 열람) |
| **Cursor Memories** | 2.1 에서 관리 UI 가 빠졌다. 공식 안내는 "Export memories → Rules(.mdc)" 다. 기능 자체가 남았는지는 직원 답변끼리 엇갈린다 | 자동 기억은 관리하기 어렵고 결국 사람이 고른 규칙으로 돌아간다는 사례 | [2차] https://forum.cursor.com/t/are-my-memories-gone/144057 , https://forum.cursor.com/t/custom-modes-and-memories-gone-in-2-1/143744 (정확한 버전 **미확인**) |
| **Cline Memory Bank** | 규약일 뿐이다: `projectbrief.md`, `productContext.md`, `activeContext.md`, `systemPatterns.md`, `techContext.md`, `progress.md`. 커스텀 지시나 `.clinerules` 로 "initialize/update memory bank" 를 시킨다. 에이전트가 직접 쓴다 | 우리 `.claude/` 기록·handover 관행과 같은 층. 검증·자동화는 없다 | [1차 검색 요약] https://docs.cline.bot/features/memory-bank |
| **mem0 / OpenMemory MCP** | MCP 기억 계층. 코딩 선호·패턴을 자동으로 잡는다. 호스팅과 로컬이 있다. 로컬도 OpenAI 키가 필요하다는 글과 Ollama 를 지원한다는 글이 엇갈린다 | 벡터 기억 서비스형 | [2차] https://mem0.ai/openmemory |
| **Letta** | memory block(DB 영속, 공유 가능), sleep-time 에이전트가 백그라운드에서 블록을 고친다(실험적). Letta Code(Apache-2.0)는 기억 우선 코딩 하네스다. Letta 의 자체 실험: grep·open 같은 **파일시스템 도구만 쓴 에이전트가 LoCoMo 74.0%** 로 mem0 보고치 68.5% 를 넘었다. mem0 는 이후 더 높은 수치를 냈다고 한다(**미확인**) | "평문 파일 + 검색" 이 전용 기억 서비스에 밀리지 않는다는 근거 | [1차 검색 요약] https://www.letta.com/blog/benchmarking-ai-agent-memory (날짜 **미확인**), https://docs.letta.com/guides/agents/architectures/sleeptime/ |
| 기억 공격 연구 | **MINJA**: 질의만으로 기억 저장소에 악성 기록을 심는다. 주입 성공 98.2%, 악성 추론 유도 76.8%(평균) | session-log 의 "주입 안전" 규칙(자유 텍스트 요약을 주입하지 않음)이 겨누는 위협 | [1차 검색 요약] https://arxiv.org/abs/2503.03704 (NeurIPS 2025, v5 2026-02-12) |

### 1.3 지식 정본 + 실행 가능한 예시

| 사례 | 표식 | luau-kb 대응 | 출처 |
|---|---|---|---|
| **rustdoc doctest** | ```` ```compile_fail,E0382 ````(컴파일되면 실패, 오류 코드 일치), `should_panic`. 오타 속성은 오류로 낸다 | `-- expect-error[: 부분 문자열]`. 하네스가 표식 오타를 막는지는 `snippet-markers.md` §3 에서 볼 일 | [1차] https://doc.rust-lang.org/rustdoc/write-documentation/documentation-tests.html |
| **TypeScript twoslash** | `// @errors: 2322`(그 오류 코드여야 렌더된다), `^?`(그 자리의 타입 질의), `^|`(자동완성), `---cut---`. 오류 번호는 버전마다 바뀔 수 있다고 명시 | `expect-error` + `tools/lsp_probe.py`(hover·자동완성). **문서 안 코드 블록**에 표식이 있다는 점이 다르다. luau-kb 는 snippets/ 파일과 references 를 링크로 잇는다 | [2차] https://www.typescriptlang.org/dev/twoslash , https://twoslash.netlify.app/refs/notations |
| **pytest `xfail(strict=True)`** | 알려진 실패. 통과(XPASS)하면 스위트가 실패한다. `raises=` 로 실패 이유를 좁힌다 | **`-- bug-present` 와 같은 의미론**(진단이 생기면 "동작이 바뀜"으로 실패) | [1차] https://docs.pytest.org/en/stable/how-to/skipping.html |
| **Python typing conformance** | `python/typing/conformance`: 사양 절마다 테스트 파일, mypy·pyright·pyrefly·ty·zuban 등의 결과를 **검사기 × 테스트 표**로 공개한다 | `snippets/RESULTS.md` 의 **버전 × 스니펫 행렬**(luau 0.734/0.742, luau-lsp 참고 열). 축이 "검사기" 대신 "같은 검사기의 버전"이다 | [2차] https://github.com/python/typing/tree/main/conformance (결과표 원문 **미확인**) |
| **Luau 저장소** | `tests/conformance/*.luau`(basic, types, calls …)는 런타임 적합성 시험이다. 타입 검사기 시험이 C++ 단위 시험(`TypeInfer.*.test.cpp`)인지는 **미확인** | luau-kb 는 상류 시험을 지식으로 쓰지 않고 자체 재현을 둔다. 상류 시험 파일을 "근거" 로 링크하는 길은 열려 있다 | [1차] https://github.com/luau-lang/luau/tree/master/tests/conformance |
| Go `Example…` + `// Output:` | 출력이 문서이자 시험이다 | `--@run` 실행 머리 | **미확인**(이번에 열지 않음, 일반 지식) |

- 조사 범위 안에서 **에이전트용 지식 도구가 주장마다 실행 재현을 붙이고 버전 행렬로 다시 돌리는 사례는 찾지 못했다.** 실행 가능한 문서의 관행은 언어·라이브러리 문서 쪽(rustdoc, twoslash, doctest)에 있다. 거기에도 "알려진 결함이 고쳐지면 알림"(xfail strict) + "버전 조건 표식" + "다중 버전 행렬" 을 한 번에 갖춘 것은 없다.

### 1.4 버전 인식 지식

| 사례 | 방식 | 대응 | 출처 |
|---|---|---|---|
| **Next.js `agents-md`** | 설치된 Next.js 버전을 감지하고, 그 버전의 문서를 `.next-docs/` 에 받고, **파이프 구분 압축 색인(40KB → 8KB)** 을 AGENTS.md 에 넣는다. 평가(Next.js 16 API): 기준 53%, 스킬 53%, 스킬 + 명시 지시 79%, **AGENTS.md 색인 100%**. "56% 에서 스킬이 한 번도 호출되지 않았다". 스킬은 "업그레이드" 같은 수직 작업에 맞다고 한다. 최신 Next.js 는 문서를 패키지에 동봉한다 | coderag §19 T2 + §18.2 핀 자동 읽기와 **같은 설계**. 우리는 pack 이 버전마다 따로 있지 않고, 주장마다 `applies_to` 를 단다 | [1차] https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals (2026-01-27), [2차] https://nextjs.org/docs/app/guides/ai-agents |
| **Context7** | 질의에 적힌 버전으로 맞춘다. ID 에 버전 접미 | 질의 수준이다. 프로젝트 핀은 읽지 않는다 | §1.1 |
| **docs-mcp-server** | 버전마다 따로 색인한다 | pack rev 키 | §1.1 |
| **MDN browser-compat-data** | 기능 × 브라우저마다 `version_added`/`version_removed`(문자열·true·false·null·"preview"), `flags[]`, `partial_implementation`, `status{experimental, standard_track, deprecated}`. JSON 스키마와 lint 로 검증한다 | `applies_to`(도구별) + `lifecycle`(`flagged`·`deprecated`) + `rfc`. BCD 가 "도구마다 다른 지원 버전 + 플래그 뒤" 를 가장 오래 다뤄 온 데이터 모델이다 | [2차] https://github.com/mdn/browser-compat-data/blob/main/schemas/compat-data-schema.md |
| **Sphinx** | `versionadded`, `versionchanged`, `deprecated`, `versionremoved` 지시어 | coderag `since`, `deprecated`, `lifecycle: removed` | [2차] 공식 페이지 **미확인** |
| 연구 | LLM 코드 완성의 폐기 API 사용(ICSE 2025, 7개 모델, 28,125 프롬프트). 원인은 학습 데이터와 추론 시점에 폐기 지식이 없는 것이고, 대체 API 를 프롬프트에 넣으면 고쳐진다. **GitChameleon 2.0**: 버전 조건 문제 328개(26개 라이브러리)에서 상위 모델 기준선이 48–51% | "빨리 변하는 언어는 버전 표시된 지식을 주입해야 한다" 는 전제의 근거 | [1차 검색 요약] https://arxiv.org/abs/2406.09834 , https://arxiv.org/abs/2507.12367 |

### 1.5 표준과 배포 경로

| 표준 | 현황 | 출처 |
|---|---|---|
| **Agent Skills** | 2025-12-18 공개 사양이다. frontmatter 필수 키는 `name`(≤64, 소문자·숫자·`-`, 디렉터리 이름과 같아야 함)과 `description`(≤1024, 무엇 + 언제). 선택 키는 `license`, `compatibility`(≤500), `metadata`(문자열 맵), `allowed-tools`(실험). 점진 공개: 메타 ~100토큰 → 본문 <5000토큰·<500줄 권장 → references 는 필요할 때. 참조는 한 단계 깊이까지. 검사기 `skills-ref validate` | [1차] https://agentskills.io/specification |
| Codex 의 스킬 | "open agent skills standard" 를 따른다. 찾는 곳: `$CWD/.agents/skills`(저장소 루트까지 위로), `$HOME/.agents/skills`, `/etc/codex/skills` | [1차] https://learn.chatgpt.com/docs/build-skills |
| Gemini CLI 의 스킬 | "Agent Skills open standard 기반". 찾는 곳: `~/.gemini/skills/` 또는 `~/.agents/skills/`, 작업 공간 `.gemini/skills/`·`.agents/skills/`(`.agents` 가 우선) | [1차] https://geminicli.com/docs/cli/skills/ |
| **AGENTS.md** | Linux Foundation 산하 Agentic AI Foundation(2025-12-09)의 창립 프로젝트(MCP, goose 와 함께). **Claude Code 도 v2.1.277+ 에서 AGENTS.md 를 직접 읽는다.** 단, 작업 디렉터리나 그 위에 CLAUDE.md·CLAUDE.local.md 가 없을 때만 읽는다. 둘 다 읽으려면 `instructionFiles: claude-md-and-agents-md` 설정이나 `@AGENTS.md` import 가 필요하다 | [2차] https://sdtimes.com/ai/linux-foundation-forms-agentic-ai-foundation-to-be-new-home-for-mcp-goose-and-agents-md/ , [1차] https://code.claude.com/docs/en/memory |
| **MCP** | Claude Code: 플러그인이 `.mcp.json`(또는 plugin.json `mcpServers`)으로 서버를 동봉할 수 있다. 출력이 10k 토큰을 넘으면 경고하고 25k 에서 자른다(`MAX_MCP_OUTPUT_TOKENS`). tool search 가 기본으로 켜져 있다. Codex: `~/.codex/config.toml` `[mcp_servers.<name>]`(프로젝트 `.codex/config.toml` 은 신뢰된 프로젝트만). Gemini CLI: `settings.json` `mcpServers`(stdio·SSE·HTTP), 확장이 MCP 를 동봉한다 | [1차] https://code.claude.com/docs/en/mcp , [2차] https://developers.openai.com/codex/mcp , [1차] https://geminicli.com/docs/tools/mcp-server/ |

---

## 2. 우리 것과 기능 대조

판정 기호: **재발명** = 이미 있는 것을 다시 만든다 / **차별** = 우리만의 차별점 / **표준** = 가져다 쓰거나 호환을 맞출 표준이 있다 / **약점** = 우리 설계의 약점이 외부에서 이미 문제로 드러났다.

### 2.1 coderag

| 기능 | 외부 대응 | 판정 | 근거·권고 |
|---|---|---|---|
| frontmatter 색인 + 결정적 랭킹(임베딩 없음) | docs-mcp-server(임베딩 선택), claude-context(BM25 + 벡터), claude-mem(FTS5 + Chroma) | **차별(약함)** | Claude Code 가 벡터 RAG 를 버렸다는 전언, Letta 의 파일시스템 74% 가 방향을 지지한다. 벡터 쪽은 "토큰 40% 절약" 을 주장하지만 업체 주장이다. 약점은 동의어를 놓치는 것이다. taxonomy `aliases`·`keywords` 가 메운다. **재현율을 실측할 것**(질의 세트 → 기대 문서) |
| 결과 = `경로:a-b ~토큰`, 큰 문서는 목차, 절 단위 읽기 | claude-mem 3단계(색인 50–100토큰/건 → 상세), DeepWiki structure → contents, Sourcegraph `read_file` startLine/endLine, aider 토큰 예산 | **재발명(패턴)·차별 아님** | 업계가 수렴한 "점진 공개" 패턴이다. 그대로 두되 새로 발명했다고 쓰지 말 것. Chroma "context rot"(2025-07-14, 18개 모델에서 입력이 길수록 성능이 고르지 않게 떨어짐)이 근거다 |
| global/pack/project 세 계층 합치기 | Claude Code 메모리 계층(org/user/project/local), Codex·Gemini 스킬 위치 계층, Context7(전역 레지스트리) | **차별(중간)** | 문서 검색에서 "공유 pack + 프로젝트 기록" 을 **한 질의로** 합치고 결과에 계층 꼬리표를 다는 도구는 찾지 못했다. 스킬 계층은 로드 우선순위일 뿐 검색이 아니다 |
| taxonomy(통제 어휘, 별칭, 폐기 → 새 경로) | BCD·Backstage 류 카탈로그. 에이전트 지식 도구에는 없다 | **차별(작음)** | 규모가 작을 때는 비용이 이익보다 크기 쉽다. 범주 94개 초안은 lint 부담이 된다. 별칭(검색 동의어)이 실익의 대부분이다 |
| `applies_to`·`lifecycle`·핀 자동 읽기·강등 | Next.js agents-md(패키지 버전 → 문서 판), Context7(질의 속 버전), docs-mcp-server(판별 색인), BCD(도구별 version_added + flags) | **차별(강함) + 표준(이름)** | **주장 단위**, **여러 도구 AND/OR**, **mise/rokit 핀 자동 읽기**, **숨기지 않고 강등**을 다 갖춘 것은 찾지 못했다. 다만 키 이름은 BCD·Sphinx 어휘(`version_added`/`since`, `version_removed`/`removed`, `flags` ↔ `flagged`, `deprecated`)와 대응표를 README 에 두면 외부 사람이 읽기 쉽다 |
| `stale`(review_after, 버전 낡음, 없는 경로·절) | Copilot Memory 28일 만료 + 사용 시점 검증. BCD lint | **차별** | 정적 검사로 "확인 버전 < 핀" 을 잡는 것은 우리만의 것이다. Copilot 은 "쓰지 않으면 만료", 우리는 "핀이 앞서면 재확인" 이다 |
| static-gen → AGENTS.md/GEMINI.md(T1 상시, T2 색인) | **Next.js `agents-md`**(압축 색인 8KB, 버전 맞춤) | **표준(패턴 일치)·약점(전제)** | 같은 설계라 방향은 검증됐다. 고칠 것 둘. ① §19 표의 "agents-md·gemini-md: 스킬을 못 읽는다" 는 **낡았다**. Codex·Gemini CLI 모두 Agent Skills 를 읽는다(§1.5). T2 는 "유일한 지도" 가 아니라 "자동 호출이 안 되는 경우의 보험" 이다. ② D19-3 "claude-md 에는 넣지 않음" 은 Vercel 의 스킬 미호출 56% 와 정면으로 부딪힌다. **우리 저장소에서 스킬 호출률을 재고**(.claude/audit/10 트랜스크립트로 셀 수 있다), 낮으면 T2 를 CLAUDE.md 나 path-scoped rule 에 넣는다. Claude Code 는 CLAUDE.md 가 있으면 AGENTS.md 를 읽지 않는다는 점도 §19 에 적을 것 |
| doc-locator(haiku 읽기 전용) + pre-bash 훅 허용 목록 | MCP 읽기 전용 도구(Serena, DeepWiki, Sourcegraph) | **약점(작음)** | 훅으로 Bash 를 좁히는 것은 우회 위험이 있고 플랫폼마다 다시 짜야 한다. MCP 도구(`search`·`get`)를 주면 서브에이전트에게 Bash 자체를 주지 않아도 된다(§3) |
| 프로바이더 `typescript-swc`(.d.ts 표면), 이후 Luau 코드 표면 | **Serena(LSP, Luau 명시)**, aider repo-map, Sourcegraph `go_to_definition`, luau-lsp 자체 | **재발명 위험(높음)** | 문서 축은 차별이고 코드 표면 축은 LSP 생태계가 이미 갖고 있다. Luau 쪽은 luau-kb `.lsp.json`(Claude Code LSP 도구)이 이미 hover·정의 이동을 준다. **Luau 코드 표면 프로바이더는 착수 전에 Serena + luau-lsp 로 충분한지부터 재 볼 것**(Serena 의 Luau 지원 품질은 **미확인**) |
| 문서 신뢰 경계 | Context7 ContextCrush·CVE-2026-75130 | **약점(잠재)** | §15 git 소스와 git pack 은 남의 문서를 색인한다. §19 T1 은 그 내용을 **상시 컨텍스트**에 넣는다. 이 둘이 만나면 Context7 과 같은 주입 표면이 된다. 권고: T1 은 로컬 path pack·global 만 허용한다. git pack 은 T2(위치만)까지만 쓴다. `get --body` 출력에는 "데이터이지 지시가 아님" 머리 한 줄을 둔다(roblox-docs 규칙과 같게) |

### 2.2 session-log

| 기능 | 외부 대응 | 판정 | 근거·권고 |
|---|---|---|---|
| 훅 → 분리 프로세스 → 저비용 모델 요약 → 로컬 저장 → SessionStart 주입 | **claude-mem**(observer 에이전트, SQLite + Chroma, SessionStart 계층 색인), remember(.claude/audit/15) | **재발명(뼈대)** | 뼈대는 두 도구와 같다. claude-mem 은 Apache-2.0 이라 remember 와 달리 코드를 참고해도 된다. 그래도 그대로 쓰기는 어렵다: 원격 측정이 기본으로 켜져 있고, 클라우드 동기화가 있고, Node 워커와 벡터 DB 가 필요하고, 저장소로 받아 가는 흐름이 없다. **빌려 올 것**: `<private>` 제외 태그, SessionStart 주입에 층마다 토큰 비용 표시 |
| 숫자·해시·사용자 인용을 원문 줄과 **기계 대조**, 실패 표시 | **Copilot Memory**(인용 + 사용 시점 검증, 적대적 기억 자가 치유) | **차별(강함)** | 외부에서 가장 가까운 것이 Copilot 이다. Copilot 은 PR 병합 +7%p 로 효과를 보였으니 방향이 검증됐다. 기계 대조(LLM 호출 없음)로 하는 것은 우리만의 것이다 |
| 근거 = 트랜스크립트 줄 `(L…)` | Copilot 은 **코드 위치**를 인용 | **약점** | 트랜스크립트는 `cleanupPeriodDays`(기본 30일) 뒤 지워진다(DESIGN §9). 그 뒤에는 `(L…)` 를 다시 확인할 수 없다. 권고: `/session-import` 때 결정·수치 항목에 **커밋 해시나 파일:줄 인용을 덧붙이고**(가져가는 에이전트가 할 수 있다), 가져간 사본에서는 L 인용을 보조로 내린다. 그러면 Copilot 식 "읽을 때 검증" 이 가능해진다 |
| 저장소 밖 저장 → pending → 저장소 에이전트가 골라 import·커밋 | Cursor(자동 기억 → 2.1 에서 UI 제거, Rules 로 내보내기), Cline Memory Bank(에이전트가 저장소 파일에 직접 씀), auto memory(기기 로컬, 커밋 안 함) | **차별** | "자동 기억은 결국 사람이 고른 규칙으로 돌아간다" 는 Cursor 사례가 pending → import 설계를 뒷받침한다. 자동 기록이 리뷰를 거쳐 **버전 관리되는 문서**가 되는 흐름은 다른 데서 찾지 못했다 |
| 주입 안전(구조화 항목만, 자유 요약 금지, `<>` 무력화) | MINJA(질의만으로 기억 오염 98%), claude-mem(색인만 주입) | **차별(정당)** | 위협이 실재한다. 유지한다 |
| coderag frontmatter 로 기록 → global 계층 색인 | claude-mem MCP `search` | **표준(내부)** | 외부 표준은 없다. 우리 계약(§11.4·§17)을 지키면 된다 |
| auto memory 와의 분담 | Claude Code auto memory(`type: feedback/project`) | **재발명 위험(경계)** | `/checkpoint` 가 "반복 지시 → 메모리 후보 제안" 을 하므로 경계가 맞닿는다. auto memory 의 `project` 유형(진행 중인 일, 결정)과 session-log "결정·미해결" 이 겹친다. 권고: 메모리 후보 제안은 `feedback`·`user` 유형만 하고, `project` 는 session-log 에 둔다 |

### 2.3 luau-kb

| 기능 | 외부 대응 | 판정 | 근거·권고 |
|---|---|---|---|
| 스킬 12개(SKILL.md + references) | Agent Skills 사양 | **표준(이미 맞음)** | 12개 모두 frontmatter 가 `name`·`description` 뿐이고, 이름 = 디렉터리, description 262–892자(≤1024), 본문 39–94줄(<500)이다. 그래서 **Codex·Gemini CLI 가 `~/.agents/skills/` symlink 로 바로 읽을 수 있다.** 지금 AGENTS.md 의 손으로 쓴 경로 표는 그 보험이다. `skills-ref validate` 를 `claude plugin validate` 옆에 둘 것(외부 도구라 설치·실행은 사용자 판단) |
| references frontmatter(`title`·`description`·`keywords`·`category`·`tags`·`last_verified`·`last_confirmed`) | Agent Skills `metadata`(문자열 맵) | **표준(해당 없음)** | references 는 사양 밖이라 충돌이 없다. SKILL.md 에 coderag 키를 더하게 되면 최상위가 아니라 `metadata:` 아래에 둘 것(검사기 호환) |
| `snippets/` + `check_snippets.py`(`expect-error[: 부분]`, `bug-present`, 버전 조건 `[<0.742] || […]`, `--@run`…), RESULTS 행렬 | rustdoc `compile_fail`+오류 코드, twoslash `@errors`·`^?`, pytest `xfail(strict)`, Python typing conformance 표 | **차별(강함)** | 낱낱의 표식에는 전례가 있다. 그런데 **에이전트 지식 정본의 주장마다** 붙이고 **다중 버전 행렬**로 상류 수정을 감지하는 조합은 찾지 못했다. 이름은 우리 것을 유지해도 된다. 문서에 "`bug-present` ≈ pytest `xfail(strict=True)`, `expect-error: X` ≈ rustdoc `compile_fail,EXXXX`" 대응을 한 줄 두면 외부 기여자가 바로 이해한다 |
| `tools/roblox_docs.py`(creator-docs 원본 캐시, search/get/api, 인용에 커밋 + STUDIO_VERSION) | 커뮤니티 Roblox Docs MCP, Context7(Roblox 등재 여부 **미확인**), Roblox 공식 `llms.txt` + `.md` 페이지 | **재발명 위험(중간)·차별(작음)** | 같은 원천을 다른 사람들도 MCP 로 낸다. 차별점은 오프라인, 신뢰하지 않는 데이터로 다루기, 인용 고정(커밋 + 버전), `api` 의 보안·thread_safety 요약이다. **coderag 의 provider 로 흡수할지**(문서 루트 = creator-docs 캐시) 검토할 만하다. 그러면 도구가 둘에서 하나로 준다 |
| AGENTS.md(손으로 쓴 경로 표) | Next.js agents-md 압축 색인, Claude Code AGENTS.md 직접 읽기 | **표준** | coderag §19 M7(생성으로 교체)이 Vercel 패턴과 같다. 압축 형식(파이프 구분, 경로 위주)으로 만들 것 |
| `last_confirmed` + 버전 낡음 | BCD `version_added`, Copilot 만료 | **차별** | §2.1 과 같음 |

---

## 3. coderag 를 MCP 로도 노출할지 — 외부 근거

### 3.1 노출하자는 근거
1. **세 에이전트 모두 stdio MCP 를 1급으로 읽는다.** Claude Code(플러그인 `.mcp.json` 동봉), Codex(`config.toml` `[mcp_servers.*]`), Gemini CLI(`settings.json` `mcpServers`, 확장 동봉). 셸 명령 허용 정책이 에이전트마다 다른 것보다 MCP 등록 한 번이 이식성이 높다. [1차] §1.5.
2. **같은 지식을 CLI·스킬과 MCP 로 이중 노출한 선례가 있다.** Context7 이 "CLI + Skills" 모드와 MCP 모드를 함께 낸다. Serena·DeepWiki·Sourcegraph·Mintlify·docs-mcp-server 같은 문서·코드 검색 도구의 배포 경로는 사실상 MCP 다.
3. **읽기 전용 표면이 타입으로 고정된다.** 지금 doc-locator 는 Bash 를 받고, 그 Bash 를 PreToolUse 훅이 `coderag search|get|list|stale` 로 좁힌다(§11.8). MCP 도구를 주면 서브에이전트에게 Bash 를 아예 주지 않아도 된다. 다른 에이전트에서는 이 훅을 다시 짤 수 없으니 이 차이가 더 크다.
4. **Claude Code 쪽 비용은 상쇄된다.** tool search 가 기본으로 켜져 있어 도구 정의를 미리 다 싣지 않는다. 출력은 25k 토큰에서 자른다(우리 출력은 이미 짧다). [1차] https://code.claude.com/docs/en/mcp.
5. Codex 기본 샌드박스에서 작업 디렉터리 밖(pack 경로 `/code/Projects/claude-doctor/packs/luau-kb`)을 셸로 읽을 수 있는지가 문제가 될 수 있다. MCP 서버는 별도 프로세스라 그 제약을 받지 않을 **가능성**이 있다(**미확인** — Codex 샌드박스와 MCP 프로세스의 관계는 열어 보지 않았다).

### 3.2 신중하자는 근거
1. **1인 개발자 환경에서는 CLI 가 더 싸고 안정적이다.** Scalekit(2026-03-11, Claude Sonnet 4, 75회, GitHub 읽기 작업 5종): MCP 가 CLI 보다 토큰을 4–32배 더 썼고(가장 단순한 작업 1,365 대 44,026), 성공률은 MCP 72% 대 CLI 100% 였다(실패는 전부 연결 시간 초과). 다만 비교 대상은 도구 43개짜리 서버다. 저자는 MCP 업체이고, 다중 사용자·인증 상황에서는 MCP 가 맞다고 결론 내린다. [1차] https://scalekit.com/blog/mcp-vs-cli-use
2. **도구 정의 부담.** Anthropic 은 도구 정의·결과가 컨텍스트를 크게 먹는다고 지적했다(코드 실행으로 150,000 → 2,000 토큰 예시). 도구가 많은 서버일수록 문제다. [1차] https://www.anthropic.com/engineering/code-execution-with-mcp (2025-11-04)
3. 우리 출력(`경로:a-b ~토큰`, 두 줄 결과)은 이미 CLI 로 짧다. Claude 에게 MCP 로 얻는 이익은 3.1-3 하나뿐이다.

### 3.3 판단
- **CLI 를 1차로 유지하고, 이미 계획된 `coderag mcp`(TODO.md, tech-design §9 🔜)를 "얇게" 만든다.**
  - 도구는 `search`, `get` 2개(+선택 `stale`). 스키마는 CLI 플래그의 부분집합으로 둔다.
  - 출력 문자열은 CLI 와 바이트 단위로 같게 한다. 그러면 doc-locator 의 응답 형식, 시험, 문서를 함께 쓴다.
  - 쓰기·`gen` 은 넣지 않는다. 색인은 훅이나 사용자가 한다(§22).
  - 근거: Scalekit 의 비용은 "도구 수 × 스키마 크기" 에서 나온다. 도구 2개짜리 서버는 그 비용 구조가 다르다. Context7 이 같은 이중 노출을 한다.
- 이득이 가장 큰 순서는 ① Codex/Gemini 에서 pack 조회(지금은 AGENTS.md 평문 경로뿐이다), ② doc-locator 의 Bash 제거, ③ Claude 메인 세션 순이다.
- MCP **resources**(`coderag://doc/<id>`)는 지원이 클라이언트마다 고르지 않아 보여 미룬다(**미확인**).
- 검증: 같은 질의 10개로 CLI 경로와 MCP 경로의 토큰·성공률을 세 에이전트에서 잰다. 1인 환경이라 Scalekit 과 비교할 수 있다.

---

## 4. 외부에서 드러난 약점 — 우리 설계에 비춰

1. **스킬은 자동으로 잘 호출되지 않는다.** Vercel: 56% 미호출, 명시 지시를 넣어도 79%, 상시 색인은 100%. "You MUST invoke" 식 문구는 오히려 프로젝트 문맥을 놓치게 했다.
   - 영향: luau-kb 는 Claude 에게 "스킬 자동 호출 = 1차 진입로" 이고(§20), coderag D19-3 은 claude-md 에 pack 색인을 넣지 않는다.
   - 조치: 우리 트랜스크립트에서 luau-kb 스킬 호출률을 잰다. 낮으면 T2 압축 색인(≤8KB 목표)을 path-scoped rule(`**/*.luau`)에 넣는 쪽을 먼저 시험한다. 그 방식은 Luau 파일을 만질 때만 로드되니 상시 컨텍스트 예산(PLAN P3)과 충돌이 적다.
2. **문서가 지시가 되는 주입.** Context7 은 커뮤니티 문서의 "규칙" 칸으로 뚫렸다.
   - 영향: coderag git 소스·git pack, §19 T1 상시 주입.
   - 조치: §2.1 마지막 행(T1 은 신뢰된 로컬 pack 만).
3. **기억의 근거가 썩는다.** Copilot 은 근거를 지워지지 않는 코드에 두고 읽을 때 검증한다. 28일 만료로 낡은 것을 버린다.
   - 영향: session-log `(L…)` 근거는 30일 뒤 사라진다.
   - 조치: §2.2 의 import 때 코드·커밋 인용 추가.
4. **자동 기억은 관리 UI 가 없으면 버려진다.** Cursor 가 2.1 에서 UI 를 빼고 Rules 로 내보내게 했다. 우리 pending → import 가 이 문제를 겨눈다.
   - 위험: pending 이 쌓이기만 하면 같은 길을 간다. `SESSION_LOG_PENDING_STRONG_*`(5개 또는 7일) 알림이 있으니 실제 import 비율을 한 달 뒤에 잰다.
5. **긴 컨텍스트는 성능을 깎는다**(Chroma context rot). 절 단위 읽기·토큰 표시·`budget` 초과 오류(§19)는 정당하다. 유지한다.
6. **llms.txt 는 크롤러에게 거의 읽히지 않는다.** luau-kb 를 공개 호스팅하지 않는 한 만들 이유가 없다. 공개한다면 coderag 색인에서 `llms.txt` 를 생성하는 generator 하나로 충분하다(T2 와 모양이 같다: H2 = 범주, 링크 + 한 줄, `## Optional` = 기록류).
7. **어휘 검색의 동의어 누락.** 벡터 쪽 업체들은 grep 이 토큰을 낭비한다고 주장한다(업체 주장). 우리는 별칭·keywords 로 메운다. 한·영 혼용 질의의 재현율을 질의 세트로 재 둘 것.

---

## 5. 권고 (우선순위)

| # | 무엇 | 어디 | 근거 |
|---|---|---|---|
| R1 | §19 표의 "agents-md·gemini-md 는 스킬을 못 읽는다" 를 고친다. Codex·Gemini 에 luau-kb 스킬을 `~/.agents/skills/<name>` symlink 로 노출하는 안을 추가한다(사용자 결정) | coderag tech-design §19, luau-kb README·AGENTS.md | §1.5 Codex·Gemini 스킬 문서 |
| R2 | 스킬 호출률을 실측하고 D19-3 을 재검토한다. Claude Code 가 CLAUDE.md 가 있으면 AGENTS.md 를 읽지 않는다는 사실도 §19 에 적는다 | claude-doctor audit, coderag §19 | Vercel 2026-01-27, Claude Code memory 문서 |
| R3 | `coderag mcp` 를 도구 2–3개짜리 얇은 어댑터로 만들고, CLI 와 출력을 같게 한다. doc-locator 는 MCP 도구만 받게 하는 안을 둔다 | coderag | §3 |
| R4 | T1 상시 주입은 로컬·신뢰 pack 만. git pack 은 위치(T2)까지 | coderag §15·§19 | ContextCrush, CVE-2026-75130 |
| R5 | session-log import 때 결정·수치 항목에 커밋·파일 인용을 붙이는 단계를 둔다 | session-log `/session-import` 스킬 | Copilot Memory |
| R6 | Luau 코드 표면 프로바이더는 착수 전에 Serena + luau-lsp 로 충분한지 비교한다 | coderag TODO | Serena README(Luau 명시) |
| R7 | 외부 대응 한 줄씩 적기: `bug-present` ≈ `xfail(strict)`, `expect-error` ≈ `compile_fail`, `applies_to`/`lifecycle` ↔ BCD `version_added`/`flags`/`deprecated` | luau-kb `snippet-markers.md`, coderag §18 | §1.3·§1.4 |
| R8 | (낮음) `roblox_docs.py` 를 coderag provider 로 흡수할지 검토. llms.txt 는 공개할 때만 | luau-kb, coderag | §2.3, §4-6 |

---

## 6. 확인하지 못한 것
- CVE-2026-75130 의 NVD 원문, CVSS, 수정 여부(집계 사이트끼리 엇갈림). ContextCrush 수정일 2026-02-23 은 2차 출처다.
- Sourcegraph MCP 가 Enterprise 전용인지, 가격.
- Cursor Memories 가 UI 만 빠진 것인지 기능까지 빠진 것인지(직원 답변이 엇갈림), 정확한 버전.
- Serena 의 Luau 백엔드가 luau-lsp 인지, 품질은 어떤지.
- Luau 타입 검사기 시험이 C++ 단위 시험인지(`tests/conformance` 는 런타임 시험으로 확인).
- Boris Cherny 의 "RAG → agentic search" 1차 발언.
- Letta 파일시스템 벤치마크의 게시일과 mem0 의 이후 수치.
- Codex 샌드박스와 MCP 서버 프로세스의 파일 접근 관계.
- Python typing conformance 결과표 원문, Sphinx 공식 지시어 페이지, Go Example 문서(이번에 열지 않음).
- Ahrefs llms.txt 연구의 게시일.
