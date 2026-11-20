---
format: 1
title: Rust 훅 0단계의 임시 이름을 그대로 둘까?
description: Rust 훅 0단계의 임시 이름을 그대로 둘까? 답 a) 그대로 둠
status: archived; answered a) 그대로 둠
id: Q40
urgency: soon
blocks: proc-guard 바이너리 이름
recommended: a
created: 2026-11-20T03:35:02.102Z
answered: 2026-11-20T04:30:37.558Z
answer: a
---

# Q40. Rust 훅 0단계의 임시 이름을 그대로 둘까?

## 맥락

에이전트가 임시로 붙인 이름이에요. 이미 커밋됐지만(761224d, 9dbb5e5) 지금 바꾸면 비용이 작아요.

- `crates/`: 저장소 맨 위 Rust 소스 폴더. 루트 `Cargo.toml` 이 `crates/*` 를 묶음
- `harness-hook`: 공통 crate(훅 입출력, 태그, nonce, 설정 층). 플러그인 바이너리가 컴파일 때만 씀
- `native/`: 플러그인 안 바이너리 자리(gitignore). 맨 위 `bin/` 은 PATH 에 오르고 claude.ai 가 거부해서 못 씀
- 바이너리 하위 명령 꼴: `<바이너리> hook <이벤트>`
- 플러그인 crate/바이너리 이름: 플러그인 이름 그대로(예: `qwreey-proc-guard`) 안
- 시험 도구: `tools/tests/hook-parity.py`(python 과 바이너리 출력 대조), `--identity`, `--from-transcripts`

## 선택지

- a) 그대로 둠
  Rust 관례(crates/, kebab-case)와 맞고, 플러그인 이름을 바이너리 이름으로 쓰면 어디서 왔는지 바로 보임
- b) 일부 바꿈 (코멘트로 적어 주세요)
  예: crate 이름을 qwreey-hook 처럼 저장소 이름과 맞추기, native/ 대신 다른 이름

**권장 a) 그대로 둠**
관례에 맞고 아직 쓰는 곳이 적어 나중에 바꿔도 되지만, proc-guard 바이너리를 만들기 전에 정하면 이름 바꾸기가 한 번으로 끝남

## 답

a
