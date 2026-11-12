---
title: "`type function` 을 쓸지 정하는 법"
description: "type function 을 쓸지 사안별(D-04)로 정하는 판단 절차, 대안 없이 불가피한 패턴(strip-nil·키별 사상·덮어쓰는 병합·리터럴 계산), 쓰기로 했을 때 체크리스트, print+never 진단 패턴, 원천 정정과 사용처"
keywords:
  - "type function 써도 되나"
  - "type function 판단"
  - "user-defined type function"
  - "타입 함수 대안"
  - "strip-nil"
  - "StripNil"
  - "키별 사상"
  - "mapped type"
  - "덮어쓰는 병합"
  - "리터럴 값 계산"
  - "예약 키 금지"
  - "진단 전용 type function"
  - "types.never 진단"
  - "types.singleton"
  - "Expected this to be unreachable"
  - "D-04"
kind: reference
category: luau/types/type-functions
tags: [policy, correction, new-solver]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - luau-lsp 1.69.0
  - luau-lsp 1.70.1
---
# type-functions — `type function` 을 쓸지 정하는 법

## 이 파일이 답하는 질문
- Q1 type function 을 써도 되는가? (정책: §0, 판단 절차: §1)
- Q2 이 표현은 type function 없이도 되는가? (불가피 패턴: §2)
- Q3 쓰기로 했다면 어디에 두고 어떻게 시험하는가? (§3, §4)
- Q4 원천 문서의 서술 중 지금 버전에서 틀린 것은? (정정: §5)
- Q5 어느 저장소가 어떤 type function 을 운영하는가? (§6)
- 제약과 부작용 목록(버전 열 포함)은 `type-functions-limits.md` 에 있다. 이 파일의 `E1`, `S1` 같은 ID 가 그 표의 행이다.

## 목차
- §0 정책 (D-04 확정)
- §1 판단 절차 (결정 트리)
- §2 타입 함수 없이는 표현할 수 없는 패턴
- §3 쓰기로 했을 때 지킬 것
- §4 진단을 띄우는 패턴
- §5 사실 정정 (원천별, 전달용)
- §6 실제 사용처

---

## §0 정책 (D-04 확정)
status: described · 원천: `claude-doctor/decisions/D-04-type-functions.md` "사용자 결정 (2026-11-10)"

> 정책: 사안별 판단. 기본 금지도 아니고 '진단 전용' 구분도 쓰지 않는다. "부작용이 이득보다 큰가" 대 "이것 없이는 표현할 수 없는가"로 정한다. 부작용이 크면 스파이크로 재고 사용자 승인을 받는다(D-04).

- 타입 함수는 제약과 부작용이 많다(`type-functions-limits.md`, 57행). 그래서 쓸 때마다 저울질한다.
- '진단 전용만 허용'은 기준으로 쓰지 않는다. 경계가 애매하다. 예를 들어 strip-nil 은 결과 타입을 합성하지만 type function 없이는 불가능하다(§2 P1).
- 옛 입장은 역사로만 남긴다.
  - quad 의 '진단 전용'(`quad/.claude/base/typing-limits.md:50-83`)
  - stl 페이퍼의 '쓰지 않는다'(`stl-luau/.claude/papers/03-tuple.md:5-18`)
  - stl 규약의 '주의해서, 시제품으로 재고 사용자에게'(`stl-luau/.claude/conventions.md:84`)는 이 정책과 같은 방향이다.
- 이미 운영 중인 합성(tbox 의 `Static`/`Merge`/`Union`/`Tuple`, quad 3.4.0 의 `Build`)은 그 저장소의 승인된 결정이다. §3 을 소급해 맞추면 된다.

## §1 판단 절차 (결정 트리)
status: described (절차) · 근거 행은 각 단계에 적었다

1. **표현할 수 있는가?** §2 의 대안을 먼저 재 본다. 15줄 재현을 `luau-analyze` 0.734·0.742 로 돌린다.
   - 대안이 **같은 자리에서** 같은 오용을 잡으면(음성 대조군으로 확인) → type function 을 쓰지 않는다.
     - 예: 값이 들어오는 생성 함수의 예약 키 검사는 `T & { Get: never? }` 로 된다(P5).
     - 예: 자유 함수의 nil 벗기기는 `<U>(r: Ref<U?>): U` 로 된다(P1).
   - 대안이 API 를 비튼다(반환을 `any` 로 연다, 메소드를 자유 함수로 바꾼다, 사용자가 타입을 손으로 다시 쓴다) → 2 로 간다. 비트는 비용도 부작용으로 친다.
   - 대안이 없다 → 2 로 간다.
