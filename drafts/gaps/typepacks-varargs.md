# typepacks-varargs — 타입 팩, 가변 인자, 여러 값 반환

## 이 파일이 답하는 질문
- Q1 `...T` 와 `T...` 는 무엇이 다른가? 함수 타입 안에서는 가변 인자를 어떻게 적나?
- Q2 `select` 와 `table.pack` / `table.unpack` 은 어떤 타입을 돌려주나? 언제 검사가 꺼지나?
- Q3 제네릭 팩 `<A..., R...>` 으로 함수를 감싸거나 인자를 넘길 때 무엇이 검사되나?
- Q4 받은 `...` 를 테이블에 담았다가 나중에 다시 넘기는 코드(defer, Signal:Fire)는 왜 타입 에러가 나나?
- Q5 `(number, string)` 같은 "튜플 타입"에 이름을 붙일 수 있나? 별칭으로 팩을 만들거나 쪼갤 수 있나?
- Q6 타입은 맞는데 런타임 값이 nil 이거나 다른 타입인 자리는 어디인가?
- Q7 인자를 너무 많이 넘겼는데 왜 에러가 안 나나?

## 목차
- §1 용어: `...T`(가변 팩)와 `T...`(제네릭 팩)
- §2 함수 타입 안의 가변 인자 문법
- §3 `select`: 첫 인자가 리터럴일 때만 정확하다
- §4 주석 없는 `...` 는 `...any` 다
- §5 제네릭 팩으로 감싸기와 전달하기
- §6 팩을 테이블에 담으면 타입을 잃는다 (defer 패턴)
- §7 별칭과 팩: 할 수 있는 것과 없는 것
- §8 여러 값의 잘림과 "튜플 타입"이 없는 이유
- §9 개수가 타입에 남지 않는 자리 (unpack, `...T` 반환, `{ f() }`, pcall)
- §10 넘친 인자를 잡지 않는 경우 (새 솔버)
- §11 자료와 버전

표기: `verified` 는 스니펫이 luau 0.734 와 0.742 의 `luau-analyze`(새 솔버, 기본)에서 그 주장대로 통과했다는 뜻이다. `described` 는 원천의 서술만 있다는 뜻이다. 스니펫은 `drafts/gaps/snippets/` 에 있다. luau-kb 로 옮길 때는 `snippets/` 로 옮긴다. 모든 `packs-*` 스니펫은 `luau-lsp 1.70.1`(새 솔버) 참고 열에서도 결과가 같았다.

---

## §1 용어: `...T`(가변 팩)와 `T...`(제네릭 팩)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-generic-forwarding.luau`, `packs-variadic-select.luau` · 원천: luau.org/types/basic-types "Type packs"

- 여러 값 반환과 가변 인자는 내부적으로 **타입 팩**(타입의 목록)이다. 팩은 값의 타입이 아니다. 지역 변수나 테이블 필드에 팩 타입을 줄 수 없다(§8).
- `...T` 는 **가변 팩**이다. 같은 타입 `T` 가 0개 이상 이어진다. 예: `(...number) -> ...string`.
- `T...` 는 **제네릭 팩**이다. 길이와 원소 타입이 제각각인 목록을 하나의 변수로 받는다. 예: `<A..., R...>(f: (A...) -> R...)`.
- 별칭 인자 자리에 팩을 주는 방법은 셋이다. `A<number, ...string>`(가변 팩), `A<number, ()>`(빈 팩), `Two<(number, string), (boolean)>`(괄호 팩). 팩 파라미터가 하나뿐이면 `Returns<>` 나 `List<number, string, boolean>` 처럼 괄호 없이 나열해도 된다.

