---
name: luau-verify
description: >-
  Verifying Luau check results: running luau-analyze and luau-lsp analyze (mise shim "No version is set"), exit
  codes, negative controls before trusting zero diagnostics, repro files, CI gates. Use when a check must be
  trusted, a repro built, or a gate written. Type rules are luau-types. 트리거: 진단 0건 믿어도 돼?, 검사 게이트, 재현 파일.
---
# luau-verify

이 스킬은 "타입 검사 결과를 어떻게 믿을 수 있게 만드나"를 다룬다. 사실의 근거는 플러그인 루트의 `snippets/` 와 `tools/` 이고, 실행 결과는 `snippets/RESULTS.md` 다.

## 핵심 절차 (재현·검증 한 번)
1. **버전을 고정해 직접 부른다.** PATH 의 shim 대신 mise 설치 디렉터리의 `installs/luau/<ver>/luau-analyze` 를 쓰거나 `mise exec luau@<ver> --` 를 붙인다. → `references/toolchain.md`
2. **파일 첫 줄에 `--!strict`** 를 둔다. `.luaurc` 나 `--mode=strict` 에 기대지 않는다. → `references/tooling.md` §1
3. **검사한다. 진단은 stderr 다.** `2>&1` 을 붙인다. 진단이 있으면 rc=1, 린트만 있으면 rc=0. → `references/checkers.md` §1
4. **음성 대조군**(같은 실수의 다른 모양, 반드시 잡혀야 하는 줄)이 기대한 메시지로 잡혔는지 본다. 안 잡혔으면 0건은 아무 의미가 없다. → `references/negative-controls.md` §2
5. 의심스러우면 `--annotate` 로 추론 타입을 보고, `--solver=old` 와 다른 luau 버전으로 대조한다. → `references/checkers.md` §3–4
6. 결과를 **도구, 버전, 솔버와 함께** 적는다(예: "luau-analyze <버전> 새 솔버, luau-lsp 는 다름").
7. 지식으로 남길 사실이면 `snippets/` 에 표식을 단 최소 재현을 넣고 두 버전으로 돌린다. → `references/snippet-markers.md`

