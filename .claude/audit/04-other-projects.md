# 04. quad 외 프로젝트 에이전트 문서 감사

감사일 2026-11-10. 대상은 `/code/Projects/` 의 stl-luau, rbvm, moonwave-luau, table-sim, tbox, vitrine, VideoSync, devplorer, mrow 입니다. 형제 격인 quad 는 비교 기준으로만 봤고, 모든 프로젝트 디렉터리는 읽기 전용으로 다뤘습니다.

측정 방법은 `md5sum`, `difflib.SequenceMatcher`(줄 단위 유사도), `wc -c`, `git ls-files`, `git check-ignore`, `git worktree list` 입니다.

토큰 수는 한국어 혼합 문서를 바이트÷2~3, 영어 문서를 바이트÷4 로 어림한 값입니다.

---

## 0. 요약 (먼저 읽을 것)

1. **문서 뼈대는 하나의 설계(quad 원형 → stl-luau → 나머지로 복제)이고, 복제 방식이 "복사 후 방치"입니다.**
   - 7개 저장소가 같은 `CLAUDE.md` + `@import 3종`(conventions / project-context / todos) 구조를 씁니다.
   - 본문 줄 유사도는 낮습니다(§2). 같은 것은 **형식과 규칙의 종류**이고, 문장이 같지는 않습니다.
   - 줄 단위로 거의 같은 파일은 `heavy-proc-guard.py` 둘(0.96)뿐이고, `agy-delegate.sh` 는 0.6대 입니다.
2. **로드 총량은 프로젝트 편차가 큽니다.**
   - table-sim 73.6KB(618줄), stl-luau 51KB, devplorer 34KB, moonwave-luau 20KB, rbvm 19KB 입니다.
   - table-sim 은 `todos.md` 만 40.5KB 이고 "된 것은 지우지 않고 아래로 내린다"는 규칙으로 계속 자랍니다.
   - devplorer `todos.md` 16.5KB 는 취소선(완료) 20줄을 매 세션 싣습니다.
3. **프로젝트 간 모순이 실제로 있습니다.**
   - rbvm 은 "`const` 쓰지 말 것", tbox·stl-luau·table-sim·devplorer 는 "`const` 기본"입니다.
   - 서로의 문서가 서로를 "관례의 원형"이라 부르며 인용합니다.
4. **stl-luau `GEMINI.md` 는 낡았습니다.**
   - 같은 저장소 `conventions.md:36` 은 "질문 AB 규칙은 뒤집혔다(질문 BI, 2026-11-10)"고 합니다.
   - `GEMINI.md` 는 AB·BD·BH 를 "확정된 결정"으로 서술합니다.
5. **접미 디렉터리**(§1)는 에이전트용 격리 작업공간입니다.
   - `-agy` 는 Gemini(agy) 위임용 git worktree 기지, `-scratch` 는 실험 산출물, `-codex` 는 OpenAI Codex 질의 기록, `-proto` 는 빈 디렉터리입니다.
   - 어느 문서에도 정의되어 있지 않습니다.
6. **공통 승격 가능한 것은 많습니다.**
   - 스크립트: `agy-delegate.sh`(4벌), `heavy-proc-guard.py`(2벌), `doc-check.py`(2~3벌 포크).
   - 문서 조각: "이 파일에 내용을 쌓지 말 것" 문구, 언어·git·서브에이전트·문서 표기 규칙, settings 의 `deny git push`.
   - 하지만 `~/.claude`(= `/code/.claude`)에는 skills/agents/hooks 가 비어 있고 `synced/` 뿐입니다(§7).

---

## 1. 접미 디렉터리의 정체

| 디렉터리 | 정체 | 근거 |
|---|---|---|
| `stl-luau-agy/` | **agy(Gemini) 위임용 격리 worktree 의 부모 디렉터리**. 지금은 비어 있습니다(`.home/`, `.homes/`, `.hooks/pre-push` 만 있고 과제 worktree 는 `remove` 로 정리됨). | `stl-luau/.claude/tools/agy-delegate.sh` 의 `BASE=/code/Projects/stl-luau-agy`. `.hooks/pre-push` 내용은 `echo "push refused: agy delegate worktree"; exit 1`. |
| `tbox-agy/`, `table-sim-agy/` | 위와 같은 구조. | 각 프로젝트의 `agy-delegate.sh` 의 `BASE`. |
| `quad-agy/` | 같은 구조. 이름 있는 worktree `naming-1021e` 가 남아 있습니다(브랜치 `agy/naming-1021e`). | `quad/.git/worktrees/naming-1021e`. `git worktree list`. |
| `quad-codex/` | **OpenAI Codex 질의 기록**입니다. `naming-1021` 등 하위는 git worktree 가 아니라 `prompt.md` / `answer.md` / `stdout.txt` 3종 파일뿐이고, `.home/.codex` 는 uid 61000 소유 HOME 입니다. | `quad-codex/naming-1021/prompt.md`(네이밍 리뷰 프롬프트). |
| `stl-luau-scratch/` | **실험·측정 산출물 모음**입니다(`arr-split`, `blog-trait`, `trait-dyn`, `class-like`, `critique-2026-11-04` 등 18개). 대부분 `.luau` 와 로그이고, `no-self-return/wt` 하나만 stl-luau 의 실제 worktree(브랜치 `proto/no-self-return`)입니다. | `git -C stl-luau worktree list`. `.claude/todos.md`, `.claude/archive/question-resolved.md` 가 이 경로를 근거로 인용합니다. |
| `quad-scratch/` | 위와 같은 용도. `refs/` 에 참고 Luau 저장소(fusion/vide/charm/tbox/rbvm)가 있고 `quad -> /code/Projects/quad` 심볼릭 링크가 있습니다. | `stl-luau/CLAUDE.md` 마지막 줄이 `quad-scratch/refs/` 를 가리킵니다. |
| `stl-luau-proto/` | **빈 디렉터리**(2026-11-06 생성). 브랜치 `proto/*` 를 위한 자리였던 것으로 보입니다. | `ls -la` 결과 비어 있음. |

격리 방식은 `agy-delegate.sh` 헤더에 적혀 있습니다.
- git worktree 를 만들고 권한 없는 uid 로 `setpriv` 실행합니다.
- 과제마다 HOME 을 따로 둡니다(`.homes/<이름>`).
- `choom -n 1000` 을 씌우고, 메인 레포의 HEAD 와 `git status` 를 실행 전후로 비교합니다.
- `pre-push` 훅으로 push 를 거부합니다.

문제는 다음과 같습니다.

- **정의가 없습니다.** `-agy` 는 `delegate-agy` 스킬이 설명하지만 `-scratch`, `-proto`, `-codex` 는 어떤 CLAUDE.md 에도 정의되어 있지 않습니다.
  - `stl-luau/.claude/` 의 문서 여럿이 `stl-luau-scratch/…`(저장소 밖 경로)를 **근거로 인용**합니다. 그런데 이 경로는 git 에 없어서 clone 하면 근거가 사라집니다.
  - 이는 `stl-luau/.claude/conventions.md:179` 의 원칙("기록을 저장소 밖으로 내보내지 않습니다")을 스스로 어깁니다.
- **uid 충돌 가능성이 있습니다.**
  - `AGY_UID` 는 quad=61000, stl-luau=61001, table-sim=61002, **tbox=61000** 입니다.
  - tbox 와 quad 가 같은 uid 라서, stl-luau 가 일부러 나눈 "한쪽 worktree 를 다른 쪽 과제가 고칠 수 없게"의 보장이 tbox↔quad 에서는 깨집니다.
  - `stl-luau/.claude/tools/agy-delegate.sh` 주석이 "quad 와 uid 를 나눕니다"라고 한 이유이고, tbox 판은 이 부분을 따르지 않았습니다.
- 규약 후보: 접미를 `<repo>-agy`(위임 worktree), `<repo>-scratch`(실험, git 밖), `<repo>-codex`(타 모델 질의 기록)로 고정하고 정의 한 곳을 둡니다.

---

## 2. 프로젝트별 감사

### 2.1 stl-luau (`/code/Projects/stl-luau`)

구성은 다음과 같습니다.
- `CLAUDE.md` 3.5KB / 50줄 + `GEMINI.md` 8.1KB / 64줄
- `.claude/` 안에 conventions / project-context / todos / question / backlog / README 6종과 `base/` `papers/` `archive/` `audit/` `research/` `skills/delegate-agy/` `tools/`(7개 스크립트)
- `settings.json` 없음
- `.claude/` 는 **1,796개 파일이 git 추적 중**, 13MB

