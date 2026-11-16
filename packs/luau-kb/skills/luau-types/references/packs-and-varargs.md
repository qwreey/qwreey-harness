---
title: "타입 팩, 가변 인자, 여러 값 반환"
description: "...T 와 T... 의 차이와 함수 타입 가변 인자 문법, select·table.pack·unpack 의 타입, 받은 ... 를 저장하는 defer 패턴 우회, 튜플 별칭·반환 팩 유니온 불가, 넘친 인자 무진단과 노출법"
keywords:
  - "타입 팩"
  - "type pack"
  - "가변 인자"
  - "varargs"
  - "...T"
  - "T..."
  - "제네릭 팩"
  - "select 타입"
  - "table.pack"
  - "table.unpack"
  - "defer 패턴"
  - "튜플 타입 별칭"
  - "반환 팩 유니온"
  - "넘친 인자"
  - "extra arguments"
  - "pcall 실패 분기"
  - "Expected this to be '...V', but got 'A...'"
  - "Trying to get a type from a variadic type parameter"
  - "Expected '->' when parsing function type"
  - "Too many type parameters"
kind: reference
category: luau/types/packs
tags: [new-solver, silent]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - luau-lsp 1.70.1
---
# packs-and-varargs — 타입 팩, 가변 인자, 여러 값 반환

## 이 파일이 답하는 질문
- Q1 `...T` 와 `T...` 는 무엇이 다른가? 함수 타입 안에서는 가변 인자를 어떻게 적나?
- Q2 `select`, `table.pack`, `table.unpack` 은 어떤 타입을 돌려주나? 언제 검사가 꺼지나?
- Q3 제네릭 팩 `<A..., R...>` 으로 함수를 감싸거나 인자를 넘길 때 무엇이 검사되나? 명시 타입 인자로 팩을 주려면?
- Q4 받은 `...` 를 테이블에 담았다가 나중에 넘기는 코드(defer, 시그널 큐)는 왜 타입 에러가 나나?
- Q5 `(number, string)` 같은 "튜플 타입"이나 반환 팩 유니온에 이름을 붙일 수 있나?
- Q6 타입은 맞는데 런타임 값이 nil 이거나 다른 타입인 자리는 어디인가?
- Q7 인자를 너무 많이 넘겼는데 왜 에러가 안 나나? 어떻게 노출하면 잡히나?

## 목차
- §1 용어: `...T`(가변 팩)와 `T...`(제네릭 팩)
- §2 함수 타입 안의 가변 인자 문법
- §3 `select`: 첫 인자가 리터럴일 때만 정확하다
- §4 주석 없는 `...` 는 `...any` 다
- §5 제네릭 팩으로 감싸기와 전달하기, 명시 타입 인자
- §6 팩을 테이블에 담으면 타입을 잃는다 (defer 패턴)
- §7 별칭과 팩: 할 수 있는 것과 없는 것
- §8 여러 값의 잘림, 튜플 타입과 반환 팩 유니온이 없는 이유
- §9 개수가 타입에 남지 않는 자리 (unpack, `...T` 반환, `{ f() }`, pcall)
- §10 넘친 인자를 잡지 않는 경우 (새 솔버)
- §11 가변 인자 자리의 꼬리 호출 (버전 차이)
- §12 자료와 버전

표기: `verified` 는 스니펫이 luau 0.734 와 0.742 의 `luau-analyze`(새 솔버, 기본)에서 그 주장대로 통과했다는 뜻이다. `pack-*` 스니펫은 luau-lsp 1.70.1(새 솔버) 참고 열에서도 결과가 같았다. 이 파일의 초안은 claude-doctor `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/typepacks-varargs.md` 다.

---

## §1 용어: `...T`(가변 팩)와 `T...`(제네릭 팩)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-generic-forwarding.luau`, `snippets/pack-variadic-select.luau` · 원천: luau.org/types/basic-types "Type packs"

