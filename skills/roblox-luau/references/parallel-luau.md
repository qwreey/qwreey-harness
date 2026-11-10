# parallel-luau — Actor, 병렬 단계, 스레드 안전 등급, Actor 메시징, SharedTable

## 이 파일이 답하는 질문
- Q1 스크립트를 Actor 아래에 두기만 하면 병렬로 도나? `task.desynchronize` 와 `ConnectParallel` 은 무엇이 다른가?
- Q2 병렬 단계에서 무엇을 부르면 안 되나? API 문서의 "Thread Safety" 표기는 어떻게 읽나?
- Q3 타입 검사기가 병렬 단계의 금지 API 사용을 잡아 주나?
- Q4 Actor 사이에 데이터를 어떻게 넘기나? 메시지는 복사인가 참조인가? 함수를 보낼 수 있나?
- Q5 SharedTable 에는 무엇을 넣을 수 있고, 타입 정의는 그 제약을 얼마나 표현하나?
- Q6 병렬화의 비용은 어디서 생기나(공식 문서가 말하는 범위)?

## 목차
- §1 실행 모델: Actor 와 직렬/병렬 단계
- §2 `task.desynchronize` / `synchronize` / `ConnectParallel` 의 타입
- §3 스레드 안전 등급(Thread Safety)
- §4 타입 검사기는 실행 단계를 모른다
- §5 Actor 메시징의 의미
- §6 Actor 메시징의 타입
- §7 Actor 별 VM, 모듈 격리, `require` 금지
- §8 SharedTable 의 의미
- §9 SharedTable 의 타입과 반복 문제
- §10 성능 특성(공식 문서 문구)
- §11 문서끼리, 문서와 타입 정의가 어긋나는 곳
- §12 사용자 저장소 현황

표기
- `verified`: `snippets/rbx-parallel-*.luau` 가 `luau-lsp analyze --platform=roblox --definitions=typedefs/globalTypes.d.luau --flag:LuauSolverV2=true` 에서 표식대로 통과했다(luau-lsp 1.70.1·1.69.0). 검사는 `python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/rbx-*.luau` 다(머리 `--@lsp-roblox` 파일은 Roblox 모드). 상류 luau-lsp `main`(`5f290c82`, 2026-11-10)의 `globalTypes.None.d.luau` 로도 같은 결과였다.
- `described`: Roblox 공식 문서 서술만 있다. 런타임 동작이라 Studio 가 있어야 확인할 수 있고, **아무도 Studio 에서 재지 않았다**(§12).
- 문서 날짜: 아래 Roblox 페이지는 모두 `last_updated: 2026-11-10T00:40Z` 이고 2026-11-10 에 받았다(끝 "출처").
- mock 흉내: 이 주제를 흉내 내는 mock 은 사실상 없다. rbvm 은 `ConnectParallel` 을 경고와 함께 `Connect` 로 바꾸고 `task.desynchronize` 를 그대로 넘긴다. quad 의 devui 킷은 빈 `ConnectParallel` 을 둔다. 즉 **CLI 와 mock 에서는 모든 병렬 코드가 직렬로 돈다.** 스레드 안전 위반, 메시지 복사, VM 격리는 Studio 에서만 드러난다.

---

## §1 실행 모델: Actor 와 직렬/병렬 단계
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: `scripting/multithreading.md` "Split code into multiple threads", `reference/engine/classes/Actor.md`, `reference/engine/libraries/task.md`

- 병렬 실행의 단위는 `Actor` 인스턴스다. 스크립트는 **가장 가까운 조상 Actor** 에 속한다. Actor 를 Actor 안에 넣는 것은 보통 권하지 않는다.
- Actor 아래에 둔 것만으로는 병렬이 되지 않는다. 기본은 여전히 직렬이다. 병렬로 가려면 다음 둘 중 하나를 쓴다.
  - `task.desynchronize()`: 직렬 단계에서 부르면 스크립트를 멈추고 **다음 병렬 단계에서** 다시 이어 간다. 이미 병렬 단계면 바로 돌아오고 아무 일도 하지 않는다.
  - `signal:ConnectParallel(fn)`: 이벤트가 오면 콜백을 병렬(desynchronized) 상태로 바로 실행한다. 콜백 안에서 `desynchronize` 를 부를 필요가 없다.
