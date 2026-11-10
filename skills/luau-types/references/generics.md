# generics — 제네릭 추론, 명시 타입 인자, 콜백

## 이 파일이 답하는 질문
- Q1 제네릭 함수를 불렀더니 결과가 `unknown` 이 되고 그 뒤로 아무것도 안 잡힌다. 왜인가?
- Q2 `local m: Box<string, number> = New()` 처럼 주석을 달았는데 왜 에러가 나는가?
- Q3 `f<<T>>(...)` 는 언제 쓰고, 타입 팩에는 어떻게 쓰는가?
- Q4 콜백 파라미터를 `number` 로 적었는데 `string` 이 넘어와도 에러가 안 난다.
- Q5 "Consider placing the following annotations" 는 무슨 뜻인가?
- Q6 제네릭 함수 몸통 안에서 `return v` 가 `number` 자리를 통과한다. 몸통을 검사되게 쓰려면?
- Q7 `M(5)` 나 `pcall(f, …)` 을 거치면 왜 타입 인자가 풀리지 않나?
- Q8 명시 타입 인자 일부만, `never` 반환 뒤, 콜백 반환 개수, 타입 가드는?

## 목차
- §1 전제: 새 솔버는 기대 타입을 제네릭 호출 안으로 전파하지 않는다
- §2 조용히 `unknown` 이 되는 세 자리
- §3 해법: 명시 타입 인자 `f<<T>>`
- §4 콜백(람다)과 제네릭
- §5 람다 상한 소실 결함 (새 솔버)
- §6 제네릭 몸통이 검사되지 않는 결함 (새 솔버)
- §7 공변 인자 둘에서 T 를 풀 때 (버전 차이)
- §8 타입 팩과 가변 인자 → `packs-and-varargs.md`
- §9 호출 경로가 타입 인자를 잃는 자리: 콜러블 네임스페이스, pcall
- §10 호출 표면의 작은 규칙 (부분 명시 인자, freeze, never, 콜백 반환 개수, 타입 가드 부재)

표기: 각 절의 `status:` 줄에서 `verified` 는 스니펫이 0.734 와 0.742 에서 그 주장대로 통과했다는 뜻이고, `described` 는 원천의 서술만 있고 이 저장소에서 재현하지 않았다는 뜻이다. 스니펫은 저장소 루트의 `snippets/` 에 있다.

---

## §1 전제: 새 솔버는 기대 타입을 제네릭 호출 안으로 전파하지 않는다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-annotation-does-not-flow.luau`

`local x: Box<string, number> = New()` 처럼 왼쪽에 주석을 달아도, 새 솔버는 그 주석을 `New` 의 `K`, `V` 추론에 쓰지 않는다. 인자에 재료가 없으면 `K`, `V` 는 `unknown` 이 된다. 그러면 결과 `Box<unknown, unknown>` 가 주석과 맞지 않아 **에러가 난다**(위양성). 옛 솔버는 이 대입을 받아 줬다. 그래서 같은 코드가 솔버를 바꾸자 깨지는 일이 생긴다.

이 성질이 아래 §2 의 세 자리를 모두 만든다. 기대 타입이 흘러들지 않는 자리에서 결과가 `unknown` 이 되는데, 거기에 주석이 없으면 에러도 나지 않고 조용히 지나간다.

## §2 조용히 `unknown` 이 되는 세 자리
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-literal-to-indexer-unknown.luau`, `snippets/generics-annotation-does-not-flow.luau` · 원천: stl-luau/.claude/base/typing-limits.md "조용히 타입을 잃는 자리 셋"

| 자리 | 예 | 결과 |
|---|---|---|
| 인자 없는 생성자 | `New()` | `Box<unknown, unknown>` |
| 테이블 리터럴을 `{ [K]: V }` 파라미터에 넘김 | `FromTable({ a = 1 })` | `{ a = 1 }` 의 타입은 `{ [string]: number }` 가 아니라 레코드 `{ a: number }` 다. 그래서 맞출 `K`/`V` 가 없다 |
| 반환 타입에만 나오는 제네릭 | `Flat({})` | `{ unknown }` |

가장 위험한 것은 둘째 자리다. 한 번 `unknown` 이 된 컨테이너에는 **어떤 키와 값을 써도** 진단이 없다. 스니펫에서 `Put(leaked, 5, "bad")` 와 `leaked.data[true] = {}` 가 0건으로 통과하고, 옛 솔버는 둘째 줄을 잡는다. `unknown` 을 구체 타입에 **읽어 담을 때만** "got 'unknown'" 에러가 난다.

## §3 해법: 명시 타입 인자 `f<<T>>`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-literal-to-indexer-unknown.luau`, `snippets/generics-annotation-does-not-flow.luau`, `snippets/generics-lambda-context.luau`

