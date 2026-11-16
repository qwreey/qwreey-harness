---
title: "스니펫 표식 문법과 하네스 사용법"
description: "snippets/*.luau 의 줄 끝 표식(expect-error, bug-present, 버전 조건)과 머리 주석(--@run, --@run-opt, --@compile, --@codegen, --@lsp-roblox) 문법, 하네스 강제 규칙, check_snippets.py 실행과 RESULTS 표, 새 주장 추가 순서"
keywords:
  - "스니펫 표식"
  - "snippet marker"
  - "-- expect-error"
  - "-- bug-present"
  - "버전 조건 표식"
  - "--@run"
  - "--@run-opt"
  - "--@run-with"
  - "--@compile"
  - "--@codegen"
  - "--@inline-remarks"
  - "--@lsp-roblox"
  - "--@luaurc"
  - "--@no-control"
  - "check_snippets.py"
  - "RESULTS.md"
  - "하네스 규칙"
  - "새 주장 추가"
  - "doc-snippets.py"
kind: reference
category: luau/verify/snippets
tags: [cli, o2]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - luau-lsp 1.69.0
  - luau-lsp 1.70.1
---
# snippet-markers — 스니펫 표식 문법과 하네스 사용법

## 이 파일이 답하는 질문
- Q1 `snippets/*.luau` 에 어떤 표식을 쓰나?
- Q2 버전마다 다른 동작은 어떻게 적나?
- Q3 `.luaurc` 나 옛 솔버가 필요한 스니펫은? Roblox 정의 파일이 필요한 스니펫은?
- Q4 `-O2`, `-g0`, `--codegen` 으로 실행한 결과나 바이트코드·remark·native 코드 크기에 걸린 주장은 어떻게 고정하나?
- Q5 하네스를 어떻게 돌리고, 결과표는 어떻게 만드나?
- Q6 새 주장을 references 에 추가하는 순서는? 파일 하나로 안 되는 주장은?

## 목차
- §1 줄 끝 표식
- §2 머리 주석 (검사)
- §2a 실행 머리 (최적화 수준, 컴파일 출력, native 코드 크기)
- §2b Roblox 모드 (luau-lsp + 정의 파일)
- §3 하네스가 강제하는 규칙
- §4 실행과 결과표
- §5 새 주장을 추가하는 순서
- §6 다른 저장소의 표식 어휘

---

## §1 줄 끝 표식
status: verified · last-confirmed: luau 0.734·0.742, luau-lsp 1.69.0·1.70.1 · 근거: `tools/check_snippets.py`, `snippets/RESULTS.md`

| 표식 | 뜻 | 통과 조건 |
|---|---|---|
| `-- expect-error` | 이 줄은 음성 대조군이다 | 그 줄에 TypeError/SyntaxError 가 1건 이상 |
| `-- expect-error: 부분문자열` | + 메시지 검사 | 그 줄의 메시지(이어진 줄 포함) 중 하나에 부분 문자열이 있음 |
| `-- bug-present` | 지금 잡히지 않는 알려진 한계 | 그 줄에 진단 0건. 진단이 생기면 "동작이 바뀜"으로 실패 |
| `… [<0.742]` 등 | 버전 조건. `<`, `<=`, `>`, `>=`, `=` 와 `x.y` 또는 `x.y.z`. Roblox 모드(§2b)에서는 luau-lsp 버전과 비교한다(`[>=1.70]`) | 조건이 맞는 버전에서만 그 표식이 살아 있다 |
| `A || B` | 한 줄에 표식 여럿(보통 버전별로 갈라 씀) | 각 버전에서 살아 있는 표식은 정확히 하나여야 함 |

예:
```luau
F(text, function(v: number) end) -- bug-present
local leaked: { string } = Map2({ 1, 2 }, function(v) return v end) -- bug-present [<0.742] || expect-error [>=0.742]
local s: string = c[1] -- bug-present [<0.742] || expect-error: number | string [>=0.742]
```

- 표식은 **코드 줄의 끝 주석**에만 쓴다. `--` 로 시작하는 순수 주석 줄의 표식 이름은 무시된다(설명문 오인 방지).
- 부분 문자열에는 ` || ` 를 쓸 수 없다.

## §2 머리 주석 (처음 30줄)
status: verified · 근거: `snippets/modes-*.luau`, `snippets/recursion-old-solver-rejects.luau`, `snippets/verify-fflags-force-strict.luau`, `--@run` 스니펫들

| 머리 | 뜻 |
|---|---|
| `--@run` | 검사 통과 뒤 같은 버전의 `luau` 로 실행, rc=0 이어야 함. 런타임 증거(`assert`)를 둘 때 쓴다 |
| `--@run=lune` | lune 으로 실행(lune 은 `const` 를 못 읽는다. tooling.md) |
| `--@solver=old` | `--solver=old` 로 검사 |
| `--@luaurc {json}` | 임시 디렉터리에 이 내용의 `.luaurc` 를 두고 검사 |
| `--@args …` | `luau-analyze` 에 덧붙일 인자(예: `--mode=strict`, `--fflags=DebugLuauForceStrictMode=true`). Roblox 모드에서는 luau-lsp 인자 |
| `--@no-control 이유` | `bug-present` 가 있어도 대조군 없이 허용(짝 파일을 이유에 적는다) |

