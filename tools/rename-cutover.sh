#!/usr/bin/env bash
# 저장소 폴더와 마켓 이름 바꾸기 전환: claude-doctor -> qwreey-harness, claude-doctor-market -> qwreey-harness.
#
#   bash rename-cutover.sh            검사하고 할 일만 단계마다 보인다(아무것도 바꾸지 않음)
#   bash rename-cutover.sh --apply    실제로 한다
#
# 이 스크립트는 전환 브랜치에 있고 main 에는 병합 뒤에야 생기므로, 자기 위치가 아니라 아래 경로로 움직인다.
#   main 에서 부를 때: git -C /code/Projects/claude-doctor show rename-qwreey-harness:tools/rename-cutover.sh > ~/rename-cutover.sh
#   (/tmp 에 두지 않는다: 다시 돌리기 전에 /tmp 를 비우면 스크립트도 사라진다. 다시 돌릴 때 쓰는 상태는 설정 폴더에 둔다)
# 모든 Claude Code 세션을 닫은 뒤에만 --apply 한다: 살아 있는 세션은 훅을 옛 폴더의 plugins/ 에서 부르고,
#   마켓 이름이 바뀌면 그 세션이 다시 읽을 때 등록과 어긋난다.
#
# 단계(--apply 는 이 순서로, 다시 돌리면 끝난 단계는 건너뛴다)
#   a  전환 브랜치를 main 에 병합(앞서 갈 수 있으면 fast-forward, main 이 움직였으면 merge, 충돌이면 중단)
#   b  qwreey-conventions 의 reply_language.py 껍데기를 git rm 하고 그 HUMAN_TODO 줄과 함께 커밋.
#      커밋까지 못 가면 HEAD 로 되돌린다(더러운 트리가 다시 돌리기를 막지 않게)
#   c  ~/.claude/plugins/data/<p>-claude-doctor-market -> <p>-qwreey-harness (마켓 remove 가 옛 이름 폴더를 지우기 전에)
#   d  저장소 폴더 mv
#   e  ~/.claude/projects 와 session-log 저장소의 경로 이름 폴더 mv(project.json 도 새 경로로)
#   f  새 위치에서 tools/home-sync.sh diff, apply (마이그레이션 0010 이 settings 의 마켓 선언과 플러그인 키를 옮긴다)
#   g  settings.json, installed_plugins.json, known_marketplaces.json 백업, enabledPlugins 와 pluginConfigs 의
#      새 마켓 항목 스냅숏, claude plugin marketplace remove 옛 마켓, 새 마켓 add, 옛 마켓에 설치돼 있던 플러그인을
#      새 이름으로 install, install 이 바꾼 새 마켓 항목을 스냅숏 값으로 되돌림
#   h  사용자에게 남는 일: ~/.coderag/coderag.toml 팩 경로(백업 뒤 고침), 지울 옛 폴더와 링크, 형제 저장소의 coderag adapt
#
# 실측한 CLI 동작(2.1.316, 버리는 CLAUDE_CONFIG_DIR 와 로컬 디렉터리 마켓)이 g 의 순서와 되돌리기를 정한다:
#   marketplace remove <m>  그 마켓의 설치본을 모두 uninstall: enabledPlugins, pluginConfigs 의 <p>@<m> 키,
#                           extraKnownMarketplaces[<m>], plugins/data/<p>-<m> 를 지운다(plugins/cache/<m> 는 남김).
#                           다른 마켓의 키와 데이터 폴더는 건드리지 않는다
#   marketplace add <dir>   known_marketplaces 와 extraKnownMarketplaces[<이름>] 를 쓴다(같은 값이 있으면 그대로)
#   plugin install --scope user  enabledPlugins[<id>] 를 덮는다(defaultEnabled false 면 false, 아니면 true,
#                           이미 설치돼 있어도, 사용자가 끈 false 도). pluginConfigs 와 데이터 폴더는 그대로
#   어느 명령도 끝난 뒤 claude 프로세스(daemon 등)를 남기지 않았다
#
# 경로는 환경 변수로 바꿀 수 있다(리허설과 테스트용): RENAME_OLD_ROOT, RENAME_NEW_ROOT, RENAME_BRANCH,
#   CLAUDE_CONFIG_DIR, HOME, XDG_DATA_HOME, SESSION_LOG_HOME, CODERAG_HOME.
#   RENAME_ALLOW_LIVE=1 은 실행 중인 claude 검사를 건너뛴다. 기본 경로(실제 저장소)에서는 받지 않는다.
set -euo pipefail

