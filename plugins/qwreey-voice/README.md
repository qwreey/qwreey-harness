# qwreey-voice

이 플러그인을 켜면 Claude 가 사용자에게 말하고 일을 넘기는 방법이 달라진다. 시키는 말 대신 하면 얻는 것과 미루면 생기는 일을 말하고, 통보 대신 고를 거리를 주고, 정할 일은 질문 꼴로 낸다. 글은 결론 먼저 짧게 쓴다. 코드, 커밋, 문서 같은 산출물은 바뀌지 않는다.

기본 글은 명령형 말이 부담스럽고 긴 글이 읽기 힘든 한 사람에게 맞춘 것이다. 사람마다 맞는 말이 다르니, 쓰면서 걸리는 줄을 자기 말로 고쳐 쓰는 것을 전제로 한다.

## 무엇이 달라지나
- 넘기기 전에 대신 할 수 있는 일은 Claude 가 대신 하고, 넘길 일은 명령을 통째로 적어 빠뜨릴 단계를 줄인다.
- "이 폴더를 지워야 합니다" 대신 "저장 공간이 모자라지지 않게, 편할 때 이 폴더를 치워 주세요" 처럼 말한다. 때는 사용자가 고른다.
- 할 수 있으면 방법이나 순서를 고르게 한다. 미뤄도 되는 일은 "무엇이 보이면 한다" 는 조건으로 적는다.
- 일을 작아 보이게 꾸미지 않고, 진짜 기한이나 막힌 일은 숨기지 않는다.
- 재촉, 반복 알림, 달래는 칭찬이 없다. 일이 끝나면 그것으로 무엇이 되었는지만 말한다.
- 건강, 진단, 약, 병원 이야기를 하지 않는다.

## 글 고치기
지침은 `context/ambient.md` 한 파일이고 한국어다. 줄을 고치면 다음 세션(또는 `/clear`, compact 뒤)부터 그 글이 실린다. 설치 방식이 캐시 사본이면 고친 뒤 `claude plugin update qwreey-voice@qwreey-harness` 가 필요하다.

## 비용
- 세션 시작마다 글 한 덩이(약 1,100자). 모델을 부르지 않는다.

## 요구 사항
- 세션 시작 훅이 `python3` 를 부른다. Linux, macOS, Windows(Python 3 설치 필요).

## 끄기
- 글만: `/plugin configure qwreey-voice@qwreey-harness` 에서 "대화 지침 싣기"를 끈다.
- 한 저장소에서만: 그 저장소 `.claude/harness.env` 에 `HARNESS_VOICE_AMBIENT=off`.
- 전부: `claude plugin disable qwreey-voice@qwreey-harness`.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-voice@qwreey-harness
```
