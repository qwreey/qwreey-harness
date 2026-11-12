# 41 round2-Q: 사실 확인, 양보와 수렴안

> Snapshot 2026-11-12. 토론자 Q 2라운드. 읽은 것: round1-P, other-harness-hooks(WebFetch 요약이라 잠정), coderag c216d11. 다시 잰 조건: debug 빌드(12:12:47, c216d11 포함), `choom -n 1000`, `CODERAG_HOME=/tmp/q41/home`, `CODERAG_CACHE=/tmp/q41b/cache`, claude-doctor `.claude` 를 `/tmp/q41b/proj` 에 복사(`.git` 표식)해서 잼.

## 0. 내 1라운드 수치 정정과 다시 잰 값
내 1라운드의 7,941항목, gen 932ms, 세 계층 search 218ms·39MB 는 P 가 찾은 루트 버그를 잰 것이었다. 버그 때문에 claude-doctor 의 `.claude` 가 아니라 `/code/.claude` 가 색인됐다. 그러니 "186문서, 7941항목"이라고 쓴 것도 틀렸다.

| 명령 | 버그일 때 | 고친 뒤 |
|---|---|---|
| `gen --layer project` | 932ms, 7,941항목, 4.9MB | **247ms, 1,696항목, 1.09MB** |
| `search` 세 계층 | 218ms, anon 39MB | **71ms, anon 8.8MB** |
| `search --layer project` | 189ms | **41ms** |
| `search --pack luau-kb` | 29ms, anon 3.0MB | 같음 |
| `stale`(전부) | 1.8s | **423ms** |
| `--version` | — | 1.4ms, anon 0.9MB |

**남은 버그(재현함).** c216d11 은 `$CODERAG_HOME` 만 홈으로 본다. 그래서 테스트 격리처럼 `CODERAG_HOME=/tmp/...` 를 주면 `~/.coderag` 가 다시 project 표식이 된다. 고친 바이너리로 claude-doctor 에서 직접 돌렸을 때도 7,941항목이 다시 나왔다. 기본 사용(변수 없음)은 고쳐졌다. `is_home` 이 `$CODERAG_HOME` 과 `$HOME/.coderag` 를 둘 다 보도록 고칠 것을 권한다(coderag 변경이므로 사용자 승인 사항).

## 1. P 의 사실 주장 확인
| 주장 | 판정 | 근거 |
|---|---|---|
| 팩마다 훅 코드 380줄 사본 | **확인** | 267+81+32 = 380줄, 팩 2개로 760줄 |
| 팩 스킬 description 합 486자 | **반박** | `description: >-` 접힌 블록을 첫 줄만 셌다. 나도 처음에 같은 486을 얻었다. 블록을 펼치면 luau-kb 12개가 6,456자, web-security 가 462자 |
| `rules_inject.py` 17-19ms | **확인** | 내 측정 17-18ms |
| 메모리 속 색인 ≈ 디스크의 7배 | **반박** | 버그 루트(46-11MB / 4.9MB)에서 나온 비율이다. 고친 뒤 anon/디스크 비율은 pack 만이면 약 2.6배((3.0-0.9)/0.81), 두 계층이면 약 4배((8.8-0.9)/1.9) |
| MCP stdio 세션당 상주 ≈11MB | **부분 반박** | VmHWM 에는 바이너리 파일 페이지 8.3MB 가 들어 있고, 이것은 페이지 캐시로 프로세스끼리 공유된다. 프로세스 전용 anon 은 0.9-3MB + 색인 |
| agy 에 glob rules 없음 | **반박(잠정)** | 조사 [AR]: `.agents/rules/*.md` 의 `trigger: glob` + `globs` |
| agy PreInvocation `injectSteps` | **미확인** | 문서에만 있고 실행해 보지 않았다 |
| codex 훅 | **부분 확인** | 로컬 `codex features list`: `hooks stable true`, `plugin_hooks removed false`. PostToolUse `additionalContext` 와 SessionStart `source=compact` 는 문서 요약에만 있고 실행하지 않았다 |
| stale 1.89s, 191건 | 버그 수치 | 고친 뒤 423ms |

