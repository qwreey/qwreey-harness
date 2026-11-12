# Q 1라운드: 좁고 정확한 규칙, 저장소 자율

직접 센 값(git log + awk, 훅 재생이 아님):
- luau-kb: 최근 23커밋에서 모델용 문서에 추가된 줄 중 날짜·이력 문구가 걸린 줄은 514줄이고, 그중 508줄(97%)이 `references/` 에 있다. SKILL.md 같은 입구 문서에는 6줄뿐이다.
- quad: 초안 경로 안의 날짜는 21건(10파일)뿐이다. 자료의 9781건은 대부분 `base/` 원장에 있고, 원장은 초안 경로 밖이다.
- 파일별 주석 언어(주석 10줄 이상인 .luau, 한 언어 90% 이상이면 그 언어):
  - stl-luau: 한국어 132, 영어 5, 섞임 26
  - quad: 영어 250, 한국어 22, 섞임 99
  - table-sim: 한국어 43
- quad 주석의 한국어 외 non-ASCII: ─ 11715, — 3079, → 310, § 193.

## 1. 제안 문안
```
---
description: Model-facing docs state what is true and what to do now; work history lives in ledgers, decisions, or commits (paired with the comment-hygiene hook)
paths: ["**/CLAUDE.md", "**/SKILL.md", "**/agents/*.md", "**/.claude/rules/*.md", "**/skills/**/*.md"]
---
# Model-facing docs
> Repo rules and `.claude/comments.json` win. The check only informs, on lines you add.
A model reads these files to act. Keep a line only if removing it would change what the model does.
- Keep: present facts and instructions; the reason for a rule, in one sentence; pointers the model can open or run (`snippets/x.luau`, `references/y.md §3`); public ids (error codes, spec numbers, URLs).
- Applicability (`last_confirmed`, tool version) goes in frontmatter, or one `status:` line under a reference heading. Not in prose.
- Move to the ledger, decisions file, or commit: who decided and when, audit or round numbers, where a number was measured, "previously X", "fixed from".
- Rewrite time-relative words ("currently", "as of", "new", "last week") as plain present-tense facts.
- Do not keep correction banners ("fact fix: X was really Y"). Make the text right and log the fix in the ledger.
- Quote the user only when the wording is the instruction (a trigger phrase, a fixed user-facing string). Otherwise state the rule.
- A ledger whose numbering is its structure is not a model-facing doc. Entry docs may route into it by number (`typing-limits 8.43`); do not cite it as provenance.
- Fix lines you touch. Do not clean old text in bulk; propose a cleanup when you see a pattern.
## Check (one notice per file per session)
- Entry docs (CLAUDE.md, SKILL.md, agents, rules): dates; `audit/`, `session/`, `round N`; decision phrases; a bare `[A-Z]{1,2}-?\d{2,4}` id with no resolvable path on the line.
- `skills/**/references/*.md`: decision phrases, `round N`, `audit/\d+ §` provenance only. Dates and ids pass.
- Always pass: frontmatter, fenced and inline code, dates inside path tokens, `§N` routes, URLs, `public_ids`.
```
comments.md 변경분:
```diff
+## Characters
+- Never add invisible or direction-control characters: U+00A0, U+200B-U+200F, U+202A-U+202E, U+2060-U+2069, U+FEFF after the first byte. The reader and the parser then see different text.
+- No emoji in code comments. Status marks (✅ ⚠️ ❌) are state that goes stale; write the condition in words.
+- Typographic punctuation (→ — · … §) and divider lines are fine.
 ## Exceptions
-- Comment language follows the language already used in that file.
+- Comment language follows the file's existing comments; in a new file, the repo's `comment_language`, else sibling files. Korean is a normal comment language.
+- A repo that wants English-only comments (a public library) sets `"comment_language": "en"` in `.claude/comments.json`.
```
훅 패턴. 모두 추가된 줄만 보고, comment-hygiene 을 넓힌다(새 훅 없음).
- invisible: `[ ​-‏‪-‮⁠-⁩]|(?<!^)﻿`. 주석에 한정하지 않고 코드·md 줄 전체를 본다(Trojan Source).
- emoji: `[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]`. 주석 줄만 본다. → — ─ ① 은 범위 밖이라 통과한다.
- lang_mismatch: 다음을 모두 만족할 때만 알린다.
  - 그 파일에 기존 주석 줄이 10개 이상이고 90% 이상이 한 문자 체계다.
  - 추가된 줄에 다른 문자 체계 단어가 3개 이상 있다.
  - 지시자 줄(`--!`, `eslint-`, `noqa`, 단독 `TODO:`)은 빼고, 섞인 파일은 보지 않는다.
  - `comment_language` 가 설정되어 있으면 그 값을 기준으로 본다.

## 2. 경계 사례
- 실행 가능한 근거와 이력: 경로가 있고 모델이 열거나 돌릴 수 있으면 근거다. `.claude/audit/18 §12`, "실측 §12.5" 는 출처라 이력이다. 판별 기준은 "빼면 행동이 바뀌는가"다. 경로가 저장소에 없으면(동료 기계에 quad 가 없는 경우 등) 이력으로 본다.
- `last_confirmed`: frontmatter, 또는 reference 절마다 `status:` 한 줄. 공식 "Avoid time-sensitive information" 이 겨냥하는 것은 본문 서술이다.
- 번호가 구조인 연구 원장(quad base/): 이 규칙 대상이 아니다. 입구 문서가 번호로 길을 안내하는 것은 허용한다. 원장까지 보려면 comments.json 의 paths 로 opt-in 하게 하고, 이것은 사용자에게 제안한다.
- 공개 id: 기존 public_ids 를 그대로 쓴다. luau-kb 의 `D-10` 은 decisions/ 로 해소될 때만 근거로 본다. 플러그인으로 설치되면 decisions/ 가 따라오는지는 확인하지 않았다(추정 위험).
- → — 기호: 산문에서도 주석에서도 통과한다. 모델에 해가 된다는 근거가 없다. quad 주석의 — 3079개를 잡으면 순수 잡음이다.
- 한국어 주류 저장소의 한국어 주석: 통과한다. 기존 규칙과 회사 동료(한국어 Luau 개발자)를 따른다. 잡는 것은 파일 언어와 어긋날 때뿐이다.
- 사용자 원문 인용: 그 문구 자체가 지시일 때만 원문 언어로 남긴다(예: "한 번 더 봐줘" 트리거). 나머지는 규칙 문장으로 바꾸고, 원문은 원장에 둔다.

## 3. 알림 예산
- 보통 편집에서는 0건, 세션당 0~2건을 예상한다(추정). 근거: quad 초안 경로 50커밋에서 (커밋, 파일) 짝 9개, luau-kb 입구 문서 23커밋에서 6줄, luau-kb references 는 이력 문구만 보면 98줄(사용자가 지적한 진짜 대상).
- 잡음을 줄이는 수단:
  - 추가된 줄만 보고, 파일당 세션 1회로 한다(기존 방식).
  - comment·doc 위생을 합쳐 세션당 3회 상한을 새로 두고, 넘으면 조용히 한다.
  - 새 훅을 만들지 않는다.
  - 한국어 자체는 잡지 않는다. 잡으면 stl-luau 에서는 거의 모든 편집이 걸린다.
- 결론을 낼 방법: 최근 50커밋을 실제 훅에 재생해 파일별 알림 수를 센다.

## 4. 내 안의 실패 양식
- references 를 느슨하게 두면 `status:` 줄이 작은 변경 이력으로 자랄 수 있다.
- "경로가 있으면 통과" 는 경로가 해소되는지 확인해야 의미가 있고, 존재 확인 비용이 든다.
- lang_mismatch 의 문턱(10줄, 90%, 3단어)은 추정이다. 짧은 영어 기술 주석이 거짓 양성이 될 수 있다.
- 기호와 구분선(─ 11715개)이 무해하다는 것은 재 보지 않았다. count_tokens 로 구분선을 넣은 파일과 뺀 파일을 비교하면 결론이 난다.
- quad CLAUDE.md 가 원장을 @import 하면 그 원장은 사실상 입구 문서가 되어 경로 기준 면제가 틀어진다. 확인하지 않았다.

## 5. P 강철인과 반박
- 강철인: 이력은 이후 모든 세션이 비용을 내고 조용히 쌓인다. opt-in 은 결국 아무도 켜지 않는다. quad 가 자율이 실패한 증거이고, 모델은 본 것을 따라 쓰므로 전역 엄격 기본값이 맞다.
- 받아들이는 것: 입구 문서 엄격 검사와 문서 위생은 기본값으로 켠다(opt-in 이 아니다). invisible 문자와 이모지는 전역으로 잡는다. 영어 전용은 공개 라이브러리용 스위치로 둔다.
- 반박:
  1. 날짜·id 를 넓게 잡으면 luau-kb references 의 출처·status 줄을 친다. 그 줄은 지식 저장소가 일부러 남긴 적용 범위 정보다.
  2. 한국어를 잡으면 74~88% 주류 저장소에서 알림이 배경 소음이 되고, 진짜 이력 알림에 대한 주의도 떨어진다(추정, 훅 피로). "파일 언어를 따른다", "사용자 선택은 제안만" 과도 정면으로 부딪힌다.
  3. quad 문제의 대부분은 원장 안에 있고, 원장에서는 번호가 구조다. 전역 기본값으로 원장을 잡는 것은 일괄 정리를 신호 없이 시키는 것과 같다.
