# 19-01. 외부 조사 1/4: Anthropic 공식 가이드와 우리 하네스 대조

- 날짜: 2026-11-10. 로컬 Claude Code 2.1.316. 공식 changelog 최신은 2.1.322(2026-11-10).
- 범위
  - 공식 문서: code.claude.com/docs (best-practices, memory, skills, sub-agents, hooks, features-overview, context-window, costs, prompt-caching, plugins/loading, plugins/measure, plugin-evals, debug-your-config, changelog)
  - Anthropic 글: claude.com 블로그 2편(2026), anthropic.com engineering 3편(2025)
  - 사양: platform.claude.com 스킬 작성 best practices, agentskills.io 사양
  - 우리 쪽 대상: `home/.claude/`(CLAUDE.md, rules 2, 훅 4, harness.env, harness-doctor), luau-kb(스킬 12, rules, .lsp.json), session-log 플러그인, PLAN·audit 10/16/17/18
- `.claude/audit/01`에서 이미 정리한 사실은 반복하지 않는다. 그 뒤에 나왔거나 거기서 빠진 것, 그리고 대조 판정을 다룬다.
- 분류
  - **(a)** 공식 권고를 잘 따름
  - **(b)** 공식 권고와 어긋나거나 과함(과잉 설계, 컨텍스트 비용, 유지보수 부담)
  - **(c)** 공식이 권하는데 우리가 안 씀
  - **(d)** 공식이 말하지 않는 영역이라 독자 판단
- 확인 표기
  - [원문]: 페이지 원문을 직접 읽음
  - [요약확인]: WebFetch 요약을 거침. 인용 문구는 요약 도구가 옮긴 것
  - [로컬]: 이 sandbox 의 파일을 읽어 확인
  - [추정]: 계산·추론
  - [미확인]: 문서에서 찾지 못함
- 공식 문서 페이지에는 게시일이 없다. 날짜는 조회일(2026-11-10)이고, 블로그는 게시일을 적었다.

## 0. 요약: 외부자가 보기에 가장 중요한 것

1. **(c)+(b) luau-kb 를 심볼릭 링크로 소비하면 생기는 두 손실**
   - luau-lsp 코드 인텔리전스(`.lsp.json`)는 플러그인으로 로드될 때만 켜진다. 링크 방식에서는 꺼진 채다 [로컬].
   - 스킬 12개의 설명(약 6,900자)은 웹·go·rust 저장소를 포함한 모든 세션에 상시 실린다 [로컬][추정].
   - 공식 문서상 **로컬 경로 마켓의 상대경로 플러그인은 제자리(in-place)에서 로드되고 버전을 올릴 필요가 없다** [원문 plugins/loading].
   - 따라서 .claude/audit/01·PLAN 이 링크를 고른 근거("캐시 사본이라 버전 bump 필요")는 이 경우에 성립하지 않는다.
   - 권고: luau-kb 를 플러그인으로 설치하고, Luau 저장소에서만 켠다.
2. **(b) 공식 방향은 "규칙을 줄이고 판단에 맡긴다"인데, 우리는 규칙·훅·프로토콜을 쌓는 쪽이다**
   - 2026-07 Claude 5 글은 "Give Claude rules → Let Claude use judgement"라고 쓰고, 시스템 프롬프트를 80% 넘게 지웠다고 밝혔다 [요약확인].
   - best-practices 는 다음을 권한다 [원문].
     - 강조어(IMPORTANT)를 쓰지 않는다.
     - 훅은 예외가 없는 규칙에만 쓴다.
     - "if you have hooks for things that are only preferences, delete them".
   - hooks 문서는 additionalContext 를 "사실 서술"로 쓰라고 한다. 명령형은 프롬프트 주입 방어를 건드릴 수 있다는 이유다 [요약확인].
   - 이에 비춰 볼 대상
     - 우리 `level="action"` 프로토콜과 CLAUDE.md 의 "반드시 읽고 … 그냥 넘기지 않는다"
     - code-structure 수치 규칙과 structure-reminder 의 1,500줄 action
3. **(c) 공식 진단·측정 도구를 쓰지 않는다**
   - 해당 도구: `/doctor`, `/doctor prompt-audit`, `/skill-doctor`, `claude plugin details`, `claude plugin eval`, `/insights`, `/usage` 귀속 분석, InstructionsLoaded 훅
   - PLAN 의 검증 루프에는 적혀 있다. 그러나 실행한 흔적은 로컬 문서에서 찾지 못했다 [로컬 grep].
   - harness-doctor scan 의 LOAD/RULE/SKILL/STALE 검사는 이 공식 도구들과 상당 부분 겹친다.
4. **(c) 사용자의 가장 큰 반복 고충에 공식 해법이 있다**
   - .claude/audit/10 패턴 A: compact 의식 64회, 컨텍스트 % 보고 27회.
   - 공식 해법 [원문]: CLAUDE.md `# Compact instructions` 절, `/compact <focus>`, `/rewind` 의 부분 요약, `/autocompact`, `idleCompaction`.
   - 또 공식이 첫째로 꼽는 "Give Claude a check to run"(Stop 훅·`/goal`)을 Luau 저장소 검증에 아직 쓰지 않는다.
5. **(a) 골격은 공식과 잘 맞는다**
   - paths 로 범위를 정한 rules
   - 부작용 스킬에 `disable-model-invocation`
   - 환경 보호용 PreToolUse deny(heavy-proc-guard)
   - `language` 설정
   - auto 모드
   - 새 컨텍스트 리뷰어 방향(.claude/audit/18)
   - "Claude 가 모르는 것만" 담은 luau-core rules
6. **(d) 독자 영역은 대체로 정당하다. 단 유지 비용을 재 봐야 한다**
   - 대상: 다저장소 지도·세션 확인, home-sync/MANIFEST, harness.env, session-log, decisions D-xx, bash-bypass-reminder
   - bash-bypass-reminder 는 "Bash 로 쓰면 path rule 이 안 붙는다"는 공식 동작의 틈을 메운다.

