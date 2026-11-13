#!/usr/bin/env bash
# delegate.sh - hand one task to another model family (agy=Gemini, codex=OpenAI) in isolation.
#
#   delegate.sh run <agy|codex> <name> <prompt file> [--repo <key|path>] [--mode worktree|empty]
#                   [--ref <commit>] [--model M] [--effort low|medium|high] [--timeout seconds]
#   delegate.sh collect <agy|codex> <name> [--repo ...]     # keep the result under <workspace>/runs/
#   delegate.sh remove  <agy|codex> <name> [--repo ...] [--discard] [--delete-branch]
#   delegate.sh list    [--repo ...|--all]                  # both backends
#   delegate.sh gc      [--repo ...|--all] [--days N] [--apply]   # preview only unless --apply
#   delegate.sh doctor  [--repo ...|--all]
#   delegate.sh register <repository path> [key]
#
# Lifecycle: run -> (main reads and verifies) -> collect -> remove. gc finds what is left.
#
# Isolation. `agy --sandbox` and codex `-s read-only` do not block reads or writes outside the cwd, and
# `unshare -m` is not permitted in this container, so the lines of defense are:
#   - The task runs under `setpriv` as an unprivileged uid chosen per repository (registry.tsv); no two repositories share one.
#   - Only the worktree, its .git/worktrees/<name> admin dir and the per-task HOME are owned by that uid, so it cannot
#     write the main working tree or .git/objects, cannot commit, and has nothing new to push. A pre-push hook
#     (GIT_CONFIG_*) is the second line.
#   - The worktree is detached (no branch is created, so removing it needs no branch deletion).
#   - HOME is per task (<workspace>/.homes/<name>) with a fresh copy of the credentials only: a shared HOME let two
#     concurrent runs delete each other's copy. remove deletes it.
#   - PATH is the tools pinned in the repository's mise.toml plus /usr/bin:/bin; /usr/local/bin is left out because
#     the Studio tools live there.
#   - Everything runs under `choom -n 1000` so the OOM killer picks it before the main session; agy's own Bash is
#     invisible to the PreToolUse hooks, so this is the only lever.
#   - HEAD and a status hash of the main repository are compared before and after the run and written to guard.txt.
#   - The script re-runs itself from a temp copy: bash reads a script incrementally, so editing the original while a
#     task runs would otherwise break the running copy.
set -euo pipefail

if [[ -z "${DELEGATE_REEXEC:-}" ]]; then
	self_dir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
	tmp=$(mktemp --suffix=.sh /tmp/delegate.XXXXXX)
	cp "$(readlink -f "$0")" "$tmp"
	DELEGATE_REEXEC=$tmp DELEGATE_SELF_DIR=$self_dir exec bash "$tmp" "$@"
fi
trap 'rm -f "$DELEGATE_REEXEC"' EXIT
SKILL_DIR=$(dirname "$DELEGATE_SELF_DIR")
TEMPLATES=$SKILL_DIR/templates

# Read one key of the harness environment layers (harness_env.load_layers: user < repo .claude/harness.env < repo
# .claude/harness.local.env < environment) through the loader the hooks use: HARNESS_ENV_LIB if set, else the installed
# ~/.claude/lib copy, else the byte copy next to this script.
harness_value() { # $1 = key
	python3 -I -c '
import os, sys
sys.path.insert(0, sys.argv[1])
import harness_env
he = harness_env if os.environ.get("HARNESS_ENV_LIB") else harness_env.installed()
print(he.load_layers(he.project_dir(os.getcwd())).get(sys.argv[2], ""))
' "${HARNESS_ENV_LIB:-$DELEGATE_SELF_DIR}" "$1" 2>/dev/null || true
}

# The registry is edited in place, so a copy inside a plugin cache would be stale per version.
# Order: DELEGATE_REGISTRY, HARNESS_DELEGATE_REGISTRY (environment or harness.env), the copy next to the skill.
REGISTRY=${DELEGATE_REGISTRY:-}
[[ -n "$REGISTRY" ]] || REGISTRY=$(harness_value HARNESS_DELEGATE_REGISTRY)
[[ -n "$REGISTRY" ]] || REGISTRY=$SKILL_DIR/registry.tsv

