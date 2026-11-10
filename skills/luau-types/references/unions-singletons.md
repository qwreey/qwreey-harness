---
title: "유니온, 교집합, 싱글턴, 좁히기"
description: "싱글턴 보존과 K & keyof + index 이름 인자 패턴, 태그 유니온 좁히기 실패, 옵셔널 갈래의 재귀 타입 무검사, 좁힌 뒤 호출 거부, 콜러블 테이블(함수∩테이블), catch-all 인덱서 교집합, 컨테이너 for-in"
keywords:
  - "싱글턴 보존"
  - "singleton"
  - "태그 유니온 좁히기"
  - "narrowing"
  - "K & keyof"
  - "index<M, K>"
  - "콜러블 테이블"
  - "callable table"
  - "함수 테이블 교집합"
  - "옵셔널 갈래 무검사"
  - "catch-all 인덱서 교집합"
  - "교집합 컨테이너 순회"
  - "Cannot call a value of the union type"
  - "could be nil"
  - "Cannot call a value of type *error-type* in union"
  - "not precise enough"
  - "Cannot iterate over a table without indexer"
  - "Cannot have more than one table indexer"
kind: reference
category: luau/types/unions
tags: [new-solver, silent, bug, correction]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# unions-singletons — 유니온, 교집합, 싱글턴, 좁히기

## 이 파일이 답하는 질문
- Q1 문자열 리터럴을 제네릭에 넘기면 `"A"` 로 남는가, `string` 으로 뭉개지는가?
- Q2 "이름 문자열 + 그 이름의 타입을 받는 콜백" 은 어떻게 타이핑하는가?
- Q3 `if o.isPresent then` 안에서 왜 좁혀지지 않는가?
- Q4 옵셔널(`X?`) 자리에서만 틀린 타입 인자가 통과한다.
- Q5 유니온에 넣었더니 틀린 테이블이 통과한다.
- Q6 `~= nil`, `type(x) == "function"` 로 좁힌 뒤 호출이 거부된다.
- Q7 함수이면서 필드도 있는 값(콜러블 테이블)은 어떻게 적는가? 함수 자리에 넘길 수 있나?
- Q8 유니온 파라미터에서 제네릭이 `unknown` 이 되거나 테이블 리터럴이 거부된다.
- Q9 `[string]: any` 인덱서가 낀 교집합에서 필드 검사가 사라진다.
- Q10 교집합·유니온 컨테이너를 `for … in` 으로 돌 때 루프 변수 타입은?

## 목차
- §1 싱글턴 보존
- §2 `K & keyof<M>` + `index<M, K>` 패턴
- §3 태그 유니온 좁히기가 죽는 경우
- §4 재귀 타입이 유니온 갈래일 때 타입 인자 무검사
- §5 같은 이름 메소드가 만드는 유니온 구멍
- §6 좁힌 뒤 호출이 막히는 두 경우
- §7 함수 ∩ 테이블은 never — 콜러블 테이블은 setmetatable 로
- §8 교집합 대조와 그 밖의 관측
- §9 유니온 파라미터 자리의 제네릭과 테이블 리터럴
- §10 catch-all 인덱서와의 교집합은 필드를 any 로 만든다
- §11 `for … in` 과 교집합·유니온 컨테이너
- §12 정정 (원천 저장소에 전달)

---

## §1 싱글턴 보존
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-singleton-preservation.luau` · 원천: quad typing-limits §7 싱글톤 표, 8.7 1번 (일부 정정)

| 선언 / 호출 | 추론된 결과 |
|---|---|
| `f<T>(x: T): T` 에 `f("bbb")` | `"bbb"` (보존) |
| `f<T>(x: T & ("A" \| "B")): T` 에 `f("B")` | `"B"`. 범위 밖 `f("C")` 는 "is not a subtype of" 에러 |
| `On<K>(name: K): { Name: K }` 에 `On("Position")` 를 담은 지역 | `{ Name: "Position" }` |
| 같은 호출을 **레코드 유니온** 기대 타입 `{ Name: "Position" } \| { Name: "Size" }` 에 대입 | `{ Name: string }` 으로 넓어져 **거부** |

- **정정**: quad 의 2026-08 표("`f<T>(x: T): T` 는 `string` 으로 뭉개짐", "`T & string` 은 `unknown`")는 0.734 와 0.742 새 솔버에서 재현되지 않는다. 그 동작은 지금 옛 솔버(`--solver=old`)에서만 보인다.
- 범위를 정해야 하는 이름 인자에는 `K & ("A" | "B")` 또는 아래 §2 의 `K & keyof<M>` 을 쓴다.
- 큰 싱글턴 유니온(수백 개)을 `K &` 로 교차하거나, 이름·타입 쌍을 오버로드 교집합으로 수십 개 찍으면 "Code is too complex" 로 죽는다(quad 8.7 2번, described). 같은 크기라도 §2 패턴은 통과했다.

## §2 `K & keyof<M>` + `index<M, K>` 패턴
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-keyof-index-param.luau` · 원천: quad typing-limits 8.7 3번 (2026-10-16 정정 포함), 8.10