**매 세션 로드:** CLAUDE.md 3,476B + conventions 35,552B + project-context 6,611B + todos 5,513B = **51,152B / 363줄**(어림 17~26k 토큰).
- 이 저장소는 `doc-check.py` 에 `BUDGET`(conventions 36,000B, 합계 60,000B)을 두고 있어서 예산 관리는 잘 합니다.
- 그러나 conventions 가 한도 36,000B 대비 **35,552B(99%)** 입니다. 예산이 "넘치지 않게" 쓰이고 있을 뿐 줄이지 못합니다.

**잘 된 점**
- `CLAUDE.md` 는 짧은 진입점 + 온디맨드 표로 역할이 분명합니다.
- 아카이브(`archive/*-2026-11-04.md`)로 옛 판을 내려보내고, `doc-check.py` 로 깨진 참조·색인 누락·없어진 이름을 기계 점검합니다.
- `todos.md` 에 "10KB 안팎 유지, 끝난 일은 지운다"는 자체 규칙이 있고 지켜집니다(5.5KB).

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **모순·낡음** | `GEMINI.md` 가 "데이터는 엔티티, 함수는 서비스(질문 AB)·메타테이블 없음·모든 트레이트는 dyn(BD)"을 확정 결정으로 단언합니다. 그런데 `conventions.md:36` 은 "전환 중(질문 BI, 2026-11-10): 아래 AB 규칙은 뒤집혔습니다"라고 하고, `todos.md` 는 트레이트 시스템을 `stl-trait` 로 떼는 방향 전환(BG)을 적습니다. | `GEMINI.md` "확정된 결정" 절 vs `conventions.md:36` |
| 2 | **코드 파생** | `GEMINI.md` 의 `src/Collections/…` 파일 나열, 타입 모양(`{ n, __type, data }`, `DynList<E,I>`)은 코드와 `base/trait-system.md` 에서 얻을 수 있습니다. | `GEMINI.md` "무엇인가" 절 |
| 3 | **코드 파생** | `project-context.md` 의 "모듈 구조" 트리(`src/` 각 폴더 설명)는 `ls src` + 각 파일 머리말로 대체됩니다. | `project-context.md` "모듈 구조" 절 |
| 4 | **과도한 길이·경위 섞임** | `conventions.md` 는 "규칙만 둔다"고 선언하는데 본문 곳곳에 `(질문 BB·BE)`, `perf 56절`, `spikes/69` 같은 경위 참조와 수치(예: "생성이 7~11% 느렸습니다", "함수를 거치면 2.7~5배")가 섞여 있습니다. 규칙 근거는 링크로 보내고 수치는 `perf-measurements.md` 에만 두는 게 맞습니다. | `conventions.md` "데이터와 모듈" 절 |
| 5 | **명령형·강조 남발** | `⭐` `⚠️` **굵게** 가 conventions 에만 수십 곳입니다. 다 중요하다고 하면 우선순위가 사라집니다. | `conventions.md` 전반 |
| 6 | **중복** | CLAUDE.md 서문의 "quad 의 .claude 를 작게 옮긴 것"은 `project-context.md`·`README.md` 와 겹치는 메타 서술이고, 에이전트 행동에는 영향이 없습니다. | `CLAUDE.md` 5~6줄 |
| 7 | **외부 근거** | 저장소 밖 `stl-luau-scratch/…` 를 근거로 인용합니다(§1). | `todos.md`, `archive/question-resolved.md` |
| 8 | **인프라 공백** | `heavy-proc-guard` 훅이 없고 `settings.json` 도 없습니다. 그런데 `GEMINI.md` 에 "luau 가 12GB 까지 커져 컨테이너가 30분 스래싱"(2026-10-13)이라는 사고가 적혀 있습니다. `ulimit -v` 는 문서 경고뿐이고 hook 으로 강제되지 않습니다. | `GEMINI.md` 마지막 문단. `quad/.claude/hooks/heavy-proc-guard.py` 가 이미 있음 |
| 9 | **버전 드리프트** | `mise.toml` 의 luau 0.742·luau-lsp 1.70.1 이 형제(0.734·1.69.0)와 다릅니다. `.vscode/settings.json` 은 한도 플래그를 길게 주석합니다. | `stl-luau/mise.toml` |

### 2.2 rbvm (`/code/Projects/rbvm`)

구성은 `CLAUDE.md` 2.7KB / 51줄 + `.claude/{README, conventions, project-context, todos, design/(4), review/, session/, agents/(2), tools/check.sh, settings.json}` 입니다.
- 추적 파일 12개이고 저장소는 dirty(변경 6건: 미커밋 `design/engine-behavior.md`, `review/` 등)입니다.

**매 세션 로드:** 2,705 + 5,816 + 5,838 + 4,855 = **19,214B / 304줄**(어림 7~10k 토큰). 가장 적정합니다.

**잘 된 점**
- 서브에이전트 2개, `check.sh`, 권한 allowlist 가 한 묶음으로 정리돼 있습니다.
- `deny` 에 `git push`, `git remote add`, `Read(./.git/config)` 를 둡니다.
- 서술이 "무엇을 실측했나(날짜·버전 포함)"에 근거합니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **낡음** | CLAUDE.md 의 "[2026-08-25 기준] 상태: 구조 미확정", "pesde.toml/mise.toml/.luaurc 는 먼저 만들지 말 것"이 그대로입니다. 그 뒤 2026-10-05 전면 코드 리뷰(4라운드)와 `review/`·`design/engine-behavior.md` 가 생겼고, 마지막 커밋은 2026-09-29 입니다. `todos.md` 의 가장 새 날짜는 08-25 + 10-05 한 절입니다. | `rbvm/CLAUDE.md` 7~12줄 |
| 2 | **색인 누락** | `CLAUDE.md` 온디맨드 표에 `design/engine-behavior.md` 와 `review/` 가 없습니다. 그것들은 `.claude/README.md` 에만 있습니다. | `.claude/README.md` 표 vs `CLAUDE.md` 표 |
| 3 | **교차 모순** | "`const` 를 쓰지 말 것 — 사용자 결정(2026-08-24)"입니다. 이유는 pesde 의 자동 타입 익스포트 문제입니다. 반면 tbox 는 pesde 0.7.4 로 올려 `const` 를 기본으로 쓰고, stl-luau·table-sim·devplorer 도 `const` 기본입니다. 형제 저장소끼리 정책이 갈립니다. | `rbvm/.claude/conventions.md` "코드 관례" vs `tbox/CLAUDE.md` "코드 스타일" |
| 4 | **명령형 남발** | "~하지 말 것"이 CLAUDE.md·conventions 에 십수 번입니다. 반드시 지킬 것은 "GC 코드 변경 시 gc-auditor 호출" 정도로 압축할 수 있습니다. | `conventions.md` |
| 5 | **긍정적인 점** | "테스트 통과"라고 쓰지 말고 "타입/포맷만 확인함, 런타임 미검증"이라고 보고하라는 규칙은 구체적이고 일반화할 가치가 있습니다. | `CLAUDE.md` 마지막 문단 |

### 2.3 moonwave-luau (`/code/Projects/moonwave-luau`)

구성은 `CLAUDE.md` 2.8KB / 51줄 + `.claude/{conventions, project-context, todos, question, known-issues, base/(3), audit/, session/(2)}` 입니다.

**매 세션 로드:** 2,819 + 9,124 + 5,179 + 2,961 = **20,083B / 319줄**.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **미추적** | `git status` 에서 `.claude/`, `CLAUDE.md`, `.gitignore`, `.luaurc`, `mise.toml`, `scripts/`, `stylua.toml`, `tests/` 가 전부 `??` 입니다. 에이전트 문서가 한 번도 커밋되지 않았습니다. 2026-09-29 에 만들었는데도 그렇습니다. | `git -C moonwave-luau status --short` |
| 2 | **낡음·모순** | `.vscode/settings.json` 은 `@lune/` 별칭을 설정하는데 `mise.toml`/`CLAUDE.md` 는 "lune 은 쓰지 않는다"고 합니다. `todos.md` 의 가장 새 날짜가 09-29 하나뿐입니다. | `.vscode/settings.json` vs `CLAUDE.md` |
| 3 | **중복** | 메타 문단("stl-luau·rbvm 의 관례를 따랐다. quad 의 session-summary, agent-memory, doc-check 는 두지 않는다")은 에이전트 행동에 영향이 없습니다. | `CLAUDE.md` 14~17줄 |
| 4 | **포크** | `mise.toml` 이 stl-luau 의 장문 주석 구조를 복제했습니다("lune 은 의도적으로 없습니다", "selene 도 없습니다")(§3 표). | `moonwave-luau/mise.toml` |

