---
title: "Studio 의 문자열 require, Instance 경로, ModuleScript 캐시와 VM 경계"
description: "Studio 문자열 require 의 경로 규칙과 에러(접두 필수, 대상을 기다리지 않음, @game, alias 대소문자), 이미 require 된 ModuleScript 캐시 때문에 Rojo 수정이 안 보이는 문제, 콘솔·플러그인·Actor VM 경계"
keywords:
  - "Studio 문자열 require"
  - "@game"
  - "@self"
  - "require path must start with a valid prefix"
  - "could not resolve child component"
  - "is not a valid alias"
  - "Unable to require module from given path"
  - "require 캐시 옛 본문"
  - "Rojo 수정 반영 안 됨"
  - "require(ms:Clone())"
  - "game.Loaded IsLoaded"
  - "플러그인 VM 경계"
  - "execute_luau require 상태 공유"
  - "pesde 소문자 폴더"
kind: reference
category: roblox/require
tags: [studio]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# require-in-roblox — Studio 의 문자열 require, Instance 경로, ModuleScript 캐시와 VM 경계

## 이 파일이 답하는 질문
- Q1 Studio 의 문자열 require 는 luau CLI 와 무엇이 다른가? 대상이 아직 없으면 기다리나? `@game`, alias 대소문자는?
- Q2 Rojo 로 고친 모듈이 Studio 에서 옛 본문을 돌려준다. 콘솔·플러그인·Actor 에서 require 한 모듈은 상태를 공유하나?
- Q3 Roblox 패키지에서 피할 모듈 설계는?

## 목차
- §1 Studio 의 문자열 require
- §2 require 캐시, VM 경계
- §3 Roblox 모듈 설계 함정
- 미판정

언어 차원의 규칙(`init.luau` 의 `./` 와 `@self`, ambiguous 에러, `.luaurc` alias 값, symlink, 정적 검사)은 엔진과 무관해서 luau-runtime `require-by-string.md` 가 정본이다. 이 파일은 Roblox 엔진·Studio 에서만 성립하는 것만 둔다.

---

## §1 Studio 의 문자열 require
status: described (Studio 열) / verified (CLI 열) · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, `rbvm-test`), Studio 0.738(quad, 2026-09-10), luau 0.734·0.742(CLI 열, `rbx-require-cli.sh` Q10) · 근거: rbvm `.claude/design/engine-behavior.md:68-83`; quad `.claude/audit/studio-docs-2026-09-10.md:227-290`, `.claude/archive/question-resolved.md:1649` · 후보: R-39, R-40, Q-105

| 경로(ModuleScript `Caller` 안, 형제 `Sibling`, 자식 `Child`) | Studio | luau CLI 대응 |
|---|---|---|
| `"./Sibling"`, `"../X/Sibling"`, `"@self/Child"`, `"@game/ReplicatedStorage/…"` | 성공 | `./`·`../`·`@self` 같음. `@game` 은 CLI 에 없음 |
| `"Sibling"`(접두 없음), `""` | `require path must start with a valid prefix: ./, ../, or @` | 같은 규칙 |
| `"./Missing"` | **즉시** `could not resolve child component "Missing"` (0.00초, 기다리지 않음) | 같음 |
| `"./"` | `Unable to require module from given path './'` | 실패(`no module present at resolved path`) |
| `"./Sibling/"`(끝 슬래시), `".//Sibling"`(빈 세그먼트) | **성공** | 성공(0.734·0.742) |
| `"@foo/X"` / `"@Self/Child"` | `@foo is not a valid alias` / 성공(대소문자 무시) | `@Self`·`@SELF` 성공(대소문자 무시) |

