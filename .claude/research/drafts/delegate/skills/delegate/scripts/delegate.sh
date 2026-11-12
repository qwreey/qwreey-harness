#!/usr/bin/env bash
# delegate.sh — 다른 모델 계열(agy=Gemini, codex=OpenAI)에게 과제 하나를 격리해서 맡긴다.
#
#   delegate.sh run <agy|codex> <이름> <프롬프트 파일> [--repo <key|경로>] [--mode worktree|empty]
#                   [--ref <커밋>] [--model M] [--effort low|medium|high] [--timeout 초]
#   delegate.sh collect <agy|codex> <이름> [--repo …]     # 결과를 <작업공간>/runs/ 로 보존
#   delegate.sh remove  <agy|codex> <이름> [--repo …] [--discard] [--delete-branch]
#   delegate.sh list    [--repo …]                         # 모든 백엔드
#   delegate.sh gc      [--repo …|--all] [--days N] [--apply]   # 기본은 무엇을 지울지 보여주기만
#   delegate.sh doctor  [--repo …|--all]
#   delegate.sh register <저장소 경로> [key]
#
# 수명 주기: run → (메인이 읽고 검증) → collect → remove.  gc 는 남은 것을 찾아 준다.
#
# 격리 (quad 2026-10-02/03 실측. `agy --sandbox` 와 codex `-s read-only` 는 cwd 밖 읽기·쓰기를 막아 주지 않았고,
# 이 컨테이너에서 `unshare -m` 은 권한이 없다):
#   - 과제는 저장소마다 정한 무권한 uid(registry.tsv)로 `setpriv` 실행. 저장소끼리 uid 가 겹치지 않는다.
#   - worktree 와 그 .git/worktrees/<이름>, 작업공간의 HOME 만 그 uid 소유 → 메인 작업 트리·.git/objects 에 못 씀
#     → 커밋 불가 → 새로 push 할 것도 없음. pre-push 훅(GIT_CONFIG_*)이 두 번째 줄.
#   - worktree 는 detached(브랜치를 만들지 않음 — 지울 때 브랜치 삭제가 필요 없게, table-sim 판).
#   - HOME 은 과제마다 따로(<작업공간>/.homes/<이름>), 인증만 새로 복사(stl-luau·tbox 판 — 공유 HOME 은 동시 실행 때
#     복사가 서로를 지웠다). remove 가 지운다.
#   - PATH 는 저장소 mise.toml 의 핀 도구 + /usr/bin:/bin 뿐(/usr/local/bin 의 Studio 도구 제외 — table-sim 판).
#   - 전체가 `choom -n 1000`(OOM 이 나면 메인 세션보다 먼저 죽게 — quad·tbox·table-sim 판. stl-luau 판에는 빠져 있었다).
#   - 실행 전후 메인 저장소의 HEAD 와 status 해시를 비교해 guard.txt 에 적는다.
#   - 이 스크립트는 자기 사본으로 다시 실행된다: 도는 중에 원본을 고쳐도 bash 의 점진 읽기가 깨지지 않는다
#     (stl-luau 2026-10-02 `syntax error near unexpected token` 사고).
set -euo pipefail

if [[ -z "${DELEGATE_REEXEC:-}" ]]; then
	self_dir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
	tmp=$(mktemp --suffix=.sh /tmp/delegate.XXXXXX)
	cp "$(readlink -f "$0")" "$tmp"
	DELEGATE_REEXEC=$tmp DELEGATE_SELF_DIR=$self_dir exec bash "$tmp" "$@"
fi
trap 'rm -f "$DELEGATE_REEXEC"' EXIT
SKILL_DIR=$(dirname "$DELEGATE_SELF_DIR")
REGISTRY=${DELEGATE_REGISTRY:-$SKILL_DIR/registry.tsv}
TEMPLATES=$SKILL_DIR/templates

AGY_BIN=${DELEGATE_AGY_BIN:-/code/.local/share/mise/installs/antigravity-cli/latest/agy}
CODEX_BIN=${DELEGATE_CODEX_BIN:-/code/.local/share/mise/installs/codex/latest/bin/codex}
GEMINI_SRC=${DELEGATE_GEMINI_SRC:-/code/.gemini}
CODEX_AUTH=${DELEGATE_CODEX_AUTH:-/code/.codex/auth.json}
MAX_CONCURRENT=${DELEGATE_MAX_CONCURRENT:-1}   # 백엔드별, 모든 저장소 합계(토큰 한도가 사용자 단위라서)
SECRETS_PROBE=(/code/.claude/.credentials.json /code/.git-credentials /code/.ssh)

