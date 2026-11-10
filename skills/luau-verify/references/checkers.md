# checkers — luau-analyze 와 luau-lsp 직접 호출, 솔버 비교

## 이 파일이 답하는 질문
- Q1 `luau-analyze` 를 어떻게 부르나? 출력과 종료 코드는?
- Q2 `luau-lsp analyze` 로 Roblox 코드를 검사하려면 무엇이 필요한가?
- Q3 새 솔버와 옛 솔버, 두 luau 버전을 어떻게 비교하나?
- Q4 추론된 실제 타입을 보려면?
- Q5 CI 기준 검사기는 둘 중 무엇인가? (결정: D-06)
- Q6 공개 API 의 hover, 자동완성, 추론 타입 표시(DX)를 어떻게 확인하나? Claude Code 에서 luau-lsp 를 LSP 로 쓰려면?

## 목차
- §1 luau-analyze
- §2 luau-lsp analyze
- §3 비교 실행 (솔버 × 버전 × 도구)
- §4 추론 타입 보기
- §5 기준 검사기 (결정: D-06)
- §6 DX 검사 (hover, 자동완성, 추론 타입) 와 Claude Code LSP 연동

---

## §1 luau-analyze
status: verified · last-confirmed: luau 0.742 (`--help`, 수동 실행; `snippets/RESULTS.md` "스니펫 밖에서 실측한 것")

```bash
L=/code/.local/share/mise/installs/luau/0.742     # 버전 디렉터리 직접 (shim 함정은 toolchain.md)
"$L/luau-analyze" path/to/file.luau               # 새 솔버(기본)
"$L/luau-analyze" --solver=old path/to/file.luau  # 옛 솔버
"$L/luau-analyze" --annotate file.luau            # 추론 타입을 소스에 붙여 출력
```

- **진단은 stderr 로 나온다.** `2>/dev/null` 을 붙이면 0건처럼 보인다. 파이프에 넘길 때는 `2>&1` 을 붙인다.
- 형식: `./file.luau(줄,열): TypeError: 메시지`. 여러 줄 메시지는 다음 줄들에 이어진다(`Expected this to be` 다음 줄에 타입). 부분 문자열로 기대할 때는 이어진 줄까지 붙여서 본다.
- 종료 코드: TypeError/SyntaxError 가 있으면 1, 린트(`LocalUnused`, `LocalShadow` 등)만 있으면 0.
- 옵션은 `--mode`, `--solver`, `--formatter`, `--annotate`, `--timetrace` 뿐이다. **FFlag 를 바꾸는 옵션이 없다.** 한도 플래그 조정과 정의 파일 로딩이 필요하면 luau-lsp 를 쓴다.
- `--mode=strict` 는 `.luaurc` 도 `--!` 지시자도 없을 때의 기본값만 정한다(`snippets/modes-*.luau`).
- `.luaurc` 는 **검사하는 파일 기준으로** 상위 디렉터리에서 찾는다. 재현 파일을 다른 프로젝트 안에 두면 그 프로젝트의 `.luaurc` 가 끼어든다. 이 저장소 하네스는 파일을 임시 디렉터리로 복사해서 검사한다.
- Roblox 전역(`Instance`, `game`)을 모른다. 정의 파일 옵션이 없어 Roblox 코드는 luau-lsp 로 검사해야 한다.

## §2 luau-lsp analyze
status: verified · last-confirmed: luau-lsp 1.70.1 (수동 실행)

```bash
LSP=/code/.local/share/mise/installs/github-johnny-morganz-luau-lsp/1.70.1/luau-lsp
# 순수 Luau
"$LSP" analyze --platform=standard --flag:LuauSolverV2=true file.luau
# Roblox: 정의 파일 필수 (이 저장소 typedefs/), Rojo 프로젝트면 --sourcemap 도
"$LSP" analyze --platform=roblox --flag:LuauSolverV2=true \
  --definitions=/code/Projects/luau-kb/typedefs/globalTypes.d.luau [--sourcemap=sourcemap.json] file.luau
```