호출 자리에서 `f<<K, V>>(...)` 로 타입 인자를 직접 준다. 그러면 위 세 자리가 모두 풀린다.

```luau
local m = New<<string, number>>()
local h = FromTable<<string, number>>({ a = 1 })
local f = Flat<<number>>(nested)
```

- 캐스트(`New() :: Box<string, number>`)도 되지만 캐스트는 "내 말을 믿어라"라서 검사를 끈다. 명시 타입 인자는 답을 알려 주는 것이라 검사가 그대로 살아 있다.
- 단일 꺾쇠 `f<T>(x)` 는 비교 연산자와 모호해서 쓸 수 없다. 반드시 `<<`, `>>` 로 쓴다.
- 명시 타입 인자는 콜백 파라미터의 문맥 타입도 정한다. 자세한 것은 §4.
- 오버로드(함수 교집합)와 `__call` 을 가진 테이블에는 명시 인스턴스화를 할 수 없다. 이 경우 "explicitly instantiating an overloaded function type" 류 에러가 난다(described, 원천: quad typing-limits 8.6 (3), stl typing-limits 유니온 표).
- 포매터 주의: stylua 가 설정 파일을 찾지 못하면 `f<<T>>(x)` 를 `f << T >> x` 로 조용히 바꾼다. luau-verify 스킬의 tooling 참고.

## §4 콜백(람다)과 제네릭
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-lambda-context.luau`, `snippets/generics-bare-lambda-free-type.luau` · 원천: stl typing-limits "콜백 파라미터 주석도 없앱니다", "첫 return 이 결과 타입을 굳힘", quad typing-limits §1③ 각주

**규칙**: 제네릭 호출의 인자로 넘긴 함수 리터럴에는 기대 함수 타입이 흘러들지 않는다. 그래서 `Map(nums, function(v) ... end)` 의 `v` 는 `nums` 에서 정해지지 않는다.

| 모양 | 결과 |
|---|---|
| 맨 람다, 몸통이 파라미터를 제약함(`v * 2`) | 에러: "Consider placing the following annotations on the arguments" |
| 맨 람다, 몸통이 파라미터를 제약하지 않음(`return v`) | 0.734: 결과가 자유 타입이 되어 아무 데나 대입됨(누수). **0.742: 잡힘**. luau-lsp 1.70.1: 여전히 누수 |
| 파라미터 주석 `function(v: number)` | 정상 |
| 명시 타입 인자 `Map<<number, number>>(nums, function(v) ...)` | `v` 가 `number` 로 정해지고 `v.foo` 같은 오용이 잡힘 |
| 분기마다 다른 타입을 반환(`return nil` 다음 `return v`) | **첫 `return` 이 결과 타입을 굳혀** "Expected 'nil', but got 'number'" 에러. 반환 주석 `(v: number): number?` 나 `<<number, number?>>` 로 푼다 |

실무 처방: 콜백을 넘길 때는 명시 타입 인자나 파라미터 주석 중 하나를 **항상** 붙인다. 0.742 에서 누수 한 칸이 고쳐졌지만, 아래 §5 의 결함이 여전히 남아 있다.

## §5 람다 상한 소실 결함 (새 솔버)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-callback-bound-lost.luau` · 원천: stl-luau/.claude/audit/luau-solver-issues/1-annotation-bound-lost.luau, DRAFTS.md 1번

```luau
local function F<T>(x: T, fn: (T, T) -> ()) end
local text: string = "x"
F(text, function(v: number) end)          -- 새 솔버 0건 (옛 솔버는 잡음)
F(text, function(v: number, _w) end)      -- 잡힘
```

