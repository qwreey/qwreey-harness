# 소음 실측: 넓힌 훅을 최근 커밋에 재생 (모델 호출 없음)

방법: quad, stl-luau, table-sim, luau-kb, claude-doctor 의 최근 50커밋(luau-kb 는 전체 28개)에서 `git show -U0` 로 파일별 추가된 줄을 얻어 `plugins/conventions/hooks/conventions-check.py` 의 검사 함수에 넣었다. 대상 저장소는 읽기만 했다. 저장소 `.claude/comments.json` 은 있으면 적용했다. 스크립트는 저장소 밖(`/tmp/replay/replay.py`)이다.

- 단위는 (커밋, 파일) 쌍이다. 훅의 한 번 알림(세션·에이전트·파일당)에 가장 가깝다. 한 쌍이 여러 범주에 걸릴 수 있다.
- 대상 쌍: 코드 파일 중 확장자 표에 드는 것과 모델용 문서 경로(`CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`). 생성 파일·exclude·fixtures 는 뺀다.
- 한계: 언어 검사의 "새 파일 형제 다수"는 현재 작업 트리의 같은 폴더를 읽는다(과거 시점이 아님). 한 커밋은 한 세션과 다르다(실제 세션은 같은 파일을 여러 번 고치므로 알림은 더 적다).

## 결과: (커밋, 파일) 쌍 수

| 저장소 | 커밋 | 대상 쌍 | 알림 있는 커밋 | history marker (코드) | non-keyboard symbol | language mismatch | invisible | Ref 이유 없음 | 문서 history marker |
|---|---|---|---|---|---|---|---|---|---|
| quad | 50 | 1197 | 34 | 191 | 380 | 15 | 0 | 1 | 1 |
| stl-luau | 50 | 251 | 30 | 57 | 110 | 2 | 0 | 0 | 1 |
| table-sim | 50 | 124 | 33 | 52 | 80 | 0 | 0 | 0 | 0 |
| luau-kb | 28 | 494 | 16 | 147 | 110 | 3 | 0 | 0 | 54 |
| claude-doctor | 50 | 300 | 21 | 14 | 49 | 0 | 3 | 0 | 41 |

## 읽기

- 가장 시끄러운 범주는 non-keyboard symbol 이다: 코드 파일 쌍 기준으로 quad 380, stl-luau 110, table-sim 80. 한글 주석에서 쓰는 긴 줄표(U+2014)가 압도적이다. 추가된 줄의 기호 글자 수: 긴 줄표 2065, 가운뎃점 338, 줄임표 133, 화살표 99, 가로줄 91, 절 기호 66, 경고 이모지 36, 동그라미 숫자 약 60. 사용자 결정(키보드 문자 기준)을 그대로 적용한 결과이므로 소음이 아니라 의도한 신호이고, 크기는 알려 둘 만하다. 일부 저장소가 반발하면 `allow_chars` 로 글자 단위로 끌 수 있다.
- history marker 는 저장소마다 다르다. luau-kb 의 snippets 는 후보 번호(`Q-066`, `S-123`)를 주석에 쓰고, table-sim 은 `사용자 2026-10-20: "..."` 식 인용을 주석에 쓴다. 둘 다 규칙이 겨냥한 모양이다. quad 191 건 중에는 `Ref:` 꼬리 밖의 인라인 번호(`round16 H-973`)가 많다.
- language mismatch 는 낮다(0~15). 거짓 양성을 줄이려고 두 가지를 더했다: 줄에 다른 체계 단어가 2개 이상이고 그 체계가 줄의 우세일 때만 센다, 영어 단어는 3글자 이상만 센다. 코드 조각 줄(`::`, `=`, 중괄호)과 지시자 줄은 뺀다.
- invisible 3건은 claude-doctor `verify.py` 의 `replace(" ", " ")` 를 실제 NBSP 문자로 쓴 줄이다. 의도한 코드지만 이스케이프로 쓰는 편이 안전하므로 알릴 만하다.
- 문서 쪽 54건(luau-kb)은 `D-03`·`D-12` 같은 결정 id 가 `.md` 경로 없이 쓰인 줄, 날짜, "사용자 결정" 문구다. claude-doctor 41건도 같은 종류다. quad 와 stl-luau 는 1건씩이다(추가된 문서 줄이 적다).

## 재생 중 고친 거짓 양성

