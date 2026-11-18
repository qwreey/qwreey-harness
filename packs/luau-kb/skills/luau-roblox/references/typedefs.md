---
title: "Roblox 타입 정의와 sourcemap 을 luau-lsp 에 넘기기"
description: "Roblox 코드를 luau-lsp 로 검사하려면 정의 파일 globalTypes.d.luau, --platform=roblox, Rojo sourcemap 이 필요하다. 빠졌을 때의 진단, luau-kb typedefs 판, Claude Code luau-lsp 플러그인·lsp_probe 설정"
keywords:
  - "globalTypes.d.luau"
  - "정의 파일"
  - "definition file"
  - "--definitions"
  - "--platform=roblox"
  - "--sourcemap"
  - "rojo sourcemap"
  - "sourcemap.json"
  - "Unknown global 'Instance'"
  - "Unknown require: unsupported path"
  - "Key 'Lib' not found in external type 'Instance'"
  - "*error-type*"
  - "luau-analyze Roblox 검사 불가"
  - "LUAU_KB_LSP_DEFS"
  - "LUAU_KB_LSP_PLATFORM"
  - "lsp_probe"
kind: reference
category: roblox/typedefs
last_verified: 2026-11-10
last_confirmed:
  - luau-lsp 1.70.1
---
# typedefs — Roblox 타입 정의와 sourcemap 을 luau-lsp 에 넘기기

## 이 파일이 답하는 질문
- Q1 Roblox 코드를 타입 검사하려면 무엇이 필요한가?
- Q2 luau-kb 의 `typedefs/globalTypes.d.luau` 는 무엇이고 어디서 왔나?
- Q3 `--definitions` 와 `--sourcemap` 은 어떻게 넘기나? 빠지면 어떻게 되나?
- Q4 Claude Code 의 LSP 도구는 Roblox 프로젝트를 어떻게 다루나?

정의 파일을 넘긴 **결과**로 어떤 타입이 나오는지(`Instance.new`, `IsA`, `GetAttribute`, Enum, 엔진 호출)는 `api-types.md` 에 있다. 이 파일은 넘기는 **법**이다.

## 목차
- §1 왜 정의 파일이 필요한가
- §2 luau-kb typedefs
- §3 luau-lsp analyze 에 넘기기
- §4 sourcemap
- §5 LSP 세션(에디터, Claude Code, lsp_probe)

---

## §1 왜 정의 파일이 필요한가
status: verified · last-confirmed: luau-lsp 1.70.1 (이 저장소 `tools/lsp_probe.py` 실측)

- `luau-analyze` 는 정의 파일을 읽지 못한다. Roblox 전역(`game`, `Instance`, `task`, `workspace`)을 쓰는 코드는 `luau-lsp` 로만 검사할 수 있다. 정확성 게이트 규칙(사용자 결정 D-06): 순수 Luau 는 `luau-analyze`, Roblox 전역을 쓰면 `luau-lsp` + 정의 파일.
- 정의 파일 없이 `--platform=roblox` 로 돌리면 `Unknown global 'Instance'`, `'game'`, `'task'` 가 나고 `local part = Instance.new("Part")` 의 hover 는 `*error-type*` 이다. 정의 파일을 주면 `Part`, `game:GetService("Players")` 는 `Players`, `part.Touched:Connect(function(hit)…)` 의 `hit` 은 `BasePart` 로 나온다.
- 정의 파일을 넣었더라도 설정의 platform 이 `standard` 면 `part.Touched:Connect` 결과가 `any`, `hit` 이 `unknown` 으로 샜다(inlay hint 실측). Roblox 코드는 platform 도 `roblox` 로 둔다.

## §2 luau-kb typedefs
status: verified · 원천: 이 저장소 `typedefs/README.md`

