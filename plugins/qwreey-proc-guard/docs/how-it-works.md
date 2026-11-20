# qwreey-proc-guard 동작 상세

구성: PreToolUse(Bash) 훅 둘. `hooks/heavy-proc-guard.py`(무거운 실행, 아래 대부분)와 `hooks/self-match-guard.py`(자기 셸에 걸리는 `pgrep -f`, 그 아래 절). 둘 다 `hooks/shell_segments.py` 로 heredoc 본문을 버리고 구간을 나눈다. 그리고 PreToolUse·PostToolUse·PostToolUseFailure(Bash) 에 도는 `hooks/resource-guard.py`(디스크 여유 공간과 core dump, 맨 아래 절). 스킬과 규약 주입은 없고, 상태 파일은 resource-guard 만 쓴다.

## 왜 choom 인가
컨테이너의 메모리 cgroup 을 모든 Claude 세션이 같이 쓴다. 벤치가 남은 메모리를 다 쓰면 cgroup OOM killer 가 `oom_score` 로 희생자를 고르는데, Claude 프로세스가 고른 적이 있다(exit 137). Claude 의 점수를 낮추려면 권한(CAP_SYS_RESOURCE)이 필요하지만 자식의 점수를 올리는 것은 권한 없이 되고 exec 를 거쳐 상속된다. 그래서 `choom -n 1000 -- <명령>` 으로 무거운 프로세스 트리를 첫 희생자로 만든다.

## 판정
1. 래퍼를 정한다: `HARNESS_HEAVY_WRAP`(기본 `auto` 는 `choom` 이 PATH 에 있으면 `choom -n 1000 --`). 빈 값이거나 래퍼 프로그램이 없으면 아무것도 막지 않는다.
2. 명령에 위임 드라이버 파일 이름(`delegate.py`, `delegate.sh`; 드라이버가 자기 실행을 choom 으로 감싼다)이 들어 있거나, 무거운 낱말도 시간 재기 호출도 없으면 통과.
3. heredoc 본문을 먼저 버리고(데이터이고, 본문 줄이 구간 머리로 오인되므로) `&&`, `||`, `;`, `|`, 줄바꿈으로 구간을 나눈다. 각 구간의 머리는 `env`, `time`, `nice`, `timeout …`, `VAR=…` 같은 접두를 건너뛴 프로그램이다.
4. 첫 구간이 `git`·`gh` 면 통과(커밋 메시지에 낱말이 흔하다).
   어느 구간의 머리가 래퍼 프로그램이면(경로로 불러도, 이름만 견준다) 이미 감싼 것으로 보고 통과. `choom -n 1000 -p $$; <명령>` 은 셸 자신을 올려 뒤 구간도 덮는다. 래퍼 이름이 글에 있기만 한 것(`echo choom; python3 bench.py`)은 치지 않는다.
5. 한 구간이 실행기를 돌리고 같은 구간에 무거운 낱말이 있으면 거절한다. 낱말이 다른 구간에 있으면 세지 않는다. 다만:
   - 낱말이 든 값을 받은 변수(`F=x/fuzz.luau; luau $F`)는 펼쳐지는 구간에서 낱말로 친다.
   - 낱말이 든 디렉터리로 `cd`·`pushd` 하면, 뒤의 툴킷 실행기(`luau`, `cargo` 등)와 스크립트(`./x`, `*.sh`)에 이어진다. `python3`, `bash` 같은 기본 인터프리터에는 잇지 않는다(집계·편집용이 많다).
   - heredoc 본문에 시간 재기 호출(`os.clock(`, `perf_counter`, `timeit`, `performance.now(`, `hrtime`, `Instant::now`)이 있으면 같은 방식으로 뒤의 툴킷 실행기와 스크립트를 잡는다(`cat > b.luau <<EOF … EOF; luau b.luau`).
6. 못 잡는 것: 인터프리터에 heredoc 으로 직접 먹인 무거운 스크립트.

- 무거운 낱말(대소문자 무시, 앞에 글자가 붙지 않은 것): `bench`, `fuzz`, `perf`·`perform`·`performance`, `stress`, `soak`, `load-test`·`loadtest`, `hyperfine`, 그리고 `HARNESS_HEAVY_KEYWORDS`.
- 실행기: 기본 `bash sh zsh python python3 node hyperfine`, `./x` 꼴 실행과 `*.sh`, 툴킷별 표(luau: `luau lune lute`, web: `npm npx pnpm yarn bun deno vitest`, rust: `cargo`), 그리고 `HARNESS_HEAVY_EXECUTORS`. `HARNESS_TOOLKITS` 가 있으면 그 툴킷 표만 쓴다.