### 2.4 table-sim (`/code/Projects/table-sim`)

구성은 `CLAUDE.md` 3.9KB / 49줄 + `.claude/` 164개 파일, 8.2MB, `settings.json`(hook 1 + deny 2), `hooks/heavy-proc-guard.py`, `skills/quad-ui-dev`(37.7KB), `tools/agy-delegate.sh` 입니다.

**매 세션 로드:** 3,896 + 19,965 + 9,171 + 40,578 = **73,610B / 618줄**(어림 25~37k 토큰). **조사 대상 중 최대**이고 CLAUDE.md 를 제외하고도 3개 문서가 모두 stl-luau 의 예산(60KB)을 단독으로 초과합니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **과도한 길이** | `todos.md` 40.5KB / 260줄 중 한 줄이 최대 206자, 날짜는 모두 2026-10-12 입니다. "[2026-10-12 고침] 된 것은 지우지 않고 맨 아래 '된 것'으로 내린다"는 규칙 때문에 끝난 일이 매 세션 로드됩니다. 같은 저장소의 형제 stl-luau 는 정반대 규칙("끝난 일은 지웁니다 — 10KB 유지")을 씁니다. | `table-sim/.claude/todos.md:5` |
| 2 | **과도한 길이** | `question.md` 22.5KB 는 온디맨드(import 안 됨)라 괜찮습니다. 하지만 `conventions.md` 20KB 중 "Studio" 절이 3.4KB(105~155줄)이고 "서브에이전트" 1.3KB, "git" 1.1KB 도 큽니다. | `conventions.md` |
| 3 | **경위 섞임** | todos 에 "세션 원문의 열네~일흔두 번째 발언, `session/…` 대조" 같은 작업 서사가 있습니다. 에이전트가 다음에 할 일이 아니라 지난 작업의 기록입니다. | `todos.md:5-8` |
| 4 | **중복·포크** | `conventions.md` 의 "문서 표기 / 문서를 어디에 두나 / 설계 원칙 / 질문하는 방식 / 검증과 보고 / 코드 스타일 / Studio / 서브에이전트 / git" 절 구조가 devplorer 와 같은 9개 제목입니다. 절별 줄 유사도는 0.07~0.40 입니다. 제목은 같고 문장은 다른 "개별 포크"입니다. 동기 규칙이 없습니다. | §3 표 |
| 5 | **사본 드리프트** | `skills/quad-ui-dev/SKILL.md` 는 "quad 가 제공하는 스킬의 사본"이라고 CLAUDE.md 가 적습니다. 원본은 `quad/docs/skills/quad-ui-dev/SKILL.md` 이고 **지금은 207줄 차이**입니다(`diff | wc -l`). 사본이 낡았습니다. | `diff` |
| 6 | **파생·중복** | `project-context.md` 의 라이브러리 소비 표(버전·상태)는 "소스는 각 저장소"라고 스스로 적으면서 상태까지 베낍니다("API 개편 중", "0.1.0 미게시"). 금방 낡습니다. | `project-context.md:36-` |
| 7 | **좋은 점** | 방향 선언("진짜 목적은 게임이 아니라 라이브러리 첫 소비자")과 "넘지 않는 선" 4항목은 CLAUDE.md 에 있어야 할 종류의 내용입니다. | `CLAUDE.md` |
| 8 | **uid** | `AGY_UID=61002`(나눔). 서술도 "형제와 나눈다"입니다. | `agy-delegate.sh` |

### 2.5 tbox (`/code/Projects/tbox`)

구성은 루트 `CLAUDE.md` 15.6KB / 187줄이 전부입니다. `.claude/` 에는 `skills/delegate-agy` 와 `tools/agy-delegate.sh` 둘뿐(파일 2개)이고, conventions·project-context·todos 분리가 없으며 `settings.json` 도 없습니다. 패키지별 `CLAUDE.md` 도 있습니다(`packages/tbox` 22.2KB, `tbox_squish` 12.9KB, `tbox_remote` 1.5KB).

**매 세션 로드:** 루트 15,563B(어림 6~8k 토큰)입니다. 패키지 CLAUDE.md 는 해당 디렉터리 작업 시에만 올라옵니다. 이 방식은 맞습니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **구조 불일치** | 다른 라이브러리는 "짧은 진입점 + import 3종 + 온디맨드"로 갔는데 tbox 는 한 파일에 개요·구조·pesde·스타일·require 규칙·검증·인수인계 메모·금지가 다 있습니다. | 루트 `CLAUDE.md` |
| 2 | **낡음** | "인수인계 메모 (단일 플랫 패키지 → pesde 모노레포 전환)" 절이 커밋 `ef7b0e2` 를 설명합니다. 일회성 인수인계이고 `git log` 에 있습니다. "git remote 는 현재 Sol-s-Studio/tbox" 같은 상태 서술도 낡기 쉽습니다. | `CLAUDE.md` "저장소 상태" 절 |
| 3 | **코드 파생** | 워크스페이스 트리, `[dependencies]` 발췌, 새 패키지 `pesde.toml` 필드 안내는 `pesde.toml` 과 `ls packages` 로 얻습니다. | `CLAUDE.md` "워크스페이스 구조" |
| 4 | **중복** | `mise.toml` 주석("pesde self-upgrade 쓰지 마세요", 0.7.4, lune 은 `const` 를 못 읽음)과 CLAUDE.md 가 같은 내용을 두 번 적습니다. 같은 서술이 stl-luau·table-sim·devplorer·moonwave `mise.toml` 에도 변형으로 반복됩니다. | 각 `mise.toml` |
| 5 | **명령형 남발** | "~하지 마세요 / 바꾸지 마세요"가 `const`·stylua·`f<<T>>`·`.trash/`·remote 에 걸쳐 십여 번이고, 같은 경고("고치려고 코드 스타일을 바꾸지 마세요")가 3번 반복됩니다. | `CLAUDE.md` |
| 6 | **uid** | `AGY_UID=61000` 으로 quad 와 같습니다(§1). | `tbox/.claude/tools/agy-delegate.sh` |
| 7 | **좋은 점** | stylua 가 `f<<T>>` 를 조용히 `<<` 시프트로 오역한다는 경고는 코드에서 알 수 없는 함정이라 가치가 높습니다. 같은 경고가 rbvm·table-sim `mise.toml` 에 다시 적혀 있어 공통 템플릿 후보입니다. | `CLAUDE.md` "위험: stylua" |

### 2.6 vitrine (`/code/Projects/vitrine`)

구성은 `CLAUDE.md` 7.3KB / 137줄(영어)과 `settings.json` 50줄이 전부입니다.

**매 세션 로드:** 7,334B(어림 1.8~2k 토큰). 목적·불변식·함정 위주여서 적정합니다.

**잘 된 점**
- "The requirement everything else follows from"과 번호 매긴 불변식 6개는 에이전트 지침의 모범입니다. 코드에서 알 수 없는 "왜"와 "이것이 깨지면 제품이 깨진다"를 적었습니다.
- 에이전트용 문서가 사람용 `docs/` 로 위임됩니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **권한 과다** | `permissions.allow` 에 `Bash(sed:*)`, `Bash(cp:*)`, `Bash(mv:*)`, `Bash(chmod:*)`, `Bash(curl:*)`, `Bash(python3:*)`, `Bash(env:*)`, `Bash(find:*)` 처럼 임의 파일 변조·네트워크·코드 실행이 되는 것까지 넣었습니다. 사실상 "전부 허용"입니다. | `vitrine/.claude/settings.json` |
| 2 | **deny 부재** | `.env` 가 존재하는데 `Read(./.env)` deny 가 없습니다. VideoSync 는 deny 합니다. `git push` deny 도 없습니다. | 같은 파일 vs `VideoSync/.claude/settings.json` |
| 3 | **코드 파생** | "Layout" 트리와 "Stack" 표는 `ls`·`go.mod`·`package.json` 에서 얻습니다. | `CLAUDE.md` "Layout", "Stack" |
| 4 | **환경 하드코딩** | 포트 21xxx 범위와 dind 주소는 사용자 레벨 환경 지식입니다(§5.1). `settings.json` 에도 `DOCKER_HOST` 가 있어 CLAUDE.md 와 중복입니다. | `CLAUDE.md` "Development" |
| 5 | **allow 중복** | `Bash(git add:*)` 와 `Bash(git commit:*)` 를 허용하면서 "Commit as work completes"를 conventions 에 적습니다. 일관되지만, 다른 프로젝트는 deny push 만 있고 commit 정책이 서로 다릅니다. | 비교 §4 |