2. **부작용 크기를 매긴다.** 아래 중 하나라도 해당하면 **큼**이다.
   - (a) 결과가 공개 표면의 타입이 된다. 메시지·hover 가 펼쳐지고(DX1), 이름 신원이 없다(L7).
   - (b) 인자가 큰 라이브러리 타입이나 재귀 메소드 테이블이다(S1, S2, C2).
   - (c) 제네릭 함수 타입을 다시 조립한다(G1, G3–G8).
   - (d) 읽기 전용 인덱서가 든 타입을 다시 조립한다(R1).
   - (e) 호출 자리가 수백 개거나, 맵이 150 키를 넘는다(L3, L5, L6).
   - (f) 다른 모듈에서 쓰는데 luau-lsp 1.69.0 을 지원해야 한다(X1, E4).
   - (g) 무주석 콜백의 편집기 도움이 표면의 핵심이다(DX3).

   해당이 없으면 **작음**이다. 작음의 전형: 리터럴 검사 진단(P4), 작은 레코드 하나의 nil 벗기기(P1).
3. **작음** → 쓴다. §3 의 체크리스트를 지킨다.
4. **큼** → **스파이크와 사용자 승인**을 거친다.
   1. 시제품을 저장소의 스파이크 폴더(또는 `/tmp`)에 만든다. 원본 파일은 건드리지 않는다.
   2. 해당 행마다 음성 대조군을 하나씩 둔다. 핀 버전과 다음 버전(예: 0.734·0.742, luau-lsp 1.70.1)으로 돌린다.
   3. 잰 것을 표로 보인다: 잡히는 오용 수, too complex 여부, 검사 시간·메모리, hover 모양. 대안의 비용(1 에서 본 것)도 나란히 둔다.
   4. 사용자 승인을 받은 뒤에만 `src/` 에 넣는다. 결정과 수치는 저장소의 결정 기록에 남긴다.
5. 버전을 올릴 때는 그 저장소의 type function 스니펫과 이 저장소 `snippets/tf-*` 를 다시 돈다. 표의 버전 열이 바뀌면 판단도 다시 한다.

## §2 타입 함수 없이는 표현할 수 없는 패턴
status: verified (P1–P6 의 type function 쪽과 대안 쪽 모두 스니펫) · P7–P9 described
summary: strip-nil(메소드 자리)·키별 사상·덮어쓰는 병합·리터럴 계산은 불가피, 예약 키·nil 벗기기는 자리에 따라 대안이 있고 이름 인자는 내장 keyof/index 로 충분