- `task.synchronize()` 는 반대 방향이다. 병렬 단계에서 부르면 다음 직렬 단계까지 멈춘다. 이미 직렬이면 바로 돌아온다.
- 두 함수 모두 **Actor 의 자손인 스크립트만** 부를 수 있다. 밖에서 부르면 에러다. ModuleScript 는 Actor 자손 스크립트가 require 한 인스턴스라면 부를 수 있다.
- 같은 Actor 안의 스크립트들은 서로에 대해 **항상 순차로** 돈다. 병렬성을 얻으려면 Actor 가 여럿 있어야 한다.
- 전형적인 모양: 병렬로 계산하고(`Raycast` 같은 Safe API, 순수 계산), `task.synchronize()` 뒤에 인스턴스를 고친다.

## §2 `task.desynchronize` / `synchronize` / `ConnectParallel` 의 타입
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `snippets/rbx-parallel-task-phase-signatures.luau`

| API | 정의 파일의 타입 | 결과 |
|---|---|---|
| `task.desynchronize`, `task.synchronize` | `() -> ()` | 인자를 주면 에러, 반환값을 `number` 에 담으면 에러 |
| `RBXScriptSignal<T...>.ConnectParallel` | `(self, callback: (T...) -> ()) -> RBXScriptConnection` | `Connect` 와 같은 콜백 타입이다. `Heartbeat`(`RBXScriptSignal<number>`)에 `(dt: string) -> ()` 를 주면 에러 |

- 공식 문서는 `desynchronize` 를 "yieldable function" 이라 하지만, 타입에는 양보 여부가 드러나지 않는다(Luau 타입 체계에 그런 표기가 없다).

## §3 스레드 안전 등급(Thread Safety)
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: `scripting/multithreading.md` "Thread safety", `classes/Instance.md`, `classes/WorldRoot.md`, `classes/Workspace.md`, `classes/BasePart.md`, `classes/TaskScheduler.md`

공식 가이드의 등급표:

| 가이드 표기 | API 페이지 원문 표기 | 속성 | 함수 |
|---|---|---|---|
| Unsafe | `Unsafe` | 병렬에서 읽기도 쓰기도 안 됨 | 병렬에서 호출 안 됨 |
| Read Parallel | `ReadSafe`(속성 JSON 블록의 `"thread_safety"`) | 읽기만 됨 | 해당 없음 |
| Local Safe | (`LocalSafe` 로 추정, 이번 조사 페이지에서는 못 봄) | 같은 Actor 안에서는 사용 가능. 다른 Actor 는 읽기만 | 같은 Actor 안에서만 호출 |
| Safe | `Safe` | 읽기·쓰기 됨 | 호출 됨 |

- **표기가 없으면 Unsafe 다**(가이드의 Info 상자).
- 엔진이 병렬 단계의 금지 접근을 "자동으로 감지하고 막는다". 즉 런타임 에러로 드러난다. 정적 검사는 없다(§4).
- 등급은 API 페이지의 메서드 줄 `*Security: … · Thread Safety: …*` 와 속성 JSON 의 `"thread_safety"` 에 있다.

2026-11-10 기준 페이지에서 센 분포(규칙을 외우는 대신 표를 찾아보라는 근거):

| 페이지 | 속성 | 메서드 Safe | 메서드 Unsafe |
|---|---|---|---|
| `Instance` | 10개 모두 `ReadSafe`(Name, Parent 포함) | 17 | 22 |
| `Workspace` | 51개 모두 `ReadSafe` | 4 | 7 |
| `BasePart` | 69개 모두 `ReadSafe` | 9 | 23 |

- 병렬에서 쓸 수 있는 대표(Safe): `FindFirstChild`, `FindFirstChildWhichIsA`, `GetChildren`, `GetDescendants`, `GetAttribute`, `GetAttributes`, `HasTag`, `GetTags`, `IsDescendantOf`, `GetActor`, `WorldRoot:Raycast`, `Blockcast`, `Spherecast`, `GetPartBoundsInBox`, `GetPartBoundsInRadius`, `GetPartsInPart`, `Actor:SendMessage`, `BindToMessage(Parallel)`, `SharedTableRegistry:Get/SetSharedTable`.
- 병렬에서 못 쓰는 대표(Unsafe): `SetAttribute`, `AddTag`, `RemoveTag`, `Clone`, `Destroy`, `ClearAllChildren`, **`WaitForChild`**, `GetAttributeChangedSignal`, `QueryDescendants`, `WorldRoot:Shapecast`, `BulkMoveTo`, 옛 `FindPartOnRay*` 와 `FindPartsInRegion3*` 전부, 소문자 옛 별칭(`findFirstChild` 등).
- 모든 속성이 `ReadSafe` 이므로 **병렬 단계에서는 어떤 인스턴스 속성도 쓸 수 없다**(이 세 클래스 기준). 쓰기는 `task.synchronize()` 뒤로 미룬다.
- 눈여겨볼 비대칭: `Shapecast` 는 Unsafe, `Blockcast`/`Spherecast` 는 Safe. `FindFirstChild` 는 Safe 인데 옛 소문자 `findFirstChild` 는 Unsafe.

