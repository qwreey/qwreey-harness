# 38 기록 규약 토론, 2라운드: P (평문 markdown 우선)

1라운드에서 Q 와 나는 생각보다 많이 겹쳤다. 문법 `status: <state> [in|by <target>] [; <note>]`, 어휘 5개, `paused` 없음, 스냅샷에는 status 없음, `sessions/` 복수형, `archive/<원래 폴더>/` 미러, 같은 커밋 `git mv`, `raw/` gitignore, doc-locator 에 기대지 않음, recall 마다 gen 이 그렇다. 아래는 다른 점만 다룬다. 사용자의 구속 발언(기록은 coderag 와 결합, 검색·stale 은 기존 틀, haiku 로 찾기, 정리는 자동, `.claude/` 재편은 coderag 구조화 실험)을 기준으로 내 1라운드 입장 일부를 내려놓는다.

## 1. Q 의 사실 주장 검증 (/tmp/p38r2 사본, coderag target/debug, CODERAG_CACHE=/tmp)

| Q 주장 | 판정 | 근거 |
|---|---|---|
| core `docs/mod.rs:164` 가 `superseded by X` 를 active 로 색인 | **확인** | `.filter(matches!(x, "active"\|"superseded"\|"archived")).unwrap_or("active")`. 재현: `status: superseded by base/b.md` 문서가 기본 `search` 에 나옴. mdfm `listed()`(lib.rs:352)도 완전 일치라 숨기지 않음. 내 1라운드 지적(lib.rs:352·:764)과 같은 버그를 core 쪽에서도 봤음 |
| lint 는 첫 낱말만 봐서 통과 | **확인** | lib.rs:933 `split_whitespace().next()` |
| `static-gen --dir .claude/base` 가 `.claude/.claude/base/README.md` 를 만듦 | **확인** | 재현 출력 `갱신 .claude/.claude/base/README.md`. `--dir` 은 문서 루트 기준(main.rs:190 주석). 버그라기보다 함정이고, 규약 문구에 `--dir base` 로 적거나 C6 으로 둘 다 받게 해야 함 |
| `--dry-run` 은 바뀔 예정이어도 rc=0 | **확인** | 재현 `바뀔 예정 … rc=0`. main.rs:568-580 에 종료 코드 분기 없음 |
| gitignore 된 sessions 도 색인, frontmatter 없으면 `[unknown]` | **확인** | 재현에서 `.gitignore` 의 `.claude/sessions/s1.md` 가 검색됨, kind 는 전부 `[unknown]`(lib.rs:763 기본값). 덧붙임: 첫 줄 `status: landed in …` 인 무-frontmatter 문서도 active 로 나옴(C3 근거) |
| coderag 플러그인이 enabledPlugins 에 없음 | **확인** | `~/.claude/settings.json` enabledPlugins 는 q, qwreey-advisor, qwreey-conventions, qwreey-proc-guard, web-security, cc-plugin-you-should-know 뿐. PATH 에도 coderag 없음 |
| session frontmatter 의 `last_verified` 가 90일 뒤 stale 잡음 | **확인** | q `store.py:246-248` 이 `status: active`, `last_verified: <오늘>` 을 씀. coderag stale.rs:69 는 frontmatter 문서에 `last_verified + 90일` 을 적용. 내 1라운드는 status 만 빼자고 했는데 이 잡음은 못 봤음 |
| drafts 51 중 frontmatter 16, audit 75 중 4, decisions·handoff 0 | **확인**(audit 은 지금 77: 이 토론 파일 2개) | head -1 집계. 첫 줄 `status:` 는 drafts 3개뿐 |
| recall 이 harness.env 에서 `$CODERAG_BIN` 을 얻는다 | **반박(현재 사실로서)** | harness.env 에 coderag 키가 없음. 제안으로는 유효하고, 키를 `home/` 에 추가해야 함. coderag `bin/coderag` 래퍼가 이미 `$CODERAG_BIN → target/{release,debug} → PATH` 순으로 찾음 |
| drafts 절 메타에 자유문 `status:` 가 많다 | **확인** | drafts 의 2행 이후 `^status:` 87줄. 그래서 내 1라운드의 "처음 15줄 안 첫 `^status:`" 규칙은 위험하다. **첫 줄로 좁힌다**(아래 2.1) |

## 2. 쟁점별 입장

