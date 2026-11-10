# tooling — .luaurc 모드, 러너, const, stylua

## 이 파일이 답하는 질문
- Q1 `.luaurc` 를 strict 로 두면 충분한가?
- Q2 코드를 무엇으로 실행하나: luau CLI, lune, lute? (정책 미정)
- Q3 `const` 를 써도 되나? (정책 미정)
- Q4 stylua 가 `f<<T>>(...)` 를 망가뜨린다는데 사실인가?

## 목차
- §1 `.luaurc` 와 `--!strict`
- §2 러너 정책 (미정)
- §3 `const` 정책 (미정)
- §4 stylua 와 명시 타입 인자
- §5 린트

---

## §1 `.luaurc` 와 `--!strict`
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/modes-luaurc-nonstrict-silences.luau`, `snippets/modes-strict-directive-wins.luau` · 원천: stl-luau/.claude/base/typing-limits.md ".luaurc 하나에 의존하면" (실물 310건 → 0건 표)

| `.luaurc` languageMode | 파일 첫 줄 `--!strict` | CLI `--mode=strict` | 결과 |
|---|---|---|---|
| nonstrict | 없음 | 있음 | **0건**(명백한 에러도) |
| nonstrict | 있음 | — | strict 검사 |
| 없음 | 없음 | 있음 | strict 검사 |

- `.luaurc` 한 단어가 바뀌면 에러 수백 건이 소리 없이 0건이 된다. 커밋 리뷰에서 "타입이 깨끗해졌다"로 읽히기 쉽다.
- `--mode=strict` 는 `.luaurc` 를 덮어쓰지 못한다. CLI 로 강제할 방법이 없다.
- **파일마다 `--!strict` 를 다는 것이 유일하게 믿을 수 있는 층이다.**
- 새 솔버의 nonstrict 는 거의 아무것도 보고하지 않는다(quad doc-snippets.py 머리 설명, 위 스니펫과 일치).

## §2 러너 정책 (미정)
status: described (정책) / verified (lune 의 const 파싱 실패) · 원천: stl-luau/.claude/base/architecture.md "런타임: 순수 luau", stl/moonwave-luau/table-sim/devplorer mise.toml 머리 주석, tbox/mise.toml `[tasks.test]`

> 정책: 미정 — decisions/ 참고

| 입장 | 저장소 | 근거 |
|---|---|---|
| **luau CLI 만** | stl-luau, moonwave-luau, quad(스펙과 문서 실행) | lune 은 `const` 를 못 읽는다. "lune 은 반쯤 버려진 프로젝트, 나중에 갈아탄다면 lute"(stl 사용자 발언). `pesde run` 은 항상 lune 으로 실행하므로 쓰지 않는다 |
| **luau + lute 이중 실행** | tbox | 테스트를 두 런타임에서 돌리고, fs/process 가 필요한 도구 스크립트는 lute 로 실행한다 |
| lune 을 넣지 않음 | table-sim, devplorer | 의존 라이브러리가 쓰는 `const` 를 lune 이 못 읽는다 |

사실(정책과 무관):
- `lune 0.10.5` 는 `const x = 1` 에서 "Incomplete statement: expected assignment or a function call" 로 실패한다. `luau` 0.734 는 실행한다(이 저장소 수동 실측).
- `luau` CLI 에는 파일·프로세스 I/O 라이브러리가 없다.
- require 해석 규칙이 런타임마다 다르다. 예: lune 0.8.9 에서는 `@self` 의 의미가 luau CLI 와 반대였다(stl 기록, described). 런타임을 바꿀 때는 require 규칙을 다시 잰다.
- `lute` 는 이 머신에 설치돼 있지 않아 이 저장소에서 확인하지 않았다.

## §3 `const` 정책 (미정)
status: described (정책) / verified (언어·도구 동작) · 원천: rbvm/.claude/conventions.md "const 를 쓰지 말 것", stl-luau/.claude/conventions.md "const 바인딩", tbox/quad mise.toml 의 pesde 핀 주석

> 정책: 미정 — decisions/ 참고

| 입장 | 저장소 | 근거 |
|---|---|---|
| **재대입 없는 바인딩은 `const`** | stl-luau, quad, tbox, moonwave-luau(mrow) 등 | 재대입을 컴파일 타임에 막는다 |
| **`const` 금지, `local` 만** | rbvm | 사용자 결정(2026-08-24). 당시 pesde 가 `const` 선언에서 자동 타입 익스포트를 하지 못했다. 되돌리는 비용을 이미 한 번 치렀다 |

사실:
- `luau-analyze` 는 `const` 재대입을 `SyntaxError: Variable 'x' is constant and may not be reassigned` 로 잡는다. stylua 2.5.2(`syntax = "Luau"`)는 `const` 를 포맷한다(이 저장소 수동 실측).
- lune 0.10.5 와 selene 은 `const` 를 파싱하지 못한다. pesde 0.7.3 은 `const` 를 거부했고 0.7.4 는 받는다(quad·tbox mise.toml 주석, described). rbvm 의 금지 이유가 pesde 0.7.4 이후에도 유효한지는 확인되지 않았다.
- 함정: `local const x = 1` 은 `const` 라는 지역변수와 **전역 대입** `x = 1` 이 된다. 주석이 없으면 문법 에러도 나지 않는다(stl conventions, described).
- stylua 의 `sort_requires` 는 `local X = require(...)` 꼴만 인식한다(rbvm 기록, described).

## §4 stylua 와 명시 타입 인자
status: verified · last-confirmed: stylua 2.5.2 · 근거: `tools/repro-stylua-typeargs.sh` (rc=0) · 원천: tbox/CLAUDE.md stylua 경고(정정), stl typing-limits "stylua 경고"

- **오염 조건은 "Luau 문법 설정이 없을 때"다.** stylua 가 `stylua.toml` 을 찾지 못하면 기본 문법으로 파싱하고, `id<<number>>(1)` 을 `id << number >> 1` 로, `T.Unsafe<<number>>({ a = 1 })` 를 `T.Unsafe << number >> { a = 1 }` 로 **rc=0 인 채** 바꾼다. 인자가 여럿이라 시프트로 파싱되지 않는 꼴(`f<<A, B>>(…)`)은 파싱 에러로 멈춘다.
- `syntax = "Luau"` 가 설정에 있거나 `--syntax luau` 를 주면 그대로 보존된다. tbox 문서의 "syntax = Luau 에서도 오염" 은 재현되지 않았다. tbox 문서 스스로 "stylua 는 현재 디렉터리의 설정만 찾는다, 하위 디렉터리에서 돌리면 기본 설정으로 포매팅된다"고 적었는데, 그것이 실제 조건으로 보인다.
- 규칙: stylua 는 **설정 파일이 있는 루트에서** 실행하거나 `--syntax luau` 를 명시한다. 포맷 뒤 `git diff` 에서 `<< ` 나 ` >>` 가 생겼는지 본다. stylua 를 올릴 때는 재현 스크립트를 먼저 돌린다.
- 여러 저장소가 같은 모양의 `stylua.toml`(syntax Luau, column_width 120, Tabs, AutoPreferDouble, call_parentheses Always, collapse_simple_statement Never)을 쓴다. 들여쓰기(Tabs/Spaces)와 `call_parentheses`(Always/Input)는 저장소마다 갈린다(claude-doctor PLAN §4).

> 정책: 미정 — decisions/ 참고 (stylua 들여쓰기와 call_parentheses)

## §5 린트
status: described · 원천: 각 저장소 `.luaurc` (`"lint": { "*": true }`), stl mise.toml(selene 폐기)

- 린트는 `luau-analyze` 내장 린트를 `.luaurc` 의 `lint` 로 켠다. selene 은 `const` 를 파싱하지 못해 여러 저장소가 폐기했다.
- 린트 경고는 종료 코드에 영향을 주지 않는다(rc=0). 게이트로 쓰려면 출력을 따로 검사해야 한다.
