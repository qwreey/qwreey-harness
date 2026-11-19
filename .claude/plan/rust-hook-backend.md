---
format: 1
title: 훅 백엔드를 Rust 로 (계획, Q38 b)
description: python 훅(매번 34 ms CPU)을 플러그인별 Rust 바이너리(매번 0.5 ms)로 옮기는 계획; 벤더 중립, 플러그인 독립, 결과 대조, 데몬은 선택; 배포와 Windows 가 열린 문제, debate 뒤 확정
status: active; on hold until the debate settles the open questions
keywords: [rust, hook backend, 훅 백엔드, CPU, daemon, single-flight, parity, 배포]
---

# 훅 백엔드를 Rust 로

Q38 b(사용자): 계획만 먼저 쓰고 debate 로 확정한다.

## 왜
- 비용
  - 훅마다 python 을 새로 띄워 CPU 약 34 ms, 프로세스 14~23 MB 가 든다.
  - 도구 한 번에 Bash 0.44 초, Edit 0.33 초, Read 0.15 초, 사용자 말 0.23 초.
  - 이 호스트는 quad, stl-luau, devplorer, tbox 세션이 함께 돌아 CPU 가 늘 빠듯하다.
- Rust 를 매번 띄우면 0.5~0.6 ms(`.claude/audit/66-hook-server-language/one-shot.md`).
- 유지보수(사용자): "네가 쓴 코드 끔찍히 분석하기 힘듦 ... 타입도 없는 상태라 난 보고서 cfg 가 뭔지 몰라 ... 그걸 다 끌고 와서 파이썬이라도 ... 아에 다시 작성하는거랑 뭐가 다른지 모르겠음".
- 사용자는 Rust 를 잘 쓴다. "툴링이 잡아주는 실수가 줄이는 시행착오도 큰데 ... 컴파일 하는건 종종이고 사용하는건 절대적으로 많은 시간".

## 지킬 것 (이미 정한 원칙)
- 벤더 중립(사용자: "qwreey-harness 는 다른 하네스를 고려할 수 있다는 입장"). 검사는 하네스를 모르는 백엔드에 두고, 하네스마다 어댑터(설정 파일)만 다르다. mod 는 UI(desk)에만 쓴다.
- 플러그인 독립(Q28 a, Q29 a): 플러그인 하나만 설치해도 돈다. 서로 기대지 않는다.
- 규약(qwreey-conventions)과 coderag 는 잇지 않는다(`.claude/base/harness-principles.md`). 같은 Rust 라 짜는 방식만 참고한다.
- 빌드된 바이너리는 GitHub release 로 내고 사용자가 GPG 로 서명한다(같은 원칙 파일).
- 훅은 막지 않는다. 막는 훅(workspace-gate, heavy-proc-guard, auditor-readonly-guard, self-match-guard 의 루프)만 예외이고, 그 동작은 그대로 지킨다.
- 결과가 지금과 같아야 한다. 모델에게 가는 글(HOOK-MESSAGES.md 형식, nonce)과 사용자 줄(systemMessage)이 바이트로 같다.

## 모양
- **워크스페이스:** 이 저장소에 Cargo 워크스페이스 하나.
  - 공통 crate: 훅 입출력 JSON, nonce(`lib/harness_nonce.py` 대응), 설정 층(`home/.claude/lib/harness_env.py`, 플러그인 옵션), compact 회차, 파일 잠금, known_repos.
  - 플러그인마다 crate 하나가 바이너리 하나를 낸다.
  - 공통 코드는 컴파일 때 공유한다. 설치된 바이너리끼리는 서로 기대지 않는다. `lib/` 바이트 사본과 `tools/sync-copies.py` 는 옮긴 만큼 필요 없어진다.
- **실행:** 훅은 명령 훅으로 바이너리를 바로 실행한다(`command` + `args`, 셸 없이). 하위 명령은 `<바이너리> hook <이벤트>`.
  - 같은 바이너리가 사람과 모델이 부르는 명령도 맡는다. 예: `conventions-scan` 은 지금 `conventions-check.py` 의 함수를 불러 쓰므로, 검사를 옮기면 scan 도 같이 옮긴다.
- **데몬(나중, 선택):** 바이너리가 먼저 사용자별 로컬 소켓의 데몬에 묻고, 없으면 혼자 계산한다.
  - 데몬이 없어도 결과와 막는 훅은 늘 맞다. 데몬은 빨라지게만 한다.
  - 데몬은 캐시 목록(경로, 크기, 수정 시각, 검사기 버전, 설정 -> 결과)을 한 벌 쥐고, 같은 키의 계산은 한 번만 한다(single-flight). 계산은 작업 스레드 여럿이 한다.
  - 서브에이전트 둘이 같은 파일의 같은 버전을 동시에 검사하면 계산은 한 번이다. 알림은 요청마다 그 에이전트가 추가한 줄로 걸러 각자 받는다.
  - 운영: 잠금 파일로 하나만 뜨고, 쉬면 꺼지고, 바이너리와 버전이 다르면 다시 띄운다.
