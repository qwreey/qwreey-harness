# qwreey-delegate 동작 상세

구성은 스킬 `qwreey-delegate:delegate` 하나와 그 드라이버 `skills/delegate/scripts/delegate.py`(표준 라이브러리 Python, `python3 -I` 로 실행) 뿐이다. 같은 폴더의 `delegate.sh` 는 `delegate.py` 를 그대로 부르는 래퍼로, 예전 경로를 부르는 세션을 위해 남겨 둔다. 훅과 규약 주입은 없다. 모델이 따르는 전체 절차는 `skills/delegate/SKILL.md` 에 있고, 여기서는 사람이 알아야 할 구조를 정리한다.

## 언제 쓰나
- 쓴다: 여러 발견이 공유할 수 있는 근본 원인, 지금 틀 밖의 시선, 같은 메커니즘의 발견 묶기, 이름의 객관성 확인(세 계열 비교), 한 메커니즘으로 범위를 정한 버그 사냥.
- 쓰지 않는다: 리뷰 라운드, 전체 감사, 전수 비교표(사용자가 이름을 들어 외부 감사를 요청한 경우는 예외), 결정, 메인 저장소에 그대로 반영할 결과, 결정 이력을 알아야 하는 판단.
- 모델 성향: Gemini(agy)는 틀 밖 근본 원인으로 잘 뛰지만 추론 오류·지어낸 진술·끼워 넣은 조작이 훨씬 잦고 단정적이며, 수정안이 성능을 무시한다. codex 는 맥락을 프롬프트에 모두 담은 객관 판단(이름)에 싸고 빠르다.

## 실행 흐름
1. 지시문: `templates/tasks.md` 골격으로 스크래치에 쓴다. 드라이버가 앞에 공통 머리말(`templates/preamble-{worktree,empty}.md`)을 붙인다(작업 폴더 밖 쓰기 금지, 변경하는 git 명령 금지, `ulimit` 과 종료 코드 판정, 실측과 추정 구분, 기준 커밋을 모델이 직접 확인, 제안은 결정이 아님). 앞선 리뷰의 분류표는 넘기지 않는다(모델이 그 틀에 갇힌다).
2. 실행: `delegate.py run <agy|codex> <name> <prompt> [--repo …] [--mode worktree|empty] [--ref <commit>] [--model M] [--effort …] [--timeout 초] [--keep]`. worktree 는 커밋된 `--ref`(기본 HEAD)에서 자르므로 보여 줄 것은 먼저 커밋한다. Bash `run_in_background` 로 돌리고 완료 알림을 기다린다. 기본 시간 제한 3600초.
   - 모드: agy 기본 `worktree`(분리된 worktree, 셸·편집 허용), codex 기본 `empty`(빈 폴더, 맥락 전부를 프롬프트에, 코드는 `nl -ba` 로 줄 번호).
   - agy `empty` 는 제한된 사본이다: 빈 폴더에서 돌고, 셸과 폴더 밖·임시 폴더의 파일 도구가 거절된다. 이 거절은 agy 의 권한 규칙이지 OS 경계가 아니고, OS 경계는 uid 다.
   - codex `worktree` 는 거절한다(exit 4). codex 의 bubblewrap 샌드박스가 비특권 uid 아래에서 네임스페이스를 만들지 못해 셸이 돌지 않는다. `HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access` 로 끄면 uid 만 남으므로 사용자가 정한다.
3. 수집과 정리(자동): 실행이 끝나면 잠금을 쥔 채로 결과를 `<상태>/runs/<key>/<YYYYMMDD-HHMM>-<name>/` 에 모으고, 파일마다 sha256 으로 사본을 다시 확인한 뒤 작업 폴더(worktree, `.git/worktrees/<id>`, 작업 HOME, 실행 기록)를 지운다. 출력은 `collected: <결과 폴더> (workspace removed)` 와 `report: <결과 폴더>/report.md`.
   - 결과 폴더: `report.md`, `guard.txt`(종료 코드, 메인 저장소 변경 여부, worktree HEAD, 바뀐 파일, agy 가 거절당한 도구), `prompt.md`, `meta.txt`, `state.json`, `exit`, `stdout.txt`, `stderr.txt`(agy), `diff.patch`(worktree, 새 파일 포함, 참고용), `agy/<대화>/`(agy 의 scratch 프로브와 transcript).
   - 확인이 하나라도 어긋나면(git 실패, 복사 오류, 해시 불일치) 아무것도 지우지 않고 `kept: <작업 폴더> - automatic collect failed …` 를 알린다. 이때와 `--keep` 을 준 때는 손으로 `collect`(결과 폴더로 모음) 뒤 `remove`(작업 폴더 삭제, collect 전에는 거절, `--discard` 로 버림)를 한다.