- 여러 값 반환과 가변 인자는 안에서 **타입 팩**(타입의 목록)으로 다뤄진다. 팩은 값의 타입이 아니다. 지역 변수나 테이블 필드에 팩 타입을 줄 수 없다(§8).
- `...T` 는 **가변 팩**이다. 같은 타입 `T` 가 0개 이상 이어진다. 예: `(...number) -> ...string`.
- `T...` 는 **제네릭 팩**이다. 길이와 원소 타입이 제각각인 목록을 변수 하나로 받는다. 예: `<A..., R...>(f: (A...) -> R...)`.
- 별칭의 팩 파라미터에 인자를 주는 방법은 셋이다: `A<number, ...string>`(가변 팩), `A<number, ()>`(빈 팩), `Two<(number, string), (boolean)>`(괄호 팩). 팩 파라미터가 하나뿐이면 `Returns<>` 나 `List<number, string, boolean>` 처럼 괄호 없이 나열해도 된다.

## §2 함수 타입 안의 가변 인자 문법
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-function-type-variadic-syntax.luau` · 원천: create.roblox.com/docs/en-us/luau/type-checking.md "Variadics", rfcs `syntax-typed-variadics.md`

| 자리 | 쓰는 법 | 틀린 예 |
|---|---|---|
| 함수 **선언**의 파라미터 | `function f(...: number)` | — |
| 함수 **타입** | `(...number) -> number`, `(x: number, ...number) -> ()` | `(...: number) -> number` 는 `SyntaxError: Expected type, got ':'` |
| 반환 | `(): ...number`, `(): (number, ...string)` | — |

선언(`...: number`)과 타입(`...number`)의 표기가 다르다. RFC 도 이 어긋남을 인정한다. 가변 인자는 늘 마지막 자리에만 온다.

## §3 `select`: 첫 인자가 리터럴일 때만 정확하다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-variadic-select.luau` · 원천: Luau 0.742 소스 `Analysis/src/BuiltinDefinitions.cpp` 의 `MagicSelect`, `EmbeddedBuiltinDefinitions.cpp` 의 `select` 선언(`...any` 반환)

선언된 반환 타입은 `...any` 다. 정확한 타입은 매직 함수가 호출 모양을 보고 덧씌울 때만 나온다.

| 호출 | 결과 타입 |
|---|---|
| `select("#", ...)` | `number` |
| `select(2, ...)` (양의 정수 리터럴) | 둘째 이후의 팩. `select(2, 1, "two", true)` 는 `(string, boolean)` |
| `select(i, ...)` (변수) | `...any`. **검사가 꺼진다** |
| `select(-1, ...)` (음수 리터럴) | 매직 함수가 처리하지 않아 `...any`(소스 조건, described) |

처방: 인덱스가 변수면 결과를 주석 단 지역에 바로 담는다(`local v: string = select(i, ...)`). 쓰는 쪽 타입은 고정되지만, 값이 실제로 맞는지는 여전히 검사되지 않는다.

## §4 주석 없는 `...` 는 `...any` 다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-variadic-select.luau` 의 `unann`

`local function unann(...) return ... end` 의 타입은 `(...any) -> (...any)` 다. strict 에서도 결과를 아무 타입에나 담을 수 있다. 가변 인자를 받는 공개 함수에는 `...: T` 를 꼭 적는다.

## §5 제네릭 팩으로 감싸기와 전달하기, 명시 타입 인자
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-generic-forwarding.luau`, `snippets/generics-pack-explicit-args.luau`

- `wrap<A..., R...>(fn: (A...) -> R...): (A...) -> R...` 는 인자 개수, 인자 타입, 반환 타입을 모두 운반한다. 감싼 함수에 틀린 인자를 주거나 결과를 틀린 타입에 담으면 잡힌다.
- `call<A..., R...>(fn: (A...) -> R..., ...: A...)` 처럼 함수와 그 인자를 함께 받으면 넘긴 인자가 `fn` 의 파라미터와 대조된다. 내장 `pcall` 이 이 모양이다(§9).
- 별칭 `type Signal<T, U...> = { f: (T, U...) -> (), data: T }` 를 `Signal<string, (number, boolean)>` 으로 쓰면 `fire(sig, 1, 2)` 의 둘째 인자 오류가 잡힌다.
- 호출 자리의 명시 타입 인자로 팩을 줄 때는 괄호로 감싼다: `Rejected<<(number)>>(e)`, `f<<(number, string)>>(…)`. 괄호가 없으면 "Too many type parameters" 에러다.

## §6 팩을 테이블에 담으면 타입을 잃는다 (defer 패턴)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-store-generic-pack.luau`(실행 포함)

