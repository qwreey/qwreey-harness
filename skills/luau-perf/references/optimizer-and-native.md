# optimizer-and-native — 최적화 수준, 인라인, 인라인 캐시, native 코드 생성

## 이 파일이 답하는 질문
- Q1 `-O0/1/2` 는 각각 무엇을 하나? `--!optimize`, CLI `-O`, `--!native`, `@native` 가 겹치면 무엇이 이기나?
- Q2 `-O2` 는 어떤 호출을 인라인하나? 인라인되면 얼마나 빨라지나?
- Q3 `-O2` 에서 `error(msg, 2)` 위치가 틀리는 이유와 처방은? (D-10 정정)
- Q4 `t.Name` 과 `t[1]` 은 언제 차이가 나나(인라인 캐시)?
- Q5 다른 모듈의 상수를 키로 쓰면 느린가? `::` 캐스트는 비용이 있나?
- Q6 native(`--!native`, `@native`, `--codegen`)는 언제 이득이고 언제 손해인가? 타입 주석은 무엇을 바꾸나?
- Q7 인라인·native 여부를 어떻게 확인하나?

## 목차
- §1 결론
- §2 수준별로 하는 일과 우선순위
- §3 `-O2` 인라인: 조건과 값
- §4 `-O2` 와 `error(msg, level)` (D-10 정정)
- §5 인라인 캐시와 상수 키
- §6 native 코드 생성
- §7 확인하는 법
- §8 정정과 조건 차이

---

## §1 결론
- `-O2` 의 가장 큰 이득은 **인라인**이다. 같은 파일의 작은 지역 함수 호출이 공짜가 된다(0.742: `-O1` 2.35x → `-O2` 1.01x). 다른 모듈의 함수, 필드 대입으로 만든 함수, 가변 인자 함수, 메서드 호출은 인라인되지 않는다.
- 인라인은 스택 프레임을 지운다. 그래서 `error(msg, 2)`, `debug.traceback`, `debug.info` 결과가 `-O1` 과 다르다. 손으로 센 level 은 쓰지 않는다.
- native 는 숫자·vector 연산에서 크고(인라인 위에 다시 2.5 배), 할당 위주 코드에서는 몇 %다. 인라인되지 않는 vector 함수는 파라미터 주석이 없으면 native 가 오히려 느렸고(`-O2` 24.6 → native 29.1 ms), 주석과 다른 타입을 넘기면 손해다.
- `--!native`·`@native` 는 그 파일을 **최적화 수준 2 로 올린다.** native 를 붙이는 순간 에러 위치가 바뀔 수 있다.

## §2 수준별로 하는 일과 우선순위
status: verified · last-confirmed: luau 0.742 (0.734 동일), `run_opt.sh` 58/58 ok (2026-11-10 재실행) · 근거: `/code/Projects/claude-doctor/drafts/gaps/optimize-levels.md` §1·§2, 스니펫 `snippets/opt-fold-unroll.luau`, `snippets/native-directive-forces-o2.luau`, `native-attribute-forces-o2.luau`, `native-directive-order.luau`, 소스 `Compiler.cpp:5855-5892`

| 수준 | 하는 일 |
|---|---|
| 0 | 최적화 없음. 상수도 그대로 계산 |
| 1 (CLI 기본, Studio 테스트 기본) | 산술·문자열 연결·로컬 상수 접기, `FASTCALL`(내장 함수 빠른 호출), `GETIMPORT` |
| 2 (Roblox 라이브 기본, 문서) | 위 + **함수 인라인**, 고정 횟수 루프 펼치기(4 회 펼침, 100 회는 안 함), 내장 호출 접기(`math.sqrt(16)` → 4). 파라미터 타입 주석으로 타입 맵을 만든다 |

우선순위(뒤가 앞을 덮는다): 호스트 값(CLI `-O`, 엔진) → 파일 머리 지시어를 위에서부터(`--!optimize N`, `--!native` = 수준 2 + 타입 정보 1) → 파일 안에 `@native` 함수가 하나라도 있으면 수준 2.
- `--!native` **다음 줄에** `--!optimize 1` 을 두면 1 로 돌아간다. 순서를 바꾸면 2 다.
- 관계없는 함수 하나에 `@native` 를 붙여도 **모듈 전체**가 인라인 대상이 된다.
- 내장 접기와 인라인은 파일 어디에든 `getfenv`/`setfenv` 라는 이름이 나오면 파일 전체에서 꺼진다.
- fastcall 은 내장 라이브러리 함수만 받는다. 사용자 함수에는 없다(S-P49, described).

