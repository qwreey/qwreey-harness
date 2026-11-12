# 바뀔 파일 (이 초안이 들어갈 때)

이름은 추천안(`coderag:agent-records`, rule `agent-records`)으로 적었다. 다른 이름을 고르면 아래의 그 이름만 바꾼다. 줄 번호는 이 초안을 쓴 시점(claude-doctor 35c0eda) 기준이다.
"닫다" = status 가 active 를 떠나는 것. "끝난 문서" 표현은 모두 이 뜻으로 바꾼다(일을 끝낸 것은 닫을 이유가 아니다).

## 1. coderag (형제 저장소, 그 저장소 승인 뒤)

### 새 파일
- `skills/agent-records/SKILL.md` ← 이 폴더의 `skills/agent-records/SKILL.md`.
- `skills/agent-records/references/frontmatter-keys.md` ← 이 폴더의 같은 경로.
- `rules/agent-records.md` ← 이 폴더의 `rules/agent-records.md`.

### 지울 파일
- `skills/docs-frontmatter/SKILL.md`(내용은 새 스킬과 references 로 옮겼다). 지우기는 HUMAN_TODO 규약상 사용자 몫이다: 선택 (a) 승인이 이 `git rm` 까지 덮는지 사용자에게 한 줄 확인한다.

### 코드: 플러그인 자체 rule 주입 (`crates/coderag-core/src/rules/mod.rs`)
coderag 플러그인은 팩이 아니어서 지금은 그 `rules/` 를 아무도 읽지 않는다. 플러그인 루트를 **내장 팩** 하나로 다룬다.
- 새 함수 `builtin_pack() -> Option<(String, PathBuf)>`: `CODERAG_PLUGIN_ROOT`(래퍼 `bin/coderag` 가 export) 가 있고 그 아래 `rules/` 가 디렉터리면 `("coderag", 그 루트)`. `CLAUDE_PLUGIN_ROOT` 는 보지 않는다(다른 플러그인 훅의 값일 수 있다).
- `post_tool`: `active_packs(...)` 결과 앞에 내장 팩을 붙인다. 내장 팩은 프로젝트 `[[packs]]` 목록과 무관하게 켜진다: 플러그인을 켠 것이 곧 동의이고, 지금 qwreey-conventions rule 도 그렇게 모든 저장소에 실린다. 그래서 `if packs.is_empty() { return None; }` 를 내장 팩을 붙인 뒤로 옮긴다.
- 전역 `--pack <이름>` 을 주면 내장 팩을 넣지 않는다(시험·대조용이 그 팩만 보게).
- 프로젝트 목록에 이름 `coderag` 인 팩이 있으면 경고하고 내장 쪽을 쓴다(중복 키 충돌 방지).
- 끄기: 기존 `CODERAG_RULES=off`(전부), rule 하나는 기존 `[rules] exclude = ["agent-records"]`·`.claude/conventions.json` `rules_exclude`. 새 스위치는 만들지 않는다.
- `matching()`(`coderag rules --for`)에도 같은 순서로 내장 팩을 넣는다.
- 출력은 그대로 `<rule plugin="coderag" name="agent-records">`, 머리 문장 "Path-scoped rules from the coderag plugin, …". 중복 제거 키 (세션, agent, 회차, `coderag.agent-records`).
- 테스트(`rules/tests.rs`): 목록 없는 프로젝트에서도 `CODERAG_PLUGIN_ROOT` 가 있으면 주입, `--pack` 이면 미주입, exclude 로 빠짐, `.claude/audit/x.md` Read 에 맞음·`.claude/rules/x.md` 에 안 맞음.
- claude-doctor `tools/tests/test-coderag-rules-parity.py` 는 바꿀 필요 없다: 자식 환경을 `base_env` 로 새로 만들어 `CODERAG_PLUGIN_ROOT` 가 없다.

