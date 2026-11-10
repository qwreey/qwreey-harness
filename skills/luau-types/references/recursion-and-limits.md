# recursion-and-limits — 재귀 타입, 선언 순서, 검사기 한도

## 이 파일이 답하는 질문
- Q1 `Foo<T>` 의 메소드가 `Foo<U>` 를 돌려주는데 결과 타입 검사가 사라진다.
- Q2 별칭 선언 순서를 바꿨더니 진단이 생기거나 사라진다.
- Q3 "Recursive type being used with different parameters" 는 언제 나는가?
- Q4 "Internal error: Code is too complex to typecheck!" 가 나면 무엇을 해야 하나?
- Q5 한도 플래그(`LuauTarjanChildLimit` 등)는 어떤 증상에 듣는가?

## 목차
- §1 비균일 재귀 반환의 조용한 누수
- §2 옛 솔버는 선언 시점에 거부한다
- §3 선언 순서 누수 (새 솔버 전용)
- §4 상호 재귀 별칭 그룹
- §5 "Code is too complex" 와 한도 플래그
- §6 too complex 를 줄이는 설계
- §7 언제 풀리는가

---

## §1 비균일 재귀 반환의 조용한 누수
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/recursion-nonuniform-return.luau` · 원천: quad/.claude/base/typing-limits.md §1 (①③, H-24)

**무엇**: 제네릭 타입 `Foo<T>` 의 메소드가 **다른 타입 인자로 자기 자신**을 돌려주면(`Mapped: <U>(self: Foo<T>, fn: (T) -> U) -> Foo<U>`, "비균일 재귀"), 인라인으로 선언한 그 메소드의 반환이 조용히 에러 타입이 된다. 그 결과에 대한 검사가 모두 사라지고 진단은 0건이다.

**정확한 경계**(이것들은 정상이다, quad §1 표, 이 저장소에서는 균일 재귀만 verified):
- 같은 인자로만 재귀(`-> Foo<T>`)
- 재귀가 아닌 다른 컨테이너에 담아 반환(`-> Box<U>`)
- 감싸지 않고 그대로 반환(`-> U`)

**처방 (verified)**: 메소드를 이름 붙은 최상위 함수로 선언하고 필드 타입을 `typeof(그 함수)` 로 준다.

```luau
local function Mapped<T, U>(self: Tw<T>, fn: (T) -> U): Tw<U>
	...
end
type Tw<T> = { Value: T, Mapped: typeof(Mapped) }
```

이렇게 하면 주석 없는 지역에 받아도 다운스트림이 정확히 타이핑된다. 원천 기록으로는 50단 체이닝, 타입이 바뀌는 체이닝, 콜백 안 재호출까지 비용 없이 된다(described). 남는 것:
- 콜백 파라미터에는 여전히 주석이 필요하다(generics.md §4 의 일반 규칙).
- 대입 줄 자체의 틀린 LHS 주석(`local wrong: Tw<boolean> = t:Mapped(...)`)은 그 줄에서 잡히지 않고 다운스트림에서만 잡힌다(described).
- `setmetatable<{...}, { __index: typeof(...) }>` 로 확장하면 모순되는 진단 두 개가 동시에 나는 솔버 버그를 만났다(quad §1③ "채택 안 함", 0.733 관측, described).

**같은 결함의 다른 얼굴** (described · 원천: stl-luau-doctor/.claude/research/class-like/README.md:24-26 · 후보 S-144): 원소 타입을 바꾸는 메서드 `Map: <U>(self: Arr<T>, …) -> Arr<U>` 를 인스턴스 타입에 적으면 정의 줄은 조용히 통과하고 반환이 `*error-type*` 이 되어, 결과를 쓰는 줄의 검사가 모두 꺼진다. 위 비균일 재귀 반환(S7)과 같은 모양이다. 별칭을 한 번 거치면 "Recursive type being used with different parameters" 로 드러난다는 기록도 같은 뿌리를 가리킨다(§2·§3). 타입을 바꾸는 연산은 메서드가 아니라 네임스페이스 함수(`Arr.Map(a, fn)`)나 위 `typeof(최상위 함수)` 처방으로 둔다.

**보조 처방 (described)**: 콜백 파라미터 무주석 추론이 필요하면 타입을 "데이터부 / 메소드부"로 쪼갠다. 메소드의 `self` 와 콜백 파라미터가 메소드를 모르는 데이터부를 가리키게 한다(`Foo<T> = FooData<T> & { Map: <U>(self: FooData<T>, fn: (FooData<T>) -> U) -> Foo<U> }`). 결과 바인딩에는 여전히 주석이 필요하다.

## §2 옛 솔버는 선언 시점에 거부한다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/recursion-old-solver-rejects.luau`

`--solver=old` 는 비균일 재귀 별칭을 선언 줄에서 "Recursive type being used with different parameters." 로 거부한다. 새 솔버는 선언은 받아 주지만 §1 처럼 인스턴스화에서 샌다. RFC 의 완화가 선언 검사까지는 들어왔고 인스턴스화까지는 아직인 중간 상태로 보인다(quad 해석, described).

