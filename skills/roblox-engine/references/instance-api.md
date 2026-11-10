---
title: "트리 API 경계, Parent·에러 문구, Clone, Attribute·태그, QueryDescendants, Reflection, 데이터 타입 값"
description: "트리 API 의 경계 입력 동작(FindFirstChild·IsDescendantOf·WaitForChild), 엔진 에러 문구 원문, Clone 과 Archivable, Attribute 값·이름 제약, QueryDescendants 셀렉터 문법, ReflectionService, 데이터 타입 float32, debug·getfenv 차이"
keywords:
  - "QueryDescendants 셀렉터"
  - "QueryDescendants selector"
  - "엔진 에러 문구"
  - "Bogus is not a valid property name."
  - "Unable to create an Instance of type"
  - "Attempt to set Frame as its own parent"
  - "would result in circular reference"
  - "Unable to assign property Size. UDim2 expected, got table"
  - "Array is not a supported attribute type"
  - "FindFirstDescendant is not enabled"
  - "Argument 1 missing or nil"
  - "attempt to get length of a Instance value"
  - "Clone Archivable nil"
  - "IsDescendantOf nil"
  - "오브젝트 참조 속성 nil 해제"
  - "InstanceHandle"
  - "ReflectionService GetPropertiesOfClass"
  - "float32 경계 비교"
  - "game.JobId 빈 문자열"
kind: reference
category: roblox/instance
tags: [studio, correction]
last_verified: 2026-11-10
---
# instance-api — 트리 API 경계, Parent·에러 문구, Clone, Attribute·태그, QueryDescendants, Reflection, 데이터 타입 값

## 이 파일이 답하는 질문
- Q1 `FindFirstChild`·`WaitForChild`·`IsDescendantOf` 같은 트리 API 가 경계 입력(nil, 숫자, 자기 자신)에서 어떻게 동작하나?
- Q2 엔진 에러 문구는 어떻게 생겼나? 오브젝트 참조 속성을 어떻게 비우나?
- Q3 `Clone()` 은 무엇을 복사하고 무엇을 빼먹나?
- Q4 Attribute 에는 무엇을 넣을 수 있나? Instance 를 넣으면?
- Q5 `QueryDescendants` 의 셀렉터 문법은? (문서에 없다)
- Q6 이벤트·속성 목록을 런타임에 얻으려면?
- Q7 데이터 타입 값의 비교, float 저장, userdata 덕 타이핑의 함정은?
- Q8 Roblox 런타임에서 `debug`·`getfenv`·`JobId` 는 CLI 와 무엇이 다른가?
- Q9 mock 은 이것들을 흉내 내나?

## 목차
- §1 트리 탐색 API 의 경계 동작
- §2 Parent 대입, 오브젝트 참조, 엔진 에러 문구
- §3 `Clone()` 과 `Archivable`
- §4 Attribute
- §5 CollectionService 태그
- §6 `QueryDescendants` 셀렉터
- §7 ReflectionService 와 API Dump
- §8 데이터 타입 값과 userdata
- §9 런타임 환경 차이 (debug, getfenv, JobId)
- 모순 판정 · 정정 · 미판정

엔진 문구·비활성 API 는 엔진 업데이트로 바뀐다. 절마다 원천의 Studio 버전과 날짜를 적었다. 이 저장소가 Studio 에서 다시 잰 것은 없다(`status: described`). 신호 모드와 무관한 동작이 대부분이다.

---

## §1 트리 탐색 API 의 경계 동작
status: described · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, Deferred) · 근거: rbvm `.claude/design/engine-behavior.md:53-66`, rbvm `.claude/review/2026-10-05-code-review.md:435-447,483,600,682-687`; devplorer `.claude/review/2026-10-19-shared-specs.md:32-35`, `.claude/review/2026-10-19-server-edit.md:85-104`, `.claude/review/2026-10-19-server-logs-remote.md:100-101` · 후보: R-30, R-31, R-32, R-33, R-34, R-35, R-36, R-38, D-R52