### 2.7 VideoSync (`/code/Projects/VideoSync`)

구성은 `CLAUDE.md` 24.2KB / 295줄(영어), `.claude/agents/ref-researcher.md`, `settings.json` 입니다.
- 사람용·연구용 문서는 `docs/`(STATE, DECISIONS, PROTOCOL 등), `research/`, `refs/` 에 있습니다.
- `.claude/worktrees/` 에 1개가 남아 있습니다(572KB, `git worktree list` 에도 있음).

**매 세션 로드:** 24,236B(어림 6k 토큰)입니다. 분량은 크지만 import 없이 단일 파일입니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **과도한 길이** | "Traps that cost real time to rediscover" 절이 42~245줄, 즉 CLAUDE.md 의 **약 70%(200줄)** 입니다. 항목마다 `file:line`, 근거 문서 §번호, 사고 경위가 붙은 긴 단락이고, 수정·측정 기록(amendment)이 곳곳에 있습니다. | `VideoSync/CLAUDE.md:42-245` |
| 2 | **중복** | "Authority documents" 표가 `docs/STATE.md` 를 "Start here"로 지정하면서 DECISIONS·SYNTHESIS 의 내용(6줄 설계 요약)을 또 적습니다. 둘이 어긋나면 어느 쪽이 맞는지 알 수 없습니다. | `CLAUDE.md:13-40` |
| 3 | **코드 파생·낡기 쉬움** | `room.go:346`, `content.ts:87-104` 같은 줄 번호 인용은 코드가 바뀌면 즉시 틀립니다. | `CLAUDE.md` Traps 절 |
| 4 | **낡음** | "PoC sequencing" 절 말미에 "How that came out"(앞 서술이 틀렸다는 사후 정정)이 붙어 있습니다. 앞 서술을 지우고 결과만 두는 쪽이 맞습니다. | `CLAUDE.md:278-` |
| 5 | **분리 안 됨** | 사람용 README, 에이전트용 `CLAUDE.md`, 연구용 `docs/` 중 "Traps"는 사실상 `docs/STATE.md` 계열 문서입니다. 에이전트 지침이 아니라 프로젝트 지식베이스입니다. | |
| 6 | **좋은 점** | 비목표(스크린 캡처 금지 등)를 맨 위에 못박았습니다. 코드에서 알 수 없는 제약이고 에이전트가 가장 먼저 알아야 합니다. | `CLAUDE.md:5-8` |
| 7 | **settings** | `deny Read(./.env*)` 는 좋은 패턴(vitrine 은 부재). `deny Bash(rm -rf /*)` 는 효용이 낮습니다(경로 와일드카드가 확장되지 않고 우회가 쉽습니다). `git push` deny 는 없습니다. | `VideoSync/.claude/settings.json` |
| 8 | **ref-researcher** | §4 에서 평가합니다. | |

### 2.8 devplorer (`/code/Projects/devplorer`)

구성은 `CLAUDE.md` 2.5KB / 40줄 + `.claude/{conventions, project-context, todos, question, base/, research/, audit/, review/, feedback/}`(88개 파일 1.3MB), `settings.json`(빈 deny), `settings.local.json`(`prefersReducedMotion`) 입니다.

**매 세션 로드:** 2,475 + 12,464 + 2,938 + 16,567 = **34,444B / 271줄**(어림 12~17k 토큰)입니다.

**문제**

| # | 유형 | 내용 | 근거 |
|---|---|---|---|
| 1 | **worktrees 잡동사니** | `.claude/worktrees/` 에 **22개**(`git worktree list` 23건), **445MB**. 각각이 저장소 전체 체크아웃이라 CLAUDE.md, `.claude/` 문서 87개 사본, `third_party/` 까지 중복됩니다. 하위 `CLAUDE.md` 가 22개이니 이 하위에서 작업하면 형제 문서가 로드됩니다. | `du -sh`, `find … -name CLAUDE.md` |
| 2 | **과도한 길이** | `todos.md` 16.6KB 는 취소선(`~~`) 완료 항목 20줄과 커밋 해시·보안 리뷰 번호("7·8차 반영")로 가득합니다. 길이 한 줄이 200자대입니다. 지금 할 일이 아니라 완료 기록입니다. | `todos.md:5-30` |
| 3 | **빈 설정** | `settings.json` 은 `{"permissions":{"deny":[]}}` 입니다. 하지만 `CLAUDE.md` 는 "실제 저장소(upstream) 푸시는 사용자가 직접" 이라고 선언하고도 deny 로 강제하지 않습니다. | `devplorer/.claude/settings.json` vs `CLAUDE.md` |
| 4 | **중복** | conventions 의 "서브에이전트" 절이 사용자 발언 원문을 인용해("쉬운 부분들은 sonnet/opus…") 위임 분담 규칙을 적습니다. table-sim 에도 같은 계열 문장이 있습니다(포크 §3). | `conventions.md:98-107` |
| 5 | **빈 문서** | `question.md` 가 "지금 열린 문항 없음" 한 줄과 해소 이력 3줄뿐인데 CLAUDE.md 표에 매번 안내됩니다. 낭비는 작지만 구조 이식의 부산물입니다. | `question.md` |
| 6 | **좋은 점** | CLAUDE.md "넘지 않는 선"(익스플로잇 경로 금지 등)이 보안 제품의 비협상 조건을 맨 앞에 둡니다. | `CLAUDE.md` |

### 2.9 mrow (`/code/Projects/mrow`)

- `CLAUDE.md`, `.claude/`, `GEMINI.md`, `settings.json` **모두 없음**. `.luaurc`, `.vscode/settings.json`, `README.md`, `src/`, `tests/`, `review/REVIEW.md` 뿐입니다.
- `.gitignore` **없음**. 28개 파일이 추적 중입니다. `review.tar.gz` 가 작업 트리에 있는데 추적 여부는 `git ls-files` 상 `review/` 만 보입니다(미추적 파일일 수 있고, 무시도 되지 않습니다).
- 문서 부재는 문제이기보다 선택일 수 있습니다. 하지만 moonwave-luau 가 mrow 를 "전면 재작성의 기반"으로 쓴다고 CLAUDE.md 에 적고, table-sim 도 소비자로 참조합니다. 따라서 mrow 에서 작업하는 세션에는 아무 지침이 없습니다.
- `.luaurc` 가 `LocalShadow:false` 로 다른 프로젝트(`lint: *` 전부 켬)와 다르고, `.vscode` 도 `luau-lsp.platform.type: standard` 로 별개입니다.
- 새 스캐폴딩 스킬의 대상이 될 최소 후보입니다.

---

## 3. 교차 비교

### 3.1 에이전트 문서 구조 비교

| 항목 | stl-luau | rbvm | moonwave | table-sim | tbox | vitrine | VideoSync | devplorer | mrow |
|---|---|---|---|---|---|---|---|---|---|
| CLAUDE.md 크기 | 3.5KB | 2.7KB | 2.8KB | 3.9KB | 15.6KB | 7.3KB | 24.2KB | 2.5KB | 없음 |
| `@import` 3종 | O | O | O | O | X (단일) | X | X | O | X |
| conventions.md | 35.6KB | 5.8KB | 9.1KB | 20.0KB | - | - | - | 12.5KB | - |
| project-context.md | 6.6KB | 5.8KB | 5.2KB | 9.2KB | - | - | - | 2.9KB | - |
| todos.md | 5.5KB | 4.9KB | 3.0KB | **40.6KB** | - | - | - | 16.6KB | - |
| question.md | 10.6KB | (루트 HUMAN_TODO) | 7.7KB | 22.5KB | - | - | - | 0.8KB | - |
| README 색인 | O | O | X | X (폴더별) | X | X | X | X | X |
| GEMINI.md | O (8.1KB) | X | X | X | X | X | X | X | X |
| **매 세션 로드 합계** | **51.2KB** | 19.2KB | 20.1KB | **73.6KB** | 15.6KB | 7.3KB | 24.2KB | 34.4KB | 0 |
| `.claude/` 추적 파일 수 | 1,796 | 12 | **0(미추적)** | 136 | 2 | 1 | 2 | 87 | - |
| 서브에이전트 | X | 2 | X | X | X | X | 1 | X | X |
| 스킬 | delegate-agy | X | X | quad-ui-dev(사본) | delegate-agy | X | X | X | X |
| hooks | X | X | X | heavy-proc-guard | X | X | X | X | X |
| settings.json | X | 30줄 | X | 21줄 | X | 50줄 | 22줄 | 5줄(빈 deny) | X |