- `typedefs/globalTypes.d.luau`: quad `scripts/roblox-defs/globalTypes.d.luau` 를 복사한 판(md5 `be071eac…`, 806,997 바이트, 2026-11-10 복사). devplorer, table-sim 의 사본과 같고, rbvm 캐시판과 tbox `None` 판은 다르다. 판이 다르면 같은 코드의 진단이 달라질 수 있다.
- 쓰임새: (1) `luau-lsp analyze --definitions=` 게이트, (2) 이 플러그인의 Claude Code LSP(`.lsp.json`)가 Roblox 프로젝트에서 싣는 기본 정의 파일, (3) `tools/lsp_probe.py --defs` 로 DX 확인.
- 프로젝트가 자기 정의 파일을 따로 두면(예: tbox 의 보안 수준 `None` 판) 그 프로젝트의 게이트는 그 파일을 쓴다. Claude Code LSP 에서는 `LUAU_KB_LSP_DEFS=<경로>` 로 바꾼다(§5).
- 판을 올릴 때는 `typedefs/README.md` 의 md5·날짜를 갱신하고 Roblox 코드를 검사하는 각 프로젝트의 게이트를 다시 돌린다.

## §3 luau-lsp analyze 에 넘기기
status: verified · last-confirmed: luau-lsp 1.70.1

```bash
LSP=/code/.local/share/mise/installs/github-johnny-morganz-luau-lsp/1.70.1/luau-lsp
"$LSP" analyze --platform=roblox --flag:LuauSolverV2=true \
  --definitions=<qwreey-harness 클론>/packs/luau-kb/typedefs/globalTypes.d.luau \
  --sourcemap=sourcemap.json src/
```

- `--defs` 는 `--definitions` 의 별칭이다. `--definitions=@roblox=<경로>` 처럼 이름을 붙이는 꼴도 받는다(lsp 모드에서 실측).
- `--no-strict-dm-types` 를 주면 DataModel 경로 타입을 느슨하게 본다. 기본은 엄격하다.
- 자세한 옵션, FFlag 기본값, 한도 플래그는 luau-verify `checkers.md` §2.

## §4 sourcemap
status: verified · last-confirmed: luau-lsp 1.70.1 (`/tmp` 의 최소 Rojo 구조로 실측)

- Rojo 의 `sourcemap.json` 이 있어야 `require(script.Parent.Lib)` 와 `game.ReplicatedStorage.X` 같은 DataModel 경로를 해석한다. 만드는 법: 프로젝트 루트에서 `rojo sourcemap default.project.json -o sourcemap.json`(에디터 확장은 `rojo sourcemap --watch` 를 띄운다).
- 실측: sourcemap 이 있으면 `local Lib = require(script.Parent.Lib)` 의 hover 가 `{ greet: (name: string) -> string }`, `rs.Main` 이 `ModuleScript` 였다. 없으면 `Unknown require: unsupported path`, `Key 'Lib' not found in external type 'Instance'` 가 나고 `Lib` 은 `*error-type*` 이었다.
- sourcemap 은 생성물이다. 낡으면 새로 만든 파일을 모르는 채 검사한다. 게이트에서는 검사 직전에 다시 만든다.

## §5 LSP 세션 (에디터, Claude Code, lsp_probe)
status: verified · last-confirmed: luau-lsp 1.70.1, Claude Code 2.1.316

- **Claude Code**: 별도 플러그인 luau-lsp(qwreey-harness `plugins/luau-lsp`)가 붙인다. 프로젝트 루트(`$CLAUDE_PROJECT_DIR`)에 `*.project.json` 이나 `sourcemap.json` 이 있으면 roblox 모드(정의 파일 = 그 플러그인에 동봉한 이 저장소 `typedefs/globalTypes.d.luau` 의 사본, sourcemap 사용, 자동 생성 끔)로, 없으면 standard 모드로 띄운다. `LUAU_LSP_PLATFORM=standard|roblox` 로 강제하고 `LUAU_LSP_DEFS` 로 정의 파일을 바꾼다. sourcemap 은 만들지 않으므로(rojo 를 띄우지 않는다) 프로젝트가 직접 만들어 둬야 한다. 자세한 동작은 그 플러그인의 `docs/how-it-works.md`, 검증은 luau-verify `checkers.md` §6.
- **lsp_probe**: `python3 -I tools/lsp_probe.py FILE --platform roblox --defs typedefs/globalTypes.d.luau --sourcemap sourcemap.json --root <프로젝트> --hover 'part'` 로 같은 조건의 hover·자동완성·inlay 를 한 번에 본다.
- **에디터(VS Code 확장)**: 정의 파일을 스스로 내려받고 `--no-flags-enabled` 와 동기화한 FFlag 로 서버를 띄운다. 이 저장소의 CLI·래퍼 결과와 FFlag 하나 차이로 갈릴 수 있다(luau-verify `checkers.md` §2).