- `--platform=roblox` 인데 정의 파일이 없으면 경고를 내고 `Instance` 같은 전역을 모른다. analyze 는 정의 파일을 내려받지 않는다.
- 출력도 stderr 로 나오고, 진단이 있으면 rc=1 이다. 파일 경로에 `./` 접두가 없다.
- **옵션 없이 부르면 모든 Luau FFlag 를 켠 채 돈다**(`--no-flags-enabled` 로 끔). 에디터 확장은 `--no-flags-enabled` 와 동기화된 값으로 서버를 띄우므로, CLI 결과와 에디터 결과가 FFlag 하나 때문에 갈릴 수 있다. 실제로 `LuauDoNotExportBrokenTypeFunction` 때문에 다른 모듈의 type function 이 CLI 에서만 무효가 된 사례가 있다(quad typing-limits 8.18 정정, described).
- 한도 플래그 예: `--flag:LuauTarjanChildLimit=160000 --flag:LuauSubtypingIterationLimit=100000 --flag:LuauTypeInferIterationLimit=1000000`. 어떤 증상에 어떤 플래그가 듣는지는 luau-types 스킬의 recursion-and-limits 에 있다. 임시 프로브는 **CI 와 같은 플래그**로 돌린다. 플래그가 빠지면 too complex 로 무너진 자리의 진단이 조용히 사라진다(quad 8.28, described).
- luau-lsp 는 **자기가 내장한 Luau 판**으로 검사한다. 1.70.1 은 0.742 에서 고쳐진 맨 람다 누수(luau-types solver-limits S2)를 아직 가지고 있다. 에디터 판정과 CI 판정이 버전 때문에 다를 수 있다.

## §3 비교 실행 (솔버 × 버전 × 도구)
status: verified · 근거: `tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table`

```bash
for v in 0.734 0.742; do for s in new old; do
  echo "--- $v $s"; /code/.local/share/mise/installs/luau/$v/luau-analyze --solver=$s file.luau 2>&1 | grep -E 'TypeError|SyntaxError'
done; done
```

- 옛 솔버만 잡으면 새 솔버 결함 후보다. 단 옛 솔버는 `read`, `keyof`/`index`, `setmetatable<>` 타입, type function 을 모르므로, 그런 문법이 섞인 파일에서는 옛 솔버 결과가 의미 없다("read keyword is illegal here").
- 두 버전 결과가 다르면 그 줄에 버전 조건 표식을 단다(`snippet-markers.md`).
- 이 저장소의 스니펫 35개에서 `luau-lsp 1.70.1` 과 `luau-analyze` 의 판정은 버전 조건 줄을 빼면 같았다. 원천에는 큰 파일 하나에서 lsp 가 too complex 로 검사를 포기해 진단이 72건 대 68건으로 갈린 기록이 있다(stl, described). 일반화하지 않는다.

## §4 추론 타입 보기
status: verified · last-confirmed: luau 0.742

`luau-analyze --annotate file.luau 2>/dev/null` 은 지역마다 추론된 타입을 붙인 소스를 stdout 으로 낸다(예: `local a:'bbb'=f1('bbb')`). "0건인데 정말 그 타입인가"를 확인하는 가장 빠른 길이다. `unknown`, `*error-type*`, `never` 가 보이면 샌 것이다.

## §5 기준 검사기 (결정: D-06)
status: described · 원천: 사용자 결정 claude-doctor `decisions/D-06-type-checker.md` (2026-11-10), 이 저장소 `decisions/D-06-type-checker.md`; 결정 전 입장: stl-luau/.claude/base/typing-limits.md "체커: luau-analyze", stl mise.toml; quad/.claude/conventions.md 의 검사 게이트(quad/scripts/test.sh); rbvm/.claude/tools/check.sh

