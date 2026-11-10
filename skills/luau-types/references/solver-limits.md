# solver-limits — 새 솔버와 옛 솔버, 결함 카탈로그(버전별)

## 이 파일이 답하는 질문
- Q1 지금 쓰는 검사기는 새 솔버인가 옛 솔버인가? 어떻게 바꾸는가?
- Q2 "에러가 나야 하는데 안 난다"는 알려진 결함 목록과, 어느 버전에서 사는지
- Q3 luau 를 0.734 에서 0.742 로 올리면 무엇이 바뀌는가?
- Q4 같은 모양의 제네릭 함수 타입끼리 대입이 안 된다.
- Q5 선언된 테이블의 제네릭 메소드 결과가 검사되지 않는다.
- Q6 원인 줄이 아닌 곳에 에러가 난다 / 맞는 코드가 pcall·분기 대입·루프에서 거부된다.
- Q7 원천 기록 중 재현해 보니 틀렸거나 조건이 달랐던 것은?

## 목차
- §1 솔버 고르기와 확인법
- §2 결함 카탈로그 (한 표)
- §3 0.734 → 0.742 에서 바뀐 것
- §4 위양성(맞는 코드가 거부됨) 쪽 결함
- §5 서술만 있는 결함과 역사
- §6 결함을 만났을 때
- §7 정정 (원천 저장소에 전달)

---

## §1 솔버 고르기와 확인법
status: verified · last-confirmed: luau 0.742 (`--help` 와 스니펫) · 근거: `snippets/recursion-old-solver-rejects.luau`, `snippets/variance-read-field.luau`

- `luau-analyze` 는 **새 솔버가 기본값**이다(`--solver={new|old}`, default new). `--solver=old` 로 옛 솔버를 고른다.
- 옛 솔버는 `read`/`write` 필드("read keyword is illegal here"), `keyof`/`index`, `setmetatable<>` 타입, `type function` 을 모른다. 이런 문법을 쓰는 코드는 새 솔버가 전제다. 옛 솔버는 **비교용**으로만 쓴다: 같은 파일에서 옛 솔버만 잡으면 새 솔버 결함 후보다.
- `luau-lsp` 의 에디터 기본값은 과거에 옛 솔버였다(`luau-lsp.fflags.enableNewSolver` 로 켬, quad 기록, described). `luau-lsp analyze` CLI 는 옵션 없이 모든 FFlag 를 켜고 돈다. 재현할 때는 `--flag:LuauSolverV2=true` 를 명시한다.
- "구 솔버 / 신 솔버"라고 적힌 옛 기록이 실제로는 "luau CLI 빌드 / luau-lsp 내장 빌드"(둘 다 새 솔버)를 뜻한 경우가 있었다(quad 머리 정정). 기록을 읽을 때 도구와 버전을 확인한다.

## §2 결함 카탈로그 (한 표)

"0.734 / 0.742" 열은 이 저장소 스니펫의 결과다(`bug` = 진단이 안 나는 한계가 있음, `fixed` = 잡힘). lsp 열은 `luau-lsp 1.70.1 analyze --flag:LuauSolverV2=true` 결과를 참고로 적었다. 옛 솔버 열은 원천 기록과 이번 프로브 결과다.

