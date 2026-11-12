# 38 round2-Q: P 의 사실 검증, 쟁점별 양보·고수, 수렴안

1라운드 입장은 그대로다. 검색과 stale 은 coderag 가 맡는다(사용자: "검색 관련해서나 stale 관련해서나 이미 만들어진 틀이 있으니까"). 바뀐 것도 있다. P 가 내놓은 "살아 있는 문서와 스냅샷" 구분과 "검사기 정본은 하나"를 받아들인다. 그래서 coderag 변경 목록이 1라운드보다 줄었다.

## 1. P 의 사실 주장 검증 (coderag 는 읽기만 했다)
| 주장 | 판정 | 근거 |
|---|---|---|
| 숨김 판정이 status 문자열 전체를 비교한다(lib.rs:352) | 맞음 | `listed()` = `!matches!(status, "superseded"\|"archived")`. status 는 소문자로 바꾼 값 전체다(:764) |
| status 가 없으면 active 로 처리한다(:764) | 맞음 | `unwrap_or_else(\|\| "active")` |
| lint 는 첫 낱말만 보고, `superseded_by` 검사는 값이 정확히 같을 때만 돈다(:933-941) | 맞음 | :935 `split_whitespace().next()`, :940 `== Some("superseded")` |
| lib.rs 의 :352, :764, :933-941 만 고치면 된다 | **틀림(일부)** | core `docs/mod.rs:162-164` 도 status 를 `active\|superseded\|archived` 로 거르고 나머지는 `active` 로 바꾼다. 1라운드 §0 의 조용한 오분류가 여기서 생긴다. static-gen 상태 열도 고쳐야 한다. 대신 일이 줄어드는 부분도 있다. core `docs/meta.rs:80 split_status` 가 이미 첫 낱말로 상태를 나누는 파서다(절 메타와 lint.rs:159 가 쓴다). 그러니 "작음"이라는 크기 판단은 그대로다 |
| 세션 writer 가 coderag 꼴 frontmatter 를 쓰고 그 뒤에 2줄 머리말을 붙인다 | 맞음(출처 보정) | frontmatter(`kind: session`, `status: active`, `last_verified`)는 `store.py:246-248` 이 쓴다. 2줄 머리말은 `records_home.py:106 with_header` 가 붙인다 |
| `q:import` 는 `.claude/records/` 를 권하는데, 이 저장소는 `.claude/sessions` 다 | 맞음 | import SKILL.md:10, `.claude/session-log.json` 의 `records_home: .claude/sessions` |
| doc-locator 훅이 grep 을 막는다 | 맞음(범위 한정) | `coderag-cli/src/hook.rs:128 pre_bash` 는 `agent_type == coderag:doc-locator` 일 때만 막는다. 다른 에이전트의 grep 은 통과한다(테스트 :194-197) |
| frontmatter 가 없으면 coderag 는 첫 `#` 제목과 첫 문단으로 대신한다 | 맞음 | lib.rs:745-756. 순서는 title → name → h1 → 파일 이름, description 이 없으면 첫 문단 |
| 암묵 설정이 `.claude/` 를 이미 색인한다 | 맞음 | config.rs:204-222 `implicit_docs(".claude")`. 제외 목록은 없다. 그래서 내 C8 이 필요하다 |
| Claude Code 상시 로드 경고가 약 40k자다 | 확인 못 함 | P 도 "확인 필요"라고 적었다. 예산 값은 실측해서 정한다 |
| GitHub 가 frontmatter 를 표로 보여 준다 | 확인 못 함(코드 밖) | GitHub 의 알려진 동작이라 반론은 없다 |

추가로 잰 것: 기록 폴더(drafts, audit, decisions, handoff)에서 처음 15줄 안의 `^status:` 는 6건이다. 첫 줄에 있는 것이 3건(drafts 의 `landed in …`), frontmatter 안(6행)에 있는 것이 3건이다. 절 메타의 근거 등급 `status:` 는 15줄 안에 없다. 그래서 P 의 "첫 15줄" 규칙은 지금 오탐이 없다. 다만 나는 "frontmatter 안, 아니면 첫 줄"로 좁히자고 제안한다. 근거 등급과 부딪칠 여지를 없애기 위해서다.

