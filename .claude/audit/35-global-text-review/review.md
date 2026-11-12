# 35. 오늘 바뀐 모델용 문구 검토 (2026-11-11)

범위: 253077f..9b1749f 에서 추가·변경된 스킬, 훅 문구, ambient, 플러그인 rules. 읽기 전용 검토, 코드로 재현한 것만 적음.
토큰 추정: 1.72 x 한글 + 0.376 x 그 밖의 글자(태그 포함).

집계: high 5, medium 8, low 9.

## high (모델이나 사용자를 잘못 이끔)

| # | 위치 | 문제 | 바꿀 문구 |
|---|---|---|---|
| H1 | plugins/q/skills/import/SKILL.md:11 | "no records home is set 이라 하면 묻고 저장한 뒤 re-run". 실제 `cmd_import`(cli.py:96-99)는 멈추지 않고 `.claude/records/` 로 복사하며 "보관 위치가 정해지지 않아 ... 를 쓴다" 만 출력한다. 묻고 다시 돌리면 이미 imported 라 "pending 없음", 파일은 원치 않은 `.claude/records/` 에 남는다. | 1, 2단계를 바꾼다: "1. Run `session-log home`. If it shows `(미설정...)`, ask the user once where records go (options: `docs/sessions/` team-visible, `.claude/records/` agents only, an existing history dir, or `session-log home --archive-only` to keep them outside the repo) and save it with `session-log home <path>`. 2. Run `session-log import` (fallback ...). It copies every pending record into the records home and marks it imported; pass rids from `session-log pending` to import only some." |
| H2 | plugins/qwreey-conventions/hooks/reply_language.py:239-240 | Stop block 사유에 예외가 없다. .claude/audit/34 L1: 사용자가 영어로 요청한 답도 한국어로 다시 썼고, 모델이 덧붙인 "(참고: 영어로 요청하셨지만...)" 를 막으려 "Do not mention" 을 넣었다. 그 결과 사용자 요청을 어긴 사실까지 숨긴다. 또 "the rewrite is all the user should see" 는 거짓(원 답은 화면에 남고 새 메시지가 이어짐, L1). "this notice" 만 금지해서 "한국어로 다시 적었습니다" 같은 언어 언급은 막지 못한다. | "Your last reply is not in %s. If the user asked for that reply in another language, write one short line in %s saying the text above is in that language as requested, and stop. Otherwise write the same reply again in %s, same content. Output only the rewritten reply: no preface or note about the language, the earlier version or this notice, and no apology." |
| H3 | plugins/qwreey-conventions/hooks/rules_inject.py:176 | "Follow them for this file." dedup 은 rule 이름 단위(claim, 208행)라 같은 회차에 같은 paths 의 다른 파일을 열어도 다시 주입되지 않는다. 모델이 rule 을 이 파일에만 적용할 수 있다. 또 "(same as .claude/rules with paths)" 는 이제 틀린 말: 플러그인 쪽은 절대 경로에 맞춰 작업 트리 밖(형제 저장소, ~/.claude)에서도 실린다(rule_matches 139-142). 지워도 행동이 안 바뀌는 문장이기도 하다. | "Path-scoped rules from the %s plugin, loaded because you opened %s. They apply to every file matching their paths for the rest of this session; they are not shown again." |
| H4 | home/.claude/HOOK-MESSAGES.md:58-61 | session-log "권장 배정" 이 코드와 반대: pending warn, 임계 넘으면 action. 코드(brief.py:140-154)는 home 있음 info(commit 직전이나 임계 초과면 warn), home 없고 쌓임 warn, action 없음("action 은 쓰지 않는다", 142행). "현재 배정" 표에 session-log 행이 하나도 없다. 23행 예시("기록 가져오기 action")도 낡음. | 58-62행을 표 행으로 바꾼다: `session-log` pending(home 있음) info, commit 직전·`SESSION_LOG_PENDING_STRONG_*` 초과 warn / home 없음+쌓임(`SESSION_LOG_HOME_NUDGE_*`) 위치 제안 warn / 요약 시작·완료 info / 요약 실패 warn / 인계 info / PreCompact 상기 warn / SessionStart 기록 안내 info / `records-read`(records_read.py) 스냅숏 경고·큰 기록 info. 23행 예시는 "인계 info 가 PreCompact warn 에 끌려 올라감" 으로. |
| H5 | plugins/q/skills/recall/SKILL.md:15 | "`session-log home` / the hook text give paths" 의 외부 저장소 경로를 `session-log home` 은 주지 않는다(cmd_home, cli.py:128-142 는 저장소 보관 폴더만). 저장소 경로는 `session-log status` 의 `store:` 줄(cli.py:170). haiku 브리프에 `<store records dir>` 를 채울 방법이 틀리게 적혔다. `<project-key>` 도 모델이 알 수 없다. | 1단계 앞에 "0. Run `session-log status` (store dir; records are in `<store>/records/`) and `session-log home` (repo records home). Put both paths in the brief." 그리고 브리프의 괄호를 "`grep -rn -i` over `<store>/records/` and `<repo records home>`" 로. |

