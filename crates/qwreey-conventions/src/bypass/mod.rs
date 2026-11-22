//! bash-bypass-reminder(python `hooks/bash-bypass-reminder.py`): 셸이나 인터프리터로 파일을 읽거나 바꾸면 하네스 장치를 비껴간다고 알린다.
//!
//! PreToolUse(Bash). 막지 않고 additionalContext 만 넣는다. 쓰기 신호(sed -i, 코드 파일로의 리다이렉트, 쓰는 인터프리터 스크립트)가
//! 있으면 warn, 읽기만 하는 인터프리터 명령은 info. 종류마다, rule 파일마다 맥락(세션, agent, compact 회차)에 한 번 알린다.
//! 쓰기 신호가 있으면 bash-writes 가 명령 뒤에 견줄 스냅숏을 적는다([`crate::bash_writes::before`]).
//!
//! python 판은 본문 전체를 try 로 감싸 무엇이 틀려도 조용히 0 으로 끝난다. 이 판도 그렇다. 하나 다른 것은 python 이 모듈을 읽을 때
//! rules_inject 를 함께 읽는 자리다: plugin.json 이 dict 가 아닌 JSON 이면 python 은 예외로 끝난다([`Plugin::locate`]).

pub mod command;
pub mod rule_dirs;

use harness_hook::HookInput;
use harness_hook::epoch;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii as Ascii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{expanduser, join};
use harness_hook::py::value::Value;

use crate::bash_writes::{before, snap};
use crate::context::{Context, PLUGIN};
use crate::halt::{Halt, Result};
use crate::pyops::str_order;
use crate::pyval;
use crate::rules::{self, Plugin};
use command::{
    INPLACE, INTERP, SCRIPT_WRITE, absolute, cmd_paths, heads, redirect_targets, redirected,
};

/// 알림 상태 폴더(python `dedup_path("claude-bypass-reminder", ...)`).
const NS: &str = "claude-bypass-reminder";

const WRITE_NOTE: &str = "This command changes files without the Edit/Write tools (sed -i, redirect, patch, ...), so \
     PostToolUse hooks on Edit|Write (formatters, checkers) do not run and the repo's path-scoped .claude/rules are not \
     loaded for the file; qwreey-conventions still checks the lines it adds and shows its own rules after the command. \
     If the file has a formatter or checker, run it yourself.";

/// 이 맥락에서 이미 알린 것(python `seen` set): 종류 이름(`write`, `interp`)과 rule 파일 경로.
///
/// 상태 파일은 글 목록이다. 글이 아닌 원소가 들었으면 python 은 저장할 때 `sorted` 에서 끝난다(`mixed`).
#[derive(Default)]
struct Seen {
    names: Vec<String>,
    mixed: bool,
}

impl Seen {
    // python set(json.load(open(path))): 목록은 원소, dict 는 키, 글은 글자. 읽지 못하거나 해시할 수 없는 원소면 빈 집합
    fn load(path: &str) -> Seen {
        let Some(v) = fs::read_text(path).ok().and_then(|t| loads(&t).ok()) else {
            return Seen::default();
        };
        let items: Vec<Value> = match &v {
            Value::List(items) => items.clone(),
            Value::Dict(d) => d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect(),
            Value::Str(s) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
            _ => return Seen::default(),
        };
        if items
            .iter()
            .any(|v| matches!(v, Value::List(_) | Value::Dict(_)))
        {
            return Seen::default();
        }

        // Strings are names; anything else makes the later sort fail
        let mut seen = Seen::default();
        for v in &items {
            match v {
                Value::Str(s) => seen.add(s.clone()),
                _ => seen.mixed = true,
            }
        }
        seen
    }

    fn has(&self, name: &str) -> bool {
        self.names.iter().any(|n| n == name)
    }

    fn add(&mut self, name: String) {
        if !self.has(&name) {
            self.names.push(name);
        }
    }

