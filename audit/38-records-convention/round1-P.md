# 38 기록 규약 토론, 1라운드: P (평문 markdown 우선)

입장: 규약은 grep 과 README 만으로 완결돼야 하고, coderag 는 있으면 빨라지는 가속기다. 이유 셋. (1) 규약은 사용자의 **모든** 저장소와 비프로그래머 동료에게 퍼지는데, coderag 는 PATH 에 없고 배포 방식이 안 정해졌으며(audit/37 §7) 개발 무게가 팀 서버(§35)로 가 있다. (2) 기록은 몇 년을 가지만 도구 문법은 바뀐다. (3) 사용자 말대로 git 이 있으니 평문은 언제든 다시 색인할 수 있지만, 반대 방향(도구 전용 형식을 평문으로 되돌리기)은 비싸다.

먼저 인정할 것. coderag 의 frontmatter 는 **그 자체로 평문**이다(`grep '^status:'` 로 잡힌다). 그러니 "frontmatter 냐 평문이냐"는 가짜 대립이다. 진짜 쟁점은 셋이다. 규약이 coderag 의 **동작**(숨김, lint, kind)에 기대느냐, 같은 상태를 두 곳에 쓰느냐, 검사기가 어디에 사느냐.

확인한 사실(코드):
- coderag `listed()` 는 status 문자열 **전체**를 `"superseded"|"archived"` 와 비교한다(lib.rs:352, :764). 그래서 `status: superseded by base/x.md` 는 검색에서 **숨지 않는다**. lint 는 첫 낱말만 보므로 통과하고, `superseded_by` 누락 검사(:940)도 완전 일치일 때만 돈다. `landed in X` 는 lint 오류가 난다. 따라서 사용자가 제안한 문법을 쓰면 coderag 쪽 파서가 손볼 곳은 한 군데로 모인다.
- q 의 세션 기록 writer 는 이미 coderag 형 frontmatter(`kind: session`, `status: active`, `last_verified`, title·description·keywords)를 쓰고, 그 뒤에 2줄 스냅샷 머리말(blockquote)을 붙인다(records_home.py `with_header`). 결합은 이미 반쯤 되어 있다.
- `q:import` 는 보관 위치 후보로 `.claude/records/` 를 권하고, 이 저장소 설정은 `.claude/sessions`, quad 는 `session/`, coderag kind 는 `session` 이다. 이름이 넷이다.

## 1. status

**문서를 두 부류로 나눈다.** 이 구분이 규약의 핵심이고, 나머지는 여기서 나온다.
- **살아 있는 문서**(plan, base, research): 내용이 계속 고쳐진다. status 가 있고, active 를 벗어나면 archive 로 간다.
- **스냅샷**(audit, sessions, handoff): 그 시점의 기록이고 다시 고치지 않는다. status 전이가 없고 상태 때문에 옮겨지지 않는다. 대신 "낡았을 수 있다"는 경고를 머리말에 단다.

audit/36 의 실패 둘(audit 4,934파일, 감사 루프 비용)은 둘을 같은 규칙으로 다룬 데서 나왔다. 스냅샷에 상태 관리를 요구하면 아무도 지키지 않고, 결국 한꺼번에 감사하게 된다.