### 3.2 "거의 같은 문서" 정량 비교

기준은 `stl-luau` 대비 줄 단위 `SequenceMatcher` 비율이고, `md5` 는 전부 서로 다릅니다.

| 파일 | 비교 쌍 | 줄 유사도 | 공통 줄 수 | 판정 |
|---|---|---|---|---|
| `heavy-proc-guard.py` | table-sim ↔ quad | **0.96** | 80/84 | 사실상 동일. 차이는 docstring 출처 줄과 메시지의 날짜 문구뿐 |
| `agy-delegate.sh` | stl-luau ↔ quad / table-sim / tbox | 0.62 / 0.65 / 0.61 | 82~90/136 | 같은 골격 + 상수(ROOT, BASE, AGY_UID, TOOL_PATH)와 주석 언어(한/영)만 다름. **파라미터화 가능** |
| `agy-delegate.sh` | table-sim ↔ quad | 0.67 | 90 | 위와 같음 |
| `delegate-agy/SKILL.md` | stl-luau ↔ quad / tbox | 0.24 / 0.16 | 27 / 15 | 목적·절차는 같고 프로젝트 맥락 서술이 다릅니다. 본문의 "왜 쓰나"가 3벌로 나뉨 |
| `doc-check.py` | stl-luau ↔ quad | **0.10** | 37 | **포크**입니다. 214줄 vs 534줄, 사실상 별개 프로그램(검사 항목, STALE 표, BUDGET 만 stl 전용) |
| `conventions.md` | stl ↔ rbvm / moonwave / table-sim / devplorer | 0.25 / 0.12 / 0.16 / 0.18 | 13~30줄 | 절 제목만 일부 같고 문장은 다름 |
| `conventions.md` | table-sim ↔ devplorer 의 같은 제목 절 | 0.07~0.40 | | 같은 제목 8개 절이 있으나 문장은 개별 작성 |
| `project-context.md` | stl ↔ 나머지 | 0.15~0.18 | 11~14줄 | 프로젝트 고유. 제목 틀만 공통 |
| `todos.md` | stl ↔ 나머지 | 0.05~0.19 | | 틀조차 다름(우선순위순 vs 번호 목록 vs 완료 누적) |
| `question.md` | stl ↔ moonwave / table-sim | 0.20 / 0.12 | | 형식은 같고 내용은 고유 |
| `README.md`(색인) | rbvm ↔ stl | 0.24 | 14 | 표 구조만 공통 |
| `CLAUDE.md` | stl ↔ rbvm / moonwave / table-sim / devplorer | 0.36~0.38 | 17~19줄 | **뼈대는 거의 공통**(table-sim↔devplorer 0.58) |
| `stylua.toml` | tbox = rbvm, table-sim = devplorer | md5 동일 쌍 둘 | | stl, moonwave 는 다른 변종 |

해석은 이렇습니다.
- 파일 하나를 통째로 승격할 수 있는 것은 **스크립트류**(hook, agy-delegate)입니다.
- 문서류는 **뼈대와 규칙 단락 몇 개**가 공통이고 내용은 고유입니다. 문서 자체를 공유하기보다 "규칙 단락 라이브러리 + 스캐폴딩 스킬"이 맞습니다.
- 4벌로 흩어진 `agy-delegate.sh` 는 이미 서로 다른 개선을 담고 있습니다.
  - stl-luau 는 HOME 을 과제마다 분리(`.homes/`)하고 `--ref` 를 지원합니다.
  - tbox 는 `.home/`(구판 형태)입니다.
  - table-sim 은 브랜치 없이 detach 한 worktree 를 만듭니다.
- 즉 버그 수정(예: stl-luau 의 "HOME 공유로 두 과제가 서로 복사를 지웁니다")이 일부 사본에만 반영됩니다.

### 3.3 스캐폴딩 비교

| 항목 | stl-luau | rbvm | moonwave | table-sim | tbox | devplorer | mrow | vitrine / VideoSync |
|---|---|---|---|---|---|---|---|---|
| `.luaurc` | strict, lint `*` | **없음** | 같음 | 같음(한 줄 표기) | (packages 안) | 같음 | strict + `LocalShadow:false` | 해당 없음 |
| `stylua.toml` | 변종 A(주석 포함) | 변종 B | 변종 C | 변종 D | = rbvm | = table-sim | **없음** | 해당 없음 |
| `default.project.json` | O | O | X | O(+place id) | packages 안 | O(+place id, 3종) | X | 해당 없음 |
| `mise.toml` | luau 0.742, lsp 1.70.1, stylua 2.5.2 | **없음** | luau 0.734, lsp 1.69.0, stylua, jq | luau 0.734, pesde, rojo 7.7.0, lsp 1.69.0 | pesde, luau 0.734, lute, darklua | pesde, rojo, luau 0.734, node | **없음** | go/node(고정) |
| pesde.toml | O(+lock) | X(예정) | X | O(+lock, 일부) | O(workspace) | O | X | 해당 없음 |
| `.vscode/settings.json` | 한도 플래그 포함 | formatOnSave | lune 별칭 | X | formatOnSave | X | platform standard | X |
| `.gitignore` 핵심 | `sourcemap.json`, `*-ignoreme*` | `.claude/cache`, rbxlx | `tests/_stage/` | 산출물, `.claude/worktrees/` | `.trash/` 등 | + `.claude/worktrees/` | **없음** | 일반 |
| `check.sh` 게이트 | `scripts/check.sh` | `.claude/tools/check.sh` | `scripts/check.sh` | `scripts/check.sh` | `mise run check` | `scripts/check.sh` | X | `scripts/check.sh`(vitrine) |
| settings.json 의 hooks | X | X | X | PreToolUse(heavy-proc-guard) | X | X | X | X |
| settings.json 의 permissions | X | allow 19 + deny 3 | X | deny 2 | X | deny [] | X | allow 41(vitrine) / allow 11 + deny 3(VideoSync) |
| `.claude/` 4종 문서 | O | O(3종+README) | O(+known-issues) | O | X | O | X | X |
| `.claude/worktrees/` 무시 | **무시 규칙 없음**(`.gitignore` 에서 0건) | 0건 | 0건 | O | 0건 | O | - | VideoSync O, vitrine 0건 |

주요 관찰은 다음과 같습니다.
- **툴체인 pin 이 4갈래**입니다(luau 0.734/0.742, luau-lsp 1.69.0/1.70.1). 각 `mise.toml` 이 "형제와 같은 값이다"라고 주석하지만 stl-luau 만 앞서 나갔고 "형제가 올릴 때 같이 올린다"는 동기화 장치가 없습니다.
- `STUDIO_SYNC_OWNER` 같은 **환경 변수 충돌 방지**는 table-sim 과 devplorer 에 복붙되어 있습니다.
- `.claude/worktrees/` 무시 규칙은 table-sim, devplorer, VideoSync 에만 있습니다(`git check-ignore -v` 로 `.gitignore:33:/.claude/worktrees/` 확인). stl-luau, rbvm, moonwave, tbox, vitrine 에는 규칙이 없습니다. 에이전트 worktree 가 생기면 `git status` 에 노출됩니다.

---

## 4. 서브에이전트 정의 품질 (`rbvm-api-parity`, `rbvm-gc-auditor`, `ref-researcher`)

| 항목 | rbvm-gc-auditor | rbvm-api-parity | ref-researcher |
|---|---|---|---|
| 위치 | `rbvm/.claude/agents/` (≈7.3KB) | 동 (≈4.9KB) | `VideoSync/.claude/agents/` (≈2KB) |
| frontmatter | name/description/tools/model=sonnet | 동(+WebFetch/WebSearch) | 동(+Write, WebFetch 등) |
| 도구 | Read, Grep, Glob, Bash | Read, Grep, Glob, Bash, WebFetch, WebSearch | Bash, Read, Grep, Glob, WebFetch, WebSearch, Write |
| 읽기 전용 강제 | **규약으로만**("파일을 고치지 마라"). 도구는 Bash 가 있어 사실상 쓰기 가능 | 같음 | 해당 없음(Write 가 필요) |
| description | 호출 시점을 구체적으로 열거(`__mode` 변경, `gcHold` 근처 등) | 호출 시점을 구체적으로 열거 | 호출 시점이 "새 reference 추가 / 인용 재검증"으로 구체적 |
| 출력 형식 | 심각도 3단계, 발견마다 필드 고정, "발견 없음 + 범위" 규칙 | 같은 틀(심각도 3단계) | "40줄 이하 요약 + 문서는 `research/<slug>.md`" |

