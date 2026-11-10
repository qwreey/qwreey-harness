# luau-kb

여러 Luau 저장소(quad, stl-luau, rbvm, table-sim, devplorer, tbox 등)에 흩어져 있던 **일반 Luau·Roblox 지식**을 한 곳에 모은 정본 저장소다. 타입 시스템의 한계, 검증 절차, 테스트, 성능 실측, 코드 스타일, Roblox 엔진 동작, 업스트림 변화를 다룬다. 모든 "verified" 주장은 `snippets/` 의 실행 가능한 재현 파일(성능 수치는 `bench/`)과 짝이고, 그 파일은 luau 0.734 와 0.742 에서 하네스로 검사된다. 프로젝트 고유 설계(특정 라이브러리의 타입 이름, API)는 넣지 않는다.

- Claude Code: 플러그인으로 설치해 스킬 `luau-kb:luau-types`, `luau-kb:luau-verify`, `luau-kb:luau-testing`, `luau-kb:luau-perf`, `luau-kb:luau-style`, `luau-kb:luau-runtime`, `luau-kb:luau-roblox`, `luau-kb:roblox-engine`, `luau-kb:roblox-net`, `luau-kb:roblox-world`, `luau-kb:roblox-docs`, `luau-kb:luau-upstream` 으로 쓴다. `.lsp.json` 이 luau-lsp 를 LSP 도구로 붙인다(`.luau` 파일의 진단, hover, 정의 이동). `rules/` 의 경로 조건부 규칙은 사용자 홈 `~/.claude/rules/` 에 symlink 로 건다(`rules/README.md`).
- Gemini, Codex 등: `AGENTS.md` 가 같은 references 를 평문 경로로 안내한다.

## 구조

```
.claude-plugin/
  plugin.json            name: luau-kb
  marketplace.json       로컬 마켓플레이스 luau-kb-market (source "./")
skills/
  luau-types/            SKILL.md (결정 트리 + 증상→파일 표) + references/ 8개
    references/          generics, packs-and-varargs, variance, unions-singletons, recursion-and-limits,
                         type-functions, type-functions-limits, solver-limits
  luau-verify/           SKILL.md + references/ 5개
    references/          negative-controls, checkers(§6 DX 검사, §7 require 검사기 대 런타임), toolchain, snippet-markers, tooling
  luau-testing/          SKILL.md + references/ 7개
    references/          runners, assertions, optimize-levels, negative-controls, roblox-boundary, gc-and-time, repo-practices
  luau-perf/             SKILL.md + references/ 9개 (수치는 bench/)
    references/          benchmarking-method, metatables, tables, iteration, calls-and-closures, strings,
                         optimizer-and-native, gc-and-memory, algorithms-and-structures
  luau-style/            SKILL.md + references/ 8개 + scripts/
    references/          naming, idioms, modules, structure, errors, pitfalls, quality, project-overrides
  luau-runtime/          SKILL.md + references/ 3개 (Roblox 엔진 없이 성립하는 언어·런타임 의미론)
    references/          gc-and-weak-tables, coroutines, require-by-string
  luau-roblox/           SKILL.md + references/ 5개 (Roblox 위 Luau 의 타입과 검증: mock, Studio MCP, 정의 파일)
    references/          env-dependence, mocks, studio-mcp, api-types, typedefs
  roblox-engine/         SKILL.md + references/ 9개 (엔진 핵심 런타임)
    references/          signals-and-events, instance-lifecycle, instance-api, tween-and-animation, tasks-and-threads,
                         parallel-luau, require-in-roblox, gc-in-roblox, perf
  roblox-net/            SKILL.md + references/ 2개 (원격·복제·플랫폼 서비스)
    references/          remotes-and-replication, platform-services
  roblox-world/          SKILL.md + references/ 2개 (GUI·물리·캐릭터)
    references/          gui-and-input, world-and-physics
  roblox-docs/           SKILL.md + references/ 1개 (tools/roblox_docs.py 사용법)
    references/          sources
  luau-upstream/         SKILL.md + references/ 5개
    references/          sources, watchlist, syntax-adoption, version-bump, roadmap-notes
rules/                   luau-core.md(**/*.luau), code-structure.md(안내만: 정본은 ~/.claude/rules/code-structure.md), README.md(배포 방식과 로드 실측)
snippets/                *.luau 152개(주장 하나에 파일 하나, 접두가 담당: perf- rbx- style- test- opt- native- pack- tf- …)
                         + *.sh 셸 하네스(require·stylua·cross-module) + RESULTS.md (버전 행렬 결과, 강등 목록)
bench/                   성능 벤치 19개 + lib/ 하네스 + run.sh + RESULTS.md, results/*.tsv (luau-perf 근거)
tools/
  check_snippets.py      스니펫 하네스 (표식: -- expect-error[: 부분], -- bug-present, [버전 조건], --@run 등)
  repro-stylua-typeargs.sh   stylua 가 f<<T>> 를 망가뜨리는 조건 재현
  lsp_probe.py           luau-lsp 를 stdio 로 잠깐 띄워 hover·자동완성·inlay·진단을 묻는 DX 프로브
  luau-lsp.sh, lsp/      .lsp.json 이 부르는 래퍼(바이너리·플랫폼 선택)와 --settings 파일
  dx-sample/             DX 프로브 실증용 샘플(Stack 라이브러리 + 소비자)
  upstream_check.py      업스트림 릴리스·RFC 확인 (luau-upstream)
  roblox_docs.py         Roblox/creator-docs 원본을 캐시에 받아 search·get·api 로 조회 (roblox-docs)
.lsp.json                Claude Code LSP: luau-lsp (tools/luau-lsp.sh)
typedefs/                globalTypes.d.luau (quad 판 복사) + README.md (다른 복제본 7개와 md5 비교)
decisions/               README(미결 목록) + 결정 요약 D-01(const), D-02(stylua), D-03(러너), D-04(type function), D-06(검사기)
AGENTS.md                다른 에이전트용 진입점 (주제가 여러 스킬에 걸칠 때의 정본 위치 포함)
coderag.toml             coderag pack 매니페스트 (모듈 = 스킬 디렉터리 12개, 목차 절 제외)
taxonomy.toml            coderag 분류 어휘 (범주 경로·별칭·review_days). references 의 category 가 이 경로를 쓴다
```

