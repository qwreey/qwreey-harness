---
title: "문법 관용구"
description: "const 채택(D-01)과 local const·( 로 시작하는 문장 함정, if 식 대 and/or 삼항, f<<T>> 를 오타로 고치지 않기, 배열 구멍과 #t, 맨 function 의 전역 대입, 메타메서드가 상속되지 않음"
keywords:
  - "local const"
  - "const 써도 되나"
  - "Variable 'k' is constant and may not be reassigned"
  - "Unknown global 'x'"
  - "SameLineStatement"
  - "Ambiguous syntax"
  - "if 식"
  - "if-then-else expression"
  - "and/or 삼항"
  - "f<<T>> 오타"
  - "배열 구멍"
  - "#t 길이"
  - "맨 function 전역"
  - "bare function global"
  - "GlobalUsedAsLocal"
  - "메타메서드 상속"
  - "__call 네임스페이스"
kind: reference
category: luau/style/idioms
tags: [policy, correction, silent, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - stylua 2.5.2
---
# idioms — 문법 관용구

## 이 파일이 답하는 질문
- `const` 를 써도 되나? `local const` 는 왜 안 되나? `(` 로 시작하는 문장은 왜 위험한가?
- `c and a or b` 를 그대로 둬도 되나? `if` 식은 오타가 아닌가?
- `f<<T>>` 는 오타인가? 언제 쓰나?
- 옵셔널 값과 배열 구멍을 어떻게 다루나?
- 맨 `function name()` 은 왜 문제인가?
- 메타테이블 객체로 만들까, 네임스페이스 함수로 만들까?
- `:: any` 로 캐스트해도 되나? 같은 값을 여러 번 캐스트하면?

## 목차
- §1 `const` 와 `local` (결정 D-01)
- §2 `if c then a else b` 식
- §3 `f<<T>>` 명시 타입 인자
- §4 nil·옵셔널·구멍
- §5 테이블을 만들고 채우기
- §6 전역 대입 함정 — 맨 `function name()`
- §7 메타테이블과 메서드에 관한 사실
- §8 객체 모양 (결정 D-11)
- §9 캐스트

---

## §1 `const` 와 `local` (결정 D-01)
status: verified · last-confirmed: luau 0.742 (0.734 동일), stylua 2.5.2 · 근거: `snippets/style-const-reassign.luau`, `snippets/style-const-local-const-global.luau`, `snippets/style-stylua-pitfalls.sh` P1 · 결정: qwreey-harness `.claude/base/decisions/D-01-const.md` (2026-11-10 확정) · 후보 S-131

**결정(확정)**: `const` 를 써도 된다. 한 파일 안에서 `const` 와 `local` 을 섞지 않는다.
- 기존 파일은 그 파일의 관행을 따른다. 새 파일은 저장소 규칙을 따르고, 규칙이 없으면 재대입하지 않는 바인딩에 `const` 를 쓴다.
- `const` 는 `local` 을 **대체**한다. `const function f()` 도 유효하다. 재대입하면 컴파일 단계에서 `Variable 'k' is constant and may not be reassigned` 가 난다.
- 예전의 금지 근거(패키지 관리자 pesde 0.7.3 의 타입 익스포트 실패)는 0.7.4 에서 사라졌다. 금지 문구가 남은 저장소 문서는 낡은 것이다.

**함정 1 — `local const x = 1`**
```lua
local const x = 1   -- 나쁜 예: 'const' 라는 지역 변수 + 전역 대입 x = 1, 두 문장이다
const x = 1         -- 좋은 예
```
- 문법 에러가 아니라서 실행된다. `--!strict` 이면 luau-analyze 가 `Unknown global 'x'` 로 잡는다. nonstrict 에서는 린트 경고(`SameLineStatement`)뿐이다.

**함정 2 — `(` 로 시작하는 문장**
```lua
-- 나쁜 예: stylua 가 const 다음 줄의 ';' 를 지워 "Ambiguous syntax" 로 실행이 거부된다
const f: any = print
;(f :: (number) -> ())(1)
-- 좋은 예: 지역으로 받아서 부른다
const g = f :: (number) -> ()
g(1)
```
- `local` 다음이면 stylua 가 `;` 를 앞 줄 끝으로 옮겨 안전하다. 그래도 규칙은 같게 둔다.

**다른 도구의 `const` 지원** (status: described, 각 저장소 기록)
- lune 0.10.5 는 파싱하지 못한다. 그래서 러너로 쓰지 않는다(결정 D-03).
- selene 0.31.0 은 panic 한다.
- stylua `sort_requires` 는 `const` require 블록을 정렬하지 않는다.

## §2 `if c then a else b` 식
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-ifexpr-vs-andor.luau`, quad `.claude/base/architecture.md:764-781`, stl-luau `.claude/conventions.md:90` · 후보 Q-083

```lua
local label = isOn and nil or "off"        -- 나쁜 예: isOn 이 참이어도 "off" 로 샌다
local label = if isOn then nil else "off"  -- 좋은 예
local mod = props.Modifier or DEFAULT      -- 허용: 단순 기본값
```
- `if … then … else …` 식은 2021-10 부터 공식 문법이다. 에이전트가 `and/or` 로 "고치지" 않는다.
- 가운데 값이 언제나 참이라도 `and/or` 삼항은 쓰지 않는다. 나중에 값이 바뀌면 조용히 틀린다.
- "`if` 식이 분기가 더 적다"는 주장은 바이트코드로 확인하지 않았다(described).

## §3 `f<<T>>` 명시 타입 인자
status: verified (포맷 위험) / described (관용) · 근거: luau-kb `skills/luau-verify/references/tooling.md` §4, `tools/repro-stylua-typeargs.sh`, rbvm `.claude/conventions.md:44-48`, stl-luau `.claude/conventions.md:81-82`

```lua
-- 이중 꺾쇠는 문법이다(단일 <T> 는 비교 연산과 모호하다). 고치지 않는다
const nums = Arr.Of<<number>>()
const map = HashMap.New<<string, number>>()
-- 콜백을 넘길 땐 타입 인자나 파라미터 주석을 단다
const doubled = Arr.Map<<number>>(a, function(v) return v * 2 end)
```
- 제네릭이 풀리지 않으면 캐스트보다 이것을 먼저 쓴다. 추론 한계는 `luau-types` 의 generics 에 있다.
- 하위 폴더에서 stylua 를 돌리면 시프트 연산으로 바뀐다 → `quality.md` §3.

## §4 nil·옵셔널·구멍
status: described · 근거: stl-luau `mise.toml:18`(0.734→0.742 에서 `#t` 값이 달라짐), quad `.claude/base/blocker-plan.md:123-127` · 후보 Q-008

- **구멍이 생길 수 있으면 타입에 `T?` 로 드러낸다.** 타입이 `T` 인데 실제로 `nil` 이 오면, 집계 함수가 런타임 검사를 따로 해야 한다.
- **구멍 있는 배열에서 `#t` 를 길이로 믿지 않는다.** 가운데 구멍에서는 아무 경계나 돌려줄 수 있고, 버전에 따라 실제로 다른 값이 나왔다. 길이를 따로 든다(`{ n = …, data = … }`).
- 값-weak 배열(`__mode = "v"`)은 원소가 수거되면 구멍이 생긴다. weak 집합은 `{ [obj] = true }` + `__mode = "k"` 로 둔다.
- `x or y` 기본값은 된다. "명시적 없음"을 값으로 다뤄야 하면 센티널 값을 쓴다.
- `any` 를 인덱싱한 뒤 `~= nil` 로 좁히는 데는 함정이 있다 → `luau-types`.
- `table.insert(t, nil)` 은 아무것도 넣지 않는다 → `pitfalls.md` §1.

## §5 테이블을 만들고 채우기
status: described (수치는 luau-perf 담당) · 근거: stl-luau `.claude/conventions.md:146-149`, `.claude/base/perf-measurements.md`

| 하지 말 것 | 할 것 |
|---|---|
| 원소 루프로 복사·이동 | `table.move`, `table.create(n)` |
| 테이블을 만든 뒤 칸을 하나씩 대입 | 생성자 리터럴에 칸을 다 적는다 |
| 배열을 큐처럼 앞에서 `nil` 로 비움 | 머리 인덱스를 따로 든다 |
| 인스턴스에 길이 필드를 데이터 키와 같은 표에 둠 | `{ data = {…}, size = n }` 래퍼 |
| 가변 인자 내장 함수(`math.max`)를 콜백 자리에 그대로 넘김 | 람다로 감싼다(콜백이 위치·뷰까지 넘기면 그것도 인자로 먹는다) |

배수와 측정 조건은 `luau-perf` 에 있다. 여기에는 방향만 둔다.

## §6 전역 대입 함정 — 맨 `function name()`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-bare-function-global.luau`, quad `scripts/test.sh:16,34` · 후보 Q-082

```lua
function helper(x) return x end         -- 나쁜 예: 전역 helper = function … 대입
local function helper(x) return x end   -- 좋은 예 (또는 const function helper(x))
```
- 모듈 스코프의 맨 `function helper()` 는 `--!strict` 에서도 **타입 진단이 0건**이다. 린트도 대개 나오지 않는다.
- 함수 안에서 처음 대입하는 전역 변수(`counter = 1`)는 strict 에서 `Unknown global` 로 잡히고, `GlobalUsedAsLocal` 린트도 나온다. 함수 선언 꼴이 더 조용하다.
- 린트를 게이트에 쓰는 저장소는 `luau-analyze` 린트를 실패로 취급한다(린트만으로는 exit code 가 0 일 수 있다).

## §7 메타테이블과 메서드에 관한 사실
status: verified (①②③) / described (나머지) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-metatable-shadow-inherit.luau`, quad `.claude/base/architecture.md:507-510`, stl-luau `.claude/conventions.md:38` · 후보 Q-077, Q-078

1. `__index` 는 rawget 이 실패할 때만 불린다. 같은 이름의 인스턴스 필드가 메서드를 가린다(`naming.md` §4).
2. **메타메서드(`__tostring`, `__eq` …)는 `__index` 체인으로 상속되지 않는다.** 파생 메타테이블마다 직접 단다.
3. `table.clone` 은 얕은 복사다. 메타테이블은 복사하지 않고 같은 참조를 공유한다.
- 콜론 호출과 메타테이블이 붙은 표의 인덱싱에는 비용이 있다. 수치와 회피 패턴(뜨거운 데이터는 메타테이블 없는 안쪽 표에 둔다)은 `luau-perf` 에 있다.
- `__call` 로 콜러블 네임스페이스(`Arr(...)`)를 만들면 제네릭 생성자가 타입 인자를 잃는다. 만들지 않는다.
- 자기 참조 메서드 시그니처를 솔버가 놓치는 문제와 우회법은 `luau-types` 에 있다.

## §8 객체 모양 (결정 D-11)
status: described · 근거: qwreey-harness `.claude/base/decisions/D-11-object-shape-and-field-access.md`
> 정책: 결정(D-11, 2026-11-11). 객체 모양(메타테이블 메서드 대 네임스페이스 함수)은 저장소 설계로 둔다. 저장소 rules 와 본보기 파일이 이긴다. stl 의 BI 전환이 끝나면 새 저장소 기본값으로 권할지 그때 다시 정한다.

- 저장소에 본보기 파일이 있으면 그 모양을 따른다. 공통 규칙은 모양을 정하지 않는다.
- 모듈 필드를 지역에 받아 둘지는 `modules.md` §5 에 있다.

## §9 캐스트
status: described · 근거: tbox 사용자 줄의 `:: any` 2/42, 에이전트 줄 22/47

- 캐스트는 다음 줄들이 필요로 하는 가장 좁은 타입으로 한다(`:: any` 대신 `:: TypedNamespace`).
- 한 번 쓰면 쓰는 자리에서 캐스트한다. 같은 값을 여러 번 쓰면 이름 붙인 뷰 지역을 한 번 만든다(`local typedNs = ns :: TypedNamespace`). 쓰는 곳마다 `(x :: any).field` 를 되풀이하지 않는다.

## 정정 (원천 서술이 재현과 다른 것, 각 저장소 세션에 전달)
- `local const x = 1` 은 "린트 경고만 난다"(qwreey-harness `.claude/base/decisions/D-01-const.md` §2, `qwreey-harness .claude/scopes/packs/luau-kb/archive/research/drafts/style` 초안)는 nonstrict 에서만 맞다. `--!strict` 에서는 luau-analyze 0.734·0.742 가 `TypeError: Unknown global 'x'` 를 낸다(`snippets/style-const-local-const-global.luau`). 실행은 두 모드 모두 된다.
- "`luau-analyze` 는 맨 `function name()` 에 `GlobalUsedAsLocal` 린트를 낸다"(후보 Q-082, quad `scripts/test.sh:33-35`)는 그 전역을 한 함수 안에서만 쓸 때만 맞다. 모듈 스코프에서 선언하고 여러 곳에서 부르면 타입 진단도 린트도 0건이다(`snippets/style-bare-function-global.luau`).