## 2. 사용자 결정(프로세스 모델)을 확정으로 받고 세부를 다툰다
사용자: "stdio MCP를 작은 래퍼로 두고 그게 데몬이 없으면 데몬을 띄우고, 데몬의 경우 활성 연결이 없으면 꺼지는 방향에 다른 사용자로 도는 경우는 각자 사용자 마다 데몬이 있는게 나은듯. read 가능하지 않은데 read 가능하면 안 되니까".

이 결정으로 내가 1라운드에 둔 데몬 조건 넷 중 넷 모두 프로세스 모델을 정하는 조건으로서는 의미가 없어진다.
- (4) MCP 만 읽는 하네스: MCP 가 생긴다.
- (3) fs watch: 데몬이 감시한다.
- (1) 지연: 데몬이 색인을 데운 채로 들고 있다.
- (2) 임베딩: 이제 프로세스 모델이 아니라 기능 범위의 질문이다(질문 4).

내가 1라운드에 우려한 uid 사이 소켓 문제도 uid 마다 데몬을 두는 것으로 풀린다. 남는 질문은 언제 만드느냐(순서)와 아래 세부다.

| 세부 | Q 제안 |
|---|---|
| 소켓 위치·권한 | `$XDG_RUNTIME_DIR/coderag/` 에 둔다. 없으면 `$CODERAG_HOME/run/`. 디렉터리 0700, 소켓 0600. 접속할 때 `SO_PEERCRED`(macOS 는 `getpeereid`)로 uid 가 같은지 확인하고 다르면 끊는다. 위임 에이전트는 과제마다 HOME(`.homes/<이름>`)이 따로라서 과제마다 데몬이 생긴다. idle 종료로 사라지므로 받아들인다 |
| 동시 기동 경합 | 데몬이 살아 있는 동안 `run/d.lock` 에 `flock` 을 쥔다(잠금 = 살아 있음). shim 은 접속을 시도하고, 실패하면 그 잠금을 비차단으로 시도한다. 잡히면 데몬이 없다는 뜻이므로 낡은 소켓을 지우고 데몬을 띄운다. 이때 잠금은 데몬에게 넘긴다(데몬이 다시 잡는다). 못 잡으면 다른 shim 이 띄우는 중이므로 최대 2초 동안 다시 접속한다. pid 파일은 쓰지 않는다. 커널이 프로세스가 죽으면 잠금을 풀어 준다 |
| idle 종료 | 마지막 연결이 끊긴 뒤 60초 유예를 두고 끝낸다. 세션 하나는 shim 연결 하나를 끝까지 들고 있으므로 "활성 연결 0" 은 곧 "세션 0" 이다. 유예는 세션을 재시작하거나 서브에이전트가 짧게 끊었다 붙을 때 다시 띄우는 비용을 피하려는 것이다 |
| 바이너리 업그레이드 | 소켓 경로에 프로토콜·빌드 버전을 넣는다(`d-<ver>.sock`). 새 shim 은 새 데몬에, 옛 세션은 옛 데몬에 붙는다. 옛 데몬은 연결이 0이 되면 스스로 끝난다. 접속할 때 hello 에서 버전을 맞추고, 다르면 shim 은 in-process 로 처리한다. 업그레이드한 순간 잠깐 데몬이 두 개 뜰 수 있다는 점은 인정한다 |
| 메모리·OOM | 데몬은 시작할 때 자기 `oom_score_adj` 를 1000 으로 올린다(올리는 것은 권한 없이 된다). 예산은 RSS 128MB 이고, 넘으면 project 색인을 LRU 로 내린다. pack 색인은 내리지 않는다. 지금 값으로는 pack 2개 + project 10개가 약 30-90MB 이다 |
| 데몬이 죽었을 때 | shim 이 EOF 를 받으면 한 번 다시 띄워 보고, 안 되면 in-process 로 검색한다. shim 은 같은 바이너리라 core 를 갖고 있어 결과가 같다. 지금 CLI 의 71ms 수준 |
| 훅(rules 주입) | **CLI 로 남는다.** 훅은 데몬을 띄우지 않는다. 띄우면 MCP 를 켜지 않은 세션에도 상주 프로세스가 생긴다. rules 판정에 필요한 것은 `rules/*.md` 의 frontmatter 뿐이라서 색인이 필요 없다(3ms 기동). 나중에 데몬을 쓸 일이 생기면 "있으면 접속만 하고, 없으면 in-process" 로 한다 |
| 데몬이 들고 있는 것 | 디스크 색인(gen 결과, 정본)을 파싱해 둔 캐시다. pack 색인은 `(pack, cache key)` 로 프로젝트끼리 한 벌을 공유하고, project 색인은 정규화한 루트로 키를 잡는다. 감시(inotify)는 쓰이고 있는 루트만 보고, 바뀐 모듈만 gen 해서 디스크에 먼저 쓴다(`.coderag/.lock` 을 기다리지 않고 건너뜀). 그래야 CLI·훅과 같은 결과가 나온다. **mmap 은 하지 않는다**: 데몬이 한 벌을 들고 있고, in-process 대체 경로의 anon 도 3-9MB 라서 이득이 없다 |

