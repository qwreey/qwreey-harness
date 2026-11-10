# 11. 지식 공백 메우기 — 결과 요약

> 작성 2026-11-10. 대상은 `05-luau-knowledge-map.md` §0-4 의 "지식이 없는 영역" 6개다(type function 제외).
> 초안: `drafts/gaps/*.md`. 스니펫: `drafts/gaps/snippets/*.luau` 41개. 도구: `drafts/gaps/tools/`. luau-kb 에는 아무것도 쓰지 않았다.
> 외부 자료는 모두 2026-11-10 에 받았다. Studio MCP 는 쓰지 않았다.

## 1. 주제별 결과

| # | 주제 | 초안 | 절 | verified | 일부 verified | described | 스니펫 | 들어갈 스킬 |
|---|---|---|---|---|---|---|---|---|
| 1 | 타입팩과 가변 인자 | `typepacks-varargs.md` | 10 (+자료 절) | 10 | 0 | 0 | 11 (`packs-*`, 실행 3) | luau-types |
| 2 | Roblox API 타입 | `roblox-api-types.md` | 10 (+자료 절) | 7 | 3 (타입은 verified, 런타임 값은 described) | 0 | 9 (`roblox-*`) | roblox-luau (+luau-verify 한 줄) |
| 3 | Actor 와 Parallel Luau | `parallel-luau.md` | 12 | 5 | 1 | 6 | 4 (`parallel-*`) | roblox-luau |
| 4 | `--!native` / native codegen | `native-codegen.md` | 9 | 5 (§5 성능은 이 기계 기준) | 2 (CLI verified / Roblox described) | 2 | 6 (`native-*`) + `bench_native.*` | luau-perf |
| 5 | 테스트 프레임워크 현황 | `testing.md` | 13 | 7 | 1 | 5 | 6 (`testing-*`) | luau-testing |
| 6 | `--!optimize` 와 `-O2` | `optimize-levels.md` | 9 | 7 | 1 (`-g0/-g1` verified, `-g2` described) | 1 | 5 (`optimize-*`) + `run_opt.sh` 29건 | luau-perf |

### 검증 방법과 마지막 실행 (2026-11-10)
- 순수 Luau 스니펫 28개(`packs`, `testing`, `native`, `optimize`):
  - 명령: `python3 -I /code/Projects/luau-kb/tools/check_snippets.py --luau 0.734,0.742`
  - 결과: 56/56 ok. `packs-*` 는 luau-lsp 1.70.1 참고 열에서도 "같음".
- Roblox 스니펫 13개(`roblox`, `parallel`):
  - 명령: `drafts/gaps/tools/check_roblox.py --lsp 1.70.1,1.69.0`
  - 이 도구는 하네스의 표식 문법을 그대로 쓰고, 검사기만 `luau-lsp analyze --platform=roblox --definitions=luau-kb/typedefs/globalTypes.d.luau --flag:LuauSolverV2=true` 로 바꾼다.
  - 결과: 26/26 ok.
- `-O`/`-g`/`--codegen` 플래그에 걸린 주장:
  - 하네스의 `--@run` 은 최적화 플래그를 주지 못한다. 그래서 `drafts/gaps/tools/run_opt.sh` 로 따로 검사했다.
  - 결과: 58/58 ok (29건 × 두 버전).
- 성능 측정은 `tools/bench_native.sh` 로 했다(`choom -n 1000` + `prlimit`, 200만 회 × 7라운드 최소값).
  - 기계: Ryzen 5 7600 위 4 vCPU 공유 컨테이너, load ≈ 4.
  - 수치는 이 기계에서만 유효하다.

### luau-kb 로 옮길 때 할 일
1. `check_roblox.py` 의 기능을 `tools/check_snippets.py` 에 넣는다(`--lsp-roblox` 모드, `--@sourcemap` 머리). 넣을 때 luau-lsp 플래그 함정 둘을 반영한다.
   - 같은 `--flag:` 가 두 번 오면 앞의 값이 이긴다.
   - `--platform` 을 두 번 주면 실행이 실패한다.
2. `run_opt.sh` 의 주장을 하네스 머리 `--@run-opt=2` 같은 형태로 옮긴다. 그래야 `-O2` 주장을 스니펫 한 곳에서 관리할 수 있다.
3. luau-kb `generics.md` §8 은 `typepacks-varargs.md` 로 넘기는 링크로 줄인다.

## 2. 공식 문서(또는 기존 기록)와 실측이 어긋난 사례

