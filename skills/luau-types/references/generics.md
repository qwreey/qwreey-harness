# generics — 제네릭 추론, 명시 타입 인자, 콜백

## 이 파일이 답하는 질문
- Q1 제네릭 함수를 불렀더니 결과가 `unknown` 이 되고 그 뒤로 아무것도 안 잡힌다. 왜인가?
- Q2 `local m: Box<string, number> = New()` 처럼 주석을 달았는데 왜 에러가 나는가?
- Q3 `f<<T>>(...)` 는 언제 쓰고, 타입 팩에는 어떻게 쓰는가?
- Q4 콜백 파라미터를 `number` 로 적었는데 `string` 이 넘어와도 에러가 안 난다.
- Q5 "Consider placing the following annotations" 는 무슨 뜻인가?
- Q6 제네릭 함수 몸통 안에서 `return v` 가 `number` 자리를 통과한다.

## 목차
- §1 전제: 새 솔버는 기대 타입을 제네릭 호출 안으로 전파하지 않는다
- §2 조용히 `unknown` 이 되는 세 자리
- §3 해법: 명시 타입 인자 `f<<T>>`
- §4 콜백(람다)과 제네릭
- §5 람다 상한 소실 결함 (새 솔버)
- §6 제네릭 몸통이 검사되지 않는 결함 (새 솔버)
- §7 공변 인자 둘에서 T 를 풀 때 (버전 차이)
- §8 타입 팩과 가변 인자

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

## §7 공변 인자 둘에서 T 를 풀 때 (버전 차이)
status: verified · last-confirmed: luau 0.742 (0.734 와 다름) · 근거: `snippets/generics-covariant-args-intersection.luau` · 원천: stl typing-limits "공변 인자 둘에서 제네릭을 풀면 교집합"

`Concat<T>(...: { read [number]: T })` 에 `{ number }` 와 `{ string }` 을 넘기면:
- **0.734**: `T = number & string`. 결과 원소를 `number` 에도 `string` 에도 대입할 수 있었다(건전하지 않음).
- **0.742**: `T = number | string`. 양쪽 대입이 모두 거부된다.
- 불변 자리(`a: { T }, b: { T }`)면 두 버전 모두 "No valid instantiation" 에러다. 같은 원소 타입을 강제하려면 불변 자리로 받는다.

## §8 타입 팩과 가변 인자
status: verified · last-confirmed: luau 0.742 · 근거: `snippets/generics-pack-explicit-args.luau`, `snippets/solver-vararg-tail-call.luau`

- 팩 제네릭 `Fut<T...>` 에 명시 타입 인자를 줄 때는 괄호로 감싼다: `Rejected<<(number)>>(e)`, `<<(number, string)>>`. 괄호 없이 쓰면 "Too many type parameters" 에러.
- 가변 인자 자리의 꼬리 호출 결과(`f(mkStr())`, `f(1, mkStr())`, 여기서 `f(...: number)`)는 **0.734 에서 검사되지 않았고 0.742 에서는 잡힌다**. 0.734 에 묶여 있다면 `f((mkStr()))` 처럼 괄호로 값 하나로 만들어야 잡힌다.
- 타입 팩·가변 인자 전반의 정리본은 원천에도 없다(공백 영역). 새 사실은 스니펫부터 만들 것.
