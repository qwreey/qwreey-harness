---
title: "type function 의 제약과 부작용 목록"
description: "type function 의 제약·부작용 목록(버전 열 포함): 바깥 지역 참조 금지와 pcall 지원, print·error 진단 모양, 무한 루프·too complex·keyof 150 키 한도, 인자 직렬화 실패, 제네릭 재조립, export 프라이밍, hover·자동완성 DX"
keywords:
  - "type function 한계"
  - "type function 제약"
  - "type function 부작용"
  - "type function limits"
  - "type function pcall"
  - "type function 무한 루프"
  - "type function hover"
  - "인자 직렬화 실패"
  - "keyof 150 키"
  - "프라이밍"
  - "LuauDoNotExportBrokenTypeFunction"
  - "export type function"
  - "setreadindexer"
  - "Type function cannot reference outer local"
  - "Type functions do not currently support types of the form"
  - "Complexity limit reached when passing a type to a type function"
  - "returned a non-type value"
  - "errored at runtime"
  - "not supported in type functions"
kind: reference
category: luau/types/type-functions
tags: [new-solver, bug, silent, measured, studio]
last_verified: 2026-11-10
---
# type-functions-limits — type function 의 제약과 부작용 목록

## 이 파일이 답하는 질문
- Q1 type function 을 쓰면 무엇이 깨지거나 느려지는가? 버전마다 다른가?
- Q2 type function 안에서 무엇을 부를 수 있고 무엇을 못 부르는가?
- Q3 진단 메시지는 어떻게 보이는가(`print`, `error()`)?
- Q4 다른 모듈에서 쓰면 무엇이 달라지는가(export, 프라이밍)?
- Q5 hover·자동완성·메시지(DX)는 어떻게 바뀌는가?

판단 절차, '타입 함수 없이는 불가능한 패턴', 정정 목록은 `type-functions.md` 에 있다.

## 목차
- §0 읽는 법
- §1 실행 환경 (E)
- §2 진단 품질 (D)
- §3 성능·한도 (L)
- §4 인자 직렬화 (S)
- §5 제네릭 (G)
- §6 패스스루 뒤 self 체이닝 (C)
- §7 재조립한 결과의 모양 (R)
- §8 내장 `keyof`/`index` (B)
- §9 모듈·export 경계 (X)
- §10 DX: hover, 자동완성, 메시지 (DX)
- §11 extern(Roblox 클래스) API 메모 (A)

---

## §0 읽는 법
status: verified (하네스 규칙) · 근거: `snippets/RESULTS.md`, `tools/check_snippets.py`

- **버전 칸**의 넷은 luau-analyze 0.734, luau-analyze 0.742, luau-lsp 1.69.0 analyze, luau-lsp 1.70.1 analyze 이다. 모두 새 솔버, 기본 한도다.
  - `재현` 은 증상이 나타난다는 뜻이고, `없음` 은 나타나지 않는다는 뜻이다.
  - `—` 는 재지 않았다는 뜻이다.
  - luau-lsp 열은 `check_snippets.py --lsp` 와 `tools/lsp_probe.py` 로 쟀다.
- **근거**의 `tf-…` 는 `snippets/tf-….luau` 다. `tf-cross-module.sh` 는 파일 여럿이나 무한 루프가 필요해 셸로 잰 것이다(`bash snippets/tf-cross-module.sh`, rc=0).
- **status**
  - `verified` 는 스니펫이 0.734·0.742 에서 rc=0 으로 재현된다는 뜻이다.
  - `described` 는 원천 서술만 있다는 뜻이다. 실물 규모나 Roblox 정의 파일, Studio 가 필요한 것이 대부분이다.
- 원천 약어
  - QTL = `quad/.claude/base/typing-limits.md`
  - QR = `quad/.claude/audit/decl-typefn-probe-2026-10-16/REPORT.md`
  - STS = `stl-luau/.claude/base/trait-system.md`
  - STR = `stl-luau/src/Trait/init.luau`
  - TB = `tbox/packages/tbox`

## §1 실행 환경 (E)
summary: 몸통은 바깥 지역 변수를 못 쓰지만 바깥 별칭은 된다. pcall 은 luau-lsp 1.69.0 에만 없고, any/unknown 입력은 분해 전에 걸러야 한다

