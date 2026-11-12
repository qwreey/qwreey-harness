# 36 구조 조사: 형제 저장소 `.claude/` 와 claude-doctor 최상위 (읽기 전용 조사)

조사일 2026-11-11. 쓴 것은 이 파일뿐이다. mtime 은 거의 전부 2026-11-03(일괄 복사/재배치 시점)이라 "오래됨" 지표로 못 쓴다.

## 1. 형제 저장소 `.claude/` 조사

### 1.1 규모 (worktrees, settings 제외)

| 저장소 | 폴더(파일 수, 크기) | 루트 파일 | docs/ |
|---|---|---|---|
| quad | audit 4934/58.5MB, session 173/2.0MB, archive 112/3.6MB, base 37/2.4MB, luau-test 37, research 27, qa-request 7/0.9MB, feedback 9, reference 8, backlog 3, agents 2, agent-memory 6, hooks 1, skills 1, tools 3 | README, conventions 63KB, project-context 10KB, todos 10KB, question 10KB, session-summary 238KB, model-diff-ignoreme 23KB | 있음(사람용: getting-started, how-to, reference, quadnomicon) |
| stl-luau (stl-luau-doctor 는 같은 수치의 사본) | audit 1356/7.9MB, research 403/3.7MB, archive 9/0.4MB, base 6, papers 8, tools 8, skills 1 | README, conventions 35KB, project-context, todos, backlog.md, question | 없음 |
| table-sim | spikes 62/5.5MB, review 33, research 23, base 16, audit 7, feedback 9, session 3, skills 4 | conventions, todos 40KB, question 22KB | 없음 |
| devplorer | audit 34, review 29, research 11, base 4, feedback 4 | conventions, todos 16KB | Astro 사이트(사람용) |
| moonwave-luau | audit 5, base 3, session 2 | conventions, known-issues, todos, question | 없음 |
| rbvm | review 14, design 4, cache 3(0.7MB), agents 2, session 1 | conventions, todos | 없음 |
| tbox, VideoSync, vitrine, coderag, quietcode-claude | skills/tools/agents/settings 정도(기록 폴더 없음) | | |
| claude-doctor | `.claude/` 는 런타임 상태뿐: conventions.json, session-log.json, sessions/(2 파일 100KB) | | 없음 |

### 1.2 폴더 목적(폴더 README 또는 CLAUDE.md 에서)

| 폴더 | 목적 | 비고 |
|---|---|---|
| base/ | 결정 완료 + 프로젝트 전체에 걸치는 배경지식. 충돌 시 최우선 | plan/done 개념 없음 |
| research/ | 착수 전, 사용자와 상의할 조사·시제품 | 끝나면 base 로 승격 또는 archive/surveys |
| audit/ | 실측·리뷰 기록(시점 기록, 고치지 않음) | 크기가 가장 큼 |
| review/ (quad 는 qa-request/) | 외부·독립 검토 원장 | |
| session/ | 세션별 상세 로그(`YYYY-MM-DD-NN-slug.md`) + session-summary.md(2~4줄 색인) | quad 만 본격 |
| archive/ | 끝났거나 뒤집힌 것의 원문 | 1.3 |
| backlog(.md) | 근거 있고 착수만 남은 일 | |
| feedback/ | 실사용 피드백(소비자로 써 보며 겪은 마찰) | |
| reference/ | 다른 문서가 인용하는 근거 자료 | |
| papers/, design/, spikes/, luau-test/ | 설계 페이퍼·스파이크 | 저장소 고유 |
| agents/, skills/, hooks/, tools/, agent-memory/ | 프로젝트 하네스 자산(표준 위치) | 기록이 아니라 소스 |
| conventions.md, project-context.md, todos.md | **항상 로드**(CLAUDE.md 에서 `@import`) | |
| question.md | 사용자가 답할 열린 질문. 답이 나오면 archive/question-resolved.md 로 | |

`plan/` 폴더는 어느 저장소에도 없다. plan 에 해당하는 것이 todos.md(지금), backlog(나중), research/(상의 전), papers/(설계 초안)로 흩어져 있다.

### 1.3 archive

