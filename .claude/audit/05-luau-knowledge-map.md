# 05. Luau/Roblox 지식 지도와 Luau 스킬 세트 설계안

> 작성 2026-11-10. 대상: `/code/Projects` 전체(읽기 전용). 쓴 곳은 `claude-doctor/audit/` 와 `/tmp` 뿐.
> 근거 표기: `프로젝트/경로:줄`(줄은 `##` 제목 줄 번호 기준, 시점 2026-11-10). 프로젝트 접두어 `stl`=stl-luau, `quad`=quad, `qcc`=quad-changelog-check.
> 검증 표기: **[실행]** = 저장소에 재현 파일/게이트가 있고 이번 세션에서 내가 다시 돌려 확인, **[실측기록]** = 문서가 "실측"이라 하고 재현 파일이 따로 있으나 내가 재실행하진 않음, **[서술]** = 서술/추론만, **[Studio]** = Roblox Studio MCP 로 실측했다고 기록.

---

## 0. 한눈에 보는 결론

1. 지식은 **세 곳에 두껍게** 있다: quad `base/typing-limits.md`(1387줄, 8.1~8.43 번호 체계, 타입 시스템 한계의 사실상 정본), stl `base/typing-limits.md`(481줄)+`perf-measurements.md`(1698줄, 60절), qcc/quad `luau-test/`(스파이크 36개). 나머지(rbvm, moonwave, table-sim)는 각자 한 갈래의 **런타임/Roblox 엔진 실측**이다.
2. **중복·드리프트가 실재한다.**
   - `quad-changelog-check`는 quad의 **낡은 포크**다: `typing-limits.md` 1073줄 vs quad 1387줄(md5 다름), `luau-test/done` 파일명 36개 동일하나 06·17·23 등 내용이 다름. 스킬의 근거로 qcc 를 쓰면 안 된다(정본=quad).
   - 도구 핀이 갈렸다: **stl 은 luau 0.742**(0.734 의 `luau-analyze` 가 병렬 검사에서 힙 손상 — 상류 #3020), **quad·table-sim·moonwave·tbox 는 0.734**, luau-lsp 는 1.69.0/1.70.1 혼재(`stl/mise.toml` 머리 주석, `quad/mise.toml:12,15`, `table-sim/mise.toml:15-16`). 문서 속 "실측 수치"는 어느 버전 것인지 문장마다 다르다.
3. **모순/갈등 3건**(아래 §3): (a) 타입 함수 쓸까 말까, (b) 타입 검사기가 luau-analyze 냐 luau-lsp 냐, (c) lune 사용 여부(stl 은 금지, qcc README 는 "luau 또는 lune", tbox 는 lute).
4. **지식이 사실상 없는 영역**(스킬로 만들려면 신규 조사 필요): 타입팩/가변 인자 정리본, Roblox Instance/Enum/서비스 타입(실 API 타입 정의 지식), Actor/Parallel Luau, `@native`/`--!native` 사용 가이드, TestEZ/jest-lua, GC 튜닝 일반론. (§2 의 "공백" 표시)
5. 로컬 도구는 **모두 설치돼 있으나 `mise` shim 이 이 디렉터리에서는 버전 미지정으로 실패**한다. 설치 경로 직접 호출은 전부 동작(§1). 스니펫 하나를 실제로 돌려 "에러 기대 포함 CI" 프로토타입이 성립함을 확인했다(`.claude/audit/drafts/snippet-harness/`).

---

## 1. 로컬 도구 가용성 (실제 실행 결과)

| 도구 | 상태 | 확인 |
|---|---|---|
| `luau`, `luau-analyze` | 설치됨: 0.734, 0.742 (`/code/.local/share/mise/installs/luau/<v>/`) | PATH 의 `mise` shim 은 `No version is set for shim: luau` 로 **실패**(전역 기본 버전 없음, 프로젝트 `mise.toml` 밑에서만 동작). 직접 호출은 OK |
| `lune` | 0.10.5 (`installs/github-lune-org-lune/0.10.5/lune`) | `lune run x.luau` → `lune ok Lune 0.10.5+709` |
| `stylua` | 2.5.2 (`installs/stylua/2.5.2/stylua`) | 동작 |
| `luau-lsp` | 1.69.0, 1.70.1 | `luau-lsp analyze --flag:LuauSolverV2=true` 동작(`luau-lsp --version`=1.70.1 확인; `luau-analyze` 에는 `--version` 옵션이 없음) |
| `rojo` 7.7.0, `pesde` 0.7.4 | 설치됨 | 확인만 |
| `selene` | 없음 | stl 이 2026-09-21 의도적 폐기(`stl/mise.toml` 주석: `const` 파싱 불가) |
| `lute` | 로컬에 없음(`tbox/mise.toml:17` 에서만 핀) | — |
| 소스 | `stl/refs-ignoreme/luau` = 0.742(`8387cfb`), `quad-scratch/refs/luau` = 0.734(`3fc82b1`), `quad-scratch/refs/luau-729` | 소스 읽기는 `stl/.claude/research/luau-source/README.md` 가 1차 정리 |

**스킬 CI 용 래퍼 필요**: `mise exec luau@0.742 -- luau-analyze` 또는 설치 경로 직접 호출. (프로토타입 `check_snippets.py` 의 `tool()` 이 shim 실패를 감지해 설치 경로로 폴백 — shim 이 `--help` 에 exit 1 로 응답해 처음엔 이걸 정상으로 오판한 버그를 직접 밟고 고침.)

### 1-1. 직접 재현해 본 것 (이번 세션)

| 실험 | 결과 | 시사점 |
|---|---|---|
| `stl/.claude/audit/luau-solver-issues/1-annotation-bound-lost.luau` 를 0.742 새 솔버로 | 5줄만 에러, **4줄 무진단** → 문서의 "새 솔버 결함 1번" 재현 | 서술이 **[실행]** 으로 승격됨. 0.734 에서도 동일 |
| 같은 파일 `--solver=old` | 4·5 줄 둘 다 에러 | 문서의 "옛 솔버는 잡음" 재현 |
| `luau-lsp analyze --flag:LuauSolverV2=true` 같은 파일 | 5줄 에러(analyze 와 동일) | 이 파일에선 lsp=analyze. stl 이 말한 "lsp 가 덜 본다"는 대형 파일(`arr.luau`)에서의 관찰 → 일반화 금지 |
| stl `luau-solver-issues/*.luau` 8개를 new/old 로 | new: 1,2,1,0,3,1,1,9 / old: 2,2,2,2,4,7,3,4 건 | `3b` 는 new=0(결함 지속), `8` 은 new 가 더 많이 냄. **DRAFTS.md 가 "0.742 에서 고쳐져 뺄 것"이라 한 2번(`2-bare-lambda`)은 new=2 라서 파일만으론 판정 불가**(기대 줄 목록이 없음 → 스킬화하면 `bug-present` 표식이 필요한 이유) |
| tbox `CLAUDE.md:84-90` 의 "stylua 2.5.2 가 `f<<T>>(...)` 를 시프트로 조용히 오염" | `id<<number>>(1)`, `id<<{number}>>({1})`, `T.Unsafe<<number>>({a=1})` 셋 다 **변형 없음**(괄호 없는 `f<<T>> {…}` 는 `({…})` 로만 정상 변환) | **재현 안 됨** → 이 경고는 [서술] 로 강등. 다른 모양(여러 인자 등)에서만 날 수 있어 "재현 파일 없음" 상태. 스킬에 넣으려면 먼저 재현 파일화 |

---

## 2. 지식 인벤토리 표

품질 등급: **A**=원인까지 추적 + 재현 파일 + 버전 명시, **B**=실측 기록 있으나 파일/버전 미흡, **C**=서술·설계 의견 위주, **공백**=없음.
"정본 후보"=스킬로 증류할 때 1차 출처.

### 2-1. 타입 시스템

| 주제 | 어디에 (경로:줄) | 품질 | 검증 | 중복/모순 | 비고 |
|---|---|---|---|---|---|
| 타입 시스템 기초 | 없음(전부 "한계" 관점) | 공백 | — | — | 입문 서술은 어디에도 없다. 공식 문서 링크 모음으로 채워야 함 |
| 제네릭: 명시적 타입 인자 `f<<T>>` | stl `base/typing-limits.md:129-253`(3개 조용한 누수 + 해법), `:203`(콜백 주석도 제거) / quad `base/typing-limits.md:1087`(8.16), `:525-578`(§7 성립 확인) | A | **[실측기록]** stl `audit/arr-type-redesign/spikes/52,54`; quad `luau-test/done/*` | 같은 사실이 stl/quad 양쪽, 표현만 다름 | 정본=stl(최신, 0.742) |
| 제네릭 추론 결함(람다 상한 소실) | stl `typing-limits.md:290`(뿌리), `audit/luau-solver-issues/1-…luau`+`DRAFTS.md:1-40` | A | **[실행]**(§1-1) | stl `spikes/52` 가 감시 | 업스트림 보고는 **안 올림**(사용자 결정) |
| 제네릭 몸통 검사 안 됨(Subtyping.cpp:830-835) | stl `research/luau-source/README.md:1-30`, `.claude/audit/luau-solver-issues/3*.luau` | A(소스 줄까지) | **[실측기록]** Opus 가 소스 직접 빌드·수정판으로 확인 | 상류 #2733(2026-09-19 Closed)와 관계는 `sonnet-web.md:1-12`(요약 모델 경유라 본문 해석은 약함) | 0.742 에서 `3b` 여전히 0건 |
| 타입 함수 `types.*` | quad `typing-limits.md:50-83`(허용범위 규칙), `:461`(§6 체이닝 깨짐), `:1115`(8.18 pcall 불가), `:1154`(8.22 프라이밍), `:1323`(8.39); stl `papers/03-tuple.md:1-25`, `base/trait-system.md:99`; `stl/research/type-function-experiment/` | A~B | quad 는 `luau-test/done/16,12,15` **[실측기록]** | **모순 (a)**: 아래 §3 | 사용자 규칙: "진단 띄우는 데까지만" |
| 변성/서브타이핑(읽기전용 필드는 공변, 함수 타입 팬텀으로 불변 만들기) | quad `typing-limits.md:954`(8.11), `:1347`(8.42 방향별 마커); stl `typing-limits.md:1-30`(2026-10-12 불변 마커), `:388`(팬텀 모양), `:466`(공변 둘→교집합); qcc `luau-test/done/34,35,32` | A | **[실측기록]** quad `spike 34/35/32`, stl `spikes/61` | quad↔stl 가 같은 결론을 서로 인용 | 스킬 `variance.md` 의 핵심 |
| 가변 인자·타입팩 | stl `typing-limits.md:48-56`(꼬리 호출 결과 미검사 `spikes/53`); qcc `luau-test/done/15-type-compute-trailing-deps-typepack.luau`; quad `typing-limits.md:525-578`(§7: trailing deps 가 붙으면 dep 파라미터에 주석 필요) | C(단편) | 15 는 H-176 으로 **폐기** | — | 정리본 **공백**. 단편 3개를 합쳐 신규 작성 필요 |
| 싱글턴/유니온/인터섹션 | quad `typing-limits.md:525-578`(싱글톤 보존 표), `:738`(8.7 `K & keyof`), `:1179`(8.25 교집합 모든 조각), `:787-810`(8.8~8.9 재귀 메소드 유니온); stl `:371`(유니온에서 제네릭), `:407`(원소 유니온 컨테이너), `:466` | A | **[실측기록]** `audit/type-store-index-keyof/REPORT.md` | — | 표 형태(선언→추론 `T`→진단)가 스킬에 좋은 포맷 |
| refinement·narrowing | stl `typing-limits.md:436`(태그 유니온: 좁히기 전 필드 읽기가 좁히기를 죽임); quad `:374`(§3 제네릭 키 narrowing 불가), `:1171`(8.24 `any` 인덱스 후 `~= nil`), `qcc luau-test/done/12` | B | 12 **[실측기록]** | — | |
| 지연 타입·순환 참조(재귀 별칭) | quad `typing-limits.md:84-360`(§1 비균일 재귀), `:1133`(8.21 순서 의존), `:1206`(8.26); `quad/.claude/research/luau-upstream-order-leak-report.md:1-40`(영문 이슈 초안, 재현 `quad-scratch/luau-order-probe/*` 10개); `quad/.claude/audit/type-recursion-issue*`; stl `audit/luau-solver-issues/5-recursive-alias-in-union.luau` | A | 재현 파일 존재 **[실측기록]**(내가 안 돌림) | 보고서 초안은 "보고 안 함" 상태 | §1 은 쓰기 전 "언제 풀리는가"(`:330`)까지 있어 버전 의존 |
| new solver vs old solver 차이·버그 | 분산됨: stl `luau-solver-issues/DRAFTS.md`(5건), quad `typing-limits.md:1025`(8.13), `:1123`(8.19 오버로드), `:1206`(8.26), `:1316`(8.38 lsp 1.70.1 신규 3건), `:1235`(8.28 한도 플래그), rbvm `design/known-issues.md:18-47`(old=340건 vs new=0), `rbvm/.claude/tools/check.sh:15-24`, quad `conventions.md:358`(사실 정정 주석) | A~B | stl 쪽 **[실행]**, 나머지 [실측기록] | **버전표 없음**: 어느 결함이 0.734/0.742/lsp 1.70 에서 사는지 한 곳에 없음 → 스킬의 최우선 산출물(`solver-bugs.tsv`) | |
| 한도(Too complex, `LuauTarjanChildLimit` 등) | quad `typing-limits.md:640`(8.5), `:1006`(8.12), `:1235`(8.28), `:1331`(8.41); `quad/scripts/doc-snippets.py` 상단 FLAGS(160000/100000/1000000) | A | **[실행]** quad CI 게이트(`test.sh:79`) | stl 은 한도 플래그 미사용(작은 코퍼스) | |
| luau-analyze / luau-lsp 사용 | stl `typing-limits.md:71-104`(72 vs 68건 비교), `base/architecture.md:89-122`; quad `conventions.md:349-361`; rbvm `tools/check.sh:1-30`(globalTypes+sourcemap 필수); moonwave `audit/mrow-spike/run.sh` | A | **[실행]** 각 check.sh | **모순 (b)** §3 | stderr 출력(`2>/dev/null` 착시) 주의 `stl architecture.md:89+` |
| `--!strict` / `--!nocheck` / `--!native` | stl `typing-limits.md:105-128`(.luaurc 한 단어로 310→0건 표), `architecture.md:89` | A | **[실측기록]** | `--!nocheck`·`--!native` 전용 서술 **공백**(`--codegen` 플래그만 §perf) | `.luaurc` 가 모든 프로젝트에서 `strict`+`lint *`(quad·stl·moonwave·table-sim·qcc 동일; mrow 는 `LocalShadow:false`) |
| 음성 대조군 방법론("진단 0건을 믿지 마라") | stl `typing-limits.md:58-70`, `scripts/check.sh:47-60`, `scripts/spike-expectations.tsv`(83줄), `.claude/tools/spike-diff.py`; moonwave `audit/mrow-spike/README.md`(NEG 10/10, 변이 10/10); quad `typing-limits.md:579`(§8 체크리스트) | A | **[실행]** 게이트 | 프로젝트마다 별 구현 | **스킬 `luau-verify` 의 핵심 절차** |
| mrow `Parser<string>`→`Parser<number>` 대입 무진단(H1) | moonwave `audit/mrow-spike/README.md`(TL;DR 2번째), `spikes/01-negative-control.luau` | B | **[실측기록]** | stl 변성 결함과 같은 뿌리 가능성(미검증) | |

### 2-2. 성능·런타임

| 주제 | 어디에 | 품질 | 검증 | 중복/모순 | 비고 |
|---|---|---|---|---|---|
| 메타테이블 인덱싱 세금 | stl `perf-measurements.md:13`(1.59x), `:422`(§16), `:486-526`(§18 모드별: -O1 1.60x / -O2 1.66~1.81x / codegen 1.96~2.00x), `:1685`(§60) | A | **[실측기록]** (`luau -O2`, 최소값 반복) | — | 배포 모드(-O2, native)에서 세금이 더 큰 점이 핵심 |
| table 배열/해시, `table.move`, `ipairs`, 정렬, 구멍 검사 | stl `perf-measurements.md:40`(§2), `:56`(§3), `:93`(§5), `:108`(§6), `:469`(§17) | A | [실측기록] | — | 1698줄 중 **일반 Luau 지식은 §1–6,14,16–18 정도(~300줄)**, 나머지(§21–59)는 stl 컨테이너/트레이트 고유 |
| 호출 모양(네임스페이스 함수 vs 콜론) | stl `:323`(§14) | A | [실측기록] | | |
| native codegen / -O2 / 인라이닝 | stl `:486`(§18); qcc `luau-test/done/27-error-walker-o2-codegen-coroutine.luau:1-30`(**`-O2` 가 로컬·직접호출 태그 함수를 인라인해 `debug.info` 프레임이 사라짐 → 테이블 필드 경유만 안전**) | A | **[실행 가능]** 파일 머리에 4개 플래그 조합 실행법 명시 | `--!native`/`@native` 지시자 가이드 **공백** | 27 은 일반 지식으로 승격 가치 큼 |
| GC·weak table | rbvm `design/gc-and-lifecycle.md:24`(`gcHold`), `:55`(`__mode` 표), qcc `luau-test/done/07-relate-weak-table-gc.luau`, `18-…-gc.luau`, `not-run/gc-trigger-helper.server.luau`; quad `audit/gcconn-trick-verification.md`, `perf-cli-2026-09-26/p6-gc.luau`; stl `perf` §18(b) 레지스트리 vs 태그(GC 2~3.7x) | A~B | rbvm 은 Studio **[Studio]**, 나머지 [실측기록] | "CLI 에선 GC 타이밍이 Studio 와 다름" 주의가 파일마다 흩어짐 | 일반론 **공백**, 사례만 |
| 컨테이너 설계 일반(위치 타입 제네릭, 구간 규약) | stl `base/container-design-notes.md:10-336` | B | 일부 실측(`:185`), 대부분 설계 의견 | **stl 고유** | 스킬 아님, 프로젝트 문서로 유지 |
| Luau 메타메소드 사용 규약 | stl `architecture.md:284` | C | — | — | |

### 2-3. Roblox·동시성·모듈·테스트

| 주제 | 어디에 | 품질 | 검증 | 비고 |
|---|---|---|---|---|
| Roblox API 타입(Instance/Enum/서비스) | rbvm `.claude/cache/globalTypes.d.luau`(+`luau-lsp-settings.json`, `sourcemap.json`), `rbvm/design/engine-behavior.md:12-96`(Instance/Signal/Destroy/트리 API 실제 동작 표), `quad/scripts/roblox-defs/globalTypes.d.luau`; luau-lsp 가 못 읽은 globalTypes(2025-11자)는 `rbvm/tools/check.sh:15-19` | B | **[Studio]**(`rbvm engine-behavior.md:12` Studio 0.742, Deferred 모드) | **타입 정의 사용법**(Instance:IsA 좁히기, `Enum` 타입, `GetService` 타입)은 **공백** — 동작 실측만 있음 |
| Studio 에서 Luau 실행/검증(MCP) | qcc `luau-test/README.md`(실행 환경 세 갈래), quad `audit/spike10-full-run-2026-09-01.md`, `.claude/audit/kit-studio-*`, `audit/headless-cli-install-2026-09-21.md`; 로컬에 `mcp__roblox-studio__execute_luau` 도구 존재 | A | [Studio] | 스킬 `roblox-verify` 후보 |
| 시그널/Deferred·Destroy·`require` 문자열 규칙(Studio 실제) | rbvm `engine-behavior.md:18`(Signal), `:36`(Destroy), `:68-83`(**`./` `../` `@self` `@game/…` 허용, 접두어 없으면 에러, `@Self` 대소문자 무시, `./X/` 슬래시 허용**) | A | [Studio] | stl `architecture.md:37`,`:307`(luau CLI require 규칙)과 **환경이 다름**(CLI vs Studio) — 둘을 한 표로 비교 필요 |
| 동시성: task/coroutine | quad(`task.*` 언급 113 파일) 중 정리본은 `quad/docs` 와 `qcc luau-test/done/27`(코루틴 안 에러는 그 코루틴 스택만 본다); stl `papers/01-fut.md`(`Fut` = 코루틴 래퍼, 구현+spikes/48) | B(단편) | 27 [실행 가능] | task 스케줄러 순서 일반 정리 **공백** |
| Actor / Parallel Luau / SharedTable | quad 62 파일에 단어만(`docs`/설계) | 공백(정리본 없음) | — | 신규 조사 필요 |
| 이벤트 재진입·순서(Signal 발화 중 해제 등) | quad `audit/h895-reentry-order-2026-10-07/`, rbvm `review/2026-10-05-repro/B1,B2,B14*.luau`(재현 12개) | A | [실행 가능] | 일반화하면 "Signal 구현 체크리스트" |
| 모듈/require/Rojo/pesde | stl `architecture.md:7-63`, `:307-341`(require 규칙은 정적 검사가 못 잡음, symlink 함정); tbox `CLAUDE.md:39-70`(pesde), `:99+`(init.luau 는 "자기 폴더"); quad `scripts/relink.sh`, `.luaurc aliases`(`quad/.luaurc`); rbvm `design/architecture.md:1-216`; Rojo 7.7 는 `quad/mise.toml:11` | A | stl **[실측기록]**, tbox [서술] | 같은 `init.luau` 규칙이 stl·tbox 양쪽에 따로 서술됨(중복) |
| 테스트 방법: Lune / TestEZ / jest-lua | stl `architecture.md:64`(assert+print, 프레임워크 없음, **lune 금지**); qcc `luau-test/README.md`(`luau` 또는 `lune`); tbox `mise.toml:26`(`luau` + `lute` 이중 실행); TestEZ/jest 는 table-sim 문서 2건에서 언급뿐 | B | stl/tbox **[실행]** | **모순 (c)**; jest-lua/TestEZ **공백** |
| 포매터 stylua | `stl/stylua.toml`(120col, tabs, AutoPreferDouble, call_parentheses Always), 같은 모양 tbox/quad/table-sim/moonwave/devplorer; tbox `CLAUDE.md:80-90`(루트에서만 실행해야 설정이 먹음; `f<<T>>` 오염 경고) | B | 앞부분 [실행], 경고는 §1-1 재현 실패 | stylua.toml 은 5곳 동일 → **공유 지식 후보** |
| 린트 | `.luaurc lint "*": true` + `LocalShadow` 등(stl `check.sh:60+`) | B | [실행] | |
| 문서 속 코드 블록 검증 | quad `scripts/doc-snippets.py:1-60`(펜스 정보 문자열 표식 `continue/skip/no-run/error=QuadNNNN`, 줄 끝 `-- 타입 에러` 표식, 통제군 3개), `doc-snippets-runshim.luau`, `conventions.md:347` | A | **[실행]** `test.sh` 게이트 | **이미 있는 "스니펫 정본" 체계** — §5 |

### 2-4. 프로젝트 고유(스킬 아님) — 경계 확인용

stl: `trait-system.md`(108줄)·`papers/06,07,08`(트레이트 시스템과 회고 — 일반 교훈은 `08-trait-retrospective.md` 의 "타입이 끝내 서지 않았다" 요약뿐 증류 가치), `container-design-notes.md`, `perf-measurements.md` §21–59. quad: `base/*-plan.md` 25개(26,494줄 중 typing-limits 제외 대부분), `conventions.md`. rbvm: `architecture.md`, `known-issues.md`(A~D). table-sim: `base/*`(게임 설계), `research/*`(Roblox 플랫폼 조사 23건 — 플랫폼 지식이지만 결과가 "조사 시점 스냅샷" `<비공개>`에 확신도 높음/중간/낮음 표기). moonwave: `base/*`, `audit/mrow-spike`(mrow 라이브러리 평가).

---

## 3. 모순·중복·드리프트 목록

| # | 내용 | 근거 | 권고 |
|---|---|---|---|
| (a) 타입 함수 | quad `typing-limits.md:50` "진단을 띄우는 데까지만"(허용: CheckVersion·CheckReservedKeys) vs stl `papers/03-tuple.md:1-25` "type function 을 쓰지 않는다(사용자: 문제가 너무 많아서)" vs quad 는 실제로 `quad-types` 에서 광범위 사용(`types.*` 언급 quad 118 파일) · `8.14` StripNil 타입 함수는 "된다". | 두 규칙은 **강도만 다르고 같은 방향**(제한적 사용). 스킬엔 "기본: 쓰지 않음. 허용: 진단 전용. 금지: 결과 타입 합성(체이닝 깨짐)" 3단 규칙 + 근거 3개 링크로 증류 |
| (b) 검사기 | stl `typing-limits.md:71-104`: `luau-lsp analyze` 가 진단을 빠뜨려 **luau-analyze 가 기준**. quad `conventions.md:358-361`: 게이트는 luau-analyze+luau-lsp **둘 다**, 한도 플래그는 lsp 쪽에만 먹음(`doc-snippets.py` FLAGS 는 `luau-lsp`용 `--flag:` 형식). rbvm/table-sim 은 lsp 가 기준(`enableNewSolver`). | 같은 파일에서 두 도구가 일치함을 §1-1 에서 확인. 규칙: "**CI 기준=luau-analyze(핀 고정 버전)**, 사용자가 보는 조건 재현=luau-lsp(`--definitions`+`--sourcemap` 필수), 둘의 차이는 보고" |
| (c) 러너 | stl `architecture.md:15`: lune 금지(타입이 못 따라가 문제), lute 로 갈아탈 것. qcc `luau-test/README.md`: "`luau` 또는 `lune`". tbox: `luau`+`lute` 이중. | 스킬은 `luau`(CLI) 를 기본 러너로, `io/fs` 가 필요한 경우만 lune. lune 의 `require`/타입 차이는 [서술] 이므로 검증 전엔 쓰지 않음 |
| (d) 구버전 서술이 한 문서 안에 공존 | stl `typing-limits.md:1-56`: 머리 ⭐ 박스들이 "아래 기록 중 X 는 **역사**" 라 정정. quad `conventions.md:358`: 문단 중간 "⚠️ [2026-09-15 사실 정정]". | **스킬에 가져올 땐 정정 반영 후 "현재 유효"만** 옮기고, 역사는 원본 링크로 |
| (e) qcc = quad 낡은 포크 | typing-limits 1073 vs 1387줄, luau-test 일부 다름 | 근거 출처에서 제외, 필요시 quad 로 교체 |
| (f) 버전 혼재 | §0-2 | 스킬의 모든 "버그 있음" 항목에 `confirmed: 0.734, 0.742` 필드 |
| (g) 선택적 폐기 스파이크가 `done/` 에 남음 | qcc `luau-test/STATUS.md`: 01/03/04/05/11/15/19/22 는 "폐기 → done/" (실물 spec 이 대체) | "done = 통과"가 아님. 스킬 근거로 쓰기 전 STATUS 확인 |
| (h) 문서 속 줄/파일 번호 낡음 | 예: stl `typing-limits.md:48-56` 가 `spikes/53` 을 가리키나 spikes 는 `audit/arr-type-redesign/spikes/`(55개)로 이동 | 증류 시 링크 정규화 |

---

## 4. 스킬 세트 설계안

### 4-0. 원칙
- Claude Code 스킬은 **description 만 항상 컨텍스트에 상주**한다 → 스킬 수는 적게(자동 4 + 수동 3), SKILL.md 는 "결정 트리 + 라우팅 표 + 규칙 요약"만 100줄 이내. 상세는 `references/` 1단계 깊이.
- 모든 references 파일 맨 위에 **목차(앵커 없이 절 번호+한 줄 요약)** 와 "이 파일에서 답하는 질문" 3~6개, 절마다 **`status:`** 한 줄(`verified:<snippet>@0.742` / `stated:<출처>`)과 **`last-confirmed:`** 버전.
- 스킬 안에 프로젝트 고유명(Quad, Arr, Namespace)은 넣지 않는다. 예시는 최소 재현(15줄 안팎) `.luau` 로 대체(§5).
- 증류본은 **원본 포인터**(`source: quad@0c2eef35:.claude/base/typing-limits.md:640-685`)를 절마다 단다 → 프로젝트 쪽이 바뀌면 드리프트 탐지 가능(§6 단계 4).

### 4-1. 디렉터리 구조(공유 위치 제안: `~/.claude/skills/` 또는 플러그인 `luau-skills`, 각 프로젝트는 심볼릭/플러그인으로 사용)

```
luau-skills/
  skills/
    luau-types/                 # 자동 호출
      SKILL.md                  # ≤100줄: 결정 트리 + 라우팅 표 + 5대 원칙
      references/
        00-index.md             # 질문→파일 라우팅 표(SKILL.md 와 동일 복제 X, 상세 버전)
        modes-and-config.md     # 120줄  strict/nonstrict/nocheck/native, .luaurc 한 단어 함정, lint
        generics.md             # 220줄  명시 타입 인자, 조용한 누수 3자리, 콜백 주석, 반환 타입 굳힘
        variance.md             # 200줄  read/write 필드, 공변 누수, 함수 타입 팬텀, 마커/브랜드
        unions-singletons.md    # 180줄  싱글톤 보존 표, K & keyof, 교집합, 태그 유니온 좁히기, 옵셔널 구멍
        recursion-and-limits.md # 200줄  재귀 별칭, 선언 순서 누수, Tarjan/Subtyping 한도, Too complex 대응
        type-functions.md       # 150줄  3단 규칙, 금지/허용, pcall 불가, 프라이밍, 체이닝 깨짐
        typepacks-varargs.md    # 100줄  (신규 작성 필요 — 공백)
        solver-limits.md        # 180줄  new vs old, 결함 카탈로그(표) + 버전별 상태
        solver-bugs.tsv         # 기계 판독: id, 요약, 재현 snippet, 0.734/0.742/lsp 상태, 업스트림 링크
      snippets/*.luau           # §5 의 실행 가능 정본 (references 는 여기를 인용)
    luau-verify/                # 자동 호출 (도구·검증 절차)
      SKILL.md                  # ≤90줄
      references/
        analyze-vs-lsp.md       # 100줄  어느 도구가 기준, definitions/sourcemap, stderr 함정
        negative-controls.md    # 120줄  NEG 대조군, 기대표 tsv, 변이 검사(mutate), 자원 상한(ulimit)
        toolchain-pins.md       # 80줄   mise 핀 정책, 버전 올릴 때 배터리 수치 확인, shim 실패 처리
        formatter-lint.md       # 60줄   stylua.toml 표준안, 루트에서 실행, 린트 목록
        runners.md              # 80줄   luau CLI(io/fs 없음) / lune / lute / Studio MCP
    luau-perf/                  # 자동 호출
      SKILL.md                  # ≤80줄
      references/
        measure-protocol.md     # 90줄   -O1/-O2/--codegen, 최소값 N회, 노이즈 이상치 처리
        tables-and-metatables.md# 200줄  메타테이블 세금(모드별 표), table.move, 배열 vs 해시, 구멍
        calls-iteration.md      # 120줄  ipairs/pairs/next, 호출 모양, 정렬 비교자
        gc-weak-tables.md       # 120줄  weak table, GC 타이밍(CLI vs Studio), 레지스트리 비용
        native-codegen-inlining.md # 100줄 -O2 인라이닝이 debug.info 를 깨는 사례, --!native (신규 조사 필요)
    roblox-luau/                # 자동 호출 (Roblox 환경 한정)
      SKILL.md                  # ≤90줄
      references/
        instance-enum-types.md  # 120줄  (공백 → 신규) globalTypes, IsA 좁히기, Enum 타입
        engine-behavior.md      # 150줄  Deferred 시그널, Destroy, 트리 API, require 문자열 (rbvm 표 증류)
        concurrency.md          # 150줄  task/coroutine 순서, 코루틴 스택 경계, Actor/Parallel (신규)
        rojo-modules.md         # 120줄  default.project.json, sourcemap, init 규칙, pesde/aliases
        studio-verify.md        # 100줄  MCP execute_luau 로 실측, 격리 규약
    luau-testing/               # 자동 호출 (테스트 설계)
      SKILL.md                  # ≤70줄
      references/ spec-layout.md, assert-print-harness.md, jest-lua-testez.md(공백)
    luau-solver-bug-triage/     # disable-model-invocation: true  (사용자 호출)
    luau-recheck/               # disable-model-invocation: true  (사용자 호출: 새 luau 버전 나올 때 재검증)
    luau-distill/               # disable-model-invocation: true  (프로젝트 문서→스킬 증류 작업 지시서)
```
요약 크기: 자동 호출 5개 × SKILL.md 평균 85줄, references 총 약 3,000줄(현 원본 3.5만 줄+ 중 증류 대상 약 8%).

### 4-2. 자동 호출 vs 사용자 전용

| 스킬 | 호출 | 이유 |
|---|---|---|
| luau-types, luau-verify, luau-perf, roblox-luau, luau-testing | **자동**(모델 호출 허용) | 읽기 전용 지식. 오발동 비용=컨텍스트 몇 백 줄 → description 을 좁게 쓰고 SKILL.md 를 짧게 유지 |
| luau-solver-bug-triage | **`disable-model-invocation: true`** | 최소 재현 축소·`--solver=old` 비교·업스트림 이슈 초안은 시간과 토큰을 쓰고, **외부 게시는 사용자 결정**이라는 기존 규약(`stl DRAFTS.md:3-5`, `quad … report.md:3`) 때문 |
| luau-recheck | **`disable-model-invocation: true`** | 설치 바이너리 교체·전 스니펫 재실행·`solver-bugs.tsv` 갱신은 의도적 유지보수 |
| luau-distill | **`disable-model-invocation: true`** | 프로젝트 문서를 읽어 스킬을 개정하는 무거운 서브에이전트 작업 |

### 4-3. description 초안(트리거 문구)

```yaml
# luau-types
name: luau-types
description: >-
  Luau 타입 시스템 질문·타입 에러 디버깅용. 제네릭(<T>, f<<T>> 명시 타입 인자), 변성·서브타이핑(read/write 필드),
  유니온/인터섹션/싱글턴 리터럴, narrowing/refinement, 재귀·순환 타입 별칭, type function(types.*), 타입팩·가변 인자,
  new solver(LuauSolverV2) vs old solver 차이·알려진 결함, "Code is too complex to typecheck", --!strict/--!nocheck.
  .luau/.lua 코드의 타입 에러가 "말이 안 되거나 에러가 안 나야 할 곳에서 안 날 때" 사용. Roblox API 사용법·성능 측정에는 쓰지 않는다.
```
```yaml
# luau-verify
name: luau-verify
description: >-
  Luau 코드를 실제로 검증할 때(luau-analyze, luau-lsp analyze, luau CLI, lune, stylua, .luaurc, mise 핀) 사용.
  "진단 0건"이 믿을 만한지 확인하는 음성 대조군, 스파이크/재현 파일 작성, 기대 진단 표(tsv), 돌연변이 검사,
  툴체인 버전 고정과 업그레이드 시 회귀 확인. 타입 규칙 자체가 아니라 '어떻게 확인하나'가 질문일 때.
```
```yaml
# luau-perf
name: luau-perf
description: >-
  Luau 성능 최적화·측정. 메타테이블 인덱싱 비용, table 배열/해시/구멍, table.move, ipairs/pairs, 호출 모양,
  -O1/-O2/--codegen/native codegen, weak table·GC 비용, 벤치마크 작성 방법. "느린 것 같다", "벤치", "최적화" 요청에 사용.
```
```yaml
# roblox-luau
name: roblox-luau
description: >-
  Roblox 엔진에서 도는 Luau: Instance/Enum/서비스 타입(globalTypes·sourcemap), RBXScriptSignal·Destroy·Deferred 이벤트 동작,
  task/coroutine/Actor/Parallel Luau 동시성, 문자열 require·Rojo·pesde 모듈 구조, Studio MCP(execute_luau)로 실측.
  순수 Luau 언어 문법/타입 질문에는 luau-types 를 쓴다.
```
```yaml
# luau-solver-bug-triage  (사용자 전용)
name: luau-solver-bug-triage
description: 신 솔버/타입 검사기의 의심 결함을 최소 재현으로 줄이고 old/new, 0.734/0.742/최신으로 대조해 solver-bugs.tsv 와 업스트림 이슈 초안을 만든다. 게시는 하지 않는다.
disable-model-invocation: true
```
`luau-recheck`: `description: 새 luau 릴리스에서 snippets/ 전체와 solver-bugs.tsv 를 재검증하고 바뀐 항목 보고서를 만든다.` + `disable-model-invocation: true`.

한계: description 의 한/영 혼용 키워드는 발동률 향상용이나 **실제 발동 테스트(질문 20개 × 기대 스킬)를 `skill-creator` 의 eval 로 돌려 보정**할 것(미실시). 초안 파일: `.claude/audit/drafts/skills/`.

### 4-4. "grep 없이 읽기" 3요건 설계

1. **각 references 파일 첫 40줄 = 목차 + 답하는 질문**
   ```
   # generics.md
   답하는 질문: Q1 타입 인자를 안 줬는데 any 로 샌다 / Q2 콜백 주석이 안 잡힌다 / Q3 f<<T>> 가 왜 필요한가 ...
   목차: §1 조용한 누수 3자리 · §2 f<<T>> 해법 · §3 콜백 주석 제거 · §4 반환이 첫 return 으로 굳음 · §5 알려진 결함 → solver-limits#S1
   ```
2. **SKILL.md → references 는 1단계 링크만**(references 끼리 연쇄 참조 금지; 필요하면 SKILL.md 의 라우팅 표에 두 파일을 같이 적음).
3. **질문→파일 라우팅 표**(SKILL.md 에 상주). 초안:

| 이런 질문/증상이면 | 읽을 파일 |
|---|---|
| 호출했는데 타입 인자가 `any`/`unknown` 으로 샌다, 반환만으로 `T` 결정 | `generics.md` §1–2 |
| 콜백 파라미터를 좁게 썼는데 에러가 안 난다 | `generics.md` §3 + `solver-limits.md` S1 |
| 읽기 전용 필드/마커/브랜드, 서브타입인데 대입이 통과해 버린다 | `variance.md` |
| `string` 으로 뭉개진다, `"a"|"b"` 키 타이핑 | `unions-singletons.md` §1 |
| 재귀 타입에서 진단이 사라진다, 선언 순서 바꾸니 달라진다 | `recursion-and-limits.md` §2 |
| "Code is too complex to typecheck" | `recursion-and-limits.md` §3 |
| `types.*`, `type function` 쓰고 싶다 | `type-functions.md` (먼저 "쓰지 않는다" 규칙) |
| 구 솔버와 신 솔버 결과가 다르다/버전을 올렸다 | `solver-limits.md` + `solver-bugs.tsv` |
| 진단 0건인데 믿어도 되나 | (luau-verify) `negative-controls.md` |
| 느리다/메타테이블 쓸까 | (luau-perf) `tables-and-metatables.md` |

### 4-5. 증류 우선순위(비용 대비 가치)
1. `solver-limits.md`+`solver-bugs.tsv`(5건+quad 8.13/8.19/8.26/8.38) — 지금 가장 흩어져 있고 버전 의존이 큼.
2. `negative-controls.md` — stl/moonwave 에 이미 완성된 방법론, 증류 거의 무비용.
3. `generics.md`/`variance.md`/`recursion-and-limits.md` — quad+stl 병합, 모순 없음.
4. `tables-and-metatables.md` — stl perf §1–6,14,16–18 만(약 300줄 원본 → 200줄).
5. `engine-behavior.md` — rbvm 표 증류(Studio 실측이라 가치 높음).
6. 공백 4개(타입팩, Instance/Enum 타입, Actor/Parallel, native)는 **신규 조사**; 조사 없이 쓰지 말고 `status: gap` 표시한 빈 파일 + "공식 문서 링크" 로 시작.

---

## 5. 스니펫을 "실행 가능한 정본"으로 만드는 방안

### 5-1. 규칙
- 스킬의 코드는 **`snippets/<topic>-<slug>.luau` 한 파일 한 사실**. references 의 코드 블록은 이 파일에서 **생성**(또는 CI 가 일치 검사).
- 줄 끝 표식(프로토타입 구현):
  - `-- expect-error[: 부분문자열]` : 그 줄에 진단이 **있어야** 함(음성 대조군).
  - `-- bug-present` : "있어야 할 에러가 안 나는" 솔버 결함. **0건이어야 통과**, 진단이 생기면 "솔버가 고쳐졌다 → 문서 갱신" 으로 **실패**.
  - 머리 `--@run` : 검사 통과 후 `luau` 실행(exit 0).
  - 표식 없는 줄의 진단은 모두 실패.
- 모든 스킬 주장 옆에 `[verified: snippets/x.luau @0.742]` 태그. 태그 없으면 `[stated]` — 이 구분이 이번 인벤토리의 "검증 상태" 열을 상시 유지한다.

### 5-2. 프로토타입 결과 (실제 실행)
`/code/Projects/claude-doctor/audit/drafts/snippet-harness/check_snippets.py` + `snippets/` 2개.
```
$ python3 -I check_snippets.py
ok   snippets/generics-callback-bound-lost.luau   (4줄 bug-present, 5줄 expect-error 'number', --@run 통과)
ok   snippets/negative-control.luau
rc=0
$ (기대 메시지를 'banana' 로 바꾼 변이본)  →  FAIL "메시지에 'banana' 없음", rc=1
$ LUAU_VER=0.734 와 0.742 모두 첫 스니펫 통과 (결함이 두 버전에서 모두 재현)
```
빌드 중 밟은 함정(스킬 본문에 그대로 기록할 가치): ① mise shim 이 버전 미지정이면 `--help` 에 exit 1 → "존재함"으로 오판, ② 진단은 **stderr**, 여러 줄 메시지는 첫 줄만 파싱하면 부분문자열 기대가 깨짐, ③ 경로가 `./` 접두로 출력돼 정규화 필요.

### 5-3. 기존 체계 재사용 평가

| 기존 자산 | 재사용도 | 이유/갭 |
|---|---|---|
| **quad `scripts/doc-snippets.py`**(420줄) | **높음(1순위 설계 모델)** | 이미 "문서 luau 펜스 검사: 표식 `continue/skip/no-run/error=`, 줄 끝 `-- 타입 에러` 기대, 통제군 3개(검사기 포기 감지), 병렬 실행". 갭: Quad 전용 컨텍스트(`q`, 모듈 등록, mock 런타임 shim)에 결합 → **컨텍스트 주입부를 제거하고 표식 문법만 가져오면** 일반 스킬용 `.md` 펜스 검사기가 됨. 지금 방식(`.luau` 파일이 정본) 대신 **마크다운 펜스가 정본**인 점이 다름 — 선택 문제(§5-4) |
| stl `scripts/spike-expectations.tsv` + `.claude/tools/spike-diff.py`(40줄) | **높음** | 줄 번호 기대표(`건수\t경로\t줄목록`)와 diff. 장점: 소스에 표식 안 심어도 됨, 단점: 줄 번호 취약(수정 시 tsv 동기화). 스킬 스니펫은 짧아 **줄 끝 표식**이 더 낫지만 `bug-present` 개념은 tsv 방식과 호환됨. `ulimit -v 2097152; timeout 120` 자원 상한은 그대로 채택 |
| stl `.claude/tools/mutate.sh` | **중간** | 사본에서 돌연변이 1개 적용 후 `check.sh` 종료코드로 판정. 스킬에선 "스니펫의 `expect-error` 줄을 정상 코드로 고치면 CI 가 실패하는가" 변이 검사에 응용 가능. 단 `git ls-files` 전제 + stl 의 `check.sh` 결합 → 얇은 래퍼 필요 |
| qcc/quad `.claude/luau-test/`(폴더=상태: `done/`,`rewrite-required/`,`not-run/` + STATUS.md) | **중간(운영 모델)** | 파일 머리 주석이 "무엇/어느 문서 근거/실행법/기대"를 모두 담는 규약과 폴더로 상태 표현은 좋음. 갭: **자동 게이트가 아님**(수동 실행, 폐기 후에도 `done/` 잔존) → 스킬 쪽은 `status:` 를 파일에 두고 CI 가 판정 |
| moonwave `audit/mrow-spike/run.sh` | **중간** | a(분석 exit0)+b(NEG 정확 건수)+c(런타임 동등)+c2(변이 사살)의 4단 구조가 가장 완성형. 스킬 CI 의 설계 참고 |
| rbvm `review/2026-10-05-repro/*.luau` | 낮음 | Roblox 가상화 결합, 단 "버그 재현 파일 한 개 한 사실" 형식은 동일 |
| qcc `luau-test/done/27-…codegen.luau` | **높음(그대로 편입)** | 4개 플래그 조합 실행법이 파일 머리에 있음. harness 에 `--@flags` 행렬 지원만 추가하면 `native-codegen-inlining.md` 의 정본이 됨 |

### 5-4. 설계 선택지와 권고
- A) `.luau` 정본 + references 에 **복사 삽입**(생성 스크립트) → 권고. 이유: 정본이 에디터/lsp 로 열려 진단 확인 가능, 한 사실 한 파일.
- B) 마크다운 펜스 정본 + 펜스 검사(quad 방식). 스킬 작성자 경험은 편하지만 `-- expect-error` 줄의 정합 보장이 약함.
- CI: `check_snippets.py` 가 (1) 새 솔버 strict(+`--solver=old` 비교는 선택 `--@also-old`), (2) 버전 행렬(0.734/0.742/최신) 결과를 `solver-bugs.tsv` 의 열과 대조, (3) references 의 `[verified: …]` 링크 파일 존재 검사, (4) `--@run` 실행. 버전 올릴 때 **tsv 의 기대 바뀜 = 솔버 동작이 바뀐 신호**(stl `mise.toml` 머리 주석의 운영 원칙과 동일).
- 필요 도구는 이미 로컬에 있음(luau 0.742 직접 경로). lune 은 `--@run=lune` 옵션으로만.
- 아직 안 한 것: 병렬 실행, `--flag:` 행렬(quad 한도 플래그), tsv 생성, Studio 전용 스니펫(`[Studio]`) 처리(MCP 의존이라 CI 불가 → `status: studio-verified` 수동 표식).

