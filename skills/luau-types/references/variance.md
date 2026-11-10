# variance — 변성, 서브타이핑, 팬텀 표식

## 이 파일이 답하는 질문
- Q1 `Box<number>` 를 `Box<number | string>` 자리에 넣을 수 있는가? 왜 어떤 건 되고 어떤 건 안 되는가?
- Q2 타입 인자에 공변/반공변/불변을 내가 고를 수 있는가? (팬텀 필드)
- Q3 제네릭 함수에 틀린 값을 넘겼는데 `V` 가 넓어져서 통과해 버린다.
- Q4 파라미터가 적은 함수를 콜백 자리에 넣을 수 있는가?
- Q5 "No valid instantiation could be inferred for generic type parameter T" 가 맞는 호출에서 난다.

## 목차
- §1 read 필드는 공변, 읽기·쓰기 필드는 불변
- §2 함수 모양 팬텀으로 변성 고르기
- §3 값 팬텀의 nil 구멍
- §4 공변 자리에서 제네릭이 넓어지는 누수
- §5 제네릭 메소드의 반공변이 검사되지 않는 구멍
- §6 함수 파라미터 개수와 서브타이핑
- §7 교집합 + 불변/반공변 T = 추론 실패
- §8 입력 자리와 출력 자리를 나누는 설계 원칙

---

## §1 read 필드는 공변, 읽기·쓰기 필드는 불변
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-read-field.luau` · 원천: quad/.claude/base/typing-limits.md 8.11

| 선언 | `X<number>` → `X<number \| string>` | `X<number>` → `X<string>` |
|---|---|---|
| `{ read v: T }` | 통과(공변) | 거부 |
| `{ v: T }` (읽기·쓰기) | **거부**(불변) | 거부 |

- 공변이 필요한 입력 자리에는 `read` 를 붙인다. `read` 가 빠지면 같은 모양이라도 불변 비교된다.
- 옛 솔버는 `read` 키워드 자체를 "read keyword is illegal here" 로 거부한다. `read`/`write` 필드를 쓰는 코드는 새 솔버 전제다.
- 메소드가 붙은 큰 값도 폭 서브타이핑으로 작은 `read` 표식 자리에 들어간다(quad 8.11 실측 2·4번, described). 그래서 입력 자리는 작은 표식 타입만 요구해도 된다.

## §2 함수 모양 팬텀으로 변성 고르기
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-function-phantom.luau` · 원천: stl typing-limits "팬텀·표식의 모양", quad 8.42

| 팬텀 필드 | T 에 대해 |
|---|---|
| `read p: () -> T` | 공변 |
| `read p: (T) -> ()` | 반공변 |
| `read p: (T) -> T` | **불변** (공변 자리와 반공변 자리를 한 칸에) |
| `p: () -> T` (`read` 없음) | 불변 (읽기·쓰기 필드라 불변 비교) |

- 런타임 값이 없는 순수 팬텀이어도 된다. 런타임에 그 필드를 넣을지는 비용에 따라 고른다(원천들의 결정, described).
- 표식 하나(`read __tag: (K, V) -> (K, V)`)로 두면 별칭 이름이 에러 메시지에 그대로 남아 읽기 쉽다(stl 기록, described).
- 공변 칸과 반공변 칸을 **한 테이블 안의 두 필드**로 나눠도 판정은 같다(stl 배터리 실측, described). 단 **교집합**(`A & Out<T> & In<T>`)으로 나누면 §7 의 추론 실패를 밟는다.

## §3 값 팬텀의 nil 구멍
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-value-phantom-nil.luau` · 원천: stl typing-limits "값 팬텀은 피하세요", quad 8.42 1번

`read __phantom: T` 처럼 **값 모양** 팬텀을 쓰면, `T` 가 `nil` 을 품을 때(`number?`) 그 필드가 **아예 없는** 빈 테이블도 통과한다. 새 솔버가 없는 `read` 필드를 `nil` 로 읽기 때문이다. 함수 모양 팬텀 `(T) -> T` 는 이 경우를 거부한다. 표식에는 함수 모양을 쓴다. 소속만 표시하는 표식이라면 `read __kind: true` 같은 싱글턴 필드를 따로 둔다.

## §4 공변 자리에서 제네릭이 넓어지는 누수
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-covariant-generic-widening.luau` · 원천: stl typing-limits 머리 "2026-10-12 키·위치·값을 넘기는 제네릭은 불변 마커"

```luau
local function put<V>(m: { read v: V }, x: V) end
put(numberBox, "bad")       -- 0건: V = number | string 으로 넓어지고, numberBox 는 공변이라 그 자리에 들어감
local function putInv<V>(m: { read v: (V) -> V }, x: V) end
putInv(numberBoxInv, "bad") -- 잡힘
```

