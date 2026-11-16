---
title: "TweenService 엔진 사실 (Play·Cancel·Completed, 파괴, 수명, 보간 타입)"
description: "TweenService 실측: Play 는 값을 동기로 안 쓰고 Create 만 던진다, 끝난 트윈 Cancel 의 Completed(Cancelled) 재발화, Cancel 통지 역전, 대상 Destroy 뒤에도 끝까지 도는 트윈, 핸들 잃은 무한 트윈, TweenInfo 기본값"
keywords:
  - "TweenService Completed 안 옴"
  - "Completed Cancelled 재발화"
  - "Tween Cancel 통지 순서"
  - "Cancel 값 되돌림"
  - "PlaybackState 끝남 판정"
  - "Play 직후 값"
  - "파괴된 Instance 트윈"
  - "무한 트윈 RepeatCount"
  - "트윈 핸들 수거"
  - "Tween 누수"
  - "TweenInfo 기본값"
  - "보간 가능한 타입"
  - "TweenService:Create 목표 표"
  - "cannot be tweened due to type mismatch"
  - "is not a data type that can be tweened"
  - "third argument expects Enum.EasingDirection input"
kind: reference
category: roblox/tween
tags: [studio, correction, silent]
last_verified: 2026-11-10
last_confirmed:
  - luau-lsp 1.69.0
  - luau-lsp 1.70.1
---
# tween-and-animation — TweenService 엔진 사실 (Play·Cancel·Completed, 파괴, 수명, 보간 타입)

## 이 파일이 답하는 질문
- Q1 `Play()` 직후 속성이 바뀌었나? 무엇이 던지나?
- Q2 `Cancel()` 은 값을 되돌리나? 끝난 트윈에 `Cancel()` 하면?
- Q3 A 를 Cancel 하고 B 를 Play 하면 통지 순서는?
- Q4 트윈 중 대상 Instance 를 Destroy 하면 트윈은 멈추나? 연결은 끊기나?
- Q5 트윈 핸들을 잃으면? 무한 트윈은 언제 멈추나? 무엇이 새나?
- Q6 끝났는지는 `PlaybackState` 로 읽나, `Completed` 로 판정하나?
- Q7 어떤 타입을 보간하나? `TweenInfo` 기본값은?
- Q8 타입 검사는 무엇을 잡아 주나?

## 목차
- §1 `Play()`·`Cancel()`·`Create` — 동기성과 던짐
- §2 `Completed` 통지: Cancel 재발화, 통지 역전, 같은 프레임 순서
- §3 끝남 판정: `PlaybackState` 대신 `Completed`
- §4 대상 Instance 가 파괴되거나 떨어질 때
- §5 트윈 핸들의 수명과 누수
- §6 보간 타입, `TweenInfo` 기본값, 진행 중 변경
- §7 타입 검사가 잡는 것
- §8 mock 과 엔진이 갈리는 지점
- 모순 판정 · 정정 · 미판정

조건 표기: 원천은 모두 quad 의 Studio 실측이다. 2026-09-21 은 Studio Edit, **Deferred**. 2026-10-22·11-04 는 데스크톱 Studio Play 클라이언트이고 **신호 모드를 기록하지 않았다**. Immediate 로 확인된 것은 없다. mock 약어는 `signals-and-events.md` §0.

---

## §1 `Play()`·`Cancel()`·`Create` — 동기성과 던짐
status: described · last-confirmed: quad 2026-10-22(Studio Play 클라이언트, 모드 미기재, 커밋 `1270cbae`) · 근거: quad `.claude/audit/tween-premises-2026-10-22/REPORT.md:9-15` · 후보: Q-032, Q-038

- **`Play()` 는 속성을 동기로 쓰지 않는다.** 직후 값은 시작값 그대로이고 `PlaybackState == Playing` 이다. Heartbeat 하나 뒤에도 시작값이었다. 첫 보간은 그 다음이다.
- **`Play`·`Cancel` 은 잰 모든 경우에 던지지 않았다**: 파괴된 Instance 의 트윈, `Play` 두 번, `Cancel` 두 번, 부모 없는 Instance, Destroy 한 Tween 객체.
- **던지는 것은 `TweenService:Create` 뿐이다.** 값 타입이 안 맞으면 `property named 'Position' cannot be tweened due to type mismatch`, 보간할 수 없는 속성이면 `… is not a data type that can be tweened`. 그래서 옛 트윈을 건드리기 전에 새 트윈을 `Create` 해 두면 실패해도 상태가 반쯤 바뀌지 않는다.
- 트윈 시작값은 `Create` 시점이 아니라 **`Play()` 를 부르는 순간의 값**이라는 서술이 있다(quad 리뷰). 미실측이다.

