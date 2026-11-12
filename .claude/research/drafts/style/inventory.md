# Luau 스타일 인벤토리 — 네이밍·코드 품질·관용구

작성 2026-11-10. 대상은 quad, stl-luau, tbox, table-sim, devplorer, rbvm, moonwave-luau 의 에이전트 문서와 소스다(읽기 전용).
약칭은 `stl`=stl-luau, `tsim`=table-sim, `devp`=devplorer, `moon`=moonwave-luau 이다.

태그 뜻은 다음과 같다.
- **공통**: 두 곳 이상이 같은 규칙을 갖고 반대하는 곳이 없다 → `rules/luau-core.md` 또는 스킬 후보.
- **고유**: 한 저장소의 설계에 매인 규칙 → 그 저장소 `.claude/rules/` 에 남긴다.
- **충돌 → D-xx**: 입장이 갈린다 → `.claude/base/decisions/`.
- **조건부**: 조건을 붙이면 모순이 사라진다.

실태 수치(예: `const` 1,963)는 `/tmp/cd-exp/stats.py` 로 소스 사본을 센 값이다.

목차
1. 네이밍 케이스
2. 모듈 패턴과 파일 배치
3. 객체 모양: 메서드 대 함수
4. 에러 처리
5. nil·옵셔널·구멍
6. 테이블 생성·컨테이너 관용
7. 문법 관용(`const`, `if`-식, 삼항)
8. 타입 작성
9. 주석과 문서화
10. 포맷
11. require
12. 테스트 관용
13. 성능 관용
14. 검증과 보고
15. 할 일·마커

---

## 1. 네이밍 케이스

| 규칙 | 출처 | 태그 |
|---|---|---|
| 타입은 PascalCase | stl `conventions.md:18`, quad `architecture.md:682+`, devp `conventions.md:77` | 공통 |
| `require` 받은 모듈 지역은 PascalCase(`local Common = require("./Common")`) | stl `:25`, 전 저장소 실태 | 공통 |
| 지역 변수·지역 함수는 camelCase | stl `:24`, devp `:77` | 공통 |
| 종류 술어는 `isX` camelCase(`stl.isArr`, `isState`, `Kind.isSchema`) | stl `:21,29`, quad `architecture.md:727-729`, tbox `packages/tbox/CLAUDE.md:114` | 공통 |
| `_` 접두 필드는 내부 계약, 언제든 바뀜 | quad `architecture.md:739-742` | 공통(반대 없음) |
| 값을 만들거나 감싸는 함수(생성자·팩토리)는 PascalCase | stl `:19`, quad `:688`, tbox `CLAUDE.md:77` | 공통(실태 예외: tsim `Bag.new`) |
| 네임스페이스 연산·메서드의 케이스 | stl Pascal 전부 / quad 타입 고유 어휘 Pascal, 범용·엔진 camel / tbox 메서드 camel / tsim camel / devp 혼합 | **충돌 → D-09** |
| 불리언 연산은 `Is…`, 형용사 하나(`Empty`, `Equal`)만 접두 없이 | stl `:22,29` | 고유(stl) |
| 어휘 표: `Has` 키, `Contains` 값, `Merge`, `Concat`, `…Desc`, `At`/`IndexOf` | stl `:32` | 고유(stl) |
| `FromTable` 은 복사, `Adopt` 는 입양 | stl `:100` | 고유(stl) |
| `type…` 이름은 Lua 내장과 겹쳐 피함(`TokenOf`) | stl `:31` | 공통 후보(일반 사실: `type`/`typeof` 내장과 혼동) |
| 파일 이름 PascalCase / 소문자 | stl·quad·tsim·devp Pascal / tbox·rbvm 소문자 | **충돌 → D-09** |
| 타입 `T` 접두(`TNumber`) | tbox 실태 130/158 | 고유(tbox) |
| 상수 대문자(`VALUE`, `NEXT`) | stl `:23` | 고유(stl, 반대 없음) |
| 테스트 파일 `spec.<module>.luau` | stl `:27`, quad `test/spec.*`, moon `conventions.md:92` | 공통(tbox 는 `test/schema/*.luau` 미러, devp `<이름>.spec.luau`) — 조건부: "저장소 관행" |
| 데이터 필드 이름이 메서드 이름과 겹치지 않게(인스턴스 필드가 `__index` 를 가림) | tbox `packages/tbox/CLAUDE.md:113` | 공통 후보(메타테이블 쓰는 모든 곳의 일반 사실) |
| 공개 API 이름은 바꾸지 않는다(호환성) | moon `conventions.md:59-61`, quad CHANGELOG 규약 | 공통 |