| ID | 증상 | 원인 | 버전 (0.734 / 0.742 / lsp 1.69.0 / lsp 1.70.1) | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| E1 | 몸통에서 같은 파일의 바깥 지역 변수(지역 함수, `require` 결과 포함)를 쓰면 그 줄이 `SyntaxError: Type function cannot reference outer local 'x'` | 파서가 막는다(`Parser.cpp`) | 재현 / 재현 / 재현 / 재현 | 공유 로직을 type function 안이나 형제 type function 으로 옮긴다. 런타임 유틸과는 중복한다 | `tf-env-outer-local`; stl `conventions.md:84` ①; quad `type-version-check/src/init.luau:45-50` | verified |
| E2 | (제약 아님) 바깥 **타입 별칭**은 참조할 수 있다. 제네릭 없는 별칭은 값처럼, 제네릭 별칭은 `Box(t)` 처럼 부르고, 형제 type function 도 부른다. `types.optional` 도 있다 | 실행 환경이 같은 스코프 별칭·함수를 넣어 준다(`UserDefinedTypeFunction.cpp` environmentAlias) | 동작 / 동작 / 동작 / 동작 | — | `tf-env-outer-alias-ok` | verified |
| E3 | 다른 모듈의 별칭 `M.Point` 를 몸통에서 바로 쓰면 E1 에러(`M` 이 바깥 지역) | E1 과 같음 | 재현 / 재현 / — / — | 파일 위에 `type Local = M.Point` 를 두고 `Local` 을 쓴다 | `tf-cross-module.sh` M5 | verified |
| E4 | `pcall` 이 없다("Unknown global 'pcall'", "this function is not supported in type functions") | luau-lsp 1.69.0 의 내장 Luau 판 | 없음 / 없음 / **재현** / 없음 | 0.734·0.742·1.70.1 은 pcall 이 되고 `types` API 에러도 잡는다(ok=false). 1.69.0 을 지원해야 하면 `t:is("table")` 같은 태그 검사를 먼저 한다 | `tf-env-pcall-available`(lsp 열); QTL 8.18 | verified |
| E5 | `getfenv`/`setfenv`/`gcinfo`/`newproxy` 를 쓰면 선언 줄에 "Unknown global", 사용 자리에 "not supported in type functions" | 실행 환경이 막는다. math/table/string/bit32/utf8/buffer/기본 라이브러리는 있다 | 재현 / 재현 / — / 같음 | 쓰지 않는다 | `tf-env-unsupported` | verified |
| E6 | type 이 아닌 값을 돌려주면 "returned a non-type value" | 반환 검사 | 재현 / 재현 / — / 같음 | 모든 경로에서 `types.*` 를 돌려준다 | `tf-env-unsupported` | verified |
| E7 | `unknown`/`any` 를 `properties()` 등으로 분해하면 "errored at runtime: … expected self to be either a table or class, but got unknown" | API 가 태그를 검사한다 | 재현 / 재현 / 재현 / 재현 | 앞에서 `t:is("any")`/`t:is("unknown")` 을 걸러 그대로 돌려준다(tbox BUG-05 가드) | `tf-env-pcall-available`; TB `src/types.luau:68,111` | verified |
| E8 | 지역 테이블에 주석이 없으면 몸통이 타입 에러 | 새 솔버는 type function 몸통도 검사한다 | 재현 / 재현 / — / — | `local comps: { type } = {}`. `types.newtable` 의 props 는 `{ [type]: { read: type?, write: type? } }` 모양 | `tf-noalt-stripnil`; QTL 8.14, 8.22 | verified |
| E9 | `types.newfunction` 에 배열을 넘기면 실패한다 | 인자가 `{ head = {…}, tail = … }` 레코드다(API 변경) | — | 레코드로 넘긴다. self 는 `types.newtable()` 핸들을 그대로 참조하면 나중에 채워도 반영된다 | quad `audit/type-recursive-issue-with-typeof/REPORT.md:40,201-206` | described |