| ID | 패턴 | 재 본 대안과 결과 | 결론 | 근거 |
|---|---|---|---|---|
| P1 | **strip-nil** — 제네릭 타입의 **메소드/필드 반환**에서 nil 을 벗긴다(`Ref<number?>:Unwrap() -> number`) | 메소드 제네릭 `<U>(self: R<U?>) -> U` 는 `unknown`. 부정 타입 `T & ~nil` 은 문법에 없다(SyntaxError). 자유 함수 `unwrap<U>(r: Ref<U?>): U` 는 `number` 를 준다 | 메소드·필드 자리에서는 **불가피**. 자유 함수로 둘 수 있는 API 면 대안이 있다 | `tf-noalt-stripnil`; quad `quad-types/src/init.luau:122` |
| P2 | **키별 사상** — 레코드의 각 필드 타입을 바꾼다(`{ hp: number }` → `{ hp: Source<number> }`, 모든 필드를 옵셔널로) | `{ [K in keyof T]: … }` 문법이 없다(SyntaxError). 손으로 다시 쓰는 것뿐이다 | **불가피**(손으로 다시 쓰지 않는 한) | `tf-noalt-mapped-record`; tbox `src/types.luau:63`, `src/schema/json/partial.luau:13` |
| P3 | **덮어쓰는 병합** — 뒤 테이블의 같은 키가 앞의 것을 대체한다 | 교집합 `A & B` 는 같은 키가 `number & string` 이 되어 아무 값도 못 넣는다. 키가 겹치지 않으면 교집합으로 충분하다(`(A & B)?` 도 동작) | 겹치는 키를 덮어써야 할 때만 **불가피** | `tf-noalt-merge`; tbox `src/types.luau:107` |
| P4 | **리터럴 값 계산** — 싱글턴 문자열의 내용을 보고 판정한다(버전 패턴 대조) | 타입 수준에 문자열 연산과 조건부 타입이 없다 | **불가피** | `tf-noalt-literal-compute`; quad `type-version-check/src/init.luau:141` |
| P5 | **예약 키 금지** — 레코드에 `Get`/`Set` 같은 키가 오면 막는다 | 값이 들어오는 생성 함수 파라미터에서는 `rec: T & { Get: never?, Set: never? }` 가 잡고, T 추론도 유지된다. 순수 타입 주석(`Store<{ Get: number }>`)은 교집합 별칭으로는 진단이 0건이다 | 주석 자리 검사만 **불가피**. 생성 함수 자리는 대안이 있다 | `tf-noalt-reserved-keys`; quad `quad-types/src/init.luau:272-295` |
| P6 | **키 이름 인자 + 그 키의 값 타입**(`OnChange("Size", fn)`) | 내장 `K & keyof<Map>` + `index<Map, K>`(이것도 type function). 큰 싱글턴 유니온 교집합과 오버로드 교집합은 실물 규모에서 too complex 였다(quad) | 내장 `keyof`/`index` 로 충분하다. 사용자 type function 은 필요 없다. 다만 L3 한도가 있다 | `tf-builtin-keyof-index`, `tf-limit-keyof-scale`; QTL 8.7 |
| P7 | **저장된 팩의 성분 사상** — 튜플·가변 스키마의 각 성분을 다른 타입으로 바꾼다(`StaticTuple`) | 팩 **저장**은 팬텀 `_pack: (T...) -> ()` 로 된다. 사상은 타입 수준 map 이 없어 안 된다 | 사상만 **불가피** | stl `papers/03-tuple.md:58-95,131-133`; tbox `src/types.luau:184` |
| P8 | **정의에서 진입점 시그니처 파생** — 한 정의에서 기본 슬롯은 옵셔널, 사용 시그니처는 필수로 두 뷰를 만든다(stl `Trait.View`) | 손으로 두 벌 쓴다(트레잇마다) | 손으로 쓰지 않으려면 **불가피**. stl 은 이 경로를 실험 패키지로 내렸다 | stl `src/Trait/init.luau:108`; `papers/08-trait-retrospective.md:153,189`; `archive/question-resolved.md:1808` |
| P9 | **검사기의 클래스 데이터에서 표면 파생** — Roblox 클래스 프로퍼티로 Modifier/Elem 표면을 만든다(quad `Build`) | 코드 생성(quad 3.3 의 생성 `Declaration`, 5250 줄). 다만 Studio 에서 too complex 로 검사가 꺼졌고(194개 중 0개 탐지), type function 표면은 194/194 를 잡았다 | 생성기가 대안이지만 실측상 type function 쪽이 나았다 | QR:24-25,642,671; quad `base/surface-plan.md` |

- '불가피'는 이 버전들(0.734·0.742, luau-lsp 1.69.0·1.70.1)의 문법과 솔버 기준이다. 조건부 타입, 부정 타입 문법, mapped type 이 들어오면 다시 잰다.
- P1·P5 의 대안이 '자리에 따라' 있다는 점이 중요하다. 같은 패턴이라도 API 모양을 바꿀 수 있으면 type function 을 피할 수 있다. 바꾸는 비용은 §1 의 2 에서 같이 따진다.

## §3 쓰기로 했을 때 지킬 것
status: described (체크리스트) · 각 항목의 근거 행 표시

1. **위치**
   - type function 은 타입 전용 모듈 한 곳에 모은다(quad `quad-types/src`, tbox `src/types.luau`, stl `src/Trait/init.luau`).
   - 몸통은 바깥 지역을 못 쓴다(E1). 런타임 유틸과 겹치는 로직은 중복을 감수하고 머리 주석에 그 사실을 적는다.
   - 다른 모듈에서 쓸 것은 `export type function` 이다(X2). luau-lsp 1.69.0 을 지원하는 동안은 같은 파일에 `type _Prime = F<…>` 를 둔다(X1).
2. **입력 가드**
   - `any`/`unknown` 은 앞에서 그대로 돌려준다(E7).
   - 태그를 먼저 본다(`t:is("singleton")`). pcall 은 1.70.1 이상에서만 믿는다(E4).
   - 루프에는 상한을 둔다(L2).