| # | 어긋남 | 주제 | 근거 |
|---|---|---|---|
| 1 | luau.org `types/roblox-types` 의 IsA 예제가 `child.Text` 를 읽어 그대로는 `Unknown global 'child'` 다 | 2 | `roblox-docs-isa-sample.luau` |
| 2 | Roblox `luau/enums.md` 는 `part.Shape = "Cylinder"` 를 허용한다고 쓴다. 타입 검사기는 `got 'string'` 으로 거부한다 | 2 | `roblox-enums.luau` |
| 3 | `Instance.md` 의 WaitForChild 시그니처 줄은 반환을 `Instance` 로 적는다. 본문은 timeout 이면 nil 이라고 한다. 정의 파일은 본문 쪽(`Instance?` 오버로드)을 따른다 | 2 | `roblox-find-wait-nil.luau` |
| 4 | `Clone()`(Archivable=false 면 nil), `LocalPlayer`(서버에서 nil), `SetAttribute`(지원 외 타입은 에러)는 문서가 런타임 실패를 말한다. 타입은 non-nil/any 라 무진단이다 | 2 | `bug-present` 4건 |
| 5 | `typeof(u) == "Part"` 를 타입 검사기는 `Part` 로 좁힌다. 런타임 typeof 는 인스턴스에 `"Instance"` 만 준다(런타임 쪽은 described). `ClassName == "Part"` 는 좁혀 주지 않는다 | 2 | `roblox-attributes-typeof.luau`, `roblox-isa-refinement.luau` |
| 6 | pcall 실패 분기의 둘째 값이 `R` 로 타입 지정된다(실제는 메시지 string). 상류 소스 FIXME 가 인정하는 한계다 | 1 | `packs-pcall-failure-value.luau` |
| 7 | 새 솔버는 `local function` / 함수 리터럴에 넘친 인자를 잡지 않는다. 옛 솔버와 타입 주석 붙은 함수는 잡는다. 문서에 언급이 없다 | 1 | `packs-extra-args*.luau` |
| 8 | 공식 SharedTable 반복 예제 `for k, v in st do` 가 새 솔버에서 `__iter` 타입 에러다. 정의는 키를 `number` 로 선언해 문서(문자열 키 허용)와도 맞지 않는다 | 3 | `parallel-sharedtable-*.luau` |
| 9 | Multithreading 가이드는 Actor 가 DataModel 을 상속한다고 쓴다. 클래스 페이지와 정의는 `Model` 이다. 가이드의 병렬 예제가 스레드 안전 표기가 없는 `Instance.new` 를 부르는 점도 가이드 자신의 규칙("표기 없음 = Unsafe")과 충돌한다 | 3 | `parallel-luau.md` |
| 10 | luau.org/performance 는 "local 함수만 인라인"이라고 한다. 상수 테이블 리터럴의 필드 함수도 인라인된다. "재귀 함수는 인라인 안 됨"도 실제로는 자기 안의 호출에만 해당한다 | 6 | `optimize-inline-rules.luau` |
| 11 | **D-10 정정 필요**: "테이블 필드 경유 호출은 `-O2` 에서 안전"은 `function M.f` 대입 필드에만 맞다. `local T = { f = function … end }` 리터럴 필드는 인라인된다. "`error(msg,2)` 위치가 사라진다"도 불완전하다. 호출자가 인라인되지 않으면 **틀린 줄**(호출자의 호출자)을 가리킨다 | 6 | `optimize-o2-error-level.luau`, `run_opt.sh` |
| 12 | Roblox native 문서는 "동작은 같고 성능만 다르다"고 한다. 실제로는 `--!native`/`@native` 가 최적화 수준 2 를 강제해 에러 위치, traceback, `debug.info` 가 바뀐다. 파일에 `@native` 함수가 하나라도 있으면 `--!optimize 1` 보다 우선한다(CLI 실측, 엔진은 described) | 4 | `native-*-forces-o2.luau` |
| 13 | Roblox native 문서가 최상위 코드 컴파일 여부를 절마다 다르게 말한다. 소스 기준으로는 루프가 있는 최상위만 컴파일한다. 문서에 없는 사실도 있다: 로컬 주석도 codegen 에 쓰이고, 옵셔널(`vector?`) 주석은 효과가 없으며 코드가 오히려 커진다 | 4 | `native-annotation-codegen.luau` |
| 14 | quad `test.sh` 는 `-O1` 로만 돈다. `-O2` 로 돌리면 3개가 실패한다. 그중 `spec.relate` 는 라이브러리 `quad-base/src/Relate.luau:28` 의 손으로 센 `error(…, 3)` 때문이다(D-10 이 막으려는 모양) | 5, 6 | `testing.md` §12 |
| 15 | Jest Roblox 버전이 원천마다 다르다(README 3.20.0, GettingStarted `^3.21.0`, wally 최신 3.20.1). Open Cloud Luau Execution 문서가 링크하는 `Roblox/place-ci-cd-demo` 는 보관(archived)됐다 | 5 | `testing.md` |

## 3. 출처 목록

