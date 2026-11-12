# 41 round1-Q: coderag 는 빠른 CLI 로 두고, 하네스마다 어댑터 하나

> Snapshot 2026-11-12. 토론자 Q(CLI 우선) 1라운드. 측정은 `coderag` debug 빌드(`target/debug`, 53MB, release 빌드 없음)로 했고 `CODERAG_HOME=/tmp/q41/home`(전역 설정 사본), `CODERAG_CACHE=/tmp/q41/cd-cache`, `choom -n 1000` 아래에서 돌렸다. 형제 저장소에 쓴 것은 없다.

## 입장 한 줄
지식 본문과 rules 는 팩의 **데이터**이고, 주입·compact 처리·검색은 coderag **코어**가 한 번만 구현한다. 하네스마다 다른 부분은 어댑터 하나씩만 둔다(Claude: coderag 플러그인 훅, codex·agy: 생성한 AGENTS.md 와 스킬 사본). MCP 와 데몬은 아래 §2 의 측정 조건 중 하나가 충족될 때 붙인다. 지금 검색 품질이 실제로 떨어지는 곳은 본문을 색인하지 않는다는 점이고, 이것은 CLI 색인 안에서 고칠 수 있다(§0-3).

## 0. 실측
### 0-1 지연 (중앙값, 5-10회. 처음 한 번과 그다음이 같았다. drop_caches 를 할 수 없어 진짜 cold 는 못 쟀다)
| 명령 | 대상 | 시간 | 비고 |
|---|---|---|---|
| `gen --layer pack` | luau-kb 78문서 | 146ms | 두 번째 실행도 142ms. 증분이 없다(§22 미구현) |
| `gen --layer project` | claude-doctor `.claude` 186문서, 7941항목 | 932ms | `sessions/` 가 대부분 |
| `search --pack luau-kb too complex` | pack 만 | 30ms | |
| `search --abs 제네릭 콜백 상한` | 세 계층 | 218ms | 4.9MB project 색인을 파싱한다 |
| `stale --layer pack` | luau-kb | 97ms | |
| `hook pre-bash` / `hook post-edit` | Rust 훅 진입 | 3.2ms / 3.0ms | |
| `python3 -I rules_inject.py` | 팩 사본 하나 | 18ms | 팩 수만큼 Read 마다 돈다(지금 2개 → 36ms) |
| `python3 -I -c pass` | 기준 | 9ms | |

release 빌드는 이보다 빠를 것이다(조사 37 의 작은 말뭉치에서 search 6ms). 위 숫자는 상한으로 읽으면 된다.

### 0-2 메모리 (`/proc/<pid>/status` 를 0.5ms 간격으로 읽은 최고값)
| 명령 | VmHWM | RssAnon(프로세스 전용) | RssFile(바이너리, 페이지 캐시 공유) |
|---|---|---|---|
| `search --pack luau-kb` | 11.3MB | **3.0MB** | 8.3MB |
| `search`(세 계층, claude-doctor) | 47.6MB | **39.3MB** | 8.3MB |
| `gen --layer project` | 39.5MB | 31.5MB | 8.0MB |
| 디스크 색인 | luau-kb 812KB(JSONL), claude-doctor project 4.9MB | | |

샌드박스 상황(같은 시각): cgroup `memory.max` 10GiB, `memory.current` 8.25GiB, `memory.peak` 10.0GiB(이미 한도에 닿은 적이 있다). claude 프로세스 4개가 합계 1.36GB(하나에 230-480MB), code-server node 프로세스들이 1.3GB 이상, luau-lsp 108MB 를 쓰고 있었다.

### 0-3 검색 품질: 본문 낱말
references 본문에만 있는 API 이름으로 `search --pack luau-kb --limit 50` 이 찾은 파일 수와 grep 으로 찾은 파일 수를 비교했다.
| 낱말 | coderag | grep |
|---|---|---|
| `__index` | 1 | 10 |
| `table.freeze` | 1 | 6 |
| `debug.info` | 3 | 10 |
| `task.defer` | 3 | 6 |
| `BindableEvent` | 3 | 5 |
| `getfenv` | 7 | 16 |
| 합 | **18** | **53** |

