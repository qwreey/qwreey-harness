# luau-lsp

Luau 언어 서버 [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) 를 Claude Code 에 붙이는 가벼운 플러그인이다. 켜 두면 Claude 가 `.luau` 파일을 고친 뒤 검사기가 낸 타입 오류를 직접 받아 보고, 변수의 타입이나 정의 위치를 검사기에게 물어볼 수 있다. VS Code 에서 쓰는 그 서버를 그대로 쓰므로 에디터에서 보던 빨간 줄을 Claude 도 본다. Rojo 프로젝트면 Roblox 정의 파일(플러그인에 들어 있다)로 검사한다. 서버 바이너리는 들어 있지 않아 따로 설치한다(아래 "바이너리 얻기").

Luau·Roblox 지식(타입 한계, 테스트, 성능, Roblox API)은 별도 팩 `luau-kb` 가 맡는다. 둘은 서로 없이도 동작한다.

## 무엇이 달라지나
- Claude 가 `.luau` 를 고치면 그 다음 도구 호출에 진단이 붙는다(`[Line 13:3] TypeError: ...` 꼴). 편집을 몰아서 하고 바로 끝내면 진단을 못 보고 끝나니, 고친 뒤 한 번 더 확인하라고 하면 잡는다.
- 처음 열린 파일은 원래 있던 오류도 함께 온다. 진단이 없다는 신호는 따로 오지 않는다.
- "이 변수 타입을 검사기 그대로 알려줘", "이 함수 어디서 정의됐어?" 같은 질문에 Claude 가 LSP 도구로 hover·정의 찾기를 한다.
- 프로젝트 루트에 `*.project.json` 이나 `sourcemap.json` 이 있으면 Roblox 모드(Roblox 전역, `require(ReplicatedStorage.X)` 해석), 없으면 일반 Luau 모드다.
- 서버는 첫 `.luau` 편집이나 첫 LSP 질문 때 뜬다. 파일을 읽기만 하면 뜨지 않는다.

## 비용
- 늘 드는 것: 없다(LSP 도구는 필요할 때만 불러온다).
- 진단: 오류 두 건이면 약 250자. 파일당 10건, 한 번에 30건까지.
- 메모리: 서버 하나가 일반 모드 약 12MB, Roblox 모드 약 71MB.

## 바이너리 얻기
아래 중 하나면 된다. 플러그인이 알아서 찾는다.