**결정**: "Roblox 전역 유무" 하나로만 고르지 않는다.
- **정확성 게이트**: 순수 Luau 는 `luau-analyze`, Roblox 전역을 쓰면 `luau-lsp analyze` + 정의 파일(+ sourcemap).
- **DX 확인**: 공개 API 를 가진 라이브러리는 순수 Luau 라도 luau-lsp 를 돌려 hover, 자동완성, 공개 API 의 추론 타입 표시를 본다(§6).

결정 전에 갈렸던 입장(기록):

| 입장 | 내용 | 근거 |
|---|---|---|
| luau-analyze 가 기준 (stl-luau) | 타입 게이트는 `luau-analyze` 로만. luau 배포판에 함께 오므로 실행기와 검사기 버전이 묶인다 | 같은 큰 파일에서 lsp 가 too complex 로 포기한 자리에 실제 버그 줄이 있었다 |
| 둘 다 게이트 (quad) | `luau-analyze`(엔진 무관 그룹)와 `luau-lsp`(Roblox 그룹, 한도 플래그와 정의 파일)를 모두 돌린다 | 정의 파일과 한도 플래그는 lsp 쪽에서만 쓸 수 있다. 사용자 에디터와 같은 조건 |
| luau-lsp 가 기준 (rbvm 등 Roblox 전용) | `luau-lsp analyze` + globalTypes + sourcemap, 에디터와 같은 `enableNewSolver` | Roblox 전역 없이는 검사가 성립하지 않는다 |

사실 정리: 순수 Luau 파일은 두 도구 모두 쓸 수 있다. Roblox 코드는 luau-lsp 만 가능하다. 한도 플래그는 luau-lsp 만 바꿀 수 있다. 두 도구의 Luau 판이 다를 수 있다.

## §6 DX 검사 (hover, 자동완성, 추론 타입) 와 Claude Code LSP 연동
status: verified · last-confirmed: luau-lsp 1.70.1 (새 솔버, 1.69.0 과 옛 솔버 일부 대조), Claude Code 2.1.316 · 근거: `tools/lsp_probe.py`, `tools/dx-sample/`, `tools/luau-lsp.sh`, `.lsp.json`

### 무엇을 보나
진단 0건은 "소비자가 쓰기 좋다"를 뜻하지 않는다. 주석 없는 공개 함수는 오류 없이 `unknown` 을 돌려줄 수 있다. DX 검사는 **소비자 파일에서** 에디터가 보여 줄 것을 확인한다.
1. 공개 함수·값의 **hover**: 매개변수 이름과 타입, 반환 타입이 구체적인가. `unknown`, `any`, `*error-type*`, 읽기 어려운 `t1 where t1 = {…}` 가 보이면 샌 것이다.
2. **자동완성**: `obj.` 뒤에 공개 멤버가 다 나오고 detail 타입이 구체적인가. 내부 필드가 노출되는가.
3. **inlay hint**: 소비자 변수에 붙는 추론 타입.
4. `---` 문서 주석이 hover 에 나오는가.
5. 결과를 도구, 버전, 솔버, platform 과 함께 적는다.

### 왜 스크립트가 필요한가
`luau-lsp` CLI 의 하위 명령은 `analyze`, `lsp`, `require-graph` 뿐이고 hover·자동완성을 묻는 명령이 없다. `--annotate` 는 지역 변수의 추론 타입만 보여 주고 hover 문자열, 자동완성 목록, 문서 주석은 보여 주지 않는다. 그래서 `lsp --stdio` 서버를 잠깐 띄워 JSON-RPC 로 묻는 `tools/lsp_probe.py`(표준 라이브러리만)를 둔다. 한 번 도는 데 순수 Luau 샘플 0.06초, Roblox 정의 파일을 실으면 0.6초였다.

