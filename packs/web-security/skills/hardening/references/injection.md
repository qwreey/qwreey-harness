---
title: "Injection"
description: "How to stop data crossing into another language from becoming code: shell-free exec, argv options, shell-sourced files, config templating, CSS, and untrusted repos."
keywords:
  - "injection"
  - "인젝션"
  - "명령 주입"
  - "command injection"
  - "argv injection"
  - "argv 주입"
  - "shell injection"
  - "exec without shell"
  - "셸 없이 실행"
  - "option injection"
  - "dig"
  - "gpg"
  - "bcrypt hash quoting"
  - "config injection"
  - "설정 주입"
  - "env value"
  - "nginx"
  - "Caddy"
  - "CSS escaping"
  - "ssh -G"
  - "Match exec"
  - "git filter"
  - "ext-diff"
  - "textconv"
  - "git hooks"
  - "untrusted repo"
  - "신뢰할 수 없는 저장소"
  - "path characters"
  - "파일 이름 검증"
kind: reference
---
# Injection
- Run exec without a shell. Reject positional values starting with `-` or `@` and use `--` (`dig @server`, `gpg --homedir`).
- When writing a value into a file a shell will source, single-quote and escape it (a `$2a$` bcrypt hash was mangled by variable expansion).
- Validate env values before pasting into a config file: `;`, `{` and quotes can end a directive.
- CSS escaping includes the backslash.
- Running a tool to "validate" can be the execution (`ssh -G` runs `Match exec`).
- Tools run in an untrusted repository execute that repo's config (git filter, ext-diff, textconv, hooks); override with command-scoped config.
- User-chosen names that become file paths: reject path characters.
