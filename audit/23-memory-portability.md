# 23. auto memory 이식성

2026-11-11 사용자 문제 제기: 저장소에 실려야 할 지식이 메모리에만 들어가 다른 사람이 저장소를 열면 빠지고, 폴더를 옮기면 메모리가 끊기는데 사용자들이 모른다. 회사 동료(비개발자 포함)에게도 배포할 하네스라 이 점을 장치로 다뤄야 한다.
상태: 설계와 구현 완료(미커밋). 실측은 Claude Code 2.1.316, sonnet, `claude -p`, `/tmp` 임시 저장소.

## 1. 사실 확인

### 1-1. 문서(`/tmp/ccdocs/memory.md` 516–552행)
- 위치 `~/.claude/projects/<project>/memory/`, `<project>` 는 git 저장소에서 파생(worktree·하위 폴더 공유). git 밖이면 프로젝트 루트.
- `autoMemoryDirectory`: 모든 settings scope(user, project, local, policy, `--settings`)에서 읽힌다. **값은 절대 경로이거나 `~/` 로 시작해야 한다.**
- project `.claude/settings.json`·`settings.local.json` 에 둔 값은 훅과 같은 workspace trust 규칙을 따른다. `permissions.blockReadsOutsideWorkingDirectories` 가 켜져 있으면 저장소가 제공한 설정 파일이 고른 디렉터리에서는 메모리를 읽지도 쓰지도 않는다.
- `CLAUDE_CODE_PROJECT_DIR_NAME`(2.1.234+), `autoMemoryEnabled`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. 백그라운드 세션이나 다른 Claude 세션이 띄운 `claude` 에서는 `/memory` 토글로 켤 수 없다(실측 때 `CLAUDE_CODE_CHILD_SESSION` 을 지우고 돌렸다).
- 로드 한도: MEMORY.md 앞 **200줄 또는 25KB** 중 먼저 닿는 쪽. 넘어도 쓰기는 성공하고, Claude 에게 "인덱스를 다시 쓰라" 는 오류가 간다(552행). 근접하면 줄이라는 리마인더가 온다. → MEM-SIZE 의 근거.

### 1-2. 실측 (임시 저장소 6개, 합계 약 $0.55)
| 실험 | 설정 | 결과 |
|---|---|---|
| A | 없음, 경로 `/tmp/memexpA.dot_1` | `~/.claude/projects/-tmp-memexpA-dot-1/memory/` 에 **Write** 도구로 저장 |
| B | project settings `autoMemoryDirectory: ".claude/memory"` (**상대 경로**) | **무시**. 기본 위치(`-tmp-memexpB-dot-1`)에 저장. 오류·경고 없음. 저장소에는 `.claude/settings.json` 만 남음 |
| C | project settings 절대 경로 `/tmp/memexpC-store` | 그 경로에 저장(MEMORY.md 포함). 기본 키 폴더에는 세션 기록만 |
| D | `${CLAUDE_PROJECT_DIR}/.claude/memory` | **무시**(변수 확장 없음). 기본 위치에 저장 |
| E | 기본 + PostToolUse(Write\|Edit) 로깅 훅 | 훅이 `tool=Write`, `file_path=~/.claude/projects/<키>/memory/<파일>.md` 를 받았다. MEMORY.md 쓰기도 같다. D 도 같다 |
| F | 규칙 `paths: ["**/memory/*.md"]`, 읽는 파일은 프로젝트 밖(`/tmp/outside-F/memory/a.md`)과 안(`./memory/b.md`) | 밖: 규칙 **로드 안 됨**, 안: 로드됨 |
- 신뢰 확인 창: `-p` 는 신뢰 대화상자를 건너뛰므로 **미확인**(interactive 에서 project scope 절대 경로가 신뢰 전에 무시되는지는 문서의 규칙을 믿을 뿐 실측하지 않았다). 보안 제한은 문서의 두 가지(trust 규칙, blockReadsOutsideWorkingDirectories)뿐이다.
- 결론 1: **저장소에 커밋하는 설정으로는 "저장소 안 메모리" 를 만들 수 없다.** 상대 경로와 변수 확장이 모두 안 되고, 절대 경로는 사람마다 다르다.
- 결론 2: 메모리 쓰기는 일반 Write 라 **PostToolUse(Write|Edit) 훅이 잡는다.** SessionStart·Stop 검사 같은 대안 설계는 필요 없다.
- 결론 3: 메모리 경로는 프로젝트 밖이라 **rules 의 `paths` 로는 걸리지 않는다**(실험 F). 그래서 write 시점의 훅이 실질 장치이고, rules 파일은 작업 트리 안에 메모리 디렉터리를 둔 경우에만 로드된다.