## §2 함수 타입 안의 가변 인자 문법
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-function-type-variadic-syntax.luau` · 원천: create.roblox.com/docs/en-us/luau/type-checking.md "Variadics", rfcs `syntax-typed-variadics.md`

| 자리 | 쓰는 법 | 틀린 예 |
|---|---|---|
| 함수 **선언**의 파라미터 | `function f(...: number)` | — |
| 함수 **타입** | `(...number) -> number`, `(x: number, ...number) -> ()` | `(...: number) -> number` 는 `SyntaxError: Expected type, got ':'` |
| 반환 | `(): ...number`, `(): (number, ...string)` | — |

RFC 도 "선언(`number`)과 타입(`...number`)의 표기가 어긋나 어색하다"고 인정한다. 가변 인자는 항상 마지막 자리에만 온다. `(...: number, x: string)` 은 구문 에러다.

## §3 `select`: 첫 인자가 리터럴일 때만 정확하다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-variadic-select.luau` · 원천: Luau 소스 `Analysis/src/BuiltinDefinitions.cpp` `MagicSelect::infer`, `EmbeddedBuiltinDefinitions.cpp` `declare function select<A...>(i: string | number, ...: A...): ...any`

선언된 타입은 `...any` 다. 정확한 타입은 "매직 함수"가 호출 모양을 보고 덧씌울 때만 나온다.

| 호출 | 결과 타입 |
|---|---|
| `select("#", ...)` | `number` |
| `select(2, ...)` (정수 리터럴 > 0) | 둘째 이후의 팩. `...: string` 이면 `string`. `select(2, 1, "two", true)` 이면 `(string, boolean)` |
| `select(i, ...)` (변수) | `...any`. **검사가 꺼진다**(스니펫 `bug-present`) |
| `select(-1, ...)` (음수 리터럴) | 매직 함수가 처리하지 않아 `...any` (소스 `offset > 0` 조건, described) |

**처방**: 인덱스가 변수라면 결과를 바로 주석 단 지역에 담는다(`local v: string = select(i, ...)`). 이렇게 하면 적어도 쓰는 쪽 타입은 고정된다. 그래도 값이 맞는지는 검사되지 않는다. 옛 솔버도 같다.

## §4 주석 없는 `...` 는 `...any` 다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-variadic-select.luau` 의 `unann` · 원천: create.roblox.com/docs/en-us/luau/type-checking.md "Variadics"

`local function unann(...) return ... end` 의 타입은 `(...any) -> (...any)` 다. strict 모드라도 결과를 아무 타입에 대입할 수 있다. 가변 인자를 받는 공개 함수에는 `...: T` 를 꼭 적는다.

## §5 제네릭 팩으로 감싸기와 전달하기
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-generic-forwarding.luau` · 원천: luau.org/types/basic-types "Type packs" (Signal 예제)

- `wrap<A..., R...>(fn: (A...) -> R...): (A...) -> R...` 는 인자 개수, 인자 타입, 반환 타입을 모두 그대로 운반한다. 감싼 함수에 틀린 인자를 주면 에러가 나고, 결과를 틀린 타입에 담아도 에러가 난다.
- `call<A..., R...>(fn: (A...) -> R..., ...: A...)` 처럼 함수와 그 인자를 함께 받으면, 넘긴 인자가 `fn` 의 파라미터와 대조된다. 내장 `pcall` 이 이 모양이다(§9).
- 별칭 `type Signal<T, U...> = { f: (T, U...) -> (), data: T }` 를 `Signal<string, (number, boolean)>` 으로 인스턴스화하면 `fire(sig, 1, 2)` 의 둘째 인자 오류가 잡힌다.
- 호출 자리의 명시 타입 인자는 팩을 괄호로 준다: `f<<(number, string)>>(...)`. luau-kb `luau-types/references/generics.md` §8 에 이미 있다.

## §6 팩을 테이블에 담으면 타입을 잃는다 (defer 패턴)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-store-generic-pack.luau`(실행 포함)

인자를 저장했다가 나중에 호출하는 코드(`task.defer` 흉내, Signal 의 큐, 재시도 래퍼)는 **새 솔버에서 저장 자리에서 깨진다**.

| 코드 (`...: A...` 안에서) | 결과 |
|---|---|
| `table.pack(...)` | `Expected this to be '...V', but got 'A...'`. `pack` 은 `<V>(...V)` 라 원소 타입이 하나뿐이어서 이질적인 팩을 못 받는다 |
| `{ ... }` | 타입이 `{nil}` 이 된다(에러 없음) |
| `fn(table.unpack(listed))` | `got '...nil'` 에러 |

