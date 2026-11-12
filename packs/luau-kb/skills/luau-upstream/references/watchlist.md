---
title: "알려진 한계와 그것을 고칠 업스트림 항목"
description: "luau-kb 의 타입 솔버 결함(S1–S19)·type function·도구 한계를 업스트림 이슈·RFC 와 잇는 감시 목록: 0.746 실측 상태, 0.742→0.746 bug-scan 결과와 새 위양성, 우회책 수명(임시·영구·불필요), 보고 후보"
keywords:
  - "곧 고쳐지나"
  - "업스트림에서 해결 중"
  - "upstream issue tracking"
  - "감시 목록"
  - "watchlist"
  - "우회책 수명"
  - "workaround lifetime"
  - "임시 우회 영구 우회"
  - "알려진 결함 상태"
  - "#2380"
  - "bug-scan 결과"
  - "is not iterable"
  - "0.746 새 진단"
  - "업스트림 보고 후보"
  - "S1–S19"
  - "고쳐짐 실측"
kind: reference
category: luau/upstream/watchlist
tags: [bug, new-solver]
last_verified: 2026-11-10
---
# watchlist — 알려진 한계와 그것을 고칠 업스트림 항목

> last-checked: 2026-11-10 (luau 최신 0.746, luau-lsp 최신 1.70.1). 이슈 상태는 GitHub API·이슈 페이지로, 릴리스 노트는 0.735–0.746 태그 페이지로(`roadmap-notes.md` §1), 동작은 `tools/upstream_check.py --bug-scan 0.746` 으로 확인했다.

## 이 파일이 답하는 질문
- Q1 luau-kb 에 기록된 이 한계·결함은 업스트림에서 추적되고 있나? 어디서?
- Q2 최신 luau 에서 고쳐졌나(실측)?
- Q3 이 한계를 피하는 우회책은 임시인가 영구인가?
- Q4 다음 버전이 나오면 무엇부터 다시 재나?

## 목차
- §0 읽는 법 (칸의 뜻)
- §1 타입 솔버 결함 (S1–S19, luau-types `solver-limits.md` §2)
- §2 bug-scan 결과 (2026-11-10, 0.742 → 0.746)
- §3 그 밖의 타입 한계 (type function, 재귀, 교집합)
- §4 도구·런타임 쪽 한계
- §5 업스트림 보고 후보 (사용자 결정)

---

## §0 읽는 법
status: described

- **업스트림**: 해결을 추적하는 항목. `#N` 은 `luau-lang/luau` 이슈, `RFC:` 는 `rfcs.luau.org/<이름>.html`. "없음" 은 찾지 못했거나 아무도 보고하지 않았다는 뜻이다(원천 저장소들은 보고 초안만 두고 게시하지 않았다 — 게시는 사용자 결정).
- **상태**: `열림` / `닫힘(<날짜>)` / `고쳐짐(<버전>, 실측)` / `일부 고쳐짐` / `bug(0.746)` = 최신에서도 재현.
- **예상 시점**: 근거(릴리스 노트, RFC 단계, 메인테이너 발언)가 있을 때만 적는다. 없으면 `—`.
- **우회 수명**
  - `임시` — 업스트림이 고칠 근거가 있다. 우회 자리에 이 표의 ID 와 링크를 주석으로 남기고, 스니펫의 `bug-present` 가 뒤집히면 걷는다.
  - `영구` — 고칠 근거가 없거나, 우회가 그 자체로 더 나은 설계다. 문서화하고 관례로 둔다.
  - `불필요` — 고쳐지면 코드 변경 없이 풀린다. 우회 장치를 심지 않는다.

## §1 타입 솔버 결함 (S1–S19)
status: verified (0.746 열, 2026-11-10 bug-scan) / described (업스트림 칸) · 근거: luau-types `../../luau-types/references/solver-limits.md` §2, `snippets/*`
summary: 진단 없이 새는 솔버 결함 S1–S19 의 0.742·0.746 상태, 업스트림 항목, 예상 시점과 우회책 수명 표

