# testing — Luau/Roblox 테스트 프레임워크 현황과 순수 luau 테스트 패턴

> 초안 2026-11-10. luau-kb 이전용(스킬 `luau-testing`). 실측: luau 0.734·0.742(`/code/.local/share/mise/installs/luau/<v>/luau`), luau-lsp 1.70.1, lune 0.10.5. 스니펫은 `claude-doctor/drafts/gaps/snippets/testing-*.luau`(6개, 하네스 두 버전 통과).

## 이 파일이 답하는 질문
- Q1 Roblox 코드 테스트에 jest-lua, TestEZ, Jest Roblox 중 무엇을 고르나? 각각 지금 유지되고 있나?
- Q2 Roblox 없이(순수 `luau` CLI) 테스트를 돌리려면 무엇을 알아야 하나? 인자, 종료 코드, require, 커버리지는?
- Q3 에러 메시지와 "사용자 줄"을 단언하는 테스트는 어떻게 써야 `-O2` 에서도 맞나?
- Q4 손으로 만든 `eq<T>` 단언 헬퍼가 타입 불일치를 잡지 못하는 이유는?
- Q5 Roblox API 에 기대는 코드는 엔진 밖에서 어떻게 시험하나? CI 로는 무엇이 있나?
- Q6 이 사용자의 저장소들(quad, stl-luau, table-sim, rbvm)은 실제로 어떻게 테스트하나?

## 목차
- §1 지형도: 세 갈래와 프레임워크별 상태표
- §2 Jest Roblox 와 jest-lua(jsdotlua)
- §3 TestEZ (보관됨)
- §4 순수 `luau` CLI 를 러너로 쓸 때의 사실들
- §5 에러 단언: 메시지 모양과 `-O2` 에서 사용자 줄
- §6 `getfenv` 로 mock 을 주입하면 그 모듈의 인라이닝이 꺼진다
- §7 단언 헬퍼의 타입: `eq<T>` 는 불일치를 못 잡는다
- §8 최소 러너와 러너 음성 대조군
- §9 독립 런타임 러너: lune, lute
- §10 Roblox 의존 코드: mock·fake·분리, 그리고 CI 경로
- §11 이 사용자 저장소 실태
- §12 실측으로 드러난 것: quad 스펙 3개가 `-O2` 에서 실패
- §13 고르는 법(결정 요약)

표기: `verified` 는 스니펫이나 수동 실행으로 두 luau 버전에서 확인했다는 뜻, `described` 는 외부 원천의 서술만 있고 여기서 실행하지 않았다는 뜻이다. 외부 저장소의 날짜는 GitHub REST API 로 2026-11-10 에 조회한 값이다.

---

## §1 지형도: 세 갈래와 프레임워크별 상태표
status: described · last-confirmed: 2026-11-10 (GitHub API, wally 레지스트리) · 근거: 아래 표의 출처 열

테스트를 돌리는 자리는 셋이다.
1. **Roblox 런타임 안**(Studio, Open Cloud Luau Execution, Roblox 내부 `roblox-cli`): Jest Roblox, TestEZ.
2. **독립 Luau 런타임**(lute, lune): lute 는 `lute test` 러너와 `@std/test` 를 내장했다. lune 에는 테스트 러너가 없다.
3. **순수 `luau` CLI**: 프레임워크 없이 `assert` + `pcall`. 이 사용자의 저장소 넷이 모두 이 방식이다(§11).

| 이름 | 저장소 | 상태(2026-11-10) | 최신 버전 | Roblox 밖 실행 |
|---|---|---|---|---|
| Jest Roblox | `Roblox/jest-roblox` | 활성. 마지막 push 2026-11-10 | wally `roblox/jest` 3.20.1. 문서 사이트 머리 v3.20.1. GitHub 태그는 v3.8.0 에 멈춤 | 불가. "tests run in a Roblox environment … Studio or OCALE" |
| jest-lua | `jsdotlua/jest-lua` (Roblox/jest-roblox 의 포크) | 사실상 정지. 마지막 push·릴리스 2024-12-23 (v3.10.0) | wally `jsdotlua/jest` 3.10.0 | 불가. README: "can currently only run inside of Roblox" |
| TestEZ | `Roblox/testez` | **archived**. 마지막 push 2024-03-05 | v0.4.2 (2022-01-05) | README 가 Lemur 를 들지만 Lemur(`LPGhatguy/lemur`)도 archived(2020-06) |
| run-in-roblox | `rojo-rbx/run-in-roblox` | 정지. 마지막 push 2024-03-06 | v0.3.0 (2020-07-20) | Studio 를 띄워 스크립트를 돌리고 출력을 stdout 으로 넘김 |
| lute | `luau-lang/lute` | 활성. v1.0.0 (2026-04-16), 나이틀리 매일 | v1.0.1-nightly.20261110 | 예(자체 런타임). 로컬 미설치 |
| lune | `lune-org/lune` | 활성. v0.11.1 (2026-10-21) | 로컬 0.10.5 | 예. 테스트 러너는 없음 |

