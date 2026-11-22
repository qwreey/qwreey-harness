//! 쓴 파일이 이 저장소의 기록인가(python `records_rel`), 형제 저장소 목록(python `siblings`).

use std::sync::LazyLock;

use harness_hook::known_repos;
use harness_hook::py::ospath::{self, basename, dirname, normcase};
use harness_hook::rx::Regex;

use super::hits::Sibling;
use crate::paths::inside;
use crate::stop::{Result, Stop};

/// 기록이 아닌 `.claude/` 첫 단계: worktree 사본, 모델용 규약과 설정.
const SKIP_TOP: &[&str] = &[
    "worktrees",
    "rules",
    "skills",
    "agents",
    "commands",
    "hooks",
];

static SKIP_FILE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^(?:settings(?:\.local)?\.json|harness(?:\.local)?\.env)$"));

/// python `records_rel(path, project)`: 기록이면 기록 뿌리의 `.claude/` 기준 상대 경로, 아니면 `None`.
///
/// 기록 뿌리는 이 저장소, 또는 그 안 `.claude/worktrees/<이름>` worktree 다. 둘 다 normpath 한 경로다.
pub fn records_rel(path: &str, project: &str) -> Result<Option<String>> {
    if !inside(path, project) || path == project {
        return Ok(None);
    }
    let rel = ospath::relpath(path, project).ok_or(Stop::Raises("os.path.relpath"))?;

    // python Path(rel).parts: 빈 조각과 `.` 은 없다
    let seps: &[char] = if cfg!(windows) { &['\\', '/'] } else { &['/'] };
    let mut parts: Vec<&str> = rel
        .split(seps)
        .filter(|p| !p.is_empty() && *p != ".")
        .collect();

    // A worktree of this repo keeps the same records
    if parts.len() > 3 && parts[0] == ".claude" && parts[1] == "worktrees" {
        parts.drain(..3);
    }
    if parts.len() < 2 || parts[0] != ".claude" || SKIP_TOP.contains(&parts[1]) {
        return Ok(None);
    }
    if parts.len() == 2 && SKIP_FILE.match_start(parts[1]).is_some() {
        return Ok(None);
    }
    Ok(Some(parts[1..].join("/")))
}

/// python `siblings(project, repos)`: 형제 저장소들(이름은 폴더 이름), 정렬한 저장소 순서.
///
/// 이 세션 저장소와 그와 이름이 같은 저장소는 뺀다(`../<이름>` 이 어느 쪽인지 모른다). 이름이 겹치면 이 저장소와
/// 같은 폴더에 있는 것, 없으면 경로순 첫째.
pub fn siblings(project: &str, repos: &[String]) -> Result<Vec<Sibling>> {
    let own = known_repos::try_repo_root(project)
        .map_err(|_| Stop::Raises("a project path os.stat rejects"))?
        .unwrap_or_else(|| project.to_owned());
    let mine = normcase(&own);
    let parent = normcase(dirname(&own));

    let mut sorted = repos.to_vec();
    sorted.sort();
    let mut out: Vec<Sibling> = Vec::new();
    for r in sorted {
        let name = basename(&r);
        if name.is_empty() || normcase(&r) == mine || name == basename(&own) {
            continue;
        }

        // A same-named repo next to this one wins
        let near = |root: &str| normcase(dirname(root)) == parent;
        match out.iter_mut().find(|s| s.name == name) {
            None => out.push(Sibling {
                name: name.to_owned(),
                root: r.clone(),
            }),
            Some(s) if near(&r) && !near(&s.root) => s.root = r.clone(),
            Some(_) => {}
        }
    }
    Ok(out)
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    /// `.claude/` 아래 기록만, worktree 의 기록도 같은 저장소의 기록이다.
    #[test]
    fn records_rel_like_python() {
        let p = "/w/mine";
        let rel = |path: &str| records_rel(path, p).unwrap();
        assert_eq!(
            rel("/w/mine/.claude/audit/a.md").as_deref(),
            Some("audit/a.md")
        );
        assert_eq!(rel("/w/mine/.claude/rules/a.md"), None);
        assert_eq!(rel("/w/mine/src/a.md"), None);
        assert_eq!(rel("/w/other/.claude/a.md"), None);
        assert_eq!(
            rel("/w/mine/.claude/worktrees/w1/.claude/plan/q.md").as_deref(),
            Some("plan/q.md")
        );
        assert_eq!(rel("/w/mine/.claude/worktrees/w1/src/a.py"), None);

        // `$` also matches before a final newline
        assert_eq!(rel("/w/mine/.claude/settings.json\n"), None);
    }

    /// 같은 이름이면 이 저장소 옆의 것.
    #[test]
    fn same_name_prefers_the_same_folder() {
        let repos = ["/e/other".to_owned(), "/w/other".to_owned()];
        let sibs = siblings("/w/mine", &repos).unwrap();
        assert_eq!(
            sibs,
            vec![Sibling {
                name: "other".into(),
                root: "/w/other".into()
            }]
        );
    }
}
