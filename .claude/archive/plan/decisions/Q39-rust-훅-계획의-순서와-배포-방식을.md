---
format: 1
title: Rust 훅 계획의 순서와 배포 방식을 어떻게 정할까? (debate 종합)
description: "Rust 훅 계획의 순서와 배포 방식을 어떻게 정할까? (debate 종합) 답 a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로"
status: "archived; answered a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로"
id: Q39
urgency: soon
blocks: Rust 훅 계획 확정, 0단계 시작
recommended: a
created: 2026-11-19T09:47:18.618Z
answered: 2026-11-20T02:42:25.122Z
answer: a
---

# Q39. Rust 훅 계획의 순서와 배포 방식을 어떻게 정할까? (debate 종합)

## 맥락

debate: P "이 기기 먼저" 대 Q "배포 먼저", opus 2개, 1회전. 사실은 공식 문서로 확인함.

두 편이 같이 확인한 것
- 맨 위 `bin/` 금지: Bash PATH 에 오르고 claude.ai, Cowork 가 설치를 거부함. -> `native/`
- 바이너리가 없으면 그 훅은 "막지 않는 오류"가 되어 진행됨. 막는 훅도 열림. `onFailure: block` 이면 그 도구가 전부 막힘.
- Windows 에서 셸 없이 실행하려면 실제 `.exe` 여야 함. 확장자 없이 찾아 주는지는 미확인.
- proc-guard 시범은 Windows 를 거치지 않음.
- 바이트 대조 장치가 아직 없고, 시험 도구 두 곳에 python 꼴이 박혀 있음.

갈린 곳
- 순서: P 는 시범 다음에 배포, Q 는 빈 바이너리로 전체 배포 경로(CI -> release -> 설치본, Windows/macOS 실기기)를 먼저 통과.
- 옮기는 동안: P 는 python 으로 돌아가는 런처, Q 는 바로 실행만 하고 main 은 이 기기 전용.
- 배포: Q 는 OS별 배포 ref(그 OS 바이너리와 그 OS 용 hooks.json). `#<ref>` 설치는 확인 전.

## 선택지

- a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로
  proc-guard 를 이 기기에서 옮기면서 빈 바이너리로 배포 경로를 실기기에서 확인. 0단계가 끝나기 전에는 동료에게 Rust 훅을 내지 않음. 런처가 없어 셀 비용과 PowerShell 위험이 없음
- b) P 그대로: 시범 먼저, python 런처, 배포는 그 뒤
  가장 빨리 실사용에 넣음. 런처가 동료 설치본을 python 으로 지켜 줌. 대신 +1.6 ms, 셀, PowerShell 전례
- c) Q 그대로: 0단계 전체를 끝내고 이식 시작
  배포가 정해진 뒤에만 코드를 옮김. 재작업 가장 적음. 대신 실기기와 CI 를 기다리는 동안 이득이 없음

**권장 a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로**
하위 명령 꼴은 배포와 상관없다는 데 두 편이 동의해서 나란히 해도 버릴 일이 적음. 동료 설치가 아직 없으니 main 을 이 기기 전용으로 두면 런처가 필요 없음. 배포 ref 는 Windows .exe 문제까지 같이 풀지만 #ref 설치가 확인 전이라 0단계에서 확인

## 답

a
