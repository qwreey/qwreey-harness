---
format: 1
title: 63. luau-lsp 를 Claude Code 플러그인 LSP 로 실측
description: 플러그인 LSP 는 동작함(서버는 첫 Edit/Write·LSP 호출에 뜨고 init 15-22ms, hover 1-5ms, Roblox 정의 첫 요청 519ms); 진단은 편집 다음 도구 호출에 붙어 한 박자 늦게 오므로 편집 뒤 바로 끝내면 못 보고, 이어서 일하면 off 에서 놓친 깨짐을 잡음(2/2 대 0/1); LSP 도구는 deferred 라 "검사기 그대로" 류 질문에서만 씀(hover 2/2, 정의 찾기는 Grep 2/2); 현재 .sh 래퍼는 Windows 에서 못 뜨고, 분리 플러그인은 확장자 없는 sh + 같은 이름 .cmd 런처(Windows 1회 확인 필요)나 PATH 의 luau-lsp 직접 호출로 간다
---
# 63. luau-lsp 를 Claude Code 플러그인 LSP 로 실측

> Snapshot 2026-11-17. May differ from now; check current files and git log before relying on it.

사용자: "실측부터 진행해줘. windows 도 가능한 구조에, luau-lsp 로 나누자. 좀더 가벼운 기능으로써 readme 에 바이너리를 두는 방법이나 사용하는 방법을 어느정도 두는게 맞아보여. 일단 실측부터"(패널 D14). 서브에이전트(opus)가 재고 메인이 이 기록을 썼다. 원자료 `/tmp/lspprobe/`(커밋 안 함).

## 설정
- Claude Code 2.1.316, `claude -p --model sonnet`, 실행마다 새 `CLAUDE_CONFIG_DIR`(자격 파일만 복사, 끝나고 삭제), `--strict-mcp-config`, `--debug-file`.
- 플러그인: `packs/luau-kb` 에서 `.lsp.json`, `tools/luau-lsp.sh`, `tools/lsp/settings-*.json`, `typedefs/globalTypes.d.luau` 만 복사한 최소 플러그인을 `--plugin-dir` 로(스킬, rules 간섭 없음). luau-lsp 1.70.1(mise 설치 경로).
- 픽스처: (a) standard, `--!strict` 두 파일, Main 에 기존 오류 2개(줄5 number 를 string 에, 줄13 미정의 전역 `totl`). (b) Rojo, `default.project.json` + `rojo sourcemap` 으로 만든 `sourcemap.json`, `require(ReplicatedStorage.Shared.Scores)`, 줄6 `local count: string = #Players:GetPlayers()`.
- 과제: T1 편집(Item.count 를 optional 로; 순차형, 일괄형 두 문구), T1R Rojo leaderstats 추가 후 "check your work", T2 "줄4 items 의 타입을 검사기 그대로", T3 bonusFor 정의 위치. 비교로 플러그인 끔. 추가로 래퍼 없이 `command: "luau-lsp"`(PATH 에 실바이너리 / mise shim 만) 두 판.
- 18회, 합계 USD 0.98(회당 0.04-0.06). Windows 는 2.1.316 win32-x64 `claude.exe` 를 내려받아 문자열만 읽음(실행 안 함).

## 결과
- 기동: 서버는 첫 `.luau` Edit/Write 또는 첫 LSP 도구 호출에 뜬다(Read 로는 안 뜸). initialize 15-22ms, hover 1-5ms, Roblox 첫 정의 요청 519ms(807KB 정의 파일 로드). 상주 메모리 standard 약 12MB, roblox 약 71MB. 네트워크 내려받기 없음(바이너리에 정의 URL 없음, 정의 파일은 플러그인이 실어야 함).
- 진단 모양: 첨부 `{"type":"diagnostics","files":[...],"isNew":true}`, 모델에게는 `<new-diagnostics>The following new diagnostic issues were detected:` 아래 파일 이름과 `[Line 13:3] TypeError: Operator '+' could not be applied to operands of types number and number?; ... [1039] (Luau)` 꼴. 파일당 10, 합계 30, 본문 4000자 상한, 이미 준 것은 다시 안 줌. 2건이면 약 250자.
- 진단 시점: 서버는 도구 결과 뒤 5-30ms 에 publish 하고 Claude Code 는 그 전에 첨부를 확인하므로 다음 도구 호출에 붙는다. 편집을 한 번에 몰아 하고 바로 끝내면 못 본다(일괄형 3회 모두). 같은 파일을 다시 고치면 대기 중 진단은 지우고 새로 받는다. 빈 진단은 건너뛰어 "깨끗함" 신호는 없다.
- "new" 의 뜻: 처음 열린 파일은 기존 오류도 전부 new 로 온다(읽기 전용 hover 에도). 모듈을 바꾸면 열지 않은 의존 파일 진단도 온다.
- T1 순차형: on 은 다음 호출에서 진단을 받고 `sum += it.count or 0` 로 고침(2/2), off 는 Util.total 을 깨진 채 두고 "아무것도 안 깨짐"(1/1). 일괄형: on, off 모두 읽고 미리 고침(4/4), 진단은 못 봄.
- T1R: Roblox 정의로 새 코드 오탐 없음, require 는 sourcemap 으로 풀림. 기존 줄6 오류가 왔지만 최종 답에서 언급 안 함(0/2). on 도 `luau-analyze` 를 돌려 mise shim 오류와 "Unknown require" 잡음을 얻음(2/2); off 는 검사 못 했다고 답함.
- T2: on 은 ToolSearch 로 LSP 를 불러 hover, 서버 답 `local items: {{ count: number, name: string }}` 를 인용하고 파일의 기존 오류도 보고(2/2). off 는 읽어서 `{ Util.Item }` 로 추론.
- T3: 정의 찾기는 Grep(2/2). 지시하면 goToDefinition 이 `Defined in src/shared/Scores.luau:4:17`(sourcemap 경유 교차 파일), hover `local Players: Players`.
- 실패: PATH 에 mise shim 만 있으면 "No version is set" 으로 exit 1. 모델은 `Error performing hover: LSP server ... crashed with exit code 1` 만 보고, 원인은 `--debug` 의 `[LSP SERVER ...]` 줄에만 남는다. 편집마다 재시작을 시도하고 진단은 오지 않아 깨끗한 코드와 구분이 안 된다.
- 클라이언트 능력: `workspace.configuration`, `didChangeWatchedFiles` 가 false 라 luau-lsp 가 sourcemap 자동 갱신을 끈다(세션 중 파일 추가는 재시작 전까지 안 풀릴 것으로 추정, 미검증).