**문법**은 `status: <state> [in|by <target>] [; <note>]` 이다. 메인 권고를 받는다.
- 어휘는 `active | landed | superseded | rejected | archived` 다섯 개로 한다. 상태마다 읽는 쪽이 할 일이 하나씩 다르기 때문이다. active 는 읽고 고친다. `landed in X` 와 `superseded by X` 는 X 를 읽는다. `rejected [by X]` 는 하지 말라는 뜻이고 이유는 note 나 본문에 있다. `archived` 는 이어받는 문서 없이 끝났다는 뜻이다.
- `paused` 는 넣지 않는다. 멈춘 계획도 여전히 고쳐 가는 문서이고, 할 일이 active 와 같다(읽고, 다시 시작할 때 고친다). `active; on hold until <조건>` 으로 쓴다. 상태 수를 늘리면 검사기와 coderag 숨김 규칙이 같이 늘어난다.
- 날짜는 넣지 않는다. 상태가 언제 바뀌었는지는 `git log -S'status:'` 가 답한다(agent-docs: 이력은 커밋에). 사용자 결정의 원문 인용과 날짜는 본문 근거에 남긴다. 그것은 이력이 아니라 근거다.
- target 이 경로처럼 생겼을 때만(`/` 를 포함하거나 `.md` 로 끝날 때) 존재를 검사한다. `D-07`, `user` 같은 값은 검사하지 않는다.
- `superseded_by: X` 필드는 `status: superseded by X` 와 같은 뜻으로 읽는다. 규약은 한 줄 형태만 쓰게 한다(grep 한 번에 상태와 대상이 같이 나온다).

**위치**는 한 곳이다. frontmatter 에 `status:` 줄이 있으면 그것이고, frontmatter 가 없으면 파일 첫 줄의 `status: ...` 다. 두 곳에 다 쓰는 것은 금지한다. audit/37 은 "본문 첫 줄에도"를 권했지만, 그것은 audit/36 이 실패로 꼽은 이중 상태(quad 의 CLAUDE.md·project-context·ROADMAP)를 문서마다 다시 만드는 일이다. 에이전트는 파일을 날것으로 읽으니 frontmatter 가 그대로 보이고, GitHub 도 frontmatter 를 표로 보여 준다. 검사기는 처음 15줄 안의 첫 `^status:` 를 읽는다.
- 새로 만드는 살아 있는 문서에는 frontmatter(title, description, status)를 **권장**한다. description 은 README 색인 줄과 coderag 검색에 함께 쓰인다. 다만 필수는 아니다. 옛 문서를 백필하지 않아도 규약을 지킨 것이 되게 하려는 것이다.
- kind 는 적지 않는다. 폴더가 곧 kind 다(5절의 coderag 변경 3).

**세션 기록 머리말**은 지금 형태(frontmatter + 2줄 blockquote)를 그대로 둔다. 바꿀 것은 하나다. writer 가 `status: active` 를 쓰지 말고 status 를 아예 빼야 한다. 스냅샷은 "active" 가 아니고, coderag 는 status 가 없으면 active 로 기본 처리하므로(lib.rs:764) 검색 동작은 그대로다. audit 의 머리말은 첫 줄에 `> 스냅샷 <YYYY-MM-DD>. 지금과 다를 수 있다; 기대기 전에 현재 파일과 git log 로 확인.` 한 줄을 둔다. import 가 쉬워야 한다는 조건에 따라 형식은 손으로 3초 안에 쓸 수 있어야 한다.

## 2. 폴더

필수는 `.claude/README.md` 하나다. 폴더는 처음 기록할 때 만든다(git 은 빈 폴더를 추적하지 않고, 빈 뼈대는 소규모 저장소에 잡음이 된다. audit/36 §1.7 의 "소규모는 base/audit/session 만").

| 폴더 | 부류 | 한 줄 정의 |
|---|---|---|
| `plan/` | 살아 있음 | 지금 하려는 일과 열린 결정. 진행 중인 큰 일 하나에 파일 하나 |
| `base/` | 살아 있음 | 확정된 결정과 프로젝트 전체에 걸치는 배경. 다른 기록과 충돌하면 이쪽이 이긴다. claude-doctor 의 `decisions/D-xx` 는 여기로 온다(ID 유지) |
| `research/` | 살아 있음 | 결정하기 전의 조사와 시제품. 사용자와 상의할 거리. `drafts/` 도 여기로 |
| `audit/` | 스냅샷 | 실측, 검토, 토론의 시점 기록. `NN-slug/` 번호 폴더, 끝나면 고치지 않음 |
| `handoff/` | 스냅샷 | 다음 세션에 넘기는 상태. 선택 |
| `sessions/` | 스냅샷 | q 가 import 한 세션 기록. 생성물이라 손으로 고치지 않음 |
| `archive/` | 끝난 살아 있음 | status 가 active 를 벗어난 살아 있는 문서. 원래 폴더를 따라 `archive/<원래 폴더>/` 로 둔다 |
| `packs/<팩>/` | 혼합 | 이 저장소의 팩 개발 자료(bench, evals, 팩 전용 결정). 안에서 같은 폴더 이름을 다시 쓴다 |

