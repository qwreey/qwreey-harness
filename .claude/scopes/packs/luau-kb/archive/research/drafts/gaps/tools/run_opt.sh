#!/usr/bin/env bash
# 최적화 수준·native 관련 주장 검사기(초안). check_snippets.py 의 --@run 은 CLI 기본(-O1, -g1, 인터프리터)으로만 돌므로,
# CLI 플래그(-O/-g/--codegen)나 luau-compile 출력에 걸린 주장은 여기서 확인한다.
# 사용: run_opt.sh [luau 버전...]   (기본 0.734 0.742). 실패가 하나라도 있으면 rc=1.
set -uo pipefail
S=$(cd "$(dirname "$0")/../snippets" && pwd)
T=$(mktemp -d /tmp/run-opt-XXXXXX)
trap 'rm -rf "$T"' EXIT
vers=("${@:-0.734}")
[ $# -eq 0 ] && vers=(0.734 0.742)
fail=0
ok() { echo "ok   [$v] $*"; }
bad() { echo "FAIL [$v] $*"; fail=1; }
# 기대 rc 로 실행: want_rc <0|nz> <설명> <luau 인자...>
want_rc() {
	local want=$1 desc=$2; shift 2
	local out rc
	out=$(cd "$T" && choom -n 1000 -- prlimit --data=3221225472 -- "$L" "$@" 2>&1); rc=$?
	if { [ "$want" = 0 ] && [ $rc -eq 0 ]; } || { [ "$want" = nz ] && [ $rc -ne 0 ]; }; then ok "$desc"; else bad "$desc (rc=$rc) ${out:0:200}"; fi
	LAST_OUT=$out
}
# --!optimize 줄을 빈 주석으로 바꿔 줄 번호를 보존한 사본
strip_opt() { sed 's/^--!optimize [0-9]$/--/' "$S/$1" > "$T/$1"; echo "$T/$1"; }
# codegen 함수별 asmSize 를 "이름=크기 ..." 로
sizes() {
	"$C" --codegen "$@" --record-stats=function --stats-file="$T/st.json" >/dev/null 2>&1
	python3 -I -c "
import json,sys
d=json.load(open(sys.argv[1]))
for v in d.values(): print(' '.join(f\"{f['name']}={f['asmSize']}\" for f in v['lowerStats']['functions']))" "$T/st.json"
}
get() { echo "$1" | tr ' ' '\n' | sed -n "s/^$2=//p"; }

for v in "${vers[@]}"; do
	L=/code/.local/share/mise/installs/luau/$v/luau
	C=/code/.local/share/mise/installs/luau/$v/luau-compile

	# A. 소스 지시어가 CLI 플래그를 이긴다(양방향)
	want_rc 0 "A1 --!optimize 1 이 CLI -O2 를 이김" -O2 "$S/optimize-o1-error-level.luau"
	want_rc 0 "A2 --!optimize 2 가 CLI -O0 을 이김" -O0 "$S/optimize-o2-error-level.luau"
	want_rc 0 "A3 --!native 다음 --!optimize 1 은 CLI -O2 에서도 1" -O2 "$S/native-directive-order.luau"

	# B. 지시어가 없으면 CLI 수준을 따른다
	f2=$(strip_opt optimize-o2-error-level.luau); f1=$(strip_opt optimize-o1-error-level.luau)
	want_rc 0 "B1 지시어 없는 o2 사본: -O2 에서 위치 소실 단언 통과" -O2 "$f2"
	want_rc nz "B2 지시어 없는 o2 사본: -O1 에서는 위치가 남아 단언 실패" -O1 "$f2"
	want_rc 0 "B3 지시어 없는 o1 사본: -O1 통과" -O1 "$f1"
	want_rc nz "B4 지시어 없는 o1 사본: -O2 에서 위치가 사라져 단언 실패" -O2 "$f1"

	# C. 네이티브 실행 자체는 위치를 바꾸지 않는다(바뀌는 건 -O2 때문)
	want_rc 0 "C1 --codegen + --!optimize 1: 위치 보존" --codegen "$S/optimize-o1-error-level.luau"
	want_rc 0 "C2 --codegen + --!optimize 2: 인터프리터와 같은 위치 소실" --codegen "$S/optimize-o2-error-level.luau"
	want_rc 0 "C3 --codegen 으로 traceback 단언도 같음" --codegen "$S/optimize-o2-traceback.luau"

	# D. -g0 은 줄 정보를 모두 지운다
	want_rc nz "D1 -g0: 에러 위치가 없어 o1 단언 실패" -g0 "$S/optimize-o1-error-level.luau"
	if echo "$LAST_OUT" | grep -q "check: expected number" && ! echo "$LAST_OUT" | grep -q ":20:"; then ok "D2 -g0 메시지에 줄 번호 없음"; else bad "D2 -g0 출력: ${LAST_OUT:0:200}"; fi

	# E. 인라인 조건: 각 호출 줄의 [inline:태그] 와 바로 위 remark 비교
	"$C" --remarks -O2 "$S/optimize-inline-rules.luau" > "$T/rm.txt" 2>&1
	res=$(awk '
		/-- remark: inlining/ { r = r $0 "\n"; next }
		/-- remark:/ { next }
		/\[inline:/ {
			match($0, /\[inline:[a-z]+\]/); tag = substr($0, RSTART + 8, RLENGTH - 9)
			got = "none"
			if (r ~ /inlining succeeded/) got = "ok"
			else if (r ~ /function is variadic/) got = "variadic"
			else if (r ~ /fixed returns to multret/) got = "multret"
			else if (r ~ /too expensive/) got = "expensive"
			if (got != tag) print "line: " $0 " got=" got
			n++
		}
		{ r = "" }
		END { print "checked " n }' "$T/rm.txt")
	if [ "$(echo "$res" | grep -c '^line:')" -eq 0 ]; then ok "E1 인라인 조건 ($res)"; else bad "E1 $res"; fi

	# F. 상수 접기와 루프 펼치기
	t1=$("$C" --text -O1 "$S/optimize-fold-unroll.luau"); t2=$("$C" --text -O2 "$S/optimize-fold-unroll.luau")
	r1=$("$C" --remarks -O1 "$S/optimize-fold-unroll.luau"); r2=$("$C" --remarks -O2 "$S/optimize-fold-unroll.luau")
	echo "$t1" | grep -q "LOADN R[0-9]* 21" && ok "F1 -O1 산술 접기(K*2+1 → 21)" || bad "F1"
	echo "$t1" | grep -q "LOADK R[0-9]* K[0-9]* \['ab'\]" && ok "F2 -O1 문자열 연결 접기" || bad "F2"
	echo "$t1" | grep -q "math.sqrt" && ok "F3 -O1 은 math.sqrt(16) 를 접지 않음" || bad "F3"
	echo "$t2" | grep -q "math.sqrt" && bad "F4 -O2 에 math.sqrt 남음" || ok "F4 -O2 는 내장 호출을 접음"
	echo "$r1" | grep -q "loop unroll" && bad "F5 -O1 에서 펼치기 remark" || ok "F5 -O1 은 루프를 펼치지 않음"
	echo "$r2" | grep -q "loop unroll succeeded (iterations 4" && ok "F6 -O2 는 4회 루프를 펼침" || bad "F6"
	echo "$r2" | grep -q "too many iterations (100)" && ok "F7 -O2 도 100회 루프는 안 펼침" || bad "F7"

	# G. 타입 주석과 codegen 크기
	printf -- '--!native\n' | cat - "$S/native-annotation-codegen.luau" > "$T/nac.luau"
	sn=$(sizes "$T/nac.luau"); so=$(sizes -O1 "$S/native-annotation-codegen.luau"); s2=$(sizes -O2 "$S/native-annotation-codegen.luau")
	echo "     --!native: $sn"; echo "     -O1      : $so"; echo "     -O2      : $s2"
	[ $(( $(get "$sn" typed) * 3 )) -lt "$(get "$sn" untyped)" ] && ok "G1 native: vector 파라미터 주석이 코드 1/3 미만" || bad "G1"
	[ $(( $(get "$sn" localAnn) * 3 )) -lt "$(get "$sn" untyped)" ] && ok "G2 native: 로컬 주석도 쓰임" || bad "G2"
	[ "$(get "$sn" optional)" -ge "$(get "$sn" untyped)" ] && ok "G3 native: vector? 는 효과 없음" || bad "G3"
	[ $(( $(get "$sn" nums) * 3 / 2 )) -lt "$(get "$sn" nonums)" ] && ok "G4 native: number 주석 효과" || bad "G4"
	[ $(( $(get "$so" typed) * 10 )) -ge $(( $(get "$so" untyped) * 9 )) ] && ok "G5 -O1(타입 정보 없음): 주석 무시" || bad "G5"
	[ $(( $(get "$s2" typed) * 3 )) -lt "$(get "$s2" untyped)" ] && ok "G6 -O2: 파라미터 주석은 쓰임" || bad "G6"
	[ $(( $(get "$s2" localAnn) * 10 )) -ge $(( $(get "$s2" untyped) * 9 )) ] && ok "G7 -O2(-t0): 로컬 주석은 무시" || bad "G7"

	# H. @native 범위
	sa=$(sizes "$S/native-attribute-nested.luau"); names=$(echo "$sa" | grep -o '[^ ]*=' | tr -d = | sort | tr '\n' ' ')
	[ "$names" = "f " ] && ok "H1 @native: 붙인 함수만 컴파일 ($names)" || bad "H1 ($names)"
	printf -- '--!native\n' | cat - "$S/native-attribute-nested.luau" > "$T/nn.luau"
	sm=$(sizes "$T/nn.luau"); names=$(echo "$sm" | sed 's/\[top level\]/[top-level]/' | grep -o '[^ ]*=' | tr -d = | sort | tr '\n' ' ')
	[ "$names" = "[anonymous] [top-level] f g " ] && ok "H2 --!native: 모든 함수 + 최상위 ($names)" || bad "H2 ($names)"
done
exit $fail
