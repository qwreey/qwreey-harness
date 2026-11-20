//! 바뀐 줄 수와 diff 지문(python `diff_stat`, `commit_size`).

use std::sync::LazyLock;

use harness_hook::Env;
use harness_hook::py::path::join;
use harness_hook::rx::Regex;

use crate::abort::Result;
use crate::git;
use crate::pylib::hashlib::sha1_hex_prefix;

use super::commit_scope::{self, numstat_lines, sum};
use super::settings::git_abort;

static GIT_DASH_C: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\bgit\s+-C\s+(\S+)"));
static COMMIT_ALL: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\scommit\b.*\s(-a|--all|-\w*a\w*)\b"));

/// 잰 크기: 줄 수와 내용 지문 16자.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Size {
    pub lines: i128,
    pub hash: String,
}

fn git_text(cwd: &str, args: &[&str]) -> Result<String> {
    git::stdout_or_empty(cwd, args).map_err(git_abort)
}

/// python `diff_stat(cwd, *args)`: `git diff --numstat <args>` 의 합과 `git diff <args>` 글의 sha1 앞 16자.
pub fn diff_stat(cwd: &str, args: &[&str]) -> Result<Size> {
    let mut stat_args = vec!["diff", "--numstat"];
    stat_args.extend_from_slice(args);
    // Every line counts, also a path listed twice (a type change)
    let lines = sum(&numstat_lines(&git_text(cwd, &stat_args)?)?)?;

    let mut diff_args = vec!["diff"];
    diff_args.extend_from_slice(args);
    let diff = git_text(cwd, &diff_args)?;
    Ok(Size {
        lines,
        hash: sha1_hex_prefix(diff.as_bytes(), 16),
    })
}

/// python `commit_size(cmd, cwd)`: (커밋 디렉터리, 크기). dry-run 커밋이면 `None`.
pub fn commit_size(cmd: &str, cwd: &str, env: &Env) -> Result<Option<(String, Size)>> {
    let plan = commit_scope::plan(cmd, cwd, env);
    if plan.as_ref().is_some_and(|p| p.commit.dry) {
        return Ok(None);
    }

    // The same command stages: measure that scope
    if let Some(plan) = plan.as_ref().filter(|p| p.stages)
        && let Some((lines, hash)) = commit_scope::measure(plan, env)?
    {
        return Ok(Some((plan.dir.clone(), Size { lines, hash })));
    }

    // Otherwise the index (or HEAD to the work tree with -a) is what gets committed
    let (dir, all) = match &plan {
        Some(plan) => (plan.dir.clone(), plan.commit.all),
        None => {
            let dir = match GIT_DASH_C.search(cmd) {
                Some(m) => {
                    let target = m.text(cmd, 1).unwrap_or("");
                    join(cwd, target.trim_matches(['\'', '"']))
                }
                None => cwd.to_owned(),
            };
            (dir, COMMIT_ALL.is_match(cmd))
        }
    };
    let size = if all {
        diff_stat(&dir, &["HEAD"])?
    } else {
        diff_stat(&dir, &["--cached"])?
    };
    Ok(Some((dir, size)))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 모듈의 고정 정규식이 regex 판과 python 판(py::re)에서 같은 자리에 맞는다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        harness_hook::testkit::assert_agree(
            &[("GIT_DASH_C", &*GIT_DASH_C), ("COMMIT_ALL", &*COMMIT_ALL)],
            &[
                "git", " ", "-C", "commit", "x", "-a", "--all", "-qam", "\n", "_", "é", "/p", "'",
                "\u{2460}", "a",
            ],
        );
    }
}