### 1-3. 경로 → 키 규칙 (실측)
절대 경로에서 **영숫자가 아닌 모든 문자를 `-` 로** 바꾼다. `/tmp/memexpA.dot_1` → `-tmp-memexpA-dot-1`, `/code/.claude` → `-code--claude`. 길이 상한 처리는 미확인(현재 최대 43자).
- 역변환은 모호하다(`/`, `.`, `_`, `-`, 공백이 모두 `-`). 그래서 `lib/memory_signals.py` 의 `resolve_key` 는 파일 시스템을 걸으며 디렉터리 이름을 같은 규칙으로 바꿔 키와 맞춰 본다.
- 현재 `~/.claude/projects/` 키 **334개**(공문 시점 328 + 내 실측 6). 경로가 없는 고아 키 **100개**. 모두 `/tmp` 아래 시험용(`-tmp-sl-sum-*`, `bre2e`, `sktest` 등)이고 **메모리 .md 가 든 고아 키는 0개**, 짝 후보도 0개다. 빈 `memory/` 폴더는 자동 생성되므로(334개 전부 존재) `.md` 가 있는지로 센다. 메모리가 있는 키는 12개(7개 실저장소 + `-tmp-cmp` + 내 실측 4개)이고 전부 경로가 살아 있다.
- 고아 키에도 세션 기록(`*.jsonl`)이 남을 수 있다. 폴더를 옮기면 `--resume` 목록에서도 끊긴다. 이 검사는 메모리만 다룬다.
- 같은 git 저장소의 다른 worktree 는 문서상 한 키를 공유한다(worktree 키는 이번에 실측하지 않음: 미확인).

## 2. 설계

### 2-1. 분류 기준
| 내용 | 둘 곳 | 이유 |
|---|---|---|
| 사용자 성향·피드백·작업 방식 선호, 이 기기·sandbox·개발 서버·여기 깔린 도구 | **메모리** | 사람과 기기에 붙는 것. 저장소에 실으면 오히려 남에게 새어 나간다 |
| 저장소 규약, 결정, 함정, 빌드·테스트 방법, 파일 소유 | **저장소**(CLAUDE.md, `.claude/rules`, docs) 또는 coderag **project** 계층 | 저장소를 여는 누구에게나 필요하다 |
| 툴킷 일반 지식(Luau, Roblox, Studio MCP) | **pack**(luau-kb 등) | 여러 저장소가 공유한다 |
| 회사·팀이 같이 알아야 하는 것 | coderag **team** 계층(설계 중, `coderag/tech-design.md` §35) | 팀 서버에서 조회. 저장소 밖에서도 읽힌다 |
- 섞인 메모는 쪼갠다: 개인·환경 부분은 메모리, 저장소 부분은 저장소(포인터만 메모리에).
- "저장소에 둘 것" 판정이 어려울 때의 한 줄: *이 저장소를 처음 clone 한 동료가 이것을 몰라서 틀릴 수 있는가?* 그렇다면 메모리가 아니다.

### 2-2. `autoMemoryDirectory` 를 저장소 안으로 지정하는 방안
| | 내용 |
|---|---|
| 장점 | 메모리가 git 으로 공유된다. 폴더를 옮겨도 따라온다(저장소와 한 몸) |
| 단점 1 | **설정 자체가 이식되지 않는다.** 상대 경로·변수 확장 불가(실측)라 커밋할 `settings.json` 에 쓸 값이 없다. 각자 `settings.local.json` 에 자기 clone 의 절대 경로를 적어야 한다 |
| 단점 2 | 개인 성향·환경 메모가 저장소에 섞여 동료와 공개 저장소로 샌다. 커밋 위생(`.gitignore`, 어느 메모를 올릴지)을 사람이 매번 지켜야 한다 |
| 단점 3 | 저장소가 정한 위치에 쓰게 하는 동작은 신뢰 경계 문제다. 문서가 trust 규칙과 `blockReadsOutsideWorkingDirectories` 예외를 둔 이유이고, 켜면 메모리가 아예 안 읽힌다 |
| 단점 4 | 메모리는 "Claude 가 알아서 쓰는 것" 이라 저장소 문서의 품질 기준(리뷰, 구조)을 받지 않는다. 대량의 낮은 품질 파일이 저장소에 들어온다 |
| **추천** | **하지 않는다.** 대신 메모리와 저장소를 분류로 나누고(위 표), 저장소 지식은 CLAUDE.md·rules·docs·coderag 로 보낸다. 이것이 사람이 검토할 수 있는 형태다 |
- 예외로 쓸 만한 곳: 개인 용도의 사용자 레벨 `~/` 경로(예: 클라우드 동기화 폴더). 기기 간 이식(같은 사람의 두 컴퓨터)에만 맞고 동료 공유에는 맞지 않는다.