die() { echo "delegate: $*" >&2; exit 2; }
note() { echo "delegate: $*" >&2; }

# ---------- 중앙 표 ----------
rows() { grep -v '^[[:space:]]*#' "$REGISTRY" | grep -v '^[[:space:]]*$' || true; }
row_by_root() { rows | awk -F'\t' -v r="$1" '$2 == r'; }
row_by_key() { rows | awk -F'\t' -v k="$1" '$1 == k'; }

resolve_repo() { # $1 = key|경로|"" → KEY ROOT AGY_UID SETUP
	local arg=${1:-} row=""
	if [[ -n "$arg" && ! "$arg" =~ / ]]; then
		row=$(row_by_key "$arg")
	else
		local dir=${arg:-$PWD} common
		common=$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || die "$dir 는 git 저장소가 아님"
		# Claude 의 .claude/worktrees/* 나 다른 worktree 안이어도 메인 저장소로 찾는다
		row=$(row_by_root "$(dirname "$common")")
	fi
	[[ -n "$row" ]] || die "중앙 표($REGISTRY)에 없는 저장소: ${arg:-$PWD} — 'delegate.sh register <경로>' 로 먼저 등록"
	IFS=$'\t' read -r KEY ROOT AGY_UID SETUP _ <<<"$row"
	[[ "$AGY_UID" =~ ^[0-9]+$ ]] || die "uid 가 이상함: $row"
}
base_of() { echo "$(dirname "$ROOT")/$KEY-$1"; } # $1 = backend