| ID | 한계 (진단이 안 남) | 스니펫 | 0.742 | 0.746 | 업스트림 | 상태 | 예상 시점 | 우회 수명 |
|---|---|---|---|---|---|---|---|---|
| S1 | 뒤쪽 파라미터를 생략한 람다의 주석 상한 소실 | `generics-callback-bound-lost` | bug | bug | 없음(인접 #2168, 증상 반대) | bug | — | 임시: 콜론 호출·명시 타입 인자 `F<<T>>`. 영구 설계 함의: 콜백 다른 파라미터에 T 를 품은 테이블을 두지 않기 |
| S2 | 맨 람다 결과 누수 | `generics-bare-lambda-free-type` | fixed | fixed | luau-lsp main "Sync to upstream Luau 0.742"(미릴리스) | 고쳐짐(0.742). **luau-lsp 1.70.1(번들 0.740)은 아직 bug** | 다음 luau-lsp 릴리스 [구현: main 에 커밋] | 0.734 핀 저장소와 에디터만 해당 |
| S3 | 제네릭 몸통에서 타입 변수 값 무검사(`V` → `number` 자리) | `generics-body-unchecked` | bug | bug | #2733 (닫힘 2026-09-19, "fixed in 739") | **일부 고쳐짐**: #2733 의 모양(구체 값 `nil` → `T` 자리)은 0.742 부터 잡힌다. 우리 모양(`T` 값 → 구체 자리, 다른 제네릭 호출에 `"bad"`)은 0.746 에서도 bug | — | 영구(관례): 제네릭 몸통의 대입은 테스트로 지킨다 |
| S4 | 문자열 키 리터럴 → 인덱서 파라미터 값 무검사 | `generics-string-key-literal-indexer` | bug | bug | 없음 | bug | — | 임시: 리터럴을 주석 단 지역에 담는다 |
| S5 | 재귀 타입이 유니온/옵셔널 갈래일 때 타입 인자 무검사 | `unions-recursive-in-optional` | bug | bug | #1822 "recursive types in unions"(열림)이 가장 가깝다(같은 결함인지는 미확인) | bug | — | 임시: 비옵셔널 자리에서 한 번 더 대입해 검사 |
| S6 | `{}` 리터럴 → `{ [K]: V }` 가 unknown | `generics-literal-to-indexer-unknown` | bug | bug | 인접 수정: Roblox 08-10 주 노트 "indexer 추론이 unknown", 0.737 인덱서 제네릭 누수, 0.738 #2669 — 우리 모양은 남음 | bug | — | 영구: 명시 타입 인자 `f<<K, V>>` (그 자체로 좋은 관례) |
| S7 | 비균일 재귀 메소드 반환 누수 (`Foo<T>` → `Foo<U>`) | `recursion-nonuniform-return` | bug | bug | **#2380** "Allow recursive generic types to differ"(열림, 2026-05-08, 메인테이너 "has not been implemented yet") · RFC `relax-recursive-type-restriction`(승인 2025-03-05, 구현 없음) | bug. class 는 이것을 풀지 않는다(제네릭 class 는 범위 밖, `roadmap-notes.md` §2) | — (근거 없음) | **불필요** — 고쳐지면 선언 그대로 풀린다. 우회 장치를 심지 않는다. 다운스트림 정확도가 꼭 필요하면 `typeof(이름 붙은 함수)` 처방(임시) |
| S8 | 비균일 재귀보다 앞 선언 별칭의 참조가 에러 타입 | `recursion-declaration-order` | bug | bug | #2380 / 같은 RFC. 인접: #2110(닫힘 2026-02-26, **균일** 재귀를 앞에서 쓰면 거짓 에러) — 우리 모양(비균일, 조용한 누수)은 남음 | bug | — | 임시: 비균일 재귀 별칭을 파일 맨 위에 둔다 |
| S9 | 자기 참조 함수 필드 + 같은 이름 멤버의 유니온 통과 | `unions-same-name-method-hole` | bug | bug | 없음 | bug | — | 영구(설계): 유니온에는 표식 타입만 |
| S10 | 제네릭 메소드의 반공변 무검사 | `variance-generic-method-contravariance` | bug | bug | 없음. 메인테이너가 rfcs#11 을 닫으며 "반공변 자리 재귀 자기 참조" 를 미해결로 언급, 제네릭 제약 초안 rfcs#266 | bug | — | 영구에 가깝게: 근거 [제안] 뿐 |
| S11 | 값 팬텀 `read p: T?` 에 빈 테이블 통과 | `variance-value-phantom-nil` | bug | **fixed** | 후보: 0.744 "폭 서브타이핑이 stand-in 속성에 nil 을 끼우지 않음"(#2625, #2644). 0.743–0.745 를 설치해 이분하지 않아 판은 미확인 | **고쳐짐(0.746, 실측)** | — | 걷을 수 있음. 단 함수 모양 팬텀 처방은 여전히 유효(0.742 이하 핀 저장소) |
| S12 | 공변 자리에서 제네릭 V 가 넓어짐 | `variance-covariant-generic-widening` | bug | bug | 없음 | bug | — | 영구(설계): 불변 팬텀 `(V) -> V` |
| S13 | 공변 인자 둘 → 교집합 | `generics-covariant-args-intersection` | fixed | fixed | — | 고쳐짐(0.742) | — | 0.734 핀만 |
| S14 | 가변 인자 꼬리 호출 결과 무검사 | `solver-vararg-tail-call` | fixed | fixed | — | 고쳐짐(0.742) | — | 0.734 핀만 |
| S15 | 함수 ∩ 테이블 값이 never | `unions-function-table-intersection` | bug | bug | 없음 | bug(설계상 never) | — | 영구: `setmetatable<{…}, { __call }>` |
| S16 | `__call` 인자 무검사 | 같은 파일 | fixed | fixed | — | 고쳐짐(0.742) | — | 0.734 핀만 |
| S17 | 선언된 테이블의 제네릭 함수 필드 결과 무검사 | `solver-declared-generic-field` | bug | bug | 없음 | bug | — | 영구: 결과 검사가 필요하면 자유 함수로 |
| S18 | 줄지 않은 `index<…, M>` 결과가 아무 데나 대입 | `tf-builtin-unreduced-index` | bug | bug | 없음 | bug | — | 임시 |
| S19 | nonstrict `.luaurc` 아래 명백한 에러 0건 | `modes-luaurc-nonstrict-silences` | 동작 | 동작 | (설계상 동작) | 동작 | — | 영구 규칙: 파일마다 `--!strict` |

## §2 bug-scan 결과 (2026-11-10, 0.742 → 0.746)
status: verified · 명령: `python3 -I tools/upstream_check.py --bug-scan 0.746` (같은 결과를 `--base 0.734` 로도 확인)
summary: 0.742 → 0.746 bug-scan 결과 — 고쳐진 S11, 풀린 교집합 인스턴스화, 나머지 같음, 스니펫 밖에서 찾은 0.746 새 진단

| 분류 | 스니펫 | 내용 | 판정 |
|---|---|---|---|
| 뒤집힘(**반영됨**) | `variance-value-phantom-nil.luau` 8행 | `local holeAccepted: VP<number?> = empty` 에 0.746 이 "Expected this to be 'VP<number?>', but got 'empty'" | **고쳐짐(S11)**. 넓게 보면 "이미 만들어 둔 테이블(봉인된 지역)에 없는 `read x: T?` 필드는 더 이상 nil 로 읽히지 않는다". 읽기·쓰기 필드(`{ x: number? }`)는 0.742 에서도 거부됐고, 0.746 은 `read` 필드도 같게 맞췄다. 리터럴 `{}` 를 바로 넣는 것은 여전히 통과 |
| 새 실패(**반영됨**) | `variance-intersection-instantiation.luau` 19행 | `id3(w3)` (`W3<T> = { v: T } & {}`) 의 "No valid instantiation" 이 0.746 에서 사라짐 | **한계가 풀림(개선)**. 재 보니 0.746 은 T 를 `number` 로 정확히 풀고, 결과의 `.v` 를 `string` 에 넣으면 잡는다(검사가 꺼진 것 아님). 같은 파일의 `W1`(`{ read v: T } & { read f: (T) -> () }`)은 여전히 실패하고 메시지 하한이 `number \| nil` → `number \| unknown` 으로 바뀌었다 |
| 같음 | 나머지 전부(마지막 실행: 138개 중 136개) | — | 변화 없음 |

### 스니펫 밖에서 발견된 0.746 의 새 진단 (저장소 실측 → 최소 재현)
status: verified (최소 재현 0.742 0건 / 0.746 진단, 2026-11-10) · 원천: stl-luau 게이트를 0.746 으로 읽기 전용 실행(sonnet 측정 세션), 진단 0 → 6건

| ID | 모양 | 0.742 | 0.746 | 판정 |
|---|---|---|---|---|
| N1 | **함수 반복자와 테이블의 유니온을 순회**: `m: { read [string]: number } \| (() -> (string, number))` 에 `for k in m do` | 0건 | "`(() -> (string, number)) \| { read [string]: number }` is not iterable" | **깨짐(위양성 후보)**. 우회: `if type(m) == "function" then … else … end` 로 갈래를 나눠 순회(0.746 rc=0 확인). 원인은 0.746 의 의도된 변경 "테이블의 서브타입이 아닌 것을 순회하면 에러"(#3090)로 보인다. 런타임에선 둘 다 순회되므로 유니온 갈래별 판정이 빠진 위양성일 수 있다. 업스트림 보고 후보 |
| N2 | **type function 몸통**에서 `local h = if fp.head == nil then {} else fp.head` 뒤 `for i, p in h do` | 0건 | "`(T & ~nil) \| {  }` is not iterable" (`~(false?)` 꼴도) | **깨짐**. `fp.head` 의 타입이 제네릭으로 보여 정제 뒤 순회가 막힌다. 우회: `local h: { type } = …` 주석(0.746 rc=0 확인) |

- bug-scan 은 **기록된 스니펫만** 본다. N1·N2 처럼 저장소 코드에서만 드러나는 변화가 있다. 핀을 올리기 전에 각 저장소 게이트를 새 버전으로 돌리는 단계(version-bump §2-5)를 건너뛰지 않는다.
- 스니펫 담당에게: N1·N2 를 `unions-iterate-function-or-table.luau`, `tf-iterate-refined-optional.luau` 같은 이름으로 `expect-error [>=0.746]` 스니펫으로 넣을 것.

- **저장소 영향**: S11 의 수정은 에러가 새로 생기는 방향이다. `read` 옵셔널 필드를 가진 타입에, 그 필드가 없는 이미 만든 테이블을 넘기는 코드가 0.746 에서 실패할 수 있다.
- **스니펫 반영됨**(2026-11-10): `variance-value-phantom-nil.luau` 8행은 `-- bug-present [<0.746] || expect-error: ... [>=0.746]`, `variance-intersection-instantiation.luau` r3 줄은 `-- expect-error: No valid instantiation [<0.746]` 로 바꾸고, 풀린 결과를 `string` 에 넣는 대조군을 더했다. 판정: W3 는 T 가 `number` 로 풀려 한계가 풀린 것(탐침 `local _x: never = id3(w3)` 가 'got { } & { v: number }'), W1 은 계속 실패. luau-types `variance.md` §3·§7, `solver-limits.md` §2 에 0.746 을 반영했다. 세 버전 rc=0.

## §3 그 밖의 타입 한계
status: described (업스트림 칸) / verified (스니펫이 있는 행) · 근거: luau-types `type-functions-limits.md`, `recursion-and-limits.md`

| ID | 한계 | 근거 | 업스트림 | 상태 (0.746) | 우회 수명 |
|---|---|---|---|---|---|
| R1 (tf) | type function 에서 읽기 전용 인덱서를 다시 조립 못 함 — `setreadindexer` 런타임 에러 "luau does not yet support separate read/write types for indexers" | `tf-rebuild-read-indexer` | UDTF RFC 문서에 API 는 있으나 master `TypeFunctionRuntime.cpp` 가 아직 에러. 추적 이슈·PR 없음(0.738 은 읽기 전용 인덱서 **추론**만 개선) | bug | 임시이지만 시점 근거 없음: 인덱서 슬롯은 원본을 그대로 돌려준다 |
| FP-ipairs | (위양성) 새 솔버가 `for i in ipairs(t)`(루프 변수 하나)를 "Argument count mismatch. Function expects 2 arguments, but 2 are specified" 로 거부. 옛 솔버·두 변수·`pairs` 는 통과 | `solver-ipairs-single-var`, luau-types `solver-limits.md` §4-1 | 없음(GitHub 검색 2026-11-10 "ipairs Argument count", "but 2 are specified". 인접 #2986 제네릭 팩 호출의 암묵 nil 인자 개수) | bug(0.746, lsp 1.70.1) | 임시: `for i, _ in ipairs(t)` 나 숫자 for. 고쳐지면 스니펫 expect-error 가 실패한다 |
| R3 (tf) | 리터럴의 모르는 키(남는 키)를 어떤 테이블 타입도 검사하지 않음 | `tf-noalt-merge` 31–33행 | exact table rfcs#11 — 0.740 실험 뒤 **2026-10-28 닫힘**("진행하지 않기로") | bug | **영구**: 이 모양의 검사는 오지 않는다 |
| L1–L9 (tf) | too complex, 스택 오버플로, 무한 루프에 시간 한도 없음 | `tf-limit-*` | 부분 수정: 0.735 UDTF 힙 한도, 0.738 #2707(모듈 간 too complex). 열림: #2273·#2234·#2356·#2056, #3013(큰 테이블 리터럴, 0.745 에 관련 수정) | 재현 | 영구: 설계로 줄인다 |
| X1 (tf) | 인스턴스화 안 된 `export type function` 소비 시 진단 0건 | type-functions-limits X1 | 없음 | — | 영구: 정의 모듈에서 프라이밍 |
| 재귀 §2 | 옛 솔버의 "Recursive type being used with different parameters" | `recursion-old-solver-rejects` | #2380, RFC `relax-recursive-type-restriction` | 동작(옛 솔버) | 불필요(새 솔버 사용) |
| 재귀 §4 | 상호 재귀 그룹 안에서 메소드 제네릭을 인자로 받는 별칭 거부 | described | #2380 | — | 임시: 시그니처를 인라인 |
| 교집합 §7 | `{ read v: T } & { read f: (T) -> () }` 추론 실패 | `variance-intersection-instantiation` | 없음 | `& {}` 꼴은 0.746 에서 풀림, 반공변 꼴은 남음 | 영구(설계): 평평한 테이블로 정의 |

## §4 도구·런타임 쪽 한계
status: verified (실측 행) / described · last-confirmed: 2026-11-10

| 한계 | 업스트림 | 상태 | 우회 수명 |
|---|---|---|---|
| 0.734 `luau-analyze` 병렬 검사 힙 손상 | #3020 (닫힘 2026-10-09) | 고쳐짐(0.742). 이 머신에서 재현 0(D-05 §2-1) | 0.734 핀 저장소: 게이트가 비정상 종료를 실패로 판정 |
| stylua 가 Luau 문법 설정 없이 `f<<T>>` 를 시프트로 재작성 | (설계상: 기본 문법이 Lua) | 2.5.2·2.6.0 같음(`tools/repro-stylua-typeargs.sh`, rc=0) | 영구: `syntax = "Luau"` |
| stylua 가 `if local`/`while local`/`class` 를 파싱 못 함 | StyLua 릴리스 노트 | 2.6.0 도 실패 | 문법 채택 보류(`syntax-adoption.md`) |
| luau-lsp 번들 Luau 가 CLI 보다 늦음(`while local` 미지원, S2 bug) | luau-lsp 릴리스 | 1.70.1 이 최신 | 임시: CLI 와 lsp 판정 차이를 기록 |
| `luau-analyze` 에 `--fflags` 가 없음(FFlag 뒤 문법·한도 플래그를 CLI 게이트로 못 켬) | 없음 | 0.746 도 없음 | 영구: 한도 플래그는 `luau-lsp analyze --flag:` |
| lune 0.10.5·selene 이 `const` 를 못 읽음 | 각 저장소 | 그대로 | 영구: luau CLI 러너(D-03), selene 폐기 |
| 정수 타입(`integer`) 철회 | rfcs PR #269(열림, 2026-10-29): "746 또는 747 이 마지막" | 0.746 에는 있음 | 쓰지 않는다. 쓰는 곳이 있으면 0.747 전에 걷는다 |

## §5 업스트림 보고 후보 (사용자 결정)
status: described

추적 항목이 "없음" 이고 0.746 에서도 재현되는 것: S1, S4, S6, S9, S10, S12, S17, S18, tf R3. 0.746 에서 새로 생긴 위양성 후보: N1(§2). 원천 저장소의 보고 초안(stl `luau-solver-issues/DRAFTS.md`)이 있다. 게시 여부는 사용자가 정한다. 게시하면 이 표의 업스트림 칸에 번호를 적는다.