반대 방향의 잡음도 있다. luau-kb 에 없는 web-security 구절인 `닫힌 실패` 를 luau-kb 에서 찾으면 27건이 나온다. 토큰 하나만 맞아도 결과에 들기 때문이다. 기록 쪽은 이미 쓸 만하다(조사 39 after-D: hit@5 가 coderag 10/12, grep 7/12, top-5 바이트는 11KB 대 250KB).

### 0-4 상시 비용
luau-kb 스킬 12개의 description 은 합쳐 6,456자이다(토큰으로는 3-4k 로 추정하고 재지는 않았다). web-security 는 462자이다. 조사 40 에 따르면 스킬 `paths` 로는 이 비용을 줄일 수 없고, 저장소별로 플러그인을 켜고 끄는 것만이 줄이는 길이다.

## 1. 구조
| 관심사 | 소유 | Claude Code | codex 0.166 | agy |
|---|---|---|---|---|
| 지식 본문 | 팩 `skills/*/references/*.md` (frontmatter) | 스킬이 Read 한다 | `.agents/skills` 사본 + `coderag get` | `.agents/skills` 사본 + `coderag get` |
| 짧은 필수 규칙 | 팩 `rules/*.md` (`paths:`) — 지금 형식 그대로 | coderag 플러그인의 PostToolUse 가 `coderag hook post-tool` 실행 | AGENTS.md 의 "경로별 규칙" 절(glob → 한 줄 요약 + `coderag rules --for <파일>`) | 같은 AGENTS.md 절. glob 트리거가 확인되면 `.agents/rules/` 사본 |
| 규칙 판정과 중복 제거 | **coderag 코어** `rules --for <path>` (glob, 프로젝트 밖·vendor 제외, dedup 마커) | 훅이 이것을 호출한다 | 에이전트가 Bash 로 호출한다 | 같음 |
| compact 회차 | coderag 코어. 이름공간 하나(`coderag`)를 모든 팩이 같이 쓴다 | PreCompact 에서 `coderag hook pre-compact` | 필요 없다(AGENTS.md 는 늘 실린다) | 필요 없다 |
| 상시 맥락 | 스킬 description(팩을 켠 저장소에서만), T1 블록(§19, 40줄 이하) | 팩 플러그인(스킬만, 훅 없음) | AGENTS.md T1/T2 마커 블록(32KiB 경고) | 같음 |
| 필요할 때만 | `coderag search/get/stale` | doc-locator(haiku) 또는 Bash | Bash | Bash |

- 스킬과 검색은 서로 대신하지 않는다(§20). SKILL.md 의 결정 트리는 "증상 → 절" 경로이고, search 는 "낱말 → 위치"이다. 다만 luau-kb description 6.5k자는 줄일 수 있는지 실험할 만하다. 예를 들어 라우터 스킬 하나에 search 를 붙이는 방식이 있다. 지금 정하지 않고 §7 M6 에서 잰다.
- 코어로 옮길 때 고칠 점이 있다. 지금 `hook post-edit` 의 dedup(`hook.rs:72`)은 세션 단위이고 compact 회차를 보지 않는다. 또 읽은 다음 덧붙이는 방식이라 병렬 호출이 겹칠 수 있다. 옮길 때 `rules_inject.py` 의 키 `(session, agent, 회차, rule)` 와 O_EXCL 마커를 그대로 가져온다.

## 2. 프로세스 모델
**CLI(지금).** 쉬는 동안 쓰는 메모리가 0이다. 한 번 호출하면 30-220ms 동안 3-39MB 를 쓰고 끝난다. 끝나면 남는 것이 없어 고아 프로세스나 버전 어긋남이 생기지 않는다. OOM 점수는 호출하는 쪽의 choom 을 물려받는다.

**MCP stdio.** 세션마다 프로세스가 하나 뜬다(데몬이 아니다). 세션 수 N 만큼 상주하고, 그 세션이 한 번도 부르지 않아도 뜬다. 세션이 끝나면 stdin EOF 로 같이 끝나므로 수명 문제는 없다. 늘어나는 것은 상주 메모리와 색인 신선도다. 색인을 메모리에 들고 있으면 프로세스마다 watch 를 따로 해야 한다. 도구 정의 토큰 비용은 이 환경처럼 MCP 도구가 지연 로드(ToolSearch)될 때는 작다. 이 점에서 §31 의 "CLI 가 4-32배 싸다"는 근거는 약해졌다고 인정한다.

