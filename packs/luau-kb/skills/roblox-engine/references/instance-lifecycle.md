---
title: "Destroy, Destroying, 파괴된 Instance, userdata 신원과 수명 묶기"
description: "Destroy 가 하는 일과 Parent=nil 의 차이, Deferred 에서 Destroying 핸들러 안 Parent 가 이미 nil, 파괴된 Instance 의 locked 에러와 센티넬 연결 생존 판정, userdata 재생성으로 weak 키 소실, 수명 묶기와 누수 조건"
keywords:
  - "Destroy 뒤 연결"
  - "Destroying 핸들러 시점"
  - "Destroying Parent nil"
  - "Parent = nil 과 Destroy 차이"
  - "The Parent property of Part is locked, current parent: NULL, new parent Workspace"
  - "파괴됨 판정"
  - "센티넬 연결"
  - "Connected false 동기"
  - "Instance userdata 신원"
  - "Instance weak 키 사라짐"
  - "수명 묶기"
  - "never-firing 연결"
  - "Instance 누수"
  - "Explorer 삭제 AncestryChanged"
  - "Debris:AddItem"
kind: reference
category: roblox/lifecycle
tags: [studio, correction]
last_verified: 2026-11-10
---
# instance-lifecycle — Destroy, Destroying, 파괴된 Instance, userdata 신원과 수명 묶기

## 이 파일이 답하는 질문
- Q1 `Destroy()` 는 정확히 무엇을 하나? `Parent = nil` 과 무엇이 다른가?
- Q2 `Destroying` 핸들러는 언제 도나? 그 안에서 Parent·자식은 아직 있나?
- Q3 이미 파괴된 Instance 를 읽거나 연결하면? "파괴됨" 을 어떻게 판정하나?
- Q4 Instance 를 weak 표의 키로 쓰면 왜 항목이 사라지나?
- Q5 Lua 객체의 수명을 Instance 에 묶으려면? 그 대가는?
- Q6 무엇이 Instance 와 클로저를 새게 하나?
- Q7 mock 은 이 동작을 흉내 내나?

## 목차
- §1 `Destroy()` 가 하는 일
- §2 Destroy 직후와 `Destroying` 핸들러
- §3 파괴된 Instance 다루기와 생존 판정
- §4 Instance userdata 의 신원과 수거
- §5 수명 묶기 패턴 (never-firing 연결)
- §6 누수 조건
- §7 만들기와 기본값
- §8 mock 과 엔진이 갈리는 지점
- 모순 판정 · 정정 · 미판정

측정 조건과 mock 약어(quad-mock, E79 심, rbvm)는 `signals-and-events.md` §0 과 같다. 모든 원천 실측은 Deferred 모드에서 했고 Immediate 는 미측정이다.

---

## §1 `Destroy()` 가 하는 일
status: described · last-confirmed: 문서 `reference/engine/classes/Instance.md` Destroy·Destroying(last_updated 2026-11-10) · 근거: 같은 문서; quad `.claude/base/slot-plan.md:120-123,3342-3343` · 후보: Q-062

- 문서: `Parent` 를 nil 로 하고 **잠근다**, 그 Instance 의 **모든 연결을 끊는다**, 자식 전부에 `Destroy()` 를 부른다. 파괴된 Instance 는 다시 붙일 수 없다. 잠깐 떼려면 `Parent = nil` 을 쓴다.
- 두 번째 `Destroy()` 는 아무 일도 하지 않는다.
- Studio Explorer 나 플러그인에서 지우면 **Destroy 가 아니라 `Parent = nil`** 이다. 그래서 `Destroying` 이 오지 않는다. 이 경우는 `AncestryChanged` 로 잡는다(문서).
- 시간 뒤 파괴는 `Debris:AddItem()`.
- `Parent = nil` 뒤 `Destroy()` 는 바로 `Destroy()` 보다 비싸다는 서술이 있다(quad, 사용자 지적). 벤치는 없다(`perf.md` §2).