### 코드: lint 수준 ("frontmatter 선택"에 맞춤)
- `crates/coderag-mdfm/src/lib.rs` `lint()`: `Vec<String>` 대신 `Vec<(Sev, String)>`(`enum Sev { Error, Advice }`). 수준:
  | 지적 | 지금 | 바꿈 (프로젝트 문서) | 팩 문서 |
  |---|---|---|---|
  | frontmatter 없음 | Error "frontmatter 없음 — title·description 필수" | Advice "frontmatter 없음(선택) — 새 살아 있는 문서면 title·description 권함" | Error 유지 |
  | title 없음 | Error | Advice "title 없음 — 첫 H1 을 제목으로 씀" | Error 유지 |
  | description 없음 | Error | Advice "description 없음 — 검색 요약은 첫 문단으로 대신함" | Error 유지 |
  | 닫히지 않은 `---`, 틀린 kind·status·날짜, description 200자 초과, superseded 대상 없음·불일치 | Error | 그대로 | 그대로 |
- `crates/coderag-core/src/lint.rs` `lint_text`: `Sev::Advice` → `Level::Info`, 단 `ctx.pack_doc` 이면 → `Level::Error`. 그러면 `coderag lint` 는 frontmatter 없는 옛 기록에 종료 0(`--verbose` 에서만 보임).
- 테스트: mdfm `lib.rs:1273`·`1276` 의 기대 문자열과 수준, `lint.rs` 에 pack_doc 대 project 대조 하나.

### 코드: post-edit 훅 (`crates/coderag-cli/src/hook.rs`)
- `post_edit`: 지금 `lint_file` 은 blocking 만 모아 frontmatter 없음이 Info 가 되면 사라진다. 이렇게 바꾼다:
  - 오류·경고는 지금처럼 Write·Edit 모두 알린다.
  - 권고(Info) 중 frontmatter 계열 셋은 `tool_name == "Write"` 이고 `rel` 의 첫 조각이 `plan`·`base`·`research`(또는 `packs/<팩>/` 아래 그 셋)일 때만 알린다. 옛 문서를 Edit 할 때는 알리지 않는다(채워 넣기를 재촉하지 않게, 지금 `retain` 이 하는 일).
  - `hook.rs:85-89` 의 문자열 접두어 `retain` 은 위 규칙으로 대체한다.
- 알림 문구(`hook.rs:93-96`) 교체:
  - 오류·경고가 있을 때: `coderag: .claude/{rel} — {issues}. 기록 규약은 coderag:agent-records 스킬, 키 목록은 그 스킬의 references/frontmatter-keys.md.`
  - 권고만 있을 때: `coderag: .claude/{rel} 에 frontmatter 가 없다(선택). 새 살아 있는 문서라면 title·description 을 권한다: description 이 검색 결과에 찍히는 한 줄이다. 넣지 않아도 된다.`
- `lint_scope`: `SKIP_DIRS` 를 `.claude` 바로 아래 첫 조각만이 아니라 경로의 어느 조각에 있어도 건너뛰게(`rules`, `skills`, `agents`). 지금은 `.claude/research/drafts/x/rules/a.md` 같은 초안 사본이 기록으로 lint 된다(이 초안을 쓸 때 실제로 "title 없음" 알림이 났다). 선택 사항.
- 테스트 `missing_frontmatter_only_on_write`(Write 는 `base/` 에서 권고 알림, Edit 는 없음, `research/` 도 Write 알림, `README.md` 는 없음), `post_edit_reports_once_per_session` 의 `contains("frontmatter 없음")` 기대 문구.

### 코드: 첫 줄 status 읽기 (권장)
- `crates/coderag-mdfm/src/lib.rs` `parse_doc`(833행 부근): frontmatter 가 없으면 첫 줄 `^status:\s*(.*)$` 를 같은 `parse_status` 로 읽는다. 이유: frontmatter 가 선택이 되면 새 문서도 첫 줄 status 를 쓰고, 지금은 그런 문서가 늘 active 로 색인되어 static-gen 표와 stale 의 갈음 대상 검사가 그 status 를 못 본다. (audit/38 은 첫 줄 문서가 옛 초안뿐이라 이 파서를 넣지 않기로 했었다. 그 전제가 이번에 바뀐다.)
- `crates/coderag-core/src/docs/index_md.rs:68-70` `status_cell`: frontmatter 가 없어도 "frontmatter 없음" 대신 status(기본 active)를 보인다. 같은 기대 문자열 테스트 `index_md.rs:247`.

