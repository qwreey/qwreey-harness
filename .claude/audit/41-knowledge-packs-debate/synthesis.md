# 41. 지식 팩 그릇 토론: 종합

> Snapshot 2026-11-12. round1·round2 P/Q 와 other-harness-hooks.md 를 메인 세션이 종합하고 사용자 결정을 원문으로 붙였다. codex·agy 훅 사실은 작은 모델의 문서 요약이라 어댑터 단계에서 실측한다.

## 질문
계속 자라는 도메인 지식(luau-kb, web-security 체크리스트)을 어떤 그릇에 담아 에이전트에 닿게 하고, coderag 는 무엇이 되어야 하나. 출발점: 둘 다 기본 꺼짐 Claude 플러그인이고, 팩마다 `rules_inject.py`·`compact_epoch.py`·`conv_env.py` 사본(팩당 380줄, 합계 760줄)을 싣는다. 플러그인 캐시는 버전마다 통째로 복사되어 지식 한 줄을 고쳐도 버전을 올려야 반영된다.

## 실측 (루트 버그 수정 c216d11·cf4558c 뒤)
| 항목 | 값 |
|---|---|
| luau-kb pack 만 검색 | 30ms, 고유 메모리 약 3MB(+공유 바이너리 페이지 8MB) |
| claude-doctor 세 계층 검색 | 66-71ms |
| project gen | 250ms, 1,696-1,708 항목, 색인 1.1MB |
| luau-kb 색인(디스크) | 812KB, 메모리는 약 2.6배 |
| Rust 훅 진입 / Python rules_inject 1회 | 3ms / 17-19ms(팩마다 Read 마다) |
| 본문에만 있는 API 6개 | coderag 18파일, grep 53파일 |
| luau-kb 에 없는 문구 `닫힌 실패` | 27건(낱말 하나만 맞아도 결과) |
| 늘 켜진 스킬 설명 | luau-kb 6,456자, web-security 462자 |
| luau-kb SKILL.md 본문 합계 | 68KB(12개, 큰 것 8.7KB) |
| 메모리 cgroup | 한도 10GiB, 기록된 최고 10.0GiB |

## 합의
1. 팩은 데이터만: 스킬, references, `rules/*.md`(paths), `coderag.toml`.
2. rule 맞추기·중복 제거·compact 회차는 coderag 코어가 한 번 구현하고 모든 팩에 쓴다. Python 훅과 같은 출력인지 대조 테스트로 옮기고 web-security 부터 바꾼다. coderag 기존 `hook post-edit` 의 dedup(읽고 덧붙이기, 회차 무시)도 이때 `rules_inject.py` 의 O_EXCL 마커와 (session, agent, epoch, rule) 키로 맞춘다.
3. 프로세스: 세션마다 stdio MCP 래퍼, 사용자(uid)별 데몬(사용자 결정, 아래). 소켓은 `$XDG_RUNTIME_DIR/coderag/`(없으면 `$CODERAG_HOME/run/`), 폴더 0700·소켓 0600, 다른 uid 접속은 끊는다. 데몬은 수명 내내 flock 을 쥐어 잠금이 곧 생존 표시다. 버전을 소켓 이름에 넣어 업데이트 뒤 옛 데몬은 연결이 끝나면 사라진다. `oom_score_adj` 1000, 프로젝트 색인은 덜 쓴 것부터 내린다. 데몬이 죽으면 래퍼는 한 번 다시 붙고 안 되면 같은 결과의 프로세스 내 검색으로 대신한다. 팩 색인은 프로젝트 사이에 공유하고 프로젝트 색인은 루트별.
4. rule 주입 훅은 CLI 로 남는다(3ms). 데몬을 띄우지 않는다.
5. 본문 검색은 색인 형식에서 고친다: 본문 낱말과 한글 두 글자 블룸 필터, 질의 낱말 최소 일치 비율. CLI 와 데몬이 같은 색인을 쓴다.
6. 바이너리가 없으면 doctor 경고만. Python 대비 사본은 두지 않는다.
7. 어댑터 순서: Claude(coderag 플러그인 하나) 먼저, 그다음 codex(생성한 `.codex/hooks.json` + AGENTS.md), agy(생성한 `.agents/rules` glob 규칙 + AGENTS.md). agy 규칙을 커밋할지는 나중(사용자가 agy 를 메인으로 거의 쓰지 않음).
8. 진행 순서: 팩 훅을 코어로 옮기기 → MCP 래퍼·데몬 → 다른 하네스.
9. luau-kb 스킬 설명 줄이기 실험.

