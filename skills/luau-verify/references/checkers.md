# checkers — luau-analyze 와 luau-lsp 직접 호출, 솔버 비교

## 이 파일이 답하는 질문
- Q1 `luau-analyze` 를 어떻게 부르나? 출력과 종료 코드는?
- Q2 `luau-lsp analyze` 로 Roblox 코드를 검사하려면 무엇이 필요한가?
- Q3 새 솔버와 옛 솔버, 두 luau 버전을 어떻게 비교하나?
- Q4 추론된 실제 타입을 보려면?
- Q5 CI 기준 검사기는 둘 중 무엇인가? (정책 미정)

## 목차
- §1 luau-analyze
- §2 luau-lsp analyze
- §3 비교 실행 (솔버 × 버전 × 도구)
- §4 추론 타입 보기
- §5 기준 검사기 정책 (미정)

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

## §5 기준 검사기 정책 (미정)
status: described · 원천: stl-luau/.claude/base/typing-limits.md "체커: luau-analyze", stl mise.toml; quad/.claude/conventions.md 의 검사 게이트(quad/scripts/test.sh); rbvm/.claude/tools/check.sh

> 정책: 미정 — decisions/ 참고

| 입장 | 내용 | 근거 |
|---|---|---|
| luau-analyze 가 기준 (stl-luau) | 타입 게이트는 `luau-analyze` 로만. luau 배포판에 함께 오므로 실행기와 검사기 버전이 묶인다 | 같은 큰 파일에서 lsp 가 too complex 로 포기한 자리에 실제 버그 줄이 있었다 |
| 둘 다 게이트 (quad) | `luau-analyze`(엔진 무관 그룹)와 `luau-lsp`(Roblox 그룹, 한도 플래그와 정의 파일)를 모두 돌린다 | 정의 파일과 한도 플래그는 lsp 쪽에서만 쓸 수 있다. 사용자 에디터와 같은 조건 |
| luau-lsp 가 기준 (rbvm 등 Roblox 전용) | `luau-lsp analyze` + globalTypes + sourcemap, 에디터와 같은 `enableNewSolver` | Roblox 전역 없이는 검사가 성립하지 않는다 |

사실 정리(정책과 무관): 순수 Luau 파일은 두 도구 모두 쓸 수 있다. Roblox 코드는 luau-lsp 만 가능하다. 한도 플래그는 luau-lsp 만 바꿀 수 있다. 두 도구의 Luau 판이 다를 수 있다.
