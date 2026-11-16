# 41 지식 팩 토론, 2라운드: P

> Snapshot 2026-11-12. coderag debug 빌드(c216d11 루트 수정 포함, 12:12 빌드), `choom -n 1000`. 재측정은 `CODERAG_HOME` 을 비우고(수정이 `$CODERAG_HOME` 만 표식에서 빼므로, 다른 값으로 격리하면 `/code/.coderag` 가 다시 표식이 되어 버그가 재현된다) `CODERAG_CACHE=/tmp/p41/cache3`, `gen --layer project` 만 돌렸다. `~/.coderag` 의 파일은 전후 24개로 같다. 사용자 결정 둘(프로세스 모델)을 4장에 확정으로 반영했다.

## 0. 내 1라운드 정정
- **스킬 description 합 486자는 틀렸다.** 여러 줄 description 의 첫 줄만 셌다. 다시 세면 luau-kb 12개 6,456자 + web-security 462자 = 6,918자로, Q 의 값이 맞다. 상시 비용 축은 내가 쓴 것보다 크다. luau-kb 를 켠 저장소마다 약 3-4k 토큰이 든다.
- **1라운드의 216ms·46MB·1.1s·191건은 버그 탓이었다.** 수정 뒤 claude-doctor 에서 다시 쟀다.
  | 명령 | 시간 | maxrss |
  |---|---|---|
  | `gen --layer project` | 250ms | 14.6MB |
  | 세 계층 `search` | 66ms | 16.5MB |
  | `search --pack luau-kb` | 31ms | 11.4MB |
  | `stale --layer project` | 49ms | 16.4MB |
  - 색인은 1,696항목에 1.1MB 다. 프로세스 전용 메모리는 세 계층 search 가 약 5MB, pack 만 찾을 때 약 0이다(기준 `--version` 이 11.2MB).
  - 1라운드에서 쓴 "디스크의 7배" 추정은 약 5배로 고친다.

## 1. Q 의 사실 주장 검증
| 주장 | 판정 | 근거 |
|---|---|---|
| `hook.rs:72` dedup 이 원자적이지 않고 compact 회차를 보지 않는다 | **확인** | `read_to_string` 으로 읽고 `append` 로 덧붙인다(O_EXCL 아님). 키는 `session` + `file\tfnv(msg)` 이고 agent_id·회차가 없다. 지금은 lint 알림이라 해가 작지만, rules 주입을 옮길 때는 `rules_inject.py` 의 키와 마커를 그대로 가져와야 한다 |
| 본문 낱말을 coderag 는 18파일, grep 은 53파일에서 찾는다 | **확인** | 낱말 6개를 다시 쟀고 값이 하나하나 같다(1/10, 1/6, 3/10, 3/6, 3/5, 7/16) |
| luau-kb 에서 `닫힌 실패` 를 찾으면 27건이 나온다 | **확인** | 27건이고, luau-kb 를 grep 하면 0파일이다. 토큰 하나만 맞아도 결과에 든다 |
| 위임 에이전트는 `setpriv` 로 다른 uid 에서 돈다 | **확인** | `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/README.md:51` "setpriv 무권한 uid" |
| project 색인 39MB anon, 932ms, 7941항목 | **반박(재측정)** | 7941 은 버그로 생긴 `/code/.claude` 의 항목 수와 정확히 같다. 수정 뒤에는 1,696항목, 약 5MB anon, 250ms 다 |
| luau-kb description 6,456자 | **확인** | 0장 |
| codex 훅 PostToolUse `additionalContext`, SessionStart `source=compact`, agy `.agents/rules` 의 `trigger: glob` | **미확인(문서 요약)** | other-harness-hooks.md 는 WebFetch 요약이라 실행으로 확인하지 않았다. 아래 설계는 이것이 맞다는 가정 위에 서고, 각 단계의 첫 측정으로 확인한다 |

