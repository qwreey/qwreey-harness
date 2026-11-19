---
format: 1
title: 66 덧붙임. 매번 띄우기, Rust 와 python
description: 훅을 매번 새 프로세스로 띄워도 Rust 는 CPU 0.5~0.6 ms(sh -c 거치면 1.2~1.5 ms), python 은 34 ms; Rust 면 데몬 없이 명령 훅만으로 벤더 중립을 지키며 60~70 배 줄어듦
---

> Snapshot 2026-11-19. May differ from now; check current files and git log before relying on it.

사용자: "어뎁터로는 mod가 맞을 수 있는데 그 백엔드는 좀.. 애초에 난 rust 잘 쓰던 사람이 맞기도 해서" ... "그걸 그냥 맨날 스폰하면 지금이랑 다른게 없고 결국 또 데몬이 가능한 구조를 가야 벤더 중립을 지킬 수 있을텐데".

`rust_server.rs` 에 `once` 모드(표준 입력의 훅 JSON 하나를 처리하고 끝남)를 더해, 같은 검사를 매번 띄워 쟀다(`wait4`, 60번 중앙값).

| 경우 | Rust once, 바로 실행 | Rust once, sh -c | python, 바로 실행 |
|---|---|---|---|
| 조용한 훅 | 0.5 ms | 1.2 ms | 34.1 ms |
| Edit 검사 42 KB | 0.6 ms | 1.5 ms | 34.6 ms |

- `ru_maxrss` 는 python 부모에서 갈라진 크기가 섞여 Rust 도 13 MB 로 나온다. 실제 Rust 상주 크기는 서버 시험의 2 MB 쪽이다.
- 결론: Rust 면 데몬 없이도 훅 비용이 도구 한 번(훅 약 17개)에 10~20 ms 로 준다. 명령 훅만 있는 다른 하네스에서도 같은 바이너리가 돈다. 데몬은 필요해질 때의 선택으로 남긴다.