## §2 Jest Roblox 와 jest-lua(jsdotlua)
status: described · last-confirmed: 2026-11-10 · 근거: `Roblox/jest-roblox` README·`docs/docs/GettingStarted.md`·`docs/docs/Deviations.md`(HEAD, 2026-11-10), `jsdotlua/jest-lua` README, wally API

- **관계**: Jest Roblox 가 원본이다(Jest v27.4.7 포팅). `jsdotlua/jest-lua` 는 그 포크로, Roblox 가 공개 저장소를 한동안 갱신하지 않던 시기에 wally 배포용으로 만들어졌다. 지금은 Roblox 가 `roblox/*` 스코프로 wally 에 직접 올린다(README: "34 modules under the `roblox/*` scope"). 새로 고른다면 jsdotlua 판을 쓸 이유가 없다.
- **설치**: wally `dev-dependencies` 에 `Jest = "roblox/jest@…"`, `JestGlobals = "roblox/jest-globals@…"`. Creator Store 자산(16031830738)으로도 받는다.
- **실행**: `spec.lua` 엔트리에서 `Jest.runCLI(Packages.Project, { verbose, ci }, { Packages.Project }):awaitStatus()` 를 부르고 결과가 실패면 `error` 한다. 이 엔트리를 Studio 나 Open Cloud Luau Execution(§10) 에서 돌린다. 문서의 `roblox-cli run … --fastFlags.overrides EnableLoadModule=true` 는 `<Internal>` 블록 안에 있다(Roblox 사내 도구).
- **Luau 쪽 차이**(Deviations.md): `not` 이 예약어라 `.never` 를 쓴다. `expect(x).toBe(y)` 는 점 호출이다. `.toBeFalsy()` 는 `false`/`nil` 만 거짓으로 본다(`0` 은 참).
- **버전 표기가 원천마다 다르다**: README 는 `3.20.0`, `GettingStarted.md` 는 `^3.21.0`, 문서 사이트 머리와 wally 최신은 `3.20.1`, GitHub 태그는 `v3.8.0`. wally 에 3.21 이 없으므로 GettingStarted 의 `^3.21.0` 을 그대로 쓰면 해석에 실패할 것으로 보인다(wally install 은 실행하지 않음).

## §3 TestEZ (보관됨)
status: described · last-confirmed: 2026-11-10 · 근거: `Roblox/testez` API(`archived: true`), CHANGELOG.md

- BDD(`describe`/`it`/`expect`) 프레임워크. 마지막 릴리스 0.4.2(2022-01-05), 저장소는 보관(read-only)되었다. Roblox 공식 후속은 Jest Roblox 다.
- 새 프로젝트에 도입하지 않는다. 기존 코드에서 만나면 Jest Roblox 로 옮기는 것이 정석이다(table-sim 조사 결론과 같음: `table-sim/<비공개>`).

## §4 순수 `luau` CLI 를 러너로 쓸 때의 사실들
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: 수동 실행(아래 명령, 2026-11-10), `snippets/testing-mini-runner.luau`