references 파일마다 frontmatter(`title`·`description`·`keywords`·`category`·`tags`·`last_verified`·`last_confirmed`)가 있다. coderag 로 검색할 때 쓰는 메타이고, 형식은 coderag tech-design §17, 범주는 `taxonomy.toml`. 새 reference 를 더하면 frontmatter 를 같이 쓰고 `coderag lint` 로 확인한다. 긴 절(~1.5k 토큰 넘고 표·코드로 시작)은 메타 줄에 `summary:` 한 줄을 둔다.

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
python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau
tools/repro-stylua-typeargs.sh
python3 -I tools/lsp_probe.py tools/dx-sample/consumer.luau --hover 'new' --complete 'local n = s.' --expect-nonempty
```

필요한 도구는 `/code/.local/share/mise/installs/` 아래 버전 경로로 직접 부른다(PATH 의 mise shim 은 버전이 정해지지 않은 디렉터리에서 실패한다). 다른 머신에서는 `MISE_DATA_DIR` 이나 `LUAU_BIN_DIR` 을 맞춘다.

### 마지막 검증 결과 (2026-11-10)

| 검사 | 결과 |
|---|---|
| `claude plugin validate /code/Projects/luau-kb` (Claude Code 2.1.316) | **✔ Validation passed, rc=0**. 디렉터리 제출용 부가 검사는 LICENSE 없음과 아이콘 없음을 알렸다. 이 둘은 통과 여부에 영향이 없고, 라이선스 선택은 사용자 몫이라 비워 두었다 |
| `python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau` | **세 버전 각 137 ok(총 ok 441줄), rc=0** (표: `snippets/RESULTS.md`) |
| `snippets/rbx-require-cli.sh`, `verify-require.sh`, `style-require-paths.sh` | 전부 ok, rc=0 |
| 하네스 돌연변이 검사 4종 | 전부 FAIL 로 잡힘 (`snippets/RESULTS.md`) |
| `tools/repro-stylua-typeargs.sh` (stylua 2.5.2) | rc=0 (설정 없음 → 오염, `syntax = "Luau"` → 보존) |
| 스킬 경계 트리거 (`claude -p --model sonnet --plugin-dir`, 질문 6개 × 2회 + require 2개 재측 × 2회) | 16/16 기대 스킬이 먼저 호출됨. 질문별 cwd 를 나눠야 한다(같은 cwd 동시 실행 1건이 여러 스킬을 연달아 부름) |
| roblox-luau 분리 트리거 (2026-11-10, `claude -p --model sonnet --plugin-dir`, 질문 25개 × 2회, 질문마다 새 cwd) | **47/50** 기대 스킬이 먼저 호출됨. 어긋난 3회는 모두 스킬 미호출(v2 "mise shim No version is set" 2회는 사용자 CLAUDE.md 가 직접 답해서, 옛 luau-verify description 으로도 0/2. rt3 1회). 나눔 비교: 스킬 넷(엔진 하나로 묶음) 23/26, 여섯(긴 description) 44/44, 여섯(짧은 description, 채택) 43/44 → 실제 저장소 47/50. 상시 문맥 비용(`ok` 한 번의 입력 토큰): 분리 전 15,724, 채택안 약 16,826 |

## 원천과 범위

- 원천(읽기 전용): `/code/Projects/quad/.claude/base/typing-limits.md`, `/code/Projects/stl-luau/.claude/base/typing-limits.md`, `stl-luau/.claude/audit/luau-solver-issues/`, `stl-luau/.claude/tools/{spike-diff.py,mutate.sh}`, `quad/scripts/doc-snippets.py`, 각 저장소의 `mise.toml`, `conventions.md`. `quad-changelog-check` 는 낡은 사본이라 근거로 쓰지 않았다.
- 2차 증류(testing, perf, style, roblox-luau 보강 — 2026-11-10 에 luau-runtime·luau-roblox·roblox-engine·roblox-net·roblox-world·roblox-docs 로 나눔, upstream)의 원천은 claude-doctor 후보표 `audit/08-quad-knowledge-mine.md`(ID `Q-`), `audit/09-other-knowledge-mine.md`(ID `S- R- T- D- X- M- O-`), `audit/11-knowledge-gaps.md` 와 `drafts/gaps/`, `drafts/style/` 이다. references 의 근거 칸에 후보 ID 가 남아 있다.
- 재현해 보니 원천 서술이 틀린 것은 각 references 의 '정정' 절에 모았다. 저장소별 전달본은 claude-doctor `handoff/<repo>-corrections.md`(quad 는 `handoff/quad.md`)다.
- 원문을 옮기지 않고 다시 썼다. 원천에서 다시 재 보니 뒤집힌 주장(싱글턴 보존, type function 안 `pcall`/`error()`, stylua 오염 조건)은 정정했다. 재현하지 못한 주장은 `described` 로 남겼다. 목록은 `snippets/RESULTS.md` 끝에 있다.
- 아직 없는 것(설계안 claude-doctor audit 05 §4 기준): 업스트림 보고용 `luau-solver-bug-triage`, `luau-recheck`.

## 기여 규칙

1. 새 사실은 `snippets/<주제>-<요지>.luau` 최소 재현과 표식부터 넣는다. 대조군 줄을 함께 둔다.
2. 두 버전에서 하네스가 rc=0 인지 확인하고, `--table` 로 `snippets/RESULTS.md` 를 갱신한다.
3. references 절에 `status`, `last-confirmed`, 근거를 단다. SKILL.md 는 100줄 이하로 두고 라우팅 표만 고친다.
4. 정책 판단이 필요한 항목은 `decisions/README.md` 의 미결 목록에 올린다.

## 옛 경로 (2026-11-10 roblox-luau 분리)

`skills/roblox-luau/references/<파일>` 을 인용한 문서는 아래로 옮겨 읽는다.

| 옛 파일 | 새 위치 |
|---|---|
| env-dependence, mocks, studio-mcp, typedefs, api-types | `skills/luau-roblox/references/` |
| signals-and-events, instance-lifecycle, instance-api, tween-and-animation, tasks-and-threads(§3·§4 는 luau-runtime `coroutines.md`), parallel-luau, perf | `skills/roblox-engine/references/` |
| remotes-and-replication, platform-services | `skills/roblox-net/references/` |
| gui-and-input, world-and-physics | `skills/roblox-world/references/` |
| gc-and-weak-tables | 의미론 `skills/luau-runtime/references/gc-and-weak-tables.md`, §6(Roblox 관찰) `skills/roblox-engine/references/gc-in-roblox.md` |
| require-and-modules | §1–5·§8·§9 `skills/luau-runtime/references/require-by-string.md`, §6–7(Studio·캐시) `skills/roblox-engine/references/require-in-roblox.md` |
| api-docs | `skills/roblox-docs/references/sources.md` §4 |

스니펫 접두 `rbx-` 는 바꾸지 않았다(외부 인용 보존). `rbx-gc-*`·`rbx-require-cli.sh` 는 luau-runtime 근거다.