| 출처 | 버전/날짜 | 쓴 주제 |
|---|---|---|
| luau.org `/types/basic-types`, `/types/generics`, `/types/roblox-types` | 2026-11-10 받음, 페이지 날짜 없음. 예제는 play.luau.org iframe(lz-string)을 디코드 | 1, 2 |
| luau.org `/performance/` | Last-Modified 2026-10-20 | 4, 6 |
| luau-lang/rfcs: `syntax-type-alias-type-packs`, `syntax-typed-variadics`, `generic-functions` (`364425c5`, 2024-06-10), `explicit-type-parameter-instantiation` (`48734765`, 2025-12-05), `syntax-attribute-functions-native`, `syntax-attributes-functions` | HEAD `5fcbb5a2` (2026-10-16). 병렬 관련 RFC 없음 | 1, 4 |
| Luau 소스 `stl-luau/refs-ignoreme/luau` | 0.742, `8387cfb` (2026-10-09). `BuiltinDefinitions.cpp`(MagicSelect/MagicPack), `EmbeddedBuiltinDefinitions.cpp`, `OverloadResolver.cpp`, Compiler/CodeGen | 1, 4, 6 |
| create.roblox.com (`llms.txt` 머리 2026-11-10T00:40:57Z 에서 찾은 경로만 사용) | 각 페이지 `last_updated` 2026-11-10T00:40Z. 문서 빌드 시각이며 내용 개정일이 아니다 | 2, 3, 4, 5 |
| └ `luau/{type-checking,enums,native-code-gen,comments}.md`, `scripting/{attributes,multithreading}.md`, `studio/properties.md`, `reference/engine/classes/{Instance,Object,ServiceProvider,Players,Actor,SharedTableRegistry,…}.md`, `datatypes/SharedTable.md`, `libraries/task.md`, `globals/RobloxGlobals.md`, `performance-optimization/*`, `cloud/reference/features/luau-execution.md` | | |
| 정의 파일 `luau-kb/typedefs/globalTypes.d.luau` | quad `2ad2c03e` (2026-09-02). 상류 luau-lsp `main` `5f290c82` 판으로도 parallel 스니펫 동일 | 2, 3 |
| GitHub: `Roblox/jest-roblox` (push 2026-11-10), `jsdotlua/jest-lua` (v3.10.0, 2024-12-23), `Roblox/testez` (archived, v0.4.2 2022-01-05), `rojo-rbx/run-in-roblox` (v0.3.0 2020-07), `lune-org/lune` (v0.11.1), `luau-lang/lute` (v1.0.0 2026-04-16, `e065a086`), wally API | 2026-11-10 조회 | 5 |
| 사용자 저장소(읽기 전용): quad, stl-luau, table-sim, rbvm 의 테스트 디렉터리와 러너; quad `quad-roblox/src/LifetimeHandle.luau:139`, devplorer `StartConfig.luau:58` | 2026-11-10 작업 트리 | 2, 5 |
| 도구 | luau 0.734, 0.742; luau-lsp 1.69.0, 1.70.1 | 전부 |

## 4. 확인하지 못한 것

- **Studio 가 필요한 런타임 동작 전부.** MCP 는 금지였다.
  - Parallel: 병렬 단계에서의 에러, `require` 금지, 메시지 복사, SharedTable 원자성, Actor VM 격리, 성능 수치(문서에도 수치 없음).
  - Roblox 타입: `typeof(instance)` 가 `"Instance"` 인지, 열거형 속성에 문자열을 대입했을 때 받아 주는지.
  - native: 엔진이 지시어 우선순위를 CLI 와 똑같이 적용하는지, Roblox 의 `-g` 수준, `Vector3` 가 vector 타입으로 등록되는지, 코드 메모리 한도, Script Profiler 와 `debug.dumpcodesize()`.
- 새 솔버가 넘친 인자를 받아 주는 **원인 소스 줄**(주제 1 §10).
  - 모듈 필드 주석이나 `export type` 으로 노출하면 넘친 인자를 잡는지도 확인하지 못했다.
- luau-lsp `--no-strict-dm-types` 의 효과. 옛 솔버에서의 IsA·Enum 결과. rbvm/tbox 판 정의 파일과의 차이.
- `-g2` 가 CLI 에서 `-g1` 과 구별되는 출력. ARM 코드 크기. `--!native` + `--!optimize 1` 조합의 성능.
- 실행하지 못한 도구 셋:
  - `lute test`: 로컬에 lute 가 없다.
  - Jest Roblox, Open Cloud Luau Execution: Roblox 런타임과 API 키가 필요하다.
  - `wally install`: `^3.21.0` 이 실제로 실패하는지 보려면 돌려야 하는데 돌리지 않았다.
- `LocalSafe` 스레드 안전 표기의 실제 사례.
