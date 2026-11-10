---
name: roblox-luau
description: >-
  Roblox 엔진·런타임 지식과 그 검증 절차다. RBXScriptSignal·이벤트(Deferred/Immediate, 핸들러 배달 시점·순서,
  Disconnect 와 Destroy 의 대기 배달, Changed·GetPropertyChangedSignal 의 같은 값 무발화), Instance 수명(Destroy,
  Destroying, 파괴된 Instance, userdata 신원), TweenService(Cancel·Completed 순서, 파괴 뒤 트윈, 무한 트윈 누수),
  약한 테이블 누수와 GC 프로브 함정(ephemeron 없음), require 경로(init.luau·@self·.luaurc alias·symlink, 잘못된
  경로가 진단되는 조건, Studio require 캐시), task·코루틴·경쟁, Actor·병렬 Luau(ConnectParallel,
  desynchronize/synchronize, 병렬 단계에서 막힌 속성 쓰기·API, 스레드 안전 등급)·SharedTable, Instance·Enum·
  Attribute 타입, 트리 API·QueryDescendants, GUI 입력·레이아웃, 원격·복제·네트워크 소유권, DataStore 등 서비스,
  엔진 성능 기준치를 다룬다. 어떤 동작을 luau CLI 와 mock 으로 볼 수 있고 어떤 동작에 Roblox Studio 가 필요한지
  가르는 판정 표, mock 작성·충실도 검증, Studio MCP 사용법, API 문서 찾기, 정의 파일·sourcemap 도 둔다.
  Roblox 코드에서 시그널·이벤트가 안 오거나 늦게 올 때, Destroy·Tween 동작을
  확인할 때, 메모리·약한 테이블 누수를 의심할 때, require 가 안 풀리거나 엉뚱한 모듈을 실을 때, Actor/병렬
  코드를 쓰거나 병렬 단계 에러를 고칠 때, mock 을 만들거나 Studio MCP 를 부를지 정할 때 쓴다. 순수 Luau 타입은 luau-types, 검사기는
  luau-verify, 순수 Luau 성능·GC 비용은 luau-perf 가 다룬다.
---
# roblox-luau

"Roblox 엔진은 실제로 어떻게 동작하나"와 "그것을 어떻게 믿을 만하게 확인하나"를 다룬다. 출발점은 사용자 결정 D-03(2026-11-10)이다.

- **기본 러너는 `luau` CLI 다.** 엔진 의존 동작은 필요한 부분만 mock 으로 만든다. lune 은 쓰지 않는다.
- **Studio(MCP)는 두 경우에만 쓴다.** mock 이 엔진과 맞는지 확인할 때, mock 으로 재현할 수 없는 동작을 볼 때.
- **엔진 사실은 대부분 원천 저장소의 Studio 실측을 옮긴 것이다**(`status: described`). 신호 동작은 **Deferred 플레이스에서만** 쟀다. Immediate 는 문서뿐이다. 절마다 있는 조건 줄과 `mock 흉내:` 줄을 같이 읽는다.

