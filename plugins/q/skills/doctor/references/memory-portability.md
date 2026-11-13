# 10. 메모리 이식성 (MEM-*)

근거와 실측: `<doctor>/audit/23-memory-portability.md`. auto memory 는 이 컴퓨터의 `~/.claude/projects/<키>/memory/` 파일이라 저장소와 함께 다니지 않는다.
검사 구현은 `scripts/memory_checks.py`(scan.py 항목 10), 판정 규칙은 `scripts/memory_signals.py`(claude-doctor `lib/memory_signals.py` 의 사본).

| 코드 | 뜻 | 판정 |
|---|---|---|
| `MEM-ORPHAN` | 키가 가리키던 폴더가 없다. 그 메모리는 어느 세션에서도 읽히지 않는다 | 짝 후보가 맞는지 원문(경로 언급, 세션 cwd)으로 확인 → 사용자 동의 → `scripts/memory_move.py` |
| `MEM-REPO` | 경로·빌드 명령·"이 저장소에서"·규약 문구가 있어 저장소 지식으로 보인다 | 후보일 뿐이다. 원문을 읽고 분류(아래)한다. 점수 5 이상이 경고, 3~4 가 정보 |
| `MEM-SIZE` | MEMORY.md 가 앞 200줄 또는 25KB 한도에 근접(80%)·초과 | 초과분은 시작 때 읽히지 않는다. 한 줄 요약만 남기고 상세는 토픽 파일로, 낡은 줄은 지운다(동의 후) |

키 규칙(2.1.316 실측): 절대 경로에서 영숫자가 아닌 모든 문자를 `-` 로 바꾼다(`/tmp/a.dot_1` → `-tmp-a-dot-1`). 거꾸로는 모호해서 파일 시스템을 걸어 찾는다. 빈 `memory/` 폴더는 자동으로 생기므로 `.md` 가 있는 키만 센다.

## MEM-REPO 항목 분류 (모델이 판정)
| 분류 | 기준 | 처리 |
|---|---|---|
| 메모리 유지 | 사용자 성향·피드백, 이 기기·sandbox·개발 서버 환경 | 그대로 |
| 저장소로 | 그 저장소의 규약·결정·함정·빌드 방법·파일 소유 | CLAUDE.md / `.claude/rules` / docs 로 옮기는 안 → 승인 후 그 저장소에서. 상주 세션이 있으면 `.claude/handoff/memory-<repo>.md` |
| pack 으로 | 툴킷 일반 지식(Luau 함정, Roblox 동작) | luau-kb 같은 pack 에 제안 |
| 회사 지식 | 팀이 같이 알아야 할 것 | coderag team 계층(설계 중) |
| 낡음 | 날짜가 지났거나 저장소와 모순 | 지우자고 제안(삭제는 사용자) |

## 옮기기 (끊긴 메모리 잇기)
1. `MEM-ORPHAN` 의 짝 후보가 옳은지 사용자와 확인한다(같은 이름의 다른 프로젝트일 수 있다).
2. dry-run: `python3 -I ${CLAUDE_SKILL_DIR}/scripts/memory_move.py --from-key=<옛 키> --to <새 저장소 절대 경로>`
3. 계획(복사·건너뜀·다른 이름 복사)을 사용자에게 보이고 동의를 받는다. 동의 뒤에만 `--apply` 를 붙인다.
4. 원본은 남긴다. 옛 키 폴더 정리는 `HUMAN_TODO.md` 로(삭제 금지 원칙).
- 같은 이름·다른 내용은 덮어쓰지 않고 `<이름>.from-<옛 키 끝 8자>.md` 로 복사한다. MEMORY.md 는 새 쪽에 없는 줄만 붙인다.
- 상주 세션이 새 키를 쓰고 있으면 그 세션이 끝난 뒤에 한다.
