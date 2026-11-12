---
title: "Roblox Studio MCP 로 엔진 동작 확인하기"
description: "Roblox Studio MCP 를 부르는 두 경우, 읽기 전용 도구와 상태를 바꾸는 도구, 여러 Studio 중 studio_id 고르기, studio-sync 로 Rojo 싣기, execute_luau 실측 관용구(return, Deferred 두 번 호출), 내장 skill 13개"
keywords:
  - "Studio MCP 로 확인"
  - "execute_luau"
  - "list_roblox_studios"
  - "studio_id"
  - "get_studio_state"
  - "start_stop_play"
  - "상태 변경 도구"
  - "studio-sync"
  - "rojo_sync_guide"
  - "servePlaceIds"
  - "AgentOwner"
  - "Deferred 두 번 호출"
  - "_G.probe"
  - "Studio 내장 skill"
  - "rbx-unit-test"
  - "rbx-perf-profiling"
  - "rbx-permissions"
kind: reference
category: roblox/studio
tags: [studio, policy]
last_verified: 2026-11-10
---
# studio-mcp — Roblox Studio MCP 로 엔진 동작 확인하기

## 이 파일이 답하는 질문
- Q1 언제 Studio 를 부르나?
- Q2 어떤 도구가 읽기 전용이고 어떤 도구가 Studio 상태를 바꾸나?
- Q3 Studio 가 여러 개 열려 있으면 어떻게 고르나?
- Q4 Rojo 프로젝트 코드를 Studio 에 어떻게 싣나?
- Q5 execute_luau 로 실측할 때의 관용구는?
- Q6 Studio 내장 skill 13개는 각각 언제 부르나?

## 목차
- §1 언제 부르나
- §2 도구 표
- §3 여러 Studio 중 대상 고르기
- §4 rojo_sync_guide 규칙 (studio-sync)
- §5 실측 관용구
- §6 내장 skill 13개

---

## §1 언제 부르나
status: described · 원천: 사용자 결정 claude-doctor `.claude/base/decisions/D-03-runner.md`

- **mock 이 실제와 맞는지 확인할 때**(`mocks.md` §6), **mock 으로 재현할 수 없는 동작을 볼 때**(`env-dependence.md` §2 의 "Studio 가 필요한 경우" 열). 이 둘뿐이다.
- 반복 실행하는 테스트 게이트를 Studio 에 기대지 않는다. Studio 는 사람이 띄워 둔 창이고 다른 세션과 공유되므로 기계적으로 돌릴 수 없다.
- Studio 실측 결과는 저장소 문서로 옮긴다. 다음 세션은 Studio 없이도 그 결과를 읽을 수 있어야 한다.

## §2 도구 표
status: verified (도구 목록과 설명) · last-confirmed: 2026-11-10, 이 머신의 `roblox-studio` MCP 서버 도구 스키마 · 원천: 같은 날 `list_roblox_studios`, `rojo_sync_guide`, `get_studio_state`, `skill` 호출 결과

모든 도구(아래 `rojo_sync_guide` 와 `list_roblox_studios` 빼고)는 `studio_id` 가 필수다.

| 분류 | 도구 | 쓰임 |
|---|---|---|
| 대상 찾기 | `list_roblox_studios` | 연결된 Studio 의 `id` 와 `name`(플레이스 이름과 placeId). 먼저 부른다 |
| 상태 보기 | `get_studio_state` | Edit/Play 모드, 쓸 수 있는 DataModel(`Edit`, `Client`, `Server`) |
| 트리 보기 | `search_game_tree`, `inspect_instance` | 계층 탐색(`datamodel_type` 필수, Play 중에는 `Edit` 거부), 한 Instance 의 속성·attribute·자식 요약 |
| 스크립트 보기 | `script_read`, `script_grep`, `script_search` | 이름·내용으로 찾기, 줄 번호 붙여 읽기 |
| 출력 보기 | `get_console_output` | Output 창. 테스트 러너는 결과를 여기 찍는다 |
| 화면 | `screen_capture` | 뷰포트 캡처(UI·렌더링 확인) |
| 문서 | `http_get` | create.roblox.com 문서(`.md` 나 `llms.txt` 로 끝나는 URL 만 허용). roblox-docs `sources.md` 참고 |
| 지식 | `list_skills`, `skill` | 내장 skill 목록과 본문(§6) |
| 동기화 안내 | `rojo_sync_guide` | `studio-sync` 사용법(§4). `studio_id` 불필요 |
| **상태 변경** | `execute_luau` | 코드 실행(`datamodel_type` 필수). Studio 메인 스레드에서 돌아 yield 전까지 Studio 가 멈춘다 |
| **상태 변경** | `start_stop_play` | Play 시작·정지. 다른 사람이 쓰는 Studio 에서는 그 사람의 세션을 끊는다 |
| **상태 변경** | `multi_edit`, `insert_asset`, `generate_*`, `user_keyboard_input`, `user_mouse_input`, `character_navigation`, `create_skill`, `edit_skill`, `upload_image`, `store_image`, `open_cloud_invoke` 등 | 스크립트·에셋·입력·클라우드 자원을 바꾼다 |

