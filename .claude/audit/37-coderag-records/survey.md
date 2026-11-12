# 37 coderag 를 기록 시스템의 뼈대로 쓸 수 있나 (읽기 전용 조사)

조사일 2026-11-12. `/code/Projects/coderag` 는 읽기만 했다(git status 깨끗, 쓴 것은 /tmp/cr 뿐). 표기: [구현] = 코드·실행으로 확인, [설계] = 문서에만 있음.
경로는 `/code/Projects/coderag/` 기준 상대. 실행은 `target/debug/coderag`(2026-11-11 빌드)를 `CODERAG_HOME=/tmp/cr/home CODERAG_CACHE=/tmp/cr/cache` 로, /tmp 에 복사한 claude-doctor 문서(decisions, PLAN, audit36)로 했다.

## 결론 먼저
- 검색·색인·README 색인 생성·stale·lint·haiku 위치 조사 에이전트(doc-locator)는 이미 [구현]돼 있고 실제로 돈다. 우리가 원하는 "찾기" 쪽은 거의 그대로 쓸 수 있다.
- 빠진 것은 우리 모델의 **상태 어휘**(landed in X / rejected)와 **폴더 규칙 검사**(끝난 문서가 archive 밖, 색인 항목 누락, 항상 로드 예산)다. coderag 의 status 는 active|superseded|archived 셋뿐이라 그대로는 우리 상태 줄과 안 맞는다.
- 권고: coderag 는 **선택적 가속기**(찾기·색인 표·stale 알림)로 쓰고, 상태 줄·폴더 규칙·archive 이동은 claude-doctor 쪽 평문 규약과 작은 검사기로 둔다. 기록 형식을 coderag 에 종속시키지 않는다(7장).
- 바이너리는 PATH 에 없고(`which coderag` 실패), `target/debug/coderag` 만 있다(53MB 디버그 빌드). 플러그인 래퍼 `bin/coderag` 가 찾아 준다. 배포 방식은 미정(TODO.md "마켓 등록").

## 1. 마크다운 지원 (`crates/coderag-mdfm`)
- 의존성 없는 순수 파서(`crates/coderag-mdfm/src/lib.rs`, 1164줄) [구현]. YAML 부분집합: `key: v`, `[a, b]`, `- 항목`, `>`/`|`, 따옴표(tech-design.md:291).
- 문서 단위 필드(`ParsedDoc`, lib.rs:330-345): title, description, summary(없으면 첫 문단 160자), keywords, kind, status, superseded_by, last_verified, review_after, line_count, sections, refs, hash(fnv1a, lib.rs:717).
- kind 알려진 값(lib.rs:14-17): base research session review decision archive plan audit reference index guide todo unknown. **우리 폴더 이름과 거의 일치**(plan, base, audit, research, archive, session 은 `sessions` 가 아니라 `session`). kind 는 폴더에서 추론하지 않고 frontmatter 에만 의존, 없으면 `unknown`(lib.rs:763). 실측: frontmatter 없는 decisions/D-01 은 `[unknown]` 으로 나왔다.
- status(lib.rs:19): `active|superseded|archived` 만. `superseded`·`archived` 는 검색에서 숨김(`listed()`, lib.rs:351). 실측: `status: landed in base/x.md` 는 lint 오류("active|superseded|archived 중 하나"), 색인에선 status=active 로 떨어지고 원문은 `meta.extra.status` 에 남음. `status: verified|described|partial` 은 근거 등급(evidence)으로 읽힘(lib.rs:21, meta.rs:5).
- 절 메타 줄(본문의 `키: 값 · 키: 값`)과 확장 키 `KNOWN_META_KEYS`(lib.rs:522-524): id status evidence last_confirmed last_verified review_after category tags lifecycle applies_to since source origin see superseded_by overrides rfc. category·tags·lifecycle(8단계)·applies_to 는 tech-design.md §16-18, 코어 `docs/meta.rs`·`taxonomy.rs`·`version.rs` 가 정규화·상속(절←파일←pack)한다 [구현](CLAUDE.md:41-45).
- 절: `##`·`###` 제목 하나가 section Info, 펜스 안 제목 무시, 중복 slug 는 `-1`(tech-design.md:256-262). 절마다 줄 범위·토큰 추정(`~1.1k`)(§21).
- 링크·인용: 마크다운 링크 대상 + 경로처럼 생긴 코드 스팬(`a/b.md:12` 줄 표기는 뗌) 을 `refs` 로 뽑고(lib.rs:272-285), 직전 `§N` 절 참조와 "스킬 이름 + references/…" 도 해석(`refpath.rs`). 사용자 말 인용·날짜 표기는 파싱 안 함.
- 스키마/검증기: 있다. `coderag lint <파일…>`(lib.rs:905-950): frontmatter 없음, title/description 필수, description 한 줄 200자(스킬은 1024), kind 어휘, status 어휘, superseded 인데 superseded_by 없음, `last_verified`·`review_after` 날짜 형식. 오류·경고가 있으면 종료 코드 1 [구현]. 우리가 원하는 "status 줄 규약"을 검사하려면 status 어휘 확장이 필요(6장).