**공유 데몬(socket·HTTP 위의 MCP).** 메모리에 사본이 하나만 있는 구조다. 대신 다음 문제를 풀어야 한다.
- 누가 띄우고 누가 끄나(첫 세션? idle timeout?).
- 바이너리를 갱신한 뒤 옛 데몬이 계속 남는 버전 어긋남.
- 소켓 권한. 위임 에이전트(agy·codex)는 `setpriv` 로 과제마다 다른 uid 로 돈다(delegate README §2). 그래서 uid 사이에 소켓을 열어 주거나, uid 마다 데몬을 따로 둬야 한다.
- 데몬 자체의 choom, 메모리 누수 감시, 그리고 비프로그래머 기기에서 "뭔가 떠 있다"는 상태를 설명하는 일.

**사용자 쟁점에 대한 답("여러 곳에서 인보크되어 메모리를 점유하는 것보다, 하나의 mcp 구조…한 메모리에 올라간다면 오히려 가벼울 수도").** 방향은 맞다. 다만 이 주장이 겨냥하는 상대는 CLI 가 아니라 세션별 MCP stdio 이다. N=6 세션(table-sim, quad, stl-luau 등 동시 개발)으로 추정하면 다음과 같다.

| 모델 | 상주 메모리 | 순간 최대 | 공유 계층(luau-kb) 사본 수 |
|---|---|---|---|
| (a) CLI 호출마다 | 0 | 6 × 3MB = 18MB(pack 만), 6 × 39MB ≈ 240MB(claude-doctor 급 project 색인이 동시에 돌 때, 0.2초) | 호출 중에만 1개씩. 실제로 동시에 도는 호출은 0-1개 |
| (b) MCP stdio, 세션마다 | 6 × (3MB pack + project 색인 파싱본 + 실행 기반) ≈ 50MB-250MB, 내내 | 같음 | 6개 상주 |
| (c) 공유 데몬 하나 | 1 × (3MB + 서로 다른 project 색인 합) | 같음 | 1개. (b)보다 (N-1) × 3MB = 15MB 아낀다 |
| (d) CLI + mmap 색인(바이너리 형식, 0-copy) | 0 | 호출마다 anon 이 거의 0 | 디스크 파일 하나를 페이지 캐시가 모든 프로세스에 나눠 준다. 프로세스 없이 "한 메모리" |

- 지금도 색인 파일 바이트는 페이지 캐시에 한 벌만 있다. 중복되는 것은 JSONL 을 파싱한 결과(anon)뿐이다. luau-kb 에서는 그것이 3MB 이고, claude 프로세스 하나의 약 1% 이다.
- 큰 항목은 project 색인(39MB)이다. 이것은 저장소마다 달라서 데몬도 줄이지 못한다(같은 저장소에 세션이 여러 개일 때만 줄어든다).
- 그래서 "한 메모리" 라는 성질은 (d) 로 데몬 없이 얻을 수 있다. 최악은 (b) 이다.

**데몬을 정당화하는 조건(측정, 하나라도 맞으면 다시 연다).**
1. release 빌드와 (d) 를 적용한 뒤에도 가장 큰 실제 project 색인에서 search 중앙값이 100ms 를 넘는다.
2. 의미 검색을 들이는데 임베딩 추론 런타임이 호출마다 300ms 넘게 로드되거나 anon 50MB 를 넘는다. 이 경우 모델이 상주해야 하므로 공유 데몬이 맞다. 다만 그 전에 본문 색인(§0-3)이 실패 사례를 줄이는지 먼저 본다.
3. B mtime 검사(§22)를 넣은 뒤에도 recall 질의의 5% 이상이 낡은 색인 때문에 틀린다. 이것이 fs watch 가 필요하다는 근거가 된다.
4. MCP 만 읽을 수 있는 하네스(동료의 데스크톱 앱 등)가 실제로 필요해진다. 이때는 데몬이 아니라 stdio 얇은 어댑터(D31-4)로 먼저 대응한다.