## §4 타입 검사기는 실행 단계를 모른다
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `snippets/rbx-parallel-task-phase-signatures.luau` (bug-present 2줄, 대조군 4줄)

- `ConnectParallel` 콜백 안에서 `part.Name = …`(속성 쓰기, `ReadSafe`)와 `part:Destroy()`(Unsafe)를 해도 진단이 0건이다. `task.desynchronize()` 뒤도 마찬가지다.
- 정의 파일에 스레드 안전 등급 정보가 없고, Luau 타입 체계에 "단계" 개념이 없다. 그래서 **병렬 코드의 안전성은 정적으로 보장되지 않는다.** Studio 에서 실행해 봐야 드러난다.
- 처방: 병렬 구간을 짧은 함수로 떼고, 그 안에서 부르는 API 를 §3 의 Safe 목록과 손으로 대조한다. 쓰기는 `task.synchronize()` 아래에 모은다.
- 참고: luau-lsp 는 sourcemap 없이는 인스턴스 경로 `require(...)` 를 "Unknown require: unsupported path" 로 거부한다(2026-11-10 실측). 그래서 "병렬 단계의 require" 는 이 스니펫에서 시험하지 않았다.

## §5 Actor 메시징의 의미
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: `scripting/multithreading.md` "Actor messaging", `classes/Actor.md` SendMessage/BindToMessage/BindToMessageParallel

- `actor:SendMessage(topic, ...)`: 직렬·병렬 어느 쪽에서든 보낼 수 있다. **비동기**다. 보내는 쪽은 막히거나 양보하지 않는다.
- 메시지 하나는 Actor 하나에만 간다. 그 Actor 안에서는 한 topic 에 콜백을 여럿 묶을 수 있다.
- **그 Actor 의 자손 스크립트만** 메시지에 바인드할 수 있다.
- `BindToMessage` 콜백은 직렬 문맥에서, `BindToMessageParallel` 콜백은 병렬 문맥에서 불린다. 둘 다 `RBXScriptConnection` 을 돌려주므로 `Disconnect` 로 끊는다.
- 인자는 **VM 경계를 넘어 복사**된다(참조가 아니다). 큰 테이블을 보내면 호출마다 전체 복사가 일어난다. **함수는 VM 에 묶여 있어 보낼 수 없다.**
- SharedTable 은 메시지로 보내도 복사되지 않는다(§8). 큰 공유 상태는 SharedTable 로 넘긴다.

## §6 Actor 메시징의 타입
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일) · 근거: `snippets/rbx-parallel-actor-messaging-types.luau`

| 항목 | 정의 파일 | 결과 |
|---|---|---|
| 상속 | `declare extern type Actor extends Model` | `Model` 에 대입 가능, `BasePart` 에 대입하면 에러 |
| `SendMessage` | `(self, topic: string, ...: any): ()` | topic 에 숫자를 주면 에러. **함수 값도 통과한다**(bug-present, 런타임에는 실패한다고 문서가 말함) |
| `BindToMessage`, `BindToMessageParallel` | `(self, topic: string, func: (...any) -> ...any): RBXScriptConnection` | 콜백 파라미터에 어떤 타입을 적어도 통과한다. 송신 쪽 인자 타입과 연결되지 않는다 |
| `Instance:GetActor` | `(self): Actor?` | `local a: Actor = script:GetActor()` 는 에러. 좁힌 뒤에 쓴다 |

- 메시지 페이로드는 타입상 `any` 다. topic 별 페이로드 타입을 지키려면 보내는 함수와 받는 콜백을 한 모듈에 묶는 얇은 래퍼(예: `sendGreeting(actor, s: string)` 과 `onGreeting(actor, fn: (string) -> ())`)를 직접 만들어야 한다. 이 처방은 described(이번에 래퍼 자체는 시험하지 않았다).

