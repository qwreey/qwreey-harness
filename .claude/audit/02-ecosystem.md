# 02. 생태계 조사: 이미 있는데 못 쓰는 공식/커뮤니티 자산

작성일 2026-11-10. 읽기 전용 조사(다른 프로젝트 수정 없음).
확인 방법 표기: **열람** = 실제 파일/도구 출력을 직접 읽음, **fetch** = WebFetch 요약(원문 전체 아님), **검색** = 검색 결과 요약만.

## 0. 로컬 툴체인 실측 (대조 기준)

| 항목 | 관찰 (열람) | 시사점 |
|---|---|---|
| 툴체인 관리 | 전 프로젝트 `mise.toml` (quad는 rokit에서 2026-08-19 mise로 전환). Rokit/Aftman/Wally 파일 없음. 패키지는 **pesde 0.7.4** (`pesde.toml`/`pesde.lock`: quad, stl-luau, tbox) | Rokit/Aftman/Wally 항목은 "참고용"일 뿐 도입 대상 아님 |
| 핀 | luau: quad/devplorer/table-sim 0.734, **stl-luau 0.742**, tbox 0.734. luau-lsp: quad 1.70.1, devplorer/tbox 1.69.0, stl-luau 1.70.1. rojo 7.7.0. stylua 2.5.2(stl-luau, tbox, table-sim) | 프로젝트마다 핀이 다름. table-sim 주석은 "형제가 올릴 때 같이 올린다"는 수동 규약. 올림 절차를 스킬화하면 가치 있음 |
| 린터 | selene은 stl-luau에서 2026-09-21 폐기(`const` 파싱 불가, 0.31.0이 최신). 린트는 `.luaurc`의 `lint: {"*": true}` + luau-analyze | selene 항목 불필요 |
| 런타임 | lune은 의도적으로 제외(`const` 미지원). tbox만 lute 1.0.0 + darklua 0.19.0 사용. 전역 mise에는 lune 0.10.5가 있음 | `const`를 쓰는 프로젝트군에서 Lune 기반 도구는 전부 막힘 |
| `.luaurc` | 모두 `languageMode: strict` + `lint: *`. mrow만 `LocalShadow:false`, quad/quad-changelog-check만 aliases | 거의 균일 |
| stylua.toml | `syntax="Luau"` 공통. **들여쓰기 불일치**: tbox/rbvm=Spaces, 나머지=Tabs. `call_parentheses`: stl-luau=Always, 나머지=Input. tbox/rbvm만 `sort_requires`+`block_newline_gaps` | 스캐폴딩 표준화 1순위 지점 (아래 D절) |
| 에디터 | `.vscode/settings.json`에 `enableNewSolver:true` + FFlag override(stl-luau는 4개 한도 확장). quad/stl-luau 등 7개 프로젝트에 존재 | CLI(`luau-analyze`)는 정수 FFlag를 못 받는다고 기록돼 있음. 에디터/CLI 진단 불일치가 알려진 함정 |
| `default.project.json` | 6개 프로젝트 확인. `servePlaceIds`는 table-sim, devplorer만 있음. rbvm/stl-luau는 2칸 들여쓰기, 나머지는 탭 | 스캐폴드 시 servePlaceIds 유무 결정 규칙 필요 |
| 프로젝트 스킬 | `delegate-agy`(quad, stl-luau, tbox), `quad-ui-dev`(table-sim)뿐. 프로젝트당 `.claude/`에 base/conventions/todos 등 문서 체계가 매우 큼 | 스킬 거의 없음 = 문서 체계가 스킬 대신 CLAUDE.md 쪽에 쌓여 있음 |
| 플러그인 | `/code/.claude/plugins/installed_plugins.json`의 plugins = **{} (설치 0개)**. marketplace `claude-plugins-official`만 등록(로컬 클론 존재). settings에는 `cc-plugin-you-should-know@builtin`만 활성 | 아래 A절은 전부 "미설치" 상태 |

## A. Claude Code 공식 마켓플레이스 / anthropics/skills

