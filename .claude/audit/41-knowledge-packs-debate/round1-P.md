# 41 지식 팩 토론, 1라운드: P (coderag 를 하네스 무관 지식 서비스로)

> Snapshot 2026-11-12. 측정: `coderag` debug 빌드(`target/debug/coderag`, 2026-11-12 11:08), `CODERAG_HOME=/tmp/p41/home`(~/.coderag/coderag.toml 사본) `CODERAG_CACHE=/tmp/p41/...`, 모든 실행 `choom -n 1000 --`. RSS 는 `getrusage(RUSAGE_CHILDREN).ru_maxrss`. 저장소 밖에 쓴 것은 /tmp/p41 뿐.

입장: 팩은 **순수 데이터**(frontmatter 달린 md, `coderag.toml` 매니페스트, `rules/*.md`, snippets)이고, 진입점(규칙 주입, compact 회차, 검색, AGENTS.md 생성, MCP)은 **coderag 한 곳**이 하네스별 어댑터로 맡는다. 행동 플러그인(q, qwreey-advisor, qwreey-conventions, qwreey-proc-guard)은 플러그인으로 남는다.

먼저 인정할 것 셋.
1. Claude Code 에서 스킬 description 으로 자동 라우팅하고 프로젝트별로 켜는 그릇은 **플러그인이 가장 낫다**(audit/40: `paths` 는 설명을 숨기지 않고, 켜고 끄기는 `enabledPlugins` 만 된다). 그래서 팩마다 `plugin.json` + `skills/` 는 남는다. 내가 없애려는 것은 팩마다 복제되는 **코드**(훅)다. 매니페스트 한 장은 복제가 아니라 선언이다.
2. 이 환경에서 codex·agy 는 지금 주로 **위임 백엔드**(좁은 질문, headless, `research/drafts/delegate/`)다. 그러니 락인 해소는 당장의 1순위 이득이 아니라 2순위다. 1순위는 중복 제거와 신선도다.
3. 메모리만 보면 daemon 이 이긴다는 말은 지금 수치로는 작다(4장). daemon 의 진짜 값은 무거운 자산(임베딩 모델)이 생길 때다.

## 0. 측정 (오늘의 CLI)

| 항목 | 값 |
|---|---|
| `search --layer pack 타입 한계`(pack 만, 빈 프로젝트) | 32ms, maxrss 11.4MB (`--version` 3ms, 11.2MB 와 거의 같음) |
| luau-kb pack 색인 디스크 | 812KB(JSONL, 모듈 12개). 팩 원문 md 합계(luau-kb+web-security) 1.06MB, `##` 절 685개 |
| claude-doctor 에서 `search 제네릭 콜백` | 216ms, 46.3MB. `gen` 1.11s, 38.3MB, 색인 4.9MB |
| `stale` (같은 루트) | 1.89s, 191건 / 문서 965개 |
| 팩 Python 훅 `rules_inject.py` 한 번(맞는 rule 없음) | 17-19ms. 파일 열 때마다 web-security·luau-kb·qwreey-conventions 가 각자 하나씩 띄움 |
| Claude 세션 프로세스 | 4개, 223-512MB(합 1.41GB). cgroup `memory.max` 10GiB 에 `memory.current` 8.9GB |

**발견(버그)**: claude-doctor 에는 `.coderag/` 도 `coderag.toml` 도 없어서 project 루트 발견이 조상으로 올라가는데, `HOME=/code` 이고 5a 1단계로 `~/.coderag/`(= `CODERAG_HOME`)가 생겼으므로 **`/code` 가 project 루트가 된다**. project 계층이 `/code/.claude` 전체(플러그인 캐시, 세션 로그 포함 7,941항목)가 되어 216ms·1.1s·191건이 나왔다. `$CODERAG_HOME` 디렉터리는 project 표식에서 빼야 한다(coderag `project.rs:21`). 이 수치는 "CLI 가 느리다"가 아니라 "루트 발견이 틀렸다"는 증거다. pack 만 보면 32ms 다.

## 1. 구조

```
packs/<p>/            (데이터만)  coderag.toml [pack] · skills/<m>/{SKILL.md,references/} · rules/*.md(paths:) · always.md(선택, ≤10줄) · snippets/ · plugin.json(Claude 스킬 노출용 선언)
coderag (바이너리 하나)
 ├ core: 계층 색인·검색·stale·rules 매칭(glob, dedup 키)·회차
 ├ 어댑터: hook claude <event> | hook agy <event> | static-gen agents-md | mcp (stdio)
 └ (나중) serve: 공유 백엔드, 있으면 위 진입점이 위임
coderag 플러그인 (Claude 쪽 하나): PostToolUse·PreCompact·SessionStart 훅 + doc-locator
```

