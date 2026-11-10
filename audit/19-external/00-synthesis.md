# 외부 관점 종합 (2026-11-10)

원천:
- 01-official: 공식 문서·블로그 대조
- 02-community: 커뮤니티 사례
- 03-knowledge-tools: 지식·기억 도구 지형
- 04-luau-ecosystem-and-evals: Luau·Roblox 생태계와 평가 방법
- 05-verification: 핵심 주장 9건 1차 출처 검증

이 문서는 메인이 쓴 종합이다. 근거 등급과 URL 은 각 원천 문서에 있다.

## 0. 한 줄 결론

골격은 공식 권고와 잘 맞는다(01 §a). paths 로 범위를 정한 rules, 새 컨텍스트 리뷰어, deny 훅, 비자명한 함정만 담은 rules 가 그 예다.

외부에서 보이는 위험은 **"쌓기"** 다. 규칙·훅·자체 도구가 계속 늘면 상시 비용과 유지보수 빚이 커진다. 모델 세대가 바뀌면 그 빚은 더 커진다. 그래서 다음 순서를 권한다.
1. 공식 도구와 표준을 먼저 쓴다.
2. 우리가 직접 만드는 것은 진짜 차별점에 집중한다. 실행 가능한 지식, 다저장소 표류 검사, 버전 인식이 여기에 해당한다.

## 1. 지금 바로 바꿀 가치가 큰 것 (근거 확인됨)