4. 검증(아래). 인용할 보고는 프로젝트 `.claude/audit/<backend>/<date>-<name>.md` 로 옮기고 메인의 검증을 위에 붙여 커밋한다. `runs/` 는 저장소 밖이고 보존 기간이 지나면 지워지므로 근거로 인용하지 않는다.
5. 정리: `list --all`, `gc --all`(미리보기), `gc --all --apply`. gc 는 실행 중이 아닌 작업 폴더를 (모으지 않았으면 먼저 모으고) 지우고, 주인 없는 HOME 과 `HARNESS_DELEGATE_RUNS_DAYS`(기본 14일, `--days` 가 이김)보다 오래된 결과를 지운다. 살아 있는 프로세스가 있는 작업 폴더는 건너뛴다. 저장소 옆 옛 자리(`<dirname(repo)>/<key>-<agent>/`)는 목록만 보이고 지우지 않는다(사용자가 `remove` 나 손으로).

종료 코드: 0 실행 끝(모델 자신의 종료 코드는 `guard.txt`), 2 사용법, 3 에이전트 실행 파일이나 인증 없음, 4 격리 정책상 거절, 5 동시 실행 한도.

## 검증 규칙
- 모든 주장을 메인이 확인한다. 실제로 틀렸던 예: 입력 문서에서 베낀 기준 커밋, 거꾸로 인용한 실측, 반대 방향을 가리킨 인용, 돌리지 않은 테스트를 "실측" 으로 표시, 닫힌 질문을 열린 것으로 셈, 들여쓰기가 바뀐 코드 인용.
- 결함 주장은 재현 테스트를 먼저 쓰고 고친다. 재현되지 않으면 "외부 주장, 메인 재현 안 됨" 으로만 남긴다.
- 수정안은 성능을 다시 잰다(뜨거운 경로).
- 새 필드·이름·메커니즘·규약은 사용자 질문이다. 증상만 확실하면 "증상 확인, 해법 미정".
- `diff.patch` 는 참고용이고 그대로 적용하지 않는다.

