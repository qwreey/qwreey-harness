---
title: "필요한 부분만 흉내 내기, 차이 기록, 충실도 검증"
description: "엔진 mock 은 테스트가 기대는 표면만 만들고 주입을 먼저 쓴다. getfenv 로 모듈 환경에 game·task 넣기, 검증된 Signal·Instance·task mock 모양, 엔진과의 차이 표, Studio 충실도 검증 절차"
keywords:
  - "mock 범위"
  - "mock 충실도 검증"
  - "mock fidelity"
  - "mock 차이 기록"
  - "mock 보다 주입"
  - "dependency injection"
  - "getfenv 전역 주입"
  - "attempt to modify a readonly table"
  - "_G.task"
  - "Signal mock 역순 순회"
  - "task mock flush"
  - "가상 시계"
  - "virtual clock"
  - "table.sort 안정 정렬 아님"
  - "makeFakeStore"
  - "quad-mock"
  - "rbvm 가상 Signal"
kind: reference
category: roblox/testing
tags: [studio]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.742
---
# mocks — 필요한 부분만 흉내 내기, 차이 기록, 충실도 검증

## 이 파일이 답하는 질문
- Q1 mock 을 어디까지 만들어야 하나?
- Q2 mock 없이 테스트할 방법은 없나?
- Q3 luau CLI 에서 엔진 전역(`game`, `task`, `Instance`)을 모듈에 어떻게 넣나?
- Q4 Signal, Instance, task, 데이터 타입 mock 은 어떤 모양이 검증됐나?
- Q5 mock 과 실제 엔진의 차이를 어디에 어떻게 적나?
- Q6 mock 이 실제와 맞는지 어떻게 확인하나?

## 목차
- §1 범위: 필요한 부분만
- §2 mock 보다 주입
- §3 전역 주입 (getfenv)
- §4 검증된 모양
- §5 차이 기록
- §6 충실도 검증 절차
- §7 실례: rbvm

---

## §1 범위: 필요한 부분만
status: described · 원천: quad `quad-base/test/mock.luau` 머리 주석, quad `scripts/doc-snippets-runshim.luau` 머리 주석

- 테스트 대상이 실제로 쓰는 표면만 만든다. quad-base mock 은 parent/children 트리, 타입 검증 없는 property bag, 속성별 변경 신호, `IsA`(계층 없는 `ClassName` 비교)만 만든다. 클래스별 속성 스키마, `WaitForChild`, `DataModel` 은 만들지 않는다. 이유는 "코어가 `inst` 를 `any` 로 취급하고 Instance 고유 동작을 참조하지 않으므로 mock 이 Roblox 충실도를 가질 이유가 없다"이다.
- 반대로 **테스트가 기대는 계약은 충실히** 만든다. quad-base mock 은 생명주기 판정이 `Connection.Connected` 에 기대므로 `Destroy` 를 Roblox 순서대로 만들었다: Destroying 발화 → `Parent = nil` → 자손 Destroy → 그 Instance 의 모든 연결 끊기 → 두 번째 Destroy 는 no-op.
- 흉내 낼 수 없는 것은 흉내 내지 않고 **표시한다.** quad runshim 은 데이터 타입을 "어떤 필드를 읽어도 값 객체를 돌려주는" 관대한 객체로 만들고, 값의 의미에 기대는 문서 스니펫은 `no-run` 으로 표시한다. 엔진 GC 가 userdata 를 수거·재생성하는 동일성 문제도 mock 범위 밖으로 두고 실기기 몫으로 남겼다.

## §2 mock 보다 주입
status: described · 원천: table-sim `<비공개>`; Studio 내장 skill `rbx-unit-test` "ISOLATING DEPENDENCIES"

- 시간: `os.clock()` 을 안에서 부르지 말고 `now` 를 인자로 받는다. `elapsed(state, now)` 처럼 테스트가 시각을 정한다. 가상 시계 mock 이 필요 없다.
- 서비스: `Module.new(deps)` 로 넘긴다. 가짜는 인터페이스를 만족하는 평범한 테이블이고, 필요하면 호출을 기록한다(`rbx-unit-test` 의 `makeFakeStore`: `GetAsync` 는 준비된 값, `SetAsync` 는 `calls` 에 기록).
- 엔진 무관 로직은 디렉터리로 분리한다(table-sim `<비공개>`). 이 부분은 mock 없이 `luau` 로 돈다.
- 주입으로 안 되는 경우(모듈이 전역 `game`, `task`, `Instance` 를 직접 부름)에만 §3 으로 간다.

## §3 전역 주입 (getfenv)
status: verified · last-confirmed: luau 0.742 (이 저장소 수동 실측) · 원천: quad `scripts/doc-snippets-runshim.luau` `M.install`, quad `quad-roblox/test/spec.handlers.luau` 머리 주석

