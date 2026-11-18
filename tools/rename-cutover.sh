#!/usr/bin/env bash
# 저장소 폴더와 마켓 이름 바꾸기 전환: claude-doctor -> qwreey-harness, claude-doctor-market -> qwreey-harness.
#
#   bash rename-cutover.sh            검사하고 할 일만 단계마다 보인다(아무것도 바꾸지 않음)
#   bash rename-cutover.sh --apply    실제로 한다
#
# 이 스크립트는 전환 브랜치에 있고 main 에는 병합 뒤에야 생기므로, 자기 위치가 아니라 아래 경로로 움직인다.
#   main 에서 부를 때: git -C /code/Projects/claude-doctor show rename-qwreey-harness:tools/rename-cutover.sh > /tmp/rename-cutover.sh
# 모든 Claude Code 세션을 닫은 뒤에만 --apply 한다: 살아 있는 세션은 훅을 옛 폴더의 plugins/ 에서 부르고,
#   마켓 이름이 바뀌면 그 세션이 다시 읽을 때 등록과 어긋난다.
#
# 단계(--apply 는 이 순서로, 다시 돌리면 끝난 단계는 건너뛴다)
#   a  전환 브랜치를 main 에 병합(앞서 갈 수 있으면 fast-forward, main 이 움직였으면 merge, 충돌이면 중단)
#   b  qwreey-conventions 의 reply_language.py 껍데기를 git rm 하고 그 HUMAN_TODO 줄과 함께 커밋
#   c  ~/.claude/plugins/data/<p>-claude-doctor-market -> <p>-qwreey-harness (마켓 remove 가 옛 이름 폴더를 지우기 전에)
#   d  저장소 폴더 mv
#   e  ~/.claude/projects 와 session-log 저장소의 경로 이름 폴더 mv(project.json 도 새 경로로)
#   f  새 위치에서 tools/home-sync.sh diff, apply (마이그레이션 0010 이 settings 의 마켓 선언과 플러그인 키를 옮긴다)
#   g  claude plugin marketplace remove 옛 마켓, 새 마켓 add, 옛 마켓에 설치돼 있던 플러그인을 새 이름으로 install,
#      install 이 켜 버린 enabledPlugins 값을 마이그레이션 뒤 값으로 되돌림
#   h  사용자에게 남는 일: ~/.coderag/coderag.toml 팩 경로(백업 뒤 고침), 지울 옛 폴더, 형제 저장소의 coderag adapt
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
SL_HOME=${SESSION_LOG_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/session-log}
CODERAG_CFG=${CODERAG_HOME:-$HOME/.coderag}/coderag.toml
OLD_M=claude-doctor-market
NEW_M=qwreey-harness
MIG_ID=0010-qwreey-harness-market
SHIM=plugins/qwreey-conventions/hooks/reply_language.py
STATE=$CFG/.rename-cutover-plugins   # g 가 옛 마켓을 지우기 전에 적어 둔 설치 목록(다시 돌릴 때 쓴다)
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

# 실행 중인 Claude Code 없음. -f 는 이 스크립트 자신의 명령 줄과도 맞으므로 프로세스 이름(-x)으로만 본다
if [[ "${RENAME_ALLOW_LIVE:-}" == 1 && "$OLD_ROOT" != "$DEFAULT_OLD" ]]; then
  say "(리허설: 실행 중인 claude 검사를 건너뛴다)"
elif live=$(pgrep -x claude -a 2>/dev/null); then
  problem "실행 중인 claude 프로세스가 있다(세션, daemon, bg-spare 모두). 모든 세션을 닫고, 남은 것은 끝나기를 기다리거나 kill 한다:
$(printf '%s\n' "$live" | cut -c1-150 | sed 's/^/    /')"
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
dirty=$(g status --porcelain --untracked-files=no)
[[ -z "$dirty" ]] || problem "커밋 안 된 변경이 있다(먼저 커밋한다):
$(printf '%s\n' "$dirty" | sed 's/^/    /')"
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
step "b. $SHIM 껍데기 지우기(옛 hooks.json 을 실은 세션이 이제 없다)"
if ((APPLY)) && ! g cat-file -e "HEAD:$SHIM" 2>/dev/null; then
  say "  이미 없다"
elif ((!APPLY)) && ((MERGED)) && ! g cat-file -e "HEAD:$SHIM" 2>/dev/null; then
  say "  이미 없다"
else
  run git -C "$REPO" rm -q "$SHIM"
  if ((APPLY)); then
    # HUMAN_TODO 의 그 할 일 줄과 플러그인 CLAUDE.md 의 껍데기 설명 문장을 같은 커밋에서 뺀다
    python3 -I -X utf8 - "$REPO" <<'PY'