## 격리
이 호스트(user namespace 없음)에서는 `agy --sandbox` 와 codex `-s read-only` 가 cwd 밖 접근을 막지 못하고 `unshare -m` 도 허용되지 않아 다음으로 막는다.
1. `setpriv`(`--no-new-privs`, 능력 모두 버림)로 저장소·에이전트별 비특권 uid(61000 부터, 저장소끼리 공유하지 않음). 그 uid 소유는 작업 폴더, `.git/worktrees/<id>`, 작업 HOME 뿐이라 메인 작업 트리와 `.git/objects` 에 쓸 수 없고 커밋·푸시도 못 한다. pre-push 훅이 한 번 더 거절한다. worktree 는 detached 라 브랜치를 만들지 않는다. uid 하나에는 작업 하나만 돈다.
2. agy 는 print 모드로, `--dangerously-skip-permissions` 없이 돈다. `--settings` 가 임시 폴더(`/tmp`, 플랫폼 임시 폴더, `$TMPDIR`)의 `read_file`·`write_file` 을 deny 하고 작업 폴더의 파일 도구를 allow 하며, 셸은 uid worktree 에서만 allow 하고 empty 에서는 deny 한다. 그 밖의 도구(폴더 밖 파일, 밖을 가리키는 링크)는 headless 라 거절되고, 그 턴은 빈 답으로 끝난다. 거절된 도구(`denied_actions`)는 `guard.txt`·`meta.txt`·`state.json` 에 남고, 답이 비면 `run` 이 그 이유를 알린다. 작업 폴더가 deny 하는 임시 폴더 안이면 deny 를 뺄 수 없으므로 run 을 거절한다(exit 4, `doctor` FAIL). 그래서 작업 폴더를 `/tmp` 가 아닌 상태 폴더에 둔다.
3. 빈 환경. PATH 는 저장소 `mise.toml` 에 고정된 도구와 `/usr/bin:/bin`(`/usr/local/bin` 제외), `TMPDIR` 은 작업 HOME 안 `.tmp`.
4. `choom -n 1000`(`HARNESS_HEAVY_WRAP`): 메모리가 모자라면 이 작업이 Claude 보다 먼저 죽는다. agy 자체의 Bash 는 Claude 의 PreToolUse 훅에 보이지 않아 이것이 유일한 손잡이다. qwreey-proc-guard 는 드라이버 명령을 통과시킨다.
5. 메인 저장소의 HEAD 와 상태를 실행 전후로 비교해 `guard.txt` 에 남긴다. CHANGED 면 그사이 메인이나 사용자가 바꿨는지 확인한다.
6. 작업마다 HOME 을 따로(`.homes/<name>`), 인증 정보 사본만 넣는다(agy 는 `~/.gemini` 에서 대화 기록을 뺀 것, codex 는 `auth.json`). `doctor` 가 그 uid 로 `~/.claude/.credentials.json`·`.git-credentials`·`.ssh` 를 읽을 수 없는지 확인한다.
7. root 는 chown 뒤 작업 쪽 폴더에 쓰지 않고, 거기서 읽을 때는 링크를 따라가지 않는다. 실행 기록과 결과는 root 소유 0700/0600 이다.
8. 드라이버는 시작할 때 모든 모듈을 읽어 두므로 실행 중에 플러그인 파일을 고쳐도 돌던 작업이 깨지지 않는다.

이 격리는 Linux root 에 기대고, 지금 드라이버는 empty 모드도 uid 로 돌려서 모드와 상관없이 root 가 필요하다(없으면 exit 4). agy 는 ACP 에서 settings `permissions` 를 듣지 않아(OS 샌드박스 없는 Linux 실측) print 모드만 쓴다. root 없이 도는 판의 설계와 기본 정책: `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/driver-design.md`, `portable-isolation.md`.

