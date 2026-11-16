---
format: 1
title: 사람이 읽기 좋은 코드 규약 문구 초안 (기본 지시 대조, 문구, 지표, 훅, 쓰기 실측 설계)
description: 기본 지시엔 코드 모양 규칙이 없어 전부 하네스 몫. 상시 rule readable-code 5줄을 HARNESS_READABLE_CODE 로 켜고, 15줄 넘는 함수의 빈 줄 없음/20줄 이어짐(사용자 3/26, 에이전트 68/75)을 info 알림 기준으로
status: landed in plugins/qwreey-conventions/rules/readable-code.md
---
# 사람이 읽기 좋은 코드 규약 문구 초안

근거와 사용자 설명은 `.claude/research/drafts/readable-code.md`. 이 문서는 그 진행 순서 1~3단계(기본 지시 대조, 문구, 쓰기 실측 설계)와 사용자 추가 요청(응집도 지표, lint, 문서 주석 유지)을 담는다. 설치나 플러그인 파일 수정은 하지 않았다.

## 1. 기본 지시 대조

### 방법
- `claude -p` 2.1.316, sonnet, 빈 `CLAUDE_CONFIG_DIR`(자격 증명 파일만 복사, 끝나고 지움), `--setting-sources ''`, `--strict-mcp-config`, 빈 git 폴더에서. 호출 2번, 합계 USD 0.10.
- 모델에게 인용을 시키는 것만으로는 못 믿으므로, 같은 실행의 기록(`projects/*/*.jsonl` 의 `api-request-shape`)에서 실제로 보낸 system 블록과 도구 설명 전문을 꺼내 낱말 검색(comment, naming, abstraction, backward, defensive, unused, blank line, style, helper, validation, minimal)도 했다.
- 일반 서브에이전트: 같은 조건에서 `general-purpose` 서브에이전트(sonnet)를 띄워 인용시키고, 그 서브에이전트 기록의 system 블록 전문을 확인했다.

### 결과
- 메인 기본 지시: 코드 주석, 빈 줄, 이름, 방어 코드, 주석 처리한 코드, 쓰지 않는 변수, 파일 길이, 도우미·추상화, 스타일에 관한 문장이 **없다**. 예전 판의 "Do not add comments unless asked" 같은 줄도 지금은 없다. 코드와 닿는 줄은 `Reference code as file_path:line_number` 와 Edit 도구의 일치 규칙(`old_string must match the file exactly, including indentation`)뿐이다.
- 모델 인용(메인): `NONE: code comments / naming / defensive code / commented-out code / unused variables / file length / abstractions or helpers / general code style`.
- 일반 서브에이전트 지시에서 가까운 두 줄(코드 모양이 아니다):
  - "Complete the task fully—don't gold-plate, but don't leave it half-done."
  - "NEVER create files unless they're absolutely necessary for achieving your goal. ALWAYS prefer editing an existing file to creating a new one."
- 그러므로 "기본 지시와 겹쳐서 뺄 항목"은 없다. 겹침은 하네스 안(qwreey-conventions, luau-kb)에서만 따진다. 에이전트 코드의 모양(빈 줄 없음, 본문 안 긴 이유)은 지시가 아니라 학습된 습관이다.

### 항목 표
표기: 기본 = Claude Code 기본 지시, 하네스 = 지금 qwreey-conventions·luau-kb 에 있음, 새 = 둘 다 없음, 날카롭게 = 하네스에 비슷한 말이 있으나 이 근거와 다르거나 약함.

| 항목 | 판정 | 지금 있는 곳 / 할 일 |
|---|---|---|
| 주석은 왜를, 코드를 되풀이하지 않음 | 하네스 | `rules/comments.md`, comments 스킬 Style. 라벨과의 관계만 고친다(4절) |
| 이력은 커밋으로 | 하네스 | comments rule. 그대로 |
| 키보드 문자, 주석 언어는 파일을 따름 | 하네스 | comments rule·스킬, luau quality §1. 그대로 |
| 배너 금지 | 하네스 | comments 스킬 Style. 그대로 |
| 파일 길이 | 하네스 | `rules/code-structure.md` + structure-reminder. 그대로 |
| 쓰지 않는 변수 | 도구 | luau-analyze `LocalUnused`, 각 언어 린터. 문구 없음 |
| 주석 처리한 코드, 자기 불변식 방어 | 새(근거 약함) | 사용자 표본에 0 이지만 대조 수치가 없다. 이번 문구에 넣지 않고 미정에 둔다 |
| 10줄 넘는 함수는 빈 줄 문단, 짧은 함수는 빈 줄 없음 | 새 | 상시 rule |
| 단계 라벨(해석표) | 새 | 상시 rule + 스킬 절. comments 스킬의 "Do not restate the code" 와 관계를 적는다 |
| 이유는 선언 위, 본문 사이에 여러 줄 이유를 끼우지 않음 | 날카롭게 | comments 스킬 Style 의 "Length" 줄이 비슷하나 위치를 말하지 않는다. 상시 rule |
| 공개 함수 문서 주석, 첫 줄은 팝업 한 줄 요약 | 날카롭게 | luau quality §1 "선언 문서는 `---`" 만 있다. 상시 rule(일반) + luau quality §1(세부) |
| 선언은 첫 사용, 가장 좁은 블록; 공용 핸들은 위 한 덩어리; 루프 상태는 루프 직전 | 새 | 상시 rule 한 줄 + 스킬 절 |
| 한 선언에 이름 하나(다중 반환 받기 예외) | 새 | 상시 rule 같은 줄 |
| 한 역할 한 이름, 짝은 대칭 이름, 한 글자 지역 없음 | 새 | 상시 rule 한 줄(앞 둘) + 스킬 절(한 글자). luau naming §4 의 "한 글자 별칭은 정체를 밝힌다" 와는 범위가 다르다(모듈 별칭) |
| 4갈래 이상 분기 사다리 갈래마다 라벨, 빈 갈래도 남김 | 새 | 스킬 절 |
| 형제 모듈은 같은 멤버 순서와 라벨 | 날카롭게 | luau-style 1절 "이웃 모듈 관행을 따른다"(케이스 위주). 스킬 절 |
| 같은 몇 줄 루프가 되풀이되면 도우미로 | 날카롭게 | code-reuse 는 "이미 있는 도우미를 찾아라"까지. 자기 코드 안 되풀이는 없다. 상시 rule 한 줄 |
| Luau 캐스트는 좁게, 한 번이면 그 자리, 여러 번이면 이름 붙인 뷰 | 새(Luau) | luau-style idioms 새 §9 |
| 한국어 주석은 파일의 기존 어미를 따름 | 새 | comments 스킬 Language (켜고 끄는 대상 아님) |

