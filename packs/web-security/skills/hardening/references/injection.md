# Injection
- Run exec without a shell. Reject positional values starting with `-` or `@` and use `--` (`dig @server`, `gpg --homedir`).
- When writing a value into a file a shell will source, single-quote and escape it (a `$2a$` bcrypt hash was mangled by variable expansion).
- Validate env values before pasting into a config file: `;`, `{` and quotes can end a directive.
- CSS escaping includes the backslash.
- Running a tool to "validate" can be the execution (`ssh -G` runs `Match exec`).
- Tools run in an untrusted repository execute that repo's config (git filter, ext-diff, textconv, hooks); override with command-scoped config.
- User-chosen names that become file paths: reject path characters.