| 호출 | 결과 | rbvm |
|---|---|---|
| `x:GetFullName()` | DataModel 을 뺀다(`Workspace.X.Deep`). `game:GetFullName()` 은 플레이스 이름 | DataModel 포함(S2) |
| `tostring(inst)` | `Name` | 다른 문자열(D4) |
| `FindFirstDescendant("X")` | 에러 `FindFirstDescendant is not enabled`(비활성 API) | — |
| `FindFirstChild(123)` | 이름 `"123"` 자식을 찾는다(문자열 강제 변환) | nil |
| `FindFirstChild(nil)`, `WaitForChild(nil, 0.1)` | 에러 `Argument 1 missing or nil` | nil / 영구 대기 |
| `FindFirstChildOfClass("Folder", true)` | **2번째 인자를 무시한다**(재귀 안 함, 손자에만 있으면 nil) | 재귀함(N4) |
| `x:IsDescendantOf(nil)` | **true** | false |
| `x:IsAncestorOf(nil)` | false | 에러 |
| `#inst` | 에러 `attempt to get length of a Instance value` | 0 |
| 소문자 별칭 `children()`, `getChildren()`, `findFirstChild()`, `isDescendantOf()` | 전부 동작 | — |
| `WaitForChild("Nope", 0.3)` | 약 0.33초 뒤 nil. timeout 을 주면 무한 대기 경고가 없다. 없으면 5초 뒤 경고(문서) | timeout 무시(S1) |

- **점 표기·`["…"]` 모두 같은 이름 자식보다 멤버(속성·메서드)가 우선한다.** `inst.Parent` 는 `Parent` 라는 자식이 있어도 속성이다. 자식은 `:FindFirstChild` 로 찾는다. 둘 다 없으면 `X is not a valid member of Folder "Name"`.
- `FindFirstAncestor*` 와 `IsDescendantOf` 는 **자기 자신을 빼고** 본다. 이름으로 소속을 판정하면 이름 편집으로 우회되므로, 시작 때 잡아 둔 참조로 `IsDescendantOf` 한다.
- `GetChildren`/`GetDescendants` 순서는 문서 보장이 없다. 관측상 삽입 순이다(roblox-world `gui-and-input.md` §5).
- 일부 CoreGui 계열 Instance 는 `Name` 을 읽을 때 에러가 날 수 있다는 서술이 있다. `game:GetDescendants()` 전체를 돌 때는 pcall 로 감싼다(미실측).
- 병렬 단계에서 쓸 수 있는 트리 API(`FindFirstChild` 는 Safe, 소문자 `findFirstChild` 와 `WaitForChild` 는 Unsafe)는 `parallel-luau.md` §3.

mock 흉내: rbvm 은 위 표의 "rbvm" 열처럼 여러 곳에서 다르다(결함 ID 는 rbvm `.claude/design/known-issues.md`). quad-mock 은 `WaitForChild` 를 만들지 않고 `IsA` 를 계층 없는 `ClassName` 비교로 흉내 낸다. 경계 동작에 기대는 코드는 이 표를 근거로 mock 을 맞추거나 Studio 로 확인한다.

## §2 Parent 대입, 오브젝트 참조, 엔진 에러 문구
status: described · last-confirmed: Studio 0.742(rbvm, 2026-10-13), quad 2026-09-03·09-08(Studio, 버전 미기재), 사용자 실측 2026-09-08 · 근거: rbvm `.claude/design/engine-behavior.md:65`; quad `.claude/audit/round8-studio-2026-09-08.md:9-12`, `.claude/audit/m10-events-studio-2026-09-03.md:52`, `.claude/base/onchange-plan.md:70-71`, `.claude/archive/question-resolved.md:1332`, `.claude/base/dispatch-core-plan.md:761-770` · 후보: R-37, Q-046, Q-047

