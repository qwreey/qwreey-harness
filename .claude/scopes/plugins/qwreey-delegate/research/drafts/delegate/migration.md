# 기존 4벌 걷어내기 — 순서와 시점

2026-11-10 기준 상태
- `pgrep -x claude`의 cwd를 보면 quad, devplorer, stl-luau, tbox에서 다른 Claude 세션이 돌고 있다.
- table-sim에는 돌고 있는 세션이 없다.
- 위임 과제는 하나도 돌고 있지 않다(`gc --all` 미리보기에 "held" 없음).

## 왜 시점이 중요한가

- 돌고 있는 세션은 시작할 때 프로젝트 스킬 목록(`delegate-agy`)을 실었다. 그 세션이 다음에 위임하려 할 때 스크립트 경로가 사라져 있으면 실패한다. 그러면 세션이 우회로를 즉흥적으로 만들 위험이 있다.
- 옛 `agy-delegate.sh`는 실행 중에 파일이 바뀌면 bash가 끝부분을 엉뚱하게 파싱한다(stl-luau 2026-10-02 사고). 돌고 있는 과제가 있을 때 고치거나 지우지 않는다. 새 `delegate.sh`는 자기 사본으로 다시 실행되므로 이 문제가 없다.
- 프로젝트 `.claude/`에 다른 세션의 미커밋 변경이 있을 수 있다. 같은 파일을 두 세션이 고치면 충돌한다.

### 작업해도 되는 시점 (저장소마다, 셋 다 만족)

```bash
R=/code/Projects/<repo>
for p in $(pgrep -x claude); do readlink /proc/$p/cwd; done | grep -qx "$R" && echo "세션 있음 — 기다림"
delegate.sh gc --repo <repo> | grep -q '^held' && echo "위임 과제 도는 중 — 기다림"
git -C "$R" status --porcelain -- .claude CLAUDE.md GEMINI.md AGENTS.md | grep -q . && echo ".claude 에 미커밋 변경 — 그 세션 몫인지 확인"
```

`claude --worktree` 세션도 확인한다. cwd가 `$R/.claude/worktrees/*`일 수 있으므로 `grep "^$R"`로도 한 번 더 본다.

## 단계

### 0. 사용자 레벨 설치 — 언제든 (프로젝트를 건드리지 않음)

- `~/.claude/skills/delegate/`(SKILL, scripts, templates, registry)를 설치한다. P1 담당이 한다(`~/.claude`는 이 초안 작업의 범위 밖).
- `delegate.sh doctor --all` → FAIL이 0개인지 확인한다. 2026-11-10 초안으로 이미 확인함: 넷 모두 ok, WARN은 AGENTS.md 없음뿐.
- 이름이 `delegate`라서 프로젝트 스킬 `delegate-agy`와 충돌하지 않는다. 돌고 있는 세션은 그대로 옛 것을 쓴다. 과도기에는 두 스킬의 설명이 같이 보이는데, 4단계에서 프로젝트 쪽이 사라진다.

### 1. 시범 — table-sim (지금 세션 없음)

1. `table-sim/AGENTS.md`를 만든다(템플릿과 `conventions.md` §2 표).
2. 좁은 과제 하나로 실제 agy를 한 번 돌린다. 확인할 것:
   - `env -i`에서 agy가 뜨는가
   - 도구 PATH(luau 0.734, stylua 2.5.2)로 `tests/run.luau`가 exit 0인가
   - guard가 `unchanged`인가
   - collect, remove가 되는가
   - 안 되면 `HARNESS_DELEGATE_KEEP_ENV=1`(사용자 층)로 다시 돌리고, 원인을 스크립트에 반영한다.
3. codex empty 모드로 이름 검토 하나를 돌린다. 옛 수동 꼴과 같은 결과 파일이 나오는지 본다.
4. table-sim의 `.claude/tools/agy-delegate.sh`를 지우고, conventions의 위임 포인터 한 줄을 "다른 모델 계열은 사용자 스킬 `delegate`"로 바꾼다. table-sim에는 프로젝트 스킬 사본이 없다. 커밋은 사용자 확인 뒤에 한다.

### 2. 옛 잔여물 정리 — 사용자 승인 후 (삭제 포함)