## 2. 모듈 패턴과 파일 배치

| 규칙 | 출처 | 태그 |
|---|---|---|
| 파일 1행 `--!strict`, 그 다음 머리 블록 주석(무엇·왜) | stl `:80`, devp `:75`, moon `:62`, 실태 quad 67/67·tsim 67/67·tbox 38/40 | 공통 |
| 모듈 끝에서 테이블 하나를 `return` | 전 저장소 실태 | 공통 |
| stl 모듈: `const Kind = Trait.Struct(...)` → top-level 함수 → 등록 → `Kind.Seal({…})` | stl `:38` | 고유(stl) |
| tbox 모듈: `Kind.Kind(tag, methods, optionNames)` + `table.freeze({ factory, kind })` | tbox `packages/tbox/CLAUDE.md:96-98` | 고유(tbox) |
| 콜러블 네임스페이스(`Arr(...)`, `__call`) 금지 — 제네릭 생성자가 타입 인자를 잃음 | stl `:38` | 공통 후보(타입 사실) |
| 기능마다 폴더, 입구는 `init.luau`. 혼자 서는 작은 모듈은 폴더 안 만듦 | devp `:64-68`, quad 폴더 재배치 경험(devp `:62` 인용) | 공통 후보 |
| 층을 쌓고 아래층이 위층을 부르지 않는다(순환 금지) | devp `:69`, stl `:122,130` | 공통 |
| 엔진 무관 로직은 Roblox API 없이 짜서 `luau` CLI 로 돌린다 | tsim `:96`, devp `:53`, quad mock(`architecture.md:808-819`) | 공통 |
| 로드 시점에 Roblox 전역(`Vector3` 등) 참조 금지, 판별은 `typeof(v) == "Vector3"` | tbox `CLAUDE.md:149-154` | 조건부(Roblox 데이터타입을 다루는 순수 라이브러리) |
| 같은 본문을 이질적 타입끼리 공유하지 않는다(공유 가능: 데이터·순수 술어) | quad `conventions.md:59-79` | 공통 후보 |
| 관측된 문제에만 구조를 쓴다 | quad `conventions.md:50`, tsim `:70`, devp `:50` | 공통 |

## 3. 객체 모양: 메서드 대 함수

| 규칙 | 출처 | 태그 |
|---|---|---|
| 메타테이블 없는 테이블 + 네임스페이스 함수만 | stl AB `:37`(전환 중) | **충돌 → D-11** |
| 메서드 객체 + 같은 이름 네임스페이스 함수, 타입을 바꾸는 연산은 메서드로 두지 않음 | stl BI `:36` | **충돌 → D-11**(진행 중) |
| 프리미티브 = 메타테이블 + Pascal 콜론 메서드 | quad `architecture.md:690-712` | 고유(quad) |
| 주입·재대입 값은 매번 `Module.x` 로 읽고 캡처·위임 래퍼 금지 | quad `:753-762`, devp `:71` | 조건부 → D-11 |
| 불변 함수는 뜨거운 루프에서 지역으로 받음 | stl `:147`(perf §14) | 조건부 → D-11 |
| 메서드 `self` 를 `any` 로 / 자기 반환은 `return self :: any` | tbox `packages/tbox/CLAUDE.md:111`, stl `:42` | 공통 후보(솔버 우회. 버전 의존 → luau-types) |
| 값 프리미티브에 `__tostring` | quad `architecture.md:502-510` | 고유(quad) |
| 메타메서드는 `__index` 로 상속되지 않음 — 파생 메타테이블은 각자 단다 | quad `:509` | 공통(언어 사실) |

## 4. 에러 처리