- quad, stl-luau, stl-luau-doctor 에만 있다. 규칙은 폴더 README 와 conventions 에 글로 있다.
  - 이동 대상: 답 나온 질문(question-resolved.md), 끝난 할 일 경위(todos-history.md), **뒤집힌**(`[역전됨]`)·**기각된**(`[기각됨]`)·**철회된**(`[철회됨]`) 설계 원문, 회신이 끝난 리뷰 라운드, 끝난 범용 조사(`archive/surveys/YYYY-MM-DD-이름.md`, 날짜는 처음 만든 날).
  - 방식: 원문 그대로 옮기고 머리에 "역사 기록" 배너(또는 제목 태그), 살아 있는 문서에는 포인터만 남김. 히스토리 문서는 절 인용·시한부 검사 면제.
- 이동은 **수동**이다. 자동 정리 규칙은 없고 "몇 주기마다 정리"(stl-luau 문서 관리 절) 수준. quad 는 `doc-check.py` + 감사 서브에이전트 루프로 사람이 시키는 형태.

### 1.4 파일 단위 관례

- 제목 태그: `[역전됨, 날짜 신설]`, `[기각됨]`, `[철회됨]`, `[해소 아카이브]`, `[에이전트 실수]`. 날짜는 대괄호 안.
- 상태 줄: stl-luau papers 는 머리에 `상태: 실험 중단 결정됨` 한 줄, README 에 "지금 읽는 법" 표. 파일명 날짜 접두(`2026-08-06-...`, session 은 `YYYY-MM-DD-NN-slug`). 사용자 말은 이탤릭 원문 인용으로 근거에 박는다.
- frontmatter 는 스킬 외에는 쓰지 않는다. 시한부 주장("아직 안 돌려봄")은 날짜 필수(doc-check 가 검사).
- 폴더별 README 가 파일 색인의 소스, 루트 `.claude/README.md` 는 폴더당 한 줄(quad 는 한 셀이 17,005자까지 자라 2026-09-08 에 분리).

### 1.5 로딩

- CLAUDE.md 는 짧은 진입점(약 50줄), "이 파일에 내용을 직접 쌓지 말 것". `@.claude/conventions.md`, `@.claude/project-context.md`, `@.claude/todos.md` 셋만 항상 로드. `@import` 는 컨텍스트를 줄이지 않고 편집성만 산다고 스스로 적어 둠.
- 온디맨드 표("무엇이 궁금할 때 어디를 볼 것")를 CLAUDE.md 에 둠. session-summary.md 는 의도적으로 import 하지 않음(grep 용). 충돌 시 `base/` > 요약 문서.
- 크기 예산: stl-luau `doc-check.py` 의 `BUDGET` 이 항상 로드 문서 크기를 검사. quad 는 예산 없이 conventions.md 63KB 가 매 세션 로드된다.

### 1.6 docs/ 와 `.claude/`

- quad 만 의미 있는 docs/(사용자 대상 사이트·튜토리얼·reference). `.claude/` 는 에이전트 작업 기록, docs/ 는 완성된 사람용 문서. devplorer 의 docs/ 는 Astro 사이트 소스. 나머지는 없음.
- 연결: quad `.claude/archive` 항목이 `quadnomicon`(사람용 개발로그) 소재로 지정됨. 에이전트 기록에서 사람 문서로 가는 방향이 명시된 유일한 예.

### 1.7 공통 패턴, 변형, 작동/실패

공통: (1) 짧은 CLAUDE.md + 항상 로드 3종 (2) base(확정)/research(상의 전)/audit(실측)/archive(끝난 것) 구분 (3) 폴더별 README 색인 (4) 사용자 결정은 날짜+원문 인용 (5) 기록은 저장소 안에 두고 밖으로 내보내지 않음(stl-luau: "다른 사람의 에이전트도 근거를 찾아야"). 기계 점검 `doc-check.py` 는 quad 에서 시작해 stl-luau 로 이식.

변형: 검토 폴더 이름(review/qa-request), 세션 로그 유무(quad 만), 스파이크 위치(luau-test/spikes/audit), 소규모 저장소는 base/audit/session 만.

작동: 폴더별 README 분리, doc-check 의 깨진 참조·색인 누락 검출, 뒤집힌 결정을 archive 로 빼고 포인터만 남기는 규칙(죽은 문단이 살아 있는 문장처럼 편집되는 사고를 막음), `[역전됨]` 태그.

