# P 1라운드 (엄격한 전역 기본값 측)

실측 하나: `/tmp/p_cnt.py` 로 각 저장소 최근 커밋(최대 300개)에서 추가된 주석 줄을 셌다. 값은 "그 문자가 들어간 커밋 비율"이다(편집 단위가 아니라 커밋 단위).
- quad: 이모지 3%, 기호(→—·§ 등) 74%, 한국어 31%
- stl-luau: 이모지 47%(대부분 테스트 기대표의 ✅❌), 기호 89%, 한국어 96%
- table-sim: 이모지 0%, 기호 78%, 한국어 95%

## 1. 규칙 문안
### A `rules/model-facing-docs.md` (paths 는 초안 그대로)
```
# Model-facing docs
> If the repo's `.claude/rules/`, `conventions.md`, or `.claude/comments.json` says otherwise, follow the repo. The `doc-hygiene` hook only informs.
## Keep
- Current facts and instructions in present tense, with one sentence of why when the why changes behavior.
- Pointers you would open or run during the task: `references/x.md §3`, `snippets/x.luau`, `scripts/check.py`.
- Version scope stated as a fact ("Requires luau 0.742 or later"). Confirmation metadata (`last_confirmed`, `last_verified`) goes in frontmatter only.
- Public ids and standard numbers. A ledger id only on a line that also names the ledger file.
- Quoted wording only when the wording is the spec (trigger phrases, an exact output string).
## Move out (to the commit message, `audit/`, `decisions/`, or one rationale link in `docs/`)
- Where a rule came from: `audit/18 §12`, `[measured §12.5]`, `D-13`, round or session numbers.
- Who decided and when: "the user decided", "per discussion", dates in the body.
- Change narration: "previously X", "as of", "recently changed", correction banners. Rewrite them as the current fact.
Test: if deleting the sentence would not change what the model does, it is history.
## Editing
- Move, do not delete. If the history has no home yet, put it in the commit message.
- Fix only lines you add or touch. Bulk cleanup only when the user signals for it.
```
A 훅. 추가된 줄만 보고, frontmatter·코드 펜스는 건너뛴다.
- 잡는 것:
  - `\b(audit|decisions?|handoff|session)/\S*`
  - `\[(실측|측정|추정|measured|estimated?)[^\]]*\]`
  - `\b20\d\d-\d\d-\d\d\b`, `\bD-\d{1,3}\b`
  - round/decision 정규식(comments 훅과 공유)
  - `\b(previously|as of|recently)\b|현재 기준|지난\s?(주|번)|사실 정정`
  - `\b[A-Z]{1,2}-\d{2,4}\b` 중 같은 줄에 `\S+\.md` 가 없는 것
- 통과: 감사 경로가 붙지 않은 `§N` 라우팅, public_ids.

### B `comments.md` 변경
```
-- Comment language follows the language already used in that file.
+## Characters and language
+- Default: plain ASCII. Comments are read in terminals, diffs, grep, and the Studio editor.
+- No emoji or status pictographs (✅ ❌ ⚠️ ★): write `ok`, `FAIL`, `NOTE:`.
+- No decorative typography (→ — · § curly quotes, box drawing, circled digits): write `->`, `-`, `,`, straight quotes.
+- Language: follow the majority language of existing comments in the file; in a new file, the repo's `comment_lang` (default `en`).
+- Repo opt-outs in `.claude/comments.json`: `{"comment_lang": "ko", "allow_chars": ["typography", "emoji"]}`.
```
B 훅. 렉서가 이미 문자열 리터럴을 걸러 내므로 주석 조각만 본다.
- emoji: `[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]`
- typography: `[‐-‧←-⇿①-⓿─-▟§·]`
- lang: 추가된 줄에 한글이 있는데 파일 주석의 다수가 영어일 때. 반대 방향도 같다.
- 통과: Latin-1 글자(이름), 단위·수학 기호 `× ± ° µ`, 백틱 안 식별자.