- **rules 주입의 주인은 coderag core.** 지금 `rules_inject.py` 의 의미(공식 paths 와 같은 glob, Read 뒤 본문, Edit 뒤 "대조하라" 한 문장, 프로젝트 밖 Read 생략, `(session, agent, 회차, rule)` 마커 O_EXCL)를 Rust 로 한 번 구현한다. 입력은 "이 프로젝트에서 켜진 팩들의 `rules/`". 이미 `coderag hook post-edit`/`pre-bash`(`hook.rs`)가 같은 자리에 있으므로 새 진입점이 아니라 이벤트 하나를 더하는 것이다.
- **compact 회차도 core.** 팩마다 PreCompact 훅과 `$TMPDIR/claude-<plugin>-epoch` 를 두지 않고, coderag 플러그인의 PreCompact 하나가 `claude-coderag-epoch` 를 올린다. 모든 팩의 rule 마커가 이 회차를 쓴다. 팩끼리 회차를 공유해도 되는 이유: 팩 rules 를 넣는 주체가 하나이기 때문이다(compact_epoch.py 가 플러그인별로 나눈 이유는 서로 다른 훅끼리 얽히지 않게였다).
- **스킬 description(상시 비용) 대 온디맨드.** 측정상 팩 13개 스킬 description 합 486자로 작다. 상시에 둘 것: description(라우팅), `always.md`(사실 몇 줄, §35.6 형식 제약). 온디맨드: references 본문, 절 단위 `get`. 결정 트리(SKILL.md)는 손으로 고른 추론 경로라 검색으로 대체하지 않는다(coderag/.claude/base/hooks-and-rules.md §20 그대로).
- **하네스별**
  | | 스킬 | 경로 조건부 rules | 상시 사실 | 온디맨드 |
  |---|---|---|---|---|
  | Claude Code | 팩 플러그인(enabledPlugins) | coderag 플러그인 PostToolUse `additionalContext` | SessionStart 훅 | doc-locator, `coderag search/get`, MCP |
  | codex 0.166 | `.agents/skills` 노출(§31) | 훅은 있음(`--dangerously-bypass-hook-trust` 플래그로 확인), 주입 계약 **미확인** → 우선 MCP `rules_for(path)` + AGENTS.md 한 줄 | AGENTS.md T1(마커 블록) | MCP `search/get` |
  | agy | `.agents/skills`, `~/.gemini/config/skills` | glob rules 없음(GEMINI.md/AGENTS.md 는 디렉터리 범위만). PostToolUse 출력은 `{}` 만 받음 → PostToolUse 로 연 파일을 기록하고 **PreInvocation `injectSteps`** 로 넣는 2단 어댑터(**미실측**) | AGENTS.md T1 | MCP(`mcp_config.json`, stdio 지원) |

## 2. 프로세스 모델

| 모델 | 수명(누가 켜고 끄나) | 이 샌드박스의 메모리 | 할 수 있는 것 | 대가 |
|---|---|---|---|---|
| CLI(지금) | 호출마다 3-30ms 살다 죽음 | 상주 0, 순간 11-46MB | 결정적 검색, stat 기반 stale(§22 B) | 매번 색인 파싱. 감시 불가. 에이전트가 셸 정책을 거쳐야 함 |
| MCP stdio | 하네스가 세션마다 띄우고 세션 끝에 죽임(고아 없음) | 세션당 상주 ≈11MB + 색인 | 셸 없이 도구로 호출, 세션 안에서 색인 따뜻하게, **세션 안 inotify 감시**와 증분 gen | 세션 수만큼 프로세스. 도구 정의 토큰(도구 2-3개면 수백 토큰) |
| daemon(`coderag serve`, 소켓) | 첫 클라이언트가 자동 기동, idle N분 뒤 스스로 종료. 바이너리 버전이 다르면 재기동 | 기계당 하나 | 감시 한 번, 쓰기 주체 하나(gen 경합 없음), 무거운 모델 한 벌 | 기동·버전 어긋남·소켓 권한, **OOM 한 번에 모든 세션이 잃음**(그래서 choom 1000 으로 먼저 죽게 하고 클라이언트는 in-process 로 폴백) |
| 공유 mmap 색인 | 파일이라 수명 없음 | 페이지 캐시를 프로세스끼리 공유 | CLI·stdio 그대로 두고 색인 메모리 한 벌 | JSONL 을 mmap 가능한 이진 형식(예: fst/tantivy 세그먼트)으로 바꾸는 작업 |

