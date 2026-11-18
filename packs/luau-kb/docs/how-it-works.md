# luau-kb 구조와 검증

luau-kb 는 여러 Luau 저장소(quad, stl-luau, rbvm, table-sim, devplorer, tbox 등)에 흩어져 있던 일반 Luau·Roblox 지식의 정본이다. 타입 시스템의 한계, 검증 절차, 테스트, 성능 실측, 코드 스타일, Roblox 엔진 동작, 업스트림 변화를 다룬다. 프로젝트 고유 설계는 넣지 않는다. 도메인 팩 공통 구조(켜는 법, coderag 등록)는 저장소의 `packs/README.md`.

## 스킬
| 스킬 | 다루는 것 |
|---|---|
| `luau-kb:luau-types` | 타입 시스템이 깨지는 곳: 제네릭, 팩·가변 인자, 변성, 합집합, 재귀, type function, 솔버 한계. 결정 트리와 증상 → 파일 표 |
| `luau-kb:luau-verify` | 검사 결과를 믿어도 되는지, 재현 파일, luau-analyze·luau-lsp 호출법, 스니펫 표식, require 검사 |
| `luau-kb:luau-testing` | 러너, 단언, `-O2` 시험, mock 경계, GC·시간 의존 시험 |
| `luau-kb:luau-perf` | 벤치 방법, 메타테이블·테이블·순회·호출·문자열 비용, 최적화·native, GC·메모리(수치는 `bench/`) |
| `luau-kb:luau-style` | 이름, 관용구, 모듈, 구조와 분리, 에러, 함정, 품질, 프로젝트별 예외 |
| `luau-kb:luau-runtime` | Roblox 없이 성립하는 의미론: weak 표와 GC, 코루틴, CLI require 경로 해석 |
| `luau-kb:luau-roblox` | Roblox 코드를 luau+mock 으로 시험할지 Studio 가 필요한지, mock, Studio MCP, Roblox API 타입, 정의 파일 |
| `luau-kb:roblox-engine` | 시그널, Instance 수명, Tween, `task`, 병렬 Luau, Studio require·모듈 캐시, Roblox 안 GC, 엔진 비용 |
| `luau-kb:roblox-net` | 원격·복제·네트워크 소유권·스트리밍, DataStore·MemoryStore·상품·글자 필터·Open Cloud |
| `luau-kb:roblox-world` | GUI 입력·레이아웃, DragDetector, 물리, 캐릭터, 카메라 |
| `luau-kb:roblox-docs` | Roblox 공식 문서 조회(`tools/roblox_docs.py`) |
| `luau-kb:luau-upstream` | luau·luau-lsp·stylua 를 올릴지, 새 문법·RFC 를 써도 되는지, 알려진 결함의 상류 상태 |

주제가 여러 스킬에 걸칠 때(weak 표, require, 코루틴, `-O2` 와 `error`)의 정본 위치는 `AGENTS.md` 의 "주제가 여러 스킬에 걸칠 때의 정본" 절.

## 폴더
```
.claude-plugin/plugin.json   name luau-kb, defaultEnabled false
skills/<스킬>/               SKILL.md(라우팅) + references/*.md (luau-style 은 scripts/split-plan.py, structure-scan.py 도)
rules/                       luau-core.md(**/*.luau), code-structure.md(안내만: 정본은 qwreey-conventions 플러그인의 code-structure rule), README.md(배포 방식과 로드 실측)
snippets/                    *.luau 재현 파일(주장 하나에 파일 하나, 접두가 주제: perf- rbx- style- test- opt- native- pack- tf- …),
                             *.sh 셸 하네스(require, stylua, cross-module), RESULTS.md(버전 행렬 결과, 강등 목록)
bench/                       성능 벤치 *.luau, lib/ 하네스, run.sh, summarize.py, RESULTS.md, results/*.tsv
tools/check_snippets.py      스니펫 하네스(표식: -- expect-error[: 부분], -- bug-present, [버전 조건], --@run 등)
tools/repro-stylua-typeargs.sh  stylua 가 f<<T>> 를 망가뜨리는 조건 재현
tools/lsp_probe.py           luau-lsp 를 잠깐 띄워 hover·자동완성·inlay·진단을 묻는 DX 프로브(샘플: tools/dx-sample/)
tools/upstream_check.py      업스트림 릴리스·RFC 확인
tools/roblox_docs.py         Roblox/creator-docs 원본을 캐시에 받아 search·get·api 로 조회
tools/tests/                 팩 시험(rule 주입, coderag 정책 값)
typedefs/                    globalTypes.d.luau(Roblox 정의 파일의 정본, luau-lsp 플러그인이 사본을 든다) + README.md(출처와 다른 복제본 비교)
decisions/                   README(미결 목록) + 결정 요약 D-01, D-02, D-03, D-04, D-06
AGENTS.md                    다른 에이전트용 진입점
coderag.toml, taxonomy.toml  coderag 팩 매니페스트(모듈 = 스킬 디렉터리), 분류 어휘
```