| 규칙 | 출처 | 태그 |
|---|---|---|
| 에러 메시지·식별자는 영어 | 7곳 전부 | 공통 |
| 메시지 리터럴을 raise 줄에 통째로(grep 가능), 포맷 헬퍼 금지 | quad `architecture.md:462-469` | 공통 후보 |
| 손으로 센 `error(msg, 2|3)` 금지 — `-O2` 인라인에서 위치 소실(재현) | stl `:134`, quad `:433-450,520-529` | 조건부(라이브러리) → D-10 |
| 내부 불변식 위반은 `error(msg, 1)`(그 자리를 가리킴) | quad `:408,446` | 공통 |
| 형식: `QuadNNNN Subj: reason (got X)` / `Module: 설명` / 소문자 시작 | quad / stl / tbox | 고유 → D-10 |
| 새 raise 자리마다 메시지 + 정확한 사용자 줄 단언 테스트, 줄은 `debug.info(1,"l")+1` 을 그 자리에서 | stl `:138` | 조건부(라이브러리) |
| 예외 안전성은 약속하지 않음 — "관측 — 계약 아님" 표기 | stl `:139`, quad `architecture.md:531-555` | 공통 |
| `pcall` 로 감싸 부기 복구하지 않음 | quad `:533-534` | 고유(quad 설계) |
| 검증 함수는 `(ok, err)` 반환 | devp 실태(`ArgCheck.check`) | 고유 |
| 사용자 `Kind` 메서드 반환 규약을 그 자리에서 검사(`false` 반환이 모든 값을 통과시키는 사고) | tbox `packages/tbox/CLAUDE.md:122-124` | 고유 |

## 5. nil·옵셔널·구멍

| 규칙 | 출처 | 태그 |
|---|---|---|
| 구멍은 타입에 `T?` 로 드러낸다 | stl `:99` | 공통 후보 |
| `#` 를 믿지 않고 길이를 따로 든다(`n`), 구멍 처리 방식을 함수 주석에 적는다 | stl `:97-98` | 고유(stl 표현) / 공통 사실(`#` 의 경계는 구멍에서 비결정, 0.742 에서 바뀜 — stl `mise.toml:18`) |
| 맵의 `nil`·NaN 키: 넣기는 에러, 조회·삭제는 "없음" | stl `:108` | 고유 |
| `x or y` 기본값은 허용, `a and b or c` 는 금지 | quad `architecture.md:772-781`, stl `:90` | 공통 |
| 센티널 `None` 으로 "명시적 없음" 표현 | quad(`props.Modifier or None`) | 고유 |
| `any` 를 인덱싱한 뒤 `~= nil` 좁히기 함정 | quad `typing-limits.md` 8.24 | 공통(→ luau-types) |
| NaN 은 에러(사용자 줄), 나머지는 `math.fmod` + 음수 보정 | stl `:107` | 고유 |

## 6. 테이블 생성·컨테이너 관용

| 규칙 | 출처 | 태그 |
|---|---|---|
| 벌크는 `table.move`/`table.create` | stl `:146` | 공통 후보(성능 사실) |
| 가변 인자는 `table.pack` 대신 `select` 루프(1.6~2.3배) | stl `:146` | 공통 후보 |
| 노드 칸은 생성자에 다 적는다(나중 대입 3배), 이름 필드 대신 번호 칸(2.3배) | stl `:127` | 고유(stl 노드) / 공통 사실(테이블 모양) |
| 배열을 앞에서부터 `nil` 로 비우지 않는다(해시로 이동, 1.7배) | stl `:126` | 공통 후보 |
| 인스턴스 길이를 데이터 키와 같은 테이블에 두지 않는다(`{ data, size }`) | stl `:118`, `HashMap.luau` 머리 | 공통 후보 |
| 인스턴스를 `table.freeze` | tbox `:115` | 고유 |
| 겉표에 내장 함수 금지(`#a`, `table.clone(a)`, `table.freeze(a)`) | stl `:98` | 고유 |
| 가변 인자 내장(`math.max`)을 콜백으로 그대로 넘기지 않는다 | stl `:75` | 공통(일반 사실) |

## 7. 문법 관용

| 규칙 | 출처 | 태그 |
|---|---|---|
| `const` 사용 | 금지 rbvm / 기본 stl·tbox·tsim·devp / 문서상 quad | **충돌 → D-01** |
| `local const x` 금지(전역 대입이 됨, 실행) | stl `:89` | 공통 |
| `(` 로 시작하는 문장 금지(stylua 가 `const` 뒤 `;` 를 지움, 실행) | stl `:93` | 공통 |
| `if c then a else b` 식이 공식 문법 — `and/or` 로 고치지 말 것 | quad `architecture.md:766-771`, 실태 tsim 633·devp 644 | 공통 |
| `<<T>>` 는 명시 타입 인자 — 오타 아님, 유지 | rbvm `conventions.md:44-48`, tbox `:75` | 공통 |
| 모듈 스코프 `function name()`(앞선 `local` 없음)은 전역 대입 — 게이트가 `GlobalUsedAsLocal` 로 잡음 | quad `conventions.md:353-355`, `test.sh:16,34` | 공통 |

## 8. 타입 작성