## 3. 쟁점별 처리
1. **MCP·데몬 시점.** 형태는 사용자가 정했다. 순서는 P 의 이행안 5단계 자리, 곧 팩 훅을 없애는 일(rules core, web-security, luau-kb) 다음이다. 양보한다. 데몬 프로토콜은 CLI 출력(두 줄, `--json`)을 그대로 쓴다.
2. **본문·블룸 검색.** 합의한다. 본문 토큰과 한국어 bigram 블룸을 gen 에서 만들어 디스크 색인에 넣고, CLI·shim·데몬이 같은 코드로 읽는다. 잴 것: 본문 낱말 표(coderag 18 / grep 53 파일)와 잡음(`닫힌 실패` 27건).
3. **팩 스위치 하나.** **P 쪽으로 양보한다.** 정본은 하네스와 무관한 project `coderag.toml` 의 팩 목록이다. Claude `enabledPlugins`, codex `.codex/config.toml [plugins]`, agy 쪽 설정은 `coderag adapt <harness>` 가 생성한다. 이 양보는 사용자가 말한 락인 우려에 맞는다. 조건이 둘 있다. 생성물은 손으로 고치지 않고 `q:doctor` 가 어긋남을 알린다. coderag core 는 Claude settings 를 파싱하지 않는다.
4. **바이너리가 없을 때.** P 와 같다. python 대체 구현은 두지 않고 `q:doctor` warn(`PACK-NO-CODERAG`)과 설치 스크립트로 대응한다. 데몬 구조가 들어오면 바이너리 의존이 어차피 커지므로, python 사본을 두면 결과가 두 갈래가 된다.
5. **지식 받은 편지함.** **P 쪽으로 양보한다.** 원래 저장소의 `.claude/` 기록에 `tags: [promote:<pack>]` 를 단다. 저장소 밖에 쓰지 않고 기록으로 남기 때문이다. 내가 더하는 것은 하나다. `coderag pack candidates` 가 다른 저장소를 찾으려면 프로젝트 루트 목록이 있어야 한다. 전역 `coderag.toml` 의 `[[projects]]` 를 쓰거나, 데몬과 CLI 가 본 루트를 `~/.coderag/seen-roots` 에 남긴다. 승격은 claude-doctor 세션과 사용자 확인으로 한다(같다).
6. **하네스별 어댑터(조사 반영).**
   - Claude: coderag 플러그인의 PostToolUse·PreCompact(또는 SessionStart compact)와 MCP shim.
   - codex: 프로젝트 `.codex/hooks.json` 을 생성한다. `plugin_hooks` 가 removed 라서 플러그인 번들 훅에는 기대지 않는다. 편집 경로는 `apply_patch` 본문에서 정확히 얻는다. 읽기 경로를 셸 명령 문자열에서 파싱하는 것은 정확도가 낮으므로 하지 않고, AGENTS.md 한 줄로 대신한다. 재무장은 SessionStart `source=compact` 로 한다. 훅 신뢰 검토는 사용자가 하는 일이다(HUMAN_TODO).
   - agy: 팩 rules 에서 `.agents/rules/*.md`(`trigger: glob`)를 생성한다. 정적 파일이라 compact 영향을 받지 않는다. PreInvocation 2단 주입은 실행해 보기 전에는 넣지 않는다.
   - codex·agy 는 지금 위임 백엔드이므로 이 일은 Claude 이전과 MCP 다음에 한다.