**블룸 필터·본문 색인은 CLI 안에서 된다.** gen 할 때 절마다 본문 토큰 집합(가중치 1)을 만들거나, 한국어 조사 문제 때문에 문자 bigram 블룸 필터(1% 오탐, 절당 1KB 안팎)를 JSONL 에 함께 쓴다. search 는 그것을 읽는다. luau-kb 는 본문이 915KB 라서 색인이 수백 KB 늘어나는 정도로 추정한다. 상주 프로세스가 할 일이 아니다. 같은 변경에서 "맞은 토큰 비율 하한"을 둬서 `닫힌 실패` 27건 같은 잡음도 줄인다.

## 3. 복제 제거와 팩이 담는 것
지금 팩마다 `hooks/` 에 python 760줄 사본이 있다(`rules_inject.py` 267, `compact_epoch.py` 81, `conv_env.py` 32, 각 2벌). `test-vendored-copies.py` 가 이것들이 같은지 검사한다. 바뀐 뒤의 팩은 다음과 같다.
```
packs/<p>/
  .claude-plugin/plugin.json   Claude 에 스킬을 보이기 위한 것. defaultEnabled false. hooks/ 없음
  coderag.toml                 [pack] + knowledge targets + rules = "rules" + detect = [".luaurc", ...] + always 태그
  skills/<s>/SKILL.md, references/
  rules/*.md                   paths frontmatter (지금 형식)
  (선택) snippets/ tools/ typedefs/ .lsp.json
```
- 팩 하나를 더할 때 필요한 것은 파일 두 개(plugin.json, coderag.toml)와 내용뿐이다. 훅 코드는 0줄이다. web-security 도 coderag pack 으로 등록한다. 지금은 `coderag.toml` 이 없다.
- 그 저장소에서 어떤 팩이 켜졌는지(활성 집합)는 한 곳에서 읽는다. Claude 경로에서는 coderag 훅이 `.claude/settings{,.local}.json` 과 사용자 settings 의 `enabledPlugins` 에서 `<pack>@claude-doctor-market` 를 읽고, 없으면 manifest 의 `defaultEnabled` 를 본다. codex·agy 경로에서는 AGENTS.md 를 생성할 때 project `coderag.toml` 의 `[[packs]]` 를 본다. `q:doctor` 가 두 곳이 어긋나는지 검사한다(PACK-MISMATCH).
- 대안도 있다. 팩에 `hooks.json` 한 줄(`coderag hook post-tool --pack <p>`)만 두는 방식이다. 코드는 없지만 팩마다 입구가 복제되고, 사용자가 "걸린다"고 한 바로 그 형태라서 차선으로 둔다.
- 행동 플러그인(q, qwreey-advisor, qwreey-conventions, qwreey-proc-guard)은 coderag 없이도 돌아야 하므로 지금처럼 플러그인으로 남는다. `rules_inject.py` 의 정본도 qwreey-conventions 에 한 벌 남는다. 팩 사본 4개와 `compact_epoch` 팩 사본 2개는 없어진다.

## 4. 락인
- **Claude 전용으로 남는 것**: PostToolUse `additionalContext`, PreCompact, 플러그인 스킬과 `defaultEnabled`/`enabledPlugins`, `${CLAUDE_PLUGIN_ROOT}`, doc-locator 서브에이전트와 pre-bash 허용 목록. 모두 어댑터 한 곳(coderag 플러그인)에 모인다.
- **하네스와 무관한 것**: 팩 형식, rules 판정(`coderag rules --for`), search/get/stale, AGENTS.md generator, 스킬 사본 노출(§35.10).
- **codex**: AGENTS.md(32KiB 에서 자른다) + `.agents/skills` + Bash. 0.166 에 훅이 있지만(`--dangerously-bypass-hook-trust`, 훅 신뢰 저장) 주입 계약은 확인하지 못했다. codex 용 두 번째 어댑터는 AGENTS.md 경로별 절을 측정해서 지시가 지켜지지 않을 때 만든다. `codex mcp add` 로 MCP 도 붙일 수 있다.
- **agy**: AGENTS.md + `.agents/skills` + `.agents/rules`. 바이너리 문자열에 규칙 트리거(`always_on`, `model_decision`, "Invalid rule trigger")가 있지만 glob 트리거는 확인하지 못했다.
- 빠지는 것은 경로 조건부 주입 하나다. codex·agy 에서는 "이 확장자를 건드리면 이 명령을 쳐라"는 상시 한 줄로 대신한다. 정확도는 떨어지지만 락인은 아니다.