### "끝난" 표현 (주석·문서)
- `crates/coderag-mdfm/src/lib.rs:411` 주석 "active 가 아닌 끝난 status" → "active 가 아닌(닫힌) status".
- `crates/coderag-core/src/docs/search.rs:275` 주석 "끝난 문서는 한 번만 강등한다" → "닫힌 문서(active 아님·archive 아래)는 한 번만 강등한다".

### 문서·설정
- `skills/docs-backfill/SKILL.md`
  - 11행 "규약은 `coderag:docs-frontmatter` 스킬. 먼저 그것을 읽는다." → "규약은 `coderag:agent-records` 스킬(키는 그 `references/frontmatter-keys.md`). 먼저 그것을 읽는다."
  - 28행 "`kind`(폴더로 추정 — docs-frontmatter 의 표)" → "`kind`(폴더로 정해지면 쓰지 않는다 — frontmatter-keys.md 의 표)".
  - 29행 status 추정 → "status: archive/ 아래면 쓰지 않는다(폴더가 정한다). 그 밖은 `active` 로 둔다. 배너나 갈음 언급으로 닫을 후보로 보이면 diff 에 쓰지 말고 보고에 후보로 적는다: 닫기는 `git mv` 가 따르는 별도 결정이고, 일을 끝냈다는 표시만으로는 닫지 않는다." (본문 불변 원칙과 archive 이동 의무가 충돌하지 않게.)
- `README.md:18` "스킬 `coderag:docs-frontmatter`(쓰기 규약)" → "스킬 `coderag:agent-records`(.claude 기록 규약: 폴더, status, 닫기와 archive, 선택 frontmatter)". 19행 훅 줄에 "`.claude/` 기록을 열고 쓸 때 기록 규약 rule 주입" 을 더한다.
- `tech-design.md`
  - §11.8 `333행` "스킬: `docs-frontmatter`(쓰기 규약), …" → "스킬: `agent-records`(기록 규약, 키 참조는 references), `docs-backfill`(…)". 331-332행의 post-edit 설명에 "frontmatter 없음·title·description 없음은 프로젝트 문서에서 권고(info), 새 살아 있는 문서 Write 때만 알림" 을 더한다.
  - §13.3 팩 rule 단락 뒤에 한 항목: "**내장 팩 `coderag`**: 플러그인 루트(`CODERAG_PLUGIN_ROOT`)의 `rules/` 는 프로젝트 목록과 무관하게 켜진다(플러그인을 켠 것이 동의). `--pack` 을 주면 빠진다. 끄기는 다른 rule 과 같다."
  - `1213행` 위험 표 "필수는 그대로 둘" → "팩 문서는 title·description 필수, .claude 기록은 선택(새 살아 있는 문서에 권함)".
- `TODO.md`: 새 항목 "- [ ] 내장 팩 rule 주입(플러그인 `rules/`), agent-records 스킬·rule, lint 수준 조정, 첫 줄 status". 26행 완료 항목은 그때의 사실이라 그대로 둔다.
- `.claude-plugin/plugin.json`: version 0.2.0 → 0.3.0, description 에 "기록 규약(agent-records 스킬과 .claude 기록 rule 주입)" 을 더한다.
- `hooks/hooks.json` description: "팩 rule 주입" → "팩과 coderag 자체의 rule 주입(기록 규약 포함)". matcher 는 그대로(이미 Read|Edit|Write|…).

## 2. claude-doctor

### 지울 파일 (사용자 확인 뒤, 위와 같음)
- `plugins/qwreey-conventions/skills/agent-records/SKILL.md`
- `plugins/qwreey-conventions/rules/agent-records.md`