## 2. 실측 지표 (사용자 코드 대 에이전트 코드)

### 표본과 방법
- 스크립트: `/tmp/rc-metrics/metrics.py`, `report.py`(정리 대상 임시 파일. 지표 정의는 아래 표가 정본). Luau 렉서는 문자열·긴 주석을 걷어 내고 `function`/`do`/`then`/`repeat` 와 `end`/`until` 로 가장 바깥 함수의 범위를 찾는다(중첩 콜백은 바깥 함수 본문에 포함).
- 귀속: rbvm, tbox 는 `git blame` 으로 줄마다 커밋을 찾아 `Co-Authored-By` 꼬리가 없는 커밋을 사용자로 본다(tbox `7d47c8a` 제외; rbvm 꼬리는 `Claude Opus 5`, tbox 꼬리는 `qwreey (Opus 5.5)`). 함수 줄의 80% 이상이 한쪽이면 그쪽, 아니면 버린다. stl-luau `src/`, quad `quad-base/src/` 는 꼬리 관행이 없는 에이전트 저장소라 통째로 에이전트 대조군.
- 표본: 본문 10줄 이상(빈 줄 제외) 함수 사용자 36(rbvm 32, tbox 4), 에이전트 132(tbox 38, stl 46, quad-base 46, rbvm 2). tbox 사용자 긴 함수는 뒤 에이전트 수정으로 4개만 남아 사용자 쪽은 사실상 rbvm 이다.

### 지표 정의 (함수 단위, 본문 = 머리 줄과 `end` 사이)
| 지표 | 정의 |
|---|---|
| nonblank | 본문의 빈 줄이 아닌 줄 수. 문단 지표는 10줄 이상에서만 본다 |
| blank_ratio | 본문 빈 줄 / 본문 줄 |
| has_blank | 본문에 빈 줄이 하나라도 있나 |
| max_run | 빈 줄 없이 이어진 가장 긴 줄 수(주석 줄 포함) |
| mean_para, n_paras | 문단(빈 줄로 나뉜 덩어리) 평균 길이와 개수 |
| label | 한 줄짜리 주석 덩어리이고, 위가 빈 줄이나 본문 시작, 아래가 코드, 낱말 1~10, 마침표로 끝나지 않음 |
| label_coverage | 3줄 이상 문단 중 라벨로 시작하는 비율 |
| cblock_mean/max | 본문 안 주석 덩어리(이어진 주석 줄) 크기 |
| interleaved_multi | 바로 위와 아래가 코드인 2줄 이상 주석 덩어리 수(문장 사이에 끼운 여러 줄 이유) |
| comment_ratio, trailing_ratio | 본문 주석 줄, 줄 끝 주석 비율 |
| doc_lines, doc_triple, doc_first_len | 머리 줄 바로 위 주석 줄 수, `---` 인가, 첫 줄 글자 수. 본문 밖이라 뭉침 지표에 넣지 않는다 |