```bash
P=/code/Projects/luau-kb/tools/lsp_probe.py
# 순수 Luau 라이브러리: 소비자 파일에서 묻는다. POS 는 1 기반 줄:열이나 '텍스트'('텍스트'@N 은 N 번째)
python3 -I $P tools/dx-sample/consumer.luau --hover 'new' --hover 'fromList(' --complete 'local n = s.' --inlay
# Roblox 코드
python3 -I $P src/Main.luau --root . --platform roblox \
  --defs /code/Projects/luau-kb/typedefs/globalTypes.d.luau --sourcemap sourcemap.json --hover 'part' --complete 'part.Anch'
# 대조: --old-solver, --lsp 1.69.0, --json, --diagnostics, --symbols, --expect-nonempty(빈 결과면 rc=3)
```

- hover 는 텍스트의 **시작** 자리, complete 는 텍스트의 **끝** 자리에서 묻는다.
- 서버는 자동완성 후보를 접두어와 무관하게 다 준다(`part.Anch` 에서 142개). 프로브는 에디터처럼 커서 앞 식별자로 거른다(`--no-filter` 로 끔).
- 설정(platform, 새 솔버, inlay hint 켜기, sourcemap)은 `workspace/configuration` 응답으로 넘긴다.

### 실증 (`tools/dx-sample/`, luau-lsp 1.70.1 새 솔버, platform standard)

| 질의 (consumer.luau) | 결과 |
|---|---|
| hover `top` (`local top = s:pop()`) | `local top: number?` |
| hover `new` | `function Stack.new<T>(): Stack.Stack<T>` + 문서 주석 `빈 스택을 만든다.` (1.69.0 도 같음) |
| hover `fromList(` (주석 없는 공개 함수) | `function Stack.fromList<T, U>(list: { [T]: U }): Stack.Stack<unknown>`. 옛 솔버는 `Stack.fromList<T>(list: T): Stack.Stack<*error-type*>` |
| hover `push` (`s:push(1)`) | `function Stack:push(self: Stack.Stack<number>, value: number): ()`. 타입 필드 위 `--- 맨 위 값을 넣는다.` 는 나오지 않았다 |
| hover 지역 `fromList` | `t1 where t1 = { items: {unknown}, … }` 에 `Stack.new` 의 문서 주석이 붙어 나왔다 |
| hover 모듈 지역 `Stack` | `new: <T>(...any) -> t2` — 함수 자체 hover(`new<T>()`)와 달리 모듈 테이블 hover 에서는 매개변수 없는 함수가 `(...any)` 로 보였다 |
| complete `local n = s.` | `size`·`push`·`pop`(Function, detail `(Stack<number>, number) -> ()` 등), `items`(Field `{number}`) 4개 |
| inlay | `fromList` 지역에 `: Stack<unknown>` |
| hover `local` 키워드 (음성 대조) | 빈 결과, `--expect-nonempty` 로 rc=3 |

Roblox(정의 파일 + platform roblox): hover `part` → `Part`, `players` → `Players`, `Touched:Connect(function(hit)` 의 `hit` → `BasePart`, complete `part.Anch` → `Anchored  Field  boolean`. 정의 파일 없이는 `*error-type*` 이고 platform 이 standard 면 `hit` 이 `unknown` 이다(roblox-luau 스킬 `typedefs.md` §1).

읽는 법: `fromList` 처럼 주석이 없으면 진단 0건이어도 소비자에게 `unknown` 이 보인다. 공개 함수의 매개변수와 반환은 주석을 단다.

### Claude Code LSP 연동 (`.lsp.json`)

```json
{ "luau": { "command": "${CLAUDE_PLUGIN_ROOT}/tools/luau-lsp.sh",
            "extensionToLanguage": { ".luau": "luau" }, "startupTimeout": 30000 } }
```

