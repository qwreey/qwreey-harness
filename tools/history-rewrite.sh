#!/bin/sh
# One-time rewrite of this repo's git history before publishing.
# The rules name private details, so they live outside the repo:
#   $RULES/paths.txt      files to drop from every commit (git filter-repo --paths-from-file)
#   $RULES/replace.txt    text replacements (git filter-repo --replace-text)
#   $RULES/verify.regex   grep -E pattern that must match nothing afterwards
#   $RULES/git-filter-repo
# Usage: tools/history-rewrite.sh            build and verify a cleaned clone, change nothing else
#        tools/history-rewrite.sh --apply    also back up, swap the cleaned clone into place, commit the hash map
# Run --apply only with every Claude Code session in this repo closed and no worktrees left.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
RULES=${RULES:-$HOME/.local/share/claude-doctor-history-cleanup}
STAMP=$(date +%Y%m%d-%H%M%S)
WORK=${WORK:-$(dirname "$REPO")/.claude-doctor-rewrite-$STAMP}
BACKUP=${BACKUP:-$HOME/backup/claude-doctor-pre-rewrite-$STAMP.git}
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

say() { printf '%s\n' "$*"; }
die() { printf 'history-rewrite: %s\n' "$*" >&2; exit 1; }

for f in paths.txt replace.txt verify.regex git-filter-repo; do
  [ -f "$RULES/$f" ] || die "missing $RULES/$f"
done

# 1. Preflight: clean tree, main checked out, and for --apply no other worktrees.
cd "$REPO"
# The desk panel rewrites its plan and decision files on its own; commit those, refuse anything else.
desk=$(git status --porcelain -- .claude/plan .claude/archive/plan)
if [ -n "$desk" ]; then
  git add -A -- .claude/plan .claude/archive/plan
  git commit -q -m "desk: 결정·계획 파일(기록 재작성 전)"
  say "committed desk files first"
fi
dirty=$(git status --porcelain --untracked-files=no)
[ -z "$dirty" ] || { printf '%s\n' "$dirty" >&2; die "uncommitted changes above in $REPO; commit them first"; }
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "check out main first"
[ "$APPLY" -eq 0 ] || [ "$(git worktree list | wc -l)" -eq 1 ] || die "remove the other worktrees first (git worktree list)"
before_commits=$(git rev-list --count main)
before_people=$(git log main --format='%an|%ae|%ad|%cn|%cd' | sha256sum)

# 2. Rewrite a fresh clone.
say "clone -> $WORK"
git clone -q --no-local --single-branch --branch main "$REPO" "$WORK"
cd "$WORK"
python3 -I "$RULES/git-filter-repo" --force --invert-paths \
  --paths-from-file "$RULES/paths.txt" --replace-text "$RULES/replace.txt"

# 3. Verify.
after_commits=$(git rev-list --count main)
after_people=$(git log main --format='%an|%ae|%ad|%cn|%cd' | sha256sum)
hits=$(git log main -p | grep -cE -f "$RULES/verify.regex" || true)
say "commits: $before_commits -> $after_commits"
[ "$before_people" = "$after_people" ] && say "authors and dates: same" || say "authors and dates: DIFFER"
say "leftover matches of verify.regex: $hits"
if [ "$hits" -ne 0 ]; then
  git log main -p | grep -nE -f "$RULES/verify.regex" | head -20
  die "leftovers found; add rules to $RULES/replace.txt and run again (clone kept at $WORK)"
fi
[ "$before_people" = "$after_people" ] || die "author or date lines changed; inspect $WORK"
say "pack size: $(du -sh .git | cut -f1)"

if [ "$APPLY" -ne 1 ]; then
  say "dry run done; cleaned clone at $WORK (delete it when done). Re-run with --apply to swap it in."
  exit 0
fi

# 4. Back up the old repo, then swap the cleaned clone into its path.
mkdir -p "$(dirname "$BACKUP")"
git clone -q --mirror "$REPO" "$BACKUP"
say "backup: $BACKUP"
cp .git/filter-repo/commit-map "$WORK.commit-map"
# Keep the old repo's local config (remotes, hooksPath, user) and its untracked and ignored files
# (without exclude flags, ls-files --others lists ignored files too).
cp "$REPO/.git/config" .git/config
(cd "$REPO" && git ls-files --others --directory) > "$WORK.untracked"
while IFS= read -r p; do
  [ -n "$p" ] || continue
  mkdir -p "$WORK/$(dirname "$p")"
  cp -a "$REPO/$p" "$WORK/$(dirname "$p")/" 2>/dev/null || true
done < "$WORK.untracked"
mv "$REPO" "$REPO.old-$STAMP"
mv "$WORK" "$REPO"
cd "$REPO"
git checkout -q main
git reset -q --hard main

# 5. Record the old -> new hash map so old citations stay traceable.
mkdir -p .claude/history
cp "$WORK.commit-map" .claude/history/commit-map-2026-11.txt
cat > .claude/history/README.md <<'EOF'
# history

The git history was rewritten in 2026-11 before publishing: one private project's internals and a few sentences were removed from every commit, and an old vendored node_modules folder was dropped. Commit hashes changed. `commit-map-2026-11.txt` maps each old hash (left) to its new hash (right); records and session logs written before then cite old hashes.
EOF
git add .claude/history
git commit -q -m "기록 재작성의 옛 해시 -> 새 해시 표(commit-map)와 설명

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
say "done. Old repo kept at $REPO.old-$STAMP (delete it after checking), backup at $BACKUP."
say "Next: restart Claude Code here, check hooks run, then push main only."