### 결과 (본문 10줄 이상, 중앙값/평균)
| 지표 | rbvm 사용자(32) | tbox 사용자(4) | tbox 에이전트(38) | stl(46) | quad-base(46) | AUC 사용자>에이전트 |
|---|---|---|---|---|---|---|
| blank_ratio | 0.11/0.10 | 0.12/0.13 | 0.00/0.02 | 0.00/0.00 | 0.00/0.01 | 0.87 |
| has_blank | 1/0.78 | 1/1.00 | 0/0.18 | 0/0.00 | 0/0.13 | 0.85 |
| n_paras | 4/3.84 | 4/4.00 | 1/1.47 | 1/1.00 | 1/2.13 | 0.84 |
| mean_para | 6.2/7.8 | 5.6/5.1 | 17/17.9 | 14/18.6 | 15/18.5 | 0.11 |
| max_run | 12/12.7 | 9/9.3 | 17/19.2 | 14/18.6 | 16.5/22.2 | 0.30 |
| label_coverage | 0.14/0.39 | 0/0 | 0/0 | 0/0 | 0/0 | 0.71 |
| interleaved_multi | 0/0.06 | 0/0 | 0/0.50 | 0/0.17 | 0/1.37 | 0.38 |
| cblock_mean | 1.0/1.03 | 0/0.25 | 1.0/1.22 | 0/0.56 | 0/1.65 | 0.53 |
| doc_lines | 0/0.28 | 0.5/0.75 | 0/0.63 | 1/1.76 | 0.5/2.80 | 0.31 |

- 본문 사이에 끼운 여러 줄 주석 덩어리: 본문 100줄당 사용자 0.19, 에이전트 2.09.
- 본문 안 주석 줄의 종류(모든 함수): rbvm 사용자 라벨 44, 한 줄 19, 여러 줄 덩어리 46, 줄 끝 10. 에이전트 쪽은 라벨이 거의 없고(tbox 1, quad 4) 여러 줄 덩어리 비중이 0.57~0.82.
- 라벨 낱말 수(사용자 44개): 2낱말 11, 3~6낱말 29, 7~10낱말 4. 영어 98%. 예: `Check cache first`, `Detach previous parent first`, `Unwrap proxy to Instance`, `Emit parent changed`. 사용자 말 "3~10단어"보다 2낱말이 많다(`Clear vChildren`, `Already same`).
- 짧은 함수(3~9줄)에 빈 줄: rbvm 사용자 2/18, tbox 사용자 1/7, stl 0/65, quad 0/55. "짧은 함수엔 빈 줄 없음"은 양쪽 모두 지켜 가르는 지표가 아니다.
- 뭉침 지표(cblock 크기)는 함수 단위로는 가르지 못한다(AUC 0.53). 에이전트 함수 대부분이 본문 주석 0이라서다. 가르는 것은 "끼운 여러 줄 덩어리"와 파일 단위 "본문 안 주석 중 여러 줄 덩어리 비중"이다.
- 문서 주석: 공개 함수(`function M.x`, `function M:x`, `M.x = function`) 중 문서가 있는 것 rbvm 사용자 11/60(그중 `#region` 표지 섞임), tbox 에이전트 14/16, quad-base 14/35, stl 6/13. **에이전트 문서는 거의 `--` 라 luau-lsp 호버와 자동완성에 안 보인다**(`---` 줄 수: rbvm 10, tbox 15, stl 0, quad-base 1). 첫 줄 길이 중앙값: tbox 에이전트 62(이유 문장이 이어짐), quad-base 79(이력 표지 포함), stl 44.5.

### 알림 기준 후보 (본문 15줄 이상 함수)
| 조건 | 사용자 걸림 | 에이전트 걸림 |
|---|---|---|
| 빈 줄 없음 | 2/26 (8%) | 61/75 (81%) |
| max_run >= 20 | 2/26 (8%) | 43/75 (57%) |
| **빈 줄 없음 또는 max_run >= 20** | 3/26 (12%) | 68/75 (91%) |
| mean_para >= 12 | 2/26 | 66/75 |
| 끼운 여러 줄 덩어리 >= 1 | 2/26 (8%) | 31/75 (41%) |
| 라벨 0 | 12/26 (46%) | 70/75 (93%) |

- 라벨 0 은 사용자도 절반이 걸려 알림 조건으로 쓰지 않는다(라벨은 자명한 단계에서 생략 가능하다는 사용자 말과 맞다). 숫자로만 보인다.
- 제안 기준: 본문 15줄 이상이고 (빈 줄 없음 또는 빈 줄 없이 20줄 넘게 이어짐) 이면 layout 알림, 끼운 여러 줄 덩어리는 따로 한 범주. 표본이 사실상 rbvm 한 저장소라 기준은 저장소 설정으로 바꿀 수 있게 한다.

### luau-lsp 가 보여 주는 문서 주석 (1.70.1, 새 솔버, `packs/luau-kb/tools/lsp_probe.py` 를 고친 임시 사본으로 `completionItem/resolve` 까지)
- 자동완성 목록 줄은 이름과 `detail`(타입 `(any) -> any`)만 보인다. 문서는 항목을 고르면 열리는 문서 칸에, 호버는 시그니처 아래에 나온다.
- 둘 다 `---` 블록 또는 `--[=[ ... ]=]` 블록 **전체**를 마크다운으로 준다. 서버는 자르지 않는다(152자 첫 줄도 그대로). 그래서 폭은 에디터 문서 칸이 정하고, 첫 줄이 길면 감겨서 요약이 첫 눈에 안 들어온다.
- 빈 `---` 줄은 문단 나눔, `@param`/`@return` 은 `**Parameters**`/`**Returns**` 절로 바뀐다.
- `--` 한 줄 주석은 호버에 **나오지 않는다**. 선언 바로 위에 이어진 `---` 만 붙는다(luau quality §1 과 같음).
- 그래서 첫 줄 지침: 한 문장 요약, 약 80자 이내(문서 칸 한 줄), 세부는 빈 `---` 줄 뒤.

