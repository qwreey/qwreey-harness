# records-in-coderag 초안 적대적 검토

D = `.claude/research/drafts/records-in-coderag/`, AR = `plugins/qwreey-conventions/skills/agent-records/SKILL.md`, AR-rule = `plugins/qwreey-conventions/rules/agent-records.md`, DF = `../coderag/skills/docs-frontmatter/SKILL.md`. 수준: must / should / note.

## 1. 원래 규칙이 어디로 갔나

| 원래 규칙 | 근거 | 합친 곳 | 판정 |
|---|---|---|---|
| 기록은 에이전트용, 사람 문서는 docs/, 저장소 README 가 우선 | AR:9 | D skill:9, rule:150 | 유지 |
| agents·skills·rules 등은 대상 아님 | AR:9, DF:67 | skill:9 | 유지 |
| 살아 있는 문서 / 스냅샷 두 부류, 스냅샷은 고치지 않고 옮기지 않음, 경로만 스크립트로 | AR:13-14, AR-rule:6 | skill:13-14, rule:154 | 유지 |
| 폴더 목록, `.claude/README.md` 만 필수 | AR:16-26 | skill:16-26 | 유지 |
| status 문법·어휘, paused 없음, 날짜 없음, 대상 경로 존재 | AR:28-40 | skill:30-42, rule:151 | 유지 |
| `superseded_by: X` == `superseded by X` | AR:40, DF:19,72 | skill:42(읽기만), refs:105 | Q2 에 따라 좁힘, 아래 S5 |
| **새 살아 있는 문서는 frontmatter title·description·status 필수** | AR:41, DF:14-15 | skill:54-57, rule:155 "optional" | **약화(must, M1)** |
| active 를 떠나면 같은 커밋 git mv, 링크·README·스냅샷 경로, 지우지 않음 | AR:43-45, AR-rule:7 | skill:51, rule:153 | 유지 |
| 갈음: 새 문서 첫머리 한 줄, 옛 문서는 status 만, 본문 보존 | DF:69-72 | skill:52("Supersedes:") | 유지(문구만 바뀜, 그 문자열을 읽는 코드는 없음) |
| "archived 로 두거나 옮긴다" | DF:73 | 삭제, 이동 필수 | 의도된 정정, 맞음 |
| "스냅샷·archive 는 본문 옛 경로를 고치지 않는다" | DF:66 | refs:143 에서 뺌 | 결정(경로 치환 허용)과의 모순이 풀림, 맞음 |
| README 색인, raw, 찾기 | AR:47-57 | skill:68-78 | 유지 |
| description 쓰는 법, keywords 가중치, 확장 키, YAML 부분집합, 절 메타, kind 표 | DF:25-64 | skill:65-66, refs 전부 | 유지 |
| records_check 검사 목록 | AR:61 | skill:84 | 유지 |
| `coderag gen` 색인 갱신 | DF:80 | skill:70(README 절에만) | note: Checks 절에 없음 |

- **M1 (must)** frontmatter 필수를 선택으로 바꾼 것은 audit/38 synthesis.md:8 합의 3번(양쪽 서명, `0d0a92b` 에서 AR:41 로 들어감)과 DF:14-15 를 함께 뒤집는다. D README:24 는 이것을 "정한 것"에 넣었지만 사용자 결정은 어디에도 없다(PLAN.md:199-200 에 없음). 바꿀 근거는 있다: 합의의 이유 "본문이 색인되지 않아"는 M5 본문 블룸(`58e5896`) 뒤로 약해졌다. 그러니 질문으로 올리거나 "새 살아 있는 문서는 필수"를 그대로 둔다. 그대로 두어도 hook.rs:85-89 가 이미 Write 에서만 알리므로 옛 문서에는 소음이 없다.

## 2. 닫기 기준이 quad 경우를 막나