## references 의 표시
- 파일마다 frontmatter(`title`, `description`, `keywords`, `category`, `tags`, `last_verified`, `last_confirmed`)가 있다. coderag 검색 메타이고, 범주는 `taxonomy.toml` 의 경로를 쓴다. 새 reference 는 frontmatter 를 같이 쓰고 `coderag lint` 로 확인한다. 약 1.5k 토큰이 넘고 표·코드로 시작하는 긴 절은 메타 줄에 `summary:` 한 줄을 둔다.
- 절마다 `status: verified | described`, `last-confirmed: luau <ver>`, 근거 스니펫이나 원천 경로가 붙는다. `verified` 는 스니펫(성능은 `bench/`)으로 재현된 것, `described` 는 재현하지 못한 것이다.
- 저장소마다 정책이 갈린 항목은 한쪽을 고르지 않고 `> 정책: 미정` 으로 표시하고 `decisions/` 를 가리킨다.

## LSP
Claude Code 에 luau-lsp 를 붙이는 일은 이 팩이 아니라 별도 플러그인 `luau-lsp`(저장소의 `plugins/luau-lsp`)가 한다. 바이너리 찾기, Rojo 판정, Windows 런처는 그쪽 `docs/how-it-works.md`.

## 검증
```bash
cd packs/luau-kb
claude plugin validate .
python3 -I tools/check_snippets.py --luau 0.734,0.742,0.746 snippets/*.luau
tools/repro-stylua-typeargs.sh
python3 -I tools/lsp_probe.py tools/dx-sample/consumer.luau --hover 'new' --complete 'local n = s.' --expect-nonempty
timeout 120 python3 -I tools/tests/test-rules-inject.py </dev/null   # coderag 바이너리가 없으면 주입 시험은 건너뛴다
python3 -I tools/tests/test-pack-policy.py
```
도구는 mise 설치 경로(`$MISE_DATA_DIR/installs/<도구>/<버전>/`)를 직접 부른다. 다른 머신에서는 `MISE_DATA_DIR` 이나 `LUAU_BIN_DIR` 을 맞춘다. 스니펫 결과표는 `--table` 로 `snippets/RESULTS.md` 에 갱신한다.

### 마지막 검증 결과 (Claude Code 2.1.316, 2026-11-10)
| 검사 | 결과 |
|---|---|
| `claude plugin validate` | 통과(rc=0). 디렉터리 제출용 부가 검사는 LICENSE 와 아이콘이 없다고 알렸다. 통과 여부와 무관하고 라이선스 선택은 사용자 몫이라 비워 두었다 |
| `check_snippets.py --luau 0.734,0.742,0.746` | 세 버전 각 137 ok, rc=0(표: `snippets/RESULTS.md`) |
| `snippets/rbx-require-cli.sh`, `verify-require.sh`, `style-require-paths.sh` | 모두 ok |
| 하네스 돌연변이 검사 4종 | 모두 FAIL 로 잡힘(`snippets/RESULTS.md`) |
| `repro-stylua-typeargs.sh`(stylua 2.5.2) | rc=0(설정 없음 → 오염, `syntax = "Luau"` → 보존) |
| 스킬 경계 트리거(`claude -p --model sonnet --plugin-dir`, 질문마다 새 cwd) | 질문 6개 × 2회 + 재측 2개 × 2회: 16/16. Roblox 스킬 여섯 개 구성, 질문 25개 × 2회: 47/50(빗나간 3회는 모두 스킬을 부르지 않음). 같은 cwd 에서 동시에 돌리면 한 실행이 여러 스킬을 연달아 불러 측정이 오염된다 |
| 상시 문맥 비용(`ok` 한 번의 입력 토큰) | 지금 구성 약 16,826(Roblox 쪽이 `roblox-luau` 스킬 하나였을 때 15,724) |

