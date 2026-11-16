# qwreey-workspace 동작 상세

네 부분으로 이루어진다: 규약 주입(`scripts/ambient.py`), 게이트(`scripts/workspace_gate.py`), 오래된 worktree 알림(`scripts/stale_worktrees.py`), 스킬 `qwreey-workspace:workspace`.

## 작업공간과 형제 저장소
- 작업공간 루트는 환경 변수 `HARNESS_WORKSPACE`, 없으면 `~/.claude/harness.env`(또는 `$CLAUDE_CONFIG_DIR/harness.env`) 의 같은 키. harness.env 는 옆의 `scripts/harness_env.py` 사본(하네스 로더의 사본)으로 읽는다. 둘 다 비면 게이트와 지도가 꺼진다. `HARNESS_WORKSPACE`(로더의 `USER_ONLY`, 여러 플러그인이 읽는다)와 `HARNESS_WORKSPACE_GATE`(`scripts/wslib.py` 의 `ENV_USER_ONLY`)는 저장소 `.claude/harness.env`·`.claude/harness.local.env` 가 바꾸지 못한다(클론한 저장소가 게이트를 끄지 못하게). `HARNESS_WORKSPACE_AMBIENT` 같은 다른 스위치는 저장소 층(local 이 공유 파일을 이긴다)에 둘 수 있다.
- 이 세션의 저장소는 `CLAUDE_PROJECT_DIR`(없으면 입력의 `cwd`). `HARNESS_WORKSPACE/<X>` 중 이 저장소가 아닌 것이 형제 저장소다.
- 경로는 `normpath` 로만 비교한다. `realpath` 를 쓰지 않는 것은 `~/.claude/rules` 같은 심볼릭 링크가 형제 경로로 풀려 오판되지 않게 하려는 것이다.

## 규약 주입
- 훅: `SessionStart`(matcher `startup|resume|clear|compact`)와 `SubagentStart` → `scripts/ambient.py`.
- `context/ambient.md` 세 줄을 `<plugin name="qwreey-workspace">` 로 감싸 `additionalContext` 로 낸다: `*-kb` 먼저, 형제 저장소는 승인 없이 고치지 않음(고치기 전 스킬 로드), `.claude/worktrees/*` 는 잠금·세션 확인 전에 지우지 않음.
- 서브에이전트에도 싣는 이유: 게이트가 서브에이전트의 쓰기도 막으므로 규약을 알아야 한다. fork(`agent_type == "fork"`)는 부모 맥락을 물려받으므로 건너뛴다.
- 블록과 게이트의 태그 끝에 이 세션의 `nonce="…"` 속성을 달고, 같은 이벤트의 규칙 줄을 이 훅이 먼저 맡으면 블록 맨 앞에 싣는다(`scripts/harness_nonce.py`, 규약은 `home/.claude/HOOK-MESSAGES.md` 2번).
- `PreCompact`(manual·auto) → `scripts/ambient.py PreCompact`: 요약기에게 `Omit the <plugin name="qwreey-workspace"> block from the summary; it is re-injected after compaction.` 한 줄을 일반 stdout 으로 낸다. SessionStart(compact) 가 다시 실으므로 요약에 남은 사본은 중복이다. 서브에이전트의 compact(`agent_id` 있음)와 규약 파일이 없을 때는 내지 않는다.
- `scripts/ambient.py` 은 저장소 `lib/ambient.py` 의 바이트 사본이다(고치지 말고 정본을 고친 뒤 `python3 -I tools/sync-copies.py --apply`). 플러그인마다 다른 것은 `context/ambient.json`(`plugin`, `events`)에 둔다. 끄기 스위치는 없다.

## 게이트
- 훅: `PreToolUse`(matcher `Edit|Write|MultiEdit|NotebookEdit|Read|Grep|Glob|Bash`).
- 쓰기: `Edit`·`Write`·`MultiEdit`·`NotebookEdit` 의 경로, 또는 쓰기로 분류된 Bash 가 형제 저장소를 건드리고 스킬 로드 표시가 없으면 deny(`level="action"`). 사유는 "스킬을 로드하고 다시 시도하라, 사용자가 승인하지 않았으면 먼저 물어라".
  - 알림이 아니라 deny 인 이유: PreToolUse 의 `additionalContext` 는 도구가 실행된 뒤에 모델에게 들어가서 첫 쓰기를 막지 못한다.