공식 마켓플레이스의 실제 파일을 `/code/.claude/plugins/marketplaces/claude-plugins-official/`에서 직접 열람함(plugin.json, 디렉터리 구성).
설치: `/plugin install <이름>@claude-plugins-official`. anthropics/skills는 `/plugin marketplace add anthropics/skills` 후 `/plugin install document-skills@anthropic-agent-skills` (fetch).

| 이름 | 용도 | URL | 확인 | 이 사용자 가치 / 근거 | 권고 |
|---|---|---|---|---|---|
| skill-creator | 스킬 작성, 평가(evals), 벤치마크, description 최적화 | https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator | 열람(plugin.json). 동일 이름의 `anthropic-skills:skill-creator`가 이 세션 스킬 목록에 이미 있음 | **상.** 프로젝트 스킬이 `delegate-agy` 등 4개뿐이고, 스캐폴딩/버전 올림 같은 반복 절차를 스킬로 만들려는 목적에 정확히 맞음. 이미 가용하므로 설치 비용 0 | 즉시 |
| plugin-dev | 플러그인/스킬/훅/MCP/에이전트 개발 가이드 7개 스킬 + agent-creator, plugin-validator, skill-reviewer 에이전트 | .../plugins/plugin-dev | 열람 | **중.** 스킬 여러 개를 하나의 플러그인(예: `luau-toolchain`)으로 묶어 프로젝트 간 공유하려면 필요. 프로젝트별 `.claude/skills` 복붙 대신 단일 소스가 됨 | 검토 (스킬이 3개 이상 되면) |
| claude-md-management | CLAUDE.md 품질 감사(claude-md-improver 스킬) + `/revise-claude-md` | .../plugins/claude-md-management | 열람 | **중-상.** CLAUDE.md와 `.claude/base`, `conventions`, `todos`가 프로젝트마다 크게 자람. 감사/정리 도구로 쓸 만함. 다만 이 사용자의 구조(`.claude/` 문서 체계)는 표준 CLAUDE.md 하나를 가정한 도구와 안 맞을 수 있어 먼저 한 프로젝트에서 시험 | 검토 |
| hookify | 대화 패턴에서 방지 규칙(훅) 생성, `/hookify`, `/hookify:list` | .../plugins/hookify | 열람 | **중.** 사용자가 이미 훅을 쓰는 곳(quad/table-sim `<비공개>`)이 있어 직접 작성 가능. "stylua `syntax` 누락 시 경고", "`const` 파일에 lune 실행 금지" 같은 규칙 생성엔 편함. 내가 직접 쓰는 것과 큰 차이는 없음 | 검토 |
| code-review (플러그인) | PR용 멀티 에이전트 리뷰, 신뢰도 점수 | .../plugins/code-review | 열람 | **하.** 세션에 내장 `code-review` 스킬이 이미 있음. 1인 개발이라 PR 흐름이 적음 | 불필요 |
| code-simplifier | 단순화 에이전트 | .../plugins/code-simplifier | 열람 | **하.** 내장 `simplify` 스킬과 중복 | 불필요 |
| lua-lsp | `lua-language-server` 연결, **확장자 `.lua`만** 매핑 | .../plugins/lua-lsp | 열람(plugin.json, README: `.lua`만) | **하.** 대상이 `.luau`가 아니고 Luau 문법(`const`, 타입 함수)을 못 읽음. **공식 Luau LSP 플러그인은 없음.** 직접 만들려면 plugin의 `lspServers`에 `luau-lsp`(확장자 `.luau`)를 지정하면 됨(lua-lsp의 plugin.json 구조를 그대로 본뜸) | 불필요 (자체 제작은 검토, 아래 요약 참고) |
| claude-code-setup | 코드베이스 분석 후 훅/스킬/MCP/서브에이전트 추천(claude-automation-recommender) | .../plugins/claude-code-setup | 열람 | **중.** 일회성 감사에 유용. 이 claude-doctor 작업과 목적이 겹침 | 검토 |
| commit-commands | `/commit`, `/commit-push-pr`, `/clean_gone` | .../plugins/commit-commands | 열람 | **하-중.** 기본 흐름으로 충분 | 불필요 |
| feature-dev | 탐색/설계/리뷰 3단계 기능 개발 워크플로 | .../plugins/feature-dev | 열람 | **하.** 사용자는 자체 `.claude/` 문서 체계와 위임 스킬로 운영 | 불필요 |
| session-report | `~/.claude/projects` 트랜스크립트로 토큰/캐시/서브에이전트/비싼 프롬프트 HTML 리포트 | .../plugins/session-report | 열람 | **중-상.** 문서량이 큰 프로젝트가 많아 컨텍스트 비용 진단에 직접 도움. claude-doctor 목적과 일치 | 즉시(진단 1회) |
| security-guidance | 편집 시 패턴 경고, Stop 시 diff 리뷰 | .../plugins/security-guidance | 열람 | **하-중.** Luau 위주라 매치되는 취약 패턴이 적음. 훅이 편집마다 돌아 비용 증가 | 불필요 |
| mcp-server-dev | MCP 서버 제작 스킬 | .../plugins/mcp-server-dev | 열람 | **하.** 지금 요구 없음 | 불필요 |
| document-skills(docx/pdf/pptx/xlsx) | 문서 파일 처리 | https://github.com/anthropics/skills | fetch (Apache-2.0 표기. 폴더별 확인 필요) | **하.** 이 사용자는 문서 산출물이 거의 없음. 일부는 이미 세션 스킬로 제공 중 | 불필요 |
| anthropics/skills 의 `template/`, `spec/` | 스킬 템플릿, Agent Skills 사양 | https://github.com/anthropics/skills | fetch | **중.** 직접 스킬을 쓸 때 frontmatter 규칙 확인용 | 검토 |
| external: serena | 심볼 단위 코드 탐색(LSP 기반) | .../external_plugins/serena | 목록만 열람, 내용 미확인 | Luau 지원 여부 미확인 | 검토 불가(미확인) |