- 사용자 말 "cli 를 직접 호출하지 않아도": MCP stdio 가 답이다. 다만 MCP 는 **CLI 와 같은 core 위의 얇은 어댑터**로, 출력도 같은 두 줄 형식(§31)으로 둔다. 그래야 MCP 가 없는 곳(hook, doc-locator 의 Bash)과 결과가 같다.
- fs watch 는 daemon 이 없어도 된다. stdio 서버가 세션 동안 팩 루트와 project 루트를 inotify 로 보고 바뀐 모듈만 gen 하면 된다. 세션이 셋이면 감시도 셋이지만 inotify 는 싸다. 대신 gen 이 겹치므로 §22 의 `.coderag/.lock`(기다리지 않고 건너뜀)이 필요하다.
- 본문 낱말·블룸 필터: 685절 × 1KB 블룸 ≈ 0.7MB, 본문 역색인은 원문 1MB 의 몇 배. 둘 다 CLI 로도 감당한다(파싱이 문제면 mmap). **CLI 구조의 진짜 한계는 둘뿐이다**: 세션을 넘는 감시·캐시가 없다는 것, 매 호출 모델 로드가 필요한 의미 검색을 못 한다는 것.

## 3. 사용자 쟁점: 여러 저장소 동시 개발과 메모리

사용자: "coderag 가 여러 곳에서 인보크 되어 메모리를 점유하는것 보다, 하나의 mcp 구조나…global 에 있는건 복제 없이 한 메모리에 올라간다면 오히려 가벼울 수도". 맞는 지적이고, 구분이 필요하다. **MCP stdio 는 세션마다 한 프로세스**라 복제가 그대로다. 한 벌이 되는 것은 공유 daemon 이나 공유 mmap 색인뿐이다.

table-sim·quad·stl-luau 세 세션이 동시에 luau-kb 를 쓴다고 하면(색인 메모리 ≈ 디스크 JSONL 의 7배로 추정: claude-doctor 4.9MB → 46MB-11MB≈35MB 에서 얻은 비):

| 모델 | 키워드 색인(오늘) | + 본문 색인 | + 로컬 임베딩 모델(작은 모델 가중치·런타임 ≈150-300MB 추정) |
|---|---|---|---|
| 호출마다 CLI | 상주 0, 순간 3×≈17MB(동시에 불릴 때만) | 순간 3×≈30MB | 호출마다 모델 로드: 지연 수 초, 순간 3×300MB, **사실상 불가** |
| 세션당 MCP stdio | 3×(11+luau-kb ≈6+project) ≈ 60-100MB 상주, luau-kb 3벌 | ≈ 100-150MB | **3×300MB ≈ 0.9GB 상주** |
| 공유 daemon | 1×(11+6+project 셋) ≈ 40-60MB | ≈ 60-80MB | **1×300MB** |
| 공유 mmap 색인 + CLI/stdio | 프로세스당 힙 몇 MB + 색인 페이지 한 벌 | 같음 | 모델은 공유 안 됨(stdio 와 같음) |

- 읽는 법: 키워드·본문 색인까지는 어느 모델이든 Claude 세션 하나(223-512MB)의 2-30% 수준이고, 복제 비용 차이는 수십 MB 다. 지금 cgroup 여유가 약 1.8GB 라 무시할 값은 아니지만 결정 요인은 아니다.
- 의미 검색을 넣는 순간 순서가 바뀐다. 모델 한 벌을 세션마다 띄우면 세 세션에 약 0.9GB 로 OOM 을 다시 부를 수 있다. **그래서 daemon 은 "의미 검색을 할 때의 필수 조건"이고, 그 전에는 mmap 색인이 같은 이득을 수명 문제 없이 준다.** 이 수치는 추정이며(모델 크기는 고르지 않았다) 7단계에서 잰다.

## 4. 중복이 사라지는 방식

- 지금: `rules_inject.py`(267줄)·`compact_epoch.py`(81)·`conv_env.py`(32) 가 web-security·luau-kb 에 바이트 같은 사본으로 있고, 팩마다 `hooks.json`, 이를 지키는 `tools/tests/test-vendored-copies.py` 가 있다. 팩이 하나 늘 때마다 380줄과 훅 등록 하나, 파일 열 때마다 Python 한 번(17ms)이 는다.
- 뒤: 팩 폴더에서 `hooks/` 가 없어진다. 파일 열 때 도는 것은 coderag 훅 하나(Rust, 기동 3ms 측정)가 켜진 팩 전부의 rules 를 한 번에 본다.
- 팩이 담을 것(이것만): `coderag.toml [pack]`(이름·설명·taxonomy·modules), `skills/`(Agent Skills 사양, references 에 frontmatter), `rules/*.md`(`description`, `paths`), 선택 `always.md`, 데이터(snippets, typedefs, `.lsp.json`), `plugin.json`(Claude 노출용). 코드는 팩 자신의 도구(`tools/`, `scripts/`)만, 주입·회차 같은 하네스 배관은 금지.
- qwreey-conventions 는 자기 rules 를 계속 자기 `rules_inject.py` 로 넣는다(행동 플러그인, coderag 없어도 동작해야 함). 정본 사본이 1개 남고 사본은 0개가 된다.

