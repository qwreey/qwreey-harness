---
format: 1
title: reuse-check 훅 설계(초안)
description: qwreey-conventions 의 새 PostToolUse 훅 reuse-check. 추가한 줄의 문자열 묶음이 저장소의 기존 정의와 겹치면 info 한 줄, @copy-of 사본 대조, 그림자 기록과 80% 관문, 언어별 추출, 편집당 비용 예산
status: landed in plugins/qwreey-conventions/rules/code-reuse.md
---
# reuse-check 훅 설계

규칙 초안은 `rules/code-reuse.md`, 처리 절차는 `skills/code-reuse/SKILL.md`, 검사별 거짓 긍정 표는 `fp-strategy.md`. 모양은 지금 플러그인의 훅을 따른다: 막지 않음, 추가한 줄만, (세션, 호출한 쪽, 파일, 범주)당 한 번, 사유 필수 예외, 기존 문제는 Stop 에서 사용자에게 보고만, 저장소 설정이 이김.

## 1. 돌리는 검사

| id | 검사 | 처음 상태 | 켜는 조건 | 비고 |
|---|---|---|---|---|
| H1 | 문자열 묶음 중복: 추가한 묶음이 다른 곳의 정의와 겹침 | 그림자 | 언어별 관문(§9) 통과 | 이 훅의 본체 |
| C1 | `@copy-of` 검사: 경로·이름이 풀리나, 둘 다 문자열 묶음이면 같은가 | 켬 | 처음부터 | 표시를 단 사람이 원한 검사라 거짓 긍정이 거의 없다 |
| C2 | 정본 쪽 편집: 바꾼 정의를 가리키는 `@copy-of` 사본 목록 | 켬 | 처음부터 | 색인에 역참조가 있으면 비용 0에 가깝다 |
| H2 | 마법 수 중복: 5자리 이상 정수, 6자리 이상 16진, `\u{..}` 가 2개 파일 이상 | 그림자만 | 따로 판단 | audit/47 에서 약 75%. 알림 문구는 H1 과 같은 꼴 |
| H6 | 긴 함수: 이번 편집으로 비시험 함수가 100줄을 **넘음** | 그림자만 | 따로 판단 | 구조 문제라 켤 때는 structure-reminder 쪽에 둔다 |
| - | H3 비슷한 함수, H4 정책 냄새 const, H5 문자열 분기, H7 바퀴 재발명 | 훅에 없음 | - | H3 은 요청 시 감사 스크립트, H4 는 `DEFAULT_` 규약으로 대신, H5 는 code-structure 규칙, H7 은 규칙과 검토 |

## 2. 입력

- 이벤트: PostToolUse(Write, Edit, MultiEdit). Bash 로 바꾼 파일은 보지 않는다(bash-bypass-reminder 가 이미 알린다).
- 추가한 줄: `conventions-check.py` 의 `collect()` 를 그대로 쓴다(Edit 은 new_string 에서 old_string 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면 `originalFile` 과의 차이).
- 새 묶음: 묶음의 줄 중 하나라도 추가한 줄이고, 같은 원소의 묶음이 편집 전 텍스트(old_string, originalFile)에 없던 것. 원소를 하나 더한 묶음도 새 묶음이다. 줄만 옮긴 묶음은 새 묶음이 아니다.
- 제외 경로: conventions-check 의 `SKIP_PARTS`·`SKIP_SUFFIX`·`GEN_MARK` 와 같은 값, 그리고 시험 경로(`TEST_PATH`), `stories/`, `gallery/`, `examples/`, `refs/`, 1 MB 넘는 파일, 저장소 `reuse.allow`.

## 3. 언어별 묶음 추출

주석·문자열 구분은 conventions-check 의 렉서(`lex(text, fam)`)를 쓴다. 블록 주석(`--[[ ]]`, `/* */`, Rust doc 주석) 안의 묶음은 묶음이 아니다. 문자열 원소 3개 이상, 원소마다 글자가 하나 이상이고 길이 2 이상(구두점·연산자 묶음 제외).