## Windows
- Windows 판 claude.exe: 이름만 준 command 는 PATH 에서 찾고(현재 디렉터리 제외), `/` 가 든 경로는 그대로 쓴다. 그 뒤 cross-spawn Windows 처리: PATHEXT 로 파일을 찾고 shebang 을 읽고, .exe, .com 이 아니면 `cmd.exe /d /s /c` 로 감싼다. 종료는 프로세스 트리째.
- 그래서 `.sh` 래퍼(현재)는 PATHEXT 에 없어 못 뜬다. `.py` 는 shebang 이 `python3` 가 되어 스토어 스텁이나 미설치에 걸린다. `command: "luau-lsp"` 는 `luau-lsp.exe` 나 rokit, aftman, foreman 의 .exe 트램펄린, mise exe shim(2026.2.7 부터 기본)으로 된다. 확장자 없는 `launcher/luau-lsp`(sh) 옆에 `luau-lsp.cmd` 를 두면 PATHEXT 로 .cmd 가 잡혀 cmd.exe 로 뜰 것으로 읽힘(npm .cmd 언어 서버와 같은 길, 실기기 확인 필요).
- 배포: luau-lsp 1.70.1 릴리스 자산 `luau-lsp-win64.zip`, `luau-lsp-macos.zip`, `luau-lsp-linux-x86_64.zip`, `luau-lsp-linux-arm64.zip`. rokit 은 `~/.rokit/bin/luau-lsp.exe`(트램펄린)와 `~/.rokit/tool-storage/johnnymorganz/luau-lsp/<ver>/luau-lsp.exe`, aftman.toml, foreman.toml 도 읽음. aftman 은 `~/.aftman/bin` 과 `~/.aftman/tool-storage/<scope>/luau-lsp/<ver>/`. foreman 은 `~/.foreman/bin` 과 `~/.foreman/tools/<key>-<ver>.exe`(key 형식 미확인). VS Code 확장은 `~/.vscode/extensions/johnnymorganz.luau-lsp-<ver>-<platform>/bin/server(.exe)`, 정의와 api-docs 는 globalStorage `johnnymorganz.luau-lsp/`.
- LSP 프로세스 cwd 는 프로젝트라 트램펄린이 프로젝트 핀을 따른다. 최상위 `bin/` 이름은 claude.ai, Cowork 설치를 막으므로 런처 폴더는 다른 이름.

## 권고
- 분리 플러그인 `luau-lsp`: `command` = `${CLAUDE_PLUGIN_ROOT}/launcher/luau-lsp`, POSIX sh 와 같은 이름 `.cmd`(탐색은 PowerShell 한 번, 실행은 바이너리 직접). Windows 실기기 1회 확인 전까지 대안은 `command: "luau-lsp"` + 고정 args(roblox 플랫폼, 동봉 정의)와 README 의 PATH 요구.
- 바이너리 찾는 순서: `LUAU_LSP_BIN` > 프로젝트 핀(`mise which`, shim 제외) > PATH 의 `luau-lsp`(`--version` 성공할 때만) > 저장소 최고 버전(rokit tool-storage, aftman tool-storage, foreman tools, mise installs, VS Code 확장 `bin/server`) > stderr 한 줄 안내 후 실패.
- 설정은 지금 것을 유지(`*.project.json`, `sourcemap.json` 이면 roblox, 새 솔버, sourcemap 자동 생성 끔, workspace 진단 끔). 정의 파일은 동봉하고 환경 변수로 바꿀 수 있게, VS Code 의 정의와 `--docs` 를 쓸 수 있으면 hover 문서까지.
- README: 바이너리 얻는 법(릴리스 zip, rokit, aftman, foreman, mise 한 줄씩, VS Code 확장 재사용), 확인법(`.luau` 편집 뒤 진단이나 hover), Rojo 는 `rojo sourcemap -o sourcemap.json` 과 파일 추가 뒤 재시작, 조용히 실패하면 `/plugin` Errors, `claude --debug`, 정의 파일 갱신법.
- 규칙 후보(미검증): ".luau 편집 뒤 끝내기 전에 도구를 한 번 더 부르거나 hover 로 확인; 진단이 없으면 깨끗한 것; Roblox 코드에 luau-analyze 를 돌리지 않는다".

## 한계
- 셀당 1-2회, Sonnet 만, `-p` 만. 대화형에서 진단이 다음 사용자 턴에 붙는지는 확인 안 함.
- Windows 는 바이너리 코드 읽기로만 판단, 실행 안 함. foreman 저장 이름, mise Windows 설치 경로는 문서와 소스로만 봄.
- sourcemap 이 세션 중 낡는 문제는 경고문에서 추정, 실측 안 함.
- 교차 파일 깨짐(의존 파일에 새로 생긴 오류)이 진단으로 오는지는 publish 기록만 확인, 그 경우의 모델 반응은 안 봄.
