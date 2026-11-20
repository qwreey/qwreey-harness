---
format: 1
title: "작업자에게 fd 를 넘기지 않는 방법: close_fds 의존성을 둘까, python 작업자가 시작할 때 닫게 할까?"
description: "작업자에게 fd 를 넘기지 않는 방법: close_fds 의존성을 둘까, python 작업자가 시작할 때 닫게 할까? 답 a) close_fds 유지"
status: archived; answered a) close_fds 유지
id: Q45
urgency: later
blocks: 없음(지금 상태로 동작함)
recommended: a
created: 2026-11-20T08:14:55.301Z
answered: 2026-11-20T08:17:41.449Z
answer: a
---

# Q45. 작업자에게 fd 를 넘기지 않는 방법: close_fds 의존성을 둘까, python 작업자가 시작할 때 닫게 할까?

## 맥락

세션 기록 훅은 요약 작업자(python `cli.py flush`, 몇 분 돎)를 띄워요. python 훅은 `close_fds=True` 로 열린 파일을 넘기지 않는데, Rust 는 넘겨서 파이프나 소켓을 붙잡을 수 있었어요.

- 지금(1af251b): `close_fds` crate(MIT, 0.3.2)로 띄우기 전에 fd 3 이상에 close-on-exec 를 검. 의존성 libc, cfg-if 는 이미 있음. unsafe 없이 하려면 crate 가 필요했어요(rustix 로는 fd 번호에서 핸들을 만들 때 unsafe)
- 대안: python 작업자가 시작하자마자 `os.closerange(3, ...)`. 의존성 없음, python 과 Rust 훅 모두에 같이 듦. 대신 `setsid` 가 python 을 띄우는 그 짧은 사이에는 fd 가 열려 있음

## 선택지

- a) close_fds 유지
  띄우는 순간부터 닫힘, python 훅과 같은 뜻. crate 하나
- b) 작업자가 시작할 때 닫음
  의존성 없음. 바이너리가 조금 작아짐. 짧은 틈은 남음

**권장 a) close_fds 유지**
python 훅과 같은 뜻을 그대로 지키고, 더하는 crate 가 작고 그 의존성은 이미 들어와 있음

## 답

a