| 언어 | 묶음 | 정의로 보는 것 | 따로 다루는 것 |
|---|---|---|---|
| Rust | `[..]`·`&[..]` 리터럴, `"a" \| "b"` match 갈래, `matches!` | `const`·`static`·`let` 바인딩, 구조체 필드 초기값 | `#[cfg(test)]` 아래 제외. Cargo path 의존이 있는 crate 는 import 가능으로 본다 |
| Python | list·tuple·set·frozenset 리터럴, `x in (...)` | 모듈 수준 이름 대입, dict 값 | argv 목록 제외(`-` 로 시작하는 원소가 있고 원소 8개 이하) |
| TS/JS | 배열(`as const` 포함), 문자열 합집합 타입 | `const`·`let`, `type X =` | 타입 합집합 ↔ 런타임 목록이 같으면 "하나에서 다른 하나를 끌어내라" 알림(N6) |
| Luau | `{ "a", ... }` 테이블, 문자열 합집합 타입 | `local`·`const` 바인딩, `type X =` | 타입 합집합 ↔ 런타임 목록은 알리지 않는다(끌어낼 수단이 없다). 타입끼리는 원소가 같을 때만 |

Go·Kotlin 은 렉서 계열은 있으나 이번 판 밖이다(표본이 없다).

## 4. 색인과 비용 예산

- 색인 파일: `$TMPDIR/claude-qwreey-reuse/<저장소 루트 sha1 앞 12자>.json`. 세션이 아니라 저장소 단위(여러 세션이 같이 씀). 쓰기는 임시 파일 + rename, 경합은 캐시라 감수한다.
- 내용: `{"v": 1, "files": {"<rel>": [mtime_ns, size, [[줄, 이름, def|inline|type, 패키지, [원소...]], ...]]}, "copies": {"<정본 rel>#<NAME>": ["<사본 rel>:<줄>", ...]}}`.
- 파일 목록: `git ls-files` 가 되면 그것(무시 규칙을 따른다), 아니면 걷기 + 제외 경로.
- 갱신: 편집한 파일은 매번 다시 뽑고, 나머지는 mtime·크기가 바뀐 것만 다시 뽑는다.
- 예산(훅 프로세스 시작부터 끝까지, 벽시계):

| 경우 | 목표 | 넘으면 |
|---|---|---|
| 색인이 데워진 편집 | 중앙값 60 ms 이하, p95 150 ms 이하 | 그림자 기록에 `budget` 표시 |
| 색인이 없는 첫 편집 | 한 번에 300 ms 까지만 색인하고 끊는다 | 다음 편집에서 이어 만든다. 다 만들기 전에는 색인된 부분에 대해서만 판정 |
| 원본 파일 5,000개 초과 | 편집한 파일의 패키지 안만 색인 | 패키지 밖 중복은 못 본다(재현율 손실, 기록) |
| 하드 상한 | 400 ms | 판정을 그만두고 조용히 끝낸다 |

- 실측 근거(`probe/sets_probe.py`, 렉서 없는 간이판, 색인 없이 저장소 전체를 매번 훑을 때): coderag 37 ms, claude-doctor 102 ms, table-sim 96 ms, VideoSync 159 ms, quad 190 ms. 짝 비교는 5 ms 이하. 색인 조회는 파일당 0.1 ms 이하. Python 기동 약 10 ms. 렉서를 쓰면 훑기가 몇 배 느려지므로 색인이 없으면 예산을 못 맞춘다. 같은 플러그인 conventions-check 의 파일당 렉싱은 재생 실측 최대 80 ms 였다.

## 5. 판정

H1 은 아래를 모두 만족할 때 알린다. 각 조건의 이유와 근거는 `fp-strategy.md`.

1. 공유 원소 3개 이상, 또는 2개이면서 Jaccard 0.5 이상(`reuse.min_shared` 로 조정).
2. 양쪽 중 적어도 하나가 정의(이름 붙은 바인딩, `type`). 둘 다 인라인(`if tool in (...)` 두 번)이면 알리지 않는다.
3. 같은 파일이면 둘 다 정의이고 50줄 이상 떨어져 있다.
4. 타입 ↔ 런타임 목록 짝은 §3 의 언어별 규칙을 따른다. 타입끼리는 원소가 같을 때만.
5. 상대 쪽이 `@copy-of`·`@dup-ok` 표시가 있는 묶음이거나 `Canonical copy:` 머리가 있는 파일과 그 정본의 짝이면 알리지 않는다.
6. 공유 원소가 모두 `reuse.vocab_ok` 안이면 알리지 않는다.
7. 다른 패키지(가장 가까운 `plugin.json`·`.claude-plugin/`·`Cargo.toml`·`package.json`·`pyproject.toml`·`wally.toml`·`pesde.toml`·`default.project.json`)이고 import 할 수 없으면 사본 문구(N2)를 쓰고, 양쪽이 모두 정의일 때만 알린다.

