//! 명령이 남긴 core dump 찾기(python 판의 `read_core_pattern`, `name_regex`, `core_info`, `Search`, `find_cores`).
//!
//! 이름이 core_pattern 꼴(또는 `core`, `core.<숫자>`)이고, 보통 파일이고, 내 uid 이고, Pre 시각 뒤 mtime 이고, ELF 헤더의 e_type 이
//! ET_CORE 인 것만 센다. 늘 보는 곳은 cwd 맨 위(그리고 core_pattern 이 절대 경로면 그 폴더). 크래시 흔적이 있을 때만 cwd 아래를
//! 같은 장치 안에서 깊이 4 까지 훑는다. 걷기, stat, ELF 읽기를 합쳐 200 ms 시한 하나다.

use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use harness_hook::py::re::{self, Regex};
use harness_hook::py::surrogate::{from_os, to_os};
use harness_hook::py::text::strip;

const WALK_DEPTH: usize = 4;
const WALK_BUDGET: Duration = Duration::from_millis(200);
const WALK_SKIP: &[&str] = &["node_modules", "__pycache__"];
const NS: i128 = 1_000_000_000;
// core_pattern 의 %p 같은 지정자는 숫자, %e 같은 것은 아무 글자
const SPEC_DIGITS: &str = "pPiIsStugcd";
const SPEC_TEXT: &str = "eEhf";

/// 크래시로 보는 신호 번호와 이름.
pub const CRASH_SIGNALS: &[(i64, &str)] = &[
    (3, "SIGQUIT"),
    (4, "SIGILL"),
    (5, "SIGTRAP"),
    (6, "SIGABRT"),
    (7, "SIGBUS"),
    (8, "SIGFPE"),
    (11, "SIGSEGV"),
    (31, "SIGSYS"),
];

/// 크래시 신호 번호의 이름(SIGSEGV 등). 크래시 신호가 아니면 `None`.
pub fn signal_name(sig: i64) -> Option<&'static str> {
    CRASH_SIGNALS
        .iter()
        .find(|(n, _)| *n == sig)
        .map(|(_, name)| *name)
}

/// core_pattern 글과 core_uses_pid 값. Linux 가 아니거나 /proc 을 읽지 못하면 `None`.
pub fn read_core_pattern() -> Option<(String, bool)> {
    if !cfg!(target_os = "linux") {
        return None;
    }
    let raw = fs::read("/proc/sys/kernel/core_pattern").ok()?;
    let pattern = strip(&String::from_utf8_lossy(&raw)).to_owned();
    let uses_pid = fs::read("/proc/sys/kernel/core_uses_pid")
        .ok()
        .and_then(|b| String::from_utf8(b).ok())
        .is_some_and(|t| strip(&t) == "1");
    Some((pattern, uses_pid))
}

/// core_pattern 의 파일 이름 부분을 python 정규식으로. `core`, `core.<숫자>` 도 늘 맞는다.
pub fn name_regex(template: &str, uses_pid: bool) -> Regex {
    let chars: Vec<char> = template.chars().collect();
    let mut body = String::new();
    let mut has_pid = false;
    let mut i = 0;

    // 지정자와 글자를 옮긴다
    while i < chars.len() {
        let c = chars[i];
        if c == '%' && i + 1 < chars.len() {
            let spec = chars[i + 1];
            has_pid = has_pid || spec == 'p' || spec == 'P';
            body.push_str(if spec == '%' {
                "%"
            } else if SPEC_DIGITS.contains(spec) {
                r"\d+"
            } else if SPEC_TEXT.contains(spec) {
                ".+"
            } else {
                ""
            });
            i += 2;
            continue;
        }
        body.push_str(&re::escape(&c.to_string()));
        i += 1;
    }

    // core_uses_pid=1 이면 커널이 .PID 를 붙인다
    if uses_pid && !has_pid {
        body.push_str(r"(?:\.\d+)?");
    }
    Regex::new(&format!(r"\A(?:{body}|core(?:\.\d+)?)\Z")).expect("escaped template compiles")
}

/// core 파일에서 읽은 것. 읽지 못한 칸은 빈 글이다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct CoreInfo {
    pub program: String,
    pub args: String,
    pub signal: String,
}

/// ELF core 이면 그 정보, 아니면 `None`.
pub fn core_info(path: &Path) -> Option<CoreInfo> {
    let mut f = File::open(path).ok()?;
    let mut head = Vec::with_capacity(64);
    (&mut f).take(64).read_to_end(&mut head).ok()?;
    if head.len() < 52 || &head[..4] != b"\x7fELF" || !matches!(head[5], 1 | 2) {
        return None;
    }
    let little = head[5] == 1;
    if u16_at(&head, 16, little) != Some(4) {
        return None; // e_type 이 ET_CORE 가 아니다
    }

    // 64비트만 자세히. 읽다 실패하면 거기까지 읽은 칸만 남는다
    let mut info = CoreInfo::default();
    if head[4] == 2 && head.len() == 64 {
        let _ = note_fields(&mut f, &head, little, &mut info);
    }
    Some(info)
}