## 2. 검색 (CLI)
- 명령(실행한 `--help`, README.md:25-37): `gen`, `search`, `list`, `get`, `stale`, `static-gen`, `lint`, `taxonomy`, `pack`, `hook`; `mcp` 는 "미구현"(main.rs:746).
- `coderag search <낱말…>` 옵션: `--kind --module --all(숨김 포함) --layer --pack --limit(기본 8) --json --abs --hint --category --tag(AND) --evidence --lifecycle '>=implemented-cli' --version/--luau --strict-version`. path 필터는 없다(path 는 점수 가중 2, tech-design.md:304).
- 랭킹: 결정적, 임베딩 없음. keywords 8 > 포함 6 > title 5 > description 3 > path 2, 절 제목 4·요약 2, archive·숨김 ÷2(tech-design.md:300-304). 본문 낱말은 색인하지 않음(TODO.md "선택: 본문 낱말 저가중치") — **제목·요약·keywords 에 없는 내용은 못 찾는다**.
- 출력: 한 건 두 줄. `경로:시작-끝 ~토큰  제목 § 절  [kind · …]` + 요약 120자. `--json` 은 id, path, rel, lines, kind, status, listed, review_after, score, sections, tokens_est, layer 등. `--abs` 면 절대경로(에이전트가 Read offset/limit 으로 바로 읽음). 실측 출력 예: `/tmp/cr/proj/.claude/decisions/D-01-const.md:75-78 ~0.1k  D-01. ... § 사용자 결정 (2026-11-10)  [unknown]`.
- 지연: `gen` 155항목 0.032초, `search` 0.006초(실측). CLAUDE.md 기록은 stl-luau 127문서 0.24초.
- 색인 필요: 예. `coderag gen` 으로 `.coderag/`(project 루트, `$CODERAG_CACHE` 로 대체 가능)에 JSONL 텍스트 캐시를 만든다. 서버·데몬 없음. 색인이 없으면 "먼저 coderag gen" 오류. **자동 갱신은 미구현**: M9(mtime 검사 B + 훅 A)가 TODO(TODO.md, tech-design.md §22). 지금은 `stale` 이 "색인 이후 바뀜/새 문서"를 알려 주는 정도.
- haiku 1-3 Bash 호출로 쓸 수 있나: 예. 플러그인에 `agents/doc-locator.md`(haiku, tools Bash+Read, Edit/Write 금지, maxTurns 12)가 이미 있고, PreToolUse 훅 `coderag hook pre-bash` 가 `coderag search|get|list|stale` 밖의 Bash 를 막는다(hooks/hooks.json, tech-design.md:331). 응답 형식은 `- <절대경로>:L<a>-<b> ~<토큰> — 근거 한 줄` 5개 이하, 옛 기록(archive/superseded)은 "옛 기록" 표시. 즉 우리 recall 의 locate 단계가 이미 설계·구현돼 있다. 단 doc-locator 는 `coderag` 플러그인을 설치해야 존재하고, 색인이 없으면 호출 쪽이 `gen` 을 먼저 돌려야 한다.
- 이 샌드박스: 바이너리는 있고 실행됨(PATH 밖). Rust 툴체인은 `mise where rust`(CLAUDE.md:58). 읽기 명령은 `.coderag` 를 만들지 않는다(project.rs:50), `gen` 만 쓴다 — 남의 저장소에서는 `CODERAG_CACHE=/tmp/...` 필수. 이 조사에선 /tmp 만 썼다.

