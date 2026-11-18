---
title: "mise 핀, shim 함정, 버전 올리기"
description: "mise shim 의 'No version is set for shim' 함정과 --help rc=0, 버전 경로 직접 호출, luau 0.734/0.742 핀 입장(미정), 버전을 올리는 절차, pesde·Rojo·symlink 링크 함정"
keywords:
  - "No version is set for shim"
  - "mise shim"
  - "mise exec"
  - "직접 호출 경로"
  - "/code/.local/share/mise/installs"
  - "버전 핀"
  - "version pin"
  - "버전 올리기"
  - "luau 업그레이드"
  - "luau-analyze 버전 확인"
  - "pesde"
  - "pesde self-upgrade"
  - "pesde 워크스페이스"
  - "Rojo 매핑"
  - "luau_packages"
  - "symlink 링크"
kind: reference
category: luau/tooling/toolchain
tags: [cli, policy]
last_verified: 2026-11-10
---
# toolchain — mise 핀, shim 함정, 버전 올리기

## 이 파일이 답하는 질문
- Q1 `luau-analyze` 를 불렀더니 "No version is set for shim" 이 나온다.
- Q2 어느 디렉터리에서든 특정 버전으로 확실히 부르려면?
- Q3 luau 버전은 무엇으로 고정하나? (정책 미정)
- Q4 luau 나 luau-lsp 를 올릴 때 무엇을 확인하나?
- Q5 pesde, Rojo, symlink 가 끼면 무엇이 깨지나?

## 목차
- §1 mise shim 함정
- §2 직접 호출 경로
- §3 버전 핀 정책 (미정)
- §4 버전을 올리는 절차
- §5 패키지 관리자와 링크 (pesde, Rojo)

---

## §1 mise shim 함정
status: verified · last-confirmed: 2026-11-10 (`<qwreey-harness 클론>` 에서 실행, `snippets/RESULTS.md`)

- PATH 의 `luau`, `luau-analyze` 는 mise shim 이다. 버전을 정하는 `mise.toml` 이 있는 프로젝트 **밖**(전역 기본 버전이 없는 곳)에서 부르면 `mise ERROR No version is set for shim: luau-analyze` 를 낸다.
- 함정: 이때 `luau-analyze --help` 의 **종료 코드가 0** 이다. "도구가 있는지" 를 `--help` 의 rc 로 판정하는 스크립트는 shim 을 정상으로 오판한다. 초안 하네스가 실제로 이 버그를 밟았다(qwreey-harness audit 05 §1).
- 다른 프로젝트의 `mise.toml` 아래에서 부르면 **그 프로젝트의 핀 버전**이 쓰인다. 같은 명령이 디렉터리에 따라 다른 luau 로 돈다.

## §2 직접 호출 경로
status: verified · last-confirmed: 2026-11-10

```
/code/.local/share/mise/installs/luau/0.734/{luau,luau-analyze,luau-ast,luau-compile}
/code/.local/share/mise/installs/luau/0.742/{luau,luau-analyze,luau-ast,luau-compile}
/code/.local/share/mise/installs/github-johnny-morganz-luau-lsp/{1.69.0,1.70.1}/luau-lsp
/code/.local/share/mise/installs/github-lune-org-lune/0.10.5/lune
/code/.local/share/mise/installs/stylua/2.5.2/stylua
```

- 또는 `mise exec luau@0.742 -- luau-analyze …` 로 버전을 명시한다.
- `luau-analyze` 에는 `--version` 이 없다. 버전은 경로로 확인한다. `luau-lsp --version` 은 있다.
- 이 저장소의 `tools/check_snippets.py` 는 shim 을 쓰지 않고 `$LUAU_BIN_DIR/<ver>` 나 `$MISE_DATA_DIR/installs/luau/<ver>` 를 직접 부른다. 다른 머신에서는 `LUAU_BIN_DIR` 이나 `MISE_DATA_DIR` 을 맞춘다.
- `lute` 는 이 머신에 설치돼 있지 않다(한 프로젝트의 mise.toml 에만 핀). 2026-11-10 현재 `luau/0.746` 도 설치돼 있지만 이 저장소의 행렬은 0.734·0.742·0.746 이고 기본 버전은 0.746 이다(최신에서 새 결함을 먼저 보려고, 2026-11-10).
- mise 로 고정한 pesde 에 `pesde self-upgrade` 를 쓰면 `~/.pesde/bin/pesde` 가 새로 생겨 PATH 순서에 따라 고정 버전을 가린다(described, 후보 X-08, `tbox/CLAUDE.md:45-48`). shim 함정(§1)과 같은 계열이다. `which -a pesde` 로 확인한다.

## §3 버전 핀 정책 (미정)
status: described · 원천: stl-luau/mise.toml 머리 주석, quad/mise.toml, tbox/mise.toml, table-sim/mise.toml, moonwave-luau/mise.toml, devplorer/mise.toml

> 정책: 미정 — decisions/ 참고

