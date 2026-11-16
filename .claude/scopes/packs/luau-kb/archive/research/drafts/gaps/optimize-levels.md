# optimize-levels — `-O0/1/2`, `--!optimize`, 인라인과 에러 위치

## 이 파일이 답하는 질문
- Q1 최적화 수준 0, 1, 2 는 각각 무엇을 하나? 상수 접기는 `-O1` 에서도 되나?
- Q2 `--!optimize N` 지시어, CLI `-O`, `--!native`, `@native` 가 겹치면 무엇이 이기나?
- Q3 `-O2` 는 어떤 호출을 인라인하나? 테이블 필드로 부르면 안전한가?
- Q4 `error(msg, 2)` 가 `-O2` 에서 위치를 잃는 이유와 처방은? (decisions D-10)
- Q5 `debug.traceback`, `debug.info` 는 `-O2` 에서 어떻게 달라지나? `-g` 수준은?
- Q6 Roblox 는 어느 수준으로 컴파일하나? Studio 테스트와 라이브가 다른가?
- Q7 인라인 여부를 어떻게 확인하나?

## 목차
- §1 수준별로 하는 일
- §2 수준을 정하는 곳과 우선순위
- §3 `-O2` 인라인 조건
- §4 `-O2` 와 `error(msg, level)` 위치 (D-10)
- §5 스택 프레임과 `debug.*`
- §6 디버그 수준 `-g0/1/2`
- §7 Roblox 의 기본값
- §8 확인하는 법
- §9 공식 문서와 실측이 어긋난 곳

표기: `verified` 는 스니펫(`.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/snippets/`)이나 검사 스크립트(`.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/run_opt.sh`)가 luau 0.734 와 0.742 에서 그 주장대로 통과했다는 뜻이다. `described` 는 원천 서술이나 소스 읽기만 있다는 뜻이다.

자료와 시점 (모두 2026-11-10 확인):
- Luau 소스 `stl-luau/refs-ignoreme/luau` 커밋 `8387cfb` (2026-10-09, 0.742 계열). 줄 번호는 이 커밋 기준.
- luau.org/performance "How we make Luau fast" (HTTP Last-Modified 2026-10-20).
- create.roblox.com/docs/en-us/luau/comments.md (`last_updated: 2026-11-10T00:40:40Z`), "Comment directives" 절.
- 실측 도구: `/code/.local/share/mise/installs/luau/{0.734,0.742}/{luau,luau-compile,luau-analyze}`.

---

## §1 수준별로 하는 일
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/optimize-fold-unroll.luau`, `snippets/optimize-inline-rules.luau`, `run_opt.sh` F1–F7, E1 · 소스: `Compiler/include/Luau/Compiler.h:31-34`, `Compiler/src/Compiler.cpp` compileOrThrow

| 수준 | 소스 주석 | 실측으로 확인한 것 |
|---|---|---|
| 0 | no optimization | 상수도 `LOADK` 로 싣고 그대로 계산한다 |
| 1 (CLI 기본) | baseline, 디버깅을 해치지 않음 | 산술·문자열 연결·if-식·`#"리터럴"`·로컬 상수 전파를 접는다(`K * 2 + 1` → `LOADN 21`). 내장 함수 빠른 호출(`FASTCALL`)과 import(`GETIMPORT math.sqrt`)도 쓴다 |
| 2 | 디버깅을 해치는 최적화(인라인 등) 포함 | 위에 더해 **내장 함수 호출 접기**(`math.sqrt(16)` → 4), **함수 인라인**, **고정 횟수 루프 펼치기**(4 회는 펼침, 100 회는 "too many iterations") |

- 수준 2 의 내장 접기는 파일이 `getfenv`/`setfenv` 를 쓰지 않을 때만 켜진다(소스 주석 "we can't de-optimize folding at runtime").
- 수준 2 는 타입 주석으로 타입 맵을 만든다(`typeInfoLevel >= 1 || optimizationLevel >= 2`). native 코드 생성에서 파라미터 주석이 쓰이는 이유다(native-codegen.md §4).

## §2 수준을 정하는 곳과 우선순위
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `run_opt.sh` A1–A3, B1–B4, `snippets/native-directive-forces-o2.luau`, `snippets/native-attribute-forces-o2.luau`, `snippets/native-directive-order.luau` · 소스: `Compiler.cpp:5861-5892`

적용 순서는 이렇다. 뒤의 것이 앞의 것을 덮는다.
1. 호스트가 준 값(CLI `-O<n>`, Roblox 엔진 설정).
2. 파일 머리 지시어를 **위에서부터** 차례로 적용:
   - `--!optimize N` → 수준 N. 0..2 로 잘린다(`--!optimize 5` 는 2).
   - `--!native` → 수준 2, 타입 정보 수준 1.
