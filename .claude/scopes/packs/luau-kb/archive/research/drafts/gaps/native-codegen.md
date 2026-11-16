# native-codegen — `--!native`, `@native`, 타입 주석과 측정

## 이 파일이 답하는 질문
- Q1 native 코드 생성은 어디서 돌고, 어떻게 켜나? `--!native` 와 `@native` 는 무엇이 다른가?
- Q2 `--!native` 를 붙이면 성능 말고 달라지는 것이 있나?
- Q3 타입 주석은 codegen 에 어떤 영향을 주나? 어떤 주석이 쓰이고 어떤 주석은 무시되나?
- Q4 언제 이득이고, 언제 손해인가?
- Q5 한도와 제약은?
- Q6 CLI 와 Roblox 에서 각각 어떻게 측정하나?

## 목차
- §1 어디서 도는가
- §2 켜는 법과 적용 범위
- §3 `--!native`/`@native` 는 컴파일 수준도 바꾼다
- §4 타입 주석이 codegen 에 주는 영향
- §5 런타임 측정: 언제 이득인가
- §6 손해 보는 경우
- §7 한도와 제약
- §8 측정 방법
- §9 공식 문서와 실측이 어긋난 곳

표기: `verified` 는 스니펫(`.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/snippets/`)이나 `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/run_opt.sh` 가 luau 0.734 와 0.742 에서 통과했다는 뜻이다. `described` 는 원천 서술이나 소스 읽기만 있다는 뜻이다. Roblox 엔진 안의 동작은 Studio 없이 확인할 수 없어 모두 described 다.

자료와 시점 (모두 2026-11-10 확인):
- create.roblox.com/docs/en-us/luau/native-code-gen.md (`last_updated: 2026-11-10T00:40:40Z`)
- luau-lang/rfcs `docs/syntax-attribute-functions-native.md`, `docs/syntax-attributes-functions.md` (둘 다 Status: Implemented, 저장소 HEAD `5fcbb5a2` 2026-10-16)
- Luau 소스 `stl-luau/refs-ignoreme/luau` 커밋 `8387cfb` (2026-10-09). 줄 번호는 이 커밋 기준.
- 실측: luau/luau-compile 0.734, 0.742. 기계: AMD Ryzen 5 7600 위 4 vCPU 컨테이너(다른 세션과 공유, load average 약 4), x64.

---

## §1 어디서 도는가
status: described · 원천: Roblox native-code-gen.md 머리, 각주 1·2

- Roblox: **서버 스크립트와 Android 클라이언트에서만** 네이티브로 돈다. 다른 기기에서는 같은 스크립트가 인터프리터로 돈다.
- 자동으로 켜지지 않는다. 지금은 `--!native` 나 `@native` 를 손으로 붙여야 한다(문서: "In the future, some scripts might automatically start running natively").
- CLI: `luau --codegen` 은 지시어와 무관하게 **불러온 모든 모듈**을 네이티브로 컴파일한다(`CLI/src/Repl.cpp:612-623`). 그래서 CLI 측정은 "`--!native` 를 붙인 Roblox 서버"와 같지 않다. 차이는 §3(수준 2 강제)과 §4(타입 정보 수준)에서 생긴다.