## medium (모호하거나 토큰 낭비)

| # | 위치 | 문제 | 바꿀 문구 |
|---|---|---|---|
| M1 | reply_language.py:214-217 | "Before answering, ask" 는 action 이라 설치한 동료의 첫 요청을 매번(저장 전까지 세션마다) 질문으로 멈춘다. 첫 프롬프트의 문자 체계가 이미 강한 신호다. "already stated a language in this conversation" 은 세션 첫 프롬프트에서만 도는 알림이라 거의 해당이 없다. `/config` 에서 `language` 를 바꿀 수 있다는 말은 코드로 확인 못 함(미검증). | "No reply language is configured. If the user's message makes it clear (they write in it or name it), store it now with: %s, and tell them in one line that Claude Code's `language` setting can change it. Otherwise first ask in one short question which language to reply in, then store the answer with that command." (/config 언급은 확인 뒤 유지) |
| M2 | reply_language.py:309-310 | level warn 인데 본문이 "Do not mention this notice". ambient(context/ambient.md:3)와 HOOK-MESSAGES:20 은 warn 을 "한 줄 언급" 으로 정의해 서로 부딪힌다. | level 을 `info` 로 내리고 "From now on write all text to the user in %s, including short progress notes between tool calls." 또는 HOOK-MESSAGES 20행에 "알림이 언급하지 말라고 하면 한 줄 언급을 생략" 을 더한다(ambient 문구는 사용자 확정본이라 건드리지 않는 쪽). |
| M3 | plugins/q/skills/import/SKILL.md:3 | "before a commit" 은 모든 커밋 전에 스킬을 부른다. pending 이 있으면 커밋 훅이 이미 알린다(hook.py:150-156, REASONS["commit"]). | "Copy pending auto-summarized session records into this repo's records home, or dismiss them. Use when a session-log notice says records are pending (it also fires before a commit), or when the user asks to import or clean up session records." |
| M4 | plugins/q/skills/recall/SKILL.md:3 | 사용자는 한국어로 묻는데 트리거 문구가 영어뿐(advisor 스킬은 한국어 트리거를 단다). "without reading them in the main context" 는 구현 설명이라 트리거에 기여 없음. "why is X this way" 는 코드 읽기로 답할 질문까지 끈다. | "Find what earlier sessions discussed or decided, from the saved session records. Use for \"what did we decide before\", \"what problem did we have with X\", \"why did we choose X\", \"find the earlier discussion of Y\". Not for facts that git log or the current files answer. 전에 뭐라고 정했지, 예전 논의 찾기, 왜 이렇게 정했지." |
| M5 | plugins/q/skills/workspace/SKILL.md:20 | "set it in `~/.claude/harness.env`" 는 사용자 CLAUDE.md:3(home-sync 대상은 claude-doctor `home/` 에서 고친다; harness.env 는 MANIFEST:5) 과 충돌. | "If it says `HARNESS_WORKSPACE not configured`, tell the user to set it in harness.env (from claude-doctor: `home/.claude/harness.env`, then `home-sync.sh apply`); the map and the gate are off until then." |
| M6 | recall/SKILL.md:15 | "coderag global docs if available" 는 도구 이름이 없어 haiku 가 판단할 수 없다. | "If a coderag search tool is in your tools, search its global layer first; otherwise grep." |
| M7 | plugins/q/scripts/sllib/messages.py:154-157 (brief.py:154 경로) | home 없을 때 pending 문구는 "`session-log import` copies them into .claude/records/" 라 바로 돌리게 하고, import 스킬은 먼저 물으라 한다. H1 을 고치면 문구도 맞춘다. | home 이 None 일 때 where 를 바꾼다: "...pending import. No records home is set yet (import would use `.claude/records/`); see /q:import. `session-log dismiss <rid>...` drops them." |
| M8 | messages.py:184-187 (hook.py:127-128) | SessionStart(startup·resume·clear)마다 기록이 있으면 약 137토큰. q:recall 설명과 RECORD_READ 가 같은 말을 한다. | "Session records: %s. They are snapshots; look things up with /q:recall instead of reading them here." (약 70토큰) |

## low (문체)