실패 신호:
- 규모: quad audit 4934파일 58MB, session-summary 238KB, conventions 63KB(항상 로드), stl-luau research 403파일. 이동이 수동이라 audit/research 가 무한 성장.
- 중복: quad 의 상태 서술이 CLAUDE.md, project-context.md, ROADMAP 세 곳이라 "상태가 바뀔 때 두 곳을 같이 고칠 것" 경고가 필요(이중 소스). 옛 M2/M3 의미 경고 같은 과거 배너가 CLAUDE.md 에 쌓임.
- 낡은 서술: base 본문에 개명 전 옛 이름이 현재형으로 남아 "읽기 안내" 배너로 땜질(quad base/README 의 2026-09-27, 2026-10-20 안내). 일괄 치환을 안 해서 배너가 누적.
- 자동화 부재: 정리 시점이 사람의 "몇 주기마다"에 달림. 감사 루프는 비용이 큼(quad 는 워크플로를 토큰 과다로 폐기).
- stl-luau-doctor 처럼 사본을 복제하면 색인·기록이 이중이 된다.

## 2. claude-doctor 최상위 분류

저장소 96 커밋. `.gitignore`: `intake/*/`(반입 사본), `*.bak-*`, `__pycache__`.
참조 열은 `경로/` 문자열을 포함하는 파일 수/줄 수 (다른 폴더가 이 폴더 이름을 인용하는 정도).

| 항목 | 내용(파일 수, 크기) | 성격 | 서베이 패턴의 자리 | 참조(파일/줄) |
|---|---|---|---|---|
| CLAUDE.md | 4KB 포인터 | 진입점(항상 로드) | 루트 유지 | 모든 세션 |
| README.md | 8KB | 사람용 문서 | 루트(또는 docs/) | 일반 이름이라 grep 잡음 큼 |
| PLAN.md | 20KB | 에이전트 기록(현재 목표·열린 결정) | `.claude/plan/` | plugins 2/3, audit 6/13, CLAUDE.md, README, decisions, handoff |
| HUMAN_TODO.md | 12KB | 사람이 할 일 | 루트 유지(사람이 봄) | plugins 8/9, audit 6/9, handoff 1/13, CLAUDE.md, README |
| decisions/ | 14파일(D-01..D-13 + README), 112KB | 합의된 규약. 기록이자 규범 | `.claude/base/` 후보 | plugins 7/9, audit 13/17, drafts 7/9, handoff 7/17 |
| audit/ | 76파일, 1.6MB, 번호 01..35(폴더/파일 혼재) | 에이전트 기록(시점 기록) | `.claude/audit/` | plugins 48/95(대부분 코드 주석), drafts 28/65, handoff 14/25, audit 내부 48/327 |
| drafts/ | 112파일, 1.0MB | 에이전트 기록(설치 전 초안, 머리줄 `status: landed in <path>`) | landed 는 `.claude/archive/`, 나머지 `.claude/research/` | plugins 5/6, home 1/1, audit 16/84, handoff 4/5 |
| handoff/ | 19파일, 116KB(memory-*.md, *-corrections.md) | 에이전트 기록(저장소별 인계·교정) | `.claude/archive/` 또는 유지 | plugins 8/11, audit 7/26, HUMAN_TODO 1/13 |
| intake/ | `README.md` 1개(12KB). 외부 프로젝트 사본을 `intake/<이름>/` 에 두고 하네스 감사를 돌리는 절차서. 사본은 gitignore, 감사 보고는 `audit/intake/` | 절차 문서 + 비어 있는 입력 자리 | 절차는 q:doctor reference, 입력은 gitignore 작업 폴더 | plugins 7/12(scan.py), audit 5/14 |
| home/ | 18파일, 232KB (`home/.claude/{CLAUDE.md,HOOK-MESSAGES.md,harness.env,hooks,lib,rules,skills,statusline}`, settings-migrations, MANIFEST) | **소스**(~/.claude 로 설치) | 루트 유지 | plugins 20/25, tools 3/17, audit 29/110 |
| plugins/ | 176파일, 2.0MB: q 1.16MB, qwreey-conventions 452KB, qwreey-advisor 244KB, web-security 80KB, qwreey-proc-guard 40KB | **소스** | 루트 유지 | audit 29/136, tools 21/24 |
| tools/ | 5파일: home-sync.sh, settings-migrate.py, tests/(2) | **소스** | 루트 유지 | plugins 21/24, drafts 16/24 |
| .claude-plugin/ | marketplace.json(마켓 `claude-doctor-market`) | **소스**(마켓 정의) | 이동 불가 | 사용자 settings 의 디렉터리 마켓이 저장소 루트를 가리킴 |
| .claude/ | conventions.json, session-log.json, sessions/(2파일 100KB) | 런타임 상태·설정 | 유지, 기록 홈이 된다 | - |

