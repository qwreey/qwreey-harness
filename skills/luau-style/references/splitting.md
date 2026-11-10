---
title: "큰 파일을 나누는 전략 카탈로그와 분리 계획기"
description: "큰 파일을 어디서 어떻게 자르나: split-plan.py 분리 계획기, 동작 단위 분화, 타입 하나를 여러 파일로 나눠도 타입이 따라오는 init 모으기 꼴, 늦은 조회 표로 전방 선언 끊기, 처리기 표, State.luau, 닫개 덩어리"
keywords:
  - "split-plan.py"
  - "분리 계획기"
  - "파일 쪼개기"
  - "split large file"
  - "타입 하나 여러 파일"
  - "재수출"
  - "re-export"
  - "전방 선언"
  - "forward declaration"
  - "늦은 조회 표"
  - "Cyclic module dependency"
  - "Cyclic dependencies are only supported if all modules in the cycle use 'export' syntax"
  - "Key 'Sort' not found in table 'Arr'"
  - "Cannot add property"
  - "처리기 표"
  - "State.luau"
  - "닫개 덩어리"
  - "closure factory"
  - "Core Ctor 분리"
kind: reference
category: luau/style/splitting
tags: [cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - luau 0.746
---
# splitting — 큰 파일을 나누는 전략 카탈로그와 분리 계획기

## 이 파일이 답하는 질문
- 3,000줄짜리 모듈을 어디서 자르나? 자를 자리를 기계로 뽑을 수 있나?
- 타입 하나(stl `Arr` 같은 네임스페이스 모듈, 메타테이블 객체)를 여러 파일로 나눠도 타입 검사가 따라오나?
- 함수끼리 서로 부르는데(전방 선언) 파일을 나눌 수 있나?
- 모듈 수준 상태, 닫개가 같이 쥔 상태는 어디로 옮기나?
- 나누면 느려지나(`-O2` 인라인, 메타테이블)?

## 목차
- §0 분리 계획기 `scripts/split-plan.py`
- §1 동작 단위 분화
- §2 타입 하나를 여러 파일로 (실측)
- §3 늦은 조회 표로 전방 선언 끊기
- §4 처리기 표와 `init` 이 모으는 꼴
- §5 데이터를 표로 빼기
- §6 상태 모듈 `State.luau`
- §7 닫개 덩어리 — 먼저 상태 표로 꺼낸다
- §8 고르는 순서

언제 나눌지(기준 수치, 예외)는 `structure.md` §2, 나누는 일반 절차(옮기기만 커밋, 이음매 감사)는 `structure.md` §4 에 있다. 이 파일은 "어떻게 자르나"만 다룬다.

---

## §0 분리 계획기
status: described · last-confirmed: 2026-11-10, 실제 파일 3개 시험(claude-doctor `drafts/split-plans/`) · 근거: `scripts/split-plan.py`
summary: split-plan.py 가 호출 그래프·공유 상태·구획으로 함수 군집을 묶어 후보 파일·순환·옮기기 순서를 낸다. 결과는 판단 재료

```bash
python3 -I <luau-style 스킬>/scripts/split-plan.py <파일.luau> [--json] [--scope <함수>] [--target 400] [--max 800]
```

읽기만 한다. 표준 라이브러리만 쓴다. 3,000~5,000줄 파일에 0.1초 안팎이다.

**무엇을 보나**
- 최상위 함수·메서드(`local function`, `function M.f`, 표 생성자 안의 `Name = function`, 15줄 넘는 익명 콜백)와 줄 범위, 바로 위 주석
- 파일 안 호출 그래프, 모듈 수준 지역 중 다시 대입하거나 내용을 바꾸는 것(상태)과 읽기만 하는 것(상수)
- 전방 선언(`local f: T` 뒤 `function f`, 빈 함수 자리표시 뒤 `f = g`)
- 반환 표에 든 이름(공개), `--#region`·주석 띠(`-- ── 제목 ──`) 구획, 이름 낱말 가족(`bagOpen`·`bagTake` → bag), 같은 필드를 만지는 함수(`session.bundles`)
- 파일 대부분이 함수 하나의 본문이면(닫개 공장, `new` 안의 지역 함수 수십 개) 그 안으로 내려가 분석한다. `--scope 함수` 로 직접 고를 수도 있다.

**어떻게 묶나**
- 호출 간선, 공유 상태(상태를 가상 노드로), 구획·낱말·필드(가상 노드, 약하게), 이웃한 정의(아주 약하게)로 가중 그래프를 만들고 탐욕 모듈성 병합으로 군집을 낸다. 한 군집이 `--max` 를 넘으면 그 안을 다시 나누고, `--target` 의 40% 아래인 군집은 가장 많이 이어진 군집에 붙인다.
- 여러 군집이 부르는 작은 무상태 함수(생성 헬퍼 `newEmpty`, 조회 헬퍼 `relative`)는 **`Core`** 로 뺀다. 이것을 `init` 에 두면 조각들이 `init` 을 require 해야 해서 순환이 된다(§2 S3).
- 함수의 30% 넘게 쓰는 상태는 군집을 붙이는 신호로 쓰지 않는다(모두를 한 덩어리로 끌어당긴다).

**출력**: 군집별 후보 파일·줄 수·공개 이름·쓰는 상태, 군집 사이 require, 순환이 있으면 "위층 → 아래층" 순서와 그 순서를 거스르는 간선(끊을 자리), 경계를 넘는 전방 선언, 상태를 어디로, "옮기기만" 커밋 순서(아래층부터, 아직 옮기지 않은 위층 이름은 늦은 조회로 받는다), 긴 함수(150줄 이상, 닫개 덩어리 표시), 반복 블록.

**한계 — 결과는 판단 재료다**
- 이름은 구획 제목 → 낱말 → 중심 함수 순으로 짓는다. "(약함)" 표시가 붙은 이름은 사람이 다시 짓는다(다른 후보를 같이 낸다).
- 구획 경계를 존중하지만 작은 구획(60줄 미만)은 이웃 군집에 섞인다. 공개 계약 구현 표(`listImpl`)처럼 init 에 남을 것은 사람이 골라 낸다.
- 정적 근사다. `self:Method()`·`obj.handler()` 처럼 표를 거친 호출, 함수 안의 이름 가림은 일부만 잡는다.
- 사람 분석과의 비교(한 게임 저장소의 큰 서버 모듈)에서 9묶음 중 7묶음이 대응했다. 사람은 저장·불러오기(Persist)를 따로 묶었는데 계획기는 `load` 를 init 에, `snapshot` 을 표시 쪽에 두었다(서로 부르지 않고 이름 낱말도 달라서).

## §1 동작 단위 분화
status: described · 근거: stl-luau `4e07d1a`(트레이트마다 파일 하나), `beab32b`(노드 종류마다), `Arr.luau` 계획(claude-doctor `drafts/split-plans/stl-luau-Arr.md`)

한 요소(타입·모듈)가 너무 커졌을 때 "무엇을 하나"로 자른다. 조회 / 넣기·빼기 / 순서 바꾸기 / 정렬 / 스트림 / 생성처럼 사용자가 함수를 찾는 길과 같은 단위다.

- **언제**: 공개 함수가 많고(수십 개) 서로 거의 부르지 않는 모듈. 계획기의 "군집 사이 require" 가 군집 수와 비슷하게 적게 나오면(대부분 `Core` 로만 감) 이 꼴이다. `Arr.luau` 는 군집 6 + Core, 군집 사이 간선 6개, 순환 0 이었다.
- **어떻게**: region 이 있으면 region 이 첫 후보다. 생성 헬퍼·범위 정규화처럼 모두가 쓰는 것은 `Core`(또는 `Ctor`)로 먼저 뺀다. `init` 은 모으기만 한다(§2).
- **타입 비용**: 없다(§2 S1, 실측).
- **성능 비용**: 소비자 → 모듈 호출은 원래 다른 모듈 호출이라 변화 없다. 다만 `-O2` 는 **같은 파일의** 루프 없는 지역 함수만 인라인한다(luau-perf `calls-and-closures.md` §1, `optimizer-and-native.md` §3). 뜨거운 루프가 부르는 작은 내부 헬퍼(구간 정규화, 인덱스 변환)를 `Core` 로 옮기면 인라인이 사라진다. 그런 헬퍼는 쓰는 묶음 파일마다 두거나, 옮긴 뒤 벤치로 확인한다.
- **사례**: stl `Traits/` 는 트레이트마다 한 파일이 된 뒤(10-13) 지금도 34~175줄이다. `Node/` 는 73줄 한 파일 → 종류별 다섯 파일(지금 넷), 최대 230줄(합 512줄로 늘었지만 종류별로 나뉘어 자랐다).

## §2 타입 하나를 여러 파일로 (실측)
status: verified · last-confirmed: luau 0.734·0.742·0.746 · 근거: `snippets/style-split-types.sh` S1–S4(세 버전 23건 rc=0)

`Arr.luau` 같은 경우의 핵심 질문은 "타입이 하나인데 나눌 수 있나"다. 답은 **된다, 단 "모으기"만 init 에서 하고 "덧붙이기"는 하지 않는다**.

| 꼴 | 타입 검사 | 실행 |
|---|---|---|
| S1 묶음 파일이 `Types` 에서 타입을 가져와 제네릭 함수를 정의, `init` 이 표 생성자 필드나 `Arr.Sort = Sort.Sort` 로 재수출 | 제네릭이 살아 있다. 원소·콜백 어긋남과 `Arr.Sized<<number?>>(…)` 명시 타입 인자 모두 그대로 | 됨 |
| S2a 설치자 `require("@self/Sort")(Arr)` 가 표에 붙임 | 소비자 `Arr.Sort` 에 `Key 'Sort' not found in table 'Arr'` | 됨 |
| S2b 메타테이블 객체: 다른 모듈이 `Core.Methods.Sum = …` | 그 줄에 `Cannot add property 'Sum'`, 소비자 `o:Sum()` 에 `does not have key 'Sum'` | 됨 |
| S2c 메타테이블 객체: `init` 이 묶음 함수로 메서드 표를 **조립** `{ Push = Mut.Push, Sum = Query.Sum }` | 깨끗. 인자 어긋남·없는 메서드를 잡는다 | 됨 |
| S2d S2c 에서 묶음 안의 `self:Push(v)` | `Key 'Push' not found in table 'Data<T>'` → 다른 묶음을 require 해서 `Mut.Push(self, v)` | — |
| S3 묶음이 생성자를 쓰려고 `init` 을 require | 0.734 `Cyclic module dependency`, 0.742+ `Cyclic dependencies are only supported if all modules in the cycle use 'export' syntax` | 실패 |
| S3 생성자를 `Ctor.luau` 로 빼고 묶음과 init 이 둘 다 require | 깨끗 | 됨 |

권장 꼴:
```lua
-- Arr/Types.luau : 타입만 (공개 Arr<T>, 내부 Raw<T>)
export type Arr<T> = { read n: number, read data: { read [number]: T }, read __phantom: (T) -> T }
export type Raw<T> = { n: number, data: { [number]: T }, read __phantom: (T) -> T }
return nil

-- Arr/Ctor.luau : 생성자. 묶음들이 init 대신 이것을 require → 순환 없음
local Types = require("./Types")
local M = {}
function M.Of<T>(...: T): Types.Arr<T> return ({ n = select("#", ...), data = { ... } } :: any) end
return M

-- Arr/Sort.luau : 동작 묶음 (Types·Ctor·Core 만 require)
local Types = require("./Types")
local M = {}
function M.Sort<T>(a: Types.Arr<T>, less: (T, T) -> boolean): Types.Arr<T> … end
return M

-- Arr/init.luau : 모으기만
local Types = require("@self/Types")
export type Arr<T> = Types.Arr<T>
return table.freeze({ Of = require("@self/Ctor").Of, Sort = require("@self/Sort").Sort })

-- 메타테이블 객체: 묶음의 self 는 데이터 타입, 메서드 표는 init 이 조립
local Methods = { Push = Mut.Push, First = Query.First }
local mt = { __index = Methods }
export type Bag<T> = setmetatable<Types.Data<T>, typeof(mt)>
-- 쓰지 않는다: 다른 모듈에서 Core.Methods.X = … / require("./X")(Arr)  → 런타임만 되고 타입에서 사라진다
```
- 타입 선언과 생성자는 한 곳(`Types` + `Ctor`)에 둔다. 메서드 묶음은 "다른 모듈이 같은 표에 붙이는" 방식이 아니라 "init 이 묶음 모듈의 함수를 모아 표를 만드는" 방식이어야 타입이 따라온다.
- 제네릭 객체에서 `local o: Bag<number> = Bag.New()` 가 어긋나는 것은 나눈 탓이 아니다. 한 파일에서도 같다(luau-types `generics.md` §1). `Bag.New<<number>>()` 로 쓴다.
- **성능**: 메서드 호출 `obj:M()` 은 `__index` 를 한 번 더 거친다(luau-perf `calls-and-closures.md` §2: `obj:M()` 1.00 > `Mod.M(obj)` 0.78~0.80 > 지역에 받은 `M` 0.55~0.62). 이것은 나누기와 무관하게 메타테이블 꼴의 값이다. 나눠도 이 비용은 늘지 않는다.

## §3 늦은 조회 표로 전방 선언 끊기
status: verified (S4) / described (quad) · 근거: `snippets/style-split-types.sh` S4, quad `4ddb9c5a` `quad-base/src/Slot/init.luau:16-30,151-180`

전방 선언(`local f: (…) -> ()` 뒤에 정의)은 파일 경계를 넘지 못한다. 서로 부르는 함수를 다른 파일로 보낼 때는 **내부 표 하나**를 두고 부를 때 읽는다.

```lua
-- Slot/types.luau
export type S = { isEven: (number) -> boolean, isOdd: (number) -> boolean }
-- Slot/init.luau
local S: Types.S = {} :: any
require("@self/Even")(S)   -- 각 파일이 S.isEven = isEven 으로 등록
require("@self/Odd")(S)
-- Slot/Even.luau 안
return function(S: Types.S)
	function S.isEven(n) return n == 0 or S.isOdd(n - 1) end  -- 부를 때 읽는다
end
```
- **타입**: 표 타입을 따로 선언하면 시그니처 어긋남, 표에 없는 이름(`Cannot add property 'isNope' to table 'S'`), 제네릭 필드(`<T>({ T }) -> T?`)까지 잡는다. 등록을 빠뜨리면 타입은 0건이고 런타임에 `attempt to call a nil value` 다 → init 이 모든 조각을 require 하는지 테스트로 지킨다.
- 이 설치자 꼴은 **내부 표**에만 쓴다. 공개 모듈 표에 설치하면 §2 S2a 처럼 타입에서 사라진다.
- 파일 머리에서 `S.x` 를 읽지 않는다. 등록 순서상 아직 없을 수 있다. quad 는 init 이 설치 뒤에 싣는 두 이름(`S.assertLive`, `S.Slot`)을 "함수 본문 안에서만 읽는다"고 머리에 적었다.
- **성능**: 표 필드 읽기 한 번이다. 다만 다른 파일의 함수라 `-O2` 인라인은 없다(§1).
- **사례**: quad `Slot.luau` 1,194줄 → `Slot/` 여섯 파일(4ddb9c5a, "함수 목록 동일·동작 diff 0"). 계획기는 한 게임 저장소의 큰 서버 모듈에서 파일 경계를 넘는 전방 선언 셋을 모두 "경계를 넘음"으로 짚었다 — audit/12 §4.3 의 사람 분석과 같다.

## §4 처리기 표와 `init` 이 모으는 꼴
status: described · 근거: devplorer `cfeedd1`, `src/Server/Handlers/init.luau`(지금 32줄)

요청 하나 = 처리기 하나인 서버는 처리기를 **묶음 파일**에 나누고 `Handlers/init.luau` 가 표를 합친다.
```lua
const groups: { { [string]: Types.HandlerEntry } } = { require("@self/Session"), require("@self/Tree"), … }
const handlers: { [string]: Types.HandlerEntry } = {}
for _, group in groups do
	for op, entry in group do
		assert(handlers[op] == nil, `duplicate operation {op}`)  -- 같은 이름이 둘이면 권한 표가 조용히 덮인다
		handlers[op] = entry
	end
end
return handlers
```
- **언제**: 표 하나에 항목이 수십 개이고 항목끼리 서로 부르지 않을 때(처리기, 명령, 화면).
- **타입**: 항목 타입(`HandlerEntry`)을 `Core/Types` 에 두고 각 묶음이 그 타입의 표를 돌려준다. 합칠 때 중복 키는 실행 시 `assert` 로 잡는다(타입은 못 잡는다).
- **비용**: 시작할 때 한 번 합친다. 호출 경로는 표 조회 하나로 같다.
- **사례**: devplorer `Server/init.luau` 4,199 → 507줄(`cfeedd1`) → 같은 날 이어진 정리로 지금 241줄. 처리기 덧붙이기가 그 파일을 사흘에 692 → 4,101줄로 키웠는데, 이제 새 처리기는 묶음 파일로 간다.

## §5 데이터를 표로 빼기
status: described · 근거: `structure.md` §6, claude-doctor `audit/12-code-structure.md` §4

같은 모양이 코드에 펼쳐져 있으면(요청 계약, 세트 배치 16갈래, 색·쿨다운) 표 + 일반 처리기로 바꾼다. 파일 길이가 줄어드는 가장 큰 수단이지만 **옮기기만이 아니라 고치기**다. 그래서 계획기 순서에서는 옮긴 뒤 "반복 블록" 항목으로 다룬다. 결정 트리는 `structure.md` §6.

## §6 상태 모듈 `State.luau`
status: described · 근거: devplorer `conventions.md` 코드 배치(상태는 `State.이름`), audit/12 §4.3

모듈 수준 상태(`budgets`, `knocks`, `last*` 표, 깃발)를 여러 조각이 쓰면 `X/State.luau` 한 곳에 두고 `State.이름` 으로 읽고 쓴다.
- **숫자·불리언은 표의 필드로 옮긴다.** `local isOpen = false` 를 다른 모듈이 `require` 해서 받으면 값이 복사된다. 한쪽이 다시 대입해도 다른 쪽은 모른다. `State.isOpen = true` 처럼 필드로 써야 한다.
- 표 상태(`local lastSeen = {}`)는 참조라서 그대로 공유되지만, `State` 에 모아 두어야 "누가 이 상태를 쓰나"를 grep 한 번으로 본다.
- 한 군집만 쓰는 상태는 그 파일로 같이 옮긴다. 계획기 §5 가 상태마다 "쓰는 군집"을 낸다.
- **비용**: 지역 업밸류 대신 표 필드 읽기다. 뜨거운 루프에서는 루프 앞에서 지역으로 받는다(luau-perf `calls-and-closures.md` §2).

## §7 닫개 덩어리 — 먼저 상태 표로 꺼낸다
status: described · 근거: table-sim `todos.md:114-121`, `16923f3`, quad devui `Window/Manager.luau` 계획

`Manager.new` 처럼 함수 하나의 본문 안에 지역 함수 수십 개와 지역 상태 수십 개가 있으면, 그 상태는 **인스턴스마다** 따로다. 모듈 수준 `State.luau` 로 옮길 수 없다.

1. 상태 표 `local st = { order = {}, known = {}, quiet = 0, … }` 를 만들고, 지역 함수가 `st.order` 를 읽게 바꾼다. **이 커밋은 옮기기가 아니라 다시 짜기다.** 동작 diff 0 을 테스트로 확인한다.
2. 지역 함수를 `function(st, …)` 꼴의 모듈 함수로 바꿔 파일로 옮긴다(§1 과 같은 꼴, 늦은 조회는 §3).
3. 상태 표 타입은 `Types.luau` 에 둔다.

- 이 단계를 건너뛰면 분리가 멈춘다. 한 게임 저장소의 큰 화면 모듈은 쉬운 가장자리 셋만 떼고 멈췄고(1,851 → 1,457), 남은 입력 처리 닫개 둘에 기능이 계속 붙어 3,223줄이 됐다. 계획기는 지금 그 두 닫개(1,248줄, 475줄)를 "닫개 덩어리"로 표시하고, `--scope <함수>` 로 보면 입력 처리기 셋이 상태 18개를 같이 쥔 것이 드러난다.
- **비용**: 업밸류 읽기 → 표 필드 읽기. 인터프리터에서 업밸류와 지역 함수 호출은 같은 값이지만(luau-perf `calls-and-closures.md` §2) 필드 읽기는 한 단계 더다. 뜨거운 루프는 지역으로 받는다.

## §8 고르는 순서
```
계획기를 돌린다 (split-plan.py)
├─ "분석 범위"가 함수 안(닫개)이거나 "닫개 덩어리"가 있다 → §7 상태 표부터 (다시 짜기, 사용자에게 먼저 묻는다)
├─ 군집 사이 간선이 적고 대부분 Core 로 간다 → §1 동작 단위 분화 (+ 타입 하나면 §2 꼴)
├─ 공개 표에 같은 모양 항목이 수십 개 → §4 처리기 표
├─ 순환이 있다 → 끊을 간선 목록을 보고: 옮기기 → §3 늦은 조회 → 인자 주입
├─ 여러 군집이 쓰는 모듈 수준 상태 → §6 State.luau
└─ 반복 블록·긴 문자열 분기 → 옮긴 뒤 §5 표로 (고치기 커밋)
```
결과를 그대로 적용하지 않는다. 군집 이름과 경계를 사람(또는 저장소 규칙)이 다듬은 뒤 분리안으로 사용자에게 묻는다(`structure.md` §2 강제 기준).