**규칙**: 타입 변수로 받은 키·위치·값을 컨테이너에 **넘기는** 제네릭(쓰기뿐 아니라 키를 넘기는 조회도 포함)은 컨테이너를 **불변** 표식으로 받는다. `==` 비교만 하는 값이나, 위치를 타입 변수로 두지 않은 조회는 넓어질 변수가 없어 공변 표식으로도 안전하다(stl 기록, described).

## §5 제네릭 메소드의 반공변이 검사되지 않는 구멍
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-generic-method-contravariance.luau` · 원천: quad typing-limits 8.9 끝 "H-321"

`{ Set: <Self>(self: Self, v: T) -> Self }` 같은 **제네릭 메소드**를 평범한 함수 타입 필드(`read Set: (self: any, v: number?) -> any`)에 대조하면 파라미터 `v` 의 반공변이 검사되지 않는다. `GRef<string>` 이 `number?` 를 받는 자리를 통과한다. 비제네릭 메소드는 정상으로 거부된다. 그래서 메소드 시그니처로 소속이나 변성을 검사하려 하지 말고 §2 의 팬텀 필드를 쓴다.

## §6 함수 파라미터 개수와 서브타이핑
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-function-arity.luau` · 원천: quad 8.23, 8.36 5번

| 대입 | 결과 |
|---|---|
| 파라미터가 적은 **리터럴**(`function(x) end`)을 `(number, number) -> ()` 에 | 통과(초과 인자는 버려지는 호출 관례) |
| 파라미터가 적은 `local function` 이름을 그 자리에 | 통과 |
| 파라미터가 적은 **선언된 함수 타입의 값**(`typed: (number) -> ()`)을 그 자리에 | **거부** ("Expected the parameter types to be a supertype") |
| 같은 값을 옵셔널 자리 `((string, number) -> any)?` 에 | 거부 |
| 파라미터가 **더 많거나** 타입이 다른 리터럴 | 거부 |

함의: 이벤트 콜백 자리에서 파라미터 수 부족은 에러가 아니다(언어 성질). 라이브러리가 `(T, number) -> any` 를 받는다면 사용자에게 함수 **값**도 같은 개수로 선언하게 하거나, 리터럴로 감싸게 한다.

## §7 교집합 + 불변/반공변 T = 추론 실패
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/variance-intersection-instantiation.luau` · 원천: quad audit consumer-type-surface-2026-10-06 probes/pure/repro_a1_pure.luau, quad 8.36 A1

`W<T> = { read v: T } & { read f: (T) -> () }` 처럼 **교집합 안에서 T 가 반공변이나 불변 자리**에 서면, 같은 별칭의 값을 넘겨도 `id<T>(x: W<T>)` 가 "No valid instantiation ... at least X | nil, at most X" 로 실패한다. `{ v: T } & {}` 도 같다. 다음은 통과한다.
- 같은 멤버를 **한 테이블**에 둔 `{ read v: T, read f: (T) -> () }`
- 교집합이어도 T 가 공변 자리뿐인 `{ read v: T } & { read x: number }`

제네릭 소비자가 받을 타입은 교집합 대신 평평한 테이블로 정의한다. 메소드의 `self: X<T>` 도 T 를 반공변 자리에 세우므로, `Data<T> & Methods<T>` 꼴의 전체형을 제네릭 인자로 받으면 이 실패를 밟는다(quad 기록, described).

## §8 입력 자리와 출력 자리를 나누는 설계 원칙
status: described · 원천: quad typing-limits 8.11 머리 배너, 8.41, 8.42; stl typing-limits "팬텀·표식의 모양"

위 사실들을 묶은 설계 원칙이다. 두 원천 저장소가 각자 실측으로 같은 결론에 닿았다. 프로젝트 고유 이름은 뺐다.
- **입력 자리**(사용자가 라이브러리에 건네는 값: 함수 파라미터, 옵션 레코드 필드, 사용자 콜백의 반환)는 재귀 구조가 없는 작은 **표식 타입**(`read` 필드와 팬텀)으로 받는다. 이점은 셋이다. 공변이라 넓은 자리에 들어가고, 검사 비용이 작고(재귀 메소드 구조 비교를 하지 않음), 선언 순서 누수(recursion-and-limits.md §3) 같은 재귀 함정이 끼어들 자리가 없다.
- **출력 자리**(반환값, 사용자 콜백의 인자, `self`)는 메소드가 다 붙은 **전체형**을 쓴다. 사용자가 메소드를 부르는 자리라 자동완성이 필요하다.
- 읽고 쓰는 상자는 전체형이 불변인 것이 맞다. 넣기만 하는 자리(반공변 표식), 읽기만 하는 자리(공변 표식), 둘 다 하는 자리(불변 표식)를 따로 둘 수 있다.
- 표식에서 전체형으로 돌아갈 때는 런타임 브랜드 확인 뒤 캐스트하는 변환 함수를 하나 둔다. `(m :: any) :: Full<T>` 는 `T` 를 검사하지 않는다.
