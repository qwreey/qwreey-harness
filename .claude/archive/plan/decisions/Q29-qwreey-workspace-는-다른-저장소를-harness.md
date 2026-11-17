---
format: 1
title: qwreey-workspace 는 다른 저장소를 HARNESS_WORKSPACE 없이 어떻게 찾을까?
description: qwreey-workspace 는 다른 저장소를 HARNESS_WORKSPACE 없이 어떻게 찾을까? 답 a) 자동 수집 + userConfig 로 더하기·빼기
status: archived; answered a) 자동 수집 + userConfig 로 더하기·빼기
id: Q29
urgency: soon
blocks: Q28 a 를 할 때 qwreey-workspace 작업
recommended: a
created: 2026-11-17T05:07:46.331Z
answered: 2026-11-17T05:11:53.075Z
answer: a
---

# Q29. qwreey-workspace 는 다른 저장소를 HARNESS_WORKSPACE 없이 어떻게 찾을까?

## 맥락

- 지금은 한 부모 폴더(`HARNESS_WORKSPACE`) 아래의 형제 저장소를 봄. Windows 처럼 프로젝트가 문서함·바탕화면 등에 흩어져 있으면 맞지 않음
- 쓰기 게이트는 목록이 없어도 됨: 현재 프로젝트 밖의 git 저장소면 '다른 저장소'로 보면 됨
- 목록이 필요한 곳은 저장소 지도(`map.py`), stale worktree 알림, conventions 의 형제 경로 알림
- Claude Code 는 `~/.claude/projects/*/*.jsonl` 에 세션마다 `cwd` 를 남김. 쓴 적 있는 저장소를 설정 없이 모을 수 있음

## 선택지

- a) 자동 수집 + userConfig 로 더하기·빼기
  설정 없이 동작하고, Claude 를 열어 본 적 없는 저장소나 빼고 싶은 곳만 사용자가 적음
- b) 자동 수집만
  가장 단순함. 한 번도 열지 않은 저장소는 목록에서 빠짐
- c) userConfig 로 루트 목록만
  명시적. 대신 사용자가 경로를 입력해야 하고 비어 있으면 지도가 빈약함

**권장 a) 자동 수집 + userConfig 로 더하기·빼기**
대부분은 손댈 것이 없고 예외만 대화상자에서 고침. 위치가 제각각이어도 동작함

## 답

a