## §7 Actor 별 VM, 모듈 격리, `require` 금지
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: `classes/Actor.md` Notes, `scripting/multithreading.md` Warning

- **Actor 마다 Luau VM 이 따로 있다.** Actor 가 require 한 ModuleScript 는 다른 Actor 나 메인 스레드와 공유·캐시되지 않는다. VM 마다 모듈을 따로 실행하므로 **모듈 수준 상태는 Actor 별로 갈라진다.** 싱글턴 모듈에 공유 상태를 두는 설계는 Actor 를 넘으면 깨진다.
- `script:GetActor()` 는 ModuleScript 에서 부르면, 그 ModuleScript 가 Actor 의 자손이 아닌 한 `nil` 이다. ReplicatedStorage 같은 곳에 있는 모듈은 Actor 가 require 해도 자손으로 치지 않는다.
- **병렬(desynchronized) 단계에서는 `require()` 를 쓸 수 없다.** 쓸 모듈은 직렬 문맥에서 먼저 require 한다.

## §8 SharedTable 의 의미
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: `datatypes/SharedTable.md`, `classes/SharedTableRegistry.md`, `scripting/multithreading.md` "Shared table"

- 여러 Actor 의 스크립트가 함께 보는 테이블 비슷한 자료 구조다. 넘기는 길은 둘이다. `SharedTableRegistry:GetSharedTable(name)`(없으면 새로 만들어 등록)과 `SetSharedTable(name, st | nil)`, 또는 `SendMessage` 에 실어 보내기.
- 보내도 복사하지 않는다. 한 Actor 의 갱신이 **즉시** 다른 Actor 에 보인다.
- **키**: 문자열, 또는 0 이상 2^32 미만의 정수만. **값**: boolean, number, Vector, string, SharedTable, 직렬화 가능한 데이터 타입만. 함수와 `true` 키는 `pcall` 이 실패한다(문서 예제).
- `SharedTable.new(t)` 는 `t` 안의 테이블 값을 새 SharedTable 로 바꾼다. 넣을 수 없는 키·값이 있으면 생성이 실패한다.
- 서로 다른 SharedTable 은 내용이 같아도 `==` 가 거짓이다.
- 동결: `cloneAndFreeze` 로 읽기 전용 사본을 만든다. 동결된 표를 고치면 에러다.
- 원자성
  - `clear`, 얕은 `clone` 은 원자적이다. 얕은 clone 은 일관된 스냅샷을 준다.
  - 깊은 `clone(st, true)` 는 표 하나하나는 원자적이지만 **전체로는 원자적이지 않다.** 동시에 고쳐지는 그래프에서는 표끼리 시점이 어긋날 수 있다.
  - `st.x = st.x + 1` 같은 읽고-쓰기는 사이에 다른 Actor 가 끼어들 수 있어 틀린다. `SharedTable.update(st, k, f)` 나 `SharedTable.increment(st, k, delta)` 를 쓴다. `update` 의 `f` 는 경합이 있으면 **여러 번 불릴 수 있다**(부작용 금지).

## §9 SharedTable 의 타입과 반복 문제
status: verified · last-confirmed: luau-lsp 1.70.1 (1.69.0 동일, 상류 main 정의 동일) · 근거: `snippets/rbx-parallel-sharedtable-types.luau`, `snippets/rbx-parallel-sharedtable-iter-old-solver.luau`

정의 파일:
```luau
declare extern type SharedTable with
  [string | number]: any
  function __iter(self): (any, number) -> (number, any)
end
```

| 시도 | 결과 |
|---|---|
| `st[true] = 1` | 에러(키 타입이 `string | number` 가 아님) |
| `st.f = function() end`, `SharedTable.new({ f = function() end })` | 진단 0건(bug-present). 값이 `any` 라 함수 금지를 표현하지 못한다. 런타임에서는 실패(문서) |
| `st[-1] = …` | 진단 0건(bug-present). 키 범위(0 이상, 2^32 미만)는 타입으로 표현되지 않는다 |
| `SharedTable.increment(...)` 를 `string` 에 | 에러(반환 `number`) |
| `SharedTable.clone(st, 1)` | 에러(`deep: boolean?`) |
| `SharedTableRegistry:SetSharedTable("W", {})` | 에러(일반 테이블은 `SharedTable` 이 아님) |
| **새 솔버**에서 `for k, v in st do` | **에러: `__iter metamethod must return (next[, table[, state]])`**. 공식 문서의 "Element Iteration" 예제와 같은 코드다. `for k, v in SharedTable.clone(st, false)` 도 같다 |
| 새 솔버에서 반복 키 `k` 를 `string` 에 | 에러: `got 'number'`. 정의가 키를 `number` 로 선언했다. 문자열 키를 허용하는 문서와 맞지 않는다 |
| **옛 솔버**(`--flag:LuauSolverV2=false`)에서 같은 반복 | 진단 0건 |