check_name() { [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "이름은 [a-z0-9-]: $1"; }
check_backend() { [[ "$1" == agy || "$1" == codex ]] || die "백엔드는 agy|codex: $1"; }

tool_path() { # 저장소 mise.toml 이 핀한 도구의 bin 경로들
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

live_runs() { # $1 = backend → 살아 있는 과제 수(모든 저장소)
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
	[[ -f "$promptFile" ]] || die "프롬프트 파일 없음: $promptFile"
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
		*) die "모르는 옵션 $1" ;;
		esac
	done
	resolve_repo "$repo"
	[[ -n "$mode" ]] || { [[ $backend == agy ]] && mode=worktree || mode=empty; }
	[[ "$mode" == worktree || "$mode" == empty ]] || die "--mode 는 worktree|empty"
	[[ -n "$model" ]] || { [[ $backend == agy ]] && model=gemini-3.8-flash-high || model=gpt-6-luna; }
	if [[ $backend == agy ]]; then [[ -x "$AGY_BIN" ]] || die "agy 없음: $AGY_BIN"; else [[ -x "$CODEX_BIN" ]] || die "codex 없음: $CODEX_BIN"; fi
	if [[ $backend == codex && $mode == worktree && "${DELEGATE_CODEX_SANDBOX:-read-only}" == read-only ]]; then
		die "codex worktree 모드는 이 호스트에서 셸이 돌지 않는다(무권한 uid 에서 bubblewrap 이 namespace 를 못 만듦 — 2026-11-10 table-sim 시범). --mode empty 로 맥락을 프롬프트에 담거나, 사용자가 정하면 DELEGATE_CODEX_SANDBOX=danger-full-access(격리는 uid 만 남음)"
	fi
	[[ $backend == agy && $mode == empty ]] && note "경고 — agy empty 모드는 미검증(실측은 worktree 모드뿐)"

	local BASE WT HOMES HOOKS H D admin=""
	BASE=$(base_of "$backend"); WT=$BASE/$name; HOMES=$BASE/.homes; HOOKS=$BASE/.hooks; H=$HOMES/$name; D=$WT/.delegate
	mkdir -p "$BASE" "$HOMES" "$HOOKS" "$BASE/runs"
	exec 9>"/tmp/delegate-$backend.lock"; flock 9
	[[ -e "$WT" ]] && die "$WT 가 이미 있음 — 다른 이름을 쓰거나 collect/remove"
	local live; live=$(live_runs "$backend")
	(( live < MAX_CONCURRENT )) || die "$backend 과제가 이미 $live 개 돌고 있음(상한 $MAX_CONCURRENT, DELEGATE_MAX_CONCURRENT 로 조정 — 토큰 한도는 사용자 몫)"

	printf '#!/bin/sh\necho "push refused: delegate workspace" >&2\nexit 1\n' >"$HOOKS/pre-push"; chmod 755 "$HOOKS/pre-push"

	local commit; commit=$(git -C "$ROOT" rev-parse --verify "$ref^{commit}") || die "커밋을 못 찾음: $ref"
	if [[ $mode == worktree ]]; then
		git -C "$ROOT" worktree add -q --detach "$WT" "$commit"
		# git 이 관리 디렉터리 이름에 번호를 붙일 수 있으므로(같은 basename 이 다른 작업공간에 있을 때) 실제 경로를 묻는다.
		# chown 뒤에는 소유자가 달라 git 이 dubious ownership 으로 거부하므로 지금 묻는다.
		admin=$(git -C "$WT" rev-parse --path-format=absolute --git-dir)
		if [[ "$SETUP" != - && -n "$SETUP" ]]; then
			(cd "$WT" && bash -c "$SETUP" >/dev/null 2>&1) || note "경고 — setup 실패: $SETUP"
		fi
	else
		mkdir -p "$WT"
	fi
	mkdir -p "$D"
	echo $$ >"$D/pid"
	flock -u 9; exec 9>&-

	# HOME — 과제마다, 인증만 새로(사용자 자신의 사용이 갱신했을 수 있음)
	rm -rf "${H:?}"; mkdir -p "$H"
	if [[ $backend == agy ]]; then
		cp -r "$GEMINI_SRC" "$H/.gemini"
		# 사용자 자신의 agy 대화 기록(다른 저장소의 것 포함)은 과제에 넘기지 않는다. 2026-11-10 시범: 통째로 복사하면
		# brain/·conversations/ 에 다른 과제 4개의 기록이 실려 과제 uid 가 읽을 수 있었고, HOME 이 27M 였다.
		# 인증(antigravity-oauth-token)·settings.json·config/ 는 남긴다. [미검증 — 이 줄을 넣은 뒤 실제 agy 실행 전]
		# 문제가 생기면 DELEGATE_AGY_FULL_HOME=1 로 옛 동작.
		if [[ -z "${DELEGATE_AGY_FULL_HOME:-}" ]]; then
			local a=$H/.gemini/antigravity-cli
			rm -rf "${a:?}/brain" "${a:?}/conversations" "${a:?}/annotations" "${a:?}/implicit" "${a:?}/log" "${a:?}/crashes" \
				"${a:?}/history.jsonl" "${a:?}"/conversation_summaries.db* "${a:?}/jetbox_summaries_proto.pb"
		fi
	else
		mkdir -p "$H/.codex"; cp "$CODEX_AUTH" "$H/.codex/auth.json"; chmod 600 "$H/.codex/auth.json"
	fi

	# 프롬프트 = 공통 머리말 + 과제
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
	note "시작 $backend/$name ($model, $mode) $(date -Is) — $WT"

	# 환경은 비우고 시작한다(루트 세션의 토큰류 환경 변수가 새지 않게). 옛 스크립트는 환경을 물려줬다 —
	# agy/codex 가 무언가를 못 찾으면 DELEGATE_KEEP_ENV=1 로 옛 동작(미검증 변경, 첫 실행에서 확인).
	local envi=-i; [[ -n "${DELEGATE_KEEP_ENV:-}" ]] && envi=
	local -a envs=(env $envi HOME="$H" PATH="${tp:+$tp:}/usr/bin:/bin" LANG=C.UTF-8 TERM=dumb
		GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$HOOKS")
	local -a priv=(choom -n 1000 -- setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups)
	set +e
	if [[ $backend == agy ]]; then
		(cd "$WT" && "${priv[@]}" "${envs[@]}" timeout $((timeoutSec + 60)) "$AGY_BIN" --model "$model" \
			--dangerously-skip-permissions --print-timeout "${timeoutSec}s" -p "$(cat "$D/prompt.md")") >"$D/stdout.txt" 2>&1
	else
		# codex 내장 샌드박스(bubblewrap)는 무권한 uid 에서 user namespace 를 못 만든다(이 호스트
		# kernel.unprivileged_userns_clone=0). read-only 로 두면 셸이 하나도 안 돈다 — 2026-11-10 table-sim 시범에서
		# worktree 모드가 `bwrap: No permissions to create a new namespace` 로 파일 하나 못 읽고 끝났다.
		# 셸 없이 파일을 읽을 길이 없으므로 worktree 모드는 쓸모가 없다. 샌드박스를 끄면(danger-full-access) 돌기는 하겠지만
		# 그때 격리는 uid 하나만 남는다 — 그 결정은 사용자 몫이라 기본은 거부하고, DELEGATE_CODEX_SANDBOX 로만 연다.
		# (이 시범에서 샌드박스를 끈 실행은 자동 권한 판정이 막았다. 사용자 결정 전까지 codex 는 empty 모드로 쓴다.)
		local sandbox=${DELEGATE_CODEX_SANDBOX:-read-only}
		# -o(마지막 메시지)는 따로 받는다: worktree 모드에서는 모델이 $report 를 직접 쓰므로 같은 파일이면 덮어쓴다.
		local last=$report; [[ $mode == worktree ]] && last=$D/last-message.md
		(cd "$WT" && "${priv[@]}" "${envs[@]}" CODEX_HOME="$H/.codex" timeout $((timeoutSec + 60)) "$CODEX_BIN" exec \
			-m "$model" -c model_reasoning_effort="$effort" -c approval_policy=never -s "$sandbox" \
			--skip-git-repo-check --ephemeral --ignore-user-config --color never -C "$WT" -o "$last" - <"$D/prompt.md") >"$D/stdout.txt" 2>&1
	fi
	rc=$?
	set -e
	# 모델이 보고서 파일을 안 썼으면 마지막 메시지로 대신한다(agy empty 모드는 파일을 쓰라는 지시가 없다 — 답이 stdout 에 온다).
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
			echo "main repo: CHANGED during the run (HEAD $before_head -> $after_head; status hash differs) — 메인 세션이나 사용자가 한 것인지 확인"
		fi
		if [[ $mode == worktree ]]; then
			echo "worktree HEAD: $(git -c safe.directory="$WT" -C "$WT" rev-parse HEAD) (기준 $commit)"
			echo "worktree changes:"
			git -c safe.directory="$WT" -C "$WT" status --porcelain=v1 | grep -v -e '^?? .delegate/' -e '^?? REPORT.md$' || true
		fi
	} >"$D/guard.txt"
	rm -f "$D/pid"
	echo "$rc" >"$D/exit"
	note "끝 $backend/$name — exit $rc"
	cat "$D/guard.txt"
	if [[ -s "$report" ]]; then echo "report: $report ($(wc -c <"$report") bytes)"; else echo "report: MISSING — $D/stdout.txt 를 볼 것"; fi
	echo "다음: 메인이 읽고 검증 → delegate.sh collect $backend $name --repo $KEY → delegate.sh remove $backend $name --repo $KEY"
}

# ---------- collect / remove ----------
locate() { # backend name repo → BASE WT D
	check_backend "$1"; check_name "$2"; resolve_repo "${3:-}"
	BASE=$(base_of "$1"); WT=$BASE/$2; D=$WT/.delegate
	[[ -d "$WT" ]] || die "없음: $WT"
}

cmd_collect() {
	local backend=$1 name=$2; shift 2; local repo=""
	[[ "${1:-}" == --repo ]] && repo=$2
	locate "$backend" "$name" "$repo"
	[[ -f "$D/pid" ]] && kill -0 "$(cat "$D/pid")" 2>/dev/null && die "아직 도는 중: $backend/$name"
	[[ -f "$D/exit" ]] || note "경고 — exit 기록이 없음(비정상 종료이거나 옛 작업공간). 있는 것만 모은다"
	local out; out=$BASE/runs/$(date +%Y%m%d-%H%M)-$name
	mkdir -p "$out"
	for f in prompt.md meta.txt guard.txt stdout.txt report.md last-message.md exit; do [[ -f "$D/$f" ]] && cp "$D/$f" "$out/"; done
	[[ -f "$WT/REPORT.md" ]] && cp "$WT/REPORT.md" "$out/report.md"
	# agy 는 프로브를 worktree 가 아니라 HOME 의 brain/<대화>/scratch 에 만든다(2026-11-10 시범 — 머리말의 "worktree 밖에
	# 만들지 말 것"을 어겼지만 uid 로는 막히지 않는 곳). guard 의 worktree 변경 목록에 안 잡히고 remove 가 HOME 을 지우면
	# 사라지므로, 보고서가 "실측"이라 부른 프로브와 대화 기록을 여기서 남긴다.
	local brain=$BASE/.homes/$name/.gemini/antigravity-cli/brain conv
	if [[ $backend == agy && -d "$brain" ]]; then
		for conv in "$brain"/*/; do
			conv=${conv%/}; [[ -d "$conv" ]] || continue
			# 이번 과제의 대화만. HOME 을 통째로 복사하던 때는 사용자의 다른 agy 대화도 여기 있었다(시범에서 runs/ 로 딸려 옴).
			[[ "$conv" -nt "$D/meta.txt" || -n "$(find "$conv" -newer "$D/meta.txt" -print -quit)" ]] || continue
			mkdir -p "$out/agy/$(basename "$conv")"
			[[ -d "$conv/scratch" ]] && cp -r "$conv/scratch" "$out/agy/$(basename "$conv")/"
			[[ -f "$conv/.system_generated/logs/transcript.jsonl" ]] && cp "$conv/.system_generated/logs/transcript.jsonl" "$out/agy/$(basename "$conv")/"
		done
	fi
	if git -c safe.directory="$WT" -C "$WT" rev-parse --git-dir >/dev/null 2>&1; then
		# 과제가 worktree 에서 고친 것(실험 diff)도 남긴다 — 새 파일 포함, .delegate/ 와 보고서 제외
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
		case "$1" in --repo) repo=$2; shift 2 ;; --discard) discard=1; shift ;; --delete-branch) delbranch=1; shift ;; *) die "모르는 옵션 $1" ;; esac
	done
	locate "$backend" "$name" "$repo"
	[[ -f "$D/pid" ]] && kill -0 "$(cat "$D/pid")" 2>/dev/null && die "아직 도는 중: $backend/$name"
	if [[ ! -f "$D/collected" && $discard == 0 ]]; then
		# 옛 스크립트가 만든 작업공간(.agy/ 와 AGY_REPORT.md)은 collect 가 모르는 꼴이다 — 보존 여부를 사람이 정한다
		die "아직 collect 안 함 — 'delegate.sh collect $backend $name' 먼저, 또는 버리려면 --discard"
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
		if [[ $delbranch == 1 ]]; then git -C "$ROOT" branch -D "$branch"; else note "옛 방식 브랜치 '$branch' 는 남겨 둠(지우려면 --delete-branch — 사용자 확인 뒤)"; fi
	fi
	echo "removed: $WT"
}

# ---------- list / gc ----------
du_h() { du -sh "$1" 2>/dev/null | cut -f1; }

state_of() { # 작업공간 디렉터리 → 상태
	local w=$1
	if [[ -f "$w/.delegate/pid" ]] && kill -0 "$(cat "$w/.delegate/pid")" 2>/dev/null; then echo running
	elif [[ -f "$w/.delegate/collected" ]]; then echo collected
	elif [[ -f "$w/.delegate/exit" ]]; then echo finished
	elif [[ -d "$w/.agy" ]]; then echo legacy
	elif [[ -f "$w/answer.md" || -f "$w/prompt.md" ]]; then echo legacy-record
	else echo unknown; fi
}

for_repos() { # $1 = --all|key|경로|"" ; 나머지 = 콜백
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
		[[ -d "$BASE/runs" ]] && echo "  runs/: $(find "$BASE/runs" -mindepth 1 -maxdepth 1 -type d | wc -l)개 ($(du_h "$BASE/runs"))"
		[[ -d "$BASE/.home" ]] && echo "  .home (옛 공유 HOME): $(du_h "$BASE/.home")"
	done
	git -C "$ROOT" worktree prune --dry-run -v 2>&1 | sed 's/^/  prune? /' || true
}

GC_DAYS=14; GC_APPLY=0
gc_one() {
	local b BASE w n st age
	for b in agy codex; do
		BASE=$(base_of $b); [[ -d "$BASE" ]] || continue
		# 새 스크립트의 pid 기록만 보면 옛 agy-delegate.sh 로 도는 과제를 놓친다 — cwd 가 작업공간 안인 프로세스를 직접 본다
		local busy=0 pc
		for pc in /proc/[0-9]*/cwd; do [[ "$(readlink "$pc" 2>/dev/null)" == "$BASE"/* ]] && { busy=1; break; }; done
		if [[ $busy == 1 ]]; then echo "보류       $KEY-$b (이 작업공간 안에서 도는 프로세스가 있음 — 끝난 뒤 다시)"; continue; fi
		for w in "$BASE"/*/; do
			w=${w%/}; n=$(basename "$w"); [[ -d "$w" && $n != runs ]] || continue
			st=$(state_of "$w"); age=$(( ($(date +%s) - $(stat -c %Y "$w")) / 86400 ))
			case $st in
			collected) echo "삭제 대상  $KEY-$b/$n (collected, ${age}일, $(du_h "$w"))"
				[[ $GC_APPLY == 1 ]] && (cmd_remove "$b" "$n" --repo "$KEY") ;;
			finished) [[ $age -ge $GC_DAYS ]] && echo "확인 필요  $KEY-$b/$n (끝났지만 collect 안 함, ${age}일) — collect 하거나 remove --discard" ;;
			legacy-record) echo "옛 기록    $KEY-$b/$n (prompt/answer — runs/ 로 옮길 후보, --apply 는 건드리지 않음)" ;;
			legacy) echo "확인 필요  $KEY-$b/$n (옛 스크립트 작업공간, ${age}일, $(du_h "$w")) — AGY_REPORT.md 를 보존할지 정한 뒤 remove --discard" ;;
			running) echo "도는 중    $KEY-$b/$n" ;;
			*) echo "확인 필요  $KEY-$b/$n (모르는 꼴 — 손으로 확인)" ;;
			esac
		done
		for h in "$BASE"/.homes/*/; do
			[[ -d "$h" ]] || continue; n=$(basename "$h")
			[[ -d "$BASE/$n" ]] && continue
			echo "삭제 대상  $KEY-$b/.homes/$n (주인 없는 HOME, $(du_h "$h"))"; [[ $GC_APPLY == 1 ]] && rm -rf "${h:?}"
		done
		if [[ -d "$BASE/.home" ]]; then
			if [[ $busy == 0 ]]; then
				echo "삭제 대상  $KEY-$b/.home (옛 공유 HOME — 대화 기록 누적, $(du_h "$BASE/.home"))"; [[ $GC_APPLY == 1 ]] && rm -rf "${BASE:?}/.home"
			else echo "보류       $KEY-$b/.home (도는 과제가 있음)"; fi
		fi
		[[ -d "$BASE/runs" ]] && find "$BASE/runs" -mindepth 1 -maxdepth 1 -type d -mtime +180 -printf '오래됨     %p (180일+, 보존 기록 — 지울지는 사람이)\n'
	done
	local p; p=$(git -C "$ROOT" worktree prune --dry-run -v 2>&1 || true)
	if [[ -n "$p" ]]; then echo "prune 대상 $KEY: $p"; [[ $GC_APPLY == 1 ]] && git -C "$ROOT" worktree prune -v; fi
	return 0
}

# ---------- doctor / register ----------
doctor_one() {
	echo "== $KEY  root=$ROOT  uid=$AGY_UID"
	[[ -d "$ROOT/.git" || -f "$ROOT/.git" ]] && echo "  ok   git 저장소" || echo "  FAIL git 저장소 아님"
	getent passwd "$AGY_UID" >/dev/null && echo "  FAIL uid $AGY_UID 가 실제 사용자와 겹침" || echo "  ok   uid 가 /etc/passwd 에 없음"
	local can_w
	can_w=$(setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups sh -c "test -w '$ROOT' && echo yes || echo no")
	[[ $can_w == no ]] && echo "  ok   uid 는 메인 작업 트리에 못 씀" || echo "  FAIL uid 가 메인 작업 트리에 쓸 수 있음"
	local s
	for s in "${SECRETS_PROBE[@]}"; do
		[[ -e "$s" ]] || continue
		setpriv --reuid="$AGY_UID" --regid="$AGY_UID" --clear-groups sh -c "test -r '$s'" \
			&& echo "  FAIL uid 가 비밀을 읽을 수 있음: $s" || echo "  ok   못 읽음: $s"
	done
	[[ -f "$ROOT/AGENTS.md" ]] && echo "  ok   AGENTS.md 있음" || echo "  WARN AGENTS.md 없음(외부 모델 진입점 — conventions.md 참고)"
	[[ -f "$ROOT/GEMINI.md" && -f "$ROOT/AGENTS.md" ]] && echo "  WARN GEMINI.md 와 AGENTS.md 가 둘 다 있음 — agy 는 둘 다 싣는다"
	[[ -f "$ROOT/.claude/tools/agy-delegate.sh" ]] && echo "  INFO 옛 사본 남음: .claude/tools/agy-delegate.sh (migration.md)"
	local tp; tp=$(tool_path); echo "  PATH 도구: ${tp:-(없음 — mise.toml 핀 없음)}"
}

doctor_global() {
	echo "== 중앙 표 $REGISTRY"
	local d
	d=$(rows | cut -f3 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   uid 중복 없음" || echo "  FAIL uid 중복: $d"
	d=$(rows | cut -f1 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   key 중복 없음" || echo "  FAIL key 중복: $d"
	d=$(rows | cut -f2 | sort | uniq -d); [[ -z "$d" ]] && echo "  ok   root 중복 없음" || echo "  FAIL root 중복: $d"
	[[ -x "$AGY_BIN" ]] && echo "  ok   agy $AGY_BIN" || echo "  WARN agy 없음 $AGY_BIN"
	[[ -x "$CODEX_BIN" ]] && echo "  ok   codex $CODEX_BIN" || echo "  WARN codex 없음 $CODEX_BIN"
}

cmd_register() {
	local root; root=$(readlink -f "${1:?저장소 경로}"); local key=${2:-$(basename "$root")}
	git -C "$root" rev-parse --git-dir >/dev/null 2>&1 || die "git 저장소 아님: $root"
	[[ -z "$(row_by_root "$root")" ]] || die "이미 등록됨: $root"
	[[ -z "$(row_by_key "$key")" ]] || die "key 가 이미 있음: $key"
	local uid=61000
	while rows | cut -f3 | grep -qx "$uid" || getent passwd "$uid" >/dev/null; do uid=$((uid + 1)); done
	printf '%s\t%s\t%s\t-\t%s\n' "$key" "$root" "$uid" "registered $(date +%F)" >>"$REGISTRY"
	echo "등록: $key $root uid=$uid"
}

# ---------- main ----------
cmd=${1:-}; shift || true
case "$cmd" in
run) [[ $# -ge 3 ]] || die "사용법: run <agy|codex> <이름> <프롬프트 파일> [옵션]"; cmd_run "$@" ;;
collect) [[ $# -ge 2 ]] || die "사용법: collect <agy|codex> <이름> [--repo R]"; cmd_collect "$@" ;;
remove) [[ $# -ge 2 ]] || die "사용법: remove <agy|codex> <이름> [--repo R] [--discard] [--delete-branch]"; cmd_remove "$@" ;;
list) sel=""; [[ "${1:-}" == --repo ]] && sel=$2; [[ "${1:-}" == --all ]] && sel=--all; for_repos "$sel" list_one ;;
gc)
	sel=""
	while [[ $# -gt 0 ]]; do
		case "$1" in --repo) sel=$2; shift 2 ;; --all) sel=--all; shift ;; --days) GC_DAYS=$2; shift 2 ;; --apply) GC_APPLY=1; shift ;; *) die "모르는 옵션 $1" ;; esac
	done
	[[ $GC_APPLY == 1 ]] || echo "(미리보기 — 지우려면 --apply)"
	for_repos "$sel" gc_one ;;
doctor) doctor_global; sel=""; [[ "${1:-}" == --repo ]] && sel=$2; [[ "${1:-}" == --all ]] && sel=--all; for_repos "$sel" doctor_one ;;
register) cmd_register "$@" ;;
*) sed -n '2,13p' "$DELEGATE_REEXEC" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