## §2 켜는 법과 적용 범위
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/native-attribute-nested.luau`, `snippets/native-attribute-syntax.luau`, `run_opt.sh` H1–H2 · 원천: rfcs `syntax-attribute-functions-native.md` Design 절, 소스 `CodeGen/src/CodeGenLower.h:37-63` gatherFunctionsHelper

| 방법 | 네이티브로 컴파일되는 것 |
|---|---|
| 파일 머리 `--!native` | 파일의 모든 함수와 최상위 코드(최상위는 루프가 있을 때만. §7) |
| 함수 앞 `@native` | **붙인 함수 하나만**. 그 안에서 만든 클로저, 같은 파일의 다른 함수, 최상위 코드는 아니다 |

- `@native` 는 `local function`, 익명 함수 식(`{ k = @native function() end }`), 메서드 선언(`function C:m()`), 필드 함수(`function C.f()`)에 붙는다.
- 함수 속성은 `@native`, `@checked`, `@deprecated` 셋뿐이다. `@inline` 은 RFC 의 가상 예시일 뿐이고 SyntaxError 다. 같은 속성을 두 번 쓰면 `Cannot duplicate attribute '@native'`.
- `--!native` 파일 안의 `@native` 는 의미가 없다. 컴파일러가 둘을 배타적인 플래그로 다룬다(`Compiler.cpp:5993-5997`).

## §3 `--!native`/`@native` 는 컴파일 수준도 바꾼다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/native-directive-forces-o2.luau`, `snippets/native-attribute-forces-o2.luau`, `snippets/native-directive-order.luau`, `run_opt.sh` A3, C1–C3 · 소스: `Compiler.cpp:5855-5859` setCompileOptionsForNativeCompilation, `:5871-5892`

- `--!native` 와 `@native` 는 네이티브 실행 표시만 하는 것이 아니다. 그 파일의 **최적화 수준을 2 로, 타입 정보 수준을 1 로** 올린다. 소스 주석: "this might be removed in the future in favor of --!optimize".
- 그래서 `--codegen` 없이 **인터프리터로 돌려도** 인라인이 일어난다. `error(msg, 2)` 위치, `debug.traceback` 프레임, `debug.info` 이름이 바뀐다(optimize-levels.md §4, §5).
- `@native` 함수가 하나만 있어도 **모듈 전체**가 수준 2 가 되고, 앞에 쓴 `--!optimize 1` 도 무시된다.
- 이를 피하려면 `--!native` **다음 줄에** `--!optimize 1` 을 둔다. 그러면 수준 1 로 돌아가지만 타입 정보 수준 1 은 남는다. 이 조합의 성능은 측정하지 않았다.
- 네이티브 실행 자체는 위치를 바꾸지 않는다. `--!optimize 1` 파일을 `--codegen` 으로 돌려도 위치가 그대로다(C1).

## §4 타입 주석이 codegen 에 주는 영향
status: verified · last-confirmed: luau 0.742 (0.734 동일, 숫자까지 같음) · 근거: `snippets/native-annotation-codegen.luau`, `run_opt.sh` G1–G7 · 소스: `Compiler/include/Luau/Compiler.h:41-45` typeInfoLevel, `Compiler.cpp` "if (options.typeInfoLevel >= 1 || options.optimizationLevel >= 2) buildTypeMap"

컴파일러는 타입 검사기의 추론을 쓰지 않는다. **소스에 적은 주석만** 읽어 바이트코드에 타입 힌트를 싣는다. 네이티브 코드는 그 힌트대로 특수화하고, 틀리면 느린 경로로 빠진다.

x64 코드 크기(`luau-compile --codegen --record-stats=function` 의 asmSize, 바이트):

| 함수 | `-O1` (타입 정보 없음) | `-O2` (CLI) | `--!native` (= `-O2` + 타입 정보 1) |
|---|---|---|---|
| `untyped(v: any)` → `v.x + v.y + v.z` | 899 | 918 | 918 |
| `typed(v: vector)` | 896 | **136** | **136** |
| `optional(v: vector?)` + `assert(v)` | 978 | 1029 | 1029 |
| `localAnn(v: any)` 안에서 `local w: vector = v` | 910 | 915 | **160** |
| `nonums(a: any, b: any)` → `a * b + a` | 256 | 253 | 253 |
| `nums(a: number, b: number)` | 251 | **130** | **130** |

