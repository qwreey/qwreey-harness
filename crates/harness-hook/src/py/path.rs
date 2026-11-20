//! python `os.path.expanduser`, pathlib 의 경로 문자열, `shutil.which`.

use std::path::{Path, PathBuf};

use crate::env::Env;

/// python `os.path.expanduser(path)`: 맨 앞 `~` 를 홈으로 바꾼다. 홈을 모르면 그대로 돌려준다.
///
/// POSIX: `~` 는 `$HOME`(빈 값도 그대로), 없으면 계정 홈. `~user` 는 Linux 에서 `/etc/passwd` 의 홈이다
/// (python 은 `pwd.getpwnam` 이라 NSS 의 다른 출처(LDAP, systemd userdb)의 사용자도 푼다). 그 밖의 OS 에서는 바꾸지 않는다.
pub fn expanduser(path: &str, env: &Env) -> String {
    if !path.starts_with('~') {
        return path.to_owned();
    }
    expand_home(path, env).unwrap_or_else(|| path.to_owned())
}

#[cfg(not(windows))]
fn expand_home(path: &str, env: &Env) -> Option<String> {
    let end = path[1..].find('/').map_or(path.len(), |i| i + 1);
    let home = if end == 1 {
        env.get("HOME").or_else(|| env.account_home())?.to_owned()
    } else {
        passwd_home(&path[1..end])?
    };

    let joined = format!("{}{}", home.trim_end_matches('/'), &path[end..]);
    Some(if joined.is_empty() {
        "/".to_owned()
    } else {
        joined
    })
}

// /etc/passwd 에서 `name` 의 홈(여섯째 칸)
#[cfg(target_os = "linux")]
fn passwd_home(name: &str) -> Option<String> {
    let passwd = std::fs::read_to_string("/etc/passwd").ok()?;
    passwd
        .lines()
        .map(|line| line.split(':').collect::<Vec<_>>())
        .find(|f| f.len() >= 7 && f[0] == name)
        .map(|f| f[5].to_owned())
}

#[cfg(all(not(windows), not(target_os = "linux")))]
fn passwd_home(_name: &str) -> Option<String> {
    None
}

// ntpath.expanduser: %USERPROFILE%, 없으면 %HOMEDRIVE%%HOMEPATH%. `~user` 는 홈과 같은 부모 아래 형제 폴더로 짐작한다
#[cfg(windows)]
fn expand_home(path: &str, env: &Env) -> Option<String> {
    let end = path[1..].find(['/', '\\']).map_or(path.len(), |i| i + 1);
    let mut home = match env.get("USERPROFILE") {
        Some(profile) => profile.to_owned(),
        None => format!(
            "{}{}",
            env.get("HOMEDRIVE").unwrap_or(""),
            env.get("HOMEPATH")?
        ),
    };

    // 다른 사용자의 홈은 내 홈의 형제 폴더로 짐작한다
    if end != 1 {
        let target = &path[1..end];
        if Some(target) != env.get("USERNAME") {
            let (parent, base) = home.rsplit_once(['/', '\\']).unwrap_or(("", home.as_str()));
            if env.get("USERNAME") != Some(base) {
                return None;
            }
            home = format!("{parent}\\{target}");
        }
    }

    Some(format!("{home}{}", &path[end..]))
}

/// python `str(pathlib.PurePosixPath(path))`: 겹친 `/` 와 `.` 조각을 지우고 끝 `/` 를 뗀다. 빈 경로는 `.`.
///
/// 맨 앞 `//` 두 개는 그대로 둔다(POSIX 가 뜻을 정하지 않은 꼴이라 pathlib 이 보존한다). `..` 는 풀지 않는다.
/// Windows 에서는 바꾸지 않고 돌려준다(pathlib 의 드라이브, UNC 규칙은 옮기지 않았다).
pub fn pathlib_str(path: &str) -> String {
    if cfg!(windows) {
        return path.to_owned();
    }
    let root = if !path.starts_with('/') {
        ""
    } else if path.starts_with("//") && !path.starts_with("///") {
        "//"
    } else {
        "/"
    };
    let parts: Vec<&str> = path
        .split('/')
        .filter(|p| !p.is_empty() && *p != ".")
        .collect();
    let joined = format!("{root}{}", parts.join("/"));
    if joined.is_empty() {
        ".".to_owned()
    } else {
        joined
    }
}