## 3. 이동 비용: 하드코딩 경로

핵심: **실행 로직이 경로에 의존하는 곳은 적고 대부분이 주석·문서의 `audit/NN` 인용**이다. 테스트가 audit/ 파일을 읽는 곳은 없다.

| 위치 | 의존 | 이동 시 영향 |
|---|---|---|
| plugins 코드 주석(reply_language.py, subagent-slots.py, workspace_gate.py, ambient.py, summarize.py, memory_signals.py, structure-reminder.py 등 약 20곳) | `audit/NN-...` 인용 | 기능 영향 없음, 링크만 끊김 |
| `conventions-check.py` 64, 90, 91행 정규식 | `\.claude/`, `session/`, `audit/`, `handoff/` 를 "이력 경로"로 감지, `ref_path: audit/\d+` | `.claude/audit/` 는 부분 일치로 계속 잡힘. 새 폴더(plan/, archive/)는 감지 목록 추가 필요 |
| test-conventions-check.py 67, 97, 212-220행 | 샘플 문자열 `.claude/audit/18` 등 | 안 깨짐 |
| `.claude/conventions.json` | `exclude: [".claude/research/drafts/**",".claude/audit/drafts/**"]`, `load_budget` | drafts 이동 시 갱신 필수 |
| `plugins/q/skills/doctor/scripts/toolkits/web.py:58` | `PLUGINS_REF = ".claude/audit/16-marketplace.md#8-..."` 를 사용자에게 출력 | audit 이동 시 갱신 필수(출력 문자열) |
| `scan.py` | intake 중첩 저장소 판정 주석(173, 888행), ROADMAP/HUMAN_TODO 이름 목록(677행), `claude-doctor/drafts/delegate` 문구(805행), HUMAN_TODO 문구(853, 1055행) | 판정은 git 루트 기준이라 로직은 안 깨짐. 문구 갱신 |
| `plugins/q/scripts/sllib/records_home.py:19` | `HISTORY_CANDIDATES = (handover, handoff, audit, history, docs/...)` | 기록 보관 위치 제안 후보. `.claude/` 하위 후보 추가 필요 |
| home/settings-migrations 0004, 0006 | ".claude/audit/23" 인용 문자열 | 안 깨짐 |
| `tools/tests/test-vendored-copies.py:12` | `ROOT.parent/"luau-kb"/"hooks"`(없으면 건너뜀) | luau-kb 가 안으로 오면 경로 변경 |
| `.gitignore` | `intake/*/` | intake 이동 시 갱신 |
| 설치 환경 | `/code/.claude/settings.json` 의 `extraKnownMarketplaces` 가 `/code/Projects/claude-doctor` 디렉터리를 마켓으로 가리킴, marketplace.json 의 source 는 `./plugins/*` | **plugins/ 와 .claude-plugin/ 은 옮기면 안 됨**. 나머지 이동은 마켓에 무영향 |
| CLAUDE.md, PLAN.md, README.md, HUMAN_TODO.md 본문 | 모든 폴더를 경로로 인용 | 본문 갱신 |
| audit/, drafts/, handoff/ 내부 상호 참조 | audit 내부 327줄/48파일, drafts->audit 84줄 | 히스토리 문서이므로 "옛 경로 해석표"(quad 방식) 또는 기계적 일괄 치환 |
| coderag.toml | claude-doctor 에는 **없음**. coderag, luau-kb 의 coderag.toml 도 claude-doctor 경로를 안 가리킴 | audit 이동의 coderag 영향 없음(전역 `~/.coderag` 는 이 조사에서 못 봄) |

