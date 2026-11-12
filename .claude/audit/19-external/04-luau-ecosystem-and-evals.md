# 19-04. Luau/Roblox 생태계의 AI 에이전트 활용과 평가 방법론 (외부 조사 4/4)

> 작성 2026-11-10. 조사는 WebSearch·WebFetch·`curl`(문서 `.md`·GitHub API 읽기)로 했고, 로컬은 읽기만 했다. 외부 코드는 실행하지 않았다. 로컬에서 실행한 것은 `claude plugin eval --help`·`claude plugin eval init --help`(Claude Code 2.1.316)와 Wilson 구간 계산뿐이다.
> 우리 쪽 출발점: `luau-kb/README.md`·`AGENTS.md`·스킬 12개 SKILL.md, `luau-kb/snippets/RESULTS.md` "rules·skill 효과 측정", 트리거 실측 도구 `/tmp/trig-tools/{run.py,questions.json}`, `audit/11`·`audit/13`, 그리고 겹치는 앞선 조사 `audit/02-ecosystem.md`(Script Sync, roblox-brain 은 거기서 이미 다뤘다).
> 날짜 표기: 원문의 게시일이나 `last_updated` 를 적고, 원문에 날짜가 없으면 "날짜 미표기"로 적는다. 조회일은 모두 2026-11-10 이다.

## 0. 요약

**luau-kb 에 빠진 것 3개**
1. **에이전트 오류 카탈로그와 옛 API 대체표.** Roblox 가 "LLM 코드 도우미용"이라고 머리에 적어 둔 deprecated 목록(603개)을 생성 코드 검사에 쓰지 않는다. `wait/spawn/delay`, `Humanoid:LoadAnimation`, `FindPartOnRay` 같은 대표 실수가 여러 references 에 흩어져 있거나 아예 없다. `spawn → task.spawn` 대체는 공식 목록과 DevForum 직원 설명이 서로 다르다(§3.4).
2. **공식 에이전트 경로의 최신 상태.**
   - Script Sync(베타, Rojo 대안)가 없다.
   - 내장 MCP 의 `subagent`(explore·playtest), 입력 시뮬레이션, `open_cloud_invoke` 의 게임별 권한 모델이 빠졌다.
   - Assistant skill 형식과 우리 SKILL.md 의 호환성도 다루지 않는다.
   - `studio-mcp.md` §2 의 "공식 문서에 없는 도구" 문장은 이제 틀렸다. `subagent` 와 `open_cloud_invoke` 가 문서에 올라왔다(§2.2).
3. **회귀 평가 자산.**
   - luau-kb 에 `evals/` 가 없다.
   - 트리거 질문 25개는 모두 "발동해야 하는" 질문이라 오발동률을 재지 않았다.
   - 외부 Luau 벤치(OpenGameEval, LuauBench)와도 이어지지 않았다.

**평가 방법 개선 3개** (§5.4)
1. **트리거 세트를 늘린다.** 발동해야 하는 25개에 발동하면 안 되는 near-miss 15개를 더하고 3회씩 돌린다. 질문 단위로 묶은 Wilson 구간으로 보고한다. description 을 고칠 때는 train/test 로 나눈다.
2. **효과 측정은 `claude plugin eval` 로 옮긴다.** 격리된 실행, with/without Δ, 무료 grader(regex·tool_used·file_exists)를 쓴다. `--model` 과 Claude Code 버전을 고정하고 비용·턴 수도 함께 본다. 실제 환경 확인 2회는 따로 남긴다.
3. **보고 규칙을 정한다.**
   - n<10 이면 "방향만"이라고 쓴다.
   - 차이를 주장하려면 같은 질문으로 짝지어 비교하고, 반복을 늘려야 한다.
   - 반드시 지켜야 하는 규칙에는 pass^k(all@k)를 쓴다.
   - 측정은 적응형으로 한다. 3회를 돌리고 실패가 하나라도 있으면 5회를 더 돌린다.

**활용할 공식 도구**
- **Studio 내장 MCP**: `execute_luau`, `subagent` playtest, `get_console_output`, `screen_capture`, `open_cloud_invoke`. 이 머신에 이미 연결돼 있다.
- **문서**: `create.roblox.com/docs/llms.txt`, `.md` 접미사, 검색 API, `reference/engine/deprecated.md`.
- **평가 틀**: `Roblox/open-game-eval`(MIT). 지표 정의와 과제 형식을 빌려 온다.
- **평가 도구**: `claude plugin eval`, 그리고 skill-creator 의 `run_eval.py`/`run_loop.py`.

## 1. 우리 쪽 현재 상태 (읽은 것)

| 항목 | 상태 |
|---|---|
| 지식 범위 | 스킬 12개, 스니펫 152개 × luau 0.734·0.742 검증, rules 2개, `.lsp.json`(luau-lsp 래퍼), `tools/roblox_docs.py`(creator-docs tarball 캐시) |
| 트리거 실측 | `claude -p --model sonnet --plugin-dir`, 질문마다 새 cwd(`git init`), `--max-turns 2 --tools Skill Read Glob Grep`, stream-json 에서 **처음 부른 Skill** 을 기대값과 비교. 질문 25개 × 2회 → 47/50. 비교안별 결과는 23/26, 44/44, 43/44. 질문은 모두 발동해야 하는 쪽(`questions.json` 25개, 기대 스킬이 빈 항목 0개) |
| 준수율 실측 | 빈 패키지에 모듈과 테스트를 추가하는 과제 1개 × 조건 3개 × 2회. 산출 `.luau` 를 12항목 정규식으로 채점하고 거짓 양성을 손으로 고침. 사용자 홈 설정은 모든 조건에 똑같이 걸림 |
| 알려진 혼입 | 사용자 CLAUDE.md 가 mise 질문에 직접 답해 스킬이 불리지 않은 2회(v2). 같은 cwd 에서 동시에 돌리면 여러 스킬이 연달아 불림 |

