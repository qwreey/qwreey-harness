#!/usr/bin/env bash
# claude-doctor/home/.claude (정본) <-> ~/.claude (실제) 동기화 도우미.
#
#   tools/home-sync.sh status   관리 대상 파일마다 같음/다름/한쪽에만 있음을 표시한다 (기본 동작)
#   tools/home-sync.sh diff     정본에서 실제로 가는 diff 를 보여준다 (apply 하면 바뀔 내용)
#   tools/home-sync.sh pull     실제 -> 정본으로 가져온다. /config 등으로 실제 쪽만 바뀐 경우에 쓴다
#   tools/home-sync.sh apply    정본 -> 실제로 복사한다. 사용자가 diff 를 검토한 뒤 직접 실행한다
#   tools/home-sync.sh new-migration <slug>   home/settings-migrations/ 에 다음 번호의 빈 마이그레이션을 만든다
#
# settings.json 은 복사하지 않는다(MANIFEST 에 없음). 정본은 home/settings-migrations/NNNN-<slug>.json 이고,
#   apply 가 아직 적용하지 않은 것만 순서대로 한 번씩 적용한다(tools/settings-migrate.py). 적용한 id 는 $DST/.home-sync-migrations.
#   마이그레이션에 없는 값(사용자 플러그인, 권한, /config 값)은 건드리지 않고, 적용 뒤 사용자가 바꾼 값도 되돌리지 않는다.
#   실패하면 그 마이그레이션만 되돌린다. 연산 종류는 settings-migrate.py 머리 주석.
#   (status 는 고아도 보고한다: 이전에 관리했지만 MANIFEST 에서 빠진 항목, 관리 디렉터리의 끊어진 링크. 지우지는 않고 제거 명령만 제안한다)
#   tools/home-sync.sh env      harness.env 를 푼 값(MANIFEST 링크 대상에 쓰이는 변수)을 보여준다
#
# 이전에 관리한 목록: apply 가 $DST/.home-sync-managed 에 기록한다(한 줄에 "file|link <경로>"). skills/ rules/ hooks/ 밖이라 로드되지 않는다.
#   상태 파일이 없으면(첫 실행) git 이력(git log -p home/MANIFEST)에서 옛 항목을 모아 실제에 남아 있는 것만 후보로 쓴다.
# 관리 대상 목록은 home/MANIFEST 에 있다. 링크 대상의 ${VAR} 는 harness.env 로 푼다.
#   harness.env 위치: $HARNESS_ENV, 없으면 정본 home/.claude/harness.env. 같은 이름의 환경 변수가 이긴다.
#   기본값: HARNESS_DOCTOR_ROOT = 이 클론, HARNESS_WORKSPACE = 그 부모.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/home/.claude"
DST="${CLAUDE_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
mapfile -t FILES < <(grep -v '^\s*#' "$ROOT/home/MANIFEST" | grep -v '^\s*$' | grep -v '^link ' | grep -vx 'settings.json')
MIG_DIR="$ROOT/home/settings-migrations"
MIG_REC="$DST/.home-sync-migrations"
migrate() { # $1 = run|status, 나머지는 settings-migrate.py 에 전달
  local c=$1; shift
  python3 -I -X utf8 "$ROOT/tools/settings-migrate.py" "$c" --settings "$DST/settings.json" --dir "$MIG_DIR" --records "$MIG_REC" "$@"
}
# JSON 을 키 정렬로 찍는다. jq 가 없으면(Git for Windows 에는 없다) python3 로.
json_sorted() {
  if command -v jq >/dev/null; then jq -S . "$1"
  else python3 -I -X utf8 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), indent=2, sort_keys=True, ensure_ascii=False))' "$1"; fi
}
# 링크 항목: "link <~/.claude 기준 경로> <대상(변수 가능)>"
mapfile -t LINKS < <(grep '^link ' "$ROOT/home/MANIFEST" | cut -d' ' -f2-)

