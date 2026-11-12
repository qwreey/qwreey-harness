---
title: "luau+mock 으로 충분한가, Studio 가 필요한가"
description: "엔진에 기대는 동작을 luau CLI+mock 으로 시험해도 되는지, Studio 가 필요한지 가르는 원칙·판정 표·절차. task 순서, 신호 시점, Destroy, 복제, GUI, 물리, GC 행마다 근거를 단다"
keywords:
  - "mock 으로 충분한가"
  - "Studio 가 필요한가"
  - "Studio 필요 판정"
  - "판정 표"
  - "luau CLI 로 Roblox 테스트"
  - "엔진 의존 테스트"
  - "계약 대 엔진 실제 동작"
  - "engine-dependent test"
  - "when to use Studio"
  - "luau CLI task 전역 없음"
  - "엔진 대면 델타"
  - "D-03"
kind: reference
category: roblox/env
tags: [policy, studio]
last_verified: 2026-11-10
---
# env-dependence — luau+mock 으로 충분한가, Studio 가 필요한가

## 이 파일이 답하는 질문
- Q1 이 동작을 확인하려면 Studio 를 불러야 하나?
- Q2 task.defer/delay/wait 의 순서를 CLI 에서 믿어도 되나?
- Q3 이벤트 핸들러 순서와 Deferred 모드에서 무엇이 달라지나?
- Q4 Destroy 뒤 무엇이 동기이고 무엇이 늦게 일어나나?

## 목차
- §1 판정 원칙
- §2 판정 표
- §3 task 와 신호의 타이밍 → roblox-engine signals-and-events, tasks-and-threads
- §4 Instance 수명과 Destroy → roblox-engine instance-lifecycle
- §5 판정 절차

---

## §1 판정 원칙
status: described · 원천: 사용자 결정 claude-doctor `.claude/base/decisions/D-03-runner.md` (2026-11-10), quad `.claude/audit/m10-events-studio-2026-09-03.md` 머리말, quad `quad-base/test/mock.luau` 머리 주석

- **mock 으로 보는 것**: "내 코드가 엔진 API 에 대해 가정한 계약대로 동작하는가". 계약이 명확하면 mock 은 그 계약만 흉내 내면 된다.
- **Studio 로 보는 것**: "그 가정이 실제 엔진과 맞는가", 그리고 엔진만 만들 수 있는 현상(렌더링, 물리, 복제, GC, 프레임 타이밍).
- quad 는 이 구분을 그대로 쓴다. CLI spec 이 mock 위에서 계약을 고정하고, Studio 실측은 "엔진 대면 델타만 본다"(m10 머리말).
- 엔진에 손대지 않는 계산은 mock 도 필요 없다. table-sim 은 엔진 무관 로직을 `src/core/` 에 모아 `luau tests/run.luau` 로 21개 스위트를 돌리고, 시간은 인자(`now`)로 받는다.

## §2 판정 표
status: described (판정) / 각 행의 "근거" 열이 실측 출처

| 동작 | luau + mock 으로 충분한 경우 | Studio 가 필요한 경우 | 근거 |
|---|---|---|---|
| 순수 계산, 자료구조, 직렬화 | 항상. mock 도 필요 없다 | — | table-sim `<비공개>` |
| 시간에 기대는 로직(타이머, 쿨다운) | 시간을 인자로 주입하면 항상 | 실제 프레임 간격, `os.clock` 정밀도 | table-sim `<비공개>` |
| `task.spawn/defer/delay/wait` 순서 | 내 코드가 "defer 는 지금 말고 나중", "delay 는 t 뒤" 정도만 가정할 때. 가상 시계 + `flush()` mock | 같은 프레임 안 resumption 순서, Heartbeat·PreSimulation 등 resumption point 와의 상대 순서, `task.wait()` 의 실제 최소 지연 | roblox-engine `tasks-and-threads.md` §1–2, roblox-engine `signals-and-events.md` §2 |
| RBXScriptSignal 발화 순서 | mock 이 실측 규칙(연결 역순, 발화 중 연결은 다음 발화)을 따를 때 | 규칙 자체를 확인할 때, Immediate 모드 동작 | roblox-engine `signals-and-events.md` §3, §8 |
| 핸들러 실행 시점(Deferred) | 코드가 "핸들러는 나중에 돈다"를 견디는지 볼 때(mock 이 큐에 넣고 flush) | 실제로 어느 resumption point 에서 도는지 | roblox-engine `signals-and-events.md` §2, §4 |
| 속성 변경 신호(`GetPropertyChangedSignal`, `Changed`) | 핸들러 등록·해제 계약 | 연속 대입의 중간값 관측, 끊긴 연결의 대기 배달 취소 | roblox-engine `signals-and-events.md` §5 |
| Instance 수명·`Destroy` | 동기 부분: `Connected=false`, `Parent=nil`, 자손 Destroy, 두 번째 Destroy no-op | `Destroying` 핸들러 시점, 파괴 뒤 속성 읽기·쓰기 에러, 파괴된 Instance 에 새로 연결, userdata GC 수거 | roblox-engine `instance-lifecycle.md` §2–4, §8 |
| 트리 API 경계 동작 | mock 에 넣을 때 rbvm 실측 표를 근거로 한다 | 표에 없는 경계(이름 변경 감지 등) | roblox-engine `instance-api.md` §1 |
| 문자열 `require` | luau CLI 규칙은 CLI 로 | Studio 규칙(`@game/…`, alias 대소문자, 끝 슬래시) | luau-runtime `require-by-string.md` §1–5, roblox-engine `require-in-roblox.md` §1 |
| Roblox 데이터 타입 값(UDim2, CFrame, Color3 산술) | 값의 의미를 보지 않을 때(형태만 통과) | 값에 기대는 결과 | quad runshim 머리 주석("값에 기대는 스니펫은 `no-run`") |
| DataStore, HttpService, MessagingService | 스텁(가짜 store 가 쓰기를 기록) | 실제 한도, 권한, 오류 코드 | Studio 내장 skill `rbx-unit-test` "ISOLATING DEPENDENCIES", `rbx-permissions` |
| 복제(서버↔클라이언트), RemoteEvent, Players, 캐릭터 (roblox-net `remotes-and-replication.md`) | 인터페이스 모양만 | 복제 순서와 지연, 소유권. 여러 클라이언트는 Studio MCP 로도 한계가 있어 사람 QA 로 넘긴다 | table-sim `CLAUDE.md` ("Studio Play 에서 본 것은 클라이언트 하나로 되는 데까지") |
| UI 레이아웃, `AbsoluteSize`, 텍스트 크기, 렌더링 (roblox-world `gui-and-input.md`) | — | 항상 | quad `.claude/audit/kit-studio-*`(Play Client 에서 MCP 로 잰 크기와 스크린샷) |
| 물리, 네트워크 지연 | — | 항상 (`rbx-network-simulator`) | Studio 내장 skill |
| 성능, GC 타이밍, 메모리 | 알고리즘 차원의 비교만 | 엔진 위 실제 비용 (`rbx-perf-profiling`). CLI 와 Studio 의 GC 타이밍은 다르다 | roblox-engine `perf.md`, roblox-engine `gc-in-roblox.md`, luau-runtime `gc-and-weak-tables.md` §4 |