## 거절 메시지
`permissionDecision: "deny"` 와 영어 사유(`<harness-hook name="heavy-proc-guard" level="action">`). 래퍼가 choom 이면 `choom -n 1000 -p $$;` 를 앞에 붙이거나 `choom -n 1000 -- prlimit --data=3221225472 -- <명령>` 으로 감싸라고 안내하고, 오탐이어도 같은 방식으로 감싸면 통과한다고 적는다.

## 설정
harness.env 층의 `HARNESS_HEAVY_WRAP`, `HARNESS_HEAVY_EXECUTORS`, `HARNESS_HEAVY_KEYWORDS`, `HARNESS_TOOLKITS`: 사용자 `~/.claude/harness.env`(`$CLAUDE_CONFIG_DIR` 아래) < 저장소 `.claude/harness.env` < 저장소 `.claude/harness.local.env` < 환경 변수. 읽기는 옆의 `hooks/harness_env.py` 사본(하네스 로더의 사본). `HARNESS_HEAVY_EXECUTORS`, `HARNESS_HEAVY_KEYWORDS` 는 이 훅만 읽어 `heavy-proc-guard.py` 의 `ENV_DEFAULTS` 에 있고, `HARNESS_HEAVY_WRAP`, `HARNESS_TOOLKITS` 는 여러 플러그인이 읽어 로더에 있다. `HARNESS_HEAVY_WRAP` 은 로더의 `USER_ONLY` 라 저장소 층이 바꾸지 못한다(클론한 저장소가 래퍼를 끄거나 다른 프로그램을 쓰게 하지 못하게). 저장소 층은 실행기·키워드를 더할 수 있다. 파일이 없으면 기본값(`auto`)으로 돈다.

## 자기 셸에 걸리는 pgrep -f (`self-match-guard.py`)
Claude Code 는 Bash 명령을 `bash -c '… eval '<명령>' …'` 로 돌려 셸의 argv 에 명령 전체가 들어간다. `pgrep -f` 는 전체 명령줄에 패턴을 맞추고 자기 자신만 빼므로, 명령에 든 패턴은 늘 그 셸에 걸린다. 백그라운드 `until ! pgrep -f X; do sleep 2; done` 이 몇 시간 동안 자기 셸을 기다린 적이 있고, `pkill -f X` 는 자기를 돌리는 셸을 죽일 수 있다.

1. 명령에 `pgrep`·`pkill` 이 없거나 첫 구간이 `git`·`gh` 면 통과. heredoc 본문은 버린다.
2. 구간(heavy-proc-guard 와 같은 나눔에 배경 실행 `&` 를 더함)마다 명령 자리의 `pgrep`·`pkill` 을 찾는다: 구간 머리(`while`, `until`, `if`, `!`, `do`, `sudo`, `timeout …` 같은 앞말 뒤)이거나 `$(…)`·백틱 안. `echo`·`grep` 의 인자는 세지 않는다.
3. 옵션을 읽는다: `-f`/`--full` 이 있고 패턴이 있어야 한다(`-af`, `-fl` 같은 묶음, 값을 받는 옵션, pkill 의 `-9`·`-KILL` 포함). `-v`, `-A`/`--ignore-ancestors` 가 있으면 건너뛴다.
4. 패턴을 정규식으로 읽어(`-i` 는 대소문자 무시, `-x` 는 전체 일치) 명령 글자에 맞으면 자기 일치다. 그래서 대괄호 꼴(`[t]est`)은 같은 글자가 명령 다른 곳에 없는 한 저절로 통과한다. 패턴의 `$VAR` 는 같은 명령의 대입으로 채우고, 모르는 변수면 건너뛴다. Python 이 못 읽는 정규식은 글자 그대로 들어 있는지로 본다.
5. 판정: `while`·`until` 루프의 조건이나 본문 안이면 deny(`level="action"`, 루프가 끝나지 않는 이유와 `pgrep -x <이름>`, 대괄호 꼴, `pgrep -A -f`, run_in_background 로 띄우고 완료 알림을 기다리기). 루프 밖 `pkill -f` 는 warn(자기 셸을 죽여 명령이 끊길 수 있음), `pgrep -f` 는 info. `for` 루프는 대기 루프로 치지 않는다.
6. 못 잡는 것: `bash -c '…'` 따옴표 안의 루프, 따옴표 안의 `;`·`|` 로 구간이 잘못 나뉜 경우(오탐 쪽).