## 2. 경계 사례
- 행동 근거 대 이력: 작업 중에 모델이 열거나 실행할 것(스니펫, 스크립트, 같은 스킬의 §)이면 둔다. 결정 과정의 기록(`audit/18 §12`, 실측 태그)이면 뺀다.
- `last_confirmed`: frontmatter 에 둔다. luau-kb 의 `status: verified · last-confirmed: luau 0.742 · 근거: snippets/…` 줄은 버전 범위 메타라 통과시키고, 본문의 날짜만 잡는다.
- quad 연구 원장: A 의 paths 밖이다. 원장은 이력이 가야 할 목적지이고 번호가 곧 구조다. 다만 SKILL.md 에 맨 id 가 있으면 잡는다. 원장 파일명이 같은 줄에 있으면 포인터로 보고 통과시킨다.
- 공개 id: A 와 B 가 내장 목록과 저장소 public_ids 를 함께 쓴다.
- `→` `—`: md 산문에서는 통과, 주석에서는 기본으로 잡는다. ASCII 대체가 있고 grep 이나 터미널 폰트와 충돌하기 때문이다(추론).
- 한국어 다수 저장소의 한국어 주석: 파일 다수결 규칙으로 통과한다. "파일 언어를 따른다" 를 집행하는 것일 뿐 새 금지가 아니다. 영어가 다수인 quad 파일에 들어간 한국어만 잡힌다.
- 사용자 원문 인용: 모델용 문서에서는 이력이다. 원문이 사양 자체(트리거 구절)일 때만 둔다. 주석에서는 항상 커밋 메시지로 보낸다.

## 3. 소음 예산
- 기존 장치로 이미 상한이 있다: 추가된 줄만 보고, 파일·세션·에이전트당 1회, 5줄까지, level=info.
- 언어는 파일 다수결이라 한국어 저장소에서는 0에 가까울 것으로 본다(추론).
- 진짜 위험은 typography 다(커밋의 74~89%). 대응: 처음 적용할 때 기존 저장소마다 `allow_chars: ["typography"]` 한 줄을 사용자 승인으로 넣는다. stl-luau 의 ✅❌ 는 사용자가 opt-out 할지 고른다.
- 결론을 낼 실측: 최근 300커밋의 파일별 diff 를 훅에 재생해서 범주별 커밋당 알림 수를 센다.

## 4. 내 안의 실패 양식
1. opt-out 을 넣지 않으면 typography 알림은 거의 매 편집 뜬다.
2. 미래 날짜("2027-01-01 에 X 폐지")는 모델이 알아야 할 사실인데 A 가 잡는다(거짓 양성, info 라 비용은 작다).
3. 모델이 이력을 옮기지 않고 지워 출처를 잃거나 필요한 포인터까지 지울 수 있다("Move, do not delete" 의 효과는 실측하지 않았다).
4. 설정이 없는 새 저장소에서는 기본값 `en` 이 한국어 주석에 알림을 낸다. 대응: /q:start 나 intake 가 `comment_lang` 을 묻는다.
5. `§` 와 원장 id 의 포인터/이력 판별을 정규식으로 하면 경계에서 틀린다.

## 5. Q steelman 과 반박
- Steelman: 커밋의 75~95% 에서 뜨는 전역 기본값은 소음세다. 모델이 info 를 흘려 읽게 길들여 더 중요한 훅까지 깎아 먹는다. 한국어 주석은 의도된 선택이고 독자는 한국인 동료다. 그러니 전역은 "파일을 따른다" 만 두고, 검사는 저장소별 opt-in 으로 하며, A 는 skills 로 좁혀야 한다.
- 반박:
  1. opt-in 은 누군가 알아차려야 켜진다. 위생을 맡은 이 저장소의 전역 규칙에조차 이력이 있다(`code-structure.md` 의 "Policy: decided as D-13 (2026-11-10)", `comments.md` 의 "(2026-11-11)").
  2. 소음은 typography 한 범주에 몰려 있고, 그건 처음 한 번의 opt-out 으로 해소된다. 언어는 "파일을 따른다" 를 집행할 뿐이다.
  3. 엄격한 기본값에 명시적 opt-out 을 두면 저장소의 선택이 `comments.json` 에 기록된다. 묵시적 자율보다 투명하다.
  4. A 를 skills 로만 좁히면 가장 자주 읽히는 CLAUDE.md 와 rules 가 빠진다.
  5. 모델이 주변 문체를 따라 이력 표지를 복제한다는 것은 추론이다. 결론을 낼 실측: 표지 있는 판과 없는 판으로 새 절을 쓰게 하고 출력의 표지 수를 비교한다.
