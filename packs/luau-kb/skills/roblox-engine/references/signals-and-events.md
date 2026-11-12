---
title: "RBXScriptSignal 의 배달 시점, 순서, 끊기, 속성 변경 신호"
description: "RBXScriptSignal 실측: Deferred 판정과 재개 지점 배달, 연결 역순 호출·발화 중 Connect·리스너 에러 격리, Disconnect 는 대기분을 버리고 Destroy 절단은 1회 배달, 같은 값 대입 Changed 0회, 시그널 userdata 신원"
keywords:
  - "Deferred 신호 순서"
  - "SignalBehavior"
  - "Deferred Immediate 판정"
  - "재개 지점"
  - "resumption point"
  - "핸들러 연결 역순"
  - "발화 중 Connect"
  - "Once Connected false"
  - "Disconnect 대기 배달"
  - "Destroy 로 끊긴 연결 대기분"
  - "같은 값 대입 Changed"
  - "GetPropertyChangedSignal 중간값"
  - "리스너 에러 격리"
  - "시그널 캐시 키"
  - "isUpdating 플래그 가드"
  - "Maximum event re-entrancy depth exceeded"
  - "Attempt to connect failed: Passed value is not a function"
kind: reference
category: roblox/signals
tags: [studio, correction]
last_verified: 2026-11-10
---
# signals-and-events — RBXScriptSignal 의 배달 시점, 순서, 끊기, 속성 변경 신호

## 이 파일이 답하는 질문
- Q1 이 플레이스는 Deferred 인가 Immediate 인가? 스크립트로 알 수 있나?
- Q2 `Fire()`, 속성 대입, `Destroy()` 직후에 핸들러가 이미 돌았나? 언제 도나?
- Q3 핸들러는 어떤 순서로 불리나? 발화 중에 연결·끊기를 하면?
- Q4 `Disconnect()` 와 `Destroy()` 는 대기 중인 배달을 어떻게 다루나?
- Q5 속성을 같은 값으로 다시 쓰면 `Changed` 가 오나? 한 프레임에 두 번 쓰면 핸들러는 무엇을 읽나?
- Q6 시그널 객체를 캐시 키로 써도 되나?
- Q7 mock 은 이 동작들을 흉내 내나?

## 목차
- §0 읽는 법: 측정 조건과 mock 약어
- §1 SignalBehavior 모드 판정
- §2 Deferred 배달 시점
- §3 핸들러 순서, 발화 중 연결·끊기, 에러 격리
- §4 끊기: `Disconnect()` 와 `Destroy()` 의 대기 배달
- §5 속성 변경 신호
- §6 시그널 객체의 신원과 모양
- §7 Immediate 모드에서 알려진 것 (문서뿐)
- §8 mock 과 엔진이 갈리는 지점 요약
- 모순 판정 · 정정 · 미판정

---

## §0 읽는 법: 측정 조건과 mock 약어

- **이 저장소가 Studio 에서 다시 잰 것은 없다.** 아래 Studio 사실은 원천 저장소의 실측 기록을 옮긴 것이라 `status: described` 다. 각 절에 원천의 Studio 버전, 날짜, DataModel, 신호 모드를 적었다.
- **신호 순서·시점에 관한 원천 실측은 모두 Deferred 플레이스에서 했다**(claude-doctor audit/09 §7). Immediate 에서 신호 동작을 잰 기록은 없다. Immediate 에 대한 서술은 Roblox 문서 인용이거나 CLI 심 결과다(§7). 예외 하나: quad `kit-studio-2026-10-15` 은 Immediate 플레이스였다(GUI 레이아웃·입력 관측, `REPORT.md:4`). 그 보고서에서 온 사실에는 Immediate 라고 적었다.
- mock 약어
  - **quad-mock**: quad `quad-base/test/mock.luau`. 동기 Signal. `Fire` 는 연결 목록 스냅샷을 **역순**으로 돈다. 속성 대입마다(같은 값이어도) 바로 발화한다.
  - **E79 심**: quad `.claude/audit/round13-e79-deferred-signals/env.luau`. quad-mock 위에 Deferred 를 흉내 낸 연구용 심. 같은 값 무발화, 연결별 큐, `flush()` 가 FIFO 로 비운다. 엔진 실측이 아니다.
  - **rbvm**: rbvm `src/signal.luau` 의 가상 Signal(엔진을 프록시로 감싸는 계층). 정순으로 부른다.
  - mock 을 만들거나 고치는 법은 luau-roblox `mocks.md`, Studio 로 재는 법은 luau-roblox `studio-mcp.md` §5.