mock 흉내: quad-mock 은 **예**(Parent nil, 자손 Destroy, 연결 끊기, 두 번째 no-op). 순서는 §2 처럼 다르다. Explorer 삭제 경로는 흉내 내지 않는다.

## §2 Destroy 직후와 `Destroying` 핸들러
status: described · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, Deferred), quad 2026-09-02(Edit, Deferred), 문서 2026-11-10 (Immediate 미측정) · 근거: rbvm `.claude/design/engine-behavior.md:40-46`; quad `.claude/audit/m5-unit1-studio-smoke-2026-09-02.md:26-45`, `.claude/audit/spike10-full-run-2026-09-01.md:28`; 문서 `classes/Instance.md` "Destroying", `scripting/events/deferred.md` "Events that change ancestry or properties" · 후보: R-14, R-15, Q-014, Q-018

| 시점 | Deferred 에서 관측한 것 |
|---|---|
| `Destroy()` 바로 다음 줄 | 그 Instance 와 자손에 걸린 모든 `RBXScriptConnection.Connected` 가 **이미 false**(동기). `Destroying` 핸들러는 **아직 안 돌았다** |
| `task.wait()` 뒤 | `Destroying` 핸들러가 정확히 1회 돈다(연결은 이미 끊겼지만 대기분은 배달된다, `signals-and-events.md` §4) |
| `Destroying` 핸들러 안 | Instance 는 **이미 파괴됐다.** `Parent` 는 nil, 자식은 0. 부모 Model 을 Destroy 했을 때 자식의 핸들러 안에서도 `child.Parent` 는 nil 이다 |

- **"Destroying 시점에는 계층이 온전하다"는 가정은 Deferred 에서 틀렸다.** 정리에 부모·형제 정보가 필요하면 Destroy 전에 미리 적어 둔다.
- 스크립트가 **자기 자신**의 `Destroying` 에 연결하면 Deferred 에서는 콜백이 돌지 않는다. 스크립트가 먼저 파괴되기 때문이다(문서).
- Immediate(문서만): `Destroying` 은 Destroy 직전에 동기로 오고, 핸들러가 yield 하기 전까지 Instance 는 제자리에 있다.

mock 흉내: quad-mock 은 **아니오**. `Destroying` 을 Parent nil 보다 **먼저 동기로** 쏘므로 핸들러 안에서 부모·자식이 살아 있다(Immediate 문서 동작에 가깝다). rbvm 은 엔진 Destroying 을 받아 늦게 부른다(L2). E79 심은 Destroy 절단 뒤 1회 배달을 흉내 낸다.

## §3 파괴된 Instance 다루기와 생존 판정
status: described · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, Deferred), quad 2026-09-02 · 근거: rbvm `.claude/design/engine-behavior.md:42-44`, rbvm `.claude/review/2026-10-05-code-review.md:535-538`; quad `.claude/base/claim-plan.md:318-332`, `.claude/archive/v2-initial-implementation/m5-implementation-round14.md:45`; devplorer `.claude/review/2026-10-20-bindable-watch.md:116-127` · 후보: R-16, R-17, Q-015

| 파괴된 Instance 에 | 결과 |
|---|---|
| `.Name`, `.Parent` 읽기 | 읽힌다(`"Part"`, `nil`) |
| `.Parent = workspace` | 에러 `The Parent property of Part is locked, current parent: NULL, new parent Workspace` |
| `Destroying:Connect`, `Changed:Connect` | **성공하고 `Connected == true`**. 영원히 울리지 않고 끊기지도 않는다 |

- **엔진에는 깔끔한 "파괴됨" 술어가 없다.** `Parent == nil` 은 막 `Clone()` 한 Instance 나 아직 붙이지 않은 Instance 와 구분되지 않는다. 파괴된 것에 새로 연결하면 `Connected` 도 true 라 쓸 수 없다.
- 처방: Instance 를 처음 손에 쥘 때 **센티넬 연결**을 하나 걸어 둔다. Destroy 가 그것을 동기로 끊으므로 `sentinel.Connected == false` 가 곧 "파괴됨" 이다. 파괴된 것을 받아 감싸면 연결과 클로저가 새므로(아래 §6), 감싸기 전에 판정한다.