### 4.1 장점
- **세 정의 모두 좋은 수준**입니다. description 이 "언제 호출하라"를 코드 변경 사건으로 열거합니다.
- **"발견 없음 + 무엇을 봤는지 범위를 밝혀라"**는 감사 에이전트의 최고 관행입니다. 안 본 것을 알려주는 규칙입니다.
- **"런타임에서 확인했다고 쓰지 마라 / 추정과 실측 구분"**, **"확신도 + 사용자 판단 필요 여부"**, **"애매하면 판정하지 말고 올려라"** 도 재사용할 가치가 큽니다.
- ref-researcher 는 "file:line 인용, ABSENT 표기, 읽지 않은 README 로 요약 금지, 근거 없는 추론 금지"가 규칙이 짧고 검증 가능합니다.

### 4.2 문제
1. **읽기 전용이 도구 수준에서 강제되지 않습니다.** `tools:` 에 Bash 가 있어서 `sed -i` 등으로 쓸 수 있습니다. 본문도 "어떤 이유로 쓰기 도구가 주어지더라도 직접 수정하지 않는다. 이건 도구 유무가 아니라 행동 규약이다"라고 인정합니다. `disallowedTools` 또는 hook 으로 막아야 합니다.
2. **프로젝트 사실이 정의에 박혀 있습니다.** gc-auditor 는 `proxy/base.luau`, `gcHold`, `Order 14 이상` 같은 코드 세부를 본문에 인라인합니다. 코드가 바뀌면 에이전트가 낡습니다. 일반화하려면 `.claude/design/gc-and-lifecycle.md` 만 정본으로 읽게 하고 본문에는 점검 항목 틀만 둡니다.
3. **rbvm-api-parity 에 "알려진 의도적 차이" 목록이 하드코딩**돼 있습니다(`ConnectParallel` 폴백, `WaitForChild` 의 `timeout` 누락). 문서와 충돌하면 문서가 이깁니다.
4. **둘 다 모델 `sonnet` 고정**입니다. 사용자가 "리뷰 모델은 sonnet 이 기본"이라고 정한 것(devplorer conventions 2026-10-21)과 일치하지만 이는 프로젝트별 결정이라 에이전트 본문이 아니라 settings 의 model 기본값에 두는 게 맞습니다.
5. 두 rbvm 에이전트는 같은 출력 형식(심각도 3단계 + 발견 필드)을 복붙합니다. 공통 "감사 보고 형식" 조각으로 뺄 수 있습니다.
6. ref-researcher 는 `/code/Projects/VideoSync/research/BRIEF.md` 를 **절대 경로로** 하드코딩해서 worktree 에서 돌리면 형제 체크아웃이 아니라 메인을 읽습니다.
7. `.claude/agents/` 의 frontmatter 에 `description` 만 있고 `maxTurns`, `memory`, 입력 형식 등 호출 규약이 없습니다. 호출자 쪽(CLAUDE.md/conventions)이 호출 시점을 적어야 하는데 rbvm 은 README 에만 있습니다.

### 4.3 일반화 가능성
- **일반화 가능(→ 사용자 레벨 또는 플러그인):**
  1. "읽기 전용 신선 맥락 감사자" **틀** — 먼저 읽을 정본 문서 / 점검 항목 / 하지 말 것 / 출력 형식 4분할. 도메인 값만 바꿔 끼웁니다.
  2. "레퍼런스 구현을 고정 스키마로 분석하는 연구자"(ref-researcher)는 이미 도메인 중립입니다. `BRIEF.md` 경로만 인자로 받으면 됩니다.
- **프로젝트 고유로 남길 것:** gc-auditor 의 점검 항목(`gcHold`, `__mode`), api-parity 의 Roblox 시맨틱 대조 목록.

---

## 5. 문서 사용 방식의 문제 사례 (유형별)

| 유형 | 사례 | 근거 |
|---|---|---|
| **코드에서 파생 가능** | `GEMINI.md` 의 `src/` 목록과 타입 모양 / stl `project-context.md` 모듈 트리 / tbox 워크스페이스 트리 / vitrine Layout·Stack / table-sim 라이브러리 버전 표 | §2 각 항 |
| **모순** | (a) stl `GEMINI.md`(AB 확정) vs `conventions.md:36`(AB 뒤집힘) (b) rbvm "const 금지" vs 나머지 "const 기본" (c) table-sim "된 것은 아래로 내린다" vs stl "끝난 일은 지운다" (d) moonwave "lune 안 씀" vs `.vscode` lune 별칭 (e) rbvm CLAUDE.md 는 `design/` 만 안내하는데 README 는 `review/` 도 안내 | |
| **낡음** | rbvm CLAUDE.md `[2026-08-25 기준]`, moonwave `todos.md` 09-29, tbox 인수인계 메모, VideoSync "How that came out" 정정문, table-sim 의 `quad-ui-dev` 사본(원본과 207줄 차이), devplorer `question.md`(빈 문서) | |
| **과도한 길이** | table-sim 로드 73.6KB(todos 40.6KB 단독), stl conventions 35.6KB(예산 99%), VideoSync CLAUDE.md 의 Traps 200줄, devplorer todos 완료 항목 | §2 |
| **명령형 남발** | rbvm·tbox 의 "~하지 마세요"(같은 경고 3회 반복), stl conventions 의 ⭐⚠️ 수십 개 | |
| **중복** | 사용자 발언 원문이 conventions·todos·skill 에 반복 인용되고(예: "agy 도 존재해서…"), mise.toml 주석과 CLAUDE.md 가 같은 내용, `delegate-agy` 가 3벌 | |
| **외부 근거** | stl-luau 문서가 `stl-luau-scratch/…`(git 밖)를 근거로 인용 | §1 |
| **미추적** | moonwave-luau 의 에이전트 문서 전체가 한 번도 커밋되지 않음 | `git status` |

### 5.1 worktree 와 .gitignore 점검
- **`.claude/worktrees/` 의 쌓임**
  - devplorer: 22개, 445MB. 각 체크아웃에 CLAUDE.md 와 `.claude/` 사본이 있습니다.
  - table-sim: 2개, 6.1MB.
  - VideoSync: 1개, 572KB.
  - 나머지는 없습니다.
- **무시 규칙 누락**
  - 무시: table-sim, devplorer, VideoSync(2건).
  - **없음: stl-luau, rbvm, moonwave-luau, tbox, vitrine.** 이 저장소에서 `claude --worktree` 나 `isolation: worktree` 를 쓰면 `git status` 에 수천 개가 `??` 로 뜹니다.
  - quad 는 `.claude/worktrees` 에 에이전트 worktree 8개가 있고, 하나는 `locked` 입니다.
  - 전역 `core.excludesfile` 은 `**/.claude/settings.local.json` 뿐입니다.
- **정리 장치 없음**: 완료된 에이전트 worktree 를 지우는 hook·스킬이 없습니다. devplorer 의 22개는 사실상 방치입니다.
- **mrow**: `.gitignore` 자체가 없습니다. `review.tar.gz`(작업 트리에 있음)와 `review/extras` 가 추적 여부 불명입니다.
- **`__pycache__`**: stl-luau 는 `.claude/tools/__pycache__` 가 존재하지만 `.gitignore:19` 가 막습니다. 추적 0건이라 안전합니다.
- **보안성**: vitrine `.env` 는 `.gitignore` 가 막고 추적 0건이라 안전합니다. 단 `.env` 읽기 deny 는 VideoSync 에만 있습니다(§2.6).

---

## 6. (2) CLAUDE.md 로드 총량과 낭비 요약

| 프로젝트 | 로드(B) | 줄 | 어림 토큰 | 낭비 평가 |
|---|---|---|---|---|
| table-sim | 73,610 | 618 | 25~37k | **큼** — todos 40.6KB 중 대부분 완료·경위 서사, conventions 의 Studio 절 3.4KB |
| stl-luau | 51,152 | 363 | 17~26k | 중 — conventions 35.6KB 가 한도에 붙어 있음. 경위·수치를 `base/` 로 보낼 여지 |
| devplorer | 34,444 | 271 | 12~17k | 중 — todos 완료 항목 20줄, 빈 `question.md` |
| VideoSync | 24,236 | 295 | 약 6k | 중 — Traps 70%. 분량 대비 영어라 토큰은 적음 |
| moonwave-luau | 20,083 | 319 | 7~10k | 소 |
| rbvm | 19,214 | 304 | 7~10k | 소 — 낡음은 있으나 분량은 적정 |
| tbox | 15,563 | 187 | 6~8k | 소 — 인수인계 메모·워크스페이스 트리 제거 시 약 25% 감소 |
| vitrine | 7,334 | 137 | 약 2k | 최소 |
| mrow | 0 | 0 | 0 | 문서 부재 |