알림 단위: (세션, 호출한 쪽, 파일, 상대 정의)당 한 번, 파일당 세션에 최대 2번. compact 회차가 오르면 다시 알린다(`compact_epoch.py`).

## 6. 알림 문구

모두 `level="info"`, PostToolUse `additionalContext`. 중괄호는 채우는 값, `{c}` 는 그 파일의 주석 기호. `{shown}` 은 공유 원소 최대 5개를 따옴표로, 나머지는 `+N`.

N1 H1, 같은 패키지(import 가능):
```
<harness-hook name="qwreey-conventions" level="info">{rel}:{ln} adds a string set that repeats {name} at {orel}:{oln}: {k} of {n} strings shared ({shown}). If it is the same knowledge, reference that definition instead of keeping a second list; if it is a per-project value, move it to config. If they only look alike, put `{c} @dup-ok: <reason>` on the line above. Load the qwreey-conventions:code-reuse skill for the steps.</harness-hook>
```

N2 H1, 다른 패키지(import 불가):
```
<harness-hook name="qwreey-conventions" level="info">{rel}:{ln} adds a string set that repeats {name} at {orel}:{oln} in {opkg}, which this package cannot import: {k} of {n} strings shared ({shown}). If it is the same knowledge, mark this one `{c} @copy-of: {orel}#{name}` and add a test that compares the two; if they only look alike, `{c} @dup-ok: <reason>`. Load the qwreey-conventions:code-reuse skill for the steps.</harness-hook>
```

N3 C2, 정본을 바꿈:
```
<harness-hook name="qwreey-conventions" level="info">You changed {name} in {rel}:{ln}; {m} copies point to it with @copy-of: {list}. Update them in the same change, or run the test that compares them.</harness-hook>
```

N4 C1, 사본 표시가 풀리지 않거나 어긋남:
```
<harness-hook name="qwreey-conventions" level="info">The @copy-of mark at {rel}:{ln} points to {target}, which {does not resolve (no such file or name) | differs from this copy: missing {a}, extra {b}}. Fix the copy or the mark.</harness-hook>
```

N5 예외 무효:
```
<harness-hook name="qwreey-conventions" level="info">The @dup-ok mark at {rel}:{ln} has no reason ("{text}"). Say why the two lists are different knowledge, or remove the mark.</harness-hook>
```

N6 TS 타입 ↔ 목록 거울:
```
<harness-hook name="qwreey-conventions" level="info">{rel}:{ln} lists the same strings as the type {name} at {orel}:{oln}. Derive one from the other (`const X = [...] as const; type T = (typeof X)[number]`) so they cannot drift.</harness-hook>
```

한 편집에 여러 개면 한 블록 안에 `; ` 로 잇는다(conventions-check 와 같다). 첫 알림에만 `See the code-reuse rule (rules/code-reuse.md in the plugin).` 를 붙인다.

## 7. 예외 문법

- `@dup-ok: <사유>`: 묶음 첫 줄 바로 위 3줄 안의 주석. 사유 판정은 structure-reminder 의 `reason_ok()` 와 같은 기준(빈 말, "later", "TODO", "-", "나중에" 무효). 무효면 평소처럼 알리고 N5 를 덧붙인다.
- `@copy-of: <경로>#<이름>`: 같은 자리. `<경로>` 는 저장소 기준 상대 경로, 형제 저장소는 `<저장소>:<경로>`(harness.env `HARNESS_WORKSPACE` 로 푼다. 못 풀면 N4 대신 그림자 기록만, 다른 저장소가 없는 기계가 있으므로).
- 저장소 `.claude/conventions.json` `reuse.allow`: `[{"path": "<글롭>", "reason": "<사유>"}]`, 사유 판정은 같다.
- 파일 사본: 머리 700바이트 안의 `Canonical copy: <경로>` 는 `@copy-of` 와 같게 본다(지금 `tools/tests/test-vendored-copies.py` 가 읽는 표시).

## 8. 턴 끝 보고(기존 중복)

