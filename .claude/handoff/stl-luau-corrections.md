# stl-luau 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 stl-luau 의 서술을 재현하거나 다시 재 보니 틀렸거나 낡은 것들이다. 반영 여부는 stl-luau 세션이 판단한다.
- 줄 번호는 2026-11-10 에 `/code/Projects/stl-luau` 를 읽기 전용으로 열어 확인했다.
  - luau-kb 는 클론인 `stl-luau-doctor` 를 인용한 곳이 있다. 두 사본은 `conventions.md` 만 다르고(184줄 대 174줄), 아래 줄 번호는 stl-luau 기준이다.
- 근거 경로는 `/code/Projects/luau-kb/` 기준이다. 스니펫은 `snippets/<ID>`, 벤치는 `bench/`(결과 `bench/RESULTS.md`)에 있다.
  - 성능 수치는 luau 0.742 의 `-O1`·`-O2`·`--codegen` 세 모드와 0.734 `-O1` 로 다시 쟀다.
- 심각도
  - **행동**: 그대로 따르면 코드·설계·도구 판단이 틀어진다.
  - **표현**: 결론이나 처방은 맞고 범위·원인·수치·버전 조건만 부정확하다.
- `decisions/README.md` "이번에 발견한 낡은 서술"의 stl-luau 항목 셋(1·2·7번째 줄)을 S21·S24·S27·S28 로 합쳤다.

