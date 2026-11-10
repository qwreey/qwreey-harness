# solver-limits — 새 솔버와 옛 솔버, 결함 카탈로그(버전별)

## 이 파일이 답하는 질문
- Q1 지금 쓰는 검사기는 새 솔버인가 옛 솔버인가? 어떻게 바꾸는가?
- Q2 "에러가 나야 하는데 안 난다"는 알려진 결함 목록과, 어느 버전에서 사는지
- Q3 luau 를 0.734 에서 0.742 로 올리면 무엇이 바뀌는가?
- Q4 같은 모양의 제네릭 함수 타입끼리 대입이 안 된다.
- Q5 선언된 테이블의 제네릭 메소드 결과가 검사되지 않는다.

## 목차
- §1 솔버 고르기와 확인법
- §2 결함 카탈로그 (한 표)
- §3 0.734 → 0.742 에서 바뀐 것
- §4 위양성(맞는 코드가 거부됨) 쪽 결함
- §5 서술만 있는 결함과 역사
- §6 결함을 만났을 때

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
| S14 | 가변 인자 자리의 꼬리 호출 결과 무검사 | `solver-vararg-tail-call` | bug | **fixed** | fixed | 잡음 | generics.md §8 |
| S15 | 함수 ∩ 테이블 값이 never 로 아무 데나 대입 | `unions-function-table-intersection` | bug | bug | bug | 호출 거부 | unions-singletons.md §7 |
| S16 | `setmetatable` 형 `__call` 인자 무검사 | 같은 파일 | bug | **fixed** | fixed | (문법 모름) | unions-singletons.md §7 |
| S17 | 선언된 테이블의 제네릭 함수 필드 결과 무검사 | `solver-declared-generic-field` | bug | bug | bug | 잡음 | §4 아래 |
| S18 | 줄어들지 않은 `index<…, M>` 결과가 아무 데나 대입 | `typefn-unreduced-index` | bug | bug | bug | (문법 모름) | type-functions.md §5 |
| S19 | nonstrict `.luaurc` 아래 명백한 에러 0건 | `modes-luaurc-nonstrict-silences` | 동작 | 동작 | — | — | luau-verify 스킬 |

## §3 0.734 → 0.742 에서 바뀐 것
status: verified · 근거: 위 표의 S2, S13, S14, S16, `snippets/RESULTS.md`

- 고쳐진 것 넷: S2(맨 람다 누수), S13(교집합 → 유니온), S14(꼬리 호출), S16(`__call` 인자).
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