---

## 6. 일반 Luau 지식(공유) vs 프로젝트 고유 설계 — 경계 제안

판정 질문 3개: ① **Quad/stl 같은 라이브러리 없이** 최소 재현으로 설명되는가? ② 결론이 **Luau 버전**(솔버 동작)에만 의존하고 프로젝트 설계 선택에는 의존하지 않는가? ③ 다른 프로젝트(tbox, devplorer, table-sim)에서도 같은 사실이 적용되는가? → 셋 다 예 = 공유.

| 구분 | 공유 스킬로 이동 | 프로젝트에 남김(스킬은 링크만) |
|---|---|---|
| 타입 | 제네릭 명시 인자·추론 결함·변성/공변 누수·싱글톤 보존·재귀 별칭·선언 순서 누수·한도·타입 함수 3단 규칙의 **사실** | "Arr 의 셋째 인자를 `ArrView<unknown>` 으로 둔 설계"(stl), `StateMarker<T>`·Ref 마커 설계, Brand/Marker 계약, 타입 함수 `CheckVersion`/`CheckReservedKeys` 적용 사례(quad), 트레이트 시스템 전체 |
| 도구 | analyze vs lsp 사실, NEG 방법론, `.luaurc` 한 단어 함정, stylua.toml 표준안, 핀 정책, 자원 상한 | 각 프로젝트의 `check.sh`/`test.sh` 구성, quad `doc-snippets.py` 의 Quad 컨텍스트 |
| 성능 | 메타테이블 세금(모드별), table.move, 배열/해시, 호출 모양, -O2 인라이닝과 debug.info | 정렬 가족·트리·덱·트레이트 조회 비용(stl §21–59), quad 디스패치 비용(`perf-cli-2026-09-26`) |
| Roblox | Signal/Destroy/require 문자열의 **엔진 실측**(rbvm), globalTypes/sourcemap 설정 | rbvm 의 가상 트리/프록시 설계·known-issues, table-sim 게임 설계·`base/*` |
| 테스트 | assert+print 하네스 패턴, NEG 배터리, 변이 사살, 폴더=상태 운영 | 프로젝트별 spec 구성 |
| 혼합(둘로 쪼갤 것) | stl `typing-limits.md`: 앞쪽 일반(§71-253 도구·제네릭) / 뒤쪽 컨테이너 고유(§388-466)가 섞임. quad `typing-limits.md`: §0·§1·§6–7·§8.5–8.26 일반, §2·§4·§5·§8.15·8.36–8.43 대부분 Quad API 고유 | 증류 시 각 절 머리에 `scope: general|project` 태그를 단 사본을 만들어 분류부터 |