## 5. 락인: 남는 Claude 의존과 폴백

- Claude 에만 있는 것: 플러그인 단위 켜기, PostToolUse `additionalContext`, subagent `agent_id`, PreCompact. 이것들은 **coderag 의 claude 어댑터 안에만** 있게 한다. 팩에는 없다. 지금은 팩마다 Claude 훅 계약이 박혀 있어 팩 자체가 Claude 전용이다. 이것이 사용자가 말한 락인이다.
- 폴백 계단(하네스가 지원하는 가장 위 칸을 쓴다): ① 훅으로 경로 조건부 주입 → ② MCP `rules_for(path)` 를 "편집 전에 부르라"는 AGENTS.md 한 줄과 함께(모델이 지켜야 하니 약하다) → ③ AGENTS.md T1 에 팩별 핵심 몇 줄 상시(§19, 40줄 상한, codex 32KiB, agy 24KB/파일·20k 토큰 규칙 예산).
- 켜기 스위치: 하네스 무관한 정본은 project `coderag.toml` 의 팩 목록으로 두고, Claude `enabledPlugins` 는 거기서 파생한다(`q:doctor` 의 `PACK-*` 검사가 둘이 어긋나면 알림). 스위치가 둘이 되는 위험은 인정한다(질문 1).

## 6. 지식이 자라는 길과 낡음

- 웹 저장소 세션에서 교훈이 나오면: 그 저장소 `.claude/` 에 평소대로 기록하고 frontmatter `tags: [promote:web-security]` 를 단다. coderag 가 project 계층에서 이 태그를 모아 `coderag pack candidates` 로 보이고, claude-doctor 세션(정본 소유)이 팩으로 옮기며 `last_verified`·`origin` 을 단다. 0.3.0 의 하드닝 노트 반입이 이 흐름을 손으로 한 것이다.
- **신선도 차이가 핵심 근거다.** 플러그인 캐시는 버전마다 폴더를 복사하므로 rules·references 수정은 버전을 올리고 업데이트할 때까지 Claude 에 안 닿는다. coderag pack 은 등록 경로(지금은 저장소 사본)를 직접 읽어 고치면 바로 닿는다(`~/.coderag/coderag.toml` 주석 그대로). 주입을 coderag 가 하면 rules 도 그 신선도를 얻는다. 스킬 description·SKILL.md 만 플러그인 버전에 묶인다.
- 낡음: `review_after`·`last_verified`(기본 90일)·`applies_to`(luau 버전)를 `stale` 이 이미 본다. 주입 블록과 검색 결과에 `pack:luau-kb · verified · rev` 머리를 붙인다. 원문이 색인 뒤 바뀌면 stat 비교(§22 B)로 알리고, stdio/daemon 이 있으면 감시로 바로 다시 만든다.
- 팀 계층: §35 선반은 이 팩 모양(폴더 = 꾸러미, `always.md`, 수락 해시)을 그대로 받는다. 팩이 데이터만 갖는다는 원칙이 §27.7 "실행 묶음 미적재"와 같은 방향이라, 지금 훅을 빼 두면 나중에 팩을 선반에 올릴 때 걸리는 것이 없다.

## 7. 배포와 coderag 가 없을 때

- 바이너리: GitHub release(정적 musl 빌드, 사용자가 sandbox 밖에서 GPG 서명). claude-doctor `tools/` 에 받기·서명 확인·없으면 소스 빌드 스크립트, `q:start` 가 부른다. 비프로그래머 동료는 이 스크립트 한 번만 겪는다. 팩은 release tarball 이나 git 으로 `coderag pack fetch`.
- 없을 때(동료 기기, 바이너리 없음): 팩 플러그인의 스킬과 references 는 평문이라 Claude 에서 그대로 동작한다(라우팅 표 → Read). 빠지는 것은 경로 조건부 rules 주입과 검색이다. `bin/coderag` 는 이미 `hook` 일 때 조용히 0 으로 끝나므로 세션을 깨지 않는다. 대신 조용히 빠지면 안 되므로 `q:doctor` 가 `PACK-NO-CODERAG`(켜진 팩에 rules 가 있는데 coderag 가 없음)를 warn 으로 알린다. 저하이지 고장은 아니다.
- 비용 고지: MCP 도구 정의는 켠 세션마다 상시 토큰을 쓴다(도구 2-3개). daemon·의미 검색은 메모리 비용이 있다(3장). 둘 다 기본 꺼짐으로 두고 사용자가 켠다.

