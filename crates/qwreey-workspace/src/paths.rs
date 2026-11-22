//! 경로 글 다루기(python `wslib` 의 `expand`, `norm`, `inside`, `shown`, `_own_config`).
//!
//! 경로 판정은 normpath 만 한다. realpath 는 쓰지 않는다: `~/.claude/rules` 의 symlink 는 형제 저장소 경로가 아니라
//! 이 세션의 규칙 파일이다. 경로 함수는 이 OS 의 python `os.path` 다([`harness_hook::py::ospath`]).

use harness_hook::py::ospath::{self, SEP};

use crate::context::Context;
use crate::stop::{Result, Stop};

/// 경로를 이을 기준 폴더(python 의 `cwd` 값). `None` 은 문자열이 아닌 참 값이다: python 은 그것을 `os.path.join` 에
/// 넘기는 자리에서 TypeError 로 끝난다.
pub type Base<'a> = Option<&'a str>;

/// python `os.path.expanduser("~")`: 홈. 모르면 `~` 그대로.
pub fn home(ctx: &Context) -> String {
    ospath::expanduser("~", &ctx.hook.env)
}

/// python `wslib.expand(p)`: 맨 앞 `$HOME`, `${HOME}` 을 홈으로, 그 뒤 `~` 로 시작하면 expanduser.
///
/// python 의 패턴 `^\$\{?HOME\}?` 는 두 괄호를 따로 본다: `$HOMEX` 도 `$HOME` 뒤에 `X` 가 붙은 꼴이다.
pub fn expand(ctx: &Context, p: &str) -> String {
    let p = match home_var_len(p) {
        Some(len) => format!("{}{}", home(ctx), &p[len..]),
        None => p.to_owned(),
    };
    if p.starts_with('~') {
        ospath::expanduser(&p, &ctx.hook.env)
    } else {
        p
    }
}

// `^\$\{?HOME\}?` 가 맞는 길이
fn home_var_len(p: &str) -> Option<usize> {
    let rest = p.strip_prefix('$')?;
    let rest = rest.strip_prefix('{').unwrap_or(rest);
    let rest = rest.strip_prefix("HOME")?;
    let rest = rest.strip_prefix('}').unwrap_or(rest);
    Some(p.len() - rest.len())
}

/// python `wslib.norm(p, cwd)`: 펼친 뒤 상대 경로면 `cwd`(빈 글이면 `/`)에 잇고 normpath.
pub fn norm(ctx: &Context, p: &str, cwd: Base) -> Result<String> {
    let p = expand(ctx, p);
    if ospath::isabs(&p) {
        return Ok(ospath::normpath(&p));
    }
    let Some(cwd) = cwd else {
        return Err(Stop::Raises("os.path.join on a cwd that is not a str"));
    };
    let base = if cwd.is_empty() { "/" } else { cwd };
    Ok(ospath::normpath(&ospath::join(base, &p)))
}

/// python `wslib.inside(p, root)`: normcase 한 `p` 가 `root` 이거나 그 아래인가(두 구분자 모두 받는다).
pub fn inside(p: &str, root: &str) -> bool {
    let p = ospath::normcase(p);
    let root = ospath::normcase(root);
    let root = root.trim_end_matches(['/', '\\']);
    p == root || p.starts_with(&format!("{root}{SEP}")) || p.starts_with(&format!("{root}/"))
}

/// python `wslib.shown(path)`: 모델에게 보일 경로. 홈 아래는 `~/` 꼴로 줄인다.
pub fn shown(ctx: &Context, path: &str) -> String {
    let home = home(ctx);
    let under = path == home || path.starts_with(&format!("{}{SEP}", home.trim_end_matches(SEP)));
    if home.is_empty() || home == SEP.to_string() || !under {
        return path.to_owned();
    }
    // python 은 홈의 글자 수만큼 자른다(홈 끝에 구분자가 겹치면 path 의 접두와 길이가 다를 수 있다)
    let rest: String = path.chars().skip(home.chars().count()).collect();
    format!("~{}", rest.replace(SEP, "/"))
}

/// python `wslib._own_config(root)`: 홈 폴더나 Claude Code 설정 폴더 자체의 저장소(dotfiles)인가.
///
/// 그런 저장소는 "다른 저장소"가 아니다: memory, 계획, 설정 쓰기가 스킬 전까지 막히면 안 된다.
pub fn own_config(ctx: &Context, root: &str) -> bool {
    let home = home(ctx);
    let cfg = match ctx.env_var("CLAUDE_CONFIG_DIR").filter(|c| !c.is_empty()) {
        Some(dir) => dir,
        None => ospath::join(&home, ".claude"),
    };
    let r = ospath::normcase(&ospath::normpath(root));
    r == ospath::normcase(&ospath::normpath(&home)) || inside(&r, &ospath::normpath(&cfg))
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use harness_hook::Env;

    fn ctx(home: &str) -> Context {
        Context::new(Env::from_pairs([("HOME", home)]), None)
    }

    /// `$HOME` 꼴과 `~` 를 펼치고, 상대 경로는 cwd 에 잇는다.
    #[test]
    fn expand_and_norm() {
        let c = ctx("/h/u");
        assert_eq!(expand(&c, "${HOME}/a"), "/h/u/a");
        assert_eq!(expand(&c, "$HOMEX"), "/h/uX");
        assert_eq!(expand(&c, "~/b"), "/h/u/b");
        assert_eq!(expand(&c, "$HOMER"), "/h/uR");
        assert_eq!(norm(&c, "a/../b", Some("/w")).unwrap(), "/w/b");
        assert_eq!(norm(&c, "x", Some("")).unwrap(), "/x");

        // 상대 경로만 글인 cwd 가 있어야 한다
        assert!(norm(&c, "x", None).is_err());
        assert_eq!(norm(&c, "/x", None).unwrap(), "/x");
    }

    /// 홈 아래는 `~/` 꼴, 홈이 `/` 면 그대로다.
    #[test]
    fn shown_shortens_home() {
        assert_eq!(shown(&ctx("/h/u"), "/h/u/r"), "~/r");
        assert_eq!(shown(&ctx("/h/u"), "/h/ux"), "/h/ux");
        assert_eq!(shown(&ctx("/"), "/r"), "/r");
        assert!(inside("/a/b/", "/a/b/") && inside("/a/b/c", "/a/b") && !inside("/a/bc", "/a/b"));
    }
}
