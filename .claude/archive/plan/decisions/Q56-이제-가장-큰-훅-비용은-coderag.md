---
format: 1
title: 이제 가장 큰 훅 비용은 coderag 래퍼(훅 하나에 약 9 ms). coderag 래퍼를 빠르게 고칠까?
description: 이제 가장 큰 훅 비용은 coderag 래퍼(훅 하나에 약 9 ms). coderag 래퍼를 빠르게 고칠까? 답 a) 래퍼를 bash 내장만 쓰게 고치고, PATH 에서 다른 래퍼가 아닌 바이너리를 고르게
status: archived; answered a) 래퍼를 bash 내장만 쓰게 고치고, PATH 에서 다른 래퍼가 아닌 바이너리를 고르게
id: Q56
urgency: later
blocks: 없음
recommended: a
created: 2026-11-22T05:57:57.051Z
answered: 2026-11-22T06:00:42.993Z
answer: a
---

# Q56. 이제 가장 큰 훅 비용은 coderag 래퍼(훅 하나에 약 9 ms). coderag 래퍼를 빠르게 고칠까?

## 맥락

reload 뒤 다시 잰 값(CPU 합, p50): Bash 앞 32 ms, 뒤 25 ms, Read 뒤 23 ms, Edit 뒤 46 ms. 우리 훅은 하나에 2~5 ms다. coderag 훅은 하나에 약 9 ms이고, 도구 한 번에 2~3 개가 돈다.

원인:
- 설치본(캐시 0.23.3)의 `bin/coderag` 은 bash 래퍼다. 캐시 폴더에는 `target/` 이 없어서 PATH 를 훑는다. 그러다 PATH 에 있는 coderag 저장소의 래퍼(`harness/claude/bin/coderag`, 또 bash)를 찾고, 그것이 바이너리를 부른다. 래퍼 둘이 `readlink`·`cd`·`dirname` 으로 프로세스를 여러 번 띄운다.
- 실측(벽시계, 20회 평균): 래퍼로 16.1 ms, 바이너리를 바로 부르면 1.2 ms, `bash -c true` 는 1.9 ms.

고칠 곳은 coderag 저장소다(고치고 push 해도 되는 곳). 설치본은 coderag 판을 올려야 바뀐다.

## 선택지

- a) 래퍼를 bash 내장만 쓰게 고치고, PATH 에서 다른 래퍼가 아닌 바이너리를 고르게
  훅 하나 약 9 ms -> 2~3 ms 예상. 동료 설치본에도 같이 간다. coderag 판 올림과 plugin update 가 든다
- b) 이 기기만: 설정 env 에 CODERAG_BIN 을 둔다
  코드는 그대로. 래퍼 하나는 남아 절반쯤 줄고, 설정은 사용자가 바꾼다
- c) 그대로 둔다
  벽시계로는 훅이 나란히 돌아 도구 한 번에 약 10 ms 다

**권장 a) 래퍼를 bash 내장만 쓰게 고치고, PATH 에서 다른 래퍼가 아닌 바이너리를 고르게**
남은 비용의 가장 큰 덩이이고, 동료 설치본도 같은 래퍼를 쓴다

## 답

a