읽는 법:
- **파라미터 주석**은 `-O2` 이상이거나 타입 정보 수준 1(`-t1`, `--!native`, `@native`)일 때 쓰인다.
- **로컬·`::` 캐스트·upvalue 주석**은 타입 정보 수준 1 일 때만 쓰인다. CLI `-O2` 만으로는 무시된다. 별도 실측(2026-11-10): `local w: vector = get()` 은 `-O2` 에서 1212, `-O2 -t1` 에서 456. upvalue `local up: vector` 는 1023 → 214.
- `-O1` 에서는 모든 주석이 무시된다. Roblox 의 비네이티브 Studio 테스트가 이 경우다.
- **`vector?` 같은 옵셔널 주석은 특수화에 쓰이지 않는다.** `assert` 로 좁혀도 마찬가지다. 핫 경로에서는 nil 검사를 바깥에서 하고, 안쪽 함수는 `vector` 로 받는다.
- `any` 주석은 주석이 없는 것과 같다.
- Roblox 의 `Vector3` 주석: CLI 기본 벡터 타입 이름은 `vector` 다. `v: Vector3` 는 `--vector-type=Vector3` 없이는 352 바이트로 부분적인 효과만 있고, 주면 136 이다. Roblox 엔진은 `Vector3` 를 벡터 타입으로 등록한다고 문서가 말한다(문서 예시 `sumComponentsFast(v: Vector3)`). described.
- 타입 검사 쪽 주의: 독립 Luau 의 `vector` 타입은 소문자 필드 `x/y/z` 만 안다. `v.X` 는 런타임에서는 되지만 `luau-analyze` 에서 `Key 'X' not found in external type 'vector'` 다.

## §5 런타임 측정: 언제 이득인가
status: verified(이 기계, 2026-11-10) · 근거: `tools/bench_native.luau`, `tools/bench_native.sh` · 프로토콜: 케이스마다 200만 회 호출을 7 라운드 돌려 `os.clock` 최소값. `choom -n 1000 -- prlimit --data=3GiB` 로 감쌈. 같은 날 세 번 돌려 차이는 10% 안쪽이었다

luau 0.742 결과(ms, 낮을수록 좋음. 0.734 도 경향이 같다):

| 케이스 | `-O1` | `-O2` | `-O1 --codegen` | `-O2 --codegen` |
|---|---|---|---|---|
| 숫자 함수, 주석 없음 | 38.0 | 12.2 | 33.4 | 5.0 |
| 숫자 함수, `number` 주석 | 37.5 | 12.3 | 33.3 | 4.9 |
| vector 함수, 주석 없음(인라인됨) | 42.2 | 8.8 | 49.4 | 4.7 |
| vector 함수, `vector` 주석(인라인됨) | 41.3 | 8.5 | 22.2 | 4.7 |
| vector 함수, 주석 없음, 인라인 막음 | 48.4 | 51.1 | 56.1 | 56.3 |
| vector 함수, `vector` 주석, 인라인 막음 | 48.9 | 49.2 | 25.2 | **24.4** |
| `vector` 주석 함수에 테이블을 넘김 | 43.9 | 27.6 | 50.2 | 27.1 |
| 같은 테이블을 주석 없는 함수에 | 42.7 | 27.0 | 34.8 | 12.6 |
| 문자열·테이블 할당 위주 | 70.7 | 67.2 | 74.2 | 64.6 |

해석:
- 이 측정에서 가장 큰 이득은 **수준 2 의 인라인**이었다(작은 함수 호출 38 → 12 ms). 그 위에 네이티브가 다시 2.5배를 더했다(12 → 5 ms).
- 인라인이 안 되는 호출에서는 **파라미터 타입 주석이 네이티브 이득의 대부분**이다(vector: 56 → 24 ms, 2.3배). 주석이 없으면 네이티브가 인터프리터보다 **느렸다**(48 → 56 ms). Roblox 문서의 "v is assumed to be a table; function performs slower due to table checks" 와 일치한다.
- 숫자 연산은 주석이 없어도 숫자로 가정하므로 `number` 주석의 런타임 차이가 작다. 코드 크기는 절반이 된다(§4).
- 문자열·테이블 할당 위주 코드는 네이티브 이득이 10% 안쪽이다. Roblox 문서의 권고("a lot of numerical computation and few calls to heavy Luau libraries or Roblox APIs")와 같은 방향이다.
- 수치는 이 기계와 날짜의 것이다. 다른 기계에서는 다시 잰다. 상대 순서만 옮겨 쓴다.