## 2. 공식 측(Roblox·luau-lang)의 AI 도구

### 2.1 Roblox Studio Assistant
- **2026-04-15 "Studio going agentic"** 발표에 담긴 것:
  - Planning Mode: 코드와 DataModel 을 분석하고 되묻기를 거쳐 고칠 수 있는 실행 계획을 만든다.
  - Mesh Generation(출시), Procedural Models(예정).
  - **Playtesting Agent(베타)**: 계획과 대조하며 로그를 읽고, 플레이어 캐릭터를 자동 QA 로 쓴다.
  - 내장 MCP 서버로 Claude, Cursor, Codex 같은 외부 도구를 쓸 수 있다.
  - 상위 1,000 크리에이터의 44% 가 Assistant 나 MCP 를 거친 서드파티 AI 를 썼다(2026-03-06~04-07).
- **Assistant skills** (`assistant/skills.md`, last_updated 2026-11-10):
  - 형식은 frontmatter `name`·`description`·`enabled` + 본문 Markdown 이다. **description 이 발동을 정한다**는 점이 Claude Code 와 같다.
  - `rbx-` 접두는 Roblox 전용으로 예약돼 있다.
  - skill 은 Roblox 계정에 묶여 모든 플레이스에서 쓸 수 있다.
  - 응답 옆에 "Loaded skill" 표시가 붙는다. 사람이 발동 여부를 눈으로 셀 수 있다는 뜻이다.
  - 문서에 실린 Roblox 제공 skill 은 9개다. 이 머신의 MCP 가 내놓는 13개(`studio-mcp.md` §6)와 다르다. 문서에 없는 것은 `rbx-network-simulator`, `rbx-permissions`, `rbx-open-cloud-usage`, `rbx-import-asset` 넷이다.
- **BYOK** (`assistant/mcp.md`): Anthropic·OpenAI·Gemini API 키를 넣어 모델을 고른다.

### 2.2 Studio MCP 서버
- **오픈소스 `Roblox/studio-rust-mcp-server`(MIT)는 2026-04-03 에 보관(archived)됐다.**
  - README 는 "더 이상 개발하지 않는다, 내장 MCP 를 쓰라"고 한다.
  - 노출하던 도구는 `run_code`, `insert_model`, `get_console_output`, `start_stop_play`, `run_script_in_play_mode`, `get_studio_mode` 6개다.
  - 그런데 `assistant/mcp.md`(last_updated 2026-11-10)는 아직 이 보관된 저장소를 "open source Studio MCP server"로 링크한다. **문서 불일치이고, 11-knowledge-gaps 표에 16번째로 올릴 만하다.**
- **내장 MCP** (`studio/mcp.md`, last_updated 2026-11-10T00:40:51Z) 도구 분류:
  - 스크립트: `script_read`, `multi_edit`, `script_search`, `script_grep`
  - 생성·에셋: `generate_mesh`, `generate_material`, `generate_procedural_model`, `search_asset`, `insert_asset`, …
  - 탐색: **`subagent`(explore·playtest)**, `search_game_tree`, `inspect_instance`
  - 실행: `execute_luau`(datamodel_type 은 Edit·Client·Server)
  - 플레이테스트: `get_studio_state`, `start_stop_play`, `get_console_output`, `screen_capture`
  - 입력 시뮬레이션: `character_navigation`, `user_keyboard_input`, `user_mouse_input`
  - 문서·skill: `http_get`, `skill`
  - 세션: `list_roblox_studios`
  - 모든 호출에 `studio_id` 가 필요하다.
  - Quick connect 대상은 Antigravity, Codex CLI, **Claude Code**, Claude Desktop, Cursor, Gemini CLI, VS Code 다. 수동 연결 명령은 macOS `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`, Windows `%LOCALAPPDATA%\Roblox\mcp.bat` 이다.
- **`open_cloud_invoke`** (`studio/mcp-open-cloud.md`, 같은 날):
  - API 키 없이 Open Cloud 를 부른다.
  - 권한은 사람이 **게임별로** 켠다: scope, 업로드 폴더, `execute_luau` 안 DataStore/MemoryStore 허용, HTTP 도메인.
  - 클라이언트는 권한을 스스로 켤 수 없다.
- **우리와 대조**: `luau-kb/skills/luau-roblox/references/studio-mcp.md` §2 는 같은 날 이 머신의 도구 스키마로 도구 표를 검증했다. 그런데 "공식 문서에 없는 도구(`subagent`, `open_cloud_invoke`, …)"라는 문장은 이제 반만 맞다. `subagent` 와 `open_cloud_invoke` 는 문서에 올라왔고, `create_skill`·`edit_skill`·`rojo_sync_guide` 는 여전히 문서에 없다.

### 2.3 LLM 친화 문서
- **`/docs/llms.txt`**:
  - 머리에 "For Code Agents: Start Here"가 있고, 엔진 API 와 Open Cloud 를 "섞으면 동작하지 않는 코드가 나온다"고 경고한다.
  - `.md` 접미사, 검색 API `/docs/api/search?q=`, "URL 을 추측하지 말라, 404 는 경로가 틀린 것"을 안내한다.
  - 하위 인덱스는 `reference/engine/llms.txt`, `cloud/llms.txt`, `llms-full.txt`(전문) 다.
  - 우리 `roblox-docs/references/sources.md` §4 가 이미 반영했다.
