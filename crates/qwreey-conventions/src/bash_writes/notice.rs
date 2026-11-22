//! bash-writes 의 알림 글(python `bash_writes.notices`, `reuse_notes`, `rules_block`, `more_line`).
//!
//! 출력 하나를 [`OUTPUT_BUDGET`] 안에 둔다: 알림을 파일 순서로 넣고, 안 드는 파일부터는 conventions-scan 명령 한 줄로 넘기고,
//! rule 은 남은 자리에만 넣는다(안 든 rule 은 마커를 잡지 않아 다음 Read, Edit 에서 실린다).

use std::collections::HashSet;
use std::time::Instant;

use harness_hook::HookInput;
use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{basename, join, relpath};
use harness_hook::py::value::{Dict, Value};

use super::changes::Changed;
use crate::check::{self, state};
use crate::context::Context;
use crate::edit::added_set;
use crate::halt::{Halt, Result};
use crate::rules::{self, Plugin};
use crate::{reuse, stdout};

/// 훅 출력 하나가 10,000자를 넘으면 잘리므로 rules-inject 시험과 같은 여유를 둔다(python `OUTPUT_BUDGET`).
pub const OUTPUT_BUDGET: usize = 9000;
/// 알림을 낸 파일 수 한도(python `NOTICE_FILES_MAX`).
const NOTICE_FILES_MAX: usize = 10;
/// 알림을 만드는 시간 한도(python `BUDGET_S`, 훅 시작부터).
const BUDGET_S: f64 = 2.5;
/// 사본 검사를 돌리는 코드 파일 수(python `REUSE_MAX`).
const REUSE_MAX: usize = 4;
/// scan 명령 줄에 적는 경로 글자 수.
const SCAN_PATHS_MAX: usize = 600;

/// python 글자 수(`len(text)`).
fn chars(text: &str) -> usize {
    text.chars().count()
}

/// 추가 줄 알림 본문들과, 사본 검사에 넘길 코드 파일.
pub struct Notices {
    pub body: Vec<String>,
    pub code: Vec<Changed>,
}

/// python `more_line(root, left)`: 알림에 담지 못한 파일을 conventions-scan 명령 한 줄로.
pub fn more_line(plugin_root: &str, root: &str, left: &[String]) -> Result<String> {
    let rels: Vec<String> = left
        .iter()
        .map(|p| relpath(p, root).ok_or(Halt::PyError("os.path.relpath failed")))
        .collect::<Result<_>>()?;

    // Paths up to the width the line allows
    let mut shown: Vec<&str> = Vec::new();
    let mut size = 0;
    for r in &rels {
        if size + chars(r) > SCAN_PATHS_MAX {
            break;
        }
        shown.push(r);
        size += chars(r) + 1;
    }
    let rest = if shown.len() < rels.len() {
        format!(" (and {} more)", rels.len() - shown.len())
    } else {
        String::new()
    };
    let scan = join(&join(plugin_root, "scripts"), "conventions-scan.py");
    Ok(format!(
        "{} more files: run `python3 -I {scan} scan {}`{rest} and fix what it lists in lines you added.",
        rels.len(),
        shown.join(" ")
    ))
}