- 새 솔버 환경에서 SharedTable 을 반복하려면 지금은 캐스트(`for k, v in st :: any do`)나 `--!nonstrict` 파일로 피해야 한다. 이 우회는 described(시험하지 않음).
- 실무 결론: SharedTable 의 키·값 제약은 런타임에서만 지켜진다. 넣는 쪽 함수에 구체 타입을 붙인 래퍼를 둔다.

## §10 성능 특성(공식 문서 문구)
status: described · last-confirmed: create.roblox.com 2026-11-10 · 근거: 아래 각 문서

공식 문서에는 **수치가 없다.** 아래는 문구만 옮긴 것이다. 직접 재려면 Studio 의 MicroProfiler 가 필요하다.

| 비용 | 문서가 말하는 것 | 출처 |
|---|---|---|
| 단계 전환 | `ConnectParallel` 은 `Connect` + `task.desynchronize()` 와 비슷하지만 "more efficient" | `datatypes/RBXScriptSignal.md` |
| 단계 전환 | `desynchronize` 는 **다음 병렬 단계**까지, `synchronize` 는 **다음 직렬 단계**까지 기다린다. 전환마다 프레임 안의 다음 기회를 기다리므로 잦은 왕복은 지연을 만든다(뒷 문장은 추론) | `libraries/task.md` |
| 데이터 모델 직접 통신 | 병렬 스크립트는 대체로 데이터 모델에 쓸 수 없어 "may force scripts to synchronize frequently, which can impact performance" | `multithreading.md` |
| 메시지 | 인자는 복사. "Sending large tables incurs a full copy on each call" | `classes/Actor.md` |
| SharedTable | 복사 없이 공유. clone 은 구조 공유(structural sharing)로 자원 효율적 | `multithreading.md` |
| SharedTable 갱신 | "`increment` is much faster than `update`" | `datatypes/SharedTable.md` |
| 긴 계산 | 병렬에서도 길고 양보 없는 계산은 다른 스크립트를 막아 랙을 만든다 | `multithreading.md` Best practices |
| Actor 수 | 코어보다 많은 Actor 가 부하 분산에 낫다(예: 4코어 대상이어도 64개 이상). 다만 논리 단위로 나누고, 너무 많으면 유지보수가 어렵다 | `multithreading.md` Best practices |
| 언제 쓰나 | "computationally expensive tasks that don't need to access the data model" | `performance-optimization/improve.md` |
| 작업 스레드 수 | `TaskScheduler.ThreadPoolConfig`(`Auto` 기본, `ThreadsN`, `PerCoreN`) | `enums/ThreadPoolConfig.md` |

## §11 문서끼리, 문서와 타입 정의가 어긋나는 곳
status: verified(타입 쪽 항목) / described(문서끼리 항목) · last-confirmed: 2026-11-10