## 4. 수렴안
**정해진 것**
1. 팩은 데이터만 담는다: `coderag.toml [pack]`, `skills/`, `rules/*.md`(paths), 선택 `always.md`, 데이터 파일, Claude 노출용 `plugin.json`. 팩에서 `hooks/` 를 없앤다.
2. rules 판정·dedup(`(session, agent, 회차, rule)`, O_EXCL)·compact 회차는 coderag core 가 Rust 로 한 번 구현한다. `rules_inject.py` 와 출력이 같은지 골든 테스트한 뒤 web-security, luau-kb 순으로 옮긴다. qwreey-conventions 는 자기 정본 한 벌을 유지한다.
3. 프로세스: MCP stdio shim + uid(와 HOME)마다 데몬 하나, 연결이 0이 되고 60초 뒤 종료, flock 으로 살아 있음 판정, 버전을 넣은 소켓 경로, oom_score_adj 1000, 실패하면 in-process. 훅은 CLI 로 남고 데몬을 띄우지 않는다. 데몬은 디스크 색인의 캐시일 뿐이고 mmap 은 하지 않는다.
4. 본문·bigram 블룸 색인은 core(gen)에 넣는다.
5. 팩 켜기의 정본은 project `coderag.toml` 이고 하네스 설정은 `coderag adapt` 가 생성한다. `q:doctor` 가 어긋남을 검사한다.
6. 바이너리가 없으면 저하된 채로 동작한다(스킬만). python 대체 구현은 없고 doctor warn 을 띄운다.
7. 교훈은 원래 저장소 기록의 `promote:<pack>` 태그 → `coderag pack candidates` → claude-doctor 에서 승격한다.
8. codex 는 생성한 `.codex/hooks.json`(편집 경로) + AGENTS.md, agy 는 생성한 glob rules + AGENTS.md. 둘 다 위의 일들 다음이다.
9. coderag 루트 판정의 남은 버그(`$HOME/.coderag` 도 홈으로 봄)를 고친다.

**남은 이견(한 줄씩)**
- 훅과 데몬. Q: 훅은 데몬을 절대 띄우지 않는다. P(예상): `serve` 가 있으면 훅도 위임해 쓰기 주체를 하나로 둔다.
- 업그레이드. Q: 버전을 넣은 소켓으로 두 데몬이 잠시 함께 산다. P(예상): 버전이 다르면 데몬을 재기동한다(옛 세션은 in-process).
- codex 읽기 경로. Q: 셸 파싱은 하지 않고 AGENTS.md 로 대신한다. P(예상): PostToolUse Bash 명령을 파싱해 주입한다.
- agy. Q: glob rules 생성만 한다. P: PreInvocation `injectSteps` 2단 어댑터도 둔다(실측 뒤).

**사용자 질문(고르기만 하면 되는 것)**
1. 데몬 idle 유예: (a) 0초, 마지막 연결이 끊기면 바로 종료 (b) 60초 [Q 추천] (c) 10분.
2. 바이너리 업그레이드 때: (a) 버전을 넣은 소켓으로 옛 데몬과 새 데몬이 잠시 함께 산다 [Q 추천] (b) 옛 데몬을 끝내고 다시 띄운다(옛 세션은 in-process 로 넘어감).
3. 바이너리가 없는 기기: (a) 스킬만 동작하고 doctor 가 경고 [양쪽 추천] (b) coderag 플러그인에 python rules 주입 사본 한 벌을 둔다.
4. 로컬 의미 검색(임베딩 모델 수백 MB, 데몬 안에 한 벌): (a) 범위 밖, 키워드와 본문 색인까지만 (b) 본문 색인을 잰 뒤 다시 정한다 [Q 추천] (c) 목표에 넣는다.