## 3. 문구 초안

### 3.1 상시 rule: `plugins/qwreey-conventions/rules/readable-code.md` (새 파일, 약 230 토큰)
code-reuse 와 같은 paths. 켜고 끄기는 3.4.

```markdown
---
description: Layout of code for a human reader (paragraphs, step labels, where explanations go, declarations, names). Details in the qwreey-conventions:comments skill, section Readable code
paths: [<code-reuse.md 와 같은 코드 글롭>]
switch: HARNESS_READABLE_CODE
---
# Readable code
- In a function longer than about 10 lines, separate its steps (guards, each unit of work, final checks, the return) with single blank lines; a short function has none.
- Head a paragraph whose intent is not obvious with a step label: English, 2-10 words, shorter than the code line, naming what the step is for, with no period, numbering or reason. Reading only the labels should give the function's flow. A label summarizes several lines for navigation; restating one line in words is still noise.
- What a function does for callers goes in a doc comment above it, in the form the editor shows on hover and completion (Luau `---`, Python docstring, `/** */`). Public functions in code others call always get one. Its first sentence ends on the first line, about 80 characters; details follow after a blank doc line.
- Reasons for a design go in a plain comment above the declaration, apart from the doc comment so hover stays about use. Inside a body a reason is one line at the trap, after the step label; never a multi-line block between statements.
- Declare a local at its first use in the narrowest block (handles every step uses go together at the top, loop state right before the loop), one name per declaration except when receiving multiple returns. One role keeps one name across the file; paired operations get symmetric names.
- When the same few-line loop appears a second time, extract a helper instead of copying it.
- Examples, branch ladders, sibling modules and toolkit details: load the `qwreey-conventions:comments` skill, section Readable code. A repo's own rules win.
```

빼서 스킬로 보낸 것(상시 비용 대비 근거가 약하거나 드물게 쓰임): 분기 사다리 라벨, 형제 모듈 순서, 한 글자 지역, Luau 캐스트, 한국어 어미. 쓰기 실측(5절)에서 상시 줄 없이 지켜지지 않고 효과가 크면 올린다.

### 3.2 comments 스킬에 더할 절 (`skills/comments/SKILL.md`, 새 절 `## Readable code`; readable-code 가 꺼진 저장소에서는 rule 이 안 실려 이 절을 부르지 않는다)
summary: 주석 종류별 자리(문서 주석은 위, 라벨은 문단 머리, 함정은 그 줄 한 줄), 예시 함수, 문단, 선언, 이름, 분기 사다리, 형제 모듈, 되풀이 루프, layout 알림 대응


```markdown
## Readable code

Applies when the readable-code rule is loaded (it is switched per user and per repo). A reader scans code by shape before reading it: blank lines show where one step ends, short comment lines in another color show what each step is for, and the doc comment above a function says what it gives a caller. Each kind of comment has one place.

| Kind | Where | Shape |
|---|---|---|
| Doc comment | Above a function, type or module, in the hover form (Luau `---` or `--[=[ ]=]`; `--` never shows) | First sentence ends on the first line, about 80 characters (it is what a completion popup or hover shows first). Details after a blank doc line. Public functions in code others call always get one, even with a clear name; metamethods and private helpers get one only when the name does not say it. |
| Design reason | Plain comment above the declaration, separate from the doc comment | As long as the reason needs; hover shows the doc comment only, so callers are not handed the history of the design. |
| Step label | First line of a paragraph inside a body | English, 3-10 words (2 is fine when it reads), shorter than the code width, names the step's intent. No period, no numbering, no reason. Skip it when the code says it (`return result`). |
| Trap note | At the line, inside the body, below the paragraph's step label | One line. A longer reason moves above the declaration. |

Example (the labels alone read as the flow):

    local function reparent(proxy, newParent)
        local data = proxyData[proxy]
        if data.parent == newParent then
            return
        end

        -- Detach from the previous parent
        local oldChildren = childrenOf(data.parent)
        removeValue(oldChildren, proxy)

        -- Attach under the new parent
        table.insert(childrenOf(newParent), proxy)
        data.parent = newParent

        -- Notify listeners
        data.parentChanged:Fire(newParent)
    end

Not a label: `-- Increment the counter` above `count += 1` (restates one line), `-- 1. Validate` (numbered), `-- Detach first because the old parent caches children.` (a reason with a period; put it above the function or keep one line at the trap).

Paragraphs:
- Steps of a function over about 10 lines are separated by one blank line: guards, each unit of work, checks after it, the final return. No blank lines inside a short function, and never two in a row.
- A long literal (table, list of cases) is one step even when long.

Declarations:
- Declare at first use, in the narrowest block that needs it. Handles every step uses (services, the object's data table) go together at the top of the function; state for a loop goes right before the loop.
- One name per declaration (`local a = 1` and `local b = 2`, not `local a, b = 1, 2`). Receiving multiple returns (`local ok, err = pcall(f)`) is the exception.

Names:
- One role keeps one name across the file (`data` for an object's state table everywhere, not `data`, `state` and `info`). Paired operations get symmetric names (`attach`/`detach`, `wrap`/`unwrap`).
- No one-letter locals except loop indices; a one-letter module alias states what it is where it is declared.

Branches and siblings:
- A ladder of 4 or more cases (`if`/`elseif`, match tables) gives each case a short label, including a case that deliberately does nothing; keep that case rather than deleting it, so a reader sees it was considered.
- Modules that implement one interface (sibling kinds, proxies of one base) keep the same member order and the same step labels, so a reader who knows one can find their way in the next.

Repetition:
- The second time the same few-line loop is needed, extract a helper and call it from both places; copies of a loop drift apart and each copy needs its own fix.

Hook notice: a `layout` notice gives per-function numbers (lines, blank lines, longest run without a blank line, multi-line comment blocks between statements). They are evidence, not a verdict: if the function really is one step (a literal, a single expression), leave it and say so once.
```