# --- harness.env (lib/harness_env.py 와 같은 규칙: KEY=VALUE, source 하지 않음, 환경 변수 우선)
declare -A HENV=([HARNESS_DOCTOR_ROOT]="$ROOT" [HARNESS_WORKSPACE]="$(dirname "$ROOT")")
ENVFILE=${HARNESS_ENV:-$SRC/harness.env}
MISSING=""
henv_get() { # $1 이름 -> 값(harness.env 키, 없으면 환경 변수, 둘 다 없으면 빈 값)
  if [[ -v "HENV[$1]" ]]; then printf '%s' "${HENV[$1]}"
  elif [[ -n "${!1+x}" ]]; then printf '%s' "${!1}"; fi
}
henv_expand() { # $1 문자열 -> EXPANDED. ${NAME}, $NAME, 맨 앞 ~
  local s=$1 out="" name
  [[ $s == "~"* ]] && s="$HOME${s:1}"
  while [[ $s =~ ^([^\$]*)\$(\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))(.*)$ ]]; do
    name=${BASH_REMATCH[3]:-${BASH_REMATCH[4]}}
    out+="${BASH_REMATCH[1]}"; s=${BASH_REMATCH[5]}
    out+="$(henv_get "$name")"
    [[ -v "HENV[$name]" || -n "${!name+x}" ]] || MISSING+=" $name"
  done
  EXPANDED="$out$s"
}
for k in "${!HENV[@]}"; do [[ -n "${!k+x}" ]] && HENV[$k]=${!k}; done
if [[ -f "$ENVFILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ $line =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]] || continue
    k=${BASH_REMATCH[2]}; v=${BASH_REMATCH[3]}
    if [[ -n "${!k+x}" ]]; then HENV[$k]=${!k}; continue; fi
    v="${v#"${v%%[![:space:]]*}"}"
    if [[ $v == \"* || $v == \'* ]]; then q=${v:0:1}; v=${v:1}; v=${v%%"$q"*}
    else v=${v%%[[:space:]]#*}; v="${v%"${v##*[![:space:]]}"}"; fi
    henv_expand "$v"; HENV[$k]=$EXPANDED
  done < "$ENVFILE"
fi
MISSING=""

links() {
  local mode=$1 l path target cur
  for l in "${LINKS[@]}"; do
    path=${l%% *}; MISSING=""; henv_expand "${l#* }"; target=$EXPANDED
    if [[ -n "$MISSING" ]]; then
      [[ $mode == apply ]] && echo "건너뜀 $path: 정의 안 된 변수(${MISSING# })" \
        || printf '%-40s 정의 안 된 변수(%s) — harness.env 확인\n' "$path" "${MISSING# }"
      continue
    fi
    cur=$(readlink "$DST/$path" 2>/dev/null || true)
    case "$mode" in
      status)
        if [[ ! -e "$target" ]]; then printf '%-40s 링크 대상 없음: %s\n' "$path" "$target"
        elif [[ "$cur" == "$target" ]]; then printf '%-40s 링크 같음\n' "$path"
        elif [[ -e "$DST/$path" && -z "$cur" ]]; then printf '%-40s 링크 아닌 실제 파일이 있음 (수동 확인)\n' "$path"
        else printf '%-40s 링크 필요 (apply) → %s\n' "$path" "$target"; fi ;;
      diff) [[ "$cur" == "$target" ]] || printf 'link ~/.claude/%s: %s → %s\n' "$path" "${cur:-(없음)}" "$target" ;;
      apply)
        if [[ "$cur" != "$target" && -e "$target" ]]; then
          if [[ -e "$DST/$path" && -z "$cur" ]]; then echo "건너뜀 $path: 링크가 아닌 실제 파일이 있음"; continue; fi
          mkdir -p "$(dirname "$DST/$path")"; ln -sfn "$target" "$DST/$path"; echo "linked $path → $target"
        fi ;;
    esac
  done
}

# --- 고아: 이전에 관리했지만 지금 MANIFEST 에 없고 실제에 남아 있는 항목
STATE="$DST/.home-sync-managed"
declare -A CUR=()
for f in "${FILES[@]}"; do CUR[$f]=1; done
CUR[settings.json]=1   # 복사 대상은 아니지만 마이그레이션이 다루므로 고아가 아니다
for l in "${LINKS[@]}"; do CUR[${l%% *}]=1; done
ORPHANS=()
if [[ -f "$STATE" ]]; then ORPHAN_SRC="상태 파일"; else ORPHAN_SRC="git 이력 후보(상태 파일 없음)"; fi
find_orphans() {
  local kind path
  if [[ -f "$STATE" ]]; then
    while read -r kind path; do [[ -n "${path:-}" ]] && echo "$path"; done < "$STATE"
  else
    git -C "$ROOT" log -p --format= -- home/MANIFEST 2>/dev/null | sed -n 's/^-\([^-#].*\)$/\1/p' \
      | sed 's/^link //; s/[[:space:]].*$//' || true
  fi | sort -u | while read -r path; do
    [[ -z "$path" || -n "${CUR[$path]:-}" ]] && continue
    [[ -e "$DST/$path" || -L "$DST/$path" ]] && echo "$path"
  done
}
rm_hint() { # $1 경로. settings.json 이 아직 부르는 파일은 지우라고 하지 않는다(지우면 훅마다 오류)
  local base; base=$(basename "$1")
  if [[ -f "$DST/settings.json" ]] && grep -qF "$base" "$DST/settings.json"; then
    printf '  보류: settings.json 이 아직 %s 를 부른다. 그 훅을 빼는 마이그레이션을 apply 한 뒤에 지운다\n' "$base"
  elif [[ -L "$DST/$1" || -f "$DST/$1" ]]; then printf '  제안: rm %q\n' "$DST/$1"
  else printf '  제안: (디렉터리 — 수동 확인) %q\n' "$DST/$1"; fi
}
orphans_report() {
  local p d found=0 listed=" "
  mapfile -t ORPHANS < <(find_orphans)
  if ((${#ORPHANS[@]})); then
    echo; echo "# 이전에 관리했지만 지금 MANIFEST 에 없음 [$ORPHAN_SRC] — 삭제는 사용자가 한다"; found=1
    for p in "${ORPHANS[@]}"; do
      listed+="$p "
      if [[ -L "$DST/$p" && ! -e "$DST/$p" ]]; then printf '%-40s 끊어진 링크 (→ %s)\n' "$p" "$(readlink "$DST/$p")"
      elif [[ -L "$DST/$p" ]]; then printf '%-40s 링크 → %s\n' "$p" "$(readlink "$DST/$p")"
      else printf '%-40s 파일/디렉터리\n' "$p"; fi
      rm_hint "$p"
    done
  fi
  while IFS= read -r p; do
    p=${p#"$DST/"}
    [[ -n "${CUR[$p]:-}" || "$listed" == *" $p "* || -e "$DST/$p" ]] && continue
    ((found)) && [[ -n "${hdr:-}" ]] || { echo; echo "# 관리 디렉터리 안의 끊어진 링크 (관리 목록에 없음)"; hdr=1; }
    found=1; printf '%-40s 끊어진 링크 (→ %s)\n' "$p" "$(readlink "$DST/$p")"; rm_hint "$p"
  done < <(for d in skills rules hooks lib; do [[ -d "$DST/$d" ]] && find "$DST/$d" -maxdepth 2 -type l; done | sort)
  ((found)) || echo "(고아 없음)"
}
write_state() { # 현재 MANIFEST + 아직 실제에 남은 고아를 기록한다. 내용이 같으면 쓰지 않는다
  local new f l p
  new=$({ for f in "${FILES[@]}"; do echo "file $f"; done
          for l in "${LINKS[@]}"; do echo "link ${l%% *}"; done
          mapfile -t ORPHANS < <(find_orphans)
          for p in "${ORPHANS[@]}"; do [[ -L "$DST/$p" ]] && echo "link $p" || echo "file $p"; done; } | sort -u)
  if [[ ! -f "$STATE" ]] || [[ "$(cat "$STATE")" != "$new" ]]; then
    mkdir -p "$DST"; printf '%s\n' "$new" > "$STATE"; echo "recorded .home-sync-managed"
  fi
}

plugins_report() { # settings 의 enabledPlugins(true) 중 아직 설치 안 된 것을 알리고, 원하면 설치한다
  local want have missing p m src
  [[ -f "$DST/settings.json" ]] && command -v claude >/dev/null || return 0
  command -v jq >/dev/null || { echo "plugins: jq 가 없어 설치 상태 확인을 건너뛴다(claude plugin list 로 본다)"; return 0; }
  [[ "$DST" == "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" ]] || return 0   # 임시 CLAUDE_HOME 시험에서는 실제 CLI 상태와 무관
  want=$(jq -r '.enabledPlugins // {} | to_entries[] | select(.value == true) | .key' "$DST/settings.json" | grep -v '@builtin$' || true)
  have=$(claude plugin list --json 2>/dev/null | jq -r '.[]?.id' 2>/dev/null || true)
  missing=$(comm -23 <(sort -u <<<"$want") <(sort -u <<<"$have") | sed '/^$/d')
  [[ -z "$missing" ]] && { echo "plugins: settings 에 켠 플러그인이 모두 설치돼 있다"; return 0; }
  echo "plugins: settings 에 켜져 있지만 설치 안 됨(새 대화형 세션을 열면 설치될 수 있다):"
  for p in $missing; do
    m=${p#*@}; src=$(jq -r --arg m "$m" '.extraKnownMarketplaces[$m].source | if .source == "directory" then .path else (.repo // .url // empty) end' "$DST/settings.json" 2>/dev/null)
    echo "  $p   →  ${src:+claude plugin marketplace add $src && }claude plugin install $p"
    if [[ "${HOME_SYNC_INSTALL_PLUGINS:-}" == 1 ]]; then
      [[ -n "$src" ]] && { claude plugin marketplace list 2>/dev/null | grep -q " $m\$\|❯ $m" || claude plugin marketplace add "$src"; }
      claude plugin install "$p"
    fi
  done
  [[ "${HOME_SYNC_INSTALL_PLUGINS:-}" == 1 ]] || echo "  지금 설치하려면: HOME_SYNC_INSTALL_PLUGINS=1 $0 apply (또는 위 명령을 직접)"
}

cmd=${1:-status}
case "$cmd" in
  status)
    links status
    [[ -d "$MIG_DIR" ]] && { printf '%-40s ' settings.json; migrate status; }
    for f in "${FILES[@]}"; do
      if [[ ! -e "$SRC/$f" ]]; then printf '%-40s 정본에 없음\n' "$f"
      elif [[ ! -e "$DST/$f" ]]; then printf '%-40s 실제에 없음 (apply 필요)\n' "$f"
      elif cmp -s "$SRC/$f" "$DST/$f"; then printf '%-40s 같음\n' "$f"
      elif [[ "$SRC/$f" -nt "$DST/$f" ]]; then printf '%-40s 다름 (정본이 더 새로움 → diff 후 apply)\n' "$f"
      else printf '%-40s 다름 (실제가 더 새로움 → pull 검토)\n' "$f"; fi
    done
    orphans_report
    plugins_report ;;
  diff)
    links diff
    if [[ -d "$MIG_DIR" ]]; then
      tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
      [[ -e "$DST/settings.json" ]] && cp "$DST/settings.json" "$tmp/actual.json" || echo '{}' > "$tmp/actual.json"
      migrate run --dry-run --out "$tmp/result.json" || echo "(마이그레이션 계획 실패)"
      diff -u --label "~/.claude/settings.json (실제)" --label "settings.json (마이그레이션 적용 후)" \
        <(json_sorted "$tmp/actual.json") <(json_sorted "$tmp/result.json") || true
    fi
    for f in "${FILES[@]}"; do
      diff -u --label "~/.claude/$f (실제)" --label "home/.claude/$f (정본)" "$DST/$f" "$SRC/$f" 2>/dev/null || true
    done ;;
  pull)
    echo "(settings.json 은 pull 대상이 아니다: 실제에서 가져올 값은 home/settings-migrations/ 에 마이그레이션으로 쓴다. new-migration 참고)"
    for f in "${FILES[@]}"; do
      [[ -e "$DST/$f" ]] || continue
      if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
        mkdir -p "$(dirname "$SRC/$f")"; cp -p "$DST/$f" "$SRC/$f"; echo "pulled $f"
      fi
    done ;;
  apply)
    if [[ -d "$MIG_DIR" ]]; then migrate run || exit $?; fi
    links apply
    for f in "${FILES[@]}"; do
      [[ -e "$SRC/$f" ]] || continue
      if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
        [[ -e "$DST/$f" ]] && cp -p "$DST/$f" "$DST/$f.bak-$(date +%Y%m%d%H%M%S)"
        mkdir -p "$(dirname "$DST/$f")"; cp -p "$SRC/$f" "$DST/$f"; echo "applied $f"
      fi
    done
    write_state
    [[ -f "$DST/settings.json" ]] && { json_sorted "$DST/settings.json" >/dev/null && echo "settings.json JSON OK"; }
    plugins_report ;;
  new-migration)
    slug=${2:?usage: $0 new-migration <slug>}
    [[ $slug =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "slug 는 소문자·숫자·하이픈" >&2; exit 2; }
    mkdir -p "$MIG_DIR"
    last=$(ls "$MIG_DIR" 2>/dev/null | sed -n 's/^\([0-9]\{4\}\)-.*/\1/p' | sort | tail -1)
    id=$(printf '%04d-%s' $((10#${last:-0} + 1)) "$slug")
    printf '{\n  "id": "%s",\n  "why": "",\n  "ops": []\n}\n' "$id" > "$MIG_DIR/$id.json"
    echo "created home/settings-migrations/$id.json" ;;
  env)
    echo "# harness.env: $([[ -f "$ENVFILE" ]] && echo "$ENVFILE" || echo "(없음 — 기본값)")"
    for k in $(printf '%s\n' "${!HENV[@]}" | sort); do printf '%s=%s\n' "$k" "${HENV[$k]}"; done ;;
  *) echo "usage: $0 [status|diff|pull|apply|new-migration|env]" >&2; exit 2 ;;
esac
