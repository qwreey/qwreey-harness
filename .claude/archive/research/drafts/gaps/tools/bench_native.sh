#!/usr/bin/env bash
# native codegen 벤치 실행기(초안). 사용: bench_native.sh [luau 버전...]  (기본 0.742)
# OOM 희생 순위를 올리고(choom), 데이터 3GiB 상한 안에서 돈다.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
vers=("${@:-0.742}")
for v in "${vers[@]}"; do
	bin=/code/.local/share/mise/installs/luau/$v/luau
	for mode in "-O1" "-O2" "-O1 --codegen" "-O2 --codegen"; do
		echo "== luau $v $mode"
		# shellcheck disable=SC2086
		choom -n 1000 -- prlimit --data=3221225472 -- "$bin" $mode "$here/bench_native.luau"
	done
done