- 읽기: `Read`·`Grep`·`Glob` 과 쓰기가 아닌 Bash 는 compact 회차마다 한 번 info 알림만 낸다. 스킬을 로드한 뒤에는 내지 않는다.
- Bash 분류(`scripts/wslib.py` `classify_bash`): 명령을 `;`·`&&`·`|` 등으로 나눠 각 조각의 머리 명령을 본다(`sudo`·`env`·`timeout` 같은 접두는 건너뜀).
  - 쓰기로 보는 것: `rm mv touch mkdir chmod tee patch` 등, `cp install ln rsync scp` 의 마지막 인자, 쓰는 git 하위 명령(`commit add checkout reset push merge` 등), `sed -i`·`perl -i`·`awk -i inplace`·`git apply`·`dd of=`, 파일 쓰기 신호가 있는 인터프리터 한 줄(`python -c "…open(…, 'w')…"` 등), 리다이렉트 대상.
  - `cd`·`pushd`·`git -C` 로 바뀐 작업 폴더를 따라간다. 형제 저장소로 `cd` 한 뒤 상대 경로를 쓰면 그 저장소 쓰기로 본다.
  - 하네스의 `bash-bypass-reminder` 분류기는 경로를 보지 않으므로 경로를 보는 분류기를 따로 둔다.
- 스킬 로드 표시: `PostToolUse`(matcher `Skill`)에서 `tool_input.skill` 이 `qwreey-workspace:workspace`(또는 `workspace`)이거나, 슬래시로 쳤을 때 `UserPromptExpansion` 의 `command_name`. 표시 단위는 (session_id, agent_id, compact 회차)라 서브에이전트와 compact 뒤에는 다시 로드해야 한다.
- 예외가 나면 통과시킨다(fail-open).

## 오래된 worktree 알림
- 훅: `SessionStart`(matcher `startup|resume|clear`) -> `scripts/stale_worktrees.py`. compact 뒤에는 돌지 않고, `agent_id` 가 있으면 건너뛴다. `HARNESS_WORKSPACE` 가 비면 아무것도 하지 않는다.
- 대상: 이 세션 저장소(`CLAUDE_PROJECT_DIR`, 없으면 `cwd`)의 `git worktree list --porcelain` 에서 첫 항목(주 worktree)과 이 세션이 들어 있는 worktree 를 뺀 전부. `.claude/worktrees/*` 와 형제 폴더 worktree 를 가리지 않는다. 다른 저장소는 보지 않는다.
- 마지막으로 손댄 때: HEAD 커밋 시각, 관리 폴더(`<git-common-dir>/worktrees/<name>`)의 `index`·`HEAD`·`logs/HEAD` mtime, worktree 루트 폴더 mtime 중 가장 늦은 것. 트리 안의 파일은 하나하나 보지 않으므로(큰 트리에서 비싸다) 커밋도 `git add` 도 없이 파일만 고친 worktree 는 실제보다 오래돼 보일 수 있다. 반대로 `GIT_OPTIONAL_LOCKS=0` 없이 `git status` 를 돌리면 index 가 새로 쓰여 최근에 손댄 것처럼 보인다.
- 빼는 것: porcelain 의 `locked`, 그리고 Linux `/proc` 에서 comm 이 `claude`·`agy`·`codex` 인 프로세스의 cwd 가 worktree 안인 것. `/proc` 이 없거나 다른 uid 의 cwd 를 읽지 못하면(위임 실행) 살아 있는 세션을 모르는 채로 둔다.
- 폴더가 사라진 등록(porcelain `prunable` 또는 폴더 없음)은 잠기지 않았으면 나이와 무관하게 따로 적는다. 잃을 작업이 없고 등록만 남은 것이기 때문이다.
- 커밋 안 한 변경: 알림에 이름이 나오는 worktree(오래된 순 3개)만, 관리 폴더 index 가 2MB 이하일 때, `GIT_OPTIONAL_LOCKS=0 git status --porcelain --untracked-files=no` 를 1.5초 안에서 본다. 추적하지 않는 새 파일은 보지 않는다(폴더 전체를 훑어야 해서). 못 보면 표시하지 않는다.
- 시간: git 호출마다 3초, 전체 6초 예산(hooks.json timeout 10초). 어떤 실패든 출력 없이 exit 0.
- 문턱: `HARNESS_WORKSPACE_STALE_WORKTREE_DAYS`(일, 기본 14, `scripts/wslib.py` 의 `ENV_DEFAULTS`). `off`·`0`·빈 값이면 끈다. 저장소 층에 둘 수 있다(USER_ONLY 아님).
- 알림(`<harness-hook name="stale-worktrees" level="info">`, 규칙 줄을 맡으면 맨 앞에): 개수, 오래된 순 3개의 경로(저장소 안이면 상대 경로)·브랜치·일수·변경 여부, prunable 목록, 그리고 "끝난 작업일 수 있다. 정리할 때면 스킬의 worktree 잠금·살아 있는 세션 확인을 거치고 지우기 전에 사용자에게 물어라. 사용자가 두는 것이거나 지금 일과 무관하면 할 것 없다". 지우는 명령은 적지 않는다.
- 세션마다 한 번: `$TMPDIR/claude-workspace-worktrees/<sid>` 를 O_EXCL 로 만든 경우만 낸다. resume 은 같은 session_id 라 다시 내지 않는다.