비고: 인용한 정보 중 `.../plugins/<name>`은 모두 위 `claude-plugins-official/tree/main/plugins/` 경로 기준. 내용 미확인인 것은 위에 표시함.

## B. Roblox 공식 자산

| 항목 | 내용 | URL | 확인 | 가치 / 권고 |
|---|---|---|---|---|
| Studio MCP 내장 스킬 (`list_skills`) | **Studio 2개 연결됨**(devplorer, quad-test)을 확인하고 `list_skills` 호출. 내장 스킬 13개: `rbx-configs-experimentation`, `rbx-create-skill`, `rbx-debug`(브레이크포인트), `rbx-device-simulator-lua`, `rbx-docs-search`, `rbx-import-asset`, `rbx-instrument-analytics`, `rbx-network-simulator`, `rbx-open-cloud-usage`, `rbx-perf-profiling`(LibMP/MicroProfiler), `rbx-permissions`, `rbx-scene-analysis`, `rbx-unit-test` | 로컬 MCP | **열람** (스킬 본문은 `rbx-docs-search` 등 일부만 시도, 인자명이 `skill_name`) | **즉시.** 특히 `rbx-docs-search`(문서 조회를 `http_get`으로), `rbx-debug`, `rbx-unit-test`(ModuleScript 테스트), `rbx-perf-profiling`. 이 중 상당수는 devplorer/table-sim 같은 Studio 연동 프로젝트에 해당. 프로젝트 CLAUDE.md에 "Studio 작업 전 `list_skills` 호출" 한 줄이 필요한지 검토 |
| `rbx-create-skill` / `create_skill` / `edit_skill` | Studio 쪽 스킬 작성 도구. 공식 문서 `studio/mcp.md`는 `skill`만 언급하고 `create_skill`은 언급 안 함 | https://create.roblox.com/docs/studio/mcp.md | fetch + 로컬 도구 목록 | **검토.** 로컬 MCP에는 있으나 문서화되지 않은 기능. 안정성 보장 없음. 프로젝트 스킬은 Claude Code 쪽 SKILL.md가 이식성 면에서 낫다 |
| `rojo_sync_guide` | **열람.** `studio-sync` 명령(code-docker 쉘)이 프로젝트의 `rojo serve`를 한 번 띄워 동기화 후 종료. 소유권 `AgentOwner` 속성, 다중 Studio는 `--place <placeId>`, `--release`, `--list`. 확인은 `search_game_tree`/`studio-output -n 100 --no-follow` | (로컬 도구) | **열람** | **즉시.** MCP 도구로 파일을 재생성하지 말라는 규칙이 명시돼 있음. `servePlaceIds`가 있는 프로젝트(table-sim, devplorer)는 `--place` 없이 자동 선택됨. 없는 프로젝트(quad 등)는 Studio가 둘 이상이면 거부되므로 스캐폴딩에서 `servePlaceIds`를 넣는 근거가 됨 |
| Roblox 문서 `llms.txt` | **있음**: `https://create.roblox.com/docs/llms.txt`. 2,335페이지 인덱스(약 187KB). 상단에 에이전트용 지침: "URL을 추측하지 말 것", 문서 URL에 `.md`를 붙이면 마크다운, 404는 경로가 틀린 것, 검색은 `q` 파라미터, 전체 텍스트 파일은 한 번에 읽지 말 것. 하위 인덱스: `/docs/reference/engine/llms.txt`(엔진 API), `/docs/cloud/llms.txt`(Open Cloud) | https://create.roblox.com/docs/llms.txt | fetch(앞 100KB만 읽음) | **즉시.** 프로젝트 CLAUDE.md에 "Roblox API는 추측 말고 llms.txt/`.md`로 확인" 규칙을 넣을 근거 |
| Roblox/creator-docs 저장소 | 문서 원본. 산문 CC-BY-4.0, 코드 샘플 MIT. 루트에 `llms.txt`, `AGENTS.md` **없음**(llms.txt는 사이트에서 제공). `content/en-us/ai` 존재 여부는 미확인 | https://github.com/Roblox/creator-docs | fetch | **검토.** 오프라인 grep용 클론으로는 유용 (`content/en-us/luau/type-checking.md` 경로는 roblox-brain 소스에서 확인) |
| AI 관련 공식 문서 | `/docs/en-us/ai/accelerated-workflows.md`, `build.md`, `build-with-assistant.md`, **`coding-harness.md`** | https://create.roblox.com/docs/en-us/ai/coding-harness.md | fetch | **검토.** coding-harness는 **Script Sync(베타) + MCP** 조합을 안내하며 Rojo/스킬/AGENTS.md는 다루지 않음. 이 사용자는 Rojo 기반이라 직접 적용할 내용은 적음. 단 Script Sync가 `StarterGui/StarterPack`은 못 다루고 MCP가 대신한다는 점은 참고 |
| 공식 Studio MCP 서버(내장) | Assistant → Manage MCP Servers에서 활성화. 문서화된 도구: script_read/multi_edit/script_search/script_grep, generate_*, search_game_tree, inspect_instance, execute_luau, get_studio_state, start_stop_play, get_console_output, screen_capture, user_*_input, http_get, skill, list_roblox_studios. 수동 연결 명령: macOS `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`, Windows `%LOCALAPPDATA%\Roblox\mcp.bat`. "신뢰하는 클라이언트만 연결" 경고 | https://create.roblox.com/docs/studio/mcp | fetch | 이미 사용 중. 로컬 도구에는 문서에 없는 `create_skill`, `edit_skill`, `open_cloud_invoke`, `subagent`, `rojo_sync_guide`가 더 있음 |
| Roblox/studio-rust-mcp-server | **2026-04-03 아카이브**, MIT. 내장 서버로 대체 | https://github.com/Roblox/studio-rust-mcp-server | fetch | 불필요 |
| Open Cloud | `open_cloud_invoke` 도구가 API 키 없이 자동 인증. 스킬 `rbx-open-cloud-usage`, `rbx-permissions`가 권한 확인 절차 제공 | `/docs/cloud/llms.txt` | 스킬 설명 열람 | **검토.** 개발자 상품/게임패스 등은 대시보드 전에 이 경로를 먼저 시도 |
| luau.org 타입 문서 | `/types`는 개요(추론 모드, 구조적 타입, 주석, 캐스트)뿐. 제네릭, 타입 함수, 유니온/인터섹션은 별도 페이지. `const`는 해당 페이지에 언급 없음 | https://luau.org/types | fetch | 타입 함수는 `https://luau.org/types/type-functions/`(roblox-brain 소스 인용으로 URL 확인). **new solver 필요**: `keyof`, `rawkeyof`, `setmetatable<T,M>`, `type function`, `read` 멤버. 사용자 프로젝트는 이미 `enableNewSolver:true`라 맞음 |
| luau-lsp CLI | 로컬 `luau-lsp analyze --help` **열람**: `--sourcemap PATH`, `--definitions @NAME=PATH`, `--base-luaurc`, `--settings PATH`(LSP 스타일 설정, FFlag override 포함 가능성), `--platform`, `--ignore GLOB`, `--formatter`, `--no-strict-dm-types`, `--flag KEY=VALUE`. 저장소 README는 analyze 플래그를 문서화하지 않고 `--help`를 안내 | https://github.com/JohnnyMorganz/luau-lsp | 열람(로컬 help) + fetch | **즉시(확인 필요).** stl-luau가 "게이트의 `luau-analyze`는 정수 플래그를 못 받는다"고 기록했는데, **`luau-lsp analyze --settings`가 `.vscode`의 `fflags.override`를 읽는지 시험할 가치가 있음**(미시험). 되면 에디터/CLI 진단 불일치가 해소됨 |
| `luau-analyze` 로컬 | 위와 같은 `--sourcemap/--definitions/--flag` 옵션을 제공(`luau-lsp analyze`의 usage 출력). mise 셤에서 버전이 프로젝트 밖에서는 해석 안 됨(`No version is set for shim`) | - | 열람 | 프로젝트 디렉터리 안에서만 `mise exec`로 실행해야 함. 스킬/스크립트는 항상 `mise exec --` 로 감싸기 |