- `sessions` (복수)로 한다. Claude Code 표준 폴더(`agents/`, `skills/`, `rules/`)와 같은 꼴이고, 이 저장소 설정과 일치한다. coderag kind `session` 은 frontmatter 값이라 폴더 이름과 맞출 필요가 없다. `q:import` 가 후보로 권하는 `.claude/records/` 는 `.claude/sessions/` 로 바꾼다. quad 의 `session/` 은 억지로 옮기지 않는다(형제 저장소는 읽기 전용이고 링크가 깨진다). 검사기와 recall 은 `session/` 도 스냅샷 폴더로 인정한다.
- `archive/<원래 폴더>/` 는 미러로 둔다. `git mv .claude/research/x.md .claude/archive/research/x.md` 이면 링크를 기계적으로 고칠 수 있고, archive 안에서도 출처가 보인다. quad 의 `archive/surveys/날짜-이름` 처럼 이름을 다시 짓지 않는다.
- 스냅샷은 archive 로 옮기지 않는다. 옮기면 다른 스냅샷 안의 옛 경로가 깨지는데, 스냅샷은 고치지 않는 것이 규칙이라 고칠 수도 없다. 상시 로드되지 않으므로 비용은 저장소 크기와 grep 잡음뿐이고, 그것은 4절의 raw/ 와 예산으로 다룬다.
- `docs/` 는 사람이 읽는 완성 문서다. 설치, 사용법, 설계 개요처럼 기록을 읽지 않아도 혼자 읽혀야 하는 것을 둔다. 에이전트는 시킬 때만 쓴다. `.claude/` 를 근거로 가리킬 수는 있지만, 정의의 정본을 `.claude/` 에 두지 않는다.

**README 색인 형식.** 살아 있는 폴더(plan, base, research, archive)와 `audit/` 의 README 는 `- [이름](경로) — <한 줄 설명>` 을 한 항목에 한 줄로 쓴다. audit 은 번호 폴더당 한 줄이다(quad 처럼 파일 수천 개를 색인하지 않는다).
- 손으로 쓰는 줄에는 상태를 적지 않는다. 상태의 정본은 파일이다. coderag `static-gen` 이 만든 마커 블록이라면 상태 열이 있어도 된다. 생성물이라 어긋나지 않는다.
- 색인 줄에 날짜·라운드 배너(`[2026-09-08 분리 …]`)를 쓰지 않는다. quad README 는 한 셀이 17,005자까지 자랐다. 이력은 커밋에 둔다.
- `sessions/` 는 README 색인을 두지 않는다. `grep -h '^title:' .claude/sessions/*.md` 가 색인이다. 생성물을 손 색인으로 한 번 더 쓰는 것은 이중 소스다.
- 루트 `.claude/README.md` 는 폴더당 한 줄과, 그 저장소 고유 폴더의 정의만 둔다.

## 3. coderag 결합