## 4. 도메인 팩과 opt-in

### 4.1 플러그인 활성화 범위 (공식 문서 plugins.md, plugins/install.md, skills.md)

| 범위 | 설정 파일 | 비고 |
|---|---|---|
| user | `~/.claude/settings.json` `enabledPlugins` | 모든 프로젝트. 지금 claude-doctor 의 5개 플러그인이 여기 |
| project | `.claude/settings.json` `enabledPlugins`(커밋) | 협업자 전원 켜짐. 각자 `claude plugin install <name>@<marketplace> --scope project` 를 한 번 해야 내려받음 |
| local | `.claude/settings.local.json` | 나만, 이 저장소만 |
| 우선순위 | local > project > user | 상위 스코프로 켠 플러그인을 하위에서 `false` 로 끌 수 있다(프로젝트 플러그인 제거 시 "Disable for me" 가 local 에 false 를 씀) |
| CLI | `claude plugin install/enable/disable --scope user\|project\|local` | install/uninstall 기본 user, enable/disable 은 이미 적힌 가장 구체적 스코프 |
| 기타 | 매니페스트 `defaultEnabled` 로 설치는 하되 꺼진 채 시작 가능. 클라우드 세션은 로컬/프로젝트 enabledPlugins 를 로드하지 않음 | |

비용(문서 원문): "An enabled plugin is part of every session". 모델이 호출할 수 있는 스킬·에이전트·커맨드의 이름과 설명이 **매 턴** 컨텍스트에 실린다(사용 안 해도). `description`+`when_to_use` 는 1,536자로 잘림. `disable-model-invocation: true` 만 설명을 컨텍스트에서 뺀다. `paths` 는 "자동 로드를 파일 매칭 때만"으로 제한하지만 **설명이 목록에서 빠지는지는 문서가 말하지 않는다(미확정, 실측 필요)**. 훅은 활성 세션 전부에서 발화하고 플러그인 단위라 훅만 따로 끌 수 없다. 측정 수단: `claude plugin details <name>` 의 Always-on 줄. 따라서 user 스코프 도메인 플러그인은 무관한 세션에서도 스킬 설명 12개(luau-kb, 상한 추정 약 18KB)와 PostToolUse rules_inject 훅을 싣는다.

### 4.2 HARNESS_TOOLKITS

- 정의: `home/.claude/harness.env` 19행 주석 `# HARNESS_TOOLKITS=luau web`, `lib/harness_env.py` 기본값 `""`(비면 전부).
- 사용처 3곳, 모두 "쓸 수 있는 툴킷 목록을 줄이는" 필터이고 **프로젝트별이 아니라 기계 전역**:
  - `qwreey-conventions/hooks/structure-reminder.py:168`: 확장자별 구조 한도 표(luau/web/rust/python/go/jvm). 테스트 241-245행이 검증(`HARNESS_TOOLKITS=luau` 면 TS 편집은 조용).
  - `q/skills/doctor/scripts/scan.py:95`: scripts/toolkits/{luau,web}.py 를 읽는 대상. 문서: `--toolkits luau,web` 는 감지 무관 켬, `none` 은 끔, 감지는 프로젝트 표식(package.json, .luaurc 등)으로 자동.
  - `qwreey-proc-guard/hooks/heavy-proc-guard.py:86`: 툴킷별 실행기 표.
- 한계: (a) 플러그인 로딩(스킬 설명, 훅 등록)은 못 끔, 훅이 조용해질 뿐. (b) 프로젝트 단위 아님. (c) luau-kb 와 web-security 의 rules_inject 는 HARNESS_TOOLKITS 를 읽지 않고 `paths` glob 일치로만 주입.
- 결론: "훅 침묵" 스위치로는 확장 가능하나 컨텍스트 비용(스킬 설명)을 못 줄인다. 컨텍스트가 목적이면 플러그인 스코프(project/local)가 정공. 감지·침묵은 HARNESS_TOOLKITS, 로딩은 enabledPlugins 로 역할이 갈린다.