## C. 커뮤니티 Luau/Roblox 스킬 모음 (실제 클론 후 열람)

`/tmp/eco-research`에 shallow clone하여 열람.

| 저장소 | 규모/최신성 | 라이선스 | 품질 평가 (직접 확인) | 재사용성 | 권고 |
|---|---|---|---|---|---|
| https://github.com/TabooHarmony/roblox-brain | 스킬 29개(core/gameplay/design/tools), `AGENTS.md` 있음, 최신 커밋 2026-10-14. 진행식 공개(SKILL.md 약 3,000자 + references/full.md) | **MIT** | `roblox-luau-types` 열람: 소스를 creator-docs/luau.org/Kampfkarren 가이드로 명시, `last_reviewed` 기재. **new solver 필요 조건, 타입 함수, `read` 멤버, 신뢰 경계(원격/DataStore는 런타임 검사)를 정확히 짚음.** `const`는 미언급 | **높음.** MIT라 일부 발췌/수정 가능. 단 대상이 Roblox 게임 개발(DataStore, GUI, 수익화 등)이라 이 사용자의 라이브러리/툴 개발(stl-luau, quad, tbox)에는 비중이 낮음 | 검토. 전체 설치 말고 `roblox-luau-types`, `roblox-luau-core`, `roblox-security`만 참고. 설치 시 `npx skills add TabooHarmony/roblox-brain/skills/core` |
| https://github.com/gamedev-skills/awesome-gamedev-agent-skills | 스킬 78개(엔진별). roblox 8개(luau, datastores, networking, ui, physics, characters, studio-workflow, simulator-economy). 최신 2026-11-09 | **Apache-2.0** (NOTICE 포함) | 폴더 구조만 열람. 본문 품질은 미확인 | 가능(Apache 표기 의무) | 불필요. 범용 게임 모음이라 얕을 가능성이 큼 (미검증) |
| https://github.com/brockmartin/roblox-game-skill | SKILL.md 라우터 + references 16개(합계 약 576KB). 장르 템플릿 | **LICENSE 파일 없음**(README만 존재) | SKILL.md 열람: "ultimate companion" 식 과장 문구, 커뮤니티 MCP 39도구/공식 MCP 6도구 감지 로직. **공식 MCP 도구명을 `run_code`, `insert_model` 등 구버전(아카이브된 서버) 기준으로 가정**. 현재 내장 서버(`execute_luau`, `script_read`…)와 불일치 | **낮음.** 라이선스 없음이라 복사 금지. 576KB는 컨텍스트 낭비 | 불필요 |
| https://github.com/christopher-buss/skills | roblox-ts, jecs, jest, ecs-design, pnpm (SKILL 6개). `AGENTS.md`, `CLAUDE.md` 있음 | **MIT** | 목록만 열람. roblox-ts(TypeScript) 중심 | 이 사용자는 순수 Luau라 해당 없음. jecs/jest는 Luau 라이브러리지만 사용 안 함 | 불필요 |
| 기타(smithery greedychipmunk/roblox-game-development, kursku/luau-roblox, stackfox-labs/luau-skills, dig1t/luau-best-practices) | 검색 결과에만 등장 | 미확인 | 열람 안 함 | - | 검색 요약만. 평가 보류 |

