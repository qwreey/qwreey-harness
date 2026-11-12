# 46. coderag 가 모델에게 보이는 것 전부: 스킬·MCP 도구 관점 검토

> Snapshot 2026-11-12. coderag 234c6c1(플러그인 0.4.2, `target/release`) 읽기 전용 검토. 다른 세션이 고치던 `crates/coderag-core/src/docs/stale.rs`(코드 주석 참조 스캐너)와 tech-design §11.6 은 뺐다. 토큰은 `0.4×ASCII + 1.6×한글 + 1.5×그 밖` 어림. 전체 목록은 `raw/inventory.md`, 초안은 `raw/doc-locator.en.md`·`raw/mcp-tools.md`.

## 결론
- 사용자 짐작이 맞다. 모델이 읽는 coderag 문구는 영어로 하나로 맞추고, "다음에 무엇을 하라" 는 꼬리 안내는 결과마다 붙이지 말고 스킬·에이전트·(나중의) MCP 도구 설명에 한 번만 적는 편이 낫다. 기록 제목·요약·본문은 사용자 언어 그대로 둔다.
- 다만 절감의 대부분은 search 결과가 아니라 늘 실리는 설명과 주입문에서 나온다. search 출력에서 꾸밈(범례·꼬리표·`~토큰`)은 6-10%(quad 8건 1,160토큰 중 115, claude-doctor 975 중 62)뿐이고, 그중 한국어는 `버전:`·`N절` 몇 토큰이다. 나머지는 데이터(요약 줄)다.
- 꼽은 문구 `// {name}: depth limit — 더 보려면 fetch`(`crates/coderag-core/src/typewalk.rs:65`)는 언어보다 더 큰 문제가 있다. coderag 에 `fetch` 명령이 없다. 지금은 TS 심볼 `get --inline` 에서만 나와 드물게 보인다.
- 고칠 결함 다섯: `get` 이 없을 때 `Error: warning: … not found`(접두가 두 번), `| head` 로 파이프하면 Rust panic 세 줄, `--hint` 가 상대 경로를 줌(Read 는 절대 경로만 받음), `--budget` 도움말의 "(글자 수 어림)"(실제로는 토큰), docs-backfill 이 `format: 1` 을 빠뜨림.
- 일반 세션(메인과 서브에이전트 2개, rule 주입 3번, post-edit 알림 1번, search 5번, get 2번) 기준으로 약 0.9k 토큰을 줄인다. 거기에 doc-locator 를 한 번 띄울 때마다 약 0.8k, 에이전트가 `--help` 를 한 번 볼 때마다 약 0.5k 가 더 준다.

## 1. 무엇이 얼마나 보이나 (요약, 전체는 raw/inventory.md)
| 표면 | 빈도 | 토큰 | 판정 |
|---|---|---|---|
| doc-locator `description`(한국어) | Agent 도구가 있는 모든 맥락(메인과 서브에이전트, 이 서브에이전트에서도 보임) | 250 | 영어 176 |
| agent-records 스킬 `description` | 스킬 목록이 있는 모든 맥락 | 236 | 영어 그대로 두고 187 로 줄임 |
| docs-backfill `description`·본문(한국어) | 0 (`disable-model-invocation: true`, 사용자 호출 때만 1,176) | 0 | 영어, 우선순위 낮음 |
| plugin.json·hooks.json `description`(한국어) | 사람이 보는 UI 뿐, 모델은 안 봄 | 0 | 영어, 우선순위 낮음 |
| rules-inject 감싸개(`rules/mod.rs:285`, 이미 영어) | rule 마다 맥락마다 한 번 | 106 | 50 으로 줄임 |
| rule `rules/agent-records.md` | `.claude/**/*.md` 를 건드린 맥락마다 한 번 | 446 | 유지 |
| post-edit 알림(`cli/src/hook.rs:88,93`) | 문제 있는 기록을 쓸 때 | 106·112 | 영어 62·49 |
| pre-bash 거부(`hook.rs:139`) | doc-locator 가 목록 밖 명령을 쓸 때 | 76 | 영어 48 |
| session-start 가리킴(`ledger.rs:202`, 영어) | compact 마다 | 약 45 + 항목 | 유지 |
| search 꾸밈: `버전:`, `N절`, `통째 권장`, `절 verified`, `→ 이 프로젝트:` | 호출마다 | 결과당 1-3 | 영어 |
| `(결과 없음 — 다른 낱말, --all(숨김 포함), coderag list 로 훑기)` | 결과가 없을 때 | 38 | `(no results)`, 안내는 설명으로 옮김 |
| get 머리: `절 단위 문서 ~9.0k — 필요한 절만 읽기(path:시작-끝)`, `id: doc …`, `frontmatter 없음` | get 마다 | 34·24·9 | 빼거나 줄임 |
| `--help` 전체 / `search --help` / `get --help` | 드묾(처음 쓰는 에이전트) | 1,318 / 1,290 / 837 | 영어, `hook`·`mcp` 숨김 |
| 오류·경고(stderr), 사람용 명령(`pack status`, `taxonomy`, `adapt`, `static-gen`) | 드묾 | 15-50 | 영어 |

