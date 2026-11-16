---
format: 1
title: 56. 읽기 좋은 코드 상시 rule 문구 토론 종합
description: 상시 rule 에 문단·라벨·문서 주석 자리·이유 자리·선언과 이름·분기 사다리·되풀이 루프·적용 범위·Bash 편집 줄과 짧은 예시를 둔다(약 2.4k자); "자세한 건 스킬" 포인터는 실제로 0번 읽혀 스킬로 보낸 항목은 사라지므로; rule 은 언어 중립으로 쓰고 Luau 형태(`---`)는 luau-kb 로
---
# 56. 읽기 좋은 코드 상시 rule 문구 토론 종합

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

입장: P 최소(효과가 잰 줄만 상시, 나머지는 알림과 스킬), Q 전부(스킬은 안 읽히고 알림은 Bash 편집을 놓치니 규약 전체를 상시). opus 2명, 1라운드. 원문은 대화 기록(c9a9e895)에 있고 `raw/` 에는 브리프와 메인의 사전 견해만 있다. 근거: `.claude/research/drafts/readable-code.md`, `readable-code-wording.md` 3.1, `audit/55-readable-code-probe/summary.md`.

## 둘이 확인한 사실 (메인이 다시 확인)
- rule 끝의 "자세한 건 스킬" 포인터는 실제 세션에서 읽히지 않는다: comments rule 이 실린 기록 36~73개에서 `qwreey-conventions:comments` 스킬 호출 0, SKILL.md Read 0. 쓰인 스킬은 q:workspace 60, code-review 25, code-reuse 2~3, agent-docs 1~2. audit 55 B 의 세부 파일 29/30 읽힘은 작은 프로젝트를 `ls`/`cat` 으로 둘러본 것이다. 표본은 claude-doctor 작업에 치우쳤다.
- 주입은 (세션, 서브에이전트 또는 main, compact 회차, rule)마다 한 번이다(`plugins/qwreey-conventions/hooks/rules_inject.py:17-18`). 파일을 열 때마다가 아니고, compact 뒤에는 다음 해당 파일 열기에서 다시 실린다.
- rule frontmatter 의 `description` 은 주입 때 떨어져 모델에게 안 보인다(`rules_inject.py` `parse_rule`).
- audit 55 채점의 `multi_decl` 은 다중 반환 받기(`local x, y = readPair()`)까지 셌다(`/tmp/rcprobe/scripts/score.py:97`). 다시 세면 진짜 한 줄 여러 선언 L2 A 3/3, B·D 0/6; 한 글자 지역(Circle.luau 제외) A 12, B 0, D 4. 선언·이름 항목은 효과가 있었고 그 효과는 세부 파일에만 있던 항목에서 나왔다.
- 알림은 Bash 편집(45회 중 약 13회)을 못 보고, 다 쓴 뒤 다시 쓰게 해 출력이 는다(출력 토큰 A 76.6k, B 87.4k, D 98.2k).
- 스타일 가이드는 갈린다: PEP 8 과 Google C++ 은 함수 안 빈 줄 문단과 까다로운 블록 앞 주석을 권하고, Linux 커널은 본문 안 주석을 피하라고 한다. 본문 라벨은 학습된 기본값이 아니라서 문구에 적어야 한다.

## 쟁점
| 항목 | P | Q | 고른 쪽과 이유 |
|---|---|---|---|
| 문단, 라벨, 문서 주석, 이유 자리 | 상시 | 상시 | 상시 |
| 선언, 한 줄 한 이름, 한 글자 금지, 이름 일관성 | 스킬 | 상시 | 상시: 재집계로 효과 확인 |
| 예시 함수 | 스킬 | 상시 | 상시(짧게). 실측 과제와 같은 예시라 효과가 부풀었을 수 있음 |
| 분기 사다리 라벨 | 스킬 | 상시 | 상시 한 줄(사용자 코드 2/2, 잰 적 없음) |
| 되풀이 루프는 도우미로 | 스킬 | 상시 | 상시 짧게(사용자 결정) |
| 형제 모듈 순서, 형제 파일 먼저 열기 | 스킬 | 상시 | 뺌: A 도 지켰고 읽기 비용이 는다 |
| 적용 범위(쓰거나 키운 함수만) | 없음 | 상시 | 상시: 손 안 댄 코드 고치기 잡음을 막는다 |
| Bash 편집 뒤 다시 보기 | 없음 | 상시 | 상시: 알림 빈틈 |
| Luau 캐스트, 한국어 어미 | 다른 곳 | 다른 곳 | luau-kb `idioms.md`, comments 스킬 |