## §1 SignalBehavior 모드 판정
status: described · last-confirmed: Roblox 문서 `scripting/events/deferred.md`(last_updated 2026-11-10), Studio 0.738(2026-09-10)·0.742(2026-10-13) 원천 실측 · 근거: quad `.claude/audit/studio-docs-2026-09-10.md:35,43-45`, rbvm `.claude/design/engine-behavior.md:14-15` · 후보: Q-017, R-07, Q-146

- `Workspace.SignalBehavior` 는 `Default`, `Immediate`, `Deferred` 셋이다. 문서(2026-11-10)는 `Default` 가 **지금은 Immediate 와 같고** 나중에 Deferred 로 바뀐다고 한다. 템플릿 플레이스는 처음부터 `Deferred` 다.
- **스크립트에서 `workspace.SignalBehavior` 를 읽을 수 없었다**(`not a valid member`, Studio 0.738·0.742). MCP 로도 읽거나 쓰지 못했다.
- 그래서 모드는 동작으로 판정한다. `BindableEvent:Fire()` 나 속성 대입 바로 다음 줄에서 핸들러가 아직 안 돌았고 `task.wait()` 뒤에 돌았으면 Deferred 다.
- 실측을 기록할 때는 Studio 버전과 이렇게 판정한 모드를 같이 적는다. 재현이 안 될 때 코드 탓인지 설정 탓인지 가를 수 있다.

mock 흉내: 해당 없음(모드는 플레이스 설정). quad-mock 과 rbvm 은 사실상 Immediate 처럼 동기로 부르고, E79 심만 Deferred 를 흉내 낸다.

## §2 Deferred 배달 시점
status: described · last-confirmed: Studio 0.742(rbvm, 2026-10-13, Edit, Deferred), quad 2026-09-02~10-13(Edit·Play, Deferred), quad 2026-10-15(Play, Immediate), 문서 2026-11-10 · 근거: 문서 `scripting/events/deferred.md` "Resumption points"; quad `.claude/audit/m5-unit1-studio-smoke-2026-09-02.md:29-45`, `.claude/audit/m10-events-studio-2026-09-03.md` §1 #8, `.claude/audit/kit-studio-2026-10-13/REPORT.md:48`, `.claude/audit/kit-studio-2026-10-15/REPORT.md:48-49`; devplorer `.claude/review/2026-10-20-client-palette-copy.md:49-52` · 후보: Q-018, Q-024, Q-027, Q-029, D-R40, R-14

- Deferred 에서 핸들러는 **다음 재개 지점(resumption point)** 에 돈다. 문서가 꼽는 재개 지점: 입력 처리, `RunService.PreRender`, 레거시 `wait()/spawn()/delay()`, `PreAnimation`, `PreSimulation`, `PostSimulation`, `task.wait/spawn/delay` 재개, `Heartbeat`, `BindToClose`.
- 그래서 `Fire()`, 속성 대입, `Destroy()` **직후 같은 줄기에서는 핸들러가 아직 안 돌았다.** 결과를 읽으려면 `task.wait()` 한 번 뒤에 읽거나, Studio MCP 에서는 다음 `execute_luau` 호출에서 읽는다.
- **"깃발 켜고 대입하고 끄기" 패턴은 깨진다.** 핸들러가 대입 뒤에 오므로, 핸들러가 볼 때 깃발은 이미 꺼져 있다(devplorer 실측). 양방향 바인딩의 동기 플래그 가드(`isUpdating`)도 같은 이유로 쓸모없다.
- 핸들러가 던진 에러는 **대입하거나 `Fire` 한 쪽으로 전파되지 않는다**(quad kit-studio 2026-10-13). 엔진은 리스너마다 에러를 격리한다(§3).
- 재진입 한도: 핸들러가 다시 신호를 일으키는 사슬은 깊이 10 에서 끊긴다(문서). 콜백이 같은 속성을 다시 건드리는 고리에서 "Maximum event re-entrancy depth exceeded" 경고가 한 번 열 때 7~30건 찍혔다(quad 2026-10-15, **Immediate 플레이스**, UIScale 애니메이션 중 위치 재배치). Deferred 에서 같은 고리를 잰 기록은 없다.
- 처방: 엔진 신호의 배달에 **동기 실행을 가정하지 않는다.** 생존 판정처럼 즉시 알아야 하는 것은 `Connected` 같은 동기 상태로 한다(§4, `instance-lifecycle.md` §2).