## 성능 (`.claude/base/perf-measurements.md`)
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| S01 | `.claude/base/perf-measurements.md:156-179` (§9 제목) | 정렬 병합은 해싱을 못 이긴다(Union 5.9배 느림) | 이미 정렬된 정수 배열의 병합은 해시의 **0.27~0.38배**다(비교자 함수를 거쳐도 0.39~0.57배). 정렬부터 해야 하면 해시가 1.16~1.24배 이긴다. 원천 수치는 원소마다 클로저 비교자와 레코드 할당이 있는 컨테이너 연산에 한정된다 | `skills/luau-perf/references/algorithms-and-structures.md` §2·§8, `bench/algo-basics.luau` | **행동** (방향이 뒤집힘) |
| S02 | `.claude/base/perf-measurements.md:129` (§7 표) | 가변 인자 다수 처리: `select` 루프가 `table.pack` 보다 1.6~2.3배 빠르다 | 인자 4개에서만 `select` 가 빠르다(0.63~0.89배). 32개부터는 1.2~4.4배 느리다 | `skills/luau-perf/references/calls-and-closures.md` §7, `bench/call-varargs.luau` | **행동** (인자 수 조건) |
| S03 | `.claude/base/perf-measurements.md:1508` (§54) | 가변 인자는 원인이 아니다(±2 ns) | 고정 인자 대비 13~28%(인터프리터), 66~79%(native) 비싸다. §53 쪽 결론이 맞다. §54 값은 무거운 진입점에 묻혔다 | `calls-and-closures.md` §7, `bench/call-varargs.luau` | **행동** |
| S04 | `.claude/base/perf-measurements.md:1096-1099` (§39) | 해시 조회: 숫자 키(9.1 ns)가 테이블 키(14.8 ns)보다 싸다 | 배열부 정수 키만 0.49~0.76배로 싸다. **해시부의 정수·실수 키는 1.16~1.43배로 테이블 키보다 느리다** | `skills/luau-perf/references/tables.md` §8, `bench/tbl-access.luau` | **행동** (범위) |
| S05 | `.claude/base/perf-measurements.md:757-758` (§28) | `table.create` 로 크기를 미리 잡는 이득은 크면 없다 | 1만 개에서도 0.61~0.70배다 | `tables.md` §8, `bench/tbl-prealloc.luau` | **행동** |
| S06 | `.claude/base/perf-measurements.md:469-485` (§17) | `#` 는 O(log n)이고 20만 배열에서 약 90 ns 다 | 경계 캐시가 맞으면 반복 호출은 필드 읽기의 0.83~1.03배(사실상 O(1))다. 경계가 바뀌는 쓰기를 끼우면 2.0~2.5배다. 90 ns 는 캐시가 빗나간 경우다 | `tables.md` §8 | 표현 (조건) |
| S07 | `.claude/base/perf-measurements.md:1519-1531` (§55) | 업밸류로 값을 든 클로저 판이 지역 함수 판보다 5~8 ns 비싸다 | `-O1` 에서는 차이가 없다(0.95~0.97). `-O2` 3.5배·native 6.3배는 지역 함수가 **인라인된** 결과다. 결론("벤치에서 한쪽만 업밸류면 거짓 차이가 난다")은 유지된다 | `calls-and-closures.md` §7, `bench/call-closures.luau` | 표현 (원인) |
| S08 | `.claude/base/perf-measurements.md:93-107` (§5) | 3방향 비교 래퍼는 1.82배 | 인터프리터 1.74~1.83배, `-O2` 1.23배, native 1.05배다. 같은 파일이면 인라인된다 | `algorithms-and-structures.md` §3·§8, `bench/sort-compare.luau` | 표현 (모드 조건) |
| S09 | `.claude/base/perf-measurements.md:289-293` (§13) | `pcall` 0.037 µs(평범한 호출의 3배) | 0.734 2.85배, **0.742 1.83배** | `calls-and-closures.md` §7, `bench/call-costs.luau` | 표현 (버전) |
| S10 | `.claude/base/perf-measurements.md:614-619` (§22, `Contains` 행) | 클로저 콜백 대 직접 루프 약 2.9배(`-O2`) | 같은 파일이면 `-O2` 1.32배, native 1.11배다. 2.9배는 콜백이 다른 모듈에 있을 때의 값이다 | `calls-and-closures.md` §7 | 표현 (조건) |
| S11 | `.claude/base/perf-measurements.md:504-525` (§18 (b)) | 약한 키 레지스트리: 20만 생존 시 전체 GC 2~3.7배 | 1.38~1.50배(네 모드)다. 같은 방향이고 크기가 작다. 원천은 필드가 여럿인 실제 컨테이너였다 | `skills/luau-perf/references/gc-and-memory.md` §2·§8, `bench/gc-weak.luau` | 표현 (크기) |
| S12 | `.claude/base/perf-measurements.md:492-502` (§18 (a)) | native 의 메타테이블 세금 1.96~2.00배 | 읽기 2.09배, **쓰기 4.39배**다(쓰기는 원천에 없음) | `skills/luau-perf/references/metatables.md` §8, `bench/mt-index.luau` | 표현 (범위 확장) |
| S13 | `.claude/base/perf-measurements.md:30-36` (§1) | 메타테이블을 붙인 작은 배열 인스턴스는 96 B | 0.734·0.742 모두 80 B 다(메타테이블 유무와 무관). 결론(메타테이블 방식이 메모리 22배 작다)은 유지된다(26.6배) | `metatables.md` §8, `gc-and-memory.md` §4, `perf-ctor-slots-memory` | 표현 (수치) |
| S14 | `.claude/base/perf-measurements.md:60-72` (§3) | `ipairs` 0.39배가 가장 빠르다. 메서드 이터레이터·`__iter` 2.86~2.89배, Fold 2.54배 | 메타테이블 붙은 배열에서는 0.42~0.48배로 같은 방향이지만, **평범한 배열에서는 0.69~0.86배**로 차이가 작다. 0.39배에는 메타테이블 세금이 섞였다. 콜백(Fold 꼴)은 `-O2` 에서 1.11배(같은 모듈일 때) | `skills/luau-perf/references/iteration.md` §6, `bench/iter-forms.luau` | 표현 (조건) |
| S15 | `.claude/base/perf-measurements.md` §6, §27 (줄 미특정) | nil 검사 1.13배 / next 삼중항 약 5배, 래퍼 약 9배 | 인터프리터 1.14~1.19배, native 0.94배 / 6.2~7.8배, 11.9~13.3배 | `iteration.md` §6 | 표현 |
| S16 | `.claude/base/perf-measurements.md:1204-1222` (§44) | 다형 자리의 `t.Name` 은 1.4배 | 0.734 `-O1` 에서는 차이 없음(0.99), 0.742 인터프리터 1.13~1.15배, native 1.81배 | `skills/luau-perf/references/optimizer-and-native.md` §5·§8 | 표현 (버전·모드) |
| S17 | `.claude/base/perf-measurements.md:597-600` (§21); `.claude/conventions.md:40` | 다른 모듈의 상수 키(`Trait.TYPE_KEY`)로 생성하면 7~11% 느리다 | 2~6% 다. 같은 방향이고 잡음 경계다 | `optimizer-and-native.md` §8 | 표현 |