## §2a 실행 머리 (최적화 수준, 컴파일 출력, native 코드 크기)
status: verified · last-confirmed: luau 0.734·0.742 (x64) · 근거: `snippets/opt-*.luau`, `snippets/native-*.luau`, 하네스 돌연변이 6종(`snippets/RESULTS.md` "하네스 자체 검증")

`--@run` 은 CLI 기본(`-O1 -g1`, 인터프리터)으로만 돈다. 라이브 Roblox 는 최적화 수준 2 로 돌고 `-O1` 테스트로는 인라인 때문에 생기는 실패가 보이지 않는다(luau-testing 스킬). 그래서 실행 조건 자체가 주장인 스니펫은 아래 머리로 조건을 고정한다. 모두 타입 검사가 통과한 뒤 같은 luau 버전의 `luau`/`luau-compile` 로 돈다. `run-with`·`compile`·`codegen` 은 여러 줄 쓸 수 있다.

| 머리 | 뜻 | 예 |
|---|---|---|
| `--@run-opt=2` | `luau -O2 파일` 도 rc=0. 쉼표로 여럿 | `--@run-opt=0,2` |
| `--@run-with 인자 => ok\|fail[; out~정규식][; out!~정규식]` | `luau 인자 파일` 의 rc 와 출력(stdout+stderr) | `--@run-with -O1 => fail; out~check: expected number` (지시어 없는 파일이 -O1 에서 실패해야 함 = 음성 대조군) |
| `--@compile 인자 => out~정규식[; out!~…]` | `luau-compile 인자 파일` 출력. `--remarks` 면 `-- remark:` 줄만 본다(소스와 머리 주석이 함께 찍히므로) | `--@compile --text -O2 => out!~math\.sqrt` |
| `--@inline-remarks=2` | `luau-compile --remarks -O2` 의 인라인 remark 를 각 줄 끝 `[inline:ok\|variadic\|multret\|expensive\|none]` 태그와 맞춘다 | `opt-inline-rules.luau` |
| `--@codegen 인자 => 단언[; 단언]` | `luau-compile --codegen 인자 --record-stats=function` 의 함수별 `asmSize`. 단언은 `이름[*k] (<\|<=\|>\|>=\|==) 이름[*k]` 와 `names = a,b,…`(최상위는 `[top-level]`). 인자 `+native` 는 파일 앞에 `--!native` 를 붙인 사본 | `--@codegen +native => typed*3 < untyped` |

- `asmSize` 는 아키텍처(x64/a64)와 버전마다 다르다. 바이트 수를 적지 말고 **비율과 대소**로만 단언한다.
- 실행 머리는 줄 번호를 바꾼다. 줄 번호를 단언하는 스니펫은 머리를 먼저 쓰고 번호를 센다(또는 `debug.info(1, "l")` 로 잰다).
- 실행은 `ulimit -v` 2 GB, `--codegen` 실행은 주소 공간 예약 때문에 상한 없이 시간 한도(60초)만 둔다.
- 옛 `claude-doctor .claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/run_opt.sh` 의 29개 확인(A 지시어 우선, B CLI 수준, C codegen, D `-g0`, E 인라인, F 접기·펼치기, G 주석과 codegen 크기, H `@native` 범위)은 모두 이 머리로 옮겼다(`opt-*`, `native-*`).

## §2b Roblox 모드 (luau-lsp + 정의 파일)
status: verified · last-confirmed: luau-lsp 1.69.0·1.70.1 · 근거: `tools/check_snippets.py analyze_roblox`, claude-doctor `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/snippets/{roblox,parallel}-*.luau` 13개 × 2 버전 통과(2026-11-10)

- 머리 `--@lsp-roblox` 가 있거나 명령행 `--mode roblox` 면 `luau-lsp analyze --platform=roblox --definitions=typedefs/globalTypes.d.luau --flag:LuauSolverV2=true` 로 검사한다. 버전은 `--rbx-lsp 1.70.1,1.69.0`(기본: 둘 중 설치된 것), 정의 파일은 `--defs`.
- `--@args` 는 luau-lsp 에 붙고 **기본값보다 앞에** 온다. luau-lsp 함정 둘을 하네스가 처리한다(1.70.1 실측):
  1. 같은 `--flag:` 가 두 번 오면 **앞의 값**이 이긴다(`--flag:LuauSolverV2=false --flag:LuauSolverV2=true` 는 옛 솔버). 머리에 그 플래그가 있으면 기본값을 넣지 않는다.
  2. `--platform` 을 두 번 주면 `Duplicate argument` 로 실행이 실패한다. 머리에 있으면 기본값을 넣지 않는다(`--definitions` 도 같게 처리).
- `--@sourcemap {json}` 은 Rojo 형식 sourcemap 을 임시 파일로 두고 `--sourcemap` 으로 넘긴다.
- Roblox 모드에서는 실행 머리(§2a)를 쓸 수 없다(엔진이 없다). 런타임 동작은 luau-roblox 스킬의 절차(mock 또는 Studio)로 확인한다.
- `--table` 은 Roblox 모드 파일을 luau-lsp 버전 열을 가진 별도 표로 출력한다.