## 결정 트리
1. 질문이 "내 코드가 가정한 계약"인가, "엔진이 실제로 어떻게 하나"인가? 앞은 luau+mock 이다. 뒤는 아래 주제 파일을 먼저 읽고, 답이 없으면 Studio 로 간다. → `references/env-dependence.md` §1–2
2. 주제 파일에 답이 있으면 그 절의 **조건**(Studio 버전, 신호 모드, Edit/Play)이 내 상황과 맞는지 본다. 모드가 다르면(Immediate) 미측정이다. 각 파일 "미판정" 절의 재현 절차를 따른다.
3. 테스트는 주입을 먼저 하고, 그다음 필요한 부분만 mock 한다. 그 mock 이 엔진과 갈리는 지점은 주제 파일 §8 표와 `mock 흉내:` 줄에 있다. → `references/mocks.md`
4. Studio 로 잴 때는 대상 Studio 를 고르고, 결과는 `return` 하고, Deferred 결과는 두 번째 호출에서 읽는다. → `references/studio-mcp.md`
5. API 는 추측하지 않는다(`references/api-docs.md`). 타입 검사는 정의 파일과 함께 한다(`references/typedefs.md`).

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| 이 테스트에 Studio 가 필요한가, luau+mock 으로 되나 | `references/env-dependence.md` §2 |
| 핸들러가 안 돌았다 / 늦게 돈다, Deferred·Immediate 판정, 재개 지점 | `references/signals-and-events.md` §1–2 |
| 핸들러 순서, 발화 중 Connect·Disconnect, `Once`, 리스너 에러 | `references/signals-and-events.md` §3 |
| `Disconnect()` 했는데 콜백이 왔다 / 안 왔다, Destroy 뒤 대기 배달 | `references/signals-and-events.md` §4 |
| 같은 값 대입에 `Changed` 가 안 온다, 연속 대입 중간값, 시그널을 캐시 키로 | `references/signals-and-events.md` §5–6 |
| Destroy 가 하는 일, `Destroying` 안에서 Parent 가 nil, 파괴됨 판정 | `references/instance-lifecycle.md` §1–3 |
| Instance 를 weak 키로 썼더니 항목이 사라진다, 수명 묶기, Instance 누수 | `references/instance-lifecycle.md` §4–6 |
| Tween `Play`·`Cancel`·`Completed` 순서, 파괴 뒤 트윈, 무한 트윈, 핸들 수거 | `references/tween-and-animation.md` |
| 약한 테이블 누수, ephemeron, `__mode`, GC 프로브가 이상하다, Roblox 에서 GC 관찰 | `references/gc-and-weak-tables.md` |
| require 가 안 풀린다, `init.luau`·`@self`, ambiguous 에러, `.luaurc` alias, symlink | `references/require-and-modules.md` §1–4 |
| 잘못된 require 경로인데 진단 0건, Studio require 규칙·캐시, 모듈 사본 둘 | `references/require-and-modules.md` §5–8 |
| `task.*` 계약, defer 순서, 코루틴 에러 삼킴, yield 불가 문맥, TOCTOU, 시한, 시계 | `references/tasks-and-threads.md` |
| Actor, `task.desynchronize`, `ConnectParallel`, 스레드 안전 등급, SharedTable | `references/parallel-luau.md` |
| `Instance.new`·`IsA`·`GetAttribute`·Enum·`FindFirstChild` 의 타입, 엔진 호출의 타입 | `references/api-types.md` |
| 트리 API 경계, 엔진 에러 문구, Clone·Archivable, Attribute·태그, QueryDescendants, Reflection | `references/instance-api.md` |
| GUI 클릭이 뒤로 샌다, AutomaticSize·TextBounds, 톱바 인셋, gameProcessed·포커스 | `references/gui-and-input.md` |
| DragDetector, 물리, 캐릭터, 용접, EditableMesh·에셋 로드 | `references/world-and-physics.md` |
| 원격·바인더블 인자 복사, 원격 값 검증, 복제 경계, 네트워크 소유권, 스트리밍 | `references/remotes-and-replication.md` |
| DataStore·MemoryStore, 글자 필터, loadstring·샌드박스, LogService, Open Cloud | `references/platform-services.md` |
| Instance·트윈·바인더블 비용 기준치, 라이브의 `-O` 수준 | `references/perf.md` |
| mock 범위, getfenv 전역 주입, 차이 기록, 충실도 검증 | `references/mocks.md` |
| Studio MCP 도구, 여러 Studio 고르기, studio-sync, 실측 관용구, 내장 skill | `references/studio-mcp.md` |
| Roblox API 문서 URL·검색 / globalTypes·`--definitions`·sourcemap | `references/api-docs.md` / `references/typedefs.md` |
| 순수 Luau 타입, 검사기 옵션, 순수 Luau 성능·GC 비용, 테스트 하네스 | luau-types, luau-verify, luau-perf, luau-testing |

## 자주 밟는 함정 (요약)
- Deferred 에서 `Fire()`·대입·`Destroy()` 직후에는 핸들러가 아직 안 돌았다. 생존 판정은 동기로 바뀌는 `Connected` 로 한다.
- `Disconnect()` 는 대기 배달을 버리지만 `Destroy()` 로 끊긴 연결은 대기분이 한 번 돈다. `Destroying` 안에서 Instance 는 이미 Parent nil 이다.
- 같은 값 대입은 `Changed` 0회다. 값 비교 없이 쏘는 mock 은 1회로 갈린다.
- 시그널 userdata 는 읽을 때마다 새것이라 표의 키로 못 쓴다. Instance userdata 도 Lua 참조가 사라지면 재생성된다.
- 트윈은 대상이 파괴돼도 끝까지 돌고, 핸들을 잃으면 Cancel 할 수 없다. 무한 트윈은 파괴 전에 Cancel 한다.
- Luau weak-key 표는 ephemeron 이 아니다. 값이 키를 잡으면 영구 누수다. 프로브에서 포획 변수를 nil 로 지우면 결론이 뒤집힌다.
- `init.luau` 의 `./` 는 폴더의 형제다(안은 `@self/`). 잘못된 require 는 strict 면 `Unknown require` 로 잡히지만, 다른 모듈로 풀리는 오타는 못 잡는다. 실제로 require 하는 테스트를 둔다.
- `.luaurc` alias 값은 `./` 로 시작해야 CLI 런타임에서 풀린다. luau-lsp 는 `./` 없는 alias 와 symlink 도 풀어 에디터만 깨끗해 보인다.
- `Active = true` 는 GUI 대 GUI 클릭 관통을 막지 못한다. 투명한 TextButton 싱크를 깐다.
- 타입 검사기는 병렬 단계의 금지 API, SharedTable 값 제약, Tween 목표 표를 검사하지 않는다.