## 2. 쟁점별 판단
1. **기록 두 부류(살아 있는 문서와 스냅샷, 스냅샷은 옮기지 않음): 양보.** 스냅샷을 옮기면 다른 스냅샷 안의 옛 경로가 깨지는데, 스냅샷은 고치지 않는 것이 규칙이라 그 경로를 고칠 수도 없다. 이 논거가 맞다. 1라운드 C5 의 "기록류 archive 후보"는 철회한다. 옛 스냅샷을 검색에서 뒤로 미는 일은 옮기기가 아니라 coderag 의 나이 표시(C7)로 한다. `handoff/` 도 스냅샷으로 분류하는 데 동의한다(1라운드의 "처리되면 archived"는 철회).
2. **status 위치: 타협.** P 의 규칙인 "frontmatter 가 있으면 거기, 없으면 첫 줄, 둘 다는 금지"를 받는다. 이 규칙도 상태를 한 곳에만 두므로 내가 걱정한 이중 소스는 생기지 않는다. coderag 에 첫 줄 파서(C3)를 따로 넣지는 않는다. 첫 줄 status 가 있는 문서는 끝난 옛 drafts 이고 모두 `archive/` 로 간다. 그러면 C2 가 폴더로 `archive` 를 판정해서 숨긴다.
3. **필수 폴더: 양보.** `.claude/README.md` 하나만 필수로 한다. git 은 빈 폴더를 추적하지 않고, 빈 `base/`·`archive/` README 는 작은 저장소에 잡음이 된다.
4. **README 색인: 타협.** 폴더 README 는 손으로 쓴 1-3줄로 시작하고, 그 뒤에 목록이 온다. 목록은 둘 중 하나다. 손으로 쓴 `- [이름](경로) — 설명`(상태는 적지 않음), 또는 커밋한 static-gen 마커 블록. 둘 다 규약을 지킨 것이다. 내 주장은 이것이다. coderag 가 있는 기계에서는 에이전트가 static-gen 을 기본으로 쓴다. 생성된 목록은 어긋나지 않고, 상태 열에 target 까지 보여 준다. 기본값을 무엇으로 할지는 실험의 측정 항목으로 정한다.
5. **sessions/ 색인: 양보.** README 를 두지 않는다. `grep -h '^title:'` 나 `coderag search --kind session` 이 색인 노릇을 한다.
6. **검사 위치: 타협(책임을 나누고, 같은 검사를 두 곳에 두지 않는다).**
   - q `records_check.py`(stdlib)는 색인 없이 되는 검사의 정본이다. status 문법, 끝난 문서가 archive 밖에 있음, README 링크 누락, 살아 있는 문서의 깨진 상대 링크, 상시 로드 크기, 파일·폴더 크기.
   - coderag 는 색인이 있어야 되는 일을 맡는다. 검색에서 숨기기, 해시와 refs 그래프로 찾는 stale, `static-gen --check`, 스냅샷 나이 표시.
   - 두 구현이 같은 status 문법을 읽어야 하므로 문법은 규약 스킬에 한 번만 정의한다. 그리고 fixture 파일 하나(`plugins/q/tests/records-fixtures/`)를 q 테스트와 coderag 테스트가 함께 쓴다. 그래서 어긋나면 테스트가 깨진다.
   - 커밋 알림은 q 검사를 먼저 돌리고, 바이너리가 있으면 `coderag stale` 결과 줄을 덧붙인다.
7. **coderag 변경 목록: 타협(두 단계).**
   - 1단계(실험 전에 필요): C1 status 문법(P 의 1번, 조용한 오분류 수정 포함, `split_status` 재사용), C2 폴더로 kind 추론(P 의 3번, 복수형 별칭, `archive/` 는 listed=false), C6 `static-gen --check`(P 의 2번)와 `--dir` 기준 경로 버그 수정.
   - 2단계(실험에서 효과를 잰 뒤): C4 `.gitignore` 존중(P 의 4번), C7 스냅샷 나이 표시. 날짜는 frontmatter `date` → 파일 이름 날짜 → `> Snapshot YYYY-MM-DD` 머리줄 순서로 찾는다. C8 암묵 설정 제외 목록.
   - 철회: C3, 그리고 C5 의 archive 후보 부분. "끝났는데 archive 밖" 검사는 q 로 옮긴다. 본문 색인은 나중으로 미룬다.