## §2 진단 품질 (D)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| D1 | `print(...)` 를 한 줄이라도 하면, 결과 타입이 멀쩡해도 사용 자리에 TypeError 가 뜬다. 디버그 로그로 못 쓴다 | `print` 출력이 그 적용의 진단 메시지로 붙는다 | 재현 / 재현 / 재현 / 재현 | 디버그가 끝나면 지운다. 진단을 띄울 때만 쓴다 | `tf-diag-error-vs-print` | verified |
| D2 | `error("m")` 은 메시지가 **보인다**. 다만 `'F' type function errored at runtime: F:<줄>: m` 모양이고, "reduced type is `never`" 불일치가 하나 더 붙는다. 파라미터 주석에 쓰면 호출마다 두 건씩 반복된다 | 실패한 적용은 never 로 줄어든다 | 재현 / 재현 / 재현 / 재현. 청크 이름만 다르다(0.734·1.69.0 `[string "F"]:3:`, 0.742 `F:3:`) | 사용자에게 보일 메시지는 `print` + `types.never`(D3). 정의자 실수 보고에는 `error` 도 쓸 만하다 | `tf-diag-error-vs-print`; D-04 §2 | verified |
| D3 | `print` + `types.never` 는 메시지 한 줄과 "Expected this to be unreachable" 을 낸다. 같은 인스턴스(`Checked<string>`)를 여러 자리에서 쓰면 메시지는 **처음 평가한 자리에만** 뜨고, 나머지 자리에는 unreachable 만 남는다 | 적용 결과가 캐시된다 | 재현 / 재현 / 재현 / 재현 | 첫 자리만 보고 판단하지 않는다. 대조군은 인스턴스를 달리해 둔다 | `tf-diag-only-pattern`, `tf-diag-eval-sites` | verified |
| D4 | 진단이 안 뜨는 자리가 둘이다. ① `any` 를 대입한 주석(`local c: Checked<string> = nil :: any`) ② 제네릭 함수 몸통 안의 지역 별칭(`type _C = Check<T>`) | 대조가 없거나, 인스턴스화 때 다시 평가되지 않는다 | 재현 / 재현 / 재현 / 재현 | 검사는 반환 타입·필드 타입·캐스트처럼 호출부마다 대조되는 자리에 둔다. 제네릭 없는 별칭 선언은 쓰이지 않아도 평가된다 | `tf-diag-eval-sites`; QTL §6 ②; quad `base/quad-types-plan.md:253-278` | verified |
| D5 | 정의자 에러가 같은 줄에 두 번(뷰 둘) 뜬다. 메시지가 없으면 `type.readproperty: expected self …` 가 2–6번 반복된다 | 한 정의에서 적용이 여러 번 생긴다 | (stl 0.742) | 정의 쪽 검사는 한 적용에서만 하고, 나머지는 조용히 빈 타입을 돌려준다(stl `Entries`) | STR:47,180; STS:26 | described |
| D6 | 저장소의 '에러 0건' 게이트가 type function 몸통의 진단을 놓친다 | stl 게이트의 에러 규약은 최상위 `type function` 몸통을 건너뛴다(본문 검사의 거짓 양성 회피) | (stl 0.742) | 몸통은 대조군 스니펫으로 따로 검사한다 | stl `conventions.md:84` 끝 | described |

