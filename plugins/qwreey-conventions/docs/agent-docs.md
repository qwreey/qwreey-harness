# 모델용 문서 규약 참고 (사람용)

모델이 지킬 것은 `rules/agent-docs.md` 에 있고, CLAUDE.md, SKILL.md, agents, rules, 스킬 문서를 열거나 쓸 때 훅이 그 본문을 넣는다. 지켜졌는지는 `conventions-check.py`(검사 함수는 `hooks/conv_docs.py`)와 `bash_writes.py` 가 추가한 줄마다 보고, 벗어나면 줄 번호와 고치는 법을 담은 알림을 모델에게 준다. 이 문서는 무엇을 남기고 무엇을 옮기는지의 예, 문서 종류별 검사, 기존 문서 정리 방법을 사람이 찾아보는 곳이다. 모델에게 실리지 않는다.

모델은 이 문서를 읽고 다음에 할 일을 정한다. 시험은 하나다: 지워도 모델이 하는 일이 달라지지 않는 문장은 여기 있을 까닭이 없다.

## 알림 범주
| 범주 | 언제 | 알림이 주는 고치는 법 |
|---|---|---|
| history marker | 입구 문서의 날짜, `audit/`·`session/`·`handoff/` 경로, 라운드, 결정 문구, 실측 표지, 변경 서술. references 는 결정 문구, 라운드, audit 근거, 실측 표지, 정정 배너만 | 지금의 사실로 다시 쓰고 이력은 커밋 메시지나 이미 있는 원장으로 |
| skill description | `SKILL.md` description 이 끝의 한국어 계기 문구 앞에서 영어가 아님, 언제 쓰는지가 없음, 1·2인칭 | 무엇을 하는지, 언제 쓰는지(`Use when ...`), 영어 3인칭, 한국어 계기는 끝에 |
| ledger id path | 입구 문서의 원장 id 줄이 가리키는 `.md` 가 문서와 함께 배포되는 곳(같은 플러그인, 플러그인 밖이면 저장소)에 없음 | id 와 파일을 함께 주거나 id 를 뺀다 |
| language mismatch | 영어로 쓴 모델용 문서에 한국어가 주인 줄. 이미 한국어로 쓴 문서는 따른다 | 영어로. 사용자에게 보일 글만 한국어 |
| invisible character | 보이지 않는 문자, 방향 제어 문자 | 지운다 |

frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰, `status:` 줄은 보지 않는다. 경로 안의 날짜나 인용한 명령은 자료다. 범주별 판정 세부는 [how-it-works.md](how-it-works.md) 의 주석·문서 검사 절.

## 남는 것
- 지금 시제의 사실과 지시.
- 행동을 바꾸는 이유 한 문장("캐시를 함께 쓰므로 실행은 먼저 OOM 순위를 낮춘다").
- 모델이 작업 중에 열거나 돌릴 포인터: references 파일, 스니펫, 스크립트, references 의 절. 절 번호로 안내하는 것도 포인터다.
- 사실로 쓴 버전 범위("luau 0.742 이상 필요"). 확인 메타데이터(`last_confirmed`)는 frontmatter 나 절마다 `status:` 한 줄에 둔다. `status:` 줄은 검사하지 않는다.
- 공개 id, 표준 번호.
- 문구 자체가 지시일 때만 사용자 말 인용(계기 문구, 정확한 출력 문자열).

## 옮기는 것
- 누가 언제 정했는지, 본문의 날짜.
- audit·라운드·세션 번호와 경로, 실측 출처 표지, 결정 id.
- 변경 서술: `previously X`, `recently`, 버전 없는 `as of`, `last week`. 지금의 사실로 다시 쓴다.
- 정정 배너(`fact fix`, `correction:`). 고친 내용을 본문에 반영하고 배너는 뺀다.
- 지시가 아니라 이력을 설명하는 사용자 말 인용.

옮기되 지우지 않는다. 근거를 지우면 나중에 결정을 따라가려는 사람이 잃는 것이 있으므로, 이미 있는 자리에 둔다: 커밋 메시지(기본), 저장소가 두는 원장이나 decisions 파일, CHANGELOG. 이력을 담으려고 새 파일을 만들지 않는다. 한 문장이 이력이면서 쓸모 있으면 나눈다: 사실은 남고 출처는 옮긴다.