/// python `notices(cc, data, snap, items, t0, unread)`: 파일 순서로 conventions-check 의 `file_notice` 를 돌린 알림.
///
/// 본문은 알림 태그를 씌워도 [`OUTPUT_BUDGET`] 안에 든다. 담지 못한 알림은 알린 것으로 적지 않는다.
pub fn notices(
    ctx: &Context,
    input: &HookInput,
    plugin_root: &str,
    root: &str,
    items: &[Changed],
    unread: &[String],
    t0: Instant,
) -> Result<Notices> {
    let state_path = check::state_file(ctx, input)?;
    let tails_room = chars(check::COMMENT_TAIL) + chars(check::DOC_TAIL) + 2;
    let wide = join(root, &"x".repeat(SCAN_PATHS_MAX));
    let more_room = chars(&more_line(plugin_root, root, &[wide.clone(), wide])?) + 1;
    let mut room = OUTPUT_BUDGET as i64
        - chars(&check::notice_tag(ctx, input, &[])?) as i64
        - tails_room as i64
        - more_room as i64;

    // Files in order, under the state lock
    let mut out = Notices {
        body: Vec::new(),
        code: Vec::new(),
    };
    let mut tails: Vec<&'static str> = Vec::new();
    let mut left: Vec<String> = Vec::new();
    {
        let _lock = state::StateLock::acquire(&state_path);
        let mut st = state::load(&state_path);
        let (mut dirty, mut noticed) = (false, 0);
        for (i, item) in items.iter().enumerate() {
            if noticed >= NOTICE_FILES_MAX || t0.elapsed().as_secs_f64() > BUDGET_S {
                left = items[i..].iter().map(|c| c.path.clone()).collect();
                break;
            }
            let Some(target) = check::target(ctx, &item.path, input.get("cwd"))? else {
                continue;
            };
            if target.skips_generated(&item.now) {
                continue;
            }

            // One file's notice, kept only if it fits
            let keep = st.clone();
            let added = added_set(&item.before, &item.now, 0);
            let edit = check::Edit {
                path: &item.path,
                target: &target,
                text: &item.now,
                added: &added,
            };
            let (parts, changed) = check::file_notice(ctx, input, &edit, &mut st, false)?;
            let size: usize = parts.iter().map(|p| chars(p) + 1).sum();
            if !parts.is_empty() && size as i64 > room {
                st = keep;
                left = items[i..].iter().map(|c| c.path.clone()).collect();
                break;
            }
            dirty |= changed;
            if !parts.is_empty() {
                noticed += 1;
                room -= size as i64;
                out.body.extend(parts);
                tails.push(target.tail());
            }
            if target.is_code() {
                out.code.push(item.clone());
            }
        }
        if dirty {
            state::save(&state_path, &st);
        }
    }

    // One answer sentence per kind, then the files left over
    let mut once = HashSet::new();
    out.body.extend(
        tails
            .into_iter()
            .filter(|t| once.insert(*t))
            .map(str::to_owned),
    );
    let have: HashSet<String> = left.iter().cloned().collect();
    left.extend(unread.iter().filter(|p| !have.contains(*p)).cloned());
    if !left.is_empty() {
        out.body.push(more_line(plugin_root, root, &left)?);
    }
    Ok(out)
}

/// python `reuse_notes(data, items)`: reuse-check 를 Write 꼴 입력으로 돌린 알림 본문들(처음 [`REUSE_MAX`] 개 파일).
///
/// python 은 하위 프로세스를 띄워 그 stdout 을 읽는다. 여기서는 같은 입력으로 reuse-check 를 불러 같은 바이트에서 본문을 뗀다:
/// 실패하거나, 출력이 UTF-8 이 아니거나(파일 이름의 바이트), 꼴이 다르면 그 파일은 건너뛴다.
pub fn reuse_notes(ctx: &Context, input: &HookInput, code: &[Changed]) -> Vec<String> {
    code.iter()
        .take(REUSE_MAX)
        .filter_map(|item| {
            let payload = reuse_payload(input, item);
            let child =
                HookInput::from_slice(dumps(&payload, EnsureAscii::Yes, None).as_bytes()).ok()?;
            let out = reuse::run(ctx, &child).ok()??;
            let (bytes, whole) = stdout::python_bytes(&out);
            let text = String::from_utf8(bytes).ok().filter(|_| whole)?;
            let parsed = loads(&text).ok()?;
            let context = parsed
                .as_dict()?
                .get("hookSpecificOutput")?
                .as_dict()?
                .get("additionalContext")?;
            tag_body(context.as_str()?).map(str::to_owned)
        })
        .collect()
}

// python 의 payload: 참인 세션 값과 Write 꼴의 편집
fn reuse_payload(input: &HookInput, item: &Changed) -> Value {
    let mut d = Dict::new();
    for k in ["session_id", "agent_id", "cwd", "transcript_path"] {
        if let Some(v) = input.get(k).filter(|v| v.truthy()) {
            d.insert(k, v.clone());
        }
    }
    let mut ti = Dict::new();
    ti.insert("file_path", Value::Str(item.path.clone()));
    ti.insert("content", Value::Str(item.now.clone()));
    let mut resp = Dict::new();
    if item.before.is_empty() {
        resp.insert("type", Value::Str("create".into()));
    } else {
        resp.insert("type", Value::Str("update".into()));
        resp.insert("originalFile", Value::Str(item.before.clone()));
    }
    d.insert("hook_event_name", Value::Str("PostToolUse".into()));
    d.insert("tool_name", Value::Str("Write".into()));
    d.insert("tool_input", Value::Dict(ti));
    d.insert("tool_response", Value::Dict(resp));
    Value::Dict(d)
}

