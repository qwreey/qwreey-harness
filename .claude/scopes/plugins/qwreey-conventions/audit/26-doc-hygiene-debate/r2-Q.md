# Q 2라운드

직접 잰 값(awk, 훅 재생이 아님):
- 곡선 따옴표 ‘’“”가 든 주석 줄: quad 1, stl-luau·table-sim·devplorer·coderag 0.
- 전각 문자 U+FF01–FF5E 가 든 주석 줄: 모든 저장소 0.
- 주석이 전부 ASCII 인 파일(주석 1줄 이상인 파일 기준): quad 1031/2797, stl-luau 792/1495, table-sim 10/139.
- luau-kb 플러그인은 `source: "./"` 라서 저장소 루트 전체가 실린다. decisions/ 도 함께 간다.

P 의 사실 오류: 1라운드 paths 에 `**/CLAUDE.md` 와 `**/.claude/rules/*.md` 가 이미 있었다(skills 로만 좁힌 적 없음).

1. 기호: 요청을 받아들이고 범위를 정한다.
   - 전역으로 잡는 것: 곡선 따옴표 ‘’“”(주석 안 예시 코드를 복사하면 문법 오류)와 전각 문자(IME 사고, ASCII 대체가 늘 있음). 둘 다 현재 0~1줄이라 잡음이 없다.
   - 나머지 기호(→ — · § … ─ ①)는 "문자 체계는 파일을 따른다" 로 잡는다. 주석이 5줄 이상이고 전부 ASCII 인 파일에 새로 들어올 때만 알린다(quad 37%, stl-luau 53% 의 파일이 해당). 이미 한국어나 기호가 쓰이는 파일에서는 통과한다.
   - 저장소마다 opt-out 을 일괄로 넣는 것은 "신호 없이 일괄로 하지 않는다" 와 부딪힌다. 파일 기준 조건이면 opt-out 이 필요 없다.
2. 변경 서술:
   - 입구 문서에서는 `previously|recently|현재 기준|지난\s?(주|번)|요즘|사실 정정|fact fix` 를 잡는다. `as of` 는 뒤에 버전이 오면 통과한다.
   - references 에서는 정정 배너만 잡는다. 공식 best-practices 가 "old patterns" 절을 권한다.
   - D-13 예시(`code-structure.md:19`), comments.md 의 "(2026-11-11)" 은 인정한다. 둘 다 이력이라 결정 문서로 옮긴다.
3. 판별 문장: `Test: if deleting a sentence would not change what the model does, it does not belong here.` "it is history" 는 군더더기 산문을 이력으로 잘못 분류한다.
4. "Move, do not delete" 를 받는다. 다만 옮길 곳은 이미 있는 곳(원장, decisions, 커밋 메시지)이어야 하고, 이력을 담으려고 새 파일을 만들지 않는다. 기본 목적지는 커밋 메시지다.
5. 원장 id: 훅은 같은 줄에 `\S+\.md` 가 있으면 통과시킨다(파일 시스템 확인 없음, 결정적이고 쌈). 규칙 문장에는 "그 파일이 문서와 함께 배포되어야 한다(같은 스킬이나 플러그인 루트)" 는 조건을 둔다.
6. 새 파일 언어: 저장소 `comment_language` → 같은 디렉터리 형제 파일 다수(최대 20개 표본) → 없으면 알리지 않는다. P 의 접수 단계(/q:start·intake 가 묻기)를 쓰되, 사용자에게 제안한다.

최종 문안의 바뀐 줄(1라운드 대비):
```diff
 # model-facing-docs.md
-A model reads these files to act. Keep a line only if removing it would change what the model does.
+A model reads these files to act. Test: if deleting a sentence would not change what the model does, it does not belong here.
-- Rewrite time-relative words ("currently", "as of", "new", "last week") as plain present-tense facts.
+- Rewrite change narration ("previously", "recently", "as of" without a version, "last week") as the current fact.
+- Move, do not delete: put history in an existing ledger or decisions file, else the commit message. Do not create a file only to hold it.
+- A ledger or decision id stays only on a line that names its file, and that file must ship with the doc (same skill or plugin root).
+- Entry docs: dates; `audit/`, `session/`, `round N`; decision phrases; measurement tags; change narration; an id with no `\S+\.md` on the line.
+- `skills/**/references/*.md`: decision phrases, `round N`, `audit/\d+ §`, measurement tags, correction banners. Dates, ids, "previously" pass.
 # comments.md
+- No curly quotes (‘ ’ “ ”) or fullwidth forms (U+FF01-FF5E) in comments; use ASCII.
+- Characters follow the file: in a file whose comments are all ASCII, keep new comments ASCII (`->`, `-`, `,`). Elsewhere → — · § … and dividers are fine.
+- ...in a new file, the repo's `comment_language`, else the majority in sibling files; with neither, no check. Korean is a normal comment language.
 # hook additions
+ quotes_fullwidth: `[‘’“”！-～]` in added comment lines, always.
+ typography: `[‐-‧←-⇿①-⓿─-▟§·]` in added comment lines, only if the file had >=5 comment lines and all were ASCII before the edit.
```