## §3 task 와 신호의 타이밍 → roblox-engine `signals-and-events.md`, `tasks-and-threads.md`
status: described · 원천 실측 요약(상세와 근거는 링크한 파일)

- `luau` CLI(0.734, 0.742)에는 `task`, `game`, `Instance`, `wait` 전역이 없다. `typeof`, `getfenv`, `setfenv`, `coroutine` 은 있다(이 저장소 실측).
- 모드: `SignalBehavior` 는 스크립트로 못 읽는다. 대입·`Fire` 다음 줄에서 핸들러가 안 돌았으면 Deferred 다(roblox-engine `signals-and-events.md` §1).
- Deferred 핸들러는 다음 재개 지점에 돈다. 같은 줄기에서 결과를 읽으면 0 이다(§2). 핸들러 순서는 연결 역순으로 관측됐고 계약은 아니다(§3). `Disconnect()` 는 대기분을 버리고 `Destroy()` 로 끊긴 연결은 대기분이 한 번 돈다(§4). 같은 값 대입은 신호가 없다(§5).
- task: `task.spawn(th)` 은 같은 thread 를 돌려주고, 죽은 스레드 `task.cancel` 은 no-op 이다(roblox-engine `tasks-and-threads.md` §1).
- **Immediate 모드에서 신호 동작을 잰 원천은 없다.** Immediate 플레이스의 순서를 이 파일들로 단정하지 않는다.

## §4 Instance 수명과 Destroy → roblox-engine `instance-lifecycle.md`
status: described · 원천 실측 요약

- `Destroy()` 직후 그 Instance 의 연결 `Connected` 는 동기로 false 다. `Destroying` 핸들러는 그 뒤에 돌고, 그 안에서 Instance 는 이미 파괴돼 있다(Parent nil)(§2).
- 파괴된 Instance 에 새로 연결하면 `Connected == true` 로 영원히 남는다. 깔끔한 "파괴됨" 술어가 없다(§3).
- Lua 참조가 사라지면 Instance userdata 는 수거되고 다시 얻으면 다른 userdata 다. weak-key 표 항목이 미아가 된다(§4).
- mock 은 동기 부분(`Connected` 전환)까지 재현하는 것이 보통이다. 나머지에 기대는 코드는 Studio 로 확인한다(§8).

## §5 판정 절차
1. 확인하려는 주장을 한 문장으로 쓴다. 예: "Destroy 하면 정리 콜백이 한 번 불린다".
2. 그 문장에 "언제", "어떤 순서로", "엔진이 실제로" 가 들어 있으면 Studio 후보다. §2 표에서 행을 찾는다.
3. mock 으로 충분한 행이면 mock 의 차이 목록(`mocks.md` §5)에 그 동작이 빠져 있지 않은지 본다. 빠져 있으면 mock 결과를 믿지 않는다.
4. Studio 가 필요한 행이면 같은 시나리오를 mock 에서도 돌려 두고(회귀용), Studio 결과를 저장소의 실측 문서에 날짜·버전·모드와 함께 남긴다(`studio-mcp.md` §5).