| 규칙 | 출처 | 태그 |
|---|---|---|
| 모든 파일 `--!strict`(`.luaurc` 한 단어로 310→0건) | stl `typing-limits.md:105-124` | 공통 |
| 제네릭이 안 풀리면 `f<<T>>`, 캐스트는 차선 | stl `:81`, tbox `:75` | 공통 |
| 콜백을 넘길 땐 `f<<T>>` 나 파라미터 주석을 항상 | stl `:82` | 공통 |
| 한계 우회로 API/타입을 비틀지 않음(`any` 반환으로 열기 금지) | stl `typing-limits.md:60-64`(quad 출처) | 공통 |
| "진단 0건"을 믿지 않음 → 음성 대조군 | stl `typing-limits.md:65-67`, moon `:34-37`, tsim `:95` | 공통 |
| 타입 함수 정책 | quad / stl / tbox | **충돌 → D-04** |
| 오버로드 `&` 를 기본 구현 타입에 쓰지 않음(상류 결함 0건) | stl `:68` | 공통 후보(→ luau-types, 버전 의존) |
| 커스텀 파서 매개변수·반환 타입 전부 적기(빼면 거짓 에러) | moon `:114-115` | 고유(mrow) / 공통 사실(무주석 파라미터는 첫 사용으로 굳음 — quad `conventions.md:359`) |

## 9. 주석과 문서화

| 규칙 | 출처 | 태그 |
|---|---|---|
| 주석은 "왜"를 적는다 | tbox `:78`, rbvm `:10-13`, stl 모듈 머리 | 공통 |
| 주석 언어 | 영어 quad / 한국어 tbox·tsim·devp·stl / 혼합 rbvm | **충돌 → D-08**(공통 부분: 파일 언어를 따름) |
| 선언 설명은 `---` 문서 주석(luau-lsp 호버), `-- Ref:` 줄은 `---` 블록 **위** | quad `conventions.md:345` | 공통 후보(lsp 사실) |
| 게시 소스에 원장 번호만 남기지 않음 — 이유 문장 + `Ref:` 꼬리 | quad `:345` | 조건부(공개 패키지) |
| 큰 파일은 `--#region 이름` / `--#endregion 이름` | quad `:345`, 실태 stl 93·rbvm 19 | 공통 후보 |
| `-- stylua: ignore` 로 네임스페이스 표만 뺌(정확히 그 글자) | stl `:92` | 공통(사실: 글자가 정확해야 먹음) |
| GC·생명주기 코드의 의도적 패턴(`nop(gcHold)`, `__mode`)은 근거 주석이 정본 — 지우기 전 설계 문서 | rbvm `:50-57` | 고유 |
| 함수가 구멍을 어떻게 다루는지 주석에 | stl `:97` | 고유 |
| 관측과 계약 구분("관측 — 계약 아님") | stl `:139`, quad `architecture.md:549-554` | 공통 |

## 10. 포맷

| 규칙 | 출처 | 태그 |
|---|---|---|
| stylua 2.5.2, `--check` 가 게이트 | stl·moon·tbox·rbvm·tsim·devp | 공통(quad 는 설정 없음) |
| `syntax = "Luau"` 필수 | moon `stylua.toml:3-7`, tsim·devp `mise.toml` 주석 | 공통 |
| 저장소 루트에서 실행(하위 폴더면 설정을 못 찾아 `f<<T>>` 오염, 실행 재현) | tbox `:80-82` | 공통 |
| indent Tabs/Spaces, call_parentheses Always/Input | 6곳 갈림 | **충돌 → D-02** |
| `sort_requires` 는 `local` require 만 정렬 | rbvm `:39-42`(실행 확인) | 공통 사실 |

## 11. require

| 규칙 | 출처 | 태그 |
|---|---|---|
| `init.luau` 안 자기 폴더 파일은 `@self/`, `./` 는 폴더 형제 | stl, tbox `:95-113`, moon `:66-70` | 공통 |
| require 대상은 문자열 리터럴 | tbox `:146-147` | 공통 |
| 테스트 엔트리를 `init.luau` 로 짓지 않음 | tbox `:141-144`, moon `:71` | 공통 |
| 정적 검사가 require 경로 오류를 못 잡음 → 실제로 불러보는 테스트 | stl `architecture.md:307-330`, moon `:73-74` | 공통 |
| symlink 를 따라가지 않음 → 스테이징은 복사 | moon `:72`, tbox `mise.toml:31-42` | 공통 |
| `@game/` 절대 경로 | 금지 devp / 사용 tsim(72) | **조건부 → D-12** |