인자를 저장했다가 나중에 호출하는 코드(`task.defer` 흉내, 시그널의 대기열, 재시도 래퍼)는 새 솔버에서 **저장하는 줄에서** 깨진다.

| 코드 (`...: A...` 를 받은 몸통 안) | 결과 |
|---|---|
| `table.pack(...)` | 에러 `Expected this to be '...V', but got 'A...'`. `pack` 은 `<V>(...V)` 라 원소 타입이 하나뿐이어서 이질적인 팩을 못 받는다 |
| `{ ... }` | 타입이 `{nil}` 이 된다(에러 없이 정보만 사라짐) |
| `fn(table.unpack(listed))` | 에러 `got '...nil'` |

**우회(새 솔버, verified)**:
```luau
local function defer<A...>(fn: (A...) -> (), ...: A...): () -> ()
	local args: { any } = { ... } :: any   -- 저장은 any 로
	local n = select("#", ...)             -- 개수는 따로
	return function() fn(table.unpack(args, 1, n)) end
end
```
- 시그니처의 `A...` 덕에 **호출부는 계속 검사된다**(`defer(function(a: number, b: string) end, 1, 2)` 가 잡힌다).
- 몸통 안의 `any` 는 검사되지 않으니 테스트로 지킨다. nil 이 낀 인자(`1, nil, true`)를 보존하려면 `#args` 가 아니라 `n` 을 쓴다.
- 옛 솔버(`--solver=old`)는 이 우회도 `Trying to get a type from a variadic type parameter` 로 거부한다(0.742 실측). 옛 솔버에 묶인 코드는 시그니처를 `(...any)` 로 낮출 수밖에 없다.

## §7 별칭과 팩: 할 수 있는 것과 없는 것
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-alias-cannot-yield-pack.luau`, `snippets/pack-syntax-no-tuple-alias.luau` · 원천: rfcs `syntax-type-alias-type-packs.md` "Drawbacks"

| 하려는 것 | 결과 |
|---|---|
| 팩을 결과로 내는 별칭 `type P<T...> = T...` | `SyntaxError: … type pack is not allowed in this context` |
| 튜플 별칭 `type M = (number, string)` | 다음 토큰에서 `Expected '->' when parsing function type`. 괄호 목록은 함수 타입의 일부로만 쓴다 |
| 팩의 앞 원소 떼기 `type Y<S...> = Car<S...>` (`Car<T, U...> = T`) | `expects at least 1 type argument`. 별칭은 즉시 인스턴스화되므로 `S...` 의 내용을 모른다 |
| 구체 팩에서 앞 원소 떼기 `Car<number, string, boolean>` | 된다(`number`) |
| 팩 파라미터 뒤에 일반 타입 `Two<S..., number, string>` | 에러 |
| 팩 파라미터 둘에 괄호 팩 `Two<(number, string), (boolean)>` | 된다 |

팩을 원소별로 계산하려면 type function 이 필요하다(`type-functions.md`).

## §8 여러 값의 잘림, 튜플 타입과 반환 팩 유니온이 없는 이유
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/pack-truncation.luau`, `snippets/pack-return-pack-union-syntax.luau` · 원천: Lua 5.1 매뉴얼 §2.5, mrow/review/REVIEW.md:840-845 (후보 M-09)