- **`/docs/reference/engine/deprecated.md`**:
  - 머리에 **"For LLM code assistants: Do NOT suggest any API listed below"**가 있다.
  - 총 603개다: 속성 141, 메서드 247, 이벤트 38, 콜백 2, 함수 15, Enum 항목 160. 열은 Class·Member·Replacement·Note 다.
  - 우리 `sources.md` 표는 URL 만 적었다. `roblox_docs.py` 는 멤버 하나씩 deprecated 를 볼 뿐 **생성 코드를 이 목록으로 훑는 절차는 없다**(→ 빠진 것 1).
- **`ai/coding-harness.md`** (last_updated 2026-11-10):
  - 공식 "코딩 하네스" 안내는 **Script Sync(베타) + 내장 MCP + git** 조합이다.
  - 동기화 확인은 `InstanceFileSyncService:GetStatus(instance)` 로 한다.
  - StarterGui·StarterPack 처럼 Script Sync 가 닿지 않는 곳은 MCP 가 맡는다.
  - Rojo, AGENTS.md, skill 은 언급하지 않는다(audit 02 와 같은 판단).
  - luau-kb 에 Script Sync 언급은 0건이다.
- **`Roblox/creator-docs`**: 루트에 llms.txt·AGENTS.md 가 없다(audit 02, 재확인 안 함).

### 2.4 Roblox 가 공개한 평가·데이터
- **OpenGameEval** (뉴스룸 2025-12-17, 저장소 `Roblox/open-game-eval`, MIT):
  - 상태가 있는 Studio 세션에서 에이전트가 도구를 쓰고, **edit 모드 `check_scene` 과 play 모드 `check_game` 단위 테스트를 모두 통과해야** 성공이다.
  - 처음 공개는 47과제였다. 현재 리더보드는 Expanded 87 evals 와 Debug 30 evals 두 세트다.
  - 지표:
    - **Pass@1**: 한 번에 성공할 확률.
    - **Pass@5**: 5번 중 한 번이라도 성공할 확률.
    - **Cons@5**: 5번 중 3번 이상 성공할 확률.
    - **All@5**: 5번 모두 성공할 확률.
    - 평균 도구 오류율.
  - 리더보드에 Claude Fable 5, Opus 4.6·4.7, Sonnet 4.6, GPT-5.4·5.5, Gemini 3.x 가 올라 있다(날짜 미표기).
  - 뉴스룸 관찰: 단순 조작(파티클·점프력)은 잘하고, 문맥 추론(체력 재생 시스템, 사거리 신호등)은 pass@k 가 매우 낮다.
  - 논문은 "OpenGameEval: Benchmarking Agentic Programming and Exploration in a Stateful Game Engine"(NeurIPS 2026 목록)이다. 과제당 시도 수(16회 설), 84과제 설은 **미확인**이다.
  - 실행은 `invoke_eval.py`/REST 로 하고, LLM 제공자는 claude·gemini·openai 다. **외부 에이전트(Claude Code+MCP)를 그대로 넣는 경로는 README 에 없다(미확인).**
- **Roblox/luau_corpus** (Hugging Face, MIT): 2023 RDC 에서 발표한 공개 Luau 학습 데이터셋이다. 카드에 "범용 코드 LLM 을 미세조정하면 Roblox Lua 코드 품질이 10~20% 오른다"는 자체 주장이 있다(검증 불가).
- **Roblox 가 공개한 Luau 전용 코드 생성 모델은 찾지 못했다(미확인).** 커뮤니티 미세조정 모델(Qwen2.5-Coder-1.5B-Roblox, L0-Luau-1B 등)만 있다.

### 2.5 luau-lang 측
- `luau.org/llms.txt`, `llms-full.txt` 는 둘 다 404 다(curl 실측).
- `luau-lang/luau` 루트에 AGENTS.md 가 없고, CONTRIBUTING.md 에 AI·LLM 언급이 없다(grep 0건).
- 이슈 검색 "LLM OR AI-generated OR claude"는 8건이고, 정책 논의는 없다. 2026-07~08 에 결함 보고 몇 건이 자동 생성 글투이지만 판단은 하지 않았다.
- **luau-lang 의 공식 AI 정책·움직임은 찾지 못했다(미확인 = 없음으로 추정).** 관련된 변화는 `lute` v1.0(2026-04)과 Roblox 의 "Open Source Luau 확대"(2026-04, 출처가 저품질이라 미확인) 정도다.