// 64비트 core 의 PT_NOTE 에서 NT_PRSTATUS 의 신호와 NT_PRPSINFO 의 프로그램 이름, 인자를 읽는다
fn note_fields(f: &mut File, head: &[u8], little: bool, info: &mut CoreInfo) -> Option<()> {
    let phoff = u64_at(head, 32, little)?;
    let phentsize = usize::from(u16_at(head, 54, little)?);
    let phnum = usize::from(u16_at(head, 56, little)?);
    if phentsize < 56 {
        return Some(());
    }

    // 앞의 프로그램 헤더 16개 안에서 첫 PT_NOTE
    f.seek(SeekFrom::Start(phoff)).ok()?;
    let table = read_up_to(f, phentsize * phnum.min(16))?;
    for k in 0..table.len() / phentsize {
        let at = k * phentsize;
        if u32_at(&table, at, little)? != 4 {
            continue;
        }
        let p_offset = u64_at(&table, at + 8, little)?;
        let p_filesz = u64_at(&table, at + 32, little)?;
        f.seek(SeekFrom::Start(p_offset)).ok()?;
        let notes = read_up_to(f, p_filesz.min(65536) as usize)?;
        read_notes(&notes, little, info);
        return Some(());
    }
    Some(())
}

// 노트를 차례로 보며 두 칸이 찰 때까지
fn read_notes(notes: &[u8], little: bool, info: &mut CoreInfo) {
    let mut pos: u64 = 0;
    while pos + 12 <= notes.len() as u64 {
        let p = pos as usize;
        let (Some(namesz), Some(descsz), Some(n_type)) = (
            u32_at(notes, p, little),
            u32_at(notes, p + 4, little),
            u32_at(notes, p + 8, little),
        ) else {
            return;
        };
        let desc = pos + 12 + ((u64::from(namesz) + 3) & !3);
        let start = (desc as usize).min(notes.len());
        let end = (desc + u64::from(descsz)).min(notes.len() as u64) as usize;
        let body = &notes[start..end.max(start)];

        if n_type == 1 && body.len() >= 14 && info.signal.is_empty() {
            // NT_PRSTATUS: pr_cursig
            let sig = i64::from(i16_at(body, 12, little).expect("length checked"));
            info.signal = match signal_name(sig) {
                Some(name) => name.to_owned(),
                None if sig != 0 => format!("signal {sig}"),
                None => String::new(),
            };
        } else if n_type == 3 && descsz == 136 {
            // NT_PRPSINFO(x86_64, aarch64): pr_fname[16] 은 40, pr_psargs[80] 은 56 에서
            info.program = c_string(slice(body, 40, 56));
            info.args = strip(&c_string(slice(body, 56, 136))).to_owned();
        }
        if !info.program.is_empty() && !info.signal.is_empty() {
            return;
        }
        pos = desc + ((u64::from(descsz) + 3) & !3);
    }
}

fn read_up_to(f: &mut File, n: usize) -> Option<Vec<u8>> {
    let mut out = Vec::new();
    f.take(n as u64).read_to_end(&mut out).ok()?;
    Some(out)
}

// python bytes[a:b] 처럼 넘치는 끝은 자른다
fn slice(b: &[u8], from: usize, to: usize) -> &[u8] {
    &b[from.min(b.len())..to.min(b.len())]
}

// 첫 NUL 까지를 UTF-8 로(잘못된 바이트는 U+FFFD)
fn c_string(b: &[u8]) -> String {
    let end = b.iter().position(|&x| x == 0).unwrap_or(b.len());
    String::from_utf8_lossy(&b[..end]).into_owned()
}

fn bytes<const N: usize>(b: &[u8], at: usize, little: bool) -> Option<[u8; N]> {
    let mut out: [u8; N] = b.get(at..at + N)?.try_into().ok()?;
    if !little {
        out.reverse();
    }
    Some(out)
}

fn u16_at(b: &[u8], at: usize, little: bool) -> Option<u16> {
    bytes(b, at, little).map(u16::from_le_bytes)
}

fn i16_at(b: &[u8], at: usize, little: bool) -> Option<i16> {
    bytes(b, at, little).map(i16::from_le_bytes)
}

fn u32_at(b: &[u8], at: usize, little: bool) -> Option<u32> {
    bytes(b, at, little).map(u32::from_le_bytes)
}

fn u64_at(b: &[u8], at: usize, little: bool) -> Option<u64> {
    bytes(b, at, little).map(u64::from_le_bytes)
}

