---
format: 1
title: luau-lsp 를 지식 팩과 따로 떼어 얇은 플러그인으로 둘까?
description: luau-lsp 를 지식 팩과 따로 떼어 얇은 플러그인으로 둘까? 답 실측부터 진행해줘. windows 도 가능한 구조에, luau-lsp 로 나누자. 좀더 가벼운 기능으로써 readme 에 바이너리를 두는...
status: archived; answered 실측부터 진행해줘. windows 도 가능한 구조에, luau-lsp 로 나누자. 좀더 가벼운 기능으로써 readme 에 바이너리를 두는...
id: Q14
urgency: later
blocks: LSP 만 원하는 저장소·동료 배포
recommended: b
created: 2026-11-17T00:14:36.731Z
answered: 2026-11-17T00:15:44.123Z
answer: 실측부터 진행해줘. windows 도 가능한 구조에, luau-lsp 로 나누자. 좀더 가벼운 기능으로써 readme 에 바이너리를 두는 방법이나 사용하는 방법을 어느정도 두는게 맞아보여. 일단 실측부터
---

# Q14. luau-lsp 를 지식 팩과 따로 떼어 얇은 플러그인으로 둘까?

## 맥락

**사용자 질문:** 표준 LSP 면 `lspServers` 몇 줄로 플러그인에 붙일 수 있는데 luau-lsp 도 되나, 기본 플러그인이 없으니 우리 쪽에 넣어야 하지 않나.

**확인한 것**
- luau-lsp 는 `lsp --stdio` 로 뜨는 표준 LSP 다.
- 이미 붙어 있다: `packs/luau-kb/.lsp.json` 이 래퍼 `tools/luau-lsp.sh` 를 부른다. 래퍼는 mise 설치본에서 바이너리를 고르고(shim 회피), Rojo 프로젝트면 roblox 정의와 sourcemap 을, `LuauSolverV2` 와 설정 파일을 넘긴다.
- 공식 마켓에는 luau 플러그인이 없다(lua-lsp 는 `.lua` 만).

**왜 안 보였나:** luau-kb 는 기본 꺼짐 팩이라 Luau 저장소가 `coderag.toml` 에 팩을 적고 `coderag adapt` 를 해야 켜진다. claude-doctor 에서는 꺼져 있다.

**걸리는 점**
- LSP 만 원하는 저장소도 지식 팩(스킬 12개, rule)을 통째로 켜야 한다.
- 래퍼가 POSIX sh 라 Windows 동료 환경에서는 안 돈다.
- 실제 세션에서 진단을 돌려주는지 실측한 적이 없다.

**제안:** `plugins/luau-lsp`(래퍼와 .lsp.json 만)를 따로 두고 팩은 그것을 의존하거나 안내. Windows 용 래퍼(Python 이나 .cmd)와 실측 한 번.

## 선택지

- a) 따로 떼고 실측
  LSP 만 켜기, Windows 대응
- b) 팩에 두고 실측만
  지금 구조로 충분한지 먼저
- c) 그대로

**권장 b) 팩에 두고 실측만**
먼저 실제 세션에서 진단이 쓸모 있게 오는지 봐야 떼어 낼 가치가 정해진다. Windows 래퍼는 동료 배포 전에 필요하다.

## 답

실측부터 진행해줘. windows 도 가능한 구조에, luau-lsp 로 나누자. 좀더 가벼운 기능으로써 readme 에 바이너리를 두는 방법이나 사용하는 방법을 어느정도 두는게 맞아보여. 일단 실측부터