mock 흉내: quad-mock·rbvm 은 **아니오**(즉시 부른다). E79 심은 큐 + `flush()` 로 흉내 낸다. 재개 지점별 실제 위치와 재진입 한도 10 은 어느 mock 도 흉내 내지 않는다.

## §3 핸들러 순서, 발화 중 연결·끊기, 에러 격리
status: described · last-confirmed: Studio 0.742.0.7421053, `rbvm-test`, Edit, Deferred, 2026-10-13 (Immediate 미측정) · 근거: rbvm `.claude/design/engine-behavior.md:27-30,46`; quad `.claude/audit/tween-premises-2026-10-22/REPORT.md:16-17`, `docs/reference/roblox/05-onchange.md:98` · 후보: R-03, R-04, R-05, Q-027, Q-028

| 관찰 | 엔진 (Deferred) | quad-mock | rbvm |
|---|---|---|---|
| A, B, C 순서로 연결 후 발화 | **C, B, A** (연결 역순) | C, B, A | A, B, C |
| 같은 Instance 의 Destroying 핸들러 둘 | 2 → 1 (역순) | 역순 | — |
| 핸들러가 자기 연결을 Disconnect | 같은 발화의 나머지 핸들러는 다 불린다 | 같음(스냅샷 순회) | 다음 핸들러를 건너뛴다(B1) |
| 발화 중 새로 Connect 한 핸들러 | 이번 발화엔 안 불리고 다음 발화에서 **맨 먼저** | 이번엔 안 불림 | 같은 발화에서 불림 |
| `Once` 핸들러 안의 `conn.Connected` | **false** (부르기 전에 끊는다) | — | true(S3) |
| 한 핸들러가 던짐 | 나머지는 그대로 돈다(격리) | 던진 에러가 `Fire` 쪽으로 올라가고 나머지를 건너뛴다 | — |
| 같은 함수를 두 번 Connect | 연결 둘(멱등 아님) | 같음 | 같음 |

- **역순은 관측일 뿐 계약이 아니다.** 문서는 순서를 약속하지 않는다. 순서에 기대는 코드를 쓰지 않는다. 다만 mock 이 정순이면 순서에 기댄 버그가 mock 에서 숨는다. mock 은 역순으로 부르는 편이 엔진 관측과 맞는다.
- 순수 Luau 로 Signal 을 만들 때 흔한 결함 둘(rbvm 재현, luau CLI): 연결 배열을 라이브로 돌며 `table.remove` 하면 자기 연결을 끊은 핸들러 다음 것이 빠진다. 발화 중 대기 중인 `Once` 를 끊으면 `Fire` 가 에러로 멈춰 `Wait` 대기자를 깨우지 못한다. 처방: `table.clone` 스냅샷을 돌고, 부르기 직전에 `Connected` 를 본다(rbvm `.claude/review/2026-10-05-code-review.md:144-166`, R-06).

## §4 끊기: `Disconnect()` 와 `Destroy()` 의 대기 배달
status: described · last-confirmed: 문서 `scripting/events/deferred.md`(2026-11-10), Studio 원천 실측: quad 2026-09-02(버전 미기재, Deferred)·2026-09-03(Deferred), rbvm 0.742(2026-10-13, Deferred) · 근거: 문서 "Disconnect … drops all pending event handler invocations", Warning 상자("Any other method of disconnection besides Disconnect(), such as calling Destroy() … runs the associated event handler for any events that are still pending"); quad `.claude/audit/m5-unit1-studio-smoke-2026-09-02.md:29-45`, `.claude/audit/m10-events-studio-2026-09-03.md` §1 #3·§3 #3, `.claude/archive/post-implementation-review/post-implementation-review-round11.md:97`; rbvm `.claude/design/engine-behavior.md:40-41` · 후보: Q-018, Q-019, Q-021, R-14, M-06

| 끊는 길 | 대기 중이던 배달 | `Connected` |
|---|---|---|
| 명시적 `conn:Disconnect()` | **버린다** (문서, quad 실측 "x 의 지연 배달은 드롭") | 즉시 false |
| `inst:Destroy()` 가 끊음(그 Instance 의 모든 연결, 자손 포함) | **그대로 한 번 돈다** (문서 Warning, quad·rbvm 실측: Destroying·GetPropertyChangedSignal 콜백이 `task.wait()` 뒤 정확히 1회) | Destroy 안에서 **동기로** false |