- **조건**: 제네릭 `T` 를 추론해야 하고, 람다가 **뒤쪽 파라미터를 생략**했으며, 생략한 파라미터의 타입이 `T` 를 공변이나 불변 자리에 품고 있다. 이때 람다 주석이 `T` 에 주는 상한이 버려진다. 좁은 타입뿐 아니라 전혀 다른 타입도 통과한다.
- **잡히는 경우**: 옛 솔버, 비제네릭 함수, 명시 타입 인자(`F<<string>>(...)`), 람다가 그 파라미터를 선언함(주석 없이라도), 생략한 파라미터 안의 `T` 가 반공변(`(T) -> ()`)인 경우.
- 생략한 파라미터의 모양은 상관없다. `T`, `{ T }`, `{ read [number]: T }`, `{ get: () -> T }` 모두 같다(원천의 실측 행렬, described).
- 콜론 호출(`a:Map(fn)`)은 `self` 에서 `T` 가 먼저 정해져 이 결함 경로를 타지 않는다(described, stl typing-limits "ArrView<T> 에서 결함을 피하는 호출 모양" 표).
- 업스트림에는 아직 보고하지 않았다. 원천 저장소의 결정이고, 초안은 원천의 DRAFTS.md 에 있다. 인접 이슈로 `luau-lang/luau#2168` 이 있는데, 증상은 반대(에러가 나는 쪽)다.

**설계 함의**: 콜백 타입을 새로 만들 때, 다른 파라미터에 `T` 를 품은 테이블을 두면 사용자가 그 파라미터를 생략했을 때 이 구멍이 열린다.

## §6 제네릭 몸통이 검사되지 않는 결함 (새 솔버)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-body-unchecked.luau`, `snippets/generics-string-key-literal-indexer.luau` · 원천: stl luau-solver-issues 3, 3b, 4 와 DRAFTS.md 3번

- 제네릭 함수 안에서 타입 변수 `V` 의 값을 구체 타입 자리에 넣어도(`return v` 를 `number` 반환에, `needsNumber(v)`) 진단이 없다. 반대 방향(구체 값 `"bad"` 를 `V` 자리에)도 마찬가지다. 캐스트도 `any` 도 없이 정적 타입 `number` 에 런타임 문자열이 든다. 스니펫이 `assert` 로 이를 확인한다. 옛 솔버는 둘 다 잡는다.
- 원인: `Analysis/src/Subtyping.cpp:830-835` 가 스코프 안의 제네릭을 서브타입 쪽이면 `never`, 슈퍼타입 쪽이면 `unknown` 으로 바꿔 끼운다. 상류 주석에 "TODO: These branches are entirely incorrect" 가 있다. 공개 이슈 #2733 은 일부만 고치고 닫혔다(described, stl DRAFTS.md 3번 소스 분석).
- 같은 계열: 문자열 키 테이블 리터럴을 `{ [string]: number }` **파라미터에 직접** 넘기면 값 타입을 보지 않는다(`plain({ x = "bad" })` 0건). 주석 단 지역에 담으면 잡힌다.

**처방**: 제네릭 헬퍼 몸통은 타입 검사를 믿지 말고 테스트로 지킨다. 불변 마커(variance.md) 같은 호출 자리 방어는 몸통 안의 재호출을 막지 못한다.

### §6-1 0.739 의 땜질 범위와 탐침 타입
status: verified · last-confirmed: luau 0.742 (0.734 와 다름, luau-lsp 1.70.1 은 0.742 와 같음) · 근거: `snippets/generics-body-probe-type.luau` · 원천: stl-luau-doctor/.claude/research/luau-source/README.md 1-3·1-5 절, conventions.md:75 (후보 S-138)

- 0.739 에 들어간 땜질 플래그 `LuauSoundGenericMismatches` 는 **기대 타입이 정확히 스코프 안의 `T`** 일 때만 거절한다. 그래서 `return 5`(반환 타입 `T`)는 0.742 에서 잡히고 0.734 에서는 0건이다. 원천의 소스 조사로는 `return`, 대입, 비제네릭 함수의 호출 인자 자리에만 닿고 지역 초기화에는 닿지 않는다.
- 두 버전 모두 0건으로 남는 줄: `T?` 반환에 `123`, `local y: T = "s"`(지역 초기화), `local z: number = x`(`x: T`, 제네릭 값을 구체 자리에).
- **탐침 타입 우회**: 몸통을 제네릭 대신 봉인된 구체 타입 `{ read __probeA: true }` 로 쓰면 제네릭 갈래를 타지 않고 구조 비교를 받아 양방향이 다 잡힌다. 결함이 고쳐져도 그대로 맞는 코드다. 경계: 필드 이름을 아는 `{ read __probeA: boolean }` 이나 `{}` 같은 넓은 타입에는 구조적으로 들어가 버린다(원천 기록, described).