| ID | 증상 (에러가 안 남) | 스니펫 | 0.734 | 0.742 | lsp 1.70.1 | 옛 솔버 | 설명 위치 |
|---|---|---|---|---|---|---|---|
| S1 | 뒤쪽 파라미터를 생략한 람다의 주석 상한 소실 | `generics-callback-bound-lost` | bug | bug | bug | 잡음 | generics.md §5 |
| S2 | 파라미터를 제약하지 않는 맨 람다의 결과 누수 | `generics-bare-lambda-free-type` | bug | **fixed** | **bug** | 잡음 | generics.md §4 |
| S3 | 제네릭 몸통에서 타입 변수 값 무검사 | `generics-body-unchecked` | bug | bug | bug | 잡음 | generics.md §6 |
| S4 | 문자열 키 리터럴 → 인덱서 파라미터 값 무검사 | `generics-string-key-literal-indexer` | bug | bug | bug | 잡음 | generics.md §6 |
| S5 | 재귀 타입이 유니온/옵셔널 갈래일 때 타입 인자 무검사 | `unions-recursive-in-optional` | bug | bug | bug | 잡음 | unions-singletons.md §4 |
| S6 | `{}` 리터럴 → `{ [K]: V }` 가 unknown, 이후 쓰기 무검사 | `generics-literal-to-indexer-unknown` | bug | bug | bug | 일부 잡음 | generics.md §2 |
| S7 | 비균일 재귀 메소드 반환 누수 | `recursion-nonuniform-return` | bug | bug | bug | 선언 거부 | recursion-and-limits.md §1 |
| S8 | 비균일 재귀보다 앞 선언 별칭의 참조가 에러 타입 | `recursion-declaration-order` | bug | bug | bug | 없음(재정렬) | recursion-and-limits.md §3 |
| S9 | 자기 참조 함수 필드 + 같은 이름 멤버의 유니온 통과 | `unions-same-name-method-hole` | bug | bug | bug | (read 거부) | unions-singletons.md §5 |
| S10 | 제네릭 메소드의 파라미터 반공변 무검사 | `variance-generic-method-contravariance` | bug | bug | bug | (read 거부) | variance.md §5 |
| S11 | 값 팬텀 `read p: T?` 에 빈 테이블 통과 | `variance-value-phantom-nil` | bug | bug | bug | (read 거부) | variance.md §3 |
| S12 | 공변 자리에서 제네릭 V 가 넓어짐 | `variance-covariant-generic-widening` | bug | bug | bug | (read 거부) | variance.md §4 |
| S13 | 공변 인자 둘 → 교집합 `number & string` | `generics-covariant-args-intersection` | bug | **fixed**(유니온) | fixed | (read 거부) | generics.md §7 |
| S14 | 가변 인자 자리의 꼬리 호출 결과 무검사 | `solver-vararg-tail-call` | bug | **fixed** | fixed | 잡음 | packs-and-varargs.md §11 |
| S15 | 함수 ∩ 테이블 값이 never 로 아무 데나 대입 | `unions-function-table-intersection` | bug | bug | bug | 호출 거부 | unions-singletons.md §7 |
| S16 | `setmetatable` 형 `__call` 인자 무검사 | 같은 파일 | bug | **fixed** | fixed | (문법 모름) | unions-singletons.md §7 |
| S17 | 선언된 테이블의 제네릭 함수 필드 결과 무검사(조건: `self: any`. `self` 를 그 타입으로 적으면 잡힘, 교집합 여부 무관) | `solver-declared-generic-field`, `solver-generic-method-self-type` | bug | bug | bug | 잡음 | §4 아래 |
| S18 | 줄어들지 않은 `index<…, M>` 결과가 아무 데나 대입 | `tf-builtin-unreduced-index` | bug | bug | bug | (문법 모름) | type-functions-limits.md B3 |
| S19 | nonstrict `.luaurc` 아래 명백한 에러 0건 | `modes-luaurc-nonstrict-silences` | 동작 | 동작 | — | — | luau-verify 스킬 |
| S20 | `local function`·`function M.f`·메서드·리터럴 필드에 **넘친 인자** 무진단(주석 타입을 거친 값은 잡힘) | `pack-extra-args`, `pack-extra-args-exposure` | bug | bug | bug | 잡음 | packs-and-varargs.md §10 |
| S21 | 제네릭 팩 `...: A...` 를 `{ ... }` 에 담으면 `{nil}`, `table.pack` 은 거부(defer 패턴) | `pack-store-generic-pack` | 동작 | 동작 | 동작 | 우회도 거부 | packs-and-varargs.md §6 |
| S22 | 제네릭 몸통: 기대 타입이 정확히 `T` 가 아닌 자리(`T?` 반환, 지역 초기화, `T` 값을 구체 자리에) 무검사 | `generics-body-probe-type` | bug(`return 5`→T 도) | bug(`→T` 만 잡음) | 0.742 와 같음 | 잡음 | generics.md §6-1 |
| S23 | 인덱서 없는 갈래가 든 유니온의 `for … in` 무검사 | `solver-union-iter-no-indexer` | bug | bug | bug | — | unions-singletons.md §11 |
| S24 | 교집합 컨테이너를 인덱서로 돌 때 루프 변수 타입 소실 | `unions-intersection-iter-method` | bug | bug | bug | — | unions-singletons.md §11 |
| S25 | `[string]: any` 인덱서와의 교집합이 이름 있는 필드까지 any 로 | `unions-catchall-indexer-intersection` | bug | bug | bug | 노이즈 다량(원천) | unions-singletons.md §10 |
| S26 | 자기 참조 함수 필드 타입 A → 다른 자기 참조 타입의 `B?` 통과 | `unions-self-ref-optional-hole` | bug | bug | bug | — | unions-singletons.md §4 |
| S27 | `__call` 콜러블 네임스페이스로 부른 제네릭 생성자 결과 무검사 | `generics-callable-namespace` | bug | bug | bug | — | generics.md §9 |
| S28 | 함수 타입끼리·테이블 타입끼리 캐스트는 모양이 달라도 통과(겹침만 봄) | `solver-cast-overlap-only` | 동작 | 동작 | 동작 | — | §4 아래 |