## 2. 문구별 판단 기준과 결과
네 가지를 물었다. 꼭 있어야 하나, 설명에 한 번 적으면 되나, 영어여야 하나, 다음 명령을 정확히 알려 주나(그냥 상황을 말하는 데 그치나).
- 결과마다 한 번 적으면 될 안내: 결과 없음 줄의 조언, `--hint` 의 `(path:시작-끝 → offset=시작 limit=끝-시작+1)`, `절 단위 문서 … 필요한 절만 읽기`, `절 N개 — --sections 로 목차`, stderr `절 단위 권장(get --sections 로 목차, path:시작-끝 으로 그 범위만)`, not-found 꼬리 `coderag search 로 찾거나 coderag list 로 훑기`, post-edit 꼬리 `기록 규약은 coderag:agent-records 스킬, 키 목록은 …`. 마지막 것은 같은 Write 에 주입되는 rule 이 이미 `Load the coderag:agent-records skill` 이라고 말한다.
- 상황만 말하고 다음 할 일을 안 알려 주거나 틀림: `더 보려면 fetch`(없는 명령), `--hint` 의 `Read .claude/…`(상대 경로라 Read 가 못 받음), `frontmatter 없음`(snapshot 에도 붙는데 snapshot 은 frontmatter 가 필요 없고, 옛 기록은 채우지 않는 규약이라 할 일이 없다).
- 유지(짧고 행동을 바꿈): 범례 `@P = <root>`, `~토큰`, `[kind, status]`, `→ 이 프로젝트:` 표식 자체, `warning: pack '{}' 색인 없음 — coderag gen --pack {}`(명령을 줌), 버전 불일치 꼬리표.
- 도움말의 변경 이력 서술(agent-docs 위반): `--abs` 의 `이 옵션이 옛 절대경로 출력을 낸다`, `--level` 의 `생략하면 지금의 두 줄 출력 그대로`, `--desc-max` 의 `(한국어 요약 줄 약 57자, 영어 약 125자)`, `static-gen` 의 `채널 A(문서)`, `mcp` 의 `미구현(TODO.md M2)`.

## 3. 언어 정책 제안
- 영어: coderag 가 만들어 내는 모든 문구. CLI stdout 의 꾸밈과 꼬리표, stderr 경고·오류, clap 도움말, 훅 출력, 스킬·에이전트·rule, plugin.json·hooks.json 설명, `bin/coderag` 의 바이너리 없음 안내. coderag 는 벤더 중립 범용 도구이고 읽는 쪽이 모델이며, claude-doctor 의 `agent-docs` 도 "Text that passes between models (skills, agent prompts, hook messages) is English" 라고 정한다. 영어 문구가 토큰도 30-45% 적다.
- 사용자 언어 그대로(데이터): 기록·팩의 title, description, 절 요약, 본문, taxonomy label. 꼬리표 낱말만 영어로 맞춘다(`N sec`, `read whole`, `closed`, `sec verified`).
- 한국어 사용자가 실제로 읽는 곳: 터미널에서 직접 치는 `gen`·`pack status`·`adapt --dry-run`·`taxonomy`, CI 의 `static-gen --check`·`lint`, `README.md`, `static-gen` 이 사용자 저장소 README 에 쓰는 머리 `| 문서 | 설명 | 상태 |`. 앞의 넷은 짧은 영어 줄이면 충분하다고 본다(사용자는 영어 CLI 를 쓴다). README 와 생성되는 표 머리는 사용자가 정할 일이다. 표 머리를 바꾸면 모든 저장소의 `static-gen --check` 가 한 번씩 다시 생성하라고 실패한다.
- 질의어: 한국어 기록에는 한국어로 질의해야 맞는다. 그래서 설명에는 "query in either language" 한 줄만 둔다.