- 상태를 바꾸는 도구는 그 Studio 를 쓰는 사람이나 다른 에이전트 세션이 없을 때만 쓴다. `list_roblox_studios` 설명도 "사용자의 게임을 바꾸기 전에 사용자에게 확인하라"고 한다. 잘 모르면 읽기 도구만 쓰고 사람에게 묻는다.
- 공식 문서(`create.roblox.com/docs/studio/mcp.md`)에 없는 도구(`create_skill`, `edit_skill`, `open_cloud_invoke`, `subagent`, `rojo_sync_guide`)도 이 서버에는 있다(claude-doctor audit 02).

## §3 여러 Studio 중 대상 고르기
status: verified · last-confirmed: 2026-11-10 (`list_roblox_studios`: `devplorer (placeId: 130663469983583)`, `quad-test (placeId: 105962699098904)` 두 개 연결)

1. `list_roblox_studios` 를 부른다. 결과의 `name` 에 플레이스 이름과 placeId 가 있다.
2. 작업 대상 프로젝트의 플레이스를 `name` 으로 고르고 그 `id` 를 이후 모든 호출의 `studio_id` 로 쓴다. 프로젝트의 `default.project.json` 에 `servePlaceIds` 가 있으면 그 placeId 와 맞춘다.
3. 맞는 플레이스가 없으면 다른 프로젝트의 Studio 를 빌려 쓰지 않는다. 사람에게 Studio 를 열어 달라고 한다.
4. `get_studio_state` 로 모드를 본다. 이미 Play 중이면 누군가 쓰는 중일 수 있다. Play 를 멈추거나 시작하지 않는다.
5. `studio-sync` 쪽 대상 지정은 `studio_id` 가 아니라 `--place <placeId 또는 이름>` 이다(§4).

## §4 rojo_sync_guide 규칙 (studio-sync)
status: verified · last-confirmed: 2026-11-10 (`rojo_sync_guide` 출력)

- Rojo 프로젝트는 **code-docker 쉘에서 프로젝트 디렉터리로 가서 `studio-sync`** 로 싣는다. 프로젝트 자신의 `rojo serve`(mise 나 PATH 가 고른 버전)를 띄워 열린 플레이스를 한 번 동기화하고 멈춘다. Studio 클릭이 필요 없고 저장소에 아무것도 쓰지 않는다. **MCP 도구로 프로젝트 파일을 다시 만들지 않는다.**

```bash
studio-sync                                   # default.project.json, owner = 현재 git 브랜치
studio-sync path/to/x.project.json --owner my-task --json
studio-sync --place 105962699098904           # Studio 가 여럿일 때: placeId 나 플레이스 이름
studio-sync --list                            # 열린 Studio: id, 플레이스 이름, placeId
studio-sync --release                         # 내 AgentOwner 표시 해제 (Instance 는 남음)
```

- **소유권**: 동기화한 최상위 Instance(서비스 바로 아래)마다 `AgentOwner` attribute 에 owner 이름이 붙는다. 다른 owner 가 쥔 Instance 를 바꾸는 동기화는 거부된다(exit 1). 동시 동기화는 차례로 돈다. 끝나면 `--release` 로 표시를 풀어 다른 사람이 바꿀 수 있게 한다(`--release` 도 `--place` 를 받는다).
- **여러 Studio**: `list_roblox_studios` 가 둘 이상을 보이면 `--place` 가 필요하다(`studio_id` 는 받지 않는다). 없으면 거부하고 열린 플레이스를 나열한다. **단 프로젝트의 `servePlaceIds` 가 정확히 하나와 맞으면 자동으로 고른다.** 그래서 Studio 연동 프로젝트는 `default.project.json` 에 `servePlaceIds` 를 넣어 두는 것이 좋다(claude-doctor audit 02: table-sim, devplorer 는 있고 quad 는 없다). 이름이 같고 placeId 가 없는 두 Studio 는 `--studio <studio-sync --list 의 id>`.
- **필요 조건**: Studio 가 플레이스를 연 채 실행 중이어야 한다. 동기화 플러그인은 studio 컨테이너가 뜰 때 설치되고 Studio 는 시작할 때만 플러그인을 읽으므로, 그보다 먼저 뜬 Studio 는 사람이 재시작해야 한다.
- **확인**: MCP `search_game_tree`, `inspect_instance` 나 code-docker 의 `studio-output -n 100 --no-follow`(모든 사람의 Output).
- code-docker 에 보이는 `rojo sourcemap --watch` 는 luau-lsp 에디터 확장의 것이고, 살아 있는 `rojo serve` 는 사람의 라이브 세션이다. 건드리지 않는다. 라이브 동기화(`rojo serve --address 0.0.0.0`, 포트 34872–34879, 호스트 `roblox-studio-front`)는 Studio 클릭이 필요하므로 사람 몫이다.

