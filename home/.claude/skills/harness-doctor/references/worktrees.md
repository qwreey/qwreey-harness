# 8·9. 툴체인과 worktree 위생

## 목차
- [8. 툴체인](#8-툴체인)
  - [형제와 같다는 주석](#형제와-같다는-주석)
- [9. worktree 위생](#9-worktree-위생)

## 8. 툴체인

`.luau` 파일이 있는 저장소에서만 본다.

| 코드 | 뜻 | 등급 |
|---|---|---|
| `TOOL-PIN` | mise.toml의 luau, luau-lsp, stylua 핀. D-05 권고 목표(0.742 / 1.70.1 / 2.5.2)와 비교한다 | 정보 |
| `TOOL-SYNTAX` | `stylua.toml`에 `syntax = "Luau"`가 없다 | 오류 |
| `TOOL-NOSTYLUA` | stylua 설정 파일이 없다 | 경고 |
| `TOOL-CLAIM` | 설정 주석이 "형제와 같다"고 하는데 실제 값이 다르다 | 경고(같다) / 정보(따른다) |
| `TOOL-LUAURC` | `.luaurc`가 없다 | 정보 |

**판단 근거**
- **D-05 (버전 핀, 제안)**: 공통 규칙으로 제안된 것은 두 가지다.
  1. 수치·결함 서술에는 그 버전을 같이 적는다.
  2. 0.734를 쓰는 저장소는 `luau-analyze`의 비정상 종료를 실패로 판정한다.
  - 0.742 통일은 권고 목표일 뿐이다. 핀 차이는 정보로만 보고하고, 핀을 올리자고 고치지 않는다. 사용자가 물으면 D-05를 가리킨다.
  - luau-lsp 핀은 Roblox `globalTypes.d.luau` 판과 짝이다(table-sim, devplorer, tbox). lsp만 따로 올리면 안 된다.
  - 0.734를 쓰는 저장소는 게이트(`check.sh`)가 비정상 종료를 실패로 보는지 확인한다. 본보기는 stl `check.sh:29`다.
- **D-02 (stylua)**: 사고를 내는 것은 설정 값이 아니라 설정이 적용되지 않은 실행이다.
  - `syntax = "Luau"`가 없거나 하위 폴더에서 실행하면 `f<<T>>`가 exit 0인 채로 시프트 연산이 된다(재현됨).
  - 재현 스크립트: `/code/Projects/luau-kb/tools/repro-stylua-typeargs.sh`
  - `syntax = "Luau"` 한 줄은 D-02의 두 안 모두에 들어 있어 갈리는 항목이 아니다. 승인을 받으면 고칠 수 있다.
  - `indent_type`과 `call_parentheses` 값은 D-02 미결이다. 건드리지 않는다.
- **D-03 (러너)**: lune은 `const`를 파싱하지 못한다. `.vscode`의 `@lune/` 별칭처럼 lune 흔적과 "lune 안 씀" 서술이 섞여 있으면 모순으로 보고한다(moonwave 사례).

**모델이 볼 것**
- 게이트 스크립트(`scripts/check.sh`, `mise run check`)가 stylua를 저장소 루트에서 `--check`로 부르는지 본다.
- 문서에 적힌 버전과 `mise.toml`의 실제 핀이 같은지 본다. CLAUDE.md, GEMINI.md, conventions를 확인한다.

### 형제와 같다는 주석

`mise.toml`이나 `stylua.toml` 주석이 형제 저장소 이름을 들며 "같다"고 하면, scan이 형제의 실제 파일과 비교한다.
- mise 주석이 `stylua.toml` 모양을 말하면 stylua 설정끼리 비교한다.
- 실례
  - table-sim `mise.toml:3`: "quad·tbox·stl-luau와 같은 값"이라고 하지만 stl은 0.742/1.70.1이다.
  - stl `stylua.toml:1`: "tbox/quad와 같은 설정"이라고 하지만 tbox는 Spaces+Input이고 quad는 설정 파일이 없다.
- **고치는 법**: 형제 이름 대신 그 값을 고른 이유를 적는다. 예: "typedefs 정의 파일과 짝", "배터리 기대 건수 재현".
  형제 이름을 주석에 넣지 않으면 형제가 바뀌어도 낡지 않는다.
- `claude-doctor/decisions/README.md`의 "이번에 발견한 낡은 서술" 목록과 대조해 이미 알려진 것인지 적는다.

## 9. worktree 위생

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

**오판 사례** (반복하지 않는다)
- quad `.claude/worktrees/agent-afbfdf8c7cd112b20`(14GB): 감사 보고서가 정리 대상으로 판정했다.
  - 실제로는 lock이 걸린 채 다른 세션이 쓰고 있었다.
  - 처음 쓴 mtime 검사는 문법 오류로 전부 0을 반환했다. 검사 결과를 그대로 믿지 않는다.
- table-sim-agy/trial-query: scan을 돌리던 그 순간 agy가 그 안에서 실행 중이었다(`WT-ACTIVE`, antigravity 프로세스).
  - 그 worktree는 다른 uid 소유라 git이 "dubious ownership"으로 거부한다. scan은 `-c safe.directory=*`로 읽기만 한다.

**고치는 법**: 지우지 않는다. `WT-CANDIDATE`와 `WT-ORPHAN`은 `claude-doctor/HUMAN_TODO.md` "삭제와 정리" 절에 올린다.
- 항목에 적을 것: 경로, 브랜치, 미커밋 수, 메인에 없는 커밋 수, 크기(`du -sh`, 사용자가 원할 때만 잰다), 확인 시각
- 명령: `git -C <메인> worktree remove <경로>`. 브랜치는 남는다고 명시한다.
- 미병합 커밋이 있으면 브랜치 보존과 백업 위치를 제안한다. 선례 위치는 `/code/backups/claude-doctor-<날짜>/`다.
- 대상 저장소에 세션이 있으면 "그 세션이 끝난 뒤"라는 조건을 붙인다.
