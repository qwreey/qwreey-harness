# 01. Claude Code 공식 권장사항 정리

- 기준일: 2026-11-10. claude-code-guide 서브에이전트가 응답으로 돌려준 보고서를 메인 세션이 저장했다.
- 확인 수준 표기
  - [확인]: 공식 페이지 원문에서 확인 (memory.md, best-practices)
  - [요약확인]: 요약 도구로 가져온 내용. 수치는 원문 재확인 권장 (skills/sub-agents/hooks/commands)
  - [추측]: 추론
  - [미확인]: 문서에서 찾지 못함
- 메인 세션 추가 확인: `/code/CLAUDE.md`, `/code/Projects/CLAUDE.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/` 모두 없음. 상위 디렉터리에서 끼어드는 지시는 없다.

## 핵심 요약

1. CLAUDE.md는 파일당 200줄 미만을 권장한다. @import는 비용을 줄이지 않는다 (가져온 파일이 함께 로드됨). [확인]
2. 조건부 로딩은 `.claude/rules/*.md`의 `paths:` frontmatter로만 된다. paths가 없는 rule은 launch 시 CLAUDE.md와 같은 우선순위로 항상 로드된다. 즉 rules로 옮기기만 하고 paths를 안 붙이면 비용은 그대로다. [확인]
3. path-scoped rule이 로드되는 시점은 Read/Write/Edit로 일치하는 파일을 다룰 때다. [확인]
4. 파일별 글자수 상한이 있다. 200K 창은 40,000자, 1M 창은 150,000자(신규 모델)이고 초과분은 앞부분만 전달된다. 측정은 `wc -m`으로 한다. [확인]
5. 프로젝트 간 공유 경로는 세 가지다.
   - (a) `~/.claude/skills/<name>` 심볼릭 링크. 중복 대상은 한 번만 로드된다. [요약확인]
   - (b) `~/.claude/rules/` + paths. 승인 대화상자 없이 로드된다. [확인]
   - (c) 플러그인 + 로컬/git 마켓플레이스. [확인]
6. 다른 디렉터리 참조 방식별 차이 [확인]
   - `--add-dir`: CLAUDE.md는 기본 미로드다 (`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` 필요). 스킬은 로드된다.
   - `additionalDirectories` 설정: 파일 접근만 열고 CLAUDE.md/rules/skills는 로드하지 않는다.
7. 스킬 목록 노출 [요약확인]
   - description과 when_to_use 합계는 1,536자에서 잘린다.
   - 목록 예산은 컨텍스트 창의 1%다.
   - SKILL.md 본문은 500줄 이하로 둔다. [확인]
8. 규칙을 강제하려면 hook을 쓴다. CLAUDE.md는 advisory다. [확인]
9. 플러그인 루트의 CLAUDE.md는 로드되지 않는다. 지식은 스킬로 넣어야 한다. 권한 규칙은 플러그인으로 배포할 수 없다. [확인]
10. 스킬 이름 예약어는 `anthropic`, `claude`다 (best-practices). 06 보고서의 플러그인명 `claude-` 접두 금지와 같은 맥락이다.

## 1. 메모리 계층 [확인] (memory.md)

- 로드 순서: managed policy → `~/.claude/CLAUDE.md` → 프로젝트 `CLAUDE.md` 또는 `.claude/CLAUDE.md` → `CLAUDE.local.md`.
- 상위 디렉터리의 CLAUDE.md는 launch 시 로드된다. 하위 디렉터리의 CLAUDE.md는 그 안의 파일을 다룰 때 로드된다.
- 블록 단위 HTML 주석은 주입 전에 제거된다.
- @import 규칙
  - 상대경로는 import하는 파일 기준으로 해석된다.
  - 최대 4홉까지 따라간다.
  - 코드블록 안의 `@경로`는 무시된다.
  - 프로젝트 파일에서 작업 디렉터리 밖을 import하면 최초 1회 승인이 필요하다. 사용자 레벨 파일은 면제된다.