| 사실 | 확인 |
|---|---|
| 잡히지 않은 에러가 나면 종료 코드 1. 메시지와 `stacktrace:` 는 stderr | `error("boom")` 파일 실행 rc=1 |
| 파일을 여럿 주면(`luau a.luau b.luau`) 앞 파일이 실패해도 **뒤 파일을 계속 돌리고**, 하나라도 실패면 rc=1 | `luau fail.luau ok.luau` → "second ran" 출력, rc=1 |
| 프로그램 인자는 `-a`(`--program-args`) 뒤에 준다. 스크립트에서는 최상위 `...` 로 받는다. `arg` 전역은 없다. `--` 는 "Unrecognized option" 으로 거부된다 | `luau args.luau -a foo bar` → `select("#", ...)` = 2 |
| `require` 대상 모듈은 값을 **정확히 하나** 반환해야 한다. 0개도 `module must return a single value` 이고, 모듈 몸통은 이미 실행된 뒤에 에러가 난다 | `return 1, 2` / `return` 없음 둘 다 rc=1 |
| `--coverage` 는 현재 디렉터리에 `coverage.out`(lcov 형식: `SF`/`FN`/`FNDA`/`DA`)을 쓴다. 줄 단위다 | 1함수 파일에서 확인 |
| `-O0/-O1/-O2` 와 `-g0/-g1/-g2` 를 고를 수 있고 기본은 `-O1 -g1`. Roblox 라이브 서버는 `-O2` 라서 테스트도 `-O2` 로 한 번 더 돌려야 한다(§5) | `luau --help` |
| `task`, `game`, `Instance` 전역은 없다. `getfenv`, `debug.info`, `buffer`, `vector` 는 있다. lune 0.10.5 도 `task` 는 전역이 아니다(`@lune/task`) | `typeof(...)` 출력 |

- 그래서 순수 CLI 테스트는 `assert(조건, 메시지)` 와 `pcall` 이 전부다. 실패 집계가 필요하면 §8 의 20줄 러너를 쓴다.
- 전체 실행 엔트리는 각 스펙을 `require` 한다. 이름을 `init.luau` 로 짓지 않는다(디렉터리 인덱스로 취급, `stl-luau/.claude/base/architecture.md:82-83`, described).

## §5 에러 단언: 메시지 모양과 `-O2` 에서 사용자 줄
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/testing-error-shapes.luau`, `snippets/testing-user-line-assert.luau`(둘 다 `-O0/-O1/-O2` 수동 실행 통과), `snippets/testing-o2-line-probe.luau`(관측용) · 연결: decisions D-10

**메시지 모양** (`pcall` 이 돌려준 값, `-O1`)

| 던진 방식 | 받은 값 |
|---|---|
| `assert(false, "boom")` | `"<파일>:<줄>: boom"`. Lua 5.1 과 달리 **위치가 붙는다** |
| `assert(false)` | `"<파일>:<줄>: assertion failed!"` |
| `assert(nil, tbl)` | 테이블을 던지지 않는다. `"invalid argument #2 to 'assert' (string expected, got table)"`. 타입 검사기도 `string?` 자리라고 잡는다 |
| `error("m", 0)` | `"m"` |
| `error("m", 2)` 를 **pcall 이 직접 부른 함수**에서 | `"m"` (level 2 가 C 함수 `pcall`이라 위치 없음). `pcall(Lib.f, …)` 꼴도 같다 |
| `error(tbl)` | 그 테이블 자체(동일성 유지) |

**`-O2` 에서 갈리는 것** (`testing-o2-line-probe.luau`, 두 버전 같은 결과)

| 모양 | `-O1` | `-O2` |
|---|---|---|
| 로컬 함수 안의 `error(msg, 2)` | 사용자 줄 `:20:` | **위치 없음** |
| 테이블 필드 함수(`function Lib.check`) 안의 `error(msg, 2)` | `:25:` | `:25:` (그대로) |
| 테스트 쪽 헬퍼 `curline()` = `debug.info(2, "l")` 로 기대 줄 재기 | 11 | **-1** (인라인되어 level 2 가 `pcall`) |

규칙:
1. 기대 줄은 단언할 자리에서 `where = debug.info(1, "l") + 1` 로 잰다. 헬퍼 함수로 빼지 않는다.
2. 메시지만 단언하지 말고 `":{where}: "` 까지 단언한다. 파일 이름만 보는 단언(`string.find(msg, "spec.x.luau")`)은 같은 파일의 다른 줄이어도 통과한다.
3. 사용자 줄 단언은 **사용자 함수 안에서** 부른다(`pcall(function() Lib.f(x) end)`). `pcall(Lib.f, x)` 는 위치가 없다.
4. 테스트를 `luau -O2` 로도 돌린다. stl-luau 가 이렇게 한다(`scripts/check.sh:355-360`).

## §6 `getfenv` 로 mock 을 주입하면 그 모듈의 인라이닝이 꺼진다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/testing-getfenv-probe.luau`(`-O2` 수동 실행), luau.org performance 가이드(`luau-lang/site` `src/content/docs/guides/performance.md` 66-68행, 210행, 2026-11-10 HEAD)

