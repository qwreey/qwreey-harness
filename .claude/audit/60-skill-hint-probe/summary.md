---
format: 1
title: 60. 프롬프트 시점 스킬 힌트 훅을 우리 스킬로 실측
description: 우리 description 은 이미 잘 불려(sonnet 양성 27/32) 힌트 훅의 이득이 작음(32/32, 첫 동작 로드 12/27 -> 30/32, 힌트 때문의 근접 오답 0/7, 틀린 힌트 0/4 따름); luau-kb 팩 스킬(net·perf)에 작게 둘 만하고 advisor 는 넣지 않음; 라우터는 lib 정본 사본, 경로는 플러그인·팩마다 파일, 팩은 coderag 가 낸다
---
# 60. 프롬프트 시점 스킬 힌트 훅 실측

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

사용자: "제안 부분도 한번 우리쪽에서도 시험해보자." audit 58 의 외부 라우터 훅(UserPromptSubmit regex -> 스킬 이름 한 줄)을 우리 스킬에 붙여 서브에이전트(opus)가 쟀고 메인이 이 요약을 썼다. 원자료 `/tmp/skillhint/`(커밋 안 함). 비용 USD 7.09(95회).

## 설정
- 훅: 표준 라이브러리 Python. `routes/*.json`(플러그인마다 {skill, why, any, pairs, not}), 점수 = any 적중 + pairs 적중, not 이면 0. 프롬프트당 하나, 세션·호출자당 스킬마다 한 번, `/` 건너뜀, 오류 시 침묵, `HARNESS_SKILL_HINT=off`. 출력 `<harness-hook name="skill-hint" level="info">` 한 줄: "This request fits the `X` skill (why). Load it with the Skill tool first, before you answer or ask for missing input, unless the request is outside that scope or a more specific skill fits better." 문구 변형은 시험하지 않음(힌트가 붙으면 sonnet 32/32 로드).
- `claude -p --max-turns 2`(2.1.316), 임시 CLAUDE_CONFIG_DIR, `--setting-sources project`, Bash·Agent 끔. 스킬만 남긴 실제 플러그인 사본으로 스킬 목록 48개. 픽스처는 작은 Roblox 게임 저장소. 스킬마다 한국어 양성 2·근접 오답 1, 양성 2회·근접 1회, 끔/켬.

## 경로
records(`기록해`, `남겨 줘·적어 둬` + 정한 거·결과·측정·.claude; not 로그·README·커밋·세션 기록·찾기), recall(`전에/예전에 … 정했·기로 했`, `왜 … 정했`; not git log), advisor(`다른 눈`, `한 번 더 봐`, 검토·다시 봐 + 계획·설계·방향; not 코드 리뷰·PR·diff), roblox-net(Remote·DataStore·영수증·복제·클라 검증), roblox-engine(이벤트 안 와, Destroy 뒤, Tween, task.*, Actor; not Remote), luau-types(타입 에러·추론, 제네릭; not TypeScript), luau-perf(벤치; 느려·최적화 + 코드·루프·정렬; not DataStore·로딩). 오프라인 대조: 양성 14/14, 근접 0/7, 일상 프롬프트 20개 중 1개(맞는 적중). "왜 느리지" 는 놓침(`느리` 어간 없음).

## 결과
| 스킬 | sonnet 끔 | sonnet 켬 |
|---|---|---|
| agent-records | 4/4 | 4/4 |
| recall | 4/4 | 4/4 |
| luau-perf | 3/4 | 4/4 |
| luau-types | 4/4 | 4/4 |
| roblox-engine | 4/4 | 4/4 |
| roblox-net | 2/4 | 4/4 |
| advisor | 2/4 | 4/4 |
| 합 | 27/32 | 32/32 |
- 첫 동작으로 로드: 끔 12/27, 켬 30/32.
- 근접 오답: 힌트 때문의 오로드 0/7.
- 이득이 난 곳: net "데미지 값 그대로 써도 돼?"(끔은 도구 없이 일반 지식으로 답함), advisor "PLAN.md 방향 다시 봐줘"(끔은 직접 검토).
- opus: 끔 8/10, 켬 9/10. advisor 프롬프트는 힌트를 받고도 직접 검토함.
- 틀린 힌트를 억지로 붙인 4회: 0/4 따름(RemoteEvent 쪽은 맞는 roblox-net 을 로드).

## 결론
- 외부(2/84 -> 24/84)와 달리 우리 description 은 과제 표현과 맞아 끔에서도 84% 로드한다. 힌트 훅은 이득이 작은 안전망이고, 탐색 전에 로드를 앞당기는 효과가 더 크다.
- advisor 는 넣지 않는다: 모델이 스스로 부르는 스킬이고, 사용자의 "다시 봐줘" 는 직접 검토로 충분하며(opus 도 그렇게 판단), 잘못 맞으면 비싼 리뷰어를 띄운다.

## 권고
- 둔다면 luau-kb 팩 스킬부터. recall·agent-records 는 이미 8/8 이라 선택.
- 라우터 코드는 `lib/skill_hint.py` 정본 + `tools/sync-copies.py` 사본, dedup 은 compact_epoch(세션·호출자·회차). q 에 두지 않는다.
- 경로는 플러그인·팩마다 스킬 옆 파일(`skill-hints.json`). 팩 스킬은 coderag 가 `coderag.toml` 의 켜진 팩에서 읽어 낸다(대안: 팩이 lib 사본 훅을 직접 싣기).
- 동기화: 경로의 스킬이 그 플러그인에 있는지 검사, 플러그인마다 한국어 양성·근접 사례를 `--match` 로 돌리는 오프라인 시험, description·경로가 바뀔 때만 모델 트리거 평가(sonnet 스킬당 끔/켬 약 USD 0.35). 붙여 넣은 훅 출력 지우기와 정보성 질문 거르기(audit 59)를 함께 넣는다.

## 한계
칸당 1~2회. 프롬프트와 경로를 같은 사람이 써서 양쪽으로 치우칠 수 있다. 단일 프롬프트 `-p` 라 CLAUDE.md·rule·대화 이력이 없다. max-turns 2 라 늦은 로드(주로 끔)를 덜 센다.