mock 흉내: quad-mock 은 **부분**(Destroy 한 mock 의 `Connected` 전환과 Parent 잠금은 흉내 낸다. 파괴 뒤 새 Connect 가 `Connected == true` 로 남는 것은 확인하지 않았다). rbvm 프록시는 GC 뒤 읽기에서 크래시했다(L6).

## §4 Instance userdata 의 신원과 수거
status: described · last-confirmed: Studio 0.736(quad spike10, 2026-09-01, Edit), Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, Deferred) · 근거: quad `.claude/audit/spike10-full-run-2026-09-01.md:35-36`, `docs/quadnomicon/07-instance-identity-and-gc-philosophy.md:28-49`; rbvm `.claude/design/engine-behavior.md:47`, rbvm `.claude/review/2026-10-05-code-review.md:559-569` · 후보: Q-012, Q-014, R-18, M-11

- Lua 의 `Instance` 값은 엔진 객체를 가리키는 userdata 다. **Lua 쪽 참조가 모두 사라지면, 엔진 객체가 트리에 살아 있어도 userdata 는 수거된다.** 그 뒤 `.Parent`, `GetChildren()`, `FindFirstChild` 로 다시 얻으면 **다른 userdata** 가 나온다.
- 그래서 Instance 를 키로 쓴 **weak-key 표의 항목은 Instance 가 살아 있어도 사라질 수 있다.** 다시 얻은 userdata 로 찾으면 없다. 강한 표의 키로 쥐고 있으면 userdata 가 살아 있어 신원이 유지된다(대신 그 표가 수거를 막는다).
- Destroy 된 Instance 는 Lua 참조가 weak 표에만 있으면 수거된다. rbvm 실측: weak 맵에만 든 Instance 20개를 Destroy 하고 할당 부하 + `task.wait()` 를 주자 5프레임 만에 20개 모두 사라졌다.
- 시그널 userdata 도 같다. 아무도 쥐지 않으면 수거되고 다시 얻으면 새 주소다(`signals-and-events.md` §6).
- Roblox 에서 수거를 관찰하는 법(`collectgarbage("collect")` 를 못 쓴다)은 `gc-in-roblox.md` §1.

mock 흉내: **아니오**. quad-mock 의 Instance 는 Lua 테이블 프록시라 참조가 있는 한 신원이 고정되고, 엔진처럼 수거·재생성되지 않는다(quad-mock 머리 주석이 범위 밖으로 명시). 이 동작에 기대는 코드는 Studio 로만 확인한다.

## §5 수명 묶기 패턴 (never-firing 연결)
status: described · last-confirmed: quad 2026-09-01(Studio 0.736, Edit) 실측, rbvm 설계 서술 · 근거: quad `.claude/audit/gcconn-trick-verification.md:40-50`, `.claude/audit/spike10-full-run-2026-09-01.md:28-36`, `docs/quadnomicon/07-instance-identity-and-gc-philosophy.md:65-81`, `.claude/base/effect-plan.md:20-23`; rbvm `.claude/design/gc-and-lifecycle.md:24-53,147-154` · 후보: Q-010, Q-013, R-19, R-20

- Luau 표에는 `__gc` 가 없다. "사라지는 순간" 훅은 엔진의 명시 신호(`Destroying`)뿐이다.
- 패턴: Instance 의 신호에 클로저를 연결하고, 그 클로저가 **Instance 와 홀더 표를 업밸류로 잡게** 한다. 엔진이 연결을 쥐고, 연결이 클로저를, 클로저가 홀더를 잡는다. 그래서 홀더의 값들이 Instance 의 수명 동안 산다. `Destroy` 가 연결을 끊는 순간 사슬이 풀린다.
  - 신호로는 **절대 발화하지 않는** `inst:GetPropertyChangedSignal("ClassName")` 을 쓴다(`Destroying` 도 되지만 한 번 울린다).
  - 부수 효과: 클로저가 Instance 를 잡으므로 **userdata 신원이 고정된다**(다시 얻어도 `rawequal`, §4 의 문제가 사라진다).
