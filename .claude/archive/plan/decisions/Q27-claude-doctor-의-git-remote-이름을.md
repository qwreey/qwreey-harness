---
format: 1
title: 올릴 저장소 이름을 뭘로 할까? (remote 는 origin)
description: 올릴 저장소 이름을 뭘로 할까? (remote 는 origin) 답 a) qwreey-harness
status: archived; answered a) qwreey-harness
id: Q27
urgency: soon
blocks: S3 main push
recommended: a
created: 2026-11-17T04:42:41.757Z
answered: 2026-11-17T05:11:53.075Z
answer: a
---

# Q27. 올릴 저장소 이름을 뭘로 할까? (remote 는 origin)

## 맥락

- 사용자 지적: `claude-doctor` 는 doctor 에 눈이 감. `brew doctor`, `/doctor`, 이 저장소의 `/q:doctor` 처럼 진단 도구로 읽히지만, 실제로는 하네스 정본과 플러그인 모음
- 플러그인은 이미 `qwreey-*` 꼴로 이름이 붙어 있음
- 이름을 바꾸면 경로가 들어간 곳(README, `home/.claude/harness.env`, settings-migrations, statusline)을 고치는 커밋 하나가 필요. 공개 전이면 지금 바꾸든 나중에 바꾸든 비용이 같음
- 마켓 이름 `claude-doctor-market` 은 따로 감. 바꾸면 설치된 플러그인을 모두 다시 설치해야 하니, 바꾼다면 동료가 설치하기 전이 가장 쌈(따로 정함)
- remote 는 origin(원격 하나, 코드가 이름에 기대지 않음)

## 선택지

- a) qwreey-harness
  플러그인 이름 qwreey-* 와 같은 줄이고, 하네스라는 내용이 드러남. claude- 로 시작하지 않아 공식 저장소로 오해받지 않음
- b) claude-doctor 유지
  고칠 것이 없음. 대신 진단 도구로 읽히는 문제가 남음
- c) 후보를 더 모아 토론에 붙이기
  예: qwreey-kit, qwreey-claude, claude-harness. 찬반 토론 뒤 고름(서브에이전트 2개)

**권장 a) qwreey-harness**
이미 있는 qwreey-* 이름과 같은 줄이라 동료가 플러그인과 저장소를 한 묶음으로 알아봄. 내용을 그대로 말하는 이름이고, 바꾸는 비용은 커밋 하나

## 코멘트

- 2026-11-17T04:43:33.136Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침
  사용자 정정: 저장소 이름도 함께 묻는 것이었음
- 2026-11-17T04:45:19.389Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침
  사용자: doctor 라는 단어에 집중이 갈 것 같다
- 2026-11-17T05:11:31.249Z user: 추가적으로 보통 벤더 중립적으로 가고, 그 안에는 claude, agy, codex 등을 전부 쓸 수 있게 주거나 필요한 사람이 포팅해서 PR할 수 있게 해주거나 하는게 일반적인데. 지금 구조는 claude 만 담긴 함. 당장은 문제는 없지 않나 싶긴 한데. 벤더 중립적인 qwreey-harness 자체는 괜찮은것 같아. 여기에서 나온 아이디어들이 다른 하네스에서도 쓸만한게 있을 수도 있고. 각자 필요한 대로 흡수하면 되니까
- 2026-11-17T05:12:01.301Z agent: 동의해요. 이름은 벤더 중립으로 두고, 지금 내용이 Claude Code 플러그인뿐이라는 점은 README 첫머리에 한 줄로 밝히면 충분해 보여요(예: "지금은 Claude Code 용만 있음. 다른 하네스로 옮기는 PR 환영"). 구조를 미리 벤더별로 나눌 필요는 없어요. 실제로 다른 하네스용이 생길 때 그 옆에 폴더를 더하면 돼요. 원칙과 결정 기록(.claude/base)은 이미 벤더와 무관한 글이라, 다른 하네스에서 아이디어를 가져가기에도 좋아요. 결정은 a 그대로 둘게요.

## 답

a
