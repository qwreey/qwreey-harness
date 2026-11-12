# Codex CLI·Antigravity 훅/확장 조사

> Snapshot 2026-11-12. 읽기 전용 문서 조사(WebFetch 요약 기반) + 로컬 설치 확인(codex-cli 0.166.0, agy 1.5.5). 문서 요약은 소형 모델이 만든 것이므로 인용 필드명은 실제 스키마(https://github.com/openai/codex/tree/main/codex-rs/hooks/schema/generated)로 한 번 더 확인할 것. "미확인"은 문서에 없거나 실행해 보지 않은 것.

출처 약어: [CH]=https://learn.chatgpt.com/docs/hooks, [CA]=https://learn.chatgpt.com/docs/agent-configuration/agents-md, [CM]=https://learn.chatgpt.com/docs/extend/mcp?surface=cli, [CP]=https://developers.openai.com/plugins/build/plugins, [AH]=https://antigravity.google/docs/hooks/, [AR]=https://antigravity.google/docs/rules/, [AM]=https://antigravity.google/docs/mcp/, [AP]=https://antigravity.google/docs/build-plugins/

## 1. Codex CLI

**이벤트와 입력 필드** [CH "Hooks" 이벤트 표, "Common input fields"]
- 이벤트: SessionStart(source: startup/resume/clear/compact/fork), SessionEnd, SubagentStart, PreToolUse, PermissionRequest, PostToolUse, PreModelRequest/PostModelRequest, PreCompact/PostCompact(trigger: manual/auto), UserPromptSubmit, SubagentStop, Stop, Interrupt.
- 공통 입력: session_id, transcript_path, cwd, hook_event_name, model (+ turn_id, permission_mode).
- 파일 경로 전용 필드는 없다. 읽기/편집 전용 이벤트도 없고 PreToolUse/PostToolUse 의 `tool_name`, `tool_input`(Bash 는 `tool_input.command`, apply_patch 는 패치 본문) 에서 경로를 파싱해야 한다. [CH "Tool coverage"/입력 절]. Codex 는 파일 읽기를 대개 셸(cat/sed)로 하므로 경로 추출은 명령 문자열 파싱이 된다(추정, 미확인).
- MCP 도구도 matcher 로 훅 가능 [CH "MCP tool hooks"].

**컨텍스트 주입** [CH "Common output fields", "Large hook output"]
- `hookSpecificOutput.additionalContext` 가능: SessionStart, SubagentStart, PreToolUse, PostToolUse, UserPromptSubmit. 평문 stdout 은 SessionStart/SubagentStart/UserPromptSubmit 에서만 developer 컨텍스트로 들어가고 PreToolUse/PostToolUse 에서는 무시됨.
- 크기: 훅 출력당 기본 약 2,500 토큰, 초과분은 `<temp>/hook_outputs/<session>/<uuid>.txt` 로 넘치고 머리·꼬리 미리보기만 보임. 핸들러별 `additionalContextLimit`(양의 정수, 0=무제한).
- 차단: PreToolUse `permissionDecision: "deny"`(또는 exit 2), `updatedInput` 으로 입력 재작성, PermissionRequest deny, UserPromptSubmit/Stop `decision: "block"`, PreCompact `continue:false`. PostToolUse 는 이미 실행된 명령을 되돌리지 못함. 문서가 "guardrail, not a complete enforcement boundary" 라고 명시.

**훅 없는 경로 범위 지정** [CA]
- AGENTS.md 를 루트에서 현재 작업 디렉터리까지 걸으며 디렉터리당 1개(AGENTS.override.md > AGENTS.md > fallback 이름) 연결, 합계 `project_doc_max_bytes` 기본 32 KiB. 체인은 시작 시 한 번 만든다. glob 규칙 없음. 하위 디렉터리 파일은 그 디렉터리에서 시작해야 로드(세션 중 동적 로드는 문서에 없음).

**MCP** [CM]
- stdio 와 streamable HTTP(bearer, OAuth). 설정 `~/.codex/config.toml`, 신뢰된 프로젝트의 `.codex/config.toml`. 로컬 `codex mcp add --url` / `-- <cmd>` 확인.
- 서버 `instructions`(initialize 응답) 를 서버 전체 지침으로 읽음(앞 512자를 자립적으로 쓰라는 권고). 서버 프롬프트 지원 여부와 tool list changed 처리는 문서에 없음. `codex features list` 에 `mcp_tool_list_changed`, `mcp_connection_sharing` 이 "under development, false" 로 존재(로컬 확인): 세션 간 연결 공유는 아직 기본 기능이 아님. 여러 세션이 한 HTTP 서버를 공유하는 것은 프로토콜상 가능(추정, 미확인).

**압축 재무장** [CH "PreCompact/PostCompact", 압축 절]
- 루트 세션 압축 뒤 `source:"compact"` SessionStart 훅이 다음 모델 요청 전에 실행(자동 압축 중간 턴 포함). 즉 SessionStart 의 additionalContext 로 규칙을 다시 심을 수 있다.

**패키징** [CH "Plugin-bundled hooks", CP "Hooks", "Install scope"]
- 플러그인: 루트 `plugin.json`(+ `.codex-plugin/plugin.json` 호환층), `skills/`, `mcp.json`, `hooks/hooks.json`. 훅은 `PLUGIN_ROOT`/`PLUGIN_DATA` (Claude 호환으로 `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` 도) 를 받음.
- 사용자 `~/.agents/plugins/marketplace.json`, 저장소 `$REPO/.agents/plugins/marketplace.json`; 프로젝트별 활성화는 `.codex/config.toml` 의 `[plugins."name@marketplace"]`.
- 주의: 훅은 신뢰 검토(`/hooks`)가 필요하고 스크립트 변경 시 재검토. CP 는 "훅은 데스크톱 앱에서 수동 설치한 플러그인만 지원"이라 하나 CLI 와의 관계는 불명. 로컬 `codex features list` 는 `plugin_hooks` removed, `hooks` stable. 훅은 `.codex/hooks.json`, `~/.codex/hooks.json` 으로도 둠 [CH "Where Codex looks for hooks"]. `--dangerously-bypass-hook-trust` 는 자동화용.

## 2. Antigravity (agy)

**이벤트와 입력** [AH "Supported events", "Common input fields"]
- SessionStart(첫 모델 호출 전 한 번), PreToolUse, PostToolUse, PreInvocation, PostInvocation, Stop. 압축 이벤트 없음(문서에 없음).
- 입력(camelCase): conversationId, workspacePaths, transcriptPath, artifactDirectoryPath, modelName, lastUserInput. 도구 이벤트는 `toolCall{name,args}`, `stepIdx`. 경로는 args 안(`view_file.AbsolutePath`, `write_to_file.TargetFile`, `replace_file_content.TargetFile`) 이라 읽기/편집 경로를 구조적으로 얻는다. Codex 보다 유리.
- 사용자 프롬프트 제출 이벤트는 없고 `lastUserInput` 필드로 PreInvocation 에서 대체(추정).

**주입** [AH "Output"]
- `injectSteps`(systemMessage/userMessage/ephemeralMessage/errorMessage) 는 SessionStart, PreInvocation, PostInvocation 에서만. PostToolUse 출력은 `{}` 라 도구 직후 주입 불가. 크기 제한은 문서에 없음. 차단: PreToolUse `decision: deny/ask/...`, `overwrite` 로 args 재작성, PreInvocation `terminationBehavior`, Stop `continue`.
- 훅 설정: `.agents/hooks.json`, `~/.gemini/config/hooks.json`, 플러그인의 `hooks.json`. 타임아웃 기본 30초, command 타입만.

**경로 범위 지정** [AR]
- `.agents/rules/*.md` 의 frontmatter `trigger: glob` + `globs` 로 해당 파일을 다룰 때 활성화(훅 없이). `always_on`, `model_decision`, `manual`(CLI 미지원). AGENTS.md/GEMINI.md 는 작업공간과 상위(레포 루트까지)만 로드, 하위 폴더는 불로드. 규칙 파일당 24,000 바이트, 전역·always_on 합계 20,000 토큰.

**MCP** [AM]
- stdio, streamable HTTP(`serverUrl`). 레거시 SSE 불가(SDK 는 SSE 허용). 설정 `~/.gemini/config/mcp_config.json`, `<workspace>/.agents/mcp_config.json`, 플러그인 `mcp_config.json`. 서버 instructions 를 `instructions.md` 로 캐시한다고 언급(동작 세부 미확인). 로컬 `agy mcp add/list/enable` 확인.

**압축 재무장**: 훅 이벤트 없음. `trigger: always_on` 규칙은 매 턴 주입되므로 재무장 문제가 없음 [AR].

**패키징** [AP]: `plugin.json`, `skills/`, `mcp_config.json`, `agents/`, `rules/`(trigger 포함), `hooks.json`. `agy plugin install|import|validate`; `agy plugin import` 가 gemini 또는 claude 에서 가져옴(로컬 `agy plugin --help`). 설치 위치 `~/.gemini/config/plugins/<name>`(사용자 단위). 프로젝트 단위 활성화 방법은 AP 에 없음(미확인, Plugins 가이드 필요).

## 3. 비교표

| 능력 | Claude Code | Codex | agy |
|---|---|---|---|
| 도구 후 additionalContext | 예(PostToolUse) | 예(PostToolUse, 기본 약 2.5k토큰/훅, 조절 가능) | 아니오(PostToolUse 는 `{}`) |
| 도구 전 주입/차단 | 예 | 예(deny, updatedInput) | 차단·args 재작성만, 주입은 PreInvocation |
| 프롬프트 제출 훅 | UserPromptSubmit | UserPromptSubmit | 없음(PreInvocation + lastUserInput) |
| 파일 경로 입력 | tool_input.file_path | 전용 필드 없음, tool_input 파싱 | toolCall.args(AbsolutePath/TargetFile) |
| SessionStart | 예 | 예(source 에 compact 포함) | 예(injectSteps) |
| SubagentStart | 예 | 예 | 문서에 없음 |
| 압축 이벤트 | PreCompact/PostCompact | PreCompact/PostCompact + SessionStart(compact) | 없음 |
| 경로 범위 규칙 파일 | paths frontmatter 규칙 | 없음(디렉터리별 AGENTS.md, 시작 시 고정) | `trigger: glob` 규칙 |
| 플러그인 번들 | 예(enabledPlugins 프로젝트별) | 예(config.toml `[plugins]`, 훅 신뢰 검토) | 예(사용자 단위 확인, 프로젝트 단위 미확인) |
| MCP stdio / HTTP | 예 / 예 | 예 / 예(streamable) | 예 / 예(streamable, SSE 불가) |
| MCP 서버 instructions | 예 | 예 | 부분(캐시 언급) |
| 세션 간 서버 공유 | HTTP 로 가능 | HTTP 로 가능(추정), 연결 공유는 개발 중 | HTTP 로 가능(추정) |

## 4. 단일 coderag 어댑터 설계 함의

공통 분모는 "경로 하나를 받아 짧은 텍스트를 돌려주는 CLI" 이므로, coderag 는 하네스 중립 핵심(`coderag hook --harness claude|codex|agy`, 표준입력 JSON 을 받아 경로 후보를 추출하고 출력 형식만 하네스별로 변환) 하나와 얇은 번역층을 두는 것이 자연스럽다. Claude 는 PostToolUse 와 PreCompact 후속 SessionStart, Codex 는 PostToolUse additionalContext 와 `source:compact` SessionStart(경로는 `tool_input.command` 에서 정규식/파서로 추출해야 하므로 정확도가 낮고, 2.5k토큰 상한 때문에 요약형 출력 필요), agy 는 PostToolUse 주입이 불가하므로 PreToolUse 에서 막는 방식 대신 `.agents/rules` 의 `trigger: glob` 규칙 파일을 coderag 가 생성하거나(정적, 압축에 안전), PreInvocation 의 injectSteps 로 직전 단계 경로를 모아 주입하는 방식이 현실적이다. 규칙 정본은 한 곳(coderag 인덱스)에 두고 하네스별 산출물(Claude paths rules, agy glob rules, Codex 는 계층 AGENTS.md 또는 훅 출력)을 생성하는 편이 낫다. MCP 는 세 하네스 모두 streamable HTTP 를 지원하므로 상주 서버 하나를 공유하는 설계가 가능하나, Codex 의 `instructions` 필드는 서버 전체 지침일 뿐 경로별 주입 수단이 아니고 Codex 훅은 신뢰 검토가 붙으므로 설치 안내(HUMAN_TODO)가 필요하다. 우선순위는 Codex 어댑터(Claude 훅 구조와 거의 1:1, CLAUDE_PLUGIN_ROOT 호환 변수까지 있어 플러그인 재사용 여지) 이고 agy 는 glob 규칙 생성기로 최소 대응이 합리적이다.

## 5. 열린 불확실성

- Codex 가 파일을 읽을 때 어떤 도구로 읽는지(셸 cat 인지 전용 read 도구인지)와 PostToolUse matcher 가 어떤 tool_name 을 주는지: 실측 필요.
- Codex CLI 에서 플러그인 번들 훅이 실제로 동작하는지(CP 는 데스크톱 앱 수동 설치만 지원한다고 했고 로컬 `plugin_hooks` 플래그는 removed): 실측 필요. 프로젝트 `.codex/hooks.json` 직접 배치는 [CH] 에 문서화됨.
- additionalContext 가 압축 뒤에도 남는지(Codex 는 SessionStart compact 로 재주입 가능하나, PostToolUse 주입분의 압축 생존은 미확인).
- agy: 훅 injectSteps 크기 제한, 플러그인의 프로젝트 단위 활성화, `rules/` glob 이 "작업 중인 파일" 을 읽기로도 판정하는지, MCP 서버 instructions 의 모델 전달 방식.
- Codex/agy MCP 의 세션 간 공유 및 서버 프롬프트 지원, tool list changed 처리.
- 이 문서의 하네스 문서 요약은 WebFetch 소형 모델 추출이므로 원문 스키마와의 대조가 안 된 상태.