- 여러 값을 돌려주는 호출은 인자 목록이나 테이블 생성자의 **마지막 자리**에서만 펼쳐지고, 그 밖에서는 첫 값 하나로 잘린다. 타입 검사기도 이 규칙을 그대로 따른다.
  - `take(two())` 는 펼쳐진다. `two(): (number, string)` 이면 둘째 값 `string` 이 둘째 파라미터 `number` 와 대조되어 잡힌다.
  - `take(two(), 1)` 은 첫 값만 쓰여 통과한다.
- 괄호 `(two())` 와 `typeof(two())` 도 첫 값 하나(`number`)다. `typeof` 로 반환 팩 전체를 붙잡을 수 없다.
- **반환 팩끼리의 유니온은 문법에 없다.** `(number) -> ((boolean, T...) | (false, string))` 는 `Expected '->' when parsing function type, got '|'` 구문 에러다. 성공·실패를 나눠 돌려주려면 레코드 유니온(`{ ok: true, value: T } | { ok: false, err: E }`)을 쓰거나, `-> (boolean, T...)` 하나로 적고 실패 분기를 따로 다룬다(§9 의 pcall 과 같은 한계).
- 반환 팩에 이름을 붙이려면 함수 타입으로 감싼다(`type Ret = () -> (number, string)`). 값으로 들고 다니려면 레코드를 쓴다. `table.pack` 은 원소 유니온이 된다(§9).

## §9 개수가 타입에 남지 않는 자리
status: verified · last-confirmed: luau 0.742 (0.734 동일, 옛 솔버도 같은 줄에서 무진단) · 근거: `snippets/pack-unsound-positions.luau`, `snippets/pack-pcall-failure-value.luau`, `snippets/solver-pcall-builtin-overload.luau`(실행 포함 둘) · 원천: `EmbeddedBuiltinDefinitions.cpp` 의 `unpack`, `pack`, `pcall` 선언과 xpcall 위 FIXME 주석, devplorer feedback quad-upstream-2026-10-20.md:502-503 (후보 D-F33)

아래 자리는 정적 타입과 런타임 값이 다르고 진단은 0건이다. 스니펫의 `assert` 가 런타임 값을 확인한다.

| 코드 | 정적 타입 | 런타임 |
|---|---|---|
| `local _, _, z = table.unpack({1, 2})` | `z: number` | `nil` |
| `rets(): ...number` 가 2개를 돌려줄 때 셋째 값 | `number` | `nil` |
| `local arr = { two() }` (`two(): (number, string)`) | `arr[2]: number` | `"a"` |
| `local ok, v = pcall(half, -1)` 의 `not ok` 분기의 `v` | `number`(R) | 에러 메시지 string |

- `table.pack(1, "a")` 는 `{ n: number, [number]: number | string }` 이라 정확하다(원소 유니온, 개수는 `n`).
- `pcall` 은 `<A..., R...>(f: (A...) -> R..., ...: A...): (boolean, R...)` 다. 넘긴 인자는 검사된다(`pcall(half, "x")` 에러). 실패 분기는 표현하지 못한다. 상류 주석에 따르면 의도는 `(true, R1...) | (false, R2...)` 인데 팩의 유니온을 표현할 수 없어 이렇게 적었다(§8).
- 선택 인자가 있는 내장 함수를 pcall 에 바로 넘기면(`pcall(string.find, s, p)`) `A...` 가 내장 선언의 전체 인자 목록으로 굳어 "Argument count mismatch. Function expects 5 arguments, but only 3 are specified" 로 거부된다. 람다로 감싼다.
- 반환이 `()` 인 제네릭 함수를 pcall 에 바로 넘기면 T 를 풀지 못한다(`generics.md` §4).
- 처방: 실패 분기에서는 `tostring(v)` 로 다시 변환한다. `unpack` 결과에는 개수(`n`)를 따로 검사한다.

## §10 넘친 인자를 잡지 않는 경우 (새 솔버)
status: verified · last-confirmed: luau 0.742 (0.734 동일, luau-lsp 1.70.1 동일) · 근거: `snippets/pack-extra-args.luau`, 짝 `snippets/pack-extra-args-old.luau`, `snippets/pack-extra-args-exposure.luau` · 원천: claude-doctor .claude/scopes/packs/luau-kb/audit/11 §2-7