## §3 성능·한도 (L)
summary: 깊은 재귀는 stack overflow 진단, 무한 루프는 검사기를 멈추니 상한과 timeout. keyof 맵 150 키 넘으면 too complex, 큰 표면 export·호출 수·메모리도 한도

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| L1 | 몸통의 깊은 Lua 재귀는 "errored at runtime: … stack overflow" 진단이 된다. 검사기는 살아 있다 | Lua 스택 한도 | 재현 / 재현 / — / 같음 | 반복문으로 바꾼다. 얕은 자기 호출(깊이 10)은 문제없다 | `tf-limit-stack-overflow` | verified |
| L2 | 몸통의 무한 루프는 검사기를 **멈춘다**. CI 가 매달린다 | luau-analyze 와 `luau-lsp analyze` 에는 시간 한도가 없다. 인터럽트는 `finishTime` 이 있을 때만 건다(`UserDefinedTypeFunction.cpp`) | 재현 / 재현 / — / 재현 | 루프에 상한을 둔다(extern 부모 체인은 이름 말고 깊이로 끊는다, QR). CI 검사는 `timeout` 으로 감싼다 | `tf-cross-module.sh` M6 | verified |
| L3 | `K & keyof<Map>` + `index<Map, K>` 꼴은 맵이 크면 too complex 다. 150 키는 오용이 정확히 잡힌다. 200 키는 같은 오용이 "Code is too complex" 로 바뀌고 원래 메시지가 사라진다. 400 키에서는 0.734 가 맞는 호출도 too complex 다 | 큰 싱글턴 유니온 정규화 | 0.734: 400 키 맞는 호출도 실패 / 0.742: 200 키부터 오용만 / 1.69.0: 150 키 맞는 호출도 실패 / 1.70.1: 0.742 와 같음 | 맵을 쪼개거나, 커리(`On("Size")(fn)`)로 K 를 먼저 정한다. quad 실측(Roblox 값 타입)은 130 통과, 140 실패였다 | `tf-limit-keyof-scale`(lsp 열); QTL 8.7 ②③; QR:329-339 | verified |
| L4 | 아직 구체화되지 않은 제네릭을 인자로 type function 이 자기를 부르면 stack overflow 로 죽는다. 지연 적용 API 가 없다 | type function 은 구체 타입에서만 돈다 | (2026-08) | 재귀 타입 문제의 우회로 쓰지 않는다 | QTL §5 끝 문단; quad `audit/type-recursive-issue-with-typeof/REPORT.md:224-236` | described |
| L5 | 줄지 않은 적용이 파라미터에 있는 생성자는 호출마다 제약을 더한다. 약 1500 호출(2300 줄)에서 모듈이 too complex 다. too complex 는 호출 자리마다 따로 뜬다 | `LuauSolverConstraintLimit=1500`(Studio 동기값) | (lsp 1.70.1) | type function 이 함수 타입 전체를 돌려주게 한다(ctor 끌어올리기). 그러면 5730 줄도 깨끗하다 | QR:560,785-787; quad `base/surface-plan.md:18-20` | described |
| L6 | 무거운 표면을 **export** 하면 too complex 이고, 같은 양을 지역에서만 쓰면 통과한다. Studio 는 이때 too complex 표시도 없이 검사를 끈다(NEG 0) | 모듈 경계에서 수출 타입을 굳히는 비용 | (lsp 1.70.1, Studio) | 모듈을 둘로 쪼갠다 | QR:105-112 | described |
| L7 | type function 결과는 줄일 때마다 이름 없는 새 사본이다. 큰 그래프끼리 구조 비교가 일어나면 too complex 다(추상 클래스 `Modifier<C>` 를 다른 표기의 주석으로 넘길 때) | 이름 신원이 없다 | (lsp 1.70.1 sync) | 입력 자리는 표식, 큰 전체형 비교를 피한다 | QR:252-256,493-503; QTL 8.40 | described |
| L8 | 메모리·시간: 1.69.0 초기 실측은 20 클래스 × 100 호출에서 factory 0.77 s 대 생성 D 1.12 s(quad DF:35). 361 클래스 brief 1.53 s·1090 MiB. 417 클래스의 `Instance` 전체 As 트리는 3 GiB 한도에서 9.8 s 뒤 `std::bad_alloc` | 결과 크기 | (lsp 1.70.1) | 표면을 필요한 만큼만 만든다. 검사는 `ulimit -v` 로 감싼다 | QR:305,370 | described |
| L9 | 넘기는 타입이 너무 크면 "Complexity limit reached when passing a type to a type function" | 직렬화 한도 | (소스) | 인자를 줄인다(`keyof<T>` 만 넘기기 등) | Luau `UserDefinedTypeFunction.cpp` | described |

## §4 인자 직렬화 (S)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| S1 | 인자 안에 제네릭에 묶여 줄지 않은 적용(`keyof<K>`, `index<…, K>`, 사용자 type function)이 있으면 "Type functions do not currently support types of the form 'keyof<K>'" 가 뜨고, 결과는 키가 없는 타입이 된다 | 직렬화기가 줄지 않은 적용을 표현하지 못한다 | 재현 / 재현 / 재현 / 재현 | 큰 라이브러리 타입을 통째로 넘기지 않는다. 필요한 조각(`keyof<T>`, 필드 하나)만 넘긴다. 진단용 type function 필드를 품은 타입(quad `Quad`)도 여기에 걸린다 | `tf-serialize-unsupported-arg`; QR:657 | verified |
| S2 | 인자가 그 적용 자신을 가리키는 순환 별칭이면(`type Obj = Pass<{ m: (self: Obj) -> … }>`) S1 과 같은 에러 | 같음 | 재현 / 재현 / 재현 / 재현 | 재귀 별칭은 type function 밖에서 정의하고 완성된 별칭을 넘긴다(그건 된다) | `tf-serialize-unsupported-arg` | verified |
| S3 | `*error-type*` 이 섞인 인자는 "types of the form '*error-type*'" 로 실패한다. 실물 Store 의 모든 자리에서 났다. 최소 꼴(`Pass<typeof(미정의)>`)에서는 미정의 진단만 나고 결과는 조용히 흡수된다 | 앞단 에러 타입 | (quad 2026-08) / 최소 꼴은 0.742 에서 흡수 | `keyof<T>` 처럼 에러 타입이 들 수 없는 조각만 넘긴다 | quad `base/store-plan.md:317-356`; QTL 8.39 | described |