## §6 손해 보는 경우
status: verified(CLI) / described(Roblox) · 근거: §5 표, Roblox native-code-gen.md "Code to avoid", "Best practices"

- **주석과 다른 타입을 넘김**: `v: vector` 함수에 테이블을 넘기면 주석 없는 함수보다 2.1배 느렸다(`-O2 --codegen`, 27.1 vs 12.6 ms). 문서도 "Passing improperly typed parameters to typed functions"를 탈최적화 원인으로 든다. `any` 를 받는 함수에 성급히 구체 타입을 달지 않는다.
- **주석 없는 vector/userdata 코드**: 네이티브가 테이블로 가정해서 검사가 늘어난다(§5).
- `getfenv`/`setfenv` 사용: 문서상 네이티브 실행 불가 원인. 수준 2 의 인라인과 내장 접기도 파일 전체에서 꺼진다(optimize-levels.md §3).
- `math.asin` 같은 내장 함수에 숫자가 아닌 인자: 문서상 탈최적화. 측정하지 않았다.
- 모든 스크립트에 `--!native`: 문서상 서버 시작 시간(컴파일), 메모리, 게임 전체 네이티브 코드 한도를 소모한다. 이 비용은 Studio 의 `debug.dumpcodesize()` 로 본다(§8). described.
- 디버깅: 문서상 브레이크포인트를 걸면 그 함수의 네이티브 실행이 꺼지고, 네이티브 프레임의 로컬·upvalue 보기가 불완전하다. described.

## §7 한도와 제약
status: described(소스와 문서가 일치) · 원천: Roblox native-code-gen.md "Limits and troubleshooting", 소스 `CodeGen/src/CodeGen.cpp:48-56`, `CodeGen/include/Luau/CodeGenOptions.h:17-19`, `Compiler.cpp:616-617`

| 한도 | 소스 값 | 문서 메시지 |
|---|---|---|
| 블록 하나의 IR 명령 수 | `CodegenHeuristicsBlockInstructionLimit` 65,536 | "exceeded single code block instruction limit" |
| 함수 하나의 IR 블록 수 | `CodegenHeuristicsBlockLimit` 32,768 | "exceeded function code block limit" |
| 모듈 전체 IR 명령 수 | `CodegenHeuristicsInstructionLimit` 1,048,576 | "exceeded total module instruction limit" |
| 네이티브 코드 메모리 총량 | 엔진 설정(소스에 고정값 없음) | "Memory allocation limit reached for native code generation" |

- 한도는 FastInt 라 엔진이 바꿀 수 있다. 문서의 숫자(64K, 32K, 1M)는 소스 기본값과 같다. Roblox 가 실제로 그 값을 쓰는지는 확인하지 않았다.
- **최상위 코드**: 루프가 없는 최상위 코드는 "cold" 로 표시되어 네이티브로 컴파일하지 않는다. 루프가 있으면 컴파일한다(`Compiler.cpp:616-617`, `CodeGenLower.h:54-55`). CLI 에서 `--codegen-cold` 를 주면 cold 도 컴파일한다. `luau-compile --codegen` 은 항상 cold 를 포함하므로 이 차이를 보여 주지 않는다.
- 한도에 걸린 함수만 인터프리터로 돌고, 나머지는 네이티브로 돈다(문서).

## §8 측정 방법
status: verified(CLI 명령) / described(Roblox 도구)

