# qwreey-harness 계획

목표와 지금 할 일, 열린 질문만 둔다. 끝난 일은 지우고(경과는 git log), 정해진 원칙은 `.claude/base/harness-principles.md` 로 옮긴다.

## 목표
- 여러 저장소가 함께 쓰는 하네스 지식을 프로젝트의 상시 로드 문서에서 꺼내, 켜고 끌 수 있는 플러그인과 도메인 팩, 기록(`.claude/`)으로 옮긴다.
- 언어나 sandbox 에 묶이지 않고, 동료(비프로그래머 포함)가 무엇을 얻고 얼마를 쓰는지 보고 플러그인을 골라 설치하게 한다.
- 구조와 층: `.claude/base/overview.md`. 원칙과 사용자 결정: `.claude/base/harness-principles.md`.

## 지금 (2026-11-17)
초점: 계획과 결정의 자리를 git 안으로 옮긴다(desk D17 a, 근거 `.claude/audit/64-plan-md-alternatives/summary.md`).
1. qwreey-desk 패널이 열린 결정을 `.claude/plan/decisions/` 항목 파일에, 계획 단계를 `.claude/plan/now.md` 에 쓰게 바꾼다(D18 a: 번호는 Q<n>, 옛 D1~D18 도 같은 번호로 옮김).
2. 사용자 몫(`HUMAN_TODO.md`): qwreey-conventions 0.11·0.12 갱신, luau-lsp 설치와 Windows 동료 확인, qwreey-desk 설치, Luau·웹 저장소마다 `coderag.toml` 로 팩 켜기.

열린 결정과 계획 단계는 desk 패널이 `.claude/plan/` 파일에 쓰게 옮길 예정이다. 그때까지는 패널(`/desk`)이 원천이다.
커밋 메시지의 `D<n> a` 꼴(D1~D18)은 desk 패널 결정이고, `.claude/base/decisions/` 의 `D-xx` 와 다르다.

## 열린 질문
- 저장소 `.claude/harness.local.env` 가 `USER_ONLY` 키를 바꿀 수 있게 할지. 추천: 실제로 바꾸고 싶은 키가 생길 때 허용 목록과 에이전트 쓰기 deny 훅을 함께(`home/.claude/lib/harness_env.py`).
- home-canon-guard(`~/.claude` 직접 수정 차단)와 worktree-guard(잠금·세션 확인 없는 worktree 삭제 차단) 훅을 만들지. 만들면 q·workspace 상시 줄을 뺀다(`.claude/audit/31-home-claude-md-debate/verdict.md`).
- 다른 하네스(codex, agy)에 규약(qwreey-conventions)을 주는 법. coderag 와는 잇지 않기로 했다(`.claude/base/harness-principles.md`).
- 세션 기록 반입본을 compact 회차 단위로 나눌지(사용자 "천천히"). 지금은 크기로만 나뉘고 description 이 마지막 구간의 것이다(`plugins/qwreey-sessions/scripts/sllib/store.py` `append_section`, coderag `.claude/audit/49-records-description/`).
- `q` 의 doctor·start references 에 남은 한국어 모델용 지시문을 영어로 옮길지. 큰 재작성이라 나중에(`plugins/q/skills/doctor/references/`).
- qwreey-conventions 의 rules-inject 를 `lib/` 로 옮길지(`plugins/qwreey-conventions/hooks/rules_inject.py`, `lib/README.md`).
- 스킬 본문의 `$숫자` 가 스킬 인자로 바뀌는 것을 doctor 나 시험으로 잡을지. 지금은 비용을 `USD 1` 꼴로 써서 피한다.
- delegate 드라이버 M3(비 root, macOS, Windows)와 토큰 회전 실측. macOS·Win11 실측은 사용자 기기(`.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/driver-design.md`).
- 사용자 coderag 설정(`~/.coderag/coderag.toml` 의 `[[packs]]`)의 정본을 `home/` 에 둘지. home-sync 는 `~/.claude` 밖을 다루지 않는다.
- 기록 자동화의 남은 둘: 커밋할 때 기록 검사 info 알림, `/q:start` 의 `.claude/` 뼈대 템플릿.
- PLAN.md 낡음 알림(마지막 갱신 뒤 커밋 수, 크기)을 둘지. 사용자: "리마인더가 최소한이라도 필요해"(`.claude/audit/64-plan-md-alternatives/summary.md`).
- 처음 계획의 남은 단계를 아직 목표로 둘지: table-sim·quad 의 CLAUDE.md 다이어트(stl-luau 시범은 `.claude/audit/07-stl-luau-diet.md`), `/new-luau-project` 스캐폴딩, 문서 정본(Starlight preset·스니펫 검증 공유). 옛 단계 표는 archive 의 §2.
- coderag 쪽 질문(바이너리 전달 Q4 등)은 coderag `.claude/plan/todo.md` 가 갖는다.

## 찾아볼 곳
- `.claude/base/overview.md`: 목표, 세 층, 저장소 배치, 상시 로드 목표.
- `.claude/base/harness-principles.md`: 사용자가 정한 원칙(원문 인용).
- `.claude/base/decisions/`: Luau 저장소 사이 규약 합의안 D-01~D-13.
- `HUMAN_TODO.md`: 사용자만 하는 일(삭제, 갱신, apply, 인계 전달).
- desk 패널(`/desk`): 열린 결정과 계획 단계, 작업 기록. 지금은 git 밖 플러그인 저장소에 있다.
- `.claude/archive/plan/PLAN-2026-11.md`: 2026-11-10~16 의 옛 PLAN 전문(실행 로그, 결정 경과, 사용자 원문). 그 전 기록이 말하는 `PLAN.md §N`, `PLAN.md:줄` 은 이 파일이다. 줄 번호는 앞에 붙은 frontmatter 만큼 6 을 더한다.
