# 38 round1-Q: 기록 규약은 coderag 문서로 정의한다 (coderag 중심안)

입장: `.claude/` 기록은 coderag 문서다. 규약은 coderag 의 어휘(frontmatter 키, kind, status)로 정의하고, 지키는지는 coderag 의 `lint`·`stale`·`static-gen` 이 기계로 검사한다. 사람이 손으로 지키는 규약은 quad 와 stl-luau 에서 이미 실패했다(audit/36 §1.7: 이동이 수동, 배너 누적, 이중 상태). 사용자도 이 결합을 제안했다.
양보: 기록은 coderag 없이 평문 markdown 으로 읽혀야 한다. coderag 가 없는 기계에서는 검색·검사가 느려질 뿐, 읽기와 쓰기는 막히지 않아야 한다(§3.4).

## 0. 이번에 새로 잰 것 (/tmp/q38 사본, coderag 0.1.0 debug, CODERAG_CACHE=/tmp)
- **조용한 오분류**: `status: superseded by plan/a.md` 는 lint 를 통과한다(lint 가 첫 낱말만 본다, lib.rs:931). 그런데 색인에는 `active` 로 들어간다(core docs/mod.rs:164 는 값 전체를 정확히 비교한다). 그래서 기본 검색에 계속 나오고, static-gen 표에는 `base · active` 로 찍힌다. lint 를 통과한 문서가 엉뚱하게 처리되는 셈이다. 사용자가 말한 `superseded by X` 꼴을 지금 쓰면 바로 이렇게 된다.
- `landed in …`, `rejected by …; note` 는 lint 오류이고 색인에는 `active` 로 들어간다(audit/37 과 같은 결과).
- `.gitignore` 에 든 `.claude/sessions/` 도 색인된다. frontmatter 가 없는 기록은 `[unknown]` 이 된다(폴더로 kind 를 추론하지 않는다).
- `static-gen --dir .claude/base` 는 `.claude/.claude/base/README.md` 를 만든다. `--dir` 이 모듈 루트 기준이라서다. `--dry-run` 은 "바뀔 예정"이어도 rc=0 이라 검사기로 쓸 수 없다.
- claude-doctor 의 기록은 이미 반쯤 coderag 꼴이다. `.claude/sessions/*.md` 는 import 때 `title/description/keywords/kind: session/status: active/last_verified` frontmatter 를 받는다. frontmatter 가 있는 것은 drafts 51개 중 16개, audit 75개 중 4개다. decisions·handoff 에는 없다.
- coderag 플러그인은 사용자 settings 의 enabledPlugins 에 **없다**. 그래서 doc-locator 와 post-edit lint 훅이 지금은 돌지 않는다. 바이너리만 `target/debug` 에 있다.

## 1. 상태
- **위치: frontmatter `status:` 한 곳.** 본문 첫 줄에 같은 정보를 또 쓰지 않는다. 같은 상태를 두 곳에 두면 어긋난다(audit/36 quad "두 곳을 같이 고칠 것"). 평문 문제는 이렇게 푼다: frontmatter 는 파일 맨 위의 평범한 텍스트이고, GitHub 와 에디터에서 그대로 보인다. 그러니 "첫 줄에 보인다"는 요구를 이미 만족한다.
- **문법**: `status: <state> [in|by <target>] [; <note>]`. target 은 경로 또는 doc ID이고, 해석은 지금의 `superseded_by` 해석 순서(문서 폴더 → 루트 → 프로젝트 루트)를 그대로 쓴다. `superseded_by: X` 는 `superseded by X` 와 같다(하위 호환).
- **어휘 5개**: `active`(기본) · `landed in <결과물>` · `superseded by <대체 문서>` · `rejected [by <근거 문서>]` · `archived`. `active` 를 뺀 넷은 listed=false 이고, `--all` 로만 검색된다.
- **`paused` 는 두지 않는다.** 상태 축은 "이 기록이 지금도 유효한가"다. 멈춘 계획도 유효하므로 `active; paused until X` 처럼 note 로 쓴다. 어휘가 늘면 lint 와 표가 갈라진다.
- **기록류(session·audit)는 status 를 쓰지 않는다.** 이들은 시점 기록이라 "유효함"이라는 말이 맞지 않는다. 지금 session frontmatter 의 `status: active` 와 `last_verified` 는 오해를 부른다. 90일 뒤 stale 잡음이 될 날짜이기도 하다. 그래서 `date: YYYY-MM-DD`(기록 시점) 하나로 바꾼다. 파일 이름의 날짜 접두로 대신할 수 있다.
- **세션 snapshot 머리**: frontmatter(`kind: session`, `date`) 뒤에 지금의 2줄 blockquote(`> 세션 … 기록 · 기간 … ` / `> 그 시점의 스냅샷…`)를 유지한다. 사람이 읽을 때와 grep 으로 찾을 때 보이는 경고가 바로 이 두 줄이다. coderag 는 kind 와 date 로 나이를 표시한다(§3, C7).

