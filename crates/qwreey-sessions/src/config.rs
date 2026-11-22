//! 설정(python `sllib/config.py`). 우선순위: 환경 변수 > harness.env 층 > 기본값.
//!
//! harness.env 층은 [`harness_hook::settings::load_layers`] 다(사용자 < 플러그인 옵션 < 저장소 `.claude/harness.env` <
//! `.claude/harness.local.env`). [`USER_ONLY`] 의 키는 저장소 층이 바꾸지 못한다. 옮긴 훅이 읽는 키만 [`Key`] 에 두었다.

use std::collections::BTreeMap;

use harness_hook::Env;
use harness_hook::py::num::parse_float;
use harness_hook::py::path::{expanduser, join, pathlib_join, pathlib_str};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::strip;

/// 옮긴 훅이 읽는 설정 키. 기본값은 python `DEFAULTS` 와 같다(`tests/parity_sessions.rs` 가 대조한다).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Key {
    SessionLog,
    Disable,
    RecordNoninteractive,
    Home,
    CooldownMin,
    GrowKb,
    PendingStrongCount,
    PendingStrongDays,
    HomeNudgeCount,
    HomeNudgeDays,
    ReadGate,
    ReadGateKb,
}

impl Key {
    /// 모든 키.
    pub const ALL: [Key; 12] = [
        Key::SessionLog,
        Key::Disable,
        Key::RecordNoninteractive,
        Key::Home,
        Key::CooldownMin,
        Key::GrowKb,
        Key::PendingStrongCount,
        Key::PendingStrongDays,
        Key::HomeNudgeCount,
        Key::HomeNudgeDays,
        Key::ReadGate,
        Key::ReadGateKb,
    ];

    /// 환경 변수와 harness.env 의 이름.
    pub fn name(self) -> &'static str {
        match self {
            Key::SessionLog => "SESSION_LOG",
            Key::Disable => "SESSION_LOG_DISABLE",
            Key::RecordNoninteractive => "SESSION_LOG_RECORD_NONINTERACTIVE",
            Key::Home => "SESSION_LOG_HOME",
            Key::CooldownMin => "SESSION_LOG_COOLDOWN_MIN",
            Key::GrowKb => "SESSION_LOG_GROW_KB",
            Key::PendingStrongCount => "SESSION_LOG_PENDING_STRONG_COUNT",
            Key::PendingStrongDays => "SESSION_LOG_PENDING_STRONG_DAYS",
            Key::HomeNudgeCount => "SESSION_LOG_HOME_NUDGE_COUNT",
            Key::HomeNudgeDays => "SESSION_LOG_HOME_NUDGE_DAYS",
            Key::ReadGate => "SESSION_LOG_READ_GATE",
            Key::ReadGateKb => "SESSION_LOG_READ_GATE_KB",
        }
    }

    /// 기본값.
    pub fn default_value(self) -> &'static str {
        match self {
            Key::SessionLog => "on",
            Key::Disable => "off",
            Key::RecordNoninteractive => "",
            Key::Home => "",
            Key::CooldownMin => "20",
            Key::GrowKb => "512",
            Key::PendingStrongCount => "5",
            Key::PendingStrongDays => "7",
            Key::HomeNudgeCount => "3",
            Key::HomeNudgeDays => "3",
            Key::ReadGate => "on",
            Key::ReadGateKb => "32",
        }
    }
}

/// 저장소 층이 바꾸지 못하는 키(python `USER_ONLY`): 기록을 쓸 곳과 실행할 claude.
pub const USER_ONLY: &[&str] = &["SESSION_LOG_HOME", "SESSION_LOG_CLAUDE"];

const OFF_VALUES: &[&str] = &["off", "0", "false", "no"];
const ON_VALUES: &[&str] = &["1", "true", "yes", "on"];

/// 합친 설정 값.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Config {
    values: BTreeMap<Key, String>,
}

impl Config {
    /// harness.env 층 `layers`(python `load_layers` 의 값) 위에 환경 변수를 얹는다.
    ///
    /// 환경 변수는 빈 값도 이긴다(python `k in os.environ`). UTF-8 이 아닌 값은 python 처럼 서로게이트 자리표로 읽는다.
    pub fn from_layers(layers: &BTreeMap<String, String>, env: &Env) -> Config {
        let values = Key::ALL
            .iter()
            .filter_map(|&key| {
                let value = match env.get_os(key.name()) {
                    Some(os) => from_os(os),
                    None => layers.get(key.name())?.clone(),
                };
                Some((key, value))
            })
            .collect();
        Config { values }
    }

    /// 키의 값(python `config.get`).
    pub fn get(&self, key: Key) -> &str {
        self.values
            .get(&key)
            .map_or(key.default_value(), String::as_str)
    }