### 4.3 luau-kb 내용 (플러그인 루트 = 저장소 루트, 314파일, 작업트리 약 3.8MB, .git 6.2MB)

| 경로 | 크기 | 역할 | 플러그인 페이로드? |
|---|---|---|---|
| skills/ (12개) | 1.37MB | 스킬 본문·references | 예 |
| rules/ (README, code-structure, luau-core) | 24KB | `paths: **/*.luau` rules, rules_inject 가 주입 | 예 |
| hooks/ (hooks.json, rules_inject, conv_env, compact_epoch) | 44KB | PreCompact, PostToolUse(Read\|Edit\|Write) | 예 |
| .lsp.json | 작음 | luau-lsp 연결(`${CLAUDE_PLUGIN_ROOT}/tools/luau-lsp.sh`) | 예. tools/luau-lsp.sh 에 의존 |
| tools/ | 264KB | luau-lsp.sh, roblox_docs.py(roblox-docs 스킬이 `python3 -I tools/roblox_docs.py ...` 로 호출), check_snippets.py, upstream_check.py, lsp_probe, tests, dx-sample | **일부 필수**(luau-lsp.sh, roblox_docs.py). 나머지는 개발용 |
| snippets/ | 728KB | 스킬 주장의 근거 실행 스니펫(스킬 274회 인용) + RESULTS.md | 런타임 필수 아님(근거 확인·재현용) |
| typedefs/ | 800KB | globalTypes.d.luau 등 | luau-lsp 가 쓸 가능성(스킬 20회 인용). luau-lsp.sh 의 사용 여부 미확인 |
| bench/ | 392KB | 성능 실측 스크립트(스킬 71회 인용) | 근거용 |
| evals/ | 64KB | 스킬 평가 | 개발용 |
| decisions/ | 32KB | 저장소 결정(스킬 45회 인용) | 개발·이력용 |
| coderag.toml, taxonomy.toml | 24KB | coderag pack 매니페스트(skills/ 가 소스) | 플러그인 런타임과 무관 |
| AGENTS.md, README.md | 32KB | 문서 | |

- 플러그인 캐시는 플러그인 디렉터리 전체를 복사한다. 현재 claude-doctor-market 캐시는 q 4.2MB(소스 1.16MB, 옛 버전 0.3.0, 0.6.0, 0.7.0 병존). luau-kb 를 플러그인 루트로 두면 bench, snippets, typedefs, evals 약 2.0MB 가 버전마다 캐시로 복사된다. 필수 페이로드는 skills+rules+hooks+tools 일부(+typedefs 일부)로 약 1.7MB.
- 스킬은 `tools/roblox_docs.py` 를 "luau-kb 루트 기준" 상대 경로로 부른다(`tools/` 인용 78회). 캐시에서는 루트가 `${CLAUDE_PLUGIN_ROOT}` 라 에이전트가 경로를 풀어야 한다. snippets 는 없어도 스킬 동작에 지장이 없으나 "verified" 재현이 불가.
- luau-kb 는 현재 **별도 마켓**(`luau-kb-market`, `source: "./"`)이고 claude-doctor-market 설명도 "Luau 지식은 luau-kb-market 에 따로 있다".
- 최근 커밋 edc1243 이 `luau-core` rule 을 luau-kb 의 rule 주입으로 옮김. HUMAN_TODO 에 설치본 심볼릭 링크 삭제가 남음.

### 4.4 luau-kb 경로 참조 (`Projects/luau-kb` 또는 `luau-kb/`)

| 저장소 | 파일/줄 | 내용 |
|---|---|---|
| luau-kb 자신 | 15/104 | 내부 |
| claude-doctor | 44/75 | 주로 audit·drafts·handoff 기록. 기능 의존은 `tools/tests/test-vendored-copies.py:12`. 그 외 plugins/q 의 doctor references(staleness-and-kb, drift-and-settings, load-and-rules, memory-portability), start 스킬, q README, qwreey-conventions rules/memory.md, structure-reminder.py 주석 |
| coderag | 7/16 | README.md:46, tech-design.md:399 의 `path = "/code/Projects/luau-kb"` 예시, `experiments/team-audit/audit.py:20` 기본값, `crates/coderag-core/src/{id,cache,config}.rs` 테스트 문자열(`pack:luau-kb/luau-types`). 이동 시 코드 기본값 1곳과 문서 예시만 영향. pack 이름 `luau-kb` 는 유지 |
| stl-luau-doctor | 3/3 | `<!-- luau-kb 후보 -->` 주석 규칙, "공유 정본은 `/code/Projects/luau-kb`(준비 중)" |
| 그 외(quad, table-sim, devplorer 등) | 0 | 경로 참조 없음 |

