---
name: luau-types
description: >-
  How the Luau type system behaves and breaks: generic inference and f<<T>>, narrowing, recursive aliases, "Code is
  too complex to typecheck", type functions, false positives, old vs new solver. Use when a .luau type error is
  confusing or correct code is rejected. Tools are luau-verify; Roblox API types are luau-roblox. 트리거: 타입 에러 이해 안 됨,
  제네릭 추론.
---
# luau-types

모든 주장은 `references/*.md` 의 절에 있다. 절마다 `status: verified`(스니펫이 luau 0.734/0.742 에서 재현됨) 또는 `described`(원천 서술만 있음)가 붙어 있다. 스니펫은 플러그인 루트의 `snippets/` 에 있고, 결과표는 `snippets/RESULTS.md` 다.

## 먼저 지킬 원칙
1. **진단 0건을 믿지 않는다.** 타입이 `unknown`/에러 타입으로 새면 검사가 조용히 통과한다. 일부러 틀린 줄(음성 대조군)이 잡히는지 확인한다. 방법은 luau-verify 스킬에 있다.
2. **추론만으로 된다/안 된다를 결론짓지 않는다.** 15줄짜리 재현을 `luau-analyze` 로 돌린다. 원천 기록의 여러 항목이 다시 재 보니 뒤집혔다(예: 싱글턴 보존, type function 안의 pcall·`error()`·바깥 별칭).
3. **한계를 우회하려고 API 나 타입을 비틀지 않는다.** 반환을 `any` 로 여는 회피는 금지다. 한계를 문서화하고, 사용 관례를 적고, 되돌릴 링크(이슈·RFC)를 남긴다.
4. 파일마다 `--!strict` 를 단다. `.luaurc` 한 단어에 기대지 않는다.
5. 버전을 적는다. 결함의 절반은 luau 버전에 따라 산다.

## 결정 트리
- **에러가 나야 하는데 안 난다**
  1. 결과가 `unknown` 으로 새는가(인자 없는 생성자, 테이블 리터럴, 반환에만 나오는 T)? → `generics.md` §2–3
  2. 콜백·람다가 끼어 있는가? → `generics.md` §4–5
  3. 값이 유니온·옵셔널 자리에 들어가는가? → `unions-singletons.md` §4–5
  4. 표식·`read` 필드·제네릭 컨테이너가 끼어 있는가? → `variance.md` §3–5
  5. 메소드가 `Foo<U>` 를 돌려주거나 별칭 선언 순서가 걸리는가? → `recursion-and-limits.md` §1, §3
  6. 가변 인자·여러 값 반환·넘친 인자·`pcall` 이 끼어 있는가? → `packs-and-varargs.md` §6, §9–10
  7. 그래도 모르겠으면 결함 카탈로그에서 증상을 찾는다 → `solver-limits.md` §2
- **맞는 코드가 거부된다**
  - "No valid instantiation" → `variance.md` §7, `generics.md` §7
  - 같은 모양 타입끼리 대입 실패, 주석 단 생성자 거부 → `solver-limits.md` §4
  - "Consider placing the following annotations" → `generics.md` §4
  - "Code is too complex to typecheck" → `recursion-and-limits.md` §5–6
  - 원인 줄이 아닌 곳에 에러, pcall·분기 대입·루프 안에서만 거부 → `solver-limits.md` §4-1
- **설계 중이다**: 입력 자리는 표식, 출력 자리는 전체형 → `variance.md` §8
- **type function 을 쓸지 정한다** (정책: 사안별, D-04)
  1. type function 없이 표현되는가? 대안부터 잰다 → `type-functions.md` §2(strip-nil, 키별 사상, 덮어쓰는 병합, 리터럴 계산 등)
  2. 부작용이 큰가(공개 표면, 큰 인자, 제네릭 재조립, 150 키 넘는 맵, 지원해야 하는 luau-lsp 버전)? → `type-functions.md` §1, 행별 근거는 `type-functions-limits.md`
  3. 크면 스파이크와 사용자 승인을 받는다. 쓰기로 했으면 §3 체크리스트(위치, 가드, 테스트, 음성 대조군, 버전 열)를 지킨다
- **luau 를 올렸더니 진단이 바뀌었다** → `solver-limits.md` §3, 그리고 `snippets/` 를 새 버전으로 돌린다

