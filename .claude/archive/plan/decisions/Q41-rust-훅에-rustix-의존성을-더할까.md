---
format: 1
title: Rust 훅에 rustix 의존성을 더할까?
description: Rust 훅에 rustix 의존성을 더할까? 답 a) rustix 더함 (feature process, fs)
status: archived; answered a) rustix 더함 (feature process, fs)
id: Q41
urgency: soon
blocks: proc-guard 바이너리(resource-guard)
recommended: a
created: 2026-11-20T03:45:12.554Z
answered: 2026-11-20T04:30:37.558Z
answer: a
---

# Q41. Rust 훅에 rustix 의존성을 더할까?

## 맥락

공통 crate 는 `unsafe_code = "forbid"` 라 libc 를 직접 못 부르고, std 에는 getuid, statvfs 가 없어요.

- 지금: nonce claim 폴더가 내 것인지 보려고 그 안에 시험 파일을 만들어 소유자를 읽고 지움(python 은 `os.getuid()`). 동작은 같지만 우회예요.
- proc-guard 의 resource-guard 는 디스크 여유 공간(statvfs)이 필요해서 옮길 때 어차피 필요해요.
- rustix: 안전한 시스템 호출 래퍼(Bytecode Alliance). Linux 에서 rustix, linux-raw-sys, bitflags 가 더해지고 macOS 는 libc, errno 도. Windows 에서는 쓰지 않음(디스크는 다른 길).

## 선택지

- a) rustix 더함 (feature process, fs)
  getuid 우회를 걷어내고 statvfs 를 안전하게 씀. 널리 쓰이는 crate
- b) libc + 그 파일만 unsafe 허용
  의존성이 더 작음. 대신 unsafe 블록을 직접 관리
- c) 의존성 없이 우회 유지
  statvfs 는 df 를 부르거나 다른 우회가 필요해 비용이 큼

**권장 a) rustix 더함 (feature process, fs)**
resource-guard 를 옮기려면 statvfs 가 필요해서 어차피 들어오고, unsafe 를 이 저장소에 두지 않아도 됨

## 답

a