DEFAULT_OLD=/code/Projects/claude-doctor
OLD_ROOT=${RENAME_OLD_ROOT:-$DEFAULT_OLD}
NEW_ROOT=${RENAME_NEW_ROOT:-$(dirname "$OLD_ROOT")/qwreey-harness}
BRANCH=${RENAME_BRANCH:-rename-qwreey-harness}
CFG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
# Claude Code 는 CLAUDE_CONFIG_DIR 가 있으면 전역 설정 파일도 그 안에 둔다(실측)
CLAUDE_JSON=${CLAUDE_CONFIG_DIR:+$CFG/.claude.json}
CLAUDE_JSON=${CLAUDE_JSON:-$HOME/.claude.json}
SL_HOME=${SESSION_LOG_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/session-log}
CODERAG_CFG=${CODERAG_HOME:-$HOME/.coderag}/coderag.toml
OLD_M=claude-doctor-market
NEW_M=qwreey-harness
MIG_ID=0010-qwreey-harness-market
SHIM=plugins/qwreey-conventions/hooks/reply_language.py
B_PATHS=("$SHIM" HUMAN_TODO.md plugins/qwreey-conventions/CLAUDE.md)   # b 가 바꾸는 파일 전부
STATE=$CFG/.rename-cutover-plugins   # g 가 옛 마켓을 지우기 전에 적어 둔 설치 목록(다시 돌릴 때 쓴다)
# g 의 첫 --apply 가 install 전에 적어 둔 enabledPlugins, pluginConfigs 의 새 마켓 항목. $STATE 가 있는 동안 기준이다:
#   다시 돌릴 때 settings 를 새로 읽으면 앞선 실행의 install 이 바꾼 값이 기준이 된다
SNAP=$STATE.settings.json
B_MARK=$CFG/.rename-cutover-b        # b 가 도는 동안만 있다. 있으면 더러운 트리는 b 가 남긴 것이다
STAMP=$(date +%Y%m%d%H%M%S)

APPLY=0
case "${1:-}" in
  --apply) APPLY=1 ;;
  "") ;;
  *) echo "usage: $0 [--apply]" >&2; exit 2 ;;
esac

say() { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
die() { printf 'rename-cutover: 중단: %s\n' "$*" >&2; exit 1; }
# 실행하거나(--apply) 할 명령만 보인다
run() {
  if ((APPLY)); then printf '  $ %s\n' "$*"; "$@"; else printf '  (할 일) %s\n' "$*"; fi
}
# 파일을 <f>.bak-<시각> 으로. home-sync 의 settings 백업도 같은 꼴이라 같은 초에 겹치면 덮지 않고 뒤에 번호를 붙인다
backup() {
  local f=$1 t
  [[ -f "$f" ]] || return 0
  t=$f.bak-$(date +%Y%m%d%H%M%S)
  local n=1 base=$t
  while [[ -e "$t" ]]; do t=$base.$n; n=$((n + 1)); done
  cp -p "$f" "$t"
  say "  백업 $t"
}
# Claude Code 의 경로 이름 폴더 키: 영숫자 밖의 글자를 모두 - 로
key_of() { local p=$1; printf '%s' "${p//[^A-Za-z0-9]/-}"; }
OLD_KEY=$(key_of "$OLD_ROOT")
NEW_KEY=$(key_of "$NEW_ROOT")

# ---------------------------------------------------------------- 사전 검사
PROBLEMS=()
problem() { PROBLEMS+=("$*"); }

# 사용자 본인으로: 설정 폴더 주인과 같은 uid (sudo 로 남의 홈을 건드리지 않게)
[[ -d "$CFG" ]] || die "Claude 설정 폴더가 없다: $CFG"
[[ "$(stat -c %u "$CFG")" == "$(id -u)" ]] || problem "설정 폴더 $CFG 의 주인이 지금 사용자(uid $(id -u))가 아니다. 그 사용자로 돌린다"
# g 가 부르는 CLI. d, e, f 가 폴더와 설정을 옮긴 뒤에야 없다는 것을 알면 반쯤 옮긴 채로 멈춘다
command -v claude >/dev/null || problem "claude 가 PATH 에 없다(g 단계가 marketplace, install 을 부른다). claude 가 잡히는 셸에서 돌린다"

# 실행 중인 Claude Code 없음. -f 는 이 스크립트 자신의 명령 줄과도 맞으므로 프로세스 이름(-x)으로만 본다
if [[ "${RENAME_ALLOW_LIVE:-}" == 1 && "$OLD_ROOT" != "$DEFAULT_OLD" ]]; then
  say "(리허설: 실행 중인 claude 검사를 건너뛴다)"
elif live=$(pgrep -x claude -a 2>/dev/null); then
  # transient daemon 은 띄운 세션의 pid 를 --spawned-by 에 적는다. 그 pid 가 없으면 닫힌 세션이 남긴 것이다
  hint=""
  while read -r pid rest; do
    if [[ "$rest" == *"daemon run --origin transient"* && "$rest" =~ \"pid\":([0-9]+) ]] && ! kill -0 "${BASH_REMATCH[1]}" 2>/dev/null; then
      hint+="    pid $pid: 띄운 세션(pid ${BASH_REMATCH[1]})이 이미 없는 transient daemon 이다. claude daemon stop --any (안 되면 kill $pid) 로 끝낸다. 그 아래 bg-spare, bg-pty-host 도 같이 끝난다"$'\n'
    fi
  done <<<"$live"
  problem "실행 중인 claude 프로세스가 있다(세션, daemon, bg-spare 모두). 모든 세션을 닫고, 남은 것은 끝나기를 기다리거나 kill 한다:
$(printf '%s\n' "$live" | cut -c1-150 | sed 's/^/    /')${hint:+
$hint}"
fi

# 어느 단계에 있나: 옮기기 전(옛 폴더만), 옮긴 뒤(새 폴더만)
if [[ -d "$OLD_ROOT" && -e "$NEW_ROOT" ]]; then
  die "옛 폴더 $OLD_ROOT 와 새 폴더 $NEW_ROOT 가 둘 다 있다. 어느 쪽이 정본인지 사용자가 정한다"
elif [[ -d "$OLD_ROOT" ]]; then
  PHASE=before; REPO=$OLD_ROOT
elif [[ -d "$NEW_ROOT" ]]; then
  PHASE=after; REPO=$NEW_ROOT
else
  die "$OLD_ROOT 도 $NEW_ROOT 도 없다"
fi
g() { git -C "$REPO" "$@"; }
[[ "$(g rev-parse --show-toplevel 2>/dev/null)" == "$(cd "$REPO" && pwd -P)" ]] || die "$REPO 가 git 저장소 최상위가 아니다"
say "# 저장소 $REPO (단계: $([[ $PHASE == before ]] && echo '폴더 옮기기 전' || echo '폴더 옮긴 뒤, 이어서 하기'))"
say "# 설정 $CFG, session-log $SL_HOME, 브랜치 $BRANCH"

[[ "$(g rev-parse --abbrev-ref HEAD)" == main ]] || problem "main 이 체크아웃돼 있지 않다($(g rev-parse --abbrev-ref HEAD))"
# 앞선 실행이 b 도중에 끊겼으면(표시 파일이 있고, 바뀐 파일이 b 의 것뿐이고, 껍데기가 아직 HEAD 에 있음) b 가 HEAD 로 되돌리고 다시 한다
dirty=$(g status --porcelain --untracked-files=no)
B_RESUME=0
if [[ -n "$dirty" && -f "$B_MARK" ]] && g cat-file -e "HEAD:$SHIM" 2>/dev/null; then
  B_RESUME=1
  while IFS= read -r l; do
    p=${l:3}; ok=0
    for b in "${B_PATHS[@]}"; do [[ "$p" == "$b" ]] && ok=1; done
    ((ok)) || B_RESUME=0
  done <<<"$dirty"
fi
if ((B_RESUME)); then
  say "# 앞선 실행이 b 도중에 멈췄다($B_MARK). b 가 아래 변경을 HEAD 로 되돌리고 다시 한다:"
  printf '%s\n' "$dirty" | sed 's/^/    /'
elif [[ -n "$dirty" ]]; then
  problem "커밋 안 된 변경이 있다(먼저 커밋한다):
$(printf '%s\n' "$dirty" | sed 's/^/    /')"
fi
nwt=$(g worktree list --porcelain | grep -c '^worktree ')
((nwt == 1)) || problem "worktree 가 main 밖에도 있다($((nwt - 1))개, git worktree list). 정리한 뒤 돌린다"

# 병합할 브랜치: 이미 main 에 들어 있으면(마이그레이션 파일이 있음) 없어도 된다
MERGED=0
if g cat-file -e "HEAD:home/settings-migrations/$MIG_ID.json" 2>/dev/null; then
  MERGED=1
elif ! g rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null; then
  problem "브랜치 $BRANCH 가 없고 main 에도 $MIG_ID 가 없다(RENAME_BRANCH 로 이름을 준다)"
fi
if ((!MERGED)) && g rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null; then
  if g merge-base --is-ancestor HEAD "$BRANCH"; then MERGE_KIND=ff
  elif g merge-tree --write-tree HEAD "$BRANCH" >/dev/null 2>&1; then MERGE_KIND=merge
  else problem "main 과 $BRANCH 가 충돌한다(git merge-tree). 브랜치를 main 위로 다시 맞춘 뒤 돌린다"; MERGE_KIND=conflict
  fi
fi

# 옮길 폴더의 목표가 이미 있으면 덮지 않고 멈춘다: 둘을 합치는 것은 사용자 판단이다
DATA_MOVES=()
for d in "$CFG"/plugins/data/*-"$OLD_M"; do
  [[ -d "$d" ]] || continue
  t=${d%-"$OLD_M"}-$NEW_M
  [[ -e "$t" ]] && problem "데이터 폴더 목표가 이미 있다: $t (옛 $d)"
  DATA_MOVES+=("$d")
done
KEY_MOVES=()
for base in "$CFG/projects" "$SL_HOME"; do
  for d in "$base/$OLD_KEY" "$base/$OLD_KEY"--*; do
    [[ -d "$d" ]] || continue
    t=$base/$NEW_KEY${d#"$base/$OLD_KEY"}
    [[ -e "$t" ]] && problem "경로 이름 폴더 목표가 이미 있다: $t (옛 $d)"
    KEY_MOVES+=("$d")
  done
done

if ((${#PROBLEMS[@]})); then
  printf '\n# 막는 것 %d개\n' "${#PROBLEMS[@]}"
  for p in "${PROBLEMS[@]}"; do printf -- '- %s\n' "$p"; done
  ((APPLY)) && die "위 문제를 먼저 푼다. 바뀐 것은 없다"
  say "(dry-run 이라 아래 계획은 계속 보인다)"
fi

# ---------------------------------------------------------------- a 병합
step "a. $BRANCH 를 main 에 병합"
if ((MERGED)); then
  say "  이미 병합됨($MIG_ID 가 main 에 있다)"
elif [[ ${MERGE_KIND:-} == ff ]]; then
  run git -C "$REPO" merge --ff-only "$BRANCH"
elif [[ ${MERGE_KIND:-} == merge ]]; then
  say "  main 이 브랜치를 만든 뒤 움직였다: merge 커밋을 만든다"
  if ((APPLY)); then
    git -C "$REPO" merge --no-edit "$BRANCH" || { git -C "$REPO" merge --abort || true; die "병합 실패, 되돌렸다"; }
  else run git -C "$REPO" merge --no-edit "$BRANCH"; fi
else
  say "  (병합할 수 없음: 위 막는 것 참고)"
fi

# ---------------------------------------------------------------- b 껍데기 지우기
B_MSG="S12 전환: qwreey-conventions 의 reply_language.py 껍데기를 지움(모든 세션을 닫은 뒤)"
# 지우기, 글 고치기, 커밋을 한 덩어리로. if 안에서 불리므로 set -e 가 듣지 않아 명령마다 || return 1
b_apply() {
  printf '  $ git -C %s rm -q %s\n' "$REPO" "$SHIM"
  git -C "$REPO" rm -q "$SHIM" || return 1
  # HUMAN_TODO 의 그 할 일 줄과 플러그인 CLAUDE.md 의 껍데기 설명 문장을 같은 커밋에서 뺀다
  python3 -I -X utf8 - "$REPO" <<'PY' || return 1
import sys, pathlib
root = pathlib.Path(sys.argv[1])
todo = root / "HUMAN_TODO.md"
lines = todo.read_text(encoding="utf-8").splitlines(keepends=True)
todo.write_text("".join(l for l in lines if "qwreey-conventions/hooks/reply_language.py` 껍데기" not in l), encoding="utf-8")
md = root / "plugins/qwreey-conventions/CLAUDE.md"
s = md.read_text(encoding="utf-8")
md.write_text(s.replace(" `reply_language.py` is an unregistered no-op shim (the reply-language check lives in `plugins/qwreey-reply-language`): sessions loaded with the old `hooks.json` still call this path.", ""), encoding="utf-8")
PY
  git -C "$REPO" add HUMAN_TODO.md plugins/qwreey-conventions/CLAUDE.md || return 1
  printf '  $ git -C %s commit -q -m "%s"\n' "$REPO" "$B_MSG"
  git -C "$REPO" commit -q -m "$B_MSG" || return 1
}
step "b. $SHIM 껍데기 지우기(옛 hooks.json 을 실은 세션이 이제 없다)"
if ((APPLY)) && ! g cat-file -e "HEAD:$SHIM" 2>/dev/null; then
  say "  이미 없다"
  rm -f "$B_MARK"   # 커밋 뒤 표시를 지우기 전에 끊긴 경우
elif ((!APPLY)) && ((MERGED)) && ! g cat-file -e "HEAD:$SHIM" 2>/dev/null; then
  say "  이미 없다"
elif ((APPLY)); then
  # 사전 검사가 트리를 깨끗하다고(또는 b 의 것뿐이라고) 봤으므로 HEAD 로 되돌려 잃는 것은 b 의 변경뿐이다
  ((B_RESUME)) && { say "  앞선 b 의 변경을 HEAD 로 되돌린다"; git -C "$REPO" reset -q --hard HEAD; }
  : >"$B_MARK"
  if ! b_apply; then
    git -C "$REPO" reset -q --hard HEAD
    rm -f "$B_MARK"
    die "b 실패(위 출력, 예: pre-commit 훅이 커밋을 막음). 껍데기와 글을 HEAD 로 되돌렸다. 원인을 풀고 같은 명령을 다시 돌린다"
  fi
  rm -f "$B_MARK"
else
  ((B_RESUME)) && say "  (할 일) 앞선 b 의 변경을 HEAD 로 되돌림(git reset --hard HEAD)"
  run git -C "$REPO" rm -q "$SHIM"
  say "  (할 일) HUMAN_TODO.md 의 껍데기 줄, plugins/qwreey-conventions/CLAUDE.md 의 껍데기 문장 빼기"
  run git -C "$REPO" commit -q -m "$B_MSG"
  say "  (커밋까지 못 가면 git reset --hard HEAD 로 되돌리고 멈춘다)"
fi

# ---------------------------------------------------------------- c 플러그인 데이터 폴더
step "c. 플러그인 데이터 폴더 <p>-$OLD_M -> <p>-$NEW_M"
((${#DATA_MOVES[@]})) || say "  옮길 것 없음"
for d in "${DATA_MOVES[@]}"; do run mv "$d" "${d%-"$OLD_M"}-$NEW_M"; done

# ---------------------------------------------------------------- d 저장소 폴더
step "d. 저장소 폴더 $OLD_ROOT -> $NEW_ROOT"
if [[ $PHASE == after ]]; then
  say "  이미 옮겼다"
else
  run mv "$OLD_ROOT" "$NEW_ROOT"
  ((APPLY)) && REPO=$NEW_ROOT
fi

# ---------------------------------------------------------------- e 경로 이름 폴더
step "e. 경로 이름 폴더 $OLD_KEY -> $NEW_KEY (projects: 기록과 auto memory, session-log 저장소)"
((${#KEY_MOVES[@]})) || say "  옮길 것 없음"
for d in "${KEY_MOVES[@]}"; do
  base=$(dirname "$d")
  t=$base/$NEW_KEY${d#"$base/$OLD_KEY"}
  run mv "$d" "$t"
  # session-log 의 project.json 은 처음 한 번만 쓰이므로 새 경로를 직접 적는다
  if [[ "$base" == "$SL_HOME" ]]; then
    if ((APPLY)); then
      [[ -f "$t/project.json" ]] && python3 -I -X utf8 - "$t/project.json" "$OLD_ROOT" "$NEW_ROOT" "$(basename "$t")" <<'PY'
import json, sys
p, old, new, key = sys.argv[1:]
d = json.load(open(p, encoding="utf-8"))
r = d.get("root", "")
if r == old or r.startswith(old + "/"):
    d["root"] = new + r[len(old):]
d["key"] = key
open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
PY
    else
      say "  (할 일) $t/project.json 의 root, key 를 새 경로로"
    fi
  fi
done

# ---------------------------------------------------------------- f home-sync
step "f. 새 위치에서 home-sync (마이그레이션 $MIG_ID: 마켓 선언과 플러그인 키 옮기기)"
if ((APPLY)); then
  (cd "$NEW_ROOT" && CLAUDE_HOME=$CFG tools/home-sync.sh diff && CLAUDE_HOME=$CFG tools/home-sync.sh apply)
  say "  (위에 '설치 안 됨' 이 보이면 다음 g 단계가 설치한다)"
else
  # 병합 전이면 브랜치의 마이그레이션으로, 클론 위치는 새 경로로 놓고 settings 결과만 미리 본다
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  src=HEAD; ((MERGED)) || { g rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null && src=$BRANCH; }
  g archive "$src" home tools/settings-migrate.py | tar -x -C "$tmp"
  [[ -f "$CFG/settings.json" ]] && cp "$CFG/settings.json" "$tmp/before.json" || echo '{}' > "$tmp/before.json"
  python3 -I -X utf8 "$tmp/tools/settings-migrate.py" run --dry-run --settings "$CFG/settings.json" \
    --dir "$tmp/home/settings-migrations" --records "$CFG/.home-sync-migrations" \
    --var "HARNESS_DOCTOR_ROOT=$NEW_ROOT" --out "$tmp/after.json" | sed 's/^/  /'
  sorted() { python3 -I -X utf8 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), indent=2, sort_keys=True, ensure_ascii=False))' "$1"; }
  diff -u --label "settings.json (지금)" --label "settings.json (apply 뒤)" <(sorted "$tmp/before.json") <(sorted "$tmp/after.json") | sed 's/^/  /' || true
  # home-sync 가 같이 맞추는 MANIFEST 파일의 차이
  while IFS= read -r f; do
    diff -u --label "~/.claude/$f (지금)" --label "home/.claude/$f ($src)" "$CFG/$f" "$tmp/home/.claude/$f" 2>/dev/null | sed 's/^/  /' || true
  done < <(grep -v '^\s*#' "$tmp/home/MANIFEST" | grep -v '^\s*$' | grep -v '^link ')
  say "  (할 일) cd $NEW_ROOT && tools/home-sync.sh diff && tools/home-sync.sh apply"
fi

# ---------------------------------------------------------------- g 마켓과 설치본
step "g. 마켓 $OLD_M 제거, $NEW_M 추가, 플러그인 다시 설치"
KM=$CFG/plugins/known_marketplaces.json
IP=$CFG/plugins/installed_plugins.json
ST=$CFG/settings.json
has_market() { python3 -I -X utf8 -c 'import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1])) else 1)' "$KM" "$1" 2>/dev/null; }
# 옛 마켓에 설치된 플러그인(이름, scope, projectPath). remove 가 지우기 전에 적어 두고 다시 돌릴 때 쓴다
if [[ -f "$STATE" ]]; then
  [[ -f "$SNAP" ]] || die "$STATE 는 있는데 스냅숏 $SNAP 이 없다. g 의 기준값을 모르므로 멈춘다: settings.json.bak-* 에서 enabledPlugins, pluginConfigs 를 보고 손으로 맞춘 뒤 $STATE 를 지운다"
  say "  설치 목록 $STATE, 설정 스냅숏 $SNAP (앞선 실행이 적어 둠)"
  PLUGS=$(cat "$STATE")
else
  PLUGS=$(python3 -I -X utf8 - "$IP" "$OLD_M" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8")).get("plugins", {})
except (OSError, ValueError):
    d = {}
for k, entries in sorted(d.items()):
    name, _, m = k.rpartition("@")
    if m == sys.argv[2]:
        for e in entries:
            print(name, e.get("scope", "user"), e.get("projectPath") or "-")
PY
)
fi
G_WORK=0
{ [[ -f "$STATE" || -n "$PLUGS" ]] || has_market "$OLD_M" || ! has_market "$NEW_M"; } && G_WORK=1
if ((G_WORK)); then
  # remove 는 옛 마켓 설치본을 uninstall 하고 install 은 enabledPlugins 를 덮는다: 바꾸기 전 세 파일을 남긴다
  if ((APPLY)); then
    for f in "$ST" "$IP" "$KM"; do backup "$f"; done
  else
    say "  (할 일) $ST, $IP, $KM 를 .bak-<시각> 으로 백업"
  fi
  if [[ ! -f "$STATE" ]]; then
    if ((APPLY)); then
      # 스냅숏을 먼저, 설치 목록을 나중에: $STATE 가 있으면 스냅숏도 있다
      python3 -I -X utf8 - "$ST" "$NEW_M" "$SNAP" <<'PY'
import json, os, sys
path, m, out = sys.argv[1:]
try:
    s = json.load(open(path, encoding="utf-8"))
except (OSError, ValueError):
    s = {}
snap = {}
for k in ("enabledPlugins", "pluginConfigs"):
    v = s.get(k)
    # None: 키 자체가 없었음(되돌린 뒤 빈 객체면 지운다)
    snap[k] = None if not isinstance(v, dict) else {i: x for i, x in v.items() if i.endswith("@" + m)}
tmp = out + ".tmp"
open(tmp, "w", encoding="utf-8").write(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
os.replace(tmp, out)
PY
      printf '%s\n' "$PLUGS" >"$STATE.tmp" && mv "$STATE.tmp" "$STATE"
      say "  스냅숏 $SNAP, 설치 목록 $STATE (g 가 끝나면 지운다)"
    else
      say "  (할 일) enabledPlugins, pluginConfigs 의 @$NEW_M 항목을 $SNAP 에, 설치 목록을 $STATE 에"
    fi
  fi
fi
if has_market "$OLD_M"; then run claude plugin marketplace remove "$OLD_M"; else say "  $OLD_M 는 이미 없다"; fi
if has_market "$NEW_M"; then say "  $NEW_M 는 이미 있다"; else run claude plugin marketplace add "$NEW_ROOT"; fi
# 하나가 실패해도 나머지를 설치하고 되돌리기까지 한 뒤 멈춘다: 덮인 enabledPlugins 가 다음 실행까지 남지 않게
FAILED=()
while read -r name scope proj; do
  [[ -n "${name:-}" ]] || continue
  if [[ "$scope" == user ]]; then
    if ((APPLY)); then
      printf '  $ claude plugin install %s --scope user\n' "$name@$NEW_M"
      claude plugin install "$name@$NEW_M" --scope user || FAILED+=("$name@$NEW_M")
    else
      printf '  (할 일) claude plugin install %s --scope user\n' "$name@$NEW_M"
    fi
  else
    say "  남김: $name 은 $scope scope($proj) 설치였다. 그 프로젝트에서: claude plugin install $name@$NEW_M --scope $scope"
  fi
done <<<"$PLUGS"
if ((APPLY)) && [[ -f "$SNAP" ]]; then
  python3 -I -X utf8 - "$ST" "$SNAP" "$NEW_M" <<'PY'
import json, os, sys
path, snap_p, m = sys.argv[1:]
snap = json.load(open(snap_p, encoding="utf-8"))
s = json.load(open(path, encoding="utf-8"))
fixed = []
for k in ("enabledPlugins", "pluginConfigs"):
    want = snap.get(k) or {}
    cur = s.get(k)
    if not isinstance(cur, dict):
        if not want:
            continue
        cur = s[k] = {}
    for i in sorted({i for i in cur if i.endswith("@" + m)} | set(want)):
        if i not in want:
            del cur[i]; fixed.append(f"{k}.{i} 지움")
        elif cur.get(i) != want[i]:
            cur[i] = want[i]; fixed.append(f"{k}.{i}={json.dumps(want[i], ensure_ascii=False)}")
    if snap.get(k) is None and not cur:
        del s[k]
if fixed:
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    print("  스냅숏 값으로 되돌림: " + ", ".join(fixed))
PY
fi
if ((${#FAILED[@]})); then
  die "install 실패: ${FAILED[*]}. enabledPlugins, pluginConfigs 는 스냅숏 값으로 되돌렸다. 원인(위 출력)을 풀고 같은 명령을 다시 돌린다(설치 목록 $STATE 와 스냅숏 $SNAP 을 다시 쓴다)"
fi
((APPLY)) && rm -f "$STATE" "$SNAP"
run claude plugin marketplace list

# ---------------------------------------------------------------- h 남는 일
step "h. 사용자에게 남는 일"
if [[ -f "$CODERAG_CFG" ]] && grep -qF "\"$OLD_ROOT/" "$CODERAG_CFG"; then
  say "  $CODERAG_CFG 의 팩 경로:"
  grep -nF "\"$OLD_ROOT/" "$CODERAG_CFG" | sed 's/^/    /'
  if ((APPLY)) && [[ -w "$CODERAG_CFG" && "$(stat -c %u "$CODERAG_CFG")" == "$(id -u)" ]]; then
    # path = "<옛 루트>/..." 줄만 바꾼다. 주석과 다른 키는 그대로
    cp -p "$CODERAG_CFG" "$CODERAG_CFG.bak-$STAMP"
    python3 -I -X utf8 - "$CODERAG_CFG" "$OLD_ROOT" "$NEW_ROOT" <<'PY'
import re, sys
p, old, new = sys.argv[1:]
s = open(p, encoding="utf-8").read()
s = re.sub(r'(?m)^(\s*path\s*=\s*")' + re.escape(old) + r'(/[^"]*")', lambda m: m.group(1) + new + m.group(2), s)
open(p, "w", encoding="utf-8").write(s)
PY
    say "  고쳤다(백업 $CODERAG_CFG.bak-$STAMP):"
    grep -nF "\"$NEW_ROOT/" "$CODERAG_CFG" | sed 's/^/    /'
  else
    say "  (할 일) 위 줄의 $OLD_ROOT/ 를 $NEW_ROOT/ 로(--apply 가 백업 뒤 고친다. 파일이 내 것이 아니면 손으로)"
  fi
else
  say "  $CODERAG_CFG: 옛 경로 줄 없음"
fi
say "  지울지 사용자가 정한다(이 스크립트는 지우지 않는다):"
for p in "$(dirname "$OLD_ROOT")"/claude-doctor.old-* "${XDG_DATA_HOME:-$HOME/.local/share}/claude-doctor-history-cleanup" "$CFG/plugins/cache/$OLD_M"; do
  [[ -e "$p" ]] && say "    rm -rf $p"
done
# 세션별 개발 mod 링크(dev-mods/<세션 id>/<이름>). 옛 폴더를 가리키면 끊긴 링크이고 그 세션은 이제 없다
while IFS= read -r l; do
  [[ -n "$l" ]] && say "    rm $l   # 옛 경로를 가리키는 dev-mods 링크"
done < <(find "$CFG/dev-mods" -mindepth 2 -maxdepth 2 -type l -lname "$OLD_ROOT/*" 2>/dev/null | sort)
say "    (선택) /tmp/claude-* 와 /tmp/claude-0: 살아 있는 세션이 없는 지금만 지워도 된다"
if [[ -f "$CLAUDE_JSON" ]] && python3 -I -X utf8 -c 'import json,sys; sys.exit(0 if sys.argv[2] in (json.load(open(sys.argv[1], encoding="utf-8")).get("projects") or {}) else 1)' "$CLAUDE_JSON" "$OLD_ROOT" 2>/dev/null; then
  say "  $CLAUDE_JSON 의 projects[\"$OLD_ROOT\"] 는 옛 폴더의 항목(신뢰, 폴더별 기록)이라 새 폴더로 오지 않는다."
  say "    새 폴더에서 처음 claude 를 열 때 신뢰 대화가 한 번 뜬다. 옛 항목은 둬도 해가 없다"
fi
stale=$(grep -rlF "$OLD_ROOT" "$CFG"/plugins/data/*-"$NEW_M" 2>/dev/null | sort || true)
if [[ -n "$stale" ]]; then
  say "  플러그인 데이터 폴더의 캐시에 옛 경로가 남은 파일(지우지 않아도 된다):"
  while IFS= read -r f; do
    if [[ "$(basename "$f")" == known_repos.json ]]; then
      say "    $f (qwreey-workspace: projects/ 가 바뀌면 다시 모으고 없는 폴더는 빼므로 스스로 고쳐진다)"
    else
      say "    $f"
    fi
  done <<<"$stale"
fi
if [[ -f "$ST" ]] && grep -qF "$OLD_ROOT" "$ST"; then
  say "  settings.json 에 옛 경로가 남은 줄(사용자가 쓴 글, 예: autoMode 설명). 손으로 고친다:"
  grep -nF "$OLD_ROOT" "$ST" | cut -c1-160 | sed 's/^/    /'
fi
siblings=$(grep -lF "@$OLD_M" "$(dirname "$NEW_ROOT")"/*/.claude/settings*.json 2>/dev/null || true)
if [[ -n "$siblings" ]]; then
  say "  형제 저장소의 .claude/settings 가 옛 마켓 키를 쓴다. 그 저장소 세션에서(저장소별 승인) coderag adapt --harness claude:"
  printf '%s\n' "$siblings" | sed 's/^/    /'
fi
say "  다음: 새 폴더에서 새 세션(cd $NEW_ROOT && claude), .claude/plan/rename-qwreey-harness.md 3절대로 확인"
((APPLY)) || say $'\n'"dry-run 끝. 바뀐 것은 없다. 실제로 하려면 --apply"