## 상태와 로그
- 게이트 상태: `$TMPDIR/claude-workspace-gate/<sid>.c<회차>[.a<agent_id>].json`(`loaded`, `warned`).
- deny 기록: `$TMPDIR/claude-workspace-gate/deny.log`.
- compact 회차: 이 플러그인 자기 것, `$TMPDIR/claude-qwreey-workspace-epoch/<sid>`. `PreCompact`(manual·auto)에서 `scripts/compact_epoch.py qwreey-workspace` 가 올리고 게이트는 읽기만 한다.

## 스킬 `qwreey-workspace:workspace`
- 지도: `skills/workspace/scripts/map.py` 가 `HARNESS_WORKSPACE` 아래 `.git` 이 있는 폴더마다 한 줄(그 폴더의 `CLAUDE.md`·`AGENTS.md`·`README.md` 중 처음 있는 파일에서 제목이 아닌 첫 줄, 120자), `*-kb` 를 맨 위에, 현재 저장소에 표시.
- 살아 있는 세션 확인: Linux 는 `pgrep -x claude|agy|codex` 의 `/proc/<pid>/cwd`, macOS 는 `lsof -a -d cwd`.
- worktree 잠금 확인: `<git-common-dir>/worktrees/<name>/locked` 파일과 살아 있는 세션의 cwd.
- 승인 뒤 절차: 승인 범위를 한 줄로 다시 말하고, 그 변경만, 요청이 없으면 커밋·푸시하지 않고, 무엇을 어느 저장소에서 바꿨는지 보고.
- `HARNESS_WORKSPACE` 가 없으면 사용자에게 설정을 안내하고 `~/.claude/harness.env` 를 직접 고치지 않는다.

## 끄기
- `HARNESS_WORKSPACE_GATE=off`(환경 변수 또는 사용자 harness.env): 게이트만 끈다. 규약 주입은 플러그인이 켜져 있는 한 계속된다.
- `HARNESS_WORKSPACE_STALE_WORKTREE_DAYS=off`(또는 `0`): 오래된 worktree 알림만 끈다. 저장소 층에서도 끌 수 있다.

## 테스트
```bash
python3 -I plugins/qwreey-workspace/tests/test_workspace_gate.py
python3 -I plugins/qwreey-workspace/tests/test_ambient.py
python3 -I plugins/qwreey-workspace/tests/test_stale_worktrees.py
```