경험 규칙: 모든 라이브러리 저장소에서 "항상 로드"는 **CLAUDE.md + 규칙 + 지금 할 일**만 두고, 총 20KB(한국어 기준)를 넘으면 아카이브로 내리는 쪽이 맞습니다. 현재 stl-luau 의 60KB 예산은 그 3배입니다.

---

## 7. (7) settings.json 의 permissions / hook 패턴

| 패턴 | 어디에 있나 | 판정 |
|---|---|---|
| `deny: Bash(git push:*)`, `Bash(git remote add:*)` | rbvm, table-sim (quad 도) | **사용자 레벨로 승격.** 모든 프로젝트 문서가 "푸시는 사용자가 직접"이라고 적는데 devplorer·vitrine·VideoSync·stl-luau·tbox·moonwave 에는 강제가 없습니다 |
| `deny: Read(./.env)`, `Read(./.env.*)` | VideoSync 만 | **승격** (vitrine 은 `.env` 가 있는데 빠짐) |
| read-only git: `status/diff/log/show/blame/ls-files` allow | rbvm, vitrine, VideoSync | **승격** |
| 읽기 전용 검색: `rg`, `fd`, `wc`, `jq`, `ls`, `head`, `tail` allow | rbvm, vitrine, VideoSync | **승격** |
| `Bash(mise:*)` allow | vitrine, VideoSync(rbvm 은 `mise ls`, `mise exec github:…` 로 좁힘) | 승격 후보. 단 `mise exec` 는 임의 실행이므로 `mise ls`/`mise run` 정도로 한정하는 게 안전 |
| `Bash(stylua:*)`, `Bash(luau:*)`, `Bash(luau-lsp:*)`, `Bash(rojo sourcemap:*)` allow | rbvm | Luau 프로젝트 공통 → **플러그인 또는 스캐폴딩 스킬이 심는 프로젝트 settings** |
| `Bash(bash .claude/tools/check.sh)` | rbvm | 프로젝트 고유 |
| PreToolUse(Bash) heavy-proc-guard | table-sim, quad | **승격 대상 1순위.** 컨테이너 cgroup OOM 은 **환경 전체**의 문제이고(2026-09-28 quad 사고, GEMINI.md 의 luau 12GB 사고) 모든 세션에 필요합니다. 사본 둘이 0.96 동일이고 stl-luau 는 사고를 겪고도 hook 이 없습니다 |
| `env: DOCKER_HOST`(dind) | vitrine | 환경 전체 값이라 사용자 레벨. 포트 21xxx 규칙도 같습니다 |
| `Bash(rm -rf /*)` deny | VideoSync | 효용 낮음. 사용자 레벨에서 위험 명령 전반으로 대체 |
| vitrine 의 `sed/cp/mv/chmod/curl/python3/env/find` allow | vitrine | **축소 권고.** 임의 변경·네트워크·실행입니다. `fewer-permission-prompts` 방식으로 읽기 전용만 남기는 편이 안전합니다 |
| `includeCoAuthoredBy:false` | quad 만 | 개인 취향이므로 사용자 레벨로 |

현재 `~/.claude`(= `/code/.claude`)는 `settings.json`(`defaultMode: auto`, `language: 한국어` 등)과 `skills/synced/` 만 있고 **hooks·agents·사용자 스킬이 비어 있습니다**. 그래서 위 승격 후보는 아직 한 곳도 올라가 있지 않습니다.

---

## 8. 신규 Luau 프로젝트 스캐폴딩 스킬(`/new-luau-project`)의 최소 정본 제안

스킬 한 개가 아래를 심으면 현재 5~6곳에서 복붙·드리프트하는 것을 한 곳으로 모읍니다. 템플릿은 스킬 디렉터리(`assets/`)에 둡니다.

### 8.1 파일 정본

| 산출물 | 정본 내용 | 변수 |
|---|---|---|
| `.luaurc` | `{ "languageMode": "strict", "lint": { "*": true } }` (mrow 만 예외 가능하므로 선택 인자) | - |
| `stylua.toml` | stl-luau 변종(`syntax="Luau"`, `column_width=120`, Tabs, 4, `AutoPreferDouble`, `call_parentheses="Always"`, `collapse_simple_statement="Never"`) 1벌. `syntax = "Luau"` 이유 주석 1줄(`f<<T>>` 오역) | - |
| `mise.toml` | `[tools]` luau / luau-lsp / stylua(+선택: pesde, rojo, lute, darklua, node). **버전은 스킬이 한 곳에서 관리**(지금은 0.734/0.742 로 갈라짐). `[env] STUDIO_SYNC_OWNER=<name>` 포함(선택) | `NAME`, 옵션 |
| `default.project.json` | `ReplicatedStorage/<Name>` → `src` 최소형. Studio 용이면 `servePlaceIds` 추가 | `NAME`, place id |
| `.gitignore` | `roblox_packages/ luau_packages/ lune_packages/ .pesde/ sourcemap.json *.rbxl* /build/ .claude/worktrees/ .claude/settings.local.json __pycache__/ .claude/cache/ *-ignoreme*` | - |
| `.vscode/settings.json` | `luau-lsp.fflags.enableNewSolver: true`, stylua formatOnSave | - |
| `scripts/check.sh` | stylua --check → luau-analyze/luau-lsp → 테스트. **exit code 가 판정**. 템플릿 하나 | 테스트 엔트리 |
| `CLAUDE.md` | 아래 8.2 | `NAME`, 한 줄 설명 |
| `.claude/conventions.md` | 아래 8.3 | |
| `.claude/project-context.md` | "이게 뭔가 / 실행 환경 / 지금 상태" 3절 뼈대만 | |
| `.claude/todos.md` | "지금 할 일(우선순위순)·끝난 일은 지운다·10KB" 한 규칙으로 통일 | |
| `.claude/question.md` | 열린 결정 표(비어 있으면 파일을 만들지 않음) | |
| `.claude/settings.json` | 아래 8.4 | |

### 8.2 `CLAUDE.md` 뼈대
```
# CLAUDE.md
**<name>**: <한 줄>.
(이 파일에 내용을 쌓지 말 것 — 진입점)

## 항상 로드: @.claude/conventions.md @.claude/project-context.md @.claude/todos.md
## 온디맨드 표
## 넘지 않는 선 (3~5항, 프로젝트 고유 비협상)
## 검증: ./scripts/check.sh (exit code)
```
- 합계 상한(20KB 한국어)을 스킬이 알려줍니다.
- `doc-check` 는 별도 선택 설치로 두고 "로드 총량" 한 가지만 먼저 검사합니다.

### 8.3 `conventions.md` 정본 단락(프로젝트 변수 없이 공통으로 들어갈 것)
- 언어(대화·문서·커밋은 한국어, 식별자·에러 문자열은 영어)
- 문서 표기(날짜·출처 표기, 【추정】과 실측 구분)
- 문서를 어디에 두나(`base/ research/ audit/ feedback/ review/ question.md`)
- 질문하는 방식(상황→문제→갈래·대가→권고, 평문)
- 검증과 보고("런타임 미검증"이라고 정확히 보고)
- git(커밋은 작업 단위마다·한국어 메시지, push 는 사용자, 파괴적 명령은 요청 시만)
- 무거운 실행(`choom` 래핑 — hook 이 강제)
- 서브에이전트(탐색·목록화는 sonnet, 설계 판단은 메인, 수정이 겹치면 병렬 금지)
- Luau 공통 스타일(`const` 정책을 **프로젝트가 선택**하게 함 — 현재 모순 해소)

### 8.4 `settings.json` 정본
```json
{
  "permissions": {
    "allow": ["Bash(git status:*)","Bash(git diff:*)","Bash(git log:*)","Bash(git show:*)",
              "Bash(rg:*)","Bash(fd:*)","Bash(stylua:*)","Bash(luau:*)","Bash(luau-lsp:*)",
              "Bash(bash scripts/check.sh)"],
    "deny":  ["Bash(git push:*)","Bash(git remote add:*)","Read(./.env)","Read(./.env.*)"]
  }
}
```
- `heavy-proc-guard` hook 은 사용자 레벨 settings 에 두고 프로젝트 settings 에는 넣지 않습니다.
- 프로젝트 고유 allow(예: `check.sh` 경로)만 더합니다.