3. **인자를 작게.**
   - 큰 라이브러리 타입을 통째로 넘기지 않는다. `keyof<T>` 나 필드 하나처럼 필요한 조각만 넘긴다(S1, S3).
   - 원본 `T` 를 그대로 다시 내보낼 필요가 없으면 결과는 별도 팬텀 필드에 싣는다(C1 의 보수적 처방, 비용이 작다).
4. **제네릭**
   - 함수 타입 전체에 건다. 바깥 제네릭을 가진 별칭에 걸지 않는다(G1).
   - 원래 제네릭 목록을 돌려준다(G3). 가변 꼬리는 뗀다(G6).
5. **진단**
   - 사용자에게 보일 메시지는 `print` + `types.never` 로 낸다(D3).
   - 정의자 실수는 `error` 도 된다(D2). 디버그 `print` 는 남기지 않는다(D1).
   - 검사는 대조가 일어나는 자리에 둔다(D4).
6. **테스트**
   - 양성·음성 쌍을 `expect-error` 표식과 함께 둔다(이 저장소 `snippets/tf-*`, tbox `test/static/static.luau`, quad `luau-test/done/*`).
   - 고쳐지기를 기다리는 한계는 `bug-present` 와 버전 조건으로 고정한다. 고쳐지면 표식이 실패해 알려 준다.
7. **음성 대조군.** 진단 0건을 믿지 않는다. type function 결과가 `*error-type*`·never 로 무너지면 모든 검사가 조용히 통과한다(X1, S1, B3). 같은 파일에 반드시 잡혀야 하는 줄을 하나 둔다.
8. **버전 열 기록**
   - 그 저장소 결정 기록과 테스트 머리에 잰 버전을 적는다(예: `luau 0.742, luau-lsp 1.70.1`).
   - 버전을 올리면 §1 의 5 를 한다.
   - 편집기(luau-lsp) 판과 CLI 판이 다를 수 있다(E4, X1, L3 이 판마다 다르다).

## §4 진단을 띄우는 패턴
status: verified · last-confirmed: luau 0.742 (0.734 동일), luau-lsp 1.69.0·1.70.1 · 근거: `snippets/tf-diag-only-pattern.luau`, `tf-diag-eval-sites.luau`, `tf-noalt-literal-compute.luau`

```luau
type function MustBeSingleton(t: type): type
	if t.tag == "singleton" then
		return types.singleton(true)
	end
	print("MustBeSingleton: expected a literal type, got " .. t.tag)
	return types.never
end
type Checked<T> = { __check: MustBeSingleton<T> }
```

- 실패하면 `print(메시지)` 를 하고 `types.never` 를 돌려준다. 사용 자리에 `TypeError: <메시지>` 가 뜬다. 같은 줄에 "Expected this to be unreachable" 이 함께 뜬다.
- 성공 시에는 트리비얼한 표식(`types.singleton(true)`)을 별도 필드(`__check`)에 싣는다. 원본 `T` 는 type function 을 거치지 않게 둔다.
- 검사는 반환 타입, 필드 타입, 캐스트처럼 대조가 일어나는 자리에서만 평가된다. `any` 를 대입한 주석이나 제네릭 몸통 안의 지역 별칭에서는 0건이다(D4).
- 같은 인스턴스의 메시지는 처음 평가한 자리에 한 번만 뜬다(D3).

## §5 사실 정정 (원천별, 전달용)
status: verified (각 줄의 스니펫) · 측정: luau-analyze 0.734·0.742, luau-lsp 1.69.0·1.70.1, 2026-11-10

각 저장소 세션에 그대로 전달할 수 있게 원천 경로를 달았다. "미재현"은 틀렸다는 뜻이 아니라 최소 꼴에서 재현되지 않았다는 뜻이다.