## 8. 이행 (작고 되돌릴 수 있게, 단계마다 잴 것)

1. **루트 발견 수정**(coderag): `$CODERAG_HOME` 을 project 표식에서 뺌. 잴 것: claude-doctor 에서 `gen` 항목 수·시간(지금 7,941항목 1.1s → claude-doctor 만), audit/39 골든 12문항 hit@5 유지.
2. **rules 매칭을 core 로**: `coderag rules match <file>` + `hook claude post-tool`. `rules_inject.py` 와 같은 입력에 같은 출력인지 골든 비교(glob·dedup·프로젝트 밖·Edit 문장). 잴 것: 훅 지연(<10ms 목표, Python 17ms), 파리티 100%.
3. **web-security 먼저 이전**: 팩의 `hooks/` 제거, coderag 플러그인이 주입. audit/34 R1-R4 식 준수 프로브(본 세션·서브에이전트·compact 뒤 재주입). 되돌리기: hooks.json 복원 한 커밋. 그 다음 luau-kb.
4. **켜기 스위치 일치**: project `coderag.toml` 팩 목록 ↔ `enabledPlugins`, `q:doctor` 검사. 잴 것: claude-doctor 에서 `.sh` 를 열 때 web-security rules 가 안 들어오는지(지금은 팩이 꺼져 있어 안 들어옴; 이전 뒤에도 같아야 함).
5. **`coderag mcp` stdio**(search·get·rules_for, CLI 와 같은 출력): delegate 의 codex·agy 실행에 등록. 잴 것: 세션당 RSS, 도구 정의 토큰, 위임 과제에서 팩 지식을 실제로 찾는지.
6. **AGENTS.md generator**(§19 T1/T2) + agy PreInvocation 주입 실측. 잴 것: agy 가 주입을 지키는지, AGENTS.md 크기 상한.
7. **본문 색인·mmap 형식** 뒤 필요하면 **daemon + 의미 검색**. 잴 것: 골든 문항(q03·q05 처럼 제목에 없는 사실) hit@5, 세 세션 동시 RSS, OOM 시 폴백.

## Q 가 다툴 것으로 보는 점
- "스위치가 둘(coderag.toml, enabledPlugins)이면 지금보다 나쁘다." 파생·검사로 막는다는 내 답이 충분한가.
- "coderag 는 개발 중이고 무게가 팀 서버(§35)로 가 있다(audit/37 §7). 매 파일 열기 경로를 거기에 묶는 것은 위험하다." 나는 2단계 파리티 테스트와 3단계 되돌리기로 답하지만, 바이너리 배포가 안 된 지금 동료 기기에서 rules 가 빠지는 기간이 생긴다.
- "codex·agy 는 위임용이라 훅 어댑터는 과설계다." 일부 인정(인정 2). 그래서 이행에서 agy 어댑터는 6단계, 실측 뒤로 미뤘다.
- "380줄 사본은 테스트가 이미 지키니 실제 비용은 작다." 비용은 줄 수가 아니라 팩마다 Claude 훅 계약이 박히는 것과 플러그인 버전에 묶인 신선도라는 것이 내 답이다.
- "daemon 없이 stdio 로 충분하다면 사용자의 daemon 구상은 필요 없다." 의미 검색 전까지는 맞다고 본다(3장).

## 사용자에게 물을 것
1. 팩 켜기의 정본을 하네스 무관한 project `coderag.toml` 로 두고 `enabledPlugins` 를 파생할까, `enabledPlugins` 를 정본으로 두고 coderag 가 그것을 읽게 할까?
2. 동료들이 codex·agy 를 직접 대화형으로 쓰게 될까, 아니면 계속 Claude 에서 위임하는 용도일까? 훅 어댑터와 AGENTS.md 의 우선순위가 여기서 갈린다.
3. 로컬 의미 검색(모델 한 벌 ≈ 수백 MB, 공유 cgroup 10GiB)을 목표에 넣을까, 키워드+본문 색인까지만 할까? 넣으면 daemon 이 필요해진다.