| 상황 | 문구 |
|---|---|
| 없는 속성 | `Bogus is not a valid property name.` |
| `Instance.new("Frmae")` | `Unable to create an Instance of type "Frmae"`(위치 접두 없음) |
| 자기 자신을 Parent 로 | `Attempt to set Frame as its own parent` |
| 자손을 Parent 로(순환) | `Attempt to set parent of A to A.B would result in circular reference`. 던진 뒤 상태가 반쯤 바뀌어 있을 수 있다 |
| 잘못된 값 타입 | `Unable to assign property Size. UDim2 expected, got table` |
| 파괴된 Instance 의 Parent | `The Parent property of Part is locked, current parent: NULL, new parent Workspace` |

- 엔진이 던지는 에러는 위치 접두(`파일:줄:`)가 없는 경우가 있다. 라이브러리가 엔진 호출을 감쌀 때 사용자 줄을 가리키려면 호출 전에 직접 검사한다.
- **오브젝트 참조 속성**(`Motor6D.Part0`, `Adornee`, `NextSelection*`)은 `inst[k] = nil` 이 정상 해제다. nil 을 못 받는 값 타입 속성(Color3, number 등 보간 가능한 타입 전부)에 nil 을 쓰면 엔진이 에러를 낸다.

mock 흉내: quad-mock 은 순환·자기 Parent 를 거부하도록 맞춰졌다(2026-10-01). 문구까지 같지는 않다. rbvm `SetVirtParent` 는 순환을 허용했다(B10).

## §3 `Clone()` 과 `Archivable`
status: described · last-confirmed: quad 2026-09-18(Studio, 태그 상속), devplorer 서술 · 근거: devplorer `.claude/review/2026-10-19-server-edit.md:36-37`, `.claude/review/2026-10-19-server-structure.md:157-158`; quad `.claude/base/tag-plan.md:220-224`, `.claude/base/claim-plan.md:313`; 문서 `classes/Instance.md` Clone · 후보: D-R16, Q-041, T-20

- `Archivable = false` 인 Instance 는 `Clone()` 이 **nil** 을 돌려주고, 그런 자손은 **소리 없이 빠진다.** 타입은 `Clone()` 을 non-nil 로 선언한다(luau-roblox `api-types.md` §10). `GetDescendants` 는 `Archivable` 과 무관하게 다 보인다.
- 사본은 태그를 물려받고 `Parent` 는 nil 이다(quad 실측).
- 사본의 `WeldConstraint` 는 사본 밖 원본 파트를 계속 가리킨다(roblox-world `world-and-physics.md` §4).
- 막 만든 사본의 `Parent == nil` 은 파괴된 Instance 와 구분되지 않는다(`instance-lifecycle.md` §3).

mock 흉내: quad-mock 은 Clone 을 다루지 않는다. Archivable 규칙은 어느 mock 도 흉내 내지 않는다.

## §4 Attribute
status: described · last-confirmed: quad 2026-09-01(Studio 0.736, Edit)·09-08·09-10(Studio 0.738), devplorer 2026-10-19(Studio Play) · 근거: quad `.claude/audit/round8-studio-2026-09-08.md:12`, `.claude/audit/studio-docs-2026-09-10.md:144-150`, `.claude/audit/spike10-full-run-2026-09-01.md:38-52`, `.claude/base/attribute-plan.md:85-110,188-194`; devplorer `.claude/review/2026-10-19-server-edit.md:300,304-309`; 문서 `studio/properties.md` "Instance attributes" · 후보: Q-039, Q-040, D-R46

