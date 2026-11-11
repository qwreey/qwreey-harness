# qwreey-conventions

코드 주석과 모델이 읽는 문서의 관례. 스킬 둘이 "어떻게 쓰나"를 담고, 훅이 방금 추가한 줄이 벗어난 것 같으면 한 줄로 알린다(막지 않는다). 규칙 파일(`rules/comments.md`, `rules/agent-docs.md`)은 매 세션 로드되므로 핵심 몇 줄만 두고 스킬을 가리킨다. 근거는 claude-doctor `audit/26-doc-hygiene-debate/`.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 스킬 | `qwreey-conventions:comments` | 코드 주석: 지금의 이유만 쓰고 이력은 커밋·CHANGELOG·원장으로, `Ref:` 꼬리, 키보드로 치는 문자만, 파일의 주석 언어를 따른다, 문체, 저장소 설정 |
| 스킬 | `qwreey-conventions:agent-docs` | CLAUDE.md·SKILL.md·references·agents·rules: 판별 문장, 둘 것과 옮길 것, 입구 문서와 references 의 차이, 원장 id, "Move, do not delete" |
| 훅 | `hooks/conventions-check.py` | PostToolUse(Write, Edit, MultiEdit). 추가된 줄만 본다. (세션, 에이전트, 파일, 범주)마다 한 번, 한 줄 `<harness-hook name="qwreey-conventions" level="info">` |
| 훅 | 같은 스크립트, Stop | 편집한 파일에 남은 기존 주석 문제를 사용자에게 한 줄로 보인다(아래 "남은 주석 보고") |

## 훅이 잡는 것

코드 파일의 주석 줄:
- history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구. 이유 문장이 있는 `Ref:` 꼬리는 통과
- non-keyboard symbol: 키보드로 치지 않는 기호(가운뎃점 포함), 곡선 따옴표, 전각, 이모지. ASCII 와 모든 문자 체계의 글자(한글, 키릴, 악센트 라틴 등)·숫자는 통과. 알림에 글자와 대체를 적는다
- escaped character: 주석 안의 `\uXXXX` 류 이스케이프(금지 문자를 이스케이프로 적어 검사를 피하는 것을 막는다)
- invisible character: 보이지 않는 문자·방향 제어 문자. 코드 줄까지 줄 전체에서 본다. 알림에는 코드포인트(`U+00A0`)로 적는다
- language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가된 줄이 다른 체계 단어 3개 이상. 새 파일은 `comment_language`, 없으면 형제 파일 다수, 없으면 검사 안 함

모델용 문서(`CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`): 입구 문서는 날짜·audit 경로·라운드·결정 문구·실측 표지·변경 서술·`.md` 경로 없는 원장 id, `skills/**/references/*.md` 는 결정 문구·라운드·audit 근거·실측 표지·정정 배너만. frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰, `status:` 줄은 통과. md 본문의 기호는 대상이 아니다.

## 남은 주석 보고

원칙은 그대로다: 알림과 정리는 추가한 줄만, 기존 주석은 일괄 정리하지 않는다. 대신 사용자가 코드 품질을 가늠하도록 남은 것을 **보고만** 한다.

- PostToolUse 가 편집한 파일 전체에서 "이번에 추가하지 않은 줄"의 문제를 범주별로 세어 (세션, 호출한 쪽)별 파일에 조용히 쌓는다(같은 파일은 마지막 편집 기준, 고치면 사라진다). 파일 전체를 읽는 비용은 이미 하는 렉싱에 줄 단위 검사가 더해지는 정도다(재생 실측 파일당 최대 80ms, 훅 제한 10초).
- Stop 이 세션의 모든 기록(서브에이전트 포함)을 합쳐 사용자에게 한 줄을 `systemMessage` 로 보인다. 내용이 직전 보고와 같으면 다시 보이지 않는다. 예: `손댄 파일에 기존 주석 문제가 남아 있음: a.luau(이력 3, 기호 12), b.rs(기호 4). 정리는 요청하실 때만.` 파일은 5개까지, 나머지는 `외 N개`.
- 전달 방식을 이렇게 고른 이유: 공식 문서상 Stop 의 `additionalContext` 도 턴을 이어 가게 하므로(`decision: block` 보다 오류 표시만 약할 뿐 같은 루프), 모델 호출 한 번과 최종 보고 재작성 비용이 매번 든다. 첫 알림 꼬리에 붙이는 방식은 수정 직후에 뜨고, 추가한 줄이 깨끗하면 아예 안 뜬다. 스킬이 "끝나기 전에 스크립트를 돌려라" 하는 방식은 모델이 잊으면 전달되지 않는다. `systemMessage` 는 모델을 거치지 않아 비용이 0이고 빠지지 않는다. 모델이 직접 쓰게 하려면 Stop 의 `additionalContext` 로 바꾸면 되지만 위 비용을 낸다.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install qwreey-conventions@claude-doctor-market
```

하네스 마이그레이션 `home/settings-migrations/0005-qwreey-plugins.json` 이 예전 user-level `comment-hygiene` 훅을 빼고 이 플러그인을 켠다(같은 apply 에서 rules·HOOK-MESSAGES 도 바뀐다). 훅이 두 번 돌지 않게 둘 중 하나만 켠다. 이름 `qwreey-` 는 이 도구가 qwreey 의 의견임을 드러낸다.

## 설정과 끄기

저장소 `.claude/conventions.json`(전부 선택, 없으면 예전 이름 `.claude/comments.json` 을 읽는다): `comment_language`, `allow_chars`, `public_ids`, `exclude`, `patterns`, `allow_ref_tail`, `min_reason_words`. 형식은 `qwreey-conventions:comments` 스킬에 있다. 환경 변수 `CONVENTIONS_CHECK=off` 로 끈다.

compact 회차마다 다시 알린다. 회차는 플러그인 자기 것(`hooks/compact_epoch.py`, `$TMPDIR/claude-qwreey-conventions-epoch/<sid>`)이고 PreCompact 훅이 올린다. 하네스 lib 가 없어도 같다.

## 테스트

```bash
python3 -I plugins/qwreey-conventions/tests/test-conventions-check.py
```
