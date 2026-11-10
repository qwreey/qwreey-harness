# tooling — .luaurc 모드, 러너, const, stylua

## 이 파일이 답하는 질문
- Q1 `.luaurc` 를 strict 로 두면 충분한가?
- Q2 코드를 무엇으로 실행하나: luau CLI, lune, lute? (결정: D-03)
- Q3 `const` 를 써도 되나? (결정: D-01)
- Q4 stylua 가 `f<<T>>(...)` 를 망가뜨린다는데 사실인가? (결정: D-02)
- Q5 린트는 게이트에서 어떻게 다루나? 정규식으로 Luau 를 고치는 스크립트는 믿어도 되나?

## 목차
- §1 `.luaurc` 와 `--!strict`
- §2 러너 (결정: D-03)
- §3 `const` (결정: D-01)
- §4 stylua 와 명시 타입 인자 (결정: D-02)
- §5 린트와 게이트 판정

---

## §1 `.luaurc` 와 `--!strict`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/modes-luaurc-nonstrict-silences.luau`, `snippets/modes-strict-directive-wins.luau` · 원천: stl-luau/.claude/base/typing-limits.md ".luaurc 하나에 의존하면" (실물 310건 → 0건 표)

| `.luaurc` languageMode | 파일 첫 줄 `--!strict` | CLI `--mode=strict` | 결과 |
|---|---|---|---|
| nonstrict | 없음 | 있음 | **0건**(명백한 에러도) |
| nonstrict | 있음 | — | strict 검사 |
| 없음 | 없음 | 있음 | strict 검사 |

- `.luaurc` 한 단어가 바뀌면 에러 수백 건이 소리 없이 0건이 된다. 커밋 리뷰에서 "타입이 깨끗해졌다"로 읽히기 쉽다.
- `--mode=strict` 는 `.luaurc` 를 덮어쓰지 못한다.
- **정정(2026-11-10)**: CLI 로 강제할 방법은 있다. `luau-analyze --fflags=DebugLuauForceStrictMode=true` 는 `.luaurc` 의 nonstrict 와 지시어 없음을 무시하고 strict 로 검사한다(0.734·0.742, `snippets/verify-fflags-force-strict.luau`). luau-lsp 는 `--flag:DebugLuauForceStrictMode=true`. 디버그 플래그라 이름이 바뀔 수 있으니 게이트에 쓰면 음성 대조군을 함께 둔다. 이전 판은 "CLI 로 강제할 방법이 없다"고 적었다.
- 그래도 **파일마다 `--!strict` 를 다는 것이 기본 층이다.** 에디터와 다른 도구는 위 플래그를 모른다.
- 새 솔버의 nonstrict 는 거의 아무것도 보고하지 않는다(quad doc-snippets.py 머리 설명, 위 스니펫과 일치).

## §2 러너 (결정: D-03)
status: described (정책) / verified (lune 의 const 파싱 실패) · 원천: 사용자 결정 claude-doctor `decisions/D-03-runner.md` (2026-11-10), 이 저장소 `decisions/D-03-runner.md`; 결정 전 입장: stl-luau/.claude/base/architecture.md "런타임: 순수 luau", stl/moonwave-luau/table-sim/devplorer mise.toml 머리 주석, tbox/mise.toml `[tasks.test]`

**결정**: 기본 러너는 `luau` CLI 다. lune 은 쓰지 않는다.
- Roblox 서비스·환경에 기대는 동작(`task`, 이벤트 등)은 **필요한 부분만 mock 을 만들어** `luau` 로 돌리는 것이 기본이다. 항상 Studio 를 부르면 기계적으로 테스트할 수 없기 때문이다.
- Roblox Studio(MCP)는 mock 이 실제와 맞는지 확인할 때와 mock 으로 재현할 수 없는 동작을 볼 때 쓴다. 판정 표, mock 패턴, Studio MCP 사용법은 roblox-luau 스킬에 있다.

결정 전에 갈렸던 입장(기록):

| 입장 | 저장소 | 근거 |
|---|---|---|
| **luau CLI 만** | stl-luau, moonwave-luau, quad(스펙과 문서 실행) | lune 은 `const` 를 못 읽는다. "lune 은 반쯤 버려진 프로젝트, 나중에 갈아탄다면 lute"(stl 사용자 발언). `pesde run` 은 항상 lune 으로 실행하므로 쓰지 않는다 |
| **luau + lute 이중 실행** | tbox | 테스트를 두 런타임에서 돌리고, fs/process 가 필요한 도구 스크립트는 lute 로 실행한다 |
| lune 을 넣지 않음 | table-sim, devplorer | 의존 라이브러리가 쓰는 `const` 를 lune 이 못 읽는다 |