mock 흉내: 해당 mock 은 quad 의 가짜 Tween 들이다. 동기로 쓰는 mock 은 "Play 직후 값" 에서 엔진과 갈린다. 각 mock 이 `Create` 에서만 던지는지는 확인하지 않았다.

## §2 `Completed` 통지: Cancel 재발화, 통지 역전, 같은 프레임 순서
status: described · last-confirmed: quad 2026-09-21(Studio Edit, Deferred), 2026-10-22·11-04(Studio Play, 모드 미기재) · 근거: quad `.claude/audit/tween-completed-2026-09-21/REPORT.md:12-24`, `.claude/audit/tween-premises-2026-10-22/REPORT.md:16-19`, `.claude/audit/tween-settle-2026-11-04/REPORT.md:7-17` · 후보: Q-031, Q-032, Q-027

- 자연 완료: `Completed(Enum.PlaybackState.Completed)` 정확히 1회.
- **끝난 트윈에 `Cancel()`**: `Completed(Cancelled)` 가 **한 번 더** 온다. 값은 목표 그대로다. 무조건 `Cancel` 하는 정리 코드는 이미 끝난 트윈에도 Cancelled 통지를 만든다. `Completed` 로 "취소됨" 콜백을 만들면 이 이중 발화를 걸러야 한다.
- **실행 중 `Cancel()` 의 통지는 늦게 온다(Deferred).** `Cancel()` 은 바로 돌아오고 `Completed(Cancelled)` 는 다음 재개 지점에 온다. 그래서 yield 없이 `A:Cancel()` → `B:Play()` 하면 관측 순서가 **B 시작 → A Cancelled → B Completed** 다. "이전 것의 취소 통지 → 다음 것의 시작" 순서는 엔진 신호만으로는 보장되지 않는다. 사이에 `task.wait()` 를 넣으면 A Cancelled 가 먼저 온다.
- 한 `Completed` 연결이 던져도 다른 연결은 돈다. 연결 사이 순서는 역순으로 관측됐고 약속되지 않는다.
- **같은 프레임에 끝나는 트윈들의 통지 순서는 정해져 있지 않다.** 한 실행에서는 생성 순, 다른 실행에서는 1번 통지 안에서 이미 2~6번이 통지돼 있었다.
- 같이 시작한 같은 길이의 형제 트윈을 **첫 `Completed` 안에서 교체**하면 나머지 형제는 `Cancelled` 를 받는다(6회 모두). 그 순간 형제는 아직 목표에 닿지 않았다.
- 끝나는 순간 근처(0.07~0.13초)에서 교체해도 콜백은 정확히 하나였다(`Completed` 21, `Cancelled` 19, 둘 다·없음 0, 40회).

mock 흉내: quad 의 동기 mock Tween 은 Cancel 통지를 즉시 내므로 통지 역전이 생기지 않는다(**아니오**). E79 심은 Tween 통지도 큐에 넣어 늦은 배달을 흉내 낸다(quad round13 E79 축 7a~7g, 엔진 실측 아님). "끝난 트윈 Cancel 의 재발화"를 흉내 내는지는 mock 마다 확인이 필요하다.

## §3 끝남 판정: `PlaybackState` 대신 `Completed`
status: described · last-confirmed: quad 2026-10-22·11-04(Studio Play, 모드 미기재) · 근거: quad `.claude/audit/tween-premises-2026-10-22/REPORT.md:20-23`, `.claude/audit/tween-settle-2026-11-04/REPORT.md:9`, `.claude/archive/post-implementation-review/post-implementation-review-round11.md:65` · 후보: Q-033, M-02

- 이론상 `PlaybackState == Completed` 인데 `Completed` 통지가 아직 큐에 있는 창이 있을 수 있다. 그러나 실측(같은 프레임 형제 통지 안, 프레임 신호 여섯 PreRender·PreAnimation·PreSimulation·PostSimulation·Heartbeat·RenderStepped)에서 **사용자 코드에 한 번도 보이지 않았다.**
- 처방: 끝남은 **`Completed` 통지로** 판정한다. "통지 전에 교체·철거됐으면 Cancelled" 로 정한다. `PlaybackState` 를 동기로 읽어 판정하지 않는다.

mock 흉내: 해당 없음(창이 관측되지 않았다). mock 은 `PlaybackState` 와 통지를 함께 바꾸면 된다.

## §4 대상 Instance 가 파괴되거나 떨어질 때
status: described · last-confirmed: quad 2026-09-21(Studio Edit, Deferred), 2026-09-08 · 근거: quad `.claude/audit/tween-completed-2026-09-21/REPORT.md:19-21`, `.claude/audit/round8-studio-2026-09-08.md:11`, `.claude/archive/post-implementation-review/post-implementation-review-round8.md:343-348` · 후보: Q-031, Q-035, M-01

