# 사용자에게 물을 것

## Q1. 스킬 모양과 이름
- (a) 새 스킬 `coderag:agent-records`, rule 도 `agent-records`. `docs-frontmatter` 는 지우고 키 참조는 그 스킬의 references 로. **추천**: 지금 쓰는 짧은 이름이 그대로라 claude-doctor 쪽은 접두어만 바뀌고, coderag 쪽 참조 다섯 곳 중 넷은 어차피 이번에 고친다.
- (b) 새 스킬 `coderag:records`(더 짧음). 고칠 곳은 (a) 와 같고 rule 이름·`rules_exclude` 값·주석도 바뀐다.
- (c) `coderag:docs-frontmatter` 를 그 이름 그대로 넓힘. 참조는 안 깨지지만 이름이 이제 선택이 된 부분을 가리키고, 닫기·archive 작업에서 덜 불린다.

## Q2. 갈음을 쓸 때의 표기
- (a) `status: superseded by <경로>` 한 줄. `superseded_by:` 키는 읽기만. **추천**: frontmatter 없는 문서에서도 되고, landed·rejected 와 같은 문법이며, records_check 와 coderag 가 이미 둘 다 읽는다.
- (b) `status: superseded` + `superseded_by: <경로>` 키. frontmatter 가 있어야만 쓸 수 있다.

## Q3. coderag 자체 rule 이 실리는 범위
- (a) coderag 플러그인을 켠 모든 저장소(지금 qwreey-conventions rule 과 같은 범위). 저장소별 끄기는 `[rules] exclude = ["agent-records"]`. **추천**: 대부분의 저장소에 `coderag.toml` 이 없어서 (b) 면 지금 받던 rule 이 거기서 사라진다.
- (b) 프로젝트 `coderag.toml` 이 켠 저장소만(팩 rule 과 같은 규칙).

## Q4. Codex·agy 에 같은 규칙 주기
- (a) 지금은 위임 템플릿 `AGENTS.md.template` 에 rule 본문을 손으로 넣고, coderag `agents-md` generator(M7)가 생기면 rule 파일에서 생성한 마커 블록으로 바꾼다. **추천**: codex·agy 는 지금 위임으로만 돌고, 원천이 rule 파일 하나로 남는다.
- (b) M7 까지 기다린다(그 사이 codex·agy 는 기록 규칙을 모른다).
- (c) (a) 에 더해 사용자 파일 `~/.codex/AGENTS.md`·`~/.gemini/config/AGENTS.md` 에도 지금 넣는다(사용자 파일이라 처음 쓸 때 동의 필요).