## 3. Staleness (`crates/coderag-core/src/docs/stale.rs`, `coderag stale`)
`coderag stale` 은 색인 + 원문 파일의 존재·해시만 본다(tech-design.md:309-315) [구현]. 보고 형태: `경로:줄  메시지` 한 줄씩, 끝에 `stale N건 (문서 M개 검사)`, `--json` 가능.
- `review_after` 지남(오늘 UTC, `CODERAG_TODAY` 로 고정). 없으면 `last_verified + 범주 review_days(기본 90일)`(stale.rs:69). **frontmatter 가 있는 문서만**(없는 기존 기록은 날짜 판정 제외, stale.rs:126).
- `superseded_by` 대상 없음. 실측: `status: superseded` + `superseded_by: plan/zzz.md` → "superseded_by 대상 없음".
- 없는 경로 참조(깨진 링크·코드 스팬 경로). 실측: `[gone](missing.md)` 와 `` `base/nope.md` `` 를 모두 L9 에서 잡음. 기본은 frontmatter 가 있는 활성 문서만, 기록류(kind archive·session·audit·review·research, 경로에 archive/·session/)는 옛 경로를 보존하므로 제외(`--refs-all` 로 확장). 스킬 라우팅 `경로 §N` 의 절 번호 어긋남도 검사(stale.rs:179).
- 원문이 색인 이후 바뀜(source_hash)/지워짐/색인에 없는 새 문서. 버전 낡음(`applies_to` 핀 vs 도구 버전, §18).
- **없는 것**: "오래된 기록을 읽을 때 경고"(읽는 순간의 알림)는 없다. 검색 결과에도 문서 나이·작성일이 안 찍힌다(json 에 `last_verified`·`review_after` 값만). 우리가 원하는 "읽을 때 낡음 경고"는 별도.

## 4. project 계층 (무엇을 선언해야 하나)
- 선언 없이도 된다: 프로젝트 루트(`.coderag/` 나 `coderag.toml` 이 있는 첫 조상, 없으면 cwd 기준, project.rs:1-10)에 `.claude/` 가 있으면 **암묵 설정**으로 `.claude` 하나를 문서 루트로 색인(tech-design.md:272). 실측: `.claude/{decisions,plan,audit36}` 16문서가 그대로 색인됨.
- 여러 루트·제외는 `coderag.toml`: `[[contexts.docs]] provider=["markdown-frontmatter"]` + `[[contexts.docs.targets]] module=".claude" source=".claude" options={exclude=[...]}`(README.md:50-59). claude-doctor 처럼 기록이 `.claude/` 밖(루트의 audit/, decisions/ 등)에 있으면 `source="."` 같은 target 을 따로 적어야 한다(암묵 설정은 `.claude` 만).
- ignore 규칙: **git·.gitignore 를 보지 않는다**. `walk_markdown`(lib.rs:876-898)은 `*.md` 를 열거하고 기본 제외는 점으로 시작하는 디렉터리, `node_modules`, `worktrees`, `target`(lib.rs:25) + `options.exclude`(이름·상대경로·접두). 따라서 git 추적 `.claude/**` 도, gitignore 된 `.claude/sessions` 같은 것도 `.md` 면 똑같이 색인된다. 루트가 `.claude` 이므로 그 안의 점 디렉터리(예 `.claude/.cache`)만 빠진다. 심볼릭 링크 디렉터리는 안 따라감.
- 캐시 위치 주의: 기본이 `<project>/.coderag/`. 저장소에 생기므로 `.gitignore` 에 넣거나 `CODERAG_CACHE` 로 밖에 둬야 한다(CLAUDE.md 는 "텍스트라 git 커밋 권장"이라 했지만 기록 저장소엔 잡음이 된다).
- 다른 계층: global(`~/.coderag/coderag.toml`)과 pack(`[[packs]]`)은 검색 때 합쳐지고 꼬리표로 구분(§13). 이 기록 시스템은 project 하나면 충분.