### 2-3. 폴더 이동 대응
1. **감지**: `/q:doctor` 의 `MEM-ORPHAN`(키 규칙으로 키를 경로로 되돌려 존재 확인). 메모리 `.md` 가 든 고아만 경고, 현황 수는 보고에 남긴다.
2. **짝짓기**(후보 제시만, 확정은 사용자): (a) 같은 디렉터리 이름(옛 세션 기록의 `cwd` 에서 얻음), (b) 메모리 본문에 적힌 경로가 가리키는 git 저장소, (c) 후보의 `origin` URL 이 메모리 본문에 나옴. 옛 경로가 사라졌으니 "같은 git remote" 는 옛 쪽에서 구할 수 없어 (c) 로 대신한다.
3. **옮기기**: `scripts/memory_move.py --from-key=<옛 키> --to <새 경로>` 기본 dry-run, 동의 후 `--apply`. 원본은 남긴다. 같은 이름·다른 내용은 덮어쓰지 않고 `.from-<옛 키 끝 8자>.md` 로 복사한다. MEMORY.md 는 새 쪽에 없는 줄만 붙인다.
4. 이사 전 예방: 폴더를 옮기기 전에 먼저 복사하는 것이 가장 안전하다. 온보딩 문구에 넣었다.

### 2-4. 비개발자용 설명 문구 (온보딩 `concepts/memory.md` 에 들어감)
> Claude 의 메모리는 **이 컴퓨터, 이 폴더** 에만 붙어 있는 메모장입니다. 프로젝트(저장소)에 들어 있지 않아서, 동료가 같은 프로젝트를 열어도 내 메모는 보이지 않습니다. 폴더를 옮기거나 이름을 바꾸면 Claude 는 새 프로젝트로 알고 메모를 잃어버립니다. 그래서 "이 프로젝트는 이렇게 빌드한다" 같은 **프로젝트 이야기는 메모가 아니라 프로젝트 안**(CLAUDE.md 나 문서)에 적어야 하고, 메모에는 내 취향과 내 컴퓨터 사정만 둡니다. Claude 가 프로젝트 이야기를 메모에 적으려 하면 하네스가 알려 주고, 옮길지는 항상 당신에게 묻습니다.

## 3. 구현
| 파일 | 역할 |
|---|---|
| `home/.claude/lib/memory_signals.py` | 키 규칙(`key_of`, `resolve_key`), memory 경로 판정(`is_memory_path`: 기본 `<config>/projects/*/memory` 와 절대 `autoMemoryDirectory`), 저장소 지식 신호 분류(`classify`). 훅과 doctor 가 공유 |
| `home/.claude/hooks/memory-placement.py` | PostToolUse `Write\|Edit\|MultiEdit`. level=warn, 막지 않음. 메모리 디렉터리의 MEMORY.md 가 아닌 `.md` 만 본다. 파일마다 (session, 호출한 쪽, compact 회차)당 한 번 |
| `home/.claude/rules/memory.md` | 분류 기준 요약(영어 19줄). `paths` 는 작업 트리 안 메모리에만 먹는다(실측 F) |
| `home/settings-migrations/0004-memory-placement.json` | 훅 등록(`settings-migrate.py` 드라이런으로 확인: 변경 1) |
| `plugins/q/skills/doctor/scripts/memory_checks.py` | MEM-ORPHAN, MEM-REPO, MEM-SIZE. scan.py 에는 항목 10 등록(`check_memory`, 21줄)만 |
| `plugins/q/skills/doctor/scripts/memory_move.py` | 옮기기(dry-run 기본) |
| `plugins/q/skills/doctor/references/memory-portability.md` | 판정 기준, 옮기기 절차 |
| `plugins/q/skills/start/references/concepts/memory.md` | 온보딩 문구 |
| 테스트 | `home/.claude/hooks/tests/test-memory-placement.py`(18), `plugins/q/skills/doctor/tests/test-memory-checks.py`(16). 기존 훅 테스트 4종 통과 확인 |