**우회책(새 솔버에서 verified)**: 시그니처 `defer<A...>(fn: (A...) -> (), ...: A...)` 에서 호출부 검사를 받는다. 몸통에서는 `local args: { any } = { ... } :: any` 와 `local n = select("#", ...)` 로 저장하고, `fn(table.unpack(args, 1, n))` 으로 부른다. 그러면 호출부의 `defer(function(a: number, b: string) end, 1, 2)` 가 여전히 잡힌다. 몸통 안의 `any` 는 검사되지 않으므로 테스트로 지킨다. nil 이 낀 인자를 보존하려면 `#args` 가 아니라 `n` 을 쓴다(스니펫이 `1, nil, true` 로 확인한다).

옛 솔버(`--solver=old`)에서는 이 우회책도 `Trying to get a type from a variadic type parameter` 로 거부된다. 옛 솔버에 묶인 프로젝트는 시그니처를 `(...any)` 로 낮추는 수밖에 없다(실측 0.742 `--solver=old`).

## §7 별칭과 팩: 할 수 있는 것과 없는 것
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-alias-cannot-yield-pack.luau`, `packs-syntax-no-tuple-alias.luau` · 원천: rfcs `syntax-type-alias-type-packs.md` "Drawbacks"

| 하려는 것 | 결과 |
|---|---|
| 팩을 결과로 내는 별칭 `type P<T...> = T...` | `SyntaxError: ... type pack is not allowed in this context` |
| 튜플 별칭 `type M = (number, string)` | 다음 토큰에서 `Expected '->' when parsing function type`. 괄호 목록은 함수 타입의 일부로만 쓸 수 있다 |
| 팩의 앞 원소 떼기 `type Y<S...> = Car<S...>` (`Car<T, U...> = T`) | `expects at least 1 type argument`. 별칭은 즉시 인스턴스화되므로 `S...` 의 내용을 모른다(RFC) |
| 구체 팩에서 앞 원소 떼기 `Car<number, string, boolean>` | 된다(`number`) |
| 팩 파라미터 뒤에 일반 타입 `Two<S..., number, string>` | 에러 |
| 팩 파라미터 둘에 괄호 팩 `Two<(number, string), (boolean)>` | 된다 |

팩을 원소별로 계산하려면 type function 이 필요하다. 이 파일의 범위 밖이다(`type-functions.md`).

## §8 여러 값의 잘림과 "튜플 타입"이 없는 이유
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `packs-truncation.luau` · 원천: Lua 5.1 매뉴얼 §2.5 (식 목록 조정), luau.org/types/basic-types

- 여러 값을 반환하는 호출은 인자 목록이나 테이블 생성자의 **마지막 자리**에서만 펼쳐진다. 그 밖에서는 첫 값 하나로 잘린다. 타입 검사기도 이 규칙을 그대로 따른다.
  - `take(two())` 처럼 마지막 자리에서는 펼쳐진다. `two(): (number, string)` 이면 둘째 인자 `string` 이 `number` 자리와 대조돼 에러가 난다.
  - `take(two(), 1)` 은 첫 값만 쓰여 통과한다.
- 괄호 `(two())` 와 `typeof(two())` 도 첫 값 하나(`number`)다. 그래서 `typeof` 로 반환 팩 전체를 붙잡을 수 없다.
- 반환 팩에 이름을 붙이려면 함수 타입으로 감싼다(`type Ret = () -> (number, string)`). 값으로 들고 다니려면 레코드(`{ ok: boolean, value: number }`)나 `table.pack` 을 쓴다. 레코드는 타입이 남지만 `table.pack` 은 원소 유니온이 된다(§9).

## §9 개수가 타입에 남지 않는 자리
status: verified · last-confirmed: luau 0.742 (0.734 동일, 옛 솔버도 같은 줄에서 무진단) · 근거: `packs-unsound-positions.luau`, `packs-pcall-failure-value.luau`(둘 다 실행 포함) · 원천: `EmbeddedBuiltinDefinitions.cpp` 의 `unpack`, `pack`, `pcall` 선언과 xpcall 위 FIXME 주석

아래 자리에서는 정적 타입과 런타임 값이 다르다. 진단은 0건이다. 스니펫의 `assert` 로 런타임 값을 확인했다.

| 코드 | 정적 타입 | 런타임 |
|---|---|---|
| `local _, _, z = table.unpack({1, 2})` | `z: number` | `nil` |
| `rets(): ...number` 가 2개를 돌려줄 때 셋째 값 | `number` | `nil` |
| `local arr = { two() }`, `two(): (number, string)` | `arr: {number}`, `arr[2]: number` | `"a"` (string) |
| `local ok, v = pcall(half, -1)` 에서 `not ok` 분기의 `v` | `number`(R) | 에러 메시지 string |

- `table.pack(1, "a")` 는 `{ n: number, [number]: number | string }` 이라 정확하다(원소 유니온, 개수는 `n: number`).
- `pcall` 은 `<A..., R...>(f: (A...) -> R..., ...: A...): (boolean, R...)` 다. 넘긴 인자는 검사된다(`pcall(half, "x")` 에러). 하지만 실패 분기는 표현하지 못한다. 상류 주석에 따르면 원래 의도는 `(true, R1...) | (false, R2...)` 인데, 팩의 유니온을 표현할 수 없어 `(boolean, R...)` 로 쓴다고 한다.
- **처방**: 실패 분기에서는 `local msg = tostring(v)` 처럼 다시 변환한다. `unpack` 결과에는 개수(`n`)를 따로 검사한다.

## §10 넘친 인자를 잡지 않는 경우 (새 솔버)
status: verified · last-confirmed: luau 0.742 (0.734 동일, luau-lsp 1.70.1 동일) · 근거: `packs-extra-args.luau`, 짝 `packs-extra-args-old.luau`

| 호출 대상 | 모자란 인자 | 넘친 인자 |
|---|---|---|
| `local function take(a: number, b: number)` | 에러 | **무진단** |
| 테이블 필드 함수 리터럴 `tbl.f(1, 2)` | 에러 | **무진단** |
| 함수 타입 주석이 붙은 지역 `local typed: (number, number) -> () = take` | 에러 | 에러 |
| 내장 함수 `math.abs(1, 2)` | 에러 | 에러 |
| 옛 솔버(`--solver=old`)에서는 위 모두 | 에러 | 에러 |

- 원인 소스 줄은 확인하지 못했다. `OverloadResolver::isArityCompatible` 의 주석("we don't care if we pass more args than needed")은 오버로드 경로에만 해당한다. 직접 정의한 함수의 경로는 따로 추적해야 한다.
- 함수가 `(number, number) -> ()` 로 표시되는데도 넘친 인자를 받아 준다. API 를 바꿔 파라미터를 줄였을 때, 남은 호출부의 넘친 인자를 새 솔버는 알려 주지 않는다.
- **처방**: 공개 API 는 모듈 테이블의 필드에 타입 주석(`M.f = f :: (number, number) -> ()`)을 달거나 `export type` 의 함수 타입으로 노출한다. 어느 쪽이 넘친 인자를 잡는지는 아직 스니펫이 없다(미확인).

## §11 자료와 버전
| 자료 | 버전/날짜 |
|---|---|
| luau.org/types/basic-types, /types/generics | 2026-11-10 받음. 페이지에 날짜 없음. 예제는 play.luau.org iframe(lz-string 인코딩)에 들어 있어 디코드해서 읽음 |
| luau-lang/rfcs `syntax-type-alias-type-packs.md`, `syntax-typed-variadics.md`, `generic-functions.md` | 마지막 커밋 `364425c5` (2024-06-10). 저장소 HEAD `5fcbb5a2` (2026-10-16) |
| rfcs `explicit-type-parameter-instantiation.md` | `48734765` (2025-12-05). 팩 관련 서술 없음 |
| create.roblox.com/docs/en-us/luau/type-checking.md | 머리 `last_updated: 2026-11-10T00:40:40Z`. 문서 빌드 시각이며 내용 개정일이 아니다(모든 페이지가 같은 값) |
| Luau 소스 | `stl-luau/refs-ignoreme/luau` = 0.742, `8387cfb` (2026-10-09) |
| 실측 도구 | luau 0.734, 0.742 (`luau-analyze` 기본 새 솔버, `--solver=old` 비교), luau-lsp 1.70.1 참고 |

---
들어갈 luau-kb 스킬: **luau-types** (`references/typepacks-varargs.md` 신규. `generics.md` §8 은 이 파일로 넘기는 한 줄 링크로 줄인다)