## 2. 폴더
필수: `.claude/README.md`(폴더마다 한 줄), `base/`, `archive/`. 나머지는 처음 필요할 때 만든다. 각 폴더 정의는 한 줄이다.
- `plan/`: 지금 하는 일, 다음 일, 열린 결정. 작은 저장소는 `plan.md` 한 파일이어도 된다.
- `base/`: 확정된 결정과 프로젝트 전반의 배경. `.claude/` 안에서 충돌하면 이것이 이긴다.
- `research/`: 결정 전 조사와 시제품. 끝은 `landed in` 또는 `rejected` 다.
- `audit/`: 시점 측정과 리뷰. 결론과 재현 명령만 담고 원시 덤프는 넣지 않는다(§4).
- `handoff/`: 다른 저장소나 세션에 주고받는 인계. 처리되면 `archived` 다.
- `sessions/`: q:import 한 세션 기록(스냅샷).
- `archive/`: active 가 아니고 더 관리하지 않는 원문. 원래 폴더 구조를 유지한다(`archive/research/…`).
- `packs/<pack>/`: 이 저장소가 개발하는 도메인 팩의 bench·evals·decisions. 안에서 같은 폴더 이름을 쓴다.
- **`sessions` 를 유지한다.** records_home 이 이미 `.claude/sessions` 이고, 바꿀 쪽은 coderag 다. kind 를 폴더에서 추론할 때 복수형 별칭(`sessions→session`, `decisions→decision`, `reviews→review`)을 받게 한다(C2). frontmatter 의 `kind` 가 있으면 그것이 이긴다.
- **README 색인은 static-gen 마커 블록**이다. 블록 위에는 손으로 쓴 1-3줄(이 폴더에 무엇을 두는지)을 둔다. 생성된 표도 커밋해서 coderag 가 없어도 색인이 보이게 한다. 상태 열은 `landed → plugins/q/x.md` 처럼 target 까지 보여 준다.
- **`docs/`**: 사람을 위한 현재 사실(설치, 사용법, 구조 설명)만 둔다. 이유와 경위는 `.claude/` 에 두고 docs 가 그것을 인용하지 않는다. docs 는 공개할 때 `.claude/base` 에서 다시 쓴다.

## 3. coderag 결합
### 3.1 coderag 에 필요한 변경 (사용자 승인 뒤, coderag 저장소에서)
| # | 변경 | 위치 | 크기 |
|---|---|---|---|
| C1 | status 문법 파서: state·target·note 로 나눔, 5어휘, active 가 아니면 listed=false, `superseded_by` 와 같게 처리, target 이 없으면 stale. **§0 의 조용한 오분류 수정** | mdfm `KNOWN_STATUS`, `split_status` 재사용, core docs/mod.rs:164, index_md.rs 상태 열 | 작음 |
| C2 | 폴더로 kind 추론(문서 루트 아래 첫 조각, 복수형 별칭), `handoff` kind 추가 | mdfm 763행 대체값 | 작음 |
| C3 | frontmatter 없이 첫 줄만 `status: …` 인 옛 문서(drafts)를 읽기 전용으로 인식 | mdfm | 작음 |
| C4 | `.gitignore` 존중(git 저장소면 `git ls-files -co --exclude-standard` 로 열거), `respect_gitignore=false` 로 끌 수 있게 | walk_markdown | 중간 |
| C5 | `stale` 에 두 부류 추가: 끝났는데 archive 밖에 있는 문서, archive 후보(기록류이고 `date` 가 N일 지났고 활성 문서가 하나도 인용하지 않음). refs 그래프는 색인에 이미 있다 | core stale.rs | 중간 |
| C6 | `static-gen --check`(달라지면 rc=1, 색인 누락 검사를 겸함), `--dir` 을 프로젝트 기준 경로로도 받기 | core | 작음 |
| C7 | 검색 결과에 기록류의 나이 표시(`· 2026-11-10, 2일 전`). `date` 가 없으면 파일 이름 날짜 접두로. 기록류의 날짜 stale 은 끔 | search 출력, stale | 작음 |
| C8 | 암묵 설정의 기본 제외에 `skills agents rules hooks commands agent-memory` 추가(post-edit 훅의 제외 목록과 같게) | config | 작음 |
| 나중 | 본문 낱말 저가중치 색인. 세션·audit 은 본문이 핵심이다. 그때까지 recall 은 grep 을 두 번째 근거로 둔다 | | 큼 |