INSTALLS=${HARNESS_TOOL_INSTALLS:-$(harness_value HARNESS_TOOL_INSTALLS)}
INSTALLS=${INSTALLS:-/code/.local/share/mise/installs}
AGY_BIN=${DELEGATE_AGY_BIN:-$INSTALLS/antigravity-cli/latest/agy}
CODEX_BIN=${DELEGATE_CODEX_BIN:-$INSTALLS/codex/latest/bin/codex}
GEMINI_SRC=${DELEGATE_GEMINI_SRC:-/code/.gemini}
CODEX_AUTH=${DELEGATE_CODEX_AUTH:-/code/.codex/auth.json}
MAX_CONCURRENT=${DELEGATE_MAX_CONCURRENT:-1}   # per backend, summed over all repositories: the token limit is per user
SECRETS_PROBE=(/code/.claude/.credentials.json /code/.git-credentials /code/.ssh)

die() { echo "delegate: $*" >&2; exit 2; }
note() { echo "delegate: $*" >&2; }

# ---------- registry ----------
rows() { grep -v '^[[:space:]]*#' "$REGISTRY" | grep -v '^[[:space:]]*$' || true; }
row_by_root() { rows | awk -F'\t' -v r="$1" '$2 == r'; }
row_by_key() { rows | awk -F'\t' -v k="$1" '$1 == k'; }

resolve_repo() { # $1 = key|path|"" -> KEY ROOT AGY_UID SETUP
	local arg=${1:-} row=""
	if [[ -n "$arg" && ! "$arg" =~ / ]]; then
		row=$(row_by_key "$arg")
	else
		local dir=${arg:-$PWD} common
		common=$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || die "$dir is not a git repository"
		# Resolves to the main repository even from inside Claude's .claude/worktrees/* or another worktree.
		row=$(row_by_root "$(dirname "$common")")
	fi
	[[ -n "$row" ]] || die "repository not in the registry ($REGISTRY): ${arg:-$PWD} - register it first with 'delegate.sh register <path>'"
	IFS=$'\t' read -r KEY ROOT AGY_UID SETUP _ <<<"$row"
	[[ "$AGY_UID" =~ ^[0-9]+$ ]] || die "malformed uid: $row"
}
base_of() { echo "$(dirname "$ROOT")/$KEY-$1"; } # $1 = backend

