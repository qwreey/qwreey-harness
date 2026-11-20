//! 요약 워커 띄우기(python `spawn_flush`). 워커는 python 그대로다: `python3 -I -X utf8 scripts/cli.py flush ...`.
//!
//! python 판과 같은 명령, 같은 환경(이 프로세스의 것)으로 띄우고 기다리지 않는다. POSIX 에서는 `setsid -f` 로 새 세션에서
//! 돌게 하고, `setsid` 가 없으면 python 은 `start_new_session` 이지만 여기서는 새 프로세스 그룹만 만든다(setsid 를
//! 부르려면 unsafe 가 필요하다). cwd 는 `/`, 표준 입출력은 모두 `/dev/null`.
//!
//! python 은 `close_fds=True` 다. Rust 의 `Command` 는 이 프로세스가 물려받은 fd(Claude Code 가 넘긴 파이프 등)를 그대로
//! 넘기므로, 띄우기 전에 2 보다 큰 fd 를 모두 close-on-exec 로 둔다. 오래 도는 워커가 그 파이프를 쥐고 있으면 읽는 쪽이
//! EOF 를 기다린다. 훅은 띄운 뒤 곧 끝나므로 이 프로세스의 다른 fd 에 표시가 붙어도 상관없다.

use std::process::{Command, Stdio};

use harness_hook::py::path::which;
use harness_hook::py::surrogate::{encode_os, from_os};

use crate::abort::{Abort, Result};
use crate::context::Context;

/// 워커에 넘길 것.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Flush<'a> {
    pub session: &'a str,
    pub transcript: &'a str,
    pub project: &'a str,
    pub trigger: &'a str,
    pub force: bool,
}

/// 워커 명령줄(python 의 `args`, `setsid` 앞붙임 전). python3 이나 cli.py 자리를 모르면 [`Abort`].
pub fn worker_argv(ctx: &Context, flush: &Flush<'_>) -> Result<Vec<String>> {
    let python = which("python3", &ctx.env).ok_or(Abort("python3 not on PATH"))?;
    let script = ctx.worker_script().ok_or(Abort("plugin root unknown"))?;

    // python 판의 args 와 같은 순서
    let mut argv: Vec<String> = vec![
        from_os(python.as_os_str()),
        "-I".into(),
        "-X".into(),
        "utf8".into(),
        script,
        "flush".into(),
        "--session".into(),
        flush.session.into(),
        "--transcript".into(),
        flush.transcript.into(),
        "--project".into(),
        flush.project.into(),
        "--trigger".into(),
        flush.trigger.into(),
    ];
    if flush.force {
        argv.push("--force".into());
    }
    Ok(argv)
}

// python 이 Popen 에 넘기는 바이트(os.fsencode). 바꾸지 못하면 UnicodeEncodeError 자리
fn os_args(argv: &[String]) -> Result<Vec<std::ffi::OsString>> {
    argv.iter()
        .map(|a| {
            if a.contains('\0') {
                return Err(Abort("argument has NUL"));
            }

            #[cfg(unix)]
            {
                use std::os::unix::ffi::OsStringExt;
                encode_os(a)
                    .map(std::ffi::OsString::from_vec)
                    .ok_or(Abort("unencodable argument"))
            }
            #[cfg(not(unix))]
            {
                encode_os(a)
                    .and_then(|b| String::from_utf8(b).ok())
                    .map(std::ffi::OsString::from)
                    .ok_or(Abort("unencodable argument"))
            }
        })
        .collect()
}

/// 워커를 떼어 띄운다. 띄우지 못하면(python Popen 의 OSError) [`Abort`].
pub fn spawn(ctx: &Context, flush: &Flush<'_>) -> Result<()> {
    let argv = os_args(&worker_argv(ctx, flush)?)?;
    #[cfg(unix)]
    close_fds::set_fds_cloexec(3, &[]);
    let (program, rest) = argv.split_first().ok_or(Abort("empty argv"))?;
    let mut command = detached(ctx, program, rest);
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command
        .spawn()
        .map(drop)
        .map_err(|_| Abort("cannot start the worker"))
}

#[cfg(unix)]
fn detached(ctx: &Context, program: &std::ffi::OsStr, rest: &[std::ffi::OsString]) -> Command {
    use std::os::unix::process::CommandExt;

    let mut command = match which("setsid", &ctx.env) {
        Some(setsid) => {
            let mut c = Command::new(setsid);
            c.arg("-f").arg(program).args(rest);
            c
        }
        None => {
            let mut c = Command::new(program);
            c.args(rest).process_group(0);
            c
        }
    };
    command.current_dir("/");
    command
}

// Windows: 콘솔과 프로세스 그룹에서 뗀다. python 판은 작업 객체 밖으로(CREATE_BREAKAWAY_FROM_JOB) 먼저 해 보지만
// 여기서는 하지 않는다(이 플러그인은 Linux, macOS 전용이고 Windows 는 빌드만 맞춘다)
#[cfg(windows)]
fn detached(_ctx: &Context, program: &std::ffi::OsStr, rest: &[std::ffi::OsString]) -> Command {
    use std::os::windows::process::CommandExt;

    const DETACHED_PROCESS: u32 = 0x0000_0008;
    const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
    let mut command = Command::new(program);
    command
        .args(rest)
        .creation_flags(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP);
    command
}