### 3-1. 신호와 점수(`classify`)
- 강한 신호(종류당 +2): 경로(`src/a/b.ext` 꼴, `~`·`/tmp`·`/code/.claude` 같은 환경 절대 경로 제외), 빌드·테스트 명령(`make`, `npm`, `luau`, `pytest`, `rojo` ... 백틱), "이 저장소에서·in this repo" 류.
- 약한 신호(+1): 백틱 심볼(`Mod.func`, `fn()`), 규약·함정 낱말(convention, always use, 규약, 함정, 금지).
- 보정: type project +1, reference -1, 환경 표현(sandbox, 이 기기, dev server, mise, `~/.claude`) -2. type=user 는 항상 조용. 판정: 점수 3 이상이고 강한 신호나 심볼이 있을 때 "repo". 경고 수준은 5 이상.
- `type` 은 최상위나 `metadata:` 아래 중첩 둘 다 읽는다(실제 파일은 중첩형이 많다).
- 훅 메시지는 `HOOK-MESSAGES.md` 규약대로 영어, `<harness-hook name="memory-placement" level="warn">`. 관찰(무엇이 repo 지식으로 보이는지) + 권고(옮길 곳 제안, 저장소 파일은 사용자에게 먼저 묻기, 개인·환경 부분은 그대로, 사실 개인 메모면 한 줄로 밝히고 진행). 현재 배정 표에 추가해야 한다(아래 §7).
- 실제 메모리 61개(MEMORY.md 제외)에 돌려 본 결과: repo 판정 10개. 사람의 분류와 맞춰 보면 `저장소로` 24개 중 7개(29%)를 잡았고, 나머지 3개는 낡음 2·유지 1(`.claude/conventions.md` 같은 포인터 언급 때문)이다. 재현율이 낮은 것은 의도다(경로·명령 같은 근거가 있는 것만 알린다). 이 훅은 쓰는 순간의 방어선이고, 사후 정리는 사람이 읽는 감사(§4)가 맡는다.

### 3-2. 한계
- 훅은 휴리스틱이라 서술형 규약("항상 X 하라", 파일 경로 없음)을 놓친다. 오탐은 한 줄로 "개인 메모다" 라고 답하면 넘어간다.
- 메모리를 Bash(`cat > memory/..`)로 쓰면 훅이 못 잡는다(bash-bypass-reminder 가 그 경우를 따로 안내한다). 모델이 메모리를 정식으로 쓸 때는 Write 이다(실측).
- 세션 중 다른 프로그램이나 사용자가 직접 편집한 메모리는 못 잡는다. 사후 검사는 `/q:doctor` 의 MEM-REPO.
- `--resume` 세션 기록은 메모리와 별개로 키에 묶인다(이 설계 밖).

## 4. 기존 메모리 감사 (읽기 전용, 원문을 읽고 분류)
다른 저장소의 메모리 파일은 읽기만 했다. 인계는 `handoff/memory-<repo>.md`.

| 저장소 | 항목 | 유지 | 저장소로 | pack으로 | 낡음 | 인계 |
|---|---:|---:|---:|---:|---:|---|
| quad | 21 | 10 | 8 | 2 | 1 | `handoff/memory-quad.md` |
| stl-luau | 11 | 4 | 6 | 1 | 0 | `handoff/memory-stl-luau.md` |
| devplorer | 10 | 6 | 2 | 1 | 1 | `handoff/memory-devplorer.md` |
| tbox | 3 | 1 | 2 | 0 | 0 | `handoff/memory-tbox.md` |
| table-sim | 3 | 1 | 1 | 0 | 1 | `handoff/memory-table-sim.md` |
| VideoSync | 1 | 0 | 1 | 0 | 0 | `handoff/memory-VideoSync.md` |
| claude-doctor(자신) | 12 | 6 | 4 | 0 | 2 | `handoff/memory-claude-doctor.md` |
| **합계** | **61** | **28** | **24** | **4** | **5** | |
- `저장소로` 24개 중 상당수는 프로젝트 맥락·설계 결정(stl-luau 의 트레이트 방향 전환, VideoSync 의 아키텍처 결정, quad 의 docs-site 규칙)이다. 이 지식이 메모리에만 있어 다른 clone 에서는 빠지는 상태다.
- 눈에 띄는 패턴: (1) 저장소 문서에 이미 있는 내용을 메모리가 복제(quad safety, claude-doctor 의 home 정본·second-opinion). (2) 사용자 성향이 저장소마다 중복(quad·devplorer 의 결정 제시 방식, 한국어, 모델 선택). 이것은 **전역 CLAUDE.md 후보**다. (3) quad 의 `feedback-quad-collaboration-style` 는 12.6KB 혼합 파일이라 쪼개기가 필요하다.
- claude-doctor 자신의 메모리도 같은 기준으로 분류했고 고치지 않았다.