## 12. 테스트 관용

| 규칙 | 출처 | 태그 |
|---|---|---|
| 프레임워크 없음, `assert`/`error` + `print`, 엔트리 `tests/run.luau` | stl `:153`, moon `:91`, tbox `:121-123` | 공통 |
| 러너 | luau / luau+lute / lune 금지 | **충돌 → D-03** |
| 테스트 파일 끝에서 값 `return`(안 하면 `module must return a single value`) | stl `:154`, moon `:92` | 공통 |
| 경계 케이스 고정: 빈 것/한 개/뒤집힌 구간/범위 초과/음수 | stl `:156` | 공통 후보 |
| 눈에 안 보이는 것은 오라클 대조(이분↔선형, 힙↔정렬, 무작위 수백 회) | stl `:157` | 공통 후보 |
| 테스트 데이터가 우연히 맞지 않게(키 `1,2,3` 금지 → `10,20,30`) | stl `:158` | 공통 후보 |
| 새 타입 계약엔 음성 대조군 스파이크 + 기대 건수 tsv | stl `:155`, moon `:101-103` | 공통 |
| 특성화 테스트는 "지금 동작"을 고정(옳음 아님), 주석에 표시 | moon `:98-100` | 공통 후보 |
| 골든 변경 커밋에는 무엇이 왜 바뀌었는지 | moon `:95-97` | 고유 |
| 최소 mock(트리 + 프로퍼티 bag + 변경 시그널)으로 엔진 없이 | quad `architecture.md:808-819` | 고유(quad) / 공통 후보(엔진 무관 테스트) |
| `luau` 실행엔 메모리·시간 상한(`ulimit -v`, `timeout`), 돌연변이는 사본에서 | stl `:159-162` | 공통(환경 — 사용자 레벨 훅과 짝) |

## 13. 성능 관용

| 규칙 | 출처 | 태그 |
|---|---|---|
| 성능 주장은 실측으로, 숫자는 한 문서에 | stl `:144`, tsim `:75` | 공통 |
| 벤치는 실제 호출 형태, 래퍼 클로저 없이, 여러 번 재고 최소값 | stl `:145` | 공통 |
| 편의가 기본 경로를 느리게 만들지 않음(편의는 별도 이름) | stl `:143` | 공통 후보 |
| 메타테이블 인덱싱 세금 1.59배(-O2/codegen 2배까지) | stl perf §16·§18 | 공통 사실(→ luau-perf) |
| 루프 앞에서 `const data = self.data` | stl `:44`(perf §57, 1.45배) | 공통 후보 |
| 키 문자열을 상수 테이블 경유 대신 리터럴로(상수 접기, 7~11%) | stl `:40` | 공통 후보 |
| 검사·안전망을 넣을 땐 비용을 재서 판단(`Retain` 1.16배 → 검사 안 넣음) | stl `:111` | 고유(stl 판단) |
| 큰 실행은 `choom` 으로 감쌈(훅 강제) | tsim `:178-182`, quad 훅 | 공통(환경) |

## 14. 검증과 보고

| 규칙 | 출처 | 태그 |
|---|---|---|
| 게이트 진입점 하나, 판정은 exit code(통과 줄 수 세기 금지) | quad `conventions.md:348-352`, tsim `:92`, devp `:85`, moon `:81-82` | 공통 |
| 검증 범위를 구분해 보고: "타입·포맷만" / "스펙 통과" / "Studio 실측" | rbvm `CLAUDE.md:50-51`, tsim `:93-94`, devp `:86` | 공통 |
| 진단은 stderr — `2>/dev/null` 금지 | stl `architecture.md:106-107` | 공통 |
| 검사 기준 도구 | analyze / lsp / 둘 다 | **조건부 → D-06** |
| 버전 핀 | 0.734 / 0.742 | **충돌 → D-05** |
| 게이트를 고치면 일부러 한 번 깨뜨려 본다 | moon `:85-87` | 공통 후보 |

## 15. 할 일·마커

| 규칙 | 출처 | 태그 |
|---|---|---|
| 끝난 todos 처리 | 지움 stl·quad / 아래로 tsim / 취소선 devp | **충돌 → D-07** |
| 코드 `TODO` 는 이유 + 추적처, 공개 소스엔 번호만 남기지 않음 | quad `conventions.md:345,525`, rbvm 맨 `TODO` 15 | 조건부 → D-07 |