## §5 제네릭 (G)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| G1 | 바깥 제네릭 `T` 에 걸린 적용(`Pass<(T) -> T>`)은 그 제네릭 함수 몸통 안에서 줄지 않는다. 호출도 거부된다("Cannot call a value of type Pass<(T) -> T>") | T 가 구체화되지 않아 평가가 막힌다(업스트림 `outer_generics_irreducible`) | 재현 / 재현 / 재현 / 재현 | 적용을 함수 타입 **전체**에 건다. 몸통 안에서는 캐스트한다 | `tf-generic-scope`; STR:103; STS:35 | verified |
| G2 | (제약 아님) 호출부에서 T 가 정해지면 줄어든다(`unwrap<T>(x: T): StripNil<T>` → `number`). 제네릭 함수 타입을 넘기면 제네릭이 보존된다(`Pass<<T>(T) -> T>`) | — | 동작 ×4 | — | `tf-generic-scope` | verified |
| G3 | type function 이 제네릭 함수 타입을 다시 만들면 제네릭이 적용 자리 스코프를 갖고, 기본값과 경계를 잃는다. `def:generics()` 를 빠뜨리면 "not in a scope of the active generic function" 이다 | 제네릭 기본값·경계는 직렬화되지 않는다 | (stl 0.742) | 원래 제네릭 목록을 그대로 돌려준다 | STR:101-105; STS:103; stl `research/trait-udtf/sonnet/REPORT.md:59` | described |
| G4 | 한 정의의 제네릭 객체를 여러 진입점에서 같이 쓰면 `Expected 'E', got 'number'` 가 난다. 손으로 줄인 재현은 0건이다 | 미상 | (stl 0.742) | 진입점마다 새 제네릭으로 치환한다(`subst`) | STR:35-36,197-198 | described |
| G5 | 정의 제네릭과 같은 이름의 슬롯 제네릭은 "Duplicate type parameter" 로 진입점 전체를 지운다. 제네릭 팩 정의는 지원하지 않는다 | 이름 충돌 | (stl 0.742) | 이름을 바꾸고, 슬롯은 따로 다룬다 | STR:~363-365; STS:105 | described |
| G6 | `parameters().tail` 의 `...any` 를 남기면 인자 수 검사가 사라진다(`X.Of(d,1,2)` 0건) | 가변 꼬리 | (stl 0.742) | 다시 조립할 때 tail 을 뗀다 | STR:104 | described |
| G7 | 같은 파일에서 정의와 등록을 하면 제네릭 슬롯(`Fold<U>`)의 실수가 0건이다 | 다시 만든 `<U>` 가 모듈 스코프를 얻는다(업스트림 `Subtyping.cpp:830`) | (stl 0.742) | 정의를 `do … end` 안에 둔다 | STS:36; STR:43-44 | described |
| G8 | 명시 타입 인자를 일부만 주면 솔버가 죽는다 | 미상 | (stl 0.742) | 제네릭 순서를 공개 표면으로 보고, 첫 인자에만 쓰이는 `Self` 는 뺀다 | STR:33-34,264-265 | described |
| G9 | 같은 type function 이 정의에 어떤 슬롯이 있느냐에 따라 다르게 동작한다. 작은 프로브의 '0건'은 약한 증거다 | 슬롯 모양별 분기 | (stl 0.742) | 실물 모양으로 대조군을 둔다 | STS:107 | described |