    /// 수로 읽은 값(python `config.num`). 읽지 못하면 기본값.
    pub fn num(&self, key: Key) -> f64 {
        parse_float(self.get(key))
            .or_else(|| parse_float(key.default_value()))
            .unwrap_or(0.0)
    }

    fn is_one_of(&self, key: Key, words: &[&str]) -> bool {
        words.contains(&strip(self.get(key)).to_lowercase().as_str())
    }

    /// 세션 기록이 꺼졌나: `SESSION_LOG` 가 꺼짐 값이거나 옛 키 `SESSION_LOG_DISABLE` 이 켜짐 값.
    pub fn disabled(&self) -> bool {
        self.is_one_of(Key::SessionLog, OFF_VALUES) || self.is_one_of(Key::Disable, ON_VALUES)
    }

    /// 큰 기록 통째 Read 막기가 꺼졌나.
    pub fn read_gate_off(&self) -> bool {
        self.is_one_of(Key::ReadGate, OFF_VALUES)
    }

    /// `claude -p`, SDK 세션이라 기록하지 않나(`CLAUDE_CODE_ENTRYPOINT` 가 `sdk` 로 시작).
    pub fn skip_noninteractive(&self, env: &Env) -> bool {
        if self.is_one_of(Key::RecordNoninteractive, ON_VALUES) {
            return false;
        }
        env.get_os("CLAUDE_CODE_ENTRYPOINT")
            .is_some_and(|v| from_os(v).starts_with("sdk"))
    }

    /// 외부 저장소 루트(python `str(config.home())`).
    ///
    /// `SESSION_LOG_HOME`, 비면 `${XDG_DATA_HOME:-~/.local/share}/session-log`.
    pub fn home(&self, env: &Env) -> String {
        let configured = strip(self.get(Key::Home));
        if !configured.is_empty() {
            return pathlib_str(&expanduser(configured, env));
        }
        let data = match env.get_os_nonempty("XDG_DATA_HOME") {
            Some(xdg) => from_os(xdg),
            None => join(&join(&expanduser("~", env), ".local"), "share"),
        };
        pathlib_join(&data, "session-log")
    }
}

/// Claude Code 설정 폴더(python `str(config.claude_config_dir())`): `$CLAUDE_CONFIG_DIR`, 없으면 `~/.claude`.
pub fn claude_config_dir(env: &Env) -> String {
    match env.get_os_nonempty("CLAUDE_CONFIG_DIR") {
        Some(dir) => pathlib_str(&from_os(dir)),
        None => pathlib_str(&join(&expanduser("~", env), ".claude")),
    }
}

/// 사용자 홈의 `.claude`(python `os.path.join(os.path.expanduser("~"), ".claude")`, 정리하지 않은 글).
pub fn home_claude_dir(env: &Env) -> String {
    join(&expanduser("~", env), ".claude")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 레이어 값과 환경 값이 겹치는 설정에서 쓸 레이어와 환경을 만든다.
    fn sample() -> (BTreeMap<String, String>, Env) {
        let layers = BTreeMap::from([
            ("SESSION_LOG_GROW_KB".to_owned(), "64".to_owned()),
            ("SESSION_LOG".to_owned(), " OFF ".to_owned()),
        ]);
        let env = Env::from_pairs([("SESSION_LOG_GROW_KB", "x"), ("HOME", "/h")]);
        (layers, env)
    }

    /// 환경 값이 레이어 값을 이기고, 숫자가 아니면 기본값으로 돌아간다.
    #[test]
    fn env_beats_layer_and_bad_number_falls_back() {
        let (layers, env) = sample();
        let config = Config::from_layers(&layers, &env);

        assert_eq!(
            config.num(Key::GrowKb),
            512.0,
            "x is not a number, so the default"
        );
    }

    /// 끄기 스위치는 앞뒤 공백과 대소문자를 무시하고 읽는다.
    #[test]
    fn off_switch_ignores_padding_and_case() {
        let (layers, env) = sample();

        assert!(Config::from_layers(&layers, &env).disabled());
    }

    /// 기록 폴더 기본값은 HOME 아래 `.local/share/session-log` 다.
    #[test]
    fn home_defaults_under_user_share() {
        let (layers, env) = sample();

        assert_eq!(
            Config::from_layers(&layers, &env).home(&env),
            "/h/.local/share/session-log"
        );
    }

    /// 기록 폴더 설정은 공백을 걷고 `~` 를 풀고 끝 `/` 를 뗀다.
    #[test]
    fn home_override_is_trimmed_and_expanded() {
        let env = Env::from_pairs([("SESSION_LOG_HOME", " ~/s/ "), ("HOME", "/h")]);

        assert_eq!(
            Config::from_layers(&BTreeMap::new(), &env).home(&env),
            "/h/s"
        );
    }
}
