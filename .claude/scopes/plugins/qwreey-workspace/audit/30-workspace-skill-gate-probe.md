# .claude/audit/30 - workspace 스킬 게이트 실험 (paths, 차단 후 로드 게이트, compact)

2026-11-11, Claude Code 2.1.316, sonnet. 실험 파일은 /tmp/probe30 (프로젝트 /tmp/probe30/proj, 훅 /tmp/probe30/hooks/gate.py,
설정 /tmp/probe30/settings.json 을 `--settings` 로만 붙임). 비용은 약 $0.83 으로 예산 $0.5 를 넘겼다(마지막 두 실험이 --resume 이라 캐시 쓰기 비용이 컸다).
고정 비용이 아니라 실험 횟수 탓이다.

## 1. 스킬 `paths` 의 실제 의미: (a) 가 맞다

문서: "When set, Claude loads the skill automatically only when working with files matching the patterns. Patterns are relative to Claude's current working directory, and files outside that directory don't match." (skills.md, frontmatter 표)

실험 (e1a/e1b/e1c): 스킬 4개(paths 각각 `src/**/*.txt`, 절대 `/tmp/probe30/outside/**`, 절대 `/tmp/probe30/proj/other/**`, `../outside/**`).
- 읽기 전에 스킬 목록: probe-* 넷 모두 **없음** (e1a, 목록 31개에 probe 없음).
- `src/a.txt` 와 cwd 밖 `/tmp/probe30/outside/c.txt` 를 Read 한 뒤: 목록에 `probe-rel` 만 **추가됨** (e1b: 응답 "probe-rel (파일을 읽은 뒤 추가된 스킬입니다)", stream 에 `{"name":"probe-rel","description":"... (project)"}`).
- 본문 토큰 `TOKEN-REL-7731` 은 주입되지 않음: 모델이 "아는 것이 없습니다", stream 에서 토큰은 프롬프트 외에 없음.
- 결론: 맞으면 **description 이 목록에 들어갈 뿐 본문은 주입되지 않는다**. 즉 (b) 아님.
- cwd 밖 절대경로 glob(`/tmp/probe30/outside/**`) 불일치: 목록에 안 뜸.
- cwd 안 파일을 가리키는 **절대경로 glob**(`/tmp/probe30/proj/other/**`, other/b.txt 를 읽음)도 불일치 (e1c). `../outside/**` 도 불일치.
  따라서 paths 는 cwd 상대 glob 만 되고, 형제 저장소(cwd 밖) 용으로는 쓸 수 없다.
- 부수: paths 가 있는 스킬은 맞기 전까지 목록에 없으므로 모델이 처음부터 호출할 수 없다. 게이트용 스킬에는 paths 를 달면 안 된다.

## 2. "차단 뒤 스킬 로드 확인" 게이트: 성립한다

구성: PreToolUse(Read|Edit|Write|Bash) 가 대상에 `/tmp/probe30/ws/` 가 있고 세션 마커가 없으면 deny. 마커는 PostToolUse(matcher Skill)에서
`tool_input.skill == "workspace"` 일 때 생성. reason: "Load skill `workspace` first (Skill tool), then retry."

- 흐름 (e2b, 스킬 description 은 중립): Read -> `PreToolUse:Read hook error: Load skill ... first` -> Skill{"skill":"workspace"} -> Read 재시도 통과.
  한 번의 `-p` 안에서 이어진다 (훅 로그: DENY, `PostToolUse Skill marker set`, allow).
- description 에 "Load before reading sibling repos" 처럼 적으면 모델이 거부 전에 먼저 스킬을 부른다 (e2a, 거부 0회). 게이트는 보험, description 이 1차.
- 로드 감지 신호:
  - 모델이 Skill 도구로 부름: PostToolUse(matcher `Skill`) 에 `tool_input = {"skill": "workspace"}` 가 온다. (플러그인 스킬이면 `q:name` 형태일 것 - 이번엔 프로젝트 스킬만 시험.)
  - 사용자가 `/workspace args` 로 침: **PostToolUse Skill 은 오지 않는다.** `UserPromptExpansion` 이 온다:
    `{"hook_event_name":"UserPromptExpansion","expansion_type":"slash_command","command_name":"workspace","command_args":"say only the word OK","command_source":"projectSettings","prompt":"/workspace say only ..."}` (e2e).
    문서(hooks.md): "a PreToolUse hook matching the Skill tool fires only when Claude calls the tool, but typing /skillname directly bypasses PreToolUse." 둘 다 들어야 한다.
- 우회 (e2c): 사용자가 "스킬 쓰지 말고 막히면 다른 방법으로" 라고 시키자 Read, Bash(cat) 거부 뒤 **Grep(pattern `^`)** 로 내용을 읽었다. 게이트 대상이 아닌 도구(Grep, Glob 등)는 뚫린다.
  사용자 지시가 없을 때 우회하는 모습은 보지 못했다(e2b, e2d 는 모두 스킬을 불렀다). 막으려면 Grep|Glob 도 matcher 에 넣어야 한다. Bash 는 명령 문자열의 경로만 보므로 `cd` 후 상대경로 등은 못 잡는다(시험 안 함).
- 스킬 frontmatter `hooks` 로 해제 (e2d): `hooks.PostToolUse(matcher "*", once: true)` 를 가진 스킬 `workspace-h` 를 부르자 그 훅이 **Skill 호출 자신의 PostToolUse 에서 이미 발화**해 마커를 세웠고, 재시도 Read 통과.
  단점: (1) 이 훅은 스킬을 부르기 전에는 없으므로 deny 쪽은 어차피 settings 훅이 해야 한다. 즉 감지는 frontmatter 로 대체되지만 게이트는 대체 안 됨. (2) `once: true` 인데 로그에 마커 설정이 두 번(Skill 직후, 다음 Read 직후) 찍혔다. `once` 가 이 구성에서 기대대로 한 번만 도는지는 불확실. (3) 스킬 호출 자체가 PostToolUse 를 일으키는지 여부에 의존. 
  권고: 감지는 settings 의 PostToolUse(Skill)+UserPromptExpansion 이 더 단순하고 스킬 이름 검사가 명시적이다.

