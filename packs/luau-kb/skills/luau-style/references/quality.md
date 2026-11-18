---
title: "주석, 마커, 포맷, 테스트 관용, 검증과 보고"
description: "주석 언어와 왜를 쓰는 주석, --- 문서 주석과 Ref: 위치, TODO 마커, stylua 를 저장소 루트에서 syntax = Luau 로 돌려 f<<T>> 를 지키기, 프레임워크 없는 테스트 관용, exit code 판정과 보고 범위, 성능 주장"
keywords:
  - "주석 언어"
  - "comment language"
  - "--- 문서 주석"
  - "-- Ref:"
  - "--#region"
  - "TODO 마커"
  - "@deprecated"
  - "stylua 하위 폴더"
  - "--search-parent-directories"
  - "syntax = \"Luau\""
  - "stylua: ignore"
  - "f << T >>"
  - "exit code 판정"
  - "ALL PASS"
  - "2>/dev/null"
  - "ulimit -v"
  - "보고 범위"
  - "관측 계약 아님"
  - "특성화 테스트"
kind: reference
category: luau/style/quality
tags: [policy, cli]
last_verified: 2026-11-10
last_confirmed:
  - stylua 2.5.2
---
# quality — 주석, 마커, 포맷, 테스트 관용, 검증과 보고

## 이 파일이 답하는 질문
- 주석은 어느 언어로, 무엇을 쓰나? `---` 와 `-- Ref:` 는 어디에 두나?
- 코드 `TODO` 는 어떻게 남기나?
- stylua 를 돌렸더니 `f<<T>>` 가 `f << T >>` 가 됐다. `-- stylua: ignore` 가 안 먹는다.
- 테스트 프레임워크 없이 무엇을 어떻게 단언하나?
- 타입 검사는 어떤 도구로 하나? "통과"라고 보고해도 되나?
- 성능 주장은 어떻게 적나?

## 목차
- §1 주석과 문서화 (결정 D-08)
- §2 코드 `TODO` 마커 (결정 D-07)
- §3 포맷: stylua 를 안전하게 돌리기 (결정 D-02)
- §4 테스트 관용 (결정 D-03)
- §5 검증과 보고 (결정 D-06)
- §6 성능 주장 (결정 D-05)

---

## §1 주석과 문서화 (결정 D-08)
status: described (언어·내용) / verified (`---` hover, stylua ignore 는 §3) · 근거: qwreey-harness `.claude/base/decisions/D-08-comment-language.md`, quad `.claude/conventions.md:345`, quad `.claude/audit/deprecated-props-spike-2026-09-09/REPORT.md:13-17`(luau 0.734 / luau-lsp 1.69.0) · 후보 Q-116

**공통(일곱 저장소 일치)**: 식별자와 에러 메시지는 영어다. 주석은 **그 파일에 이미 쓰인 언어**를 따른다.
> 정책: 결정(D-08, 2026-11-11). 식별자·에러 메시지는 영어, 주석은 그 파일의 기존 언어, 새 파일의 주석 언어는 저장소 rules 가 정한다(영어 쓰는 저장소, 한국어 쓰는 저장소, "짧은 건 영어·긴 이유는 한국어" 저장소가 있다). 공개 패키지의 새 파일 언어를 따로 영어로 통일하지는 않는다.

- **"왜"를 쓴다.** 코드가 말하는 "무엇"을 반복하지 않는다. 버린 대안과 그 이유, 의도적으로 이상한 코드에 대한 경고를 쓴다.
  ```lua
  nop(gcHold) -- call nop     ← 나쁜 예
  nop(gcHold) -- 클로저가 gcHold 를 업밸류로 잡게 하는 참조다. 지우면 GC 사슬이 조용히 끊긴다 — 설계 문서 §2   ← 좋은 예
  ```