사실:
- `lune 0.10.5` 는 `const x = 1` 에서 "Incomplete statement: expected assignment or a function call" 로 실패한다. `luau` 0.734 는 실행한다(이 저장소 수동 실측).
- `luau` CLI 에는 파일·프로세스 I/O 라이브러리가 없다.
- require 해석 규칙이 런타임마다 다르다. 예: lune 0.8.9 에서는 `@self` 의 의미가 luau CLI 와 반대였다(stl 기록, described). 런타임을 바꿀 때는 require 규칙을 다시 잰다.
- `lute` 는 이 머신에 설치돼 있지 않아 이 저장소에서 확인하지 않았다. 원천 기록(described, 후보 M-01): lute 1.0.0 과 mlua 0.12.1(Luau 0.736)은 `const`, `f<<T>>`, 문자열 require 를 luau CLI 와 같게 처리하고, lute 는 에러 메시지까지 같았다. lute 에는 전역 `loadstring` 이 없어 `@lute/luau` 로 컴파일한다. mlua 는 `create_require_function(FsRequirer::new())` 로 require 를 등록한다(`moonwave-luau/.claude/base/architecture.md:92-108`, `mrow/review/REVIEW.md:1488-1502`, `tbox/CLAUDE.md:138-140`).
- `const` 와 `f<<T>>` 는 Luau 0.711 이상에서만 파싱된다(0.709·0.710 은 구문 에러). lune 0.10.5 가 번들한 Luau 가 0.709 라는 것이 lune 이 `const` 를 못 읽는 이유로 기록돼 있다(described, 후보 M-02, `mrow/review/REVIEW.md:1375`; 번들 판은 웹 조사).
- `pesde run` 은 스크립트를 lune 으로 돌리고 엔진을 `~/.pesde/bin` 에서 찾는다. 그 경로가 PATH 에 없으면 `failed to replace process` 로 패닉한다(described, 후보 X-09, `tbox/CLAUDE.md:134-137`). 스크립트는 mise task 로 luau·lute 를 직접 부른다.

## §3 `const` (결정: D-01)
status: described (정책) / verified (언어·도구 동작) · 원천: 사용자 결정 claude-doctor `decisions/D-01-const.md` (2026-11-10), 이 저장소 `decisions/D-01-const.md`; 결정 전 입장: rbvm/.claude/conventions.md "const 를 쓰지 말 것", stl-luau/.claude/conventions.md "const 바인딩", tbox/quad mise.toml 의 pesde 핀 주석

**결정**: `const` 를 써도 된다. Roblox 라이브(게시) 코드까지 포함한다. rbvm 의 금지 근거(pesde 0.7.3)는 0.7.4 에서 사라졌다. 새 파일은 `const`, 기존 파일은 그 파일 관행을 따르고, 한 파일 안에서 `const` 와 재대입 없는 `local` 을 섞지 않는다. 결정 전 "정책 미정" 표시는 2026-11-10 에 걷었다.

결정 전에 갈렸던 입장(기록):

| 입장 | 저장소 | 근거 |
|---|---|---|
| **재대입 없는 바인딩은 `const`** | stl-luau, quad, tbox, moonwave-luau(mrow) 등 | 재대입을 컴파일 타임에 막는다 |
| **`const` 금지, `local` 만** | rbvm | 사용자 결정(2026-08-24). 당시 pesde 가 `const` 선언에서 자동 타입 익스포트를 하지 못했다. 되돌리는 비용을 이미 한 번 치렀다 |

사실:
- `luau-analyze` 는 `const` 재대입을 `SyntaxError: Variable 'x' is constant and may not be reassigned` 로 잡는다. stylua 2.5.2(`syntax = "Luau"`)는 `const` 를 포맷한다(이 저장소 수동 실측).
- lune 0.10.5 와 selene 은 `const` 를 파싱하지 못한다. pesde 0.7.3 은 `const` 를 거부했고 0.7.4 는 받는다(quad·tbox mise.toml 주석, claude-doctor D-01 확인). pesde 0.7.3 이하의 `install` 은 `const` 파일에서 "failed to parse file to extract types" 경고를 내지만 설치는 된다(described, 후보 X-10, `tbox/CLAUDE.md:56-62`).
- `const` 를 모르는 도구는 조용히 틀린다. 정규식으로 Luau 를 고친 마이그레이션 스크립트가 `local` 만 보고 `const` 선언 25곳을 놓친 기록이 있다(described, 후보 D-F34, `devplorer/.claude/feedback/devui.md:149-150`). 선언을 찾는 스크립트는 `local` 과 `const` 를 둘 다 본다.
- 함정: `local const x = 1` 은 `const` 라는 지역변수와 **전역 대입** `x = 1` 이 된다. 주석이 없으면 문법 에러도 나지 않는다(stl conventions, described).
- stylua 의 `sort_requires` 는 `local X = require(...)` 꼴만 인식한다(rbvm 기록, described).

## §4 stylua 와 명시 타입 인자
status: verified · last-confirmed: stylua 2.5.2 · 근거: `tools/repro-stylua-typeargs.sh` (rc=0) · 원천: tbox/CLAUDE.md stylua 경고(정정), stl typing-limits "stylua 경고"

