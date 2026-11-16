# 주석 규약 참고 (사람용)

모델이 지킬 것은 모두 `rules/comments.md` 에 있고, 코드 파일을 열거나 쓸 때 훅이 그 본문을 넣는다. 지켜졌는지는 `conventions-check.py` 와 `bash_writes.py` 가 추가한 줄마다 보고, 벗어나면 줄 번호와 고치는 법을 담은 알림을 모델에게 준다. 이 문서는 그 알림의 뜻, 저장소 설정, 기존 주석 정리 방법을 사람이 찾아보는 곳이다. 모델에게 실리지 않는다.

## 알림 범주
알림 꼴: `<파일> may not follow the comment conventions. L12, L15 non-keyboard symbol: <글자> (use "-", ","); L20 history marker: <고치는 법>. Fix those lines; ...`. 범주는 아래 순서로 나온다.

| 범주 | 언제 | 알림이 주는 고치는 법 |
|---|---|---|
| history marker | 원장 번호(`H-973`), 날짜, 라운드, `.claude/`·`audit/`·`session/` 경로, 결정 문구(`사용자 결정`, `per user`), 변경 서술 | 이유를 지금의 코드에 대한 문장으로 남기고 이력은 커밋 메시지로 |
| Ref tail without a reason sentence | `Ref:` 꼬리 줄은 있는데 같은 주석 덩어리에 이유 문장(낱말 3개 이상)이 없음 | 그 위에 이유 문장을 쓴다 |
| non-keyboard symbol | 키보드로 치지 않는 기호, 곡선 따옴표, 전각, 이모지 | 글자와 대체(아래 표) |
| escaped character | 주석 안의 `\uXXXX`, `\u{...}` 이스케이프 | 글자 자체를 쓰거나 고쳐 쓴다 |
| invisible character | 보이지 않는 문자, 방향 제어 문자(코드 줄도 본다) | 코드포인트(`U+00A0`)와 "지운다" |
| language mismatch | 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가한 줄이 다른 체계 낱말을 3개 이상 씀 | 파일의 다른 주석과 같은 언어로 |

변경 서술은 정밀도 쪽으로 좁혔다: 문장 첫 `Previously`, 대명사 주어 뒤 `used to`(`it`, `this`, `we`, `they`, `nothing`), `예전에는`·`예전엔`·`이전에는`·`이전엔`, `기존에는`·`기존엔` 뒤 같은 문장의 과거형. `the previously selected item`, `a key used to sign`, `이전에 없던 키` 처럼 코드가 하는 일을 말하는 꼴은 통과한다.

공개 식별자는 이력이 아니다: 사용자에게 문서화한 오류 코드, 표준 번호(UTF-8, H264, ES2020), 정수 폭(F64, I32), 컴파일러 오류 코드(TS2322, E0308)는 그대로 둔다. 저장소 고유의 것은 `public_ids` 로 더한다.

모델이 오탐(인용한 글, 꼭 필요한 기호)이나 일부러 둔 예외를 그대로 두면 보고에 한 번 적는다(rule 의 알림 대응 줄).

## 기호 대체
| 대신 | 쓸 것 |
|---|---|
| 가운뎃점 | `,` 또는 `/` |
| em dash, en dash, 가로 막대 | ` - ` 또는 `:` |
| 화살표 | `->`, `<-`, `=>` |
| 동그라미 숫자 | `1)`, `2)` |
| `§` | 뺀다 |
| 말줄임 글자 | `...` |
| 곡선 따옴표 | 곧은 따옴표 |
| 이모지, 체크·엑스 표시 | `ok`, `FAIL`, `NOTE:` 또는 평범한 말 |

모든 문자 체계의 글자(한글, 키릴, 가나, 악센트 라틴)와 숫자는 통과한다. 가운뎃점까지 거는 이유: 코드 주석에 사람이 일부러 치는 일이 드물고(대개 붙여 넣기로 온다), 공백을 보이게 한 편집기는 공백을 옅은 가운뎃점으로 그려서 헷갈리기 쉽다.

## 읽기 좋은 코드 알림 (`HARNESS_READABLE_CODE=on`)
규약은 `rules/readable-code.md` 에 있다. 이번 편집이 함수 줄의 절반 이상을 쓰거나 15줄 이상 키운 함수에만 알림 뒤에 `layout (readable-code)` 부분이 붙는다.