### 3.3 comments 스킬 기존 줄 고침 (켜고 끄기와 무관하게 늘 맞는 말)
- Style 의 "Silence where nothing is surprising. Do not restate the code, label sections with banners, or describe an obviously named function." 를 다음으로:
  > Silence where nothing is surprising. Do not restate a line of code in words, draw banners, or describe an obviously named private function. A short step label above a paragraph is not a restatement: it names what several lines are for, so a reader can skim labels as an index (section Readable code).
- 같은 절 예시 끝에 한 줄: `-- Good (step label above a paragraph): Detach from the previous parent`
- Language 절에 한 줄: `- Korean comments follow the sentence ending the file already uses (합니다체 or 한다체); a new file follows its siblings.`
- comments rule(`rules/comments.md`)은 고치지 않는다. "Write why" 는 이유 주석의 규칙이고 라벨은 readable-code 가 꺼지면 아예 안 쓰는 것이라, 늘 실리는 rule 에 라벨 예외를 쓸 필요가 없다.

### 3.4 Luau 쪽 (luau-kb)
- `skills/luau-style/references/quality.md` §1 의 "선언 문서는 `---` 로 쓴다" 다음에:
  > - 공개 함수(다른 모듈이 부르는 것)에는 `---` 문서를 단다. luau-lsp 1.70.1 은 선언 바로 위에 이어진 `---` 와 `--[=[ ... ]=]` 만 호버와 자동완성 문서 칸에 싣고, `--` 는 싣지 않는다. 서버는 자르지 않으므로 첫 줄을 한 문장 요약(약 80자)으로 두어 문서 칸 첫 줄에 들어오게 하고, 세부는 빈 `---` 줄 뒤에 쓴다. `@param`/`@return` 은 Parameters/Returns 절로 그려진다.
- `skills/luau-style/references/idioms.md` 새 §9 캐스트:
  > - 캐스트는 다음 줄들이 필요로 하는 가장 좁은 타입으로 한다(`:: any` 대신 `:: TypedNamespace`).
  > - 한 번 쓰면 쓰는 자리에서 캐스트한다. 같은 값을 여러 번 쓰면 이름 붙인 뷰 지역을 한 번 만든다(`local typedNs = ns :: TypedNamespace`). 쓰는 곳마다 `(x :: any).field` 를 되풀이하지 않는다.
  > - 근거: tbox 사용자 줄의 `:: any` 2/42, 에이전트 줄 22/47.
- `rules/luau-core.md` "Names and comments" 에 한 줄(luau-kb 를 켠 모든 저장소에 실리므로 사용자 확인 필요):
  > - Public functions in code others call (a library, a module other modules require) get a `---` doc comment (luau-lsp shows only `---` and `--[=[ ]=]` in hover and completion, never `--`); first line a summary of about 80 characters. → `[quality§1](../skills/luau-style/references/quality.md)` (link relative to `packs/luau-kb/rules/`)
- 캐스트는 luau-core 에 올리지 않는다(상시 비용, 근거는 tbox 한 저장소).

### 3.5 켜고 끄기
지금 장치: `rules_inject.py` 는 `HARNESS_CONVENTIONS_RULES=off`(harness.env 층)로 전부 끄고, 저장소 `.claude/conventions.json` 의 `rules_exclude: ["<rule>"]` 로 rule 하나를 뺀다. 사용자별로 rule 하나를 켜는 장치는 없다.

제안:
- rule frontmatter 의 `switch: <KEY>` 를 `rules_inject.py` 가 읽어 `conv_env.env_value(KEY).lower() == "on"` 일 때만 싣는다. `switch` 없는 rule 은 지금과 같다. 플러그인 기본은 꺼짐(동료 배포에서 개인 취향이 퍼지지 않게).
- 사용자: 자기 `~/.claude/harness.env` 에 `HARNESS_READABLE_CODE=on` 을 직접 적는다. 정본 `home/` 에는 넣지 않는다(동료가 같은 `home/` 을 받으면 퍼지므로; 사용자 "개인 기본값은 그쪽에 두는것 괜찮은것 같아"). `home/.claude/harness.env` 에는 주석 처리한 예시 줄만 둔다.
- 저장소 끄기: 팀 공유는 `.claude/harness.env` 에 `HARNESS_READABLE_CODE=off`, 개인은 `.claude/harness.local.env`. harness.env 층은 높은 층의 빈 값·off 가 이긴다(`lib/harness_env.py` 16행). 기존 `rules_exclude: ["readable-code"]` 도 그대로 먹는다.
- 같은 키가 conventions-check 의 layout 알림(4절)도 켜고 끈다. 언어 불일치의 라벨 예외는 키와 무관하게 늘 둔다(잘못된 알림을 없애는 것뿐이라).
- 주의: `rules_inject.py` 는 coderag Rust 훅의 팩 rule 주입과 대조 기준이다(플러그인 CLAUDE.md). `switch` 는 플러그인 rule 에만 쓰고 팩 rule 에는 쓰지 않으면 coderag 동작은 같지만, 대조 시험(`tools/tests/test-coderag-rules-parity.py`)이 `rules_inject.py` 를 복사해 돌리므로 `switch` 없는 rule 결과가 같음을 시험에 한 줄 더한다. 팩에도 쓰려면 coderag 에 같은 변경이 필요하다.