결론: Luau 타입/신규 문법을 **`const`까지** 다루는 커뮤니티 스킬은 확인하지 못함. 이 사용자는 `const`, 타입 함수, new solver 한도 확장 같은 최전선 설정을 쓰므로 (프로젝트 내 `typing-limits.md`, `.vscode` FFlag) **직접 작성한 스킬이 커뮤니티 것보다 정확**할 가능성이 높음. 커뮤니티 자산은 참고용.

## D. 스캐폴딩 도구 현황과 스킬화 표준화 지점

| 도구 | 현황 | 출처 / 확인 | 이 사용자 |
|---|---|---|---|
| Rokit | Roblox 공식 문서가 권장하는 툴체인 관리자. Foreman/Aftman 설정 호환. Wally도 설치 가능 | https://create.roblox.com/docs/projects/external-tools.md (검색 요약) | 미사용. quad가 rokit에서 mise로 전환(2026-08-19) |
| Aftman | 자체 README가 mise를 대안으로 권장. Rokit README는 제3자 유지보수라고 언급 | https://github.com/LPGhatguy/aftman (검색 요약) | 미사용. 현재 신규 도입 대상 아님 |
| mise | 범용 관리자. `github:` 백엔드로 rojo/pesde/luau-lsp 설치. 사용자 로컬 2026.9.16 | 로컬 열람 | **사용 중(표준)** |
| Wally | 로컬에 없음. Roblox 문서에서 인기 패키지 관리자로 언급. 이 사용자는 pesde | 검색 요약 | 미사용 |
| pesde | 0.7.4에서 `const` 신문법 게시 검증 통과 (quad `mise.toml` 주석) | 로컬 열람 | 사용 중 |
| Selene | 0.31.0이 최신, `const` 파싱 불가 → stl-luau에서 폐기 | 로컬 열람 | 폐기됨 |
| StyLua | 2.5.2 사용. 2.6.0이 있다고 table-sim 주석에 기록. `syntax="Luau"` 필수(안 그러면 `f<<T>>(...)`가 시프트 연산으로 **조용히** 변환 — moonwave-luau 주석에 실측) | 로컬 열람 | 사용 중 |
| Lune | 0.10.5 전역 설치, `const` 때문에 프로젝트에서는 제외 | 로컬 열람 | 제한적 |
| lute / darklua | tbox만 사용(lute 1.0.0, darklua 0.19.0) | 로컬 열람 | 부분 사용 |
| Rojo | 7.7.0 고정 (7.7.1이 있다고 table-sim 주석에 기록) | 로컬 열람 | 사용 중 |