## §5 실측 관용구
status: described · 원천: rbvm `.claude/design/engine-behavior.md` 실측 방법, quad `.claude/audit/m10-events-studio-2026-09-03.md`, quad `.claude/audit/kit-studio-2026-10-13/REPORT.md`, `execute_luau` 도구 설명, 내장 skill `rbx-unit-test`

- **결과는 `return` 한다.** `print` 는 Output 창을 다른 사람과 섞는다. 테이블로 모아 돌려준다.
- **Deferred 관측은 두 번 부른다.** 첫 호출에서 준비하고 발화한 뒤 결과를 전역(예: `_G.probe`)에 쌓게 하고, 두 번째 호출에서 읽는다. 같은 호출 안에서는 `task.wait()` 를 한 번 넣어야 핸들러가 돈다.
- **모드를 확인하고 적는다.** `workspace.SignalBehavior` 는 MCP 로 읽지도 쓰지도 못했다(quad kit-studio). 대입 다음 줄에서 콜백이 안 불렸고 `task.wait()` 뒤에 불렸다면 Deferred 로 판정한다.
- **Studio 를 얼리지 않는다.** `execute_luau` 는 메인 스레드에서 돈다. 큰 작업은 덩어리로 나누고 덩어리마다 `task.wait()` 를 한 번 부른다. 상태를 기다리는 루프 안에는 반드시 `task.wait()` 를 둔다.
- **Edit 와 Play 를 구분한다.** 많은 엔진 동작(Instance, 신호, require)은 Edit DataModel 에서 잴 수 있다(rbvm 은 Edit 에서 쟀다). 스크립트 종료 시 연결 해제, 복제, 캐릭터처럼 Play 가 필요한 것은 `datamodel_type` 이 `Server`/`Client` 이고, Play 시작은 상태 변경이다.
- **흔적을 치운다.** 실측용으로 만든 Instance 는 같은 호출 끝에서 `Destroy` 한다. 전역 표식(`_G.probe`)도 지운다.
- **기록 형식**: 날짜, Studio 버전, 플레이스, 모드, 그리고 "관찰 | 결과 | 영향" 표. "아직 안 잰 것" 목록을 따로 둔다(rbvm engine-behavior 형식).

## §6 내장 skill 13개
status: verified (목록과 설명) · last-confirmed: 2026-11-10 (`skill` 도구 설명, `rbx-unit-test`·`rbx-docs-search` 본문 열람)

부르는 법: `list_skills(studio_id)` 로 목록을 보고 `skill(skill_name, studio_id)` 로 본문을 읽는다. 본문 조회는 Studio 상태를 바꾸지 않는다. skill 이 시키는 도구 중 상태 변경 도구가 있으면 §2 규칙을 그대로 따른다.

| skill | 언제 부르나 |
|---|---|
| `rbx-docs-search` | Roblox API·가이드를 `http_get` 으로 찾을 때. URL 패턴 표와 `query` 사용법이 있다(roblox-docs `sources.md`) |
| `rbx-unit-test` | Studio 안에서 ModuleScript 단위 테스트를 쓰거나 돌릴 때. 기존 프레임워크(Jest-Lua, TestEZ) 감지 → 없으면 `ServerStorage.UnitTest` 내장 하네스. Play 의 Server DataModel 에서 돈다. 이 저장소 방침상 단위 테스트의 기본은 luau CLI + mock 이고, 이 skill 은 mock 으로 안 되는 모듈에 쓴다 |
| `rbx-debug` | 브레이크포인트를 걸고 스레드 정보를 보며 스크립트 동작을 확인할 때 |
| `rbx-perf-profiling` | MicroProfiler 데이터(LibMP)로 CPU/GPU 병목, 프레임 스파이크, 하위 시스템별 메모리를 볼 때 |
| `rbx-scene-analysis` | SceneAnalysisService 로 렌더링·메모리·Instance 구성·부모 없는 Instance(누수)를 볼 때 |
| `rbx-network-simulator` | 지연·지터·패킷 손실을 걸고 응답 시간과 서버 따라잡기를 잴 때 |
| `rbx-device-simulator-lua` | Device Simulator 로 기기·방향별 UI 를 확인할 때(execute_luau + screen_capture) |
| `rbx-permissions` | Open Cloud, 업로드, DataStore/MemoryStore, HTTP 접근 전에 필요한 권한을 확인할 때, "has not been granted"·403 이 났을 때 |
| `rbx-open-cloud-usage` | 개발자 상품, 게임패스 같은 자원을 `open_cloud_invoke` 로 다룰 때 |
| `rbx-configs-experimentation` | ConfigService 로 재시작 없는 값 조정, 기능 플래그, A/B 실험을 할 때 |
| `rbx-instrument-analytics` | AnalyticsService 이벤트 계측을 감사하거나 넣을 때 |
| `rbx-import-asset` | 외부 3D 도구의 모델을 Open Cloud 로 올려 넣을 때 |
| `rbx-create-skill` | Studio 쪽 skill 을 만들거나 고칠 때. 프로젝트 지식은 이식성 때문에 Claude Code 쪽 SKILL.md 가 낫다(claude-doctor audit 02) |