## 4. 훅 변경

### 4.1 언어 불일치: 한국어 주석 파일 안 영어 라벨
지금(`plugins/qwreey-conventions/hooks/conventions-check.py`):
- 106~113행: 낱말은 라틴 3글자 이상 연속(`SCRIPT_WORDS["latin"]`), `LANG_MIN_LINES = 10`, `LANG_SHARE = 0.9`, `LANG_MIN_WORDS = 3`.
- 214행 `comment_stats`, 226행 `majority`: 파일의 주석 줄 중 한 문자 체계가 90% 이상이고 10줄 이상이면 그것이 기대 언어.
- 264~278행 `language_lines`: 추가된 주석 줄마다 다른 체계 낱말이 2개 이상이고 기대 체계보다 많으면 걸리고, 걸린 줄들의 낱말 합이 3 이상이면 모두 알린다. 645~647행이 부르고, `scripts/conventions-scan.py` 176~178행도 같은 함수를 쓴다.
- 확인(임시 실행): 한국어 주석 12줄 파일에 `-- Detach previous parent first` 한 줄을 더하면 걸린다(낱말 4). `-- Clear vChildren`(낱말 2) 하나는 안 걸리지만 2낱말 라벨 둘이면 합 4 로 둘 다 걸린다.
- 두 번째 문제: 라벨이 쌓이면 `comment_stats` 가 라벨도 세어 한국어 비율이 90% 밑으로 내려가고, 그러면 파일 자체 기준이 사라져 저장소 `comment_language` 나 형제 다수로 넘어간다.

제안:
- `is_step_label(rows, lines, i)` 를 더한다. 참이면 언어 판정과 다수 계산에서 그 줄을 뺀다.
  - 그 줄은 주석만 있고(`not rows[i]["code"]`), 주석 조각이 하나다.
  - 바로 위 줄이 주석만 있는 줄이 아니고(한 줄짜리 덩어리), 바로 아래 줄에 코드가 있다.
  - 들여쓰기가 있다(함수 본문 안).
  - 라틴 낱말 1~10개, 한글·가나·한자 없음, 72자 이하, 마침표로 끝나지 않음.
  - 이유 접속어가 없다: `\b(because|since|so|otherwise|unless|must|never|in order to|to avoid)\b`(대소문자 무시). 이유 문장은 계속 걸려야 해서다.
- `comment_stats(rows, skip)` 와 `language_lines` 에서 `is_step_label` 인 줄을 건너뛴다. `language_lines` 는 기대 체계가 latin 이 아닐 때만 건너뛴다(영어 파일 안 라벨은 원래 안 걸린다).
- 설정: `.claude/conventions.json` 의 `"label_language": "en"`(기본). `null` 이면 예외를 끈다.
- 비용: 줄마다 정규식 둘, 위·아래 줄 보기. 표준 라이브러리만.

시험(`tests/test-conventions-check.py` 186행 언어 묶음 옆):
1. 한국어 다수 파일, `\n\t-- Detach previous parent first\n\tparent = nil\n` 추가 -> 알림 없음.
2. 2낱말 라벨 두 개 추가 -> 알림 없음.
3. 기존 187행 `-- Clamp the index so reads stay in range` -> 여전히 걸림(`so`).
4. 마침표로 끝나는 영어 한 줄, 11낱말 영어 한 줄, 영어 두 줄 덩어리, 들여쓰기 없는 영어 한 줄 -> 각각 걸림.
5. 한국어 주석 10줄 + 영어 라벨 3줄 파일에 영어 이유 문장 추가 -> 걸림(라벨이 다수 계산을 흐리지 않음).
6. `label_language: null` 이면 1 이 걸림.
7. `tests/test-conventions-scan.py` 에 1 과 같은 파일로 scan 이 language 를 내지 않는지.

