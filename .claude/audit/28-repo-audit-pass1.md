# .claude/audit/28 claude-doctor 저장소 감사 1패스: 목록과 측정

범위: 읽기 전용 측정. 판단과 개선안은 2패스(다른 검토자)가 한다. 기준 시점은 작업 트리 HEAD 6ca93be + 다른 에이전트가 고치는 중인 변경(conventions 플러그인, home/.claude/rules/comments.md, PLAN.md, README.md)이다. 그 파일들의 크기는 측정 시각의 값이라 바뀔 수 있다.

## 0. 토큰 측정 방법

- `ANTHROPIC_API_KEY` 없음. 대신 `claude -p ok --model sonnet --system-prompt <파일 내용> --tools "" --setting-sources ""` 의 `usage.input_tokens` 에서 빈 프롬프트 기준선(509)을 빼서 파일별 **실측**을 얻었다(호출당 약 $0.004~0.03, 합계 약 $0.3 미만).
- 실측 21개로 최소제곱 보정한 **추정식**: 토큰 = 1.72 x 한글 글자 수 + 0.376 x 그 밖의 글자 수. 실측 15개 대비 오차 약 +-8% (최대 약 +-12%: 목록 문자열 911 실측 vs 1088 추정, HUMAN_TODO 3162 vs 2820). 아래 표에서 **실측**은 직접 잰 것, **추정**은 식으로 구한 것.
- 한글 문서는 바이트 기준 약 0.47 토큰/B, 영어 문서는 약 0.33 토큰/B.
- 세션 시스템 프롬프트와 내장 도구 정의는 이 저장소가 제어하지 않으므로 뺐다.

## 1. 자동으로 맥락에 실리는 것과 비용

공식 문서 근거: `/tmp/ccdocs/memory.md`(CLAUDE.md 와 MEMORY.md 앞 200줄/25KB 는 매 세션, `@import` 는 같은 파일과 함께 로드되어 비용이 줄지 않음, `paths` 있는 rules 는 해당 파일을 Read/Write 할 때), `skills.md`(`disable-model-invocation: true` 스킬은 설명도 맥락에 없음, 목록은 설명+when_to_use 를 1,536자로 자르고 예산은 컨텍스트 창의 1%).

**이 저장소에는 프로젝트 `CLAUDE.md` 도, `.claude/rules/` 도 없다.** `.claude/` 에는 `settings.json`(81B) 하나뿐이다. 그래서 "프로젝트 CLAUDE.md @import" 항목은 해당 없음이다.

### 1-1. 매 세션 로드 (고정 비용)

실제로 지금 실리는 것은 설치된 `~/.claude`(`/code/.claude`) 기준이고, 저장소 정본(`home/`)을 apply 하면 바뀐다. 두 열을 모두 적는다.

| 항목 | 로드 시점 | 바이트 | 토큰 | 구분 |
|---|---|---|---|---|
| 설치된 `~/.claude/CLAUDE.md` | 매 세션 | 5,764 (49줄) | 2,773 | 실측 |
| 정본 `home/.claude/CLAUDE.md` (apply 후 대체) | 매 세션 | 7,106 (50줄) | 3,389 | 실측 |
| 메모리 `MEMORY.md` (인덱스만, 8개 파일 중) | 매 세션 | 1,354 (8줄) | 605 | 실측 |
| 모델이 부를 수 있는 스킬 설명 목록 6개: q:checkpoint, q:import, fresh-advisor, inherit-advisor, agent-docs, comments | 매 세션 | 2,806 | 911 | 실측(정본 기준 합본. 설치본은 옛 second-opinion 이름이고 conventions 스킬이 아직 없어 더 작다) |
| `qwreey-advisor:reviewer` 에이전트 설명 (Agent 도구 설명에 들어감) | 매 세션 | 433 | 157 | 실측 |
| 사용자 전용 스킬 5개(q:start, doctor, away, back 등) 설명 | 안 실림 (`disable-model-invocation: true`) | - | 0 | 문서 근거 |
| 훅 고정 문구 | 안 실림(아래 1-4) | - | 0 | - |