8. **recall: 이미 수렴.** doc-locator 를 쓰지 않는다. 매번 `coderag gen` 을 돌리고 캐시는 저장소 밖에 둔다. `search --abs --layer project` 를 쓰고, 결과가 3건 미만이거나 대상이 세션 기록이면 grep 을 같이 돌린다. 지금 recall SKILL.md:16 은 "coderag search tool 이 있으면 global layer 먼저"라고 적혀 있으므로, project layer 와 바이너리 경로(harness.env) 방식으로 고쳐야 한다.
9. **archive 이동: 양보.** 1라운드 질문 2("묻지 않고 옮겨도 되나")는 철회한다. 사용자가 이미 "정리는 자동으로"라고 했다. status 를 바꾼 에이전트가 같은 커밋에서 `git mv` 를 하고, 살아 있는 문서의 링크를 고치고, README 줄을 고친다. 쌓인 것을 정리할 때는 doctor 가 목록을 내고, 사용자가 허락하면 sonnet 이 한 커밋으로 옮긴다. 삭제는 하지 않는다.
10. **raw 덤프: 같음.** `.claude/**/raw/` 를 gitignore 한다. 요약에는 수치와 raw 를 다시 만드는 명령을 적는다. 파일 하나 200KB, 최상위 폴더 하나 5MB 를 예산으로 둔다. 동료와 공유할지는 질문으로 남긴다.
11. **q:start 뼈대: 양보.** `.claude/README.md`(coderag 가 있으면 마커 블록 포함), `.gitignore` 두 줄(`.claude/**/raw/`, `.coderag/`), `session-log home .claude/sessions` 을 만든다. 항목마다 동의를 받는다. coderag.toml 은 만들지 않는다.
12. **규약 문구를 싣는 곳: 같음.** `qwreey-conventions:agent-records` 스킬에 싣는다. 여기에 `paths: ["**/.claude/**/*.md"]` 인 4줄 rule 을 더하는데, rule 본문 첫 줄에서 agents·skills·rules·hooks·worktrees 를 범위에서 뺀다. coderag 의 `docs-frontmatter` 는 키 참조만 남기고 이 스킬을 가리킨다.
13. **스냅샷 머리말(추가 수렴).** 세션 frontmatter 에서 `status: active` 와 `last_verified` 를 빼고 `date:` 를 넣는다. `last_verified` 가 남으면 90일 뒤 stale 잡음이 된다(P 는 status 만 빼자고 했다). audit 은 P 의 한 줄 머리말 `> Snapshot <date>. …` 을 쓴다. 이 줄이 C7 의 날짜 출처도 된다. 날짜는 바뀌지 않는 값이라 frontmatter 와 머리줄 두 곳에 있어도 어긋나지 않는다.

## 3. 수렴안