3. 파일 안에 `@native` 함수가 **하나라도** 있으면 → 수준 2, 타입 정보 수준 1.

따라서:
- `--!optimize 1` 은 CLI `-O2` 를 이기고, `--!optimize 2` 는 CLI `-O0` 을 이긴다(A1, A2).
- `--!native` 다음 줄에 `--!optimize 1` 을 쓰면 1 이 된다. 순서를 바꾸면 2 가 된다(`native-directive-order.luau`, A3).
- `@native` 는 2단계 뒤에 적용되므로 `--!optimize 1` 보다 우선한다. 관계없는 함수 하나에 `@native` 를 붙여도 **모듈 전체가 인라인 대상**이 된다(`native-attribute-forces-o2.luau`).
- 지시어는 첫 토큰 앞에만 유효하다. 코드 뒤에 쓴 `--!optimize 2` 는 무시된다. 이때 `luau-analyze` 가 `CommentDirective: Comment directive is ignored because it is placed after the first non-comment token` 린트를 낸다. 범위 밖 값에는 `optimize directive uses unknown optimization level '5', 0..2 expected`, 오타(`--!optimise`)에는 `did you mean 'optimize'?` 를 낸다. 린트라서 `check_snippets.py` 는 판정하지 않는다(재현: `/tmp` 에 그런 파일을 두고 `luau-analyze` 로 실행, 2026-11-10 0.734/0.742 동일).

## §3 `-O2` 인라인 조건
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/optimize-inline-rules.luau`(호출 12개에 기대 태그), `run_opt.sh` E1 · 소스: `Compiler.cpp` compileFunction(canInline 기록, `:641-652`), getFunctionExpr(`:352-378`), tryIndexConstantTable(`:303-`), tryCompileInlinedCall(`:935-1028`), compileExprCall(`:1375-1412`), `ConstantFolding.cpp` buildTableConstantMap(`:1314`)

| 호출 모양 | 인라인 | 이유(remark 문구) |
|---|---|---|
| `local function f` / `local f = function` 를 직접 호출 | 됨 | 비용 모델을 통과하면 |
| **상수 테이블 리터럴의 필드** `local K = { f = function … end }` 후 `K.f(x)` | **됨** | 0.724 동기화(2026-06-05)부터. 테이블이 생성 뒤 바뀌지 않고 밖으로 새지 않을 때 |
| 위 테이블을 다른 함수에 넘기거나(`print(Esc)`), `return` 하거나, 필드에 대입(`Wr.g = 1`) | 안 됨 | 상수 테이블이 아니게 됨(remark 없음) |
| `local M = {}; function M.f() end` 후 `M.f(x)` | 안 됨 | 필드 대입으로 만든 테이블 |
| 다시 대입된 로컬 함수 | 안 됨 | remark 없음 |
| 메서드 호출 `obj:m(x)` | 안 됨 | `self` 호출은 시도도 하지 않음 |
| 가변 인자 함수 `function(...)` | 안 됨 | `function is variadic` |
| 다중 반환 함수를 다중 반환 자리에서(`print(multi(v))`) | 안 됨 | `can't convert fixed returns to multret` |
| 단일 반환 함수를 다중 반환 자리에서(`print(small(v))`) | 됨 | 항상 값 하나를 돌려주면 고정 반환으로 바꿈 |
| 재귀 함수 | 바깥 호출 1회는 됨, 자기 호출은 안 됨 | `can't inline recursive calls` |
| 가변 upvalue 를 쓰는 함수 | 됨 | |
| 몸통이 큰 함수 | 안 됨 | `too expensive (cost 48, profit 1.06x)`. 기준 25 × 이득 배율(최대 3배). 상수 인자를 주면 비용이 내려가 될 수 있다 |
| 파일 어디서든 `getfenv`/`setfenv` 라는 이름이 나옴 | 파일 전체 안 됨 | `module uses getfenv/setfenv`. 읽기만 해도 끈다 |

- 그 밖의 한도: 인라인 깊이 5, 레지스터 압력(호출 지점 regTop > 128 이거나 피호출 스택 > 32).
- 인라인을 막는 사용자용 속성(`@noinline`, `@inline`)은 없다. `@inline` 은 SyntaxError 다(`snippets/native-attribute-syntax.luau`). `@debugnoinline` 은 디버그 플래그(`--fflags=DebugLuauNoInline=true`) 아래에서만 받아들여진다. Roblox 에서는 쓸 수 없다.

## §4 `-O2` 와 `error(msg, level)` 위치 (D-10)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/optimize-o2-error-level.luau`, `snippets/optimize-o1-error-level.luau`(대조군), `run_opt.sh` B1–B4, C1–C2 · 관련: decisions D-10, `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/snippets/testing-o2-line-probe.luau`(테스트 주제 에이전트의 관측용 스니펫)