처음 재생에서 나온 것을 고친 뒤 위 표를 다시 쟀다.
1. `# noqa: E402` 가 원장 id 로 잡힘: 지시자 줄은 주석 검사에서 뺀다.
2. 문서의 `/tmp/claude-audit/` 가 `audit/` 경로로 잡힘: 경로 패턴 앞에 `[\w-]` 가 오면 아니다.
3. 문서의 "if the user asked" 가 결정 문구로 잡힘: 문서용 결정 문구는 "사용자 결정/합의", `per user`, `as decided`, `the user decided` 로 좁혔다.
4. 한글 주석 파일의 한 단어 라벨(`# ---- index ----`), `` ```lua `` 줄, 단위(`us`)가 언어 불일치로 잡힘: 위 조건으로 해소.

## Rust/TS/Go 저장소 재생과 원장 id 오탐 확인 (r3-verdict 의 "원장 id 정규식 오탐 후보")

방법은 위와 같다(읽기만, 모델 호출 없음). 대상: coderag(Rust, 22커밋뿐), vitrine(TS/Go/sh, 29커밋뿐), VideoSync(TS/JS, 50), 이름 변경 전 훅 소스를 담은 claude-doctor(50). 스크립트는 `/tmp/replay/replay2.py`. 훅은 3라운드 반영본이다(알림 단위는 (파일, 범주)로 바뀌었다).

| 저장소 | 커밋 | 대상 쌍 | 알림 있는 커밋 | 코드 history marker | non-keyboard symbol | escaped character | invisible | language mismatch | 문서 history marker |
|---|---|---|---|---|---|---|---|---|---|
| coderag | 22 | 138 | 17 | 25 | 85 | 0 | 1 | 6 | 14 |
| vitrine | 29 | 90 | 13 | 0 | 47 | 0 | 0 | 0 | 0 |
| VideoSync | 50 | 69 | 8 | 9 | 0 | 0 | 0 | 0 | 1 |
| claude-doctor | 50 | 306 | 21 | 14 | 47 | 2 | 2 | 0 | 41 |

- 원장 id 로 잡힌 토큰(코드 주석, 전부 열거): coderag `D13` `D14` `D16` `D17` `D18` `D21` `D-09` `H-321` `B01`..`B12`, VideoSync `N19` `N20`. 실제 설계 결정·실험 번호이고(coderag `D21` 은 설계서 결정 번호, `B01`..`B12` 는 실험 코퍼스 사례 번호), `F64`·`I32`·`X86`·`C99` 같은 오탐은 이 4개 저장소 최근 커밋에서 나오지 않았다.
- 그래도 정규식 `[A-Z]{1,2}-?\d{2,4}` 는 하이픈이 없으면 정수 폭(`F64`), 아키텍처(`X86`), C 표준(`C99`), 컴파일러 오류 코드(`TS2322`, Rust `E0308`)에 맞는다는 것을 합성 줄로 확인했다. 그래서 기본 `BUILTIN_PUBLIC` 에 `[FIUS](8|16|32|64|128)`, `X86`, `C(89|90|99|11|17|23)`, `TS\d{4}`, `E0\d{3}` 를 더했다(하이픈 있는 `D-09` 류는 그대로 잡힌다). 회귀 테스트가 있다. 하이픈 없는 `D21` 꼴 원장은 여전히 잡힌다(실제 이력이므로 의도).
- `escaped character` 2건은 claude-doctor 훅 소스·테스트 주석의 `·` 이다(수정 전 커밋을 재생한 것). 새 검사가 3라운드가 지적한 우회를 실제로 잡는다는 확인이다.
- non-keyboard symbol 은 coderag·vitrine 에서도 가장 많다(vitrine 은 영어 주석의 긴 줄표가 전부). 기호 글자 순위(전 저장소 합): 긴 줄표 136, 화살표 128, 가운뎃점 112, 절 기호 96, 줄임표 15.
- invisible 1건(coderag)은 `experiments/team-audit/build_corpus.py` 의 bidi 공격 샘플 문자열이 주석 줄에 걸린 것이다(코퍼스 용도라 의도).
- 설계 메모: coderag 의 `claude-doctor `decisions/D-09.md`` 처럼 경로를 인용한 주석이 `D-09` 로 잡힌다(`.md` 경로 면제는 문서 쪽만 있다). 코드 주석에도 같은 면제를 줄지는 결정이 필요하고, 여기서는 건드리지 않았다.
