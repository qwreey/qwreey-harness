#!/usr/bin/env bash
# luau-perf 벤치 실행기.
# 사용: bench/run.sh [-p 프로세스수] [-o 출력.tsv] [-m "버전|플래그;버전|플래그"] [벤치.luau ...]
#   기본: 프로세스 3회 x 모드 4개(0.734 -O1, 0.742 -O1, 0.742 -O2, 0.742 -O2 --codegen), 벤치 = bench/*.luau 전부.
#   결과 줄은 "버전 모드 프로세스번호 파일 RESULT|MEM ..." 탭 구분으로 출력 파일에 덧붙는다.
#   요약: python3 -I bench/summarize.py <출력.tsv> > 표.md
# 모든 실행은 choom(OOM 희생 1순위) + prlimit(데이터 3GiB 상한) 안에서 돈다. 공유 기계 규칙이다.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
procs=3
out="$here/results/latest.tsv"
modes="0.734|-O1;0.742|-O1;0.742|-O2;0.742|-O2 --codegen"
while getopts "p:o:m:" opt; do
	case $opt in
	p) procs=$OPTARG ;;
	o) out=$OPTARG ;;
	m) modes=$OPTARG ;;
	*) exit 2 ;;
	esac
done
shift $((OPTIND - 1))
files=("$@")
[ ${#files[@]} -eq 0 ] && files=("$here"/*.luau)
mkdir -p "$(dirname "$out")"
IFS=';' read -r -a mode_list <<<"$modes"
fail=0
for f in "${files[@]}"; do
	name=$(basename "$f")
	for p in $(seq 1 "$procs"); do
		# 프로세스마다 모드 순서를 돌려 기계 부하의 표류가 한 모드에만 쌓이지 않게 한다
		n=${#mode_list[@]}
		for j in $(seq 0 $((n - 1))); do
			m=${mode_list[$(((p + j) % n))]}
			ver=${m%%|*}
			flags=${m#*|}
			bin=/code/.local/share/mise/installs/luau/$ver/luau
			# shellcheck disable=SC2086
			res=$(cd "$here" && choom -n 1000 -- prlimit --data=3221225472 -- timeout 600 "$bin" $flags "$f" 2>&1)
			rc=$?
			if [ $rc -ne 0 ]; then
				echo "FAIL $name $ver $flags rc=$rc: ${res:0:300}" >&2
				fail=1
				continue
			fi
			echo "$res" | grep -E '^(RESULT|MEM)' | sed "s|^|$ver\t$flags\t$p\t$name\t|" >>"$out"
		done
	done
	echo "done $name" >&2
done
exit $fail
