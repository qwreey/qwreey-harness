# qwreey-proc-guard 동작 상세

구성: PreToolUse(Bash) 훅 하나(`hooks/heavy-proc-guard.py`). 스킬, 규약 주입, 상태 파일은 없다.

## 왜 choom 인가
컨테이너의 메모리 cgroup 을 모든 Claude 세션이 같이 쓴다. 벤치가 남은 메모리를 다 쓰면 cgroup OOM killer 가 `oom_score` 로 희생자를 고르는데, Claude 프로세스가 고른 적이 있다(exit 137). Claude 의 점수를 낮추려면 권한(CAP_SYS_RESOURCE)이 필요하지만 자식의 점수를 올리는 것은 권한 없이 되고 exec 를 거쳐 상속된다. 그래서 `choom -n 1000 -- <명령>` 으로 무거운 프로세스 트리를 첫 희생자로 만든다.

## 판정
1. 래퍼를 정한다: `HARNESS_HEAVY_WRAP`(기본 `auto` 는 `choom` 이 PATH 에 있으면 `choom -n 1000 --`). 빈 값이거나 래퍼 프로그램이 없으면 아무것도 막지 않는다.
2. 명령에 래퍼 이름이나 위임 드라이버 파일 이름(`delegate.py`, `delegate.sh`; 드라이버가 자기 실행을 choom 으로 감싼다)이 들어 있거나, 무거운 낱말도 시간 재기 호출도 없으면 통과.
3. heredoc 본문을 먼저 버리고(데이터이고, 본문 줄이 구간 머리로 오인되므로) `&&`, `||`, `;`, `|`, 줄바꿈으로 구간을 나눈다. 각 구간의 머리는 `env`, `time`, `nice`, `timeout …`, `VAR=…` 같은 접두를 건너뛴 프로그램이다.
4. 첫 구간이 `git`·`gh` 면 통과(커밋 메시지에 낱말이 흔하다).
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

## 테스트
```bash
python3 -I plugins/qwreey-proc-guard/tests/test-heavy-proc-guard.py
```
