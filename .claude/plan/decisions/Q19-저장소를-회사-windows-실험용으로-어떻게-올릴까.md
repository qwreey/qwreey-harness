---
format: 1
title: 저장소를 회사 Windows 실험용으로 어떻게 올릴까?
description: 저장소를 회사 Windows 실험용으로 어떻게 올릴까? 권장 a) 비공개로 올리고 Windows 대응 진행
status: active; on hold until reopened on the desk
id: Q19
urgency: soon
blocks: 회사 Windows 에서 실험
recommended: a
created: 2026-11-17T01:51:52.021Z
---

# Q19. 저장소를 회사 Windows 실험용으로 어떻게 올릴까?

## 맥락

**점검 결과(opus, git 기록 전체, gitleaks 포함)**
- 비밀값: 작업 트리와 기록 전체에서 0건. 비공개로 올리는 데 유출 위험은 없다.
- 공개는 지금 안 됨: 세션 기록에 건강 정보 인용(ADHD, `.claude/sessions/2026-11-16-394d4744.md:36`), 비공개 형제 저장소(tbox, table-sim, rbvm) 내부 구조를 적은 기록 수십 개, LICENSE 없음, luau-lsp 정의 파일 MIT 고지 없음.
- 동료에게 열기 전 살필 것: `.claude/scopes/plugins/q/audit/20-onboarding.md:15-18` 에 동료를 평가하는 문장 두 곳(공개판에서 중립 문구로 바꿈).
- 이미 고침(5679b07): 루트 `.gitattributes`(Windows 에서 sh 스크립트가 CRLF 로 깨지는 것 방지), `.gitignore` 에 `.claude/worktrees/`.

**Windows 에서 실제로 돌리려면 남은 것**
- `home/settings-migrations/0001` 의 마켓 경로가 `/code/Projects/claude-doctor` 로 박혀 있음, `home/.claude/harness.env` 의 `/code/...` 경로.
- 훅 65개가 `python3 -I` 로 시작(Windows 엔 `python3` 가 없거나 스토어 가짜일 수 있음).
- q 의 `subagent_ledger.py`, sessions 의 `store.py` 가 `fcntl`(리눅스 전용)을 바로 import 해서 Windows 에서 오류. sessions 는 `setsid` 도 씀.
- 그래서 처음 실험은 luau-lsp, qwreey-conventions, desk 처럼 단순한 것부터가 안전.

**확인 부탁:** table-sim, tbox 가 회사 자산인지(점검 에이전트는 table-sim 문서의 공유 범위 문구만 봄).

**선택지**
- a: 비공개 저장소에 main 만 지금 올리고 혼자 실험. 동시에 Windows 대응(경로를 클론 위치로, python 찾기, fcntl 대체)을 에이전트로 진행. 동료 초대 전에 위 두 파일 정리.
- b: a 와 같되 Windows 대응은 실험해 보고 나서.
- c: 공개용 새 저장소(plugins, packs, lib, tools, home, README 만; `.claude/` 기록·PLAN·HUMAN_TODO 빼고 LICENSE 추가).

## 선택지

- a) 비공개로 올리고 Windows 대응 진행
  실험이 목적이라 경로·python·fcntl 부터 막힘
- b) 비공개로 올리고 실험 먼저
  어디서 깨지는지 직접 보고 고침
- c) 공개용 새 저장소

**권장 a) 비공개로 올리고 Windows 대응 진행**
비밀값이 없어 비공개 업로드는 바로 해도 된다. 박힌 경로와 fcntl 은 실험 첫날 바로 걸릴 것이 확실해서 미리 고치는 편이 시간을 아낀다.

## 코멘트

- 2026-11-17T02:06:47.562Z user: 아마 다른 결정으로 같이 어느정도 해결 되지 않았나 싶음
- 2026-11-17T02:07:16.374Z agent: 맞습니다. D20 b(정리해서 공개)와 지금 도는 Windows 대응 에이전트가 이 결정을 덮습니다. 올리는 시점은 D20 정리가 끝난 뒤가 안전합니다(기록을 다시 쓰면 커밋 해시가 바뀌므로, 먼저 올리면 다시 올려야 함). 이 결정은 미뤄 둡니다.