- **coderag 에 필수로 요구하는 것은 없다.** coderag 가 없어도 규약의 모든 검사와 찾기가 grep 과 stdlib python 으로 돈다. coderag 는 검색 랭킹, 절 단위 줄 범위·토큰 추정, `static-gen`, `stale` 의 해시 변화를 더해 준다. 이 기능들이 실제로 좋다는 것은 인정한다. haiku 가 `경로:줄 ~토큰` 을 받아 범위만 읽는 꼴은 grep 보다 낫다(audit/37: search 0.006초).
- **coderag 의 최소 변경**(coderag 저장소라 사용자 승인 필요):
  1. status 문법 파싱. state 는 첫 낱말이다. `in|by` 뒤가 target 이고, target 은 `superseded_by` 와 같이 stale 대상 검사를 받는다. `;` 뒤는 note 다. landed·superseded·rejected·archived 는 `listed=false` 다. KNOWN_STATUS 에 landed·rejected 를 더한다. lib.rs 의 :352, :764, :933-941 만 고치면 된다.
  2. `static-gen --check`. 바뀔 것이 있으면 종료 코드 1 이다. 색인 누락 검사를 coderag 쪽에서도 쓸 수 있게 한다.
  3. frontmatter 에 kind 가 없으면 폴더 이름(plan, base, research, audit, archive, handoff, `sessions`·`session`)으로 kind 를 추론한다. 이게 있어야 백필 없이 `--kind` 가 쓸모 있다.
  4. (있으면 좋음) `raw` 를 기본 제외에 넣거나 `.gitignore` 를 존중한다.
- **coderag 가 없을 때**는 grep 으로 찾고 q 의 검사기로 검사한다. 사용자가 보는 차이는 속도와 줄 범위 정확도뿐이어야 한다.
- **recall 의 haiku locate 단계**는 이렇게 한다. coderag 를 쓸 수 있으면(`bin/coderag` 래퍼가 찾으면) 먼저 `coderag gen`(`CODERAG_CACHE` 는 저장소 밖)을 돌린 뒤 `coderag search --abs --layer project` 를 쓴다. **결과가 3건 미만이거나 세션 기록이 대상이면 grep 도 돌린다.** coderag 는 본문 낱말을 색인하지 않는데(audit/37 §2), 세션 기록은 본문이 핵심이다. 그래서 세션 기록에는 grep 을 대체가 아니라 기본으로 쓴다. recall 은 doc-locator 에 기대지 않는다. doc-locator 는 coderag 플러그인을 설치해야 생기고, 훅이 grep 을 막는다.
- **색인 신선도**: recall 할 때마다 gen 을 돌린다. 155항목에 0.032초라 비용이 없고, M9 를 기다리면 낡은 줄 범위를 읽게 된다. 캐시는 `/tmp` 나 `$XDG_CACHE_HOME` 에 두고, `.coderag/` 는 `.gitignore` 에 넣는다.

## 4. 자동화

**검사기 하나**를 둔다. q 플러그인의 `records_check.py`(stdlib, 1초 이내)이고, 대상은 `.claude/` 의 기록 폴더다(agents, skills, rules, hooks, worktrees 는 소스라 제외).

| 검사 | 대상 | 수준 |
|---|---|---|
| 깨진 상대 링크·경로 코드 스팬 | 살아 있는 문서만(스냅샷은 옛 경로 보존) | warn |
| status 문법, 경로 target 없음 | 살아 있는 문서 | warn |
| active 가 아닌 문서가 archive 밖에 있음 / active 문서가 archive 안에 있음 | 살아 있는 폴더 | warn |
| 색인 누락(폴더 README 에 링크 없음) | plan, base, research, archive, audit 번호 폴더 | info |
| 상시 로드 크기(CLAUDE.md + `@import` 합계) | 저장소 | 예산 초과 시 warn. 예산 값은 Claude Code 자체 경고(약 40k자로 기억함, 확인 필요)에 맞춘다 |
| 크기·증가: 추적되는 파일 하나가 200KB 초과, 최상위 폴더 하나가 5MB 초과 | `.claude/` | info, raw/ 로 빼라는 안내 |