| 방법 | 명령 |
|---|---|
| VS Code 확장 | 이미 VS Code 에 "Luau Language Server" 확장이 있으면 그 안의 서버를 쓴다. 할 일 없음 |
| rokit | 프로젝트: `rokit add JohnnyMorganz/luau-lsp`, 전역: `rokit add --global JohnnyMorganz/luau-lsp` |
| aftman | 프로젝트: `aftman add JohnnyMorganz/luau-lsp`, 전역: `aftman add --global JohnnyMorganz/luau-lsp` |
| foreman | `foreman.toml` 에 `luau-lsp = { github = "JohnnyMorganz/luau-lsp", version = "1.70.1" }` 를 넣고 `foreman install` |
| mise | 프로젝트: `mise use github:JohnnyMorganz/luau-lsp`, 전역: `mise use -g github:JohnnyMorganz/luau-lsp` |
| 릴리스 zip | [릴리스 페이지](https://github.com/JohnnyMorganz/luau-lsp/releases)에서 `luau-lsp-win64.zip`(Windows), `luau-lsp-macos.zip`, `luau-lsp-linux-x86_64.zip`, `luau-lsp-linux-arm64.zip` 중 하나를 받아 풀고, PATH 에 있는 폴더에 넣거나 `LUAU_LSP_BIN` 에 경로를 적는다 |

찾는 순서: `LUAU_LSP_BIN` → 프로젝트에 mise 로 고정한 버전 → PATH 의 `luau-lsp`(`--version` 이 성공할 때만. 버전이 고정되지 않은 rokit·aftman·mise shim 은 건너뛴다) → rokit, aftman, foreman, mise, VS Code(Insiders, Cursor, VS Code Server 포함) 설치본 중 가장 높은 버전. 같은 버전이면 앞의 것.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install luau-lsp@qwreey-harness
```
설치한 뒤 새 세션을 연다.

## 잘 붙었는지 확인
1. 프로젝트 폴더에서 플러그인 폴더의 런처에 `--which` 를 붙여 실행한다. 쓸 바이너리와 인자가 한 줄로 나오면 된다.
   - Linux·macOS: `<플러그인 폴더>/launcher/luau-lsp --which`
   - Windows: `<플러그인 폴더>\launcher\luau-lsp.cmd --which`
   - 플러그인 폴더는 `claude plugin list` 나 `/plugin` 에서 본다. 마켓을 폴더로 추가했으면 qwreey-harness 의 `plugins/luau-lsp` 다.
2. Claude 에게 "아무 `.luau` 파일에 타입 오류를 일부러 넣었다가 고쳐 줘" 라고 한다. 대화에 `Found N new diagnostic issues` 줄이 보이면 붙은 것이다(ctrl+o 로 내용).

## Rojo 프로젝트
- `require(ReplicatedStorage.Shared.X)` 를 풀려면 `sourcemap.json` 이 있어야 한다. 플러그인은 rojo 를 띄우지 않으니 직접 만든다: `rojo sourcemap default.project.json -o sourcemap.json`.
- 세션 중에 파일을 더하거나 옮기면 sourcemap 을 다시 만들고 세션을 새로 시작한다. Claude Code 가 파일 변경 알림을 서버에 보내지 않아 서버가 새 sourcemap 을 스스로 읽지 않는 것으로 보인다.
- Roblox 코드 검사에는 `luau-analyze` 가 아니라 이 서버를 쓴다(`luau-analyze` 는 Roblox 전역을 모른다).

## 정의 파일과 문서
- 동봉한 Roblox 정의 파일은 luau-lsp 1.69.0, 1.70.1 에서 읽히는 것을 확인한 판이다.
- 서버가 VS Code 확장의 것이면, 확장이 내려받아 둔 정의 파일(`globalTypes.PluginSecurity.d.luau`)을 쓴다. 확장이 함께 갱신하므로 버전이 맞는다.
- hover 에 API 설명을 붙이는 문서 파일(`api-docs.json`)은 VS Code 확장이 받아 둔 것이 있으면 쓴다.
- 직접 바꾸려면 [정의 파일](https://luau-lsp.pages.dev/type-definitions/globalTypes.PluginSecurity.d.luau)과 [문서](https://luau-lsp.pages.dev/api-docs/en-us.json)를 받아 `LUAU_LSP_DEFS`, `LUAU_LSP_DOCS` 에 경로를 적는다. 최신 정의 파일은 오래된 luau-lsp 가 못 읽을 수 있으니 서버도 최신으로 맞춘다.

## 환경 변수
`claude` 를 띄우는 셸에서 export 하거나 `~/.claude/settings.json` 의 `env` 에 적는다.

| 변수 | 뜻 |
|---|---|
| `LUAU_LSP_BIN` | 쓸 바이너리 경로. 있으면 찾지 않는다 |
| `LUAU_LSP_PLATFORM` | `standard` 나 `roblox` 로 모드를 고정 |
| `LUAU_LSP_DEFS` | Roblox 정의 파일 경로 |
| `LUAU_LSP_DOCS` | 문서 파일 경로 |
| `LUAU_LSP_LOG` | Linux·macOS: 이 파일에 고른 바이너리와 Claude Code 가 보낸 메시지를 남긴다 |

## 조용히 실패할 때
서버가 못 뜨면 Claude 는 진단을 하나도 받지 못하고, 그것이 깨끗한 코드와 구분되지 않는다. 진단이 한 번도 오지 않거나 Claude 가 `LSP server ... crashed` 를 말하면:
1. `/plugin` 의 Errors 탭을 본다.
2. `claude --debug` 로 띄워 `.luau` 를 한 번 고치게 하고, 디버그 기록에서 `LSP SERVER` 와 `luau-lsp plugin:` 줄을 찾는다. 바이너리를 못 찾으면 `luau-lsp plugin: luau-lsp not found ...` 한 줄이 남는다.
3. 위 "잘 붙었는지 확인" 1번을 프로젝트 폴더에서 돌린다.

## Windows
- Claude Code 는 `launcher/luau-lsp` 를 PATHEXT 로 찾아 옆의 `luau-lsp.cmd` 를 띄운다. 이 파일은 PowerShell(Windows 기본 내장) 한 번으로 바이너리를 찾은 뒤 바이너리를 직접 실행한다. Git Bash 는 필요 없다.
- 실제 Windows 기기에서는 아직 확인하지 않았다. 확인해 줄 분은 아래 순서로 보고 결과를 알려 주면 된다.
  1. `cmd` 를 열고 Luau 프로젝트 폴더로 가서 `<플러그인 폴더>\launcher\luau-lsp.cmd --which` 를 실행한다. 바이너리 경로와 인자가 한 줄로 나오는지, 오류가 나는지 적는다.
  2. 그 폴더에서 `claude` 를 띄우고 `.luau` 파일에 타입 오류를 넣었다 고치게 한다. `Found N new diagnostic issues` 줄이 보이는지 본다.
  3. 안 보이면 `/plugin` Errors 탭과 `claude --debug` 의 `LSP SERVER` 줄을 복사해 둔다.
  4. 사용자 폴더 이름에 한글이 있으면 그 사실도 적는다(경로가 깨지는지 보려고).
- 안 되면 임시로: 바이너리를 PATH 에 두고(rokit, aftman, foreman, mise 의 PATH 설치나 릴리스 zip) `.lsp.json` 을 아래처럼 바꾸면 런처 없이 뜬다. 이때는 모드가 고정되므로 Roblox 프로젝트가 아니면 `args` 에서 뒤의 두 줄을 뺀다.
  ```json
  {
    "luau": {
      "command": "luau-lsp",
      "args": ["lsp", "--stdio", "--flag:LuauSolverV2=true",
               "--settings=${CLAUDE_PLUGIN_ROOT}/lsp-settings/roblox.json",
               "--definitions=@roblox=${CLAUDE_PLUGIN_ROOT}/definitions/globalTypes.d.luau"],
      "extensionToLanguage": { ".luau": "luau" },
      "startupTimeout": 30000
    }
  }
  ```
- `LUAU_LSP_LOG` 는 Windows 에서 동작하지 않는다.

## 끄기
- `claude plugin disable luau-lsp@qwreey-harness` (제거는 `uninstall`).

자세한 동작(찾는 순서의 세부, 인자, 시험): [docs/how-it-works.md](docs/how-it-works.md)