- 트윈 도중 대상을 `Destroy()` 하거나 `Parent = nil` 해도 **트윈은 끝까지 돈다.** 파괴된 Instance 에 속성을 쓰고 `Completed(Completed)` 를 낸다. `Completed` 연결은 `Connected == true` 로 남는다(자동 Disconnect 없음). `tween.Instance` 는 파괴된 Instance 를 그대로 가리킨다.
- 실물 Tween userdata 의 `.Instance` 는 **Lua 객체 그래프에 잡히지 않는다.** 트윈을 강하게 쥐고 있어도 Destroy 된 Frame 은 수거된다. 이것을 Lua 필드로 흉내 낸 mock 에서만 누수가 난다.

mock 흉내: `.Instance` 를 Lua 필드로 쥐는 mock Tween 은 **아니오**(엔진에 없는 누수를 만든다). 끝까지 돌며 파괴된 대상에 쓰는 동작은 mock 마다 확인한다.

## §5 트윈 핸들의 수명과 누수
status: described · last-confirmed: quad 2026-09-21(Studio Edit, Deferred) · 근거: quad `.claude/audit/tween-completed-2026-09-21/infinite-tween-probe.md:14-48`, `.claude/audit/tween-completed-2026-09-21/REPORT.md:25-31,58`, `.claude/base/tween-plan.md:727-728` · 후보: Q-034, Q-009

- **엔진은 트윈의 Lua 핸들을 붙잡지 않는다.** 재생 중이어도 Lua 참조를 다 놓으면 몇 GC 에포크 안에 핸들이 수거되고, 엔진은 트윈을 계속 돌린다. 활성 트윈을 열거하는 API 가 없으므로 그 뒤에는 **Cancel 할 방법이 없다.**
- **`RepeatCount = -1` 트윈은 대상을 Destroy 하거나 떼도 영원히 돈다.** 무한 트윈은 대상을 파괴하기 **전에** 핸들로 `Cancel` 한다.
- 반대 방향 누수: `Completed` 연결 클로저가 대상 Instance 를 잡으면, 트윈 객체가 살아 있는 동안 그 Instance 가 수거되지 않는다(150 에포크 동안 잔존). 연결 클로저는 Instance 대신 레코드만 잡고, 완료 시와 Cancel 자리에서 연결을 끊는다.
- weak 캐시에만 둔 트윈 레코드는 GC 시점에 사라질 수 있다. 명시적으로 만든 기록은 명시적으로 지운다(luau-runtime `gc-and-weak-tables.md` §4).

mock 흉내: **아니오**. Lua mock Tween 은 엔진처럼 "핸들 없이 계속 도는" 상태를 만들지 않는다. 핸들 수거는 Studio 에서 할당 압박으로만 관찰한다(`gc-in-roblox.md` §1).

## §6 보간 타입, `TweenInfo` 기본값, 진행 중 변경
status: described · last-confirmed: quad H-333 Studio 실측(날짜 미기재), 2026-11-04 · 근거: quad `.claude/base/tween-plan.md:211-215,497-528,546-560`, `.claude/audit/tween-settle-2026-11-04/REPORT.md:10` · 후보: Q-036, Q-037

- 보간되는 타입: number, boolean, CFrame, Rect, Color3, UDim, UDim2, Vector2, Vector2int16, Vector3. 그 밖은 `Create` 가 던진다(목록은 quad 생성기 기준이라 문서로 다시 확인할 것).
- `TweenInfo.new()` 기본값: Time 1, `EasingStyle.Quad`, `EasingDirection.Out`, RepeatCount 0, Reverses false, DelayTime 0. **enum 자리에 명시적 `nil`** 을 넘기면 "third argument expects Enum.EasingDirection input" 로 거부된다. 기본값을 쓰려면 인자를 생략한다.
- TweenBase 는 `Play`/`Pause`/`Cancel` 뿐이다. 진행 중 목표를 바꾸거나 목표를 역산하는 API 가 없다. 목표를 바꾸려면 새 트윈을 만든다.
- **`Cancel()` 은 값을 되돌리지 않는다.** 현재 보간값에 멈추고, 다음 트윈은 거기서 이어진다. `Reverses = true` 트윈의 정지값은 시작값이다.
- 끝난 트윈은 다시 `Play` 할 수 있다는 관측이 있다("재사용 불가" 서술은 의심, 정정 표).

mock 흉내: 보간 타입 검사는 mock 마다 다르다. quad runshim 의 데이터 타입 값 객체는 값의 의미가 없어 보간 결과를 흉내 내지 않는다(luau-roblox `mocks.md` §4).

