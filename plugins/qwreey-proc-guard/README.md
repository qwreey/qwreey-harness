# qwreey-proc-guard

이 플러그인을 켜면 Claude 가 벤치마크, 퍼저, 성능 측정처럼 메모리를 많이 쓸 수 있는 명령을 그냥 돌리려 할 때 한 번 막고, `choom` 으로 감싼 명령으로 다시 치게 한다. 여러 세션이 메모리를 같이 쓰는 Linux 컨테이너에서 무거운 실행이 남은 메모리를 다 먹으면, 커널의 OOM killer 가 엉뚱하게 Claude 프로세스를 죽일 수 있기 때문이다. 감싸 두면 그 실행이 먼저 죽고 Claude 는 산다. `choom` 이 없는 환경(대부분의 개인 PC, macOS, Windows)에서는 이 검사는 아무것도 하지 않는다.

또 하나: Claude 가 `pgrep -f 이름` 이 사라질 때까지 기다리는 루프를 짜면, 그 패턴이 Claude 자신의 셸 명령줄에도 들어 있어 루프가 영영 끝나지 않는다. 이런 루프는 한 번 막고 끝나는 방법을 알려 주며, 루프 밖의 `pgrep -f`·`pkill -f` 는 알림만 준다. 이 검사는 모든 플랫폼에서 돈다.

## 무엇이 달라지나
- `luau bench.luau`, `cargo bench`, `npm run perf` 같은 명령이 한 번 거절되고, Claude 가 감싼 형태로 다시 실행한다. 사람이 터미널에서 직접 치는 명령은 상관없다.
- git 명령, 이미 감싼 명령, 벤치 폴더 안에서 결과를 집계하는 `python3` 같은 명령은 통과한다.
- 낱말로 짐작하는 검사라 가끔 오탐이 있다. 그때도 감싸서 다시 치면 되므로 손해는 재시도 한 번이다.
- `until ! pgrep -f 작업이름; do sleep 2; done` 같은 대기 루프가 거절되고, Claude 가 `pgrep -x`, `[작]업이름` 꼴 패턴, 백그라운드 실행의 완료 알림 같은 방법으로 바꾼다.

## 비용
- 늘 드는 것: 없다. 모델을 부르지 않는 가벼운 훅 하나가 Claude 의 셸 명령마다 돈다.

## 요구 사항
- 무거운 실행 검사: Linux, `choom`(util-linux), `python3`. Windows 에서는 설정과 상관없이 아무것도 막지 않는다.
- `pgrep -f` 검사: `python3` 만.

## 끄기
- `claude plugin disable qwreey-proc-guard@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-proc-guard@claude-doctor-market
```

자세한 동작(판정 규칙, 설정, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