### 합의(양쪽이 서명할 수 있는 것)
1. `.claude/` 기록은 두 부류다. 살아 있는 문서(plan, base, research)는 status 를 갖고, 끝나면 `archive/<원래 폴더>/` 로 옮긴다. 스냅샷(audit, handoff, sessions)은 status 가 없고, 고치지 않고, 옮기지 않으며, 맨 위에 낡을 수 있다는 경고를 둔다.
2. status 문법은 `<state> [in|by <target>] [; <note>]` 이다. 어휘는 `active | landed | superseded | rejected | archived` 다섯이고 `paused` 는 없다(`active; on hold until …` 로 쓴다). 상태 줄에 날짜를 쓰지 않는다. 경로처럼 생긴 target 만 존재를 검사한다. `superseded_by:` 는 `superseded by` 와 같은 뜻이다.
3. status 는 한 곳에만 둔다. frontmatter 가 있으면 거기, 없으면 첫 줄이다.
4. 폴더는 plan, base, research, audit/NN-slug, handoff, sessions, archive/<원래 폴더>, packs/<팩> 이다. 처음 쓸 때 만든다. 필수는 `.claude/README.md` 하나다. 이름은 `sessions` 이고, 형제 저장소의 `session/` 도 인정한다.
5. 폴더 README 는 손으로 쓴 1-3줄 다음에 목록이 온다. 목록은 손으로 쓴 줄(상태·날짜·배너 없음)이거나 커밋한 static-gen 블록이다. sessions/ 에는 README 를 두지 않는다.
6. status 를 바꾼 에이전트가 같은 커밋에서 `git mv`, 링크 수정, README 수정까지 한다. 훅은 파일을 옮기지 않고, 아무도 파일을 지우지 않는다. 쌓인 것은 doctor 목록을 보고 사용자가 허락한 뒤 한 커밋으로 옮긴다.
7. 검사는 책임을 나눈다. q `records_check.py` 가 레이아웃과 크기를 맡고(doctor 와 커밋 info 알림), coderag 가 숨김, stale, 색인 신선도, 나이를 맡는다. status 문법은 스킬과 공용 fixture 로 한 번만 정의한다.
8. coderag 변경 1단계는 C1(status 문법과 오분류 수정), C2(폴더로 kind 추론, archive 숨김), C6(`static-gen --check`, `--dir` 버그)이다. 2단계는 C4, C7, C8 이고, 실험에서 효과를 잰 뒤 넣는다.
9. recall 은 coderag 바이너리로 gen 과 search 를 하고(캐시는 저장소 밖), 세션 본문과 결과가 적을 때는 grep 을 같이 쓴다. doc-locator 에는 기대지 않는다. coderag 가 없으면 grep 만으로 동작한다.
10. 세션 frontmatter 는 status 와 last_verified 를 빼고 `date` 를 넣는다. audit 은 `> Snapshot <date>` 머리줄을 둔다. import 의 기본 제안 위치는 `.claude/sessions/` 로 바꾼다.
11. raw 출력은 `.claude/**/raw/` 에 두고 gitignore 한다. 크기 예산은 파일 하나 200KB, 폴더 하나 5MB 다. 상시 로드 예산은 실측해서 정한다.
12. q:start 는 README 하나, .gitignore 두 줄, sessions home 만 만들고 항목마다 동의를 받는다.
13. 규약 문구는 `qwreey-conventions:agent-records` 스킬과 범위를 좁힌 rule 로 싣는다. 본문은 P 의 55줄 안을 바탕으로 한다. 내 안에서 더할 것은 세 가지다. "Finding records: search first, then read line ranges", static-gen 실행 명령, coderag 가 폴더로 kind 를 추론한다는 한 줄.
14. 재편 실험은 PLAN §3.9 의 4단계를 따른다. 먼저 recall 질문 10개로 기준선을 잰다. 그다음 커밋 A(옮기기만), B(경로 기계 치환), C(끝난 문서의 status 와 archive), D(색인) 순서로 간다. 판정 기준은 이렇다. coderag 의 위치 찾기가 grep 보다 hit@5 가 낮거나 stale 오탐이 30%를 넘으면 C·D 만 되돌리고 A·B 는 남긴다.

### 남은 이견
- **새 살아 있는 문서의 frontmatter(title, description)를 필수로 할지.** Q: 본문이 색인되지 않으므로 haiku 위치 찾기의 품질은 description 이 좌우한다. P: lint 소음이 커지고 동료에게 진입 장벽이 된다. 첫 제목과 첫 문단으로 대신하면 된다. 해법: 실험에서 frontmatter 가 있는 문서와 없는 문서의 hit@5 를 비교해서 정한다.
- **README 목록의 기본 형태.** Q: coderag 가 있으면 static-gen 을 기본으로 한다(어긋나지 않고 target 이 보인다). P: 손으로 쓴 목록을 기본으로 하고 생성물은 허용만 한다(도구 없이도 완결). 해법: 실험의 "README 를 일부러 낡게 만든 뒤 `--check` 가 잡는가"와 손 목록 누락률을 보고 정한다.

### 사용자에게 물을 것(최대 4)
1. coderag 저장소 변경을 어디까지 승인하나? (a) 1단계(C1, C2, C6)만 지금 승인 (b) 1·2단계 모두 승인 (c) 승인하지 않고 q 검사기만 쓴다. 이 경우 coderag 는 `landed`·`rejected` 문서를 계속 active 로 보여 준다. 승인한다면 어느 세션이 맡을지도 정해야 한다.
2. 원시 측정 출력은 어떻게 하나? (a) `raw/` 를 gitignore 한다. 동료에게는 요약과 재생성 명령만 간다 (b) 200KB 예산 안의 것은 커밋한다.
3. 형제 저장소(quad 의 `session/`, `archive/surveys/`, 제목 태그)에 소급할까? (a) 새 저장소와 claude-doctor 에만 적용하고, 옛 형태는 검사기가 인정만 한다 (b) 저장소마다 승인을 받아 옮긴다.
4. coderag 를 어떤 형태로 쓰나? (a) 바이너리 경로(harness.env)만 쓴다 (b) 사용자 설치에서만 플러그인(post-edit lint)을 켠다 (c) 동료에게도 미리 빌드한 바이너리와 플러그인을 배포한다.
