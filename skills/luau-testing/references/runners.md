# runners — 무엇으로 테스트를 돌리나: 순수 luau CLI, 독립 런타임, 프레임워크 현황

## 이 파일이 답하는 질문
- Q1 Roblox 없이 순수 `luau` CLI 로 테스트를 돌리려면 무엇을 알아야 하나(인자, 종료 코드, require, 커버리지, 없는 전역)?
- Q2 프레임워크 없이 러너를 어떻게 짜나? 엔트리 파일 이름에 함정이 있나?
- Q3 lute, lune 은 러너로 쓸 수 있나?
- Q4 Jest Roblox, jsdotlua/jest-lua, TestEZ 중 무엇을 고르나? 지금 유지되고 있나?
- Q5 파일 입력이 필요한 테스트(픽스처, 골든)는 `io` 없이 어떻게 하나?

## 목차
- §1 결정: `luau` CLI 가 기본 러너 (D-03)
- §2 `luau` CLI 를 러너로 쓸 때의 사실
- §3 최소 러너 모양과 엔트리 파일
- §4 파일 입력: 픽스처는 모듈로 굽고 비교는 셸이
- §5 독립 런타임: lute, lune
- §6 프레임워크 현황: Jest Roblox, jest-lua, TestEZ, run-in-roblox
- §7 엔진 안에서 돌리는 CI 경로

---

## §1 결정: `luau` CLI 가 기본 러너 (D-03)
status: described (정책) · 근거: claude-doctor `decisions/D-03-runner.md` "사용자 결정 (2026-11-10)", luau-kb `decisions/D-03-runner.md`

- 테스트·스파이크의 기본 실행기는 `luau` CLI 다. Roblox 서비스·환경에 기대는 부분만 **필요한 만큼 mock** 으로 바꿔 `luau` 로 돈다. 경계 긋는 법은 `roblox-boundary.md`.
- Roblox Studio(MCP)는 mock 이 실제와 맞는지 확인하거나, mock 으로 재현할 수 없는 동작을 볼 때만 쓴다. 매번 Studio 를 부르면 기계적으로 반복할 수 없다.
- lune 은 쓰지 않는다. lune 0.10.5 는 `const` 를 파싱하지 못한다(luau-verify 스킬 `tooling.md` §2).

## §2 `luau` CLI 를 러너로 쓸 때의 사실
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-cli-runtime-facts.luau`, `snippets/test-mini-runner.luau`, 원천 claude-doctor `drafts/gaps/testing.md` §4 의 수동 실행, 후보 D-C03·S-127·Q-070·Q-118

| 사실 | 함의 |
|---|---|
| 잡히지 않은 에러는 종료 코드 1. 메시지와 `stacktrace:` 는 stderr | 게이트는 출력 줄을 세지 말고 rc 로 판정한다 |
| 파일을 여럿 주면(`luau a.luau b.luau`) 앞 파일이 실패해도 뒤 파일을 계속 돌리고, 하나라도 실패하면 rc=1 | 파일 단위 러너로 쓸 수 있다. 다만 실패 집계는 직접 해야 한다 |
| 프로그램 인자는 `-a` 뒤에 주고 스크립트는 최상위 `...` 로 받는다. `arg` 전역은 없고 `--` 는 거부된다 | 셸 스크립트에서 인자를 넘길 때 주의 |
| `require` 대상 모듈은 값을 정확히 하나 돌려줘야 한다(0개도 에러). 에러는 모듈 몸통이 이미 실행된 뒤에 난다 | 스펙 파일을 `return function(test) … end` 로 짜면 등록과 실행을 나눌 수 있다 |
| `--coverage` 는 현재 디렉터리에 `coverage.out`(lcov 형식, 줄 단위)을 쓴다 | 커버리지 도구가 따로 필요 없다 |
| 기본 `-O1 -g1`. `-O0/-O2`, `-g0/-g2`, `--codegen` 을 고를 수 있다 | **테스트를 `-O2` 로도 돌린다**(`optimize-levels.md`) |
| `task`, `game`, `Instance`, `Vector3`, `Enum`, `io`, `fs`, `warn` 이 없다. `getfenv`, `debug.info`, `buffer`, `vector`, `collectgarbage` 는 있다 | 엔진 전역을 **로드 시점**에 건드리는 모듈은 require 하는 순간 죽는다. 호출 시점으로 미룬다(`roblox-boundary.md` §3) |

- 프레임워크가 없으니 단언은 `assert(조건, 메시지)` 와 `pcall` 이 전부다. 단언 패턴은 `assertions.md`.
- `luau` 실행은 메모리·시간 상한 안에서 돌린다(`ulimit -v`, `timeout`). 폭주한 테스트가 컨테이너를 같이 쓰는 다른 프로세스를 죽일 수 있다(stl-luau `.claude/conventions.md:159`).

## §3 최소 러너 모양과 엔트리 파일
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-mini-runner.luau`, 원천 `table-sim/<비공개>`, `devplorer/tests/run.luau:1-3`, `moonwave-luau/tests/run.luau:1-20`, 후보 S-119

