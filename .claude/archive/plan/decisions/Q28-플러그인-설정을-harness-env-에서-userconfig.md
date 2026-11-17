---
format: 1
title: 플러그인마다 독립 패키지로 만들까? (설치본만으로 동작, 설정은 각자 userConfig)
description: 플러그인마다 독립 패키지로 만들까? (설치본만으로 동작, 설정은 각자 userConfig) 답 a) 독립 패키지로
status: archived; answered a) 독립 패키지로
id: Q28
urgency: soon
blocks: 공개 정리, 동료 배포 안내
recommended: a
created: 2026-11-17T04:55:04.261Z
answered: 2026-11-17T05:11:53.075Z
answer: a
---

# Q28. 플러그인마다 독립 패키지로 만들까? (설치본만으로 동작, 설정은 각자 userConfig)

## 맥락

**사용자 방향**: README 하나 보고 필요한 것만 골라 설치. 묶음 플러그인도 겹쳐서 애매함. 지금처럼 저장소에서 바로 싣는 것이 아니라 패키지된 설치본이 실제로 깔리는 구조. DOCTOR_ROOT, WORKSPACE 처럼 클론·프로젝트 위치에 기대는 값은 이상함(Windows 는 문서함, 바탕화면 등 위치가 제각각)

**원칙(안)**: 플러그인은 자기 폴더, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PROJECT_DIR`, 자기 userConfig 만 봄. 저장소 클론 위치나 다른 플러그인에 기대지 않음

**지금 기대는 곳**
- `HARNESS_DOCTOR_ROOT`: q doctor(설치 어긋남 검사, web 툴킷), conventions structure-reminder, home-sync, settings-migrate
- `HARNESS_WORKSPACE`: qwreey-workspace 전체, conventions reuse-check·structure-reminder, q doctor, luau-kb upstream_check → Q29
- `DELEGATE_REGISTRY`, `TOOL_INSTALLS`: delegate. 기본값을 플러그인 안이나 mise 기본 경로로 두고, 바꿀 때만 userConfig

**바뀌는 것**
- 설치 어긋남 검사, home-sync 처럼 저장소를 보는 것은 저자용 도구(`tools/`)로 옮김
- 저자는 이 sandbox 에서 지금처럼 로컬 폴더 마켓(저장소에서 바로 실림)으로 개발. 동료는 GitHub 마켓에서 설치본을 받음. 출시 전에는 설치본으로 시험
- harness.env 는 저장소 층과 튜닝용 선택 파일로만 남음

## 선택지

- a) 독립 패키지로
  위 원칙대로. 사람이 고르는 스위치는 플러그인별 userConfig, 묶음 플러그인 없음
- b) userConfig 만 옮기고 경로 키는 유지
  일이 적음. 대신 클론 위치에 기대는 문제가 남음
- c) 지금대로, 문서만 정리
  할 일이 가장 적음

**권장 a) 독립 패키지로**
골라 설치하는 구조와 위치가 제각각인 Windows 를 함께 해결함. 사람이 만지는 값은 공식 대화상자와 검사를 받음. 저자 개발 방식은 그대로

## 코멘트

- 2026-11-17T04:59:17.365Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침
  사용자: dependencies 로 기반 플러그인을 두는 게 나을지도, q 는 자동 alias 라 의미 없음
- 2026-11-17T05:03:05.701Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b 고침, 권장 이유 고침
  사용자: 기반은 골라 설치를 깨고 무관한 키를 포함, 업데이트도 주입 방지 때문에 곤란할 것
- 2026-11-17T05:07:31.180Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침
  사용자: 묶음도 겹쳐서 애매, README 하나 보고 골라 설치; DOCTOR_ROOT·WORKSPACE 이상함(Windows 위치 제각각); 패키지된 설치본이 깔리는 구조가 맞음

## 답

a