## 5. 지식이 늘어나는 길과 동기화
1. **포착.** 웹 저장소 세션이 교훈을 찾는다. claude-doctor 는 그 세션에서 읽기 전용이므로 팩을 바로 고치지 않는다. 대신 저장소 밖의 받은 편지함 `~/.coderag/inbox/<pack>/<날짜>-<저장소>.md` 에 남긴다(`coderag inbox add --pack web-security`, 어느 하네스에서나 부를 수 있는 CLI). web-security 0.3.0 이 손으로 한 일(`usernotes/` → rule + 스킬)을 이 형식으로 굳히는 것이다.
2. **승격.** claude-doctor 세션에서 inbox 를 본다. 재현하거나 출처를 확인하고, references 에 `source`, `last_verified`, `applies_to` 를 단다. 그다음 사용자가 확인하고 커밋한다. 사례 이름을 일반 표현으로 바꾸는 것도 이 단계에서 한다(0.3.0 에서 사용자가 정한 방식).
3. **동기화.** coderag pack 은 저장소 경로를 직접 읽으므로 gen 한 번(146ms)으로 반영된다. Claude 플러그인 캐시는 버전마다 복사본이라서 버전을 올리고 update 해야 반영된다(§20 의 "갈림 위험"). 커밋 하나에 버전 하나를 올리는 일은 import 처럼 자동화한다. 동료에게는 GitHub release 태그 하나가 두 경로를 함께 묶는다.
4. **낡음.** frontmatter `review_after`·`last_verified`·`lifecycle` 와 `coderag stale --layer pack`(97ms)을 쓴다. 팩 주인 세션(claude-doctor SessionStart)에만 알린다. 동료에게는 search 결과의 evidence 꼬리표와 `--luau` 필터만 보인다.
5. **팀.** §35 선반은 나중에 쓸 전송 수단이다(사용자: "급하지 않음"). 팩 폴더 하나가 선반의 꾸러미 하나와 같은 모양이 되게 둬서, 나중에 형식을 바꾸지 않아도 되게 한다.

## 6. 배포와 coderag 가 없을 때
- **바이너리.** GitHub release(정적 musl linux x86_64/aarch64, macOS, Windows)로 낸다. GPG 서명은 사용자가 샌드박스 밖에서 한다. claude-doctor 스크립트가 받고, 서명을 확인하고, `${CLAUDE_PLUGIN_DATA}/bin` 이나 `~/.coderag/bin` 에 둔다. 래퍼 `bin/coderag` 는 이미 이 경로들을 찾는다. 받을 수 없으면 소스 빌드로 넘어간다(무거우므로 choom).
- **바이너리가 없을 때.** 스킬과 references 는 평문 md 라서 그대로 동작한다. 래퍼는 `hook` 호출에서 조용히 0 을 돌려준다. 잃는 것은 경로 rules 주입과 search 이다. `q:doctor` 가 `CODERAG-MISSING` 과 함께 설치 명령 한 줄을 알려 준다. 비프로그래머 동료에게는 `q:start` 가 동의를 받고 설치한다.
- rules 를 잃는 게 문제라면 python 대체 구현 한 벌을 coderag 플러그인에 둘 수 있다. 사본이 팩마다 하나에서 어댑터에 하나로 줄어든다. 나는 먼저 대체 구현 없이 시작하고 동료 파일럿에서 잴 것을 권한다.
- **비용 고지**: luau-kb 를 켠 저장소에는 description 6.5k자가 상시로 실린다. search 출력은 호출할 때만 든다(top-5 약 11KB).