- PostToolUse 가 편집한 파일 안의 **추가하지 않은** 묶음 중 §5 를 만족하는 것을 세어, conventions-check 의 남은 주석 보고와 같은 파일(`$TMPDIR/claude-conventions/<sid>.left.<who>.json`)에 범주 `중복` 으로 넣는다.
- Stop 은 지금 reporter 그대로 한 줄 `systemMessage` 를 낸다. 순서 목록에 `중복` 을 더한다. 예: `손댄 파일에 기존 주석 문제가 남아 있음: a.luau(이력 3, 기호 12), b.rs(중복 2). 정리는 요청하실 때만.` 문구 머리는 "기존 주석 문제" 대신 "기존 문제" 로 바꾼다(중복은 주석이 아니므로).
- 보고 하나로 합치는 이유: Stop 의 `systemMessage` 는 모델 비용이 0이지만 줄이 둘이면 사용자가 읽을 것이 는다.

## 9. 그림자 모드와 관문

- 기록: `${CLAUDE_PLUGIN_DATA}/reuse-shadow.jsonl`(없으면 `$TMPDIR/claude-qwreey-reuse/shadow.jsonl`). 그림자일 때는 알리지 않고 기록만, 켰을 때도 계속 기록한다(켠 뒤 정밀도를 본다).
- 한 줄: `{"id": "<sha1 앞 12>", "t": <epoch>, "repo": "<루트 이름>", "lang": "rust|py|ts|luau", "check": "H1|H2|H6|C1|C2", "notice": "N1|N2|...|none", "at": "<rel>:<ln>", "other": "<rel>:<ln>", "name": "<정의 이름>", "shared": [..최대 8개, 각 40자..], "k": 3, "n": 5, "j": 0.6, "signals": {"def": [true, false], "same_pkg": true, "type": [false, false]}, "ms": 42, "budget": false}`. 본문·대화는 남기지 않는다.
- 표지 붙이기: claude-doctor `tools/` 에 스크립트 하나(`reuse-shadow-label.py`, 사용자 명령이 아니라 모델이 돌린다)가 표지 없는 줄을 양쪽 ±3줄 맥락과 함께 보인다. sonnet 이상 서브에이전트가 `labels.jsonl` 에 `{"id", "label": "TP|OK|FP", "why": "<한 줄>"}` 를 쓴다.
  - TP: 같은 지식이 두 벌, 알림대로 하면 나아진다.
  - OK: 같은 지식이지만 지금이 맞다(표시해야 할 사본, 바깥 API 의 고정 어휘). 정밀도 계산에서 TP 가 아니다(모델에게는 소음이므로).
  - FP: 다른 지식이 우연히 겹침.
- 확인: 표지의 20%를 다른 맥락의 검토자(`qwreey-advisor:reviewer` 류)가 다시 붙이고, 일치율 85% 미만이면 기준 문장을 고쳐 다시 붙인다.
- 관문: (검사, 언어)마다 알림이 될 기록 30개 이상, 정밀도 TP/(TP+OK+FP) 80% 이상이면 그 언어를 켠다. 30개가 안 되면 그림자를 늘린다. 켠 뒤 2주 동안 같은 계산이 70% 밑으로 내려가면 다시 그림자로.
- 첫 표지 집합: `fp-strategy.md` §3 의 31개 묶음(이 초안에서 붙임, 한 모델의 판단이라 위 확인 절차를 거치지 않았다).

## 10. 설정과 끄기

- `REUSE_CHECK=off|shadow|on` 환경 변수가 저장소 `reuse.mode` 를 이긴다. 기본은 그림자, 관문을 통과한 언어는 플러그인 판 올림으로 기본 `on`.
- `CONVENTIONS_CHECK=off` 는 이 훅도 끈다(같은 플러그인의 판정 훅 전체 스위치).

## 11. 파일 배치

- 새 스크립트 `hooks/reuse-check.py`. conventions-check.py 는 지금 874줄로 경고 기준(800)을 넘어 거기에 더하지 않는다.
- 렉서는 먼저 옮기기만 하는 커밋으로 `hooks/conv_lex.py` 로 빼고 두 스크립트가 import 한다(하이픈 이름 파일은 import 할 수 없어서). 같은 플러그인 안이라 사본이 아니다.
- `hooks.json` PostToolUse `Write|Edit|MultiEdit` 에 한 항목, timeout 5초.
