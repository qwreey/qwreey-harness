# audit/32 플러그인이 상시 맥락을 실을 수 있는가

조사일 2026-11-11, Claude Code 2.1.316. 문서는 /tmp/ccdocs 와 code.claude.com(output-styles) 기준. 실험은 /tmp/ambient (플러그인 `--plugin-dir`, sonnet, `-p`).

## 결론
플러그인 루트 CLAUDE.md 는 로드되지 않는다(문서가 명시, 실험 확인). 플러그인 `rules/` 도 마찬가지다. 상시로 실리는 경로는 셋이다: output style(시스템 프롬프트), MCP server `instructions`(시스템 프롬프트의 "MCP Server Instructions"), SessionStart `additionalContext`(system reminder). 이 중 사용자 CLAUDE.md 와 같은 층에 섞이지 않고 출처가 붙는 것은 앞의 둘이다.

## 구성 요소 전체 (plugins-reference.md 디렉터리 표)
skills, commands, agents, hooks, monitors, output-styles, themes, workflows, bin, settings.json, .mcp.json, .lsp.json. 루트 CLAUDE.md 는 "isn't loaded as context, `claude plugin validate` warns" (plugins-reference.md:665). rules 디렉터리는 목록에 없다. 플러그인 `settings.json` 은 `agent` 와 `subagentStatusLine` 만 적용되고 나머지 키는 버려진다(그래서 `outputStyle`, `claudeMd`, `permissions` 도 못 싣는다. `claudeMd` 는 어차피 managed 전용).

## 방식별 표
| 방식 | 상시 | 끄면 | CLAUDE.md 와의 관계 | 출처 | 제한·비용 | 프로젝트별 |
|---|---|---|---|---|---|---|
| 플러그인 CLAUDE.md | 아니오(로드 안 됨) | - | - | - | - | - |
| 플러그인 rules/ | 아니오(실험: 토큰 안 보임) | - | - | - | - | - |
| output style (`force-for-plugin: true`) | 예. 매 요청 시스템 프롬프트에 포함. 실험: resume·compact 뒤에도 있음 | 사라짐 | 병합이 아니라 별도 섹션 "Output Style: <plugin>:<name>". 사용자 outputStyle 설정을 덮어쓴다. 켜진 플러그인 여럿이 force 하면 첫 번째만 | 모델: 섹션 제목에 plugin:name. 사용자: /output-style 에 보임 | 크기 제한 문서에 없음. 캐시는 시스템 프롬프트라 안정적이면 싸다. 단 `keep-coding-instructions` 를 true 로 안 두면 코딩 지침이 빠진다. 스타일은 한 번에 하나라 사용자 자신의 스타일과 충돌 | 플러그인 enabled 범위(user/project/local)를 따른다 |
| MCP `instructions` (플러그인 .mcp.json) | 예. 실험: 시스템 프롬프트 "MCP Server Instructions" 에 `plugin:amb:amb` 항목으로 실림. compact 뒤에도 유지 | 서버가 사라지므로 사라짐 | 병합. CLAUDE.md 와 별도 섹션에 공존 | 모델: 서버 이름이 붙음. 사용자: /mcp 에 서버 | 문서에는 상한 언급 없음(내가 못 찾음. 일부 버전은 2KB 로 자른다는 보고가 있으나 미확인). 서버 프로세스가 상주하는 비용. tool search 가 켜져 있어도 instructions 는 상시 | 플러그인 enabled 범위 |
| SessionStart additionalContext | 예. startup·resume·clear·compact 마다 재실행. 실험: compact 뒤에도 보임 | 훅이 안 돌아 사라짐 | 병합. system reminder 로 대화 앞에 들어감 | 모델: reminder 에 훅 이름이 붙음. 사용자: 안 보임(기록에 항목 없음) | 10,000자 상한. 대화 메시지 쪽이라 시스템 프롬프트 캐시와 무관하지만 매 세션 토큰 소모. 명령문 말투는 프롬프트 인젝션으로 의심받을 수 있다(hooks.md:1179) | 플러그인 enabled 범위 |
| `agent` (plugin settings.json) | 예. 메인 스레드의 시스템 프롬프트가 에이전트 것으로 바뀜 | 사라짐 | 대체에 가깝다(Claude Code 기본 프롬프트가 에이전트 프롬프트로 교체). 사용자 CLAUDE.md 는 유지 | 에이전트 이름 | 동료가 쓰는 메인 에이전트를 빼앗는다. 가장 침습적 | enabled 범위. `--agent` 가 우선 |
| 스킬 description | 예(description 만 목록으로) | 사라짐 | 병합 | `plugin:skill` | 목록 예산 안에서 잘림. 본문은 상시 아님(audit/30) | enabled 범위 |
| 훅 PreToolUse 등 additionalContext | 해당 시점만. 상시 아님 | 사라짐 | 병합 | 훅 이름 | 10,000자 | enabled 범위 |

