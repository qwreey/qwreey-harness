---
format: 1
title: 58. 외부 스킬 모음(alirezarezvani/claude-skills) 조사
description: 약 400개 스킬 모음도 description 다듬기만으로는 안 불리는 스킬이 남아 UserPromptSubmit 라우터 훅(프롬프트 regex -> "Load it with the Skill tool first, before you answer or ask for missing input")을 두었고 sonnet 2/84 -> 24/84, 근접 오답 0/21; rule·references 포인터는 재지 않음; 쓸 만한 것은 라우터 훅과 트리거 평가 설계
---
# 58. 외부 스킬 모음 조사

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

사용자: "만일 우리처럼 rule -> skill invoke 모양이 있거나 선행 사례로써, 생각해볼 점은 얻을 수 있겠다 싶어. clone 은 해도 되는데 읽기만 해보는게 맞겠음". 서브에이전트(opus)가 `/tmp/ext-claude-skills`(커밋 08cd8a9)를 읽기만 하고 조사했고, 메인이 라우터 훅 문구와 실측 표를 원문에서 다시 확인했다.

## 구조
- SKILL.md 483개(Gemini 사본 67, 중복 게시 23쌍; 저장소 스스로 "384 unique"). 플러그인 112개. SKILL.md 중앙값 173줄·8.3k자, references 305개·scripts 283개 스킬.
- 크기 규칙이 문서마다 다르고(10KB / 100줄 / 500줄) 많이 어긴다. 생성된 틀 문구가 많다("You are an expert" 32, "Proactive Triggers" 66). CLAUDE.md 895줄은 대부분 릴리스 서술.

## description
- 중앙값 218자. "Use/Load/Invoke" 시작 294, "use when" 178, "whenever" 113. description 안 "not for" 경계는 3개뿐(경계는 본문 Related Skills 에 있어 트리거에 안 쓰인다).
- 작성 지침: "The description is the only thing your agent sees", "lead with the job in user words and name the situations that should load the skill".

## rule -> skill 꼴
- `.claude/rules` 같은 상시 rule 은 없다. 대신 UserPromptSubmit 라우터 훅 `engineering/hooks/skill_router.py`(사본 8개, `scripts/check_skill_router.py` 가 같은지 검사), 패턴은 `hooks/skill_routes.json`(경로마다 any/pairs/not regex, why 한 줄).
- 주입 문구(원문): "Skill hint ({plugin} plugin): this request fits the `{name}` skill ({why}). Load it with the Skill tool first, before you answer or ask for missing input, unless the request is outside that scope or a more specific skill fits better."
- 만든 이유(원문): "Two rounds of description rewrites did not move them, so wording is not the lever. This hook is."
- 소음 규칙: 프롬프트당 플러그인마다 힌트 하나, 세션에 스킬당 한 번, `/` 로 시작하는 프롬프트 건너뜀, 오류 시 침묵, `SKILL_ROUTER=0`·`SKILL_ROUTER_<PLUGIN>=0`.
- 스킬 안 포인터는 "See references/..."(196줄)와 "ALWAYS load before ..."(8파일) 꼴. references 가 실제로 읽히는지는 재지 않았다.

## 트리거 평가
- `claude -p --plugin-dir <플러그인> --max-turns 2`, 빈 폴더·일회용 config, transcript 의 `Skill` 호출로 판정. 스킬마다 양성 2, 근접 오답 1. PR 게이트는 이전·새 description 을 같은 실행에서 2회씩(REGRESSED 25점 넘게 하락, BELOW_FLOOR 50% 미만, FALSE_FIRE).
- 전체 389개 중 한 번도 안 불린 스킬 112개. 재작성 1차 26%->38%, 2차 48개 중 14개만 나아져 남김. 라우터 스킬 4개는 0회 로드로 명령 전용으로 바꿈.
- 라우터 훅(Claude Code 2.1.322, sonnet, 그 플러그인만): 끔 2/84, 켬 24/84, 근접 오답 0/21. 힌트가 붙은 34회 중 24회 로드. 문구 "load it before answering" 19/84 -> "first, before you answer or ask for missing input" 24/84. 나머지 50회는 프롬프트가 모호해 패턴이 안 맞았다.
- 한계: 칸당 1~2회, 같은 프롬프트로 고르고 잰 선택 편향, 플러그인 하나만 실은 후한 조건.

## 우리에게
- 해볼 만한 것: (1) 프롬프트 시점 스킬 힌트 훅(agent-records "기록해 줘", recall "전에 뭐라고 정했지", luau-kb 증상; 지금 luau-core 의 "Symptom -> skill" 표는 Read 뒤에 실려 audit 57 기준 효과가 약하다); (2) 트리거 회귀 측정(이전·새 description 나란히, 양성 2·근접 오답 1, 한국어 프롬프트); (3) 실제 세션의 스킬 목록 잘림 확인.
- 들여오지 말 것: 스킬 본문·rule 의 "See/ALWAYS load" 포인터를 로드 장치로 기대하기(audit 57), 라우터·인덱스 메타 스킬, description 다듬기만으로 해결하기.
- 프롬프트가 스킬 주제를 말하지 않는 경우(함수를 쓰다가 주석 규약)는 힌트 훅도 못 잡는다. 그 경우는 audit 57 권고(사실은 rule 본문, 저장소 설정 값은 주입 훅이)가 맞다.