### 스캐폴딩 스킬(`new-luau-project`)로 표준화할 지점

1. **mise.toml 핀 테이블**: 핀을 한 곳(스킬 내 `versions.md` 또는 템플릿)에서 가져와 모든 프로젝트에 동일하게 적용. 현재 luau 0.734/0.742, luau-lsp 1.69.0/1.70.1이 섞임. 올림 절차("형제가 올릴 때 같이")를 별도 `bump-toolchain` 스킬로 분리.
2. **stylua.toml 프리셋 2종**: (a) 탭형(stl-luau/quad/table-sim/devplorer), (b) 스페이스형 + `sort_requires`(tbox/rbvm). `syntax="Luau"` 누락 방지 주석과 함께. `call_parentheses` 불일치는 의도인지 확인 후 결정.
3. **`.luaurc`**: `strict` + `lint:{"*":true}` 기본. aliases는 소비자가 있는 프로젝트만.
4. **`.vscode/settings.json`**: `luau-lsp.fflags.enableNewSolver:true`와 한도 override 값(quad/stl-luau 공통 4개 값)을 템플릿화. 근거 주석(`typing-limits.md`) 링크.
5. **`default.project.json`**: 들여쓰기 통일(탭), `servePlaceIds` 포함 여부(Studio 연동 시 필수라는 `rojo_sync_guide`의 규칙) 질문 한 번.
6. **`.gitignore`**: `sourcemap.json` 제외(luau-lsp README 권고)인데, 6개 프로젝트에 `sourcemap.json`이 **존재**함. 커밋 여부가 프로젝트마다 다른지 확인 필요(미확인).
7. **게이트 스크립트**: `scripts/check.sh`(luau-analyze + stylua --check)를 템플릿화. 프로젝트 `scripts/`에 이미 있는 것을 기준으로 추출.
8. **`const` 호환성 체크리스트**: selene/lune/pesde 구버전 모두 `const`를 못 읽음. 새 프로젝트가 `const`를 쓸지 먼저 묻고, 쓰면 selene/lune을 빼는 분기.
9. **CLAUDE.md 골격**: 이미 `.claude/{base,conventions,todos,project-context}` 체계가 있으므로 그 골격(빈 템플릿)을 스킬 자산으로 포함.