CLI(이 저장소에서 쓰는 것):
```bash
L=/code/.local/share/mise/installs/luau/0.742
# 1) 코드 크기와 함수 목록: 무엇이 네이티브로 컴파일되고, 주석이 먹었는지
$L/luau-compile --codegen -O2 --record-stats=function --stats-file=/tmp/st.json f.luau   # lowerStats.functions[].asmSize
#    --!native 파일과 같게 보려면 파일 머리에 --!native 를 두거나 -O2 -t1. -O1 만 주면 주석이 무시된다(§4)
# 2) IR 에서 특수화 확인: CHECK_TAG ttable/tvector, fallback 블록 수
$L/luau-compile --codegenir -O2 f.luau
# 3) 실행 시간: 같은 파일을 네 조합으로, 최소값 N회
choom -n 1000 -- prlimit --data=3221225472 -- $L/luau -O2 --codegen bench.luau
#    (.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/bench_native.sh 가 -O1/-O2 × codegen 유무를 돈다)
# 4) 기타: --codegen-cold(cold 포함), --counters(네이티브 카운터 → callgrind.out), --codegen-perf(perf 맵)
```
- 측정 규칙: 같은 프로세스 안에서 라운드를 반복하고 최소값을 쓴다. 인라인 효과를 빼고 싶으면 함수를 "필드 대입 테이블" 경유로 부른다(optimize-levels.md §3). 공유 기계라 `choom` 으로 OOM 희생 순위를 올린다.
- `--target=a64|x64|a64_nf|x64_ms` 로 다른 아키텍처의 코드도 볼 수 있다. Roblox Android 클라이언트(ARM)를 짐작할 때 쓴다. 이번에는 x64 만 쟀다.

Roblox(문서, described):
- Script Profiler: 네이티브로 도는 함수 옆에 `<native>` 가 붙는다. 붙어야 할 함수에 없으면 브레이크포인트, 피해야 할 코드, 타입 불일치를 의심한다.
- Luau heap 프로파일러: 네이티브 코드 메모리가 `[native]` 로 보인다.
- 서버 뷰 커맨드 바에서 `debug.dumpcodesize()`: 스크립트·함수별 네이티브 코드 크기와 한도 대비 비율.

## §9 공식 문서와 실측이 어긋난 곳
status: verified(CLI) · last-confirmed: luau 0.742 (0.734 동일)

| 문서 | 문서의 말 | 실측 |
|---|---|---|
| Roblox native-code-gen.md | "behavior of the natively executing scripts is exactly the same as before and only the performance is different" | `--!native`/`@native` 는 최적화 수준을 2 로 올려 `error(msg, 2)` 위치, traceback, `debug.info` 를 바꾼다(§3). Studio 테스트 기본은 1 이므로 Studio 에서 지시어를 붙이는 순간 달라진다. CLI 실측이고 엔진 안에서는 미확인 |
| Roblox native-code-gen.md | 한 절은 "all functions in the script, and the top-level scope, if deemed profitable", 다른 절은 "Only the script's functions are compiled natively" | 소스는 앞쪽과 같다. 루프가 있는 최상위 코드는 컴파일하고, 없으면 cold 로 건너뛴다(§7) |
| Roblox native-code-gen.md | "Luau type annotations on function arguments are checked" | 파라미터만이 아니다. `--!native` 에서는 로컬·캐스트·upvalue 주석도 쓰인다(§4). 반대로 `vector?` 옵셔널 주석은 쓰이지 않는다. 둘 다 문서에 없다 |
| rfcs syntax-attribute-functions-native.md | `@native` 는 함수 하나의 네이티브 컴파일을 요청한다 | 맞다(중첩 클로저 제외까지 일치). 다만 RFC 와 Roblox 문서 모두 "**모듈 전체가 수준 2 가 된다**"는 부작용을 적지 않았다 |

---
들어갈 luau-kb 스킬: **luau-perf** (references `native-codegen.md`). §3 은 optimize-levels.md §2·§4 와 서로 링크한다.
