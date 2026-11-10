# 9. worktree 위생

언어와 무관한 코어 검사다. 툴체인 검사(옛 8번 절)는 툴킷으로 옮겼다: `references/toolkits/<이름>.md`.

**반드시 지킬 확인 순서** (하나라도 걸리면 '쓰는 중'으로 본다)
1. **lock**: `git worktree list --porcelain`의 `locked` 줄
2. **실행 중인 프로세스**: cwd가 그 경로 안에 있는 claude, agy, codex
   - `pgrep -f claude`는 셸 래퍼까지 잡는다. 실행 파일 이름(`/proc/<pid>/exe`)으로 거른다. scan이 그렇게 한다.
3. **마지막 활동**: 메인 `.git/worktrees/<이름>/`의 `index`, `HEAD`, `logs/HEAD` mtime. 2시간 이내면 쓰는 중으로 본다.
4. **미커밋 변경** 수와 **메인에 없는 커밋** 수. 0이 아니면 정리 전에 보존 방법을 정해야 한다.

| 코드 | 뜻 |
|---|---|
| `WT-ACTIVE` | lock, 세션, 최근 활동 중 하나가 있다. 정리 금지 |
| `WT-CANDIDATE` | 위 셋이 모두 없다. 정리 후보지만 직전에 다시 확인한다 |
| `WT-ORPHAN` | `.claude/worktrees/` 아래에 있지만 git worktree 목록에 없는 디렉터리 |

대상이 자기 git 저장소의 루트가 아니면(반입 사본 `intake/<이름>/` 등) 이 항목은 건너뛴다(`SET-NOGIT` 정보).

**오판 사례** (반복하지 않는다)
- quad `.claude/worktrees/agent-afbfdf8c7cd112b20`(14GB): 감사 보고서가 정리 대상으로 판정했다.
  - 실제로는 lock이 걸린 채 다른 세션이 쓰고 있었다.
  - 처음 쓴 mtime 검사는 문법 오류로 전부 0을 반환했다. 검사 결과를 그대로 믿지 않는다.
- table-sim-agy/trial-query: scan을 돌리던 그 순간 agy가 그 안에서 실행 중이었다(`WT-ACTIVE`, antigravity 프로세스).
  - 그 worktree는 다른 uid 소유라 git이 "dubious ownership"으로 거부한다. scan은 `-c safe.directory=*`로 읽기만 한다.

**고치는 법**: 지우지 않는다. `WT-CANDIDATE`와 `WT-ORPHAN`은 `<doctor>/HUMAN_TODO.md` "삭제와 정리" 절에 올린다(`<doctor>` = `scan.py --env`의 `DOCTOR_ROOT`).
- 항목에 적을 것: 경로, 브랜치, 미커밋 수, 메인에 없는 커밋 수, 크기(`du -sh`, 사용자가 원할 때만 잰다), 확인 시각
- 명령: `git -C <메인> worktree remove <경로>`. 브랜치는 남는다고 명시한다.
- 미병합 커밋이 있으면 브랜치 보존과 백업 위치를 제안한다. 백업은 작업공간 밖 사용자 백업 디렉터리에 둔다(이 환경의 선례: `/code/backups/claude-doctor-<날짜>/`).
- 대상 저장소에 세션이 있으면 "그 세션이 끝난 뒤"라는 조건을 붙인다.
