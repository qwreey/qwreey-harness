---
format: 1
title: 67. Rust 훅 백엔드 계획 debate 종합
description: Rust 훅 계획은 proc-guard 시범과 빈 바이너리로 배포 경로를 확인하는 0단계를 나란히 하고, 런처 없이 바이너리를 바로 실행하며, OS별 배포 ref 를 우선 후보로 둔다; 맨 위 bin/ 대신 native/, 바이트 대조 실행기가 먼저
---
# 67. Rust 훅 백엔드 계획 debate 종합

> Snapshot 2026-11-20. May differ from now; check current files and git log before relying on it.

P(이 기기 먼저: proc-guard 시범, 실사용, 그 뒤 배포)와 Q(배포 먼저: 빈 바이너리로 배포 경로 전체를 먼저 통과), opus 2개, 1회전, 종합은 메인 세션. 근거: `.claude/plan/rust-hook-backend.md`(5d552a1 판), `.claude/audit/66-hook-server-language/`, Claude Code 공식 문서(plugins components, hooks, marketplaces). 사용자(Q39): "a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로".

## Trigger
훅마다 python 을 띄우는 데 CPU 약 34 ms 가 들고(audit 66), 사용자가 python 의 유지보수성에 불만을 말해 Q38 b 로 "계획만 먼저 쓰고 debate 로 확정"하기로 했다. 계획 초안에서 바이너리 배포, Windows·macOS, 옮기는 순서가 열린 문제였다.

## Facts both sides confirmed
메인이 공식 문서 사본으로 다시 확인한 것만 적는다.
- 플러그인 맨 위 `bin/` 은 모델이 쓰는 Bash 의 PATH 에 오르고, claude.ai·Cowork 조직 배포는 맨 위 `bin/` 이 있는 플러그인을 설치하지 않는다(plugins components 문서).
- 명령 훅이 시작하지 못하면 막지 않는 오류가 되어 도구는 진행된다. 막는 훅도 열린다. `onFailure: "block"`(v2.1.295 이상, 이 기기 2.1.316)을 달면 반대로 그 도구가 모두 막힌다(hooks 문서).
- Windows 에서 셸 없이(`command` + `args`) 실행하려면 `command` 가 실제 `.exe` 여야 한다. 확장자 없는 경로를 찾아 주는지는 문서에 없다.
- Git Bash 가 없는 Windows 에서 셸 형식 PreToolUse 훅이 실패하면 도구 호출이 막힌다. 지금 python 훅에도 있는 위험이다.
- proc-guard 시범은 Windows 를 거치지 않는다(heavy-proc-guard 는 Linux 에서만 막는다).
- 바이트 대조 장치가 없다. 지금 시험은 성질(태그, 포함 여부)만 보고, `hook_sandbox.py` 와 `tools/tests/test-hook-commands.py` 의 `FORM` 에 python 실행 꼴이 박혀 있다.
- 바이너리는 0.4~0.6 MB(strip 0.37 MB)라 플러그인마다 하나여도 감당할 만하다(audit 66).
- 마켓 소스 종류에 `archive`(zip + sha256), `npm`, `command` 가 있다(marketplaces 문서).
- 이 기기에는 Linux 대상만 있다. macOS·Windows 빌드는 CI 몫이다.

## Accepted by both
- 플러그인마다 바이너리 하나, Cargo 워크스페이스는 이 저장소, 데몬은 conventions 차례에서 재고 정한다.
- 하위 명령 꼴(`<바이너리> hook <이벤트>`)은 배포 방식과 상관없어서, 옮기는 일과 배포를 정하는 일을 나란히 해도 다시 고칠 것이 적다.