---

## 1. .claude/audit/01 이후 새로 확인한 공식 사실 (델타)

| # | 사실 | 출처 | 표기 | .claude/audit/01 과의 관계 |
|---|---|---|---|---|
| 1 | 로컬 경로(`file`/`directory`)로 추가한 마켓의 상대경로 플러그인은 **제자리 로드**된다. 편집은 다음 세션 시작이나 `/reload-plugins` 때 반영되고 **version 을 올릴 필요가 없다**. `~/.claude/skills/` 아래 `.claude-plugin/plugin.json` 이 있는 디렉터리도 `<name>@skills-dir` 플러그인으로 제자리 로드된다 | plugins/loading "In-place and copied plugins", "Find where a plugin came from" | [원문] | .claude/audit/01 §5 "캐시 사본이라 버전 올림 필요"를 **로컬 마켓에 한해 정정** |
| 2 | `enabledPlugins` 는 user/project/local/flag/managed 를 키별로 병합한다. 저장소별로 켜고 끌 수 있다(`.claude/settings.local.json` 이 project 보다 우선) | plugins/loading "Find where a plugin is enabled" | [원문] | 신규 |
| 3 | 플러그인 상시 비용은 `claude plugin details <name>` 로 잰다. 공식 마켓은 상시 2,000토큰 이상이면 "Every turn" 줄을 강조 표시한다 | plugins/measure | [원문] | 신규 |
| 4 | 스킬 목록 예산은 컨텍스트 창의 1%다. 넘치면 **가장 적게 호출된 스킬부터 설명이 빠진다**. 조정은 `skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`, `skillListingMaxDescChars`, `skillOverrides: name-only` 로 한다 | skills "Skill descriptions are cut short" | [원문] | .claude/audit/01 은 1%만 기록. 탈락 순서와 설정 키는 신규 |
| 5 | 스킬 트리거율은 `claude plugin eval` 의 `tool_used: Skill` grader 로 잰다. `claude plugin validate ~/.claude/skills` 는 2.1.233 이상에서 쓸 수 있다. skill-creator 플러그인도 with/without 벤치·설명 튜닝을 한다 | skills "Skill not triggering", plugin-evals | [원문](skills) [요약확인](plugin-evals 머리말) | .claude/audit/06 이 "미검증"으로 남긴 것 |
| 6 | 설명이 모호하거나 **서로 겹치면** Claude 가 엉뚱한 스킬을 고르거나 놓친다 | features-overview "How Claude chooses skills" | [원문] | 신규 |
| 7 | rule frontmatter 에서 Claude Code 가 읽는 필드는 **`paths` 뿐**이고 나머지는 조용히 무시된다. YAML 이 깨지면 paths 없는 rule 로 로드된다(=상시) | memory "Rule frontmatter reference" | [원문] | 신규 |
| 8 | 사용자 rule 과 프로젝트 rule 은 서로 덮지 않는다. 충돌하면 "Claude may follow either one" | memory "User-level rules" | [원문] | 신규 |
| 9 | path rule 과 하위 CLAUDE.md 는 대화 이력에 들어가므로 compact 때 요약되어 사라지고, 다음 매칭 때 다시 로드된다. 루트 CLAUDE.md·paths 없는 rule·auto memory 는 디스크에서 다시 주입된다. 호출된 스킬 본문은 스킬당 5,000, 합계 25,000토큰까지 재부착된다 | context-window "What survives compaction" | [원문] | .claude/audit/01 미기재 |
| 10 | on-demand 파일(path rule, 하위 CLAUDE.md) 글자 한도는 v2.1.309 부터 적용된다. 1M 창 신규 모델 기준 150,000자 | memory "Claude ignores the end…" | [원문] | .claude/audit/01 #4 보강(적용 시점) |
| 11 | `/doctor` 는 "CLAUDE.md 에서 코드로 알 수 있는 내용", 쓰지 않는 확장, 스킬 목록 비용을 지적하고 고칠 안을 낸다. `/doctor prompt-audit` 은 사용자·프로젝트의 rules/skills/agents/output styles 까지 "옛 모델용 지시, 없는 파일 참조, 상충"을 본다(2.1.283 이상) | memory, debug-your-config | [원문] | .claude/audit/01 은 명령 이름만 기록 |
| 12 | CLAUDE.md 에 `# Compact instructions` 절을 두면 compact 요약에 무엇을 남길지 정할 수 있다 | costs "Manage context proactively" | [원문] | 신규 |
| 13 | idle compaction: 1시간 캐시에서 200K 를 넘은 세션을 놀려 두면 캐시 만료 직전에 요약된다. `idleCompaction: false` 로 끈다(2.1.290 이상). 2.1.314 에서 적용 대상이 넓어졌다 | best-practices note, prompt-caching, changelog 2.1.314 | [원문][요약확인] | 신규. 이 사용자 세션은 중앙값 26만~42만 토큰(.claude/audit/18) |
| 14 | 캐시 TTL: 구독은 메인 1시간, 서브에이전트·포크·compact 는 5분. `promptCacheTtl`, `subagentPromptCacheTtl` 로 바꾼다. CLAUDE.md 를 세션 중에 고치면 캐시는 유지되지만 `/clear`·`/compact`·재시작 전까지 반영되지 않는다 | prompt-caching | [원문] | 신규 |
| 15 | 훅 additionalContext·plain stdout 상한은 10,000자다. 넘치면 파일로 저장하고 앞 2,000자 미리보기만 넘긴다. **additionalContext 는 "factual statements rather than imperative system instructions"로 쓰라.** 명령형은 "can trigger Claude's prompt-injection defenses" | hooks | [요약확인] | .claude/audit/17 실측(태그 없는 평문 접두)과 맞물림 |
| 16 | `onFailure: "block"`(command/http 훅, 2.1.295 이상): 훅이 죽으면 동작을 막는다. 훅 종류는 command, http, mcp_tool, prompt, agent 다. prompt/agent 는 비결정적이다 | hooks, best-practices | [요약확인][원문] | 신규 |
| 17 | best-practices: "keep the enforced set small … If you ever find yourself at forty of them, most are probably preferences". "a hook is for a rule with zero exceptions, and `Prefer named exports` … stays in CLAUDE.md" | best-practices "Choose who a rule applies to", "Enforce steps with hooks" | [원문] | 신규 |
| 18 | best-practices "What you can stop doing": 컨텍스트를 공격적으로 관리하기, IMPORTANT·대문자 강조, "더 나은 답을 위해 서브에이전트에 위임", `think hard`, "keep going/don't be lazy", CLAUDE.md 에 구조 설명 쓰기 | best-practices | [원문] | 신규 |
| 19 | Opus 5.5 등 5.5 계열의 기본 effort 는 `medium` 이다. `max` 는 일상 작업에서 과하게 생각한다. 서브에이전트는 `CLAUDE_CODE_SUBAGENT_EFFORT` 로 따로 정한다(2.1.316) | best-practices, changelog 2.1.316 | [원문][요약확인] | 신규 |
| 20 | 서브에이전트: 기본 3단까지 중첩된다(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`). `omitClaudeMd`, `memory`, `skills` 프리로드, `tools` 제한은 하네스가 강제한다. 리뷰어 예시는 `tools: Read, Grep, Glob` 와 "Skip style" | sub-agents, best-practices | [요약확인][원문] | .claude/audit/01 §3 보강 |
| 21 | AGENTS.md 는 2.1.277 부터 기본으로 읽는다. 단 CLAUDE.md 가 있으면 AGENTS.md 는 안 읽는다(`claude-md-and-agents-md` 로 둘 다). 한 파일 공유는 CLAUDE.md 에서 `@AGENTS.md` import | memory "AGENTS.md" | [원문] | 신규 |
| 22 | `/insights`: 최근 세션(최대 200개)을 분석해 마찰 지점과 개선 제안을 담은 HTML 보고서를 만든다 | costs "Analyze your usage patterns" | [원문] | 신규. .claude/audit/10 수작업 채굴의 공식 대응물 |
| 23 | 공식 블로그(2026-07-24, Thariq Shihipar): Claude 5 세대에서 시스템 프롬프트를 80% 넘게 지웠는데 코딩 평가 손실이 없었다. 6개 전환은 다음과 같다. 규칙→판단, 예시→인터페이스 설계, 전부 앞에→점진 공개, 반복→단순 도구 설명, CLAUDE.md 메모리→auto memory, 단순 명세→풍부한 참조(루브릭·검증 에이전트). "clashing messages … DO NOT add comments" 같은 상충은 지우라고 한다. `/doctor` 로 "rightsize your skills, and CLAUDE.md files" | claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models (claude.dev 로 308) | [요약확인] | 신규. 전체 방향의 기준점 |
| 24 | 공식 블로그(2026-06-18) "Steering Claude Code": paths 없는 rule 은 CLAUDE.md 와 같은 비용이다. 공유 CLAUDE.md 는 아무도 지우지 않아 자란다 | claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more | [요약확인] | 신규 |

---

## 2. 대조표

### 2.1 상시 컨텍스트: CLAUDE.md 와 rules

| 항목 | 분류 | 공식 근거 | 우리 상태 [로컬] | 판단·권고 |
|---|---|---|---|---|
| 사용자 CLAUDE.md 크기 | (a) | 200줄 미만. Claude 가 볼 수 없는 것만 담는다(best-practices "Keep CLAUDE.md short") | 정본 4.2KB, 약 45줄 | 충분히 작다 |
| 형제 저장소 지도·읽기 전용 원칙·세션 확인 명령 | (a)/(d) | "Describe your architecture … in CLAUDE.md"는 그만둘 일(Claude 가 저장소를 읽으므로). 다른 저장소는 현재 저장소에서 안 보인다 | 표 1개, 명령 1줄 | 저장소 안에서는 알 수 없는 정보라 정당하다(d). 저장소 내부 구조 설명은 넣지 않았다(a) |
| "훅 메시지" 절(level·반드시) | (b) | 강조와 명령형은 과잉 적용을 부른다(best-practices). additionalContext 는 사실 서술로 쓴다(hooks [요약확인]) | `info/warn/action` 의미를 3줄로 규정. "반드시 읽고 … 그냥 넘기지 않는다", "action … 반드시 처리" | HOOK-MESSAGES.md 규칙 4("지시가 아니라 관찰+권고")는 공식과 맞다(a). 그러나 CLAUDE.md 가 그 텍스트에 사용자 지시에 준하는 권위를 부여하는 것은 공식이 경계하는 방향이다. 권고: level 은 남기되 CLAUDE.md 문구는 "사실 알림이니 판단에 반영"으로 낮춘다. 실제로 꼭 지켜야 하는 것(1,500줄 초과 시 질문)은 PreToolUse `ask` 결정으로 옮겨 하네스가 묻게 한다 |
| "코드 리뷰를 먼저 한다" 절 | (b) 위험 | 새 컨텍스트 리뷰어는 권장(/code-review). 동시에 "A reviewer that's asked to find problems will always find something … extra abstraction layers"(best-practices). "keep going" 류 문장은 과로를 부른다 | 시점 4개를 정하고, 예산 규칙 우선이라는 단서를 단다 | 방향은 맞다. 다만 사용자의 비용 사고 이력($589, .claude/audit/10 B)에 비춰 "먼저 한다"는 과로 신호다. 시점을 훅이 알리는 .claude/audit/18 방식과 중복이므로 CLAUDE.md 쪽은 한 줄로 줄인다 |
| 모델 사용 규칙(haiku 는 읽기 전용) | (a)/(d) | "Haiku is a good fit for subagents doing simple jobs"(best-practices, costs) | haiku 를 위치 조사로만 제한 | 공식 권고의 부분집합이다. 실측(규칙 위반) 근거가 있다 |
| 툴체인·choom 안내 | (a) | Claude 가 모르는 환경 사실 | 3줄 | 적절하다 |
| rules 의 paths 범위 | (a) | 부분에만 해당하는 규칙은 paths rule 로(best-practices "Scope rules") | 3개 모두 paths 있음 | 공식대로다 |
| rules 의 `description:` frontmatter | (d) | Claude Code 는 `paths` 외 필드를 무시한다 | luau-kb rules/README 가 description 을 "필수"로 둠 | 사람용 메타로는 무해하다. 모델이 본다고 오해하지 않게 README 에 "Claude Code 는 무시"라고 적는다 |
| luau-core.md 내용 | (a) | "only write down what Claude can't find on its own" | `local const x` 전역화, `f<<T>>`, 문장 첫 `(` 같은 비자명한 함정 40줄 | 공식이 말하는 "gotchas" 그 자체다 |
| code-structure.md (800/1,500줄, 같은 접두 3개면 폴더, 문자열 분기 8개면 표 등) | (b) | Claude 5 글 "rules → judgement". best-practices "Most of the time, you want Claude to decide … Claude is usually better placed to make that call than a rule you wrote in advance" | 확장자 12종(거의 모든 코드 세션)에 로드된다. structure-reminder 훅과 짝이다 | 사용자 결정(D-13)이므로 **제안만** 한다. 수치 기준 대부분은 모델이 이미 아는 일반 원칙이다. 이 저장소들 고유의 것(예외 표식, move-only 커밋)만 남기고 나머지는 훅의 사실 알림(줄 수)에 맡기는 축소안을 A/B 로 재 보자 |
| web-security.md | (a)/(b) 경계 | Claude 가 이미 아는 일반 보안 상식은 비용이다. 단 "must hold every time"이면 훅·deny | 17줄. JS/TS 파일에서만 로드 | .claude/audit/16 의 공백 보완이라 근거는 있다. 다만 일반 OWASP 지식이 대부분이다. 저장소 고유 위험(vitrine 의 nonce 재사용·CSRF 실사례)만 남기고 나머지는 `/security-review` 에 맡기는 쪽이 공식 방향에 가깝다 |
| user rule ↔ repo rule 충돌 | (a) | 둘 다 로드되고 어느 쪽을 따를지 불확실하다 | 각 rule 머리에 "repo 가 다르면 repo 를 따른다" | 공식이 지적한 불확실성을 명시 규칙으로 메웠다 |
| 실제 ~/.claude 반영 상태 | (관찰) | - | `~/.claude/rules/` 없음, `~/.claude/skills/` 에는 `synced` 만 있다. 배포된 CLAUDE.md 는 옛판(`pgrep -f`) | 정본이 아직 apply 되지 않았다. **반영 전에 `/context all` 기준선을 재 두면** 전후 비교를 공식 도구로 할 수 있다 |

### 2.2 스킬과 luau-kb

| 항목 | 분류 | 공식 근거 | 우리 상태 [로컬] | 판단·권고 |
|---|---|---|---|---|
| SKILL.md 길이, 참조 1단계, references 분리 | (a) | 500줄 미만, 참조는 1단계, 100줄 넘는 참조 파일에는 목차(platform best practices, agentskills.io) | SKILL.md 39~94줄, references/ 분리 | 공식대로다 |
| 이름 규칙 | (a) | 소문자·하이픈, 64자, 디렉터리명과 일치, `claude`·`anthropic` 예약 | `luau-*`, `roblox-*` 로 디렉터리명과 일치 | 공식대로다. 동명사형 권장은 선택 사항이다 |
| 설명 길이·앞에 핵심 두기 | (a)/(b) | 설명은 1,024자(사양). Claude Code 는 description+when_to_use 를 1,536자에서 자른다. "Put the key use case first" | 262~892자. 첫 문장에 "무엇"을 둔다 | 형식은 맞다. 다만 키워드를 길게 나열해 합계가 약 6,900자(이름 포함)다 → 아래 상시 비용 행 |
| 스킬 12개 상시 비용 | (b) | 플러그인 상시 2,000토큰 이상이면 공식 UI 가 강조한다(plugins/measure). 설명은 매 요청 비용이다(features-overview) | 한국어 6,900자. 토큰으로 대략 3.5k~7k [추정]. `~/.claude/skills` 링크라 **vitrine·VideoSync·coderag 세션에도** 실린다 | 플러그인화(아래)로 Luau 저장소에서만 켠다. `claude plugin details luau-kb` 로 실측한다. 설명은 "무엇+언제" 한두 문장으로 줄이고 세부 키워드는 SKILL.md 본문으로 옮긴다. 줄인 뒤 트리거율은 eval 로 확인한다 |
| 스킬 사이 겹침 | (b) 위험 | 겹치는 설명은 오선택을 부른다(features-overview) | luau-roblox ↔ roblox-engine/net/world, luau-verify ↔ luau-testing, luau-style ↔ luau-core rule | 혼동하기 쉬운 쌍마다 "should-trigger / should-not" 프롬프트로 eval 을 만든다(공식 skill-creator 의 description tuning 또는 `claude plugin eval`) |
| 평가 먼저 만들기 | (c) | "Create evaluations BEFORE writing extensive documentation". 시나리오 3개 이상, Haiku·Sonnet·Opus 각각(platform best practices). 공식 도구는 `claude plugin eval`, skill-creator | PLAN 검증 루프에 "스킬마다 평가 시나리오 3개"로 적혀 있음. 실행 흔적은 찾지 못함 [로컬 grep] | 스니펫 하네스(`check_snippets.py`)는 **지식의 참/거짓**을 검증한다(훌륭한 (d)). **스킬이 제때 불리는지**는 검증하지 않는다. 둘은 별개다 |
| 시간에 민감한 정보 | (d) | "Avoid time-sensitive information", "old patterns" 절 사용 | references 에 status/last-confirmed, coderag `lifecycle`·`review_after`, luau 0.734/0.742 비교 | 주간 릴리스 생태계라 버전 표기는 정당하다. 공식 반대 방향이 아니라 보완이다. 단 SKILL.md 본문에는 "현재 방법"만 두고 버전별 차이는 references 로 미는 원칙을 유지한다 |
| 실행 가능한 검증 스크립트 | (a) | "Provide utility scripts", "verifiable intermediate outputs", "Solve, don't defer" | snippets, split-plan.py, roblox_docs.py, scan.py | 공식이 가장 권하는 패턴과 같다 |
| harness-doctor `disable-model-invocation: true` | (a) | 부작용 있는 절차는 사용자 호출 전용. 설명이 컨텍스트에 실리지 않는다 | 적용됨 | 공식대로다 |
| 스킬 본문이 compact 뒤 5,000토큰에서 잘림 | (c) 점검 | 가장 중요한 지시를 SKILL.md 위쪽에 둔다(context-window, skills) | harness-doctor SKILL.md 91줄로 원칙이 위에 있음 | 대체로 맞다. luau-* 의 "결정 트리"가 위에 있는지만 점검한다 |

### 2.3 배포 방식: 링크 vs 플러그인

| 항목 | 분류 | 공식 근거 | 우리 상태 | 판단·권고 |
|---|---|---|---|---|
| luau-kb 소비를 `~/.claude/skills/<각 스킬>` 13개 링크로 | (b)+(c) | "A second repository needs the same setup → Package it as a plugin"(features-overview). 로컬 마켓 상대경로 플러그인은 제자리 로드, 버전 bump 불필요(plugins/loading [원문]). `enabledPlugins` 를 저장소별로 켜고 끈다 | MANIFEST 에 링크 13줄. `luau-kb-market` 은 별도로 있음(마켓 설명문). 설치 기록 없음(`installed_plugins.json` 빔) | **플러그인 설치로 바꾸는 것을 권한다.** 얻는 것: ① `.lsp.json` 의 luau-lsp(공식 "code intelligence plugin" 권고, 파일 읽기 감소)가 켜진다. ② Luau 저장소에서만 켜서 웹 저장소 상시 비용 0. ③ `plugin details`·`/skill-doctor`·"Not used recently"로 측정. 잃는 것: 스킬 이름이 `luau-kb:luau-types` 로 네임스페이스된다. rules 는 플러그인으로 못 보낸다(.claude/audit/01 #9) → `luau-core.md` 링크 1줄만 MANIFEST 에 남는다 |
| 플러그인의 rules 미지원 | (d) | 플러그인 구성 요소에 rules 가 없다(plugins/components, .claude/audit/01) | `rules/luau-core.md` 만 링크 | 합리적이다 |
| session-log 를 플러그인으로 | (a) | 여러 저장소 공용 훅은 플러그인으로(features-overview) | claude-doctor-market 에 등록 | 공식 패키징대로다 |
| home-sync + MANIFEST + harness.env | (d) | 공식은 1인 다기기 dotfiles 동기화를 다루지 않는다. 플러그인은 CLAUDE.md 를 로드하지 않는다 | 정본·diff·apply·백업 | CLAUDE.md·settings 는 플러그인으로 못 옮기니 필요하다. 다만 **훅 4개와 lib/ 는 "harness-core" 플러그인으로 묶을 수 있다**(플러그인 훅은 사용자 훅과 병합되고 서브에이전트에서도 돈다). 그러면 MANIFEST 관리 대상이 CLAUDE.md·settings·harness.env 정도로 준다. 유지 부담과 이식성을 따져 결정한다 |

### 2.4 훅

| 항목 | 분류 | 공식 근거 | 우리 상태 | 판단·권고 |
|---|---|---|---|---|
| heavy-proc-guard (PreToolUse deny) | (a) | 예외가 없어야 하는 규칙은 훅·deny로("must hold every time") | 메모리 cgroup 을 공유하는 환경 보호 | 교과서적인 용도다. "Every hook and deny rule will occasionally fire when it shouldn't"라는 공식 경고대로 오탐이 있다("bench" 글자 매칭 → `choom -p $$` 우회 관행). 명령의 첫 실행 파일 기준 매칭으로 좁히거나 훅 `if` 필터를 검토한다 |
| bash-bypass-reminder | (d) | path rule 은 Read/Write/Edit 때만 붙는다(memory). Bash 쓰기는 다루지 않는다 | Bash 로 파일을 바꾸면 해당 rule 을 알린다. haiku 2/2 vs 0/2 실측 | 공식 동작의 틈을 메우는 독자 판단이라 정당하다. 표본이 n=2 라 sonnet·opus 로 더 재 볼 가치가 있다 |
| structure-reminder | (b) 일부 | PostToolUse 출력은 "linter 결과를 돌려주는" 정석 용도다(features-overview). 반면 선호 규칙을 훅으로 강제하지 말라(best-practices) | 줄 수 사실 알림(info/warn)과 1,500줄 action(사용자에게 질문 요구) | 줄 수·예외 사유 같은 **사실 알림은 (a)** 다. "질문하라"는 action 은 결정적 강제가 아니면서 강제처럼 쓰여 있어 어중간하다. 꼭 묻게 하려면 PreToolUse `permissionDecision: "ask"` 로 하네스가 묻게 하고, 아니면 info 로 낮춘다 |
| rearm-on-compact (SessionStart compact) | (a) | compact 매처의 SessionStart 훅 출력은 압축된 컨텍스트에 더해진다(context-window) | dedup 회차 재무장 | 공식 메커니즘을 정확히 썼다 |
| `<harness-hook>` 태그 + level | (d)/(b) | 공식은 태그 규약을 정하지 않는다. 사실 서술을 권한다 | .claude/audit/17 실측 근거로 태그를 도입 | 출처 구분용 태그 자체는 합리적이다(d). 위 2.1 의 권위 문구만 조정한다 |
| 훅 수와 비용 | (b) 주의 | "keep the enforced set small". SessionStart 는 매번 돌므로 빠르게 | 사용자 훅 4개 + session-log 7개 이벤트(PostToolUse 는 **모든 도구** 호출마다 python 기동) + .claude/audit/18 제안 4개(PreToolUse Bash\|ExitPlanMode, PostToolUseFailure, SubagentStop, Stop) | 도구 호출 한 번에 python 프로세스가 2~4개 뜬다. 지연은 아직 재지 않았다 [미확인]. 새 훅을 들이기 전에 `claude --debug` 로 훅별 시간을 재고, session-log 의 PostToolUse 를 matcher 로 좁힐 수 있는지 본다 |
| Stop 훅·`/goal` 로 완료 조건 강제 | (c) | "Give Claude a check to run". Stop 훅 `exit 2` 로 typecheck 통과 전 종료 막기. 8회 상한(best-practices) | 검증 절차는 luau-verify 스킬과 rules 의 "gate exit code" 줄에만 있음 | Luau 저장소별 `.claude/settings.json` 에 `luau-analyze`(+stylua --check) Stop 훅을 두는 것이 공식이 가장 먼저 권하는 투자다. 사용자 레벨이 아니라 저장소 레벨이다(명령이 저장소마다 다름) |
| `onFailure: "block"` | (c) 검토 | 훅이 죽어도 막아야 하는 가드에 쓴다 | heavy-proc-guard 가 죽으면 통과(기본 continue) | 이 가드가 OOM 방지용이라면 `onFailure: "block"` 이 맞다. 다만 오탐 때 막히는 비용과 함께 판단한다 |
| 리뷰어 읽기 전용을 훅으로 강제(.claude/audit/18 초안) | (b) | `tools:` 제한은 "enforced by Claude Code rather than requested in a prompt". 공식 리뷰어 예시는 `tools: Read, Grep, Glob` | Bash 를 허용하고 `auditor-readonly-guard.py` 훅으로 막음 | Bash 가 꼭 필요하면 훅이 맞다. git diff 정도라면 메인이 diff 를 넘기고 `tools: Read, Grep, Glob` 로 두는 쪽이 단순하다 |

### 2.5 서브에이전트·리뷰·비용

| 항목 | 분류 | 공식 근거 | 우리 상태 | 판단·권고 |
|---|---|---|---|---|
| 새 컨텍스트 리뷰어(.claude/audit/18) | (a) | "Getting a reviewer that hasn't seen how the code was written". "Delegate for a better answer"는 그만둘 일이고, fresh reviewer 는 다른 일이다 | 시점 3개, 원문 직접 추출, 원장 | 공식 논리와 같다. "skip style" 같은 범위 제한 문구를 리뷰어 프롬프트에 넣는다 |
| advisor 끄기 | (d) | advisor 문서는 고위험 독립 검증 용도라고 한다(.claude/audit/18 인용) | 암호화 결과, 캐시 없음, 비용 실측으로 끔 | 이 환경에서 잰 값에 근거한 독자 판단이라 타당하다 |
| 관점별 감사 에이전트(.claude/research/drafts/agents) | (a)/(c) | "Define a custom subagent when you keep spawning the same kind of worker". `/audit` 이 security·performance·style 서브에이전트를 띄우는 예가 features-overview 에 그대로 있다 | 초안만 있고 설치되지 않음 | 방향은 공식 예시와 같다. 설치 전 `skills:` 프리로드 크기(전체 본문 주입)를 재 둔다 |
| 다중 에이전트 비용 | (b) 주의 | 다중 에이전트는 채팅의 약 15배 토큰. 코딩처럼 맥락을 공유하는 일에는 잘 안 맞는다(engineering 2025-06-13). 에이전트 팀은 약 7배(costs) | 이번 세션도 외부 조사 4갈래를 병렬로 돌림. 감사 5관점 분할 계획 | 병렬은 "독립적인 일"일 때만 이득이다. 관점별 감사는 같은 diff 를 다섯 번 읽으므로 diff 크기 임계 아래에서는 단일 리뷰어 하나로 시작한다 |
| effort | (b) 검토 | 기본은 medium, 놓치기 쉬운 경우에만 high/xhigh(best-practices). `CLAUDE_CODE_SUBAGENT_EFFORT`(2.1.316) | `modelSettings.claude-opus-5-5.effortLevel: high` 상시 | 사용자 선택이므로 제안만 한다. `/usage` 권고 행(effort 관련 `f` 수정)이 뜨는지 먼저 본다. 서브에이전트 effort 를 따로 낮추는 안을 검토한다 |
| 서브에이전트 TTL 5분 | (c) 검토 | `subagentPromptCacheTtl: 1h` 로 바꿀 수 있다(prompt-caching) | 기본 | 오래 도는 백그라운드 감사가 많다면 효과가 있을 수 있다 [추정]. `/usage` 의 cache miss 권고를 보고 정한다 |

### 2.6 세션 수명·compact·기억

| 항목 | 분류 | 공식 근거 | 우리 상태 | 판단·권고 |
|---|---|---|---|---|
| compact 인자를 매번 손으로 (.claude/audit/10 A) | (c) | 저장소 루트 CLAUDE.md 의 `# Compact instructions` 절, `/compact <focus>`, `/rewind` → "Summarize from here", `/autocompact`(context-window, costs) | `/checkpoint` 스킬과 % 주입 훅을 계획 중 | **새 스킬을 만들기 전에** 저장소별 CLAUDE.md 에 Compact instructions 3~5줄("잊지 말 것: 결정, 실측 수치, 열린 todo, 사용자 정정")을 넣는 것이 공식 해법이고 비용이 0 이다. % 확인은 statusline 의 context 필드로 상시 보인다(costs "configure your status line") |
| idle compaction | (c) 점검 | 1시간 캐시에서 200K 넘은 세션은 놀려 두면 자동 요약(2.1.314 확대). `idleCompaction` | 이 사용자 세션은 대부분 200K 초과(.claude/audit/18) | 점심 뒤에 "요약본에서 이어가는" 일이 사용자 모르게 일어난다. 사용자가 compact 시점을 직접 다루고 싶어 하므로 `idleCompaction` 을 켤지 끌지 명시적으로 정하게 한다 |
| session-log 플러그인 | (d) | 공식에는 auto memory, `/recap`, PostCompact 요약, `/rename`+`--resume`, `/insights` 가 있다. "structured note-taking"은 공식 기법이다(engineering 2025-09-29) | haiku 요약 + 원문 기계 대조, 외부 저장, `/session-import` | 저장소 밖에 검증된 기록을 남기는 것은 공식에 없는 기능이라 독자 판단으로 정당하다. 단 겹치는 공식 기능과 역할을 문서로 나눈다(auto memory=교정·선호, session-log=작업 이력). 백그라운드 요약 비용은 `/usage` 귀속에 잡히지 않을 가능성이 높다 [추정: `/usage` 는 로컬 세션 기록으로 계산하고 워커는 `--no-session-persistence` 로 돈다] → 자체 cost_usd 집계를 유지한다 |
| auto memory | (a) | Claude 5 글: "Memory in CLAUDE.md → auto memory". MEMORY.md 200줄/25KB | 사용자 memory 를 색인 1줄씩 운용(MEMORY.md) | 공식 권장 형태(색인+토픽 파일)와 같다 |
| 저장소 사이 소통: handoff/·HUMAN_TODO | (c) 검토 | cross-session messaging: 실행 중인 다른 세션에 메시지 전달. 대기 중 수신은 `crossSessionInbound: hold`(features-overview, costs) | 살아 있는 세션이 있으면 `.claude/handoff/<repo>.md` 문서로 인계 | 영속 기록으로서 handoff 문서는 계속 필요하다. "지금 돌고 있는 quad 세션에 알리기"는 공식 메시징으로 대체할 수 있다. 세부 동작은 읽지 않았다 [미확인] |

### 2.7 진단·측정

| 공식 도구 | 하는 일 [원문] | 우리 대응물 | 분류 | 권고 |
|---|---|---|---|---|
| `/context all` | 실제 로드 항목과 크기 | PLAN 검증 루프에 있음 | (c) 미실행 | apply 전후로 잰다 |
| `/doctor` | CLAUDE.md 에서 코드로 알 수 있는 내용 삭감 제안, 쓰지 않는 확장, 스킬 목록 비용, 설정 오류 | harness-doctor LOAD-/SET- | (b) 중복 | 공식이 하는 부분은 공식에 맡긴다 |
| `/doctor prompt-audit` | 옛 모델용 지시, 없는 파일 참조, 파일 사이 상충(rules·skills·agents 포함) | harness-doctor STALE-/RULE-DUP | (b) 중복 | 같음. harness-doctor 는 "저장소 사이 표류(DRIFT), 세션·worktree, 툴킷 툴체인, D-xx 결정 대조"처럼 공식이 못 하는 (d) 영역에 집중시키면 유지 부담이 준다 |
| `/skill-doctor` | 스킬별 비용과 사용 빈도, 한 번도 안 불린 스킬 | 없음 | (c) | luau-kb 12개 중 실제로 불리는 것을 1~2주 뒤에 확인한다 |
| `claude plugin details` | 플러그인 상시·호출 시 토큰 | 없음 | (c) | luau-kb, session-log 에 돌린다 |
| `claude plugin eval` / skill-creator | 트리거율, with/without 비교, 블라인드 A/B | 없음(스니펫은 지식 검증) | (c) | 겹치는 스킬 쌍부터 |
| `claude plugin validate` | frontmatter 와 플러그인 스키마 | scan SKILL- 일부 | (b) 일부 중복 | validate 를 scan 에서 불러 쓰거나 대체한다 |
| `/insights` | 세션 마찰 분석 보고서 | .claude/audit/10 수작업 채굴 | (c) | 다음 채굴은 `/insights` 를 먼저 돌리고 빠진 것만 수작업으로 |
| `/usage` 귀속·권고 | 스킬·서브에이전트·플러그인·MCP 별 사용 비율, 10% 넘는 패턴 권고, `f` 로 적용 | 사용자가 `/usage` 를 142회 열었음(.claude/audit/10) | (c) 부분 | 권고 행을 하네스 결정의 근거로 기록한다 |
| InstructionsLoaded 훅 | rule·CLAUDE.md 로드 사유(`path_glob_match`, `compact` 등) 기록 | rule 로드를 손으로 실측(PLAN 3.5) | (c) | 로그 전용 훅으로 두면 "rule 이 실제로 언제 붙나"를 상시 관찰할 수 있다 |

### 2.8 공식이 다루지 않는 영역(독자 판단 목록)

| 항목 | 분류 | 외부자 의견 |
|---|---|---|
| 여러 세션이 동시에 도는 환경에서 다른 저장소 수정 금지, `pgrep -x` 로 세션 확인 | (d) | 공식은 worktree 격리만 말한다. 1인 다세션 운용에서 꼭 필요한 안전장치다 |
| decisions D-xx(규약 합의안), "사용자 선택은 제안만" | (d) | 공식 "상충 지시를 지우라"를 사람의 결정 절차로 구현한 것이다. 좋다 |
| harness.env 로 환경값 분리, 툴킷 무관 코어 | (d) | 이식성 목표에 맞다. 다만 현재 사용자는 1명·1 sandbox 이므로 추상화 비용(설정 해석기, 툴킷 감지)이 이득보다 앞서지 않는지 주기적으로 본다 |
| 한국어 문서 + 영어 rule/훅 본문 | (d) | 공식은 언어를 말하지 않는다. 한국어 토큰 비용을 근거로 한 합리적 선택이다. `language: 한국어` 설정 사용은 (a) |
| coderag(문서 검색 CLI), taxonomy, frontmatter | (d)/(a) | "just-in-time retrieval"(engineering 2025-09-29)과 "MCP 보다 CLI 가 컨텍스트 효율적"(costs)에 부합한다. 출력은 tools 글의 원칙(고신호, 페이지네이션, concise/detailed)에 맞춰 설계되어 있는지 확인한다 [미확인] |
| AGENTS.md(luau-kb), GEMINI.md(stl-luau) | (c) 일부 | 공식은 이제 AGENTS.md 를 읽는다. 같은 내용을 두 파일에 쓰는 대신 `CLAUDE.md` 에서 `@AGENTS.md` import 를 권한다. harness-doctor DRIFT 검사 대상이 줄어든다 |

---

## 3. 외부자 권고 (우선순위)

1. **측정부터.** 정본을 apply 하기 전후로 다음을 기록한다. 이후 모든 추가(훅, 스킬, 규칙)는 이 수치를 움직이는지로 판단한다.
   - `/context all`
   - `/doctor`
   - `/skill-doctor`
   - `claude plugin details`
   - `/usage` 권고 행
   - (공식 근거: best-practices "keep the enforced set small", Claude 5 글의 subtraction)
2. **luau-kb 를 로컬 마켓 플러그인으로 설치하고 Luau 저장소에서만 켠다.** LSP 를 얻고 웹 저장소의 상시 비용을 없앤다. MANIFEST 의 스킬 링크 12줄은 지운다.
3. **트리거 eval.** 겹치는 스킬 쌍마다 should/should-not 프롬프트 eval 을 만든다. 그다음 설명을 "무엇+언제" 두 문장으로 줄인다.
4. **compact 고충은 Compact instructions 로 먼저.** 저장소별 CLAUDE.md 에 `# Compact instructions` 를 넣고 `idleCompaction` 정책을 정한다. `/checkpoint` 스킬과 % 훅은 그 뒤에도 필요할 때만 만든다.
5. **Luau 저장소에 Stop 훅으로 검증을 강제한다**(`luau-analyze`/stylua check). 공식이 "가장 유용한 한 줄"로 꼽는 것이 검증 명령이다.
6. **권위 문구 낮추기(제안).**
   - CLAUDE.md "훅 메시지" 절의 "반드시"를 사실 알림 톤으로 바꾼다.
   - 꼭 묻게 할 것은 PreToolUse `ask` 로 하네스가 묻게 한다.
   - code-structure 수치 규칙은 축소안을 A/B 로 잰다(D-13 사용자 결정이므로 제안만).
7. **harness-doctor 범위 재조정.** 공식 `/doctor`·`prompt-audit`·`plugin validate` 와 겹치는 검사는 위임하고, 다저장소·세션·worktree·표류·결정 대조에 집중한다.
8. **훅 추가 전 지연 측정.** session-log PostToolUse(모든 도구)와 .claude/audit/18 제안 훅 4개를 들이기 전에 `--debug` 로 훅별 시간을 잰다.

---

## 4. 미확인

- 스킬 frontmatter `paths` 가 **목록 노출**(설명 상시 비용)까지 줄이는지. skills 문서는 "자동 로드 범위"만 말한다(.claude/audit/01 미확인 그대로).
- `skillOverrides` 를 프로젝트 settings 에 두면 사용자 레벨 링크 스킬에 적용되는지. 문서는 "플러그인 스킬에는 적용되지 않는다"만 말한다.
- `~/.claude/skills/luau-kb` 처럼 **심볼릭 링크로 둔 skills-dir 플러그인**이 `@skills-dir` 로 인식되는지. 문서는 "saved a plugin directory"라고만 쓴다.
- hooks 문서의 "factual statements rather than imperative" 문단 원문. WebFetch 요약으로만 확인했고, 두 번째 구간에서 다시 찾지 못했다.
- plugin-evals 본문(grader 종류 전체, 비용). 머리말만 읽었다.
- cross-session messaging 의 세부 동작.
- 훅 다수가 도구 호출 지연에 주는 실제 영향.
- 한국어 설명 6,900자의 정확한 토큰 수. `claude plugin details` 를 돌리지 않았다(로컬 실행 경계).

## 5. 출처 (조회 2026-11-10)

공식 문서 (code.claude.com/docs/en/…)
- best-practices: https://code.claude.com/docs/en/best-practices.md
- memory: https://code.claude.com/docs/en/memory.md
- skills: https://code.claude.com/docs/en/skills.md
- sub-agents: https://code.claude.com/docs/en/sub-agents.md
- hooks: https://code.claude.com/docs/en/hooks.md
- features-overview: https://code.claude.com/docs/en/features-overview.md
- context-window: https://code.claude.com/docs/en/context-window.md
- costs: https://code.claude.com/docs/en/costs.md
- prompt-caching: https://code.claude.com/docs/en/prompt-caching.md
- plugins/loading: https://code.claude.com/docs/en/plugins/loading.md
- plugins/measure: https://code.claude.com/docs/en/plugins/measure.md
- plugin-evals: https://code.claude.com/docs/en/plugin-evals.md
- debug-your-config: https://code.claude.com/docs/en/debug-your-config.md
- changelog(2.1.311~2.1.322 구간): https://code.claude.com/docs/en/changelog.md

스킬 사양
- Skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Agent Skills 사양: https://agentskills.io/specification

블로그
- "The new rules of context engineering for Claude 5 generation models", 2026-07-24: https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models (claude.dev 로 308 리다이렉트)
- "Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents", 2026-06-18: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more
- "Effective context engineering for AI agents", 2025-09-29: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- "Writing effective tools for agents — with agents", 2025-09-11: https://www.anthropic.com/engineering/writing-tools-for-agents
- "How we built our multi-agent research system", 2025-06-13: https://www.anthropic.com/engineering/multi-agent-research-system
- "Equipping agents for the real world with Agent Skills", 2025-10-16: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills (검색 결과로 날짜만 확인 [요약확인])