**quad**
| 원천 | 원래 서술 | 실측 | 근거 |
|---|---|---|---|
| `.claude/base/typing-limits.md:421` (§5), `:72`; `.claude/audit/type-store-index-keyof/REPORT.md:24-28` | type function 은 바깥 타입 별칭을 참조하지 못한다 | 참조할 수 있다(제네릭 별칭은 `Box(t)` 로 호출). 바깥 **지역 변수**만 안 된다. 다른 모듈 별칭은 지역 별칭으로 받는다 | `tf-env-outer-alias-ok`, `tf-cross-module.sh` M5 |
| `.claude/base/typing-limits.md:1161` (8.22) | `types.optional` 은 없다 | 있다(`Opt<number>` → `number?`) | `tf-env-outer-alias-ok` |
| `.claude/base/typing-limits.md:1115-1117` (8.18 제목·첫 문단); `type-version-check/src/init.luau:142-143`; `quad-roblox-types/src/Surface/init.luau:15-16`; `.claude/base/surface-plan.md:38` | type function 안에서 pcall 은 쓸 수 없다 | luau-lsp **1.69.0 만** 그렇다. quad 핀인 1.70.1 과 0.734·0.742 는 pcall 이 되고, `parameters()` 같은 `types` API 에러도 잡는다. Surface 의 "멤버 하나가 죽으면 클래스 전체가 never" 는 1.70.1 에서 pcall 로 막을 수 있다 | `tf-env-pcall-available` |
| `.claude/base/typing-limits.md:69` (§0); `.claude/luau-test/done/23-…luau:16-18`; `type-version-check/src/init.luau:128-129`; `quad-types/src/init.luau:272` | `error()` 는 type function 이 버려져 진단이 안 뜬다. `print` + `never` 만 보인다 | 네 판 모두 `error()` 메시지가 "errored at runtime: F:<줄>: …" 로 보인다. 다만 never 불일치가 덧붙고 호출마다 반복된다. `print` + `never` 가 더 깔끔하다는 권고는 유효하다 | `tf-diag-error-vs-print` |
| `.claude/base/typing-limits.md:1119-1121` (8.18 둘째 문단·정정), `:1160` (8.22 프라이밍); `quad-base/test/spec.versioncheck.luau:10-17` | 수출 type function 은 프라이밍해야 한다 | 1.69.0 + 모든 FFlag 일 때만이다. 1.70.1 에서는 `LuauDoNotExportBrokenTypeFunction` 이 없어져 프라이밍 없이 평가된다. 그 플래그를 주면 "Unknown FFlag" 경고가 난다. 프라이밍은 해가 없으니 1.69.0 지원 동안 둬도 된다. spec.versioncheck 의 "pcall 때문에 평가 안 됨" 설명은 낡았다 | `tf-cross-module.sh` M1–M3 |
| `.claude/base/typing-limits.md:461-524` (§6); `.claude/luau-test/done/23-…luau:23-29`; `quad-types/src/init.luau:919` | 패스스루만 해도 이후 제네릭 self 체이닝이 조용히 깨진다(이력 때문) | **미재현**(다섯 꼴 × 네 판). 실물 `Quad` 를 패스스루하면 S1(직렬화 실패: `CheckReservedKeys<keyof<T>>`)로 `AddPlugin` 키가 사라진다. 원인 후보는 이력이 아니라 직렬화다 [추정] | `tf-passthrough-chaining`, `tf-serialize-unsupported-arg` |
| `.claude/base/typing-limits.md:1055-1058` (8.14) | `<U>(self: Ref<U?>) -> U` 로는 nil 을 벗길 수 없다(unknown) | 메소드 제네릭은 맞다. 자유 함수 `unwrap<U>(r: Ref<U?>): U` 는 된다 | `tf-noalt-stripnil` |
| `.claude/base/quad-types-plan.md:263-267`; `.claude/luau-test/done/23-…luau:27-29` | (plan) 주석만으로 평가된다 / (test 23) 필드를 참조해야 평가된다 | 둘 다 부분적이다. 값이나 캐스트가 대조되는 주석은 평가되고, `any` 를 대입한 주석은 평가되지 않는다 | `tf-diag-eval-sites` |
| `.claude/base/typing-limits.md:944-951` (8.10) | `index<>` 파라미터는 연산자 앞에서 unknown | 최소 꼴(기본 한도)에서 미재현. test.sh 플래그 조건일 수 있다. described 로 둔다 | B4 |