### 3.2 claude-doctor 에 남는 것
규약 문구(§5), `q:start` 뼈대, `q:import` 머리(2줄 경고), `records_read.py` 의 읽을 때 경고, 항상 로드 크기 예산, archive 이동 절차, 커밋할 때 알림 훅이 여기 남는다. 크기 예산은 CLAUDE.md `@import` 문제라 coderag 몫이 아니다. 이 부분은 P 의 평문안이 맞다.

### 3.3 recall 의 locate 단계와 색인 신선도
- recall 은 coderag 플러그인의 doc-locator 에 기대지 않는다. 플러그인이 꺼져 있어서다(§0). q 의 haiku 브리핑이 `$CODERAG_BIN search --abs --layer project …` 를 직접 쓴다(harness.env 에서 경로를 얻는다). 플러그인이 켜져 있으면 `coderag:doc-locator` 를 쓴다. 둘 다 결과는 `경로:L a-b ~토큰 — 근거` 형식이다.
- 신선도: recall 0단계에서 `coderag gen` 을 돌린다. 155항목에 0.03초라 recall 마다 돌려도 싸다. 캐시는 저장소 밖(`$XDG_CACHE_HOME/coderag/<repo-hash>`)에 둔다. 형제 저장소에도 쓰지 않고, `.coderag/` 잡음도 생기지 않는다. coderag M9-B(mtime 경고)가 들어오면 그것으로 바꾼다.

### 3.4 coderag 가 없을 때
frontmatter 는 평문이고, README 표는 커밋돼 있고, 2줄 경고는 본문에 있다. 그래서 읽기는 그대로 된다. recall 은 `grep -rn` 으로 돌아간다(지금 분기 유지). q:doctor 는 정규식 몇 줄로 최소 검사를 한다(active 가 아닌데 archive 밖, README 에 없는 파일). 규약이 coderag 에 의존하는 것은 **검사와 검색의 품질**이지, 기록의 존재가 아니다.

## 4. 자동화
- **쓸 때**: coderag post-edit 훅(플러그인을 켠 경우)이 `.claude/**/*.md` 를 lint 하고 `additionalContext` 로 알린다. C1 이 들어가기 전에는 landed·rejected 가 오탐이 되므로, C1 이 먼저다.
- **커밋할 때(q, info, 차단 없음)**: 커밋이 `.claude/` 를 건드리면 `stale` + `static-gen --check` 를 돌려 세 가지를 한 줄씩 알린다: README 낡음, 끝났는데 archive 밖, 활성 문서의 깨진 참조. 바이너리가 없으면 §3.4 의 최소 검사로 대신한다.
- **q:doctor**: 위 검사 전부, archive 후보 목록, 크기 예산(항상 로드 합계, audit 항목별 200KB와 폴더 합계).
- **옮기는 주체**: 백그라운드에서 저절로 옮기지 않는다. 대신 **status 를 바꾸는 커밋이 `git mv` 로 archive 이동까지 같이 하는 것**을 규약으로 한다. 에이전트가 그 자리에서 하고, 커밋 훅이 빠진 것을 알린다. archive 후보(C5)는 목록만 내고, 옮길지는 사용자에게 묻는다. git 이 있어서 되돌리기는 싸지만, 아무도 모르는 이동은 막는다.
- **audit 덤프 증가**: audit 문서는 결론, 수치, 재현 명령만 담는다. 원시 출력(트랜스크립트 재생, json, 로그)은 `audit/<n>/raw/`(gitignore)나 /tmp 에 둔다. quad 4,934파일·58MB 는 대부분 이런 덤프였다.
- **q:start 뼈대**: `.claude/README.md`(폴더 한 줄씩 + 마커), `base/README.md`, `archive/README.md`, `.claude/session-log.json`(`records_home: .claude/sessions`). C8 이 들어가면 `coderag.toml` 은 만들지 않는다. 기록이 `.claude/` 밖에 있을 때만 쓴다.