`error(msg, 2)` 는 "나를 부른 프레임"을 가리킨다. 인라인된 함수에는 프레임이 없으므로 level 이 한 칸씩 밀린다.

| 경우 | `-O1` | `-O2` |
|---|---|---|
| 로컬 함수 `check` 를 `pcall` 직속 함수가 호출 | 호출 줄 | **위치 없음**(level 2 = `pcall` C 프레임) |
| 호출자가 인라인되지 않는 함수(가변 인자) 안에서 호출 | 호출 줄 | **틀린 줄**: 호출자의 호출자 줄을 가리킨다 |
| 상수 테이블 리터럴 필드 `T.check` | 호출 줄 | **위치 없음**(인라인됨) |
| 필드 대입으로 만든 `M.check` | 호출 줄 | 호출 줄(인라인 안 됨) |

- D-10 은 "위치가 사라진다"만 적었다. 실측으로는 **엉뚱한 줄을 가리키는 경우**도 있다. 위치가 없으면 눈에 띄지만 틀린 줄은 디버깅을 잘못 이끈다.
- D-10 과 quad 스파이크 27 의 "테이블 필드 경유면 안전"은 **절반만 맞다**. `function M.f()` 처럼 대입으로 만든 필드는 안전하다. 하지만 `local T = { f = function … end }` 로 만들고 그 테이블을 밖으로 넘기지 않으면 인라인된다(0.734, 0.742 모두). 모듈이 `return T` 하면 안전하다.
- 네이티브 실행(`--codegen`) 자체는 위치를 바꾸지 않는다. `--!optimize 1` 파일을 `--codegen` 으로 돌려도 위치가 보존된다(C1). 위치를 바꾸는 것은 수준 2 다.

**처방** (D-10 안 A-2 의 근거 보강):
1. 라이브러리가 사용자 호출 줄을 가리켜야 하면 손으로 센 `level` 을 쓰지 않는다. 스택을 걸어 첫 비라이브러리 프레임을 찾는 raise 헬퍼를 둔다. 그 헬퍼도 인라인되지 않게 해야 한다. 가변 인자로 만들거나 필드 대입 테이블 경유로 부르면 된다(§3 표).
2. 에러 단언 테스트는 **`-O1` 과 `-O2` 양쪽에서** 메시지와 사용자 줄을 단언한다. `run_opt.sh` B 절처럼 `--!optimize` 줄만 바꾼 사본으로 두 번 돌리면 된다.

## §5 스택 프레임과 `debug.*`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/optimize-o2-traceback.luau`, `run_opt.sh` C3 · 원천: luau.org/performance "Function inlining and loop unrolling"("a function call is compiled as a function call, which may be observable via debug.traceback")

- `-O2` 에서 인라인된 함수는 `debug.traceback` 에 `function inner` 같은 줄이 없다. 줄 번호는 인라인된 몸통의 원래 줄이 바깥 프레임에 남는다.
- 인라인된 자리에서 `debug.info(1, "n")` 는 바깥 함수의 이름을 돌려준다(최상위면 `""`). 가변 인자 함수(인라인 안 됨)는 자기 이름을 돌려준다.
- `debug.info(2, "l")` 로 "호출자 줄"을 재는 헬퍼도 같은 이유로 `-O2` 에서 깨진다(testing 주제의 `testing-o2-line-probe.luau` 가 관측).

## §6 디버그 수준 `-g0/1/2`
status: verified(-g0, -g1) / described(-g2) · last-confirmed: luau 0.742 · 근거: `run_opt.sh` D1–D2, 실측 명령 `luau -g0 e4.luau`(2026-11-10) · 소스: `Compiler.h:36-39`

| 수준 | 소스 주석 | 실측 |
|---|---|---|
| 0 | 디버그 지원 없음 | 에러 메시지에 `파일:줄:` 이 없다. traceback 에 줄이 없다. `debug.info(f, "n")` 이름이 `""`, `"l"` 은 0 |
| 1 (기본) | 줄 정보와 함수 이름. traceback 에 충분 | 위치와 이름이 다 나온다 |
| 2 | 로컬·upvalue 이름까지. 디버거에 필요 | CLI 에서 1 과 구별되는 출력은 찾지 못했다(Luau 의 `debug` 라이브러리에는 로컬 조회가 없다). described |

- `-g` 와 `-O` 는 서로 독립이다. `-O2 -g2` 여도 인라인된 프레임은 돌아오지 않는다(실측: traceback 결과가 `-O2 -g1` 과 같음).

