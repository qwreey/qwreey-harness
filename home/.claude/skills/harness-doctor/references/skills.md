# 3. 스킬 상태

## 목차
- [3. 스킬 상태](#3-스킬-상태)
- [부작용 판단](#부작용-판단)
- [사본 스킬](#사본-스킬)

## 3. 스킬 상태

**기준** (`claude-doctor/audit/01-official-docs.md` §2·§7)
- `name`: 소문자, 숫자, 하이픈만 써서 64자 이내로 짓는다. 디렉터리 이름과 같게 둔다. `claude`, `anthropic`은 예약어다.
- `description`과 `when_to_use`를 합쳐 1,536자를 넘으면 잘린다. "무엇을 하나 + 언제 쓰나"를 함께 적는다.
- SKILL.md 본문은 500줄 이하로 둔다.
- reference는 SKILL.md에서 1단계로만 연결한다. 더 깊으면 일부만 읽힐 수 있다.
- 100줄이 넘는 reference는 맨 위에 목차를 둔다.
- 부작용이 있는 절차는 `disable-model-invocation: true`로 사용자 호출 전용으로 만든다. 그러면 스킬 목록에서도 빠져 description 비용이 들지 않는다.

| 코드 | 뜻 |
|---|---|
| `SKILL-PARSE` | frontmatter가 없거나 파싱되지 않는다 |
| `SKILL-NAME` | 이름 규칙 위반, 예약어, 디렉터리 이름과 다름 |
| `SKILL-DESC` | description이 없거나 1,536자를 넘는다 |
| `SKILL-KEY` | 알려지지 않은 frontmatter 키(정보). 오타일 수 있다 |
| `SKILL-LINES` | SKILL.md가 500줄을 넘는다 |
| `SKILL-NEST` | reference가 하위 폴더에 있거나, reference가 다른 reference를 가리킨다(2단계) |
| `SKILL-TOC` | 100줄이 넘는 reference에 목차가 없다 |
| `SKILL-ORPHAN` | SKILL.md에서 닿지 않는 .md가 있다(정보) |
| `SKILL-SIDEFX` | 부작용 낌새가 있는데 `disable-model-invocation`이 없다 |
| `SKILL-UNMANAGED` | `~/.claude/skills`에 있지만 정본이나 MANIFEST 링크에 없다(`--user`) |
| `LINK-TARGET` | MANIFEST의 링크 대상이 없다(`--user`) |

scan의 frontmatter 파서는 간이 YAML이다. 판정이 미심쩍으면 공식 검사기로 교차 확인한다.
- `claude plugin validate <스킬 디렉터리의 상위>`
- 예: `claude plugin validate /code/Projects/stl-luau/.claude/skills`

**모델이 볼 것**
- description이 3인칭으로 "무엇 + 언제"를 담는지, 다른 스킬과 트리거가 겹치지 않는지 본다.
- 프로젝트 고유 절차가 conventions 산문으로만 있고 스킬이 없는 경우를 찾는다(`audit/03` §5). 예: 핸드오버 체크리스트, 감사 루프, 리뷰 라운드, 릴리스.
- 이 경우 스킬 후보로 제안한다.

**고치는 법**
- `SKILL-LINES`: 절차와 판단 기준만 SKILL.md에 남기고, 상세는 `references/<주제>.md`로 나눈다. SKILL.md에서 각 파일을 직접 링크한다.
- `SKILL-NEST`: 2단계로 걸린 파일을 SKILL.md에서 바로 가리키게 한다. 하위 폴더는 평평하게 편다(파일 이동은 승인 뒤).
- `SKILL-TOC`: 파일 맨 위에 `## 목차`와 절 앵커 링크 목록을 넣는다.
- `SKILL-DESC`: 트리거에 필요 없는 배경 설명을 본문으로 옮긴다.

## 부작용 판단

`SKILL-SIDEFX`는 키워드 낌새일 뿐이다. 다음 키워드에 걸린다.
- git 명령: `git commit`, `push`, `worktree add/remove`
- 행동 동사: "커밋한다", "삭제한다"
- 그 밖: `setpriv`, `choom -n`, `studio-sync`, `publish.py`

판정 기준은 "모델이 스스로 이 스킬을 따라도 괜찮은가"다.
- **사용자 전용으로 둘 것**: 스킬을 따르면 되돌리기 어렵거나 저장소 밖에 흔적이 남는 경우다.
  - 커밋, push, 게시·배포·업로드, Studio 쓰기
  - worktree나 브랜치 생성·삭제
  - 다른 uid로 외부 모델 실행, 서브에이전트 다수나 돌연변이 같은 큰 비용
- **모델 호출을 허용해도 될 것**: "커밋 전에 이 검사를 돌린다"처럼 부작용을 언급만 하는 경우와 읽기 전용 절차다.
- 판단이 갈리는 스킬은 사용자에게 묻는다. 예: review-round(`audit/07` §7의 4번 미결), delegate-agy.

고치는 법: frontmatter에 `disable-model-invocation: true` 한 줄을 넣는다.
그 스킬을 자동 호출에 기대던 문서가 있으면("~할 때 스킬이 뜬다") 그 문장도 함께 고친다.

## 사본 스킬

같은 이름의 스킬이 다른 저장소나 사용자 레벨에 있으면 `DRIFT-SKILLCOPY`(6번 항목)가 함께 나온다.
- 사본 쪽 형식 문제(줄 수, 목차)는 사본에서 고치지 않는다. 원본을 고쳐서 다시 복사하는 안을 낸다.
  - 예: table-sim `quad-ui-dev`의 원본은 `quad/docs/skills/quad-ui-dev/SKILL.md`다.
- 원본 저장소에 실행 중인 세션이 있으면 그 저장소 앞으로 인계 문서를 만든다.
