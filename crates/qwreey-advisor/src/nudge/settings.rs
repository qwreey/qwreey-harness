//! 검토 알림 설정(python `env_vals`, `kv`, `tier_of`, `limit_of`)과 저장소 등급.
//!
//! 설정 층: 사용자 harness.env < 플러그인 옵션 < 저장소 `.claude/harness.env` < 저장소 local < 환경 변수.
//! 층을 읽지 못하면(홈을 모름) 내장 기본값만 쓴다.

use std::collections::BTreeMap;

use harness_hook::HookEnv;
use harness_hook::py::num::{parse_float, parse_int};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::{split_whitespace, strip};
use harness_hook::settings::{self, LoadRequest};

use crate::abort::{Abort, Result};
use crate::git::{self, GitError};
use crate::pylib::pathx::pathlib_parent_name;

/// 플러그인 옵션(plugin.json userConfig)에 둔 키의 기본값. userConfig 의 default 와 같아야 한다.
pub const REVIEW_DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_REVIEW_DEFAULT", "mid"),
    ("HARNESS_REVIEW_STOP", "on"),
    ("HARNESS_REVIEW_PLAN", "warn"),
    ("HARNESS_REVIEW_HANDBACK", "on"),
];

/// 환경 변수가 마지막에 덮는 키(python 판의 목록).
const ENV_KEYS: &[&str] = &[
    "HARNESS_REVIEW_TIERS",
    "HARNESS_REVIEW_DEFAULT",
    "HARNESS_REVIEW_LINES",
    "HARNESS_REVIEW_FRESH_MIN",
    "HARNESS_REVIEW_STOP",
    "HARNESS_REVIEW_PLAN",
    "HARNESS_REVIEW_HANDBACK",
];

const DEFAULT_LINES: &[(&str, &str)] = &[("high", "40"), ("mid", "200"), ("low", "0")];

/// 합친 설정 값(python `vals`).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Vals(BTreeMap<String, String>);

impl Vals {
    /// python `env_vals(cwd)`.
    pub fn load(ctx: &HookEnv, cwd: &str) -> Vals {
        let settings_dir = ctx.settings_dir();
        let request = LoadRequest {
            project: settings::project_dir(&ctx.env, Some(cwd)),
            defaults: REVIEW_DEFAULTS,
            plugin_dir: settings_dir.as_deref(),
            ..LoadRequest::default()
        };
        let mut values = match settings::load_layers(&ctx.env, &request) {
            Ok(layers) => layers.values,
            Err(_) => REVIEW_DEFAULTS
                .iter()
                .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
                .collect(),
        };
        for key in ENV_KEYS {
            if let Some(value) = ctx.env.get_os(key) {
                values.insert((*key).to_owned(), from_os(value));
            }
        }
        Vals(values)
    }

    /// 값을 직접 준 설정(시험용).
    #[cfg(test)]
    pub fn from_pairs(pairs: &[(&str, &str)]) -> Vals {
        Vals(
            pairs
                .iter()
                .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
                .collect(),
        )
    }

    /// python `vals.get(key) or ""`.
    pub fn text(&self, key: &str) -> &str {
        self.0.get(key).map_or("", String::as_str)
    }

    /// python `float(vals.get("HARNESS_REVIEW_FRESH_MIN") or 90) * 60`: 최근 검토로 치는 초. 읽지 못하면 python 은 ValueError.
    pub fn fresh_seconds(&self) -> Result<f64> {
        let raw = self.text("HARNESS_REVIEW_FRESH_MIN");
        let minutes = if raw.is_empty() {
            90.0
        } else {
            parse_float(raw).ok_or(Abort("HARNESS_REVIEW_FRESH_MIN is not a number"))?
        };
        Ok(minutes * 60.0)
    }

    /// python `limit_of(tier, vals)`: 그 등급의 줄 수 임계(0 이면 끔). 읽지 못하면 python 은 ValueError.
    ///
    /// i128 을 넘는 값은 python 만 읽는다. 여기서는 오류로 본다.
    pub fn limit_of(&self, tier: &str) -> Result<i128> {
        let mut lines: BTreeMap<String, String> = DEFAULT_LINES
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect();
        lines.extend(kv(self.text("HARNESS_REVIEW_LINES")));
        match lines.get(tier).map_or("0", String::as_str) {
            "" => Ok(0),
            raw => parse_int(raw).ok_or(Abort("HARNESS_REVIEW_LINES is not an integer")),
        }
    }

