---
title: "파일 머리, 모듈 모양, require"
description: "모듈 파일 머리(--!strict 와 왜를 적는 머리 주석), 값 하나 return, init.luau 안에서 ./ 대신 @self, 테스트 엔트리 이름, 패키지 사본·타입 전용 require, 주입 필드를 지역에 받는 문제(D-11), 엔진 무관 로직 분리"
keywords:
  - "파일 머리"
  - "--!strict"
  - "머리 주석"
  - "@self"
  - "init.luau require"
  - "require(\"./x\")"
  - "module must return a single value"
  - "Unknown require"
  - "unsupported path"
  - "동적 require"
  - "@game/ 절대 경로"
  - "패키지 사본 둘"
  - "타입 전용 require"
  - "모듈 필드 지역 별칭"
  - "languageMode nonstrict"
  - "--!nocheck"
kind: reference
category: luau/style/modules
tags: [policy, correction, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# modules — 파일 머리, 모듈 모양, require

## 이 파일이 답하는 질문
- 새 모듈 파일의 첫 줄들은 어떻게 쓰나?
- `init.luau` 안에서 `./x` 는 왜 폴더 밖을 찾나? `@self` 는 언제 쓰나?
- require 경로가 틀리면 타입 검사가 잡아 주나?
- 테스트 엔트리를 `init.luau` 로 지으면 왜 깨지나?
- 같은 패키지가 두 벌 설치되면 무엇이 깨지나? 타입만 쓰려는 require 도 실행되나?
- 나중에 주입되는 함수를 지역에 받아 둬도 되나?

## 목차
- §1 파일 머리: `--!strict` + 머리 주석
- §2 모듈 모양
- §3 require 경로 규칙
- §4 패키지 사본과 타입 전용 require
- §5 모듈 필드 읽기 (결정 D-11)
- §6 엔진 무관 로직 떼어 두기
- (파일 길이, 폴더 구조, 층, 데이터 분리는 `structure.md`)

---

## §1 파일 머리
status: verified (`--!strict` 의 필요) / described (머리 주석) · last-confirmed: luau 0.742 (0.734 동일) · 근거: luau-kb `snippets/modes-luaurc-nonstrict-silences.luau`, `snippets/modes-strict-directive-wins.luau`, stl-luau `.claude/base/typing-limits.md:105-124`

```lua
--!strict
--[[
	Blocker — 값 기반 emit 지연. Gate 위에 얹은 정책이다.
	(무엇을 하는가 한 줄 → 공개 표면 요약 → 소유·수명 같은 "왜")
]]
```
- **파일마다 `--!strict` 를 단다.** `.luaurc` 의 `languageMode` 한 단어가 `nonstrict` 로 바뀌면 에러 수백 건이 0건이 된다. CLI `--mode=strict` 도 `.luaurc` 를 덮지 못한다. 파일 지시자만 믿을 수 있다.
- 머리 주석에는 **코드에서 알 수 없는 것**을 쓴다. 표현을 왜 골랐는지, 소유와 수명, 의존 방향이다. "왜 래퍼인가", "크기를 왜 따로 세는가" 같은 문장이 좋은 예다.
- `--!nocheck` 는 따라 할 관례가 아니다.

## §2 모듈 모양
status: described · 근거: 저장소 실태(2026-11-10)

- 모듈은 테이블(또는 값) **하나를** `return` 한다. 테스트 파일도 끝에서 값을 돌려준다. 그러지 않으면 `module must return a single value` 가 난다.
- 모양의 틀(메타테이블 프리미티브, 트레이트 등록, 닷 함수 모음)은 저장소마다 다르다. **그 저장소의 본보기 파일을 열어 따른다.** 본보기 경로는 저장소 `.claude/` 문서에 있다.

## §3 require 경로 규칙
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 정본: luau-runtime `../../luau-runtime/references/require-by-string.md` §1·§2·§4·§5 (경로 해석표, ambiguous 에러, symlink, 정적 검사 범위), luau-verify `../../luau-verify/references/checkers.md` §7 (검사기와 런타임이 갈리는 자리) · 근거 스니펫: `snippets/style-require-paths.sh` R1–R4

이 절은 **규칙 한 줄씩**만 둔다. 이유와 재현은 정본에 있다.

```lua
-- pkg/src/init.luau
local Types = require("./types")     -- 나쁜 예: init.luau 의 ./ 는 폴더의 형제(pkg/types)를 찾는다
local Types = require("@self/types") -- 좋은 예
```
- `init.luau` 안에서 같은 폴더 파일은 `@self/x` 로 부른다. 바깥 폴더 이름(`./src/x`)을 적지 않는다. → 정본 §1
- 테스트 엔트리를 `init.luau` 로 짓지 않는다(`tests/run.luau`). → 정본 §1·§2
- `require` 인자는 문자열 리터럴로 쓴다. 동적 경로는 런타임은 돌지만 `--!strict` analyze 가 거부한다. → 정본 §5, checkers §7
- 파일마다 `--!strict` 를 단다. strict 가 있어야 없는 경로를 정적 검사가 잡는다. 있는 다른 파일로 풀리는 오타는 못 잡으므로 새 모듈에는 그 모듈을 실제로 `require` 하는 테스트를 둔다. → 정본 §5
- 워크스페이스 symlink 는 CLI 가 따라가지 않으니 실행 검증은 `cp -rL` 사본에서 한다. → 정본 §4
- Studio 의 문자열 require 규칙은 `roblox-engine` 담당이다. → roblox-engine `../../roblox-engine/references/require-in-roblox.md` §1

**`@game/…` 절대 경로** (status: described · 근거: claude-doctor `decisions/D-12-require-paths.md`)
> 정책: 결정(D-12, 2026-11-11). `@game/` 은 "위치가 바뀌는 번들에서만 금지"이다.
- 클라이언트로 복제돼 위치가 바뀌는 번들에서는 쓰지 않는다(devplorer).
- 고정 위치에서만 도는 코드는 쓴다(table-sim). 저장소 rules 가 정한다.

## §4 패키지 사본과 타입 전용 require
status: described · 정본: roblox-engine `../../roblox-engine/references/require-in-roblox.md` §2·§3, luau-runtime `../../luau-runtime/references/require-by-string.md` §8 · 후보 Q-107, Q-108, Q-109, R-45

- 같은 패키지의 설치 사본이 둘이면 모듈 수준 상태가 갈린다. 라이브러리는 코어를 직접 require 하지 말고 게임이 넘긴 인스턴스를 팩토리 인자로 받는다. → 정본 §8
- 타입만 쓰려는 `require` 도 런타임에 실행된다. 타입 전용 모듈은 가벼운 types 패키지로 분리해 일반 의존성으로 둔다. → 정본 §8
- require 되는 순간 Instance 같은 수명 있는 값을 만들어 모듈 변수에 쥐지 않는다. → 정본 §8

## §5 모듈 필드 읽기 (결정 D-11)
status: described · 근거: claude-doctor `decisions/D-11-object-shape-and-field-access.md`, devplorer `.claude/conventions.md:71` · 후보 D-C04
> 정책: 결정(D-11, 2026-11-11). 두 입장은 조건이 달라 모순이 아니다. 저장소 rules 가 다르게 정하면 그쪽을 따른다.

**(a) 나중에 주입되거나 다시 대입되는 값은 부를 때마다 `Module.x` 로 읽는다.**
```lua
local bindLifetime = module.bindLifetime   -- 나쁜 예: 받은 시점의 스텁을 영원히 잡는다
module.bindLifetime(inst, owner)           -- 좋은 예: 매번 읽는다(정적 필드 읽기는 충분히 빠르다)
```
테이블 값은 참조라 별칭으로 들어도 된다. 문제는 값 자체가 바뀌는 필드다.

**(b) 바뀌지 않는 함수는 실측된 뜨거운 루프에서만 지역으로 받는다.**
```lua
const push = Arr.PushBack         -- 루프 밖에서 한 번
for i = 1, n do push(out, f(i)) end
```
(b) 를 초기화·이벤트 경로까지 퍼뜨리지 않는다. 이득이 측정 오차 안이다. 수치는 `luau-perf`.

## §6 엔진 무관 로직 떼어 두기
status: described · 근거: table-sim `.claude/conventions.md:96`, devplorer `.claude/conventions.md:53`, tbox `CLAUDE.md:149-154` · 결정: D-03(러너 `luau`, 필요한 부분만 mock)

- 오브젝트 모델, 직렬화, 권한 판정, 트리 평탄화, 프로토콜 검증은 **Roblox API 없이** 짜서 `luau` CLI 스펙으로 돌린다.
- 엔진 쪽이 필요하면 최소 mock 을 쓴다. mock 작성법과 Studio 로 확인할 시점은 `luau-roblox` 에 있다.
- Roblox 데이터타입을 다루는 순수 라이브러리는 **로드 시점에 `Vector3` 같은 전역을 참조하지 않는다.** 판별은 `typeof(v) == "Vector3"` 문자열 비교로 한다.

## 정정 (원천 서술이 재현과 다른 것, 각 저장소 세션에 전달)
- "require 경로 오류는 정적 검사가 못 잡는다"(claude-doctor `decisions/D-12-require-paths.md` §2 "기록 3곳", `drafts/style/skills/luau-style/references/modules.md:314`)는 너무 넓다. `--!strict` 의 luau-analyze·luau-lsp 는 **없는** 경로를 `Unknown require` 로 잡는다. 못 잡는 것은 nonstrict 파일과 **있는 다른 파일로 풀리는** 경로다(`snippets/style-require-paths.sh` R3).
- "동적 require 경로는 `ambiguous` 에러를 낸다"(같은 초안 `modules.md:315`)는 재현되지 않았다. luau CLI 0.734·0.742 런타임은 동적 경로를 실행하고, strict 의 luau-analyze 가 `unsupported path` 로 거부한다(R3·R4). Studio 쪽은 재지 않았다.
- 테스트 엔트리 `tests/init.luau` 의 "ambiguous" 원인을 "`src/init.luau` 와 이름이 겹쳐서"라고 한 설명(tbox `CLAUDE.md:141-147`)은 맞지 않다. `tests/init.luau` 의 `./` 가 저장소 루트를 가리키는 것이 실제 함정이고, "ambiguous" 는 `X.luau` 와 `X/` 가 형제일 때 난다(후보 X-04 의 mrow 쪽 설명, R2, `snippets/rbx-require-cli.sh` Q4·Q5).