## 사용자 답 (원문)
"전부 동의는 함. 그러자. 다만 생각해볼 점이. 주석을 언제 어떻게 달고 그런건 언어에 무관히 도움되는 영역인데, luau 에 묶여 있는 조건들이 달린다는게 조금 뭔가 그렇네. 그리고 스킬이 읽히지 않는건 이유가 약간 다른것 같음. 룰도 요청 내용처럼 실릴거고, '자세한건 보라' 는데 그 자세한건 봐야할 동기가 없는거 아닐까 싶기도. 다만 이건 진짜 규칙이긴 해서 규칙으로 집어넣으면, 또 자동으로 compact 단위에서 restore 가 된다면 문제는 없겠다는 생각이 들긴함. rules 에서 skill 이 언급되는 경우 어떤 동작을 띄는지는 좀만 더 연구를 해봐야하나 싶기도 하네. 다른곳도 유사한게 있던것 같기도 하고."
정한 것: 크기 약 2.4k자로 간다; 키운 함수는 전체를 다시 맞춘다; 공개 함수 `---` 문서 줄은 luau-core 에(남이 부르는 코드 조건 포함); 한 글자 금지에서 루프 인덱스는 예외.

## 적용 문구
rule 은 언어 중립으로 쓴다(사용자: Luau 조건이 붙는 것이 어색하다). 문서 주석의 형태는 "편집기가 호버와 자동완성에 보여 주는 형태"로만 말하고, Luau 의 `---`/`--[=[ ]=]` 는 luau-core 와 luau-style 이 말한다. 예시는 Luau 로 두되 형태 설명에 기대지 않는다.

```markdown
# Readable code
A reader scans code by shape before reading it: blank lines end a step, short comment lines name what each step is for, the doc comment above a function says what it gives a caller.

- In a function over about 10 lines, separate its steps (guards, each unit of work, checks after it, the return) with single blank lines; a short function has none.
- Head a step whose intent is not obvious with a label: English, 2-10 words, no period, numbering or reason. The labels alone should read as the function's flow. Restating one line (`-- Increment the counter`) is noise; skip a label the code already says.
- In a ladder of 4 or more cases, label each case and keep a case that deliberately does nothing.
- Put what a function gives its caller in a doc comment above it, in the form your editor shows on hover and completion (the toolkit's style rule names it). Public functions in code others call always get one. Its first sentence ends on the first line, about 80 characters.
- A design reason is a plain comment above the declaration, apart from the doc comment. Inside a body a reason is one line at the trap, below the step label; never a multi-line block between statements.
- Declare a local at first use in the narrowest block (handles every step uses at the top, loop state right before the loop). One name per declaration except receiving multiple returns. One role keeps one name; paired operations get symmetric names; no one-letter locals except loop indices.
- The second time the same few-line loop is needed, extract a helper.

      local function reparent(proxy, newParent)
          local data = proxyData[proxy]
          if data.parent == newParent then return end

          -- Detach from the previous parent
          removeValue(childrenOf(data.parent), proxy)

          -- Attach under the new parent
          table.insert(childrenOf(newParent), proxy)
          data.parent = newParent
      end

- Applies to functions you write or grow; a function you grew should read this way as a whole. Leave untouched functions alone.
- After an edit through Bash (heredoc, sed), re-read the changed functions against this rule; the layout notice does not see Bash edits.
- A layout notice gives per-function numbers as evidence, not a verdict. A repo's own rules win.
```

luau-core 한 줄(luau-kb 를 켠 모든 저장소): `- Public functions in code others call (a library, a module other modules require) get a \`---\` doc comment; luau-lsp shows only \`---\` and \`--[=[ ]=]\` on hover and completion, never \`--\`.`

## 받아들이지 않은 것
- P 의 4줄안: 선언·이름 효과를 잃는다(근거였던 지표가 틀림).
- Q 의 "형제 파일을 먼저 열어라": A 도 순서를 지켰고 읽기 비용이 는다.

## 고칠 것 (결과와 별개로)
- 알림과 채점의 다중 선언 판정은 다중 반환 받기를 빼고 센다.
- rule 의 중요한 말은 본문에 쓴다(frontmatter description 은 모델에게 안 보인다).

## 남은 질문
- rule 이 스킬을 가리킬 때 모델이 실제로 스킬을 읽게 하는 조건(사용자: "그 자세한건 봐야할 동기가 없는거 아닐까"). 다른 rule 들(qwreey-conventions 의 comments, code-reuse, agent-docs, coderag agent-records)도 같은 꼴의 포인터로 끝난다. 포인터 꼴별 스킬 로드율 실측이 필요하다.