**2.1 status 위치. 타협.** 새로 만드는 살아 있는 문서는 frontmatter 를 **필수**로 한다(title, description, status; keywords 는 권장). 사용자가 haiku 검색과 coderag 결합을 원했고, coderag 는 본문을 색인하지 않으니 description 이 검색 품질을 좌우한다. 이 점은 Q 가 맞다. 다만 frontmatter 가 없는 옛 문서와 이미 첫 줄 `status:` 를 쓴 drafts 는 **첫 줄 한 줄** 형태를 유효한 것으로 인정하고 백필하지 않는다(Q 의 C3 와 같은 결론). 두 곳에 쓰는 것은 금지한다. lint 소음은 post-edit/커밋 검사가 새로 만들거나 고친 파일만 보게 해서 막는다.

**2.2 스냅샷의 status 와 `date:`. 양보.** session·audit 에서 `status` 와 `last_verified` 를 둘 다 뺀다. 기록 시점은 `date: YYYY-MM-DD` 로 남긴다. 이것은 이력이 아니라 스냅샷의 정체다. 한 곳 원칙은 그대로 지킨다. frontmatter 가 있으면 `date:` 에, 없으면 머리말 줄(`> Snapshot <date>. …`)에 둔다. q writer 의 2줄 blockquote 는 생성물이라 날짜가 겹쳐도 어긋나지 않는다. q `store.py` 의 변경은 `status: active` 와 `last_verified` 를 `date:` 로 바꾸는 것이다.

**2.3 필수 폴더. 유지하되 타협.** 필수는 `.claude/README.md` 하나다. 빈 `archive/README.md` 는 처음 옮길 때까지 정보가 없고 작은 저장소에서는 잡음이다. 타협안은 `q:start` 가 `base/` 를 권하는 것이다(동의하면 만든다. 거의 모든 저장소가 결정을 남긴다). `archive/` 는 첫 이동 커밋이 만든다. 이동 규칙이 커밋 단위라 폴더가 미리 있을 필요가 없다.

**2.4 README 색인. 양보.** coderag 를 쓸 수 있는 저장소에서는 static-gen 마커 블록을 **기본**으로 하고 생성된 표를 커밋한다. 사용자의 "자동으로" 요구에는 이쪽이 맞다. 조건이 둘 있다. (a) C6(`--check` rc=1, 경로 기준 통일)이 먼저 들어가야 한다. 지금 `--dry-run` 은 검사기로 못 쓰고 `--dir` 함정이 있다. (b) coderag 가 없는 기계에서는 손으로 쓴 `- [이름](경로) — 설명` 목록도 유효하다. 손 줄에는 상태와 날짜를 쓰지 않는다. `sessions/` 의 README 는 계속 두지 않는다(Q 도 반대하지 않았다).

**2.5 검사기 위치. 타협: 규칙마다 구현은 하나.** Q 안은 coderag `stale`/`--check` 를 쓰고 없으면 q 의 정규식으로 대신한다. 이러면 같은 규칙이 두 구현에 들어간다. 내 안은 q 가 전부 맡아서 coderag 의 refs 그래프를 다시 만든다. 그래서 겹치지 않게 나눈다.
- **coderag 가 맡는 것**(색인이 필요한 것): 깨진 참조와 target 존재, README 색인 낡음(`--check`), 숨김(listed).
- **q `records_check.py` 가 맡는 것**(stdlib, 색인 불필요): status 문법과 위치(한 곳, 첫 줄), active 가 아닌 문서가 archive 밖에 있음, 상시 로드 크기, 파일·폴더 크기, `raw/` gitignore 여부.
- coderag 가 없으면 coderag 몫 검사는 건너뛰고 "coderag 없음: 참조·색인 검사 생략" 한 줄을 낸다. 대신 구현하지 않는다.
- status 파싱만은 양쪽이 다 해야 한다(q 는 위치 검사, coderag 는 숨김). 어긋나지 않도록 claude-doctor 에 **골든 예시 파일** 하나(`status:` 줄과 기대 파싱 결과 20줄)를 두고 두 테스트가 같은 파일을 읽는다.

**2.6 coderag 변경 목록. 거의 수용.** 실험의 선행 조건은 C1(문법 파서, 조용한 오분류 수정), C2(폴더로 kind 추론, 복수형 별칭), C3(첫 줄 status 인식), C6(`--check`, `--dir` 기준)이다. 이것이 내 1라운드의 1·2·3 에 C3 을 더한 것이다. C4(gitignore 존중), C7(나이 표시, 기록류 날짜 stale 끔), C8(skills·agents 등 기본 제외)은 실험 뒤에 해도 된다. 다만 C7 의 "날짜 stale 끔"은 C1 과 같은 이유(스냅샷 잡음)로 같이 넣으면 좋다. **C5 는 절반만 받는다.** "끝났는데 archive 밖"은 2.5 에 따라 q 몫이다. "기록류 archive 후보(나이 + 인용 0)"는 반대한다(2.8).