| # | 어긋남 | 근거 |
|---|---|---|
| 1 | 가이드는 등급을 "Read Parallel", "Local Safe" 로 쓰고, API 페이지 원문은 `ReadSafe` 다. 검색할 때는 원문 표기로 찾는다 | `multithreading.md` vs `classes/Instance.md` |
| 2 | 가이드는 Actor 가 "`DataModel` 을 상속한다"고 쓴다. 클래스 페이지와 정의 파일은 `Model` 상속이다 | `multithreading.md` "Split code…" vs `classes/Actor.md` `inherits: Model`, `snippets/rbx-parallel-actor-messaging-types.luau` |
| 3 | 가이드의 레이캐스트 예제는 `task.desynchronize()` 뒤 병렬 구간에서 `Instance.new("Explosion")` 을 부른다. 그런데 `Instance.new` 에는 스레드 안전 표기가 없고, 가이드는 "표기가 없으면 Unsafe" 라고 한다. 둘 중 하나는 틀렸다. Studio 확인 필요 | `multithreading.md` 예제 + Info 상자, `datatypes/Instance.md` |
| 4 | 문서의 SharedTable 반복 예제(`for k, v in st do`)가 새 솔버 strict 에서 타입 에러다. 정의의 `__iter` 선언 모양이 새 솔버 규칙과 맞지 않는다. 상류 luau-lsp `main`(2026-11-10)도 같다 | `snippets/rbx-parallel-sharedtable-types.luau` |
| 5 | 문서는 문자열 키를 허용하지만, 정의의 `__iter` 는 키를 `number` 로 준다 | 같은 스니펫 |
| 6 | 문서는 함수 값, 함수 메시지를 금지하지만, 정의는 `any` 라 통과시킨다 | `snippets/rbx-parallel-sharedtable-types.luau`, `snippets/rbx-parallel-actor-messaging-types.luau` |
| 7 | 문서의 `SetSharedTable` 반환은 `()`, 정의는 `nil`. `SharedTable.new(t: table)` 은 정의에서 `{ [any]: any }?` 다. 실사용 차이는 없다 | `classes/SharedTableRegistry.md` vs 정의 16446, 19092 줄 |
| 8 | `SharedTable.new` 설명의 링크가 `ShareTableRegistry`(오타)를 가리킨다 | `datatypes/SharedTable.md` |

## §12 사용자 저장소 현황
status: verified(grep) · last-confirmed: 2026-11-10 · 근거: `rg 'desynchronize|ConnectParallel|BindToMessageParallel|SharedTable\.'` (`/code/Projects`, refs·vendor·정의 파일 제외)

- 실제로 병렬 실행을 쓰는 코드는 없다. 이름이 나오는 곳은 셋이고 모두 흉내(shim)다.
  - `rbvm/src/signal.luau:156` 의 `ConnectParallel` 은 경고를 찍고 `Connect` 로 대신한다.
  - `rbvm/src/task.luau:83` 은 `task.desynchronize` 를 그대로 넘긴다.
  - `quad/kits/roblox-devui/src/Input.luau:56` 은 빈 `ConnectParallel` 이다.
- 따라서 이 파일의 런타임 서술(§1, §5, §7, §8, §10)은 사용자 경험으로 뒷받침되지 않는다. 처음 도입할 때 Studio 에서 확인해야 한다.

---

## 출처
| 자료 | 판/날짜 |
|---|---|
| https://create.roblox.com/docs/en-us/scripting/multithreading.md | last_updated 2026-11-10T00:40:51Z, 받은 날 2026-11-10 |
| https://create.roblox.com/docs/en-us/reference/engine/classes/Actor.md | 2026-11-10T00:40:46Z |
| https://create.roblox.com/docs/en-us/reference/engine/datatypes/SharedTable.md | 2026-11-10T00:40:49Z |
| https://create.roblox.com/docs/en-us/reference/engine/classes/SharedTableRegistry.md | 2026-11-10T00:40:48Z |
| https://create.roblox.com/docs/reference/engine/libraries/task.md | 2026-11-10T00:40:49Z (engine `llms.txt` 경유) |
| https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptSignal.md | 2026-11-10T00:40:49Z |
| https://create.roblox.com/docs/en-us/reference/engine/classes/{Instance,Workspace,WorldRoot,BasePart}.md, `datatypes/Instance.md` | 2026-11-10 |
| https://create.roblox.com/docs/reference/engine/classes/TaskScheduler.md, `enums/ThreadPoolConfig.md` | 2026-11-10T00:40:49Z |
| https://create.roblox.com/docs/en-us/performance-optimization/{improve,design}.md, `microprofiler/task-scheduler.md` | 2026-11-10T00:40:42Z |
| `luau-kb/typedefs/globalTypes.d.luau` | quad `2ad2c03e`(2026-09-02), md5 `be071eac…` |
| 상류 `JohnnyMorganz/luau-lsp` `scripts/globalTypes.None.d.luau` | `main` 최신 커밋 `5f290c82`(2026-11-10) — §9 결과 동일 |
| `luau-lang/rfcs` `docs/` | `5fcbb5a2`(2026-10-16). 문서 93개 중 Parallel Luau, Actor, SharedTable 관련 RFC 없음(엔진 기능이라 Luau 언어 RFC 대상이 아님) |

## 정정
- 원천 저장소 서술 중 틀린 것은 없다(이 주제를 쓴 저장소가 없다). Roblox 문서와 정의 파일의 어긋남은 §11 에 모았다(문서 쪽 정정 후보).