## 디스크와 core dump (`resource-guard.py`)
명령을 막지 않는다. 어떤 예외든 아무것도 내지 않고 exit 0, 하위 프로세스는 띄우지 않는다. 0 아닌 종료로 끝난 Bash 는 PostToolUse 가 아니라 PostToolUseFailure 로 오므로 둘 다 등록한다(크래시한 명령은 늘 후자).

디스크:
1. Pre 와 Post 에서 훅 `cwd` 와 `tempfile.gettempdir()` 의 파일 시스템을 잰다(`st_dev` 로 중복 제거). 여유는 `statvfs` 의 `f_bavail`(권한 없는 사용자가 쓸 수 있는 양), statvfs 가 없는 Windows 는 `shutil.disk_usage`. 마운트 이름은 `st_dev` 가 바뀌기 직전 디렉터리(Windows 는 드라이브 루트).
2. 낮음: 여유가 `PROC_GUARD_DISK_MIN_FREE_GIB`(기본 10) GiB 또는 전체의 `PROC_GUARD_DISK_MIN_FREE_PCT`(기본 5)% 아래.
3. 급감: Post 에서 Pre 의 측정보다 `PROC_GUARD_DISK_DROP_GIB`(기본 2) GiB 넘게 줄었다. Pre 측정은 `tool_use_id` 마다 파일 하나로 두고 Post 가 읽고 지운다.
4. 되풀이 막기: 같은 파일 시스템의 같은 종류는 세션에 한 번. 낮음은 그 뒤 여유가 `DROP_GIB`(최소 0.5) 만큼 더 줄면, 급감은 지난번보다 그만큼 더 크게 줄면 다시 낸다. 여유가 문턱 위로 돌아오면 기록을 지워 다시 떨어질 때 알린다.
5. 알림(`level="warn"`): 마운트, 여유 GiB, 비율과 문턱, 급감량. 사용자에게 한 줄로 알리라고 하고, 급감이면 이 명령이 쓴 폴더를 `du -sh` 로 보라고(다른 세션이 같은 디스크를 쓴다), 낮음이면 이 세션이 만든 필요 없는 큰 파일은 지우는 것을 고려하되 그 밖은 묻고 지우라고 한다.

core dump(Linux 만, `/proc/sys/kernel/core_pattern` 을 읽지 못하면 건너뛴다):
1. Post 에서 mtime 이 Pre 시각(ns) 이후인 파일만 본다. 여유는 없다. 다만 mtime 이 정확히 초 단위인 파일(초만 남기는 파일 시스템)은 Pre 의 초부터 받는다. Pre 기록이 없으면 입력의 `duration_ms` 로 거꾸로 잡고, 그것도 없으면 보지 않는다. 상태 폴더나 그 부모가 내 것이 아니거나 남이 쓸 수 있으면 Pre 기록을 믿을 수 없어 core 를 보지 않는다.
2. 이름: core_pattern 의 파일 이름 부분을 정규식으로(`%p` 같은 숫자 지정자는 숫자, `%e` 같은 것은 아무 글자, `core_uses_pid=1` 이고 `%p` 가 없으면 `.PID` 를 더함), 그리고 늘 `core`, `core.<숫자>`. 일반 파일(심볼릭 링크 아님), 내 uid, ELF 헤더의 `e_type` 이 `ET_CORE`(4)인 것만 센다. 그래서 `src/core` 폴더나 `core.py`, 실행 파일은 걸리지 않는다.
3. 어디를: 늘 Pre 와 Post 의 cwd 맨 위, core_pattern 이 절대 경로면 그 폴더. 크래시 흔적이 있을 때만 cwd 아래를 얕은 것부터 깊이 4 까지 훑는다. 폴더마다 scandir 한 번으로 이름 맞추기와 하위 폴더 모으기를 함께 하고, 본 폴더는 집합으로 거른다. 걷기, stat, ELF 읽기를 합쳐 200 ms 시한 하나다(101,101 폴더 나무에서 0.2 초에 멈춤). 숨은 폴더, `node_modules`, `__pycache__`, 다른 장치(`st_dev` 가 cwd 와 다른 마운트, 멈춘 NFS)에는 들어가지 않는다. 크래시 흔적: PostToolUseFailure 의 `error` 첫 줄 `Exit code N` 에서 N-128 이 SIGQUIT·SIGILL·SIGTRAP·SIGABRT·SIGBUS·SIGFPE·SIGSEGV·SIGSYS, 또는 출력 끝 64 KB 에 `core dumped`, `Segmentation fault`, `SIGSEGV` 꼴, `signal: 11` 꼴(cargo).
4. 알림: 경로, 크기, 64비트 core 면 NT_PRPSINFO 의 프로그램과 인자(못 읽으면 `program unknown`), NT_PRSTATUS 의 신호. Pre 는 권한 확인 전에 돌아 사용자가 고르는 동안의 다른 크래시(언어 서버 등)도 시간 창에 든다. 그래서 둘로 나눈다.
   - `level="action"`: core 의 프로그램 이름(pr_fname, 또는 인자 첫 낱말의 basename)이 명령 글에 있거나(왼쪽 낱말 경계만 본다, pr_fname 이 15자에서 잘리므로), 명령에 크래시 흔적이 있고 프로그램을 못 읽었다. 의도한 크래시(재현, 크래시 시험)이거나 필요 없으면 지우고, 디버깅에 필요할 수 있으면 남기고 경로와 크기를 사용자에게 알리라고 한다.
   - `level="warn"`(디스크 경고와 같은 태그): 그 밖의 모두(프로그램이 명령에 없음, 또는 크래시 흔적 없이 프로그램을 못 읽음). 이 명령의 것이 아닐 수 있다는 관찰만 적고, 남긴 채 경로와 크기를 사용자에게 알리고 사용자가 동의할 때만 지우라고 한다.
   - 알린 파일(경로와 mtime)은 세션 기록에 남겨 겹쳐 돈 명령이 다시 알리지 않는다. 기록의 읽기-고치기-쓰기는 `fcntl.flock`(LOCK_NB 를 10 ms 간격으로 50 번, 못 잡으면 잠금 없이 진행, Windows 는 잠금 없음) 안에서 한다. 측정과 core 찾기는 잠금 밖이다.