## §3 0.734 → 0.742 에서 바뀐 것
status: verified · 근거: 위 표의 S2, S13, S14, S16, S22, `snippets/RESULTS.md`

- 고쳐진 것 넷: S2(맨 람다 누수), S13(교집합 → 유니온), S14(꼬리 호출), S16(`__call` 인자).
- 일부 고쳐진 것 하나: S22. 0.739 의 땜질 플래그 `LuauSoundGenericMismatches` 로, 제네릭 몸통에서 기대 타입이 **정확히** `T` 인 자리(`return 5` 를 반환 타입 `T` 에)만 0.742 에서 잡힌다(`generics-body-probe-type` 9행). luau-lsp 1.70.1 도 잡는다.
- **luau-lsp 1.70.1 은 S2 가 아직 bug 다**(나머지 셋은 고쳐짐). 같은 파일이라도 CI(`luau-analyze` 0.742)와 에디터(`luau-lsp` 1.70.1)의 판정이 다를 수 있다. luau-lsp 는 자기가 내장한 Luau 판으로 검사하기 때문이다.
- 이 넷 모두 **에러가 새로 생기는** 방향이다. 0.734 에서 통과하던 코드가 0.742 에서 실패할 수 있다. 원천 저장소 하나는 0.742 로 올리며 새 진단 12건과 음성 대조군 배터리의 변화를 기록했다(stl mise.toml 머리 주석, described).
- 원천 저장소 하나가 0.742 로 올린 직접적인 이유: 0.734 의 `luau-analyze` 가 병렬 검사에서 힙을 깨뜨렸다(상류 #3020, described).
- 같은 0.742 에서 `#` 가 가운데 구멍이 있는 배열에 다른 경계를 돌려줬다(런타임 동작, stl 기록, described). 구멍 있는 배열의 `#` 에 의존하지 않는다.

## §4 위양성(맞는 코드가 거부됨) 쪽 결함
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/solver-generic-intersection-return.luau`, `snippets/solver-declared-generic-field.luau`, `snippets/generics-annotation-does-not-flow.luau`, `snippets/variance-intersection-instantiation.luau`

- **교집합 + 반환 속 제네릭**: `<S>(S & S) -> S` 를 글자 그대로 같은 타입에 대입해도 거부된다. `S` 가 반환에 없거나 교집합이 없으면 통과한다(stl luau-solver-issues/8). 같은 뿌리로 보이는 실무 증상: 서로 다른 패키지 사본에서 온 "같은" 큰 타입끼리 대입이 실패한다(quad 8.43, described). 라이브러리 경계는 `read` 필드 하나짜리 표식으로 받고, 런타임 브랜드를 확인한 뒤 캐스트한다.
- **교집합 안 불변/반공변 T** 추론 실패: variance.md §7.
- **주석이 제네릭 호출로 흐르지 않음**(`local m: Box<string, number> = New()` 거부): generics.md §1.
- (반대 방향, 에러가 안 나는 쪽) **선언된 테이블 타입의 제네릭 함수 필드**(`Apply: <U>(self: any, factory: (any) -> U) -> U`)는 결과를 아무 타입에나 담아도 0건이다. 자유 함수나 **추론된** 테이블의 같은 함수는 잡힌다(quad 8.29). 결과 검사가 필요한 API 는 자유 함수로 노출하거나 결과에 주석을 요구한다.
  - 조건은 `self: any` 다(verified · `snippets/solver-generic-method-self-type.luau` · 후보 Q-126). `GetOrCreate: <T>(self: A, …) -> T` 처럼 `self` 를 그 타입으로 적으면 결과가 검사된다. 단독 값이든 교집합(`A & B`) 값이든 같다. 비제네릭 메서드는 `self: any` 여도 검사된다. 원천의 "교집합 타입 값의 메서드 호출이 any 를 돌려준다"(quad kit-packaging-plan.md:73)는 이 결함이 교집합 값에서 보인 것이다. 그런데 variance.md §9 의 추론 실패를 피하려면 메서드 칸에 `self: any` 를 써야 하므로, 두 결함 사이에서 고른다: 제네릭 메서드는 반환 주석을 받는 자리에서 부르거나 자유 함수로 노출한다.
- (에러가 안 나는 쪽) **캐스트는 검사가 아니다**(verified · `snippets/solver-cast-overlap-only.luau` · 원천 stl-luau-doctor/.claude/research/luau-source/README.md:125, 후보 S-140). `x :: T` 는 두 타입이 겹칠 수 있는지만 본다. `f :: (string) -> boolean`(`f: (number) -> number`), `({ a = 1 } :: { a: number }) :: { b: string }` 이 통과하고, 서로소인 원시 타입(`number` → `string`)만 "unrelated" 로 거부된다.

### §4-1 위양성 추가분 (2026-11-10)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: 아래 스니펫

| 증상 (맞는 코드가 거부됨) | 스니펫 | 우회 | 설명 위치 |
|---|---|---|---|
| 제네릭 함수를 담은 테이블 리터럴을 인자 자리에 두면 거부되고, 그 실패가 Subtyping 캐시에 남아 **같은 모듈 뒷줄의 멀쩡한 비교**(`takeFn(id)`)까지 실패한다. 순서를 바꾸면 뒷줄은 통과 | `solver-table-literal-cache-poison`, 대조 `solver-table-literal-read-field-ok` | 받는 필드를 `read` 로, 또는 리터럴을 주석 단 지역에 먼저 담기. 원인 줄이 아닌 곳의 에러는 이것을 의심 | 원천 stl DRAFTS.md:194-202, 후보 S-139 |
| 반환이 `()` 인 제네릭을 `pcall(f, …)` 에 바로 | `generics-pcall-unit-return` | 람다로 감싼다 | generics.md §9 |
| `pcall(string.find, s, p)` (선택 인자 있는 내장) | `solver-pcall-builtin-overload` | 람다로 감싼다 | packs-and-varargs.md §9 |
| `{ x: V, y: V? }` 에 `T1<number?>` | `variance-optional-generic-field` | `read y: V?` | variance.md §9 |
| 주석 단 지역에 분기마다 다른 갈래 대입 → 제네릭 메서드 호출 "Cannot call a value of the union type" | `unions-annotated-local-branch-narrowing` | if-식을 주석 단 지역에 | unions-singletons.md §6 |
| 클로저 안 루프에서 업밸류 좁히기 무효("could be nil") | `unions-closure-loop-narrowing` | 루프 전에 지역으로 받기 | unions-singletons.md §6 |
| 유니온 파라미터에 넓혀야 하는 테이블 리터럴 | `unions-generic-union-param` | 주석 단 지역에 담아 넘기기 | unions-singletons.md §9 |
| 명시 타입 인자를 일부만(`two<<number>>`) → 솔버 내부 에러 | `solver-explicit-args-freeze-never` | 전부 주거나 하나도 안 주기 | generics.md §10 |
| 루프 변수 하나만 쓰는 `for i in ipairs(t)` → "Argument count mismatch. Function expects 2 arguments, but 2 are specified". 두 변수·`pairs`·`next`·`for i in t` 는 통과, 옛 솔버 0건. luau 0.734·0.742·0.746, luau-lsp 1.69.0·1.70.1 모두 같음. 업스트림 동일 이슈 못 찾음(2026-11-10) | `solver-ipairs-single-var` | `for i, _ in ipairs(t)` 나 숫자 for | luau-upstream `watchlist.md` §3 |
| (Roblox 정의 파일) `DateTime:ToLocalTime()` 이 `{ any }` 라 `.Year` 거부 | `solver-roblox-datetime-tolocaltime`(`--@lsp-roblox`) | 결과를 레코드 타입으로 캐스트 | 원천 devplorer feedback :502, 후보 D-F33 |

## §5 서술만 있는 결함과 역사
status: described

| 항목 | 원천 | 상태 |
|---|---|---|
| 제네릭 팔이 든 오버로드 교집합에서 제네릭 팔이 선택되지 않음("None of the overloads … compatible") | quad 8.19 (luau-lsp 1.69.0, 메소드 제네릭 `<Item, UD>` + self) | 이번 최소 꼴(인자 둘)에서는 선택됨 — 조건 미확정 |
| 다른 호출의 인자인 테이블 리터럴 안에서 람다 파라미터가 추론되지 않음 | quad 8.13, 8.30 (luau-lsp 1.69.0) | quad 가 1.70.1 에서 사라졌다고 기록. 인라인 람다의 **반환**이 프로퍼티와 대조되지 않는 구멍은 남음 |
| 재대입되는 옵셔널 함수 업밸류를 `~= nil` 로 좁혀 호출하면 "Cannot call … & ~nil in union" | quad 8.38 2번 (luau-lsp 1.70.1) | 최소 꼴에서 재현 안 됨. 처방: 옵셔널 대신 아무 일도 안 하는 기본 함수 |
| 제네릭 함수 안 인라인 람다의 `return true` 가 바깥 `T` 와 대조됨 | quad 8.38 3번 | 최소 꼴에서 재현 안 됨. 처방: 람다를 제네릭 밖 지역 함수로 |
| `table.clone(f())` 꼴이 nonstrict 에서도 "Argument count mismatch" | quad 8.33 | 지역 변수로 받아 우회 |
| `any`/`{ [any]: any }` 를 교집합(`Self & P`)에 넣으면 이후 멤버 접근 전부 `*error-type* in union` | quad 8.35 | 제공자 반환 타입을 구체적으로 |
| 제네릭으로 받은 인스턴스의 배열 반환 메소드 결과가 `unknown` | quad 8.20 (Roblox defs) | 지역 주석 `{ Instance }` |
| `luau-lsp` 가 `luau-analyze` 보다 진단을 덜 냄(72 대 68, too complex 에서 검사 포기) | stl typing-limits "체커" 절 (큰 파일 1건) | 스니펫 35개에선 두 도구가 같음 — 큰 파일·한도 문제로 한정해 읽을 것 |

## §6 결함을 만났을 때
status: described · 원천: stl luau-solver-issues/DRAFTS.md "올리기 전 체크리스트", quad §0

1. 라이브러리 없이 15줄 안팎의 최소 재현을 만든다. **같은 파일에 대조군 줄**(같은 실수의 다른 모양이 잡히는 줄)을 둔다. 검사기가 통째로 꺼진 것이 아님을 보이기 위해서다.
2. `--solver=old` 와 두 luau 버전으로 대조한다. 이 저장소에서는 `snippets/` 에 표식(`-- bug-present`)을 붙여 넣고 `tools/check_snippets.py --luau 0.734,0.742` 로 돌린다.
3. 우회하려고 공개 API 나 타입 모양을 비틀지 않는다. 한계를 문서화하고, 사용 관례를 적고, 되돌릴 지점(이슈·RFC 링크)을 남긴다. 반환을 `any` 로 여는 회피는 금지다(quad·stl 공통 원칙). 단, 우회가 비튼 것이 아니라 그냥 더 나은 설계라면 채택한다.
4. 업스트림 보고는 사용자가 결정한다(두 원천 모두 초안만 두고 게시하지 않았다). 중복 검색어와 인접 이슈(#2168, #2380, #2733)는 원천 DRAFTS.md 에 있다.

## §7 정정 (원천 저장소에 전달)
status: verified (각 줄의 스니펫·실측)

| 원천 | 원천 서술 | 실측 (luau 0.734·0.742) |
|---|---|---|
| `quad/.claude/research/kit-packaging-plan.md:73` | 교집합 타입 값의 메서드 호출이 any 를 돌려준다 | 교집합 탓이 아니다. 제네릭 메서드의 `self: any` 가 조건이다(S17). `self` 를 그 타입으로 적은 메서드는 교집합에서도 검사된다(`solver-generic-method-self-type`) |
| `quad/.claude/research/kit-packaging-plan.md:91` | 서로 다른 선언의 제네릭 함수는 글자가 같아도 같지 않다 | 최소 꼴 `local g2: <U>(U) -> U = g1`(`g1: <T>(T) -> T`)은 통과한다. 원천의 실패는 `self` 재귀가 든 큰 타입 사본 둘 사이에서 났다 — 조건 미확정(described). 교집합·반환에 같은 제네릭이 든 꼴은 §4 첫 항목 |
| `stl-luau-doctor/.claude/conventions.md:40` | 콜러블 네임스페이스는 모듈 필드 오타도 못 잡는다 | `setmetatable(M, { __call = … })` 꼴에서 `M.Neww` 는 잡힌다. 타입 인자 소실만 재현(`generics-callable-namespace`) |
| `stl-luau-doctor/.claude/base/typing-limits.md:371-386` | 유니온 자리 제네릭은 같은 별칭일 때만 풀린다 | 조건이 더 넓다(unions-singletons.md §12) |
| `devplorer/.claude/feedback/quad-upstream-2026-10-20.md:494` | 필드를 좁힌 뒤 다른 호출이 끼면 "could be nil" | 재현 안 됨(unions-singletons.md §12) |
| 이 저장소 `recursion-and-limits.md` §5 옛 판 | `luau-analyze` 에는 플래그 옵션이 없다 | `--fflags=Name=true\|false` 가 동작한다(불리언만, `--help` 에는 없음). recursion-and-limits.md §5 에서 고쳤다 |