## §7 타입 검사가 잡는 것
status: verified · last-confirmed: luau-lsp 1.70.1·1.69.0 + `typedefs/globalTypes.d.luau` · 근거: `snippets/rbx-types-engine-calls.luau`

| 코드 | 타입 검사 | 런타임 |
|---|---|---|
| `TweenInfo.new(1, Enum.EasingDirection.Out)`(enum 자리 바뀜) | 에러 | 거부 |
| `TweenInfo.new(1, nil, Enum.EasingDirection.Out)` | **통과**(선택 인자) | 거부(§6) |
| `TweenService:Create(p, info, { Bogus = 1 })` | **통과**(목표 표가 `{ [any]: any }`) | `Create` 가 던진다 |
| `tw.Completed:Connect(function(state) ... end)` | `state` 는 `Enum.PlaybackState` | — |

목표 표의 속성 이름·타입은 정적으로 지켜지지 않는다. 목표 표를 만드는 쪽에 구체 타입을 붙인 래퍼를 둔다.

## §8 mock 과 엔진이 갈리는 지점
| 동작 | 엔진 | 동기 mock Tween(흔한 모양) |
|---|---|---|
| `Play()` 직후 값 | 시작값 그대로 | 바로 쓰는 mock 이 많다 |
| 실행 중 `Cancel` 통지 | 늦게(재개 지점) | 즉시 |
| 끝난 트윈 `Cancel` | Cancelled 재발화 | mock 마다 다름 |
| 대상 파괴 뒤 | 끝까지 돌며 씀, 연결 유지 | mock 마다 다름 |
| `.Instance` 참조 | GC 그래프에 안 잡힘 | Lua 필드라 누수 |
| 핸들 잃은 트윈 | 계속 돈다 | 없음 |

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| claude-doctor .claude/scopes/packs/luau-kb/audit/08 M-01 | 파괴된 Instance 위의 트윈: "삭제된다"(사용자 관찰), "연결이 먼저 끊겨 Completed 에 안 닿음"(옛 서술) 대 실측 "끝까지 돌고 Completed, 연결 유지" | **판정**: 두 질문이 섞였다. "Tween 객체(핸들)가 수거되는가"는 예(§5), "통지가 오는가"도 예(§4). 실측 쪽을 채택 |
| claude-doctor .claude/scopes/packs/luau-kb/audit/08 M-02 | 통지 대기 창이 있으니 `PlaybackState` 를 읽어라 대 창이 한 번도 안 보임 | **판정**: "관측 안 됨(2026-10-22·11-04)"만 사실로 둔다. 처방은 `Completed` 판정(§3) |
| claude-doctor .claude/scopes/packs/luau-kb/audit/08 M-03 | 죽은 트윈에 `Cancel` 은 에러 대 던지지 않음 | **판정**: 실측(던지지 않음) |

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad `.claude/base/lifecycle-pattern.md:150-152` | 죽은 Tween 에 `Cancel` 은 그냥 에러 | 던지지 않는다 | quad tween-premises-2026-10-22 사실 2 |
| quad `.claude/archive/post-implementation-review/post-implementation-review-round12.md:10` | 연결이 먼저 끊겨 Completed 에 닿지 않는다 | 끝까지 돌고 Completed(Completed), 연결 유지 | quad tween-completed-2026-09-21 사실 5 |
| quad `.claude/base/ui-shorthand-plan.md:303-304` | (취소선) 파괴된 Instance 위 트윈은 삭제된다 | 위와 같음 | 같음 |
| quad `.claude/research/tween-callback-structure.md:29` | 통지 대기 창이 있으니 PlaybackState 를 직접 읽어라 | 창은 관측되지 않았다. Completed 로 판정 | tween-premises 사실 5, tween-settle 사실 3 |
| quad `.claude/base/tween-plan.md:548` | 트윈 인스턴스는 재사용 불가 | 완료 뒤 다시 `Play` 가능(관측) | claude-doctor .claude/scopes/packs/luau-kb/audit/08 Q-037 비고. 재측 권장 |

## 미판정
- **트윈 시작값이 `Play` 순간의 값인가(Q-038).** 재현 절차: (1) `Create(part, info, {Transparency = 1})` 로 만든다. (2) `part.Transparency = 0.5` 로 바꾼다. (3) `Play()` 하고 `Heartbeat` 몇 번 동안 값을 기록한다. (4) 0.5 에서 출발하면 Play 시점, 원래 값에서 출발하면 Create 시점이다.
- **Immediate 모드의 Cancel 통지 시점.** `signals-and-events.md` 미판정 절차로, 이 파일 §2 의 교체 시나리오를 돌린다.