```luau
type PM = { Position: number, Size: string }
local function On<K>(name: K & keyof<PM>, fn: (index<PM, K>) -> ()) end
On("Positon", function(v: number) end) -- Property '"Positon"' does not exist on type 'PM'
On("Size", function(v: number) end)    -- 콜백 타입 불일치
```

- 이름 오타와 콜백 파라미터 불일치가 호출 자리에서 잡힌다.
- 무주석 콜백 `function(v) ... end` 는 **검사만** 된다. `v` 로 문맥 타입이 흘러들지는 않는다. 본문 사용으로 `v` 의 타입이 먼저 굳고, 그 뒤 람다 전체가 `(index<…>) -> ()` 와 대조되어 람다 자리에 에러가 뜬다. 에디터 hover 는 `unknown` 이고 자동완성도 없다(quad 실측, described).
- `index<>` 로 만든 파라미터를 무주석 람다 안에서 **연산자**에 쓰면 타입 함수가 줄어들기 전에 연산자 제약이 풀려 "Operator '+' could not be applied to operands of types unknown and number" 가 난다(quad 8.10, described). 연산자를 쓸 파라미터에는 주석을 단다.
- `keyof`/`index` 도 내장 **타입 함수**다. 타입 함수 일반의 함정을 공유한다(type-functions.md).
- 맵에서 같은 이름이 클래스마다 다른 타입이면 `index<>` 가 유니온을 주고, 주석 단 콜백은 반공변 때문에 거부된다(described).

## §3 태그 유니온 좁히기가 죽는 경우
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-tagged-narrowing.luau` · 원천: stl typing-limits "태그 유니온 — 좁히기 전에 필드를 읽으면"

`type Opt<T> = { isPresent: true, value: T } | { isPresent: false, value: nil }`

| 상황 | `if o.isPresent then` 안에서 `o.value` 가 `T` 로 좁혀지나 |
|---|---|
| 같은 스코프에서 좁히기 **전에** `o.value` 를 읽음 | **아니다** ("Expected 'number', but got 'number?'") |
| 좁히기 전 읽기가 없음 | 좁혀진다 |
| 읽은 뒤 새 지역 별칭 `local p = o` 로 좁힘 | 좁혀진다 |
| 읽기가 다른 함수 안, 태그만 먼저 읽음, 읽기가 `if` 뒤 | 좁혀진다(원천 표, described) |

진단 문구가 "좁히기가 안 됐다"로 보이지 않아 헷갈린다. API 쪽에서는 사용자가 필드를 직접 읽을 일을 줄이는 함수(`UnwrapOr` 등)를 준다.

## §4 재귀 타입이 유니온 갈래일 때 타입 인자 무검사
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-recursive-in-optional.luau` · 원천: stl luau-solver-issues/5-recursive-alias-in-union.luau, quad 8.26

다음 둘 중 하나가 유니온(옵셔널 `X?` 포함)의 갈래이면, 새 솔버는 그 **타입 인자**를 검사하지 않는다.
- 재귀 별칭: `type Plain<T> = { value: T, next: Plain<T>? }`
- 자기 재귀 메소드를 가진 테이블: `type Box<T> = { read V: T, Put: (self: Box<T>, v: T) -> () }`

`Plain<string>` 값을 `Plain<number>?` 나 `Plain<number> | boolean` 자리에, `Box<string>` 을 `Box<number>?` 파라미터에 넘겨도 0건이다. 같은 값을 **비옵셔널** 자리에 넣으면 잡힌다. 자기 재귀 메소드가 없는 `BoxNoSelf<T>?` 도 잡힌다. 런타임에는 문자열이 `number` 자리로 간다.