## 사용자 결정 (2026-11-12)
- 프로세스: "stdio MCP를 작은 래퍼로 두고 그게 데몬이 없으면 데몬을 띄우고, 데몬의 경우 활성 연결이 없으면 꺼지는 방향에 다른 사용자로 도는 경우는 각자 사용자 마다 데몬이 있는게 나은듯. read 가능하지 않은데 read 가능하면 안 되니까"
- 메모리: "만일 연관성이 없는 table-sim 과 quad, stl-luau 가 동시에 개발된다면 coderag 가 여러 곳에서 인보크 되어 메모리를 점유하는것 보다…한 메모리에 올라간다면 오히려 가벼울 수도"
- 팩 스위치: "팩의 스위치는 b가 맞다고 봄" → 프로젝트 `coderag.toml` 이 하나뿐인 원천, `coderag adapt` 가 하네스 설정(Claude `enabledPlugins` 등)을 생성. doctor 는 어긋남을 본다.
- 교훈 모으기: 추천대로 → 그 저장소 `.claude` 기록에 `promote:<pack>` 꼬리표. 찾으려면 알려진 프로젝트 루트 목록이 필요하다.
- 데몬 유휴 종료: 추천대로 60초(세션이 살아 있으면 래퍼가 연결을 쥐고 있다).
- 시맨틱 검색: 추천대로 본문 색인을 넣고 잰 뒤 정한다. 사용자: "블룸필터를 파일시스템에 두고 걸러내고 읽어야할 것을 반반씩 쪼개나간다던가 하면 줄일 수도 있고, 전략은 다양할듯. 메모리의 경우 더 키울 순 있음."

## 열린 문제: compact 뒤 복원 (사용자 제기)
사용자: "luau 지식을 skill 아닌 변경 가능한 곳으로 옮긴다 함은, skill 이 자동으로 restore 해주는게 안 먹는다는거야. 이게 오히려 장점일 수도 있어. 필요하거나 필요하지 않거나 상관 없어도 restore 당하고 restore 예산을 크게 깎아 먹고, 분량이 크다면 skill로 부적합한것도 맞는데 반대로 생각하면 잊어먹을 수 있다는 문제가 다시 떠오른다는거야."

사실(공식 문서 skills "Skill content lifecycle"): compact 뒤 Claude Code 는 부른 스킬마다 가장 최근 호출의 SKILL.md 앞 5,000토큰을 다시 붙이고, 합계 25,000토큰을 최근 것부터 채운다. 예산을 넘은 옛 스킬은 통째로 빠진다. 스킬이 Read 로 연 references 는 원래 복원되지 않는다. 이 세션의 compact 에서도 스킬 본문이 잘려 붙었다.

그래서 무게가 실리는 곳은 references 가 아니라 SKILL.md 본문이다. luau-kb 12개 본문 68KB 를 여럿 부르면 25,000토큰 예산을 팩 하나가 채우고, q:workspace 같은 동작 스킬이 밀려난다.

제안(정하지 않음, 다음 토론 또는 실측 대상):
- 본문이 아니라 가리킴을 복원한다. coderag 훅이 (session, agent, epoch) 마다 이 세션에서 쓴 팩 문서(get, 연 reference, 부른 스킬)를 원장에 적고, compact 뒤(Claude PostCompact·SessionStart compact, codex SessionStart `source=compact`) "앞에서 쓴 지식: 제목 — 경로§절, 기대기 전에 다시 읽어라" 몇 줄을 넣는다. 항목당 수십 토큰이라 5,000토큰 복원보다 싸고 하네스와 무관하다.
- rule 은 이미 회차가 바뀌면 다시 붙는다(다음에 맞는 파일을 열 때). 잊으면 안 되는 불변식은 rule 로 올리고, SKILL.md 는 입구와 판단 기준만 남게 줄인다.
- 확인할 것: 가리킴만 받은 에이전트가 필요할 때 다시 읽는지(compact 를 끼운 탐침, audit/34 방식), 복원 예산에서 팩이 동작 스킬을 밀어내는 빈도.