- 스킬: skill:46-47 "Finishing the work ... is never by itself a reason", "`base/` stays active after implementation". rule:152 도 같은 뜻에 예까지 든다. 막는다.
- records_check: status 값에만 반응하고 내용으로 닫힘을 추정하지 않는다(records_check.py:156-157). coderag 도 같다: 숨김은 status·archive 경로뿐(lib.rs:411-413), stale 은 대상 경로와 review_after 만 본다(stale.rs:157-158). 이 둘이 quad base 를 닫으라고 밀 길은 없다.
- 남은 "일을 끝냄 = 닫기" 문구:
  - **S1 (should)** skill:48 "`plan/`: usually closes as `landed in ...` once executed." 실행했다는 것이 기준으로 읽힌다. quad 는 `base/` 에 `*-plan.md` 가 여럿이다(`quad/.claude/base/bind-system-plan.md` 등). 고칠 문구: "closes as `landed in <where>` once its result and decisions live there and nobody steers by the plan".
  - **S2 (should)** docs-backfill 새 29행(changes.md:94)은 "배너나 갈음 언급"을 닫을 후보로 보고한다. quad base 머리에는 "분할 3단계 완료" 같은 완료 배너가 흔하다(`quad/.claude/base/bind-system-plan.md:5`). "완료·구현됨 배너는 후보가 아니다"를 넣는다.
  - **S3 (should)** changes.md:125 의 새 records_check 문구 "git mv to archive/<origin>/ in the same commit" 와 doctor 의 "move to archive" 고침 항목(changes.md:120)은 이미 잘못 닫힌 문서(예: 구현을 마친 base 스펙에 에이전트가 `archived` 를 단 경우)를 archive 로 더 밀어낸다. 문구를 "git mv to archive/<origin>/, or set it back to active if it is still a current source"로 바꾸고, doctor 는 옮기기 전에 그 판단을 확인하게 한다.
  - note: PLAN.md:181 "끝난 문서가 archive 밖에" 와 `.claude/archive/README.md:3` "Finished living records" 가 changes.md 목록에 없다. archive README 는 그 폴더의 색인이라 스냅샷이 아니다.

## 3. rule 본문만으로 충분한가

스킬이 안 실려도 지켜지는 것: status 한 줄, 닫기 기준, 같은 커밋 git mv, 지우지 않음, 스냅샷 불변. 빠진 것:
- **S4 (should)** 전치사: rule:151 은 `[in|by <target>]` 만 보여 준다. `landed by X`, 맨 `landed` 는 REC-STATUS-BAD 가 된다(records_check.py:69-72). "landed in <path>, superseded by <path>, rejected [by ...]" 로 적는다.
- **S4** 이동 경로: rule:153 `archive/<origin folder>/` 에 "same subpath" 가 없어 평평하게 옮길 수 있다. skill:51 처럼 `<origin folder>/<same subpath>`.
- **S4** 갈음할 때 옛 문서는 status 줄만 바꾸고 본문은 그대로(skill:52). 닫을 때 본문을 "정리"하는 실수를 막는 줄이라 rule 에도 있어야 한다.
- note: "Never both"(frontmatter 와 첫 줄)도 rule 에 없다. 한 구절이면 된다.
세 줄을 더해도 10줄 안이다.

## 4. changes.md 실현성

- `CODERAG_PLUGIN_ROOT`: bin/coderag:8 이 바이너리를 고르기 전에 늘 export 하고, hooks.json 의 다섯 훅이 모두 `${CLAUDE_PLUGIN_ROOT}/bin/coderag` 를 부르므로 훅 경로에서는 보인다. PATH 의 `coderag` 도 이 래퍼다(`which coderag`). post_tool 의 `packs.is_empty()` 조기 반환(rules/mod.rs:314)을 내장 팩 뒤로 옮기자는 지적과 출력 머리 문장(mod.rs:254-257)이 그대로 맞는다는 점도 맞다.
- 대조 테스트 주장은 맞다: test-coderag-rules-parity.py:31-41 은 target 바이너리를 직접 부르고 `base_env` 에 그 변수가 없다. 다만 **note** packs/web-security/tests/test-web-security.py:14,31 은 래퍼를 부르므로 변수가 설정된다. `--pack` 이면 내장 팩을 넣지 않는다는 규칙(changes.md:52)에 기대므로 그 테스트도 검증 목록에 넣는다.
- **S5 (should)** Q2(a) 로 `status: superseded by X` 만 쓰면 post-edit 의 즉시 대상 검사가 사라진다: hook.rs:53-69 는 `superseded_by` 키만 본다. stale(stale.rs:157)과 records_check 는 잡지만 쓴 직후 알림이 없다. `lint_file_all` 이 status 줄 대상(`superseded by`, 경로 꼴 `landed in`)도 보게 한다.
- 이중 주입: 두 쪽 모두 rule 파일을 실행 때 읽으므로 창은 "세션 재시작 전"(changes.md:149)이 아니라 두 커밋 사이의 디스크 상태다. note: 이 기기에는 `/code/.claude/plugins/cache/coderag-market/coderag/0.2.0`(target 포함) 캐시 사본이 있다. HUMAN_TODO:36 은 저장소를 바로 읽는다고 적었으므로, 4단계에서 실제 훅의 플러그인 루트가 어느 쪽인지 확인한다.
- **S6 (should)** 동료 기기: qwreey-conventions 만 켠 기기에서는 기록 rule 이 사라지고, records_check·doctor 가 가리킬 `coderag:agent-records` 스킬도 없다. coderag 는 Rust 빌드가 있어야 돈다(bin/coderag:37-39), 바이너리가 없으면 훅은 조용히 0 으로 끝난다(:34-36). doctor 의 PACK-NO-CODERAG 는 팩이 켜졌을 때만 뜬다(doctor SKILL.md:68). changes.md:131 은 이것을 HUMAN_TODO 의 사실로만 적었는데, 이는 사용자가 정할 일이다(아래 Q6). doctor 에 "coderag 플러그인 켬, 바이너리 없음 → 기록 rule 없음" 항목이 필요하다.
- note: `HARNESS_CONVENTIONS_RULES=off` 로 rule 을 끈 사람은 이제 이 rule 을 받는다(`CODERAG_RULES=off` 가 따로 필요). HUMAN_TODO 한 줄.
- note: `lint_scope` 의 SKIP_DIRS 를 아무 조각에나 적용하면(changes.md:79) `research/agents/비교.md` 같은 진짜 기록도 빠진다. `research/drafts/**` 아래로 좁히거나 "선택"을 빼고 미룬다.
- note: changes.md:46,106 의 "지우기는 사용자 확인 뒤"는 이미 풀렸다: PLAN.md:200 "그 부분은 삭제 해도 돼". 다시 묻지 않는다. parse_doc 은 lib.rs:788(833 아님).
- note: skill:82 "coderag lint: ... status grammar" 는 frontmatter 안만이다. 첫 줄 status 문법은 records_check 만 본다(lint 는 frontmatter 가 없으면 lib.rs:986-988 에서 끝남).