## 5. 상태 (코드·문서 근거)
- CLAUDE.md:36-52 와 TODO.md: M0 골격, 문서 검색, M1-M6(계층·메타·taxonomy·pack·버전·luau-kb 채택)까지 완료 [구현]. `cargo test --workspace` 102개, clippy 경고 0 주장(미재실행).
- 문서 검색 쪽 미완(TODO.md "문서 검색 다음"): 마켓 등록·바이너리 배포 방식 미정, 색인 자동 갱신(M9), 교차 저장소 경로 표기 규약, `list --missing-frontmatter`, 랭킹 골든 테스트, 본문 낱말 색인.
- 미구현: `mcp`(에러로 끝남), M7 채널 A generator(AGENTS.md 등), M8 git pack, 골든 질의 저장소 내 픽스처. TS 쪽(typescript-swc)은 일부, jsdoc 은 스텁.
- 진행 상황: 최신 커밋은 tech-design §35(팀 공유 재설계, 서버 S1 잠정 확정·"급하지 않음", tech-design.md:2302-2361). 즉 개발의 무게가 **팀 공유 서버/구독/감사**로 가 있고, 기록 문서 검색 쪽은 안정 단계. 설계서는 2481줄로 커서 같은 저장소 안에서도 변동 폭이 크다.
- 작업 방식: 사용자가 에이전트 세션에 맡긴 저장소이고 큰 방향 전환은 사용자에게 묻도록 돼 있다(CLAUDE.md:55). 다른 세션이 동시에 작업할 수 있음.

## 6. 적합도 (원하는 기능별)

| 원하는 것 | 판정 | 근거 | 가장 작은 변경 |
|---|---|---|---|
| 문서마다 상태 줄(active / landed in X / superseded by Y / rejected + 날짜) | 부분 | status 는 active·superseded·archived 만, superseded_by 필드 있음(lib.rs:19, :933-941). landed·rejected 는 lint 오류 | coderag 쪽: KNOWN_STATUS 에 `landed`(+`landed_in`), `rejected` 추가하고 listed=false 로. 또는 claude-doctor 쪽: 상태를 본문 첫 줄 평문으로 두고 frontmatter 는 coderag 어휘(archived+superseded_by)로 한정. 상태 줄은 사람이 읽는 것이 먼저이므로 평문 우선 권고 |
| 폴더별 README 색인 | 대부분 | `static-gen --dir plan` 이 마커 블록 표(문서·설명·상태)를 멱등 생성, 마커 밖 보존(tech-design.md:317-322). 실측 dry-run 동작 | 표에 "상태" 열이 `kind · status` 인 점만 우리 상태 줄로 맞추기 |
| 검사: 깨진 링크 | 커버(조건부) | stale 의 "없는 경로 참조". 단 기본은 frontmatter 있는 활성 문서만, audit·session·archive 류 제외 | `--refs-all` 로 전부, 또는 우리 쪽 검사기(이미 claude-doctor 에 링크 검사가 있으면 그것) |
| 검사: 색인 누락(README 에 없는 문서) | 갭 | static-gen 은 생성기일 뿐 "누락 검사"가 아님(마커 밖 수기 표는 검사 안 함). 간접: `static-gen --dry-run` 이 "바뀔 예정" 이면 어긋남 | `static-gen --check`(바뀔 예정이면 종료 코드 1) 한 줄 추가, 또는 우리 검사기에서 dry-run 결과 사용 |
| 검사: 끝난 문서가 archive 밖 | 갭 | status=archived 는 있으나 폴더 위치와 비교 안 함 | lint 규칙 하나: `status` 가 archived/landed/rejected/superseded 인데 경로에 `archive/` 없음. coderag 에 넣기보다 우리 검사기가 빠름 |
| 검사: 항상 로드 크기 예산 | 갭(부품만) | `budget.rs` 는 읽기 토큰 추정(~토큰)이고 AGENTS.md 32KiB 경고 helper 가 있으나(커밋 766c31f) CLAUDE.md `@import` 합계 검사는 아님 | 우리 검사기에서 `@import` 따라가 바이트 합산(doc-check.py 방식). coderag 불필요 |
| 오래된 기록을 읽을 때 경고 | 갭 | 3장. 검색 결과에 나이 표시 없음 | 두 갈래: (a) coderag search 출력에 작성일/`last_verified` 와 "N일 전" 꼬리표(작은 변경), (b) doc-locator 응답 형식에 "옛 기록·N일" 줄 지시(에이전트 문서만 고침) |
| recall: haiku 가 찾고 sonnet 이 읽어 요약 | 대부분 | doc-locator 가 위치(경로:줄 ~토큰)만 반환, 큰 에이전트가 줄 범위만 읽음(agents/doc-locator.md) — q:recall 1단계와 같은 모양. q:recall SKILL.md 는 이미 "coderag search 도구가 있으면 global 계층을 먼저, 없으면 grep -rn" 으로 갈라 둠 | recall 의 haiku 브리핑에 `coderag search --abs --layer project …` 경로 추가하고, 색인 신선도 확인(`coderag stale` 의 "색인 이후 바뀜")을 첫 단계에. 색인 없으면 grep 폴백 유지 |
| 세션 기록(sessions/) 검색 | 부분 | `## 날짜 · trigger` 절과 `id: … · summary: …` 메타 줄은 coderag 의 "절 메타 줄(`키: 값 · …`)" 형식과 닮음(lib.rs:557 `parse_meta_line`는 알려진 키로 시작해야 인식) — 우리 줄은 `id:` 로 시작하므로 id 는 인식 가능성 있으나 미확인. kind=session 은 frontmatter 필요(2줄 snapshot 헤더에 `kind: session` 을 넣으면 해결) | snapshot 헤더를 frontmatter 로 하는지 결정 필요(8장) |