## 7. 이행(작게, 되돌릴 수 있게)
| 단계 | 바꾸는 것 | 잴 것 | 되돌리기 |
|---|---|---|---|
| M0 | 없음 | 이 문서의 기준선(§0) | — |
| M1 | coderag: `rules --for`, `hook post-tool`(활성 팩 판정, 회차, O_EXCL), `hook pre-compact` | 같은 고정 경로 입력에서 python `rules_inject` 와 출력이 같은지 골든 테스트, release 지연 10ms 이하 | coderag 커밋 revert |
| M2 | web-security 에 `coderag.toml` 추가, 전역 `[[packs]]` 등록 | hardening references 검색 적중 | 설정 줄 삭제 |
| M3 | coderag 플러그인 hooks.json 에 PostToolUse·PreCompact 추가, web-security `hooks/` 제거(버전 올림), 웹 저장소 하나에서 켬 | audit/34 R1-R4 식 주입 준수 프로브, 이중 주입 0, compact 뒤 다시 주입 | 버전을 내리고 `hooks/` 를 되살림 |
| M4 | luau-kb `hooks/` 제거, vendored `EXPECTED` 줄임 | Luau 저장소 하나에서 M3 과 같은 것 | 같음 |
| M5 | 본문 토큰·bigram 블룸 색인, 토큰 비율 하한 | §0-3 표(18/53 → ?), after-D 12문항 hit@5 회귀 없음, 잡음 27건 → ? | 플래그 끄기 |
| M6 | AGENTS.md generator(§19), codex 위임 하나로 시험. luau-kb description 줄이기 실험(라우터 + search) | 32KiB, codex 가 `coderag` 를 부르는지, description 을 줄인 뒤 스킬 발동률 | 생성 블록 삭제 |
| M7 | 배포 스크립트와 release, 동료 파일럿 1명 | 설치 성공, `CODERAG-MISSING` 건수 | 바이너리 삭제 |
| M8 | (조건부) mmap 색인, 그래도 부족하면 §2 조건에 따라 MCP 나 데몬 | §2 의 조건 1-4 | — |

## P 가 반박할 것으로 보는 점
- 활성 팩 판정을 위해 coderag 가 Claude 의 `enabledPlugins` 를 읽는 것은 하네스 지식이 코어에 새는 것이다. 차라리 MCP 나 데몬이 맥락을 소유하는 편이 깨끗하다는 반론이 나올 수 있다.
- 사용자의 메모리 직관을 근거로 공유 데몬을 주장할 것이다. 나는 (d) mmap 으로 사본 하나를 프로세스 없이 얻는다고 답한다. 데몬이 실제로 아끼는 양은 (N-1) × 3MB 라고 본다.
- fs watch 와 의미 검색에는 데몬이 필요하다는 주장. 나는 B mtime 검사와 146ms gen, 그리고 먼저 본문 색인으로 충분하다고 본다. 의미 검색이 필요하다는 증거는 아직 없다.
- 대체 구현 없이 가면 바이너리가 없는 동료 기기에서 rules 가 사라진다.
- codex·agy 의 경로 rules 를 AGENTS.md 상시 한 줄로 대신하는 것은 사실상 지원하지 않는 것과 같다는 반론.

## 사용자에게 물을 것
1. 팩을 켜는 스위치를 하나로 둘까요? Claude 경로에서 coderag 훅이 `.claude/settings.json` 의 `enabledPlugins` 를 읽어 활성 팩을 정하는 방식이고, codex·agy 용 `coderag.toml` 목록은 doctor 가 맞춥니다.
2. coderag 바이너리가 없는 동료 기기에서 "스킬만 동작하고 rules 주입은 없음 + doctor 경고"로 충분할까요, 아니면 python 대체 구현 한 벌을 coderag 플러그인에 둘까요?
3. 다른 저장소 세션이 찾은 교훈을 저장소 밖 `~/.coderag/inbox/<팩>/` 에 쌓고 claude-doctor 세션에서 승격하는 흐름에 동의하시나요?

재생성: `choom -n 1000 -p $$` 를 한 뒤, 위 환경 변수를 두고 `coderag gen|search|stale ...` 를 반복 실행해 시간을 잰다(perf_counter). 메모리는 `/proc/<pid>/status` 의 VmHWM·RssAnon·RssFile 을 0.5ms 간격으로 읽는다. 본문 적중은 `search --pack luau-kb --limit 50 --json <낱말>` 의 서로 다른 path 수와 `grep -rlF <낱말> packs/luau-kb/skills` 의 .md 수를 비교한다. 쓴 스크립트(/tmp/q41-scripts)는 남기지 않았다.