/// python `posixpath.normpath(path)`: 겹친 `/`, `.` 을 지우고 `..` 를 글자로 푼다(링크를 보지 않는다). 빈 경로는 `.`.
pub fn normpath(path: &str) -> String {
    if path.is_empty() {
        return ".".to_owned();
    }
    let slashes = if path.starts_with("//") && !path.starts_with("///") {
        2
    } else {
        usize::from(path.starts_with('/'))
    };

    // 조각마다 `..` 는 앞 조각을 지운다(맨 위에서는 버리고, 상대 경로 맨 앞에서는 남긴다)
    let mut parts: Vec<&str> = Vec::new();
    for part in path.split('/') {
        if part.is_empty() || part == "." {
            continue;
        }
        if part != ".." || (slashes == 0 && parts.is_empty()) || parts.last() == Some(&"..") {
            parts.push(part);
        } else {
            parts.pop();
        }
    }

    let joined = format!("{}{}", "/".repeat(slashes), parts.join("/"));
    if joined.is_empty() {
        ".".to_owned()
    } else {
        joined
    }
}

/// python `os.path.abspath(path)`. 현재 디렉터리를 읽지 못하면 `None`.
///
/// POSIX 는 현재 디렉터리에 이어 [`normpath`], Windows 는 `std::path::absolute`(python 도 GetFullPathNameW 다).
pub fn abspath(path: &str) -> Option<String> {
    if cfg!(windows) {
        return std::path::absolute(path)
            .ok()
            .and_then(|p| p.into_os_string().into_string().ok());
    }
    if path.starts_with('/') {
        return Some(normpath(path));
    }
    let cwd = std::env::current_dir()
        .ok()?
        .into_os_string()
        .into_string()
        .ok()?;
    let joined = if cwd.ends_with('/') {
        format!("{cwd}{path}")
    } else {
        format!("{cwd}/{path}")
    };
    Some(normpath(&joined))
}

/// python `posixpath.join(a, b)`: `b` 가 절대 경로면 `b`, `a` 가 비었거나 `/` 로 끝나면 그대로 잇고, 아니면 `/` 를 끼운다.
pub fn join(a: &str, b: &str) -> String {
    if b.starts_with('/') || a.is_empty() {
        b.to_owned()
    } else if a.ends_with('/') {
        format!("{a}{b}")
    } else {
        format!("{a}/{b}")
    }
}

/// python `str(PurePosixPath(base) / name)`: [`join`] 한 뒤 [`pathlib_str`] 로 정리한다.
pub fn pathlib_join(base: &str, name: &str) -> String {
    pathlib_str(&join(base, name))
}

/// python `posixpath.splitext(path)`: (앞, 확장자). 확장자는 마지막 조각의 마지막 `.` 부터, 조각 맨 앞의 `.` 들은 확장자가 아니다.
pub fn splitext(path: &str) -> (&str, &str) {
    let name_start = path.rfind('/').map_or(0, |i| i + 1);
    match path[name_start..].rfind('.') {
        Some(dot)
            if path[name_start..name_start + dot]
                .bytes()
                .any(|b| b != b'.') =>
        {
            path.split_at(name_start + dot)
        }
        _ => (path, ""),
    }
}

/// python `posixpath.dirname(path)`: 마지막 `/` 앞. 끝의 `/` 들은 떼되 모두 `/` 인 머리는 그대로 둔다.
pub fn dirname(path: &str) -> &str {
    let cut = path.rfind('/').map_or(0, |i| i + 1);
    let head = &path[..cut];
    if !head.is_empty() && head.bytes().any(|b| b != b'/') {
        head.trim_end_matches('/')
    } else {
        head
    }
}

/// python `posixpath.basename(path)`: 마지막 `/` 뒤.
pub fn basename(path: &str) -> &str {
    path.rfind('/').map_or(path, |i| &path[i + 1..])
}