## §3 하네스가 강제하는 규칙
status: verified · 근거: 돌연변이 검사 4종(`snippets/RESULTS.md`)

1. 표식 없는 줄의 진단은 실패다(뜻밖의 진단도 정보다).
2. `expect-error` 줄에 진단이 없으면 실패다(검사기가 꺼진 0건 방지).
3. `bug-present` 가 있는 파일에는 그 버전에서 살아 있는 `expect-error` 가 하나 이상 있어야 한다.
4. 파일은 임시 디렉터리로 복사해서 검사한다. 상위 디렉터리의 `.luaurc` 가 끼어들지 않는다.
5. 검사는 `ulimit -v 2097152; timeout 120` 안에서 돈다. rc 가 0/1 이 아니면 실패다.
6. 린트(`LocalUnused`, `UnknownType` 등)는 판정하지 않는다. 린트에 걸린 주장은 수동 확인으로 `snippets/RESULTS.md` 에 적는다.
7. 실행 머리는 타입 검사가 통과한 뒤에만 돈다. 실행 머리의 실패도 그 버전의 실패다.

## §4 실행과 결과표
status: verified

```bash
cd /code/Projects/claude-doctor/packs/luau-kb
python3 -I tools/check_snippets.py snippets/*.luau                         # 기본 0.746 (LUAU_VER 로 변경)
python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau      # 행렬, 하나라도 실패면 rc=1
python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 --lsp 1.70.1 --table snippets/*.luau > /tmp/t.md
python3 -I tools/check_snippets.py --mode roblox --rbx-lsp 1.70.1,1.69.0 snippets/rbx-*.luau   # 머리 없는 Roblox 스니펫
bash snippets/tf-cross-module.sh; bash snippets/verify-require.sh                   # 모듈 여럿이 필요한 주장
```

- `--table` 은 `snippets/RESULTS.md` 의 표 형식으로 출력한다. 칸의 `E`/`B` 는 살아 있는 표식 수, `run` 은 `--@run` 통과, `X<n>` 은 실행 머리(§2a) 검사 수다.
- `--lsp` 열은 참고용이다. luau-lsp 가 어느 Luau 판을 내장했는지 하네스가 모르므로, 버전 조건이 섞인 줄은 판정하지 않고 "잡음/무진단"만 적는다.
- 파일 인자는 반드시 준다(glob 은 셸이 푼다). `-I` 는 현재 디렉터리의 파이썬 모듈이 끼어들지 않게 한다.

## §5 새 주장을 추가하는 순서
1. 라이브러리 없이 15줄 안팎으로 재현한다. 파일명은 `<주제>-<요지>.luau`. 주제 접두: 타입(generics, variance, unions, recursion, tf, solver, modes, pack), 검증(verify), 테스트(test), 최적화 수준·native(opt, native), 성능(perf), Roblox(rbx), 스타일(style). 모듈 여럿이나 symlink 가 필요하면 `<주제>-<요지>.sh` 로 쓰고 기대와 어긋나면 rc=1 을 내게 한다(`tf-cross-module.sh`, `verify-require.sh`).
2. 머리 주석에 `-- 주장:` 과 `-- 근거:`(원천 경로와 절)를 쓴다.
3. 주장 줄에 `bug-present` 나 `expect-error` 를, 옆에 대조군을 둔다.
4. 두 버전으로 돌려 통과시킨다. 실행 조건이 주장이면 §2a 머리로, Roblox 전역이 필요하면 §2b 머리로 고정한다. 재현이 안 되면 주장을 고치거나 references 에서 `status: described` 로 둔다.
5. references 의 절에 `status: verified · last-confirmed: luau <ver> · 근거: snippets/<파일>` 을 단다.
6. `--table` 로 `snippets/RESULTS.md` 를 갱신한다.

## §6 다른 저장소의 표식 어휘
status: described · 원천: quad/scripts/doc-snippets.py 머리 docstring(후보 Q-117, 2026-11-10 기준 561블록·게이트 12.6초), stl-luau/.claude/tools/spike-diff.py

- quad 문서 펜스: 정보 문자열 `continue`(앞 블록에 이어 붙임), `skip`(검사도 실행도 안 함), `no-run`(검사만), `error=<ID>`(실행이 그 에러를 내야 함). 강제하는 닫힌 어휘다. 블록 안 줄 끝 `-- 타입 에러` 는 그 줄에 진단이 있어야 한다는 뜻이다. 시그니처만 있는 블록은 자동 제외된다.
- stl 스파이크: 소스에 표식을 넣지 않고 `scripts/spike-expectations.tsv` 에 `건수, 경로, 줄 목록` 을 둔다. `spike-diff.py` 가 줄별 건수를 대조해 어긋난 줄만 출력한다.
- 세 어휘는 같은 생각(기대 진단을 미리 적고 차이를 실패로)을 다른 매체에 적용한 것이다. 이 저장소 표식은 `.luau` 파일 정본용이다.