### 8.5 스킬이 하지 말아야 할 것
- rbvm 의 "스캐폴딩은 사용자가 나중에 quad 것을 붙인다"는 보류 선언처럼 **"만들지 말 것" 조건**은 스킬이 아니라 사용자의 확인 단계로 둡니다.
- 프로젝트별 설계 서술(트레이트 시스템, GC 규칙 등)은 스킬에 넣지 않습니다.

---

## 9. 공통 승격 후보 목록

| # | 후보 | 현재 상태 | 승격 위치 | 근거 |
|---|---|---|---|---|
| 1 | `heavy-proc-guard.py` 와 PreToolUse(Bash) 등록 | quad·table-sim 만 사용, stl-luau 는 사고 이력이 있는데 없음 | **사용자 레벨 hook**(`~/.claude/hooks/` + 사용자 settings) | 줄 유사도 0.96 / OOM 이 환경 전체 문제 |
| 2 | `agy-delegate.sh` 와 `delegate-agy` 스킬(4벌) | 상수와 주석 언어만 다름(0.61~0.67 / 스킬 0.16~0.24) | **사용자 레벨 스킬**(`~/.claude/skills/delegate-agy`) — 인자로 `ROOT`·`BASE`·`AGY_UID`·`TOOL_PATH`(mise 에서 자동 산출). uid 할당은 중앙 표 1개로 | uid 중복(tbox=quad), 사본별 버그 수정 불일치 |
| 3 | `deny git push` / `deny Read(.env*)` / 읽기 전용 git·검색 allow | rbvm·table-sim·VideoSync·vitrine 에 제각각 | **사용자 레벨 settings.json** | 모든 프로젝트 CLAUDE.md 가 "푸시는 사용자"를 선언 |
| 4 | "읽기 전용 신선 맥락 감사자" 서브에이전트 **틀** | rbvm 에 2벌 복붙(심각도 3단계, 발견 필드, "발견 없음+범위") | **사용자 레벨 agent/플러그인** | 도메인 값만 다름 |
| 5 | `ref-researcher`(고정 스키마 분석기) | VideoSync 고유처럼 보이나 도메인 중립 | 사용자 레벨 agent(BRIEF 경로 인자화) | 절대 경로 하드코딩 해소 |
| 6 | `/new-luau-project` 스캐폴딩 스킬 | 5개 저장소에 `.luaurc`/`stylua.toml`/`mise.toml` 변종이 흩어짐 | **사용자 레벨 user-invocable 스킬** | §8 |
| 7 | 툴체인 pin 목록(luau, luau-lsp, stylua, pesde, rojo) | 4갈래 드리프트 | 스킬의 한 곳(또는 공유 `mise` 템플릿) | §3.3 |
| 8 | `doc-check.py`(문서 감사) | stl-luau 214줄, quad 534줄, 유사도 0.10(포크) | **통일 후 플러그인.** 공통 기능 3가지만 우선: 깨진 `@import`/참조, 로드 총량 예산, README 색인 누락 | 현재 stl-luau 외에는 쓰지 않음 |
| 9 | conventions 공통 단락(언어, 문서 표기, 문서 위치, 질문 방식, 검증 보고, git, 서브에이전트, 무거운 실행) | table-sim↔devplorer 같은 제목 8개를 개별 포크 | **스캐폴딩 스킬의 템플릿** 또는 사용자 레벨 CLAUDE.md 의 `@import` 대상 | 줄 유사도는 낮아도 규칙 종류가 같음 |
| 10 | "이 파일에 내용을 쌓지 말 것 / 짧은 진입점" 규약과 온디맨드 표 형식 | 7개 CLAUDE.md 가 같은 문구 | 스캐폴딩 스킬 | CLAUDE.md 줄 유사도 0.36~0.58 |
| 11 | `.claude/worktrees/` + `settings.local.json` + `__pycache__` ignore 규칙 | 3개 저장소에만 있음 | 스캐폴딩 `.gitignore`, 그리고 전역 `core.excludesfile`(`**/.claude/worktrees/`) | §5.1 |
| 12 | worktree 정리 스킬(완료된 에이전트 worktree 제거) | 없음. devplorer 445MB | 사용자 레벨 스킬 | §5.1 |
| 13 | 접미 디렉터리 규약(`-agy`/`-scratch`/`-codex`)과 `-scratch` 근거 인용 금지 | 문서화 안 됨 | 사용자 레벨 CLAUDE.md 에 3줄 | §1 |
| 14 | "런타임 미검증이라고 정확히 보고" / "추정과 실측 구분" 규칙 | rbvm·GEMINI.md·gc-auditor 에 반복 | 사용자 레벨 CLAUDE.md 에 한 줄 | |

## 10. 프로젝트 고유로 남길 것

| 프로젝트 | 남길 것 |
|---|---|
| stl-luau | 컨테이너·트레이트 설계 규약(AB/BD/BH/BI 의 현재 판정), 성능 1급 원칙과 `perf-measurements.md`, 네이밍 표, 음성 대조군 스파이크 체계, `GEMINI.md` 의 "좁은 질문만" 원칙(내용은 재작성) |
| rbvm | GC/생명주기 규칙(`gcHold`, `__mode`), 가상 트리 시맨틱, `check.sh`(globalTypes·sourcemap 캐시), 두 감사 에이전트의 **점검 항목**, "const 금지" 사용자 결정(근거가 살아 있다면) |
| moonwave-luau | mrow 재작성 계획(`migration-plan.md`, `mrow-requirements.md`), 파서 파이프라인 구조, 골든 테스트 방식(`stage.sh`) |
| table-sim | "첫 소비자" 방향 선언과 넘지 않는 선 4항, Studio 실측 방법, `feedback/` 마찰 기록 체계, `quad-ui-dev` 는 **원본(quad/docs/skills)을 참조**하도록 바꿈 |
| tbox | 스키마 라이브러리 원칙("가볍게"), pesde 워크스페이스 함정(심볼릭 링크로 크로스 패키지 실행 불가), `init.luau` require 규칙 표, stylua `f<<T>>` 경고(공통 템플릿에도 한 줄) |
| vitrine | "복구 가능성" 요구와 불변식 6개, 두 구현 원칙(Go seal ↔ Python recover), Drive 관련 제약 |
| VideoSync | 비목표(캡처·릴레이 금지), 설계 6줄 요약, **Traps 는 `docs/`로 이관**하고 CLAUDE.md 에는 링크와 상위 5개만 |
| devplorer | 익스플로잇 불가 보안 원칙, 서버/클라이언트 분담 규칙, 코드 배치 규약 |
| mrow | (문서 없음) 최소 CLAUDE.md 를 새로 둘지 사용자 결정. 둔다면 REVIEW.md 에 대한 한 줄 안내 정도 |

---

## 11. 우선순위 권고

1. **즉시(위험)**
   - moonwave-luau 에이전트 문서를 커밋합니다.
   - vitrine 의 `.env` deny 를 추가하고 allow 를 축소합니다.
   - 사용자 레벨에 `deny git push` 를 추가합니다.
   - tbox 의 `AGY_UID` 를 분리합니다.
2. **로드 감량**
   - table-sim `todos.md` 의 완료분을 `archive/` 로 이동합니다(40KB → 약 10KB).
   - devplorer `todos.md` 의 취소선 항목을 정리합니다.
   - stl-luau conventions 에서 경위·수치를 `base/` 로 이동합니다.
   - VideoSync 의 Traps 를 `docs/` 로 이관합니다.
3. **모순 해소**
   - stl-luau `GEMINI.md` 를 BI 에 맞춰 고칩니다(또는 "conventions.md 를 따르라"만 남깁니다).
   - 프로젝트 간 `const` 정책 차이를 `conventions` 에서 "프로젝트 선택"으로 명시합니다.
4. **승격**
   - heavy-proc-guard 와 settings 공통 항목(§7)을 사용자 레벨에 올립니다.
   - 그 다음 delegate-agy 스킬, 감사자 에이전트 틀, `/new-luau-project`(§8) 순입니다.
5. **정리**
   - devplorer worktree 22개 정리, `.gitignore` 에 `/.claude/worktrees/` 추가(stl-luau, rbvm, moonwave, tbox, vitrine), mrow 에 `.gitignore`.
   - `-scratch`/`-proto`/`-codex` 의 정의를 문서화합니다.
