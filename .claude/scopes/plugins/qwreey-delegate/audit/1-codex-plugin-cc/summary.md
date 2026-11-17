---
format: 1
title: 1. OpenAI codex-plugin-cc 와 qwreey-delegate 비교
description: codex-plugin-cc(1.0.6, Apache-2.0)는 codex app-server 로 같은 저장소·계정에서 일하는 두 번째 코더(rescue 기본 --write, 결과는 원문 그대로, 검증 단계 없음); 우리는 uid 격리와 Claude 검증; 가져올 것은 구조화 findings 스키마와 XML 프롬프트 블록, Windows 동료에게는 그 플러그인이 현실적 대안
---
# 1. OpenAI codex-plugin-cc 와 qwreey-delegate 비교

> Snapshot 2026-11-17. May differ from now; check current files and git log before relying on it.

사용자: "openai 공식으로 이런게 있어 https://github.com/openai/codex-plugin-cc 'Use Codex from Claude Code to review code or delegate tasks.' 공식 구현이라 참고할만한 충분한 가치가 있지 않을까 싶은걸 봤어". 서브에이전트(sonnet)가 얕은 클론을 읽기만 하고(실행 안 함, 삭제) 비교했고 메인이 기록했다. 출처 경로는 그 저장소 기준.

## 그 플러그인
- 1.0.6, Apache-2.0, 최신 커밋 2026-07-07(#447). 명령 8개(review, adversarial-review, rescue, transfer, status, result, cancel, setup), 서브에이전트 `codex-rescue`(sonnet, Bash 한 번으로 넘기기만), 내부 스킬 3개, 훅 3개(SessionStart, SessionEnd, 선택 Stop-gate). MCP 없음.
- `scripts/codex-companion.mjs` 가 `codex app-server`(JSON-RPC)를 상주 broker 로 띄우고 thread, turn, review 를 다룬다(`codex exec` 를 안 씀). Windows 는 named pipe, taskkill, git 은 `shell:false`.
- 샌드박스: `approvalPolicy: "never"`, 리뷰는 `read-only`, rescue 는 기본 `--write` 라 `workspace-write`. 별도 worktree 없이 실제 저장소와 사용자 인증(`~/.codex`)을 그대로 쓴다.
- 결과는 원문 그대로 사용자에게(요약, 수정 금지; 리뷰 뒤 고칠지 사용자에게 묻기). Codex 주장을 검증하는 절차는 없다.
- 리뷰: 네이티브 `review/start` 와 `adversarial-review`(XML 블록 프롬프트 `<role> <task> <operating_stance> <attack_surface> <finding_bar> <structured_output_contract>`, JSON 스키마 `verdict/summary/findings[file,line_start,line_end,confidence,recommendation]/next_steps`). diff 는 2파일, 256KB 이하면 프롬프트에 넣고 아니면 codex 가 직접 모은다.
- `--resume-last`, `codex resume <id>`, `/codex:transfer`(Claude jsonl 을 Codex 세션으로 가져옴). 작업 타임아웃은 없고 Stop-gate 만 15분. 비용 제어는 README 경고뿐.

## 우리와 다른 점
- 격리: 우리는 저장소별 권한 없는 uid, 빈 환경, 자격증명 사본, `guard.txt` 로 저장소를 못 건드리게 OS 수준에서 막는다. 그쪽은 codex 샌드박스에만 기댄다.
- 검증: 우리는 Claude 가 주장을 재현하고 사용자 결정을 나눈다. 그쪽은 원문 전달.
- 모델 계열: 우리는 agy(Gemini)와 codex. 그쪽은 Codex 만.
- 그쪽이 나은 점: Windows, macOS 지원, root 불필요, 바로 설치, 네이티브 리뷰, 세션 이어가기. 우리 delegate 는 Linux root 가 필요해 비프로그래머 동료에게 권하지 않는다.

## 가져올 만한 것
- 구조화 findings 스키마(파일, 줄 범위, 확신, 권고)를 `plugins/qwreey-delegate/skills/delegate/templates/tasks.md` 버그 사냥 템플릿의 출력 계약으로. 작음.
- XML 블록 프롬프트와 `finding_bar`, grounding 규칙(근거 없는 주장 금지)을 같은 템플릿에. 작음. 근거: 그 저장소 `skills/gpt-5-4-prompting/references/`(일부만 읽음).
- diff 를 프롬프트에 넣을 크기 경계를 SKILL.md 에. 작음.
- `attack_surface`, `operating_stance` 문구를 `plugins/qwreey-advisor/agents/reviewer.md` 보강 후보로(읽고 토론 뒤).
- 세션 이어가기는 "좁은 질문 하나" 원칙과 부딪혀 낮은 우선순위. Stop-gate 는 들이지 않음(턴마다 Codex 비용, advisor 와 이중 차단).

## 함께 설치하면
- 이름 공간과 상태 폴더가 달라 함께 설치는 된다. 겹침: 같은 Codex 한도를 쓰고 그쪽엔 동시 제한이 없다; "코덱스한테 물어봐" 에 `codex:codex-rescue`(proactive 설명)와 `qwreey-delegate:delegate` 가 함께 후보; rescue 의 `--write` 기본은 우리 "저장소에 그대로 넣지 않는다" 와 상충.
- 역할 나누기 권고: 격리와 검증은 delegate, 읽기 전용 네이티브 리뷰는 그 플러그인, Stop-gate 끔. Windows 동료 배포용으로는 그 플러그인이 현실적.

## 확인 안 한 것
- `workspace-write` 가 실제로 막는 범위(`.git/`, 저장소 밖, 네트워크).
- 우리 codex 어댑터에서 네이티브 리뷰(`codex exec review` 꼴)를 쓸 수 있는지.
- 상주 broker 가 `qwreey-proc-guard` 에 걸리는지.
- reviewer.md, tasks.md, 그쪽 프롬프트 references 전문.