## 5. CLAUDE.md 초안 (정본 `home/.claude/CLAUDE.md` 에는 넣지 않음, 50줄 상한은 메인이 판단)
rules 의 `paths` 가 메모리 경로에 안 먹으므로(실측 F), 저장 결정 시점에 항상 보이게 하려면 CLAUDE.md 가 맞다. 2줄 초안:
```
## 메모리 위치
auto memory 는 이 컴퓨터·이 폴더에만 있다(저장소·동료·옮긴 폴더에 안 따라간다). 저장소 규약·결정·함정·빌드 방법은 메모리가 아니라 저장소(CLAUDE.md, .claude/rules, docs)나 coderag 에, 개인 성향과 환경은 메모리에 둔다. 섞이면 쪼갠다.
```
`rules/memory.md` 는 paths 조건이 있어 작업 트리 안 메모리에만 로드되고, 훅 메시지가 쓰는 순간을 맡는다. 겹침을 피하려고 rules 파일을 paths 없이 상시 로드로 바꾸지는 않았다(제안: 훅 + 이 CLAUDE.md 2줄 조합).

## 6. 이후
- coderag project 계층이 생기면 훅 문구의 "coderag project layer" 를 실제 명령으로 바꾼다.
- `MEM-REPO` 점수 기준은 이번 61개의 표본으로 정했다. 회사 동료의 메모리(비개발자)는 다른 분포일 수 있어 첫 배포 뒤 오탐·누락을 보고 조정한다.

## 7. 사용자 결정이 필요한 것
1. **CLAUDE.md 2줄**을 정본에 넣을지(§5). 넣으면 `rules/memory.md` 의 paths 없는 상시 로드 여부와 같이 정한다.
2. **새 사용자 명령 이름**: 메모리 복사·점검을 `/q:memory` 같은 별도 명령으로 둘지, `/q:doctor` 항목으로만 둘지. 이름은 사용자 결정이라 제안만 한다. 현재는 `/q:doctor` 의 항목 10 과 스크립트로만 있다.
3. `HOOK-MESSAGES.md` 현재 배정 표에 `memory-placement`(warn) 행 추가: 이 문서가 `home/` 안의 다른 에이전트 영역과 가까워 표 수정은 보류했다. 아래 한 줄을 넣으면 된다.
   `| memory-placement | 메모리에 쓴 내용이 저장소 지식으로 보임(파일마다 회차당 한 번) | warn |`
4. 인계 문서 7개를 각 저장소 세션에 전달할지와 시점. 상주 세션이 있는 저장소(quad, stl-luau, devplorer, tbox)는 그 세션이 처리한다.
5. 메모리를 회사 배포 때 기본값으로 끄거나(`autoMemoryEnabled: false`) 켜 둘지. 이식성 문제만 보면 "개인 성향만" 쓰게 하는 지침이 더 가볍다.

## 8. 실측이 남긴 것
`~/.claude/projects/` 에 만든 임시 키 6개: `-tmp-memexpA-dot-1`, `-tmp-memexpB-dot-1`, `-tmp-memexpC-dot-1`, `-tmp-memexpD-dot-1`, `-tmp-memexpE-dot-1`, `-tmp-memexpF-dot-1`. 임시 저장소 `/tmp/memexp{A..F}.dot_1`, `/tmp/memexpC-store`, `/tmp/outside-F`, `/tmp/hk`. 모두 삭제하지 않았다(삭제 금지 원칙). 정리는 사용자 몫이다.
