--!strict
local Stack = require("./Stack")

local s = Stack.new() :: Stack.Stack<number>
s:push(1)
local top = s:pop()
local fromList = Stack.fromList({ "a", "b" })
local n = s.