### "claude-doctor `.claude/` 를 coderag 로 구조화" 실험의 구체안
목표: 구조 규약(plan/base/audit/research/archive/handoff/sessions + 상태 줄 + README 색인)을 coderag 도움으로 정하되, 되돌릴 수 있게.
1. 별도 브랜치(예 `exp/records-coderag`) 또는 git worktree. coderag 는 읽기 전용 바이너리로만 사용, 캐시는 `CODERAG_CACHE=/tmp/cd-cache`.
2. 기준선 측정(변경 전): 문서 수·크기, 항상 로드 합계, `coderag gen` 시간, 대표 질문 10개(예 "D-04 가 뭐였지", "왜 luau-core 를 옮겼나")로 현재 방식(grep/recall)의 정답 위치 적중률·토큰.
3. `coderag.toml` 작성(claude-doctor 는 기록이 `.claude/` 밖이라 target 을 `audit`, `decisions`, `handoff`, `drafts`, 새 `.claude/*` 로 나눠 선언하거나 `source="."` + exclude).
4. 기존 문서 frontmatter 백필은 하지 않는다(문서 수가 많고 audit 은 "고치지 않음" 규칙). 새/이동 문서에만 `status`·`kind`·`description` 을 달고, 옛 문서는 `kind: unknown` 으로 둔 채 제목·첫 문단 색인에 맡긴다. 이것이 coderag 의 "frontmatter 없어도 동작"(tech-design.md:293)의 시험이다.
5. 폴더 이동(audit·handoff 등)은 사람이 승인하고 `git mv` 로만. 이동 뒤 `coderag stale --refs-all` 로 깨진 링크 목록을 얻어 CLAUDE.md·스크립트의 하드코딩 경로(audit/36 §3)와 대조.
6. `static-gen --dir <폴더>` 로 폴더 README 색인 생성 → 수기 부분과 마커 블록 분리 확인.
7. 측정: (a) 같은 10개 질문의 haiku locate 적중률·호출 수·토큰(grep 대비), (b) `stale` 잡음 비율(오탐: 보존 기록의 옛 경로), (c) lint 가 상태 어휘(landed/rejected)에서 막는 건수, (d) 색인 갱신을 잊었을 때의 오답 사례(M9 미구현의 실제 비용), (e) coderag 없이(PATH 에서 제거) 같은 문서를 읽을 수 있는지.
8. 롤백: 실험이 .claude 안에 만든 것은 git 이 추적하는 md 와 마커 블록뿐이어야 한다. `.coderag/` 는 /tmp 밖에 안 둔다. 실패 시 브랜치 폐기 또는 `git revert`. 마커 블록은 `<!-- coderag:begin/end -->` 사이만이라 `git diff` 로 분리해 볼 수 있다.