- 값: 프리미티브와 일부 데이터 타입만(문서 목록은 luau-roblox `api-types.md` §6). 테이블·메타테이블 테이블은 `Array is not a supported attribute type` 로 거부된다. `SetAttribute(name, nil)` 은 삭제다.
- 이름: 공백, `RBX` 접두, 100자 초과, 빈 문자열을 거부한다. 안전한 꼴은 `^[%w_]+$` 이다(devplorer 검증 규칙).
- **Instance 값(미문서 Studio Beta, 2026-09-01 관측 — 낡음 위험 최상)**: `SetAttribute(name, inst)` 를 받았고 `GetAttribute` 는 Instance 가 아니라 `typeof == "InstanceHandle"` 을 돌려줬다. 원본과 `==`·`rawequal` 모두 false, `handle:Get()` 이 원본을 돌려주고(nil 일 수 있음, `:Wait()` 가 실체화를 기다림), 대상이 Destroy 돼도 nil 로 풀리지 않았다. 지금 동작은 다시 확인한다.
- 타입: `GetAttribute` 는 `unknown?`, `SetAttribute` 의 값은 `any` 다(luau-roblox `api-types.md` §6).

mock 흉내: 확인한 mock 이 없다. 값 타입·이름 검사를 mock 에 넣으려면 이 절의 규칙을 그대로 쓴다.

## §5 CollectionService 태그
status: described · last-confirmed: quad 2026-09-18(태그 상속만 실측) · 근거: quad `.claude/base/tag-plan.md:220-224`, `.claude/archive/post-implementation-review/post-implementation-review-round11.md:139`, `.claude/base/claim-plan.md:215-220`, `.claude/archive/debug-channel-replicatedstorage-rejected.md:6,20` · 후보: Q-041, Q-061

- `AddTag`/`RemoveTag` 는 멱등이다(서술). `Clone()` 사본은 태그를 물려받는다(실측).
- 도구가 런타임 객체를 찾게 할 때는 `ReplicatedStorage` 에 주입하지 말고 자기 트리에 두고 태그 + `GetTagged` 로 찾게 한다(quad 사용자 결정).
- `StarterGui` 내용은 리스폰마다 `PlayerGui` 로 복제되고 여러 스크립트가 같이 쓴다. 라이브러리는 자기 ScreenGui 를 만들어 소유한다.

mock 흉내: 확인한 mock 이 없다.

## §6 `QueryDescendants` 셀렉터
status: described · last-confirmed: Studio 0.738.0.7381393(quad, 2026-09-10, 전수 프로브), devplorer 2026-10-19·11-08 · 근거: quad `.claude/audit/studio-docs-2026-09-10.md:152-194`; devplorer `.claude/review/2026-10-19-server-round6.md:312-317`, `.claude/review/2026-11-08-post-move-audit.md:16,40`; rbvm `.claude/design/engine-behavior.md:62` · 후보: Q-042, D-R24, R-31

`Instance:QueryDescendants(selector)` 는 실재한다(rbvm `typeof == "function"`). 공식 문서에 문법이 없어 프로브로 복원했다.

| 문법 | 뜻 |
|---|---|
| `Part` | 클래스(`IsA` 기준, 하위 클래스 포함) |
| `.Tag` | 태그 |
| `#Name` | 이름 |
| `[$Attr=v]` / `[$Attr]` | Attribute 값 / 존재 |
| `[Prop=v]` | 속성 값 |
| `A B`(공백), `A.B` 처럼 나열 | **AND**(CSS 의 자손 결합자가 아니다) |
| `A > B` | 직계 자식 |
| `A >> B` | 자손 |
| `A, B` | 합집합 |

- 에러: 작은따옴표, `!=`, 소수 리터럴, `*`(결합자 뒤 포함), `$=`(`not a valid selector`).
- **`$` 를 빠뜨린 Attribute 셀렉터(`[Attr=v]`)는 에러 없이 0개**를 돌려준다. 속성 이름으로 해석되기 때문이다.
- 없던 것: `QueryChildren`, `QuerySelector`, `MatchesQuery`(0.738). `FindFirstDescendant` 는 비활성(0.742).
- 성능: 깊이 200 사슬·결합자 4개까지 0.02ms 이하. 깊이 500~1000 사슬에서 Studio 가 무응답이 됐다(devplorer). `:has()` 는 재지 않았다.
- 병렬 단계에서는 Unsafe 다(`parallel-luau.md` §3).

