---
format: 1
title: 하네스 설계 원칙과 사용자 결정
description: 사용자가 정한 하네스 원칙: 규약 충돌은 합의안 D-xx, 전역 CLAUDE.md 없이 플러그인 주입과 끄기, 팩은 기본 꺼짐·데이터만, 비용은 알리고 줄 세움, 메인 대화·서브 구현(opus), 훅은 판단 기회만
status: active
---

# 하네스 설계 원칙과 사용자 결정

사용자가 정했고 지금도 유효한 원칙이다. 결정에 이른 경과와 실행 기록은 `.claude/archive/plan/PLAN-2026-11.md` 와 git log 에 있다. Luau 저장소 사이에서 갈린 규약의 합의안은 [decisions/](decisions/README.md)(D-xx), 구조는 [overview.md](overview.md).

## 결정하는 법
- 규약이 저장소마다 갈리면 한쪽으로 통일하지 않는다. 항목마다 근거를 붙인 합의안을 `.claude/base/decisions/D-xx` 로 쓰고 사용자 확인을 받는다. 정책이 갈리면 선택지와 근거를 낸다.
- 새 규약은 새 저장소와 claude-doctor 에만 적용한다. 형제 저장소의 옛 형태는 소급해 고치지 않고, 검사기는 인정만 한다.
- 다른 세션이 도는 저장소는 손대지 않는다(2026-11-10 quad 의 14GB worktree 는 lock 이 걸린 채 쓰이는 중이었고, 감사 보고의 "지워도 됨" 판단이 틀렸다). 고칠 것은 `.claude/handoff/<저장소>.md` 에 쓰고 전달은 사용자가 한다.
- 상시로 실리는 문구는 기본 시스템 지시와 겹치는지 먼저 보고, 토론(`qwreey-debate:debate`)을 거쳐 정한다.

## 지식을 두는 곳
- 짧은 필수 규칙은 rule(경로 조건), 상세는 스킬에 둔다. 실측: 경로 조건 rule 은 Read, 새 파일 Write, Bash `cat`, 서브에이전트의 Read 에서 실리고 grep 에서는 실리지 않는다(사용자 레벨 rule 도 2026-11-11 확인). Bash 로 쓴 파일에는 qwreey-conventions 의 `bash_writes.py` 가 rule 을 붙인다.
- 툴킷 무관: 하네스는 Roblox/Luau 전용이 아니다. 공통 코어에 툴킷별 자리(luau, web …)를 두고, 경로와 기기 값은 코드 기본값과 자동 감지로 정하며 바꿀 때만 `/config` 옵션이나 `harness.env` 를 쓴다. 근거: `.claude` 를 제어하지 못해 실패한 예전 경험. 설계 조사는 `.claude/audit/14-toolkit-agnostic.md`.
- 도메인 팩(`packs/`)은 관용 규약(qwreey-conventions)과 따로 둔다(사용자: "luau-kb 는 관용 표현이 아님"). 기본 꺼짐이고, 쓰는 저장소가 `coderag.toml` 의 `[[packs]]` 로 켠다.
- 팩은 데이터만 든다. rule 주입, 중복 제거, compact 회차는 coderag 코어가 맡고, 팩 스위치는 프로젝트 `coderag.toml` 하나다(`.claude/audit/41-knowledge-packs-debate/synthesis.md`). 이유(사용자): "luau-kb 는 stale 해질 수도 있고, 필요에 따라 검색해야할 수도 있고…시행착오로 새로운게 나올 수도 있고, 그래서 싱크 되거나 해야할 수도".
- 원천 하나, 접근 둘: 팩 references 는 frontmatter 를 달고, 스킬(Claude)과 coderag CLI(다른 에이전트, 정밀 조회)가 같은 파일을 읽는다.
- compact 뒤에는 팩 본문을 다시 넣지 않고 앞에서 쓴 문서를 가리킨다. 사용자: "한번 로드 된것이 항상 끝까지 필요한건 아닐 수 있고. 그래서 그것이 필요할지 판단은 메인 에이전트가 해야할 것 같기도 함."
- 규약(qwreey-conventions)과 coderag 는 잇지 않는다. 사용자: "컨벤션은 늘 필요하기도 하고. 또 무언가를 강제화 하기 위한 도구라서…stale 이 되는 도구도 아니고…coderag 는 처음부터 '컨벤션' 을 다루는 도구는 아닌것 같아서". qwreey-conventions 는 자기 주입기와 판정 훅을 가진 플러그인으로 남는다.