### 4.2 layout 알림 (지표를 근거로, info, 막지 않음)
자리 검토:
- `structure-reminder.py`: 파일 길이와 폴더 모양을 보고 Bash 편집도 추적한다. 함수 범위를 알려면 언어별 파서가 필요하고, 이 훅의 상태는 파일 단위다. 맞지 않는다.
- `conventions-check.py`: 이미 렉서 결과(`rows`), 이번에 추가한 줄 집합, (파일, 범주) 한 번 알림 상태가 있고, 라벨 판정(4.1)을 같이 쓴다. 여기가 맞다. 다만 695줄이라 함수 범위 찾기와 지표는 새 모듈 `hooks/layout_metrics.py` 로 둔다(표준 라이브러리; Lua 계열은 키워드 블록, Python 은 들여쓰기, C 계열은 중괄호 깊이).
- `scripts/conventions-scan.py`: 파일 전체를 보는 도구라 `layout` 하위 명령으로 함수별 숫자와 파일 요약(문서 주석 범위 포함)을 낸다. 고치지 않는다. 5절 쓰기 실측의 채점도 이것을 쓴다.
- PLAN 의 "읽기 어려운 코드 알림(빈 줄 없이 길게 이어진 코드, 주석이 한곳에 몰림)" 항목이 이것이다.

동작:
- PostToolUse(Write|Edit|MultiEdit), `HARNESS_READABLE_CODE=on` 이고 `CONVENTIONS_CHECK` 가 꺼지지 않았을 때. 이번 편집이 새로 만들었거나(함수 줄의 절반 이상을 썼거나) 빈 줄 아닌 줄을 15줄 이상 더한 함수만 본다. 후자가 없으면 기존 함수 키우기(audit 55 E1)를 못 잡는다. 알림 끝에 `[grown by N lines]` 를 붙인다.
- Bash 로 고친 파일(python heredoc, sed)은 이 훅이 못 본다(audit 55 에서 45회 중 약 13회). `bash-bypass-reminder` 가 이미 그런 편집을 알리므로, 그 알림에 "readable-code 가 켜져 있으면 `conventions-scan.py layout <file>` 로 확인" 한 줄을 더한다.
- 범주 `layout`: 본문 15줄 이상이고 (빈 줄 없음 또는 빈 줄 없이 20줄 넘게 이어짐). 범주 `interleaved comment`: 본문 안에서 위아래가 코드인 2줄 이상 주석 덩어리. 범주 `doc summary`: 공개 함수에 문서 주석이 없거나(Luau 는 `---`/`--[=[` 가 아니면 없음으로 셈) 첫 줄이 100자 넘음.
- 문서 주석은 본문 밖이라 뭉침으로 세지 않는다.
- `doc summary`: 없을 때 문구에 그 언어의 형태를 적는다(Luau "`---` doc comment; `--` is not shown on hover"). 메타메서드(`__tostring` 등)는 뺀다. 한 번 알린 함수도 다음 편집 뒤 여전히 없으면 한 번 더 알린다(audit 55 L1-D-2 가 `--` 로 답하고 끝났다).
- 첫 줄 검사는 길이만이 아니라 "첫 문장이 첫 줄에서 끝나는가"(첫 줄이 `.` `?` `!` 나 콜론 없이 끝나고 다음 줄이 이어지는 문장이면 걸림)도 본다(audit 55 B 4/15, D 5/14).
- 문구 예(영어, `HOOK-MESSAGES.md` 형식, nonce 붙임):
  `foo.luau: functions you edited read as one block: reparent L40-78 (34 lines, 0 blank lines, longest run 34); wrap L90-121 (a 4-line comment block between statements at L101). For comparison, the user's functions of this size have about 4 paragraphs and runs under 13 lines. If these have steps, separate them with blank lines and short labels; if a function is one step (a literal, one expression), leave it.`
- (파일, 범주)당 한 번, compact 회차마다 다시. Stop 보고에는 넣지 않는다(기존 코드 문제가 아니다).
- 기준은 `.claude/conventions.json` 의 `"layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100}` 로 바꿀 수 있게 한다. `doc_first_max` 를 80 이 아닌 100 으로 두는 것은 알림이 지침보다 느슨해야 잡음이 적어서다.
- 시험: 빈 줄 없는 20줄 함수 추가 -> layout; 빈 줄로 4문단인 같은 함수 -> 없음; 9줄 함수 -> 없음; 위아래가 코드인 3줄 주석 -> interleaved; 공개 함수 위 `--` 한 줄 -> doc summary; 꺼진 키 -> 없음.

## 5. 쓰기 실측 설계 (돌리지 않음)

### 과제 (각 과제에 정답 시험 하나를 붙여 정확성도 본다)
- L1 (Luau, rbvm 류): 가상 부모·자식 표와 신호가 있는 고정 모듈에 `reparent(proxy, newParent)` 와 `destroy(proxy)` 를 더한다. 자연스러운 단계: 같은 부모 확인, 옛 부모에서 떼기, 새 부모에 붙이기, 알림, 반환. 자식 목록에서 값 지우기 루프가 두 함수에 다 필요하다(도우미 추출을 본다).
- L2 (Luau, tbox 류): `check(schema, value, path)` 를 kind 5가지(string, number, array, object, optional)로 짠다. 분기 사다리 라벨, 캐스트, 이름 일관성을 본다. 공개 함수 둘(`check`, `assert`)의 `---` 문서와 첫 줄 길이도.
- L3 (Luau, 형제 모듈): `Circle.luau`(멤버 순서·라벨이 있는 기존 파일)를 주고 같은 인터페이스의 `Rect.luau` 를 쓰게 한다. 멤버 순서 일치와 라벨 재사용을 본다.
- P1 (Python): 로그 파일 여러 개를 읽어 요약을 내는 `summarize(paths)` (열기·파싱·집계·정렬·출력 다섯 단계, 함수 40~60줄 규모). 일반 항목(빈 줄 문단, 라벨, 선언 위치, 한 선언 한 이름)이 Luau 밖에서도 먹는지 본다.