mock 흉내: rbvm stub 은 에러를 던진다. 셀렉터를 흉내 내는 mock 은 없다.

## §7 ReflectionService 와 API Dump
status: described · last-confirmed: quad 2026-09-03·09-09(Studio), devplorer 2026-10-19 · 근거: quad `.claude/audit/m10-events-studio-2026-09-03.md:18`, `.claude/base/bind-system-plan.md:267-274,452-458`, `.claude/audit/deprecated-props-spike-2026-09-09/REPORT.md:11-12`, `scripts/gen-d.py:19-23`; devplorer `.claude/review/2026-10-19-server-edit.md:128-150,293` · 후보: Q-043, Q-044, D-R47

- `ReflectionService:GetEventsOfClass(c)` / `GetPropertiesOfClass(c)` 는 **상속을 포함한** 디스크립터(`{ Name, Display, Owner, Permits, Parameters }`)를 준다. 두 집합은 서로소라 문자열 키가 이벤트인지 속성인지 가를 수 있다. `GetMethodsOfClass` 는 있고 `GetMembersOfClass`·`GetFunctionsOfClass`·`GetCallbacksOfClass` 는 없다(0.738 무렵).
- 약 650개 클래스의 속성 목록과 Category·Permits·Serialized 를 준다. 아이콘·정렬 순서는 없다. `Permits.Write` 로 쓰기 가능을 판정할 때는 **허용 목록**으로 판정한다. 새 능력이 생겼을 때 열린 쪽으로 실패하지 않게 하기 위해서다.
- Hidden·Deprecated 인 `Font`/`FontSize`/`TextWrap`/`Transparency` 도 `Permits.Write` 가 있다. `RelativeGui` 는 만들 수 있지만 capability 로 막힌다. `Font` 는 Deprecated 가 아니라 Hidden(+NotReplicated)이고 `FontSize`·`TextWrap` 이 Deprecated 다.
- `workspace.SignalBehavior` 처럼 ReflectionService 로도 `Permits.Read` 가 없는 속성은 스크립트로 읽을 수 없다(`signals-and-events.md` §1).
- `Script.Source` 는 런타임에 읽히지 않는다.
- API Dump 받기: `clientsettings.roblox.com/v2/client-version/WindowsStudio64` 로 버전을 얻고 `setup.rbxcdn.com/<버전>-API-Dump.json` 을 받는다.

mock 흉내: 해당 없음.

## §8 데이터 타입 값과 userdata
status: described · last-confirmed: tbox 리뷰(2026-10-05), quad 서술 · 근거: tbox `docs/code-review-2026-10-05.md:153-162,187-194,356`, `docs/redesign-precedents.md:23`; quad `.claude/base/source-state-plan.md:1081-1085`, `.claude/base/tween-plan.md:120-121`, `.claude/base/brand-plan.md:276-286`, `.claude/qa-request/post-implementation-review-round13.md:750` · 후보: Q-080, Q-063, Q-048, X-17, X-20, X-23

- Roblox 데이터 타입은 **값으로 같다**(`UDim.new(0, 8) == UDim.new(0, 8)` 은 true). NaN 은 자기와 같지 않아 `==` 기반 중복 제거를 늘 통과한다.
- `Vector2`·`Vector3`·`CFrame`·`NumberRange` 성분과 네이티브 `vector` 성분은 **float32** 다. 64비트 경계와 비교하면 틀린다(`NumberRange.new(0, 0.1)` 이 `maxSpan = 0.1` 검사에 실패). 경계도 float32 로 반올림해 비교한다. 원격 값 검증 맥락은 roblox-net `remotes-and-replication.md` §5.
- float 로 저장되는 속성은 쓴 값과 읽은 값이 다를 수 있다는 서술이 있다(`BackgroundTransparency = 0.1`). **미실측**이다.
- 일부 Roblox userdata 는 **없는 멤버를 인덱싱만 해도 던진다.** 임의 값을 `v.tag ~= nil` 처럼 덕 타이핑하지 말고 `typeof` 를 먼저 보거나 weak-key 집합으로 소속을 판정한다.
- `CFrame:FuzzyEq` 는 회전을 각도 근사로 비교한다(문서). trace 를 보존하는 왜곡이 정규직교 검사를 통과할 수 있다(Studio 미확인).