## 4. MCP 준비 (초안 raw/mcp-tools.md)
- 도구: `search`, `get` 둘을 기본으로 둔다(tech-design §31 의 "도구 2–3개" 와 같다). 선택 도구는 둘이다. 기록 관리용 `stale`, 그리고 post-edit 훅이 없는 codex·agy 용 `lint`. `gen`(데몬이 색인을 관리), `static-gen`, `pack`, `taxonomy`, `adapt`, `provider`, `hook`, `rules` 는 CLI 에만 둔다.
- `search(query, limit=8, kind, layer[], pack[], category[], tag[], evidence[], all, expand=0|1|2|auto, budget)`: 결과 형식, 2-4 낱말 질의, 빗나가면 바꿔 말한 뒤 `all`, 읽을 때는 `get` 이나 Read 로 범위만.
- `get(target, section, body, with_requires)`: target 은 출력에 찍힌 위치(`@P/a.md`, `#slug`, `:a-b` 꼬리 허용)나 절대 경로나 id. 플래그가 없으면 머리를 주고, 긴 문서면 목차를 준다. `body` 는 원문을 준다(Read 가 없는 하네스에도 쓸 수 있다).
- 서버 `instructions`(세션당 한 번, 초안 약 410토큰. 내기 전에 줄여야 함): 위치 문법과 `@X =` 범례, 1부터 세는 양끝 포함 줄 범위, `~토큰`, 꼬리표 어휘, 닫힌 기록이 숨는다는 것, `-> overridden here:`, 질의 언어. 결과마다 붙던 안내 7개(2절 첫 항목)와 doc-locator 1단계, agent-records "Finding records" 의 `@P` 설명이 이리로 옮겨 간다.
- CLI 출력은 MCP 와 같은 바이트로 내고, 안내 줄은 stdout 이 터미널(사람)일 때만 낸다. 에이전트가 Bash 로 부르면 파이프라 나오지 않는다.

## 5. 스킬·에이전트·rule 감사 (skill-creator 기준)
- agent-records 스킬: 설명이 무엇을 하고 언제 쓰는지 둘 다 담고, 조금 밀어붙이는 말투이고, 끝에 한국어 트리거가 있어 좋다. 본문은 102줄로 500줄보다 훨씬 짧고, references 하나를 언제 열지 적어 두었다. 덜어낼 것은 셋이다. 설명 괄호 속 폴더 나열과 `key list in references`(본문에 적을 정보다. 초안: "Convention for agent records under a repo's .claude/: which folder a record goes in, the status line, closing a record and moving it to archive/, frontmatter for new living records, README indexes, raw output, finding old records. Use it whenever you write, edit, supersede, close or move a record under .claude/, get a coderag lint or records-check notice, or set up .claude/ in a new repo. 기록 규약, 기록 폴더, 아카이브, status, frontmatter."), 앞날 계획 `A future coderag migrate rewrites only active living records; …`(50토큰), 그리고 범용 도구 스킬이 claude-doctor q 플러그인에 묶인 `python3 -I <q plugin>/scripts/records_check.py (also run by q:doctor)`(279토큰짜리 Checks 절 안). 마지막 것은 "q 플러그인이 있으면" 한 줄로 바꾸거나 q 쪽 문서로 옮긴다. MCP 가 생기면 "Finding records"(182) 와 "Using what coderag returns"(174) 는 도구 설명과 겹치므로 두세 줄로 준다. 스킬을 부를 때마다 약 250토큰이 준다.
- rule 과 스킬의 중복: rule 의 7줄(446)은 스킬의 Status·닫기·Frontmatter 를 줄인 것이라, 둘 다 실리면 그만큼 겹친다. 하지만 rule 은 스킬을 안 불러도 늘 지켜야 할 핵심이고, 스킬은 rule 이 없는 하네스에서도 혼자 서야 한다. 그래서 의도된 중복으로 보고 그대로 둔다.
- doc-locator: 한국어(1,915토큰)라 영어 초안 1,049로 줄인다(설명 −74, 본문 −791). 본문에는 search 출력 형식 설명이 들어 있어 스킬 "Finding records", q:recall 의 locate 지시와 세 군데서 겹친다. q:recall 은 플러그인이 꺼진 경우를 이유로 doc-locator 를 쓰지 않는다(audit/38 round1-Q §3.3). 실제 호출도 기록상 한 세션뿐이었다(c9a9e895). MCP 가 생기면 Bash 거부 훅과 함께 없애는 것을 사용자에게 제안한다. 그때까지는 영어 초안으로 둔다.
- docs-backfill: 사용자만 부르므로 평소 비용은 0 이고, 새 저장소나 팩 문서를 들일 때 쓸모가 있어 남긴다. 다만 두 가지를 고친다. 영어로 옮기고(약 600토큰 예상), 채울 키 목록 `title·description·keywords·kind·status` 에 `format: 1` 을 더한다. 지금은 규약("write `format: 1` in every frontmatter you create, whether by hand or by a tool")과 어긋난다. 게다가 backfill 은 Edit 로 쓰는데 post-edit 의 format 알림은 Write 에만 나와서, 빠뜨려도 아무도 모른다.