## 배포와 켜고 끄기
- 공유와 배포는 플러그인으로 한다(마켓 `claude-doctor-market`).
- 전역 CLAUDE.md 는 두지 않는다. 사용자: "끄고 켜거나 하는 유연성도 적고 이식성이 적어서. 없는게 나아보이기도 하더라. 하나를 정본으로 두고 끄고 켜는 방법을 선호". 상시 규약은 플러그인의 SessionStart·SubagentStart 주입(`lib/ambient.py`, 글은 `plugins/<p>/context/`)으로 싣고 플러그인마다 끈다(`.claude/audit/32-plugin-ambient-context.md`).
- memory 줄은 상시 주입에 넣지 않는다. 사용자: "메모리 쓰는건 소수 경우고 그 때 알려주는게 일반적으로 싼것 같아". memory 파일을 쓸 때 실리는 memory rule 과 memory-placement 훅이 맡는다.
- 플러그인은 독립 패키지다(Q28 a): 설치본만으로 돌고 자기 폴더, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PROJECT_DIR`, Claude Code 자신의 파일만 본다. 이 저장소의 클론 위치, 작업공간 폴더, 다른 플러그인 설치 여부에 기대지 않고, 다른 플러그인은 있을 때만 쓴다. 기반 플러그인과 묶음 플러그인은 두지 않는다. 사용자: "딱 하나의 plugins/*/readme.md 를 보고 필요한걸 까는 구조", "윈도우면 문서함에 프로젝트가 있기도, desktop 에 프로젝트가 있기도 다 다르고". 확인은 `HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py`. 계획 `.claude/archive/plan/plugin-independence.md`.
- 다른 저장소는 Claude Code 세션 기록의 작업 폴더에서 자동으로 찾고, 사용자가 qwreey-workspace 옵션으로 더하고 뺀다(Q29 a, `lib/known_repos.py`).
- 플러그인은 작게 나눈다. 사람이 치는 명령은 `q`(start, doctor, away, back)에 두고, 자연어로 시키거나 모델이 판단해 쓰는 기능은 따로 끌 수 있는 플러그인으로 둔다(사용자: "안 쓰고 싶은 곳에서는 끌 수 있는 모양").
- 플러그인마다 README 를 사람용 카드로 쓴다: 무엇이 달라지나, 비용, 효과, 왜 택하나, 요구 사항, 설치와 끄기. 기술 세부는 플러그인 `docs/`. 사용자: "그 패키지가 뭘 하는지, 대략 비용이 어떻고 효과가 어떤지, 택한다면 왜 택해야하는지 알 수 있도록…각 동료들은…본인이 원하는 최선을 택할 수 있는것 같음".
- 사람이 고르는 설정(켜기·끄기, 언어, 모델 선택 등)은 각 플러그인의 `userConfig`(`/config`)에 둔다. 사용자: userConfig 를 두고 harness.env 를 쓰면 "공개하기에 애매한 단계처럼 보이기도". 튜닝 값과 저장소 층은 `harness.env` 고급 키로 남는다.
- 플러그인의 기능은 설치하면 켜진다. 처음부터 꺼져 있어야 할 기능은 그 기능만의 플러그인으로 나눈다. 예외는 저장소가 골라야 뜻이 있는 것(advisor 의 high 등급처럼) 하나다. 사용자: "플러그인 설치 즉시 기본값은 있고, 기본은 켜짐이여야 하는거 아냐? 플러그인 설치 자체가 사용하겠다는 의사인데, 그 의사 뒤에 또 켜야할것들이 엄청 많아보이는데." (Q30 b)
- 끄기 스위치는 플러그인마다 둔다. 설정은 층으로 읽는다: 기본값 < `~/.claude/harness.env` < 플러그인 옵션(`settings.json` 의 `pluginConfigs`) < 저장소 `.claude/harness.env` < `.claude/harness.local.env`(커밋 안 함) < 환경 변수(사용자: "레이어로 합쳐지는 모양에 local 이 최상위"). 실행 경로, 기기 값, 보안 게이트 키(`USER_ONLY`)는 저장소 층이 바꾸지 못한다.
- 플러그인이 함께 쓰는 코드와 문구는 `lib/` 에 정본을 두고 플러그인은 사본을 든다(`tools/sync-copies.py`). 사용자: "플러그인의 특징과 상관 없게 필요한 코드기도 하니까".
- `~/.claude` 는 `home/` 정본에서 고치고, `home-sync.sh apply` 는 사용자가 한다. settings.json 은 마이그레이션으로 반영하고 사용자가 `/config` 로 바꾼 값은 건드리지 않는다.
- 이 sandbox 의 git 계정은 에이전트 전용이라 에이전트의 push 가 정상 흐름이다(`HARNESS_AGENT_PUSH=normal`). `git push` deny 를 기본으로 넣지 않는다.
- 빌드된 바이너리(coderag 등)는 개발이 어느 정도 끝난 뒤 GitHub release 로 낸다. 사용자: "github release 로 실어서 넣고, 내가 gpg 사이닝을 더할게.(sandbox 바깥에서)". 받는 쪽은 서명을 확인하고, 없으면 소스에서 빌드한다.
- 사용자 가시성(statusline, 테마, 응답 형식)도 개선 대상이다. 주관적이라 설치는 묻고 켜고 끌 수 있게 둔다(`.claude/audit/22-user-ergonomics.md`).

## 비용과 위임
- 비용은 막지 않고 알리고 줄 세운다. 사용자: "강제라면 위임해 두고 갔는데 멈춰 버려 오히려 손해", "전체 예산을 한계치로 두고 하나가 끝나면 다음을 돌리는 게 실제로 좋더라", "작은 패스를 여러 번 하는 게 토큰이 덜 든다".
  - 사용자가 있을 때는 큰 팬아웃 전에 알린다(훅 warn, 한도 `HARNESS_FANOUT_WARN_*`). away 에서는 예산 상한과 슬롯으로 직렬화한다. 예산 단위는 요금제에 맞춘다(USD 또는 한도 %). 구현 `plugins/q/scripts/subagent-slots.py`, 근거 `.claude/scopes/plugins/q/audit/21-cost-disclosure.md`.
- 메인은 대화와 판단을 맡고, 설계가 정해진 구현은 백그라운드 서브에이전트(수행자)가 한다. 근거(사용자): "fresh 컨텍스트에서 그 작업이 시작되고 끝나는게 나아…opus 가 opus수행자를 내리는게 더 싼 경우도 많이 존재함…설계 한 사람이 설계대로 짜면…확증편향에 걸려 과신하고 구현하는데". 남용은 피한다(사용자: "모든 상황에서 서브에이전트를 남용하는건 또 좋지 않아"). 문구 `plugins/qwreey-operator/context/ambient.md`, 근거 `.claude/scopes/plugins/qwreey-operator/audit/50-main-delegate/synthesis.md`.
- 수행자 모델은 opus 가 기본이다(사용자: sonnet 수행자는 시행착오로 더 비쌌다). haiku 는 읽기 전용 조사만. 메인은 diff 를 다 읽지 않고 시험과 보고로 확인한다.
- 같은 부분은 한 에이전트를 작은 단계로 재개하고, 독립 부분은 병렬로 돌린다. 사용자: "작은 작업 끝내 나온걸 약간의 검토와…프롬프트를 더 넣어 재개…이미 읽은건 다시 안 읽을 수 있고…반증 근거가 확실하게 들어오면 받아드리거든. 독립 부분엔 병렬 쓰는것 동의".
- 다른 벤더(agy, codex) 위임은 서브에이전트 운용과 다른 플러그인(qwreey-delegate, 기본으로 켜지 않음)이다. 사용자: "서브에이전트 이상의 delegate 는 잡음". 격리(root uid, codex·agy 샌드박스)가 없으면 읽기 전용 의견만 기본이다(agy ACP 는 워크스페이스 밖 파일 읽기·쓰기도 묻지 않는다, `.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/portable-isolation.md`).
- 두 번째 의견: 내장 advisor 도구는 사용자가 요청할 때만 쓴다(사용자: 가격 대비 효용이 diff 기반 리뷰보다 너무 낮다). 내 흐름의 검토는 `qwreey-advisor:inherit-advisor`(fork), 내 가정 없이 반박하는 검토는 `qwreey-advisor:fresh-advisor`. 결정을 맡길 추천안을 사용자에게 내기 전에도 쓴다. 근거 `.claude/scopes/plugins/qwreey-advisor/audit/18-second-opinion.md`.

## 훅과 상시 문구
- 훅은 모델이 놓친 부분에 판단할 기회만 준다. 사용자: "훅은 단순히 모델이 놓친 부분에 대해 판단할 기회를 줄 뿐이여야해(다른 workspace 쓰기처럼 위험하거나 꼭 확인해야하는 특정 상황 아니면)". 메시지 규칙은 `home/.claude/HOOK-MESSAGES.md`.
- compact 뒤 다시 싣는 플러그인 블록은 PreCompact 에서 요약에서 빼라고 알린다(`.claude/audit/51-precompact-omit/notes.md`).
- 모델용 지시문은 영어로 쓴다. 사용자가 부르는 스킬의 description 은 한국어 메뉴 줄이어도 된다(사용자: "유저 invoke 는 한국어여도 된다").

## 기록
- 기록 규약의 정본은 coderag(`coderag:agent-records` 스킬)다. 기록은 coderag 가 없어도 평범한 markdown 으로 읽혀야 한다.
- 기록이 닫히는 기준은 일을 마쳤는지가 아니라 지금의 원천으로 필요 없어졌는지다. 사용자: "quad를 보면 slot 을 전부 구현 완료 했지만 그래도 base에 가지고 있음…'끝났다' 라는건 문서가 필요하지 않다가 기준일텐데".
- `PLAN.md` 는 루트에 둔다(사용자: "나도 많이 참조하는 파일"). 수명이 다른 것을 섞지 않는다: 원칙은 이 파일, 구조는 `overview.md`, 경과는 git log 와 archive(`.claude/audit/64-plan-md-alternatives/summary.md`).
- 옮긴 기록의 옛 경로는 손이 아니라 스크립트로 바꾼다(사용자: "작은 모델로 기계적으로 링크를 고치는게 나을지도"). 지금은 `coderag records move`.
- coderag 가 만드는 문구와 static-gen 표 머리는 영어, 기록 내용은 쓴 언어 그대로 둔다(사용자: "언어는 coderag가 만드는건 영어여도 좋고 static-gen이 각 저장소 README에 넣는 표 머리 또한 영어여도 상관 없을것 같음").