### 조건
- A: 1절과 같은 깨끗한 설정(규칙 없음).
- B: A + 3.1 rule 을 고정 저장소의 `.claude/rules/readable-code.md` 로 두고 `--setting-sources project`(공식 rules 는 맞는 파일을 Read 할 때 실리므로 플러그인 주입과 같은 시점).
- C(선택): B + 3.2 스킬 절을 rule 본문에 붙인 것(스킬을 불렀을 때의 상한).
- 모델: opus(사용자 기본 수행자)와 sonnet. 프롬프트는 과제만 주고 스타일을 말하지 않는다.

### 채점
- 기계 지표(`conventions-scan.py layout` 또는 `/tmp/rc-metrics` 스크립트를 Python 에 넓힌 것; Python 은 `ast` 로 함수 범위, `tokenize` 로 주석): 본문 15줄 이상 함수의 "빈 줄 없음 또는 20줄 넘게 이어짐" 비율(사용자 12%, 에이전트 91%), blank_ratio, n_paras, mean_para, label_coverage, 라벨 낱말 수 분포와 3~10 안 비율, 라벨의 영어·마침표·번호 비율, 끼운 여러 줄 덩어리 100줄당 수(사용자 0.19, 에이전트 2.09), 본문 주석 비율, 공개 함수 `---` 범위와 첫 줄 길이, 한 선언 여러 이름 수, 선언에서 첫 사용까지 줄 거리 중앙값, 같은 루프 복사 수(정규화한 3~6줄 창이 두 번 이상), L3 멤버 순서 Kendall tau.
- 라벨 해석표 시험: 판정 모델에게 함수의 시그니처와 주석만(코드 지우고) 보여 주고 흐름을 단계로 적게 한 뒤, 과제의 정답 단계 목록과 겹친 비율을 잰다. 사용자 말 "주석만 보고 흐름을 알게"를 직접 잰다.
- 눈가림 판정: 같은 과제의 A·B 결과를 짝으로, 이름표 없이 opus 에게 "단계 X 를 찾기 쉬운가, 흐름이 보이는가, 호출하는 쪽에게 문서가 충분한가" 를 1~5 로 매기고 어느 쪽이 나은지 고르게 한다. 순서 치우침을 막으려 짝마다 순서를 바꿔 두 번.
- 정확성: 과제 시험 통과율. 출력 토큰 차이.

### 표본과 비용
- 1차(시범): opus 만, 과제 4 x 조건 A·B x 3회 = 24회. 과제당 약 USD 0.4 -> 약 USD 10, 판정 12짝 x 2순서 x 약 USD 0.06 + 해석표 시험 24회 x 약 USD 0.03 -> 약 USD 2. 합계 약 USD 12.
- 2차(효과가 애매하거나 sonnet 도 볼 때): 과제 4 x A·B·C x 5회 x 모델 2 = 120회, sonnet 약 USD 0.15, opus 약 USD 0.4 -> 약 USD 33, 판정 약 USD 6. 합계 약 USD 40.
- 실행은 `choom -n 1000 -- timeout 600 claude -p ... --max-budget-usd 1 </dev/null`, 과제마다 새 임시 저장소. 비용은 사용자 판단이라 1차 뒤 결과와 함께 2차를 묻는다.
- 채택 기준(제안): B 에서 15줄 이상 함수의 "빈 줄 없음 또는 긴 줄 이어짐" 이 50% 밑, 라벨 해석표 겹침이 A 보다 뚜렷이 높음, 눈가림 판정에서 B 선호 2/3 이상, 정확성 하락 없음. tbox CLAUDE.md 의 "밀도와 톤을 따르라" 한 줄은 바꾸지 못했으므로, B 가 못 바꾸면 C 와 layout 알림(4.2)의 조합을 본다.

## 미정
- 플러그인 기본을 꺼 둘지(동료 배포에서 사용자 취향을 퍼뜨리지 않음) 켜 둘지. 초안은 꺼 둠 + 사용자 층 on.
- luau-core 에 `---` 문서 한 줄을 올릴지(luau-kb 를 켠 모든 저장소에 실림).
- 라벨 길이: 사용자 말은 3~10낱말, 사용자 코드는 2낱말이 25%. 초안은 "3-10, 2 도 읽히면 됨".
- 한 글자 지역: 루프 인덱스를 예외로 둘지(rbvm 은 0 이지만 루프 인덱스를 세었는지 근거 탐사에서 확인 안 됨).
- 주석 처리한 코드, 자기 불변식 방어: 대조 수치를 더 모은 뒤.
- 상시 문구 5줄은 토론(진행 순서 4단계)과 쓰기 실측(5절)을 거쳐 확정한다.
- 지표 표본이 사실상 rbvm 하나(사용자 긴 함수 36 중 32). 사용자 손 코드가 더 생기면 기준을 다시 잰다.