예. 전: `Since 2026-11-10 (audit/18) the hook only reads added lines; previously it scanned whole files.` 후: `The hook reads only the lines added by the current edit.` 날짜, audit 경로, 옛 동작은 커밋 메시지로 간다.

## 입구 문서와 references
| 종류 | 파일 | 걸리는 것 |
|---|---|---|
| 입구 | CLAUDE.md, SKILL.md, agents, rules, 스킬 폴더 안 `references/` 밖의 파일 | 날짜, `audit/`·`session/`·`handoff/` 경로, 라운드, 결정 문구, 실측 표지, 변경 서술, 같은 줄에 `.md` 경로가 없는 원장 id |
| references | `skills/**/references/*.md` | 결정 문구, 라운드, `audit/<n>` 근거, 실측 표지, 정정 배너 |

references 는 옛 꼴을 설명하는 것도 할 일이라 날짜, id, `previously X` 를 둘 수 있다. 입구 문서는 매번 실리므로 가볍게 둔다.

## 원장 id
원장이나 결정 id 는 그 파일(`.md` 경로)을 함께 적은 줄에만, 그리고 그 파일이 문서와 함께 배포될 때(같은 스킬이나 플러그인 루트)만 남는다. 함께 가지 않는 곳을 가리키는 id 는 읽는 쪽에게 막다른 길이다.

훅은 그 줄이 문서를 담은 플러그인(플러그인 밖이면 저장소) 안의 있는 `.md` 를 가리키는지 본다. 경로는 문서 폴더, 플러그인 루트, 저장소 루트에서 차례로 푼다.

번호가 구조인 연구 원장(다른 문서가 번호로 인용하는 항목들)은 검사하지 않는다. 입구 문서는 그런 원장을 번호로 가리켜도 된다.

## 글의 꼴
- 스킬 description: 무엇을 하는지와 언제 쓰는지, 영어 3인칭, 덜 불리지 않게 조금 적극적으로, 끝에 한국어 계기 문구 몇 개. 본문은 쓰는 법: 어떻게 부르고, 무엇이 돌아오고, 다음에 무엇을 하는지.
- 예외: `disable-model-invocation: true` 스킬(사용자 명령)은 모델이 보지 않고 사용자만 `/` 메뉴에서 읽으므로 메뉴 줄 description(언어 자유, 계기 문구 없음)이다. 훅도 보지 않는다.
- 모델 사이를 오가는 글(스킬, 에이전트 프롬프트, 훅 메시지)은 영어. 사용자에게 보일 문구만 한국어.
- 사례를 늘어놓기보다 원리를 한 번 말한다. 모델은 일반화한다.
- 관리자를 위한 근거는 스킬 자신의 `references/rationale.md`(필요할 때 열고, 본문에서 한 줄로 링크)나 스킬 밖 `docs/` 에 둔다.

## 기존 문서 정리
훅은 이번에 추가한 줄만 알리고, 손댄 문서에 전부터 있던 문제는 턴 끝에 사용자에게 한국어 한 줄로 셀 뿐이다. 정리하려면 사용자가 명령을 부른다.

```
/qwreey-conventions:docs-cleanup [경로...]
```

명령은 `scripts/conventions-scan.py scan --kind doc` 으로 모델용 문서만 검사하고, 보이지 않는 문자는 `fix` 로 본문 안만 지운 뒤, 이력 줄은 모델이 지금의 사실로 다시 쓰고 옮길 이력을 보고에 모은다. 커밋은 사용자가 시킬 때만 한다. 도구만 쓰려면:

```bash
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py scan --kind doc [경로...] [--summary]
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix --kind doc [경로...] --dry-run
```

skill description, language mismatch, ledger id path 는 추가한 줄에만 보는 꼴 검사라 `scan` 에 나오지 않는다. 한국어로 쓴 기존 문서가 통째로 걸리기 때문이다.
