---
format: 1
title: conventions 2단계와 workspace 의 hooks.json 도 바이너리로 켤까?
description: conventions 2단계와 workspace 의 hooks.json 도 바이너리로 켤까? 답 a) 둘 다 지금 켬다
status: archived; answered a) 둘 다 지금 켬다
id: Q54
urgency: soon
blocks: hooks.json 전환, 그 뒤 operator·q 이식
recommended: a
created: 2026-11-22T03:40:44.020Z
answered: 2026-11-22T03:42:23.861Z
answer: a
---

# Q54. conventions 2단계와 workspace 의 hooks.json 도 바이너리로 켤까?

## 맥락

둘 다 main 에 합쳤고(86dcbb6, 99d7d9e), 검토와 시험이 끝났다.

- **대조**: conventions 재생 123·실제 입력 926, workspace 재생 88·실제 입력 330, 모두 같음. 플러그인 시험 python 판·바이너리 판 모두 통과.
- **검토 결과**
  - workspace: python 은 막는데 Rust 가 조용하던 자리 하나(경로가 목록일 때)를 고침(99d7d9e).
  - conventions: 바로 고칠 것 없음. python 에도 있던 결함 하나(저장소에 UTF-8 이 아닌 파일 이름이 있으면 Bash 쓰기 검사가 그 저장소에서 꺼짐)는 양쪽에서 같이 고칠 거리로 남김.
- **켜면**: Bash 한 번 훅 CPU 가 약 60 ms 줄고, Read·Edit 도 30~50 ms 준다. workspace-gate 는 막는 훅이라 바이너리가 없으면 막지 않는다(proc-guard 와 같다).

## 선택지

- a) 둘 다 지금 켬다
  대조 0, 검토 반영 끝. 앞의 다섯 플러그인과 같은 기준
- b) conventions 만 켜고 workspace(막는 훅)는 남김 일을 고친 뒤
  막는 훅은 한 번 더 지켜본 뒤에
- c) 둘 다 남김 일을 고친 뒤
  가장 조심스럽지만 남은 일은 드문 입력이다

**권장 a) 둘 다 지금 켬다**
남은 일은 python 에도 있던 드문 입력의 결함이라 켜는 것과 별개로 고칠 수 있다

## 답

a