- luau CLI 에서 `_G.task = x` 는 `attempt to modify a readonly table` 로 실패한다. 진입 스크립트에서 `task = x` 로 전역을 대입하면 그 스크립트에서만 보이고, require 한 모듈은 여전히 `nil` 을 본다(모듈마다 환경이 따로다). 그래서 대상 모듈의 함수 하나를 잡아 `getfenv(f)` 로 그 모듈의 환경을 얻고 거기에 넣는다. 이렇게 넣은 값은 그 모듈에서 보인다.

```luau
local env = getfenv(SomeModule.someFunction)
env.game = gameMock
env.task = taskMock
env.Instance = { new = mock.Instance.new }
```

- 모듈이 **최상위에서 바로** 전역을 쓰면 require 단계에서 이미 실패하므로 이 방식이 통하지 않는다. 그런 모듈은 전역을 함수 안에서 읽게 하거나 §2 로 바꾼다.
- quad runshim 은 같은 환경에 두 번 넣지 않도록 `seen[env]` 로 거르고, 넣은 모듈 수를 돌려준다.

## §4 검증된 모양
status: described · 원천: quad `quad-base/test/mock.luau`, quad `scripts/doc-snippets-runshim.luau`, rbvm `src/signal.luau`(가상 Signal)

| 대상 | 모양 | 주의 |
|---|---|---|
| Signal | `Connect` → `{ Connected, Disconnect }`, `Fire` 는 연결 목록 **스냅샷**을 떠서 **역순**으로 순회하고 `Connected` 인 것만 부른다 | quad mock 의 역순 순회는 Studio 실측(연결 역순 발화)과 맞는다. 정순으로 부르는 mock(rbvm 가상 Signal)은 실측과 달랐다. rbvm 가상 Signal 은 발화 중 자기 연결을 끊으면 다음 핸들러를 건너뛰었다(rbvm B1, 엔진은 나머지를 다 부름). quad mock 은 스냅샷 순회로 이 경우를 다룬다 |
| Instance | `ClassName`, `Name`, `Parent`, children, property bag, `GetPropertyChangedSignal`, `Destroying`, `Destroy` | 속성 대입마다 신호를 **즉시** 발화하면 Deferred 엔진과 다르다(`env-dependence.md` §2) |
| task | `spawn` 은 즉시 resume, `defer/delay` 는 `{at, f, args}` 를 큐에 넣고 `flush()` 가 가상 시계 순서로 꺼낸다, `wait(t)` 는 즉시 `t` 를 돌려준다 | 아래 "같은 시각의 순서" 참고 |
| 데이터 타입 | 아무 필드나 읽으면 값 객체, 호출하면 값 객체, 산술은 왼쪽 값 | 값의 의미가 없다. 값에 기대는 테스트는 `no-run` |
| Enum | `Enum.X.Y` 를 처음 읽을 때 `{ Name, EnumType, Value = 0 }` 을 얼려 캐시 | 같은 항목은 같은 테이블이라 `==` 가 성립한다 |
| `game:GetService` | 이름별 테이블, 모르는 서비스는 관대한 값 객체 | 모르는 서비스를 조용히 통과시키므로, 테스트 대상이 쓰는 서비스는 명시적으로 만든다 |

**같은 시각의 순서 (실측, luau 0.742).** quad runshim 의 `flush()` 는 매번 `table.sort(queue, function(a, b) return a.at < b.at end)` 로 정렬한 뒤 맨 앞을 꺼낸다. `table.sort` 는 안정 정렬이 아니어서, 같은 `at` 항목이 3개면 FIFO 가 유지되지만 5개부터 섞인다(5개: `1,4,2,3,5`, 40개: `1,26,3,28,…`). 같은 프레임에 `task.defer` 를 여럿 거는 코드의 순서를 이런 큐로 테스트하면 엔진과 다른 순서가 나올 수 있다. 큐에 삽입 번호를 두고 `(at, seq)` 로 비교하면 막을 수 있다. 엔진 쪽 같은 프레임 defer 순서는 이 저장소가 Studio 로 재지 않았다.

## §5 차이 기록
status: described · 원천: quad `quad-base/test/mock.luau`("Roblox 와 다른 점 하나"), quad runshim 머리 주석, rbvm engine-behavior "rbvm 영향" 열

- mock 파일 **머리 주석**에 "흉내 내는 것", "흉내 내지 않는 것", "엔진과 다른 점"을 적는다. 테스트를 읽는 사람이 mock 의 한계를 파일 하나로 알 수 있어야 한다.
- 엔진과 다른 점은 표로 둔다. 형식 예:

