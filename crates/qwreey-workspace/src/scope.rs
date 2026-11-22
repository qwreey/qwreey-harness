//! 이 세션의 저장소에서 본 "다른 저장소" 판정(python `wslib.Scope`).
//!
//! 다른 저장소: 경로를 담은 git 저장소(worktree 는 본 저장소로)가 이 세션의 저장소와 다른 것. 목록은 쓰지 않는다.
//! 홈이나 설정 폴더 자체의 저장소, known_repos 의 기본 제외(임시 폴더, `~/.cache`, `.claude/worktrees/`)와
//! 사용자가 `HARNESS_WORKSPACE_EXCLUDE` 로 뺀 저장소는 다른 저장소로 보지 않는다.
//!
//! 비용: 이 세션 저장소 안 경로는 설정을 읽지 않는다. 설정과 제외 목록은 다른 저장소 후보가 처음 나올 때 읽는다.

use std::cell::{OnceCell, RefCell};
use std::collections::HashMap;

use harness_hook::known_repos::{self, PathError};
use harness_hook::py::ospath::{self, normcase};
use harness_hook::py::value::Value;
use harness_hook::settings::Values;

use crate::context::Context;
use crate::paths::{inside, own_config};
use crate::stop::{Result, Stop};

/// 한 훅 실행 동안의 판정. 같은 경로를 두 번 걷지 않게 결과를 기억한다.
pub struct Scope<'a> {
    ctx: &'a Context,
    /// 이 세션의 저장소 자리(normpath). python 판처럼 비어 있지 않다(빈 값은 `.` 이 된다).
    pub project: String,
    /// 이 세션의 저장소 루트(normcase, worktree 는 본 저장소). 저장소 밖이면 빈 글.
    own: String,
    /// 설정 층을 읽을 때 넘길 훅 입력의 `cwd`.
    cwd: Option<&'a Value>,
    settings: OnceCell<Values>,
    exclude: OnceCell<Result<Vec<String>>>,
    memo: RefCell<HashMap<String, Option<String>>>,
}

impl<'a> Scope<'a> {
    /// `project` 에서 본 판정. 저장소 루트를 바로 찾는다(python 의 `__init__` 처럼 예외 자리에서 멈춘다).
    pub fn new(ctx: &'a Context, project: &str, cwd: Option<&'a Value>) -> Result<Scope<'a>> {
        let project = ospath::normpath(project);
        let own = known_repos::try_repo_root(&project).map_err(path_raises)?;
        Ok(Scope {
            ctx,
            own: normcase(own.as_deref().unwrap_or("")),
            project,
            cwd,
            settings: OnceCell::new(),
            exclude: OnceCell::new(),
            memo: RefCell::new(HashMap::new()),
        })
    }

    /// harness.env 층(python `scope.settings()`). 처음 부를 때 읽는다.
    pub fn settings(&self) -> &Values {
        self.settings.get_or_init(|| self.ctx.load_env(self.cwd))
    }

    // 기본 제외와 사용자 제외(python `scope.exclude()`)
    fn exclude(&self) -> Result<&[String]> {
        let list = self.exclude.get_or_init(|| {
            let mut list = known_repos::default_exclude(&self.ctx.hook.env)
                .map_err(|_| Stop::Raises("no usable temporary directory"))?;
            let user = self.settings().get("HARNESS_WORKSPACE_EXCLUDE");
            list.extend(known_repos::split_paths(
                user.map_or("", String::as_str),
                &self.ctx.hook.env,
            ));
            Ok(list)
        });
        list.as_deref().map_err(|e| *e)
    }

    /// `path`(normpath)를 담은 저장소가 다른 저장소면 그 루트, 아니면 `None`.
    pub fn sibling(&self, path: &str) -> Result<Option<String>> {
        if path.is_empty() || inside(path, &self.project) {
            return Ok(None);
        }
        if let Some(known) = self.memo.borrow().get(path) {
            return Ok(known.clone());
        }

        // Repo root, then the repos that do not count
        let root = known_repos::try_repo_root(path)
            .map_err(path_raises)?
            .filter(|r| !r.is_empty() && normcase(r) != self.own);
        let root = match root {
            Some(r) if own_config(self.ctx, &r) || self.excluded(&r)? => None,
            other => other,
        };

        self.memo.borrow_mut().insert(path.to_owned(), root.clone());
        Ok(root)
    }

    fn excluded(&self, root: &str) -> Result<bool> {
        known_repos::excluded(root, self.exclude()?)
            .map_err(|_| Stop::Unported("an exclude glob the fnmatch port cannot translate"))
    }
}

fn path_raises(_: PathError) -> Stop {
    Stop::Raises("a path os.stat or os.getcwd rejects")
}
