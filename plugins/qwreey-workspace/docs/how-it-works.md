# qwreey-workspace 동작 상세

세 부분으로 이루어진다: 규약 주입(`scripts/ambient.py`), 게이트(`scripts/workspace_gate.py`), 스킬 `qwreey-workspace:workspace`.

## 작업공간과 형제 저장소
- 작업공간 루트는 환경 변수 `HARNESS_WORKSPACE`, 없으면 `~/.claude/harness.env`(또는 `$CLAUDE_CONFIG_DIR/harness.env`) 의 같은 키. harness.env 는 하네스의 `lib/harness_env.py` 로 읽으므로, 그 파일이 없는 환경에서는 환경 변수로 줘야 한다. 둘 다 비면 게이트와 지도가 꺼진다.
- 이 세션의 저장소는 `CLAUDE_PROJECT_DIR`(없으면 입력의 `cwd`). `HARNESS_WORKSPACE/<X>` 중 이 저장소가 아닌 것이 형제 저장소다.
- 경로는 `normpath` 로만 비교한다. `realpath` 를 쓰지 않는 것은 `~/.claude/rules` 같은 심볼릭 링크가 형제 경로로 풀려 오판되지 않게 하려는 것이다.

## 규약 주입
- 훅: `SessionStart`(matcher `startup|resume|clear|compact`)와 `SubagentStart` → `scripts/ambient.py`.
- `context/ambient.md` 세 줄을 `<plugin name="qwreey-workspace">` 로 감싸 `additionalContext` 로 낸다: `*-kb` 먼저, 형제 저장소는 승인 없이 고치지 않음(고치기 전 스킬 로드), `.claude/worktrees/*` 는 잠금·세션 확인 전에 지우지 않음.
- 서브에이전트에도 싣는 이유: 게이트가 서브에이전트의 쓰기도 막으므로 규약을 알아야 한다. fork(`agent_type == "fork"`)는 부모 맥락을 물려받으므로 건너뛴다.
- `PreCompact`(manual·auto) → `scripts/ambient.py PreCompact`: 요약기에게 `Omit the <plugin name="qwreey-workspace"> block from the summary; it is re-injected after compaction.` 한 줄을 일반 stdout 으로 낸다. SessionStart(compact) 가 다시 실으므로 요약에 남은 사본은 중복이다. 서브에이전트의 compact(`agent_id` 있음)와 규약 파일이 없을 때는 내지 않는다.

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
- `HARNESS_WORKSPACE_GATE=off`(환경 변수 또는 harness.env): 게이트만 끈다. 규약 주입은 플러그인이 켜져 있는 한 계속된다.

## 테스트
```bash
python3 -I plugins/qwreey-workspace/tests/test_workspace_gate.py
```