두 가지 모양이 쓰인다.
1. **집계형**: 엔트리가 스펙 목록을 들고, 각 스펙에 `test(name, fn)` 을 넘긴다. `test` 는 `pcall(fn)` 으로 케이스를 격리해 성공·실패를 세고, 끝에 실패가 있으면 `error("spec failures", 0)` 로 rc=1 을 만든다(table-sim, devplorer).
2. **즉시 실패형**: 엔트리가 스펙 파일을 차례로 `require` 하고, 스펙은 require 되는 순간 `assert` 를 실행한다. 첫 실패에서 끝난다(stl-luau, moonwave-luau, quad 는 파일마다 `luau` 를 한 번씩).

공통 규칙:
- 엔트리 이름을 `init.luau` 로 짓지 않는다. `init.luau` 는 "디렉터리 자신"으로 취급되어 그 안의 `./` 가 한 단계 위를 가리킨다(`moonwave-luau/tests/run.luau:15-17`, described. require 규칙 자체는 luau-style 쪽 주제다).
- require 경로는 문자열 리터럴로 쓴다. 동적 경로는 require-by-string 이 풀지 못한다(`moonwave-luau/tests/run.luau:13-14`, described).
- 절마다 `do … end` 로 지역을 격리하고, 실패 메시지에 기대값과 실제값을 넣는다(stl-luau 방식, S-119, described).
- 러너 자체의 음성 대조군과 등록 누락 검사는 `negative-controls.md` §1–2.

## §4 파일 입력: 픽스처는 모듈로 굽고 비교는 셸이
status: described · 근거: `stl-luau/.claude/base/architecture.md:9-13,24-34`, `moonwave-luau/scripts/golden.sh:6-14`, `moonwave-luau/tests/run.luau:19-20`, 후보 S-127·M-15·M-16

- `luau` CLI 에는 `io`·`fs` 가 없다(§2 는 verified). 픽스처 텍스트는 `return [==[ … ]==]` 모듈로 구워 `require` 한다.
- 골든 출력 비교(파일 입출력)는 테스트 엔트리가 아니라 셸 스크립트가 한다. 순수 luau 가 결과를 stdout 으로 내고 셸이 `diff` 한다(moonwave-luau `scripts/golden.sh`).
- 골든 파일을 다른 런타임의 JSON 인코더로 만들 때 주의: lune(mlua)의 인코더는 배열부가 있는 표를 배열로만 내보내 문자열 키를 버렸다(moonwave known-issues, M-15, lune 전용, described).
- `pairs` 순회 순서에 기댄 출력은 같은 입력·같은 삽입 순서면 프로세스 안팎에서 같았다는 관찰이 있다(luau 0.734, M-16, described). 약속된 동작이 아니므로 골든 비교 출력은 키를 정렬해서 낸다.

## §5 독립 런타임: lute, lune
status: described · last-confirmed: 2026-11-10 (GitHub 조회) · 근거: `luau-lang/lute` `docs/cli/test.md`, `std/libs/test/*`(e065a086), `tbox/mise.toml:23-26`, 원천 `drafts/gaps/testing.md` §9