## §3 `-O2` 인라인: 조건과 값
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/opt-inline.luau`(call 그룹), `bench/call-closures.luau`, 스니펫 `snippets/opt-inline-rules.luau`(호출 12 개에 기대 태그), 후보 S-P26, S-P31, Q-088

인라인되는 것과 안 되는 것(`luau-compile --remarks -O2` 로 확인):

| 호출 모양 | 인라인 |
|---|---|
| `local function f` / `local f = function` 직접 호출 | 됨(비용 모델 통과 시) |
| 상수 테이블 리터럴의 필드 `local K = { f = function … end }` 후 `K.f()`, 그 표를 밖으로 넘기지 않을 때 | **됨** (0.724 부터) |
| 위 표를 넘기거나 `return` 하거나 필드에 대입 | 안 됨 |
| `local M = {}; function M.f() end` 후 `M.f()` | 안 됨 |
| 다른 모듈(`require`)의 함수 | 안 됨 |
| 메서드 `obj:m()`, 가변 인자 함수, 다시 대입된 지역 함수 | 안 됨 |
| 재귀 함수 | 바깥 첫 호출만 됨 |
| 몸통이 큰 함수 | 안 됨(`too expensive`, 기준 비용 25 × 이득 최대 3 배) |

값(200만 호출, 기준 = 필드 `a.n` 직접 읽기):

| 호출 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native |
|---|---|---|---|---|
| 같은 파일 지역 함수 `lenLocal(a)` | 2.47 | 2.35 | **1.01** | **0.99** |
| `lenLocal(a :: any)` (캐스트) | 2.45 | 2.30 | 1.00 | 0.99 |
| 다른 모듈 함수(local 로 받음) | 2.39 | 2.22 | 2.22 | 3.07 |

- `::` 캐스트는 런타임 비용이 0 이다(S-P31). 다만 `(f()) :: T` 처럼 다중 반환을 하나로 자르는 의미 변화는 별개다(luau-style).
- 벤치에서 비교 대상을 같은 파일에 흉내 내면 `-O2` 에서 인라인되어 실제와 다른 결론이 나온다(`benchmarking-method.md` §5).
- 인라인을 막는 사용자 속성(`@noinline`)은 없다. `@inline` 은 SyntaxError 다. 막아야 하면 필드 대입 테이블을 거치거나 가변 인자로 만든다.

## §4 `-O2` 와 `error(msg, level)` (D-10 정정)
status: verified · last-confirmed: luau 0.742 (0.734 동일), `run_opt.sh` B1–B4, C1–C3 · 근거: `drafts/gaps/optimize-levels.md` §4·§5, 스니펫 `snippets/opt-o2-error-level.luau`, `opt-o1-error-level.luau`(대조군), `opt-o2-traceback.luau`, `/code/Projects/claude-doctor/decisions/D-10-error-handling.md` "정정" 절, 후보 S-116(+S-118, R-44), Q-088

`error(msg, 2)` 는 "나를 부른 프레임"을 가리킨다. 인라인된 함수에는 프레임이 없어 level 이 밀린다.

| 경우 | `-O1` | `-O2` |
|---|---|---|
| 지역 함수 `check` 를 `pcall` 직속 함수가 호출 | 호출 줄 | **위치 없음**(level 2 = `pcall` C 프레임) |
| 호출자가 인라인되지 않는 함수(가변 인자) 안에서 호출 | 호출 줄 | **틀린 줄**(호출자의 호출자) |
| 상수 테이블 리터럴 필드 `T.check` | 호출 줄 | **위치 없음**(인라인됨) |
| 필드 대입으로 만든 `M.check` | 호출 줄 | 호출 줄 |

- native 실행 자체는 위치를 바꾸지 않는다(`--!optimize 1` + `--codegen` 은 위치 보존). 바꾸는 것은 수준 2 다.
- `-O2` 의 `debug.traceback` 에는 인라인된 함수 줄이 없다. `debug.info(1, "n")` 은 바깥 함수 이름을 돌려준다. `-g2` 로도 돌아오지 않는다.
- 처방: 라이브러리가 사용자 호출 줄을 가리켜야 하면 손으로 센 level 대신 스택을 걸어 첫 비라이브러리 프레임을 찾는 헬퍼를 둔다(헬퍼도 인라인되지 않게). 에러 단언 테스트는 `-O1` 과 `-O2` 양쪽에서 돈다. 테스트 쪽 규칙(같은 스위트를 `-O1`·`-O2` 로 두 번)은 luau-testing 스킬 `references/optimize-levels.md` 가 다룬다.

## §5 인라인 캐시와 상수 키
status: verified · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/opt-inline.luau`(ic-name, ic-slot, const-key 그룹), `bench/tbl-access.luau`(field-vs-slot), 후보 S-P21, S-P22, S-P24, S-P25

