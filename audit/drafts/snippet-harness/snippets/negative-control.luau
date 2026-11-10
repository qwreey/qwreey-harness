--!strict
--@run
local function id<T>(x: T): T
	return x
end
local ok: number = id<<number>>(1)
local bad: number = id<<string>>("a") -- expect-error: number
print(ok, bad)