### 고칠 파일
- `plugins/qwreey-conventions/tests/test-rules-inject.py:61` 기대 집합에서 `"agent-records"` 를 뺀다.
- `plugins/qwreey-conventions/.claude-plugin/plugin.json` version 0.6.2 → 0.7.0(스킬·rule 제거).
- `plugins/qwreey-conventions/README.md`: 스킬 표에 agent-records 줄이 없고 13행 rules 목록도 이미 넷(comments, agent-docs, code-structure, memory)이라 그대로 맞다. 끝에 한 줄 "기록 규약(.claude/)은 coderag 플러그인의 `coderag:agent-records` 가 맡는다" 를 더한다.
- `CLAUDE.md:11` "laid out per `plugins/qwreey-conventions/skills/agent-records/SKILL.md`" → "laid out per the `coderag:agent-records` skill (`../coderag/skills/agent-records/SKILL.md`)".
- `CLAUDE.md:12` "`.claude/archive/`: finished records at their original subpath" → "`.claude/archive/`: living records that left active (landed, superseded, rejected, archived) at their original subpath".
- `.claude/README.md:3` "per the `qwreey-conventions:agent-records` skill" → "per the `coderag:agent-records` skill".
- `.claude/README.md:9` archive 줄의 설명 "finished living records" → "living records that left active (no longer a current source)".
- `README.md:15` "끝난 초안은 `.claude/archive/research/drafts/` 로 옮긴다" → "결론이 자리 잡았거나(landed) 접은(rejected) 초안은 `.claude/archive/research/drafts/` 로 옮긴다".
- `.gitignore:10` 주석 "(agent-records 규약)" → 이름을 그대로 두면 바꾸지 않는다. 다른 이름이면 그 이름으로.
- `plugins/q/skills/doctor/SKILL.md:43` "`REC-` codes follow the `qwreey-conventions:agent-records` skill" → "`coderag:agent-records` skill"; "list `REC-FINISHED-OUTSIDE-ARCHIVE` files as one "move to archive" fix item" → "list `REC-CLOSED-OUTSIDE-ARCHIVE` files (status already not active) as one "move to archive" fix item". 덧붙임: "Never propose closing a doc because its work is done; whether a doc is still a current source is the repo's call."
- `plugins/q/skills/doctor/SKILL.md:67` 표 마지막 칸 → "`coderag:agent-records` skill".
- `plugins/q/scripts/records_check.py`
  - 2행 docstring "against the qwreey-conventions:agent-records convention" → "against the coderag:agent-records convention".
  - 143-144행 주석 "a file under archive/ is finished by where it is" → "a file under archive/ is closed by where it is".
  - 157행 코드와 문구: `REC-FINISHED-OUTSIDE-ARCHIVE`, "status %s but not under archive/" → `REC-CLOSED-OUTSIDE-ARCHIVE`, "status %s (not active) but not under archive/: git mv to archive/<origin>/ in the same commit". 코드 이름의 "FINISHED" 가 "일을 끝낸 문서" 로 읽히기 때문이다. 이 코드를 쓰는 곳은 이 파일, `tests/test_records_check.py`, doctor SKILL.md 셋뿐이다(그 밖 grep 0건).
- `plugins/q/tests/test_records_check.py:54-55` 기대 코드 이름 네 곳.
- `plugins/q/tests/records-fixtures/.claude/plan/landed.md` description "Finished, outside archive" → "Closed (landed), outside archive".
- `plugins/q/.claude-plugin/plugin.json` version 0.8.8 → 0.8.9.
- `.claude/research/README.md`: 색인에 `drafts/records-in-coderag/` 줄 하나, 설명 "merged records convention for coderag: skill, rule and change list" (이 초안을 쓴 에이전트는 이 폴더 밖에 쓰지 않았다. records_check 가 `REC-INDEX-MISSING` 으로 잡는다). 들어간 뒤에는 이 폴더를 `landed in ../coderag/skills/agent-records/` 로 닫고 `archive/research/drafts/` 로 옮긴다.
- `PLAN.md` 3.9: "기록 규약 정본은 coderag(`coderag:agent-records`), qwreey-conventions 의 사본은 뺐다, `records_check.py` 이전은 다음 단계" 한 줄. 사용자 결정 원문은 이미 PLAN 에 있는 형식대로.
- `HUMAN_TODO.md` "다른 기기에 배포할 때" 항목에 덧붙임: "기록 규약 rule 은 coderag 바이너리가 있어야 실린다(래퍼는 바이너리가 없으면 훅에서 조용히 0 으로 끝난다). qwreey-conventions 만 켠 기기에는 이제 기록 rule 이 없다."
- 스냅샷(`audit/`, `handoff/`, `sessions/`)과 `archive/` 안의 `agent-records`·`docs-frontmatter` 언급은 그때의 사실이라 고치지 않는다(경로가 옮겨진 것이 아니므로 경로 치환 대상도 아니다).

