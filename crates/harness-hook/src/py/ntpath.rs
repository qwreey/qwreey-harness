//! python `ntpath`(Windows 의 `os.path`) 가운데 글만 다루는 함수. 파일 시스템을 보지 않으므로 모든 OS 에서 빌드하고 시험한다.
//!
//! 3.14 의 순수 python 판을 옮겼다(Windows 의 `nt._path_normpath` 등 C 판과 뜻이 같다). 구분자는 `\` 이고 `/` 도 받는다.
//! 드라이브(`C:`), UNC(`\\server\share`), 장치 경로(`\\?\UNC\server\share`)를 [`splitroot`] 가 가른다.
//! `abspath` 는 Windows API(GetFullPathNameW)를 부르므로 여기 없고 [`crate::py::ospath`] 가 OS 에 맞게 고른다.

/// 구분자.
pub const SEP: char = '\\';
const ALTSEP: char = '/';
const SEPS: &[char] = &['\\', '/'];
const UNC_PREFIX: &str = "\\\\?\\UNC\\";

/// python `ntpath.normcase(s)`: `/` 를 `\` 로 바꾸고 소문자로.
///
/// 소문자는 Rust `to_lowercase` 다. python `str.lower` 와 같은 표(전체 대응, 끝 시그마 포함)를 쓴다.
pub fn normcase(s: &str) -> String {
    s.replace(ALTSEP, "\\").to_lowercase()
}

/// python `ntpath.isabs(s)`: 드라이브와 뿌리(`C:\`)가 있거나 `\\` 로 시작하면 참. `\x` 와 `C:x` 는 절대 경로가 아니다(3.13+).
pub fn isabs(s: &str) -> bool {
    let head: String = s.chars().take(3).map(alt_to_sep).collect();
    head.starts_with("\\\\") || head.chars().skip(1).take(2).eq([':', SEP])
}

/// python `ntpath.splitroot(p)`: (드라이브, 뿌리, 꼬리). 셋을 이으면 `p` 다.
pub fn splitroot(p: &str) -> (&str, &str, &str) {
    let normp: String = p.chars().map(alt_to_sep).collect();
    let mut chars = normp.chars();
    let (first, second) = (chars.next(), chars.next());

    // UNC 나 장치 경로(`\\server\share`, `\\?\UNC\server\share`)
    if first == Some(SEP) && second == Some(SEP) {
        let start = if normp.len() >= 8
            && normp.is_char_boundary(8)
            && normp[..8].eq_ignore_ascii_case(UNC_PREFIX)
        {
            8
        } else {
            2
        };
        let Some(index) = find_from(&normp, SEP, start) else {
            return (p, "", "");
        };
        let Some(index2) = find_from(&normp, SEP, index + 1) else {
            return (p, "", "");
        };
        return (&p[..index2], &p[index2..index2 + 1], &p[index2 + 1..]);
    }

    // 뿌리만(`\x`)
    if first == Some(SEP) {
        return ("", &p[..1], &p[1..]);
    }

    // 드라이브(`C:`), 뒤에 뿌리가 있을 수도
    if second == Some(':') {
        let drive_end = first.map_or(0, char::len_utf8) + 1;
        if normp[drive_end..].starts_with(SEP) {
            return (
                &p[..drive_end],
                &p[drive_end..drive_end + 1],
                &p[drive_end + 1..],
            );
        }
        return (&p[..drive_end], "", &p[drive_end..]);
    }
    ("", "", p)
}

/// python `ntpath.join(a, b)`. 뿌리가 있는 `b` 는 앞을 버리고, 다른 드라이브의 `b` 는 그 드라이브에서 새로 시작한다.
pub fn join(a: &str, b: &str) -> String {
    let (mut drive, mut root, mut path) = {
        let (d, r, p) = splitroot(a);
        (d.to_owned(), r.to_owned(), p.to_owned())
    };
    let (b_drive, b_root, b_path) = splitroot(b);

    // 뿌리가 있는 b, 다른 드라이브의 b 는 앞을 버린다. 대소문자만 다른 드라이브는 b 의 것으로 바꿔 잇는다
    let other_drive = !b_drive.is_empty() && b_drive.to_lowercase() != drive.to_lowercase();
    if !b_root.is_empty() || other_drive {
        if !b_drive.is_empty() || drive.is_empty() {
            drive = b_drive.to_owned();
        }
        root = b_root.to_owned();
        path = b_path.to_owned();
    } else {
        if !b_drive.is_empty() {
            drive = b_drive.to_owned();
        }
        path = append(path, b_path);
    }

    // `C:` 같은 드라이브 뒤의 상대 꼬리 사이에는 구분자를 넣지 않는다(UNC 드라이브는 넣는다)
    if !path.is_empty()
        && root.is_empty()
        && !drive.is_empty()
        && !drive.ends_with([':', '\\', '/'])
    {
        return format!("{drive}\\{path}");
    }
    format!("{drive}{root}{path}")
}

// python join 의 `result_path + sep + p_path`(앞이 구분자로 끝나면 넣지 않는다)
fn append(mut path: String, tail: &str) -> String {
    if !path.is_empty() && !path.ends_with(SEPS) {
        path.push(SEP);
    }
    path.push_str(tail);
    path
}

