# 6·7. 복제본 표류와 설정

## 목차
- [6. 복제본 표류](#6-복제본-표류)
  - [훅 중복](#훅-중복)
  - [위임 사본](#위임-사본)
- [7. 설정](#7-설정)

## 6. 복제본 표류

같은 파일을 "복사 후 방치"하면 사본마다 다른 수정이 쌓인다(`audit/04` §3.2).

| 코드 | 대상 | 정본 |
|---|---|---|
| `DRIFT-TYPEDEFS` | `globalTypes*.d.luau` | `/code/Projects/luau-kb/typedefs/globalTypes.d.luau` (md5 `be071eac…`) |
| `DRIFT-HOOK` | `heavy-proc-guard.py` 사본 | `claude-doctor/home/.claude/hooks/heavy-proc-guard.py` |
| `DRIFT-HOOKDUP` | 사용자 레벨과 같은 훅을 프로젝트 settings가 또 등록 | 사용자 레벨 `settings.json` |
| `DRIFT-DELEGATE` | `agy-delegate.sh`, `skills/delegate-agy` 사본 | 통합안 `claude-doctor/drafts/delegate/` (P4) |
| `DRIFT-UID` | 서로 다른 저장소가 같은 agy uid를 쓴다 | 통합안의 `registry.tsv` |
| `DRIFT-SKILLCOPY` | 같은 이름 스킬이 다른 저장소나 사용자 레벨에 있는데 내용이 다르다 | 원본 쪽(사례마다 확인) |

같은 git 저장소의 다른 worktree(stl-luau ↔ stl-luau-doctor)는 사본으로 치지 않는다.

**모델이 볼 것**
- `DRIFT-TYPEDEFS`의 md5가 다르다고 곧 표류는 아니다. 그 저장소의 luau-lsp 핀과 짝인 판일 수 있다.
  - 예: rbvm의 캐시 판, tbox의 `globalTypes.None.d.luau`
  - 그 저장소 `mise.toml` 주석과 `luau-kb/typedefs/README.md`의 비교표를 확인한다.
- 정본과 같은 사본은 지금 고칠 것이 없다. 참조로 바꾸는 일은 P5 범위다.

### 훅 중복

프로젝트 settings가 사용자 레벨과 같은 훅을 등록하면 훅이 두 번 돈다. 차단 메시지나 리마인더도 두 번 나온다.
- 사례: table-sim `.claude/settings.json`의 PreToolUse `heavy-proc-guard.py`
- **고치는 법**
  1. `tools/home-sync.sh status`로 사용자 레벨 훅이 실제 `~/.claude`에 반영됐는지 확인한다.
     - 반영 전이면 프로젝트 쪽을 걷지 않는다. 훅이 0개가 된다.
  2. 반영됐으면 프로젝트 `settings.json`에서 해당 hooks 항목을 걷는 안을 낸다. 설정 편집이라 승인이 필요하다.
  3. 남는 훅 파일(`.claude/hooks/heavy-proc-guard.py`)의 삭제는 HUMAN_TODO로 올린다.

### 위임 사본

agy 위임 도구는 4벌이다(quad, stl-luau, tbox, table-sim). 지금은 고치지 않는다.
- 통합안과 걷어내기 순서는 `claude-doctor/drafts/delegate/README.md`와 `migration.md`에 있다.
- uid 충돌(`DRIFT-UID`)은 격리 보장을 깨므로 보고에 꼭 넣는다. 사례: quad와 tbox가 모두 61000.
  - 고치는 일은 P4 통합 때 한다. 대상 저장소에 세션이 있으면 인계한다.
- `DRIFT-SKILLCOPY`는 어느 쪽이 정본인지부터 확인한다. CLAUDE.md의 "사본" 서술과 git log를 본다.
  - 사본 갱신은 사본을 가진 저장소의 일이다. 그 저장소에 세션이 있으면 인계한다.

## 7. 설정

| 코드 | 뜻 | 처리 |
|---|---|---|
| `SET-JSON` | settings 파일이 JSON으로 읽히지 않는다 | 오류. 고칠 안 |
| `SET-HOOKPATH` | 훅이 가리키는 스크립트가 없다(`$CLAUDE_PROJECT_DIR` 풀어서 확인) | 오류. 경로를 고치거나 훅 항목을 걷는다 |
| `SET-PUSHDENY` | `git push` deny가 있다 | 정보. 고치지 않는다(아래) |
| `SET-BROADALLOW` | `Bash(sed/cp/mv/curl/python3/…:*)` allow가 있다 | 읽기 전용만 남기는 안 |
| `SET-LOCALIGNORE` | `settings.local.json`이 git에서 무시되지 않는다 | `.gitignore` 한 줄 |
| `SET-WTIGNORE` | 경고: `.claude/worktrees/`가 무시되지 않는다. 정보: `.git/info/exclude`(이 기기 전용)로만 무시한다 | `.gitignore`에 `/.claude/worktrees/` 한 줄 |
| `SET-UNTRACKED` | `.claude/`와 CLAUDE.md가 한 번도 커밋되지 않았다 | 사용자 결정 → HUMAN_TODO |
| `SET-DIRTY` | 에이전트 문서에 미추적이나 미커밋 변경이 있다 | 정보. 세션이 작업 중일 수 있다 |
| `SET-NOGIT` | git 저장소가 아니다 | 정보 |

**판단 근거**
- **push deny**: 이 환경은 sandbox이고 git 계정이 에이전트 전용이다. 에이전트의 push가 정상 흐름이고, 사용자가 pull해서 업스트림에 올린다.
  - 그래서 push deny를 권하지 않고, 걷는 것도 사용자 판단이다. `claude-doctor/HUMAN_TODO.md` "권한" 절에 이미 있는지만 확인한다.
- **`.gitignore` 보강**: 실행 중인 세션이 있는 저장소에서는 보류한다(`PLAN.md` P0). 그런 저장소는 인계 문서에 넣는다.
- **미커밋 문서**: 에이전트가 대신 커밋하지 않는다. 사례: moonwave-luau의 `.claude/`가 한 번도 커밋되지 않았다.
- **넓은 allow**: `fewer-permission-prompts` 스킬처럼 실제로 쓰인 읽기 전용 명령만 남기는 안을 낸다.

**모델이 볼 것**
- `settings.local.json`에 공유할 설정(훅, deny)이 숨어 있지 않은지 본다.
- 훅의 matcher가 의도와 맞는지 본다. 예: `Bash` 대신 `*`를 쓰고 있지 않은지.
- 사용자 레벨로 올릴 만한 공통 설정이 있으면 정본 `claude-doctor/home/.claude/settings.json`을 고치는 안을 낸다.
