# Roblox 특화 — Studio MCP 와 luau-kb

> 한 줄: **Studio MCP** 는 Claude 가 열려 있는 Roblox Studio 를 보고 조작하게 해 주는 연결선이고, **luau-kb** 는 Luau·Roblox 지식을 담은 회사 스킬 꾸러미다.

## Studio MCP
- MCP 는 AI 가 다른 프로그램을 쓰게 해 주는 표준 연결 방식이다. Roblox Studio 에 **내장**돼 있다.
- 켜는 법(공식): Studio 에서 **Assistant → … → Manage MCP Servers → Enable Studio as MCP server** 를 켠다. Quick connect 목록에서 Claude Code 를 고를 수 있다.
  - 수동 설정 시 Windows 는 `%LOCALAPPDATA%\Roblox\mcp.bat`, macOS 는 `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP` 를 실행하는 서버로 등록한다.
  - MCP 서버 등록은 **설정 변경**이므로 동의 후에만 한다.
- 연결되면 Studio 의 MCP 설정 화면에 초록 표시가 뜬다.

### 도구는 두 종류
| 보기만 하는 것 | Studio 를 바꾸는 것 (동의 필수) |
|---|---|
| `list_roblox_studios`, `get_studio_state`, `search_game_tree`, `inspect_instance` | `execute_luau` (코드 실행) |
| `script_read`, `script_search`, `script_grep` | `multi_edit` (스크립트 수정·생성) |
| `get_console_output`, `screen_capture` | `insert_asset`, `generate_mesh`·`generate_material` 등 생성 |
| `http_get` (Roblox 문서만), `skill` | `start_stop_play`, 키보드·마우스 입력 흉내, `upload_image` |

### 주의
- Studio 가 여러 개 열려 있으면 `list_roblox_studios` 로 **어느 플레이스인지** 먼저 고른다. 다른 프로젝트의 Studio 를 빌려 쓰지 않는다.
- 바꾸는 도구는 **플레이스 저장 후**, 그리고 같은 플레이스를 동료나 다른 세션이 쓰고 있지 않을 때만.
- `start_stop_play` 는 그 Studio 를 쓰는 사람의 플레이 테스트를 끊는다.
- `execute_luau` 는 Studio 를 잠깐 멈출 수 있다. 무한 루프를 조심.
- Studio 에서 확인한 결과는 저장소 문서로 옮겨 두면 다음 세션은 Studio 없이 읽을 수 있다.

## luau-kb
- 회사 Luau·Roblox 지식 정본. 스킬 12개: 타입(luau-types), 검증, 테스트, 성능, 스타일, 런타임, Roblox 타입·mock·Studio MCP(luau-roblox), 엔진·네트워크·월드 동작, Roblox 문서 조회, 업스트림 변화.
- 설치: `claude plugin marketplace add <qwreey-harness 폴더>`(이미 있으면 생략) → Luau 저장소 `.claude/settings.json` 의 `enabledPlugins` 에 `"luau-kb@qwreey-harness": true` (사용자 동의 후).
- **Luau 저장소에서만 켜기**를 권한다. 다른 프로젝트에서는 스킬 설명이 상시 비용만 늘린다.
- 쓰는 법: Luau 질문이면 "luau-kb 스킬 먼저 봐" 라고 한 줄 붙인다. 자동 발동은 보장되지 않는다. → `skills.md`

## 역할별
- 아티스트·기획: Studio MCP 의 **보기 도구**만으로도 "이 모델 계층 구조 정리해 줘", "이 UI 에 쓰인 이미지 목록" 같은 일이 된다. 바꾸는 일은 한 번에 하나씩, 저장 후에.
- Luau 개발자: 엔진 동작이 궁금하면 luau-kb 의 roblox-* 스킬을 먼저, 거기 없으면 Studio 로 실측.
- 오래된(deprecated) Roblox API 를 Claude 가 제안할 수 있다. Roblox 공식 deprecated 목록은 "쓰지 말고, 기존 코드에서 만나면 대체 API 로 옮겨라" 라고 한다.

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- Studio 를 '바꾸는' MCP 도구를 쓰기 전에 확인할 것 두 가지는?
- luau-kb 를 모든 프로젝트에서 켜 두지 않는 이유는?

## 근거
- 공식(Roblox): create.roblox.com/docs/studio/mcp (내장 서버, 켜는 법, 도구 표, 경로, studio_id, 2026-11-10 확인)
- 공식(Roblox): create.roblox.com/docs/reference/engine/deprecated (qwreey-harness .claude/audit/19-external/05 #7)
- 사내: luau-kb `skills/luau-roblox/references/studio-mcp.md`
- 미확인: 회사 PC 에서 Studio MCP 사용 허용 여부, Team Create 플레이스에서 바꾸는 도구의 영향, Open Cloud 연동 권한