처방: 옵셔널 입력 자리에는 메소드 없는 표식 타입을 쓴다(variance.md §8). 표식은 옵셔널 자리에서도 검사된다(quad 8.26 2026-11-08 실측, described).

**제네릭 없는 최소 꼴** (verified · 근거: `snippets/unions-self-ref-optional-hole.luau` · 원천: moonwave-luau/.claude/audit/mrow-spike/README.md:127-147, mrow/review/REVIEW.md:774, 후보 M-19): `type A = { f: (A) -> string }` 의 값을 `type B = { f: (B) -> number }` 에 넣으면 잡히지만 `B?` 에 넣으면 0건이다. 자기 참조 함수 필드만 있으면 타입 인자가 없어도 같은 구멍이 열린다. 이런 타입으로 조립하는 라이브러리(파서 결합자 등)는 값 사이의 배선이 타입으로 보장되지 않고, 값이 콜백이나 언랩으로 나오는 끝에서만 검사된다.

## §5 같은 이름 메소드가 만드는 유니온 구멍
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-same-name-method-hole.luau` · 원천: quad 8.9 (luau-test/done/31)

**규칙**: 서브타입 테이블에 **자기 타입을 참조하는 함수 필드**가 있고, 슈퍼타입 유니온의 어느 멤버가 **같은 이름의 함수 필드**를 가지면, 다른 필드(태그 싱글턴 등)가 어긋나도 대조가 통과한다. 다음은 모두 정상으로 거부된다: 재귀 없는 이름 충돌, 충돌 없는 재귀, 단일 테이블 슈퍼타입. 한도 플래그 문제가 아니라 판정 결함이라 플래그로 고칠 수 없다.

처방: 소속 검사용 유니온에는 메소드 없는 표식만 넣는다. 메소드 필드의 `self` 를 `any` 로 두거나, 이름 충돌을 생성기·린트로 막는다.

## §6 좁힌 뒤 호출이 막히는 두 경우
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-any-index-nonnil.luau`, `snippets/unions-function-narrowing.luau` · 원천: quad 8.24, 8.9 인접 실측

- `local cb = v[name]`(`v: any`) 뒤에 `if cb ~= nil then cb() end` 를 쓰면 "Cannot call a value of type *error-type* in union" 이 난다. `local cb: (() -> ())? = v[name]` 처럼 함수 타입을 적으면 된다.
- `type(x) == "function"` 으로 좁힌 값은 최상위 `function` 타입이 되어 호출하면 "not precise enough" 에러가 난다. 검사용 값과 호출용 값을 나눠, 호출용은 구체 함수 타입으로 캐스트한다.

**좁히기가 풀리는 두 자리** (verified · last-confirmed: luau 0.742, 0.734 동일 · 근거: `snippets/unions-annotated-local-branch-narrowing.luau`, `snippets/unions-closure-loop-narrowing.luau` · 원천: devplorer/.claude/feedback/quad-upstream-2026-10-20.md:48-58, 492-496, 후보 D-F30, D-F31)
- **주석 단 지역도 분기마다 대입 값으로 좁혀진다.** `local h: St<number> | S<number>` 에 분기별로 다른 값을 대입하면, 합쳐지는 자리에서 그 유니온이 되고 갈래마다 있는 제네릭 메서드 호출 `h:Compute(…)` 가 "Cannot call a value of the union type" 로 거부된다. 값을 if-식으로 만들어 한 타입으로 주석 단 지역에 담거나(`local k: St<number> = if … then … else …`), 값을 돌려주는 함수로 뺀다.
- **클로저 안 루프에서는 업밸류 좁히기가 듣지 않는다.** `if nav then nav.X() end` 가 루프 몸통 안이면 "Value of type 'Nav?' could be nil", 같은 클로저의 루프 밖이면 통과한다. 루프 전에 `local n = nav` 처럼 좁혀진 지역으로 받는다.
- 원천의 셋째 모양(필드를 좁힌 뒤 다른 호출이 끼면 `if ops.Tick then other(); ops.Tick(1) end` 가 실패)은 luau-analyze 0.734·0.742 와 luau-lsp 1.69.0·1.70.1 모두에서 재현되지 않았다(§12 정정).