## 원천과 범위
- 원천(읽기 전용): quad·stl-luau 의 `.claude/base/typing-limits.md`, `stl-luau/.claude/audit/luau-solver-issues/`, `stl-luau/.claude/tools/{spike-diff.py,mutate.sh}`, `quad/scripts/doc-snippets.py`, 각 저장소의 `mise.toml`, `conventions.md`. `quad-changelog-check` 는 낡은 사본이라 근거로 쓰지 않는다.
- testing, perf, style, Roblox, upstream 쪽 원천은 qwreey-harness 의 후보표 `.claude/scopes/packs/luau-kb/audit/08-quad-knowledge-mine.md`(ID `Q-`), `09-other-knowledge-mine.md`(ID `S- R- T- D- X- M- O-`), `11-knowledge-gaps.md` 와 `.claude/scopes/packs/luau-kb/archive/research/drafts/gaps/`, `style/` 이다. references 의 근거 칸에 후보 ID 가 남아 있다.
- 원문을 옮기지 않고 다시 썼다. 다시 재 보니 원천 서술이 틀린 것은 각 references 의 '정정' 절에 있고, 저장소별 전달본은 qwreey-harness `.claude/handoff/<repo>-corrections.md`(quad 는 `handoff/quad.md`)다. 재현하지 못한 주장은 `described` 로 두고 목록은 `snippets/RESULTS.md` 끝에 있다.
- 아직 없는 것: 업스트림 보고용 `luau-solver-bug-triage`, `luau-recheck`.

## 기여 규칙
1. 새 사실은 `snippets/<주제>-<요지>.luau` 최소 재현과 표식부터 넣는다. 대조군 줄을 함께 둔다.
2. 행렬의 모든 버전에서 하네스가 rc=0 인지 확인하고, `--table` 로 `snippets/RESULTS.md` 를 갱신한다.
3. references 절에 `status`, `last-confirmed`, 근거를 단다. SKILL.md 는 100줄 이하로 두고 라우팅 표만 고친다.
4. 정책 판단이 필요한 항목은 `decisions/README.md` 의 미결 목록에 올린다.
5. 로컬 경로 마켓은 파일을 직접 읽으므로 고친 뒤 `/reload-plugins` 하면 반영된다. 호스팅 설치본은 `plugin.json` 의 `version` 을 올려야 갱신된다.

## 옛 경로
`skills/roblox-luau/` 는 여러 스킬로 나뉘었다. 그 경로를 인용한 문서는 아래로 옮겨 읽는다.

| 옛 파일(`skills/roblox-luau/references/`) | 새 위치 |
|---|---|
| env-dependence, mocks, studio-mcp, typedefs, api-types | `skills/luau-roblox/references/` |
| signals-and-events, instance-lifecycle, instance-api, tween-and-animation, tasks-and-threads(§3·§4 는 luau-runtime `coroutines.md`), parallel-luau, perf | `skills/roblox-engine/references/` |
| remotes-and-replication, platform-services | `skills/roblox-net/references/` |
| gui-and-input, world-and-physics | `skills/roblox-world/references/` |
| gc-and-weak-tables | 의미론 `skills/luau-runtime/references/gc-and-weak-tables.md`, §6(Roblox 관찰) `skills/roblox-engine/references/gc-in-roblox.md` |
| require-and-modules | §1–5·§8·§9 `skills/luau-runtime/references/require-by-string.md`, §6–7(Studio·캐시) `skills/roblox-engine/references/require-in-roblox.md` |
| api-docs | `skills/roblox-docs/references/sources.md` §4 |

스니펫 접두 `rbx-` 는 외부 인용을 지키려고 그대로 둔다. `rbx-gc-*`, `rbx-require-cli.sh` 는 luau-runtime 의 근거다.