설치 쪽: `~/.claude` 의 luau-kb 마켓 등록(디렉터리 경로일 가능성)은 이 조사에서 읽지 않았다. 저장소를 옮기면 그 경로도 바뀐다(확인 필요).

## 5. 열린 질문(설계용)

1. **plan/ 의 정체**: 형제에 없다(todos, backlog, research, papers 로 흩어짐). PLAN.md 한 파일을 폴더로 키울지, todos 계열을 모을지.
2. **decisions/ 위치**: 에이전트 기록이지만 D-01..D-13 은 플러그인(qwreey-conventions, luau-kb)이 쓰는 코딩 규약이다. `.claude/base/` 로 갈지, 규범이면 플러그인 rules/references 로 승격할지.
3. **audit/ 번호 체계**: 번호 접두와 폴더/파일 혼재를 유지할지, `audit/README.md` 색인 + 주제별로 바꿀지.
4. **정리 자동화**: audit 가 이미 1.6MB. archive 이동의 **자동 규칙**(상태 머리줄 + 날짜 + 마지막 참조)과 실행 주체(`q:doctor` 점검, Stop 훅 알림, 도구)를 정해야 한다. 형제에는 자동 규칙 선례가 없다.
5. **.claude/research/drafts/**: `status: landed in <path>` 머리줄이 이미 "끝남" 표지다. landed 는 통째 archive, 나머지는 research 로 일괄 이동할지, 규칙으로 자동화할지.
6. **handoff/, intake/**: handoff 는 HUMAN_TODO 가 13번 참조해 아직 살아 있는가. intake/ 는 절차서 1개뿐이라 q:doctor reference 로 옮기고 폴더를 없앨지.
7. **luau-kb 통합 형태**: (a) 한 저장소 안(예 `packs/luau/`)에 플러그인으로 두고 마켓 하나에서 여럿 제공, (b) 페이로드(skills, rules, hooks, tools 일부)와 개발물(bench, snippets, typedefs, evals, decisions)을 분리해 캐시 비용을 줄일지. snippets 는 스킬이 경로로 인용(274회)하므로 분리하면 링크 규칙이 필요.
8. **opt-in 단위**: project/local 스코프 enabledPlugins 로 충분한가, 훅 침묵 스위치(HARNESS_TOOLKITS)도 둘지. 문서가 말하지 않는 `paths` 와 설명 로딩의 관계를 실측해야 한다(막아 준다면 user 스코프 비용이 작아질 수 있다).
9. **기본값**: universal 플러그인(q, advisor, conventions, proc-guard)은 user 스코프, luau-kb/web-security 는 `defaultEnabled: false` 로 두고 프로젝트가 켜게 할지. `q:start` 가 프로젝트 감지(.luaurc, package.json)로 project `.claude/settings.json` 조각을 제안할지(.claude/handoff/vitrine.md 에 web 조각 선례).
10. **self-maintaining 단위**: 형제의 doc-check.py 는 프로젝트별 사본(quad -> stl-luau)이다. 재사용하려면 q:doctor 에 일반화된 `.claude/` 구조 점검(색인 누락, 깨진 참조, 항상 로드 예산, archive 후보)을 두고 새 프로젝트가 참조만 하게 할지.
11. **마켓 경로 고정**: `.claude-plugin/marketplace.json` 과 `plugins/` 는 사용자 settings 의 디렉터리 마켓이 가리켜 이동 불가. plugin 소스 위치를 바꾸면 사용자 쪽 `extraKnownMarketplaces` 갱신이 HUMAN_TODO 가 된다.
12. 미확인: `~/.coderag` 전역 설정, `~/.claude` 의 luau-kb 마켓 등록, luau-lsp.sh 의 typedefs 사용 여부, 스킬 12개 설명의 실제 토큰 수.