| # | 조언 | 근거 | 우리 상태 |
|---|---|---|---|
| 1 | **luau-kb 를 플러그인으로 설치하고 Luau 저장소에서만 켠다** | 로컬 경로 마켓 플러그인은 제자리에서 로드되어 버전 bump 가 필요 없다(05 #5 확인). 지금 링크 방식은 `.lsp.json`(luau-lsp)을 못 켜고, 스킬 설명 약 6,900자가 웹·rust 세션에도 상시로 실린다(01) | 사용자 결정 대기(A/B). **A(플러그인)로 근거가 확정됐다** |
| 2 | **비용 폭주는 문장이 아니라 훅으로 막는다** | 공식: "막으려면 PreToolUse 훅". 서브에이전트 폭주 이슈가 여러 건 있다(02) | $589 사고 대응이 CLAUDE.md 문장뿐이다. Agent 생성 수·모델을 세는 PreToolUse(Agent) 훅과 `--max-budget-usd` 가 없다 |
| 3 | **공식 진단 도구를 먼저 쓰고, harness-doctor 는 공식이 못 하는 것에 집중한다** | `/doctor`(prompt-audit), `/skill-doctor`, `/insights`, `claude plugin details/eval`, `InstructionsLoaded` 가 모두 존재한다(05 #4, 로컬 2.1.316) | harness-doctor 의 LOAD·RULE·STALE 검사가 이 도구들과 겹친다. 다저장소, 세션, 표류, 정본 싱크 검사로 좁힌다 |
| 4 | **compact 고충은 공식 장치로 먼저 푼다** | CLAUDE.md `# Compact instructions` 절, `idleCompaction`(v2.1.290+)(05 #4) | session-log 의 PreCompact 상기와 보완 관계다. 짧은 `# Compact instructions` 를 사용자 CLAUDE.md 에 두는 것이 가장 싸다 |
| 5 | **스킬 자동 발동을 믿지 말고 상시 로드되는 색인을 둔다** | Vercel: 스킬 56% 미호출, AGENTS.md 색인 100%. 수치는 맞지만 모델·과제 수는 비공개다(05 #2). Spence 측정은 50~55%(02) | 우리 sonnet 실측 47/50 은 이보다 좋지만, n 이 작고 메인 모델(Opus 5.5)로 재지 않았다. `**/*.luau` 로 이미 로드되는 `luau-core.md` 에 "증상 → 스킬/참고 경로" 색인 10~20줄을 넣는 것이 가장 싼 보험이다 |
| 6 | **AGENTS.md 와 다른 에이전트 공유 전제를 갱신한다** | Codex(v0.95+)와 Gemini CLI 가 `~/.agents/skills` 의 SKILL.md 를 직접 읽는다(05 #1). Codex 는 AGENTS.md 합계 32KiB 를 넘으면 잘라 낸다(02) | coderag §19 의 "다른 에이전트는 스킬을 못 읽는다" 는 낡은 전제다. luau-kb AGENTS.md(15.6KB)는 색인으로 줄인다 |
| 7 | **Roblox 공식 deprecated 목록을 쓴다** | 603개, 머리말 "Do NOT suggest any API listed below". 웹 빌드에서만 생성되는 페이지다(05 #7) | luau-kb 에 0건이다. roblox-docs 에 `deprecated` 조회와 생성 코드 검사를 더하고, 스킬에 링크한다 |

## 2. 긴장 관계 — 외부 권고와 사용자 결정·우리 실측이 부딪히는 곳

### 2.1 "규칙보다 판단" 대 harness-hook level 과 수치 규칙
- **외부:** Claude 5 글(2026-07-24)과 best-practices 는 강조어를 줄이고, 훅은 예외 없는 규칙에만 쓰라고 한다. 단, 05 #6 의 보정이 있다. 원문 취지는 "상충을 지우라" 가 아니라 "불필요한 제약을 걷으라" 다.
- **우리:**
  - 사용자 결정: "참고 정보로만 치부하면 넘긴다. 꼭 검토하게 하고 urgency 를."
  - 실측(sonnet): `action` 에서 진행 전 처리가 0/2 → 2/2 로 바뀌었다.
- **종합:** level 체계는 유지한다. 다만 빚 관리를 규칙으로 둔다.
  - `action` 은 몇 개의 진짜 불변식에만 쓴다. 지금은 1,500줄 초과와 deny 뿐이다. 늘릴 때 근거를 남긴다.
  - **모델 세대가 바뀔 때마다 "규칙 없이 재기" 를 한다.** 메인 모델로 규칙과 훅을 끈 조건을 재서, 이미 지켜지는 규칙은 걷는다.
  - 상시 컨텍스트 비용을 harness-doctor 에서 숫자로 추적한다. 기준선은 apply 전에 `/context` 로 잰다.
- 측정 모델: 지금까지 실측은 sonnet 이었다. 메인은 Opus 5.5 다. 핵심 규칙은 Opus 로 한 번 다시 잰다(02).

### 2.2 compact 로 길게 이어 가기 대 진척 파일 + `/clear`
- **외부 주류:** 진척 파일을 쓰고 `/clear` 한다(02). 공식 문서상 compact 자체가 큰 요청이다.
- **우리:** 사용자는 "설명하다 보면 compact 만 못 해서 이어 간다" 고 했다. 이 세션은 맥락 26만~42만 토큰이고, advisor 1회에 $1.33 이 들었다.
- **종합:** session-log 가 진척 파일을 자동으로 만든다. 그러면 `/clear` 의 진입 비용("다시 설명하기")이 거의 0이 된다. 그래서 session-log 의 SessionStart 인계를 "`/clear` 하고 와도 이어진다" 수준으로 다듬는 것이 사용자 습관을 억지로 바꾸지 않는 길이다. 컨텍스트 % 알림을 둔다면 문턱마다 1회만 낸다. 주기 알림은 외부에서 가장 먼저 꺼졌다(02).

### 2.3 토론(debate)
- **외부:** 같은 계열끼리 토론하면 다수에 동조하고 토큰이 2~3배 든다. 잘 된 형태는 독립 답변, 초안 맥락 숨김, 구체적 실패 근거 요구, diff 크기 게이트다(02).
- **우리:** 사용자는 "세 모델 토론 결과가 좋았다" 고 했다. 우리 debate 초안은 "실측 판정" 이 최종이다(audit/16 비교).
- **종합:** 다른 회사 모델끼리 하는 토론은 유지한다. 형식에 "1라운드는 서로 못 보고 독립 답변" 과 "재현 가능한 근거 없는 주장은 기각" 을 명시한다. "소진될 때까지" 리뷰에는 **재현 가능한 새 발견이 0인 라운드에서 멈춘다** 는 종료 규칙을 단다.

## 3. 재발명 점검

| 우리 것 | 외부 대응 | 판정 |
|---|---|---|
| session-log | claude-mem(훅 → 백그라운드 요약 → 로컬 → SessionStart 색인), remember | 뼈대는 같다. **차별점:** 원문 대조, 저장소 에이전트가 골라 받아 커밋하는 흐름, 원격 측정 없음. Copilot Memory 의 "인용 + 사용 시점 검증" 이 같은 방향이고, 병합률 90% 대 83% 로 효과가 보고됐다(05 #9). 유지한다. **보완:** 트랜스크립트가 지워지면 `(L…)` 근거가 죽는다. import 때 원문 인용을 함께 옮긴다 |
| roblox_docs.py | docs MCP 류(Context7, docs-mcp-server, 커뮤니티 Roblox Docs MCP) | 겹친다. 다만 오프라인 tarball, 엔진 YAML 의 보안·스레드 필드, 줄 범위 출력은 우리 요구에 맞다. 유지하되 범위를 늘리지 않는다 |
| coderag 문서 검색 | Context7, DeepWiki, llms.txt 생태계 | 차별점은 주장 단위 `applies_to`, 핀 자동 읽기, 강등, 절 단위 예산이다. **보안:** Context7 이 문서 경유 지시 주입에 뚫렸다(CVE-2026-75130 확인, 05 #3). T1 상시 주입과 AGENTS.md 컴파일은 로컬·신뢰 pack 만 허용한다 |
| coderag Luau 심볼 프로바이더(미착수) | Serena(LSP 기반, Luau 명시) | **착수 전에 Serena 를 비교한다.** luau-lsp 를 이미 붙였으므로 LSP 경유가 더 쌀 수 있다 |
| coderag MCP 노출 | Context7 은 CLI 와 MCP 를 함께 낸다 | 도구 2~3개짜리 얇은 stdio 어댑터는 선택 사항이다. 1인 환경에서는 CLI 가 4~32배 쌌다는 반대 자료가 있다(업체 자료). Codex·Gemini 공유가 실제로 필요해질 때 만든다 |
| luau-kb 스니펫 하네스 | pytest `xfail(strict)`, rustdoc `compile_fail`, twoslash | 표식 하나하나에는 전례가 있다. 에이전트 지식에 "주장마다 실행 재현 + 다중 버전 행렬로 상류 수정 감지" 를 묶은 사례는 찾지 못했다. **가장 뚜렷한 차별점** 이다 |

## 4. 평가 방법 (04)
- **지금 실측은 통계적으로 약하다.**
  - 47/50 의 95% Wilson 구간은 0.84~0.98 이다.
  - 같은 질문을 2회 반복했으니 실제 표본은 더 작다.
  - 11 대 12 는 잡음 수준이다.
- 비용 0 개선:
  - Wilson 구간을 붙인다.
  - n<10 비교는 "방향만" 으로 적는다.
  - 반드시 지킬 규칙은 all@k 로 판정한다.
  - 3회를 돌리고, 실패한 질문만 5회 추가한다.
- 비용 소규모 개선(회당 $3~6 추정):
  - **발동하면 안 되는 near-miss 질문 15개** 를 넣는다. 지금은 오발동률을 재지 않는다.
  - description 을 고칠 때는 60/40 으로 나눠 test 점수로 고른다.
- **`claude plugin eval` 로 옮긴다**(v2.1.269+, 확인). 격리 실행이라 사용자 CLAUDE.md 가 섞이지 않고, 플러그인 유무의 차이가 자동으로 나온다. grader 는 regex·tool_used 로 무료다.
- 지표 정의는 `Roblox/open-game-eval`(MIT)의 pass@k, cons@k, all@k 를 빌린다.
- luau-kb 에 `evals/` 를 둔다.

## 5. Luau·Roblox 쪽 보강 (04, 05)
- **deprecated 목록:** 1-7 참고.
- **`spawn` 대체:** 공식 목록은 `task.spawn`, DevForum 은 `task.defer` 가 더 가깝다고 한다. Studio 확인 후보다.
- **studio-mcp.md 갱신:**
  - "공식 문서에 없는 도구" 문장은 낡았다. `subagent` playtest 와 `open_cloud_invoke` 가 문서에 올라왔다.
  - 오픈소스 rust MCP 저장소는 보관됐다(05 #8).
  - Script Sync(베타, Rojo 대안)를 추가한다.
- luau-lang·luau-lsp 쪽 AI 움직임은 없다. luau-lsp 를 Claude Code LSP 로 붙인 것은 우리가 앞서 있다.

## 6. 원천 보고서 정정
- 02: "luau-kb 12개는 발동률을 잰 적이 없다" 는 틀렸다. sonnet 으로 47/50(재편 후), 16/16(경계), 스킬별 2~3/3 을 쟀다. 다만 "메인 모델로 재지 않았다, n 이 작다" 는 맞다.
- 01: "상충은 지우라" 는 원문보다 과하다(05 #6).
- 03, 02: Vercel 수치는 맞지만 조건이 비공개다(05 #2). 우리 결정의 단독 근거로 쓰지 않는다.
- 04: deprecated 목록은 로컬 creator-docs 사본에 없다. 웹 빌드 생성 페이지다(05 #7). roblox_docs 는 웹 `.md` 로 따로 받아야 한다.

## 7. 권하는 다음 순서
1. **apply 전 기준선:** `/context` 로 상시 컨텍스트를 잰다. 대화형 명령이라 사용자가 실행한다.
2. **luau-kb 를 A(플러그인)로 정한다.** MANIFEST 에서 스킬 링크를 빼고 rules 링크만 둔다. 그다음 apply 한다.
3. **비용 가드 훅:** PreToolUse(Agent) 로 세션당 서브에이전트 수, opus 비율, 동시 실행을 센다. 기본은 warn 이고, 문턱을 넘으면 action 이다. 사용자 결정 항목이다.
4. `luau-core.md` 에 증상 → 경로 색인을 넣는다. Opus 와 near-miss 를 넣고 `claude plugin eval` 로 다시 잰다.
5. 사용자 CLAUDE.md 에 `# Compact instructions` 짧은 절을 둔다. session-log 인계를 "`/clear` 해도 이어진다" 수준으로 다듬는다.
6. harness-doctor 범위를 좁힌다. 공식 `/doctor`, `/skill-doctor` 와 겹치는 검사는 위임하거나 링크한다.
7. roblox-docs 에 deprecated 를 추가하고 studio-mcp.md 를 갱신한다.
8. debate·audit 에 종료 규칙과 독립 1라운드를 넣는다.
9. coderag: T1 신뢰 pack 제한, §19 전제 갱신. Serena 비교는 심볼 프로바이더 착수 전에 한다.