    // python json.dump(sorted(seen), open(path, "w")): 쓰기 실패는 넘긴다
    fn save(&self, path: &str) {
        let mut names = self.names.clone();
        names.sort_by(|a, b| str_order(a, b));
        let list = Value::List(names.into_iter().map(Value::Str).collect());
        let _ = fs::write_text(path, &dumps(&list, Ascii::Yes, None));
    }
}

/// bash-bypass-reminder 훅 하나. python 이 조용히 넘기는 실패는 모두 `None` 이다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let plugin = Plugin::locate(ctx)?;
    Ok(remind(ctx, input, &plugin).unwrap_or(None))
}

/// 명령 하나에서 읽은 신호.
struct Signals {
    cmd: String,
    cwd: String,
    proj: String,
    heads: Vec<String>,
    /// 제자리 편집이나 코드 파일로의 리다이렉트.
    writes: bool,
    interp: bool,
    interp_writes: bool,
}

impl Signals {
    fn read(ctx: &Context, input: &HookInput) -> Result<Signals> {
        let cmd = match input.get("tool_input") {
            Some(Value::Dict(ti)) => ti
                .get("command")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_owned(),
            _ => String::new(),
        };
        let cwd = match input.cwd() {
            Some(c) if !c.is_empty() => c.to_owned(),
            _ => rules::getcwd()?,
        };
        let proj = ctx
            .env
            .get_nonempty("CLAUDE_PROJECT_DIR")
            .unwrap_or(&cwd)
            .to_owned();

        // Programs run, and whether something writes
        let heads = heads(&cmd);
        let writes = INPLACE.is_match(&cmd) || !redirect_targets(&cmd).is_empty();
        let interp = heads.iter().any(|h| INTERP.contains(&h.as_str()));
        let interp_writes = interp && SCRIPT_WRITE.is_match(&cmd);
        Ok(Signals {
            cmd,
            cwd,
            proj,
            heads,
            writes,
            interp,
            interp_writes,
        })
    }
}

fn remind(ctx: &Context, input: &HookInput, plugin: &Plugin) -> Result<Option<String>> {
    let s = Signals::read(ctx, input)?;
    let _ = snap::sweep(ctx);
    let git_only = s.heads.first().is_some_and(|h| h == "git" || h == "gh");
    if git_only && !INPLACE.is_match(&s.cmd) {
        return Ok(None);
    }

    // What this context was already told
    let sid = pyval::truthy_text(input.get("session_id")).unwrap_or_default();
    let agent = pyval::truthy_text(input.get("agent_id"));
    let state_path = epoch::state_path(ctx.tempdir()?, PLUGIN, NS, &sid, agent.as_deref())
        .map_err(|_| Halt::PyError("cannot create the reminder state folder"))?;
    let mut seen = Seen::load(&state_path);

    // Snapshot for the after-command check; a failure keeps the reminder
    let _ = take_snapshot(ctx, input, &s);

    let (notes, warn) = notes(ctx, plugin, &s, &mut seen)?;
    if notes.is_empty() || seen.mixed {
        return Ok(None);
    }

    // Remember, then one tag
    seen.save(&state_path);
    let level = if warn { "warn" } else { "info" };
    let nonce = ctx.nonce_attr(input.get("session_id"))?;
    let text = format!(
        "<harness-hook name=\"bash-bypass-reminder\" level=\"{level}\"{nonce}>\n{}\n</harness-hook>",
        notes.join(" ")
    );
    Ok(Some(
        HookOutput::context("PreToolUse", text).render(EnsureAscii::No),
    ))
}