## 타입 시스템과 검사 도구
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| S18 | `.claude/base/typing-limits.md:120-122` | `--mode=strict` 는 `.luaurc` 를 덮지 못하므로 CLI 로 strict 를 강제할 방법이 없다 | `luau-analyze --fflags=DebugLuauForceStrictMode=true`(luau-lsp 는 `--flag:DebugLuauForceStrictMode=true`)로 강제된다. 디버그 플래그라 게이트에 쓰면 음성 대조군을 함께 둔다. "파일마다 `--!strict` 가 기본 층"은 그대로다 | `skills/luau-verify/references/tooling.md` §1, `verify-fflags-force-strict` | 표현 (처방 유지) |
| S19 | `.claude/base/typing-limits.md:371-386` | 유니온 자리의 제네릭은 인자가 갈래와 **같은 별칭**일 때만 풀린다 | 갈래 모양이 인자 타입 안에(교집합 조각으로라도) 그대로 있으면 풀린다. 실패하는 것은 필드를 더한 평평한 테이블이다 | `skills/luau-types/references/unions-singletons.md` §9·§12 | 표현 (조건이 더 넓음) |
| S20 | `.claude/conventions.md:38` (stl-luau-doctor 사본은 `:40`) | 콜러블 네임스페이스는 모듈 필드 오타도 잡지 못한다 | `setmetatable(M, { __call = … })` 꼴에서 `M.Neww` 는 잡힌다. 재현되는 것은 타입 인자 소실뿐이다 | `skills/luau-types/references/solver-limits.md` §7, `generics-callable-namespace` | 표현 |
| S21 | `.claude/papers/03-tuple.md:23`; `.claude/research/type-function-experiment/README.md:26` | type function 에서는 `error()` 대신 `print()` + `types.never` 를 써야 진단이 보인다 | luau 0.734·0.742, luau-lsp 1.69.0·1.70.1 모두 `error()` 메시지가 보인다(`conventions.md:84` ③ 이 맞다). `print` + `never` 가 더 깔끔하다는 점은 유효하다 | `skills/luau-types/references/type-functions.md` §5, `tf-diag-error-vs-print` | 표현 (낡은 서술 6번째 줄) |
| S22 | `.claude/conventions.md:84` ③ | 옛 버전에서는 `print()` + `types.never` 가 필요하다 | luau 0.734 와 luau-lsp 1.69.0(내장 판)도 `error()` 를 보인다. 안 보이던 판은 그 이전이다(추정: lsp 내장 0.729 무렵) | `type-functions.md` §5, `tf-diag-error-vs-print` | 표현 |
| S23 | `.claude/conventions.md:84` ②; `.claude/research/type-function-experiment/README.md:27-28` | 어떤 타입이 type function 을 한 번 통과하면 이후 제네릭 self 체이닝이 조용히 깨진다 | 다섯 꼴 × 네 판에서 재현되지 않았다. quad 실물 사례는 인자 직렬화 실패로 보인다(추정). 재현 파일이 있으면 알려 달라 | `type-functions.md` §5, `tf-passthrough-chaining`, `tf-serialize-unsupported-arg` | 표현 (주의 근거) |
| S24 | `.claude/papers/03-tuple.md:15` | 확정 — type function 을 쓰지 않는다 | `conventions.md:84` "금지 규약이 아니다"와 어긋난다. D-04 확정은 "사안별 판단"이다 | claude-doctor `decisions/D-04-type-functions.md` | 표현 (낡은 서술 7번째 줄) |

