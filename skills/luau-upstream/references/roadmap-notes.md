# roadmap-notes — 지금 진행 중인 큰 변화

> **last-checked: 2026-11-10** (luau 0.746 / luau-lsp 1.70.1 / StyLua 2.6.0 / rojo 7.7.1 / rfcs master 5fcbb5a). 이 파일은 빨리 낡는다. 30일이 지났으면 답하기 전에 `sources.md` 대로 다시 본다.

## 이 파일이 답하는 질문
- Q1 최근 luau 릴리스에서 무엇이 바뀌었나(0.735–0.746)?
- Q2 `class` 는 재귀 타입 문제를 풀어 주나?
- Q3 새 기능은 CLI 에서 Roblox 엔진까지 얼마나 걸리나?
- Q4 type function, 솔버, 그 밖의 RFC 는 어디로 가고 있나?

## 목차
- §1 luau 릴리스 요약 (0.735–0.746)
- §2 class 와 재귀 타입
- §3 CLI → Roblox 엔진 시차
- §4 RFC 현황 (상태별)
- §5 luau-lsp, StyLua, rojo
- §6 다음 점검 때 볼 것

---

## §1 luau 릴리스 요약 (0.735–0.746)
status: described · 출처: `https://github.com/luau-lang/luau/releases/tag/<ver>` (태그 페이지 날짜)