모자란 인자는 늘 잡힌다. 넘친 인자는 **호출 대상의 타입이 함수 정의에서 왔는지, 주석 타입에서 왔는지**로 갈린다.

| 호출 대상 | 넘친 인자 |
|---|---|
| `local function take(a, b)`, `function M.h(a, b)`, 메서드 `O:m(a)`, 함수 리터럴 지역, 제네릭 함수 | **무진단** |
| 정의를 그대로 받은 지역(`local alias = take`), 주석 단 테이블을 리터럴로 초기화한 필드(`local N: { k: Fn } = { k = take }`), 리터럴 안 캐스트(`{ k = take :: Fn }`) | **무진단** |
| 함수 타입 주석을 단 지역(`local g: Fn = take`), 함수 타입 파라미터(`cb: Fn`) | 에러 |
| 생성 뒤 필드에 캐스트로 대입(`M.f = take :: Fn`), 주석 타입의 빈 테이블에 나중에 대입 | 에러 |
| 내장 함수(`math.abs(1, 2)`) | 에러 |
| 옛 솔버(`--solver=old`)에서는 위 모두 | 에러 |

- 모듈 경계(require)를 넘어도 같다. 다른 모듈의 `function M.f` 에 넘친 인자는 무진단이고, `M.h = g :: Fn` 로 노출한 필드는 잡힌다(0.734·0.742 수동 실측, 두 파일이라 스니펫 밖).
- 솔버 차이를 한 번에 보는 법: luau-lsp 1.70.1 에서 `--flag:LuauSolverV2=false` 를 먼저 주면 `f(1, 2)` 가 "Argument count mismatch" 로 잡히고, `=true` 를 먼저 주면 잡히지 않는다(같은 `--flag:` 가 두 번이면 앞의 값이 이긴다).
- 함의: API 를 바꿔 파라미터를 줄였을 때 남은 호출부의 넘친 인자를 새 솔버는 알려 주지 않는다. 원인 소스 줄은 확인하지 못했다(`OverloadResolver::isArityCompatible` 의 "we don't care if we pass more args" 주석은 오버로드 경로만 다룬다).
- **처방**: 넘친 인자 검사가 필요한 공개 API 는 모듈 테이블을 만든 뒤 `M.f = f :: (number, number) -> ()` 로 필드를 캐스트해 노출한다. `export type` 별칭을 정의해 두는 것만으로는 부족하고, 호출되는 값의 타입이 그 별칭이어야 한다.

## §11 가변 인자 자리의 꼬리 호출 (버전 차이)
status: verified · last-confirmed: luau 0.742 (0.734 와 다름) · 근거: `snippets/solver-vararg-tail-call.luau`

`f(...: number)` 에 `f(mkStr())`, `f(1, mkStr())` 처럼 마지막 자리에서 펼쳐지는 호출 결과를 넘기면, **0.734 는 검사하지 않았고 0.742 는 잡는다**(solver-limits.md S14). 0.734 에 묶여 있다면 `f((mkStr()))` 처럼 괄호로 값 하나로 만들어야 잡힌다.

## §12 자료와 버전
status: described

| 자료 | 버전/날짜 |
|---|---|
| luau.org/types/basic-types, /types/generics | 2026-11-10 받음, 페이지 날짜 없음(예제는 play.luau.org 임베드를 디코드해 읽음) |
| luau-lang/rfcs `syntax-type-alias-type-packs.md`, `syntax-typed-variadics.md`, `generic-functions.md` | `364425c5` (2024-06-10), 저장소 HEAD `5fcbb5a2` (2026-10-16) |
| create.roblox.com/docs/en-us/luau/type-checking.md | 머리 `last_updated` 2026-11-10 (문서 빌드 시각) |
| Luau 소스 | 0.742, `8387cfb` (2026-10-09) |
| 실측 도구 | luau 0.734, 0.742 (`luau-analyze` 새 솔버, `--solver=old` 비교), luau-lsp 1.70.1 참고 |