## 2. 쟁점별 처리
1. **본문·블룸 검색은 CLI 안에서 한다: Q 에 양보.** 이것은 gen 때 정해지는 색인 형식이라 CLI·shim·daemon 이 같이 쓴다. 상주 프로세스가 필요한 일이 아니다. 잡음을 줄이는 "맞은 토큰 비율 하한"도 같은 변경에 넣는다. 18/53, 27건, audit/39 의 12문항을 회귀 기준으로 삼는다.
2. **mmap 대 daemon: 지금은 둘 다 메모리 때문에 필요한 것이 아니다.** 수정 뒤 수치로 N=6 세션을 셈하면 shim 은 하나에 anon 3-5MB 이고, daemon 이 아끼는 양은 수십 MB 아래다. 메모리 면에서 daemon 의 이점이 작다는 Q 의 결론이 맞다. 다만 사용자가 프로세스 모델을 정했으므로 쟁점은 "할지"가 아니라 "무엇을 들고 언제 켜는지"로 바뀐다(4장). mmap 은 본문 색인이나 임베딩 때문에 색인이 수십 MB 를 넘을 때 다시 본다.
3. **팩 스위치: Q 안에 양보하되 경계를 하나 둔다.** Claude 저장소에서는 `enabledPlugins` 가 정본이다. 스킬 description 을 켜고 끄는 길이 어차피 그것뿐이기 때문이다(audit/40). 내가 말한 "하네스 지식이 core 로 샌다"는 걱정은 위치를 정해서 푼다. `enabledPlugins` 를 읽는 일은 claude 어댑터만 하고, core 는 `--packs a,b` 목록만 받는다. codex 는 `.codex/config.toml [plugins]`, agy 는 미확인이다. 그런 저장소에서만 project `coderag.toml` 의 팩 목록을 두고, `q:doctor` PACK-MISMATCH 로 맞춘다.
4. **바이너리가 없을 때: Q 안에 동의.** python 대체 구현은 두지 않고 시작한다. 이유는 셋이다.
   - rules 가 있는 팩은 coderag 를 전제 조건으로 선언한다(`coderag.toml` 의 `[pack] requires = "coderag>=x"`).
   - `q:start` 가 설치한다.
   - `q:doctor` 가 `CODERAG-MISSING` 을 warn 으로 알린다.

   동료 파일럿에서 설치 실패가 나오면 그때 coderag 플러그인에 한 벌 둔다. 팩마다 두지는 않는다.
5. **지식 받은 편지함: Q 안을 받고 하나를 더한다.** 내 1라운드 안(원천 저장소 `.claude` 에 `promote:` 태그)은 포착한 곳이 읽기 전용 형제 저장소이거나 동료 기기일 때 막힌다. 그래서 `~/.coderag/inbox/<팩>/` 이 낫다. 더할 것은 넷이다.
   - 항목은 frontmatter 가 달린 md 로 쓴다(`origin: <저장소>@<커밋>`, `pack`, `evidence`, `date`).
   - `inbox` 계층은 기본 검색에서 숨긴다.
   - MCP 도구 `inbox_add` 를 둬서 codex·agy 도 같은 길로 넣게 한다.
   - claude-doctor SessionStart 가 쌓인 건수를 한 줄로 알린다.

   승격(재현, 일반 표현으로 바꾸기, 사용자 확인)은 Q 가 쓴 대로 한다. 위험은 inbox 가 git 밖이라 백업이 안 된다는 것이다. 그래서 승격하거나 버릴 때까지만 머문다.
6. **하네스별 어댑터: 조사를 보고 내 agy 안을 버린다.**
   - **agy**: PostToolUse 로 연 파일을 기록하고 PreInvocation 으로 주입하는 2단 어댑터 대신, 팩의 `rules/*.md` 에서 `.agents/rules/<팩>-<rule>.md`(`trigger: glob`, `globs` = `paths`)를 생성한다. 정적이고, 압축에도 안전하고, 훅이 필요 없다. 확인할 것: 읽기만 해도 발동하는지, 생성 파일을 커밋할지(질문 4).
   - **codex**: 계약이 Claude 와 거의 1:1 이므로 어댑터 하나로 된다(PostToolUse `additionalContext`, PreCompact·SessionStart(compact) 로 회차를 올림, `CLAUDE_PLUGIN_ROOT` 호환). 걸리는 점은 경로 추출이다. `apply_patch` 본문의 경로는 믿을 만하다. 셸로 읽는 경로(`cat`/`sed`/`rg` 인자)는 최선 노력으로만 잡는다. 그래서 AGENTS.md 경로별 절(Q 안)을 먼저 두고, 편집 경로 주입을 그 뒤에 붙인다. 훅 신뢰 검토는 HUMAN_TODO 에 적는다.
   - **Claude**: coderag 플러그인 PostToolUse·PreCompact. 1라운드와 같다.
7. **MCP·daemon 시점: 사용자가 정했다(4장).** Q 의 측정 조건 1-4 는 "daemon 을 기본으로 켤지"의 조건으로 남긴다. 순서는 shim 의 in-process 경로를 먼저 만든다. 이것은 daemon 이 죽었을 때의 폴백이기도 하므로 버려지는 작업이 아니다.

