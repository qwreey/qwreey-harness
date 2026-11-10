# luau-kb

여러 Luau 저장소(quad, stl-luau 등)에 흩어져 있던 **일반 Luau 지식**(타입 시스템의 한계, 검증 절차)을 한 곳에 모은 정본 저장소다. 모든 "verified" 주장은 `snippets/` 의 실행 가능한 재현 파일과 짝이고, 그 파일은 luau 0.734 와 0.742 에서 하네스로 검사된다. 프로젝트 고유 설계(특정 라이브러리의 타입 이름, API)는 넣지 않는다.

- Claude Code: 플러그인으로 설치해 스킬 `luau-kb:luau-types`, `luau-kb:luau-verify`, `luau-kb:roblox-luau` 로 쓴다. `.lsp.json` 이 luau-lsp 를 LSP 도구로 붙인다(`.luau` 파일의 진단, hover, 정의 이동).
- Gemini, Codex 등: `AGENTS.md` 가 같은 references 를 평문 경로로 안내한다.

## 구조

```
.claude-plugin/
  plugin.json            name: luau-kb
  marketplace.json       로컬 마켓플레이스 luau-kb-market (source "./")
skills/
  luau-types/            SKILL.md (결정 트리 + 증상→파일 표) + references/ 6개
    references/          generics, variance, unions-singletons, recursion-and-limits, type-functions, solver-limits
  luau-verify/           SKILL.md + references/ 5개
    references/          negative-controls, checkers(§6 DX 검사), toolchain, snippet-markers, tooling
  roblox-luau/           SKILL.md + references/ 5개 (Roblox 엔진 의존 동작 검증)
    references/          env-dependence, mocks, studio-mcp, api-docs, typedefs
snippets/                *.luau 38개 (주장 하나에 파일 하나) + RESULTS.md (버전 행렬 결과, 강등 목록)
tools/
  check_snippets.py      스니펫 하네스 (표식: -- expect-error[: 부분], -- bug-present, [버전 조건], --@run 등)
  repro-stylua-typeargs.sh   stylua 가 f<<T>> 를 망가뜨리는 조건 재현
  lsp_probe.py           luau-lsp 를 stdio 로 잠깐 띄워 hover·자동완성·inlay·진단을 묻는 DX 프로브
  luau-lsp.sh, lsp/      .lsp.json 이 부르는 래퍼(바이너리·플랫폼 선택)와 --settings 파일
  dx-sample/             DX 프로브 실증용 샘플(Stack 라이브러리 + 소비자)
.lsp.json                Claude Code LSP: luau-lsp (tools/luau-lsp.sh)
typedefs/                globalTypes.d.luau (quad 판 복사) + README.md (다른 복제본 7개와 md5 비교)
rules/                   README 만 (경로 조건부 공통 규약 자리, 다른 작업에서 채움)
decisions/               README(미결 목록) + 결정 요약 D-03(러너), D-06(검사기)
AGENTS.md                다른 에이전트용 진입점
```

references 의 절마다 `status: verified | described`, `last-confirmed: luau <ver>`, 근거 스니펫이나 원천 경로가 붙어 있다. 정책이 저장소마다 갈린 항목은 한쪽을 고르지 않고 `> 정책: 미정 — decisions/ 참고` 로 표시했다.

## 설치 (Claude Code)

```bash
claude plugin marketplace add /code/Projects/luau-kb
claude plugin install luau-kb@luau-kb-market
```

로컬 경로 마켓플레이스는 파일을 직접 읽으므로, 수정한 뒤 `/reload-plugins` 하면 반영된다. 호스팅 설치본을 쓸 때는 `plugin.json` 의 `version` 을 올려야 갱신된다.

## 검증

```bash
cd /code/Projects/luau-kb
claude plugin validate /code/Projects/luau-kb
python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau
tools/repro-stylua-typeargs.sh
python3 -I tools/lsp_probe.py tools/dx-sample/consumer.luau --hover 'new' --complete 'local n = s.' --expect-nonempty
```

필요한 도구는 `/code/.local/share/mise/installs/` 아래 버전 경로로 직접 부른다(PATH 의 mise shim 은 버전이 정해지지 않은 디렉터리에서 실패한다). 다른 머신에서는 `MISE_DATA_DIR` 이나 `LUAU_BIN_DIR` 을 맞춘다.

### 마지막 검증 결과 (2026-11-10)

| 검사 | 결과 |
|---|---|
| `claude plugin validate /code/Projects/luau-kb` (Claude Code 2.1.316) | **✔ Validation passed, rc=0**. 디렉터리 제출용 부가 검사는 LICENSE 없음과 아이콘 없음을 알렸다. 이 둘은 통과 여부에 영향이 없고, 라이선스 선택은 사용자 몫이라 비워 두었다 |
| `python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/*.luau` | **38개 × 2 버전 전부 ok, rc=0** (표: `snippets/RESULTS.md`) |
| 하네스 돌연변이 검사 4종 | 전부 FAIL 로 잡힘 (`snippets/RESULTS.md`) |
| `tools/repro-stylua-typeargs.sh` (stylua 2.5.2) | rc=0 (설정 없음 → 오염, `syntax = "Luau"` → 보존) |

## 원천과 범위

- 원천(읽기 전용): `/code/Projects/quad/.claude/base/typing-limits.md`, `/code/Projects/stl-luau/.claude/base/typing-limits.md`, `stl-luau/.claude/audit/luau-solver-issues/`, `stl-luau/.claude/tools/{spike-diff.py,mutate.sh}`, `quad/scripts/doc-snippets.py`, 각 저장소의 `mise.toml`, `conventions.md`. `quad-changelog-check` 는 낡은 사본이라 근거로 쓰지 않았다.
- 원문을 옮기지 않고 다시 썼다. 원천에서 다시 재 보니 뒤집힌 주장(싱글턴 보존, type function 안 `pcall`/`error()`, stylua 오염 조건)은 정정했다. 재현하지 못한 주장은 `described` 로 남겼다. 목록은 `snippets/RESULTS.md` 끝에 있다.
- 아직 없는 것(설계안 claude-doctor audit 05 §4 기준): `luau-perf`, `luau-testing` 스킬, 업스트림 보고용 `luau-solver-bug-triage`, `luau-recheck`. 타입 팩·가변 인자, Instance/Enum 타입, Actor/Parallel Luau 는 원천에도 정리본이 없다.

## 기여 규칙

1. 새 사실은 `snippets/<주제>-<요지>.luau` 최소 재현과 표식부터 넣는다. 대조군 줄을 함께 둔다.
2. 두 버전에서 하네스가 rc=0 인지 확인하고, `--table` 로 `snippets/RESULTS.md` 를 갱신한다.
3. references 절에 `status`, `last-confirmed`, 근거를 단다. SKILL.md 는 100줄 이하로 두고 라우팅 표만 고친다.
4. 정책 판단이 필요한 항목은 `decisions/README.md` 의 미결 목록에 올린다.
