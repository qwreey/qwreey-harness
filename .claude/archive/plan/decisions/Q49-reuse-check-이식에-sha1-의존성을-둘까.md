---
format: 1
title: reuse-check 이식에 sha1 의존성을 둘까?
description: reuse-check 이식에 sha1 의존성을 둘까? 답 a) sha1 둠
status: archived; answered a) sha1 둠
id: Q49
urgency: soon
blocks: conventions hooks.json 전환
recommended: a
created: 2026-11-20T09:28:40.472Z
answered: 2026-11-20T09:32:50.080Z
answer: a
---

# Q49. reuse-check 이식에 sha1 의존성을 둘까?

## 맥락

reuse-check 는 색인 파일 이름과 shadow 기록 id 를 SHA-1 로 만들어요. python 과 같은 파일을 같이 쓰려면 같은 해시가 필요해요(python 과 Rust 가 번갈아 돌아도 색인을 공유).

- sha1: RustCrypto, 이미 승인한 sha2 와 같은 가족, 공유 부품(digest 0.11)이 같아 crate 하나만 더함. 크기 영향은 아직 안 잼(작을 것으로 봄)
- 대안: SHA-1 직접 구현(약 100줄, 시험 벡터로 확인) 또는 색인 이름을 python 과 공유하지 않음(번갈아 돌 때 색인을 두 벌 만듦)

## 선택지

- a) sha1 둠
  sha2 와 같은 가족, crate 하나
- b) 직접 구현
  의존성 없음, 대신 암호 코드를 우리가 유지

**권장 a) sha1 둠**
해시는 직접 짤 이유가 없고, 이미 쓰는 sha2 와 부품을 나눠 써서 비용이 거의 없음

## 답

a