## 3. 사용자 결정 반영: stdio shim + 사용자별 daemon
사용자: "stdio MCP를 작은 래퍼로 두고 그게 데몬이 없으면 데몬을 띄우고, 데몬의 경우 활성 연결이 없으면 꺼지는 방향에 다른 사용자로 도는 경우는 각자 사용자 마다 데몬이 있는게 나은듯. read 가능하지 않은데 read 가능하면 안 되니까".

- **소켓 위치·권한.** `$XDG_RUNTIME_DIR/coderag/`, 없으면 `$CODERAG_HOME/run/` 에 둔다.
  - 디렉터리는 0700, 소켓은 0600 이다. 연결을 받을 때 `SO_PEERCRED` 로 uid 가 자기와 같은지 보고, 다르면 끊는다.
  - setpriv 위임은 과제마다 HOME 이 다르므로 자동으로 자기 daemon 을 띄운다. 그 daemon 은 그 uid 로 돌아서 그 uid 가 읽을 수 있는 파일만 색인한다(사용자 요구 그대로).
  - 위임 uid 가 팩을 쓰려면 팩 경로가 그 uid 에 읽혀야 한다. 쓰기는 각 uid 의 `CODERAG_HOME` 캐시에만 한다.
- **기동 경합.** shim 이 연결하고, 실패하면 `run/start.lock` 에 `flock` 을 건 뒤 다시 연결해 본다.
  - 그래도 실패하면 남은 소켓을 지우고 daemon 을 `setsid` 로 띄운다. 이어 shim 이 최대 1초 동안 연결을 다시 시도한다.
  - 둘이 동시에 와도 하나만 띄운다. lock 을 기다리는 한도는 2초이고, 넘기면 in-process 로 넘어간다.
- **idle 종료.** 활성 연결이 0이 된 뒤 10분이 지나면 끈다(`CODERAG_DAEMON_IDLE`).
  - 연결은 shim 이 세션 내내 하나를 들고 있으므로, 연결 수가 곧 살아 있는 세션 수다.
  - 다시 띄우는 비용은 디스크 캐시를 읽는 30-70ms 뿐이라 짧게 잡아도 된다. 10분은 세션 사이 공백에 다시 띄우지 않게 하려는 값이다.
- **바이너리 갱신.** 소켓 이름에 build id 를 넣는다(`run/d-<build>.sock`).
  - 새 shim 은 새 daemon 을 띄운다. 옛 daemon 은 옛 shim 의 연결이 끝나면 idle 로 저절로 꺼진다. 서로 죽이지 않는다.
  - 연결 직후 `hello{proto, build}` 를 주고받아 proto 가 다르면 거부한다.
  - 대가로 갱신하는 동안 잠깐 두 벌이 뜬다(수십 MB).
- **메모리·OOM.** daemon 은 시작할 때 자기 `oom_score_adj` 를 1000 으로 올린다(올리는 것은 무권한으로 된다). 그러면 cgroup 이 한도에 닿았을 때 Claude 보다 먼저 죽는다.
  - 상한 `CODERAG_DAEMON_MAX_RSS` 의 기본은 256MB 다. 넘으면 가장 오래 안 쓴 project 색인부터 내린다.
  - 키워드 색인 기준 예상 상주량은 pack 약 3MB, project 하나에 1-5MB 다.
- **죽었을 때.** shim 은 요청 중에 EOF 를 만나면 한 번 다시 띄워 본다. 그래도 안 되면 같은 바이너리 안의 core 로 직접 검색한다(지금 CLI 경로). 결과 형식이 같으므로 에이전트 쪽에서는 차이가 없고, 지연만 31-66ms 로 돌아간다.
- **훅은 CLI 로 남는다.** rules 주입은 rules 파일 몇 개에 glob 을 맞추는 일이라 색인이 필요 없다. 기동도 3ms 다. 또 MCP 를 켜지 않은 세션에서도 돌아야 한다. 그래서 daemon 에 기대지 않는다.
  - 선택: post-edit 훅이 daemon 소켓이 있으면 바뀐 경로를 한 줄 보내고 기다리지 않는다. 같은 일을 fs watch 가 하므로 없어도 된다.