| 입장 | 저장소 | 근거 |
|---|---|---|
| luau **0.742** | stl-luau | 0.734 의 `luau-analyze` 가 병렬 검사에서 힙을 깨뜨림(상류 #3020). 올리며 새 진단 12건과 음성 대조군 배터리 변화를 기록하고 반영 |
| luau **0.734** | quad, tbox, table-sim, moonwave-luau, devplorer | 각 저장소의 타입 실측 기록이 이 빌드 기준이다. quad 는 "typing-limits 의 실측은 전부 빌드별"이라 핀 |
| luau-lsp 1.70.1 | quad, stl-luau | 1.69.0 → 1.70.1 로 올리며 새로 걸린 꼴 셋을 기록(quad 8.38) |
| luau-lsp 1.69.0 | tbox | 정의 파일과 같은 버전으로 맞춤 |

공통 원칙(양쪽 모두 동의): **버전은 반드시 고정한다.** 실행기와 검사기가 같은 배포판에서 오므로, 고정하지 않으면 진단 기준선과 음성 대조군 기대 건수가 재현되지 않는다. 0.734 와 0.742 사이에서 실제로 바뀐 칸은 luau-types 스킬의 solver-limits §3 에 있다.

## §4 버전을 올리는 절차
status: described (절차) / verified (이 저장소에서 0.734 → 0.742 행렬로 실행) · 원천: stl mise.toml 머리 주석, quad 8.38

1. 새 버전을 설치하고, 기존 버전과 **나란히** 스니펫·스파이크를 돌린다: `python3 -I tools/check_snippets.py --luau <old>,<new> snippets/*.luau`
2. `bug-present` 줄이 실패하면 고쳐진 것이다. 그 줄에 버전 조건을 달고(`[<new]`), luau-types 의 해당 절과 카탈로그를 갱신한다.
3. `expect-error` 줄이 실패하면 퇴행이거나 메시지가 바뀐 것이다. 메시지 부분 문자열을 다시 본다.
4. 프로젝트에서는 전체 게이트를 새 버전으로 돌리고, **배터리 수치(음성 대조군 건수)가 바뀌는지**를 확인한다. 바뀌었다면 그것이 곧 검사 동작이 달라졌다는 신호다.
5. 포매터(stylua)를 올릴 때는 `tools/repro-stylua-typeargs.sh <새 stylua>` 를 먼저 돌린다.
6. mise.toml 머리 주석에 무엇이 바뀌었는지 남긴다.

## §5 패키지 관리자와 링크 (pesde, Rojo)
status: verified (symlink, alias: `snippets/verify-require.sh`) / described (pesde·Rojo 세부, 2026-08~10 판) · 원천: 후보 Q-103, Q-110, Q-111, Q-112, S-126, X-08, X-10 (quad `.claude/base/project-setup-plan.md:62-92,184-246,284-318,380-391,427-434`, `.claude/audit/headless-cli-install-2026-09-21.md:78-118`; tbox `CLAUDE.md:34-70`; stl `base/architecture.md:337-341`)

- **symlink**: luau CLI(와 lute 1.0.0)의 require-by-string 은 symlink 를 따라가지 않는다. luau-lsp 는 따라간다. 그래서 pesde **워크스페이스** 링크(디렉터리 symlink) 위에서는 에디터는 깨끗하고 CLI 실행은 실패한다. CLI 테스트는 `cp -rL` 사본에서 돈다(`checkers.md` §7).
- **pesde 소비자 설치**(레지스트리 패키지)는 링커와 `.pesde/` 실체가 하드 링크된 일반 파일이고 symlink 가 0개다. symlink 는 같은 워크스페이스 멤버끼리의 링크에만 생긴다. 소비자는 `pesde install` → `require("../luau_packages/x")` → `luau` 실행으로 끝난다(described, Q-111, 2026-09-21).
- **pesde 0.7.x 함정**(described, Q-110): 패키지 이름은 `a-z0-9_` 만 된다(하이픈은 무관해 보이는 "untagged enum DependencySpecifiers" 에러). `pesde add` 는 워크스페이스 멤버를 못 찾아 `workspace=` 를 손으로 쓴다. target 이 다른 워크스페이스 의존에는 `target="luau"` 를 적는다. 멤버마다 lock 이 생긴다. 워크스페이스 dev-dep 사본은 설치 시점 스냅샷이라 새 `export type` 을 쓰려면 다시 설치한다. 0.7.4 는 중첩 워크스페이스가 안 되고 `kits/*` 글롭은 된다.
- **pesde + Rojo**(described, Q-112, Rojo 7.7.0): 인스턴스 공간에서 상대 require 가 풀리려면 rojo 트리에 패키지마다 `src` 와 `*_packages` 를 형제로 매핑한다. luau target 의존은 `luau_packages` 로 가므로 `roblox_packages` 만 매핑하는 표준 가이드 소비자는 놓친다. rojo 가 PATH 에 있으면 luau-lsp 가 `rojo sourcemap --watch` 를 스스로 띄운다.
- pesde 0.7.3 이하의 `const` 경고와 `pesde run` 패닉은 `tooling.md` §2–§3. Roblox 게시·Open Cloud·Rojo 프로젝트 구성(후보 T-51~T-53, X-07)은 roblox-net 스킬 몫이다(`platform-services.md` §10).