**매 세션 고정 합계**
- 지금 설치된 상태: 약 4,450 토큰(2,773 + 605 + 911 + 157, 목록은 정본 값을 상한으로 사용). 실측 합.
- 정본을 apply 한 뒤: 약 5,060 토큰(3,389 + 605 + 911 + 157). 실측 합.
- 이 중 한글 CLAUDE.md 가 55~67%, 메모리 인덱스가 12%.
- 참고: PLAN §1·P1 은 사용자 CLAUDE.md 를 "40줄", "30줄 이내" 로 적었다. 실제는 49~50줄.
- 설치된 `~/.claude/CLAUDE.md` 와 정본은 이미 다르다(차이 1,342B: quietcode-claude 행, 메모리 위치 절, second-opinion 용어 -> 정본이 앞섬). 아직 apply 전이다.

### 1-2. 경로 조건부 로드 (해당 파일을 Read/Write 할 때만)

| 항목 | paths | 바이트 | 토큰 | 구분 |
|---|---|---|---|---|
| `home/.claude/rules/code-structure.md` | luau, lua, ts, tsx, js, jsx, mjs, astro, rs, py, go, kt | 2,675 (55줄) | 1,025 | 실측 |
| `home/.claude/rules/comments.md` (다른 에이전트가 수정 중, 측정 시점 값) | 같은 확장자 | 1,054 (10줄) | 431 | 실측 |
| `home/.claude/rules/agent-docs.md` | CLAUDE.md, SKILL.md, agents/*.md, .claude/rules/*.md, skills/**/*.md | 842 (9줄) | 324 | 실측 |
| `home/.claude/rules/memory.md` | MEMORY.md, memory/*.md | 1,432 (19줄) | 514 | 실측 |
| `home/.claude/rules/web-security.md` | ts, tsx, js, jsx, mjs 등 | 1,949 (29줄) | 800 | 실측 |
| 설치본 `luau-core.md` (luau-kb 심볼릭 링크) | `**/*.luau` | 6,816 | 2,614 | 실측 |

이 저장소 작업(py, sh, md, json 위주)에서 한 번이라도 .py 를 읽으면 code-structure + comments = 약 1,450 토큰이 추가된다. SKILL.md 나 rules 를 열면 agent-docs 324 가 추가된다. 설치본 `comments.md`/`code-structure.md` 는 옛 버전(각 2,676B, 2,713B)이라 .py 에는 안 걸린다. 이 열은 apply 전 현재와 apply 후가 다르다.

### 1-3. 호출 시 로드 (스킬 본문, 참조)

| 항목 | 바이트 | 토큰 | 구분 |
|---|---|---|---|
| q:start SKILL.md | 8,492 | 3,474 | 실측 |
| qwreey-conventions:comments SKILL.md (수정 중) | 8,637 | 3,075 | 실측 |
| q:doctor SKILL.md | 7,154 | 2,958 | 실측 |
| qwreey-advisor:fresh-advisor | 6,333 | 2,315 | 실측 |
| qwreey-conventions:agent-docs | 5,508 | 2,080 | 추정 |
| qwreey-advisor:inherit-advisor | 4,006 | 1,524 | 추정 |
| q:away / import / checkpoint / back | 4,055 / 2,254 / 1,786 / 954 | 1,659 / 849 / 682 / 363 | 추정 |
| reviewer 에이전트 본문 (서브에이전트 시스템 프롬프트) | 4,866 | 1,831 | 추정 |
| q:doctor references 11개 | 59,803 | 약 24,000 | 추정(필요한 것만 읽음) |
| q:start references 18개 | 65,544 | 약 27,000 | 추정(필요한 것만 읽음) |

문서 근거: 압축 뒤 호출된 스킬 본문은 스킬당 5,000 토큰, 합계 25,000 토큰까지 재주입(`context-window.md`). 위 본문은 모두 한도 이내.

### 1-4. 훅이 넣는 문구

고정 문구는 없다. 전부 이벤트 조건부 `additionalContext`/`systemMessage` 다. 이번 세션에서 본 것으로 대표값을 잡으면 알림 1건 약 70~120 토큰(bash-bypass-reminder 는 경고형 100토큰대, 정보형 70토큰대). 세션당 같은 범주 1회 dedup 이라 상한은 훅 수 x 범주 수. 별도 큰 문구는 q 플러그인 SessionStart 인계(`SESSION_LOG_HANDOVER_CHARS` 기본 800자, 이전 세션 기록이 있을 때만)와 PreCompact 상기.
- 훅 설정 자체(`settings.json` 훅 목록)는 모델 맥락에 실리지 않는다.
- `home/.claude/HOOK-MESSAGES.md` (7,824B, 추정 3,800 토큰)는 MANIFEST 에 없고 어느 곳에서도 자동 로드되지 않는다(문서 전용).

### 1-5. 참고: 설치 상태와 저장소 상태의 어긋남

- 설치된 `~/.claude/settings.json` 은 아직 `second-opinion@claude-doctor-market` 을 켜고 옛 `comment-hygiene` 훅을 부른다(0005 마이그레이션 미적용). 설치된 플러그인 목록도 `second-opinion`, `q` 둘뿐이다.
- 설치된 rules 에 `agent-docs.md` 가 없다.
- MEMORY.md 인덱스에 없는 메모리 파일이 있다: `review-is-model-side.md` (디스크 8개, 인덱스 7항목).

## 2. 자동으로 실리지 않지만 에이전트가 자주 읽는 큰 문서

최상위에 `TODO.md` 는 **없다**(과거 서브에이전트 프롬프트 4건이 "TODO.md 를 읽으라"고 지시했다. 아래 2-2).

### 2-1. 크기 (md 기준, 토큰은 추정)

| 문서 | 바이트 | 줄 | 토큰 |
|---|---|---|---|
| .claude/audit/09-other-knowledge-mine.md | 166,004 | 647 | 76,300 |
| .claude/audit/18-second-opinion.md | 88,884 | 795 | 43,900 |
| .claude/audit/08-quad-knowledge-mine.md | 93,386 | 252 | 43,000 |
| .claude/audit/16-marketplace.md | 93,058 | 770 | 40,400 |
| .claude/audit/04-other-projects.md | 54,226 | 543 | 25,300 |
| .claude/audit/19-external/02-community.md | 44,520 | 399 | 21,500 |
| .claude/audit/24-skill-audit.md | 43,421 | 321 | 21,000 |
| .claude/audit/19-external/03, 01, 05(knowledge-map), 22, 21 | 37~41K 각 | 212~495 | 18,000~19,500 |
| PLAN.md | 15,081 | 178 | 7,173 (실측) |
| README.md | 6,787 | 54 | 3,398 (실측) |
| HUMAN_TODO.md | 6,091 | 67 | 3,162 (실측) |
| .claude/archive/research/drafts/session-log/DESIGN.md | 25,069 | 274 | 12,000 |
| .claude/handoff/quad.md | 18,383 | 98 | 8,700 |

폴더별 md 합계(추정):

| 폴더 | md 수 | 바이트 | 줄 | 토큰 |
|---|---|---|---|---|
| audit/ | 52 | 1,235,764 | 9,497 | 580,000 |
| drafts/ | 48 (전체 파일 109) | 423,958 | 4,881 | 202,000 |
| plugins/q | 41 | 165,806 | 2,201 | 79,000 |
| decisions/ | 14 | 82,310 | 986 | 39,800 |
| handoff/ | 19 | 74,717 | 529 | 35,200 |
| plugins/qwreey-advisor | 9 | 34,199 | 344 | 14,800 |
| 루트(PLAN, README, HUMAN_TODO) | 3 | 27,959 | 299 | 13,200 |
| home/ | 7 | 23,038 | 244 | 10,400 |
| plugins/qwreey-conventions | 3 | 19,736 | 238 | 8,100 |
| intake/ | 1 | 5,615 | 64 | 2,700 |

`audit/` 만 저장소 md 의 약 60%(바이트). 이 상위 문서 몇 개를 통째로 읽으면 한 번에 4만~7만 토큰이다.

### 2-2. 이 저장소 세션 기록에서 "먼저 읽으라" 고 준 문서

`~/.claude/projects/-code-Projects-claude-doctor/*.jsonl` 7개(176MB). 서브에이전트 프롬프트(Agent/Task 도구 입력)에서 "먼저/우선/반드시 읽" 류 지시와 함께 나온 문서 횟수:

| 문서 | 에이전트 프롬프트 | 사용자 프롬프트 |
|---|---|---|
| CLAUDE.md | 8 | 7 |
| PLAN.md | 7 | 1 |
| README.md | 5 | 2 |
| .claude/audit/06-docs-and-canon.md | 4 | 0 |
| .claude/audit/01-official-docs.md | 4 | 0 |
| TODO.md (없는 파일) | 4 | 1 |
| .claude/audit/05-luau-knowledge-map.md | 3 | 0 |
| HUMAN_TODO.md | 2 | 1 |
| .claude/base/decisions/README.md | 2 | 1 |
| .claude/audit/04, .claude/audit/10, .claude/audit/17, drafts/session-log, .claude/research/drafts/coderag | 각 2 | - |

Read 도구로 실제 연 상위: `tools/home-sync.sh` 4, `harness-status.py` 3, luau-kb README/AGENTS 각 3, `home/.claude/CLAUDE.md` 2, `PLAN.md` 1. (PLAN.md 는 지시는 많이 받지만 이 세션들에서 Read 는 1회. 다른 경로의 Bash cat 은 세지 않았다.)

## 3. 구조

### 3-1. 최상위 폴더 (git 추적 파일 기준)

| 폴더 | 목적 | 파일 | 바이트 |
|---|---|---|---|
| `audit/` | 조사·감사 보고서(01~27, 19-external, 25·26 토론, drafts) | 55 | 1,240,150 |
| `drafts/` | 설치 전 초안(agents, coderag, delegate, gaps, hooks, second-opinion, session-log, split-plans, style) | 109 | 614,820 |
| `plugins/` | q(41 md 포함), qwreey-advisor, qwreey-conventions | 95 | 561,393 |
| `home/` | `~/.claude` 정본, settings-migrations(0001, 0002, 0004, 0005) | 28 | 207,721 |
| `decisions/` | 규약 합의안 D-01~D-13 + README | 14 | 82,310 |
| `handoff/` | 다른 저장소 세션 인계(corrections 7, memory-* 7, 저장소별 5) | 19 | 74,717 |
| `tools/` | home-sync.sh, settings-migrate.py, tests | 3 | 34,634 |
| `intake/` | 반입 자리(README 만, 사본은 gitignore) | 1 | 5,615 |
| `.claude-plugin/` | 마켓 정의 | 1 | 1,543 |
| `.claude/` | settings.json 하나 | 1 | 81 |
| 루트 | PLAN 15K, README 6.8K, HUMAN_TODO 6.1K | 3 | 27,959 |

추적 파일 330개, 총 약 2.85MB. 큰 비-md 파일: `scan.py` 56KB(1,203줄), `conventions-check.py` 38KB(883줄), `subagent_ledger.py` 31KB(712줄).

### 3-2. 같은 목적이 두 곳에 있는 것

1. `.claude/archive/research/drafts/hooks/structure-reminder.py`(283줄) vs `home/.claude/hooks/structure-reminder.py`(405줄): 라이브 쪽이 확장됨. 둘의 diff 309줄. PLAN §3.5 P1 은 아직 "원본은 `drafts/hooks/`" 라고 적었다.
2. `drafts/session-log/{extract,summarize,verify}.py` vs `plugins/q/scripts/sllib/{extract,summarize,verify}.py`: 설계 초안이 플러그인으로 구현됨. `DESIGN.md` 25KB 는 `plugins/q/docs/session-log.md`(97줄)와 겹침.
3. `.claude/archive/research/drafts/second-opinion/home/*.fragment*` 2개 vs `plugins/qwreey-advisor`: 플러그인으로 옮겨 끝남.
4. `.claude/archive/research/drafts/style/`(88KB) vs 형제 저장소 `luau-kb/skills/luau-style` + `luau-kb/rules`: PLAN 3.6 은 ".claude/archive/research/drafts/style 에서 이동" 이라고 적었다. luau-kb 에 스킬이 이미 있다.
5. `home/.claude/rules/code-structure.md` vs `luau-kb/rules/code-structure.md`(sibling 존재): MANIFEST 는 `luau-core.md` 만 링크하고 code-structure 는 복사한다. 두 정본 후보.
6. `.claude/audit/drafts/skills/luau-*`(3) vs `.claude/archive/research/drafts/gaps`, luau-kb 스킬 `luau-types`, `luau-verify`, 그리고 `.claude/audit/drafts/snippet-harness/check_snippets.py` vs luau-kb 의 snippets 하네스.
7. 설치된 `~/.claude/CLAUDE.md` vs `home/.claude/CLAUDE.md`(1-5 참고)와 `.claude/handoff/memory-claude-doctor.md` vs 실제 memory 디렉터리: 같은 내용의 사본.

### 3-3. 다 끝났는데 남은 초안 (`drafts/`)

| 하위 | 파일 | 바이트 | 마지막 커밋 | 상태(추정 근거) |
|---|---|---|---|---|
| `second-opinion/` | 2 | 2,299 | 11-10 | 플러그인 qwreey-advisor 로 이동 완료 |
| `hooks/` | 2 | 24,573 | 11-10 | 라이브 훅이 대체(3-2 #1) |
| `session-log/` | 9 | 64,026 | 11-11 | 플러그인 q 가 구현. DESIGN 은 설계 근거로 남음 |
| `style/` | 11 | 88,225 | 11-10 | luau-kb 로 이동 여부 확인 필요 |
| `delegate/` | 16 | 113,015 | 11-10 | 시범 trial 기록 있음, 이관 여부 HUMAN_TODO 의존 |
| `agents/` | 11 | 71,589 | 11-11 | 진행 중으로 보임 |
| `gaps/` | 51 | 165,399 | 11-10 | luau-kb 증류 입력 |
| `coderag/` | 3 | 42,430 | 11-10 | coderag 설계 입력 |
| `split-plans/` | 3 | 39,408 | 11-10 | 다른 저장소 분리안, HUMAN_TODO 와 handoff 에 의존 |
| `distill-brief.md` | 1 | 3,856 | 11-10 | 확인 필요 |
| `.claude/audit/drafts/` | 6 | 8,277 | 11-10 | 확인 필요 |

끝났다고 볼 수 있는 후보: second-opinion, hooks, session-log(스크립트). 나머지는 상태 확인 필요(2패스 질문).

### 3-4. 빈 폴더

- `home/.claude/skills/` (빈 디렉터리, git 에는 안 보임. MANIFEST 에서 스킬은 q 플러그인으로 옮겼다는 README 서술과 일치하는 잔재).
- 그 밖에 추적 대상 빈 폴더 없음. `__pycache__` 5곳은 gitignore 로 제외.

### 3-5. 깨진 상대 링크 (md 안의 경로가 실제로 없는 것)

- 정식 마크다운 링크 `](...)`: 4건, 모두 오탐(표 내용, `skills` 앵커 단어, `path`, `…`). 실제 깨진 링크 0.
- 백틱 경로 참조 중 **현행 문서에서 실재하지 않는 것**: 2건 + 1건.
  - `README.md`, `intake/README.md` -> `audit/intake/` (폴더 아직 없음. 첫 반입 감사 때 생길 곳)
  - `.claude/base/decisions/D-10-error-handling.md` -> `tools/run_opt.sh` (존재하지 않음)
  - `plugins/q/skills/doctor/scripts/scan.py` 안의 `TODO.md` 참조(코드 쪽, 1건)
- 과거 기록(audit/, drafts/, handoff/) 안의 백틱 경로 중 없는 것: 약 67건(.claude/audit/18 11, .claude/audit/05 10, .claude/audit/16 6, .claude/audit/20 4 ...). 이동·삭제된 파일(`plugins/second-opinion/`, `home/CLAUDE.md.fragment.md`, `home/harness.env.fragment`, `tools/agy-delegate.sh`, `tools/roblox_docs.py`, `.claude/audit/mrow-spike/*` 등)과 날짜 접미 파일명. 이력이라 고치는 대상이 아닐 수 있다.
- 서브에이전트 프롬프트가 "TODO.md 를 읽으라" 고 한 것 4건(파일 없음).

### 3-6. 낡은 이름 (과거 기록 밖, audit/ drafts/ handoff/ 제외)

| 이름 | 남은 곳 | 판단 |
|---|---|---|
| `second-opinion` | qwreey-advisor 의 `hooks/second-opinion-nudge.py`, `tests/test-second-opinion-nudge.py`, README(6), 상태 경로 `claude-second-opinion`, hooks.json(4), 마이그레이션 0001·0005, HOOK-MESSAGES | 대부분 의도적(README 40행이 "상태 경로와 훅 파일 이름은 이어지게 둔다" 고 설명). 파일 이름만 아직 옛 것 |
| `harness-doctor` | q/skills/doctor 의 SKILL.md 제목, references 4파일, scan.py 2, toolkits 2, README 47행 | `/q:doctor (harness-doctor)` 병기. 이름 정리 안 됨 |
| `comment-hygiene` | README, HOOK-MESSAGES, qwreey-conventions README, 마이그레이션 0001·0005 | 대체 설명이거나 마이그레이션이라 정상. 단 설치된 settings 는 아직 이 훅을 부른다 |
| `conventions:` (옛 이름) | `q/skills/doctor/references/load-and-rules.md` 80행 1건 | 오탐 가능("rule ↔ conventions" 의미) |
| `q-ui` | 현행 파일에는 없음 | 정리됨(커밋 ce6e9d6 이 분리) |
| `TODO.md` | scan.py 1건 | 확인 필요 |

설치된 상태는 옛 이름이다: settings 의 `second-opinion@claude-doctor-market`, 설치된 플러그인 `second-opinion`, 설치된 CLAUDE.md 의 `second-opinion:audit`/`second-opinion:context`(이미 제거된 스킬 이름).

### 3-7. 추적되지 않는 큰 파일, q-ui node_modules

- 현재 `git status`: 수정 10개(PLAN, README, rules/comments, qwreey-conventions 6개 등) + 미추적 `.claude/audit/27-conventions-skill-audit.md`. 큰 미추적 파일 없음. gitignore 된 것은 `__pycache__` 와 `intake/*/`(현재 사본 없음).
- **`plugins/q-ui/node_modules` 삭제 표시의 정체**: `node_modules/typescript` 가 커밋 ce6e9d6(q-ui 를 quietcode-claude 로 분리하는 커밋)에서 **처음 추적에 들어갔다**(분리하면서 실수로 남은 것으로 보임). 커밋 6ca93be(이름 변경 커밋)가 `plugins/q-ui/node_modules` 135개 파일(442,356줄 삭제)을 함께 삭제했다. 따라서 지금은 HEAD 에서 이미 정리됐다(그 전 status 에서 D 로 보인 것). 이름 변경 커밋 메시지에는 이 삭제가 언급되지 않았다.
- 같은 사고 재발 방지: `.gitignore` 에 `node_modules/` 가 **없다**(`__pycache__/`, `*.pyc`, `*.bak-*`, `intake/*/` 만 있음).
- `.git` 16MB (느슨한 객체 1,528개, 팩 0). 히스토리에는 ce6e9d6 에 node_modules 약 14MB 가 남아 있다.

## 4. 문서끼리의 중복 (표본 9건)

| # | 내용 | 놓인 곳 |
|---|---|---|
| 1 | 형제 저장소 지도, 읽기 전용 원칙 | 설치본 `~/.claude/CLAUDE.md`, 정본 `home/.claude/CLAUDE.md`(두 벌이 다름), PLAN §1·P1 서술, README 설치 2단계(지도를 고치라는 지시) |
| 2 | 서브에이전트 비용 정책("알리고 줄 세운다") | `home/.claude/CLAUDE.md`, PLAN §3.8, 메모리 `model-usage-policy.md`, `plugins/q/skills/away/SKILL.md` + `references/rationale.md`, .claude/audit/21(37KB) |
| 3 | second opinion 운용(내장 advisor 는 사용자가 요청할 때만, fork 검토/리뷰어 검토 구분) | `home/.claude/CLAUDE.md` "코드 리뷰와 second opinion", PLAN §3.8, `plugins/qwreey-advisor/README.md`, 두 SKILL.md 설명, `docs/rationale-*.md`, .claude/audit/18(89KB), HOOK-MESSAGES |
| 4 | 플러그인 구성(q, qwreey-advisor, qwreey-conventions, luau-kb 가 각각 무엇인가) | README 표, PLAN §3.8, 각 `plugin.json` description, 각 플러그인 README, `plugins/q/docs/` |
| 5 | settings 는 복사가 아니라 마이그레이션으로 적용 | README 설치 4단계(장문), `home/MANIFEST` 머리, PLAN 3.5 ~/.claude 정본 관리, `tools/home-sync.sh` 도움말과 마이그레이션 파일들 |
| 6 | 메모리에만 있던 원칙을 저장소로 옮김 | PLAN §3.8 전체가 메모리 파일들(`model-usage-policy`, `propose-dont-overwrite...` 등)과 `.claude/handoff/memory-claude-doctor.md` 의 사본 (의도적 이동이나 둘 다 남음) |
| 7 | 다른 세션에 넘길 일 | HUMAN_TODO 의 "다른 세션에 넘길 것" 13항목 vs `.claude/handoff/*.md` 19개의 본문(항목 건수와 근거를 양쪽에 적음) |
| 8 | luau-kb 구조와 증류 계획 | PLAN §1 ②(스킬 목록 12개), §3.6, README 설치 5단계, `.claude/archive/research/drafts/gaps`, `.claude/archive/research/drafts/style`, 형제 저장소 luau-kb 자신의 README |
| 9 | coderag 지식 계층(global/pack/project) | PLAN §3.7, README 맨 끝 단락, `.claude/research/drafts/coderag/`, 홈 CLAUDE.md 지도 행 |

README 서술 오류: 설치 4단계 플러그인 항목에 같은 구절이 겹친다("`status`/`apply` 끝에는 `status`/`apply` 끝에 설치 안 된 것과 ...").
오래된 진술: PLAN 머리 "사용자 레벨이 비어 있다 `(검)`"(§0), "30줄 이내"(P1), `drafts/hooks` 원본(P1), HUMAN_TODO "현재 대기 중: luau-kb 스킬 링크 2개, CLAUDE.md 갱신(리뷰 시점, 모델 사용 규칙)" 은 0005 와 rules 변경 이후 사실과 다르다(대기 중인 것은 마이그레이션 0005, rules 3종, CLAUDE.md 정본 차이).

## 5. 이 저장소에 걸린 하네스 규칙의 자기 위반

방법: `conventions-check.py` 의 `doc_class`·`doc_check`·`invisible_lines` 를 직접 불러 전체 파일을 "모든 줄이 추가됨" 으로 돌렸다(스크립트는 /tmp 에, 저장소에는 쓰지 않음). 모델용 문서 = `CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`. 훅은 문서에서 `history marker` 와 `invisible character` 만 본다(주석용 non-keyboard symbol, escaped, language 범주는 코드 파일 전용이라 해당 없음). 저장소 설정 `.claude/conventions.json` 없음(기본값).

| 범위 | 파일 수 | history marker | invisible | 합 |
|---|---|---|---|---|
| 입구 문서, 라이브(home/rules + home/CLAUDE.md + 플러그인 SKILL/agents) | 22 (home 6, plugins 16) | 2 | 0 | 2 |
| references (플러그인 `skills/**/references`, 이력 허용 범위) | 30 | 17 | 0 | 17 |
| 초안 쪽(drafts/, .claude/audit/drafts/) 입구 | 20 | 41 | 0 | 41 |
| 초안 쪽 references | 6 | 1 | 0 | 1 |
| **전체** | 78 | **61** | **0** | **61** |

- 라이브 입구 2건은 둘 다 오탐 가능성이 높다: `home/.claude/CLAUDE.md` 49행 "사용자 결정과 그 원문 인용을 남긴다"(결정 문구가 지시 내용), `qwreey-advisor/skills/inherit-advisor/templates/fork-prompt.md` 15행 "most recently judged 'done'"(지시 내용).
- references 17건은 8곳이 한 줄씩 `audit/NN` 근거 인용(예: `start/references/concepts/*.md` 8파일 각 1건, 모두 "~ (claude-doctor .claude/audit/19-external/05 #2)" 류 꼬리). 규칙상 references 는 `audit/N 근거` 가 걸리는 범주다. 그리고 `away/rationale.md`, `start/rationale.md` 각 2건, `doctor/references/*` 5건.
- 초안 쪽 41건은 `.claude/research/drafts/delegate/skills/debate/SKILL.md` 14, `.claude/research/drafts/agents/README.md` 11, `.claude/research/drafts/delegate/skills/delegate/SKILL.md` 7, `debate/templates/ledger.md` 4 등. 설치 전 초안이라 라이브 영향은 없다.
- 범주별 합: history marker 61, invisible character 0.
- 코드 파일 주석 범주(non-keyboard symbol, escaped, language, invisible)는 이번 1패스에서 돌리지 않았다(요청 범위가 모델용 문서). 코드 쪽 측정은 2패스 질문으로 넘긴다.
- 다른 규칙의 자기 위반(보고만): `code-structure` 파일 길이 한도(경고 800줄) 초과 2건: `scan.py` 1,203줄, `conventions-check.py` 883줄(작업 중 structure-reminder 훅이 실제로 경고). `agent-docs` 규칙의 "입구 문서는 짧게" 기준으로는 `q:start`(120줄), `comments` 스킬(120줄)이 길다.

## 6. 2패스(판단·개선안)에서 다룰 질문

1. **고정 비용 예산.** 사용자 CLAUDE.md 가 설치본 2.8k, 정본 3.4k 토큰이고 PLAN 은 "40줄/30줄" 을 목표로 적었다. 어디까지를 상시 로드로 허용하고(예: 토큰 상한), 무엇을 rules(paths)나 스킬로 내릴 것인가? 한글이 토큰당 약 3배 비싼 점을 문서 언어 정책에 반영할 것인가?
2. **크기를 보이게 하는 방법.** "이 문서 하나가 N 토큰" 을 누가 어디서 보여 줄 것인가: `/q:doctor` 의 로드 비용 표, conventions 훅의 별도 범주(길이 경고), statusline, 커밋 시 점검? 오차 약 +-8% 의 추정식을 도구에 넣을지, 실측(API)만 쓸지.
3. **audit/ 처리.** 52개 md, 1.2MB(추정 58만 토큰)가 전부 활성 문서처럼 놓여 있다. 에이전트가 우연히 통째로 읽으면 4~7만 토큰이다. 인덱스/요약 1개 + 보관(archive) + coderag 색인으로 나눌지, 번호 규칙과 "읽기 전 확인" 신호를 둘지, 서브에이전트에게 "먼저 읽으라" 고 주는 목록을 어떻게 관리할지.
4. **상태가 끝난 초안 정리.** `drafts/{second-opinion, hooks, session-log, style}` 등 3-3 표에서 이관 완료 여부 확인, 삭제·보관·이동 기준(git 이력이 있으니 지워도 되는가), 그리고 이후 새 초안이 `drafts/` 에 쌓이지 않게 하는 규칙.
5. **PLAN.md / README / HUMAN_TODO 역할 분리.** PLAN 은 2026-11-10 계획과 이후 결정 기록이 섞여 있고 오래된 문장이 있다(0절, P1). 완료 항목은 어디로(커밋·ledger), 현재 상태는 어디에 한 곳만 둘 것인가. HUMAN_TODO 와 handoff 의 이중 기록(표본 7) 해소 방법. 최상위 `TODO.md` 를 만들 것인지(과거 프롬프트가 존재를 가정).
6. **중복 정본 정리.** 표본 1~9 중 정본 하나로 줄일 것(비용 정책, advisor 운용, 마이그레이션 설명)과 의도적 중복(메모리 -> 저장소 이동)의 구분. 특히 `home/.claude/CLAUDE.md` 와 PLAN §3.8, 메모리 파일의 관계.
7. **설치 상태와 정본의 어긋남.** 0005 적용 전이라 설치본에 옛 이름과 옛 훅이 남아 있고, 정본 CLAUDE.md 는 앞서 있다. apply 순서와 확인 방법, 이 어긋남 자체를 `/q:doctor` 가 잡는지.
8. **낡은 이름 정책.** `second-opinion-nudge.py`, `claude-second-opinion` 상태 경로, `harness-doctor` 제목처럼 "이어짐을 위해 남긴 이름" 과 "정리 누락" 의 구분. `/q:doctor` 에 낡은 이름 검사(현행 문서 대 과거 기록)를 넣을 것인가.
9. **저장소 위생 규칙.** `.gitignore` 에 `node_modules/` 가 없어 15MB 가 히스토리에 남았다(재작성할지 두는 것이 맞는지). 이름 변경 같은 큰 커밋에 숨은 삭제를 메시지에 쓰는 규칙. 빈 폴더 `home/.claude/skills/`.
10. **자기 위반 처리와 코드 범주.** 라이브 입구 2건의 오탐 보정(훅 패턴), references 17건의 `audit/N` 꼬리 처리(이력을 한 곳으로 모을지), 코드 주석 범주(1패스에서 미측정)의 측정. 파일 길이 초과 2건(scan.py, conventions-check.py)의 분리안. 이 저장소가 시험대라면 다른 저장소에 이식할 때 달라질 임계값(문서 길이, 토큰 한도)을 어디에 설정할지(`.claude/conventions.json`).
11. **coderag 연계.** audit 류 이력 문서를 coderag 의 어떤 계층(project/pack)으로 보내 상시 로드 없이 검색만 되게 하는 컨벤션(frontmatter, 요약 줄)을 둘지.
