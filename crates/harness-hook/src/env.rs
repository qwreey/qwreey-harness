//! 환경 변수 사본. python 의 `os.environ` 자리에 쓴다.

use std::collections::BTreeMap;

/// 한 번 찍어 둔 환경 변수와, `$HOME` 이 없을 때 쓸 계정의 홈 디렉터리.
///
/// 설정 층과 nonce 는 프로세스 환경 대신 이것을 읽는다. 바이너리는 [`Env::from_process`] 를 한 번 부르고,
/// 시험은 [`Env::from_pairs`] 로 경우마다 다른 환경을 준다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Env {
    vars: BTreeMap<String, String>,
    account_home: Option<String>,
}

impl Env {
    /// 지금 프로세스의 환경. UTF-8 이 아닌 이름이나 값은 뺀다.
    ///
    /// `$HOME` 이 없으면 계정 데이터베이스의 홈(python `pwd.getpwuid`)을 함께 찍어 둔다.
    pub fn from_process() -> Env {
        let vars: BTreeMap<String, String> = std::env::vars_os()
            .filter_map(|(k, v)| {
                Some((normalize_key(k.into_string().ok()?), v.into_string().ok()?))
            })
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
        V: Into<String>,
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

    /// 변수 값. 빈 값도 있는 것으로 본다(python `os.environ.get(key)`).
    pub fn get(&self, key: &str) -> Option<&str> {
        self.vars
            .get(&normalize_key(key.to_owned()))
            .map(String::as_str)
    }

    /// 비어 있지 않은 값만(python `os.environ.get(key) or ...`).
    pub fn get_nonempty(&self, key: &str) -> Option<&str> {
        self.get(key).filter(|v| !v.is_empty())
    }

    /// 변수가 있는지(python `key in os.environ`).
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
