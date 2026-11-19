---
format: 1
title: 66. http 훅 서버, python 과 Rust 비교 (최소 시험)
description: 매번 python 을 띄우는 지금 방식(요청당 CPU 34 ms) 대비 상주 http 서버는 python 0.06~0.7 ms, Rust 0.01~0.13 ms; 띄우는 비용이 거의 전부라 컴파일 언어의 이득은 도구 한 번에 약 1~2 ms 로 무의미, Rust 는 거름
---

> Snapshot 2026-11-19. May differ from now; check current files and git log before relying on it.

질문(사용자): "rust안과 python안, 둘 다 http 서버를 둔다고 가정하면 얼마나 다른가? 컴파일 언어를 택할 가치를 볼 수 있는가, 만일 유의미하지 않다면 여기서 거르자."

## 방법
- 두 서버가 같은 두 경로를 받는다. `/quiet` 는 JSON 만 읽고 빈 응답(대부분의 훅), `/edit` 는 편집한 파일(quad `quad-base/test/mock.luau`, 42 KB)을 읽어 줄마다 `--` 주석을 찾고 세 가지(기록 표지, 비ASCII, TODO)를 본다.
- python: 표준 라이브러리 `ThreadingHTTPServer`, 정규식 3개([py_server.py](py_server.py)). Rust: std 의 `TcpListener`, 연결마다 스레드, `serde_json`, 정규식 없이 문자열로 같은 검사([rust_server.rs](rust_server.rs), [rust_Cargo.toml](rust_Cargo.toml)).
- 한 연결(keep-alive)로 순서대로 보내고, 서버 프로세스의 CPU 를 `/proc/<pid>/stat` 로 잰다. 비교 기준은 같은 검사를 하는 스크립트를 요청마다 `python3 -I -X utf8` 로 띄우는 지금 방식(`wait4` 로 잼).
- 다시 재기: 이 폴더에서 `cargo build --release` 로 Rust 서버를 만들고(경로는 [bench.py](bench.py) 안), `choom -n 1000 -p $$; python3 -I bench.py`.
- TCP_NODELAY 를 켜고 응답을 한 번에 쓴다. 켜기 전에는 응답을 나눠 써서 Nagle 과 지연 ACK 로 지연이 41 ms 씩 나왔다(CPU 숫자는 같았다).

## 결과 (요청당 서버 CPU, p50 지연)
| 경우 | python 서버 | Rust 서버 | 지금(매번 띄우기) |
|---|---|---|---|
| 조용한 훅, 입력 0.2 KB | 57 us, 87 us | 13 us, 44 us | 33,786 us |
| 조용한 훅, 입력 35 KB | 140 us, 175 us | 120 us, 168 us | - |
| Edit 검사, 파일 42 KB | 670 us, 713 us | 130 us, 171 us | 34,912 us |
| 상주 메모리 | 19 MB | 2 MB | - |

## 결론
- 비용은 거의 전부 프로세스를 띄우는 데서 나온다. 상주 서버로 바꾸면 python 그대로 50~600 배 준다.
- 도구 한 번(훅 약 17개)을 서버가 받으면 python 약 1~3 ms, Rust 약 0.5 ms. 지금 약 440 ms 대비 둘 다 0 에 가깝다. 컴파일 언어를 택할 이유가 되지 않아 거른다.
- python 서버에서도 무거운 검사는 큰 입력에서 몇 ms 가 될 수 있다. 알고리즘과(54a13a3 의 렉서처럼) 메모리 캐시로 다룬다.
- 남은 설계 거리는 언어가 아니라 데몬 운영이다: 켜고 끄기, 포트와 인증, 코드를 고쳤을 때 다시 읽기, 데몬이 죽었을 때 막는 훅의 동작.
