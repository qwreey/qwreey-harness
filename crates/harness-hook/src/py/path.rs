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
