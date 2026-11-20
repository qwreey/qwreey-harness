---
format: 1
title: 시험 코드 가독성을 readable-code 규약에도 넣을까?
description: 시험 코드 가독성을 readable-code 규약에도 넣을까? 답 a) 규약은 토론 뒤 더하고, 기존 시험은 이식이 끝난 뒤 다듬음
status: archived; answered a) 규약은 토론 뒤 더하고, 기존 시험은 이식이 끝난 뒤 다듬음
id: Q47
urgency: later
blocks: 없음
recommended: a
created: 2026-11-20T08:44:13.553Z
answered: 2026-11-20T08:44:35.714Z
answer: a
---

# Q47. 시험 코드 가독성을 readable-code 규약에도 넣을까?

## 맥락

사용자: "#[cfg(test)] mod tests 부분들이 주석 없이 붙어있고 각 테스트 단위가 뭘 하는지, 그 안에서도 뭘 assert 하는지 코드를 읽지 않으면 모른다"

예: `crates/qwreey-sessions/src/config.rs` 의 시험이 `assert_eq!(config.num(Key::GrowKb), 512.0)` 를 하는데, 512 가 "x" 를 숫자로 못 읽어 기본값으로 돌아간 것이라는 걸 코드를 따라가야 앎.

이미 한 것: 돌고 있는 두 에이전트에게 새 시험은 (1) 시험 함수마다 한 줄 doc 주석, (2) 준비·실행·확인을 빈 줄과 이름표로 나눔, (3) 뻔하지 않은 기대값은 이유를 이름표나 assert 메시지에, 로 쓰라고 전함.

남은 것
- 전역 규약(readable-code)에 시험 한 줄을 더할지. 모든 저장소의 모든 언어에 실리는 글이라 토론을 거쳐 정하는 게 원칙이에요
- 이미 있는 crate 시험(harness-hook, proc-guard, sessions)을 나중에 한 번 다듬을지(동작은 그대로, 시험만)

## 선택지

- a) 규약은 토론 뒤 더하고, 기존 시험은 이식이 끝난 뒤 다듬음
  전역 문구는 토론으로 정하는 원칙을 지키고, 지금 이식과 충돌하지 않음
- b) Rust crate 에만(저장소 CLAUDE.md 나 .claude/rules)
  전역을 건드리지 않고 이 저장소에서만
- c) 지금은 브리프에만 둠
  실사용 뒤에 다시 보기

**권장 a) 규약은 토론 뒤 더하고, 기존 시험은 이식이 끝난 뒤 다듬음**
시험이 안 읽히는 것은 Rust 만의 문제가 아니라 python·luau 시험도 같고, 전역 문구라 토론으로 정하는 게 원칙

## 답

a