## Disagreements
| Issue | P | Q | Chosen and why |
|---|---|---|---|
| 순서 | 시범 -> 실사용 -> 배포 결정 | 0단계: 빈 바이너리로 CI -> release -> 설치본, Windows·macOS 실기기까지 먼저, 시범은 나란히 | 합침(사용자 a). 나란히 하고, 0단계가 끝나기 전에는 동료에게 Rust 훅을 내지 않는다 |
| 옮기는 동안 실행 | python 으로 돌아가는 런처(바이너리 없으면 python, +1.6 ms) | 바로 실행만, main 은 이 기기 전용, 동료는 배포 ref 에서 받음 | Q. 런처는 셸을 다시 띄우고 PowerShell 에서 깨진 전례가 있다. 동료 설치가 아직 없다 |
| 배포 방식 | 선택지만 두고 시범 뒤로 | OS별 배포 ref(그 OS 바이너리와 그 OS 용 hooks.json) | Q 를 우선 후보로. `.exe` 문제도 같이 풀린다. `#<ref>` 설치는 확인 전이라 0단계에서 확인 |
| 바이너리 없을 때 막는 훅 | 미정 | 진행(오늘과 같음) 대 block | 사용자 결정(아직 답 없음) |

## Alternatives
| Option | Pros | Cons | Raised by |
|---|---|---|---|
| 플러그인 폴더에 바이너리 커밋 | 설치만 하면 돈다 | git 기록이 커지고 한 경로에서 OS 를 고를 수 없다 | 현재 초안 |
| 첫 실행 때 release 에서 받기 | 문서가 권하는 꼴(DATA 폴더), macOS 격리 속성이 붙지 않는다 | 런처, 네트워크, 비공개면 인증, 세션 여럿의 경합 | P, Q |
| 마켓 `archive` 소스 | sha256 으로 고정 | OS 를 고르는 필드가 없어 런처가 필요 | Q |
| npm optionalDependencies(esbuild 방식) | OS 고르기를 npm 이 한다 | 동료 기기에 npm 이 있어야 한다 | Q |
| OS별 배포 ref | 바로 실행, 받는 양이 가장 작다 | CI 가 ref 3개를 만들고 동료가 OS 를 한 번 고른다 | Q |

## Proposed wording
`.claude/plan/rust-hook-backend.md` 에 반영했다(같은 커밋): 순서에 0단계와 시범을 나란히, `bin/` 을 `native/` 로, 바로 실행과 main 은 이 기기 전용, OS별 ref 를 우선 후보로, workspace-gate 를 앞으로.

## Not accepted
- P: python 으로 돌아가는 런처. 셸을 다시 띄워 이득을 깎고, PowerShell 에서 깨진 전례가 있다. 동료 설치가 없는 지금은 필요 없다.
- Q: 0단계 전체를 끝낸 뒤에 이식 시작. 실기기와 CI 를 기다리는 동안 이 기기의 CPU 이득이 없다.

## Fix regardless
- 계획의 `bin/` 을 `native/` 로.
- 시험 도구 두 곳이 실행 형식(`command` + `args`)을 받게 하고, python 과 바이너리의 출력을 바이트로 비교하는 대조 실행기를 0단계에 넣는다.
- 시범 순서에서 workspace-gate 를 앞으로. 모든 OS 에서 돌고 막는 훅이라 Windows 확인에 맞다(Q).

## For the user
Q39 외에는 아직 답이 없다. 계획의 열린 문제로 옮겼다.
1. 동료가 claude.ai 조직 배포나 Cowork 를 쓰나, 마켓 CLI 로만 설치하나.
2. 동료 OS 와 아키텍처(macOS, ARM 이 있나).
3. 회사 Windows 가 사용자 폴더의 서명 없는 exe 를 막나(AppLocker, Defender), 실기기에서 시험 exe 를 띄울 수 있나.
4. 막는 훅의 바이너리가 없을 때: 진행(오늘과 같음) 대 `onFailure: block`.
5. 배포 ref: 이 저장소의 브랜치 대 별도 저장소(Q19 공개 시점과 함께).
6. macOS·Windows CI 러너 비용.
7. 시범 바이너리를 실사용 주간(11-23~)에 이 기기에서 켜 둬도 되나.
- 이름(`native/`, 환경 변수)은 제안이다.

## Next
1. 0단계: 대조 실행기와 시험 도구의 실행 형식, Cargo 워크스페이스와 공통 crate.
2. proc-guard 시범을 이 기기에서(main 은 이 기기 전용).
3. 빈 바이너리로 CI -> release -> OS별 ref -> 설치본을 확인(`#<ref>` 설치, Windows `.exe`, macOS 격리). 질문 1~6 의 답이 필요하다.
