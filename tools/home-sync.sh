#!/usr/bin/env bash
# claude-doctor/home/.claude (정본) <-> ~/.claude (실제) 동기화 도우미.
#
#   tools/home-sync.sh status   관리 대상 파일마다 같음/다름/한쪽에만 있음을 표시한다 (기본 동작)
#   tools/home-sync.sh diff     정본에서 실제로 가는 diff 를 보여준다 (apply 하면 바뀔 내용)
#   tools/home-sync.sh pull     실제 -> 정본으로 가져온다. /config 등으로 실제 쪽만 바뀐 경우에 쓴다
#   tools/home-sync.sh apply    정본 -> 실제로 복사한다. 사용자가 diff 를 검토한 뒤 직접 실행한다
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
mapfile -t FILES < <(grep -v '^\s*#' "$ROOT/home/MANIFEST" | grep -v '^\s*$' | grep -v '^link ')
# 링크 항목: "link <~/.claude 기준 경로> <대상(변수 가능)>"
mapfile -t LINKS < <(grep '^link ' "$ROOT/home/MANIFEST" | cut -d' ' -f2-)

# --- harness.env (lib/harness_env.py 와 같은 규칙: KEY=VALUE, source 하지 않음, 환경 변수 우선)
declare -A HENV=([HARNESS_DOCTOR_ROOT]="$ROOT" [HARNESS_WORKSPACE]="$(dirname "$ROOT")")
ENVFILE=${HARNESS_ENV:-$SRC/harness.env}
MISSING=""
henv_get() { # $1 이름 → 값(harness.env 키, 없으면 환경 변수, 둘 다 없으면 빈 값)
  if [[ -v "HENV[$1]" ]]; then printf '%s' "${HENV[$1]}"
  elif [[ -n "${!1+x}" ]]; then printf '%s' "${!1}"; fi
}
henv_expand() { # $1 문자열 → EXPANDED. ${NAME}·$NAME·맨 앞 ~
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
rm_hint() { # $1 경로
  if [[ -L "$DST/$1" || -f "$DST/$1" ]]; then printf '  제안: rm %q\n' "$DST/$1"
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

cmd=${1:-status}
case "$cmd" in
  status)
    links status
    for f in "${FILES[@]}"; do
      if [[ ! -e "$SRC/$f" ]]; then printf '%-40s 정본에 없음\n' "$f"
      elif [[ ! -e "$DST/$f" ]]; then printf '%-40s 실제에 없음 (apply 필요)\n' "$f"
      elif cmp -s "$SRC/$f" "$DST/$f"; then printf '%-40s 같음\n' "$f"
      elif [[ "$SRC/$f" -nt "$DST/$f" ]]; then printf '%-40s 다름 (정본이 더 새로움 → diff 후 apply)\n' "$f"
      else printf '%-40s 다름 (실제가 더 새로움 → pull 검토)\n' "$f"; fi
    done
    orphans_report ;;
  diff)
    links diff
    for f in "${FILES[@]}"; do
      diff -u --label "~/.claude/$f (실제)" --label "home/.claude/$f (정본)" "$DST/$f" "$SRC/$f" 2>/dev/null || true
    done ;;
  pull)
    for f in "${FILES[@]}"; do
      [[ -e "$DST/$f" ]] || continue
      if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
        mkdir -p "$(dirname "$SRC/$f")"; cp -p "$DST/$f" "$SRC/$f"; echo "pulled $f"
      fi
    done ;;
  apply)
    # 실제 settings.json 에만 있는 최상위 키(예: /config, /auto-mode-setup 이 만든 것)가 있으면
    # 통째 cp 가 그 키를 지운다. 멈추고 알린다. 덮어쓰려면 HOME_SYNC_FORCE=1.
    if [[ -f "$DST/settings.json" && -f "$SRC/settings.json" && "${HOME_SYNC_FORCE:-}" != 1 ]]; then
      extra=$(jq -rn --slurpfile r "$DST/settings.json" --slurpfile c "$SRC/settings.json" '(($r[0]|keys) - ($c[0]|keys)) | join(", ")' 2>/dev/null)
      if [[ -n "$extra" ]]; then
        echo "중단: 실제 settings.json 에만 있는 키가 있다: $extra" >&2
        echo "  정본으로 가져오려면: jq 로 정본에 합친 뒤 다시 apply (또는 pull 로 파일째 가져오기)" >&2
        echo "  지워도 되면: HOME_SYNC_FORCE=1 $0 apply" >&2
        exit 2
      fi
    fi
    links apply
    for f in "${FILES[@]}"; do
      [[ -e "$SRC/$f" ]] || continue
      if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
        [[ -e "$DST/$f" ]] && cp -p "$DST/$f" "$DST/$f.bak-$(date +%Y%m%d%H%M%S)"
        mkdir -p "$(dirname "$DST/$f")"; cp -p "$SRC/$f" "$DST/$f"; echo "applied $f"
      fi
    done
    write_state
    [[ -f "$DST/settings.json" ]] && { jq -e . "$DST/settings.json" >/dev/null && echo "settings.json JSON OK"; } ;;
  env)
    echo "# harness.env: $([[ -f "$ENVFILE" ]] && echo "$ENVFILE" || echo "(없음 — 기본값)")"
    for k in $(printf '%s\n' "${!HENV[@]}" | sort); do printf '%s=%s\n' "$k" "${HENV[$k]}"; done ;;
  *) echo "usage: $0 [status|diff|pull|apply|env]" >&2; exit 2 ;;
esac