**stl-luau**
| 원천 | 원래 서술 | 실측 | 근거 |
|---|---|---|---|
| `.claude/papers/03-tuple.md:23`; `.claude/research/type-function-experiment/README.md:25-29` | `error()` 대신 `print` + `types.never` 를 써야 진단이 보인다 | 0.734·0.742·lsp 1.69.0·1.70.1 모두 `error()` 메시지가 보인다(conventions.md:84 ③ 이 맞다) | `tf-diag-error-vs-print` |
| `.claude/conventions.md:84` ③ "옛 버전은 `print()` + `types.never`" | 옛 버전에서는 `error` 가 안 뜬다 | 0.734 와 luau-lsp 1.69.0(내장 판)도 뜬다. 안 뜨던 판은 그보다 앞이다 [추정: lsp 내장 0.729 무렵] | `tf-diag-error-vs-print` |
| `.claude/conventions.md:84` ② | 한 번 통과한 타입은 제네릭 self 체이닝이 깨진다 | 미재현(quad §6 줄 참고) | `tf-passthrough-chaining` |

**tbox**
| 원천 | 원래 서술 | 실측 | 근거 |
|---|---|---|---|
| `packages/tbox/CLAUDE.md:120-121` | 정적 타입이 옵션 테이블의 모르는 키를 못 잡는 것은 `Types.Merge` 가 만드는 테이블이 닫혀 있지 않아서다 | Merge 탓이 아니다. 새 솔버는 손으로 쓴 테이블 타입과 교집합에서도 리터럴의 남는 키를 검사하지 않는다 | `tf-noalt-merge` |
| `packages/tbox/CLAUDE.md:150`; `src/types.luau:105-106` | 교집합(`&`)이 `?` 와 섞이면 깨진다 | 최소 꼴 `(A & B)?` 는 0.734·0.742 에서 동작한다(대입·거부 모두 정상). 깨지는 꼴이 따로 있다면 재현 파일이 필요하다 | `tf-noalt-merge` |
| `docs/code-review-2026-10-05.md:20-21` | `luau-analyze --fflags=LuauDoNotExportBrokenTypeFunction=false` 로 확인했다 | luau-analyze 에서는 효과가 없다. 0.734 는 그 플래그를 받지만 프라이밍 안 한 함수도 원래 평가하고, 0.742 는 "unrecognized flag" 경고를 낸다. 결과는 플래그 없이 돌린 것과 같다 | `tf-cross-module.sh` M1; RESULTS.md |
| `packages/tbox/scripts/analyze.luau:24-32`; `.vscode/settings.json:7-8` | `--flag:LuauDoNotExportBrokenTypeFunction=false` 를 준다 | tbox 핀 1.69.0 에서는 필요하다. 1.70.1 로 올리면 "Unknown FFlag" 경고만 나고 분석은 계속된다. 그때 지우면 된다 | `tf-cross-module.sh` M2–M3 |

**luau-kb 자신**
- `snippets/RESULTS.md` 의 "`luau-analyze` 에는 `--fflags` 같은 플래그 옵션이 없다"는 틀렸다. 0.734·0.742 모두 `--fflags=이름=값` 을 받는다(`--help` 에는 없다). 0.742 는 모르는 이름에 경고를 낸다.

## §6 실제 사용처
status: described · 원천: 각 저장소 소스(2026-11-10 기준)

| 저장소 | type function | 위치 | 용도 |
|---|---|---|---|
| quad | `StripNil` | `quad-types/src/init.luau:122` | 결과 합성(P1, `Ref:Unwrap`) |
| quad | `CheckReservedKeys` | `quad-types/src/init.luau:275` | 진단(P5 주석 자리), `keyof<T>` 만 받음(S1·S3 회피) |
| quad | `CheckVersion` | `type-version-check/src/init.luau:141` | 진단(P4), `_Prime` 프라이밍(:235) |
| quad | `Build(mode, cls, policy)` | `quad-roblox-types/src/Surface/init.luau:74` | 결과 합성(P9), 3.4.0 표면 전체 |
| stl-luau | `View`, `Entries` | `src/Trait/init.luau:108,176` | 결과 합성(P8). 2026-11-09 실험 패키지로 내림(`papers/08-trait-retrospective.md:153`) |
| tbox | `Static`, `StaticName`, `TObjectPropsFlatten`, `MergeInner`, `UnionInner`, `GetTupleType`, `StaticTuple`, `StaticNameTuple` | `packages/tbox/src/types.luau:6-202` | 결과 합성(P2, P3, P7), 공개 API |
| tbox | `CheckMergeable`, `CheckIsSingleton` | `src/schema/json/merge.luau:17`, `src/schema/singleton.luau:13` | 진단(print + never) |
| tbox | `PartialStatic` | `src/schema/json/partial.luau:13` | 결과 합성(P2) |