/// python `ntpath.split(p)`: (머리, 마지막 조각). 머리 끝의 구분자는 뗀다(뿌리는 남긴다).
pub fn split(p: &str) -> (&str, &str) {
    let (drive, root, tail) = splitroot(p);
    let cut = tail.rfind(SEPS).map_or(0, |i| i + 1);
    let head = tail[..cut].trim_end_matches(SEPS);
    let prefix = drive.len() + root.len();
    (&p[..prefix + head.len()], &tail[cut..])
}

/// python `ntpath.dirname(p)`.
pub fn dirname(p: &str) -> &str {
    split(p).0
}

/// python `ntpath.basename(p)`.
pub fn basename(p: &str) -> &str {
    split(p).1
}

/// python `ntpath.normpath(path)`: `/` 를 `\` 로, 겹친 구분자와 `.` 을 지우고 `..` 를 글자로 푼다. 빈 경로는 `.`.
pub fn normpath(path: &str) -> String {
    let path: String = path.chars().map(alt_to_sep).collect();
    let (drive, root, tail) = splitroot(&path);

    // 조각마다 `..` 는 앞 조각을 지운다(뿌리 바로 아래면 버리고, 상대 경로 맨 앞이면 남긴다)
    let mut comps: Vec<&str> = Vec::new();
    for comp in tail.split(SEP) {
        if comp.is_empty() || comp == "." {
            continue;
        }
        if comp != ".." {
            comps.push(comp);
        } else if comps.last().is_some_and(|last| *last != "..") {
            comps.pop();
        } else if !(comps.is_empty() && !root.is_empty()) {
            comps.push(comp);
        }
    }

    let prefix = format!("{drive}{root}");
    if prefix.is_empty() && comps.is_empty() {
        return ".".to_owned();
    }
    format!("{prefix}{}", comps.join("\\"))
}

/// python `ntpath.relpath(path, start)` 를 이미 절대 경로인 두 값에(abspath 는 부르는 쪽 몫).
///
/// 드라이브가 다르면 python 은 ValueError 다: `None`.
pub fn relpath_abs(path_abs: &str, start_abs: &str) -> Option<String> {
    let (start_drive, _, start_rest) = splitroot(start_abs);
    let (path_drive, _, path_rest) = splitroot(path_abs);
    if normcase(start_drive) != normcase(path_drive) {
        return None;
    }

    // 같은 머리 조각(대소문자 무시)을 지나 남은 start 조각마다 `..`
    let pieces = |rest: &str| -> Vec<String> {
        if rest.is_empty() {
            Vec::new()
        } else {
            rest.split(SEP).map(str::to_owned).collect()
        }
    };
    let (start_list, path_list) = (pieces(start_rest), pieces(path_rest));
    let common = start_list
        .iter()
        .zip(&path_list)
        .take_while(|(a, b)| normcase(a) == normcase(b))
        .count();
    let mut rel: Vec<&str> = vec![".."; start_list.len() - common];
    rel.extend(path_list[common..].iter().map(String::as_str));

    Some(if rel.is_empty() {
        ".".to_owned()
    } else {
        rel.join("\\")
    })
}

fn alt_to_sep(c: char) -> char {
    if c == ALTSEP { SEP } else { c }
}

fn find_from(s: &str, c: char, from: usize) -> Option<usize> {
    s.get(from..)?.find(c).map(|i| i + from)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 드라이브, UNC, 장치 경로를 python 처럼 가른다.
    #[test]
    fn splitroot_like_python() {
        assert_eq!(splitroot("C:\\a\\b"), ("C:", "\\", "a\\b"));
        assert_eq!(splitroot("C:a"), ("C:", "", "a"));
        assert_eq!(
            splitroot("\\\\srv\\share\\x"),
            ("\\\\srv\\share", "\\", "x")
        );
        assert_eq!(splitroot("//srv/share"), ("//srv/share", "", ""));
        assert_eq!(
            splitroot("\\\\?\\UNC\\srv\\sh\\x"),
            ("\\\\?\\UNC\\srv\\sh", "\\", "x")
        );
        assert_eq!(splitroot("/x"), ("", "/", "x"));
        assert_eq!(splitroot("\u{e9}:x"), ("\u{e9}:", "", "x"));
    }

    /// normpath, join, split 의 몇 가지 꼴.
    #[test]
    fn normpath_join_split_examples() {
        // Normalize separators, dots and parents
        assert_eq!(normpath("C:/a/../b/./c//"), "C:\\b\\c");
        assert_eq!(normpath("\\..\\a"), "\\a");
        assert_eq!(normpath("..\\a\\..\\.."), "..\\..");
        assert_eq!(normpath(""), ".");

        // Join across drives and roots
        assert_eq!(join("C:\\a", "b"), "C:\\a\\b");
        assert_eq!(join("C:", "b"), "C:b");
        assert_eq!(join("C:\\a", "D:b"), "D:b");
        assert_eq!(join("C:\\a", "c:b"), "c:\\a\\b");
        assert_eq!(join("C:\\a", "\\b"), "C:\\b");

        // Split, absolute paths and relative paths
        assert_eq!(split("C:\\a\\b"), ("C:\\a", "b"));
        assert_eq!(split("C:\\"), ("C:\\", ""));
        assert_eq!(dirname("a//b"), "a");
        assert!(isabs("C:/x") && isabs("\\\\x") && !isabs("\\x") && !isabs("C:x"));
        assert_eq!(relpath_abs("C:\\a\\B\\c", "c:\\a\\b").as_deref(), Some("c"));
        assert_eq!(relpath_abs("D:\\a", "C:\\a"), None);
    }
}