| 판 | 날짜 | 타입 솔버·검사 | 문법·실험 | 깨짐·주의 |
|---|---|---|---|---|
| 0.735 | 08-21 | type function 런타임 힙 한도 설정 | — | — |
| 0.736 | 08-28 | 테이블 리터럴 안 람다 일반화 개선 | 순환 require 확장 | — |
| 0.737 | 09-04 | `f<<T>>` 의 타입 인자를 검사(#2491). 인덱서 제네릭이 비봉인 테이블로 새지 않음. 일반화 재귀 한도 ICE 수정 | class: 생성자가 타입 시스템에 통합. **`if local` 문장 프로토타입** | require 순환 길이 한도 제거. `keyof` 결과가 사전순 |
| 0.738 | 09-11 | 읽기 전용 인덱서 추론 개선(#2669). type function 상태 유지(#2707 모듈 간 too complex) | — | — |
| 0.739 | 09-18 | **제네릭 몸통 검사 강화**(#2733: `call<T>(fn: (T)->T)` 안의 `fn(nil)` 을 잡음) | `if local` 식(실험) | — |
| 0.740 | 09-25 | 함수 정규화 버그, 큰 타입 ICE 수정 | exact table 실험(→ 10-28 RFC 닫힘). `if local` 플래그가 `LuauExperimentalIfLocalSyntax` 로 | — |
| 0.741 | 10-02 | `typeof(x :: T)` 충돌 수정 | — | C API: `lua_setbuffercage` → `lua_setmemorycage` |
| 0.742 | 10-10 | **#3020 병렬 검사 데이터 경쟁 수정**. 통합기 재작성 규칙, strict 스코프, `~nil` 정제 단순화 | `coroutine.finally` 정식 | 0.734 → 0.742 에서 S2·S13·S14·S16 이 고쳐짐(에러 증가 방향) |
| 0.743 | 10-16 | 읽기 전용·쓰기 전용 속성 에러 문구 개선 | — | `-g2` 에서 const 지역이 지역·업밸류로 안 남음 |
| 0.744 | 10-23 | 폭 서브타이핑이 nil 을 끼워 넣지 않음(#2625, #2644). nonstrict 꼬리 호출 팩 수정 | class private 필드 런타임 | — |
| 0.745 | 10-30 | 부정 교집합 정규화. 중간 크기 테이블 리터럴 분석 폭주 수정 | **`while local` / `while const`**(실험) | 임베딩 API: `lua_EmbedderGc` 가 int 반환 |
| 0.746 | 11-07 | 동등 제약의 불필요한 순환 제거. **테이블이 아닌 것을 순회하면 에러**(#3090). type function 안 전역이 바깥 추론에 영향 없음, 에러 보고 | `while local` 지원 발표. class 상속 생성자 에러 | 실측 변화: S11 고쳐짐, `{ v: T } & {}` 추론 풀림, 유니온 순회 위양성(N1) — `watchlist.md` §2 |

- 다가오는 깨짐: **정수 타입 철회.** rfcs PR #269(2026-10-29, 열림)는 "746 또는 747 이 정수 지원을 포함한 마지막 릴리스" 라고 적었다. `integer` 라이브러리나 타입을 쓰는 코드가 있으면 다음 판에서 깨진다. Roblox 에서는 켜진 적이 없다.

## §2 class 와 재귀 타입
status: described · 출처: RFC `syntax-classes.md`(병합 2026-04-27), rfcs PR #242(classes mega-RFC, 2026-11-04 갱신), luau 이슈 #2380, RFC `relax-recursive-type-restriction.md`(병합 2025-03-05), rfcs#11 닫는 댓글(2026-10-28)

- **사용자 관찰**: class 도입이 재귀 타입 해결을 가속하고 있다. **업스트림 문서로는 직접 근거를 찾지 못했다.**
  - class RFC 의 동기는 OOP 편의, `setmetatable` 추론의 어려움, 성능이다. RFC 본문과 PR #191·#242 토론에 "recursive" 언급이 없다.
  - **제네릭 class 는 범위 밖**이다("별도 RFC 예정", 아직 없음). 그래서 `Foo<T>` 가 `Foo<U>` 를 돌려주는 모양(S7)은 class 로 풀리지 않는다.
  - 재귀 제한 완화 RFC 는 2025-03 에 승인됐지만 구현이 없다. master 의 `TypeChecker2.cpp` 는 여전히 "Recursive type being used with different parameters" 를 낸다. #2380 에서 메인테이너가 "has not been implemented yet" 이라 했다(이슈 열림).
- **간접 연결은 있다**(추론, [제안] 등급)
  - class 타입은 **명목 타입**이고, 서로 참조하는 class 를 미리 선언으로 허용한다. 자기 참조 OOP 타입이 구조적 재귀 별칭 확장을 거치지 않게 된다. 오늘 S5·S7·S8 을 밟는 "메소드 테이블 + 자기 참조" 설계의 상당수가 class 로 옮기면 그 경로를 피할 수 있다.
  - shared self types RFC 가 2026-10-13 에 삭제됐다("구현하지 않음"). class 가 그 대안이다.
  - exact table RFC 를 닫으며 메인테이너가 "반공변 자리의 재귀 자기 참조" 를 막힌 문제로 꼽고 F-bounded polymorphism 을 해법 후보로 들었다. 제네릭 제약 RFC 초안(#266, 2026-10-22)이 있지만 미완이다.
- **설계 함의**
  - 재귀 타입 한계를 피하려고 지금 공개 API 를 비틀지 않는다(완화되면 선언 그대로 풀린다, `watchlist.md` S7 "불필요").
  - 새 OOP 표면을 설계할 때는 class RFC 의 모양(명목 타입, `public` 필드, `Name { … }` 생성, `__init` 대신 정적 생성자)과 충돌하지 않게 한다. 한 저장소는 이미 이 이유로 이름 `Class` 를 피했다.
  - class 구현은 `Debug*` 플래그 뒤에서 매주 진척된다(0.737 생성자 타입, 0.744 private 필드, 0.746 상속 생성자). 런타임 일부가 이미 있다는 점은 [구현] 근거지만, 엔진 반영 일정은 없다.

## §3 CLI → Roblox 엔진 시차
status: described · 출처: Roblox 주간 업데이트 `https://create.roblox.com/docs/updates/2026-MM-DD.md`, DevForum 공지, `https://clientsettingscdn.roblox.com/v2/settings/application/PCStudioApp`·`PCDesktopClient` (2026-11-10)

| 종류 | 경로 | 시차 실례 |
|---|---|---|
| 솔버 버그 수정 | OSS 태그와 같은 주에 Roblox 주간 노트에 실림 | 0–1주. 제네릭 몸통 수정: Roblox 09-14 주 / OSS 0.739 09-18. 명시 인스턴스화 검사: 08-31 주 / 0.737 09-04 |
| 새 문법 | `DebugLuau*` 플래그(CLI 도 꺼짐) → `LuauExperimental*`(CLI 는 켜짐) → **Studio 베타**(옵트인) → 공지 없는 정식 반영 | `if local`: CLI 0.737(09-04) → Studio 베타 10-06(약 1개월) → 라이브 미정. `const`: RFC 병합 02-24 → 라이브 약 03 월(`FFlagLuauConst2=True`) |
| 새 솔버 | 분석기만 바뀌므로 라이브 서버와 무관 | 2025-11-20 정식(nocheck/nonstrict 기본), strict 스크립트가 있는 플레이스는 옵트아웃 상태, 옛 솔버는 "2026 년까지" 유지 |
| 정수 타입 | 엔진에서 켜진 적 없음 | 철회 진행 중 |

- 라이브 서버(RCC)의 플래그는 공개되지 않는다. "라이브" 는 `PCDesktopClient` 플래그로 추정한 것이다.
- 정책 함의: CLI 판정만으로 Roblox 코드에 새 문법을 쓰면 라이브 게임에서 스크립트가 통째로 로드되지 않을 수 있다. `syntax-adoption.md` 의 C4 를 반드시 본다.

## §4 RFC 현황 (상태별)
status: described · 출처: `https://github.com/luau-lang/rfcs` master `docs/`, 열린 PR 목록(92개, 2026-11-10)

| 상태 | RFC | 메모 |
|---|---|---|
| 구현됨 | `const-keyword`(02-24), math 상수, `recursive-type-restriction`(2021) | — |
| 승인(병합), 미구현 또는 진행 | `syntax-classes`(04-27, Debug 플래그로 진행), `relax-recursive-type-restriction`(2025-03-05, 구현 없음), `export-keyword`(04-27), `support-for-cyclic-requires`(06-02), `@self` 예약(07-17), UDTF 에러 처리·pcall(08-03), `coroutine.finally`(10-16, 구현됨) | 백트래킹 금지가 10-15 부터 사안별로 풀림 |
| 승인 뒤 철회 | `type-long-integer`(02-12 병합 → PR #269 철회 제안), shared self types(10-13 삭제) | — |
| 제안(열린 PR) — 문법 | **#238 `if local`/`while local`**(beta, prototyping), **#242 classes mega-RFC**(상속 `open`, 생성자, private 필드), #216·#267 class 대안, #260 구조 분해, #258 import, #255·#197 match, #219 labeled break(prototyping), #232 enum, #275 try/catch(11-05), #192 루프 변수·파라미터 const, #277 함수 선언 기본 const(11-09) | — |
| 제안 — 타입 | #266 제네릭 제약(초안), #50 제네릭 제약(2024), #122 `noinfer`, #211 타입 팩 별칭, #123 명목 타입, #173 unique 타입 | — |
| 제안 — type function | #165 `keyof`/`index`/`rawget` 의 read/write 키, #248 내장 type function 노출, #270 extern 타입 이름으로 찾기, #116 타입 팩, #117 가변 인자, #113 문자열 키 | `setreadindexer`("separate read/write types for indexers")를 직접 다루는 RFC 는 없다. UDTF RFC 문서에는 API 가 적혀 있지만 master 는 아직 에러를 낸다 |
| 닫힘 | **#11 exact table**(10-28, "진행하지 않기로") | 리터럴의 남는 키 검사(tf R3)는 이 모양으로는 오지 않는다 |

## §5 luau-lsp, StyLua, rojo
status: described (릴리스 노트) / verified (문법 파싱, `syntax-adoption.md` §2)

- **luau-lsp**: 1.70.0(09-20, 번들 luau 0.739), **1.70.1(09-27, 번들 0.740)이 최신**. main 에 "Sync to upstream Luau 0.742" 가 있지만 릴리스 전이다. 그래서 CLI 0.742 에서 고쳐진 S2 가 lsp 에선 bug 이고, `while local` 을 못 읽는다. `luau-lsp.fflags.sync`(기본 true)로 Roblox 의 `Luau*` 플래그를 받아 쓰고, `enableNewSolver` 기본은 false 다.
- **StyLua 2.6.0**(10-10): `if local`/`if const` 지원(full-moon 3.0.0). `while local`, `class` 는 못 읽는다. full-moon 의 Unreleased 도 비어 있다. `f<<T>>` 는 2.4.0, `const` 는 2.5.0 부터.
- **rojo 7.7.1**(10-02): syncback, websocket+MessagePack, `.jsonc`. Luau 문법과 무관(파싱하지 않는다).

## §6 다음 점검 때 볼 것
status: described

- 0.747: 정수 지원 제거 여부(#269), `while local` 이 실험 표시를 뗐는지, class 진척.
- luau-lsp 1.71(또는 1.70.2): 번들 0.742 이상이면 S2 와 lsp 판정 차이가 사라지는지 `check_snippets.py --lsp` 로 확인.
- Roblox: `if local` 베타의 롤아웃 퍼센트(`FIntLuauIfLocalBetaFeatureRolloutPercent`)와 클라이언트 플래그 등장.
- rfcs #238 병합 여부, #242 병합 여부, 제네릭 class RFC 등장.
- #2380 에 구현 PR 이 붙는지.
