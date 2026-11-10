# snippet-markers — 스니펫 표식 문법과 하네스 사용법

## 이 파일이 답하는 질문
- Q1 `snippets/*.luau` 에 어떤 표식을 쓰나?
- Q2 버전마다 다른 동작은 어떻게 적나?
- Q3 `.luaurc` 나 옛 솔버가 필요한 스니펫은?
- Q4 하네스를 어떻게 돌리고, 결과표는 어떻게 만드나?
- Q5 새 주장을 references 에 추가하는 순서는?

## 목차
- §1 줄 끝 표식
- §2 머리 주석
- §3 하네스가 강제하는 규칙
- §4 실행과 결과표
- §5 새 주장을 추가하는 순서
- §6 다른 저장소의 표식 어휘

---

## §1 줄 끝 표식
status: verified · 근거: `tools/check_snippets.py`, 스니펫 38개 (`snippets/RESULTS.md`)

| 표식 | 뜻 | 통과 조건 |
|---|---|---|
| `-- expect-error` | 이 줄은 음성 대조군이다 | 그 줄에 TypeError/SyntaxError 가 1건 이상 |
| `-- expect-error: 부분문자열` | + 메시지 검사 | 그 줄의 메시지(이어진 줄 포함) 중 하나에 부분 문자열이 있음 |
| `-- bug-present` | 지금 잡히지 않는 알려진 한계 | 그 줄에 진단 0건. 진단이 생기면 "동작이 바뀜"으로 실패 |
| `… [<0.742]` 등 | 버전 조건. `<`, `<=`, `>`, `>=`, `=` 와 `x.y` | 조건이 맞는 버전에서만 그 표식이 살아 있다 |
| `A || B` | 한 줄에 표식 여럿(보통 버전별로 갈라 씀) | 각 버전에서 살아 있는 표식은 정확히 하나여야 함 |

예:
```luau
F(text, function(v: number) end) -- bug-present
local leaked: { string } = Map2({ 1, 2 }, function(v) return v end) -- bug-present [<0.742] || expect-error [>=0.742]
local s: string = c[1] -- bug-present [<0.742] || expect-error: number | string [>=0.742]
```

- 표식은 **코드 줄의 끝 주석**에만 쓴다. `--` 로 시작하는 순수 주석 줄의 표식 이름은 무시된다(설명문 오인 방지).
- 부분 문자열에는 ` || ` 를 쓸 수 없다.

## §2 머리 주석 (처음 20줄)
status: verified · 근거: `snippets/modes-*.luau`, `snippets/recursion-old-solver-rejects.luau`, `--@run` 스니펫 9개

| 머리 | 뜻 |
|---|---|
| `--@run` | 검사 통과 뒤 같은 버전의 `luau` 로 실행, rc=0 이어야 함. 런타임 증거(`assert`)를 둘 때 쓴다 |
| `--@run=lune` | lune 으로 실행(lune 은 `const` 를 못 읽는다. tooling.md) |
| `--@solver=old` | `--solver=old` 로 검사 |
| `--@luaurc {json}` | 임시 디렉터리에 이 내용의 `.luaurc` 를 두고 검사 |
| `--@args …` | `luau-analyze` 에 덧붙일 인자(예: `--mode=strict`) |
| `--@no-control 이유` | `bug-present` 가 있어도 대조군 없이 허용(짝 파일을 이유에 적는다) |

## §3 하네스가 강제하는 규칙
status: verified · 근거: 돌연변이 검사 4종(`snippets/RESULTS.md`)

1. 표식 없는 줄의 진단은 실패다(뜻밖의 진단도 정보다).
2. `expect-error` 줄에 진단이 없으면 실패다(검사기가 꺼진 0건 방지).
3. `bug-present` 가 있는 파일에는 그 버전에서 살아 있는 `expect-error` 가 하나 이상 있어야 한다.
4. 파일은 임시 디렉터리로 복사해서 검사한다. 상위 디렉터리의 `.luaurc` 가 끼어들지 않는다.
5. 검사는 `ulimit -v 2097152; timeout 120` 안에서 돈다. rc 가 0/1 이 아니면 실패다.
6. 린트(`LocalUnused` 등)는 판정하지 않는다.

## §4 실행과 결과표
status: verified

```bash
cd /code/Projects/luau-kb
python3 -I tools/check_snippets.py snippets/*.luau                         # 기본 0.742 (LUAU_VER 로 변경)
python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau      # 행렬, 하나라도 실패면 rc=1
python3 -I tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table snippets/*.luau > /tmp/t.md
```

- `--table` 은 `snippets/RESULTS.md` 의 표 형식으로 출력한다. 칸의 `E`/`B` 는 살아 있는 표식 수다.
- `--lsp` 열은 참고용이다. luau-lsp 가 어느 Luau 판을 내장했는지 하네스가 모르므로, 버전 조건이 섞인 줄은 판정하지 않고 "잡음/무진단"만 적는다.
- 파일 인자는 반드시 준다(glob 은 셸이 푼다). `-I` 는 현재 디렉터리의 파이썬 모듈이 끼어들지 않게 한다.

## §5 새 주장을 추가하는 순서
1. 라이브러리 없이 15줄 안팎으로 재현한다. 파일명은 `<주제>-<요지>.luau`(주제: generics, variance, unions, recursion, typefn, solver, modes, verify).
2. 머리 주석에 `-- 주장:` 과 `-- 근거:`(원천 경로와 절)를 쓴다.
3. 주장 줄에 `bug-present` 나 `expect-error` 를, 옆에 대조군을 둔다.
4. 두 버전으로 돌려 통과시킨다. 재현이 안 되면 주장을 고치거나 references 에서 `status: described` 로 둔다.
5. references 의 절에 `status: verified · last-confirmed: luau <ver> · 근거: snippets/<파일>` 을 단다.
6. `--table` 로 `snippets/RESULTS.md` 를 갱신한다.

## §6 다른 저장소의 표식 어휘
status: described · 원천: quad/scripts/doc-snippets.py 머리 docstring, stl-luau/.claude/tools/spike-diff.py

- quad 문서 펜스: 정보 문자열 `continue`(앞 블록에 이어 붙임), `skip`(검사도 실행도 안 함), `no-run`(검사만), `error=<ID>`(실행이 그 에러를 내야 함). 강제하는 닫힌 어휘다. 블록 안 줄 끝 `-- 타입 에러` 는 그 줄에 진단이 있어야 한다는 뜻이다. 시그니처만 있는 블록은 자동 제외된다.
- stl 스파이크: 소스에 표식을 넣지 않고 `scripts/spike-expectations.tsv` 에 `건수, 경로, 줄 목록` 을 둔다. `spike-diff.py` 가 줄별 건수를 대조해 어긋난 줄만 출력한다.
- 세 어휘는 같은 생각(기대 진단을 미리 적고 차이를 실패로)을 다른 매체에 적용한 것이다. 이 저장소 표식은 `.luau` 파일 정본용이다.