## 3. compact 뒤

문서 근거:
- skills.md: "re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens ... older skills can be dropped entirely".
- context-window.md 표: 호출된 스킬 본문 "Re-injected, capped at 5,000 tokens per skill and 25,000 tokens total; oldest dropped first"; paths 규칙과 nested CLAUDE.md 는 "reloads on demand", 훅이 넣은 이전 context 는 "Summarized with the rest of the conversation"; SessionStart `compact` source 훅은 "Claude Code runs them and adds their output to the compacted context"; 스킬 description 목록은 v2.1.304+ 에서 재주입.

실험 (e3a/e3b, `claude -p --resume <sid> "/compact"` 가 -p 에서 동작함):
- 훅 순서: PreCompact(`trigger: manual`) -> SessionStart(`source: "compact"`, `model`) -> PostCompact(`trigger`, `compact_summary` 전문).
  **session_id 는 그대로**다. 따라서 session_id 키의 마커 파일은 compact 뒤에도 남는다 -> 초기화하려면 PreCompact/PostCompact/SessionStart(compact)에서 지워야 한다.
- 이 실험에서는 `/workspace` (슬래시)로 부른 스킬 본문이 compact 뒤 **별도 재주입되지 않았다**: 트랜스크립트 compact_boundary 뒤에 스킬 본문 메시지가 없고, 토큰은 요약문(`isCompactSummary`)에만 남았다. 모델 답: "요약문에 적힌 내용으로만 남아 있고, 스킬 본문 원문이 직접 로드된 것은 아니다".
  문서와 어긋나거나(슬래시 호출 경로는 대상 아님?) 본문이 아주 작아 요약이 대신했을 수 있다. **Skill 도구로 부른 경우는 시험하지 못했다**(예산).
- SessionStart(compact) 훅이 낸 additionalContext 는 compact 요약 뒤에 attachment(`hook_additional_context`)로 들어간다(기존 session-log 훅의 출력으로 확인).
- skill_listing 은 compact 뒤 다시 attachment 로 들어간다.

판단: **게이트 마커는 compact 뒤 초기화해야 한다.** 이유 (1) 스킬 본문이 재주입에서 빠질 수 있다(5k 자름, 25k 합계에서 오래된 것 탈락, 위 실험에선 재주입 자체가 안 보임). (2) 마커가 남으면 본문 없이 게이트만 통과한다.
초기화 시점은 SessionStart(source=compact)가 가장 간단하다(같은 훅이 additionalContext 로 "workspace 스킬을 다시 읽어라" 안내도 낼 수 있음). 초기화 뒤 첫 접근에서 다시 deny 되므로 모델이 스킬을 다시 부르고,
같은 렌더 내용이면 "already loaded" 노트만 붙는다는 문서(skills.md Skill content lifecycle) 때문에 본문이 아직 남아 있으면 재호출이 싸다. 단 compact 뒤에는 이전 호출 흔적이 요약으로 바뀌므로 실제로는 본문이 다시 들어올 것(검증 안 함).

## 4. main 세션에 본문을 늘 싣는 공식 방법

- 스킬 자체에는 "항상 로드" 가 없다. 목록에는 description 만(`disable-model-invocation: true` 면 그것도 빠짐), 본문은 호출 시에만. 서브에이전트 `skills:` preload 는 서브에이전트 전용.
- 공식 경로: SessionStart 훅의 `additionalContext` (hooks.md "SessionStart ... String added to Claude's context at the start of the conversation, before the first prompt"). source 는 startup/resume/clear/compact/fork 모두 실행되므로 compact 뒤에도 다시 실려 상시성이 유지된다(위 실험으로 compact 경로 확인, resume 은 문서: "SessionStart hooks run again on resume").
  제약: 10,000자 초과 시 파일에 쓰고 경로와 앞 2,000자 미리보기만 전달(hooks.md). "정적이면 CLAUDE.md 를 쓰라" 는 문서 권고가 있다.
  `<system-reminder>` 태그는 이스케이프된다. 명령조는 prompt injection 방어로 사용자에게 노출될 수 있으니 사실 진술로 쓰라고 안내.
- 비용: 모든 세션의 컨텍스트에 그 토큰 수만큼 상시(CLAUDE.md 와 같은 위치·비용, 캐시 대상). 즉 "기계마다 다른 내용을 상시 로드에서 뺀다" 는 목적과 정면 충돌한다. 상시 주입은 작은 포인터(경로·한 줄 요약)만 하고 본문은 게이트(차단 후 스킬)로 가는 것이 목적에 맞다.
- compact 뒤: 호출된 스킬은 5k/25k 예산으로 재주입, additionalContext 는 SessionStart(compact) 훅이 있어야 되살아난다(훅 출력 자체는 요약에 포함되고 재실행되어 새로 들어감).

## 한계
- 비용 초과($0.83). Skill 도구로 부른 스킬의 compact 뒤 재주입, `once` 의 정확한 동작, 플러그인 스킬명(`plugin:skill`)이 tool_input.skill 에 어떻게 오는지, Bash 의 상대경로 우회는 미검증.
- 목록 노출은 transcript 상 `skill_listing` attachment 와 모델 응답으로만 확인했다.