## 어느 도구로 검사하나
- 순수 Luau: `luau-analyze`(빠르고 luau 배포판과 같은 버전) 또는 `luau-lsp analyze --platform=standard --flag:LuauSolverV2=true`
- Roblox 코드: `luau-lsp analyze --platform=roblox --definitions=<globalTypes.d.luau> [--sourcemap=…]` 만 가능하다(luau-analyze 는 정의 파일을 못 읽는다). 정의 파일은 이 저장소의 `typedefs/globalTypes.d.luau`.
- 불리언 FFlag 는 `luau-analyze --fflags=이름=true`(`--help` 에 없음)로도 바꾼다. 정수 한도 플래그(too complex)는 luau-lsp `--flag:` 로만 바꿀 수 있다.
- 정확성 게이트는 순수 Luau 면 `luau-analyze`, Roblox 전역을 쓰면 `luau-lsp` + 정의 파일이다(결정 D-06, `references/checkers.md` §5).
- **DX 확인**: 공개 API 가 있는 라이브러리는 순수 Luau 라도 `tools/lsp_probe.py` 로 소비자 파일의 hover·자동완성·inlay 를 본다. 진단 0건이어도 소비자에게 `unknown` 이 보일 수 있다. → `references/checkers.md` §6

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| "No version is set for shim", 다른 디렉터리에서 결과가 다르다 | `references/toolchain.md` §1–2 |
| luau 0.734 와 0.742 중 무엇으로 고정하나, 버전을 올리는 절차 | `references/toolchain.md` §3–4 |
| luau-analyze 옵션, 출력 형식, 종료 코드, `--annotate` | `references/checkers.md` §1, §4 |
| luau-lsp analyze 와 정의 파일, FFlag 기본값, 한도 플래그 | `references/checkers.md` §2 |
| 새 솔버/옛 솔버/버전/도구 비교 실행 | `references/checkers.md` §3 |
| 공개 API 의 hover, 자동완성, 추론 타입 표시(DX) 확인 | `references/checkers.md` §6, `tools/lsp_probe.py` |
| Claude Code 에서 luau-lsp 를 LSP 도구로 쓰기(luau-lsp 플러그인), `.lsp.json` | `references/checkers.md` §6 |
| 진단 0건을 믿어도 되나, 대조군 만드는 법, 돌연변이 검사 | `references/negative-controls.md` |
| 알려진 결함을 테스트로 고정(고쳐지면 알림) | `references/negative-controls.md` §3, `references/snippet-markers.md` |
| 스니펫 표식 문법, 하네스 실행, RESULTS 표 갱신 | `references/snippet-markers.md` |
| `-O2`·`-g0`·`--codegen` 실행, 바이트코드·remark·native 크기 주장을 스니펫으로 고정 | `references/snippet-markers.md` §2a |
| Roblox 전역이 필요한 스니펫(luau-lsp + 정의 파일), luau-lsp 플래그 함정 | `references/snippet-markers.md` §2b, `references/checkers.md` §2 |
| `--fflags`, 엔진 무관 게이트, 같은 진단이 두 번 보고됨 | `references/checkers.md` §1 |
| require 가 에디터에선 풀리는데 실행은 실패(symlink, alias), nonstrict 거짓 클린, 다른 파일로 풀리는 오타 | `references/checkers.md` §7, `snippets/verify-require.sh` (경로 규칙 자체는 luau-runtime `require-by-string.md` §1–4) |
| 린트는 rc=0, 게이트를 종료 코드로 판정, selene 설정 탐색 | `references/tooling.md` §5 |
| pesde 워크스페이스·소비자 설치, Rojo 매핑, `self-upgrade` 가 핀을 가림 | `references/toolchain.md` §1, §5 |
| 테스트 작성, 러너 패턴, 에러 줄 단언, `-O2` 로 테스트 | luau-testing 스킬 |
| `.luaurc` nonstrict/strict, `--!strict` | `references/tooling.md` §1 |
| luau / lune / lute 중 무엇으로 실행하나, Roblox 의존 동작은 | `references/tooling.md` §2 (결정 D-03), luau-roblox 스킬 |
| `const` 를 써도 되나 | `references/tooling.md` §3 (결정 D-01: 써도 됨) |
| stylua 가 `f<<T>>` 를 `f << T >>` 로 바꿨다 | `references/tooling.md` §4 (결정 D-02), `tools/repro-stylua-typeargs.sh` |
| 타입 규칙 자체(왜 안 잡히나, 결함 카탈로그) | luau-types 스킬 |

## 자주 밟는 함정 (요약)
- shim 의 `--help` 는 실패해도 rc=0 이다. 존재 확인을 rc 로 하지 않는다.
- `2>/dev/null` 을 붙이면 진단이 사라진다.
- 재현 파일을 다른 프로젝트 디렉터리에 두면 그 프로젝트의 `.luaurc` 와 `mise.toml` 이 끼어든다. `/tmp` 의 새 디렉터리에서 돌린다.
- 음성 값은 주석으로 만든다(`(nil :: any) :: T`). 추론 결과로 만든 음성 값은 이미 샌 타입일 수 있다.
- luau-lsp 는 자기 내장 Luau 판으로 검사한다. 에디터 판정과 CI 판정은 다를 수 있다.
- `claude plugin validate` 는 `.lsp.json` 의 알 수 없는 키를 잡지 못한다. 고친 뒤에는 세션 도구 목록에 `LSP` 가 있는지 본다.
- stylua 는 설정 파일이 없는 디렉터리에서 돌면 `f<<T>>(x)` 를 조용히 망가뜨린다.
- `--fflags` 의 모르는 플래그 이름은 경고만 내고 rc=0 이다. 오타를 rc 로 알 수 없다.
- luau-lsp 는 symlink 와 접두 없는 `.luaurc` alias 를 풀지만 luau 런타임은 못 푼다. 에디터가 깨끗해도 한 번은 실제로 require 한다.