## §6 패스스루 뒤 self 체이닝 (C)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| C1 | (보고) `return t` 패스스루를 거친 값에서 제네릭 self 메소드(`<Self, P>(self: Self, …) -> Self & P`) 체이닝이 "Expected exactly 'P & Self', got 'P & Self'" 로 깨진다 | 원천은 "이력"이라고 추정했다 | **미재현** ×4. 다섯 꼴을 쟀다: 직접, 두 인자, 두 번 체이닝, 제네릭, 자유 함수 | 원천의 처방(검사 결과는 별도 필드, 원본은 type function 을 거치지 않게)은 비용이 작으므로 유지해도 된다 | `tf-passthrough-chaining`; QTL §6; stl `conventions.md:84` ② | described |
| C2 | 실물 quad `Quad` 를 패스스루하면 `AddPlugin` 키가 사라진다. 0.742 는 S1 메시지를 내고, 0.734 는 메시지 없이 사라진다 | S1(직렬화 실패). C1 의 실제 원인 후보다 [추정] | 0.734 조용히 / 0.742 메시지 | S1 우회법 | 이 저장소 수동 실측(quad-types 사본, RESULTS.md) | described |
| C3 | `index<>`/`keyof<>` + `Self` 제네릭 조합을 거치면 무주석 콜백 파라미터 추론이 깨진다(평범한 레코드 필드는 정상) | 미상 | (2026-08-25) | 그 조합을 피한다. 같은 날 철회한 실사례 | QTL §0 끝 | described |

## §7 재조립한 결과의 모양 (R)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| R1 | 읽기 전용 인덱서를 다시 조립하면 `read` 를 잃어 쓰기가 통과한다. `setreadindexer` 는 런타임 에러("separate read/write types for indexers") | 인덱서 read/write 분리를 아직 지원하지 않는다 | 재현 ×4 | 인덱서가 든 슬롯은 다시 조립하지 않고 원본을 돌려준다. 패스스루는 `read` 를 지킨다. 읽기 전용 **프로퍼티**는 `setreadproperty` 로 옮겨진다 | `tf-rebuild-read-indexer`; STR:~373-377; STS:105 | verified |
| R2 | read/write 를 따로 넘기면 결과 표시가 `read b`/`write b` 로 갈라진다 | 같은 타입이라도 객체가 둘이다 | (tbox 1.69.0) | read 와 write 가 같으면 `setproperty` 하나로 넣는다 | TB `src/types.luau:76-77,124-133` | described |
| R3 | 리터럴의 모르는 키(`{ a = 1, c = true }`)가 통과한다 | type function 탓이 **아니다**. 새 솔버는 어떤 테이블 타입에서도 리터럴의 남는 키를 검사하지 않는다(교집합, 손으로 쓴 타입도 같다) | 재현 / 재현 / 재현 / 재현 | 런타임 검사로 잡는다(tbox `New`) | `tf-noalt-merge` | verified |
| R4 | type function 결과에 두 단계 이상 중첩된 싱글턴 리터럴이 `string` 으로 넓어진다. 같은 모양을 손으로 쓴 타입은 통과한다 | 결과에는 양방향 추론이 흐르지 않는다 | (tbox 1.69.0) | `"buy" :: "buy"` 캐스트 | TB `CLAUDE.md:156-157`; tbox `docs/code-review-2026-10-05.md:221` | described |
| R5 | `Type.Tuple(…)` 의 마지막 인자가 함수 호출이면 Static 이 "unsupported type pack type" 으로 풀리지 않는다 | 팩 꼬리 직렬화 | (tbox 1.69.0) | 마지막 인자를 괄호로 감싼다 | TB `CLAUDE.md:154-155` | described |
| R6 | 결과 테이블에서 같은 키의 타입이 다르면, 교집합(`{a: number} & {a: string}`)과 달리 Merge 는 덮어쓴다 | 의미가 다르다(제약이 아니라 선택) | 동작 ×4 | — | `tf-noalt-merge` | verified |

