# Auth gates
- Cap failure counters and backoff math (a shift overflow after 35 failures reset the lockout).
- Serialize attempts per key; N concurrent requests skipped the backoff.
- Limit concurrent runs of expensive hashes (argon2, bcrypt); they are a DoS lever.
- Every endpoint that checks a password (change, reset included) shares one lockout bucket.
- Lockout and logout end the server-side session too.
- First-run setup (claiming the first password) needs a one-time token delivered over an operator-only channel (logs), and requests are serialized.
- After adding a proxy route, confirm auth still runs first (in Caddy, `handle` ran before `respond`, so a token check on one path was skipped).