## §7 함수 ∩ 테이블은 never — 콜러블 테이블은 setmetatable 로
status: verified · last-confirmed: luau 0.742 (0.734 와 일부 다름) · 근거: `snippets/unions-function-table-intersection.luau` · 원천: quad 8.6 (2026-11-06 재실측 문단)

- `((string) -> number) & { Merged: number }` 는 Luau 값 모델에서 거주하는 값이 없다(값의 원시 타입은 하나뿐이고 콜러블 테이블은 테이블이다). 새 솔버는 이를 never 처럼 다룬다. 그 값을 `local s: string = mk()` 에 넣어도 진단이 없다. 호출 자리의 인자 검사만 정상이다.
- 이런 값을 품은 레코드는 정규화되는 순간(무주석 지역 둘의 `a == b` 정제, `<Self>` 제네릭 메소드 풀이) 통째로 무너진다(quad 실측, described).
- **처방**: `setmetatable<{ Merged: number }, { __call: (any, string) -> number }>` 로 적는다. 반환 타입과 필드는 검사된다. `__call` 의 **인자** 검사는 0.734 에서 빠져 있었고(`ct(5)` 0건) 0.742 에서는 잡힌다.
- **콜러블 테이블은 함수 타입 자리에 들어가지 않는다**(verified · 근거: `snippets/unions-callable-table-not-function.luau`(실행 포함) · 원천: quad/.claude/base/source-state-plan.md:1204-1211, gate-plan.md:154-162, 후보 Q-125). `apply(f: (number) -> number)` 에 `__call` 테이블을 넘기면 "Expected this to be '(number) -> number'" 다. 직접 호출 `callable(1)` 은 타입이 맞고, 런타임은 같은 값을 함수처럼 부른다. 그래서 `--!nocheck` 스파이크로는 드러나지 않는다. 함수를 받는 API 에는 람다로 감싸 넘기거나 지정된 필드 함수를 쓴다. 원천이 함께 적은 "타입 레벨 `__call` 은 self 를 못 받는다"는 따로 재현하지 않았다(described).
- `__call` 을 제네릭으로 두거나 제네릭 생성자에 필드를 얹으면 어느 표기로도 명시 인스턴스화(`f<<T>>`)가 막힌다. 콜러블 테이블의 `__call` 은 비제네릭으로만 두고, 옵션 열거는 문자열 싱글턴 유니온으로 준다(quad 8.6, described).

## §8 교집합 대조와 그 밖의 관측
status: described · 원천: quad 8.25(2026-10-06 정정 배너), 8.31, 8.9 인접 실측, 8.17

- 왼쪽이 교집합(`A & B & C`)인 값을 구조 타입 하나에 대조하면 조각별 에러가 나고 거부되는 일이 있다. 원천이 다시 좁혀 보니, 실제 원인은 교집합 자체보다 **수신자 `self: X<T>` 가 목표의 `self: any` 와 반공변 자리에서 맞지 않는 것**일 가능성이 높았다.
- 교집합 파라미터(`{ [number]: E } & Shared`)에 리터럴을 주면 조각마다 따로 대조되어, 인덱서 조각이 문자열 키를 거부한다. 공유 필드는 교집합으로 호이스팅하지 말고 평평하게 인라인한다.
- 테이블 타입의 인덱서는 하나뿐이다("Cannot have more than one table indexer"). 키 유니온 `[number | Key]: V` 는 되지만 값 도메인은 하나다.
- 부정 타입이 없어 "이 타입의 하위 타입은 빼고" 같은 배제를 타입으로 표현할 수 없다.