| 범주 | 언제 | 답 |
|---|---|---|
| layout | 빈 줄 아닌 본문 15줄 이상인데 빈 줄이 없거나, 빈 줄 없이 20줄 넘게 이어짐 | 함수 전체를 빈 줄과 라벨로 단계 나누기. 정말 한 단계(표 리터럴, 식 하나)면 두고 보고에 한 번 |
| interleaved comment | 본문 안에서 위아래가 코드인 2줄 이상 주석 | 설계 이유는 선언 위(문서 주석과 따로), 함정 자리에는 한 줄 |
| doc summary | 공개 함수에 호버 꼴 문서 주석이 없음, 첫 줄 100자 초과, 첫 문장이 첫 줄에서 안 끝남 | 문서 주석을 쓰거나 고친다. 다음 편집 뒤 한 번 더 본다. 메타메서드와 비공개 함수는 묻지 않는다 |

알림의 숫자: lines 는 빈 줄 아닌 본문 줄, blank 는 본문 안 빈 줄, longest run 은 빈 줄 없이 이어진 가장 긴 줄 수(주석 줄 포함). 함수마다 같은 숫자와 라벨, 한 줄 여러 선언, 한 글자 지역 변수를 보려면 `python3 -I scripts/conventions-scan.py layout <파일>`.

## 저장소 설정
저장소의 `.claude/conventions.json`(모든 키 선택. 없으면 예전 이름 `.claude/comments.json`):

```json
{"comment_language": "ko", "allow_chars": ["emoji", "~"], "public_ids": ["Quad\\d{4}"], "exclude": ["docs/**"],
 "label_language": "en", "layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15}}
```

- `comment_language`: `en`, `ko`, `ja`, `zh`, `ru`. 새 파일에 쓰고(없으면 같은 폴더 형제 파일의 다수, 그것도 없으면 검사 안 함), 규칙 주입이 comments rule 제목 아래에 `This repo: comment_language = ...` 한 줄로 넣는다. 영어만 받는 공개 라이브러리는 `"en"`.
- `allow_chars`: `"emoji"` 는 이모지를 허용하고, 그 밖의 항목은 허용할 글자들이다.
- `public_ids`: 이력이 아닌 식별자 정규식.
- `exclude`: 훅이 건너뛸 경로 글롭.
- `patterns`: 검출기 이름(`ledger`, `date`, `round`, `path`, `decision`, `narration`)별 정규식 덮어쓰기, `null` 이면 끈다.
- `allow_ref_tail`: `false` 면 `Ref:` 꼬리 허용을 끈다. `min_reason_words`(기본 3): 이유 문장으로 칠 낱말 수.
- `label_language`: 언어 검사에서 빼는 단계 라벨의 언어(기본 `en`, `null` 이면 예외를 끈다). 한국어 주석 파일 안의 짧은 영어 라벨이 그 예다.
- `layout`: 읽기 좋은 코드 알림의 기준.
- 환경 변수 `CONVENTIONS_CHECK=off` 가 알림 훅을 끈다. 저장소 자신의 `.claude/rules/` 나 규약 문서가 이 규약보다 우선한다.

## 기존 주석 정리
훅은 이번에 추가한 줄만 알리고, 손댄 파일에 전부터 있던 문제는 턴 끝에 사용자에게 한국어 한 줄로 셀 뿐이다(`손댄 파일에 전부터 있던 문제: a.luau(이력 3, 기호 12) ...`). 정리하려면 사용자가 명령을 부른다.

```
/qwreey-conventions:comments-cleanup [경로...]
```

명령은 `scripts/conventions-scan.py` 로 검사하고, 판단이 필요 없는 기호와 보이지 않는 문자는 `fix` 로 주석 안만 바꾼 뒤 코드가 그대로인지 확인하며, 이력·언어처럼 판단이 필요한 줄은 모델이 직접 고쳐 쓴다. 도구만 쓰려면:

```bash
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py scan [경로...] [--summary]
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...] --dry-run
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...]
```

자세한 동작(대체 규칙, 토큰 가드, 사본은 고치지 않음)은 [how-it-works.md](how-it-works.md) 의 파일 전체 검사 절.