- `tools/luau-lsp.sh` 가 바이너리와 플랫폼을 고른다. 바이너리: `$LUAU_LSP_BIN` → 프로젝트 디렉터리에서 `mise which luau-lsp`(프로젝트 핀, shim 경로는 버림) → `$MISE_DATA_DIR/installs/github-johnny-morganz-luau-lsp/` 의 가장 높은 버전. 플랫폼: 프로젝트 루트에 `*.project.json` 이나 `sourcemap.json` 이 있으면 roblox(`--definitions=@roblox=typedefs/globalTypes.d.luau`, sourcemap 사용, 자동 생성 끔), 아니면 standard. 기본 설정은 `--settings=tools/lsp/settings-<platform>.json`(새 솔버, inlay hint 켬). `.lua` 는 다른 Lua 프로젝트를 건드리지 않도록 넣지 않았다.
- 검증 결과:
  - `claude plugin validate /code/Projects/luau-kb` → `✔ Validation passed`.
  - `claude -p --model sonnet --plugin-dir /code/Projects/luau-kb` 의 init 메시지 도구 목록에 `LSP` 가 있었다. 모델이 `LSP` 도구로 `consumer.luau` 6줄 7열 hover 를 부르자 `local top: number?` 가, 7줄 7열은 프로브와 같은 `fromList` 문자열이 왔다. 편집하지 않았는데도 모델 답에 그 파일의 진단(`LocalUnused`, 8줄 SyntaxError)이 들어 있었다.
- Claude Code 클라이언트가 실제로 보낸 initialize 능력(래퍼의 `LUAU_KB_LSP_LOG` 로 기록): `workspace.configuration: false`, hover, definition, references, documentSymbol, callHierarchy, publishDiagnostics. **completion, inlayHint, pull diagnostic 능력은 없다.** 그래서 Claude Code 의 `LSP` 도구로는 자동완성 목록과 inlay hint 를 볼 수 없고, 그 둘은 `lsp_probe.py` 로 본다. 도구 입력의 줄·열은 1 기반이고(서버에는 0 기반으로 보냄) 공식 문서 기준 연산은 정의 이동, 참조 찾기, 위치의 타입 정보, 문서 심볼, 작업 공간 심볼 검색, 구현 찾기, 호출 계층이다.
- **설정 전달 실측(luau-lsp 1.70.1)**: 클라이언트가 `workspace.configuration` 능력을 알리지 않으면 `--settings` 파일이 쓰인다. 키는 평평한 `"luau-lsp.platform.type"` 꼴이어야 하고, 중첩 `{"luau-lsp": {…}}` 꼴은 무시됐다. 클라이언트가 능력을 알리고 `null` 로 답하면 `--settings` 가 무시됐다. `workspace/didChangeConfiguration` 페이로드만으로는 반영되지 않았다. 그래서 `.lsp.json` 의 `settings` 필드 대신 래퍼의 `--settings` 를 쓴다.
- **`validate` 가 잡지 못하는 것**: 문서상 `.lsp.json` 의 서버 설정은 strict 라 알 수 없는 키가 있으면 로드에 실패한다. 사본에 `bogusKey` 를 넣고 돌린 결과 `claude plugin validate` 는 `✔ Validation passed` 였지만(`plugin.json` 에 `lspServers` 를 선언해도 같음), `claude -p` 에서 `LSP` 도구가 사라졌다. `.lsp.json` 을 고친 뒤에는 init 도구 목록에 `LSP` 가 있는지까지 본다.
- 문제 추적: `LUAU_KB_LSP_LOG=/tmp/x.log claude …` 로 띄우면 래퍼가 고른 바이너리·플랫폼과 클라이언트가 보낸 메시지를 남긴다. Claude Code 는 `didChangeWatchedFiles` 동적 등록을 지원하지 않는다고 알린다. `analyze` 는 같은 조건에서 "sourcemap 변경 자동 반영 꺼짐" 경고를 냈으므로, 세션 중 sourcemap 을 다시 만들면 서버가 모를 수 있다(LSP 세션에서는 미검증).
