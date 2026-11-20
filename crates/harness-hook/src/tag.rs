//! 모델에게 가는 훅 글의 태그(`home/.claude/HOOK-MESSAGES.md` 규칙 2).
//!
//! `<harness-hook name="N" level="L" nonce="X">\n본문\n</harness-hook>`, 상시 블록은 `<plugin name="P" nonce="X">`.
//! nonce 속성은 언제나 마지막이고, nonce 가 없으면 속성째 뺀다. 이름과 본문은 escape 하지 않는다(python 판과 같다).

use crate::nonce::{self, Nonce};

/// 훅 알림의 긴급도(`level` 속성). 모델이 할 일은 HOOK-MESSAGES.md 의 표를 따른다.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Level {
    /// 진행 전에 반드시 처리한다. deny 사유는 늘 이것.
    Action,
    /// 다음 행동 전에 다루고 한 줄로 언급한다.
    Warn,
    /// 판단에 반영한다.
    Info,
}

impl Level {
    /// 속성 값(`action`, `warn`, `info`).
    pub fn as_str(self) -> &'static str {
        match self {
            Level::Action => "action",
            Level::Warn => "warn",
            Level::Info => "info",
        }
    }
}

/// `<harness-hook>` 태그 하나로 감싼 본문.
pub fn harness_hook(name: &str, level: Level, nonce: Option<&Nonce>, body: &str) -> String {
    format!(
        "<harness-hook name=\"{name}\" level=\"{}\"{}>\n{body}\n</harness-hook>",
        level.as_str(),
        nonce::attr(nonce)
    )
}

/// `<plugin>` 태그 하나로 감싼 본문(상시 블록, `lib/ambient.py`).
pub fn plugin_block(plugin: &str, nonce: Option<&Nonce>, body: &str) -> String {
    format!(
        "<plugin name=\"{plugin}\"{}>\n{body}\n</plugin>",
        nonce::attr(nonce)
    )
}

/// 한 훅이 한 번에 내는 알림을 level 별로 모은다. level 마다 태그 하나(HOOK-MESSAGES.md: 섞으면 낮은 알림이 높게 읽힌다).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Notices {
    action: Vec<String>,
    warn: Vec<String>,
    info: Vec<String>,
}

impl Notices {
    /// 빈 모음.
    pub fn new() -> Notices {
        Notices::default()
    }

    /// `level` 에 알림 한 줄(또는 여러 줄 글)을 더한다.
    pub fn push(&mut self, level: Level, text: impl Into<String>) {
        let list = match level {
            Level::Action => &mut self.action,
            Level::Warn => &mut self.warn,
            Level::Info => &mut self.info,
        };
        list.push(text.into());
    }

    /// 알림이 하나도 없는지.
    pub fn is_empty(&self) -> bool {
        self.action.is_empty() && self.warn.is_empty() && self.info.is_empty()
    }

    /// action, warn, info 순서로 level 마다 태그 하나, 태그 사이는 줄바꿈. 알림이 없으면 빈 문자열.
    ///
    /// 한 태그 안의 알림은 줄바꿈으로 잇는다(python `"\n".join(texts)`).
    pub fn render(&self, name: &str, nonce: Option<&Nonce>) -> String {
        [
            (Level::Action, &self.action),
            (Level::Warn, &self.warn),
            (Level::Info, &self.info),
        ]
        .into_iter()
        .filter(|(_, texts)| !texts.is_empty())
        .map(|(level, texts)| harness_hook(name, level, nonce, &texts.join("\n")))
        .collect::<Vec<_>>()
        .join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_one_tag_per_level_in_order() {
        let n = Nonce::from_salt("00".repeat(32).as_str(), "abc");
        let mut notes = Notices::new();
        notes.push(Level::Info, "i1");
        notes.push(Level::Warn, "w1");
        notes.push(Level::Info, "i2");
        assert_eq!(
            notes.render("x", Some(&n)),
            "<harness-hook name=\"x\" level=\"warn\" nonce=\"39596342ed0e\">\nw1\n</harness-hook>\n\
             <harness-hook name=\"x\" level=\"info\" nonce=\"39596342ed0e\">\ni1\ni2\n</harness-hook>"
        );
        assert_eq!(Notices::new().render("x", None), "");
        assert_eq!(
            plugin_block("q", None, "t"),
            "<plugin name=\"q\">\nt\n</plugin>"
        );
    }
}