## 요약: 채택 권고

| 권고 | 항목 |
|---|---|
| 즉시 | Studio 내장 스킬(`list_skills`) 활용 규칙을 CLAUDE.md에 명시 / Roblox `llms.txt`(+`.md` 규칙) 참조 규칙 / skill-creator로 `new-luau-project`, `bump-toolchain` 스킬 제작 / session-report 1회 실행 / `luau-lsp analyze --settings`의 FFlag override 적용 여부 시험 |
| 검토 | claude-md-management(한 프로젝트에서 시험) / plugin-dev(스킬 3개 이상일 때) / hookify / claude-code-setup / roblox-brain 중 `roblox-luau-types` 등 3개 발췌 / Open Cloud 스킬 / creator-docs 로컬 클론 / **luau-lsp 기반 자체 LSP 플러그인**(공식 lua-lsp는 `.lua` 전용) |
| 불필요 | lua-lsp, code-review, code-simplifier, commit-commands, feature-dev, security-guidance, mcp-server-dev, document-skills, studio-rust-mcp-server(아카이브), brockmartin/roblox-game-skill(라이선스 없음), christopher-buss/skills(roblox-ts), Rokit/Aftman/Wally/Selene |

## 한계

- anthropics/skills는 저장소를 클론하지 않고 fetch 요약만 사용(스킬 개별 목록 미확인).
- Roblox llms.txt는 앞 100KB만 읽음. Studio MCP 스킬은 목록(설명)만 읽고 본문 대부분은 열람 안 함.
- serena 등 external_plugins 내용, `gh` CLI 부재로 저장소 메타(별/아카이브 일자)는 fetch로만 확인.
- `luau-lsp analyze --settings`가 FFlag override를 읽는다는 것은 가설이며 시험하지 않음.