양방향 규칙: ① 프로젝트 문서는 일반 사실을 **다시 서술하지 않고** 스킬 파일로 링크, ② 프로젝트에서 새 일반 사실을 발견하면 `snippets/` 에 최소 재현을 추가하는 PR 이 선행(스킬이 정본), ③ 프로젝트 문서에 남는 "일반 사실" 은 한 줄 요약+링크로 축소.

---

## 7. 후속 작업 제안(이번에 하지 않은 것)
1. `solver-bugs.tsv` 1차본: stl 5건 + quad 8.13/8.19/8.26/8.38/8.21 을 최소 재현으로 재작성해 0.734·0.742·lsp 1.70.1 행렬로 실행(수 시간).
2. 공백 4영역(타입팩, Instance/Enum 타입, Actor/Parallel, native) 신규 조사 — 공식 문서 + 실행 스파이크.
3. tbox 의 stylua `f<<T>>` 경고 재현 시도(다른 모양) — 재현 불가면 tbox 문서의 경고 수정 제안.
4. description 발동 평가(질문 20개 세트, `skill-creator` eval).
5. 원본 드리프트 감시: 스킬 절의 `source:<repo>@<sha>:<path>:<lines>` 와 현재 파일 해시 비교 스크립트.
6. qcc 를 근거에서 제외하고 quad 정본으로 교체(복제 확인 후), stl 문서의 낡은 `spikes/` 경로 정규화.

### 산출물
- 이 문서: `/code/Projects/claude-doctor/audit/05-luau-knowledge-map.md`
- 프로토타입: `/code/Projects/claude-doctor/audit/drafts/snippet-harness/{check_snippets.py, snippets/*.luau}`
- 스킬 초안: `/code/Projects/claude-doctor/audit/drafts/skills/`