- **대가**: 그 Instance 는 Lua 참조를 다 놓아도 수거되지 않고 **`Destroy` 로만** 풀린다. Frame 하나에 약 4.5KB(quad 실측). 30,000회 만들고 Destroy 해도 +2KB 로 평탄했다.
- 함정: 클로저는 본문이 **실제로 읽는** 지역만 업밸류로 잡는다. 홀더를 잡게 하려고 넣은 참조(`nop(hold)`)를 "안 쓰는 줄"로 보고 지우면 타입 검사는 통과하고 사슬만 조용히 끊긴다. 그 줄에 주석을 단다.

mock 흉내: quad-mock 은 **예**(같은 패턴을 mock 시그널 위에서 재현한다. 머리 주석의 `installLifetime`). 단 mock 은 userdata 신원 문제가 없으므로 "신원 고정" 효과는 시험되지 않는다.

## §6 누수 조건
status: described · last-confirmed: 원천 서술(대부분 Studio 미확인) · 근거: quad `.claude/base/dispatch-core-plan.md:1058-1066`, `.claude/base/fallback-plan.md:165-172`, `docs/quadnomicon/03-luau-memory-topology.md:94`; rbvm `.claude/review/2026-10-05-code-review.md:518-527,596-597`, rbvm `.claude/design/engine-behavior.md:95`; devplorer `.claude/review/2026-10-19-server-security.md:75-94`, `.claude/review/2026-10-20-bindable-watch.md:116-127` · 후보: Q-016, R-21, R-42, D-R22

- **Destroy 하지 않고 버린 Instance + 그 Instance 를 잡는 연결 클로저 = 누수.** §5 와 같은 사슬이 의도치 않게 생긴 것이다. `Parent = nil` 만 하고 버린 것, 한 번도 붙이지 않은 채 예외로 버려진 부분 트리가 여기에 걸린다.
- 엔진이 만들고 아무도 Destroy 하지 않는 객체(Tween, AnimationTrack, InputObject)에 연결하고 그 클로저가 대상 Instance 를 잡아도 같다(트윈 쪽은 `tween-and-animation.md` §5).
- Instance 를 강하게 쥐는 id 표는 Destroy 된 것도 수거되지 못하게 한다. 상한과 정리(prune)를 두고, 상한에 닿은 뒤 요청마다 prune 하지 않게 백오프한다(devplorer).
- 스크립트가 Destroy·Disabled 되면 그 스크립트가 만든 연결이 끊긴다는 서술은 **확인되지 않은 기억**이다(rbvm). 문서는 Deferred 에서 스크립트가 자기 Destroying 에 연결하면 스크립트가 먼저 파괴돼 콜백이 돌지 않는다고만 한다.
- 처방: 소유한 Instance 는 Destroy 로 끝낸다. 연결 클로저는 Instance 대신 필요한 레코드만 잡는다.

mock 흉내: quad-mock 은 Lua GC 위에서만 돌아 엔진이 쥐는 연결 참조를 흉내 내지 않는다(**아니오**). 이 누수는 Studio(`rbx-scene-analysis` 의 부모 없는 Instance, Luau 힙)로만 확인한다.

## §7 만들기와 기본값
status: described · 근거: devplorer `.claude/review/2026-10-21-reset-default.md:17-37,61-70`; quad `docs/how-to/11-library-on-quad.md:213`, `.claude/base/fallback-plan.md:165-172` · 후보: D-R50, Q-109, Q-074

