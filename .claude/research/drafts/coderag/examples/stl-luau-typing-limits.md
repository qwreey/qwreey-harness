---
title: Luau 타입 한계와 stl-luau 의 현황
description: stl-luau 고유의 타입 한계 현황(일반 사실은 luau-kb luau-types). 지금 유효 — f<<T>> 가 콜백 주석까지 없앰, 유니온 원소, 구멍 규약, 생략 인자 결함, 함수 묶음 계약 추론, 같은 별칭이어야 풀리는 유니온
keywords: [typing-limits, 타입 한계, spikes/54, spikes/77, 질문 AB, 질문 BE, 질문 BH, ArrData, 함수 묶음 계약, MapMarkerMut]
kind: base
category: luau/types
tags: [stl-luau, containers, traits]
last_verified: 2026-11-06
last_confirmed: [luau 0.742]
review_after: 2027-01-06
see: [doc SKILL in "pack:luau-kb/luau-types"]
---
<!--
예시 설명 (coderag tech-design §17 — 실제 파일에는 넣지 않는다)
- 원본: stl-luau/.claude/base/typing-limits.md (481줄, 2026-11-06 커밋 2bc4a09). 이것은 **발췌**다.
  절 다섯 개만 옮겼고 본문은 앞 몇 줄만 남긴 뒤 "(…)" 로 줄였다. 원본은 고치지 않았다.
- 보여 주려는 것
  1. 프로젝트 기록이 pack 어휘(category: luau/types…)를 빌려 쓴다 — `coderag search --category luau/types/unions`
     한 번에 luau-kb reference 와 이 기록이 함께 나온다(§13.4, §16: project 문서의 어휘 밖 범주는 경고만).
  2. 원본 머리의 "⭐ 2026-10-01 M0 이후 읽는 법 — 아래 중 …는 역사입니다" 같은 손 배너를 **절 단위 status** 가 대신한다.
     archived 절은 search/list 에서 빠지고(get 으로는 나옴), 배너를 읽지 않은 에이전트도 역사를 현재로 오인하지 않는다.
  3. luau-kb 로 옮겨 간 일반 원칙 절은 `status: superseded` + pack ID 로 갈음 — 검색은 pack 쪽 원본을 보여 준다.
  4. 날짜·이모지가 든 제목(`⭐ [2026-08-31 실측] …`)은 `id:` 로 절 ID 를 고정한다. 날짜는 `since:` 로 옮길 수 있다.
  5. 이 문서의 last_confirmed 가 luau 0.742 라서, 핀을 0.746 으로 올리면 stale 이 "버전 낡음"을 알린다(§18.4).
  6. 이 문서는 추정 ~17k 토큰이라 자동으로 "절 단위"다(§21.3). 표로 시작하는 긴 절에는 `summary:` 를 둔다(§21.4, union-same-alias 절).
  7. `see:` 의 pack 절 ID(`…variance.3-값-팬텀의-nil-구멍`)는 luau-kb 가 그 절에 `id:` 를 고정하지 않았을 때의 모양이다.
     제목의 "§3" 이 slug 에 "3-" 으로 남아 번호를 바꾸면 깨진다 — pack 쪽 `id:` 고정이 필요한 이유(§14).
-->
# Luau 타입 한계와 이 저장소의 현황

quad 의 같은 이름 문서(`/code/Projects/quad/.claude/base/typing-limits.md`)가
**훨씬 방대하고 실측이 잘 돼 있습니다 — 타입 문제로 막히면 거기부터
읽으세요.** 이 문서는 stl-luau 고유의 현황만 기록합니다.

(… 원본의 "⭐ 읽는 법" 배너 블록 — 절 status 로 옮기면 지금 유효한 것의 요약 한 문단만 남긴다 …)

## 원칙 (quad 에서 가져옴)
id: principles · status: superseded · superseded_by: doc SKILL in "pack:luau-kb/luau-types"

- **⭐ Luau 한계를 우회하려고 API/타입을 비틀지 마세요.** (…)
- **⭐ "진단 0건" 을 신뢰하지 마세요.** (…)
- **추론만으로 "된다/안 된다" 를 결론짓지 마세요.** (…)

## ⭐ [2026-08-31 실측] 체커: `luau-analyze` (luau-lsp 아님)
id: checker-luau-analyze · since: 2026-08-31 · evidence: verified · category: luau/verify/checkers · see: doc references.checkers in "pack:luau-kb/luau-verify"

**결론부터**: 타입 검사는 `luau-analyze` 로 합니다. 예전에 쓰던
`luau-lsp analyze --platform=standard --flag:LuauSolverV2=true` 는 **진단을
조용히 빠뜨립니다.** (…)

## 유니온 자리에서 제네릭이 풀리는 조건 — 같은 별칭이어야 함 (2026-11-05, 질문 BE)
id: union-same-alias · since: 2026-11-05 · evidence: verified · last-confirmed: luau 0.742 · category: luau/types/unions · source: spikes/77
summary: 유니온 갈래가 인자와 **같은 별칭**이어야 T 가 풀린다(구조만 같으면 unknown) — 그래서 ArrData<T> 를 말단 모듈 Types 에 둠. 대가: 표 리터럴에 기대 타입이 안 내려감

리스트 자리를 "평범한 표 또는 `Arr`" 로 받으려고 잰 것(luau 0.742, 프로브 `stl-luau-scratch/arr-split/probes`, 지키는 곳 `spikes/77`):
(… 표 생략 …)

유니온의 한 갈래와 인자가 **같은 별칭**이면 인자끼리 맞춰 `T` 를 뽑고, 구조만 같으면 뽑지 못합니다. (…)

## 팬텀·표식의 모양 — quad 의 Ref 마커와 대조 (2026-11-06)
id: phantom-shape · since: 2026-11-06 · evidence: verified · last-confirmed: luau 0.742 · category: luau/types/variance · see: section references.variance.3-값-팬텀의-nil-구멍 in "pack:luau-kb/luau-types"

근거 `audit/quad-types-2026-11-06/`(quad `typing-limits.md` 8.11·8.36·8.41·8.42 와 대조, luau-analyze 0.742).
(…)

## ⚠️ 원소가 유니온인 컨테이너 — `self` 를 전체형으로 받으면 무너진다 (2026-09-26)
id: union-element-self · since: 2026-09-26 · status: archived · note: M0(질문 AB) 이후 컨테이너가 메타테이블 없는 표 + 네임스페이스 함수라 이 모양이 생길 자리가 없다

**증상**: `Arr<number?>` 나 `Arr<number | string>` 에서 `:Filter`/`:Map`/
`:Count`/`:Sort`/`:PushBack`/`:Clone` 이 전부 *"No valid instantiation could
be inferred for generic type parameter T"*. (…)