## §9 유니온 파라미터 자리의 제네릭과 테이블 리터럴
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-generic-union-param.luau` · 원천: stl-luau-doctor/.claude/base/typing-limits.md:371-386 (후보 S-145)

파라미터 `{ read [number]: T } | Data<T>` 의 `T` 를 인자에서 뽑는 조건:

| 인자 타입 | `T` |
|---|---|
| `Data<number>` (갈래와 같은 타입) | `number` |
| `Data<number> & { read Len: … }` (갈래를 교집합 조각으로 품음) | `number` |
| 갈래의 필드에 `Len` 을 더한 **평평한** 테이블 | **`unknown`** (구조적으로는 갈래의 서브타입인데도) |

- 결과를 주석 단 자리에 담으면 "got 'unknown'" 으로 드러나지만, 주석 없이 들고 다니면 그 뒤 검사가 사라진다(generics.md §2 와 같은 누수).
- 처방: 갈래 타입을 말단 모듈 하나에 두고, 인자 쪽 타입은 그 별칭을 교집합 조각으로 품게 짓는다. 원천은 "같은 별칭일 때만"이라고 적었지만, 실측 조건은 "갈래 모양이 인자 타입 안에 조각으로 그대로 있느냐"다(구조만 같은 갈래로 적은 파라미터에도 `Data<number>` 인자는 풀렸다).
- **유니온 파라미터에는 테이블 리터럴의 기대 타입이 내려가지 않는다.** `Recs({ { key = "a", value = 1 } })` 는 `value: number?` 를 넓히지 못해 거부되고, 유니온이 아닌 `{ read [number]: R }` 파라미터는 통과한다. 리터럴을 주석 단 지역에 먼저 담아 넘긴다.

## §10 catch-all 인덱서와의 교집합은 필드를 any 로 만든다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-catchall-indexer-intersection.luau` · 원천: rbvm/.claude/design/known-issues.md:18-45 (후보 R-51, 원천은 luau-lsp 1.69.0)

`type X = { ShouldStop: boolean } & { Name: string, [string]: any }` 의 값에 `x.ShouldStop = nil` 을 써도, `local s: string = x.ShouldStop` 을 써도 새 솔버는 0건이다. 교집합이 없는 `{ ShouldStop: boolean }` 은 nil 대입을 잡는다. 확장 가능한 "네임스페이스" 타입에 `[string]: any` 를 두고 교집합으로 넓히면 게이트 통과가 로직 검증을 뜻하지 않게 된다. 원천 저장소에서는 옛 솔버가 같은 코드에 교집합 노이즈 340건을 냈다. 확장 필드는 이름 있는 필드로 적고 catch-all 인덱서를 빼거나, 인덱서 값 타입을 `unknown` 으로 둔다.

## §11 `for … in` 과 교집합·유니온 컨테이너
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/unions-intersection-iter-method.luau`, `snippets/solver-union-iter-no-indexer.luau` · 원천: stl-luau-doctor 의 base 측정 문서 76-91행(spikes/35, 37; 후보 S-P50), audit/luau-solver-issues/DRAFTS.md:236-247 (후보 S-141)

| 루프 | 루프 변수 |
|---|---|
| `for _, v in c` (`c` 가 `{ read [number]: T } & {…}` 교집합, 인덱서 경유) | **타입을 잃는다**(틀린 대입 0건) |
| `for i, v in c:Iter()` (메서드가 `((any, number) -> (number, T), any, number)` 삼중항을 돌려줌) | `number`, `T` 로 정확 |
| 같은 메서드를 정직하게 `(number?, T?)` 로 선언 | 옵셔널이 되어 산술에 바로 못 씀. 내장 `ipairs` 도 `(number, T)` 꼴로 선언돼 있다 |
| `for _, v in u` (`u` 가 인덱서 있는 갈래 \| 인덱서 없는 갈래의 유니온) | **진단 0건**, 루프 변수 타입도 안 본다. 인덱서 없는 갈래 하나만이면 "Cannot iterate over a table without indexer" |

교집합 컨테이너를 만들 때는 순회 메서드를 이터레이터 삼중항으로 노출한다. 원천 측정으로는 `__iter` 와 비용이 같았다(described).

## §12 정정 (원천 저장소에 전달)
status: verified (각 줄의 스니펫)

| 원천 | 원천 서술 | 실측 |
|---|---|---|
| `stl-luau-doctor/.claude/base/typing-limits.md:371-386` | 유니온 자리 제네릭은 인자가 갈래와 **같은 별칭**일 때만 풀린다 | 갈래 모양이 인자 타입 안에 (교집합 조각으로라도) 그대로 있으면 풀린다. 실패하는 것은 필드를 더한 평평한 테이블이다(§9) |
| `devplorer/.claude/feedback/quad-upstream-2026-10-20.md:494` | 필드를 좁힌 뒤 다른 호출이 끼면 "could be nil" | luau-analyze 0.734·0.742, luau-lsp 1.69.0·1.70.1 모두 재현 안 됨. 루프 모양만 재현(§6) |