## §8 내장 `keyof`/`index` (B)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| B1 | `keyof<T>` 에 테이블이 아닌 타입이 오면 "does not have keys" 로 죽는다. 그 별칭을 쓰는 자리마다 다시 뜬다 | 조건부 타입이 없다 | 재현 ×4 | T 가 늘 테이블인 자리에만 둔다. 결과 타입이 재귀적으로 그 메소드를 갖는 설계는 피한다 | `tf-builtin-keyof-index`; QTL 8.15 | verified |
| B2 | (제약 아님) `keyof<{}>` 는 빈 유니온(never)이다 | — | 동작 ×4 | — | `tf-builtin-keyof-index` | verified |
| B3 | 제네릭 `M` 에 의존하는 `index<…, M>` 반환을 다른 제네릭에 함수 **값**으로 넘기면, 결과가 줄지 않은 채 아무 타입에나 대입된다 | 강제 축약이 실패하면 never 로 취급된다 [추정] | 재현 / 재현 / 재현 / 재현 | 경계에서 구체 타입 주석으로 고정한다 | `tf-builtin-unreduced-index`; stl `audit/luau-solver-issues/7-…` | verified |
| B4 | `index<>` 로 만든 무주석 콜백 파라미터에 연산자를 쓰면 `unknown` 이다(`v + 1`) | 연산자 제약이 축약보다 먼저 풀린다 | 최소 꼴 미재현(0.742). quad 는 test.sh 한도 플래그로 관측 | 연산자를 쓰는 콜백은 주석한다 | QTL 8.10 | described |
| B5 | `<K>(K & keyof P, Source<index<P, K>>)` 에서 `P[K]` 가 `any` 면, 맞는 `Source<UDim2>` 도 23건으로 거부된다. 직접 쓴 `Source<any>` 는 통과한다 | 보류된 적용의 비교가 `any` 특례를 못 탄다 [추정] | (lsp 1.69.0) | 충돌 이름만 보조 맵으로 따로 받는다 | QTL 8.27 | described |

## §9 모듈·export 경계 (X)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| X1 | 정의 모듈이 한 번도 인스턴스화하지 않은 `export type function` 을 소비자가 쓰면 **진단 0건**(조용히 `*error-type*`) | `luau-lsp analyze` 가 옵션 없이 모든 FFlag 를 켜고, 그중 `LuauDoNotExportBrokenTypeFunction` 이 작동한다 | 없음 / 없음 / **재현** / 없음(그 FFlag 가 사라짐) | 1.69.0 을 쓰는 동안은 정의 모듈에 `type _Prime = F<…>` 를 둔다(인자는 아무거나). 또는 `--flag:LuauDoNotExportBrokenTypeFunction=false`. 1.70.1 에서 그 플래그를 주면 "Unknown FFlag" 경고만 나고 분석은 계속된다 | `tf-cross-module.sh` M1–M3; QTL 8.18 정정, 8.22 | verified |
| X2 | `export` 하지 않은 type function 을 `M.F<…>` 로 쓰면 "Unknown type 'M.F'" | 수출 규칙 | 재현 / 재현 / — / — | `export type function` 으로 둔다. 또는 그것을 감싼 export 별칭(`export type ViaF<T> = F<T>`)을 둔다(동작함) | `tf-cross-module.sh` M4; quad `luau-test/done/23` 머리 4번 | verified |
| X3 | 값 자리의 명시 인스턴스화 인자가 둘 이상이면 `Foo<A, B>` 가 비교 연산으로 파싱된다 | 문법 | — | `Foo<<A, B>>` | quad `luau-test/done/23` 머리 4번 | described |
| X4 | 다른 패키지 사본에서 온 같은 이름 타입은 서로 대입되지 않는다 | 타입 신원(type function 고유는 아님) | (lsp 1.70.1) | 라이브러리 진입점은 표식 타입으로 받는다 | QTL 8.43 | described |

## §10 DX: hover, 자동완성, 메시지 (DX)