## 5. 열린 질문

- Q1 (a): 맞다. 남은 참조 다섯 곳이 어차피 고쳐질 파일이라는 계산도 확인했다(coderag README·tech-design·hook.rs·docs-backfill·TODO, 다른 형제 저장소 grep 0건).
- Q2 (a): 맞다. 단 S5 를 같이 해야 "coderag 가 이미 읽는다"가 쓰는 순간의 검사까지 덮는다.
- Q3 (a): 맞다(coderag.toml 없는 저장소가 대부분). 끄기 스위치가 바뀌는 점(위 note)을 추천 이유 옆에 적는다.
- Q4 (a): 손 사본은 "정본 하나"에 두 번째 사본을 만든다. 위임 에이전트가 기록을 쓰는 일이 드물다는 초안 자신의 판단(changes.md:142)대로면 (b) 가 더 싸다. (a) 를 고른다면 rule 본문과 템플릿 절을 바이트로 비교하는 테스트를 붙인다. 추천을 (b) 로, 또는 (a)+대조 테스트로.
- 빠진 질문:
  - **Q5 (must, M1)** frontmatter: 새 살아 있는 문서에 필수로 남길지(audit/38 합의 3) 권장으로 낮출지(M5 본문 색인 근거).
  - **Q6 (should, S6)** qwreey-conventions 사본을 지우는 때: 지금(동료 기기에는 coderag 배포 전까지 기록 rule 없음), 또는 coderag 를 동료에게 배포한 뒤.

## 6. 길이와 agent-docs

- 스킬 86줄, references 57줄, rule 본문 7줄. 원래 둘(61+83줄)보다 작다. 이력 서술, 감사·라운드 번호, 정정 배너가 없다. "older key"·"old `plans/`" 는 지금도 읽는다는 현재 사실이라 괜찮다.
- 이유 한 문장: skill:47(base 가 남는 이유), skill:57(description), refs:89(팩 문서 필수 이유)는 있다. skill:56 "Do not backfill" 에는 이유가 없다(원본도 없음, note).
- D README:30, changes.md:83 의 audit/38 경위는 초안 기록 안이라 괜찮다. 다만 그 문장이 코드 주석으로 옮겨지면 안 된다(주석은 "frontmatter 가 없으면 첫 줄 status 를 읽는다"까지만).

## 판정: proceed after fixes

최소 고침:
1. M1/Q5: frontmatter 선택을 "정한 것"에서 빼고 사용자 질문으로 올린다(또는 필수를 그대로 둔다). 이에 따라 lint 수준 표(changes.md:60-69)도 그 답을 따른다.
2. Q6 추가, doctor 에 coderag 바이너리 없음 → 기록 rule 없음 항목.
3. skill:48 plan 문구, backfill 완료 배너 제외, records_check·doctor 문구에 "아직 현재 원천이면 active 로 되돌림" (S1-S3).
4. rule 본문에 전치사, same subpath, 갈음 시 본문 보존 (S4).
5. hook.rs `lint_file_all` 에 status 줄 대상 검사 (S5).
6. Q4 추천을 (b) 또는 (a)+대조 테스트로.
7. changes.md 의 삭제 재확인 문구 삭제(PLAN.md:200), PLAN.md:181·archive/README.md:3 추가, web-security 테스트를 검증 목록에.
