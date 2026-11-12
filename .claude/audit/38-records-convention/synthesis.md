# 38 기록 규약 토론 종합

> Snapshot 2026-11-12. 토론 P(평문 우선)·Q(coderag 중심) 2라운드의 수렴 결과다. 확정은 사용자 답(아래 "물을 것") 뒤에 규약 스킬로 옮긴다. 근거는 round1-P/Q, round2-P/Q.

## 합의 (양쪽 서명)
1. **두 부류.** 살아 있는 문서(plan, base, research)는 status 를 갖고 끝나면 `archive/<원래 폴더>/` 로 간다. 스냅샷(audit, handoff, sessions)은 status 없음, 고치지 않음, 옮기지 않음, 맨 위에 낡을 수 있다는 머리줄. 근거: 스냅샷을 옮기면 다른 스냅샷 안의 경로가 깨지는데 스냅샷은 고칠 수 없다.
2. **status 문법** `<state> [in|by <target>] [; <note>]`. 어휘 `active | landed | superseded | rejected | archived`. `paused` 없음(`active; on hold until …`). 날짜 없음(git 이 안다). 경로 꼴 target 만 존재 검사. `superseded_by: X` == `superseded by X`.
3. **status 는 한 곳.** frontmatter 가 있으면 거기, 없으면 첫 줄. 새로 만드는 살아 있는 문서는 frontmatter(title, description, status) 필수(본문이 색인되지 않아 위치 찾기 품질을 description 이 좌우한다). 옛 문서는 백필하지 않는다.
4. **폴더.** plan, base, research, audit/NN-slug, handoff, sessions, archive/<원래 폴더>, packs/<팩>. 처음 쓸 때 만든다. 필수는 `.claude/README.md` 하나. 이름은 `sessions`(형제의 `session/` 은 인정).
5. **README.** 손으로 쓴 1-3줄 + 목록. coderag 가 있으면 커밋한 static-gen 블록이 기본, 없으면 손 목록(`- [이름](경로) - 설명`, 상태·날짜·배너 없음). sessions/ 에는 README 없음.
6. **정리는 자동.** status 를 바꾼 에이전트가 같은 커밋에서 `git mv`, 살아 있는 문서의 링크, README 를 고친다. 훅은 옮기지 않고 아무도 지우지 않는다. 쌓인 것은 doctor 가 목록을 내고 허락 뒤 한 커밋으로 옮긴다.
7. **검사 분담(같은 검사를 두 곳에 두지 않음).** q `records_check.py`(stdlib): status 문법, archive 밖의 끝난 문서, README 누락, 살아 있는 문서의 깨진 상대 링크, 상시 로드·파일·폴더 크기. doctor 와 커밋 info 알림에서 돈다. coderag: 검색 숨김, stale, `static-gen --check`, 스냅샷 나이. coderag 가 없으면 그 몫은 건너뛴다. status 문법은 스킬에 한 번 정의하고 공용 fixture 를 양쪽 테스트가 쓴다.
8. **coderag 변경.** 1단계(실험 전): C1 status 문법과 조용한 오분류 수정(`docs/mod.rs:162-164` 가 모르는 값을 active 로 바꿔 `superseded by X` 가 검색에 남는다; `docs/meta.rs:80 split_status` 재사용), C2 폴더로 kind 추론(복수형 별칭, archive 숨김), C6 `static-gen --check` 와 `--dir` 기준 경로 버그. 2단계(실험에서 잰 뒤): C4 `.gitignore` 존중, C7 스냅샷 나이 표시, C8 암묵 설정 제외 목록(skills, agents, rules).
9. **recall.** coderag 바이너리로 `gen`(캐시는 저장소 밖, 0.03초) 후 `search --abs --layer project`. 세션 본문이나 결과 3건 미만이면 grep 병행. doc-locator 에 기대지 않는다(플러그인이 꺼져 있고 그 에이전트는 grep 이 막힌다). 바이너리 위치는 harness.env 새 키 `HARNESS_CODERAG`.
10. **스냅샷 머리말.** 세션 frontmatter 에서 `status: active`·`last_verified` 를 빼고 `date:`(90일 뒤 stale 잡음 방지). audit 은 `> Snapshot <date>. …` 한 줄. import 의 기본 제안 위치를 `.claude/sessions/` 로.
11. **raw 출력.** `.claude/**/raw/` gitignore, 요약에 수치와 재생성 명령. 예산 파일 200KB, 최상위 폴더 5MB. 상시 로드 예산은 실측으로 정한다.
12. **q:start.** `.claude/README.md`, `.gitignore` 두 줄(`.claude/**/raw/`, `.coderag/`), `session-log home .claude/sessions`. 항목마다 동의.
13. **싣는 곳.** `qwreey-conventions:agent-records` 스킬(영어 약 55줄, P 안 + Q 의 "search first, then read line ranges", static-gen 명령, 폴더로 kind 추론) + `paths: ["**/.claude/**/*.md"]` 짧은 rule(agents, skills, rules, hooks, worktrees 제외). coderag `docs-frontmatter` 는 키 참조만 남기고 이 스킬을 가리킨다.
14. **재편 실험**(PLAN 3.9 4단계). 브랜치에서, 살아 있는 세션·worktree lock 확인 뒤. recall 질문 12개(절반은 실제 트랜스크립트에서), 정답 위치를 옮기기 전에 커밋. grep/coderag x 이동 전/후 2x2 측정. 커밋 A 옮기기만, B 경로 기계 치환, C 끝난 문서의 status 와 archive, D 색인. 되돌리기: A·B 는 grep 결과가 2문항 넘게 나빠지거나 깨진 링크·테스트를 한 커밋으로 못 고칠 때. C·D 는 coderag hit@5 가 grep 보다 낮거나, 같은 hit 에 토큰이 더 들거나, stale 오탐 30% 초과, `--check` 가 일부러 낡힌 README 를 놓칠 때.

## 사소한 차이 (메인 판정)
- C3(coderag 첫 줄 status 파서): Q 는 철회, P 는 유지. 판정: 넣지 않는다. 첫 줄 status 문서는 끝난 옛 drafts 이고 archive 로 가며 C2 가 폴더로 숨긴다.
- 실험 질문 수: P 20, Q 10. 판정: 12.

## 토론이 찾은, 결과와 무관하게 고칠 것
- `plugins/q/skills/recall/SKILL.md:16` 이 coderag global layer 를 먼저 찾는다. project layer 와 바이너리 경로로.
- 세션 frontmatter(`plugins/q/scripts/sllib/store.py:246-248`)의 `status: active`, `last_verified`.
- `q:import` 의 기본 제안 위치 `.claude/records/`(import SKILL.md:10).

## 물을 것
1. coderag 저장소 변경 범위와 맡을 세션.
2. coderag 사용 형태: 바이너리 경로만 / 사용자 설치에서 플러그인도 / 동료에게 빌드된 바이너리와 플러그인 배포.
3. 형제 저장소 소급: 새 저장소와 claude-doctor 만(옛 형태는 인정) / 저장소마다 승인 받아 옮김.