/// 찾은 core 하나.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Found {
    /// python 이 쓰는 꼴의 경로 글(UTF-8 이 아닌 바이트는 surrogateescape 자리표, 출력에서 `\udcff` 꼴).
    pub path: String,
    pub size: u64,
    pub mtime_ns: i128,
    pub info: CoreInfo,
}

/// 파일이 `since_ns` 뒤에 바뀌었는가. 여유는 두지 않는다.
///
/// mtime 이 정확히 초 단위면(초만 남기는 파일 시스템) 같은 초 안의 시각이 잘렸을 수 있어 since 의 초부터 받는다.
pub fn mtime_after(mtime_ns: i128, since_ns: i128) -> bool {
    if mtime_ns.rem_euclid(NS) == 0 {
        return mtime_ns >= since_ns - since_ns.rem_euclid(NS);
    }
    mtime_ns >= since_ns
}

/// 한 번의 core 찾기. 시한 하나가 걷기, stat, ELF 읽기를 모두 덮는다.
///
/// 경로는 OS 경로(`PathBuf`)로 걷는다. UTF-8 이 아닌 폴더 이름(`cwd/\xff/core.5`) 아래의 core 도 열고, 알릴 때만 python 처럼
/// surrogateescape 글로 바꾼다.
pub struct Search {
    names: Regex,
    since_ns: i128,
    uid: Option<u32>,
    deadline: Instant,
    pub found: Vec<Found>,
    files: HashSet<PathBuf>,
    dirs: HashSet<PathBuf>,
}

impl Search {
    /// 이름 정규식, Pre 시각, 내 uid(Windows 는 `None`)로.
    pub fn new(names: Regex, since_ns: i128, uid: Option<u32>) -> Search {
        Search {
            names,
            since_ns,
            uid,
            deadline: Instant::now() + WALK_BUDGET,
            found: Vec::new(),
            files: HashSet::new(),
            dirs: HashSet::new(),
        }
    }

    fn expired(&self) -> bool {
        Instant::now() > self.deadline
    }

    // 이름이 맞는 항목: 보통 파일(링크 아님), 내 uid, Pre 뒤 mtime, ELF core 면 found 에 더한다
    fn consider(&mut self, entry: &fs::DirEntry, path: &Path) {
        // DirEntry 의 file_type, metadata 는 링크를 따라가지 않는다(python follow_symlinks=False)
        if !entry.file_type().is_ok_and(|t| t.is_file()) {
            return;
        }
        let Ok(meta) = entry.metadata() else {
            return;
        };
        let mtime_ns = mtime_ns(&meta);
        if self.files.contains(path) || !mtime_after(mtime_ns, self.since_ns) || !self.mine(&meta) {
            return;
        }

        self.files.insert(path.to_owned());
        if let Some(info) = core_info(path) {
            self.found.push(Found {
                path: from_os(path.as_os_str()),
                size: meta.len(),
                mtime_ns,
                info,
            });
        }
    }

    #[cfg(unix)]
    fn mine(&self, meta: &fs::Metadata) -> bool {
        use std::os::unix::fs::MetadataExt;
        self.uid.is_none_or(|uid| meta.uid() == uid)
    }

    // uid 가 없으면(python 은 os.getuid 가 없는 Windows) 소유자를 보지 않는다
    #[cfg(not(unix))]
    fn mine(&self, _meta: &fs::Metadata) -> bool {
        self.uid.is_none()
    }

    /// `dir` 을 한 번 훑어 core 를 찾고, `dev` 가 있으면 같은 장치의 하위 폴더 목록을 돌려준다.
    pub fn scan(&mut self, dir: &Path, dev: Option<u64>) -> Vec<PathBuf> {
        if !self.dirs.insert(dir.to_owned()) {
            return Vec::new();
        }
        let Ok(entries) = fs::read_dir(dir) else {
            return Vec::new();
        };

        let mut subdirs = Vec::new();
        for entry in entries {
            if self.expired() {
                break;
            }
            let Ok(entry) = entry else {
                break;
            };
            // 이름은 python 처럼 surrogateescape 글로 맞춰 보고, 경로는 OS 경로 그대로 잇는다(python os.path.join)
            let os_name = entry.file_name();
            let name = from_os(&os_name);
            let path = dir.join(&os_name);
            if self.names.match_start(&name).is_some() {
                self.consider(&entry, &path);
            }

            // 같은 장치만: 다른 마운트는 느리거나 멈춰 있을 수 있다(NFS)
            let Some(dev) = dev else { continue };
            if name.starts_with('.') || WALK_SKIP.contains(&name.as_str()) {
                continue;
            }
            let same_device = entry.file_type().is_ok_and(|t| t.is_dir())
                && entry.metadata().ok().as_ref().and_then(device) == Some(dev);
            if same_device {
                subdirs.push(path);
            }
        }
        subdirs
    }