- **문자열 require 는 대상이 생길 때까지 기다리지 않는다.** 그래서 클라이언트 진입점은 require 전에 `if not game:IsLoaded() then game.Loaded:Wait() end` 를 둔다. Play Solo 에서는 첫 줄에 이미 `IsLoaded() == true` 였다. 실서버 접속 순서는 재지 않았다.
- 위치가 바뀌는 트리(클라이언트 번들이 PlayerGui 로 복제되는 경우 등)는 `@game/...` 절대 경로 대신 상대 경로와 `@self` 를 쓴다(devplorer, luau-lsp 실측 2026-10-19).
- alias(원천 실측): 모르는 alias 는 `@foo is not a valid alias`, alias 는 대소문자를 가리지 않는다(`@Self/Child` 성공). `@game/...` 은 절대 경로다.
- darklua 0.19.0 `convert_require` 는 `@self`/`@game` 은 건드리지 않고 커스텀 alias 만 Rojo sourcemap 기준으로 바꾼다(quad, described).

mock 흉내: rbvm 은 **아니오**. 없는 모듈·빈 세그먼트·미지원 alias 에서 무한 대기하고 접두 없는 이름을 받아 준다(rbvm S6, D7). 엔진은 셋 다 즉시 에러다.

## §2 require 캐시, VM 경계
status: described · last-confirmed: quad 2026-09-02·09-08·09-10 Studio, table-sim·devplorer 관용구 · 근거: quad `.claude/audit/sugar-studio-2026-09-08.md:8-10`, `.claude/audit/m5-unit5-first-render-2026-09-02.md:26-30`, `.claude/research/debug-tooling-plan.md:66-71`; table-sim `.claude/conventions.md:139`; devplorer `.claude/conventions.md:93`; rbvm `.claude/review/2026-10-05-sibling-repos.md:135-136` · 후보: Q-106, T-55, Q-057

- **이미 require 된 ModuleScript 는 캐시된다.** Rojo 가 `Source` 를 바꿔도 같은 세션의 `require` 는 옛 본문을 돌려준다. 처방: Play 를 다시 시작하거나, 단일 모듈은 `require(ms:Clone())`, 상대 require 가 있는 패키지는 폴더째 `:Clone()` 해 임시 폴더에 두고 사본을 require 한다. 복제 전에 자식 수가 디스크와 같은지 확인한다(스트리밍 중 부분 트리).
- 콘솔·`execute_luau` 에서 require 한 모듈은 게임 스크립트의 모듈과 **상태를 공유하지 않는다.**
- 플러그인과 Play 중 게임은 별도 VM 이라 `_G`, `shared`, require 캐시가 공유되지 않는다. 같은 DataModel 의 `BindableEvent`/`BindableFunction` 은 그 경계를 넘는다(quad 2026-08-06, 원시값만 확인).
- Actor 마다 VM 이 따로라 모듈 수준 상태도 Actor 별로 갈라진다(`parallel-luau.md` §7). 같은 패키지 **사본** 둘이 상태를 가르는 문제는 언어 차원이라 luau-runtime `require-by-string.md` §8.

mock 흉내: 해당 없음(Studio 세션 동작).

## §3 Roblox 모듈 설계 함정
status: described · 근거: quad `scripts/relink.sh:97-103`, `.claude/base/module-lifecycle-plan.md:164-172`; devplorer `.claude/research/feature-proposals-2.md:77,265-266` · 후보: Q-107, D-F27, Q-109

- pesde 로 설치한 패키지 폴더 이름은 소문자라, 이름으로 루트를 찾지 말고 `script.Parent` 를 보관해 쓴다.
- require 할 때 Instance 를 만들어 모듈 변수에 쥐지 않는다(`instance-lifecycle.md` §7).
- 같은 패키지 사본 둘, 타입 전용 require 의 실행, 순환 require 는 언어 차원이다 → luau-runtime `require-by-string.md` §8.

mock 흉내: rbvm 의 require 대체가 엔진과 갈리는 점은 §1 의 mock 흉내 줄.

---

## 미판정
- **실서버에서 클라이언트 첫 require 시점의 `IsLoaded`.** 절차: 게시한 플레이스에서 LocalScript 첫 줄에 `game:IsLoaded()` 와 `os.clock()` 을 기록하고 Developer Console 로 읽는다.