/// python `os.path.relpath(path, start)`.
///
/// 빈 `path` 는 python 이 ValueError 를, 현재 디렉터리를 읽지 못하는 상대 경로는 OSError 를 내는 자리라 `None` 이다.
pub fn relpath(path: &str, start: &str) -> Option<String> {
    if path.is_empty() {
        return None;
    }
    let start = abspath(start)?;
    let path = abspath(path)?;

    // 같은 머리 조각을 지나 남은 start 조각마다 `..`
    let split = |p: &str| -> Vec<String> {
        let tail = p.trim_start_matches('/');
        if tail.is_empty() {
            Vec::new()
        } else {
            tail.split('/').map(str::to_owned).collect()
        }
    };
    let (start_list, path_list) = (split(&start), split(&path));
    let common = start_list
        .iter()
        .zip(&path_list)
        .take_while(|(a, b)| a == b)
        .count();
    let mut rel: Vec<&str> = vec![".."; start_list.len() - common];
    rel.extend(path_list[common..].iter().map(String::as_str));

    Some(if rel.is_empty() {
        ".".to_owned()
    } else {
        rel.join("/")
    })
}

/// [`realpath`] 가 python 에서 예외가 나는 자리.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RealpathError {
    /// 경로를 OS 바이트로 바꾸지 못하거나 NUL 이 들었다(python ValueError).
    Invalid,
    /// 상대 경로인데 현재 디렉터리를 읽지 못했다(python `os.getcwd` 의 OSError).
    Cwd,
}

// realpath 가 풀 조각과, 다 푼 링크를 표시하는 자리(python 의 None 표식)
enum Pending {
    Name(String),
    Resolved(String),
}

/// python `os.path.realpath(path)`(POSIX, strict=False): 링크를 모두 따라간 절대 경로.
///
/// 3.14 판의 순서를 그대로 옮겼다: 조각마다 lstat 하고 링크면 대상을 펼친다. 없는 조각과 lstat, readlink 오류는 글자 그대로 잇는다.
/// 링크 고리는 고리를 이룬 링크 경로에서 멈춘다. 글은 python str 꼴(서로게이트 자리표, [`crate::py::surrogate`])이다.
pub fn realpath(path: &str) -> Result<String, RealpathError> {
    use crate::py::surrogate::{from_os, to_os};
    use std::collections::HashMap;

    // 남은 조각(뒤집은 스택)과 지금까지 푼 경로
    let mut rest: Vec<Pending> = path
        .split('/')
        .rev()
        .map(|p| Pending::Name(p.to_owned()))
        .collect();
    let mut part_count = rest.len();
    let mut resolved = if path.starts_with('/') {
        "/".to_owned()
    } else {
        let cwd = std::env::current_dir().map_err(|_| RealpathError::Cwd)?;
        from_os(cwd.as_os_str())
    };
    let mut seen: HashMap<String, Option<String>> = HashMap::new();

    while part_count > 0 {
        let Some(item) = rest.pop() else { break };
        let name = match item {
            Pending::Resolved(link) => {
                seen.insert(link, Some(resolved.clone()));
                continue;
            }
            Pending::Name(name) => name,
        };
        part_count -= 1;

        // 빈 조각, `.`, `..`
        if name.is_empty() || name == "." {
            continue;
        }
        if name == ".." {
            let cut = resolved.rfind('/').unwrap_or(0);
            resolved.truncate(cut.max(1));
            continue;
        }

        // 조각 하나를 이어 lstat
        let next = if resolved == "/" {
            format!("/{name}")
        } else {
            format!("{resolved}/{name}")
        };
        if next.contains('\0') {
            return Err(RealpathError::Invalid);
        }
        let os = to_os(&next).ok_or(RealpathError::Invalid)?;
        let is_link = std::fs::symlink_metadata(&os).is_ok_and(|m| m.file_type().is_symlink());
        if !is_link {
            resolved = next;
            continue;
        }
        if let Some(done) = seen.get(&next) {
            // 이미 푼 링크는 그 값, 푸는 중인 링크는 고리라 글자 그대로
            resolved = done.clone().unwrap_or(next);
            continue;
        }
        let Ok(target) = std::fs::read_link(&os) else {
            resolved = next;
            continue;
        };

        // 링크 대상을 스택에 펼치기
        let target = from_os(target.as_os_str());
        if target.starts_with('/') {
            resolved = "/".to_owned();
        }
        seen.insert(next.clone(), None);
        rest.push(Pending::Resolved(next));
        let parts: Vec<&str> = target.split('/').collect();
        part_count += parts.len();
        rest.extend(parts.into_iter().rev().map(|p| Pending::Name(p.to_owned())));
    }
    Ok(resolved)
}

