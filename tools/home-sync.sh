#!/usr/bin/env bash
# claude-doctor/home/.claude (정본) <-> ~/.claude (실제) 동기화 도우미.
#
#   tools/home-sync.sh status   관리 대상 파일마다 같음/다름/한쪽에만 있음을 표시한다 (기본 동작)
#   tools/home-sync.sh diff     정본에서 실제로 가는 diff 를 보여준다 (apply 하면 바뀔 내용)
#   tools/home-sync.sh pull     실제 -> 정본으로 가져온다. /config 등으로 실제 쪽만 바뀐 경우에 쓴다
#   tools/home-sync.sh apply    정본 -> 실제로 복사한다. 사용자가 diff 를 검토한 뒤 직접 실행한다
#
# 관리 대상 목록은 home/MANIFEST 에 있다.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/home/.claude"
DST="${CLAUDE_HOME:-$HOME/.claude}"
mapfile -t FILES < <(grep -v '^\s*#' "$ROOT/home/MANIFEST" | grep -v '^\s*$' | grep -v '^link ')
# 링크 항목: "link <~/.claude 기준 경로> <절대 대상>"
mapfile -t LINKS < <(grep '^link ' "$ROOT/home/MANIFEST" | cut -d' ' -f2-)

links() {
  local mode=$1 l path target cur
  for l in "${LINKS[@]}"; do
    path=${l%% *}; target=${l#* }
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
  *) echo "usage: $0 [status|diff|pull|apply]" >&2; exit 2 ;;
esac
