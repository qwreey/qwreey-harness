---
format: 1
title: "다음 이식 순서: conventions 2단계와 workspace 를 나란히 할까?"
description: "다음 이식 순서: conventions 2단계와 workspace 를 나란히 할까? 답 a) conventions 2단계와 workspace 를 나란히(worktree 에이전트 둘, opus), 끝나면 operator·q"
status: archived; answered a) conventions 2단계와 workspace 를 나란히(worktree 에이전트 둘, opus), 끝나면 operator·q
id: Q52
urgency: soon
blocks: 다음 이식 시작
recommended: a
created: 2026-11-22T02:34:41.396Z
answered: 2026-11-22T02:35:40.271Z
answer: a
---

# Q52. 다음 이식 순서: conventions 2단계와 workspace 를 나란히 할까?

## 맥락

재기 결과(reload 뒤, p50). 이제 도구마다 남은 python 이 거의 전부다.

- **conventions 2단계**: bash-bypass-reminder 32 ms(Bash 앞), bash_writes 29 ms(Bash 뒤), rules_inject 30 ms(Read·Edit 뒤)
- **workspace**: workspace_gate 20 ms(Bash·Read·Edit 앞, 막는 훅, 모든 OS), sibling_notice 33 ms(Edit 뒤)
- **operator delegate-nudge** 25~29 ms, **q subagent-slots** 14 ms: 도구마다 뒤에
- Rust 로 바꾼 훅은 하나에 2~4 ms

도구 한 번 합: Bash 앞 83 ms·뒤 93 ms, Read 뒤 89 ms, Edit 뒤 147 ms. 그 대부분이 위 python 이다.

- rules_inject 는 coderag 와 바이트 대조 시험이 이미 있다.
- 메모리: 지금 anon 2.9 GiB. 에이전트 둘이 -j 2 로 빌드하면 감당된다. 셋은 빠듯하다.

## 선택지

- a) conventions 2단계와 workspace 를 나란히(worktree 에이전트 둘, opus), 끝나면 operator·q
  가장 큰 두 덩이를 동시에. advisor·reply-language 때와 같은 방식
- b) 셋(conventions 2단계, workspace, operator+q)을 한꺼번에
  가장 빠르지만 메모리·CPU 가 빠듯하고 검토가 한꺼번에 몰린다
- c) conventions 2단계만 먼저
  하나씩 보며 가기. 느리다

**권장 a) conventions 2단계와 workspace 를 나란히(worktree 에이전트 둘, opus), 끝나면 operator·q**
남은 비용의 대부분이 이 두 플러그인에 있고, 메모리 안에서 둘은 안전하게 돈다

## 답

a
