#!/usr/bin/env bash
# style-split-types.sh - 타입 하나(네임스페이스 모듈, 메타테이블 객체)를 여러 파일로 나눌 때 새 솔버 타입 검사가 어디까지 따라오나.
# 파일이 여럿 필요해서 check_snippets.py 대신 여기서 잰다. 질문의 출발: stl `Arr.luau`(3,030줄, 함수 145) 같은 단일 타입 모듈을 나눌 수 있나.
# 주장 (luau 0.734, 0.742, 0.746, --!strict, luau-analyze + luau CLI):
#  S1 재수출은 타입 손실이 없다. 묶음 파일(`Arr/Sort.luau`, `Arr/Ctor.luau`)이 공개, 내부 타입을 `Arr/Types.luau` 에서 가져와
#     제네릭 함수를 정의하고, `Arr/init.luau` 가 표 생성자 필드(`{ Sort = Sort.Sort }`)나 대입(`Arr.Sort = Sort.Sort`)으로 다시 내보내면
#     소비자에서 제네릭이 살아 있다(원소 타입 어긋남, 콜백 인자 어긋남,`Arr<string>` 대입을 잡는다). 명시 타입 인자 `Arr.Sized<<number?>>(…)` 도 된다.
#  S2 "다른 모듈이 같은 표에 붙이기"는 타입에서 안 된다(런타임은 된다).
#     a) 설치자 `require("@self/Sort")(Arr)` -> 소비자 `Arr.Sort` 에 "Key 'Sort' not found in table 'Arr'".
#     b) 메타테이블 객체: 타입, 생성자 파일의 `Methods` 에 다른 모듈이 `function Core.Methods.Sum(self: Core.Obj)` ->
#        그 줄에 "Cannot add property 'Sum' to table 'Methods'", 소비자 `o:Sum()` 에 "Type 'Obj' does not have key 'Sum'".
#     c) 우회 - init 이 묶음 모듈의 함수로 메서드 표를 **조립**하면 된다: `local Methods = { Push = Mut.Push, Sum = Query.Sum }`,
#        `type Bag = typeof(setmetatable({} :: Types.Data, mt))`(제네릭이면 `setmetatable<Types.Data<T>, typeof(mt)>`).
#        묶음 함수의 self 는 **데이터 타입**(`Types.Data<T>`)으로 받는다. 소비자의 인자 어긋남, 없는 메서드를 잡는다. 순환 없음(묶음 -> Types 한 방향).
#     d) 그 대가 - 묶음 안에서 다른 묶음의 메서드를 `self:Push(v)` 로 부르면 "Key 'Push' not found in table 'Data<T>'". 다른 묶음 모듈을 직접 require 해서
#        `Mut.Push(self, v)` 로 부른다.
#     e) 제네릭 객체의 `local o: Bag<number> = Bag.New()` 가 `Data<unknown>` 으로 어긋나는 것은 **나눈 탓이 아니다** - 한 파일 기준선에서도 같다
#        (인자 없는 제네릭 생성자, luau-types generics 1). `Bag.New<<number>>()` 로 쓴다.
#  S3 묶음이 생성자를 쓰려고 init 을 require 하면 순환이다. 0.734 "Cyclic module dependency", 0.742, 0.746 "Cyclic dependencies are only supported
#     if all modules in the cycle use 'export' syntax". 런타임도 "error while running module" 로 죽는다. 생성자를 `Arr/Ctor.luau` 로 빼고 묶음과 init 이
#     둘 다 Ctor 를 require 하면 타입, 실행 모두 깨끗하다.
#  S4 늦은 조회 표(quad Slot 의 `S`)로 상호 재귀를 파일 경계 너머로 끊을 수 있다. `S.luau` 가 `export type S = { isEven: …, isOdd: … }` 와
#     `local S: S = {} :: any` 를 내고, 묶음 파일이 `function S.isEven(…)` 로 채우고 `S.isOdd(n - 1)` 로 부를 때 읽는다. 시그니처 어긋남과
#     표에 없는 이름("Cannot add property 'isNope' to table 'S'")을 잡고, 제네릭 필드(`<T>({ T }) -> T?`)도 된다.
#     등록을 빠뜨리면 타입은 0건이고 런타임에 "attempt to call a nil value" - init 이 모든 묶음을 require 하는지 테스트로 지킨다.
# 성능 메모(측정은 luau-perf): 소비자 -> Arr 호출은 원래 다른 모듈이라 나눠도 같다. 다만 `-O2` 는 **같은 파일의** 지역 함수만 인라인하므로,
#   Arr 안의 작은 내부 헬퍼(구간 정규화 등)를 공용 모듈로 옮기면 인라인이 사라진다(luau-perf calls-and-closures 3, `opt-inline-rules.luau`).
# 근거: stl-luau src/Collections/Arr.luau(머리 주석: 메타테이블 없는 네임스페이스 함수), quad 4ddb9c5a(Slot 의 `S`), claude-doctor .claude/audit/12 3 원인 5.
# 기대와 어긋나면 rc=1. 사용: bash snippets/style-split-types.sh [버전...]   (기본 0.734 0.742 0.746)
set -u
MISE=${MISE_DATA_DIR:-/code/.local/share/mise}
vers=("$@"); [ $# -eq 0 ] && vers=(0.734 0.742 0.746)
d=$(mktemp -d /tmp/luau-kb-split.XXXXXX)
trap 'rm -rf "$d"' EXIT
w() { mkdir -p "$(dirname "$d/$1")"; cat > "$d/$1"; }

# ---------- S1 재수출 ----------
w s1/Arr/Types.luau <<'EOF'
--!strict
export type Arr<T> = { read n: number, read data: { read [number]: T }, read __phantom: (T) -> T }
export type Raw<T> = { n: number, data: { [number]: T }, read __phantom: (T) -> T }
return nil
EOF
w s1/Arr/Sort.luau <<'EOF'
--!strict
local Types = require("./Types")
type Arr<T> = Types.Arr<T>
type Raw<T> = Types.Raw<T>
local M = {}
function M.Sort<T>(a: Arr<T>, less: (T, T) -> boolean): Arr<T>
	table.sort(((a :: any) :: Raw<T>).data, less)
	return a
end
return M
EOF
w s1/Arr/Ctor.luau <<'EOF'
--!strict
local Types = require("./Types")
type Arr<T> = Types.Arr<T>
local M = {}
function M.Sized<T>(n: number, fill: T): Arr<T>
	return ({ n = n, data = table.create(n, fill) } :: any) :: Arr<T>
end
function M.Of<T>(...: T): Arr<T>
	return ({ n = select("#", ...), data = { ... } } :: any) :: Arr<T>
end
return M
EOF
w s1/Arr/init.luau <<'EOF'
--!strict
local Types = require("@self/Types")
local Sort = require("@self/Sort")
local Ctor = require("@self/Ctor")
export type Arr<T> = Types.Arr<T>
return table.freeze({
	Sort = Sort.Sort,
	Sized = Ctor.Sized,
	Of = Ctor.Of,
})
EOF
w s1/good.luau <<'EOF'
--!strict
local Arr = require("./Arr")
local a = Arr.Of(3, 1, 2)
Arr.Sort(a, function(x: number, y: number) return x < y end)
local h = Arr.Sized<<number?>>(3, nil)
local v: number? = h.data[1]
assert(a.data[1] == 1 and v == nil)
EOF
w s1/bad.luau <<'EOF'
--!strict
local Arr = require("./Arr")
local a = Arr.Of(3, 1, 2)
local _s: string = a.data[1]
Arr.Sort(a, function(x: string, y: string) return x < y end)
local _h = Arr.Sized<<number>>(3, "x")
local _b: Arr.Arr<string> = Arr.Of(1)
EOF
# 대입 꼴의 init (같은 모듈에서 짓는 중인 표에 더하기는 된다)
mkdir -p "$d/s1b"; cp -r "$d/s1/Arr" "$d/s1/good.luau" "$d/s1/bad.luau" "$d/s1b/"
w s1b/Arr/init.luau <<'EOF'
--!strict
local Types = require("@self/Types")
local Sort = require("@self/Sort")
local Ctor = require("@self/Ctor")
export type Arr<T> = Types.Arr<T>
local Arr = {}
Arr.Sort = Sort.Sort
Arr.Sized = Ctor.Sized
Arr.Of = Ctor.Of
return table.freeze(Arr)
EOF

# ---------- S2a 설치자 ----------
mkdir -p "$d/s2a/Arr"; cp "$d/s1/Arr/Types.luau" "$d/s1/Arr/Ctor.luau" "$d/s2a/Arr/"
w s2a/Arr/Sort.luau <<'EOF'
--!strict
local Types = require("./Types")
type Arr<T> = Types.Arr<T>
type Raw<T> = Types.Raw<T>
return function(Arr: any)
	function Arr.Sort<T>(a: Arr<T>, less: (T, T) -> boolean): Arr<T>
		table.sort(((a :: any) :: Raw<T>).data, less)
		return a
	end
end
EOF
w s2a/Arr/init.luau <<'EOF'
--!strict
local Ctor = require("@self/Ctor")
local Arr = { Of = Ctor.Of }
require("@self/Sort")(Arr)
return Arr
EOF
w s2a/use.luau <<'EOF'
--!strict
local Arr = require("./Arr")
local a = Arr.Of(3, 1, 2)
Arr.Sort(a, function(x: number, y: number) return x < y end)
assert(a.data[1] == 1)
EOF

# ---------- S2b 메타테이블 Methods 에 다른 모듈이 붙이기 ----------
w s2b/Bag/Core.luau <<'EOF'
--!strict
local Methods = {}
Methods.__index = Methods
function Methods.Push(self: Obj, v: number) table.insert(self.items, v) end
export type Obj = typeof(setmetatable({ items = {} :: { number } }, Methods))
local Core = {}
Core.Methods = Methods
function Core.New(): Obj return setmetatable({ items = {} :: { number } }, Methods) end
return Core
EOF
w s2b/Bag/Extra.luau <<'EOF'
--!strict
local Core = require("./Core")
function Core.Methods.Sum(self: Core.Obj): number
	local s = 0
	for _, v in self.items do s += v end
	return s
end
return nil
EOF
w s2b/use.luau <<'EOF'
--!strict
local Core = require("./Bag/Core")
require("./Bag/Extra")
local o = Core.New()
o:Push(2)
o:Push(3)
assert(o:Sum() == 5)
EOF

# ---------- S2c init 이 메서드 표를 조립 (비제네릭 / 제네릭) ----------
w s2c/Bag/Types.luau <<'EOF'
--!strict
export type Data = { items: { number } }
return nil
EOF
w s2c/Bag/Mut.luau <<'EOF'
--!strict
local Types = require("./Types")
local M = {}
function M.Push(self: Types.Data, v: number) table.insert(self.items, v) end
return M
EOF
w s2c/Bag/Query.luau <<'EOF'
--!strict
local Types = require("./Types")
local M = {}
function M.Sum(self: Types.Data): number
	local s = 0
	for _, v in self.items do s += v end
	return s
end
return M
EOF
w s2c/Bag/init.luau <<'EOF'
--!strict
local Types = require("@self/Types")
local Mut = require("@self/Mut")
local Query = require("@self/Query")
local Methods = { Push = Mut.Push, Sum = Query.Sum }
local mt = { __index = Methods }
export type Bag = typeof(setmetatable({} :: Types.Data, mt))
local Bag = {}
function Bag.New(): Bag return setmetatable({ items = {} }, mt) end
return table.freeze(Bag)
EOF
w s2c/good.luau <<'EOF'
--!strict
local Bag = require("./Bag")
local o = Bag.New()
o:Push(2)
o:Push(3)
local s: number = o:Sum()
assert(s == 5)
EOF
w s2c/bad.luau <<'EOF'
--!strict
local Bag = require("./Bag")
local o = Bag.New()
o:Push("x")
local _s: string = o:Sum()
o:Nope()
EOF
w s2g/Bag/Types.luau <<'EOF'
--!strict
export type Data<T> = { items: { T } }
return nil
EOF
w s2g/Bag/Mut.luau <<'EOF'
--!strict
local Types = require("./Types")
local M = {}
function M.Push<T>(self: Types.Data<T>, v: T) table.insert(self.items, v) end
return M
EOF
w s2g/Bag/Query.luau <<'EOF'
--!strict
local Types = require("./Types")
local M = {}
function M.First<T>(self: Types.Data<T>): T? return self.items[1] end
return M
EOF
w s2g/Bag/init.luau <<'EOF'
--!strict
local Types = require("@self/Types")
local Mut = require("@self/Mut")
local Query = require("@self/Query")
local Methods = { Push = Mut.Push, First = Query.First }
local mt = { __index = Methods }
export type Bag<T> = setmetatable<Types.Data<T>, typeof(mt)>
local Bag = {}
function Bag.New<T>(): Bag<T> return setmetatable({ items = {} :: { T } }, mt) end
return table.freeze(Bag)
EOF
w s2g/good.luau <<'EOF'
--!strict
local Bag = require("./Bag")
local o = Bag.New<<number>>()
o:Push(2)
local f: number? = o:First()
assert(f == 2)
EOF
w s2g/bad.luau <<'EOF'
--!strict
local Bag = require("./Bag")
local o = Bag.New<<number>>()
o:Push("x")
local _f: string? = o:First()
EOF
w s2g/Bag/Cross.luau <<'EOF'
--!strict
local Types = require("./Types")
local M = {}
function M.PushTwice<T>(self: Types.Data<T>, v: T)
	self:Push(v)
end
return M
EOF
# 기준선: 한 파일에서도 인자 없는 제네릭 생성자는 주석 기대 타입을 못 받는다
w s2g/single.luau <<'EOF'
--!strict
type Data<T> = { items: { T } }
local Methods = {}
function Methods.Push<T>(self: Data<T>, v: T) table.insert(self.items, v) end
local mt = { __index = Methods }
type Bag<T> = setmetatable<Data<T>, typeof(mt)>
local function New<T>(): Bag<T> return setmetatable({ items = {} :: { T } }, mt) end
local _o: Bag<number> = New()
EOF
printf '%s\n' '--!strict' 'local Bag = require("./Bag")' 'local _o: Bag.Bag<number> = Bag.New()' > "$d/s2g/split-noarg.luau"

# ---------- S3 순환과 Ctor 로 끊기 ----------
mkdir -p "$d/s3c/Arr" "$d/s3f/Arr"; cp "$d/s1/Arr/Types.luau" "$d/s3c/Arr/"; cp "$d/s1/Arr/Types.luau" "$d/s1/Arr/Ctor.luau" "$d/s3f/Arr/"
w s3c/Arr/Map.luau <<'EOF'
--!strict
local Arr = require("../Arr")
local Types = require("./Types")
local M = {}
function M.Map<T, U>(a: Types.Arr<T>, f: (T) -> U): Types.Arr<U>
	local out = {}
	for i = 1, a.n do out[i] = f(a.data[i]) end
	return Arr.Of(table.unpack(out, 1, a.n))
end
return M
EOF
w s3c/Arr/init.luau <<'EOF'
--!strict
local Types = require("@self/Types")
local Map = require("@self/Map")
local Arr = {}
function Arr.Of<T>(...: T): Types.Arr<T>
	return ({ n = select("#", ...), data = { ... } } :: any) :: Types.Arr<T>
end
Arr.Map = Map.Map
return Arr
EOF
w s3c/use.luau <<'EOF'
--!strict
local Arr = require("./Arr")
local b = Arr.Map(Arr.Of(1, 2), function(x: number) return tostring(x) end)
assert(b.data[1] == "1")
EOF
w s3f/Arr/Map.luau <<'EOF'
--!strict
local Types = require("./Types")
local Ctor = require("./Ctor")
local M = {}
function M.Map<T, U>(a: Types.Arr<T>, f: (T) -> U): Types.Arr<U>
	local out = {}
	for i = 1, a.n do out[i] = f(a.data[i]) end
	return Ctor.Of(table.unpack(out, 1, a.n))
end
return M
EOF
w s3f/Arr/init.luau <<'EOF'
--!strict
local Ctor = require("@self/Ctor")
local Map = require("@self/Map")
return table.freeze({ Of = Ctor.Of, Map = Map.Map })
EOF
cp "$d/s3c/use.luau" "$d/s3f/use.luau"
printf '%s\n' '--!strict' 'local Arr = require("./Arr")' 'local b = Arr.Map(Arr.Of(1, 2), function(x: number) return tostring(x) end)' 'local _n: number = b.data[1]' > "$d/s3f/bad.luau"

# ---------- S4 늦은 조회 표 ----------
w s4/P/S.luau <<'EOF'
--!strict
export type S = {
	isEven: (n: number) -> boolean,
	isOdd: (n: number) -> boolean,
}
local S: S = {} :: any
return S
EOF
w s4/P/Even.luau <<'EOF'
--!strict
local S = require("./S")
function S.isEven(n: number): boolean
	if n == 0 then return true end
	return S.isOdd(n - 1)
end
return nil
EOF
w s4/P/Odd.luau <<'EOF'
--!strict
local S = require("./S")
S.isOdd = function(n: number): boolean
	if n == 0 then return false end
	return S.isEven(n - 1)
end
return nil
EOF
w s4/P/init.luau <<'EOF'
--!strict
local S = require("@self/S")
require("@self/Even")
require("@self/Odd")
return table.freeze({ isEven = S.isEven })
EOF
printf '%s\n' '--!strict' 'local P = require("./P")' 'assert(P.isEven(10) and not P.isEven(7))' > "$d/s4/use.luau"
w s4/P/Bad.luau <<'EOF'
--!strict
local S = require("./S")
S.isOdd = function(n: string): boolean return n == "" end
S.isNope = function() end
local _x: string = S.isEven(1)
return nil
EOF
mkdir -p "$d/s4/Q"; cp "$d/s4/P/S.luau" "$d/s4/P/Even.luau" "$d/s4/Q/"
printf '%s\n' '--!strict' 'local S = require("@self/S")' 'require("@self/Even")' 'return table.freeze({ isEven = S.isEven })' > "$d/s4/Q/init.luau"
printf '%s\n' '--!strict' 'local Q = require("./Q")' 'print(Q.isEven(3))' > "$d/s4/useq.luau"
w s4/G/S.luau <<'EOF'
--!strict
export type S = { first: <T>(xs: { T }) -> T? }
local S: S = {} :: any
return S
EOF
w s4/G/A.luau <<'EOF'
--!strict
local S = require("./S")
function S.first<T>(xs: { T }): T? return xs[1] end
return nil
EOF
printf '%s\n' '--!strict' 'local S = require("./G/S")' 'require("./G/A")' 'local v: number? = S.first({ 1, 2 })' 'assert(v == 1)' > "$d/s4/useg.luau"
printf '%s\n' '--!strict' 'local S = require("./G/S")' 'local _v: string? = S.first({ 1, 2 })' > "$d/s4/badg.luau"

rc=0
ok() { echo "ok   [$v] $*"; }
bad() { echo "FAIL [$v] $*"; rc=1; }
has() { [[ $1 == *"$2"* ]]; }
for v in "${vers[@]}"; do
	L=$MISE/installs/luau/$v/luau; A=$MISE/installs/luau/$v/luau-analyze
	an() { (cd "$d/$1" && "$A" "$2" 2>&1); }
	run() { (cd "$d/$1" && "$L" "$2" 2>&1); }
	# S1
	for s in s1 s1b; do
		out=$(an $s good.luau) && run $s good.luau >/dev/null && ok "S1 재수출($s) 깨끗·실행" || bad "S1 $s good: $out"
		out=$(an $s bad.luau)
		if has "$out" "(4,20): TypeError: Expected this to be 'string', but got 'number'" && has "$out" "(5,1): TypeError: No valid instantiation" \
			&& has "$out" "(6,35): TypeError: Expected this to be 'number', but got 'string'" && has "$out" "(7,29): TypeError: Expected this to be"; then
			ok "S1 재수출($s): 원소·콜백·<<T>>·Arr<string> 넷 다 잡음"
		else bad "S1 $s bad: $out"; fi
	done
	# S2a
	out=$(an s2a use.luau); has "$out" "Key 'Sort' not found in table 'Arr'" && ok "S2a 설치자: 타입에 안 보임" || bad "S2a: $out"
	run s2a use.luau >/dev/null && ok "S2a 설치자: 런타임은 됨" || bad "S2a run"
	# S2b
	out=$(an s2b use.luau)
	has "$out" "Cannot add property 'Sum' to table 'Methods'" && has "$out" "Type 'Obj' does not have key 'Sum'" \
		&& ok "S2b 다른 모듈이 Methods 에 붙이기: 대입 줄·소비자 둘 다 진단" || bad "S2b: $out"
	run s2b use.luau >/dev/null && ok "S2b 런타임은 됨" || bad "S2b run"
	# S2c / S2g
	for s in s2c s2g; do
		out=$(an $s good.luau) && run $s good.luau >/dev/null && ok "S2c 조립($s) 깨끗·실행" || bad "S2c $s good: $out"
		out=$(an $s bad.luau)
		has "$out" "(4,8): TypeError: Expected this to be 'number', but got 'string'" && has "$out" "(5," \
			&& ok "S2c 조립($s): 인자·반환 어긋남 잡음" || bad "S2c $s bad: $out"
	done
	has "$(an s2c bad.luau)" "Type 'Bag' does not have key 'Nope'" && ok "S2c 없는 메서드 잡음" || bad "S2c Nope"
	out=$(an s2g Bag/Cross.luau); has "$out" "Key 'Push' not found in table 'Data<T>'" && ok "S2d 묶음 안 self:다른묶음메서드 → 진단" || bad "S2d: $out"
	o1=$(an s2g single.luau); o2=$(an s2g split-noarg.luau)
	has "$o1" "Data<unknown>" && has "$o2" "Data<unknown>" && ok "S2e 인자 없는 제네릭 생성자: 한 파일·나눈 꼴 똑같이 Data<unknown>" || bad "S2e: $o1 / $o2"
	# S3
	out=$(an s3c use.luau)
	if has "$out" "Cyclic module dependency" || has "$out" "Cyclic dependencies are only supported if all modules in the cycle use 'export' syntax"; then
		ok "S3 init↔묶음 순환: 분석 진단"
	else bad "S3 cyc analyze: $out"; fi
	out=$(run s3c use.luau); [ $? -ne 0 ] && has "$out" "error while running module" && ok "S3 순환: 런타임 실패" || bad "S3 cyc run: $out"
	out=$(an s3f use.luau) && run s3f use.luau >/dev/null && ok "S3 Ctor 로 끊음: 깨끗·실행" || bad "S3 fix: $out"
	has "$(an s3f bad.luau)" "(4,20): TypeError: Expected this to be 'number', but got 'string'" && ok "S3 Ctor 꼴: Map 의 U 가 살아 있음" || bad "S3 fix bad"
	# S4
	out=$(an s4 use.luau) && run s4 use.luau >/dev/null && ok "S4 늦은 조회 표: 깨끗·실행" || bad "S4 good: $out"
	out=$(an s4 P/Bad.luau)
	has "$out" "(3,11): TypeError: Expected this to be" && has "$out" "Cannot add property 'isNope' to table 'S'" && has "$out" "(5,20): TypeError: Expected this to be 'string', but got 'boolean'" \
		&& ok "S4 시그니처 어긋남·없는 이름·반환 어긋남 잡음" || bad "S4 bad: $out"
	o1=$(an s4 useq.luau); o2=$(run s4 useq.luau); r=$?
	[ -z "$o1" ] && [ $r -ne 0 ] && has "$o2" "attempt to call a nil value" && ok "S4 등록 누락: 타입 0건, 런타임 nil 호출" || bad "S4 missing: $o1 / $o2"
	out=$(an s4 useg.luau) && run s4 useg.luau >/dev/null && has "$(an s4 badg.luau)" "Expected this to be 'string?', but got 'number?'" \
		&& ok "S4 제네릭 필드도 됨" || bad "S4 generic: $out"
done
exit $rc
