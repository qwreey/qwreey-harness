//! 환경 변수 사본. python 의 `os.environ` 자리에 쓴다.

use std::collections::BTreeMap;
use std::ffi::{OsStr, OsString};

/// 한 번 찍어 둔 환경 변수와, `$HOME` 이 없을 때 쓸 계정의 홈 디렉터리.
///
/// 설정 층과 nonce 는 프로세스 환경 대신 이것을 읽는다. 바이너리는 [`Env::from_process`] 를 한 번 부르고,
/// 시험은 [`Env::from_pairs`] 로 경우마다 다른 환경을 준다.
///
/// 값은 OS 문자열 그대로 두지만 [`Env::get`] 은 UTF-8 인 값만 준다. python 은 UTF-8 이 아닌 값도
/// surrogateescape 로 문자열로 읽어 쓰므로, 그런 값은 두 판이 다르게 본다: Rust 에는 그 변수가 없는 것과 같다.
/// 그 결과가 nonce 를 어긋나게 하는 salt 경로 변수(`QWREEY_HARNESS_SALT_FILE`, `XDG_DATA_HOME`)만
/// [`Env::get_os_nonempty`] 로 바이트 그대로 읽는다. `$HOME` 이 UTF-8 이 아니면 Rust 는 홈을 모르고
/// (salt 기본 경로, 설정 디렉터리) python 은 안다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Env {
    vars: BTreeMap<String, OsString>,
    account_home: Option<String>,
}

impl Env {
    /// 지금 프로세스의 환경. UTF-8 이 아닌 이름은 뺀다.
    ///
    /// `$HOME` 이 없으면 계정 데이터베이스의 홈(python `pwd.getpwuid`)을 함께 찍어 둔다.
    pub fn from_process() -> Env {
        let vars: BTreeMap<String, OsString> = std::env::vars_os()
            .filter_map(|(k, v)| Some((normalize_key(k.into_string().ok()?), v)))
            .collect();
        // HOME 이 있으면 std::env::home_dir 도 그 값을 돌려주므로 따로 둘 것이 없다
        let account_home = if vars.contains_key("HOME") {
            None
        } else {
            std::env::home_dir().and_then(|p| p.into_os_string().into_string().ok())
        };
        Env { vars, account_home }
    }

    /// 주어진 이름과 값만 있는 환경. 계정 홈은 없다(`$HOME` 이 없으면 `~` 를 풀지 않는다).
    pub fn from_pairs<K, V, I>(pairs: I) -> Env
    where
        K: Into<String>,
        V: Into<OsString>,
        I: IntoIterator<Item = (K, V)>,
    {
        let vars = pairs
            .into_iter()
            .map(|(k, v)| (normalize_key(k.into()), v.into()))
            .collect();
        Env {
            vars,
            account_home: None,
        }
    }

    /// 계정 홈을 바꾼 사본. 시험이 `$HOME` 없는 경우를 흉내 낼 때 쓴다.
    pub fn with_account_home(mut self, home: Option<String>) -> Env {
        self.account_home = home;
        self
    }

    /// 변수 값. 빈 값도 있는 것으로 본다(python `os.environ.get(key)`). UTF-8 이 아닌 값은 `None`.
    pub fn get(&self, key: &str) -> Option<&str> {
        self.get_os(key)?.to_str()
    }

    /// 변수 값을 OS 문자열 그대로. UTF-8 이 아니어도 준다.
    pub fn get_os(&self, key: &str) -> Option<&OsStr> {
        self.vars
            .get(&normalize_key(key.to_owned()))
            .map(OsString::as_os_str)
    }

    /// 비어 있지 않은 값을 OS 문자열 그대로(python `os.environ.get(key) or ...`, 경로로 쓸 값).
    pub fn get_os_nonempty(&self, key: &str) -> Option<&OsStr> {
        self.get_os(key).filter(|v| !v.is_empty())
    }

    /// 비어 있지 않은 값만(python `os.environ.get(key) or ...`).
    pub fn get_nonempty(&self, key: &str) -> Option<&str> {
        self.get(key).filter(|v| !v.is_empty())
    }

    /// 변수가 UTF-8 값으로 있는지([`Env::get`] 과 같은 기준).
    pub fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// `$HOME` 이 없을 때 쓸 계정 홈(python `pwd.getpwuid(os.getuid()).pw_dir`).
    pub fn account_home(&self) -> Option<&str> {
        self.account_home.as_deref()
    }
}

// Windows 의 python os.environ 은 이름을 대문자로 바꿔 대소문자를 가리지 않는다
#[cfg(windows)]
fn normalize_key(key: String) -> String {
    key.to_uppercase()
}

#[cfg(not(windows))]
fn normalize_key(key: String) -> String {
    key
}
