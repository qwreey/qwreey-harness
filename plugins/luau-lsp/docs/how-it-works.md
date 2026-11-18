# luau-lsp 플러그인 동작

## 폴더
```
.claude-plugin/plugin.json   이름 luau-lsp
.lsp.json                    command = ${CLAUDE_PLUGIN_ROOT}/launcher/luau-lsp, .luau 만(.lua 는 다른 Lua 프로젝트를 건드리지 않게 뺐다)
launcher/luau-lsp            POSIX sh 런처(Linux, macOS). 확장자가 없어야 Windows 에서 PATHEXT 로 .cmd 가 잡힌다
launcher/luau-lsp.cmd        Windows 런처(CRLF). find-luau-lsp.ps1 을 한 번 부르고 바이너리를 직접 실행
launcher/find-luau-lsp.ps1   Windows 쪽 찾기와 인자 만들기(Windows PowerShell 5.1 문법)
lsp-settings/*.json          --settings 로 넘기는 기본 설정(standard, roblox)
definitions/globalTypes.d.luau  Roblox 정의 파일. 정본은 packs/luau-kb/typedefs/ 의 같은 이름 파일(출처와 md5 는 그쪽 README)
tests/                       런처 시험, 실제 서버 기동 시험
```
최상위 `bin/` 은 두지 않는다. Claude Code 는 그 폴더를 Bash PATH 에 올리고, claude.ai·Cowork 는 그 폴더가 있는 플러그인을 설치하지 않는다.