**2.7 recall 연동. 타협.** 둘 다 doc-locator 에 기대지 않는다(플러그인이 꺼져 있음이 확인됐다). `home/` 의 harness.env 원본에 `HARNESS_CODERAG=${HARNESS_WORKSPACE}/coderag/bin/coderag` 를 추가하자(사용자가 apply). 래퍼가 release/debug 중 더 새 것을 고르니 바이너리 경로를 직접 박지 않는다. 키가 없거나 래퍼가 127 이면 grep 으로 간다. 세션 본문은 coderag 결과와 상관없이 grep 을 함께 쓴다. 이 점은 Q 도 "나중 항목까지 두 번째 근거"로 동의했다. recall SKILL 의 지금 문구("coderag search tool 이 있으면 global layer 먼저")는 이 순서로 고쳐야 한다.

**2.8 archive 이동 규칙. 유지(스냅샷은 옮기지 않음).** 살아 있는 문서는 status 를 바꾼 그 커밋에서 옮긴다. 여기까지는 합의다. Q 의 C5 "기록류 archive 후보"에는 반대한다. 스냅샷을 옮기면 다른 스냅샷 안의 옛 경로가 깨지는데, 스냅샷은 고치지 않는다는 규칙에 둘 다 동의했다. 그러면 고칠 수 없는 링크가 생긴다. 오래된 스냅샷이 검색에서 밀리게 하는 일은 C7 이 `date` 로 감쇠·표시하면 된다. 폴더를 옮길 필요가 없다. Q 의 "활성 문서가 링크한 곳에만 한 줄 포인터"와 내 "살아 있는 문서의 링크를 고친다"는 같은 동작이다. 링크를 고치는 쪽으로 통일한다.

**2.9 raw 덤프.** 합의했다. 동료에게 근거 원본이 안 간다는 비용은 남는다. 기본값은 gitignore 로 두고 질문에서는 뺐다(3절 끝).

**2.10 실험 설계. Q 안을 기본으로 하고 보강한다.**
- 시점: **이 토론(audit/38)이 끝나고 커밋된 뒤**에 한다. 시작 전에 claude-doctor 의 살아 있는 세션과 worktree lock 을 확인한다(q:workspace). 지금도 다른 세션이 audit/ 에 쓰고 있다.
- 질문 세트: 10개는 hit@5 차이를 가리기에 적다. **20개**로 하고, 절반은 transcript 의 실제 recall·"전에 뭐라고 정했지" 질문에서 뽑는다. 정답 위치는 **옮기기 전에** 정하고 커밋한다. 이동 뒤에는 대응표로 바꾼다.
- 4개 조건을 잰다. grep(이동 전), grep(이동 후), coderag(이동 전, /tmp coderag.toml), coderag(이동 후). Q 의 "이동 효과와 색인 효과 분리"를 2×2 로 완성하는 것이다. 마지막 측정은 Q 안대로 PATH 에서 coderag 를 뺀 grep 이다.
- 커밋 A·B·C·D 순서와 drafts 절 메타 주의는 Q 안 그대로다. B 뒤에 q 테스트와 `e2e.sh`, `home-sync.sh status` 를 돌린다(audit/36 §3 의 깨지는 곳).
- **롤백 기준**:
  - A·B(이동) 되돌림: grep(이동 후) hit@5 가 grep(이동 전)보다 2문항 넘게 낮거나, B 뒤에도 살아 있는 문서의 깨진 링크나 테스트 실패가 남아 한 커밋으로 못 고칠 때.
  - C·D(결합) 되돌림: coderag(이동 후)의 hit@5 가 grep(이동 후)보다 낮거나, 같은 hit 에서 읽은 토큰이 더 많을 때. stale 오탐이 30%를 넘을 때. 일부러 낡게 만든 README 를 `--check` 가 하나라도 놓칠 때.
  - 기준을 넘지 않으면 유지하고 PLAN 3.9 에 수치를 남긴다.

## 3. 수렴안