## 6. 우선순위 변경 목록
"테스트" 칸은 바꾸면 함께 고쳐야 하는 검사다. e2e 는 `crates/coderag-cli/tests/e2e.rs`, 대조는 claude-doctor `tools/tests/test-coderag-rules-parity.py` 다.
| # | 위치 | 지금 | 제안 | 절감 | 위험·테스트 |
|---|---|---|---|---|---|
| 1 | `agents/doc-locator.md` 전체 | 한국어 1,915 | `raw/doc-locator.en.md`(응답 표식 `옛 기록`→`closed`, `미재현`→`unverified`) | 세션당 맥락마다 −74, 호출마다 −791 | 낮음. 부르는 쪽이 한국어 표식을 기대하지 않는지 확인 |
| 2 | `rules/mod.rs:285-294` 감싸개 | `Path-scoped rules from the {pack} plugin, loaded because you wrote {label}. They apply … not shown again.` + `Check what you just wrote … with Edit if it does not comply.` | `Rules for files matching these paths (shown once per context; you wrote {label}). Check what you wrote against them and fix it.` | 주입마다 −56(세션 3번이면 −168) | 중간. 바이트 대조라 qwreey-conventions `hooks/rules_inject.py`·팩 사본과 같은 커밋에. `rules/tests.rs` |
| 3 | `cli/src/hook.rs:88` | `… 기록 규약은 coderag:agent-records 스킬, 키 목록은 그 스킬의 references/frontmatter-keys.md.` | `coderag: {rel}: {issues}.` 꼬리 뺌(문제 문구는 영어로) | 알림마다 −63 | 낮음. `CODERAG_RULES=off` 이면 rule 이 없으니 그때만 꼬리를 남긴다. hook.rs 테스트의 `superseded_by 대상 없음`·`format 없음`·`status 의 대상 없음` |
| 4 | `hook.rs:93` | `frontmatter 없음 — 새 살아 있는 기록(plan·base·research)은 title·description·status 를 둔다(…). description 이 검색 결과에 찍히는 한 줄이다.` | `{rel}: no frontmatter. A new living record starts with format: 1, title, description, status; description is the line search shows.` | −44, `format` 누락 고침 | 낮음. `frontmatter 없음` 단언 |
| 5 | `hook.rs:139` | `doc-locator 는 … 만 실행합니다(파이프·리다이렉트 없이). 원문 확인은 Read 로 줄 범위만 읽으세요.` | `doc-locator may run only coderag search\|get\|list\|stale (no pipes or redirects). Check text with Read on the line range.` | 거부마다 −28 | 없음 |
| 6 | `typewalk.rs:65,71` | `// {name}: depth limit — 더 보려면 fetch`, `(위 참조)` | `// {name}: not expanded (depth limit); raise --type-depth`, `(see above)` | ±0, 할 일을 알려 줌 | 낮음. typewalk 테스트 |
| 7 | `main.rs:549` | `Error: warning: {id} not found — coderag search 로 찾거나 coderag list 로 훑기` | `Error: not found: {id} (find it with coderag search)` | −15 | 없음 |
| 8 | stdout 쓰기 | `\| head` 에 panic 세 줄 | `main` 첫머리에서 SIGPIPE 를 기본 동작으로 되돌리거나 EPIPE 를 종료 0 으로 | 그때마다 −45, 헷갈림 없앰 | 없음 |
| 9 | `docs/mod.rs:918,922,907` + head `id:` | `절 단위 문서 ~9.0k — 필요한 절만 읽기(path:시작-끝)`, `절 {n}개 — --sections 로 목차`, `frontmatter 없음`, `id: doc …` | 첫째 줄 뺌(목차와 `N sec` 꼬리표가 같은 말), `{n} sections (--sections)`, `frontmatter 없음` 은 living 기록에만, 문서 `id:` 는 `--json` 에만(절 id 는 `overrides:` 에 쓰이니 둠) | get 마다 −30~−60 | 중간. e2e `절 단위 문서` |
| 10 | 꼬리표·머리(`docs/mod.rs:291,302,303,842`, `render.rs:68`, `version.rs:139,165,179,183`, `levels.rs:113-116`) | `절 {st}`, `{n}절`, `통째 권장`, `옛 기록`, `→ 이 프로젝트:`, `버전:`, `— 지금`, `재확인 필요(… 확인 …, 핀 …)`, `(단계 공개: 추정 …)` | `sec {st}`, `{n} sec`, `read whole`, `closed`, `-> overridden here:`, `versions:`, `now`, `recheck (confirmed …, pinned …)`, `(expand: ~564/800 tokens · …)` | 호출마다 −1~−15 | 중간. e2e 단언 여럿, `render.rs` 테스트. q:recall 은 영어 status 만 읽어서 영향이 없다 |
| 11 | `main.rs:426` 결과 없음 | `(결과 없음 — 다른 낱말, --all(숨김 포함), coderag list 로 훑기)` | `(no results)`. 조언은 doc-locator·MCP 설명에(CLI 는 터미널일 때만) | 빈 결과마다 −35 | 낮음 |
| 12 | `skills/agent-records/SKILL.md` | 설명 236, migrate 문장, q 결합 Checks | 5절 초안대로 | 맥락마다 −49, 부를 때마다 약 −250 | 낮음. claude-doctor `records_check` 이름이 바뀌면 같이 |
| 13 | clap 도움말 `main.rs:17-284` | 한국어, 변경 이력 서술, `--budget (글자 수 어림)` 틀림, `hook`·`mcp` 보임 | 영어, `#[command(hide = true)]`(hook, mcp), 서술 빼기, `--json`·`--limit`·심볼 플래그에 도움말 | `--help` 볼 때마다 약 −550 | 없음 |
| 14 | `search.rs:360` `--hint` | `범위만 읽기: Read .claude/… offset=1 limit=158 (path:시작-끝 → …)` | 플래그를 없애거나 절대 경로와 `Read {abs} offset=a limit=n` 만 | 쓰는 곳이 없음 | 낮음. e2e `범위만 읽기: Read ` |
| 15 | 그 밖의 stderr·오류(`main.rs:296,301,401,539,554,596,927`, `layer.rs:284,293,303`, `config.rs:274`, `docs/mod.rs:377`, `bin/coderag:39`), lint 문구(`mdfm/lib.rs:1044-1104`, `lint.rs`) | 한국어 | 영어, 다음 명령은 그대로 둠. doc-locator 4단계가 맞추는 `먼저 coderag gen` 과 같이 바꿈 | 드묾 | 중간(e2e 단언이 많음). stale.rs 는 진행 중인 작업이 끝난 뒤에 |
| 16 | `skills/docs-backfill/SKILL.md` | 한국어, `format` 없음 | 영어, 키 목록에 `format: 1` | 0(사용자 호출) | 없음 |
| 17 | plugin.json·hooks.json 설명, README | 한국어 | 설명은 영어, README 는 사용자가 정함 | 0 | 없음 |