- **하네스 어댑터:** Claude Code 는 플러그인 `hooks/hooks.json`. codex, agy 는 그 하네스의 훅 설정(나중, 있으면).

## 옮기는 순서 (매 도구마다 뜨는 것, CPU 큰 것부터)
훅이 쓰는 python(시험 제외, `lib/` 사본 포함) 약 2만 4천 줄. 위임·토론·라이선스의 스킬 스크립트는 훅이 아니라 대상에서 뺀다.

1. **qwreey-proc-guard** (1.6k 줄): Bash 앞에 3개, 뒤에 1개. 작고 막는 훅이 있어 첫 시범으로 알맞다(어댑터, 막기, 시험 대조를 다 거친다).
2. **qwreey-sessions** `hook.py`, `records_read.py` (3.6k 줄 중 훅 부분): 도구 앞뒤마다 45~55 ms. 요약 작업자(`cli.py flush`)는 백그라운드라 나중.
3. **qwreey-advisor** (2.7k 줄): Bash 앞, PostToolBatch, Stop, 사용자 말.
4. **qwreey-conventions** (6.6k 줄): 가장 크다. bash-bypass-reminder, bash_writes, structure-reminder, rules_inject, conventions-check, reuse-check, memory-placement, 그리고 conventions-scan. rules_inject 는 coderag 와 바이트 대조 시험이 있으니 그 시험을 그대로 쓴다.
5. **qwreey-workspace** (2.0k 줄), **qwreey-operator** (1.0k 줄), **q** (5.4k 줄 중 훅), **qwreey-reply-language** (0.9k 줄).
6. 세션 시작에만 도는 것(ambient, drift, stale_worktrees)은 마지막. 자주 돌지 않는다.

## 플러그인 하나를 옮기는 단계
1. crate 를 만들고 훅마다 하위 명령을 짠다.
2. **결과 대조:** 지금의 python 시험(`plugins/<p>/tests/`, `tools/tests/test-hook-replay.py`)을 바이너리에도 돌려 출력이 바이트로 같은지 본다. 시험 실행기가 훅 명령을 바꿔 끼울 수 있게 고친다.
3. `cargo test`, `cargo clippy -D warnings`, `cargo fmt --check` 를 통과한다.
4. `hooks.json` 을 바이너리로 바꾼다. python 파일은 열린 세션이 모두 다시 읽을 때까지 그 자리에 둔다(디렉터리 마켓이라 살아 있는 세션이 옛 경로를 부른다). 지우는 것은 사용자 몫(HUMAN_TODO).
5. `python3 -I tools/usage-report.py --time-hooks` 로 전후를 잰다.

## 열린 문제 (debate 에서 다룰 것)
1. **바이너리 배포:** 설치된 플러그인 폴더에 바이너리가 어떻게 들어가나.
   - (a) 플랫폼별 바이너리를 플러그인 폴더에 커밋(git 기록이 커짐)
   - (b) 처음 실행 때 release 에서 받고 서명 확인(네트워크, 신뢰)
   - (c) 설치 뒤 한 번 돌리는 설치 명령
   - 이 기기에서는 `cargo build` 결과를 `bin/` 에 둔다(gitignore).
2. **Windows:** `hooks.json` 의 `command` 가 `.exe` 를 어떻게 가리키나(실행 형식에서 확장자 생략이 되는지). 실기기 확인이 필요하다(S9, Q19 와 함께).
3. **macOS:** 내려받은 바이너리의 Gatekeeper 격리, 서명과 공증.
4. **바이너리 단위:** 플러그인마다 하나(독립, 크기 x 플러그인 수 x 플랫폼 수) 대 하나에 모두(작지만 독립이 깨짐).
5. **워크스페이스 자리:** 이 저장소 안(정본과 함께) 대 따로 저장소.
6. **이름:** 바이너리와 crate 이름은 사용자가 정한다(제안만).
7. **데몬 시점:** 매번 실행으로 충분한지 실사용에서 보고 정한다.
8. **python 을 남길 곳:** 훅이 아닌 스크립트(세션 요약 작업자, doctor, 위임 드라이버)를 언제 옮기나, 그대로 두나.
9. **옮기는 동안:** 플러그인 하나 안에서 python 과 Rust 가 섞이는 기간의 버전 표시와 설정 키.

## 끝났다고 볼 때
- 매 도구마다 뜨는 훅이 모두 Rust 이고, 도구 한 번의 훅 CPU 가 Bash 기준 30 ms 아래.
- 지금 시험이 바이너리에서 모두 통과하고, 출력이 python 과 바이트로 같다.
- 배포 방법이 정해져 동료 기기(Windows 포함)에서 설치본만으로 돈다.