## 증상 → 파일 라우팅
| 증상 / 질문 | 읽을 곳 |
|---|---|
| 주석을 달았는데 제네릭 호출이 `Box<unknown, unknown>` 불일치 | `references/generics.md` §1 |
| `{ a = 1 }` 을 넘긴 뒤 아무 키·값이나 들어간다 | `references/generics.md` §2–3 |
| `f<<T>>` 를 언제 쓰나, 일부만 주면 내부 에러 | `references/generics.md` §3, §10 |
| `...T` 와 `T...`, `select`, `table.pack`/`unpack`, 팩 명시 인자 `<<(T)>>` | `references/packs-and-varargs.md` §1–5 |
| 받은 `...` 를 저장했다 넘기기(defer, 시그널 큐) | `references/packs-and-varargs.md` §6 |
| 인자를 너무 많이 넘겼는데 에러가 없다 | `references/packs-and-varargs.md` §10 |
| 튜플 별칭, 반환 팩 유니온 `(boolean, T...) \| (false, E)` | `references/packs-and-varargs.md` §7–8 |
| `M(5)`(`__call`)·`pcall(f, …)` 경유에서 타입 인자 소실·거부 | `references/generics.md` §9 |
| `never` 반환 뒤, `table.freeze` 필드, 콜백 반환 개수, 타입 가드 | `references/generics.md` §10 |
| 콜백 파라미터 주석이 무시된다(다른 타입이 통과) | `references/generics.md` §5 |
| 분기마다 다른 return 에서 "Expected 'nil', but got 'number'" | `references/generics.md` §4 |
| 제네릭 함수 몸통에서 `return v` 가 아무 타입이나 통과, 탐침 타입 | `references/generics.md` §6, §6-1 |
| `X<number>` 를 `X<number \| string>` 에 못 넣는다 / 넣으면 안 되는데 들어간다 | `references/variance.md` §1–2 |
| 빈 테이블이 표식 타입을 통과한다 | `references/variance.md` §3 |
| 제네릭 `put(m, k, v)` 에 틀린 값이 통과한다 | `references/variance.md` §4 |
| 파라미터 수가 다른 콜백 | `references/variance.md` §6 |
| `T1<number?>` 에서 "No valid instantiation" (`V` 와 `V?` 필드) | `references/variance.md` §9 |
| 문자열 리터럴이 `string` 으로 넓어진다 / `keyof`·`index` 로 이름 인자 타이핑 | `references/unions-singletons.md` §1–2 |
| `if o.tag then` 안에서 안 좁혀진다 | `references/unions-singletons.md` §3 |
| `~= nil`, `type(x) == "function"` 뒤 호출 거부 | `references/unions-singletons.md` §6 |
| 함수이면서 필드가 있는 값(콜러블 테이블), 함수 자리에 넘기기 | `references/unions-singletons.md` §7 |
| 분기 대입 뒤 "Cannot call a value of the union type", 루프 안 "could be nil" | `references/unions-singletons.md` §6 |
| 유니온 파라미터에서 제네릭이 `unknown`, `[string]: any` 교집합 | `references/unions-singletons.md` §9–10 |
| 교집합·유니온 컨테이너 `for … in` 의 루프 변수 타입 | `references/unions-singletons.md` §11 |
| `Foo<T>` 메소드가 `Foo<U>` 를 돌려줄 때 결과 검사 소실 | `references/recursion-and-limits.md` §1 |
| 별칭 순서를 바꾸니 진단이 생기거나 사라진다 | `references/recursion-and-limits.md` §3 |
| "Recursive type being used with different parameters" | `references/recursion-and-limits.md` §2, §4 |
| too complex, `LuauTarjanChildLimit` 등 한도 플래그 | `references/recursion-and-limits.md` §5–6 |
| type function 을 써도 되나, 대안이 있나, 원천 서술 정정 | `references/type-functions.md` §1–§2, §5 |
| type function 의 제약·부작용(`print`/`error`/`pcall`, 프라이밍, too complex, 직렬화 실패, hover) | `references/type-functions-limits.md` |
| 새 솔버 vs 옛 솔버, 0.734 vs 0.742, luau-lsp 와 판정 차이 | `references/solver-limits.md` §1–3 |
| 캐스트가 왜 통과하나, `self: any` 제네릭 메서드 결과 무검사 | `references/solver-limits.md` §4 |
| `for i in ipairs(t)` 에 "expects 2 arguments, but 2 are specified" (위양성) | `references/solver-limits.md` §4-1 |
| `luau-analyze --fflags`(불리언만), Studio 의 무표시 too complex | `references/recursion-and-limits.md` §5 |
| 업스트림에 보고할 만한 결함인가 | `references/solver-limits.md` §6 |
| `.luaurc`, `--!strict`, luau-analyze/luau-lsp 호출법, 음성 대조군 | luau-verify 스킬 |

## 답할 때
- 절의 `status` 를 함께 말한다. `described` 인 주장은 "원천 서술, 미재현"이라고 밝힌다.
- 버전에 의존하는 주장은 버전을 붙인다(예: "luau 의 어느 버전에서 고쳐짐, luau-lsp 는 아직"; 현재 확인된 버전은 각 reference 의 `last_confirmed` 와 `solver-limits.md` §1–3).
- 정책이 갈린 항목은 한쪽을 고르지 말고 양쪽 입장과 `decisions/` 를 안내한다. type function 은 D-04 로 확정됐다(사안별 판단, `type-functions.md` §0).
- 새 사실을 발견하면 `snippets/` 에 최소 재현과 표식(`-- expect-error`, `-- bug-present`)을 먼저 추가한다.