### 바꾸지 않는 것 (확인함)
- `home/`: `agent-records`·`docs-frontmatter` 언급 0건.
- 다른 형제 저장소: 두 이름 언급 0건(`/code/Projects` 전체 grep, `.git`·`target`·`.coderag`·worktrees 제외).
- `home/settings-migrations`: coderag 플러그인을 켜는 마이그레이션은 없다(이 기기는 사용자가 직접 설치). 동료 배포에서 기록 규약을 싣으려면 coderag 를 켜는 마이그레이션이 따로 필요하다. 그것은 배포 결정이라 여기서 만들지 않는다.

## 3. Codex·agy

경로 조건부 rule 주입은 Claude Code 훅뿐이다. codex·agy 는 `AGENTS.md` 를 읽고(agy 는 `.agents/rules/*.md` 와 `GEMINI.md` 도), 스킬도 읽는다(coderag/.claude/research/team-sharing.md §35.10).
- 지금: claude-doctor 에서 codex·agy 는 위임으로만 돈다. 위임 템플릿 `.claude/research/drafts/delegate/skills/delegate/templates/AGENTS.md.template` 에 "## 기록 (.claude/)" 절을 더하고 본문은 `rules/agent-records.md` 의 본문 7줄을 그대로, 마지막 줄만 "Details: `<coderag root>/skills/agent-records/SKILL.md`"(평문 경로)로 바꾼다. 위임받은 에이전트가 `.claude/` 기록을 쓰는 일은 드물어서 상시 비용(약 1KB)이 작다.
- 나중(coderag M7, `[[outputs]] generator = "agents-md"`): 손 사본 대신 생성. 내장 팩의 `rules/*.md` 본문을 `<!-- coderag:begin agent-records -->` 마커 블록으로 저장소 `AGENTS.md`(또는 사용자 동의 뒤 `~/.codex/AGENTS.md`, `~/.gemini/config/AGENTS.md`)에 쓴다. 원천이 rule 파일 하나라 Claude 와 codex·agy 의 문구가 어긋나지 않는다. agy 는 `.agents/rules/` 에 같은 파일을 둘 수도 있지만, AGENTS.md 와 둘 다 두면 두 번 실리므로 하나만.

## 4. 들이는 순서

1. coderag: 내장 팩 코드, lint·훅, 스킬·rule·references, 문서. `cargo test`, `coderag rules --for .claude/base/x.md` 로 `coderag.agent-records` 확인, 빌드(바이너리가 있어야 훅이 돈다).
2. claude-doctor: qwreey-conventions 의 스킬·rule 제거와 나머지 고치기, `python3 -I plugins/qwreey-conventions/tests/test-rules-inject.py`, `python3 -I plugins/q/tests/test_records_check.py`, `python3 -I tools/tests/test-coderag-rules-parity.py`.
3. 두 커밋을 같은 세션 재시작 전에 둔다. 1만 들어간 사이에는 두 rule 이 같은 파일에 둘 다 실리고(문구가 다른 같은 규약), 2만 들어간 사이에는 기록 rule 이 없다.
4. 새 세션에서 `.claude/base/` 파일 하나를 Read 해 `<rule plugin="coderag" name="agent-records">` 가 한 번만, qwreey-conventions 쪽은 없음을 본다.