- **선언 문서는 `---` 로 쓴다.** luau-lsp 는 멤버 접근 hover 에 선언 바로 위의 연속된 `---` 줄만 띄운다. 테이블 키 자동완성에는 doc 주석이 실리지 않는다.
- 공개 함수(다른 모듈이 부르는 것)에는 `---` 문서를 단다. luau-lsp 1.70.1 은 선언 바로 위에 이어진 `---` 와 `--[=[ ... ]=]` 만 호버와 자동완성 문서 칸에 싣고, `--` 는 싣지 않는다. 서버는 자르지 않으므로 첫 줄을 한 문장 요약(약 80자)으로 두어 문서 칸 첫 줄에 들어오게 하고, 세부는 빈 `---` 줄 뒤에 쓴다. `@param`/`@return` 은 Parameters/Returns 절로 그려진다.
- 설계 이유는 `---` 문서 안이 아니라 그 위의 `--` 주석에 따로 둔다. 문서 칸에는 쓰는 법만 남아야 호출하는 쪽이 읽는다.
- 원장 추적 줄(`-- Ref: 2026-11-10 H-973`)은 `---` 블록 **위**에 둔다. 사이에 끼우면 문서가 끊긴다.
- **공개 소스에 원장 번호만 남기지 않는다.** 외부 기여자에게 `H-231` 은 뜻이 없다. 이유 문장을 쓰고 번호는 `Ref:` 꼬리로 붙인다.
- `@deprecated` 는 함수에만 먹는다. 필드에 달면 무효다(luau 0.734 기록).
- 큰 파일은 `--#region 이름` / `--#endregion 이름` 으로 접는다.
- 지금 동작을 고정한 서술에는 **"관측 — 계약 아님"** 을 붙인다. 나중에 바꿔도 호환성 파괴가 아니게 하려는 것이다.

## §2 코드 `TODO` 마커 (결정 D-07)
status: described · 근거: qwreey-harness `.claude/base/decisions/D-07-finished-todos.md` §4, rbvm `src/signal.luau:54`(나쁜 예의 실례)
> 정책: 결정(D-07, 2026-11-11). D-07 의 본론(끝난 할 일 목록을 지울지 보존할지)은 `.luau` 편집 규칙이 아니라서 이 스킬 밖이다. 여기에는 코드 마커 한 줄만 둔다.

```lua
error("Connection already disposed") -- TODO: fix error message           ← 나쁜 예: 이유도 추적처도 없다
-- TODO: 메시지에 시그널 이름을 싣는다 — 지금은 어느 연결인지 모른다. Ref: todos.md #4   ← 좋은 예
```
- 이유와 추적처(할 일 목록 항목, 이슈 번호)를 붙인다. 끝나면 마커를 지운다.

## §3 포맷: stylua 를 안전하게 돌리기 (결정 D-02)
status: verified · last-confirmed: stylua 2.5.2 · 근거: luau-kb `tools/repro-stylua-typeargs.sh`, `snippets/style-stylua-pitfalls.sh` P1·P2, `decisions/D-02-stylua.md` §2 · 결정: D-02 (2026-11-10 확정) · 후보 S-130, S-131

**결정(확정)**: 포맷 값(들여쓰기, 괄호, 폭)은 저장소 `stylua.toml` 이 소유한다. 공통 규칙은 실행 방법 셋뿐이다.
1. **손으로 정렬하지 않는다. 저장소 루트에서 `stylua` 를 돌린다.** 하위 폴더에서 `stylua file.luau` 를 돌리면 상위 설정을 찾지 않는다. 기본 설정이 적용되어 **exit 0 으로** 이렇게 바뀐다.
   ```lua
   local a = id<<number>>(1)      -- 원본
   local a = id << number >> 1    -- 하위 폴더에서 포맷한 결과 (의미가 깨진다)
   ```
   하위 폴더에서 돌려야 하면 `stylua --search-parent-directories <파일>` 을 쓴다.
2. **`stylua.toml` 에 `syntax = "Luau"` 가 있어야 한다.** 있으면 `f<<T>>`, `f<<A, B>>`, `Box<Box<T>>`, 괄호 없는 `f<<T>> {…}` 가 모두 안전했다.
3. **`<<` 가 든 파일은 포맷 뒤 diff 에서 `<<`/`>>` 를 확인한다.**
- 설정 파일이 없는 저장소(손 포맷)에서는 stylua 를 돌리지 않는다.
- 새 저장소 기본값은 Tabs + `call_parentheses = "Input"` 이다(+ `syntax = "Luau"`, 폭 120, `AutoPreferDouble`, `collapse_simple_statement = "Never"`, `line_endings = "Unix"`).
- `-- stylua: ignore` 는 **주석 전체가 정확히 그 글자**여야 먹는다. 뒤에 설명을 붙이면 무시되고 포맷된다. 블록은 `-- stylua: ignore start` / `-- stylua: ignore end`. 정렬해 둔 표에만 쓴다.
- `const` 다음 줄의 `;(…)` 를 stylua 가 지운다 → `idioms.md` §1 함정 2.

## §4 테스트 관용 (결정 D-03)
status: described · 근거: stl-luau·moonwave-luau·tbox·quad 테스트 관행, `decisions/D-03-runner.md` (2026-11-10 확정, 보완)