| ID | 증상 | 원인 | 버전 | 우회법 | 근거 | status |
|---|---|---|---|---|---|---|
| DX1 | type function 결과는 별칭 이름을 잃는다. 진단 메시지와 `luau-analyze --annotate` 에 구조 전체(`{ alpha: number, beta: string }`, 재귀면 `t1 where …`)가 펼쳐진다. 같은 값을 별칭으로 주석하면 `Big` 이 나온다 | 결과는 이름 없는 새 타입이다(L7) | 재현 / 재현 / 재현 / 재현 | 공개 표면의 메시지가 중요하면 type function 결과를 다시 이름 붙은 별칭으로 감쌀 수 없다는 점을 문서에 적는다 | `tf-dx-alias-name-lost`; QR:9-10,43,577-579 | verified |
| DX2 | 시그니처 hover 는 적용을 줄이지 않고 보여 준다(`function unwrap<T>(x: T): StripNil<T>`). 호출 결과 hover 는 줄인 타입(`number`)이다 | — | — / — / 재현 / 재현 | — | `tf-dx-hover`(lsp_probe) | verified |
| DX3 | `index<Map, K>` 파라미터를 가진 무주석 콜백은 hover 가 `v: unknown` 이고 `v.` 자동완성이 없다. 오용은 검사된다(본문 사용으로 v 가 먼저 굳고 콜백 전체가 대조된다). 같은 모양의 구체 시그니처는 `number` 다 | 문맥 타입이 파라미터로 흘러들지 않는다 | — / — / 재현 / 재현 | 편집기 도움이 필요하면 주석을 단다. 커리(`On("Size")(function(v) … end)`)는 흘러든다 | `tf-dx-hover`; QTL 8.7 ③(2026-10-16 정정); QR:35 | verified |
| DX4 | (제약 아님) type function 이 만든 테이블에서도 키 자동완성이 뜬다 | — | — / — / 동작 / 동작 | — | `tf-dx-hover`; quad `audit/d-factory-studio-probe-2026-09-16/REPORT.md:37` | verified |
| DX5 | 큰 표면은 자동완성이 느리다. 전체 맵에서 `Part { ` 가 1.2 s(sync)–4.39 s(vsc), 31 클래스 맵은 0.01–0.02 s | 결과 크기 | (lsp 1.70.1) | 표면을 나눈다 | QR:353-360 | described |
| DX6 | sync 한도에서 Into 체인 뒤 자동완성이 쓰레기 항목 하나(`AAsTextButton`)로 깨진다 | 한도 | (lsp 1.70.1 sync) | — | QR:569 | described |
| DX7 | 오버로드 교집합 커리는 이름 자동완성을 잃는다(0개). 제네릭 `K & keyof` 꼴은 유지한다(27개) | — | (lsp 1.70.1) | 이름 인자는 `K & keyof<Map>` 으로 받는다 | QR:94-98 | described |
| DX8 | 요소·Spread 테이블 안에 넣은 `OnEvent` 콜백에 문맥 타입이 안 들어와 `x + y` 가 거짓 양성이다 | luau-lsp 1.69.0 | — / — / 재현 / 없음 | 1.70.1 로 올리거나 주석한다 | QR:788 | described |

## §11 extern(Roblox 클래스) API 메모 (A)
status: described · 원천: QTL 8.22 (luau-lsp 1.69.0, VSCode, Studio 세 환경), QR(luau-lsp 1.70.1). Roblox 정의 파일이 필요해 스니펫이 없다.

- 클래스 걷기: `cls:properties()`(그 레벨만), `cls:readparent()`, `tostring(cls)` 가 이름이다. `:name()`·`:parent()` 는 없다. `readproperty` 는 테이블 전용이라 extern 멤버는 `properties()` 를 돌며 찾는다.
- 클래스와 값 타입(UDim2 등) 모두 태그가 `extern` 이다. Instance 계열인지는 부모 체인으로 가린다(QR:122).
- 인스턴스화된 extern 시그널의 `readparent()` 는 같은 이름의 원형을 준다. 체인 루프는 이름이 아니라 깊이 상한·신원으로 끊는다(L2).
- 넘어온 핸들은 호출마다 새 래퍼다. `==` 는 참이고 `rawequal` 은 거짓이다(QR:47-49).
- 이벤트를 `function Connect(self, …)` 메소드로 선언한 정의 파일에서는 `conn:parameters()` 가 "unsupported type pack type" 으로 던진다. 함수 타입 프로퍼티는 된다. 멤버 하나가 던지면 클래스 표면 전체가 never 가 되므로, 1.70.1 이상이면 pcall 로 감싼다(E4).
- 읽기 전용 표시는 어느 환경의 타입 데이터에도 없다(`AbsoluteSize` 도 read == write). 정책은 생성 데이터로 따로 받는다.
- 체커 동작은 세 환경이 같고 **타입 정의 데이터**가 다르다. 클래스별 프로퍼티 수, deprecated 포함 여부, 이벤트가 테이블인지 extern 인지가 다르다. 정의 파일에 없는 클래스를 이름으로 부르면 맵 전체가 깨진다(`Unknown type 'AdPlacement'`, QR:374-375).