- `.claude/rules/` 심볼릭 링크
  - 지원된다.
  - 대상이 작업 디렉터리 밖이면 승인이 필요하고, 승인 후에도 **paths 없는 규칙만** 로드된다.
  - 승인 없이 공유하려면 `~/.claude/rules/`를 쓰라고 공식이 안내한다.

## 2. Skills (skills.md) [요약확인]

| 필드 | 의미 |
|---|---|
| name | 슬래시 이름 (기본값은 디렉터리명) |
| description / when_to_use | 자동 호출 근거. 합계 1,536자에서 잘림 |
| argument-hint / arguments | 인자 힌트, `$name` 치환 |
| disable-model-invocation | true면 사용자 `/name` 호출 전용 |
| user-invocable | false면 `/` 메뉴에서 숨기고 Claude만 호출 |
| allowed-tools | 해당 턴에서 무확인으로 쓸 도구 |
| model, effort | 해당 턴 한정 |
| context: fork + agent | 포크 서브에이전트에서 실행 |
| hooks | 호출 시 등록 (`once: true` 가능) |
| paths | 자동 로드 범위 glob |
| shell | `!` 블록의 셸 |

- 인자 치환: `$ARGUMENTS`, `$0`, `$1`, `$name`.
- `` !`cmd` ``는 스킬 내용을 넘기기 전에 실행되어 결과로 치환된다. 실패하면 호출 전체가 중단된다.
- 우선순위: enterprise > personal > project. 플러그인 스킬은 `plugin:skill` 네임스페이스로 분리되어 충돌하지 않는다.
- `.claude/commands/x.md`와 `.claude/skills/x/SKILL.md`는 동등하다. 신규 작성은 스킬 형식을 권장한다.
- `skillOverrides` 설정 (`on`, `name-only`, `user-invocable-only`, `off`)으로 노출 수준을 조정한다. 플러그인 스킬에는 적용되지 않는다.
- 부작용이 있는 절차(배포, Studio 쓰기)는 `disable-model-invocation: true`로 둔다.

## 3. 서브에이전트 (sub-agents.md) [요약확인]

- 주요 frontmatter
  - 기본: tools, disallowedTools, model, permissionMode, maxTurns
  - 구성 요소: `skills` (전체 내용 프리로드, 최대 32개), mcpServers, hooks
  - `memory`: user / project / local 중 하나. MEMORY.md 200줄 / 25KB 한도
  - 실행: background, effort, `isolation: worktree`, initialPrompt
- 시작 시 CLAUDE.md 계층을 받는다 (Explore/Plan 제외, `omitClaudeMd`로 제외 가능). 메인 세션의 auto memory는 상속되지 않는다.
- 이 사용자에 대한 함의 (rbvm-gc-auditor 같은 감사 에이전트)
  - `memory: project`를 쓰면 학습이 누적된다.
  - `skills: [luau-types]`를 쓰면 도메인 지식을 프리로드할 수 있다.

## 4. Hooks [요약확인]

- SessionStart
  - stdout 또는 `additionalContext`가 컨텍스트로 주입된다.
  - 항목당 10,000자 상한이다.
  - matcher: startup / resume / clear / compact / fork.
  - todos 요약을 동적으로 주입하는 용도로 쓸 수 있다.
- PreToolUse
  - allow / deny / ask / defer를 지정한다. exit 2는 차단이다.
  - heavy-proc-guard 같은 가드에 쓴다.
- InstructionsLoaded
  - rules/CLAUDE.md 로드 시 실행된다. 관찰 전용이다.
  - paths 규칙의 실제 로드 시점을 검증하는 데 쓴다.
- Stop: transcript를 받아 CLAUDE.md 갱신을 제안하는 자동화에 쓸 수 있다.
- 사용자 settings의 훅은 서브에이전트에서도 발화한다.

