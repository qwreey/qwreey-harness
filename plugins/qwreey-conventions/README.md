# qwreey-conventions

코드 주석과 모델이 읽는 문서의 관례. 스킬 둘이 "어떻게 쓰나"를 담고, 훅이 방금 추가한 줄이 벗어난 것 같으면 한 줄로 알린다(막지 않는다). 규칙 파일(`rules/comments.md`, `rules/agent-docs.md`)은 매 세션 로드되므로 핵심 몇 줄만 두고 스킬을 가리킨다. 근거는 claude-doctor `audit/26-doc-hygiene-debate/`.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 스킬 | `qwreey-conventions:comments` | 코드 주석: 지금의 이유만 쓰고 이력은 커밋·CHANGELOG·원장으로, `Ref:` 꼬리, 키보드로 치는 문자만, 파일의 주석 언어를 따른다, 문체, 저장소 설정 |
| 스킬 | `qwreey-conventions:agent-docs` | CLAUDE.md·SKILL.md·references·agents·rules: 판별 문장, 둘 것과 옮길 것, 입구 문서와 references 의 차이, 원장 id, "Move, do not delete" |
| 훅 | `hooks/conventions-check.py` | PostToolUse(Write, Edit, MultiEdit). 추가된 줄만 본다. (세션, 에이전트, 파일, 범주)마다 한 번, 한 줄 `<harness-hook name="qwreey-conventions" level="info">` |

## 훅이 잡는 것

코드 파일의 주석 줄:
- history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구. 이유 문장이 있는 `Ref:` 꼬리는 통과
- non-keyboard symbol: 키보드로 치지 않는 기호(가운뎃점 포함), 곡선 따옴표, 전각, 이모지. ASCII 와 모든 문자 체계의 글자(한글, 키릴, 악센트 라틴 등)·숫자는 통과. 알림에 글자와 대체를 적는다
- escaped character: 주석 안의 `\uXXXX` 류 이스케이프(금지 문자를 이스케이프로 적어 검사를 피하는 것을 막는다)
- invisible character: 보이지 않는 문자·방향 제어 문자. 코드 줄까지 줄 전체에서 본다. 알림에는 코드포인트(`U+00A0`)로 적는다
- language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가된 줄이 다른 체계 단어 3개 이상. 새 파일은 `comment_language`, 없으면 형제 파일 다수, 없으면 검사 안 함

모델용 문서(`CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`): 입구 문서는 날짜·audit 경로·라운드·결정 문구·실측 표지·변경 서술·`.md` 경로 없는 원장 id, `skills/**/references/*.md` 는 결정 문구·라운드·audit 근거·실측 표지·정정 배너만. frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰, `status:` 줄은 통과. md 본문의 기호는 대상이 아니다.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install qwreey-conventions@claude-doctor-market
```

하네스 마이그레이션 `home/settings-migrations/0005-qwreey-plugins.json` 이 예전 user-level `comment-hygiene` 훅을 빼고 이 플러그인을 켠다(같은 apply 에서 rules·HOOK-MESSAGES 도 바뀐다). 훅이 두 번 돌지 않게 둘 중 하나만 켠다. 이름 `qwreey-` 는 이 도구가 qwreey 의 의견임을 드러낸다.

## 설정과 끄기

저장소 `.claude/conventions.json`(전부 선택, 없으면 예전 이름 `.claude/comments.json` 을 읽는다): `comment_language`, `allow_chars`, `public_ids`, `exclude`, `patterns`, `allow_ref_tail`, `min_reason_words`. 형식은 `qwreey-conventions:comments` 스킬에 있다. 환경 변수 `CONVENTIONS_CHECK=off` 로 끈다.

하네스의 `~/.claude/lib/compact_epoch.py` 가 있으면 compact 회차마다 다시 알리고, 없으면 내장 대체(세션·에이전트·파일·범주마다 한 번)로 돈다.

## 테스트

```bash
python3 -I plugins/qwreey-conventions/tests/test-conventions-check.py
```