- 공식 문서: "`getfenv` deoptimizes the environment even if it's only used to read values", "inlining is completely disabled for modules that use `getfenv`/`setfenv`".
- 실측: §5 의 관측 파일 맨 위에 `local _ = getfenv` 한 줄(호출 없이 이름만)을 넣자 `-O2` 결과가 `-O1` 과 같아졌다(헬퍼 줄 13, 로컬 level 2 위치 유지).
- 함의: Roblox 전역(`Instance`, `game`)을 `getfenv(f).Instance = mock` 으로 주입하는 스펙 파일은 **그 파일 자신**이 `-O2` 인라인을 재현하지 못한다. 인라이닝은 모듈 단위라 `require` 한 라이브러리 모듈은 여전히 인라인된다. 주입 대상 함수의 환경도 "impure" 가 되어 내장 함수 최적화가 빠진다(문서, described).
- 대안: 주입을 생성자 인자나 모듈 테이블 필드로 받는 설계(의존성 주입)면 `getfenv` 가 필요 없다.

## §7 단언 헬퍼의 타입: `eq<T>` 는 불일치를 못 잡는다
status: verified · last-confirmed: luau 0.742 (0.734 동일, luau-lsp 1.70.1 새 솔버 동일) · 근거: `snippets/testing-generic-eq-helper.luau`

- `local function eq<T>(actual: T, expected: T)` 에 `eq(n, "1")` (`n: number`)을 넘겨도 진단이 없다. `T` 가 `number | string` 으로 풀린다.
- 잡으려면 `eq<<number>>(n, "1")` 처럼 명시 타입 인자를 주거나 타입이 고정된 헬퍼(`eqNumber`)를 쓴다. 둘 다 "Expected this to be 'number', but got 'string'".
- 런타임 판정은 그대로 동작하므로(`==` 가 false) 테스트가 실패해 드러나긴 한다. 다만 "타입 테스트"로 이 헬퍼를 쓰면 아무것도 검사하지 않는다. 타입 회귀 테스트는 테스트 실행이 아니라 `luau-analyze` 의 기대 진단으로 짠다(luau-verify 스킬의 snippet-markers).
- `pcall` 이 돌려주는 에러 값은 `any` 다. `local s: string = err` 는 검사되지 않는다(같은 실행에서 진단 0건).

