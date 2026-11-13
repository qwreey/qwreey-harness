---
format: 1
title: 49. 기록 description 요구 토론 종합
description: 새 기록은 스냅샷까지 description(결론 한 줄)을 쓸 때 달고, 새 스냅샷 Write 에 없으면 알림, 날짜·범위 머리말이나 제목 반복은 Warn. 옛 기록은 채우지 않고 읽는 쪽에서 머리말을 건너뛴다
---
# 49. 기록 description 요구 토론 종합

> Snapshot 2026-11-13. P(최소, 글쓴이 비용)와 Q(넓게, 강제)의 1라운드 의견서를 메인 세션이 종합했다. 사용자 "확인. 답을 기다리는 부분은 생각대로 가면 될듯 함".

## 계기
coderag 검색 둘째 줄 실측(coderag `.claude/research/search-summary-line.md`): 둘째 줄이 고르기 정확도를 올리지만(hit@1 11/16 -> 14/16) claude-doctor 결과의 19-22% 가 날짜 머리말 잡음. 사용자: 무엇을 언제 찾을지와 요약은 쓰는 모델만 알므로 "글을 쓰게 될 때 summary/description 을 쓰도록 더 요구하는게 맞긴하겠다".

## 두 쪽이 함께 확인한 사실
- coderag `.claude/` 는 29/29 가 description 을 가졌고 잡음 0. 쓸 때 요구하면 지켜진다.
- claude-doctor audit 은 101 중 97 에 frontmatter 가 없고, 48 이 날짜·범위 줄로 시작한다. base/decisions 13 도 frontmatter 가 없다(6 이 `> 작성 2026-11-10.`).
- 규약 자체가 잡음을 만든다: 스킬이 스냅샷 첫 줄로 `> Snapshot <날짜>. May differ…` 를 요구하고 frontmatter 는 요구하지 않아, 대체 요약이 그 줄을 집는다.
- 쓸 때 검사의 빈틈: post-edit 훅은 스냅샷을 검사하지 않고, frontmatter 없음은 새 living 기록에만 Info 로 알린다.
- 세션 반입본의 description 은 마지막 구간의 것이라 제목과 어긋난다(`plugins/q/scripts/sllib/store.py:245`).

## 정한 것
1. 읽는 쪽: 대체 요약의 날짜·Snapshot·작성·범위 머리말을 건너뛴다(coderag `summary_line.rs`, 잡음 22% -> 7%). 직접 쓴 `summary:`·`description:` 은 그대로.
2. rule 한 줄: 새 기록은 스냅샷 포함 frontmatter `format`, `title`, `description`(검색이 보이는 줄: 결론, 날짜·범위 아님), living 은 `status` 더. 좋은 예·나쁜 예는 스킬에.
3. 쓸 때 lint: 새 스냅샷을 Write 로 만들 때 description 이 없으면 한 번 알림. Edit 은 알리지 않는다(스냅샷을 고치라고 재촉하지 않게). `sessions/` 는 도구 몫. description 이 날짜·범위 머리말로 시작하거나 정규화한 제목과 같으면 Warn. 길이 하한은 두지 않는다.
4. 절 `summary:` 기준(1.5k 넘고 표·코드·목록으로 시작)은 그대로. 절 요약 141건이 정상이었다.
5. 옛 기록(audit, handoff, archive, 반입한 sessions)은 채우지 않는다. 살아 있는 옛 기록은 사용자가 `docs-backfill` 을 부를 때만.
6. 세션 반입 description 은 세션 전체를 말하게 고친다(세션 기록 분절 작업 때).

## 받아들이지 않은 것
- Q: 긴 절마다 `summary:` 강제, 15자 하한, 제목 80% 겹침 경고. 오탐 대비 이득이 작다(Q 도 양보 가능으로 둠).
- P: handoff 면제는 받지 않았다. 문구가 단순해지고 비용이 작다.