## 5. 플러그인 / 마켓플레이스 [확인]

- 구성 디렉터리: skills/, agents/, hooks/hooks.json, .mcp.json, .lsp.json, monitors/, bin/, output-styles/, commands/ (레거시)
- 경로 환경변수: `${CLAUDE_PLUGIN_ROOT}` (버전마다 바뀜), `${CLAUDE_PLUGIN_DATA}` (업데이트 후에도 유지)
- 버전: manifest의 version을 올려야 사용자에게 갱신된다.
- 마켓플레이스 등록: `claude plugin marketplace add ./dir` 또는 `owner/repo`
- 설치: `claude plugin install name@market`
- 프로젝트 settings의 `extraKnownMarketplaces`와 `enabledPlugins`로 권장 플러그인을 지정할 수 있다.

| 공유 방법 | 적합 | 주의 |
|---|---|---|
| `~/.claude/skills` 심볼릭 링크 | 1인, 전 프로젝트 공통 | 전역 적용 |
| `~/.claude/rules/` + paths | Luau 공통 규약 | paths 필수 |
| 플러그인 + 마켓플레이스 | 버전 관리, LSP/훅 번들 | 캐시 사본이라 버전 올림 필요 |
| 프로젝트 rules 심볼릭 링크 | 선택적 공유 | 승인 필요, paths 없는 것만 로드 |
| `@~/...` import | 개인 공통 문서 | 항상 로드되어 절감 없음 |

## 6. auto memory vs CLAUDE.md [확인]

- CLAUDE.md는 사용자가 쓰는 지시다.
- auto memory는 Claude가 쓰는 학습과 교정이다. MEMORY.md 첫 200줄 / 25KB가 로드되고, 기기 로컬이다.
- 사용자 교정류는 auto memory에 맡긴다. todos 같은 사용자 상태 파일은 auto memory 대상이 아니다.

## 7. 스킬 작성 베스트 프랙티스 [확인]

출처: platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

- Claude가 모르는 것만 쓴다. 본문은 500줄 이하로 둔다.
- description은 3인칭으로, "무엇 + 언제"를 함께 적는다.
- name은 소문자와 하이픈만 쓴다. 동명사형을 권장한다. `anthropic`, `claude`는 예약어다.
- 참조 파일은 SKILL.md에서 1단계로만 연결한다. 중첩되면 일부만 읽힐 수 있다.
- 100줄 이상인 참조 파일은 상단에 목차를 둔다.
- 취약한 절차는 정확한 명령을 쓰고, 판단이 필요한 작업은 방향만 준다.
- 평가를 먼저 만든다. 시나리오 3개 이상을 Haiku, Sonnet, Opus 모두에서 테스트한다.

## 8. 진단 명령

| 명령 | 용도 |
|---|---|
| `/context all` | launch 시 실제 로드 항목과 크기 |
| `/memory` | 메모리 파일 열기, auto memory 토글 |
| `/skills` | 목록 확인. `t`로 토큰순 정렬 |
| `/skill-doctor` | 스킬별 비용과 사용 빈도, 미호출 스킬 |
| `/doctor prompt-audit [path]` | 낡은 지시, 없는 파일 참조, 상충 탐지 |
| `/status` | 길이 초과 경고 |
| `claude plugin validate <path>` | frontmatter와 플러그인 검증 |
| `claude --debug` | 파싱 오류, 예산 초과 경고 |

## 미확인

- InstructionsLoaded의 입력 스키마
- 스킬 `paths` 필드가 목록 노출에 미치는 영향
- skills/sub-agents/hooks 페이지의 원문 문구 (요약 도구 경유)

## URL

- code.claude.com/docs/en/{memory,skills,sub-agents,hooks-guide,hooks,large-codebases,features-overview,commands,settings-reference}.md
- code.claude.com/docs/en/plugins/{components,create-marketplace}.md
- platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