- **어디서 도나**: (a) `q:doctor` 진단 항목. (b) 커밋할 때 info 알림. q 는 이미 커밋 시점에 pending 기록 알림을 띄우므로 거기에 붙이고, 스테이징된 `.claude/**` 만 보며 5줄 이하로 낸다. 막지 않는다. (c) coderag lint/stale 은 있으면 같이 보여 줄 뿐, 검사기는 거기에 기대지 않는다. 규칙의 정본을 두 구현에 나눠 두지 않으려는 것이다. coderag 가 1번 변경을 받아들이면 같은 문법을 읽게 된다.
- **누가 옮기나**: status 를 바꾼 에이전트가 **같은 커밋에서** `git mv` 로 archive 로 옮기고, 그 문서를 가리키는 살아 있는 문서의 링크를 고친다. 시키지 않아도 한다. 사용자가 말한 "정리를 하면서 동시에 자동으로"가 이것이다. 훅이 파일을 옮기지는 않는다(의도를 모른다). 삭제는 하지 않는다(HUMAN_TODO 몫). 쌓인 것을 정리할 때는 doctor 가 후보 목록을 내고, 사용자가 허락하면 sonnet 서브에이전트가 규약 스킬을 따라 한 커밋으로 옮긴다.
- **audit 덤프**: 원시 측정 출력은 `.claude/audit/<NN-slug>/raw/` 에 두고 `.gitignore` 에 `.claude/**/raw/` 한 줄을 넣는다. 요약 md 에는 핵심 수치와 **raw 를 다시 만드는 명령**을 적는다. 커밋해야 하는 근거(작은 fixture, 재현 불가 출력)는 raw 밖에 두고 200KB 예산을 따른다. 동료에게 근거가 공유되지 않는다는 비용이 있다(질문 2).
- **`q:start` 뼈대**(항목마다 동의를 받는다): `.claude/README.md`(2절 표에서 그 저장소에 쓸 행만), `.gitignore` 두 줄(`.claude/**/raw/`, `.coderag/`), `session-log home .claude/sessions`. 빈 폴더와 coderag.toml 은 만들지 않는다. coderag 의 암묵 설정이 `.claude/` 를 이미 색인한다.

## 5. 규약 문구 (출하안)

출하 위치는 `qwreey-conventions:agent-records` 스킬(아래 본문)과, agent-docs 처럼 스킬을 가리키는 4줄 rule 이다. rule 의 `paths: ["**/.claude/**/*.md"]` 는 rules, skills, agents 에도 걸리므로, 본문 첫 줄에서 적용 범위를 좁힌다.