| 대상 | 크기 | 처리 |
|---|---|---|
| `quad-agy/naming-1021e`(worktree, 브랜치 `agy/naming-1021e`) | 83M | `AGY_REPORT.md`가 이미 `quad/.claude/audit/naming-devui-*`에 반영됐는지 확인 → `quad-agy/runs/legacy-naming-1021e/`로 복사 → `delegate.sh remove agy naming-1021e --repo quad --discard`. 브랜치 삭제(`--delete-branch`)는 사용자 확인 |
| `quad-agy/.home`, `stl-luau-agy/.home`, `tbox-agy/.home`, `quad-codex/.home` | 117M + 260M + 228M + 31M | Python 드라이버의 gc 는 저장소 옆 옛 자리를 목록으로만 보인다(`delegate.sh gc --all` 의 `stale … .home`). 사용자가 확인한 뒤 손으로 지운다(`HUMAN_TODO.md`). **옛 스크립트(quad, tbox)는 공유 `.home`을 쓰므로, 그 저장소 세션이 옛 스크립트로 위임 중이면 안 된다** |
| `quad-codex/naming-*`, `run-marker-helper` | 수십 KB | `quad-codex/runs/<날짜>-<이름>/`으로 `mv`(날짜는 mtime이나 디렉터리 이름). gc는 건드리지 않는다 |
| `stl-luau-scratch/no-self-return/wt`(worktree `proto/no-self-return`) | — | 규약상 `-proto`. stl-luau 세션이 쓰는 중일 수 있으니 4단계 stl-luau 시점에 `git worktree move`(사용자 확인) |

### 3. tbox — 세션이 끝난 뒤

- 이유: uid 충돌(61000)이 걸린 곳이라 빨리 옮길수록 좋다. 다만 지금 세션이 있다.
- 할 일
  - `AGENTS.md`를 만든다. 옛 머리말의 검사 명령을 옮긴다.
  - `.claude/skills/delegate-agy/`와 `.claude/tools/agy-delegate.sh`를 지운다. tbox `.claude/`에는 이 둘뿐이라 `.claude/`가 비게 된다.
  - CLAUDE.md에 위임 언급이 있으면 한 줄로 바꾼다.
- 그때까지는 quad와 tbox가 같은 날 옛 스크립트로 동시에 위임하지 않게 한다(기존 위험이 그대로 남아 있다).

### 4. stl-luau — 세션이 끝난 뒤

- `GEMINI.md`를 `AGENTS.md`로 새로 쓴다(P0 ⑤를 대신함). `GEMINI.md`는 지운다.
- 스킬과 스크립트 사본을 지운다.
- conventions "리뷰" 절의 delegate-agy 언급을 바꾼다.
- 프로젝트 메모리 `agy-budget-generous`, `agy-is-second-opinion`은 내용이 SKILL "비용", "언제"로 옮겨졌다. 메모리 정리는 `~/.claude` 담당에게 넘긴다.
- **stl-luau-doctor**에 같은 사본이 있다(md5 동일, 2026-11-10 15:46 생성). P3 시범 작업자의 클론으로 보인다. 그 작업자와 맞춰 같이 걷어낸다.

### 5. quad — 마지막 (가장 활발함)

- `AGENTS.md`를 새로 쓴다. 마지막 절이 `external-review-entry.md`를 가리킨다.
- `.claude/skills/delegate-agy/`와 `.claude/tools/agy-delegate.sh`를 지운다.
- `conventions.md:380`과 `heavy-proc-guard.py`의 `agy-delegate.sh` 예외 문구를 `delegate.sh`로 바꾼다. 훅의 제외 패턴도 같이 바꾼다.
- quad 메모리 `feedback-agy-cross-family-review`, `reference-codex-delegation`의 경로 서술도 바꾼다. 이것도 `~/.claude` 담당이다.
- **vendor 사본**: `devplorer/vendor/quad/`, `table-sim/<비공개>`에도 quad의 `.claude` 사본이 있다. vendor는 손대지 않는다. quad에서 지워지면 다음 vendor 동기화 때 같이 사라진다.

### 6. 마무리

- `delegate.sh doctor --all`에서 INFO "옛 사본 남음"이 0개인지 확인한다.
- `delegate.sh gc --all`에 저장소 옆 옛 자리(`legacy …`)가 남지 않았는지 확인한다.
- 사용자 레벨 CLAUDE.md에 접미 디렉터리 세 줄(`conventions.md` §1)을 넣는다.

## 되돌리기

- 옛 스크립트와 스킬은 각 저장소의 git 기록에 있다(`git checkout <커밋> -- .claude/tools/agy-delegate.sh .claude/skills/delegate-agy`).
- 중앙 표의 tbox uid를 되돌릴 이유는 없다. 61003은 충돌 해소다.