## 설정
- uid 표 `registry.tsv`(열: key, root, uid, setup, note, 에이전트별 uid). 여섯째 열 `codex=<uid>` 가 그 에이전트의 uid 이고, agy 와 여섯째 열에 없는 에이전트는 셋째 열을 쓴다. 여섯째 열이 없는 줄은 agy·codex 가 uid 하나를 나눠 하나씩 돈다(`doctor` WARN). `delegate.py register <path> [key]` 가 새 저장소에 에이전트마다 다음 빈 uid 를 주고(`/etc/passwd` 와 겹치지 않게), 여섯째 열이 없는 줄에는 빠진 uid 를 채운다. setup 열은 새 worktree 에서 작업 uid 로 한 번 돈다(실패는 경고만).
- 표 위치: `HARNESS_DELEGATE_REGISTRY`, 없으면 스킬 옆 사본. 고쳐 쓰는 파일이라 플러그인 캐시의 사본은 버전마다 낡으므로 claude-doctor 클론의 것을 가리킨다.
- 저장소마다 루트에 `AGENTS.md`(골격 `templates/AGENTS.md.template`): 정본 경로, 확인 명령, 저장소 전용 주의를 담은 6KB 이하의 지도. 두 모델이 모두 읽는다. `GEMINI.md` 는 지운다(agy 가 둘 다 읽어 겹친다).
- `delegate.py doctor --all`: 인터프리터, 쓰는 harness_env, uid 중복, uid 별 setpriv·메인 트리 쓰기·비밀 읽기, 상태 폴더까지 지나갈 수 있는지, agy 가 deny 하는 임시 폴더, `AGENTS.md`, 적용된 harness.env 파일.
- 설정 키는 harness.env 층(기본값 < `~/.claude/harness.env` < 저장소 `.claude/harness.env` < `.claude/harness.local.env` < 환경 변수)에서 옆의 `harness_env.py` 사본으로 읽는다. 위임 키의 기본값과 설명은 `delegate.py` 의 `ENV_DEFAULTS`, 저장소 층이 바꾸지 못하는 키는 `ENV_USER_ONLY` 다. 모델 키와 `HARNESS_DELEGATE_SECRET_GLOBS` 말고는 모두 USER_ONLY 라 저장소 파일로는 바꾸지 못한다(클론한 저장소가 격리를 풀면 안 되므로). `HARNESS_DELEGATE_REGISTRY`, `HARNESS_TOOL_INSTALLS`, `HARNESS_HEAVY_WRAP` 은 다른 플러그인도 읽어 로더(`home/.claude/lib/harness_env.py`)가 정한다.
  - `HARNESS_DELEGATE_MAX_CONCURRENT`(기본 1): 에이전트마다, 모든 저장소 합계. 토큰 한도가 사용자 단위라서. 사용자가 여유가 있다고 할 때만 늘린다.
  - `HARNESS_DELEGATE_STATE`: 상태 폴더(작업 폴더 `work/`, 결과 `runs/`, 잠금). 기본 `$XDG_STATE_HOME/qwreey-delegate`(없으면 `~/.local/state/qwreey-delegate`). 작업 uid 가 그 부모들을 지나갈 수 있어야 한다.
  - `HARNESS_DELEGATE_RUNS_DAYS`(기본 14): gc 가 지우는 결과의 나이(일).
  - `HARNESS_DELEGATE_CODEX_SANDBOX`(기본 `read-only`), `HARNESS_DELEGATE_KEEP_ENV`(비어 있지 않으면 빈 환경 대신 지금 환경, 토큰 변수가 샐 수 있음).
  - 실행 파일·인증 위치: `HARNESS_DELEGATE_AGY_BIN`, `HARNESS_DELEGATE_CODEX_BIN`(기본은 PATH, 없으면 `HARNESS_TOOL_INSTALLS` 아래), `HARNESS_DELEGATE_AGY_HOME`(기본 `~/.gemini`), `HARNESS_DELEGATE_CODEX_HOME`(기본 `$CODEX_HOME`, 없으면 `~/.codex`).
  - 모델(저장소 층도 정할 수 있음): `HARNESS_DELEGATE_AGY_MODEL`(`gemini-3.8-flash-high`, pro 는 없는 것으로 본다), `HARNESS_DELEGATE_CODEX_MODEL`(`gpt-6-luna`). `run --model` 이 이긴다. effort 기본 `medium`.

## 작업 폴더
상태 폴더 아래에 둔다. 모두 root 소유이고, 작업 uid 가 지나가야 하는 폴더(상태 폴더, `work/`, `<key>-<agent>/`, `.homes/`, `.hooks/`)는 0711, 기록·결과·잠금 폴더는 0700 이다.
- `work/<key>-<agent>/`: `<name>/`(작업 폴더, 작업 uid 소유), `.homes/<name>/`(작업 HOME), `.hooks/pre-push`, `.runs/<name>/`(실행 기록). 성공한 실행은 끝에 지워진다.
- `runs/<key>/<YYYYMMDD-HHMM>-<name>/`: 모은 결과. gc 가 보존 기간 뒤 지운다.
- `slots/`, `uids/`, `start-<agent>.lock`: 동시 실행 슬롯, uid 별 잠금, 시작 잠금.

손으로 만들거나 고치지 않는다. 저장소 옆 `<repo>-scratch` 는 버려도 되는 실험, `<repo>-proto/<slug>` 는 프로토타입 브랜치의 worktree 다. 상태 폴더와 형제 폴더는 클론에 없으므로 근거로 인용하지 않는다. 예전 판이 저장소 옆에 만든 `<repo>-agy`·`<repo>-codex` 는 `list`·`collect`·`remove` 가 계속 찾고 gc 는 목록만 보인다.