mock 흉내: quad runshim 의 데이터 타입은 값의 의미가 없는 관대한 객체라 위 사실을 흉내 내지 않는다(luau-roblox `mocks.md` §4). 네이티브 `vector` 의 float32 는 luau CLI 에서도 재현된다.

## §9 런타임 환경 차이 (debug, getfenv, JobId)
status: described · last-confirmed: quad 2026-08-06(Studio, 사용자 실측 일부), Luau CLI·Lune·Studio 재현(Q-119), devplorer 2026-10-19 · 근거: quad `.claude/research/debug-tooling-plan.md:85-91,186-222`, `.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:512`; devplorer `.claude/research/feature-proposals-2.md:97,184,243` · 후보: Q-057, Q-119, D-F18

- Roblox 의 `debug` 에는 `sethook`, `getlocal`, `setlocal`, `getupvalue`, `setupvalue` 가 없다. `info`, `traceback`, `profilebegin` 계열만 있다.
- `pcall(getfenv, 1)` 은 호출자 환경이 아니라 pcall(C 함수)에 대한 환경, 곧 실행 중 스레드의 전역을 돌려준다. `loadstring`+`setfenv` 로 주입된 환경(UI Labs 등)을 찾으려면 그냥 `getfenv()` 를 쓴다. `getfenv`/`setfenv` 는 환경 최적화를 끈다(roblox-net `platform-services.md` §7).
- Studio 에서 `game.JobId` 는 빈 문자열이다.

mock 흉내: luau CLI 의 `debug` 는 Roblox 와 목록이 같지 않다. CLI 에서 되는 디버그 기법이 Roblox 에서 없을 수 있다.

---

## 모순 판정
- 이 파일 범위에서 원천끼리 결론이 갈린 항목은 없다. rbvm 의 열은 "엔진과 다른 mock" 으로 기록했다(모순이 아니라 결함 목록).

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| rbvm `.claude/design/architecture.md:208-209` | 접두 없는 require 는 형제 기준(rbvm 구현 서술) | 엔진은 접두 없는 경로를 거부한다 | rbvm engine-behavior:68-83 (`require-in-roblox.md` §1) |
| devplorer `.claude/review/2026-10-19-server-structure.md:25`(【추론】, 문서 기억) | `QueryDescendants` 가 `:not()` 과 `[prop ^= "x"]` 계열(`^=`·`*=`·`$=`) 연산자를 지원한다 | `:not` 은 "Expected at least one filter", `^=`·`*=`·`$=` 는 "comparison operator expected"(`not a valid selector`) | devplorer `.claude/audit/2026-10-19-server-structure.md:23`, `.claude/review/2026-11-08-post-move-audit.md:40`(Studio 2026-11-09 실측, 같은 저장소) |

## 미판정
- **float 저장 속성의 왕복(Q-063).** 절차: `Frame.BackgroundTransparency = 0.1` 뒤 `== 0.1` 과 `string.format("%.17g")` 값을 기록하고, Position(UDim2)·Size·Color3 성분도 같이 본다.
- **InstanceHandle 의 현재 상태(Q-040).** 절차: `SetAttribute("Ref", part)` 가 지금도 되는지, `typeof(GetAttribute("Ref"))`, `Destroy` 뒤 `:Get()` 을 기록한다.
- **CoreGui 계열 `Name` 읽기 에러(D-R52).** 절차: Play(Client) 에서 `game:GetDescendants()` 를 돌며 `pcall(function() return x.Name end)` 실패 수와 클래스를 모은다.
