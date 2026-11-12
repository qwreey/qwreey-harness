---
title: "새 문법을 언제부터 쓰나"
description: "class·if local·while local·const 같은 새 문법 채택 판정: CLI·luau-lsp·stylua·Studio/라이브 4조건과 2026-11-10 판정표, CLI 가 실험 FFlag 를 켜는 함정, 재현 명령, 못 쓰는 문법 대비(이름 충돌·우회 금지)"
keywords:
  - "새 문법 채택"
  - "syntax adoption"
  - "새 문법 써도 되나"
  - "if local 채택"
  - "if local 써도 되나"
  - "while local"
  - "class 문법"
  - "class syntax"
  - "const 채택"
  - "4조건 판정표"
  - "LuauExperimentalIfLocalSyntax"
  - "DebugLuauUserDefinedClasses"
  - "class keyword is illegal here"
  - "stylua 새 문법 파싱"
  - "FFlag 뒤 문법"
  - "실험 문법 CLI"
  - "Studio 베타 문법"
kind: reference
category: luau/upstream/syntax
tags: [policy, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
  - luau 0.746
  - luau-lsp 1.69.0
  - luau-lsp 1.70.1
  - lune 0.10.5
  - stylua 2.5.2
  - stylua 2.6.0
---
# syntax-adoption — 새 문법을 언제부터 쓰나

## 이 파일이 답하는 질문
- Q1 `class`, `if local`, `while local`, `const` 같은 새 문법을 지금 써도 되나?
- Q2 판정에 필요한 조건은 무엇이고, 각 도구가 지금 어디까지 지원하나?
- Q3 아직 못 쓰는 문법에 미리 대비할 것은 무엇인가?
- Q4 이 판정은 누구의 결정인가?

## 목차
- §0 정책 (사용자 확인 전)
- §1 4조건
- §2 판정 표 (2026-11-10 실측)
- §3 확인하는 법 (재현 명령)
- §4 아직 못 쓰는 문법에 대비하기

---

## §0 정책 (사용자 확인 전)
status: described · 연결: claude-doctor `.claude/base/decisions/D-05-toolchain-pins.md` (제안 상태), D-01(`const`, 확정)

> 정책: 미정 — 아래는 제안이다. 사용자 확인 전에는 판정표를 보여 주고 결정을 묻는다.

- 제안 규칙: **그 코드를 읽고 고치고 돌리는 모든 도구가 그 문법을 기본값으로 받아들일 때** 쓴다. 하나라도 FFlag 를 켜야 하면 쓰지 않는다. CLI 는 `LuauExperimental*` 플래그를 스스로 켜므로(§2 아래), CLI 에서 돈다는 것만으로는 부족하다. RFC 가 병합됐고 릴리스 노트의 "experimental" 표시가 떨어졌는지도 본다.
- "모든 도구" 는 코드가 사는 곳에 따라 다르다.
  - Roblox 엔진에서 도는 코드: 4조건 전부(§1).
  - 순수 luau(CLI) 라이브러리: CLI, luau-lsp, stylua 의 3조건. 그리고 **이 라이브러리를 소비하는 저장소의 핀**도 그 문법을 받아야 한다. 0.734 핀 저장소가 소비하면 0.742 이상 문법은 못 쓴다.
- 핀과의 관계(D-05): 저장소 핀이 문법 지원 버전보다 낮으면 그 저장소에서는 못 쓴다. 문법 하나를 쓰려고 핀을 올리는 것은 그 저장소의 결정이다.
- 확정 사례: `const` 는 D-01 로 정해졌다(재대입 없는 바인딩은 `const`). 그 판단에 쓰인 근거가 이 표의 모양이다 — luau·luau-lsp·stylua·pesde 는 받고, selene·lune 은 못 받아서 그 도구를 버렸다.

## §1 4조건
status: described

| # | 조건 | 왜 필요한가 | 확인 |
|---|---|---|---|
| C1 | **luau CLI** 가 기본값으로 파싱·실행 | 실행기와 `luau-analyze` 가 같은 배포판. 검사 게이트가 문법 에러로 무너진다 | `luau x.luau`, `luau-analyze x.luau` (FFlag 없이) |
| C2 | **luau-lsp** 가 파싱·검사 | 에디터와 Roblox 정의 파일 검사. 번들 Luau 판이 CLI 보다 늦다 | `luau-lsp analyze --platform=standard x.luau` |
| C3 | **stylua** 가 파싱 | 포맷 게이트가 파싱 실패로 rc=2. 파일 전체가 포맷되지 않는다 | `stylua --syntax luau --check x.luau` |
| C4 | **Roblox Studio / 라이브 서버**가 기본값으로 켬 | 엔진은 같은 기능을 자기 FFlag 로 늦게 켠다. Studio 베타에서만 켜진 기능은 라이브 게임에서 문법 에러다 | DevForum 공지, `create.roblox.com/docs` 의 Luau 문서에 실렸는지, Studio 에서 실행(`luau-roblox` 스킬의 Studio MCP) |

- 부가 도구: lune(러너), selene(린터), pesde(게시 검증기), darklua(번들러)도 각자 파서를 갖는다. 저장소가 쓰는 것만 본다.
- `luau-analyze` 에는 `--fflags` 옵션이 없다. 그래서 FFlag 뒤에 있는 문법은 CLI 게이트로 검사할 수 없다. `luau` 실행기에는 `--fflags=` 가 있다.

## §2 판정 표 (2026-11-10 실측)
status: verified (C1–C3, 이 머신에서 실행) / described (C4: clientsettingscdn 과 DevForum, 2026-11-10) · last-confirmed: luau 0.734·0.742·0.746, luau-lsp 1.69.0·1.70.1, stylua 2.5.2·2.6.0, lune 0.10.5

| 문법 | C1 luau CLI | C2 luau-lsp | C3 stylua | C4 Roblox | 판정 |
|---|---|---|---|---|---|
| `const x = 1` | 0.734·0.742·0.746 기본(그 이전은 재지 않음). RFC `const-keyword` 병합 2026-02-24 | 1.69.0, 1.70.1 OK | 2.5.0 부터(2.5.2, 2.6.0 실측 OK) | **라이브**: `FFlagLuauConst2=True`(Studio·클라이언트, 2026-11-10 clientsettings). 2026-03 무렵 | **채택됨(D-01)**. lune 0.10.5·selene 은 못 읽음 |
| `if local x = f() then` / `if local` 식 | 0.742·0.746 에서 플래그 없이 파싱·실행(0.734 는 SyntaxError). 문장 0.737, 식 0.739, 플래그 `LuauExperimentalIfLocalSyntax` 는 0.740 부터. RFC PR #238 **열림(미병합)** | 1.70.1(번들 0.740) OK, 1.69.0 SyntaxError | **2.6.0 부터**(full-moon 3.0.0). 2.5.2 실패 | **Studio 베타만**: 2026-10-06 "[Beta] if local Statements and Expressions", Studio `FIntLuauIfLocalBetaFeatureRolloutPercent=0`(옵트인), 클라이언트에 플래그 없음 | **아직 아님** — 엔진 라이브 미반영, RFC 미병합(문법이 바뀔 수 있음). 순수 luau 라이브러리라도 1.69.0·stylua 2.5.2 핀 저장소가 막힌다 |
| `while local y = g() do` | **0.746 에서 플래그 없이 파싱**(0.745 에 실험 도입, 0.742 SyntaxError). 플래그 `LuauExperimentalWhileLocalSyntax`. RFC #238 이 2026-11-02 에 범위를 넓힘 | **1.70.1 SyntaxError**(번들 0.740) | 2.6.0 도 실패 | 없음(스태프: "in progress", if local 베타에 합류 가능) | **아직 아님** — lsp·stylua·엔진 모두 막는다 |
| `class Point … end` | **기본 꺼짐**. `Debug*` 플래그라 CLI 도 켜지 않는다. `luau --fflags=DebugLuauUserDefinedClasses=true,DebugLuauUserDefinedClassesRuntime=true` 일 때만 실행. 0.742·0.746 은 RFC 예제(`public x: number`, `Point { … }` 생성)가 돈다. 0.734 는 옛 설계(생성자 `__init`). `luau-analyze` 는 플래그를 못 켜서 SyntaxError. RFC `syntax-classes` 병합(2026-04-27), 확장판 PR #242 열림 | 1.70.1 에 `--flag:DebugLuauUserDefinedClasses=true` 를 주면 파싱은 하지만 "class keyword is illegal here" | 2.6.0 파싱 실패 | 공지·베타·플래그 없음 | **쓰지 않는다.** 대비만(§4) |

- 재현 파일: `/tmp/ups-probe/{c2,c3,k2}.luau` 와 같은 내용을 §3 에 적었다.
- 플래그 이름은 바이너리 문자열과 업스트림 소스에서 확인했다(`strings luau | grep -E 'LuauExperimental(If|While)LocalSyntax|DebugLuauUserDefinedClasses'`).
- **왜 "실험" 문법이 CLI 에서 그냥 도는가**: luau CLI 는 시작할 때 이름이 `Luau` 로 시작하는 FFlag 를 **전부 켠다**(`CLI/src/Flags.cpp` 의 `setLuauFlagsDefault`). 예외는 `ExperimentalFlags.h` 목록(타입 검사 플래그 몇 개)과 `Debug` 로 시작하는 플래그뿐이다. 그래서 릴리스 노트가 "experimental" 이라 불러도 `LuauExperimental*` 문법은 CLI 에서 켜져 있고, `DebugLuau*`(class)는 꺼져 있다. **CLI 에서 파싱된다는 사실은 안정됐다는 증거가 아니다.** 엔진은 같은 플래그를 서버 쪽 설정으로 따로 켠다.
- luau-lsp 도 기본으로 Luau 플래그를 켜고, `luau-lsp.fflags.sync`(기본 true)로 Roblox 가 공개한 `Luau*` 플래그 값을 받아 쓴다. 에디터 판정이 Roblox 플래그 값에 따라 달라질 수 있다(어느 프로필을 받는지는 미확인).
- **C4(Roblox 엔진)**: 근거와 날짜, 시차의 모양은 `roadmap-notes.md` §3 에 있다. 엔진 쪽 상태는 이 표보다 빨리 낡는다.

## §3 확인하는 법 (재현 명령)
status: verified

```bash
M=/code/.local/share/mise/installs
D=$(mktemp -d)
printf 'local function f() return 1 end\nif local x = f() then print(x) end\nlocal i = 0\nwhile local y = (i < 2 and i or nil) do i += 1; print(y) end\n' > $D/c2.luau
for v in 0.742 0.746; do $M/luau/$v/luau $D/c2.luau; $M/luau/$v/luau-analyze $D/c2.luau; done
$M/github-johnny-morganz-luau-lsp/1.70.1/luau-lsp analyze --platform=standard $D/c2.luau
$M/stylua/2.6.0/stylua --syntax luau --check $D/c2.luau; echo "stylua rc=$?"   # 2 = 파싱 실패, 1 = 파싱은 됨(포맷 차이)
# 주의: 한 파일에 문법 둘을 섞으면 하나가 실패해 다른 쪽도 실패로 보인다. 문법마다 파일을 나눈다
# class: 기본 꺼짐, 실행기에서만 플래그로 켤 수 있다
$M/luau/0.746/luau --fflags=DebugLuauUserDefinedClasses=true,DebugLuauUserDefinedClassesRuntime=true <class 예제>.luau
```

새 문법이 릴리스 노트에 보이면 이 네 줄을 그 문법으로 바꿔 표의 한 행을 채운다.

## §4 아직 못 쓰는 문법에 대비하기
status: described · 원천: 사용자 지시 표본(`sources.md` §4)

- **이름 충돌을 피한다.** `class` 가 키워드가 되면(문맥 키워드라도) 공개 API 의 `Class`, `class` 같은 이름은 혼동을 부른다. 한 저장소는 이 이유로 API 이름 후보 `Class` 를 버렸다(2026-10-16). 0.746 바이너리에는 `LuauAllowGlobalDeclarationToBeCalledClass` 라는 플래그가 있다 — `class` 라는 이름의 전역을 허용하는 호환 장치로 보인다(이름에서 추정, described).
- **설계 방향을 맞춘다.** 메소드 체이닝·`self` 타입·vtable 흉내 같은 설계는 class 가 들어오면 언어가 직접 제공할 수 있다. 지금 그런 장치를 공개 API 로 굳히기 전에 RFC 진행을 본다(`roadmap-notes.md` §2).
- **우회 문법을 쓰지 않는다.** `if local` 을 흉내 내려고 즉시 실행 함수나 `do … end` 블록으로 코드를 비트는 대신, 지금 문법(`local x = f(); if x then`)으로 쓴다. 나중에 기계적으로 바꿀 수 있다.
- **도구 쪽 신호를 본다.** stylua(full-moon)가 새 문법을 받는 릴리스가 대개 채택의 마지막 관문이다. StyLua·full-moon 릴리스 노트의 "Luau" 항목을 본다. `if local` 은 CLI 프로토타입(0.737, 2026-09-04) → Studio 베타(2026-10-06) → stylua 2.6.0(2026-10-10) 순이었다.
- **RFC 가 철회될 수 있다.** 실험 구현이 있어도 RFC 가 닫힐 수 있다: exact table(rfcs#11, 0.740 실험 → 2026-10-28 닫힘), 64비트 정수(병합 2026-02-12 → 철회 PR #269). 실험 플래그 뒤 기능에 코드를 기대지 않는 이유다.
