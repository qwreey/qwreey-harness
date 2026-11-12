# qwreey-conventions

코드 주석과 모델이 읽는 문서의 관례. 스킬 셋이 "어떻게 쓰나"를 담고, 훅이 방금 추가한 줄이 벗어난 것 같으면 한 줄로 알린다(막지 않는다). 규칙 파일(`rules/*.md`)은 `paths:` 가 맞는 파일을 열 때 훅이 주입하므로(공식 `.claude/rules` 와 같은 효과, 플러그인은 rules 를 실을 수 없어서) 핵심 몇 줄만 두고 스킬을 가리킨다. 근거는 claude-doctor `.claude/audit/26-doc-hygiene-debate/`.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 스킬 | `qwreey-conventions:comments` | 코드 주석: 지금의 이유만 쓰고 이력은 커밋·CHANGELOG·원장으로, `Ref:` 꼬리, 키보드로 치는 문자만, 파일의 주석 언어를 따른다, 문체, 저장소 설정 |
| 스킬 | `qwreey-conventions:agent-docs` | CLAUDE.md·SKILL.md·references·agents·rules: 판별 문장, 둘 것과 옮길 것, 입구 문서와 references 의 차이, 원장 id, "Move, do not delete" |
| 훅 | `hooks/conventions-check.py` | PostToolUse(Write, Edit, MultiEdit). 추가된 줄만 본다. (세션, 에이전트, 파일, 범주)마다 한 번, 한 줄 `<harness-hook name="qwreey-conventions" level="info">` |
| 훅 | `hooks/structure-reminder.py` | PostToolUse(Write, Edit, Bash). 파일 크기 한도(경고 800, 강제 1,500줄), 세션 성장, 폴더 파일 과다를 알린다. 저장소 `.claude/structure.json` 으로 조정 |
| 훅 | `hooks/bash-bypass-reminder.py` | PreToolUse(Bash). sed -i·리다이렉트·인터프리터로 파일을 바꾸면 Edit·Write 훅과 rules 가 비껴간다고 알린다 |
| 훅 | `hooks/memory-placement.py` (+`memory_signals.py`) | PostToolUse(Write, Edit, MultiEdit). auto memory 에 저장소 지식으로 보이는 내용을 쓰면 저장소로 옮기라고 알린다. `MEMORY_PLACEMENT=off` 로 끈다 |
| 훅 | `hooks/rules_inject.py` | PostToolUse(Read, Edit, Write, MultiEdit, NotebookEdit). 같은 훅의 사본을 web-security 플러그인도 쓴다(정본은 여기). `rules/*.md`(comments, agent-docs, code-structure, code-reuse, memory)를 `paths:` glob 이 맞는 파일을 열 때 `<rule plugin=... name=...>` 로 감싸 주입한다. 키 (세션, 에이전트, compact 회차, rule) 당 한 번, `O_EXCL` 마커라 병렬 배치도 이중 주입이 없다. Read 뒤에는 본문만, 이 키로 처음인 Edit·Write 뒤에는 본문과 "방금 쓴 것을 rules 에 대조하고 어긋나면 Edit 로 고쳐라" 한 문장을 싣는다. PreToolUse deny 는 없다(큰 새 파일 Write 를 통째로 다시 내게 하고 hook error 로 보여서). node_modules, .git, dist, build, .venv, vendor, __pycache__ 아래와 프로젝트 밖 Read 는 주입하지 않는다(편집, 그리고 설정 디렉터리 `projects/*/memory/` 는 예외). 대조 실측: Read 뒤 주입이 지켜짐 |
| 훅 | `hooks/reply_language.py` | 답변 언어 이탈. 언어는 `language` 설정(프로젝트 local > project > 사용자), 없으면 `${CLAUDE_PLUGIN_DATA}/language.json`. 둘 다 없으면 UserPromptSubmit 이 한 번 사용자에게 묻게 하고 `python3 -I reply_language.py set <language>` 로 저장. Stop: 목표 문자 비율 < 0.25 이고 라틴 글자 20자 이상이면 `decision: block` 으로 다시 쓰게 한다(`stop_hook_active` 면 통과). PostToolBatch: 도구 호출 사이 텍스트 이탈(warn, 쿨다운)과 긴 턴 알림(10회, 이후 15회마다 info). 감지·조치는 `${CLAUDE_PLUGIN_DATA}/drift.jsonl`(본문 없음). 메인 대화만. 라틴 문자 언어는 감지하지 않고 기록만 |
| 스킬 | `qwreey-conventions:code-reuse` | 값(정책/불변식), 한 사실 한 정의, `@copy-of` 사본 표시와 언어별 문법, 라이브러리와 직접 구현의 기준(`why not <library>:`), 알림 처리 순서, 저장소 설정(`reuse`) |
| 훅 | `hooks/reuse-check.py` (+`reuse_sets.py`) | PostToolUse(Write, Edit, MultiEdit). `@copy-of` 사본이 원본과 같은지(C1), 원본을 고치면 사본 목록(C2)을 알린다. 문자열 목록 중복(H1, 타입 합집합과 런타임 목록의 어긋남 포함)은 기본이 그림자: 알리지 않고 `${CLAUDE_PLUGIN_DATA}/reuse-shadow.jsonl`(없으면 `$TMPDIR/claude-qwreey-reuse/shadow.jsonl`)에 남긴다. `REUSE_CHECK=off\|shadow\|on` 또는 `.claude/conventions.json` 의 `reuse.mode`. 저장소 단위 색인은 `$TMPDIR/claude-qwreey-reuse/`, 데운 편집 중앙값 36-58ms(프로세스 기동 포함), 첫 색인은 300ms 에서 끊고 이어 만든다. `.claude/`, `*-ignoreme*`, 벤더 트리, 생성 파일, 시험은 보지 않는다. conventions-check 와 프로세스를 나누는 이유: 같은 이벤트의 훅은 병렬이라 합치면 둘의 시간이 더해지고, 색인과 렉서 사용이 달라 공유할 상태가 거의 없다 |
| 위임 | 기록 규약(`.claude/`) | 이 플러그인에는 없다. coderag 플러그인의 `coderag:agent-records` 스킬과 그 rule 이 맡는다 |
| 훅 | 같은 스크립트, Stop | 편집한 파일에 전부터 있던 문제(주석, 같은 목록)와 원본과 달라진 사본을 사용자에게 보인다(아래 "남은 주석 보고") |

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
- Stop 이 세션의 모든 기록(서브에이전트 포함)을 합쳐 사용자에게 한 줄을 `systemMessage` 로 보인다. 내용이 직전 보고와 같으면 다시 보이지 않는다. 예: `손댄 파일에 전부터 있던 문제: a.luau(이력 3, 기호 12), b.rs(같은 목록이 두 곳 2). 고치려면 "기존 문제도 정리해줘" 라고 하시면 됩니다.` 파일은 5개까지, 나머지는 `외 N개`. reuse-check 가 따로 쓰는 기록(`<sid>.reuse.<who>.json`)을 합치며, `@copy-of` 사본이 원본과 다르면 둘째 줄 `사본이 원본과 다름: c.py 1. 동작이 달라질 수 있습니다.` 가 붙는다. 같은 목록 수는 `reuse.mode` 가 `on` 일 때만 센다.
- 전달 방식을 이렇게 고른 이유: 공식 문서상 Stop 의 `additionalContext` 도 턴을 이어 가게 하므로(`decision: block` 보다 오류 표시만 약할 뿐 같은 루프), 모델 호출 한 번과 최종 보고 재작성 비용이 매번 든다. 첫 알림 꼬리에 붙이는 방식은 수정 직후에 뜨고, 추가한 줄이 깨끗하면 아예 안 뜬다. 스킬이 "끝나기 전에 스크립트를 돌려라" 하는 방식은 모델이 잊으면 전달되지 않는다. `systemMessage` 는 모델을 거치지 않아 비용이 0이고 빠지지 않는다. 모델이 직접 쓰게 하려면 Stop 의 `additionalContext` 로 바꾸면 되지만 위 비용을 낸다.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install qwreey-conventions@claude-doctor-market
```

하네스 마이그레이션 `home/settings-migrations/0005-qwreey-plugins.json` 이 예전 user-level `comment-hygiene` 훅을 빼고 이 플러그인을 켠다(같은 apply 에서 rules·HOOK-MESSAGES 도 바뀐다). 훅이 두 번 돌지 않게 둘 중 하나만 켠다. 이름 `qwreey-` 는 이 도구가 qwreey 의 의견임을 드러낸다.

## 설정과 끄기

저장소 `.claude/conventions.json`(전부 선택, 없으면 예전 이름 `.claude/comments.json` 을 읽는다): `comment_language`, `allow_chars`, `public_ids`, `exclude`, `patterns`, `allow_ref_tail`, `min_reason_words`. 형식은 `qwreey-conventions:comments` 스킬에 있다. 키 `reuse`(`mode`, `allow`, `vocab_ok`, `min_shared`)는 `qwreey-conventions:code-reuse` 스킬에 있다. 환경 변수 `CONVENTIONS_CHECK=off` 로 끈다. rules 주입은 `HARNESS_CONVENTIONS_RULES=off`(환경 변수 또는 harness.env)나 저장소 `.claude/conventions.json` 의 `rules_exclude: ["comments", ...]`(rule 이름 목록)로, 답변 언어 훅은 `HARNESS_REPLY_LANGUAGE=off` 로 끈다.

compact 회차마다 다시 알린다. 회차는 플러그인 자기 것(`hooks/compact_epoch.py`, `$TMPDIR/claude-qwreey-conventions-epoch/<sid>`)이고 PreCompact 훅이 올린다. 하네스 lib 가 없어도 같다.

## 테스트
(모든 훅의 사용자 설정 위치는 `$CLAUDE_CONFIG_DIR`(기본 `~/.claude`)다. `lib/harness_env.py` 가 없으면 기본값으로 돈다.)

```bash
python3 -I plugins/qwreey-conventions/tests/test-conventions-check.py
python3 -I plugins/qwreey-conventions/tests/test-structure-reminder.py
python3 -I plugins/qwreey-conventions/tests/test-reuse-check.py
python3 -I plugins/qwreey-conventions/tests/test-memory-placement.py
python3 -I plugins/qwreey-conventions/tests/test-rules-inject.py
python3 -I plugins/qwreey-conventions/tests/test-reply-language.py
```
