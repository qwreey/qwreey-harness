# qwreey-proc-guard

공유 메모리 cgroup 에서 벤치·퍼저·성능 실측이 남은 메모리를 다 쓰면 OOM killer 가 Claude 프로세스를 죽일 수 있다(quad 2026-09-28, exit 137). 이 플러그인의 PreToolUse(Bash) 훅은 그런 실행을 `choom -n 1000 --` 로 감싸지 않았으면 deny(level=action)하고, 다시 칠 명령을 알려 준다.

Linux 전용이라 따로 뒀다. Windows·macOS 에서는 이 플러그인을 끄면 된다. 래퍼 프로그램(choom)이 없으면 훅이 아무것도 막지 않는다.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 훅 | `hooks/heavy-proc-guard.py` | PreToolUse(Bash). 무거운 낱말(bench, fuzz, perf, stress 등)이 있고 어느 구간이 실행기(luau, bash, python, node, ./x.sh 등)를 돌리면 deny. git·gh 명령과 이미 감싼 명령은 통과 |

설정(`~/.claude/harness.env`, 선택. `lib/harness_env.py` 가 없으면 기본값): `HARNESS_HEAVY_WRAP`(기본 auto: choom 이 있으면 `choom -n 1000 --`, 없으면 끔; 빈 값이면 끔), `HARNESS_HEAVY_EXECUTORS`, `HARNESS_HEAVY_KEYWORDS`, `HARNESS_TOOLKITS`.

## 테스트
`python3 -I tests/test-heavy-proc-guard.py`
