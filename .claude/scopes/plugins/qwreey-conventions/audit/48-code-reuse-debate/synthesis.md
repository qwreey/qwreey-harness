# 48. code-reuse 문구 토론: 종합

> Snapshot 2026-11-12. round1-P(간결)와 round1-Q(툴킷 전반)를 메인 세션이 종합했다. P 의 지적은 사용자가 동의했다("지적 나도 봤어. 맞는 말이라 동의함"). Q 의 사례 중 table-sim 의 쿨다운 상수 쌍과devplorer `codeClasses`/`codeLike` 는 메인 세션이 원문으로 확인했다(Q 가 적은 devplorer 경로에는 `src/` 가 빠져 있다).

## 바탕
P 의 줄인 rule(본문 약 620 토큰)을 바탕으로 하고, Q 가 "남겨야 한다"고 한 세 가지(클라이언트·서버 값, 사본 줄의 vendor·다른 언어, 타입으로 검사되는 리터럴)를 얹는다. Q 가 먼저 양보하겠다고 한 것(Roblox 엔진 서비스 = 라이브러리, `or` 사슬, 바깥 API 낱말 절) 중 바깥 API 낱말은 훅 오탐의 가장 큰 무리라 짧게 남긴다.

## 받아들인 것
- P: 정책 값 기준은 다른 저장소를 대상으로 도는 코드(도구, 플러그인, 라이브러리)에만. 게임 저장소의 밸런스·UI 상수를 설정으로 빼라고 읽히지 않게.
- P: "생태계 이름 목록은 그 팩으로"는 rule 에서 빼고 스킬에 제안으로만(팩은 보통 다른 저장소).
- P: "이 패키지가 import 할 수 있는 것"만 찾아 쓰고, 경계를 넘는 import 로 바꾸지 않는다.
- P: "이유 없으면 라이브러리"는 지움. 의존성 추가는 사용자 몫, 잰 비용과 함께 제안.
- P: 긴 함수 줄과 문자열 분기 가리킴은 rule 에서 뺌(code-structure 가 같은 문맥에 주입된다). 자기 자신을 돌려주는 분기는 스킬로.
- P: "더한 코드에만 적용" 범위를 rule 전체로.
- P: 빠진 알림 N7(타입 유니언과 런타임 목록이 어긋남). 사용자 결정 "어긋날 때만"에 TS 도 포함하고 N6 을 N7 로 합친다.
- P: 알림 끝의 스킬 안내는 "모르겠으면 스킬"로 줄인다(알림마다 스킬 약 1k 토큰을 읽게 하지 않게).
- Q: 클라이언트·서버가 맞춰야 하는 값은 공유 모듈 한 곳에. "X 와 같음" 주석은 검사되지 않는 사본이다.
- Q: vendor 트리(`vendor.lock.json` 등)는 표시도 수정도 하지 않는다. 원본을 고치고 다시 vendor.
- Q: 다른 언어 사이의 사본은 import 할 수 없는 사본으로 보고, 하나에서 다른 하나를 생성할 수 있으면 생성.
- Q: 타입으로 검사되는 리터럴은 이미 참조다. 바깥 API 이름(엔진 클래스, 도구 이름)은 자기 어휘가 아니다.
- Q: 라이브러리를 못 쓰는 이유에 "런타임이 설치할 수 없음"(stdlib 만 되는 훅 등)을 더한다.
- Q 훅: `.claude/` 제외(quad 는 추적 코드 파일 3,155 중 2,605 가 `.claude/` 안), `*-ignoreme*` 제외, 다른 언어 쌍은 N2 + 생성 안내, pesde·wally 의존은 import 가능, 생성 파일 패턴에 `생성:`, 자기 파일을 가리키는 표시는 원본 표시, 파일 표시는 머리 바이트에서 찾음(Python 은 docstring), 표시는 줄 주석에(문서 블록 안 아님), Astro 템플릿은 `{/* */}`, JSON 은 표시 불가, `#NAME` 은 정의에 적힌 이름 그대로, 지금의 `정본:` 머리말도 옮길 대상.
- Q 턴 끝 보고: 비프로그래머가 읽을 수 있게. `손댄 파일에 전부터 있던 문제: a.luau(주석 15), b.rs(같은 목록이 두 곳 2). 고치려면 "기존 문제도 정리해줘" 라고 하시면 됩니다.` 원본과 달라진 사본은 따로 한 줄: `사본이 원본과 다름: ...`.

## 고친 rule 본문
```
# Code reuse

## Values
- In code that runs against other repos or projects (tools, plugins, libraries), a value two projects could reasonably want different (folder or extension lists, size limits, stage ladders, tool names) is policy: read it from config, with a `DEFAULT_*` fallback in code. Values fixed by a format, spec, outside tool or correctness stay `const`.
- `DEFAULT_` promises an override; do not use the prefix for a value nothing overrides.
- A value two sides must agree on (client and server, two scripts of one game) lives in one shared module both require. A "same as X" comment is an unchecked copy.

## One definition
- Before writing a helper (parser, walker, hash, glob, date, string trim) or a list of names (statuses, kinds, levels), search for one this package can import, and use or extend it. Two copies of one fact drift apart.
- A copy this package cannot import (separately installed package, another repo, another language): keep it, mark it `@copy-of: <path>[#NAME]` in a line comment, and compare it with the source in a test, or generate one from the other. Do not replace it with an import across the package boundary. Vendored trees are not marked or edited: change the source and re-vendor.
- A literal checked against a type (a Luau or TS union) already references it. Names owned by an outside API (engine classes, tool names) are not your vocabulary.
- A list that mirrors a union: TS derives the union from the list (`(typeof LIST)[number]`); Luau annotates the list with the union type.

## Libraries
- Hand-writing a parser or algorithm that a well-known library provides: put `why not <library>: <reason>` at the top of the module (measured size or startup budget, exact parity with a reference, tolerant parsing, the runtime cannot install it). Adding a dependency is the user's call; propose it with measured cost (size, build time, dependency count).

## Scope
- Apply this to code you add. Do not refactor existing code for it unprompted; old duplicates in edited files are reported to the user at turn end.
- Markers, repo settings and hook notices: load the `qwreey-conventions:code-reuse` skill. A repo's own rules win.
```

## 다음
1. 초안의 rule, 스킬, hook-design, fp-strategy 를 위에 맞게 고친다(스킬로 옮길 것: 판단 표, 라이브러리 기준 세부, 자기 자신을 돌려주는 분기, 생태계 팩 제안, 마커 문법 세부).
2. `conventions-check.py`(874줄)의 렉서를 `conv_lex.py` 로 이동만 하는 커밋.
3. 설치: rule·스킬, `code-structure` 의 복사 파일 항목과 가리킴 줄 삭제, `Canonical copy:`·`정본:` 머리말을 `@copy-of:` 로 옮기고 `tools/tests/test-vendored-copies.py` 를 새 표시에 맞춤, 훅 H1(그림자)·C1·C2, 턴 끝 보고 문구.