| 동작 | mock | 엔진 (출처, 날짜, Studio 버전, 모드) | 영향 |
|---|---|---|---|
| 핸들러 순서 | 연결 역순 | 연결 역순 (rbvm engine-behavior, 2026-10-13, 0.742, Deferred) | 없음 |
| 속성 변경 신호 시점 | 대입 즉시 | 다음 resumption point, 중간값 안 보임 (quad m10 #2) | 중간값에 기대는 테스트는 Studio 로 |
| `task.wait(t)` | 즉시 `t` 반환 | 최소 한 프레임 | 시간 경과에 기대는 테스트 불가 |

- 주제별 "엔진 대 mock" 표가 이미 있다. 새 mock 의 차이 표를 쓸 때 출발점으로 쓴다: 신호 roblox-engine `signals-and-events.md` §8, Instance 수명 roblox-engine `instance-lifecycle.md` §8, 트윈 roblox-engine `tween-and-animation.md` §8, 트리 API roblox-engine `instance-api.md` §1(rbvm 열), require roblox-engine `require-in-roblox.md` §1. 각 reference 절의 `mock 흉내:` 줄이 그 동작을 흉내 내는 mock 이 있는지 적는다.
- 근거가 Studio 실측이 아니라 기억이나 문서 인용이면 그렇게 표시한다. rbvm known-issues 는 "전부 코드 리딩으로 찾았고 런타임에서 재현한 것은 하나도 없다"고 머리에 밝히고, 확인된 항목에 `[확인됨, 날짜]` 를 붙이게 했다.

## §6 충실도 검증 절차
status: described · 원천: rbvm `.claude/design/engine-behavior.md` 실측 방법, quad `.claude/audit/m10-events-studio-2026-09-03.md`

1. **시나리오를 엔진 API 만으로 쓴다.** mock 과 Studio 양쪽에서 같은 코드가 돌도록, 결과를 테이블로 `return` 한다(print 로 남기지 않는다).
2. **mock 에서 돌린다.** `luau` 로 실행하고 결과를 적는다.
3. **Studio 에서 돌린다.** `execute_luau` 로 같은 코드를 실행한다. Deferred 관측은 첫 호출에서 준비하고 두 번째 호출에서 읽는다(`studio-mcp.md` §5). 상태를 바꾸는 도구라 그 Studio 를 쓰는 사람이 없는지 먼저 확인한다.
4. **비교해 기록한다.** 같으면 차이 표의 해당 행에 출처와 날짜를 단다. 다르면 mock 을 고치거나, 고칠 수 없으면 차이 표에 올리고 그 동작에 기대는 테스트를 Studio 쪽으로 옮긴다.
5. **엔진이 바뀌면 다시 잰다.** 기록마다 Studio 버전을 붙여 두고, 버전이 바뀌었거나 SignalBehavior 모드가 다른 플레이스면 재측정 대상이다.
6. 실측 기록은 **저장소에** 남긴다(예: `.claude/design/engine-behavior.md`, `.claude/audit/`). Studio 테스트 플레이스에 진실 원천을 두지 않는다(table-sim CLAUDE.md).

## §7 실례: rbvm
status: described · 원천: rbvm `.claude/project-context.md`, `.claude/design/engine-behavior.md`, `.claude/design/known-issues.md`

- rbvm 은 Roblox 엔진 객체(`Instance`, `RBXScriptSignal`)와 전역 라이브러리(`Instance`, `require`, `coroutine`)를 Lua 테이블 프록시로 감싸 스크립트와 엔진 사이의 모든 연산을 가로채는 계층이다. `src/signal.luau` 는 `RBXScriptSignal` 을 대체하는 Signal 을 다시 구현했다. 즉 **엔진을 흉내 내는 환경 그 자체**이고, 흉내가 엔진과 어디서 다른지가 곧 결함 목록이다.
- `engine-behavior.md` 는 이 흉내의 충실도를 Studio 에서 잰 표다. 열이 "관찰 | 결과 | rbvm 영향" 이고, 영향 칸이 결함 ID(B1, S3, L6 …)로 이어진다. 예: 엔진은 연결 역순으로 발화하는데 rbvm 은 정순, 엔진은 발화 중 연결한 핸들러를 이번에 안 부르는데 rbvm 은 부른다, `WaitForChild("Nope", 0.3)` 은 엔진에서 0.33초 뒤 nil 인데 rbvm 은 timeout 을 무시한다.
- 표 머리에 날짜, Studio 버전, 플레이스, 모드(Deferred)를 적고 "Immediate 모드는 아직 재지 않았다", "아직 안 잰 것" 목록을 따로 둔다. 재지 않은 것을 잰 것처럼 쓰지 않는 형식의 본보기다.
- 같은 저장소의 known-issues 는 반대로 "코드 리딩만, 런타임 재현 없음"을 밝히고 항목마다 확신도를 단다. 두 문서를 나눠 두면 어떤 주장이 엔진 실측인지 바로 보인다.