### 2.6 luau-lsp 와 에이전트 통합
- luau-lsp 릴리스 노트 1.53.0~1.70.1(2025-07~2026-09-27)에 AI·agent·MCP 언급은 0건이다(GitHub API 로 훑음). 1.55.0 의 `--output-mode=json` 은 다른 기능의 출력 형식이다.
- Claude Code 공식 마켓의 `lua-lsp` 플러그인은 **Lua 전용**이다.
- 서드파티 이슈 보고: Claude Code 가 `.lsp.json` 서버를 띄울 때 `rootUri` 를 넘기지 않아 프로젝트 설정을 못 찾는다(lua-language-server 사례, claudeissues #27220, 미검증).
- **우리가 앞서 있다.** `luau-kb/.lsp.json` + `tools/luau-lsp.sh` + `--settings` 전달 실측, `validate` 가 못 잡는 키 오류(`checkers.md` §6)까지 기록했다. 공개된 luau-lsp 용 Claude Code 플러그인은 찾지 못했다. `rootUri` 문제가 우리 래퍼에도 해당하는지는 **미확인**이다(래퍼가 cwd 로 설정을 찾는다면 영향이 없다).

## 3. 커뮤니티

### 3.1 Luau·Roblox 스킬·rules 모음
| 모음 | 내용 | 평가 방식 | 우리와 대조 |
|---|---|---|---|
| `TabooHarmony/roblox-brain` (MIT, audit 02 에서 최신 커밋 2026-10-14) | 스킬 29개(core 10, gameplay 10, design 5, tools 4), AGENTS.md, `roblox-studio-mcp`·`roblox-tooling` 포함 | `validate_skills.py`, unittest, **`verify_api_drift.py`·`verify_source_urls.py`·`verify_version_pins.py`**. 트리거·효과 eval 은 없음 | 범위가 게임 개발(디자인·수익화)에 넓다. **API 드리프트·출처 URL 검사 스크립트는 우리 references 의 "문서 근거" 인용 검사로 빌릴 만하다** |
| `stackfox-labs/luau-skills` (MIT, `npx skills add`) | luau-core·luau-types·luau-performance + roblox-* (집계 사이트마다 6~9개) | 표시 없음 | 이름이 겹친다(luau-types). 실측 근거 표기는 없음(미확인) |
| `gamedev-skills/awesome-gamedev-agent-skills` `roblox-luau` (Apache-2.0) | 서비스·Instance·이벤트·서버/클라 분리 단일 스킬 | 없음 | 입문 수준 |
| `nonlooped/roblox-suite` | 하위 스킬 허브(DataStore, 애니메이션, Open Cloud, MCP 등) | 없음 | — |
| 서드파티 MCP: `boshyxd/robloxstudio-mcp`(npm), Chrrxs 포크, `hope1026/roblox-mcp`, 유료 Ropilot 등 | Studio 조작, 런타임 디버깅, 멀티플레이 테스트 | — | 공식 내장 MCP 가 생긴 뒤로는 쓸 이유가 줄었다 |

- **공개 모음 중 트리거 발동률이나 with/without 효과를 실측해 공개한 것은 찾지 못했다.** 실측 스니펫과 버전 행렬로 주장을 묶은 곳도 없다. luau-kb 의 "주장 하나에 스니펫 하나, 두 버전 검증" 방식은 차별점이다.

### 3.2 roblox-ts 진영
- roblox-ts 를 지지하는 근거는 TypeScript 의 강한 정적 검사다. 예를 들어 `FindFirstChild` 가 `Instance | undefined` 를 돌려주므로 nil 처리를 강제한다(lastlevel 블로그, 날짜 미표기). 약점은 Studio 런타임 에러가 컴파일된 Luau 를 가리킨다는 점이다.
- 스킬로는 `christopher-buss/skills` 의 `roblox-ts` 가 있다(tessl 등록부, 내용 미열람).
- **에이전트가 roblox-ts 에서 Luau 보다 낫다는 실측은 찾지 못했다(미확인).** 일반 TS 에 대해 Armin Ronacher(2025-08-04)는 "타입 검사를 루프에 넣으면 오히려 성능이 떨어졌다"고 적었다. 1인 관찰이다.
- 사용자 저장소는 모두 Luau 라 지금 영향은 없다. 다만 "타입 검사를 에이전트 루프에 넣는 것이 늘 이득은 아니다"라는 관찰은 luau-verify 의 게이트 설계와 함께 볼 만하다.

### 3.3 회고(DevForum 등)
- **"3 months building an AI plugin — lessons learned"** (DevForum, 2026-04-11):
  - Claude 에게 바로 물었더니 Instance API 를 "constantly" 지어냈다. 예: `workspace.CurrentCamera:SetField()`.
  - DevForum·creator-docs·오픈소스에서 뽑은 코드 조각 2,000개로 RAG 를 붙였더니 환각이 "~90% 줄었다"고 한다. **측정 방법은 공개하지 않았다.**
  - 한 번에 크게 생성하지 않고 8~15단계의 작은 도구 호출로 나누자 중간 복구가 쉬워졌다.
  - "데이터 500조각 추가가 모델 교체보다 효과가 컸다."
- **Lux 플러그인 글**(DevForum): 에이전트가 스크립트를 편집할 때 파괴적이었다(날짜 미확인).
- Cursor 튜토리얼(2025)과 "Leveraging AI" 글은 설계는 Claude, 구현은 Copilot 으로 나누라고 한다. 일화 수준이다.
- 학습 저해를 호소한 글도 있다(AI advice for code).
- **체계적으로 측정한 커뮤니티 회고는 찾지 못했다.** Claude Code + Rojo + luau-lsp 조합의 DevForum 회고도 찾지 못했다(미확인).

### 3.4 에이전트가 Luau 에서 흔히 틀리는 것과 luau-kb 범위
근거 등급: [공식] Roblox 문서, [포럼] DevForum, [우리] luau-kb 스니펫·references, [추론] 위 자료로 미루어 본 것.

| 오류 유형 | 예 | 근거 | luau-kb 에 있나 |
|---|---|---|---|
| 옛 전역 | `wait()`, `spawn`, `delay` → `task.*` | [공식] deprecated.md "Deprecated Functions (15)" | 부분. `tasks-and-threads.md`, `signals-and-events.md` §(재개 지점)에 흩어져 있고, "쓰지 말 것" 규칙은 rules 에 없다 |
| **`spawn → task.spawn` 1:1 치환** | 공식 목록은 Replacement 를 `task.spawn()` 으로 적는다. DevForum(task 라이브러리 공지 스레드)은 옛 `spawn` 이 다음 프레임에 돌므로 **`task.defer` 가 더 가깝다**고 한다 | [공식]↔[포럼] 충돌 | **없음.** 공식 문서와 실측이 어긋난 사례로 올릴 후보다(Studio 확인 필요) |
| 옛 API | `Humanoid:LoadAnimation` → `Animator:LoadAnimation`, `FindPartOnRay*` → `WorldRoot:Raycast`, camelCase 변형(`brickColor`, `:connect`) | [공식] deprecated.md | **없음**(LoadAnimation 0건, FindPartOnRay 0건) |
| 레거시지만 deprecated 표시가 없는 것 | `BodyVelocity`/`BodyGyro`(목록에는 camelCase 속성만 있음) → 제약(LinearVelocity 등) | [공식] 목록에 클래스가 없음, [추론] | 없음 |
| API 환각 | 없는 메서드·속성(`CurrentCamera:SetField()`) | [포럼] | 부분. `luau-lsp --platform=roblox` + 정의 파일이 strict 에서 잡는다(`luau-roblox` api-types). "생성 코드를 반드시 이 검사로 거른다"는 절차와 그것을 보여 주는 음성 대조 스니펫은 없다 |
| 엔진 API·Open Cloud 혼동 | 게임 스크립트에서 REST 엔드포인트를 부름 | [공식] llms.txt 경고 | 부분(roblox-net 이 Open Cloud 를 다룸). 경고 문장은 없다 |
| Lua 5.x 습관 | `table.getn`/`foreach`, `setfenv`/`getfenv`, `goto`, ephemeron 가정, `assert` 메시지 모양 | [공식] deprecated.md, [우리] | 대부분 있다(`gc-and-weak-tables` 의 ephemeron, `pitfalls`, `optimize-levels` 의 getfenv). `goto` 0건 |
| 새·옛 솔버 차이 | 옛 솔버 관습 코드가 새 솔버에서 거짓 에러를 내거나 그 반대 | [포럼] New Type Solver 버그 스레드 다수, [우리] | **강하다**(`solver-limits.md`, 버전 행렬). 외부 모음보다 앞선다 |
| 새 문법 과신 | `if local`·`class` 를 CLI 에서 되니 쓴다 | [우리] audit 13 | **있다**(luau-upstream 4조건 표) |
| 클라·서버 신뢰 경계 | 원격 인자를 검사하지 않는다 | roblox-brain 이 중시 | 있다(roblox-net §1·§5) |
| 파괴적 편집 | 스크립트 전체를 덮어씀 | [포럼] Lux | 부분. `studio-mcp.md` 의 상태 변경 도구 규칙. 편집 전 스냅샷·git 지침은 없다 |

## 4. 대조 결론
- **우리가 앞선 것**:
  - 타입 솔버 한계를 버전 행렬과 함께 실측했다.
  - 검사기와 런타임 사이 require 판정, `-O2`·native 가 에러 위치를 바꾸는 점, Studio MCP 의 실제 도구 스키마를 기록했다.
  - luau-lsp 를 Claude Code LSP 로 붙였다.
  - 트리거와 준수율을 실측했다.
  - 공개 모음 어느 것도 이 수준의 근거 표기를 하지 않는다.
- **빠진 것** (§0 의 3개와 같다):
  - (1) 에이전트 오류 카탈로그. deprecated.md 를 생성 코드 검사에 쓰고, `spawn`/`task.defer` 를 정정한다.
  - (2) 공식 에이전트 경로의 최신 상태: Script Sync, `subagent` playtest, 입력 시뮬레이션, `open_cloud_invoke` 권한, Assistant skill 이식성, 보관된 rust 서버.
  - (3) 회귀 평가 자산: `evals/`, 오발동 질문, 외부 벤치 연결.
- 반영 위치 제안(사용자 확인 뒤, luau-kb 는 이 세션에서 읽기 전용):
  - (1) `luau-style/references/pitfalls.md` 또는 새 reference `roblox-docs/references/deprecated-scan.md` + `roblox_docs.py deprecated <파일>` 하위 명령. rules `luau-core.md` 에 "`wait/spawn/delay` 금지, `task.*` 사용" 한 줄.
  - (2) `luau-roblox/references/studio-mcp.md` §2 문장 정정과 §7 Script Sync 신설.
  - (3) luau-kb `evals/`.

## 5. 평가 방법론

### 5.1 외부 방법 비교
| 방법 | 표본·반복 | 판정 | 격리 | 우리에게 주는 것 |
|---|---|---|---|---|
| **skill-creator** description 최적화 (`run_eval.py`·`run_loop.py`, 로컬 플러그인 사본) | 질문 **20개(발동 8~10 + 비발동 8~10, near-miss 위주)**, 질문당 **3회**, 발동률 ≥ 0.5 를 통과로 봄. **60/40 train/test 로 나누고, 최대 5번 반복한 뒤 test 점수로 고른다** | stream-json 에서 `content_block_start` 를 보고 Skill 발동을 일찍 감지 | `claude -p` 서브프로세스(사용자 설정은 그대로 걸림) | 오발동 질문, train/test 분리로 과적합 방지 |
| skill-creator 효과 벤치 (`aggregate_benchmark.py`) | with-skill 과 baseline 을 같은 턴에 병렬로 돌림 | 단언 통과율의 mean·stddev·min·max. analyzer 가 "늘 통과하는 단언(변별력 없음)"과 고분산 eval 을 찾음 | 서브에이전트 | 변별력 없는 항목 제거 |
| **`claude plugin eval`** (2.1.316 `--help`, `code.claude.com/docs/en/plugin-evals`) | 케이스당 **3회가 기본**(`--runs`), with·without 두 팔, `-j` 최대 8 | grader 6종. regex, tool_used(`input_match`, `min`/`max`), tool_order, file_exists 는 무료. llm, baseline 은 judge 를 쓰고 기본 judge 는 haiku 다(사용자 규칙상 `--judge-model sonnet` 을 고정해야 함). **`tool_used: Skill` 은 두 팔 실행에서 점수 밖의 표시로만 남는다**. 비발동 검사는 `min: 0, max: 0, arm: both` | **임시 HOME·cwd. 사용자 CLAUDE.md, 훅, rules, 다른 플러그인, 메모리가 로드되지 않는다.** Bash 는 OS 샌드박스 안에서 돈다 | 사용자 CLAUDE.md 혼입 제거, Δ 자동 계산, CI 종료 코드, `--max-cost-usd` |
| promptfoo `anthropic:claude-agent-sdk` | `--repeat N` | `skill-used` 단언(Skill 호출을 `metadata.skillCalls` 로 정규화), `trajectory:tool-used`, `trace-span-count` | `setting_sources` 로 설정 로드 여부 지정, `plugins` 로 로컬 플러그인 | 다른 모델·하네스(Codex)와 같은 판정으로 비교할 때. 우리에겐 plugin eval 과 겹친다 |
| Scott Spence 발동 실측 (2026-02-08) | 22 프롬프트 × 2회, near-miss 24개 × 1회. Sonnet 4.5, `--max-turns 1`, 20초 제한. 약 250회 호출에 $5.59(**회당 약 $0.022**) | stream-json `Skill()` | Daytona 샌드박스 | **같은 설정을 다시 돌려도 기준선이 5%p 흔들렸다.** 강제 평가 훅은 100%/100% 였지만 어려운 세트에서는 75% 였다 |
| OpenGameEval | 과제당 5회 이상 | **pass@1, pass@5, cons@5(5번 중 3번 이상), all@5**, 도구 오류율. 실행 가능한 edit/play 검사 | Studio 세션 | 규칙 준수처럼 "매번" 지켜야 하는 것은 all@k 로 본다 |
| Anthropic "Adding Error Bars to Evals" (arXiv 2411.00640, 2024-11) | — | CLT 표준오차. **관련된 질문 묶음은 clustered SE**(순진한 SE 의 3배 넘게 커질 수 있음). CoT 가 있으면 **질문마다 여러 번 표본을 뽑아 평균을 낸다**. 두 조건 비교는 **짝지은 차이**로 한다 | — | 보고 규칙의 근거 |
| bestagent.dev 의 plugin eval 실측 (2026-09-13) | 3 케이스 × 3회 × 2팔 = 18회, $1.79 | — | — | (a) grader 가 스킬 본문과 맞는지만 보면 **낡은 답이 1.00** 을 받는다. 정답은 날짜와 출처가 있는 값으로 채점한다. (b) Δ=0 이어도 스킬을 켜면 비용이 56~84% 늘었다. 비용과 턴 수를 같이 본다. (c) Skill 발동 표시는 threshold 게이트에 걸리지 않는다. CI 에서 따로 확인한다 |

### 5.2 지금 우리 실측의 통계적 강도
95% Wilson 구간(로컬 계산):

| 결과 | 구간 | 읽기 |
|---|---|---|
| 트리거 47/50 | 0.84–0.98 | 표본 50이지만 질문 25개 × 2회라 **질문 단위로 묶여 있다**. 같은 질문의 두 회 상관 ρ 를 0.6 으로 잡으면 유효 n 은 약 31 이고, 하한은 0.80 언저리까지 내려간다 |
| 짧은 description 43/44 대 긴 description 44/44 | 0.88–1.00 대 0.92–1.00 | **구별할 수 없다.** 짧은 쪽을 고른 근거는 발동률이 아니라 상시 문맥 비용(토큰)이어야 하고, 실제로 그렇게 적혀 있다. 맞는 판단이다 |
| 스킬 넷 23/26 | 0.71–0.96 | 여섯 개 안과 구간이 겹친다. "넷이 더 나쁘다"는 방향만 말할 수 있다 |
| 경계 트리거 16/16 | 0.81–1.00 | 0건 실패여도 3의 법칙으로 실패율 상한은 약 19% 다 |
| 준수율 12/12, 11/12 (조건당 2회) | 조건당 n=2 → 한 항목이 2/2 여도 0.34–1.00 | 조건 사이의 "11 대 12" 차이는 **잡음과 구별할 수 없다.** 문서도 "방향만 본다"고 이미 적었다. 2/2 대 0/2 처럼 극단인 항목(`-O2` 실행, 에러 줄 단언, 검증 범위 구분)만 신호로 볼 만하다 |

차이를 잡는 데 필요한 반복 수(양측 α=0.05, 검정력 0.8, 독립 표본 기준):

| 비교 | 팔당 n |
|---|---|
| 0.2 대 0.8 (스킬이 행동을 뒤집는 경우, 예: `-O2` 실행) | 10 |
| 0.5 대 0.9 | 20 |
| 0.9 대 0.6 | 32 |
| 0.95 대 0.80 (description 개선 판정) | 76 |
| 0.95 대 0.85 | 141 |

- 같은 질문으로 짝지어 비교하면 필요한 n 이 줄지만, 0.95 근처의 미세 조정은 여전히 수십 회 단위가 든다. **description 미세 조정을 실측으로 판정하는 것은 비용 대비 이득이 낮다.** 큰 효과(스킬 유무, 문구가 행동을 뒤집는지)만 실측으로 판정하는 것이 맞다.
- 통계 외의 혼입 요인:
  - (a) 사용자 CLAUDE.md 와 rules 가 모든 조건에 걸린다(v2 사례).
  - (b) 모델과 Claude Code 버전이 고정 기록만 되고 다시 돌릴 때 바뀐다.
  - (c) **발동해야 하는 질문만 있어서 오발동(거짓 양성)을 재지 않았다.** 스킬 12개가 서로 경쟁하므로 "엉뚱한 스킬이 먼저" 같은 실패는 잡지만, "Luau 와 무관한 질문에 luau-* 가 발동" 같은 실패는 보이지 않는다.
  - (d) 채점 정규식의 거짓 양성을 손으로 고쳤다. 재현할 수 없다.

### 5.3 비용 감각
- 트리거 1회는 `--max-turns 2` 에 도구가 읽기뿐이라 회당 몇 센트로 본다. Spence 의 Sonnet 4.5, max-turns 1 기준이 회당 약 $0.022 이고, 우리 값은 **미기록이라 미확인**이다. 40질문 × 3회 = 120회면 약 $3~6 으로 추정한다.
- 준수율 과제 1회는 $0.11~0.31(우리 실측)이다. plugin eval 은 두 팔이라 2배다. 과제 3개 × 3회 × 2팔 = 18회면 약 $3~6 이다.

### 5.4 비용 대비 개선안 (싼 순)
1. **보고 규칙** (비용 0)
   - RESULTS.md 의 실측 표에 Wilson 구간을 붙인다. 질문 × 반복 구조면 "질문 n=25, 반복 2"를 따로 적는다.
   - n<10 인 비교는 "방향만"으로 표기한다. 이미 하는 관행을 규칙으로 만든다.
   - 반드시 지켜야 하는 규칙(`@self`, `--!strict`)에는 OpenGameEval 처럼 **all@k** 를 함께 적는다.
   - 적응형 반복: 기본 3회를 돌리고, 실패가 하나라도 있는 질문만 5회를 더 돌린다. 실패 질문에 반복이 몰리므로 같은 비용으로 실패 원인을 더 잘 본다.
2. **트리거 세트 확장과 train/test** (약 $3~6/회)
   - `questions.json` 에 비발동 near-miss 15개를 더한다. 예:
     - Lua 5.4 의 `goto` 질문
     - TypeScript 제네릭 질문
     - Python 성능 질문
     - "Roblox 게임 아이디어 추천"
     - mise 일반 사용법
     - 스킬끼리 경계가 겹치는 질문(roblox-docs 대 roblox-engine)
   - 기대값 `[]` 로 "아무 luau-kb 스킬도 먼저 불리지 않음"을 판정한다.
   - 3회씩 돌린다.
   - description 을 고칠 때는 skill-creator `run_loop.py` 처럼 60/40 으로 나누고 test 점수로 고른다. 25문항에 맞춘 과적합을 막는다.
3. **효과 측정을 `claude plugin eval` 로 옮긴다** (약 $3~6/회)
   - luau-kb 에 `evals/<case>/{prompt.md,graders/*.md}` 를 둔다. 빈 패키지는 `scaffold_script` 로 만들고 `--scaffold` 를 쓴다(우리가 쓴 케이스뿐이므로 허용).
   - grader 는 무료 위주로 한다:
     - regex: 산출 파일에 `--!strict`, `@self`, `pcall(f(` 이 없는지
     - `tool_used Bash input_match "-O2"`
     - `tool_used Skill` 발동 표시
     - 비발동 케이스는 `max: 0, arm: both`
   - `--model sonnet`, `--judge-model sonnet`(llm grader 를 쓸 때), `--max-cost-usd`, Claude Code 버전을 기록한다.
   - 격리 덕분에 사용자 CLAUDE.md 혼입이 사라지고 with/without Δ 가 자동으로 나온다.
   - 대신 **실제 환경**(`~/.claude/rules` symlink, 사용자 CLAUDE.md 와의 상호작용)은 재지 못한다. 지금의 `claude -p` 2회 실측은 "실제 환경 확인"으로 남겨 둔다.
   - grader 는 스킬 본문이 아니라 **스니펫이 검증한 사실**에 맞춰 쓴다. bestagent 가 본 "낡은 답 1.00" 함정을 피하기 위해서다.
   - Δ=0 인 케이스는 `aggregate-result.json` 의 비용과 턴 수로 판정한다.
4. (선택, 비쌈) **roblox-* 스킬의 엔진 주장은 OpenGameEval 형식으로.** 이 머신의 Studio MCP 에서 `execute_luau` + play 모드 검사로 작은 과제 몇 개를 만들어 스킬 유무를 비교한다. Studio 는 사람이 띄워 공유하는 창이라(D-03) 반복 게이트로는 맞지 않는다. 분기에 한 번 정도 수동으로만 돌릴 만하다.

## 6. 출처
| 출처 | 날짜 | 쓴 곳 |
|---|---|---|
| https://about.roblox.com/newsroom/2026/04/roblox-studio-going-agentic | 2026-04-15 | §2.1 |
| https://create.roblox.com/docs/en-us/assistant/skills.md | last_updated 2026-11-10 | §2.1 |
| https://create.roblox.com/docs/en-us/assistant/mcp.md | last_updated 2026-11-10 | §2.1, §2.2 |
| https://create.roblox.com/docs/studio/mcp.md | last_updated 2026-11-10T00:40:51Z | §2.2 |
| https://create.roblox.com/docs/en-us/studio/mcp-open-cloud.md | last_updated 2026-11-10 | §2.2 |
| https://github.com/Roblox/studio-rust-mcp-server | archived 2026-04-03 | §2.2 |
| https://devforum.roblox.com/t/introducing-the-open-source-studio-mcp-server/3649365 | 날짜 미열람 | §2.2(검색 결과만) |
| https://create.roblox.com/docs/llms.txt | 조회 2026-11-10(날짜 미표기) | §2.3 |
| https://create.roblox.com/docs/reference/engine/deprecated.md | "build time 생성", 조회 2026-11-10 | §2.3, §3.4 |
| https://create.roblox.com/docs/en-us/ai/coding-harness.md | last_updated 2026-11-10 | §2.3 |
| https://about.roblox.com/newsroom/2025/12/opengameeval-benchmark-agentic-ai-assistants-roblox-studio | 2025-12-17 | §2.4 |
| https://github.com/Roblox/open-eval (→ open-game-eval), `LLM_LEADERBOARD.md` | 날짜 미표기 | §2.4, §5.1 |
| https://neurips.cc/virtual/2026/166905 | NeurIPS 2026 | §2.4(제목만) |
| https://huggingface.co/datasets/Roblox/luau_corpus | 2023 발표(RDC) | §2.4 |
| https://devforum.roblox.com/t/empower-luau-creation-public-luau-dataset-initiative-needs-your-help/2711493 | 2023-12-05 갱신 | §2.4 |
| https://luaubench.pages.dev/methodology | 날짜 미표기 | §0(언급) — 4트랙 가중(로직 35, 버그 35, 타입 15, 실행 15), 과제당 3회. 과제 수·라이선스는 미확인 |
| https://torpedosoftware-roblox-llm-leaderboard.static.hf.space/index.html | 날짜 미확인 | 검색 결과만(RobloxQA v2.0: Leetcode 208문항을 Luau 로 옮김) |
| luau.org/llms.txt (404), luau-lang/luau CONTRIBUTING.md, GitHub 이슈 검색 API | 조회 2026-11-10 | §2.5 |
| GitHub API `JohnnyMorganz/luau-lsp/releases` | 1.53.0–1.70.1 (2025-07-26 ~ 2026-09-27) | §2.6 |
| https://claude.com/plugins/lua-lsp | 날짜 미표기 | §2.6 |
| https://claudeissues.com/issue/27220-lsp-plugins-dont-receive-workspace-root-rooturi-breaking-luarc-json-discovery | 날짜 미확인 | §2.6(미검증) |
| https://cdn.jsdelivr.net/gh/tabooharmony/roblox-brain@main/README.md | 날짜 미표기(audit 02: 커밋 2026-10-14) | §3.1 |
| https://skills.sh/stackfox-labs/luau-skills , https://gh.r-mj.com/stackfox-labs/luau-skills | 날짜 미표기 | §3.1 |
| https://www.skills.sh/gamedev-skills/awesome-gamedev-agent-skills/roblox-luau | 날짜 미표기 | §3.1 |
| https://skillselion.com/skills/nonlooped/roblox-suite/roblox-mcp | 날짜 미표기 | §3.1 |
| https://lastlevel.pages.dev/blog/why-we-use-typescript-instead-of-luau | 날짜 미표기 | §3.2 |
| https://devforum.roblox.com/t/luau-vs-typescript-roblox-ts-for-production-roblox-games/4757257 | 미열람 | §3.2(검색 결과만) |
| https://lucumr.pocoo.org/2025/8/4/shitty-types/ | 2025-08-04 | §3.2 |
| https://devforum.roblox.com/t/i-spent-3-months-building-an-ai-plugin-that-generates-whole-systems-inside-studio-%E2%80%94-lessons-learned/4569684 | 2026-04-11 | §3.3 |
| https://devforum.roblox.com/t/lux-cursorclaude-code-but-for-roblox-free-plugin/4207506 | 미열람(검색 요약) | §3.3 |
| https://devforum.roblox.com/t/task-library-now-available/1387845 (페이지 다수) | 2021~ | §3.4 `spawn`/`task.defer` |
| https://devforum.roblox.com/t/new-type-solver-beta/3155804 외 새 솔버 버그 스레드 | 2024~2026 | §3.4 |
| `claude plugin eval --help`, `claude plugin eval init --help` (Claude Code 2.1.316, 로컬) | 2026-11-10 | §5.1 |
| https://code.claude.com/docs/en/plugin-evals.md | 조회 2026-11-10 | §5.1 |
| 로컬 `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/{SKILL.md,scripts/run_eval.py,scripts/aggregate_benchmark.py}` | 로컬 사본 | §5.1 |
| https://www.promptfoo.dev/docs/providers/claude-agent-sdk/ , https://promptfoo.dev/docs/usage/command-line | 날짜 미표기 | §5.1 |
| https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals | 2026-02-08 | §5.1, §5.3 |
| https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably | 날짜 미열람 | §5.1(84%·20% 원 수치, Haiku 4.5 합성 호출) |
| https://bestagent.dev/claude-plugin-eval-measured-2026 | 2026-09-13 | §5.1 |
| https://arxiv.org/abs/2411.00640 , https://www.anthropic.com/research/statistical-approach-to-model-evals | 2024-11 | §5.1, §5.2 |

## 7. 확인하지 못한 것
- OpenGameEval 논문의 과제 수(84)와 과제당 시도 수(16). 리더보드 갱신일. 외부 에이전트(Claude Code + 내장 MCP)를 하네스에 그대로 넣을 수 있는지.
- 문서에 실린 Assistant skill 9개와 이 머신 MCP 의 13개가 다른 이유(버전 차이인지, 문서 지연인지).
- `spawn` 과 `task.spawn`/`task.defer` 의 실제 재개 시점 차이. Studio 실측이 필요하다(roblox-engine 후보).
- Claude Code `.lsp.json` 의 `rootUri` 문제가 luau-kb 래퍼에도 해당하는지.
- `claude plugin eval` 이 플러그인의 `.lsp.json`(LSP 도구)을 격리 실행에서도 띄우는지. 문서는 "plugin 만 로드"라고만 쓴다.
- 우리 트리거 실측의 회당 비용(기록 없음).
- roblox-ts 와 Luau 의 에이전트 성공률 비교 실측. DevForum 에서 Claude Code + Rojo + luau-lsp 조합 회고.
- luau-lang 쪽 AI 정책. 공개된 것은 찾지 못했다. 비공개 논의는 알 수 없다.
- stackfox-labs/luau-skills 의 실제 스킬 수와 근거 표기 방식(집계 사이트마다 숫자가 다름, 저장소 미열람).
