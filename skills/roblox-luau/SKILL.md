---
name: roblox-luau
description: >-
  Roblox 엔진과 서비스에 의존하는 Luau 동작을 검증하는 절차다. 어떤 동작을 luau CLI 와 mock 으로 볼 수 있고
  어떤 동작에 Roblox Studio 가 필요한지 가르는 판정 표(task.defer/wait 순서, RBXScriptSignal 발화 순서와
  Deferred 모드, 속성 변경 신호, Instance 수명과 Destroy, 트리 API, 문자열 require, 복제)를 둔다. 필요한 부분만
  흉내 내는 mock 작성 패턴과 mock 충실도 검증 절차(rbvm, quad 실례), Roblox Studio MCP 사용법(execute_luau,
  get_console_output, inspect_instance, 여러 Studio 중 대상 고르기, rojo_sync_guide 의 studio-sync 규칙, 내장
  skill 13개), create.roblox.com llms.txt 로 API 문서 찾기, Roblox 타입 정의(globalTypes)와 sourcemap 을
  luau-lsp 에 넘기는 법을 다룬다. Roblox 프로젝트에서 task·이벤트·Instance 동작을 테스트하거나 확인할 때,
  mock 을 만들거나 고칠 때, Studio MCP 를 부를지 정할 때, Roblox API 를 찾아볼 때 쓴다. 순수 Luau 타입 규칙은
  luau-types, 검사기 호출법은 luau-verify 가 다룬다.
---
# roblox-luau

이 스킬은 "엔진에 기대는 동작을 어떻게 믿을 수 있게 확인하나"를 다룬다. 사용자 결정(claude-doctor D-03, 2026-11-10)이 출발점이다.

- **기본 러너는 `luau` CLI 다.** lune 은 쓰지 않는다(`const` 를 파싱하지 못한다).
- 엔진 의존 동작은 **필요한 부분만 mock 으로 만들어** luau 로 돌린다. 기계적으로 반복할 수 있어야 하기 때문이다.
- **Studio(MCP)는 두 경우에만 쓴다.** (1) mock 이 실제 엔진과 맞는지 확인할 때, (2) mock 으로 재현할 수 없는 동작을 볼 때.

## 핵심 절차
1. **판정한다.** 이 동작이 "내 코드가 가정한 계약"을 묻는가, "엔진이 실제로 어떻게 하는가"를 묻는가? 앞은 luau+mock, 뒤는 Studio 다. → `references/env-dependence.md` §1–2
2. **mock 보다 주입을 먼저 쓴다.** 시간은 인자로 받고(`read(state, now)`), 서비스는 `new(deps)` 로 넘긴다. 그래도 엔진 전역이 필요하면 그 부분만 mock 한다. → `references/mocks.md` §1–3
3. **mock 의 차이를 적는다.** mock 파일 머리에 "엔진과 다른 점" 목록을 둔다. 근거가 Studio 실측이면 날짜, Studio 버전, SignalBehavior 모드를 붙인다. → `references/mocks.md` §5
4. **충실도를 Studio 로 잰다.** 같은 시나리오를 mock 과 Studio 에서 돌려 표로 비교한다. 다르면 mock 을 고치거나 차이 표에 올린다. → `references/mocks.md` §6, `references/studio-mcp.md` §5
5. **Studio 를 쓸 때는** `list_roblox_studios` 로 대상을 고르고, 상태를 바꾸는 도구는 그 Studio 를 쓰는 사람이 없는지 확인한 뒤에만 쓴다. 코드를 넣을 때는 MCP 로 파일을 다시 만들지 말고 `studio-sync` 를 쓴다. → `references/studio-mcp.md` §2–4
6. **API 는 추측하지 않는다.** `create.roblox.com/docs/llms.txt` 인덱스나 검색 API 로 찾고 `.md` 를 붙여 읽는다. → `references/api-docs.md`
7. **타입 검사는 정의 파일과 함께 돌린다.** `luau-lsp analyze --platform=roblox --definitions=<typedefs/globalTypes.d.luau> --sourcemap=sourcemap.json`. → `references/typedefs.md`

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| 이 테스트에 Studio 가 필요한가, luau+mock 으로 되나 | `references/env-dependence.md` §2 (판정 표) |
| task.defer/delay/wait 순서, Heartbeat 와의 관계 | `references/env-dependence.md` §2, §3 |
| 이벤트 핸들러 순서, Deferred/Immediate, "Fire 직후 핸들러가 안 돌았다" | `references/env-dependence.md` §3 |
| Destroy 뒤 연결·속성·Destroying 시점 | `references/env-dependence.md` §4 |
| mock 을 어디까지 만드나, 전역을 모듈에 넣는 법(getfenv) | `references/mocks.md` §1–4 |
| mock 이 실제와 맞는지 확인하는 절차, 차이 기록 형식 | `references/mocks.md` §5–6 |
| Studio MCP 도구 목록, 읽기 도구와 상태 변경 도구 | `references/studio-mcp.md` §2 |
| Studio 가 여러 개 열려 있다, `studio_id` 고르기 | `references/studio-mcp.md` §3 |
| Rojo 프로젝트를 Studio 에 싣기, `--place`, `servePlaceIds`, 소유권 | `references/studio-mcp.md` §4 |
| execute_luau 로 실측하는 관용구(Deferred 는 두 번 호출) | `references/studio-mcp.md` §5 |
| 내장 skill(rbx-debug, rbx-unit-test, rbx-docs-search, rbx-perf-profiling 등)을 언제 부르나 | `references/studio-mcp.md` §6 |
| Roblox API 문서 URL, 검색, 404 의 뜻 | `references/api-docs.md` |
| globalTypes 정의 파일, `--defs`, sourcemap, Claude Code LSP 의 Roblox 모드 | `references/typedefs.md` |
| 순수 Luau 타입 규칙, 검사기 옵션, DX(hover·자동완성) 검사 | luau-types, luau-verify(`checkers.md` §6) |

## 자주 밟는 함정 (요약)
- `luau` CLI 에는 `task`, `game`, `Instance`, `wait` 가 없다(`typeof`, `getfenv` 는 있다). 엔진 전역을 쓰는 모듈은 mock 없이는 require 단계에서 죽는다.
- Deferred 모드에서는 `Fire()`, 속성 대입, `Destroy()` 직후에 핸들러가 아직 돌지 않았다. 같은 `execute_luau` 호출 안에서 결과를 읽으면 0 으로 보인다.
- Deferred 모드에서 한 프레임에 속성을 두 번 바꾸면 `GetPropertyChangedSignal` 핸들러는 두 번 불리지만, 그 안에서 속성을 읽으면 두 번 다 마지막 값이다. 즉시 발화하는 mock 은 중간값을 보여 준다.
- 연결 순서와 발화 순서가 반대다(Deferred 실측: A,B,C 연결 → C,B,A 호출). 정순으로 부르는 mock 은 순서에 기댄 버그를 숨긴다.
- `table.sort` 는 안정 정렬이 아니다. 같은 시각 항목을 정렬로 꺼내는 가상 task 큐는 5개부터 FIFO 를 잃었다(luau 0.742 실측).
- 정의 파일 없이 `--platform=roblox` 로 검사하면 `Instance` 가 `*error-type*` 이 되고, Roblox 전역 오류가 진짜 오류를 덮는다.
- Studio 테스트 플레이스에 진실 원천을 두지 않는다. 실측 결과와 코드는 저장소에 남긴다.
