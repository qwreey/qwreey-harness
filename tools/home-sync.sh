#!/usr/bin/env bash
# claude-doctor/home/.claude (정본) <-> ~/.claude (실제) 동기화 도우미.
#
#   tools/home-sync.sh status   관리 대상 파일마다 같음/다름/한쪽에만 있음을 표시한다 (기본 동작)
#   tools/home-sync.sh diff     정본에서 실제로 가는 diff 를 보여준다 (apply 하면 바뀔 내용)
#   tools/home-sync.sh pull     실제 -> 정본으로 가져온다. /config 등으로 실제 쪽만 바뀐 경우에 쓴다
#   tools/home-sync.sh apply    정본 -> 실제로 복사한다. 사용자가 diff 를 검토한 뒤 직접 실행한다
#   tools/home-sync.sh env      harness.env 를 푼 값(MANIFEST 링크 대상에 쓰이는 변수)을 보여준다
#
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
    done ;;
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
    links apply
    for f in "${FILES[@]}"; do
      [[ -e "$SRC/$f" ]] || continue
      if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
        [[ -e "$DST/$f" ]] && cp -p "$DST/$f" "$DST/$f.bak-$(date +%Y%m%d%H%M%S)"
        mkdir -p "$(dirname "$DST/$f")"; cp -p "$SRC/$f" "$DST/$f"; echo "applied $f"
      fi
    done
    [[ -f "$DST/settings.json" ]] && { jq -e . "$DST/settings.json" >/dev/null && echo "settings.json JSON OK"; } ;;
  env)
    echo "# harness.env: $([[ -f "$ENVFILE" ]] && echo "$ENVFILE" || echo "(없음 — 기본값)")"
    for k in $(printf '%s\n' "${!HENV[@]}" | sort); do printf '%s=%s\n' "$k" "${HENV[$k]}"; done ;;
  *) echo "usage: $0 [status|diff|pull|apply|env]" >&2; exit 2 ;;
esac