**합의 항목(양쪽 서명 가능)**
1. 기록은 `.claude/` 아래 평문 markdown 이고 coderag 어휘(frontmatter 키, kind, status)로 정의한다. coderag 가 없으면 읽기와 쓰기는 그대로 되고, 검색과 일부 검사만 약해진다.
2. 문법은 `status: <state> [in|by <target>] [; <note>]` 이고 어휘는 `active | landed | superseded | rejected | archived` 다. `paused` 는 `active; on hold until …` 으로 쓴다. `superseded_by:` 는 하위 호환으로 읽는다. 상태 줄에 날짜를 쓰지 않는다.
3. status 는 한 곳에만 둔다. 새 살아 있는 문서는 frontmatter(title, description, status) 필수다. frontmatter 없는 옛 문서는 첫 줄 형태를 인정하고 백필하지 않는다.
4. 스냅샷(audit, handoff, sessions)에는 status 와 `last_verified` 가 없다. `date:` 하나와 머리말 경고 줄을 둔다. 고치지 않는다. q `store.py` 를 그렇게 바꾼다.
5. 폴더는 plan, base, research, audit/NN-slug, handoff, sessions, archive/<origin>, packs/<pack> 이고 처음 쓸 때 만든다. `.claude/README.md` 는 필수다.
6. 살아 있는 문서의 status 를 active 에서 바꾸는 에이전트는 같은 커밋에서 `git mv` 로 archive 로 옮기고 살아 있는 문서의 링크를 고친다. 삭제는 하지 않는다.
7. 원시 덤프는 `audit/<n>/raw/` 에 두고 gitignore 한다. 요약 md 에는 수치와 재생성 명령을 둔다.
8. 색인은 coderag 가 있으면 static-gen 블록을 커밋하고, 없으면 손 목록을 쓴다. 어느 쪽이든 손 줄에는 상태·날짜·배너를 쓰지 않는다. sessions/ 에는 README 를 두지 않는다.
9. coderag 선행 변경은 C1·C2·C3·C6 이다. C7·C8·C4 는 그 뒤에 한다.
10. recall 은 doc-locator 에 기대지 않는다. 래퍼 경로로 `gen` 뒤 `search --abs --layer project` 를 쓰고, 세션 본문은 grep 을 함께 쓴다. 캐시는 저장소 밖에 둔다.
11. 크기 예산(상시 로드, 파일 200KB, 폴더 합계)은 q 가 검사한다.
12. 실험은 브랜치에서 A(mv)→B(경로)→C(status)→D(static-gen) 순서로 하고, 커밋 단위로 되돌린다. 이동과 결합은 따로 판정한다.

**남은 이견**
- 검사 분담. P: 규칙마다 구현은 하나로 하고, coderag 가 없으면 참조·색인 검사는 생략한다. Q: coderag 검사를 쓰고, 없으면 q 정규식으로 대신한다. (P 의 근거: 대체 구현은 두 정본이 된다. Q 의 근거: 동료 기계에서도 최소 검사가 돌아야 한다.)
- 스냅샷 archive 후보(C5 후반). P: 옮기면 고칠 수 없는 링크가 깨지니 C7 의 날짜 감쇠로 충분하다. Q: 오래되고 인용 없는 기록은 archive 로 빼야 검색과 폴더가 가벼워진다.
- 필수 폴더. P: README 하나만 필수다. 빈 폴더는 잡음이다. Q: base/·archive/ 를 항상 두어야 규약이 눈에 보인다.
- 실험 규모. P: 질문 20개, 2×2 조건, 이동 판정 기준을 따로 둔다. Q: 질문 10개, 결합만 판정한다(이동은 무조건 유지).

**사용자에게 물을 것 (4)**
1. coderag 저장소 변경: (a) C1·C2·C3·C6 만 지금, (b) C1-C8 전부, (c) 보류(실험은 /tmp 패치 바이너리로만 잼). 어느 세션이 맡을지도 정해 주세요.
2. status 를 바꿀 때 에이전트가 묻지 않고 같은 커밋에서 archive 로 `git mv` 해도 되나: (a) 예, 모든 작업 저장소, (b) claude-doctor 만, (c) 매번 묻기.
3. coderag 를 사용자와 동료 설치에 어떻게 붙일까: (a) 플러그인을 켠다(doc-locator, post-edit lint. 동료에게는 미리 빌드한 바이너리 필요), (b) 바이너리 래퍼 경로만 쓴다(harness.env `HARNESS_CODERAG`), (c) 당분간 사용자 기계만.
4. 기존 형제 저장소(quad 의 `session/`, `archive/surveys/`, 제목 태그)를 어떻게 할까: (a) 새 규약으로 소급 정리, (b) 새 저장소와 claude-doctor 에만 적용하고 옛 형태는 검사기가 인정만 한다.

(원시 덤프를 동료와 공유하는 문제는 합의 7 의 기본값 "gitignore, 요약과 재생성 명령만"으로 두었다. 사용자가 원하면 "200KB 이하는 커밋"으로 바꿀 수 있다.)
