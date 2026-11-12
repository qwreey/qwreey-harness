--!strict
-- 주장: '레코드에 예약 키가 들어오면 막기'는 자리에 따라 type function 이 필요 없다.
--   - 값이 들어오는 생성 함수 자리: `rec: T & { Get: never? }` 만으로 `Get = 1` 이 잡힌다.
--     T 는 그대로 추론된다(hp 가 number). type function 없이 된다.
--   - 순수 타입 주석 자리(`Store<{ hp: number, Get: number }>`): 교집합 별칭은 주석만으로는 진단을 내지 않는다(bug-present).
--     quad CheckReservedKeys 처럼 `keyof<T>` 를 받아 print + never 로 띄우는 type function 이 필요하다.
-- 근거: quad/quad-types/src/init.luau:272-295 (CheckReservedKeys), quad/.claude/base/typing-limits.md §0
local function store<T>(rec: T & { Get: never?, Set: never? }): T
	return rec :: any
end
local ok = store({ hp = 1 })
local _bad = store({ hp = 1, Get = 1 }) -- expect-error: Expected property `Get` to be exactly `nil`
local _hp: string = ok.hp -- expect-error: Expected this to be 'string', but got 'number'
type StoreAlias<T> = T & { Get: never?, Set: never? }
type _S = StoreAlias<{ hp: number, Get: number }> -- bug-present
type function CheckReservedKeys(keys: type): type
	for _, k in (if keys:is("union") then keys:components() else { keys }) do
		if k:is("singleton") and (k:value() == "Get" or k:value() == "Set") then
			print("reserved key: " .. tostring(k:value()))
			return types.never
		end
	end
	return types.singleton(true)
end
type StoreTf<T> = T & { __reservedCheck: CheckReservedKeys<keyof<T>> }
type _S2 = StoreTf<{ hp: number, Get: number }> -- expect-error: reserved key: Get
type _S3 = StoreTf<{ hp: number }>