- 부모 없이 `Instance.new` 로 만든 것은 다른 게임 코드가 관찰하지 못한다. 속성 기본값이 필요하면 하나 만들어 읽고 Destroy 한다. `ResetPropertyToDefault` 의 범위는 확인하지 않았다.
- 모듈을 require 하는 순간 Instance 를 만들어 모듈 변수에 쥐지 않는다. 처음 붙은 화면과 함께 파괴되고, 그 뒤 호출은 파괴된 것을 쓴다.
- 표 생성자는 왼쪽부터 평가한다. 중간 원소가 던지면 앞서 만든 Instance 는 고아로 남는다(§6 누수 후보).

mock 흉내: 해당 없음(설계 지침).

## §8 mock 과 엔진이 갈리는 지점
| 동작 | 엔진 (Deferred 실측) | quad-mock | rbvm |
|---|---|---|---|
| Destroy 직후 `Connected` | false, 동기 | false, 동기 | 엔진 그대로 |
| `Destroying` 시점 | 다음 재개 지점, 이미 파괴된 상태 | Destroy 안에서 맨 먼저, 계층 온전 | 늦게(L2) |
| 파괴 뒤 `Parent =` | locked 에러 | 확인 안 함 | — |
| 파괴 뒤 Connect | 성공, `Connected == true` 고정 | 확인 안 함 | 연결이 남는다(L3) |
| userdata 수거·재생성 | 있다 | 없다(테이블 프록시) | 프록시가 GC 뒤 크래시(L6) |

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| audit/09 §6 #10 | Destroying 시점의 계층: quad-mock "동기 발화, 계층 온전" 대 rbvm 실측 "핸들러 안 Parent 는 nil" | **판정**: 조건 차이(mock 대 엔진, 그리고 Immediate 문서 대 Deferred 실측). Deferred 엔진은 rbvm 쪽이고 문서 예제도 같다. quad-mock 은 Immediate 문서 동작에 가깝다. quad 도 자기 mock 충실도 감사에서 "상이"로 표시했다 |
| audit/09 §6 #13 | devplorer "weak 표의 Instance 수거는 실측 필요" 대 quad·rbvm 실측 | **판정**: devplorer 서술이 낡았다. Destroy 된 Instance 는 수거된다(§4) |
| audit/09 §6 #12 | rbvm 내부: 시그널을 쥐면 같은 userdata 대 rawequal false | **판정**: 같은 저장소의 실측(engine-behavior)이 이긴다(`signals-and-events.md` §6) |
| audit/08 M-11 | quad lifecycle-pattern "userdata 신원은 미실측" 대 spike10 실증 | **판정**: 실측이 있다. Q-012 를 실측으로 옮긴다 |

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad `.claude/base/lifecycle-pattern.md:278-285` | Instance userdata 의 수거·재생성은 미실측 | 2026-09-01 Studio 에서 1 GC 사이클 만에 수거, 다시 얻으면 다른 userdata(실증) | quad `.claude/audit/spike10-full-run-2026-09-01.md:35` |
| devplorer `.claude/review/2026-10-19-server-security.md:92,389-390` | weak 표로 Instance 가 수거되는지는 실측 필요 | Destroy 된 Instance 는 수거된다 | rbvm engine-behavior:47, quad audit/README.md:21 |
| rbvm `.claude/review/2026-10-05-code-review.md:590` | Destroying 시점에 계층이 온전하다 | Deferred 에서는 핸들러 안 Parent 가 이미 nil | rbvm engine-behavior:45 (원천에서 이미 정정 표시됨, 확인용) |

## 미판정
- **스크립트 종료 시 연결 해제(R-42).** 재현 절차: (1) Play(Server) 에서 Script A 가 `workspace.ChildAdded` 에 연결하고 `_G.count` 를 올린다. (2) 다른 Script 가 A 를 `Disabled = true` 로 한 뒤 Part 를 추가한다. (3) 같은 시험을 `A:Destroy()` 로 한 번 더 한다. (4) 각 경우 `task.wait()` 뒤 카운트로 판정하고 모드와 함께 기록한다.
- **Immediate 모드에서 §2 표 전체.** 절차는 `signals-and-events.md` 미판정 절과 같다.