## require
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| S25 | `.claude/base/architecture.md:48-52` | `.luaurc` 의 일반 alias 는 편집기 전용이라 런타임 require 에서 동작하지 않는다 | 값이 `./` 로 시작하거나 절대 경로면 luau 0.734·0.742 런타임과 `luau-analyze` 가 모두 푼다. `./` 가 없을 때만 런타임·analyze 가 실패하고 luau-lsp 만 푼다 | `skills/roblox-luau/references/require-and-modules.md` §3, `skills/luau-verify/references/checkers.md` §7, `rbx-require-cli.sh` Q6·Q11 | **행동** (alias 를 쓸지의 판단이 바뀐다) |
| S26 | `.claude/base/architecture.md:322-326` | `@self` 대신 `./` 를 쓰면 `luau-analyze` 는 진단 0건이다. 정적 검사는 이 실수를 **절대** 못 잡는다 | `--!strict` 면 풀리지 않는 경로는 `Unknown require: unsupported path` 로 잡힌다. 0건은 nonstrict 이거나 `./` 가 다른 실제 파일로 풀릴 때다. 처방(런타임 require 게이트)은 그대로 필요하다 | `checkers.md` §7, `rbx-require-cli.sh` Q8·Q9 | 표현 |

## 설정 파일 주석
| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| S27 | `stylua.toml:1` | tbox/quad 와 같은 설정이다 | tbox 는 Spaces + Input 이고 quad 는 설정 파일이 없다 | claude-doctor `decisions/D-02-stylua.md` | 표현 (낡은 서술 1번째 줄) |
| S28 | `mise.toml:18-19` | quad 는 luau 를 고정하지 않는다 | quad 는 0.734 를 핀했다 | claude-doctor `decisions/D-05-toolchain-pins.md` | 표현 (낡은 서술 2번째 줄) |

## 분리 계획: `src/Collections/Arr.luau` (2026-11-10)
전체 근거와 계획기 원문: claude-doctor `drafts/split-plans/stl-luau-Arr.md`. 읽기 전용 시험이며 stl-luau 에는 쓰지 않았다.
- 3,030줄이 **6군집**(Insert 196, Ctor 310, Query 469, Sort 404, Shuffle 319→`Range`/`Reorder` 로 이름 변경 권장, Stream 683) + `Core` 37줄 + `init` 약 150줄로 갈린다. 군집 사이 간선 7개가 모두 `Core` 로 가고 **순환 0**, 모듈 상태 0 이라 **옮기기만 하는 커밋**으로 나눌 수 있다.
- 타입이 하나(`Arr<T>`)여도 나눌 수 있다. `snippets/style-split-types.sh`(luau-kb) S1 이 0.734·0.742·0.746 에서 제네릭·콜백 검사·`Arr.Sized<<number?>>` 명시 인자가 그대로임을 실측했다. 묶음이 `init` 을 require 하면 순환이므로(S3) 생성자는 `Ctor` 로 뺀다.
- **측정 필요**: `Core` 의 `toIndex`·`resolveRange`·`wrap`·`newEmpty` 는 뜨거운 루프 앞의 작은 헬퍼라, 다른 파일로 옮기면 `-O2` 인라인이 사라질 수 있다(luau-perf `calls-and-closures.md` §1). 옮긴 뒤 `bench/` 로 재거나 묶음마다 사본을 둔다.
- 계약 구현 위치 함수 다섯(241–280)은 `listImpl` 표와 함께 `init` 에 남기거나 `Query` 로 보낸다.
- D-13 확정(2026-11-10): 파일 길이 800줄 경고·1,500줄 강제(테스트는 두 배)이나 **알림만 하고 막지 않는다**. 확실한 사유를 기록하면 기준을 넘는 예외도 가능하다. 계획기는 `python3 -I /code/Projects/luau-kb/skills/luau-style/scripts/split-plan.py <파일.luau> [--target 400] [--max 800] [--scope 함수이름] [--json]` (읽기 전용, 표준 라이브러리만). `Arr.luau` 는 예외로 두지 않는다는 것이 사용자 결정이다.