## 5. 규약 문구 (qwreey-conventions 스킬 `agent-records` 로 배포, coderag `docs-frontmatter` 는 키 참조만 남기고 이 스킬을 가리킴)
```markdown
---
name: agent-records
description: Layout, status and lifecycle of agent records under a repo's .claude/ (plan, base, research, audit, handoff, sessions, archive). Use when creating, finishing, moving or indexing a record, or when a coderag lint/stale notice names one.
---
# Agent records under .claude/
`.claude/` holds what agents decided and why, raw and as long as needed. Human docs go in `docs/` and state current facts only.

## Folders (create on first use; README.md, base/, archive/ always exist)
- `plan/` current and next work, open decisions (a single `plan.md` is fine)
- `base/` settled decisions and project-wide background; wins any conflict inside .claude/
- `research/` investigation before a decision; ends `landed` or `rejected`
- `audit/` point-in-time measurements and reviews: conclusions, numbers, reproduce command
- `handoff/` notes passed to or from another repo or session
- `sessions/` imported session records (snapshots)
- `archive/` originals no longer maintained, same subpath as before (`archive/research/x.md`)
- `packs/<pack>/` dev material for a domain pack in this repo, same folders inside
coderag infers `kind` from the folder; set `kind:` only to override.

## Frontmatter
Every new record starts with:
    ---
    title: <one line>
    description: <one line, <=200 chars, what a searcher needs to pick it>
    keywords: [<identifiers, ids, both languages>]
    status: active            # plan, base, research, handoff
    date: YYYY-MM-DD          # audit and sessions instead of status
    ---
Status grammar: `<state> [in|by <target>] [; <note>]`, one of
`active`, `landed in <path>`, `superseded by <path>`, `rejected [by <path>]`, `archived`.
Targets are paths or doc ids and must exist. Put status only here, not again in the body.
Sessions and audits are snapshots: no status; readers check them against current files and git log.

## Lifecycle
- When a record stops being active, change `status:` and `git mv` it under `archive/` in the same commit. Leave a one-line pointer only where an active doc linked it.
- Never edit an audit or session body after the fact; supersede it with a new record.
- Raw dumps (logs, json, replays) stay out of git: `audit/<n>/raw/` is ignored.
- Old records without frontmatter are not backfilled; the folder gives their kind.

## Indexes and checks
- Each folder README has 1-3 hand-written lines, then a `<!-- coderag:begin -->` block from `coderag static-gen`. Commit the generated table.
- After moving or finishing records run `coderag gen && coderag static-gen` (cache outside the repo).
- `coderag lint`, `coderag stale` and `/q:doctor` report broken refs, stale indexes, finished records outside archive/ and archive candidates. They never move files.
- Without coderag the files read as plain markdown; use `grep -rn` and keep the README tables by hand.

## Finding records
Search first (`coderag search --abs`, or /q:recall), then read only the returned line ranges. Never read whole session or audit records in the main session.
```