## 7. 위험
- 개발 중인 도구에 모든 저장소 기록을 묶는 위험: 설계서가 팀 공유 서버 쪽으로 크게 움직이는 중(§35), 캐시 포맷·ID 문법(파일 이동·제목 변경 시 ID 바뀜, tech-design.md:262)·status 어휘가 바뀔 수 있다. 큰 방향 전환은 coderag 저장소 규칙상 사용자에게 묻도록 돼 있으나 일상 변경은 에이전트 세션 몫이다.
- 어휘 충돌: coderag 의 status 의미(superseded·archived 는 검색에서 숨김)가 우리 `landed`/`rejected` 와 다르다. 어휘를 맞추지 않은 채 frontmatter 를 달면 lint 가 계속 경고하고, 완료 문서가 검색에 계속 노출되거나 반대로 숨는다.
- 색인 신선도: 자동 갱신 미구현이라 옛 색인이 "있는 문서를 없다" 하거나 줄 범위가 어긋난다(`get --body` 는 원문 줄 범위를 읽으므로 범위가 틀리면 엉뚱한 줄). doc-locator 는 오류 시 "색인 없음"만 보고한다.
- 본문 낱말 색인 없음: 제목·요약·keywords 에 없는 사실은 못 찾아 grep 이 여전히 필요. 세션 기록처럼 본문이 핵심인 곳에선 검색 품질이 제한된다.
- 배포: 바이너리 미동봉(`cargo build` 필요), PATH 에 없음, 마켓 등록 미정. 동료(비프로그래머)에게 퍼뜨릴 때 빌드 의존이 부담.
- 오탐 잡음: 기록류는 stale 의 경로 검사에서 빠지지만 문서 본문이 형제 저장소 경로를 많이 인용하는 claude-doctor 특성상(audit 인용) `--refs-all` 을 켜면 luau-kb 처럼 수십 건 잡음(TODO.md "pack 문서의 저장소 밖 산문 경로 stale 잡음").
- coderag 가 없을 때: 기록은 평문 md 이고 frontmatter 는 평범한 YAML 헤더, README 색인은 마커 블록 속 평범한 표라 **coderag 없이도 읽힌다**. 지켜야 할 규칙: (1) 상태·날짜를 frontmatter 에만 두지 말고 본문 첫 줄에도 보이게, (2) 마커 블록 밖에 사람이 쓴 설명을 두는 규약 유지, (3) recall·검사 도구는 coderag 없으면 grep/자체 검사기로 폴백(현재 q:recall 이 이미 이 분기를 가짐), (4) `.coderag/` 는 커밋하지 않음.

## 8. 열린 질문 (사용자 결정 필요)
1. 상태 어휘를 coderag 에 맞출까(archived+superseded_by 로 단순화), coderag 가 우리 어휘를 배울까(KNOWN_STATUS 확장, coderag 쪽 수정은 사용자 승인 필요)? 또는 상태 줄은 평문 규약으로 두고 coderag 는 모르는 값을 무시하게 할까?
2. 세션 기록 snapshot 2줄 헤더를 YAML frontmatter 로 할지(coderag kind=session 인식, 검색 가능) 본문 평문으로 할지.
3. 폴더 이름: coderag 의 kind 는 `session`, 우리 폴더는 `sessions`. 맞출지 매핑할지(kind 는 폴더 추론이 없으니 문서에 명시해야 함).
4. 검사기의 소유: 폴더 규칙(끝난 문서 위치, 색인 누락, 예산)을 claude-doctor 의 자체 스크립트로 둘지, coderag `lint`/`stale` 규칙으로 넣을지(전 저장소 공통이면 coderag, 우리 규약 전용이면 claude-doctor).
5. 색인 신선도: recall 시작 때마다 `coderag gen`(수십 ms~0.3초)을 돌려도 되는지(캐시는 /tmp 로), 아니면 M9 완성을 기다릴지.
6. claude-doctor 실험의 범위: 기록이 `.claude/` 밖(audit/, decisions/, handoff/)에 있는 현재 구조에서 먼저 coderag.toml 만 올려 측정할지, 구조 이동과 동시에 할지(이동과 색인 효과가 섞이면 측정이 흐려지므로 이동 전·후 따로 측정을 권고).
7. 읽을 때 낡음 경고를 coderag 출력에 넣을지(작은 변경이나 coderag 쪽 수정), 읽는 에이전트의 지시문으로만 할지.
