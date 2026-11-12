# 14. 하네스를 툴킷·sandbox 에 묶이지 않게 — 하드코딩 조사와 재구성

작성 2026-11-10. 사용자 요구(같은 날): 이 하네스는 Roblox/Luau 전용이 아니다(블로그 react/astro, vitrine 이 웹 툴킷). 다른 sandbox 에서도 쓰고, 외부 프로젝트 일부를 반입해 감사한다.
개념은 coderag 지식 계층(`coderag/.claude/base/layers-and-packs.md` §13 global / pack / project)과 맞췄다: **코어 = global, 툴킷 + `<툴킷>-kb` = pack, 대상 저장소 = project.**

## 목차
- [1. 하드코딩 표](#1-하드코딩-표)
- [2. 검사 코드 55종 분류](#2-검사-코드-55종-분류)
- [3. 재구성 결과](#3-재구성-결과)
- [4. 회귀 비교](#4-회귀-비교)
- [5. 남은 일](#5-남은-일)

## 1. 하드코딩 표

분류: **코어** = 언어·환경 무관하게 다시 씀, **툴킷** = `toolkits/<이름>`(또는 툴킷 표)로 옮김, **환경** = `home/.claude/harness.env` 키나 변수로 뺌.
처리: ✔ 이번에 고침, ▷ 제안만(다른 작업 중이거나 drafts 기록 문서), – 유지(사례·근거라 그대로 둠).

### 1-1. home/.claude (정본), tools, MANIFEST

| # | 위치 | 하드코딩 | 분류 | 처리 |
|---|---|---|---|---|
| 1 | `CLAUDE.md:3` | "`/code/Projects/*` … 대부분 Roblox/Luau" | 코어 + 환경 | ✔ "작업공간 … 저장소마다 툴킷이 다르다", 경로는 "이 환경" 절 |
| 2 | `CLAUDE.md` 형제 지도 | 툴킷 열 없음, vitrine·VideoSync·coderag 가 "참고"로만 | 코어 | ✔ 툴킷 열(luau / web+go / rust / 하네스) |
| 3 | `CLAUDE.md` luau-kb 행 | "다른 저장소 보러 가기 전에 여기 스킬부터" 가 luau 에만 | 툴킷 | ✔ 머리 문단 "`<툴킷>-kb` 가 정본" + luau-kb 는 표의 한 행 |
| 4 | `CLAUDE.md` ~/.claude 절 | `/code/Projects/claude-doctor/home/.claude/` | 환경 | ✔ "claude-doctor 의 `home/.claude/`" |
| 5 | `CLAUDE.md` 코드 리뷰 | "의존 도구(luau, luau-lsp)", "Luau 관점별 감사 /audit" | 코어 | ✔ "툴체인(luau·luau-lsp, node 등)", "관점별 감사" |
| 6 | `CLAUDE.md` 도구 | `/code/.local/share/mise/installs` | 환경 | ✔ "이 환경" 절로 모음(값의 정본 `HARNESS_TOOL_INSTALLS`) |
| 7 | `CLAUDE.md` 도구 | `choom -n 1000 --` | 환경 | ✔ "이 환경" 절(`HARNESS_HEAVY_WRAP`) |
| 8 | `settings.json` 훅 2개 | `python3 /code/.claude/hooks/…` 절대 경로 | 환경 | ✔ `$HOME/.claude/hooks/…` |
| 9 | `hooks/heavy-proc-guard.py` | choom 을 무조건 요구(없는 sandbox 에서는 감쌀 방법이 없어 무거운 실행이 영구 차단) | 환경 | ✔ `HARNESS_HEAVY_WRAP`. 빈 값·프로그램 없음 → 아무것도 막지 않음 |
| 10 | 같은 파일 | 실행기 `luau`, `lune` 이 기본표에 섞임 | 툴킷 | ✔ `TOOLKIT_EXECUTORS`(luau / web / rust), `HARNESS_TOOLKITS` 로 거름 |
| 11 | 같은 파일 | 면제 `agy-delegate.sh` | 코어 | ✔ `delegate.sh`(통합안 이름도 포함) |
| 12 | `hooks/bash-bypass-reminder.py` | `CODE_EXT` 에 jsx·astro·vue·svelte·css·rs·go 없음 | 툴킷 | ✔ 확장자 추가 |
| 13 | 같은 파일 | `PREFIX` 의 choom·prlimit | 환경 | – 없으면 쓰이지 않아 무해 |
| 14 | `harness-doctor/SKILL.md` description | "/code/Projects 저장소 … Luau 규약·툴체인을 진단", "luau-kb 후보", "툴체인 핀" | 코어 | ✔ 작업공간·intake, 코어 검사 + 감지된 툴킷 |
| 15 | SKILL.md 원칙 2·3 | `/code/Projects/claude-doctor/handoff`, `HUMAN_TODO.md` | 환경 | ✔ `<doctor>`(= `scan.py --env` 의 `DOCTOR_ROOT`) |
| 16 | SKILL.md 절차 1 | `table-sim → /code/Projects/table-sim` | 환경 | ✔ `<작업공간>/table-sim`, `intake/<이름>` 대상 추가 |
| 17 | SKILL.md 원칙 4 | "D-01~D-12는 아직 사용자 확인 전" (실제는 D-01·02·03·06·13 확정, D-04 수정) | 코어(낡음) | ✔ "`.claude/base/decisions/README.md` 현황표가 정본" |
| 18 | SKILL.md 항목 5·8 | "공유 지식 쏠림(luau-kb)", "툴체인" 이 코어 항목처럼 | 툴킷 | ✔ 항목 표에 층(코어/툴킷) 열, 툴킷 문서 행 |
| 19 | `scan.py` `DOCTOR_ROOT` | 대체값 `/code/Projects/claude-doctor` | 환경 | ✔ 환경 변수 > 파일 위치 > harness.env, 없으면 정본 검사 건너뜀 |
| 20 | `scan.py` `D05_TARGET` | 미확정 D-05 를 목표값(0.742/1.70.1/2.5.2)으로 비교 | 툴킷 + 버그 | ✔ luau 툴킷으로, **형제 저장소 핀 사이 불일치만** |
| 21 | `scan.py` `SIDE_EFFECT` | `studio-sync` | 툴킷 | ✔ luau `SIDE_EFFECT_WORDS` |
| 22 | 같은 정규식 | `choom -n` | 환경 | ✔ `HARNESS_HEAVY_WRAP` 앞 두 낱말 |
| 23 | `scan.py` `SKIP_DIRS` | `luau_packages`, `lune_packages`, `Packages` | 툴킷 | ✔ 툴킷 `SKIP_DIRS` |
| 24 | `scan.py` `check_kb` | `<!-- luau-kb 후보`, Luau 용어·`0.7xx` 근거 신호 | 툴킷 | ✔ `toolkits/luau.py` |
| 25 | `scan.py` DRIFT-TYPEDEFS, `--kb` 기본 `projects/luau-kb` | `globalTypes*.d.luau` 와 luau-kb 정본 | 툴킷 | ✔ luau 툴킷, `ctx.kb("luau")` → `<projects 또는 작업공간>/luau-kb` |
| 26 | `scan.py` `check_toolchain` | `.luau` 유무, mise luau·stylua·`.luaurc` | 툴킷 | ✔ luau 툴킷 |
| 27 | `scan.py` DRIFT-UID | `*/.claude/tools/agy-delegate.sh` 사본만 봄, uid 표 위치 모름 | 환경 | ✔ `HARNESS_DELEGATE_REGISTRY` 도 읽음(사본 검사는 유지) |
| 28 | `scan.py` SET-PUSHDENY | "이 sandbox 는 에이전트 push 가 정상 흐름" | 환경 | ✔ `HARNESS_AGENT_PUSH`(normal / deny / 비움) |
| 29 | `scan.py` SET-HOOKPATH(`--user`) | `$HOME` 을 풀지 않음(#8 을 고치면 오탐) | 코어 | ✔ `expandvars` + `expanduser` |
| 30 | `scan.py` `repo_files` | 다른 저장소 안의 무시된 하위 디렉터리(반입 사본)는 `git ls-files` 가 빈 목록 → 툴킷 감지 실패 | 코어 | ✔ 자기 git 루트가 아니면 걷기, 7·9 의 git 검사 건너뜀(`SET-NOGIT` 정보) |
| 31 | `references/toolchain-and-worktrees.md` | §8 Luau 툴체인 + §9 worktree 가 한 파일 | 툴킷 | ✔ §8 → `toolkits/luau.md`, §9 → `worktrees.md` |
| 32 | 같은 파일 §9 | `/code/backups/claude-doctor-<날짜>/` | 환경 | ✔ "이 환경의 선례"로 표시 |
| 33 | `references/staleness-and-kb.md` §5 | luau-kb 정본 경로, Luau 판정 예 | 툴킷 | ✔ 원리만 코어, 값은 `toolkits/luau.md` |
| 34 | `references/drift-and-settings.md` | typedefs 정본 경로·md5, push deny 근거, `claude-doctor/` 경로 | 툴킷 + 환경 | ✔ |
| 35 | `references/fix-protocol.md` | `/code/Projects/claude-doctor/…` 5곳, `/code/.claude`, Luau D-xx 표 | 환경 + 툴킷 | ✔ `<doctor>`, 코어 결정(D-07·D-13)만 남기고 나머지는 툴킷 문서 |
| 36 | `references/load-and-rules.md` | "(e) luau-kb", paths 예 `src/**/*.luau` 만 | 코어 | ✔ |
| 37 | `references/skills.md` | `/code/Projects/stl-luau/.claude/skills`, choom·studio-sync | 환경 + 툴킷 | ✔ |
| 38 | `references/example-report.md` | luau 저장소 v1 출력(D-05 목표 비교) | 툴킷 | ✔ 머리에 "luau 저장소, v1 출력" 주석. 본문 유지 |
| 39 | `tools/home-sync.sh` | MANIFEST 링크 대상이 절대 경로만 | 환경 | ✔ `${VAR}` 확장(harness.env 규칙), 정의 안 된 변수는 건너뜀 |
| 40 | 같은 파일 | `CLAUDE_CONFIG_DIR` 무시 | 코어 | ✔ `CLAUDE_HOME` > `CLAUDE_CONFIG_DIR` > `~/.claude` |
| 41 | `home/MANIFEST` | 링크 9개 `/code/Projects/…` | 환경 | ✔ `${HARNESS_DOCTOR_ROOT}`, `${HARNESS_WORKSPACE}` |
| 42 | 같은 파일 | luau-kb 링크가 일반 링크와 섞임 | 툴킷 | ✔ "툴킷 luau" 묶음 주석 |

### 1-2. drafts (바꾸지 않음 — 제안만)

| # | 위치 | 하드코딩 | 분류 | 처리 |
|---|---|---|---|---|
| 43 | `drafts/agents/luau-{type,runtime,perf,quality}-auditor.md` | 이름·본문의 Luau 도구·사례 | 툴킷 | ▷ `.claude/research/drafts/agents/README.md` §9 |
| 44 | `luau-perf-auditor.md`, `luau-runtime-auditor.md` | `/sys/fs/cgroup/memory.max`, `choom -n 1000 -- prlimit` | 환경 | ▷ §9-3 |
| 45 | `.claude/research/drafts/agents/hooks/auditor-readonly-guard.py` | 설치 명령(pesde·wally·rokit·aftman / npm·pnpm / cargo), `mcp__roblox-studio__*` | 툴킷 | ▷ 툴킷 표로(§9-3) |
| 46 | `.claude/research/drafts/agents/hooks/test-guard.py` | `/code/Projects/example` 픽스처 | 환경 | – 문자열 픽스처라 무해 |
| 47 | `.claude/research/drafts/agents/skills/audit/SKILL.md` | 관점 선택 `*.luau`, `subagent_type=<luau-…>` | 툴킷 | ▷ §9-3 |
| 48 | `.claude/research/drafts/agents/skills/audit-report-format/SKILL.md` | 도구 버전 예 `luau-analyze 0.734`, luau-verify | 툴킷 | ▷ §9-3 |
| 49 | `.claude/research/drafts/delegate/skills/delegate/scripts/delegate.sh` | `AGY_BIN`·`CODEX_BIN` 기본 `/code/.local/share/mise/installs/…` | 환경 | ▷ 기본값을 `HARNESS_TOOL_INSTALLS` 에서 |
| 50 | 같은 파일 | `/code/.claude/.credentials.json` | 환경 | ▷ `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` |
| 51 | 같은 파일 | `choom -n 1000 -- setpriv` | 환경 | ▷ `HARNESS_HEAVY_WRAP`. setpriv(root 필요)는 위임의 환경 전제로 README 에 |
| 52 | `.claude/research/drafts/delegate/skills/delegate/registry.tsv` | 루트 `/code/Projects/<repo>`, uid 61000~61003 | 환경 | ▷ 파일 자체가 환경 값. 위치는 `HARNESS_DELEGATE_REGISTRY` 로(✔ scan 이 읽음) |
| 53 | 같은 파일 setup 열 | `mise exec -- pesde install`(quad) | 툴킷 | – 저장소별 값이라 맞는 자리 |
| 54 | `.claude/research/drafts/delegate/skills/delegate/templates/AGENTS.md.template` | `/code/Projects/claude-doctor/packs/luau-kb/AGENTS.md`, `/code/Projects/<repo>/vendor/` | 환경 + 툴킷 | ▷ `{{WORKSPACE}}`·툴킷 KB 자리표시 |
| 55 | `.claude/research/drafts/delegate/{conventions,migration,model-traits,trial-…}.md` | `/code/Projects`, uid, `/code/.claude/projects/…` | 환경 | – 경위·실험 기록이라 그대로 |
| 56 | `.claude/archive/research/drafts/style/skills/luau-style/` 전체 | Luau 스타일 | 툴킷 | – luau-kb 로 갈 툴킷 지식(맞는 자리) |
| 57 | `luau-style/scripts/structure-scan.py` | 길이 기준 800·1,500(D-13, 언어 무관) 이 Luau 스킬 안 | 코어 | ▷ 하네스 공용 위치로(§9-3) |
| 58 | `luau-style/scripts/structure-scan.py` docstring | `/code/Projects/table-sim` 예 | 환경 | – 예시 |

### 1-3. 집계

여러 분류에 걸친 행(#1, #34, #35, #37, #54)은 주 분류 하나로만 셌다.

| 분류 | 건수 | 이번에 고침 ✔ | 제안 ▷ | 유지 – |
|---|---:|---:|---:|---:|
| 코어로 일반화 | 11 | 10 | 1 | 0 |
| 툴킷 자리로 | 21 | 15 | 4 | 2 |
| 환경 설정으로 | 26 | 16 | 6 | 4 |
| **합계** | **58** | **41** | **11** | **6** |

## 2. 검사 코드 55종 분류

scan.py v1 의 코드 55종(`grep -oE '"[A-Z]+-[A-Z0-9]+"' scan.py | sort -u`). v2 에서도 이름과 등급은 그대로다.

| 항목 | 코드 | 층 | 비고 |
|---|---|---|---|
| 0 세션 | `SESSION-LIVE`, `SESSION-SIBLING` | 코어 (2) | 반입 사본은 SIBLING 을 보지 않음 |
| 1 상시 로드 | `LOAD-ANCESTOR`, `LOAD-CHARS`, `LOAD-GOAL`, `LOAD-HOPS`, `LOAD-IMPORT`, `LOAD-OVER200`, `LOAD-TOTAL` | 코어 (7) | `LOAD-TODOS-DONE` 도 코어(하이픈이 둘이라 55종 목록 정규식에서 빠짐) |
| 2 rules | `RULE-BIG`, `RULE-DEADGLOB`, `RULE-DUP`, `RULE-NOPATHS`, `RULE-PARSE` | 코어 (5) | |
| 3 스킬 | `SKILL-DESC`, `SKILL-KEY`, `SKILL-LINES`, `SKILL-NAME`, `SKILL-NEST`, `SKILL-ORPHAN`, `SKILL-PARSE`, `SKILL-SIDEFX`, `SKILL-TOC`, `SKILL-UNMANAGED`, `LINK-TARGET` | 코어 (11) | `SKILL-SIDEFX` 낱말은 코어 + 툴킷(`studio-sync`) + 환경(래퍼). `SKILL-NEST` 는 SKILL.md 가 바로 가리키는 하위 폴더 문서를 허용하게 고침(`references/toolkits/`). `LINK-TARGET` 은 MANIFEST 변수를 푼다 |
| 4 낡음 | `STALE-DATED`, `STALE-DATETAGS`, `STALE-MISMATCH`, `STALE-SUPERSEDED` | 코어 (4) | `STALE-AGENTDOC-OLD` 도 코어(같은 이유로 목록에서 빠짐) |
| 5 공유 지식 | `KB-MARK`, `KB-CAND` | **툴킷 luau** (2) | 원리는 코어 문서, 표시·용어는 luau |
| 6 사본 | `DRIFT-HOOK`, `DRIFT-HOOKDUP`, `DRIFT-SKILLCOPY`, `DRIFT-DELEGATE`, `DRIFT-UID` | 코어 (5) | UID 는 환경의 uid 표도 읽음 |
| 6 사본 | `DRIFT-TYPEDEFS` | **툴킷 luau** (1) | |
| 7 설정 | `SET-BROADALLOW`, `SET-DIRTY`, `SET-HOOKPATH`, `SET-JSON`, `SET-LOCALIGNORE`, `SET-NOGIT`, `SET-PUSHDENY`, `SET-SYNC`, `SET-UNTRACKED`, `SET-WTIGNORE` | 코어 (10) | PUSHDENY 문구는 환경 정책, NOGIT 은 반입 사본이면 정보 |
| 8 툴체인 | `TOOL-PIN`, `TOOL-SYNTAX`, `TOOL-NOSTYLUA`, `TOOL-CLAIM`, `TOOL-LUAURC` | **툴킷 luau** (5) | PIN 은 형제 불일치만 |
| 9 worktree | `WT-ACTIVE`, `WT-CANDIDATE`, `WT-ORPHAN` | 코어 (3) | |

**55종 중 코어 47, 툴킷 luau 8** (KB 2 + TYPEDEFS 1 + TOOL 5). 목록 밖 2종(`LOAD-TODOS-DONE`, `STALE-AGENTDOC-OLD`)을 더하면 코어 49. web 은 0(예약 `WEB-LOCK`, `WEB-TSSTRICT`, `WEB-LINT`, `WEB-CMDS`, `WEB-NODEPIN`, `WEB-GENERATED`).

## 3. 재구성 결과

### 3-1. 파일

| 파일 | 상태 | 내용 |
|---|---|---|
| `home/.claude/harness.env` | 새로 | 이 sandbox 값: `HARNESS_WORKSPACE`, `HARNESS_DOCTOR_ROOT`, `HARNESS_TOOL_INSTALLS`, `HARNESS_HEAVY_WRAP`, `HARNESS_DELEGATE_REGISTRY`, `HARNESS_AGENT_PUSH`(`HARNESS_TOOLKITS` 는 주석 = 전부) |
| `home/.claude/lib/harness_env.py` | 새로 | 읽기 규칙(KEY=VALUE, source 안 함, `${VAR}`·`~`, 환경 변수 우선)과 `DEFAULTS` |
| `home/MANIFEST` | 고침 | `harness.env`, `lib/harness_env.py` 추가, 링크 대상 변수화 |
| `tools/home-sync.sh` | 고침 | 변수 확장(같은 규칙의 bash 판), `env` 하위 명령, `CLAUDE_CONFIG_DIR` |
| `home/.claude/hooks/heavy-proc-guard.py` | 고침 | 래퍼·툴킷 실행기를 harness.env 에서 |
| `home/.claude/hooks/bash-bypass-reminder.py` | 고침 | 웹·rust 확장자 |
| `home/.claude/settings.json` | 고침 | 훅 경로 `$HOME/.claude/hooks/…` |
| `home/.claude/CLAUDE.md` | 고침 | 49 → **40줄**, 툴킷 열, "이 환경" 절 |
| `skills/harness-doctor/SKILL.md` | 고침 | description·본문 일반화, `--env`, `intake/`, 층 열 |
| `skills/harness-doctor/scripts/scan.py` | 고침(v2) | 코어만. 툴킷 로더·감지, `--toolkits`, `--env`, 반입 사본, 공용 도우미(`pin_mismatch`, `sibling_repos`) |
| `scripts/toolkits/luau.py` | 새로 | KB-·DRIFT-TYPEDEFS·TOOL- (D-05 수정 포함) |
| `scripts/toolkits/web.py` | 새로 | **골격**: 감지 + `CANDIDATES` 6개, 검사 없음 |
| `references/toolkits/{README,luau,web}.md` | 새로 | 구조·인터페이스·새 툴킷 추가 절차 / luau 판정 기준 / web 골격 |
| `references/worktrees.md` | 이름 바꿈 | 옛 `toolchain-and-worktrees.md` 의 §9 |
| 그 밖의 references 5개 | 고침 | 경로 `<doctor>`·`<작업공간>`, Luau 값은 툴킷 문서로 |
| `README.md` | 새로 | 저장소 지도, 다른 sandbox 설치 순서(클론 → harness.env → home-sync env/status → diff/apply → 플러그인 마켓 → 진단) |
| `intake/README.md`, `.gitignore` | 새로·고침 | 반입 절차, `intake/*/` 제외·`!intake/README.md` |
| `.claude/research/drafts/agents/README.md` | §9 추가 | 감사자 일반화 제안(파일은 안 바꿈) |

### 3-2. 툴킷 감지 (실측, 읽기 전용)

| 저장소 | 툴킷 | 표식 |
|---|---|---|
| quad | luau + web | `*.luau` 3007, mise luau·luau-lsp·pesde·rojo, `default.project.json`, `.luaurc`, `pesde.toml` / `docs/site/package.json: astro` |
| devplorer | luau + web | … / `docs/package.json: astro` |
| stl-luau(-doctor), table-sim, tbox, moonwave-luau, rbvm, luau-kb, claude-doctor | luau | `*.luau`(claude-doctor 는 `.claude/archive/research/drafts/gaps/snippets`) 등 |
| vitrine | web | `web/package.json: react, vite`, tsx 7 |
| VideoSync, coderag | 없음 | go·node 플러그인, rust — 툴킷 미정(코어만) |

반입 사본 시험: vitrine(CLAUDE.md, `.claude/`, `web/package.json`·`tsconfig.json`·`src/main.tsx`)과 rbvm(CLAUDE.md, `.claude/`, `stylua.toml`, `default.project.json`, `src/init.luau`)을
`intake/_selftest-*/`에 복사해 scan → 각각 web, luau 로 감지, `SET-NOGIT` 정보 1건, git·worktree 검사 건너뜀을 확인한 뒤 사본을 지웠다.
rbvm 사본에서는 git 무시 캐시 `.claude/cache/globalTypes.d.luau` 가 걸어져 `DRIFT-TYPEDEFS` 가 났다 → `intake/README.md` 에 "캐시는 가져오지 않는다" 로 반영.

### 3-3. 이식성 시험

| 시험 | 결과 |
|---|---|
| home-sync 옛판(HEAD) vs 새판, 빈 `CLAUDE_HOME` 에서 status → diff → apply → status → apply → diff | 링크 9개 대상 문자열·실제 심볼릭 링크 **동일**. 차이는 MANIFEST 줄 순서와 새 관리 파일 2개(harness.env, lib)뿐. 두 번째 apply·diff 는 빈 출력(멱등) |
| 다른 sandbox 모의(`/tmp/…/ws2/claude-doctor`, harness.env 없음, luau-kb 일부만) | 기본값 `HARNESS_WORKSPACE=ws2`, `HARNESS_DOCTOR_ROOT=ws2/claude-doctor` 로 링크, 없는 대상은 "링크 대상 없음"·apply 건너뜀, 정의 안 된 `${NOPE_VAR}` 줄은 경고 후 건너뜀 |
| bash·python 읽기 규칙 일치(따옴표, 줄 끝 주석, `${A}`·`$A`·`~`, export) | 같은 결과 |
| heavy-proc-guard 12건(이 sandbox) | 12/12. 새로 막는 것: `pnpm run bench`, `cargo bench`(web·rust 실행기). 새로 통과: `bash delegate.sh run 'bench'` |
| heavy-proc-guard, choom 없는 PATH + harness.env 없음 / `HARNESS_HEAVY_WRAP=` | 아무것도 막지 않음, exit 0. 깨진 입력도 exit 0 |
| scan.py 를 claude-doctor 밖에 복사, lib·harness.env 없음, HOME 바꿈 | 동작. `DOCTOR_ROOT=(모름)` → 정본 비교(DRIFT-HOOK, MANIFEST) 건너뜀, PUSHDENY 문구 중립 |
| `claude plugin validate home/.claude/skills` | 통과 |

## 4. 회귀 비교

13개 저장소(VideoSync, coderag, devplorer, moonwave-luau, quad, rbvm, stl-luau, stl-luau-doctor, table-sim, tbox, vitrine, claude-doctor, luau-kb)와 `--user` 에
재구성 전 scan.py(스냅숏)와 후를 `--json --today 2026-11-10` 으로 돌려 `(등급, 코드, 위치)` 다중집합을 비교했다. 휘발 코드(SESSION-·WT-)는 따로 셌다.

| 결과 | 건수 | 설명 |
|---|---:|---|
| 사라진 발견 | 1 | `--user` `LOAD-GOAL` — 사용자 CLAUDE.md 를 49 → 40줄로 줄인 결과(의도) |
| 새 발견 | 0 | |
| 문구만 바뀜 `TOOL-PIN` | 7 | D-05 목표 비교 → 형제 핀 불일치. 예: stl-luau "D-05 권고 목표와 같다" → "luau 0.742 ↔ 0.734(devplorer·moonwave-luau·quad·table-sim·tbox); luau-lsp 1.70.1 ↔ 1.69.0(…)" |
| 문구만 바뀜 `SET-PUSHDENY` | 2 | rbvm, table-sim — 정책 출처를 harness.env 로 |
| 문구만 바뀜 `TOOL-CLAIM` | 5 | 형제 이름 순서만(이제 정렬). 내용 집합은 같음을 확인 |
| 휘발 | — | quad WT-CANDIDATE 7→9 / WT-ACTIVE 3→1, claude-doctor SESSION-LIVE 1→0 — 실행 시각의 세션·worktree 활동 차이 |

`TOOL-PIN` 은 "불일치만" 규칙인데도 모든 luau 저장소에서 남았다. 지금 핀이 실제로 0.734/0.742, 1.69.0/1.70.1 로 갈려 있기 때문이다. 핀이 모두 같아지면 사라진다.

## 5. 남은 일

1. **반영(사용자)**: `tools/home-sync.sh diff` 검토 → `apply`. 지금 status: 링크 9개 "링크 필요", settings·CLAUDE.md·훅 2개 "다름", harness.env·lib "실제에 없음".
   apply 전에는 실제 `~/.claude/hooks/heavy-proc-guard.py` 가 옛판(choom 고정)이다. harness-doctor 링크도 아직 없다.
2. **drafts 감사자 일반화**: `.claude/research/drafts/agents/README.md` §9 의 안 A — `luau-quality-auditor.md` 작업이 끝난 뒤, 사용자 승인 후. G2 시나리오로 "Read 주입"을 sonnet 으로 잰다.
3. **structure-reminder(다른 에이전트 작업 중, 건드리지 않음)**: 툴킷 무관하게 쓰려면 확장자별 기준 표가 필요하다 — 소스 확장자(luau `.luau`, web `.ts/.tsx/.astro/.vue/.svelte`, rust `.rs`)와 테스트 판정(`*.spec.luau` / `*.test.ts`, `__tests__/`, `tests/*.rs`), 생성물 제외(`dist/`, `.astro/`, `target/`, `schema.d.ts`). 800·1,500 기준(D-13)은 그대로. `HARNESS_TOOLKITS` 로 거르는 방식은 heavy-proc-guard 와 같게.
4. **delegate 초안**(#49~52, #54): `AGY_BIN`·`CODEX_BIN` 기본값을 `HARNESS_TOOL_INSTALLS` 에서, credentials 경로를 `CLAUDE_CONFIG_DIR` 에서, 래퍼를 `HARNESS_HEAVY_WRAP` 에서 읽게. P4 설치 때 `HARNESS_DELEGATE_REGISTRY` 를 설치 위치로 바꾼다.
5. **web 툴킷 채우기**: 블로그·vitrine 을 `intake/` 로 반입해 `references/toolkits/web.md` "채우는 순서"대로. `WEB-NODEPIN` 은 `pin_mismatch` 를 재사용한다.
6. **rust·go 툴킷**: coderag(rust), vitrine·VideoSync(go)는 지금 코어만 돈다. 필요해지면 `references/toolkits/README.md` 절차로(heavy-proc-guard 는 이미 `cargo` 를 안다).
7. **사용자 CLAUDE.md "이 환경" 절**: 상시 로드 문서라 harness.env 를 읽지 못해 값이 두 곳에 있다. 다른 sandbox 는 둘 다 고쳐야 한다(README 에 적음). 정본 하나로 줄이려면 home-sync 가 apply 때 그 절을 harness.env 로 채우는 방식을 검토.
8. **커밋 관련 주의**: `references/toolchain-and-worktrees.md → worktrees.md` 이름 바꿈을 `git mv` 로 했는데, 그 스테이징이 다른 작업의 커밋 `38cc7e4`(D-13 반영)에 내용 변경 없는 rename 으로 함께 들어갔다. 이후 내용 수정은 작업 트리에만 있다.
9. **SKILL-SIDEFX `roblox-luau`(`--user`)**: luau-kb 스킬의 `studio-sync` 언급이 계속 잡힌다(전후 같음). luau-kb 쪽 판단이라 그대로 둔다.