5. core_pattern 이 `|` 로 시작하면(systemd-coredump, apport) 파일을 찾지 않는다. 크래시 흔적이 있을 때만 덤프가 그 처리기로 갔다고 알린다(`level="info"`, `coredumpctl list`, `/var/crash`).
6. 못 잡는 것: `run_in_background` 명령(Post 가 실행 직후라 그 뒤의 크래시를 보지 못한다), 깊이 4 아래나 숨은 폴더의 덤프(크래시 흔적이 있어도), core_pattern 이 상대 경로에 폴더를 담은 경우의 그 폴더(깊이 안이면 훑기가 찾는다).

설정(harness.env 층과 `/plugin` 설정, 옵션 키는 이름의 소문자):
- `PROC_GUARD_DISK`, `PROC_GUARD_CORE`: 기본 `on`(`on`, `1`, `true`, `yes` 가 켬). 사용자 전용(`ENV_USER_ONLY`): 기계 전체의 안전망이라 클론한 저장소가 커밋한 harness.env 로 끄지 못한다.
- `PROC_GUARD_DISK_MIN_FREE_GIB`, `PROC_GUARD_DISK_MIN_FREE_PCT`, `PROC_GUARD_DISK_DROP_GIB`: 0 이면 그 검사를 끈다. 저장소 층은 더 엄하게만 바꾼다: 사용자 층(저장소 층 없이 한 번 더 읽은 값)과 비교해 최소 여유는 큰 쪽, 급감은 0 아닌 것 가운데 작은 쪽을 쓴다. 풀 수 있으면 0 으로 꺼진 스위치와 같아지기 때문이다.

상태: `${CLAUDE_PLUGIN_DATA}/resource-guard/`(없으면 `$TMPDIR/claude-qwreey-proc-guard-<uid>/resource-guard/`, Windows 는 uid 대신 사용자 이름). 새로 만드는 폴더는 0700. `pre/<세션 해시>-<tool_use_id>.json`(Pre 시각 `t_ns`, cwd, 측정), `s-<세션 해시>.json`(경고한 값, 알린 core)과 그 잠금 파일 `.lock`. 하루 지난 Pre 파일과 일주일 지난 세션 파일은 Pre 가 지운다.

비용(2026-11-19, 이 기계): 훅 한 번 중앙값 약 31 ms(빈 python 시작 9 ms, heavy-proc-guard 24 ms). 크래시 뒤 훑기는 이 저장소에서 3 ms 안팎을 더한다.

## 테스트
```bash
python3 -I plugins/qwreey-proc-guard/tests/test-heavy-proc-guard.py
python3 -I plugins/qwreey-proc-guard/tests/test-self-match-guard.py
python3 -I plugins/qwreey-proc-guard/tests/test-resource-guard.py
```
`test-resource-guard.py` 는 훅 모듈의 `disk_usage`, `read_core_pattern` 을 바꿔 끼우고 임시 폴더에 ELF core 헤더를 써서 본다. 이 기계의 기존 core 파일은 건드리지 않는다.