## Windows 에서 뜨는 길
Windows 판 Claude Code 는 `/` 가 든 command 를 그대로 쓰되 cross-spawn 식으로 PATHEXT 확장자를 붙여 파일을 찾고, `.exe`·`.com` 이 아니면 `cmd.exe /d /s /c` 로 감싼다. 확장자 없는 `launcher/luau-lsp` 는 PATHEXT 에 맞지 않아 건너뛰고 `luau-lsp.cmd` 가 잡힌다. `.cmd` 는:
1. `for /f` 로 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File find-luau-lsp.ps1 <NUL` 의 출력 `LLSP_BIN=...`, `LLSP_ARGS=...` 를 변수로 받는다. stdin 을 NUL 로 막아 PowerShell 이 LSP 메시지를 먹지 않게 한다.
2. `"%LLSP_BIN%" %LLSP_ARGS%` 로 바이너리를 자식으로 띄운다. stdin, stdout 은 그대로 이어진다. 그 전에 stdout 에 아무것도 쓰지 않는다(LSP 통로라서).
3. 종료는 Claude Code 가 프로세스 트리째 한다.

`.ps1` 은 경로 인자를 통째로 따옴표로 감싸(`"--settings=C:\...\standard.json"`) 공백이 든 경로를 지키고, 경로는 `GetFullPath` 로 `\` 꼴로 바꾼다.

## 바이너리 찾는 순서
sh 와 ps1 이 같은 순서다(코드의 `[find:*]` 표시, `tests/test-launcher.py` 가 비교).

| 순서 | 무엇 | sh | Windows |
|---|---|---|---|
| 1 | `LUAU_LSP_BIN` | 실행 파일이 아니면 그 자리에서 실패 | 같음 |
| 2 | 프로젝트 핀 | 프로젝트 폴더에서 `mise which luau-lsp`, 경로에 `/shims/` 가 들면 버림 | 같음(`\shims\`) |
| 3 | PATH 의 `luau-lsp` | 프로젝트 폴더에서 `--version` 이 0 으로 끝날 때만(rokit·aftman·foreman 트램펄린, mise shim 이 핀 없이 실패하는 경우를 거름) | `Get-Command luau-lsp` |
| 4 | 저장소 최고 버전 | 아래 표, `x.y.z` 폴더만, 숫자 비교, 같으면 앞의 저장소 | 같음 |
| 5 | 실패 | stderr 한 줄, exit 127 | 같음 |

| 저장소 | 경로(Windows 는 `%USERPROFILE%`, mise 는 `%LOCALAPPDATA%\mise`) |
|---|---|
| rokit | `~/.rokit/tool-storage/<owner>/luau-lsp/<ver>/luau-lsp[.exe]` |
| aftman | `~/.aftman/tool-storage/<owner>/luau-lsp/<ver>/luau-lsp[.exe]` |
| foreman | `~/.foreman/tools/<source key>-<ver>[.exe]`, key 끝이 `luau-lsp` |
| mise | `$MISE_DATA_DIR`(기본 `${XDG_DATA_HOME:-~/.local/share}/mise`)`/installs/*luau-lsp/<ver>/[bin/]luau-lsp[.exe]` |
| 에디터 확장 | `~/.vscode`, `~/.vscode-insiders`, `~/.cursor`, `~/.vscode-server` 의 `extensions/johnnymorganz.luau-lsp-<ver>[-<target>]/bin/server[.exe]` |

`--version` 과 `mise which` 는 stdin 을 `/dev/null` 로 막고 돌린다. 런처의 stdin 은 LSP 통로다.

## 인자
- 공통: `lsp --stdio --flag:LuauSolverV2=true --settings=<플러그인>/lsp-settings/<모드>.json`.
- 모드: `LUAU_LSP_PLATFORM`, 없으면 프로젝트 루트(`$CLAUDE_PROJECT_DIR`, 없으면 현재 폴더)에 `*.project.json` 이나 `sourcemap.json` 이 있으면 roblox, 아니면 standard.
- roblox: `--definitions=@roblox=<파일>`. 파일은 `LUAU_LSP_DEFS` → 바이너리가 에디터 확장의 서버면 그 에디터 globalStorage 의 `globalTypes.PluginSecurity.d.luau`(없으면 `None`) → 동봉 파일. 다른 서버에 에디터의 최신 정의를 섞지 않는 것은, 새 문법을 쓴 정의 파일을 옛 서버가 못 읽은 기록이 있어서다.
- 문서: `LUAU_LSP_DOCS` → 에디터 globalStorage 의 `api-docs.json`(roblox) 또는 `luau-api-docs.json`(standard). 없으면 넘기지 않는다.
- globalStorage 위치: Linux `${XDG_CONFIG_HOME:-~/.config}/{Code,Code - Insiders,Cursor}`, macOS `~/Library/Application Support/{...}`, Windows `%APPDATA%\{...}`, VS Code Server `~/.vscode-server/data`, 그 아래 `User/globalStorage/johnnymorganz.luau-lsp/`.
- 설정 파일: 새 솔버, sourcemap 사용(roblox), sourcemap 자동 생성 끔(rojo 를 띄우지 않는다), workspace 진단 끔(열린 파일만), inlay hint 켬.

## 시험
```bash
python3 -I plugins/luau-lsp/tests/test-launcher.py      # 가짜 바이너리·저장소로 찾는 순서와 인자. PowerShell 7 이 있으면 ps1 도 같은 경우로
LUAU_LSP_TEST_PWSH=<pwsh 경로> python3 -I plugins/luau-lsp/tests/test-launcher.py
python3 -I plugins/luau-lsp/tests/test-lsp-smoke.py     # 이 기기의 luau-lsp 로 initialize, shutdown (없으면 skip)
claude plugin validate plugins/luau-lsp
```
`.cmd` 는 Linux 에서 돌릴 수 없어 모양만 본다(CRLF, PowerShell 호출 꼴, 서버 경로 앞에 stdout 출력 없음). `.ps1` 은 pwsh 7 로 돌려 sh 와 같은 기대값을 맞추지만, Windows PowerShell 5.1 과 cmd.exe 의 실제 동작은 Windows 기기에서 봐야 한다.

## 실측
Claude Code 2.1.316 에서 잰 기동 시간, 진단이 붙는 시점, 모델이 LSP 도구를 쓰는 경우는 qwreey-harness 의 `.claude/scopes/packs/luau-kb/audit/63-luau-lsp-probe/summary.md` 에 있다.