## §7 Roblox 의 기본값
status: described · 원천: create.roblox.com/docs/en-us/luau/comments.md "Comment directives"(2026-11-10판)

- 공식 문서: `--!optimize` 의 기본값은 **Studio 테스트에서 1, 라이브 게임에서 2**. "Exact optimizations aren't published and are subject to change."
- 그 결과(CLI 실측에서 추론, Roblox 안에서는 미확인):
  - `error(msg, 2)` 위치, `debug.traceback`, `debug.info` 결과가 Studio 플레이 테스트와 라이브 서버에서 다를 수 있다. Studio 에서 통과한 에러 위치 테스트가 라이브에서 틀릴 수 있다.
  - Studio 에서 라이브와 같은 조건을 보려면 파일 머리에 `--!optimize 2` 를 둔다(§2 우선순위가 엔진에서도 같다고 가정).
  - `--!native` 나 `@native` 를 쓴 스크립트는 Studio 에서도 수준 2 가 된다(§2, CLI 실측).
- Roblox 의 디버그 수준(`-g`)은 공개 문서에서 찾지 못했다. 라이브 에러에 줄 번호가 나오므로 1 이상이라고 추정한다.
- Roblox Studio 가 지원한다고 문서에 적힌 지시어: `--!strict`, `--!nonstrict`, `--!nocheck`, `--!native`, `--!nolint`, `--!optimize 0|1|2`.

## §8 확인하는 법
status: verified · 근거: `run_opt.sh` 전체(29 검사 × 2 버전 = 58 ok, 2026-11-10)

```bash
L=/code/.local/share/mise/installs/luau/0.742
$L/luau-compile --remarks -O2 file.luau   # 호출 줄 위에 "inlining succeeded/failed: 이유", "loop unroll …" 이 붙는다
$L/luau-compile --text -O1 file.luau      # 바이트코드. 접힌 상수(LOADN/LOADK), FASTCALL, GETIMPORT 를 본다
$L/luau -O2 file.luau                      # 수준별 실행(파일 머리 --!optimize 가 있으면 그게 이긴다)
bash /code/Projects/claude-doctor/drafts/gaps/tools/run_opt.sh 0.734 0.742   # 이 문서와 native-codegen.md 의 CLI 의존 주장 일괄 검사
```

- `check_snippets.py` 의 `--@run` 은 CLI 기본(`-O1 -g1`, 인터프리터)으로만 돈다. 수준별 런타임 주장은 스니펫 머리에 `--!optimize N` 을 넣어 하네스 안에서 검증하거나, `run_opt.sh` 처럼 CLI 플래그를 바꿔 돌린다.
- `-O2` 에서 인라인을 하나만 끄고 비교하려면 `--fflags=DebugLuauNoInline=true` 와 함수 앞 `@debugnoinline` 을 쓴다(CLI 전용, 0.734/0.742 확인).

## §9 공식 문서와 실측이 어긋난 곳
status: verified · last-confirmed: luau 0.742 (0.734 동일)

| 문서 | 문서의 말 | 실측 |
|---|---|---|
| luau.org/performance (2026-10-20) | "Only local functions (defined either as `local function foo` or `local foo = function`) can be inlined." | 상수 테이블 리터럴의 필드 함수도 인라인된다(`optimize-inline-rules.luau` `K.f`, `optimize-o2-error-level.luau` `T.check`). 소스 `tryIndexConstantTable`, 0.724 동기화 커밋 `8f33df9`(2026-06-05)에서 들어옴 |
| luau.org/performance | "recursive invocations of a function can't be inlined" | 재귀 함수라도 **다른 함수에서의 첫 호출**은 인라인된다. 안 되는 것은 자기 자신 안의 호출뿐이다 |
| decisions D-10, quad 스파이크 27 | `-O2` 는 "테이블 필드 경유 호출은 인라인하지 않는다", 그래서 테이블 경유가 안전 | 대입으로 만든 필드(`function M.f`)만 안전. 리터럴로 만든 테이블은 인라인됨 |
| decisions D-10 | `-O2` 에서 위치가 "사라진다" | 사라지거나 **틀린 줄**(호출자의 호출자)을 가리킨다 |
| create.roblox.com luau/native-code-gen.md (2026-11-10) | native 스크립트는 "behavior … is exactly the same as before and only the performance is different" | `--!native`/`@native` 는 컴파일 수준을 2 로 올린다. Studio 테스트(기본 1)에서 `--!native` 를 붙이면 `error(msg, 2)` 위치와 traceback 이 바뀐다(CLI 실측, 엔진 안 미확인). native-codegen.md §3 |

---
들어갈 luau-kb 스킬: **luau-perf** (references `optimize-levels.md`). §4 는 luau-testing 의 에러 단언 절에서 링크한다.