check_name() { [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "name must match [a-z0-9-]: $1"; }
check_backend() { [[ "$1" == agy || "$1" == codex ]] || die "backend must be agy|codex: $1"; }

tool_path() { # bin dirs of the tools pinned by the repository's mise.toml
	local names
	names=$(cd "$ROOT" && timeout 30 mise ls --current --json 2>/dev/null | python3 -I -c '
import json, sys, os
root = sys.argv[1]
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k, v in d.items():
    for e in v:
        if e.get("installed") and e.get("source", {}).get("path", "").startswith(root + os.sep): print(k)
' "$ROOT") || true
	[[ -n "$names" ]] || return 0
	# shellcheck disable=SC2086
	(cd "$ROOT" && timeout 30 mise bin-paths $names 2>/dev/null) | paste -sd: -
}

live_runs() { # $1 = backend -> number of live tasks over all repositories
	local n=0 k r u s _ b d
	while IFS=$'\t' read -r k r u s _; do
		b="$(dirname "$r")/$k-$1"
		for d in "$b"/*/.delegate/pid; do
			[[ -f "$d" ]] && kill -0 "$(cat "$d")" 2>/dev/null && n=$((n + 1))
		done
	done < <(rows)
	echo "$n"
}

# ---------- run ----------
cmd_run() {
	local backend=$1 name=$2 promptFile=$3; shift 3
	check_backend "$backend"; check_name "$name"
	[[ -f "$promptFile" ]] || die "prompt file not found: $promptFile"
	promptFile=$(readlink -f "$promptFile")
	local repo="" mode="" ref=HEAD model="" effort=medium timeoutSec=3600
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--repo) repo=$2; shift 2 ;;
		--mode) mode=$2; shift 2 ;;
		--ref) ref=$2; shift 2 ;;
		--model) model=$2; shift 2 ;;
		--effort) effort=$2; shift 2 ;;
		--timeout) timeoutSec=$2; shift 2 ;;
		*) die "unknown option $1" ;;
		esac
	done
	resolve_repo "$repo"
	[[ -n "$mode" ]] || { [[ $backend == agy ]] && mode=worktree || mode=empty; }
	[[ "$mode" == worktree || "$mode" == empty ]] || die "--mode must be worktree|empty"
	[[ -n "$model" ]] || { [[ $backend == agy ]] && model=gemini-3.8-flash-high || model=gpt-6-luna; }
	if [[ $backend == agy ]]; then [[ -x "$AGY_BIN" ]] || die "agy not found: $AGY_BIN"; else [[ -x "$CODEX_BIN" ]] || die "codex not found: $CODEX_BIN"; fi
	if [[ $backend == codex && $mode == worktree && "${DELEGATE_CODEX_SANDBOX:-read-only}" == read-only ]]; then
		die "codex worktree mode cannot run a shell on this host (bubblewrap cannot create a namespace under an unprivileged uid). Use --mode empty with the context in the prompt; turning the sandbox off with DELEGATE_CODEX_SANDBOX=danger-full-access leaves the uid as the only isolation and is the user's decision"
	fi
	[[ $backend == agy && $mode == empty ]] && note "warning: agy empty mode is unverified (only worktree mode has been exercised)"

	local BASE WT HOMES HOOKS H D admin=""
	BASE=$(base_of "$backend"); WT=$BASE/$name; HOMES=$BASE/.homes; HOOKS=$BASE/.hooks; H=$HOMES/$name; D=$WT/.delegate
	mkdir -p "$BASE" "$HOMES" "$HOOKS" "$BASE/runs"
	exec 9>"/tmp/delegate-$backend.lock"; flock 9
	[[ -e "$WT" ]] && die "$WT already exists - use another name, or collect/remove it"
	local live; live=$(live_runs "$backend")
	(( live < MAX_CONCURRENT )) || die "$live $backend task(s) already running (limit $MAX_CONCURRENT, DELEGATE_MAX_CONCURRENT adjusts it - the token limit is the user's)"

	printf '#!/bin/sh\necho "push refused: delegate workspace" >&2\nexit 1\n' >"$HOOKS/pre-push"; chmod 755 "$HOOKS/pre-push"

	local commit; commit=$(git -C "$ROOT" rev-parse --verify "$ref^{commit}") || die "commit not found: $ref"
	if [[ $mode == worktree ]]; then
		git -C "$ROOT" worktree add -q --detach "$WT" "$commit"
		# git may number the admin dir (same basename in another workspace), so ask for the real path.
		# After the chown git refuses the repo as dubious ownership, so ask now.
		admin=$(git -C "$WT" rev-parse --path-format=absolute --git-dir)
		if [[ "$SETUP" != - && -n "$SETUP" ]]; then
			(cd "$WT" && bash -c "$SETUP" >/dev/null 2>&1) || note "warning: setup failed: $SETUP"
		fi
	else
		mkdir -p "$WT"
	fi
	mkdir -p "$D"
	echo $$ >"$D/pid"
	flock -u 9; exec 9>&-

	# HOME per task, with fresh credentials (the user's own use may have refreshed them)
	rm -rf "${H:?}"; mkdir -p "$H"
	if [[ $backend == agy ]]; then
		cp -r "$GEMINI_SRC" "$H/.gemini"
		# The user's own agy history (including other repositories') must not reach the task: copying it whole put
		# other tasks' brain/ and conversations/ where the task uid could read them. Credentials
		# (antigravity-oauth-token), settings.json and config/ stay. If agy cannot authenticate with the trimmed HOME,
		# set DELEGATE_AGY_FULL_HOME=1 to copy everything.
		if [[ -z "${DELEGATE_AGY_FULL_HOME:-}" ]]; then
			local a=$H/.gemini/antigravity-cli
			rm -rf "${a:?}/brain" "${a:?}/conversations" "${a:?}/annotations" "${a:?}/implicit" "${a:?}/log" "${a:?}/crashes" \
				"${a:?}/history.jsonl" "${a:?}"/conversation_summaries.db* "${a:?}/jetbox_summaries_proto.pb"
		fi
	else
		mkdir -p "$H/.codex"; cp "$CODEX_AUTH" "$H/.codex/auth.json"; chmod 600 "$H/.codex/auth.json"
	fi

	# prompt = common preamble + task
	local report
	if [[ $mode == worktree && $backend == agy ]]; then report=$WT/REPORT.md; else report=$D/report.md; fi
	{
		python3 -I - "$TEMPLATES/preamble-$mode.md" "$WT" "$ROOT" "$KEY" "$report" <<-'PY'
		import sys
		t = open(sys.argv[1], encoding="utf-8").read()
		for k, v in zip(("{{WT}}", "{{ROOT}}", "{{KEY}}", "{{REPORT}}"), sys.argv[2:]): t = t.replace(k, v)
		sys.stdout.write(t)
		PY
		cat "$promptFile"
	} >"$D/prompt.md"
	cat >"$D/meta.txt" <<-EOF
	backend: $backend
	mode: $mode
	repo: $KEY ($ROOT)
	uid: $AGY_UID
	model: $model
	effort: $effort
	ref: $ref -> $commit
	prompt-source: $promptFile
	started: $(date -Is)
	EOF

	chown -R "$AGY_UID:$AGY_UID" "$WT" "$H"
	[[ $mode == worktree ]] && chown -R "$AGY_UID:$AGY_UID" "$admin"
	chown root:root "$D/meta.txt" "$D/pid"

	local tp; tp=$(tool_path)
	local before_head before_status rc
	before_head=$(git -C "$ROOT" rev-parse HEAD)
	before_status=$(git -C "$ROOT" status --porcelain=v1 | sha1sum)
	note "start $backend/$name ($model, $mode) $(date -Is) - $WT"

	# The environment starts empty so token-like variables of the root session do not leak. If agy or codex cannot find
	# something it needs, DELEGATE_KEEP_ENV=1 passes the environment through.
	local envi=-i; [[ -n "${DELEGATE_KEEP_ENV:-}" ]] && envi=
	local -a envs=(env $envi HOME="$H" PATH="${tp:+$tp:}/usr/bin:/bin" LANG=C.UTF-8 TERM=dumb
		GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$HOOKS")
	local -a priv=(choom -n 1000 -- setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups)
	set +e
	if [[ $backend == agy ]]; then
		(cd "$WT" && "${priv[@]}" "${envs[@]}" timeout $((timeoutSec + 60)) "$AGY_BIN" --model "$model" \
			--dangerously-skip-permissions --print-timeout "${timeoutSec}s" -p "$(cat "$D/prompt.md")") >"$D/stdout.txt" 2>&1
	else
		# The codex built-in sandbox (bubblewrap) cannot create a user namespace under an unprivileged uid on this host
		# (kernel.unprivileged_userns_clone=0), so with read-only no shell runs at all and worktree mode is useless.
		# Turning the sandbox off would leave the uid as the only isolation; that is the user's decision, so the default
		# is to refuse and DELEGATE_CODEX_SANDBOX is the only way to open it.
		local sandbox=${DELEGATE_CODEX_SANDBOX:-read-only}
		# -o (last message) goes to its own file: in worktree mode the model writes $report itself, and the same file would be overwritten.
		local last=$report; [[ $mode == worktree ]] && last=$D/last-message.md
		(cd "$WT" && "${priv[@]}" "${envs[@]}" CODEX_HOME="$H/.codex" timeout $((timeoutSec + 60)) "$CODEX_BIN" exec \
			-m "$model" -c model_reasoning_effort="$effort" -c approval_policy=never -s "$sandbox" \
			--skip-git-repo-check --ephemeral --ignore-user-config --color never -C "$WT" -o "$last" - <"$D/prompt.md") >"$D/stdout.txt" 2>&1
	fi
	rc=$?
	set -e
	# If the model did not write the report file, fall back to the last message (agy empty mode has no instruction to
	# write a file; the answer arrives on stdout).
	if [[ ! -s "$report" ]]; then
		if [[ $backend == codex && -s "${last:-}" && "$last" != "$report" ]]; then cp "$last" "$report"
		elif [[ $backend == agy && $mode == empty && -s "$D/stdout.txt" ]]; then cp "$D/stdout.txt" "$report"; fi
	fi

	local after_head after_status
	after_head=$(git -C "$ROOT" rev-parse HEAD)
	after_status=$(git -C "$ROOT" status --porcelain=v1 | sha1sum)
	{
		echo "exit: $rc"
		echo "finished: $(date -Is)"
		if [[ "$before_head" == "$after_head" && "$before_status" == "$after_status" ]]; then
			echo "main repo: unchanged"
		else
			echo "main repo: CHANGED during the run (HEAD $before_head -> $after_head; status hash differs) - check whether the main session or the user did it"
		fi
		if [[ $mode == worktree ]]; then
			echo "worktree HEAD: $(git -c safe.directory="$WT" -C "$WT" rev-parse HEAD) (base $commit)"
			echo "worktree changes:"
			git -c safe.directory="$WT" -C "$WT" status --porcelain=v1 | grep -v -e '^?? .delegate/' -e '^?? REPORT.md$' || true
		fi
	} >"$D/guard.txt"
	rm -f "$D/pid"
	echo "$rc" >"$D/exit"
	note "done $backend/$name - exit $rc"
	cat "$D/guard.txt"
	if [[ -s "$report" ]]; then echo "report: $report ($(wc -c <"$report") bytes)"; else echo "report: MISSING - see $D/stdout.txt"; fi
	echo "next: main reads and verifies -> delegate.sh collect $backend $name --repo $KEY -> delegate.sh remove $backend $name --repo $KEY"
}

# ---------- collect / remove ----------
locate() { # backend name repo -> BASE WT D
	check_backend "$1"; check_name "$2"; resolve_repo "${3:-}"
	BASE=$(base_of "$1"); WT=$BASE/$2; D=$WT/.delegate
	[[ -d "$WT" ]] || die "not found: $WT"
}

cmd_collect() {
	local backend=$1 name=$2; shift 2; local repo=""
	[[ "${1:-}" == --repo ]] && repo=$2
	locate "$backend" "$name" "$repo"
	[[ -f "$D/pid" ]] && kill -0 "$(cat "$D/pid")" 2>/dev/null && die "still running: $backend/$name"
	[[ -f "$D/exit" ]] || note "warning: no exit record (abnormal end, or a workspace from an older script); collecting what exists"
	local out; out=$BASE/runs/$(date +%Y%m%d-%H%M)-$name
	mkdir -p "$out"
	for f in prompt.md meta.txt guard.txt stdout.txt report.md last-message.md exit; do [[ -f "$D/$f" ]] && cp "$D/$f" "$out/"; done
	[[ -f "$WT/REPORT.md" ]] && cp "$WT/REPORT.md" "$out/report.md"
	# agy writes its probes to brain/<conversation>/scratch under HOME, not to the worktree. That is outside the guard's
	# worktree change list and disappears when remove deletes HOME, so the probes the report calls "measured" and the
	# transcript are kept here.
	local brain=$BASE/.homes/$name/.gemini/antigravity-cli/brain conv
	if [[ $backend == agy && -d "$brain" ]]; then
		for conv in "$brain"/*/; do
			conv=${conv%/}; [[ -d "$conv" ]] || continue
			# Only this task's conversations: with a full HOME copy the user's other agy conversations are here too.
			[[ "$conv" -nt "$D/meta.txt" || -n "$(find "$conv" -newer "$D/meta.txt" -print -quit)" ]] || continue
			mkdir -p "$out/agy/$(basename "$conv")"
			[[ -d "$conv/scratch" ]] && cp -r "$conv/scratch" "$out/agy/$(basename "$conv")/"
			[[ -f "$conv/.system_generated/logs/transcript.jsonl" ]] && cp "$conv/.system_generated/logs/transcript.jsonl" "$out/agy/$(basename "$conv")/"
		done
	fi
	if git -c safe.directory="$WT" -C "$WT" rev-parse --git-dir >/dev/null 2>&1; then
		# Keep what the task changed in the worktree (experiment diff), new files included, without .delegate/ and the report.
		git -c safe.directory="$WT" -C "$WT" add -N --all -- . ':!.delegate' ':!REPORT.md' 2>/dev/null || true
		git -c safe.directory="$WT" -C "$WT" diff --binary -- . ':!.delegate' ':!REPORT.md' >"$out/diff.patch" || true
		[[ -s "$out/diff.patch" ]] || rm -f "$out/diff.patch"
	fi
	chown -R root:root "$out"
	echo "$out" >"$D/collected"
	echo "collected: $out"
	ls -la "$out"
}

cmd_remove() {
	local backend=$1 name=$2; shift 2; local repo="" discard=0 delbranch=0
	while [[ $# -gt 0 ]]; do
		case "$1" in --repo) repo=$2; shift 2 ;; --discard) discard=1; shift ;; --delete-branch) delbranch=1; shift ;; *) die "unknown option $1" ;; esac
	done
	locate "$backend" "$name" "$repo"
	[[ -f "$D/pid" ]] && kill -0 "$(cat "$D/pid")" 2>/dev/null && die "still running: $backend/$name"
	if [[ ! -f "$D/collected" && $discard == 0 ]]; then
		# Workspaces from older scripts (.agy/ and AGY_REPORT.md) have a shape collect does not know; a person decides whether to keep them.
		die "not collected yet - run 'delegate.sh collect $backend $name' first, or pass --discard to throw it away"
	fi
	local branch=""
	if git -C "$ROOT" worktree list --porcelain | grep -qx "worktree $WT"; then
		branch=$(git -C "$ROOT" worktree list --porcelain | awk -v w="worktree $WT" '$0==w{f=1;next} f&&/^branch /{print substr($2,12);exit} f&&/^$/{exit}')
		git -C "$ROOT" worktree remove --force "$WT"
	else
		rm -rf "${WT:?}"
	fi
	rm -rf "${BASE:?}/.homes/${name:?}"
	if [[ -n "$branch" ]]; then
		if [[ $delbranch == 1 ]]; then git -C "$ROOT" branch -D "$branch"; else note "branch '$branch' (old style) left in place; --delete-branch removes it, after the user confirms"; fi
	fi
	echo "removed: $WT"
}