## §8 최소 러너와 러너 음성 대조군
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/testing-mini-runner.luau`, `table-sim/<비공개>`

- 케이스를 `pcall` 로 격리하고 실패 메시지를 모은 뒤, 실패가 있으면 마지막에 `error("spec failures", 0)` 로 rc=1 을 만든다. table-sim 의 실제 러너와 같은 모양이다.
- 러너 자체의 음성 대조군: 일부러 실패하는 케이스 하나를 두고 "실패 1건을 셌다"를 단언한다. "0 failed" 는 러너가 케이스를 하나도 안 돌렸어도 나온다.
- 등록 누락 방지: 스펙 파일을 만들고 엔트리에 등록하지 않으면 조용히 안 돈다. table-sim 은 게이트에서 `tests/core/*.spec.luau` 가 `run.luau` 에 다 있는지 grep 한다(`table-sim/<비공개>`).

## §9 독립 런타임 러너: lune, lute
status: described · last-confirmed: 2026-11-10 · 근거: `luau-lang/lute` `docs/cli/test.md`, `lute/std/libs/test/{init,types,assert}.luau`(마지막 변경 2026-10-15, `e065a086`), `lune-org/lune` CHANGELOG

- **lute**: `lute test [--list] [-s SUITE] [-c CASE] [paths]` 가 `*.test.luau`, `*.spec.luau` 를 찾는다(기본 `tests/`). API 는 `@std/test` 의 `test.case(name, fn)`, `test.suite(name, function(s) s:case(…) end)`, 훅 `beforeEach/afterEach/beforeAll/afterAll`. 단언은 실패 시 `Failure` 값(`assertion` / `lifecycle` / `runtime_error`)을 돌려주는 `eq`, `throws`, `throwsWith`, `tableeq`, `strContains` 등. 로컬에 lute 가 없어 실행하지 않았다.
- **lune**: 내장 테스트 러너가 없다. `task`, `fs` 등은 `@lune/*` 모듈로 받는다. 이 사용자의 stl-luau 는 2026-08-22 lune 을 걷어냈고 다음 후보를 lute 로 적었다(`stl-luau/.claude/base/architecture.md:15-30`; `pesde run` 이 항상 lune 으로 실행해서 쓰지 않는다는 것도 `:30`).
- 두 런타임 모두 Roblox `Instance`·`game` 이 없다. Roblox API 의존 코드에는 §10 의 방법이 따로 필요하다.

## §10 Roblox 의존 코드: mock·fake·분리, 그리고 CI 경로
status: described (Open Cloud, run-in-roblox) / verified (저장소 패턴 읽기) · last-confirmed: 2026-11-10 · 근거: Roblox Open Cloud 문서 `docs/cloud/reference/features/luau-execution.md`(`last_updated: 2026-11-10T00:41:02Z`), 저장소 경로는 §11

엔진 밖에서 시험하는 세 방법(사용자 저장소에서 확인):
1. **엔진 무관 코어 분리**: Roblox API 없이 짠 로직만 CLI 로 돌린다(table-sim `<비공개>`).
2. **mock 주입**: 최소 mock(트리, property bag, 변경 시그널, `IsA` 는 ClassName 동등)을 만들고 전역을 `getfenv` 로 바꿔 끼운다(quad `quad-base/test/mock.luau`, `quad-roblox/test/spec.elem.luau:43`). §6 의 최적화 함의가 따른다.
3. **fake 객체로 내부 구동**: 26줄 가짜 Instance/Signal 과 `task` 전역 대역(rbvm `.claude/review/2026-10-05-repro/fake.luau`). `typeof()` 가 `"table"` 이라 엔진 판별 경로는 못 탄다고 파일이 스스로 적는다.

엔진 안에서 돌리는 CI 경로:
- **Open Cloud Luau Execution(OCALE)**: `POST /cloud/v2/universes/{u}/places/{p}[/versions/{v}]/luau-execution-session-tasks` 로 스크립트를 보내고 `GET …/tasks/{id}` 로 `state`(QUEUED/PROCESSING/COMPLETE/FAILED/CANCELLED)와 반환값을, `…/logs` 로 `print` 출력을 받는다. 제약: 스크립트 4 MB, 실행 5분, 반환값 JSON 4 MB, 로그 450 KB(넘으면 앞부분 버림), 장소당 미완료 작업 10개(넘으면 429), 작업 생성 5회/분(API 키 소유자당), 결과 보존 24시간. **물리 시뮬레이션과 장소 안의 Script/LocalScript 는 돌지 않고**, DataModel 변경은 저장되지 않는다. DataStore 등 클라우드 API 는 실제로 건드린다. 범위 `universe.place.luau-execution-session:write`. Jest Roblox 의 공식 CI 경로가 이것이다.
- 문서가 "reference implementation" 으로 링크하는 `Roblox/place-ci-cd-demo` 는 **2024-09-17 에 archived** 되었다(GitHub API). 예제로는 쓰되 유지되는 도구로 여기지 않는다.
- **run-in-roblox**: 로컬 Studio 를 띄워 스크립트를 돌린다. 2020년 v0.3.0 이후 릴리스가 없다.
- **Studio MCP(`execute_luau`)**: 이 사용자 저장소들은 Studio 실측을 게이트 밖 수동 절차로 둔다(table-sim `<비공개>`; rbvm `conventions.md:71-76`).

## §11 이 사용자 저장소 실태
status: verified · last-confirmed: 2026-11-10 (읽기 전용으로 파일 확인, 아래 "실행" 열은 이번에 직접 돌린 결과) · 근거: 표의 경로:줄

| 저장소 | 프레임워크 | 러너 명령 | 단언 방식 | 에러 단언의 줄 위치 | Roblox 의존 처리 | 실행(2026-11-10) |
|---|---|---|---|---|---|---|
| quad (luau 0.734) | 없음 | `scripts/test.sh:81-84` 가 `luau "$f"` 로 `quad-base/test/{smoke,spec}.*`, `quad-roblox/test/spec.*` 를 하나씩. 기본 `-O1` 만 | `assert(cond, msg)` + 절마다 `print("=== N. … ===")` | `spec.errorutil.luau:26-31` 은 정확한 줄(`:{line}: msg`). 공용 `mock.assertBlamesUser`(`mock.luau:854-858`)는 **파일 이름만** 본다 | mock + `getfenv` 주입(`spec.elem.luau:43`); 타입은 luau-lsp + globalTypes(`test.sh:72-78`); 문서 스니펫 게이트(`doc-snippets.py`) | 67/67 통과(`-O1`). **`-O2` 에서 3개 실패**(§12) |
| stl-luau (0.742) | 없음(`architecture.md:64-87` 사용자 결정 2026-08-22) | `luau tests/run.luau`(엔트리가 각 `spec.*` 를 require) + `luau -O2 tests/run.luau`(`scripts/check.sh:349-360`), `ulimit -v 4194304`, 300초 | `assert` + 메시지, `print("PASS")` | 정확한 줄. `where = debug.info(1, "l") + 1`(`tests/spec.common.luau:99-130`, `conventions.md:138`) | Roblox 의존 없음 | `-O1`·`-O2` 둘 다 ALL SUITES PASS(2.8초) |
| table-sim (0.734) | 없음(Jest 미도입 권고 `<비공개>`) | `luau tests/run.luau`(`scripts/check.sh:90-91`). 러너가 `test(name, fn)` 을 스펙에 넘김(`tests/run.luau:27-43`) | `assert`; 스펙은 `return function(test) … end` | 줄 단언 없음 | 엔진 무관 코어만 스펙(`tests/core`); 타입 음성 대조군 3 + 린트 대조군 1(`check.sh:29-62`); Studio 는 게이트 밖(`check.sh:4`) | 277 passed, 0 failed |
| rbvm | 없음. **유닛 테스트 0개**(`.claude/conventions.md:71-74`) | 재현 스크립트 `luau .claude/review/2026-10-05-repro/<B?>.luau`(`2026-10-05-code-review.md:78`) | `print` 로 기대값과 나란히 출력(단언 없음) | 없음 | fake Instance/Signal(`repro/fake.luau`, 26줄) | 실행하지 않음(게이트 아님) |

공통점: 넷 다 프레임워크를 쓰지 않는다. TestEZ/jest 를 쓰는 곳은 없다. "진단 0건을 믿지 마라"는 음성 대조군 규칙이 테스트에도 적용된다(stl·table-sim).

## §12 실측으로 드러난 것: quad 스펙 3개가 `-O2` 에서 실패
status: verified · last-confirmed: luau 0.734 (quad 의 핀) · 근거: `quad-base/test/*.luau` 를 `luau -O2` 로 직접 실행(읽기 전용, 출력 `/tmp/gaps/t5/`)

quad 의 `test.sh` 는 기본 `-O1` 로만 돌린다. `-O2` 로 같은 파일들을 돌리면 64/67 통과, 3개 실패:

| 스펙 | 실패 | 원인 |
|---|---|---|
| `spec.errorutil.luau:28` | "error should blame line 0" | 테스트 쪽 `curline()` 헬퍼(`:21-23`)가 인라인되어 `debug.info(2)` 가 -1. 라이브러리가 던진 줄(`:40`)은 맞다. §5 규칙 1 위반 |
| `spec.fallback.luau:78` | traceback 에 `inner` 가 없음 | `inner` 가 `Widget` 에 인라인되어 프레임 이름이 사라짐. traceback 의 함수 이름을 단언하면 `-O2` 에서 깨진다 |
| `spec.relate.luau:102` | 에러가 사용자 파일을 가리키지 않음 | `quad-base/src/Relate.luau:28` 이 손으로 센 `error(…, 3)`. D-10 이 말한 바로 그 모양이 라이브러리 안에 남아 있다 |

셋째는 라이브러리 동작 문제(라이브 Roblox 는 `-O2`)이고, 첫째·둘째는 테스트의 측정 방식 문제다. quad 의 `architecture.md:521` 은 `-O2` 인라인을 알고 있지만 게이트가 `-O2` 를 돌리지 않아 잡히지 않았다. 고치는 일은 이 초안의 범위가 아니다(quad 저장소 소관).

## §13 고르는 법(결정 요약)
status: described (판단) · 근거: §1-§12

- 라이브러리·엔진 무관 로직 → 순수 `luau` CLI + `assert`/`pcall`. `-O1` 과 `-O2` 로 두 번 돌린다. 에러는 메시지와 정확한 사용자 줄을 같이 단언한다.
- Roblox API 가 핵심인 코드를 자동으로 시험해야 함 → Jest Roblox(wally `roblox/jest`) + Open Cloud Luau Execution. Studio 수동 실측은 게이트 밖 기록으로 둔다.
- TestEZ, jsdotlua/jest-lua, run-in-roblox 는 새로 도입하지 않는다(보관 또는 정지).
- lute 로 옮길 계획이면 `lute test` 와 `@std/test` 가 있다. 실측 전이므로 도입 전에 스니펫부터 만든다.

---
이 내용이 들어갈 luau-kb 스킬: **luau-testing** (§5·§6 의 `-O2` 부분은 luau-perf 의 `--!optimize` 절과 상호 참조)
