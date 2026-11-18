---
format: 1
title: "위임 uid 를 저장소별 표 대신 대역 하나(예: 61000-61015)에서 비는 것을 골라 쓰게 바꿀까?"
description: "위임 uid 를 저장소별 표 대신 대역 하나(예: 61000-61015)에서 비는 것을 골라 쓰게 바꿀까? 답 a) 대역 하나, 표 없앰"
status: archived; answered a) 대역 하나, 표 없앰
id: Q31
urgency: soon
blocks: home-sync apply 전 uid 표 경로 설정(HUMAN_TODO)
recommended: a
created: 2026-11-17T23:57:58.707Z
answered: 2026-11-17T23:59:32.202Z
answer: a
---

# Q31. 위임 uid 를 저장소별 표 대신 대역 하나(예: 61000-61015)에서 비는 것을 골라 쓰게 바꿀까?

## 맥락

**지금 uid 표(registry.tsv)가 하는 일**
- 저장소마다 agy·codex 용 비특권 uid 를 고정으로 줌(quad 61000, claude-doctor 61004/codex 61005 ...). 위임은 그 uid 로 돌아서 메인 작업 트리, `.git/objects`, 인증 파일에 쓸 수 없음
- 저장소끼리 uid 를 나누지 않는 이유: 한 저장소의 위임이 다른 저장소의 위임 작업 폴더를 못 고치게
- 다섯째 열 setup: 새 worktree 에서 한 번 도는 명령(quad 의 `pesde install`)
- `register` 가 표에 줄을 더하므로 표는 사용자가 가진 파일이어야 함 -> 지금 옵션 경로를 정해야 하는 이유

**사용자 말**: 위임역은 개발 env 만 있어서 다른 프로젝트에 접근 가능하든 상관없고, 메인 Projects 폴더만 못 만지면 됨

**대역으로 바꾸면**
- 메인 트리 보호는 그대로: uid 가 메인 트리 주인이 아니기만 하면 됨(저장소별 고정과 무관)
- 잃는 것: 위임 작업 폴더끼리의 격리(사용자 위협 모델에서는 필요 없음)
- 표, `register`, 경로 옵션이 사라짐. 대역 크기 = 동시 실행 수(uid 별 잠금은 이미 있음)
- setup 명령은 그 저장소 쪽으로: 저장소 `.claude/harness.env` 의 `HARNESS_DELEGATE_SETUP`(작업 uid 로 worktree 안에서만 돔)
- 남은 작업 폴더의 파일 주인이 실행마다 다를 수 있음: 정리는 root 인 드라이버가 하니 문제없음

## 선택지

- a) 대역 하나, 표 없앰
  옵션 `harness_delegate_uids`(기본 61000-61015, /etc/passwd 와 겹치면 doctor 가 알림). setup 은 저장소 키로. 옛 표는 있으면 setup 만 읽는 호환
- b) 대역 + 저장소별 고정 할당은 자동
  저장소 경로의 해시로 대역 안 uid 를 고정. 작업 폴더끼리 격리는 남지만 해시가 겹치면 공유되고, 표는 없음
- c) 지금 표 유지
  저장소끼리 격리. 대신 표 경로 설정과 register 가 필요

**권장 a) 대역 하나, 표 없앰**
지켜야 할 것(메인 Projects)은 저장소별 표 없이도 지켜지고, 설정할 것이 대역 하나로 줄어 동료에게도 설명이 쉬움. 저장소끼리 격리는 이 위협 모델에서 필요 없음

## 답

a