- **러너는 `luau` CLI 다.** lune 은 `const` 를 파싱하지 못해서 쓰지 않는다. Roblox 서비스에 기대는 동작은 필요한 부분만 mock 해서 `luau` 로 돌리고, mock 이 실제와 맞는지는 Studio MCP 로 확인한다 → `luau-roblox`.
- 프레임워크 없이 `assert(cond, "메시지")` 로 쓴다. 엔트리는 `tests/run.luau`(이름을 `init.luau` 로 짓지 않는다, `modules.md` §3), 파일은 주제마다 하나다. 파일 끝에서 값을 `return` 한다.
- **경계 케이스를 고정한다**: 빈 것 / 한 개 / 뒤집힌 구간 / 범위 초과 / 음수 인덱스. 조용히 clamp 하는 API 는 테스트가 없으면 "아무것도 안 함"과 "망가짐"을 구분하지 못한다.
- **눈에 안 보이는 것은 오라클과 대조한다**: 이분 탐색은 선형 탐색과, 힙은 정렬 결과와, 무작위 입력 수백 회로.
- **테스트 데이터가 우연히 맞지 않게 고른다.**
  ```lua
  local m = Map.FromTable({ [1] = 1, [2] = 2, [3] = 3 })          -- 나쁜 예: "키를 인덱스로 쓰는" 버그가 통과한다
  local m = Map.FromTable({ [10] = "x", [20] = "y", [30] = "z" })  -- 좋은 예: 키·값·위치가 모두 다르다
  ```
- **새 타입 계약에는 음성 대조군을 만든다.** 진단 0건은 검사가 죽어도 나온다. 절차는 `luau-verify` 의 negative-controls.
- 지금 동작을 고정하는 특성화 테스트에는 "옳아서가 아니라 조용히 바뀌지 않게"라고 적는다.
- 에러 테스트는 `errors.md` §5.

## §5 검증과 보고 (결정 D-06)
status: described · 근거: quad `.claude/conventions.md:348-355`(줄 세기로 5커밋 동안 실패를 놓친 기록), stl-luau 2026-10-13 메모리 사고 기록, `decisions/D-06-type-checker.md` (2026-11-10 확정, 보완) · 후보 Q-082

- **판정은 저장소 게이트 스크립트의 exit code 로 한다.** "ALL PASS" 줄을 세지 않는다. 린트만 나와도 exit 0 일 수 있으니, 게이트가 린트를 어떻게 다루는지 본다.
- 진단은 **stderr** 로 나온다. `2>/dev/null` 로 버리면 "0건"으로 착각한다.
- **검사기 선택(결정 D-06)**
  - 정확성 게이트: 순수 Luau 는 `luau-analyze`, Roblox 전역을 쓰는 코드는 `luau-lsp analyze` + 정의 파일.
  - DX 확인(자동완성, hover, 공개 API 의 추론 타입 표시): 공개 API 를 다루는 라이브러리면 순수 Luau 라도 luau-lsp 도 돌린다.
  - 호출법은 `luau-verify` 의 checkers.
- `luau` 를 직접 돌릴 땐 상한을 같이 건다: `( ulimit -v 1048576; timeout 60 luau … )`. 무한 루프 하나가 메모리 12GB 를 채운 사고가 있었다.
- 보고할 때 범위를 구분한다: **"타입·포맷만 통과" / "스펙 통과" / "Studio 실측"**. 돌려 보지 않은 것을 "동작 확인"이라고 쓰지 않는다.
- 게이트 스크립트를 고쳤으면 일부러 한 번 깨뜨려 실패하는지 본다.

## §6 성능 주장 (결정 D-05)
status: described · 근거: stl-luau `.claude/base/perf-measurements.md` 운영 방식, quad `.claude/conventions.md:50-58`, qwreey-harness `.claude/base/decisions/D-05-toolchain-pins.md`
> 정책: 결정(D-05, 2026-11-11). "수치·결함 서술에는 Luau 버전을 적는다"를 공통 규칙으로 둔다. 버전 핀 값은 저장소가 정하고, 0.742 로 맞추는 것은 프로젝트별 권고 목표다.

- 성능 주장은 **실측으로** 한다. 숫자는 저장소의 한 문서에 모으고, 측정한 Luau 버전과 모드(`-O1`/`-O2`/native)를 적는다.
- 편의 기능이 기본 경로를 느리게 만들지 않게 한다. 편의는 별도 이름으로 옆에 둔다(예: `PushBack` / `PushBackMany`).
- 구조(메커니즘, 필드, 경로)는 관측된 문제에만 더한다. 입구 한 줄 검사처럼 싼 품질 개선은 예외다.
- 측정 방법과 수치는 `luau-perf` 에 있다.
