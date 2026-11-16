#!/bin/sh
# luau-kb 플러그인의 .lsp.json 이 부르는 luau-lsp 래퍼. 하는 일:
#  1. 바이너리 고르기: $LUAU_LSP_BIN > 프로젝트 디렉터리에서 `mise which luau-lsp`(프로젝트 핀)
#     > $MISE_DATA_DIR/installs/github-johnny-morganz-luau-lsp/ 의 가장 높은 버전. mise shim 은 쓰지 않는다
#     (버전 미지정 디렉터리에서 'No version is set' 으로 실패한다).
#  2. 플랫폼 고르기: 프로젝트 루트에 *.project.json 이나 sourcemap.json 이 있으면 roblox(정의 파일 + sourcemap),
#     아니면 standard. $LUAU_KB_LSP_PLATFORM=standard|roblox 로 강제한다.
#  3. 기본 설정을 --settings 로 넘긴다(tools/lsp/settings-*.json, 새 솔버, sourcemap 자동 생성 끔 - rojo 를 띄우지 않는다).
#  $LUAU_KB_LSP_DEFS 로 정의 파일을 바꾸고, $LUAU_KB_LSP_LOG=<파일> 이면 클라이언트가 보낸 메시지를 그 파일에 남긴다.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=${CLAUDE_PLUGIN_ROOT:-$(dirname -- "$HERE")}
PROJ=${CLAUDE_PROJECT_DIR:-$PWD}
MISE_DATA=${MISE_DATA_DIR:-/code/.local/share/mise}

bin=${LUAU_LSP_BIN:-}
if [ -z "$bin" ] && command -v mise >/dev/null 2>&1; then
	bin=$(cd "$PROJ" && mise which luau-lsp 2>/dev/null || true)
	case "$bin" in */shims/*) bin= ;; esac
fi
if [ -z "$bin" ]; then
	dir="$MISE_DATA/installs/github-johnny-morganz-luau-lsp"
	ver=$(ls "$dir" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -t. -k1,1n -k2,2n -k3,3n | tail -n 1 || true)
	[ -n "$ver" ] && bin="$dir/$ver/luau-lsp"
fi
if [ -z "$bin" ] || [ ! -x "$bin" ]; then
	echo "luau-kb luau-lsp.sh: luau-lsp 를 찾지 못했다. mise 로 github:JohnnyMorganz/luau-lsp 를 설치하거나 LUAU_LSP_BIN 을 지정한다." >&2
	exit 127
fi

platform=${LUAU_KB_LSP_PLATFORM:-}
if [ -z "$platform" ]; then
	platform=standard
	for f in "$PROJ"/*.project.json "$PROJ"/sourcemap.json; do
		[ -e "$f" ] && platform=roblox && break
	done
fi

set -- lsp --stdio --flag:LuauSolverV2=true --settings="$ROOT/tools/lsp/settings-$platform.json"
if [ "$platform" = roblox ]; then
	set -- "$@" --definitions=@roblox="${LUAU_KB_LSP_DEFS:-$ROOT/typedefs/globalTypes.d.luau}"
fi

if [ -n "${LUAU_KB_LSP_LOG:-}" ]; then
	echo "# $(date -u +%FT%TZ) bin=$bin platform=$platform proj=$PROJ" >>"$LUAU_KB_LSP_LOG"
	tee -a "$LUAU_KB_LSP_LOG" | "$bin" "$@"
	exit $?
fi
exec "$bin" "$@"
