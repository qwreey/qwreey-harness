# qwreey-proc-guard

이 플러그인을 켜면 Claude 가 벤치마크, 퍼저, 성능 측정처럼 메모리를 많이 쓸 수 있는 명령을 그냥 돌리려 할 때 한 번 막고, `choom` 으로 감싼 명령으로 다시 치게 한다. 여러 세션이 메모리를 같이 쓰는 Linux 컨테이너에서 무거운 실행이 남은 메모리를 다 먹으면, 커널의 OOM killer 가 엉뚱하게 Claude 프로세스를 죽일 수 있기 때문이다. 감싸 두면 그 실행이 먼저 죽고 Claude 는 산다. `choom` 이 없는 환경(대부분의 개인 PC, macOS, Windows)에서는 이 검사는 아무것도 하지 않는다.

또 하나: Claude 가 `pgrep -f 이름` 이 사라질 때까지 기다리는 루프를 짜면, 그 패턴이 Claude 자신의 셸 명령줄에도 들어 있어 루프가 영영 끝나지 않는다. 이런 루프는 한 번 막고 끝나는 방법을 알려 주며, 루프 밖의 `pgrep -f`·`pkill -f` 는 알림만 준다. 이 검사는 모든 플랫폼에서 돈다.

마지막으로 디스크와 core dump 를 지켜본다. Claude 가 셸 명령을 돌릴 때마다 앞뒤로 디스크 여유 공간을 재어, 모자라거나 명령 하나 동안 크게 줄었으면 Claude 가 한 줄로 알려 준다. 프로그램이 죽으며 core dump 파일(수 GiB 가 되기도 한다)을 남기면, 의도한 크래시였거나 필요 없는 덤프는 Claude 가 지우고, 디버깅에 필요해 보이면 남긴 채 경로와 크기를 알려 준다. 이 검사는 아무것도 막지 않는다.

## 무엇이 달라지나
- `luau bench.luau`, `cargo bench`, `npm run perf` 같은 명령이 한 번 거절되고, Claude 가 감싼 형태로 다시 실행한다. 사람이 터미널에서 직접 치는 명령은 상관없다.
- git 명령, 이미 감싼 명령, 벤치 폴더 안에서 결과를 집계하는 `python3` 같은 명령은 통과한다.
- 낱말로 짐작하는 검사라 가끔 오탐이 있다. 그때도 감싸서 다시 치면 되므로 손해는 재시도 한 번이다.
- `until ! pgrep -f 작업이름; do sleep 2; done` 같은 대기 루프가 거절되고, Claude 가 `pgrep -x`, `[작]업이름` 꼴 패턴, 백그라운드 실행의 완료 알림 같은 방법으로 바꾼다.
- 디스크 여유 공간이 10 GiB 또는 5% 아래로 내려가거나 명령 하나 동안 2 GiB 넘게 줄면, Claude 가 어느 디스크에 몇 GiB 남았는지 한 줄로 알려 준다. 같은 경고는 세션에 한 번이고 더 나빠졌을 때만 다시 나온다.
- 명령이 도는 동안 생긴 `core`, `core.<번호>` 같은 덤프 파일을 Claude 가 정리하거나(의도한 크래시, 필요 없는 덤프) 경로와 크기를 알려 준다(디버깅에 필요해 보일 때). 지우는 것은 죽은 프로그램이 그 명령에 나오는 덤프뿐이다. 다른 프로그램(언어 서버 등)의 덤프는 지우지 않고 경로와 크기만 알려 주며, 명령 전부터 있던 덤프는 보지 않는다.

## 비용
- 늘 드는 것: 모델 호출은 없다. 가벼운 훅이 Claude 의 셸 명령마다 돈다: 명령 전에 셋, 명령 뒤에 하나(0.4.0 부터 Rust 바이너리라 각 1 ms 안팎, python 이었을 때는 각 30 ms 안팎). 디스크 측정은 statvfs 몇 번이다.
- 크래시가 보인 명령 뒤에만 작업 폴더를 깊이 4 까지 훑는다(같은 디스크 안, 폴더가 아주 많아도 0.2 초에서 멈춘다).

## 요구 사항
- 훅은 Rust 바이너리 `native/qwreey-proc-guard` 를 부른다. 지금은 저장소에서 `cargo build --release -p qwreey-proc-guard` 로 만들어 그 자리에 복사해야 하고, 바이너리가 없으면 훅이 아무것도 하지 않는다(막지 않는 오류). 배포 방법은 정하는 중이다.
- 무거운 실행 검사: Linux, `choom`(util-linux). Windows 에서는 설정과 상관없이 아무것도 막지 않는다.
- `pgrep -f` 검사, 디스크 경고: 바이너리만. Windows 에서는 디스크 경고가 아직 없다.
- core dump 알림: Linux(`/proc/sys/kernel/core_pattern`). 덤프가 systemd-coredump·apport 같은 처리기로 가는 기계에서는 파일을 찾지 않고 어디로 갔는지만 알린다.

## 끄기
- 플러그인 전체: `claude plugin disable qwreey-proc-guard@qwreey-harness` (제거는 `uninstall`).
- 디스크 경고나 core dump 알림만: `/plugin` 의 이 플러그인 설정에서 끄거나 문턱을 바꾼다(`~/.claude/harness.env` 의 `PROC_GUARD_DISK=off`, `PROC_GUARD_CORE=off` 도 된다). 저장소 설정으로는 끌 수 없다.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-proc-guard@qwreey-harness
```

자세한 동작(판정 규칙, 설정, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