## 6. claude-doctor 재편 실험
- 0. 브랜치 `exp/records`. 선행 조건은 C1·C2·C6 이고, coderag 저장소에서 사용자 승인을 받은 뒤 진행한다. 승인이 없으면 `/tmp` 사본에서 패치한 바이너리로만 잰다.
- 1. **기준선(옮기기 전)**: 정답 위치가 정해진 recall 질문 10개(예: "D-04 근거", "luau-core 를 왜 옮겼나")를 고른다. 지금 방식인 grep locate 의 hit@5, 호출 수, 읽은 토큰을 잰다. 같은 질문을 `coderag.toml`(target 을 audit, decisions, drafts, handoff 로 지정하고 /tmp 에 둔다)로도 잰다. 이동 효과와 색인 효과를 따로 재기 위해서다.
- 2. **커밋 A**: `git mv` 만 한다. audit→`.claude/audit`, decisions→`.claude/base/decisions`, drafts 중 landed→`.claude/archive/drafts`, 나머지 drafts→`.claude/research`, handoff→`.claude/handoff`, PLAN.md→`.claude/plan/`. CLAUDE.md·HUMAN_TODO.md·README.md 는 루트에 남긴다.
- 3. **커밋 B**: 기계적인 경로 치환(옛→새 대응표 하나). 함께 고칠 곳은 web.py `PLUGINS_REF`, conventions.json exclude, conventions-check 정규식, records_home 후보, `.gitignore` 다(audit/36 §3).
- 4. **커밋 C**: 끝난 문서에만 frontmatter status 를 단다. 첫 줄 `status: landed in` 이 있는 drafts 는 지금 몇 개뿐이라(예: `drafts/second-opinion/README.md`) 폴더 README 와 머리줄로 하나씩 판정한다. audit 은 백필하지 않고 폴더로 kind 를 얻는다. 주의: drafts 의 절 메타 줄에는 자유문 `status:`(근거 등급, 메모)가 많다. 그래서 C1 문법은 파일 frontmatter 에만 적용하고, 절 메타의 `status:` 는 지금처럼 evidence 나 note 로 읽어야 한다.
- 5. **커밋 D**: static-gen 으로 폴더 README 를 만든다.
- 측정:
  - 같은 10개 질문의 hit@5, 토큰, 호출 수
  - `stale` 오탐 비율
  - lint 건수
  - 일부러 README 를 낡게 만들었을 때 `--check` 가 잡는지
  - archive 후보 중 사용자가 동의한 비율
  - coderag 를 PATH 에서 빼고 사람과 에이전트가 같은 질문을 grep 으로 풀 수 있는지
- 롤백: 커밋 단위 revert. **판정 기준**: coderag locate 가 grep 보다 hit@5 가 낮거나 stale 오탐이 30%를 넘으면 C·D 만 되돌리고 A·B(이동)는 유지한다. 이동은 결합과 상관없이 가치가 있다.

## 7. P 가 반박할 것으로 보는 점
1. 개발 중인 도구(설계 §35 가 팀 서버로 움직이는 중)에 모든 저장소의 규약을 묶는 위험. 내 답은 이렇다. 묶는 것은 frontmatter 키 5개와 status 문법뿐이고, 이것은 평문 YAML 이라 coderag 가 사라져도 남는다. 게다가 coderag 는 사용자 자신의 도구라 우리가 어휘를 고정할 수 있다.
2. status 를 frontmatter 에만 두는 것. P 는 본문 첫 줄의 평문 상태 줄을 원할 것이다. 나는 이중 소스가 더 큰 실패라고 본다(audit/36).
3. coderag 변경 8건이 형제 저장소 작업이라는 점: 승인이 필요하고, 다른 세션과 충돌할 수 있다. 그동안은 lint 오탐이 생긴다.
4. archive 후보 휴리스틱(나이와 인용 0)의 오탐, 그리고 "status 변경과 이동을 같은 커밋에"가 너무 엄격하다는 점.
5. 비프로그래머 동료에게 배포할 때 바이너리 빌드가 필요하다는 점. 그래서 §3.4 폴백이 실제로 쓸 만해야 한다.

## 8. 사용자에게 물을 것 (3개)
1. coderag 저장소에 C1-C8 을 넣어도 되나? 어느 세션이 맡나? (최소는 C1·C2·C6. C1 은 지금의 조용한 오분류 수정이기도 하다.)
2. 이 세션이 작업하는 저장소에서, status 를 바꿀 때 에이전트가 매번 묻지 않고 `git mv` 로 archive 이동까지 같은 커밋에 해도 되나? (archive 후보 목록은 따로 묻는다.)
3. coderag 플러그인(doc-locator, post-edit lint)을 사용자와 동료 설치에 켤까, 아니면 바이너리 경로(harness.env)만 쓸까? 동료에게는 미리 빌드한 바이너리 배포가 필요하다.