상수 문자열 필드 읽기(`GETTABLEKS`)는 명령 자리마다 "그 키가 지난번에 있던 칸"을 기억한다. 한 자리가 칸 배치가 다른 표들을 번갈아 보면 기억이 빗나간다.

| 비교 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native | 원천(stl 44절, `-O2`) |
|---|---|---|---|---|---|
| `t.Name`: 모양 다른 표 넷을 번갈아 (대 같은 모양 넷) | 0.99 | 1.13 | 1.15 | **1.81** | 6.5 대 5.1 ns(1.3x) |
| `t[1]`: 같은 비교 | 0.99 | 1.01 | 0.99 | 1.01 | 4.6 대 4.7 ns |
| 단건 `n[1]` (대 `n.value`, 표 하나) | 0.86 | 0.95 | 0.94 | 0.99 | 4.7 대 5.1 ns |
| `t[KEY]`, KEY = 다른 모듈 상수 (대 `t["__type"]` 리터럴) | 1.03 | 1.06 | 1.04 | 1.02 | 생성 7~11% 느림(21절) |

- 표가 하나면 이름 필드와 번호 칸은 거의 같다. 다형 자리(여러 컨테이너를 한 함수로 다루는 공용 코드)에서만 번호 칸이 낫다. native 에서 차이가 가장 크다.
- 다른 모듈에서 받은 상수 키는 `SETTABLEKS`(상수 키 명령)를 못 써 2~6% 느렸다. 잡음 경계라 큰 결론은 아니다. 리터럴이나 같은 파일의 리터럴 지역 상수로 적으면 된다.
- 키 이름만 바꿔도 해시 칸 배치가 바뀌어 ±5% 흔들린다(S-P25). 이름 선택으로 성능을 고르지 않는다.

## §6 native 코드 생성
status: verified(CLI) / described(Roblox) · last-confirmed: luau 0.742 (0.734 대조) · 근거: `bench/native-annot.luau`, `drafts/gaps/native-codegen.md` §1~§7, `run_opt.sh` G1–G7·H1–H2, 스니펫 `snippets/native-annotation-codegen.luau`, `native-attribute-nested.luau`, 후보 M-06

어디서 도나: Roblox 에서는 **서버 스크립트와 Android 클라이언트**에서만, `--!native`(파일 전체+루프 있는 최상위) 또는 `@native`(그 함수 하나만, 안의 클로저 제외)를 단 것만. CLI `luau --codegen` 은 지시어와 무관하게 불러온 모든 모듈을 컴파일한다.

타입 주석: 컴파일러는 타입 검사기의 추론을 쓰지 않고 **소스에 적은 주석만** 읽는다.
- 파라미터 주석은 `-O2` 이상 또는 타입 정보 수준 1(`--!native`, `@native`)에서 쓰인다. `-O1` 에서는 무시된다.
- 로컬·`::`·업밸류 주석은 타입 정보 수준 1 에서만 쓰인다(CLI `-O2` 만으로는 무시).
- `vector?` 같은 옵셔널 주석은 특수화에 쓰이지 않는다. `any` 는 주석이 없는 것과 같다. Roblox 에서는 `Vector3` 가 벡터 타입이다(문서, described).

런타임(100만 호출, 인라인되지 않게 필드 대입 표를 거쳐 부름). 기준 = 주석 없는 함수에 vector 를 넘김.

| 케이스 | 0.734 `-O1` | 0.742 `-O1` | 0.742 `-O2` | 0.742 native |
|---|---|---|---|---|
| `v: vector` 주석, vector 넘김 | 1.06 | 1.00 | 0.99 | **0.43** |
| `v: vector` 주석, 테이블 넘김(불일치) | 1.09 | 1.04 | 1.03 | 1.06 |
| 주석 없음, 테이블 넘김 | 1.01 | 1.04 | 1.03 | 0.62 |

| 일의 종류(절대 시간, 0.742) | `-O1` | `-O2` | native | native 이득 |
|---|---|---|---|---|
| 작은 숫자 함수 호출(인라인 가능) | 18.9 ms | 6.5 ms | 2.5 ms | `-O2` 대비 2.6 배 |
| 문자열·테이블 할당 위주 | 35.1 ms | 33.6 ms | 31.6 ms | `-O2` 대비 6% |