| # | 위치 | 문제 | 바꿀 문구 |
|---|---|---|---|
| L1 | import/SKILL.md:6, recall/SKILL.md:6 | 제목의 em dash | `# /q:import - move ...`, `# /q:recall - look ...` |
| L2 | import/SKILL.md:12, messages.py:157 | `<rid…>` 줄임표 문자 | `<rid>...` |
| L3 | recall/SKILL.md:15, 19 | `id: …`, `(L…)` | `id: <id> · summary: <text> · note: L<a>–L<b>`(실제 기록 형식 그대로, `·` `–` 는 데이터라 유지), `(L<n>)` |
| L4 | messages.py:155 | "1 days", "oldest since" | `{oldest_days} day{'s' if oldest_days != 1 else ''}`, "oldest from {date}" |
| L5 | messages.py:191 (records_read.py:27) | Grep 은 path 가 디렉터리인데 "You read a session record" | "You read or searched session records. ..." |
| L6 | rules_inject.py:183 | 사용자는 "PreToolUse:Write hook error" 로 본다. "Do not mention this notice to the user" 는 동료가 오류를 물을 때 설명을 막는다. | "You need not mention this; if the user asks about the hook error, say a conventions rule was loaded first." |
| L7 | messages.py:86 | 주석 "pending warn(임계 넘으면 action)" 이 코드와 다름 | "pending info(commit 직전·임계 초과 warn), home 없음 위치 제안 warn" |
| L8 | plugins/qwreey-conventions/rules/agent-docs.md:3 | paths 가 `**/.claude/rules/*.md` 만 잡아 이제 rules 가 있는 `plugins/*/rules/*.md` 편집에는 agent-docs 가 안 실린다(문구 아님, frontmatter) | paths 에 `"**/plugins/*/rules/*.md"` 추가 |
| L9 | records_read.py:6, reply_language.py:15·48·88, messages.py:99 | 새 한국어 주석의 `·`, `→`(comments rule 위반, 모델용 영어 아님) | 쉼표, `->` |

## rules 가 주입으로 거짓이 된 문장
- 5개 본문 안에는 남은 것 없음(memory.md 끝 문장은 이미 지움). comments.md:9 의 "turn end hook" 은 Stop 의 conventions-check.py 로 맞음. code-structure.md:20 "never blocks" 는 structure-reminder.py:4 와 맞음.
- 주입 머리말의 "(same as .claude/rules with paths)" 는 거짓(H3).

## 토큰 비용

ambient(세션 시작마다, q 는 서브에이전트 시작마다도)

| 텍스트 | 토큰 | 비고 |
|---|---|---|
| plugins/q/context/ambient.md | 352 | SessionStart, SubagentStart(서브에이전트마다), 중간 켜짐 보충 |
| plugins/qwreey-advisor/context/ambient.md | 28 | 스킬 설명이 이미 "no one needs to ask" 라 삭제 시험에 걸릴 수 있음(측정 근거가 있으면 유지) |
| home/.claude/CLAUDE.md | 688 | |
| 스킬 설명(목록): recall / import / workspace | 119 / 79 / 155 | 매 세션 |
| 스킬 본문(로드 시): recall / import / workspace | 864 / 394 / 962(+map 출력) | |

훅 문구

| 문구 | 토큰 | 빈도 |
|---|---|---|
| ask-language (action) | 238 | 언어 미설정이면 세션 첫 프롬프트마다 |
| Stop block (action) | 97 | 이탈마다 1회(stop_hook_active 면 통과) |
| interim (warn) | 86 | 5호출 쿨다운 |
| long-turn (info) | 35 | 프롬프트당 도구 10, 25, 40... 회 |
| records hint (info) | 137 | 기록 있는 저장소의 SessionStart(compact 제외)마다 |
| RECORD_READ / LARGE (info) | 91 / 152 | (세션, agent, 회차)당 1회 / 큰 기록 통째 Read 마다 |
| pending / home 제안 | 156 / 232 | (세션, 회차, 트리거)당 1회 |

주입 rules: (session, agent_id 또는 main, compact 회차, rule) 마다 첫 Read·편집에서 1회. compact 뒤와 서브에이전트마다 다시 낸다. 경로는 절대 경로로 맞추므로 작업 트리 밖(node_modules, 형제 저장소)을 읽어도 실린다.

| rule | 토큰(wrap 포함) | 맞는 파일 |
|---|---|---|
| agent-docs | 240 | CLAUDE.md, SKILL.md, agents/*.md, .claude/rules/*.md, skills/**/*.md |
| code-structure | 898 | luau lua ts tsx js jsx mjs astro rs py go kt |
| comments | 403 | 위 + sh html htm |
| memory | 385 | MEMORY.md, memory/*.md, .claude/memory/** |
| web-security | 669 | ts tsx js jsx mjs cjs astro |

머리말 73(deny 는 102). 첫 .ts/.js: 73+898+403+669 = 약 2,040. 첫 .py: 약 1,370. 첫 SKILL.md: 약 313. deny 경로는 사유에 같은 본문을 싣고 재시도는 다시 싣지 않는다.

## 관찰(대상 밖)
- 이 검토 중 읽기 전용 `python3` heredoc 에 bash-bypass-reminder 가 "Rules that apply to files this command touches ... Read them first" 를 warn 으로 냈다. 읽기만 하는 명령에 warn 은 무겁다(HOOK-MESSAGES:33 배정).