- 그래서 **생존 판정은 `Connected` 로, 정리 시점은 배달에 기대지 않는다.** Destroy 직후 같은 줄기에서 `conn.Connected == false` 가 이미 보인다. 반면 `Destroying` 핸들러는 그 뒤에 온다.
- **재바인드 함정**: 같은 청크에서 옛 연결을 Destroy 경로로 끊고 새로 연결해도, 큐에 남은 옛 `Destroying` 콜백이 새 연결 **뒤에** 돈다(quad round11, H-574). 옛 콜백은 세대 번호로 걸러 무시한다.
- `Destroying` 핸들러 안에서는 Instance 가 이미 파괴돼 있다(Parent nil, 자식 0). 자세한 것은 `instance-lifecycle.md` §2.

mock 흉내: quad-mock 은 **부분**(Destroy 가 연결을 끊는 순서는 흉내 내지만 Destroying 을 끊기 전에 동기로 쏘므로 "끊긴 뒤 한 번 배달"과 "Disconnect 는 버림"의 차이가 생기지 않는다). E79 심은 둘을 구분해 흉내 낸다. rbvm 은 Destroying 을 늦게 부른다(L2).

## §5 속성 변경 신호
status: described · last-confirmed: Studio 0.738.0.7381393(2026-09-10, Deferred), quad m10(2026-09-03, Deferred), round11(2026-09-21) · 근거: quad `.claude/audit/studio-docs-2026-09-10.md:17-45,78-80`, `.claude/audit/m10-events-studio-2026-09-03.md:28,49` (§1 #2, §3 #1), `.claude/audit/README.md:17`; 타입: `snippets/rbx-types-engine-calls.luau` · 후보: Q-020, Q-023, Q-024, Q-025, D-F18

- **같은 값 대입은 신호를 쏘지 않는다.** 현재값(기본값 포함)과 같은 값을 쓰면 `GetPropertyChangedSignal` 도 `Changed` 도 0회다(`Frame.Visible = true` 0회, `TextLabel.Text = "Label"` 0회). 그래서 "OnChange → 저장 → 다시 대입" 왕복은 엔진에서 저절로 멈춘다. 값 비교 없이 쏘는 mock 에서는 1회가 나와 "엔진 0 / mock 1"로 갈린다.
- **핸들러는 배달 시점의 값을 읽는다.** 한 프레임에 `Text = "hello"`, `Text = "world"` 를 쓰면 핸들러는 2회 불리고 두 번 다 `world` 를 읽는다. 중간값 `hello` 는 관측되지 않는다. 연결 직후의 대입도 한 틱 뒤에 배달된다.
- **엔진이 스스로 바꾸는 값은 신호가 없을 수 있다.** 물리로 떨어지는 Part 의 `Position` 은 `GetPropertyChangedSignal` 을 0회 발화했다(devplorer, D-F18). 엔진이 쓰기를 고쳐 돌려주는 속성(`ScrollingFrame.CanvasPosition` 클램프)은 roblox-world `gui-and-input.md` §3.
- 소문자 별칭: `GetPropertyChangedSignal("archivable")` 은 신호 객체는 만들지만 **발화하지 않는다**(`Archivable` 은 1회). `"name"`, `"parent"` 는 만들 때 거부된다(quad round11).
- 타입: luau-lsp `--platform=roblox` 는 리터럴 속성 이름을 검사한다(`GetPropertyChangedSignal("Bogus")` → `Key 'Bogus' not found`). 이름이 변수면 검사하지 않고, 런타임은 `Bogus is not a valid property name.` 으로 던진다(`rbx-types-engine-calls.luau`, verified luau-lsp 1.70.1·1.69.0).

mock 흉내: quad-mock 은 **아니오**(같은 값에도 즉시 발화하고 중간값을 보여 준다). E79 심은 같은 값 무발화와 배달 시점 읽기를 흉내 낸다. rbvm 은 엔진 신호를 그대로 쓰므로 해당 없음. "엔진이 스스로 바꾼 값"은 어느 mock 도 흉내 내지 않는다.

## §6 시그널 객체의 신원과 모양
status: described · last-confirmed: Studio 0.742.0.7421053(2026-10-13, Edit, Deferred), quad 2026-09-03·09-08 · 근거: rbvm `.claude/design/engine-behavior.md:22-26`, rbvm `.claude/review/2026-10-05-code-review.md:15-17,504-509,540-551`; quad `.claude/audit/m10-events-studio-2026-09-03.md:27`, `.claude/audit/round8-studio-2026-09-08.md:13`; 타입: `snippets/rbx-types-engine-calls.luau`, `snippets/rbx-types-signals-datatypes.luau` · 후보: R-01, R-02, Q-045, Q-026

- **시그널 userdata 는 읽을 때마다 새로 생긴다.** 하나를 쥔 채 다시 읽어도 `rawequal(p.ChildAdded, p.ChildAdded)` 는 false 다(`==` 는 `__eq` 로 true). `GetPropertyChangedSignal("Name")` 도 같다. 그래서 시그널을 표의 키로 쓰면 절대 적중하지 않는다(rbvm 은 이 캐시 때문에 52번 읽자 영구 연결 52개가 생겼다). 키는 `(Instance, 이벤트 이름)` 으로 잡는다.
- 메서드는 반대로 캐시된다. `p.Destroy == p.Destroy` 는 `rawequal` 로도 true 다.
- `typeof(signal)` 은 `"RBXScriptSignal"`, `tostring` 은 `"Signal ChildAdded"`. 레거시 소문자 `signal:connect`, `conn:disconnect()`, `signal:wait` 가 아직 동작한다(문서에는 없다).
- 이벤트 콜백 인자 앞에 self 가 붙지 않는다(`ChildAdded` 콜백 argc 1, Instance 하나).
- `signal:Connect(5)` 처럼 함수가 아닌 값을 넘겨도 **던지지 않는다.** 연결을 돌려주고 콘솔에 "Attempt to connect failed: Passed value is not a function" 만 남긴다(quad 2026-09-08). 타입 검사는 이것을 잡는다(`rbx-types-engine-calls.luau`, verified).

mock 흉내: quad-mock 은 시그널을 테이블로 캐시하므로 신원이 고정된다(**아니오**). 레거시 소문자 별칭은 rbvm 가상 Signal 에 없다(S11). quad-mock 은 함수가 아닌 Connect 를 그냥 받는다.

## §7 Immediate 모드에서 알려진 것 (문서뿐)
status: described (문서 인용, 엔진 미측정) · last-confirmed: 문서 `classes/Instance.md` "Destroying", `scripting/events/deferred.md`(2026-11-10) · 근거: 위 문서; quad `.claude/base/slot-plan.md:1028-1031`, `.claude/audit/h895-reentry-order-2026-10-07/README.md`(CLI 심 `imm` 모드) · 후보: Q-018, Q-022, M-04

- 문서: Immediate 에서는 한 신호가 다른 신호를 일으키면 두 번째 핸들러가 **바로 중첩해서** 돈다. `Destroying` 은 Destroy **직전에** 동기로 오고, 핸들러가 yield 하기 전까지는 Instance 가 제자리에 있다(문서 예제: yield 전 `Workspace.Part 1`, 뒤 `Part 0`).
- quad 는 Immediate 를 가정해 "`Parent` 대입이 `ChildAdded`·`Changed("Parent")`·`Destroying` 을 엔진 호출 **안에서** 동기로 불러, 자료구조를 갱신하는 도중에 재진입이 일어난다"고 설계했다. 근거는 CLI 심의 `imm` 모드와 문서다. **엔진 Immediate 실측은 없다.**
- 처방: 라이브러리는 두 모드 모두에서 맞아야 한다. 엔진 호출 앞뒤로 부기를 끝내 두고(호출 창 안에서 재진입해도 깨지지 않게), 신호 배달 시점에는 기대지 않는다.

mock 흉내: quad-mock 과 rbvm 의 동기 호출이 Immediate 에 가깝다. 다만 "같은 값 무발화"는 둘 다 흉내 내지 않는다.

## §8 mock 과 엔진이 갈리는 지점 요약
status: described · 근거: §2~§6 각 절, quad `.claude/archive/post-implementation-review/post-implementation-review-round11.md:107-109`, `.claude/audit/studio-docs-2026-09-10.md:81-89` · 후보: Q-120, Q-030

| 동작 | 엔진 (Deferred 실측) | quad-mock | E79 심 | rbvm |
|---|---|---|---|---|
| 배달 시점 | 다음 재개 지점 | 즉시 | `flush()` | 즉시 |
| 핸들러 순서 | 연결 역순(관측) | 역순 | FIFO | 정순 |
| 같은 값 대입 | 0회 | 1회 | 0회 | 엔진 그대로 |
| 연속 대입 중간값 | 안 보임 | 보임 | 안 보임 | 엔진 그대로 |
| `Disconnect` 뒤 대기분 | 버림 | 대기분 없음 | 버림 | — |
| `Destroy` 로 끊긴 뒤 대기분 | 1회 배달 | Destroying 을 먼저 동기 발화 | 1회 배달 | Destroying 늦게 |
| 리스너 에러 | 격리 | 발화 쪽으로 올라감 | 격리 | — |
| `Connect(비함수)` | 경고만, 연결 반환 | 받음 | 받음 | — |
| 시그널 신원 | 읽을 때마다 새 userdata | 고정 | 고정 | 캐시(적중 안 함) |

- 이 표의 엔진 열은 Deferred 하나다. Immediate 플레이스를 대상으로 하는 mock 은 이 표로 검증하지 않는다.
- mock 의 차이 기록 형식과 충실도 절차는 luau-roblox `mocks.md` §5–6.

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| audit/09 §6 #9 | Destroying 핸들러 순서: quad "비결정적"(구현 전 추정) 대 rbvm "연결 역순"(실측) | **판정**: 조건 차이가 아니다. quad 쪽은 실측 없는 추정이었고, quad 도 뒤에 Completed 연결에서 역순을 관측했다(Q-027). 사실은 "Deferred 0.742 에서 역순 관측, 문서 보장 없음 → 기대지 말 것" 하나다 |
| audit/09 §6 #11 | 대기 배달: quad "Disconnect 하면 취소" 대 rbvm "Destroy 로 끊겨도 Destroying 1회" | **판정**: 끊는 길이 다르다(조건 차이). 문서가 둘을 명시적으로 구분한다(§4). 모순 아님 |
| audit/08 M-06 | Q-018(Destroy 절단은 1회 배달) 대 Q-019(Disconnect 는 드롭) | 위와 같다. 한 표(§4)에 같이 둔다 |
| audit/08 M-04 | `Parent` 대입이 ChildAdded 를 동기 발화한다(모드 조건 없음) | **판정**: Immediate 에서만(문서). Deferred 실측은 다음 재개 지점이다. 모드 조건을 붙인다(§7) |
| audit/09 §6 #16 | devplorer "SignalBehavior Deferred 미실측" | **판정**: devplorer 서술만 낡았다. 같은 저장소가 BindableEvent 로 실측했고(D-R40) quad·rbvm 실측과 같다 |

## 정정
원천 저장소 세션에 전달할 것. 이 저장소가 재현한 것이 아니라 더 새 실측·문서와 대조해 판정했다.

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad `.claude/base/slot-plan.md:3390` | Parent 대입이 ChildAdded 를 동기로 발화한다(모드 조건 없음) | Immediate 에서만. Deferred 는 다음 재개 지점 | 문서 deferred.md, quad m5-unit1 실측 |
| quad `.claude/archive/surveys/2026-08-06-pre-implementation-audit.md:218` | Destroying 핸들러 순서는 비결정적 | Deferred 0.742 에서 역순 관측(보장은 없음) | rbvm engine-behavior:46 |
| devplorer `.claude/review/2026-10-20-client-palette-copy.md:50` | SignalBehavior Deferred 는 미실측 | 같은 저장소 bindable-watch:85 와 quad·rbvm 이 실측 | audit/09 §6 #16 |
| rbvm `.claude/design/gc-and-lifecycle.md:87-92` | 시그널을 쥐고 있으면 같은 userdata | 쥔 채로도 `rawequal` false | rbvm engine-behavior:22 (같은 저장소) |
| quad `.claude/base/event-plan.md:84-85`(옛 헤더) | 엔진은 `Connect(비함수)` 에서 raise | 던지지 않고 경고만 | quad round8 2026-09-08 |

## 미판정
- **Immediate 모드 전부.** 재현 절차: (1) 쓰는 사람이 없는 테스트 플레이스에서 사람이 Workspace 속성 `SignalBehavior` 를 `Immediate` 로 바꾼다(스크립트·MCP 로는 못 바꾼다). (2) luau-roblox `studio-mcp.md` §5 관용구로 이 파일 §3·§4·§5 의 시나리오를 그대로 돌린다(결과는 `return`). (3) 대입 다음 줄에서 핸들러가 이미 돌았는지로 모드를 확인한다. (4) 결과를 날짜·Studio 버전·모드와 함께 이 파일 표에 열로 더한다.