- 이득 순서: 인라인(`-O1` → `-O2` 3 배) 다음 native(2.6 배). 기준 행(주석 없는 vector, 인라인 안 됨)의 절대 시간은 `-O1` 24.3 / `-O2` 24.6 / native **29.1 ms** 로, 주석 없이는 native 가 손해였다. 인라인되지 않는 호출에서는 **파라미터 타입 주석이 native 이득의 대부분**이다(vector 0.43x).
- 손해: `v: vector` 함수에 테이블을 넘기면 같은 테이블을 주석 없는 함수에 넘길 때보다 1.7 배 느렸다(1.06 대 0.62). `any` 를 받는 함수에 성급히 구체 타입을 달지 않는다.
- 할당 위주 코드(파서, 문자열 조립)는 native 로 몇 %~10% 다(M-06: mrow 1.40 → 1.06 ms, 7.93 → 6.93 ms). 할당을 줄이는 쪽이 먼저다.
- 메타테이블 정수 칸 세금은 native 에서 커진다(`metatables.md` §2). native 를 쓸 코드일수록 원소를 메타테이블 없는 표에 둔다.
- 한도(소스 기본값, 문서와 같음): 블록 하나 IR 65,536, 함수 하나 블록 32,768, 모듈 전체 IR 1,048,576. 루프 없는 최상위 코드는 cold 로 건너뛴다. 브레이크포인트를 건 함수는 native 가 꺼진다(문서, described).

## §7 확인하는 법
status: verified(CLI)

```bash
L=/code/.local/share/mise/installs/luau/0.742
$L/luau-compile --remarks -O2 f.luau        # "inlining succeeded/failed: 이유", "loop unroll …"
$L/luau-compile --text -O1 f.luau           # 바이트코드: LOADN/LOADK(접힌 상수), FASTCALL, GETIMPORT, GETTABLEKS
$L/luau-compile --codegen -O2 --record-stats=function --stats-file=/tmp/st.json f.luau  # 함수별 asmSize
$L/luau-compile --codegenir -O2 f.luau      # IR: CHECK_TAG, fallback 블록
choom -n 1000 -- prlimit --data=3221225472 -- $L/luau -O2 --codegen bench.luau
bash /code/Projects/claude-doctor/drafts/gaps/tools/run_opt.sh 0.734 0.742   # 이 파일의 CLI 주장 일괄 검사(58 개)
```
- `-O2` 에서 인라인 하나만 끄려면 `--fflags=DebugLuauNoInline=true` 와 함수 앞 `@debugnoinline`(CLI 전용).
- Roblox: Script Profiler 의 `<native>` 표시, 서버 콘솔 `debug.dumpcodesize()`, heap 프로파일러의 `[native]`(문서, described).

## §8 정정과 조건 차이
| 원천 | 원래 서술 | 실측 | 처리 |
|---|---|---|---|
| decisions D-10, quad 스파이크 27 (Q-088) | "`-O2` 는 테이블 필드 경유 호출을 인라인하지 않는다 → 테이블 경유가 안전" | 필드 대입(`function M.f`)만 안전. 리터럴 테이블 필드는 인라인됨 | **정정**(D-10 정정 절에 이미 반영) |
| decisions D-10 | `-O2` 에서 위치가 "사라진다" | 사라지거나 **틀린 줄**을 가리킨다 | **정정**(같음) |
| luau.org/performance (2026-10-20) | "Only local functions … can be inlined", "recursive invocations can't be inlined" | 상수 테이블 리터럴 필드도 인라인. 재귀 함수의 바깥 첫 호출은 인라인 | 문서 보충 |
| Roblox native-code-gen.md (2026-11-10) | native 스크립트는 "only the performance is different" | `--!native`/`@native` 는 수준 2 로 올려 에러 위치·traceback 을 바꾼다(CLI 실측, 엔진 안 미확인) | 문서 보충 |
| stl perf 44절 (`perf-measurements.md:1204-1222`) | 다형 자리 `t.Name` 1.4 배 | 0.734 `-O1` 차이 없음(0.99), 0.742 인터프리터 1.13~1.15x, native 1.81x | 버전·모드 조건 명시 |
| stl perf 21절 (`:597-600`) | 다른 모듈 상수 키로 생성 7~11% 느림 | 2~6% | 같은 방향, 잡음 경계 |