# ---------- list / gc ----------
du_h() { du -sh "$1" 2>/dev/null | cut -f1; }

state_of() { # workspace dir -> state
	local w=$1
	if [[ -f "$w/.delegate/pid" ]] && kill -0 "$(cat "$w/.delegate/pid")" 2>/dev/null; then echo running
	elif [[ -f "$w/.delegate/collected" ]]; then echo collected
	elif [[ -f "$w/.delegate/exit" ]]; then echo finished
	elif [[ -d "$w/.agy" ]]; then echo legacy
	elif [[ -f "$w/answer.md" || -f "$w/prompt.md" ]]; then echo legacy-record
	else echo unknown; fi
}

for_repos() { # $1 = --all|key|path|"" ; rest = callback
	local sel=$1; shift
	if [[ "$sel" == --all ]]; then
		local k _
		while IFS=$'\t' read -r k _; do resolve_repo "$k"; "$@"; done < <(rows)
	else resolve_repo "$sel"; "$@"; fi
}

list_one() {
	local b BASE w
	for b in agy codex; do
		BASE=$(base_of $b); [[ -d "$BASE" ]] || continue
		echo "== $BASE ($(du_h "$BASE"))"
		for w in "$BASE"/*/; do
			w=${w%/}; [[ -d "$w" && $(basename "$w") != runs ]] || continue
			printf '  %-28s %-10s %6s  %s\n' "$(basename "$w")" "$(state_of "$w")" "$(du_h "$w")" "$(stat -c %y "$w" | cut -c1-16)"
		done
		[[ -d "$BASE/runs" ]] && echo "  runs/: $(find "$BASE/runs" -mindepth 1 -maxdepth 1 -type d | wc -l) ($(du_h "$BASE/runs"))"
		[[ -d "$BASE/.home" ]] && echo "  .home (old shared HOME): $(du_h "$BASE/.home")"
	done
	git -C "$ROOT" worktree prune --dry-run -v 2>&1 | sed 's/^/  prune? /' || true
}

GC_DAYS=14; GC_APPLY=0
gc_one() {
	local b BASE w n st age
	for b in agy codex; do
		BASE=$(base_of $b); [[ -d "$BASE" ]] || continue
		# The pid record only covers tasks of this script; a process whose cwd is inside the workspace is checked directly.
		local busy=0 pc
		for pc in /proc/[0-9]*/cwd; do [[ "$(readlink "$pc" 2>/dev/null)" == "$BASE"/* ]] && { busy=1; break; }; done
		if [[ $busy == 1 ]]; then echo "held       $KEY-$b (a process is running inside this workspace - retry after it ends)"; continue; fi
		for w in "$BASE"/*/; do
			w=${w%/}; n=$(basename "$w"); [[ -d "$w" && $n != runs ]] || continue
			st=$(state_of "$w"); age=$(( ($(date +%s) - $(stat -c %Y "$w")) / 86400 ))
			case $st in
			collected) echo "delete     $KEY-$b/$n (collected, ${age}d, $(du_h "$w"))"
				[[ $GC_APPLY == 1 ]] && (cmd_remove "$b" "$n" --repo "$KEY") ;;
			finished) [[ $age -ge $GC_DAYS ]] && echo "check      $KEY-$b/$n (finished but not collected, ${age}d) - collect it or remove --discard" ;;
			legacy-record) echo "old record $KEY-$b/$n (prompt/answer - candidate to move into runs/; --apply leaves it alone)" ;;
			legacy) echo "check      $KEY-$b/$n (workspace of an older script, ${age}d, $(du_h "$w")) - decide whether to keep AGY_REPORT.md, then remove --discard" ;;
			running) echo "running    $KEY-$b/$n" ;;
			*) echo "check      $KEY-$b/$n (unknown shape - inspect by hand)" ;;
			esac
		done
		for h in "$BASE"/.homes/*/; do
			[[ -d "$h" ]] || continue; n=$(basename "$h")
			[[ -d "$BASE/$n" ]] && continue
			echo "delete     $KEY-$b/.homes/$n (HOME without an owner, $(du_h "$h"))"; [[ $GC_APPLY == 1 ]] && rm -rf "${h:?}"
		done
		if [[ -d "$BASE/.home" ]]; then
			echo "delete     $KEY-$b/.home (old shared HOME - accumulates conversation history, $(du_h "$BASE/.home"))"; [[ $GC_APPLY == 1 ]] && rm -rf "${BASE:?}/.home"
		fi
		[[ -d "$BASE/runs" ]] && find "$BASE/runs" -mindepth 1 -maxdepth 1 -type d -mtime +180 -printf 'old        %p (180d+, kept record - a person decides whether to delete)\n'
	done
	local p; p=$(git -C "$ROOT" worktree prune --dry-run -v 2>&1 || true)
	if [[ -n "$p" ]]; then echo "prune      $KEY: $p"; [[ $GC_APPLY == 1 ]] && git -C "$ROOT" worktree prune -v; fi
	return 0
}

# ---------- doctor / register ----------
doctor_one() {
	echo "== $KEY  root=$ROOT  uid=$AGY_UID"
	[[ -d "$ROOT/.git" || -f "$ROOT/.git" ]] && echo "  ok   git repository" || echo "  FAIL not a git repository"
	getent passwd "$AGY_UID" >/dev/null && echo "  FAIL uid $AGY_UID collides with a real user" || echo "  ok   uid is not in /etc/passwd"
	local can_w
	can_w=$(setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups sh -c "test -w '$ROOT' && echo yes || echo no")
	[[ $can_w == no ]] && echo "  ok   uid cannot write the main working tree" || echo "  FAIL uid can write the main working tree"
	local s
	for s in "${SECRETS_PROBE[@]}"; do
		[[ -e "$s" ]] || continue
		setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups sh -c "test -r '$s'" \
			&& echo "  FAIL uid can read a secret: $s" || echo "  ok   cannot read: $s"
	done
	[[ -f "$ROOT/AGENTS.md" ]] && echo "  ok   AGENTS.md present" || echo "  WARN no AGENTS.md (entry point for external models; see templates/AGENTS.md.template)"
	[[ -f "$ROOT/GEMINI.md" && -f "$ROOT/AGENTS.md" ]] && echo "  WARN GEMINI.md and AGENTS.md both present - agy loads both"
	[[ -f "$ROOT/.claude/tools/agy-delegate.sh" ]] && echo "  INFO old per-repository copy left: .claude/tools/agy-delegate.sh (superseded by this script)"
	local tp; tp=$(tool_path); echo "  PATH tools: ${tp:-(none - no pins in mise.toml)}"
}

doctor_global() {
	echo "== registry $REGISTRY"
	[[ -f "$REGISTRY" ]] || { echo "  FAIL registry file missing"; return 0; }
	local d
	d=$(rows | cut -f3 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   no duplicate uid" || echo "  FAIL duplicate uid: $d"
	d=$(rows | cut -f1 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   no duplicate key" || echo "  FAIL duplicate key: $d"
	d=$(rows | cut -f2 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   no duplicate root" || echo "  FAIL duplicate root: $d"
	[[ -x "$AGY_BIN" ]] && echo "  ok   agy $AGY_BIN" || echo "  WARN agy not found: $AGY_BIN"
	[[ -x "$CODEX_BIN" ]] && echo "  ok   codex $CODEX_BIN" || echo "  WARN codex not found: $CODEX_BIN"
}

cmd_register() {
	local root; root=$(readlink -f "${1:?repository path}"); local key=${2:-$(basename "$root")}
	git -C "$root" rev-parse --git-dir >/dev/null 2>&1 || die "not a git repository: $root"
	[[ -z "$(row_by_root "$root")" ]] || die "already registered: $root"
	[[ -z "$(row_by_key "$key")" ]] || die "key already exists: $key"
	local uid=61000
	while rows | cut -f3 | grep -qx "$uid" || getent passwd "$uid" >/dev/null; do uid=$((uid + 1)); done
	printf '%s\t%s\t%s\t-\t%s\n' "$key" "$root" "$uid" "registered $(date +%F)" >>"$REGISTRY"
	echo "registered: $key $root uid=$uid"
}

# ---------- main ----------
cmd=${1:-}; shift || true
case "$cmd" in
run) [[ $# -ge 3 ]] || die "usage: run <agy|codex> <name> <prompt file> [options]"; cmd_run "$@" ;;
collect) [[ $# -ge 2 ]] || die "usage: collect <agy|codex> <name> [--repo R]"; cmd_collect "$@" ;;
remove) [[ $# -ge 2 ]] || die "usage: remove <agy|codex> <name> [--repo R] [--discard] [--delete-branch]"; cmd_remove "$@" ;;
list) sel=""; [[ "${1:-}" == --repo ]] && sel=$2; [[ "${1:-}" == --all ]] && sel=--all; for_repos "$sel" list_one ;;
gc)
	sel=""
	while [[ $# -gt 0 ]]; do
		case "$1" in --repo) sel=$2; shift 2 ;; --all) sel=--all; shift ;; --days) GC_DAYS=$2; shift 2 ;; --apply) GC_APPLY=1; shift ;; *) die "unknown option $1" ;; esac
	done
	[[ $GC_APPLY == 1 ]] || echo "(preview - pass --apply to delete)"
	for_repos "$sel" gc_one ;;
doctor) doctor_global; sel=""; [[ "${1:-}" == --repo ]] && sel=$2; [[ "${1:-}" == --all ]] && sel=--all; for_repos "$sel" doctor_one ;;
register) cmd_register "$@" ;;
*) sed -n '2,13p' "$DELEGATE_REEXEC" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