- **daemon 이 드는 것.**
  - global 계층과 pack 계층(`pack:<이름>@<rev|local-키>`)은 한 벌이고 모든 project 가 같이 쓴다. 사용자가 말한 "global 은 복제 없이 한 메모리"가 이것이다.
  - project 색인은 정규화한 루트 경로를 키로 둔다. shim 의 cwd 로 루트를 찾아 처음 요청할 때 올리고, 30분 동안 안 쓰면 내린다.
  - inotify 로 pack·project 루트를 보고 바뀐 모듈만 다시 gen 한다. 쓰는 주체가 하나라서 세션 사이 gen 경합이 없다. CLI gen 은 §22 의 `.lock` 을 계속 쓴다.
  - mmap 은 쓰지 않는다. JSONL 을 메모리로 올려 둔다. 색인이 수십 MB 가 되면 그때 다시 본다.
  - 임베딩 모델이 들어오면 daemon 이 그것을 한 벌만 든다.
- **캐시 위치(새 쟁점).** 사용자 소유가 아닌 형제 저장소에 `<root>/.coderag/` 를 만들면 안 된다. 그래서 daemon 이 관리하는 project 캐시의 기본 위치를 `$CODERAG_HOME/cache/projects/<루트 해시>/` 로 옮기자고 제안한다. 지금 `CODERAG_CACHE=/tmp/...` 를 손으로 붙이는 습관도 없어진다.

## 4. 수렴안

**정해진 것**
1. 팩은 데이터다: `plugin.json`(Claude 스킬 노출), `coderag.toml [pack]`(+ `requires`), `skills/`, `rules/*.md`(`paths`), 선택 `always.md` 와 데이터. 팩 안의 `hooks/` 와 vendored python 사본은 없앤다. qwreey-conventions 의 정본 한 벌만 남는다.
2. rules 판정, dedup 키 `(session, agent, 회차, rule)`, O_EXCL 마커, 회차를 coderag core 로 옮긴다. `rules_inject.py` 와 출력이 같은지 골든 테스트로 확인한다. web-security 를 먼저, luau-kb 를 그다음에 옮긴다.
3. 진입 구조는 사용자 결정 그대로 stdio shim 에서 사용자별 daemon(자동 기동, idle 종료, uid 분리)으로 간다. shim 의 in-process 폴백을 먼저 만든다. 훅은 CLI 로 둔다.
4. 본문 색인, 블룸 필터, 토큰 비율 하한은 색인 형식 변경으로 CLI 에서 한다. 회귀 기준은 18/53, 27건, audit/39 의 12문항이다.
5. Claude 에서는 `enabledPlugins` 를 팩 스위치의 정본으로 쓰고 어댑터만 읽는다. 다른 하네스에서는 `coderag.toml` 목록을 쓰고 doctor 가 맞춘다.
6. 하네스별: Claude 는 플러그인 훅, codex 는 AGENTS.md 경로별 절을 먼저 두고 훅 어댑터를 다음에, agy 는 `.agents/rules` glob 생성. 셋 다 첫 단계에서 실측으로 확인한다.
7. 교훈은 `~/.coderag/inbox/<팩>/` 으로 받고 claude-doctor 세션에서 승격한다. 낡음은 `stale` 과 evidence 꼬리표로 다룬다.
8. 바이너리가 없을 때 python 대체 구현은 두지 않는다. 설치와 doctor warn 으로 대응하고 파일럿 뒤에 다시 본다.
9. luau-kb description(6.5k자)을 라우터 스킬과 search 로 줄이는 실험을 한다(Q 의 M6).

**남은 이견**
- daemon 의 기본값. P: shim 과 함께 기본으로 켠다(fs watch 신선도와 쓰는 주체 하나가 지금도 값이 있다). Q: 측정 조건 1-4 중 하나가 맞을 때까지 in-process 로 둔다.
- 1장 표의 마지막 줄. P: codex·agy 문서 요약을 설계의 전제로 쓰고 첫 단계에서 확인한다. Q 가 이것을 미확인 전제라며 단계 뒤로 미룰지는 Q 의 답을 봐야 한다.

**사용자에게 물을 것(고르기)**
1. 팩 스위치: (a) Claude 는 `enabledPlugins` 를 정본으로, 다른 하네스는 `coderag.toml` + doctor 검사(추천) (b) `coderag.toml` 하나를 정본으로 두고 `enabledPlugins` 는 생성.
2. daemon 기본값: (a) shim 과 함께 기본으로 켬 (b) 처음에는 in-process 만, 측정 조건이 맞으면 켬.
3. 교훈 받은 편지함: (a) `~/.coderag/inbox/`(추천) (b) 원천 저장소 `.claude` 에 태그 (c) 둘 다.
4. agy 용 생성 rules(`.agents/rules/*.md`): (a) 저장소에 커밋 (b) 생성하고 gitignore, `q:start` 가 만듦 (c) agy 의 경로 rules 는 아직 지원하지 않음.