import sys, pathlib
root = pathlib.Path(sys.argv[1])
todo = root / "HUMAN_TODO.md"
lines = todo.read_text(encoding="utf-8").splitlines(keepends=True)
todo.write_text("".join(l for l in lines if "qwreey-conventions/hooks/reply_language.py` 껍데기" not in l), encoding="utf-8")
md = root / "plugins/qwreey-conventions/CLAUDE.md"
s = md.read_text(encoding="utf-8")
md.write_text(s.replace(" `reply_language.py` is an unregistered no-op shim (the reply-language check lives in `plugins/qwreey-reply-language`): sessions loaded with the old `hooks.json` still call this path.", ""), encoding="utf-8")
PY
    git -C "$REPO" add HUMAN_TODO.md plugins/qwreey-conventions/CLAUDE.md
  else
    say "  (할 일) HUMAN_TODO.md 의 껍데기 줄, plugins/qwreey-conventions/CLAUDE.md 의 껍데기 문장 빼기"
  fi
  run git -C "$REPO" commit -q -m "S12 전환: qwreey-conventions 의 reply_language.py 껍데기를 지움(모든 세션을 닫은 뒤)"
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
command -v claude >/dev/null || die "claude 가 PATH 에 없다"
KM=$CFG/plugins/known_marketplaces.json
IP=$CFG/plugins/installed_plugins.json
# 옛 마켓에 설치된 플러그인(이름, scope, projectPath). remove 가 지우기 전에 적어 두고 다시 돌릴 때 쓴다
if [[ -f "$STATE" ]]; then
  say "  설치 목록: $STATE (앞선 실행이 적어 둠)"
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
  ((APPLY)) && [[ -n "$PLUGS" ]] && printf '%s\n' "$PLUGS" > "$STATE"
fi
has_market() { python3 -I -X utf8 -c 'import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1])) else 1)' "$KM" "$1" 2>/dev/null; }
if has_market "$OLD_M"; then run claude plugin marketplace remove "$OLD_M"; else say "  $OLD_M 는 이미 없다"; fi
if has_market "$NEW_M"; then say "  $NEW_M 는 이미 있다"; else run claude plugin marketplace add "$NEW_ROOT"; fi
# install 은 enabledPlugins 를 true(defaultEnabled false 면 false)로 덮는다. 마이그레이션이 옮긴 값(사용자가 끈 것, 없음)을 되돌리려고 먼저 적어 둔다
ENABLED_BEFORE=$(mktemp)
python3 -I -X utf8 -c 'import json,sys
try: s = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError): s = {}
json.dump(s.get("enabledPlugins") or {}, open(sys.argv[2], "w"))' "$CFG/settings.json" "$ENABLED_BEFORE"
INSTALLED=()
while read -r name scope proj; do
  [[ -n "${name:-}" ]] || continue
  if [[ "$scope" == user ]]; then
    run claude plugin install "$name@$NEW_M" --scope user
    INSTALLED+=("$name@$NEW_M")
  else
    say "  남김: $name 은 $scope scope($proj) 설치였다. 그 프로젝트에서: claude plugin install $name@$NEW_M --scope $scope"
  fi
done <<<"$PLUGS"
if ((APPLY)) && ((${#INSTALLED[@]})); then
  python3 -I -X utf8 - "$CFG/settings.json" "$ENABLED_BEFORE" "$STAMP" "${INSTALLED[@]}" <<'PY'
import json, shutil, sys
path, before_p, stamp, *ids = sys.argv[1:]
before = json.load(open(before_p))
s = json.load(open(path, encoding="utf-8"))
ep = s.setdefault("enabledPlugins", {})
fixed = []
for k in ids:
    if k in before and ep.get(k) != before[k]:
        ep[k] = before[k]; fixed.append(f"{k}={before[k]}")
    elif k not in before and k in ep:
        del ep[k]; fixed.append(f"{k} 지움")
if fixed:
    shutil.copy2(path, f"{path}.bak-{stamp}")
    open(path, "w", encoding="utf-8").write(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    print("  enabledPlugins 되돌림: " + ", ".join(fixed))
PY
fi
rm -f "$ENABLED_BEFORE"
((APPLY)) && rm -f "$STATE"
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
say "    (선택) /tmp/claude-* 와 /tmp/claude-0: 살아 있는 세션이 없는 지금만 지워도 된다"
if [[ -f "$CFG/settings.json" ]] && grep -qF "$OLD_ROOT" "$CFG/settings.json"; then
  say "  settings.json 에 옛 경로가 남은 줄(사용자가 쓴 글, 예: autoMode 설명). 손으로 고친다:"
  grep -nF "$OLD_ROOT" "$CFG/settings.json" | cut -c1-160 | sed 's/^/    /'
fi
siblings=$(grep -lF "@$OLD_M" "$(dirname "$NEW_ROOT")"/*/.claude/settings*.json 2>/dev/null || true)
if [[ -n "$siblings" ]]; then
  say "  형제 저장소의 .claude/settings 가 옛 마켓 키를 쓴다. 그 저장소 세션에서(저장소별 승인) coderag adapt --harness claude:"
  printf '%s\n' "$siblings" | sed 's/^/    /'
fi
say "  다음: 새 폴더에서 새 세션(cd $NEW_ROOT && claude), .claude/plan/rename-qwreey-harness.md 3절대로 확인"
((APPLY)) || say $'\n'"dry-run 끝. 바뀐 것은 없다. 실제로 하려면 --apply"