## §3 선언 순서 누수 (새 솔버 전용)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/recursion-declaration-order.luau` · 원천: quad typing-limits 8.21

**조건 둘이 동시에** 성립하면, 앞에 선언된 별칭 안의 `SC<number>` 참조가 **통째로 에러 타입**이 되어 진단 없이 무엇이든 통과한다.
1. 참조하는 별칭(또는 함수 파라미터 주석)이 대상 제네릭보다 **파일에서 먼저** 선언됐다.
2. 대상이 **비균일 재귀**(§1 의 모양)다.

뒤에 선언된 별칭이나 균일 재귀는 정상이다. 옛 솔버는 문장을 의존성 순으로 재정렬한 뒤 검사하므로 이 순서 의존이 없다.

**원인**(quad 소스 조사, 0.734 = `3fc82b1`, described): 새 솔버는 제약을 만들어진 순서대로 푼다. 앞선 `SC<number>` 확장이 SC 본문 안의 `SC<U>` 확장보다 먼저 처리되고, 무한 확장 가드(`ConstraintSolver.cpp` 의 별칭 확장부)가 `U ≠ T` 를 보고 무한 타입으로 오판해 바깥 확장 전체를 `errorType` 으로 묶는다. 진단은 다른 스코프에 기록되어 보고되지 않는다.

**규칙**: 비균일 재귀 제네릭 별칭은 그것을 쓰는 **모든 별칭·주석보다 먼저** 선언한다. 또는 다른 모듈에서 가져와 쓴다(이미 풀린 다른 모듈의 별칭은 안전, described).

## §4 상호 재귀 별칭 그룹
status: described · 원천: quad typing-limits §1 "정확한 경계" 각주, §8 체크리스트 8번, §7 첫 항목

- 같은 인자로만 도는 상호 재귀 그룹(`Tree<T>` ↔ `Item<T> = T | Tree<T>`)은 정상이다.
- 그 그룹 안에서 **메소드 제네릭을 인자로 받는 별칭**을 따로 뽑으면(`UpdateFn<Item, T>` 를 `<Item>(...)` 메소드 안에서 쓰기) "Recursive type being used with different parameters" 로 거부된다. 에러가 나니 조용한 손실은 아니다. 처방: 그 시그니처를 메소드 자리에 인라인한다.
- 서브타입 호환이 걸린 두 제네릭 별칭의 상호 재귀(`A<T>` 가 `B<T>` 를 참조하고 그 반대도 참조)는 솔버가 취약하다. 의존은 한 방향으로 둔다.

## §5 "Code is too complex" 와 한도 플래그
status: described · 원천: quad typing-limits 8.5, 8.7 4번, 8.9, 8.12, 8.28, 8.40, 8.41; quad/scripts/doc-snippets.py FLAGS

- **플래그를 바꾸는 길** (정정 2026-11-10, verified · 근거: `snippets/verify-fflags-force-strict.luau`, 0.742 소스 `CLI/src/Flags.cpp`, `CLI/src/Analyze.cpp:434` · 후보 S-129, claude-doctor audit/09 §6 모순 1):
  - `luau-analyze --fflags=Name=true|false[,Name2=…]` 로 **불리언** 플래그를 바꿀 수 있다. `--help` 에는 나오지 않는다(이 파일의 옛 서술 "플래그 옵션이 없다"는 `--help` 만 보고 쓴 것이라 틀렸다).
  - 모르는 이름은 stderr 에 `Warning: unrecognized flag 'X'.` 를 내고 무시된다. **정수 한도**(`LuauTypeInferIterationLimit=1000000` 등)는 `Warning: unrecognized value '…' for flag …` 로 무시된다. 소스가 불리언 플래그 목록만 돈다. 경고는 종료 코드를 바꾸지 않으니 stderr 를 본다.
  - 예: `--fflags=DebugLuauForceStrictMode=true` 는 `.luaurc` 의 nonstrict 를 덮고 strict 로 검사한다.
  - CLI 는 실험적이지 않은 `Luau*` 플래그를 모두 켠 채 시작한다. 그래서 Studio·luau-lsp 에디터와 판정이 다를 수 있다(원천 서술, described).
  - 따라서 이 절의 **한도 플래그(정수)는 여전히 luau-lsp `analyze --flag:Name=값`** 이나 에디터의 `luau-lsp.fflags.override` 로만 바꿀 수 있다. Studio 의 분석기는 사용자가 바꿀 수 없다.
- **증상마다 듣는 레버가 다르다**(원천의 이분 탐색 결과):