    /// `root` 아래를 얕은 것부터 깊이 4 까지 훑는다(숨은 폴더, node_modules, 다른 장치는 건너뜀).
    pub fn walk(&mut self, root: &Path) {
        let Some(dev) = fs::metadata(root).ok().as_ref().and_then(device) else {
            return;
        };
        let mut level = self.scan(root, Some(dev));
        for depth in 1..=WALK_DEPTH {
            let mut next = Vec::new();
            for d in &level {
                if self.expired() {
                    return;
                }
                next.extend(self.scan(d, (depth < WALK_DEPTH).then_some(dev)));
            }
            level = next;
        }
    }
}

#[cfg(unix)]
fn device(m: &fs::Metadata) -> Option<u64> {
    use std::os::unix::fs::MetadataExt;
    Some(m.dev())
}

// Windows 의 st_dev(볼륨 일련번호)는 std 로 읽을 수 없다. 넓은 훑기를 하지 않는다(core 찾기는 Linux 만이라 쓰이지 않는다)
#[cfg(not(unix))]
fn device(_m: &fs::Metadata) -> Option<u64> {
    None
}

#[cfg(unix)]
fn mtime_ns(m: &fs::Metadata) -> i128 {
    use std::os::unix::fs::MetadataExt;
    i128::from(m.mtime()) * NS + i128::from(m.mtime_nsec())
}

#[cfg(not(unix))]
fn mtime_ns(m: &fs::Metadata) -> i128 {
    m.modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map_or(0, |d| d.as_nanos() as i128)
}

/// `since_ns` 뒤에 생긴 ELF core. core_pattern 이 절대 경로면 그 폴더도 본다. `wide` 면 roots 아래를 훑는다.
/// python 이 OS 경로로 바꾸지 못하는 경로 글이 있으면 `None`(python 은 거기서 예외).
pub fn find_cores(
    roots: &[&str],
    pattern: &str,
    uses_pid: bool,
    since_ns: i128,
    wide: bool,
    uid: Option<u32>,
) -> Option<Vec<Found>> {
    // 패턴의 폴더와 파일 이름(python os.path.split, os.path.basename)
    let cut = pattern.rfind('/').map_or(0, |i| i + 1);
    let (head, template) = pattern.split_at(cut);
    let place = if !pattern.starts_with('/') {
        ""
    } else if head.chars().all(|c| c == '/') {
        head
    } else {
        head.trim_end_matches('/')
    };
    let template = if template.is_empty() {
        "core"
    } else {
        template
    };
    let mut search = Search::new(name_regex(template, uses_pid), since_ns, uid);

    // 싼 길: 패턴의 폴더와 각 cwd 의 맨 위. python 이 OS 경로로 바꾸지 못하는 글(파일 이름 바이트가 아닌 서로게이트)이면
    // python 은 UnicodeEncodeError 로 훅을 멈춘다
    if !place.is_empty() && !place.contains('%') {
        search.scan(&to_os(place)?, None);
    }
    for r in roots {
        let root = to_os(r)?;
        if wide {
            search.walk(&root);
        } else {
            search.scan(&root, None);
        }
    }
    Some(search.found)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `%e` 와 `%p` 자리가 있는 core_pattern 은 그 꼴의 이름만 맞는다.
    #[test]
    fn name_regex_follows_core_pattern() {
        let r = name_regex("core.%e.%p", false);

        assert!(r.match_start("core.luau-lsp.123").is_some());
        assert!(r.match_start("core.txt.x").is_none() && r.match_start("src").is_none());
    }

    /// core_uses_pid 가 켜져 있으면 `core` 와 `core.<숫자>` 도 늘 맞는다.
    #[test]
    fn name_regex_always_takes_plain_core_names() {
        let r = name_regex("%e.core", true);

        assert!(r.match_start("prog.core.12").is_some() && r.match_start("core").is_some());
        assert!(r.match_start("core.7").is_some());
    }

    /// 이름이 `core` 로 시작할 뿐인 파일은 맞지 않는다.
    #[test]
    fn name_regex_rejects_names_that_only_start_with_core() {
        assert!(
            name_regex("core", true)
                .match_start("core_test.py")
                .is_none()
        );
    }

    /// since 가 초 중간이어도 초 단위 mtime 은 그 초의 처음부터 받고, 나노초 mtime 은 정확히 가른다.
    #[test]
    fn whole_second_mtimes_count_from_the_pre_second() {
        let since = 5 * NS + 300;
        assert!(mtime_after(5 * NS, since));
        assert!(!mtime_after(4 * NS, since));
        assert!(!mtime_after(5 * NS + 299, since));
        assert!(mtime_after(5 * NS + 300, since));
    }
}
