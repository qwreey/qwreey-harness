---
name: roblox-engine
description: >-
  Roblox 엔진 핵심 런타임의 실제 동작(대부분 Studio 실측)이다. RBXScriptSignal(Deferred/Immediate 배달 시점·순서,
  Disconnect·Destroy 의 대기 배달, Changed 의 같은 값 무발화), Instance 수명(Destroy·Destroying, userdata 신원,
  Instance 를 weak 키로 쓴 표, 연결이 잡는 참조), 트리 API·Attribute·QueryDescendants, TweenService(Cancel·Completed,
  파괴 뒤 트윈), task 라이브러리(spawn·defer·cancel, RemoteFunction 동시 요청 같은 협력 스케줄링의 경쟁·TOCTOU, 시한),
  Actor·병렬 Luau(ConnectParallel, 병렬 단계 제약, 스레드 안전 등급, SharedTable), Roblox 안 require(Studio 문자열
  require, 캐시), Roblox 안 GC 관찰, 엔진 비용을 다룬다. 이벤트가 안 오거나 늦을 때, Destroy·Tween·누수를 확인할 때,
  병렬 코드나 task 순서·경쟁을 따질 때 쓴다. 원격·서비스는 roblox-net, GUI·물리는 roblox-world.
---
# roblox-engine

"Roblox 엔진 핵심 런타임은 실제로 어떻게 동작하나"를 다룬다. 어떻게 **확인하나**(mock, Studio MCP, 타입)는 luau-roblox, 엔진 없이 성립하는 언어 의미론(weak 표, 코루틴, CLI require)은 luau-runtime 이다.

- **엔진 사실은 대부분 원천 저장소의 Studio 실측을 옮긴 것이다**(`status: described`). 신호 동작은 **Deferred 플레이스에서만** 쟀다. Immediate 는 문서뿐이다. 절마다 있는 조건 줄과 `mock 흉내:` 줄을 같이 읽는다.
- 문서 근거가 필요하면 roblox-docs(`tools/roblox_docs.py api <Class>.<Member>`)로 확인한다. 문서에 없는 순서·시점은 Studio 로 간다(luau-roblox `studio-mcp.md`).

## 결정 트리
1. 질문이 엔진과 무관한가(weak 표 의미론, `coroutine.resume`, luau CLI 의 `init.luau`·alias)? → luau-runtime.
2. 원격·복제·서비스(DataStore 등)면 roblox-net, GUI·입력·물리·캐릭터면 roblox-world. 아니면 아래 표.
3. 주제 파일에 답이 있으면 그 절의 **조건**(Studio 버전, 신호 모드, Edit/Play)이 내 상황과 맞는지 본다. 모드가 다르면(Immediate) 미측정이다. 각 파일 "미판정" 절의 재현 절차를 따른다.
4. mock 으로 시험했다면 그 mock 이 엔진과 갈리는 지점(주제 파일 §8 표, `mock 흉내:` 줄)을 확인한다. → luau-roblox `mocks.md`

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| 핸들러가 안 돌았다 / 늦게 돈다, Deferred·Immediate 판정, 재개 지점 | `references/signals-and-events.md` §1–2 |
| 핸들러 순서, 발화 중 Connect·Disconnect, `Once`, 리스너 에러 | `references/signals-and-events.md` §3 |
| `Disconnect()` 했는데 콜백이 왔다 / 안 왔다, Destroy 뒤 대기 배달 | `references/signals-and-events.md` §4 |
| 같은 값 대입에 `Changed` 가 안 온다, 연속 대입 중간값, 시그널을 캐시 키로 | `references/signals-and-events.md` §5–6 |
| Destroy 가 하는 일, `Destroying` 안에서 Parent 가 nil, 파괴됨 판정 | `references/instance-lifecycle.md` §1–3 |
| Instance 를 weak 키로 썼더니 항목이 사라진다, 수명 묶기, Instance 누수 | `references/instance-lifecycle.md` §4–6 |
| Roblox 에서 수거 관찰(`collectgarbage` 는 `"count"` 만), 메모리가 안 줄어든다 | `references/gc-in-roblox.md` |
| Tween `Play`·`Cancel`·`Completed` 순서, 파괴 뒤 트윈, 무한 트윈, 핸들 수거 | `references/tween-and-animation.md` |
| `task.*` 계약, defer 순서 | `references/tasks-and-threads.md` §1–2 |
| RemoteFunction 동시 요청이 쿨다운을 뚫는다, TOCTOU, "한 번만" 초기화 | `references/tasks-and-threads.md` §5 |
| 끝나지 않는 대기와 시한, 시계(`os.clock`·`GetServerTimeNow`) | `references/tasks-and-threads.md` §6–7 |
| Actor, `task.desynchronize`, `ConnectParallel`, 스레드 안전 등급, SharedTable | `references/parallel-luau.md` |
| 트리 API 경계, 엔진 에러 문구, Clone·Archivable, Attribute·태그, QueryDescendants, Reflection | `references/instance-api.md` |
| Studio 문자열 require, `@game`, 대상이 없을 때, 모듈 캐시·VM 경계 | `references/require-in-roblox.md` |
| Instance·트윈·바인더블 비용 기준치, 라이브의 `-O` 수준 | `references/perf.md` |
| 원격·복제·소유권·DataStore / GUI·물리·캐릭터 | roblox-net / roblox-world |
| mock·Studio MCP·Roblox 타입 / 문서 조회 | luau-roblox / roblox-docs |

## 자주 밟는 함정 (요약)
- Deferred 에서 `Fire()`·대입·`Destroy()` 직후에는 핸들러가 아직 안 돌았다. 생존 판정은 동기로 바뀌는 `Connected` 로 한다.
- `Disconnect()` 는 대기 배달을 버리지만 `Destroy()` 로 끊긴 연결은 대기분이 한 번 돈다. `Destroying` 안에서 Instance 는 이미 Parent nil 이다.
- 같은 값 대입은 `Changed` 0회다. 값 비교 없이 쏘는 mock 은 1회로 갈린다.
- 시그널 userdata 는 읽을 때마다 새것이라 표의 키로 못 쓴다. Instance userdata 도 Lua 참조가 사라지면 재생성된다.
- 트윈은 대상이 파괴돼도 끝까지 돌고, 핸들을 잃으면 Cancel 할 수 없다. 무한 트윈은 파괴 전에 Cancel 한다.
- RemoteFunction 호출은 호출마다 별도 스레드다. 확인과 설정 사이에 양보(DataStore 등)가 있으면 동시 요청이 확인을 모두 통과한다.
- Studio 문자열 require 는 대상이 생길 때까지 기다리지 않는다. 이미 require 된 ModuleScript 는 Rojo 로 고쳐도 옛 본문이다.
- 타입 검사기는 병렬 단계의 금지 API 를 모른다. 병렬 단계에서 속성 쓰기는 런타임 에러다.