| 증상 | 들은 플래그 | 안 들은 것 |
|---|---|---|
| 큰 생성 별칭이 **존재하는 것만으로** too complex (클래스 수 × 필드 수에 비례) | `LuauTarjanChildLimit` (기본 10000 → 4만~16만) | TypeInferRecursion/Iteration, NormalizeCache |
| 멤버가 많은 타입의 콜백 유니온 대조 | `LuauSubtypingIterationLimit` (5만~10만) | Simplification, SolverConstraint 등 |
| 상위 클래스 캐스트·큰 표를 통째로 제네릭에 맞춤 | `LuauTypeInferIterationLimit` (기본 20000 → 100만) | — |
| 유니온 안에 재귀 메소드 테이블을 직접 넣음 | **없음**(15종 모두 무효) | 설계를 바꿔야 함(§6) |
| 같은 유니온을 수백 자리에 인라인 | 없음 | 별칭 하나로 한 번만 선언하면 풀림 |

- **too complex 는 진단을 지운다**: 한 자리가 무너지면 그 타입을 쓰는 다른 호출부의 진단까지 조용히 사라진다(quad 8.28). 임시 프로브는 CI 와 **같은 플래그**로 돌린다.
- 측정법: 건수만으로는 효과가 보이지 않는다. "too complex 없이 통과하는 최소 한도"를 이분 탐색해 비교한다(quad 8.41).
- **Studio 는 무너져도 표시하지 않는다**(described · 원천: quad/.claude/research/release-3.4.0-plan.md:30, declaration-surface-plan.md:94-98, base/surface-plan.md:19 · 후보 Q-128). 원천 기록으로 Studio 는 `LuauSolverConstraintLimit=1500` 동기화 값으로 돌았고, 생성된 타입 약 2300줄(호출 약 1500)을 내보내는 모듈에서 검사가 꺼졌는데 Studio 화면에는 음성 대조군이 0건으로만 보였다. 한도는 **모듈이 내보내는 타입**에 걸리고 파일 안 무게는 그 파일에 갇혔다(파일당 0.04~0.17초, 선형). Studio 의 플래그 값은 엔진 갱신으로 바뀔 수 있으니 날짜와 함께 읽는다.
- **`any` 파라미터에 큰 모듈 표를 넘길 때**(described · 원천: stl-luau-doctor/.claude/audit/luau-solver-issues/DRAFTS.md:285-293, research/class-like/README.md:53-60 · 후보 S-143): 제네릭 함수 F 개가 메서드 M 개짜리 인스턴스 타입을 받는 모듈 표를 `local function take(_x: any)` 에 넘기면 too complex 가 나고, 같은 값을 `unknown` 파라미터·`Module :: any`·`local x: any = Module` 로 넘기면 나지 않는다는 기록이다. 원천의 소스 분석은 `any` 를 모든 칸에 밀어 넣는 걸음이 F × M 에 비례해 `LuauTypeInferIterationLimit`(2만)을 넘는다는 것이다. 이 저장소의 단순 꼴(읽기 메서드, `self: any`, F 50 × M 30)에서는 `any`/`unknown`/캐스트 사이에 차이가 없었고, 60 × 40 에서는 정의만으로 too complex 가 났다. 재현 조건(메서드 모양)이 더 필요하다. 처방(파라미터를 `unknown` 으로)은 비용이 없으니 그대로 권한다.

## §6 too complex 를 줄이는 설계
status: described · 원천: quad 8.8, 8.9 (2), 8.11, 8.12, 8.41

- 유니온에는 재귀 메소드 테이블을 넣지 말고 **표식 타입**(`{ read __kind: "A" }`)만 넣는다.
- 같은 유니온은 **별칭 하나**로 한 번만 선언하고 재사용한다.
- 큰 파일 안에서 외부 모듈 별칭을 유니온 인자로 새로 인스턴스화하지 말고, 전개는 별도 모듈에서 하고 큰 파일은 재별칭만 한다.
- 입력 자리는 전체형 대신 표식으로 받는다(variance.md §8). 원천에서 필요 한도가 크게 줄었다.
- 큰 표를 통째로 `...: any` 나 제네릭에 넘기는 경계에서는 `:: any` 캐스트로 끊는다. 반환 주석이 타입을 정하면 잃는 검사가 없다.

## §7 언제 풀리는가
status: described · 원천: quad typing-limits §1 "언제 풀리는가", §9

- §1 과 §2 의 모양은 RFC `relax-recursive-type-restriction`(https://rfcs.luau.org/relax-recursive-type-restriction.html) 이 다루는 바로 그 예(`Promise<T>.andThen: <U>(...) -> Promise<U>`)다. 추적 이슈는 `luau-lang/luau#2380` 이다. 완화는 내부 변경(별칭을 지연 확장)이라 사용자 문법 변경이 없다. 지금 선언을 그대로 두면 고쳐지는 순간 코드 변경 없이 풀린다. 그래서 미리 우회 장치를 심어 두지 않는 것이 원천들의 결론이다.
- 버전을 올리면 `snippets/recursion-*.luau` 의 `bug-present` 줄이 실패하는지부터 본다. 실패하면 이 절과 §1 처방을 다시 쓴다.