- **오염 조건은 "Luau 문법 설정이 없을 때"다.** stylua 가 `stylua.toml` 을 찾지 못하면 기본 문법으로 파싱하고, `id<<number>>(1)` 을 `id << number >> 1` 로, `T.Unsafe<<number>>({ a = 1 })` 를 `T.Unsafe << number >> { a = 1 }` 로 **rc=0 인 채** 바꾼다. 인자가 여럿이라 시프트로 파싱되지 않는 꼴(`f<<A, B>>(…)`)은 파싱 에러로 멈춘다.
- `syntax = "Luau"` 가 설정에 있거나 `--syntax luau` 를 주면 그대로 보존된다. tbox 문서의 "syntax = Luau 에서도 오염" 은 재현되지 않았다. tbox 문서 스스로 "stylua 는 현재 디렉터리의 설정만 찾는다, 하위 디렉터리에서 돌리면 기본 설정으로 포매팅된다"고 적었는데, 그것이 실제 조건으로 보인다.
- 규칙: stylua 는 **설정 파일이 있는 루트에서** 실행하거나 `--syntax luau` 를 명시한다. 포맷 뒤 `git diff` 에서 `<< ` 나 ` >>` 가 생겼는지 본다. stylua 를 올릴 때는 재현 스크립트를 먼저 돌린다.
- 여러 저장소가 같은 모양의 `stylua.toml`(syntax Luau, column_width 120, Tabs, AutoPreferDouble, call_parentheses Always, collapse_simple_statement Never)을 쓴다. 들여쓰기(Tabs/Spaces)와 `call_parentheses`(Always/Input)는 저장소마다 갈린다(claude-doctor PLAN §4).
- stylua 가 하위 디렉터리에서 기본 설정으로 포맷하는 같은 함정을 두 저장소가 따로 기록했다(후보 X-13, `tbox/CLAUDE.md:80-82`, `moonwave-luau/.claude/conventions.md:57-58`).

> 결정: D-02 — 값(들여쓰기, `call_parentheses`)은 저장소 `stylua.toml` 이 소유한다. 공통 규칙은 '루트에서 실행, `syntax = "Luau"`, 포맷 뒤 `<<` diff 확인' 셋이다(`decisions/D-02-stylua.md`).

## §5 린트와 게이트 판정
status: verified (린트 rc=0, `UnknownType` 우회) / described (나머지) · last-confirmed: luau 0.734·0.742, luau-lsp 1.70.1 · 근거: 수동 실행(`snippets/RESULTS.md` "스니펫 밖에서 실측한 것"), `snippets/verify-engine-free-globals.luau` · 원천: 각 저장소 `.luaurc` (`"lint": { "*": true }`), stl mise.toml(selene 폐기), 후보 Q-082·Q-113·Q-115·R-50

- 린트는 `luau-analyze` 내장 린트를 `.luaurc` 의 `lint` 로 켠다. selene 은 `const` 를 파싱하지 못해 여러 저장소가 폐기했다.
- 린트 경고는 종료 코드에 영향을 주지 않는다(rc=0). 게이트로 쓰려면 출력을 따로 검사해야 한다. 예:
  - `local` 없는 `function name()` 은 전역 대입이다. `luau-analyze` 는 조건이 맞을 때 `GlobalUsedAsLocal` 린트만 내고 rc=0 이다(quad `scripts/test.sh:33-35`, described).
  - Roblox 정의가 없는 `luau-analyze` 는 `typeof(v) == "Instance"` 에 `UnknownType: Unknown type 'Instance'` 린트를 내고 rc=0 이다(strict 에서도). 출력을 0줄로 두려면 `(typeof(v) :: string) == "Instance"` 로 쓴다(verified 0.734·0.742·lsp 1.70.1, 후보 Q-115).
- **게이트는 종료 코드로 판정하고 실패를 누적한다**(`fail=1 … exit $fail`). 다음 둘은 실제로 사고를 냈다(described):
  - "ALL PASS" 줄 수를 세는 판정이 타입 에러를 다섯 커밋 동안 놓쳤다(quad `.claude/conventions.md:348-355`, H-404/H-405).
  - `luau-lsp … || true` 뒤 출력에서 `TypeError|SyntaxError` 를 grep 하는 판정은 rc 와 린트를 버리고, 형식이 다른 줄(SyntaxError 위치 등)을 놓친다(rbvm `tools/check.sh:63-76`, 후보 R-50).
- selene 은 설정을 현재 디렉터리의 `./selene.toml` 에서만 찾는다. 없으면 Lua 5.1 표준으로 조용히 돌아가 Luau 타입 문법에 가짜 파싱 에러를 30여 건 낸다(described, 후보 Q-113, quad `.claude/base/project-setup-plan.md:362-378`). 이 머신에는 selene 이 없어 재현하지 않았다.
- `getfenv` 는 deprecated 린트로 걸리고 모듈의 최적화도 끈다(후보 D-R19, luau-style·luau-testing 스킬).