/// [`pathlib_str`] 를 `PathBuf` 로.
pub fn pathlib(path: &str) -> PathBuf {
    PathBuf::from(pathlib_str(path))
}

/// python `shutil.which(cmd)`: 실행할 수 있는 파일의 경로, 없으면 `None`.
///
/// `/` 가 든 이름은 그 경로만 보고, 아니면 `$PATH`(없으면 `/bin:/usr/bin`)를 앞에서부터 찾는다.
/// 실행 권한은 권한 비트(누구든 x)로 본다. python 은 `os.access(X_OK)` 라 다른 사용자의 파일에서 다를 수 있다.
pub fn which(cmd: &str, env: &Env) -> Option<PathBuf> {
    if cmd.contains('/') {
        let p = PathBuf::from(cmd);
        return executable(&p).then_some(p);
    }

    // $PATH 를 앞에서부터
    let search = env.get("PATH").unwrap_or("/bin:/usr/bin");
    if search.is_empty() {
        return None;
    }
    let sep = if cfg!(windows) { ';' } else { ':' };
    search
        .split(sep)
        .map(|dir| {
            if dir.is_empty() {
                PathBuf::from(cmd)
            } else {
                Path::new(dir).join(cmd)
            }
        })
        .find(|p| executable(p))
}

#[cfg(unix)]
fn executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path).is_ok_and(|m| !m.is_dir() && m.permissions().mode() & 0o111 != 0)
}

#[cfg(not(unix))]
fn executable(path: &Path) -> bool {
    std::fs::metadata(path).is_ok_and(|m| !m.is_dir())
}

#[cfg(all(test, not(windows)))]
mod tests {
    use super::*;

    /// dirname, basename, relpath 가 posixpath 와 같은 글을 낸다.
    #[test]
    fn dirname_basename_relpath_like_python() {
        assert_eq!(dirname("/a/b/c"), "/a/b");
        assert_eq!(dirname("/a"), "/");
        assert_eq!(dirname("a"), "");
        assert_eq!(dirname("//a//b"), "//a");
        assert_eq!(dirname("///"), "///");
        assert_eq!(basename("/a/b.c"), "b.c");
        assert_eq!(basename("a/"), "");
        assert_eq!(relpath("/a/b/c", "/a").as_deref(), Some("b/c"));
        assert_eq!(relpath("/a", "/a/b/c").as_deref(), Some("../.."));
        assert_eq!(relpath("/a", "/a").as_deref(), Some("."));
        assert_eq!(relpath("/x/y", "/a/b").as_deref(), Some("../../x/y"));
        assert_eq!(relpath("", "/a"), None);
    }

    #[test]
    fn pathlib_examples() {
        assert_eq!(pathlib_str(""), ".");
        assert_eq!(pathlib_str("./a//b/./"), "a/b");
        assert_eq!(pathlib_str("//a/../b"), "//a/../b");
        assert_eq!(pathlib_str("///a"), "/a");
    }

    #[test]
    fn expanduser_examples() {
        let env = Env::from_pairs([("HOME", "/home/x/")]);
        assert_eq!(expanduser("~/a", &env), "/home/x/a");
        assert_eq!(expanduser("~", &env), "/home/x");
        assert_eq!(
            expanduser("~no-such-user-here/a", &env),
            "~no-such-user-here/a"
        );
        assert_eq!(expanduser("~", &Env::from_pairs([("HOME", "/")])), "/");
        assert_eq!(expanduser("~/a", &Env::default()), "~/a");
    }
}