// 알림 문장들과 warn 인가: 쓰기나 인터프리터(종류마다 한 번), 그다음 건드리는 파일에 맞는 rule(파일마다 한 번)
fn notes(
    ctx: &Context,
    plugin: &Plugin,
    s: &Signals,
    seen: &mut Seen,
) -> Result<(Vec<String>, bool)> {
    let mut notes: Vec<String> = Vec::new();
    let mut warn = false;
    if s.writes && !seen.has("write") {
        seen.add("write".into());
        warn = true;
        notes.push(WRITE_NOTE.to_owned());
    } else if s.interp && !seen.has("interp") {
        seen.add("interp".into());
        warn |= s.interp_writes;
        notes.push(interp_note(&s.heads));
    }
    if !(s.writes || s.interp) {
        return Ok((notes, warn));
    }

    // Rules for the files the command names
    let hit = rules_hit(ctx, plugin, s, seen)?;
    if !hit.is_empty() {
        warn |= s.writes || s.interp_writes;
        let shown: Vec<&str> = hit.iter().map(|(_, d)| d.as_str()).collect();
        notes.push(format!(
            "Rules that apply to files this command touches: {}. If this command writes these files, read the rules first if \
             you have not; read-only commands need nothing.",
            shown.join(", ")
        ));
        for (path, _) in hit {
            seen.add(path);
        }
    }
    Ok((notes, warn))
}

fn interp_note(heads: &[String]) -> String {
    let mut names: Vec<&str> = INTERP
        .iter()
        .copied()
        .filter(|i| heads.iter().any(|h| h == i))
        .collect();
    names.sort_by(|a, b| str_order(a, b));
    format!(
        "Reading or changing files through an interpreter ({}) bypasses the Read/Edit/Write tools: path-scoped .claude/rules \
         may not load and Edit|Write hooks do not run. If you generate or bulk-edit source with a script, first check the \
         relevant skills and rules (naming, idioms). Scratch or generated output needs nothing.",
        names.join(", ")
    )
}

// python 의 스냅숏 자리: 리다이렉트 대상(코드 파일이 아닌 것도)과 경로 꼴 낱말, 그리고 쓰기 신호
fn take_snapshot(ctx: &Context, input: &HookInput, s: &Signals) -> Result<()> {
    let targets: Vec<String> = redirected(&s.cmd)
        .iter()
        .map(|t| absolute(t, &s.cwd))
        .collect();
    let inside = |t: &String| rules_inside(t, &s.proj) || rules_inside(t, &s.cwd);
    let signal = INPLACE.is_match(&s.cmd) || s.interp_writes || targets.iter().any(inside);
    let mut candidates = targets;
    candidates.extend(cmd_paths(&s.cmd).iter().map(|p| absolute(p, &s.cwd)));
    let b = before::Before {
        cmd: &s.cmd,
        cwd: &s.cwd,
        candidates: &candidates,
        signal,
    };
    before::take(ctx, input, &b)
}

// python 의 bypass 쪽 `_inside(path, root)`: 이미 정리한 경로가 root/ 아래인가
fn rules_inside(path: &str, root: &str) -> bool {
    let root = harness_hook::py::path::normpath(root);
    path.starts_with(&format!("{}/", root.trim_end_matches('/')))
}

// 명령이 건드리는 파일에 맞고 아직 알리지 않은 rule 파일: (경로, 알림에 적는 글)
fn rules_hit(
    ctx: &Context,
    plugin: &Plugin,
    s: &Signals,
    seen: &Seen,
) -> Result<Vec<(String, String)>> {
    let dirs = rule_dirs::plugin_rule_dirs(ctx, &plugin.rules_dir(), &s.proj)?;
    let mut roots = vec![
        join(&join(&s.proj, ".claude"), "rules"),
        join(&join(&expanduser("~", &ctx.env), ".claude"), "rules"),
    ];
    roots.extend(dirs.dirs().map(str::to_owned));
    let found = rule_dirs::load_rules(ctx, &roots)?;
    let abs_paths: Vec<String> = cmd_paths(&s.cmd)
        .iter()
        .map(|p| absolute(p, &s.cwd))
        .collect();

    let mut hit = Vec::new();
    for r in found {
        if seen.has(&r.path) {
            continue;
        }
        let mut matched = false;
        for ap in &abs_paths {
            if rules::rule_matches(&r.regexes, ap, &s.proj)? {
                matched = true;
                break;
            }
        }
        if matched {
            let shown = rule_dirs::describe(&r.path, &dirs, &s.proj, &ctx.env);
            hit.push((r.path, shown));
        }
    }
    Ok(hit)
}