    /// 저장소 이름의 등급(python `kv(TIERS).get(repo, DEFAULT or "mid")`): 표에 빈 값으로 있으면 빈 등급이다.
    pub fn tier_for(&self, repo: &str) -> String {
        match kv(self.text("HARNESS_REVIEW_TIERS")).remove(repo) {
            Some(tier) => tier,
            None => match self.text("HARNESS_REVIEW_DEFAULT") {
                "" => "mid".to_owned(),
                tier => tier.to_owned(),
            },
        }
    }
}

/// python `kv(s)`: 공백으로 나눈 `k=v` 조각들(뒤가 이긴다). `=` 없는 조각은 버린다.
pub fn kv(s: &str) -> BTreeMap<String, String> {
    split_whitespace(s)
        .filter_map(|part| part.split_once('='))
        .map(|(k, v)| (k.to_owned(), v.to_owned()))
        .collect()
}

/// 저장소와 등급. 저장소가 아니면 등급 `off`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Tier {
    /// git common dir 의 부모 이름(worktree 안에서도 본 저장소 이름). 저장소가 아니면 `None`, 이름이 빈 글일 수도 있다.
    pub repo: Option<String>,
    pub tier: String,
}

impl Tier {
    /// python `tier == "off" or not repo`: 알릴 것이 없는 저장소.
    pub fn is_silent(&self) -> bool {
        self.tier == "off" || self.repo.as_deref().is_none_or(str::is_empty)
    }
}

/// python `tier_of(cwd, vals)`.
pub fn tier_of(cwd: &str, vals: &Vals) -> Result<Tier> {
    let common = git::stdout_or_empty(
        cwd,
        &["rev-parse", "--path-format=absolute", "--git-common-dir"],
    )
    .map_err(git_abort)?;
    let common = strip(&common);
    if common.is_empty() {
        return Ok(Tier {
            repo: None,
            tier: "off".to_owned(),
        });
    }
    let repo = pathlib_parent_name(common);
    Ok(Tier {
        tier: vals.tier_for(&repo),
        repo: Some(repo),
    })
}

/// python 이 잡지 않는 git 오류(UTF-8 이 아닌 출력, 쓸 수 없는 인자).
pub fn git_abort(error: GitError) -> Abort {
    match error {
        GitError::Decode => Abort("git output is not UTF-8"),
        GitError::BadArg => Abort("git argument cannot be encoded"),
        GitError::Failed => Abort("git failed"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// kv 는 공백 조각의 첫 `=` 로 나누고 같은 키는 뒤가 이긴다.
    #[test]
    fn kv_like_python() {
        let map = kv("quad=high  a=b=c x a=low");
        assert_eq!(map.get("quad").map(String::as_str), Some("high"));
        assert_eq!(
            map.get("a").map(String::as_str),
            Some("low"),
            "the later pair wins"
        );
        assert!(!map.contains_key("x"), "a part without = is dropped");
    }

    /// 등급과 임계: 표에 없으면 DEFAULT, 표의 빈 값은 빈 등급, 빈 임계는 0.
    #[test]
    fn tiers_and_limits() {
        // Tier lookup
        let vals = Vals::from_pairs(&[
            ("HARNESS_REVIEW_TIERS", "quad=high empty="),
            ("HARNESS_REVIEW_DEFAULT", "low"),
            ("HARNESS_REVIEW_LINES", "high=10 low="),
        ]);
        assert_eq!(vals.tier_for("quad"), "high");
        assert_eq!(vals.tier_for("other"), "low");
        assert_eq!(
            vals.tier_for("empty"),
            "",
            "python dict.get keeps an empty value"
        );

        // Line limits
        assert_eq!(vals.limit_of("high"), Ok(10));
        assert_eq!(vals.limit_of("mid"), Ok(200), "built-in default");
        assert_eq!(vals.limit_of("low"), Ok(0), "empty is `or 0`");
        assert_eq!(vals.limit_of("nope"), Ok(0));
        let bad = Vals::from_pairs(&[("HARNESS_REVIEW_LINES", "mid=x")]);
        assert!(bad.limit_of("mid").is_err(), "python int() raises");
    }

    /// FRESH_MIN 은 분 단위, 비면 90분, 읽지 못하면 오류.
    #[test]
    fn fresh_minutes() {
        assert_eq!(Vals::default().fresh_seconds(), Ok(5400.0));
        let vals = Vals::from_pairs(&[("HARNESS_REVIEW_FRESH_MIN", " 1_0 ")]);
        assert_eq!(
            vals.fresh_seconds(),
            Ok(600.0),
            "python float() takes spaces and underscores"
        );
        let bad = Vals::from_pairs(&[("HARNESS_REVIEW_FRESH_MIN", "soon")]);
        assert!(bad.fresh_seconds().is_err());
    }
}