- **lute**(v1.0.0, 2026-04-16): `lute test [--list] [-s SUITE] [-c CASE] [paths]` 가 `*.test.luau`·`*.spec.luau` 를 찾는다(기본 `tests/`). `@std/test` 에 `test.case`, `test.suite`, `beforeEach/afterEach/beforeAll/afterAll` 훅, `eq`·`throws`·`tableeq`·`strContains` 단언이 있다. 이 머신에는 lute 가 없어 실행하지 않았다.
- 이 사용자 저장소 중 tbox 는 같은 `test/run.luau` 를 `luau` 와 `lute run` 으로 두 번 돈다(`tbox/mise.toml:26`). 워크스페이스 symlink 를 따라가지 못해 `cp -rL` 사본에서 돈다(`tbox/mise.toml:31-42`).
- **lune**: 내장 테스트 러너가 없고 `task`·`fs` 는 `@lune/*` 모듈이다. `const` 를 못 읽어 쓰지 않는다(D-03).
- 두 런타임 모두 Roblox `Instance`·`game` 이 없다. Roblox 의존 코드에는 `roblox-boundary.md` 방법이 따로 필요하다.

## §6 프레임워크 현황: Jest Roblox, jest-lua, TestEZ, run-in-roblox
status: described · last-confirmed: 2026-11-10 (GitHub REST API, wally 레지스트리) · 근거: `Roblox/jest-roblox` README·`docs/docs/GettingStarted.md`·`Deviations.md`, `jsdotlua/jest-lua` README, `Roblox/testez`(archived), `rojo-rbx/run-in-roblox`, 원천 `drafts/gaps/testing.md` §1–3

| 이름 | 상태(2026-11-10) | Roblox 밖 실행 | 고를 때 |
|---|---|---|---|
| Jest Roblox (`Roblox/jest-roblox`, wally `roblox/jest`) | 활성. wally 최신 3.20.1 | 불가(Studio 나 Open Cloud Luau Execution) | Roblox API 가 핵심인 코드를 자동 시험할 때 |
| jest-lua (`jsdotlua/jest-lua`) | 사실상 정지(마지막 2024-12-23, v3.10.0). Jest Roblox 의 포크 | 불가 | 새로 고를 이유가 없다. Roblox 가 `roblox/*` 로 직접 배포한다 |
| TestEZ (`Roblox/testez`) | **archived**, 마지막 릴리스 0.4.2(2022-01) | Lemur 도 archived | 새로 도입하지 않는다. 기존 코드는 Jest Roblox 로 옮긴다 |
| run-in-roblox | 정지(v0.3.0, 2020) | 로컬 Studio 를 띄움 | 쓰지 않는다 |

- Jest Roblox 의 Luau 쪽 차이: `not` 이 예약어라 `.never`, `expect(x).toBe(y)` 는 점 호출, `.toBeFalsy()` 는 `false`/`nil` 만 거짓(`0` 은 참).
- 버전 표기가 원천마다 다르다: README `3.20.0`, GettingStarted `^3.21.0`, wally·문서 사이트 `3.20.1`. wally 에 3.21 이 없어 GettingStarted 의 `^3.21.0` 은 해석에 실패할 것으로 보인다(`wally install` 은 실행하지 않음).
- 이 사용자 저장소 일곱 곳 중 프레임워크를 쓰는 곳은 없다(`repo-practices.md`).

## §7 엔진 안에서 돌리는 CI 경로
status: described · 근거: Roblox `docs/cloud/reference/features/luau-execution.md`(2026-11-10 받음), `table-sim/<비공개>`, 후보 T-52

- **Open Cloud Luau Execution**: 스크립트를 작업으로 보내고 상태(QUEUED/PROCESSING/COMPLETE/FAILED/CANCELLED), 반환값, 로그를 받는다. 제약: 스크립트 4 MB, 실행 5분, 장소당 미완료 작업 10개, 작업 생성 분당 5회, 결과 보존 24시간. **물리 시뮬레이션과 장소 안 Script 는 돌지 않고** DataModel 변경은 저장되지 않는다. DataStore 는 실제로 건드린다. Jest Roblox 의 공식 CI 경로다.
- 문서가 참조 구현으로 링크하는 `Roblox/place-ci-cd-demo` 는 2024-09-17 에 archived 됐다. 예제로만 본다.
- Studio MCP 로 하는 수동 확인 절차는 roblox-luau 스킬 `../../roblox-luau/references/studio-mcp.md` 에 있다.