## §7 공변 인자 둘에서 T 를 풀 때 (버전 차이)
status: verified · last-confirmed: luau 0.742 (0.734 와 다름) · 근거: `snippets/generics-covariant-args-intersection.luau` · 원천: stl typing-limits "공변 인자 둘에서 제네릭을 풀면 교집합"

`Concat<T>(...: { read [number]: T })` 에 `{ number }` 와 `{ string }` 을 넘기면:
- **0.734**: `T = number & string`. 결과 원소를 `number` 에도 `string` 에도 대입할 수 있었다(건전하지 않음).
- **0.742**: `T = number | string`. 양쪽 대입이 모두 거부된다.
- 불변 자리(`a: { T }, b: { T }`)면 두 버전 모두 "No valid instantiation" 에러다. 같은 원소 타입을 강제하려면 불변 자리로 받는다.

## §8 타입 팩과 가변 인자
타입 팩, 가변 인자, 여러 값 반환, 팩 명시 타입 인자(`<<(number)>>`), 가변 인자 자리 꼬리 호출(0.734 와 0.742 차이)은 `packs-and-varargs.md` 로 옮겼다(§5, §11).

## §9 호출 경로가 타입 인자를 잃는 자리: 콜러블 네임스페이스, pcall
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/generics-callable-namespace.luau`, `snippets/generics-pcall-unit-return.luau` · 원천: stl-luau-doctor/.claude/conventions.md:40, 114, base/architecture.md:300 (후보 S-136, S-137)

- **콜러블 네임스페이스**: 모듈 테이블에 `__call` 을 달아 `M(5)` 로 제네릭 생성자를 부르면 결과의 타입 인자가 검사되지 않는다. `M(5).v` 를 `string` 에 담아도 0건이다. `__call` 을 `function<T>(_: any, v: T): Box<T>` 로 주석해도 같다. 같은 생성자를 필드로 부르면(`M.New(5)`) 잡힌다. 생성자는 `M.New` 같은 네임스페이스 함수로 노출한다. 원천은 "모듈 필드 오타도 못 잡는다"고 적었지만 이 꼴에서는 `M.Neww` 가 잡혔다(정정은 solver-limits.md §7).
- **반환이 `()` 인 제네릭을 pcall 에 바로**: `pcall(each, { 1, 2 }, function(x: number) end)` 처럼 맞는 호출도 "Expected this to be exactly 'T', but got 'number'" 로 거부된다(위양성). 반환이 있는 제네릭은 같은 모양이 통과한다. `pcall(function() each(…) end)` 로 감싼다.
- 명시 인스턴스화(`f<<T>>`)는 오버로드와 `__call` 테이블에 쓸 수 없다(§3). 콜러블 테이블이 함수 타입 자리에 들어가지 않는 것은 `unions-singletons.md` §7.

## §10 호출 표면의 작은 규칙
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/solver-explicit-args-freeze-never.luau`, `snippets/generics-callback-fewer-returns.luau` · 원천: stl-luau-doctor/.claude/base/trait-system.md:34,44, archive/conventions-2026-11-04.md:542-543 (후보 S-146), quad/.claude/base/slot-plan.md:1232-1240, brand-plan.md:291-298 (후보 Q-127)

| 규칙 | 실측 |
|---|---|
| 명시 타입 인자를 **일부만** 주면 안 된다 | `two<<number>>(1, "s")`(타입 변수 둘) → "Internal error: outstanding free or blocked type in function call". 그래서 제네릭 파라미터의 **순서가 공개 표면**이다. 자주 명시할 것을 앞에 둔다 |
| `table.freeze({ … })` 결과의 필드는 `read` | `t.a = 2` → "Property a … is read-only" |
| `never` 를 돌려주는 호출 뒤를 함수의 끝으로 보지 않는다 | `raise("neg")` 로 끝나는 분기 → "Not all codepaths in this function return 'number'". `return raise(…)` 로 쓴다 |
| 콜백은 선언된 반환 **개수**를 채워야 한다(옵셔널이어도) | `(number) -> (string?, number?)` 자리에 `return "a"` → "Expected 'string?, number?', but got 'string?'". 덜 돌려줘도 되는 API 는 함수 타입 유니온(`F2 \| F1`)으로 받는다 |
| 사용자 정의 타입 가드(`x is T`)가 없다 | `if isStr(u) then local s: string = u end` → "got 'unknown'". 술어 뒤에 `u :: string` 으로 캐스트하거나 `type(u) == "string"` 을 그 자리에 쓴다 |