## 서브에이전트와 compact
- 서브에이전트: 실험에서 general-purpose 서브에이전트는 style, MCP instructions, SessionStart context 셋 다 못 봤다. 문서(sub-agents.md "What loads at startup")도 서브에이전트에 실리는 것은 자기 시스템 프롬프트, 위임 메시지, CLAUDE.md 계층(user/project/local/managed), git status, 선언된 skills 뿐이라고 한다. 플러그인에서 서브에이전트까지 닿는 건 그 에이전트 정의의 본문과 `skills:` 프리로드 뿐이다. 포크는 메인의 시스템 프롬프트를 상속하므로 style 이 간다(문서).
- 사용자 CLAUDE.md 는 서브에이전트에 실리는데 플러그인 맥락은 안 실린다. 이 차이는 분리의 대가다. `SubagentStart` 훅의 additionalContext 로 보충할 수는 있다(문서 근거만, 실험 안 함).
- compact: 실험으로 style, MCP, SessionStart(compact 재실행) 모두 /compact 뒤에 남음.

## 세 이유에 대한 판단
1. 받는 사람이 이미 CLAUDE.md 가 있다: 플러그인 맥락은 CLAUDE.md 를 건드리지 않고 별도 채널로 더해지므로 충돌 없음. style 만 사용자 outputStyle 과 하나를 두고 경쟁한다.
2. 켜고 끄면 달라져야 한다: 위 세 방식 모두 만족. 가장 깔끔한 것은 MCP instructions 와 SessionStart(둘 다 플러그인 끄면 그대로 사라짐).
3. "최상위에 떠 있는 것" 이 사용자 CLAUDE.md 와 같은 층에 섞이는 것이 싫다는 해석: style·MCP 는 시스템 프롬프트에서 제목에 출처가 붙은 별도 섹션이라 맞다. 반면 SessionStart 는 reminder 에 훅 이름만 붙고 사용자에게 안 보인다. 다른 해석(플러그인 스킬·명령이 최상위 이름공간에 떠 있다)이라면 플러그인 스킬은 이미 `q:` 로 이름공간이 분리돼 있어 해당하지 않는다. 사용자 확인이 필요하다.

## `home/.claude/rules/` 가 home-sync 대상인 전제
여전히 맞다. 플러그인은 rules 를 싣지 못한다(문서에 구성 요소로 없고, 실험에서 `rules/` 와 `.claude/rules/` 모두 토큰이 안 보임). 다만 "상시 규약" 목적이면 rules 의 대체로 위 style/MCP/SessionStart 가 있다. 경로 조건부 로드(paths)는 대체재가 없다(스킬 paths 는 description 만 거름, audit/30).

## 권고안
대상: 훅 메시지 규약, workspace 불변식, 모델 사용 규칙.
- A안(보수): 지금대로. 사용자 CLAUDE.md 에 전부. 개인 환경이라면 충분하나 동료 배포 시 각자 CLAUDE.md 를 직접 고치게 만든다.
- B안(권장): 이식 가능한 규약을 플러그인 SessionStart 훅 하나로 싣고(`q` 의 기존 SessionStart 에 합치기, 사실 진술체로 10k자 아래, compact 뒤 자동 재실리), 사용자 CLAUDE.md 에는 개인 것만 남긴다: 작업 환경 지도(형제 저장소 표), 개인 정책(비용·모델 선호), `~/.claude` 정본 위치. 훅 메시지 규약은 `<harness-hook>` 를 내는 플러그인과 같은 곳에 있어야 정합하므로 플러그인 쪽이 맞다. workspace 불변식은 workspace_gate 가 이미 플러그인이므로 같은 곳. 모델 사용 규칙은 개인 취향과 비용 정책이 섞여 있어 CLAUDE.md 에 남기는 편이 낫다(동료에게 강제하면 안 됨).
- C안(출처 분리를 우선): 규약을 MCP instructions 로 싣는다. 시스템 프롬프트에서 출처가 가장 선명하나 규약 하나 때문에 상주 프로세스를 두는 셈이라 과하다. 빈 도구 서버로도 동작함은 실험으로 확인했으니 필요할 때만.
- 쓰지 말 것: `agent` 로 메인 교체(침습), style force(사용자 스타일 덮어씀, 코딩 지침 누락 위험). style 은 "응답 형식" 규약에만 선택적으로.
- 서브에이전트에 규약이 필요하면 CLAUDE.md 에 두거나 SubagentStart 훅으로 따로 주입해야 한다. 플러그인 SessionStart 는 서브에이전트에 안 간다.

## 실험 요약 (/tmp/ambient)
플러그인에 CLAUDE.md, rules/, .claude/rules/, force style, SessionStart 훅, 빈 도구 stdio MCP(instructions) 각각 고유 토큰을 넣음. 결과: STY·MCP·HOK 보임, CMD·RUL 안 보임. 서브에이전트는 셋 다 못 봄. /compact 후 resume 하여 셋 다 유지. 플러그인 없는 대조 실행은 토큰 없음. 비용 약 0.45 USD(대략, 상한 0.3 은 약간 초과). 문서로만 본 것: MCP instructions 상한, 포크의 style 상속, SubagentStart 보충, plugin settings 키 제한, 여러 플러그인 force 순서.