// python re.match(r"<harness-hook [^>]*>(.*)</harness-hook>\Z", ctx, re.S).group(1): 처음 `>` 뒤부터 끝 닫는 태그 앞까지
fn tag_body(ctx: &str) -> Option<&str> {
    let rest = ctx.strip_prefix("<harness-hook ")?;
    let open_end = rest.find('>')?;
    rest[open_end + 1..].strip_suffix("</harness-hook>")
}

/// python `rules_block(data, paths, room)`: 바뀐 파일에 맞는 rule 가운데 이 맥락에 아직 안 넣은 것.
///
/// `room` 글자 안에 드는 것만 마커를 잡는다. 이 판도 rules-inject 의 마커와 글을 쓴다.
pub fn rules_block(
    ctx: &Context,
    input: &HookInput,
    paths: &[String],
    room: i64,
) -> Result<String> {
    if ctx.is_off("HARNESS_CONVENTIONS_RULES") {
        return Ok(String::new());
    }
    let plugin = Plugin::locate(ctx)?;
    let proj = rules::project_root(ctx, input.get("cwd"))?;
    let skip = rules::excluded(&proj)?;
    let base = plugin.marker_base(ctx, input)?;
    let all = rules::load_dir(&plugin.rules_dir())?;

    // The first changed file each rule matches
    let mut hits: Vec<(String, String, String)> = Vec::new();
    for ap in paths {
        if rules::skipped_dir(ap, &proj) {
            continue;
        }
        for r in &all {
            let fresh = !hits.iter().any(|(n, _, _)| *n == r.name)
                && !skip.contains(&r.name)
                && !fs::exists(&format!("{base}.{}", r.name));
            if fresh && rules::rule_matches(&r.regexes, ap, &proj)? && r.text.switch_on(ctx) {
                let body = rules::with_setting(ctx, &r.name, &r.text.body, ap, input);
                hits.push((r.name.clone(), body, ap.clone()));
            }
        }
    }

    // Rules that fit, each claimed
    let nonce = ctx.nonce_attr(input.get("session_id"))?;
    let (mut picked, mut files): (Vec<(String, String)>, Vec<String>) = (Vec::new(), Vec::new());
    for (name, body, ap) in hits {
        let mut trial_files = files.clone();
        trial_files.push(basename(&ap).to_owned());
        let trial_picked: Vec<(String, String)> = picked
            .iter()
            .cloned()
            .chain([(name.clone(), body.clone())])
            .collect();
        let trial = rules::injection(
            &plugin.name,
            &nonce,
            &label(&trial_files),
            &trial_picked,
            true,
        );
        if chars(&trial) as i64 <= room && rules::claim(&base, &name) {
            picked.push((name, body));
            files.push(basename(&ap).to_owned());
        }
    }
    if picked.is_empty() {
        return Ok(String::new());
    }
    Ok(rules::injection(
        &plugin.name,
        &nonce,
        &label(&files),
        &picked,
        true,
    ))
}

// python ", ".join(dict.fromkeys(files))
fn label(files: &[String]) -> String {
    let mut once = HashSet::new();
    let unique: Vec<&str> = files
        .iter()
        .map(String::as_str)
        .filter(|f| once.insert(*f))
        .collect();
    unique.join(", ")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 태그 본문은 처음 `>` 뒤에서 끝 닫는 태그 앞까지다.
    #[test]
    fn tag_body_like_python_regex() {
        assert_eq!(
            tag_body("<harness-hook name=\"a\" nonce=\"n\">x > y</harness-hook>"),
            Some("x > y")
        );
        assert_eq!(tag_body("<harness-hook a>b</harness-hook>\n"), None);
        assert_eq!(tag_body("<harness-hook>b</harness-hook>"), None);
    }

    /// 경로는 600자까지 적고 나머지는 수로 센다.
    #[test]
    fn more_line_counts_the_rest() {
        let left: Vec<String> = (0..3)
            .map(|i| format!("/r/{}{i}.py", "a".repeat(290)))
            .collect();
        let line = more_line("/p", "/r", &left).unwrap();
        assert!(
            line.starts_with("3 more files: run `python3 -I /p/scripts/conventions-scan.py scan ")
        );
        assert!(line.ends_with("` (and 1 more) and fix what it lists in lines you added."));
    }
}