```markdown
# Agent records under .claude/
Records hold raw context for agents: decisions, why, evidence, user quotes. Human docs go in docs/.
Applies to record folders, not to .claude/{agents,skills,rules,hooks,worktrees}. A repo's own README wins.

## Two kinds of record
- Living (plan/, base/, research/): edited as things change; carries a status.
- Snapshot (audit/, handoff/, sessions/): true at its date, never edited later; no status; starts with a stale warning.

## Folders (create on first use; .claude/README.md lists the ones in use, one line each)
- plan/: what we intend to do and open decisions.
- base/: settled decisions and project-wide background; wins over other records on conflict.
- research/: investigation and drafts before a decision.
- audit/NN-slug/: measurements, reviews, debates at a point in time. Raw output goes in raw/ (gitignored); the .md keeps key numbers and the command that regenerates raw/.
- handoff/: state for the next session (optional).
- sessions/: session records imported by q. Generated; do not hand-edit.
- archive/<origin>/: living records whose status is no longer active, at their original subpath.
- packs/<pack>/: development material for a pack in this repo, using the same folders inside.

## Status (living records)
One line, in frontmatter if the file has one, else as the first line. Never both.
  status: <state> [in|by <target>] [; <note>]
- active: current. Pause with `active; on hold until <condition>`.
- landed in <path>: the content now lives at <path>; read that.
- superseded by <path|id>: replaced; read the target.
- rejected [by <path|id>] [; <reason>]: decided against; the body keeps why.
- archived [; <note>]: finished with no successor.
Do not date the status line; git log has when it changed. User quotes and their dates stay in the body as evidence.

## When you change a status away from active
In the same commit: `git mv` the file to archive/<origin>/<same path>, fix links to it in living records,
and update the folder README lines. Do not delete records; deletion is the user's call.

## Snapshot header
First line after any frontmatter:
  > Snapshot <YYYY-MM-DD>. May differ from now; check current files and git log before relying on it.

## Indexes
Each living folder and audit/ has a README with one line per entry: `- [name](path) — one-line description`.
No status, dates or banners in hand-written lines (the file holds its status). sessions/ has no README;
`grep -h '^title:' .claude/sessions/*.md` is its index. A coderag static-gen marker block may replace the list.

## Finding things
grep -rn over .claude/ works everywhere; add `--exclude-dir=archive` for current state only.
If coderag is available, `coderag search --abs --layer project` gives line ranges; still grep session bodies.
Read only the line range you need; records are long.

## Checks
q's records check (q:doctor, and an info notice at commit) reports broken links in living records,
bad status lines, finished records outside archive/, index gaps, always-loaded size and oversized files.
Fix what you introduced; list the rest for the user.
```

(본문 약 55줄)

## Q 가 반박할 것으로 보는 점
1. **frontmatter 필수화.** coderag 는 본문을 색인하지 않으므로 title·description·keywords 가 없으면 검색 품질이 떨어진다. 그러니 살아 있는 문서에는 frontmatter 를 필수로 하자는 주장이 나올 것이다. 내 답: 새 문서에는 권장하고, 백필은 하지 않으며, 대신 coderag 가 첫 `#` 제목과 첫 문단으로 대체한다(이미 그렇게 동작한다). 필수로 만들면 lint 소음이 커진다.
2. **검사기를 coderag lint 에 두자**("전 저장소 공통이니 coderag"). 내 답: 규약은 coderag 가 없는 동료 기계에서도 검사돼야 한다. coderag 는 같은 문법을 읽어 숨김과 stale 에 쓰면 되고, 정본 검사기는 하나여야 한다.
3. **README 색인을 static-gen 생성물로 일원화.** 이중 소스를 없애는 데는 그쪽이 낫다. 다만 손으로 쓰는 한 줄 색인도 상태를 빼면 어긋날 거리가 링크와 설명뿐이다. 생성물을 허용하되 강제하지는 않는다.
4. **스냅샷 나이 기반 archive.** archive 를 ÷2 로 가중하는 coderag 의 감쇠를 쓰려면 옛 audit 도 archive 에 있어야 한다는 주장이 나올 수 있다. 내 답: 스냅샷을 옮기면 고칠 수 없는 링크가 깨지므로 옮기지 않는다. 감쇠가 필요하면 coderag 가 frontmatter 날짜나 git 시각으로 하면 된다.
5. `paused` 상태, recall 이 grep 을 기본으로 함께 돌리는 것.

## 사용자에게 물을 것 (최대 3)
1. coderag 저장소 변경 1~3(status 문법 파싱, `static-gen --check`, 폴더로 kind 추론)을 승인할지. 승인하지 않으면 coderag 는 `landed`·`rejected` 문서를 계속 노출하고 lint 오류를 낸다(규약 자체는 그대로 돈다).
2. 원시 측정 출력을 gitignore(`raw/`)하면 동료 환경에는 근거 원본이 없고, 요약과 재생성 명령만 간다. 괜찮은지, 아니면 크기 예산 안에서는 커밋할지.
3. 기존 형제 저장소(quad 의 `session/`, `archive/surveys/`, 제목 태그 `[역전됨]`)에 이 규약을 소급할지, 새 저장소와 claude-doctor 에만 적용하고 옛 형태는 검사기가 인정만 할지.
