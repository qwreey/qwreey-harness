---
title: "저장소마다 다른 값과 결정 상태"
description: "저장소마다 갈린 const·stylua·러너·검사기·버전 핀·주석 언어·네이밍·에러 형식·객체 모양 값(2026-11-10 스냅숏)과 D-01~D-13 결정 상태(확정/제안), 저장소 규칙이 이긴다는 읽는 법"
keywords:
  - "저장소별 차이"
  - "per-repo overrides"
  - "결정 상태"
  - "decision status"
  - "확정 제안"
  - "D-01"
  - "D-13"
  - "stylua indent"
  - "call_parentheses"
  - "버전 핀"
  - "luau-lsp 핀"
  - "검사 기준"
  - "주석 언어 저장소별"
  - "저장소 규칙 우선"
kind: reference
category: luau/style/overrides
tags: [policy]
last_verified: 2026-11-10
---
# project-overrides — 저장소마다 다른 값과 결정 상태

## 이 파일이 답하는 질문
- 이 저장소의 stylua·`const`·러너·검사기·핀·주석 언어·네이밍은 무엇인가?
- 공통 규칙과 저장소 규칙이 다르면 어느 쪽을 따르나?
- 어느 항목이 사용자 확정이고, 어느 항목이 아직 제안인가?

## 목차
- §1 결정 상태
- §2 갈린 규약 × 저장소 (2026-11-10 스냅숏)
- §3 읽는 법과 갱신 규칙

---

## §1 결정 상태
status: described · 근거: qwreey-harness `.claude/base/decisions/README.md` "사용자 결정 현황 (2026-11-10)"

| ID | 주제 | 상태 | 이 스킬에서 |
|---|---|---|---|
| D-01 | `const` | **확정**: 써도 된다. 한 파일 안에서 섞지 않는다 | 규칙 (`idioms.md` §1) |
| D-02 | stylua | **확정**: 값은 저장소 `stylua.toml`, 공통은 루트 실행·`syntax = "Luau"`·`<<` diff 확인 | 규칙 (`quality.md` §3) |
| D-03 | 러너 | **확정**: `luau` CLI 기본, 필요한 부분만 mock, mock 확인은 Studio MCP, lune 안 씀 | 규칙 (`quality.md` §4) |
| D-04 | 타입 함수 | **확정(수정)**: 사안별 판단(부작용 대 불가피성) | `luau-types` 의 type-functions |
| D-05 | 버전 핀 | **확정**(2026-11-11): 수치에 버전 명시, 핀 값은 저장소 | `quality.md` §6 |
| D-06 | 검사기 | **확정(보완)**: 정확성 게이트는 조건부, DX 확인에는 lsp | 규칙 (`quality.md` §5) |
| D-07 | 끝난 할 일 | **확정**(2026-11-11) | `quality.md` §2 (코드 마커만) |
| D-08 | 주석 언어 | **확정**(2026-11-11) | `quality.md` §1 |
| D-09 | 네이밍 케이싱 | **확정**(2026-11-11): 공통 다섯만 강제, quad·stl 기준은 새 저장소 기본값 | `naming.md` §2–3 |
| D-10 | 에러 | **확정**(2026-11-11, 정정 절 반영: `-O2` 인라인 범위) | `errors.md` §2, §6 |
| D-11 | 객체 모양·필드 읽기 | **확정**(2026-11-11) | `idioms.md` §8, `modules.md` §5 |
| D-12 | require 경로 | **확정**(2026-11-11): `@game/` 금지는 위치가 바뀌는 번들만 | `modules.md` §3 |
| D-13 | 파일 길이·폴더·데이터 | **확정(보완)**: 800/1,500줄 알림만, 이유 기록 시 예외 가능 | `structure.md`, rules `code-structure.md` |

확정 항목은 본문에 `> 정책: 결정(D-xx, 날짜)` 으로 표시한다. 제안 상태가 새로 생기면 `> 정책: 제안(D-xx) — 사용자 확인 전` 으로 표시하고, 결정이 나면 이 표와 해당 절을 함께 고친다.

## §2 갈린 규약 × 저장소 (2026-11-10 스냅숏)
status: described · 근거: `decisions/D-01`…`D-12` 의 §1 표

| 항목(결정) | quad | stl-luau | tbox | table-sim | devplorer | rbvm | moonwave |
|---|---|---|---|---|---|---|---|
| `const`(D-01) | 문서상 채택, 게시 소스는 `local` | 기본 | 기본 | 기본(`const function` 포함) | 기본 | 금지 문구 남음(근거 소멸, 갱신은 rbvm 세션 몫) | 미정 |
| stylua indent / parens(D-02) | 설정 없음(손 포맷, 탭) | Tabs / Always | Spaces / Input | Tabs / Input | Tabs / Input | Spaces / Input | Tabs / Always |
| 러너(D-03) | luau | luau | luau + lute | luau | luau | (테스트 없음) | luau |
| luau / luau-lsp 핀(D-05) | 0.734 / 1.70.1 | 0.742 / 1.70.1 | 0.734 / 1.69.0 | 0.734 / 1.69.0 | 0.734 / 1.69.0 | 없음 / 1.69.0 | 0.734 / 1.69.0 |
| 검사 기준(D-06) | analyze + lsp | analyze | lsp | lsp | lsp | lsp | analyze |
| 끝난 todos(D-07) | 지움 | 지움 | — | 아래로 내림 | 취소선 | 갱신 | 지움 |
| 주석 언어(D-08) | 영어 | 한국어·파일 언어 | 한국어 | 한국어·파일 언어 | 한국어·파일 언어 | 짧게 영어·이유는 한국어 | 파일 언어 |
| 네임스페이스 함수(D-09) | 타입 고유 Pascal / 범용 camel | Pascal | 메서드 camel | camel | 혼합 | Pascal | — |
| 파일 이름(D-09) | Pascal | Pascal | 소문자 | Pascal | Pascal | 소문자 | — |
| 에러 형식(D-10) | 번호 + `Subject: reason (got X)` | `Module: 설명` + raise 헬퍼 | 소문자 시작 | 규칙 없음 | `(ok, err)` 검증 | 규칙 없음 | — |
| 객체 모양(D-11) | 메타테이블 + Pascal 메서드 | 전환 중 | 메타테이블 + camel 메서드, freeze | 모듈 + 닷 함수 | 모듈 + 닷 함수 | 프록시 메타테이블 | — |
| `@game/` require(D-12) | — | — | — | 사용(고정 위치) | 금지(복제 번들) | — | — |

## §3 읽는 법과 갱신 규칙
- 저장소 `.claude/rules/` 나 CLAUDE.md 가 이 표와 다르면 **저장소가 맞다**. 이 표는 2026-11-10 시점의 사진이다.
- 저장소별 override 는 각 저장소의 `.claude/rules/*.md` 에 둔다. 이 스킬은 기본값과 근거만 준다.
- 결정 전 항목은 "현재 실태"만 적고 권고를 섞지 않는다.
- 새 저장소는 이 표의 어느 열도 복사하지 않는다. `naming.md` §3, `idioms.md` §1, `quality.md` §3 의 기본값을 쓴다.