## 7. 합계
- 일반 세션(1절의 가정) 약 −0.9k 토큰. 나누면 설명 두 개 3맥락 −369, 감싸개 3번 −168, post-edit 1번 −55, get 2번 −60, search 5번 −10, 스킬 한 번 부를 때 −250.
- 사건마다 더 준다. doc-locator 호출 −0.8k, `--help` −0.5k, 결과 없음 −35, panic −45.
- MCP 로 가면 같은 내용이 서버 instructions(약 0.4k, 줄일 것)와 미뤄 실리는 도구 스키마로 옮겨 간다. 그러면 doc-locator(설명 176 + 본문 823)와 pre-bash 훅을 없앨 수 있다.
- 순위 결함 하나(문구가 아님): `coderag search zzqqxx` 가 claude-doctor 에서 그 낱말이 없는 결과 2건(audit/29 measure.md, audit/31 r2-P.md)을 냈다. 한 낱말 질의가 본문 블룸 오탐으로 통과한 것이다. 본문으로만 맞은 결과는 원문을 확인하거나 `[body?]` 표시를 붙인다.

## 다시 만들기
- 색인: `CODERAG_CACHE=/tmp/cr46/cd coderag --layer project gen`(claude-doctor), `CODERAG_CACHE=/tmp/cr46/quad …`(quad, luau-kb 팩 포함 검색). 훅: `CODERAG_HOME=/tmp/cr46/home CODERAG_PLUGIN_ROOT=<coderag> CLAUDE_PROJECT_DIR=/tmp/cr46/proj` 에서 stdin JSON 으로 `coderag hook post-edit|pre-bash|post-tool`(post-tool 은 `"hook_event_name":"PostToolUse"` 가 있어야 낸다).
- 토큰 어림 스크립트는 `/tmp/cr46/bin/tok.py`(남기지 않음). 식은 위와 같다.
