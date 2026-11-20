//! 알림 문장과 그 급(python `Note`, `top_level`, `render`): 급마다 태그 하나, 높은 급부터.
//!
//! 급 없는 문장은 가장 높은 급의 태그에 실린다. 태그 안은 여는 태그 뒤 줄바꿈, 문장들을 공백 하나로 이은 것, 줄바꿈, 닫는 태그다
//! (`harness_hook::tag::Notices` 와 꼴이 달라 따로 둔다).

/// 알림 급(HOOK-MESSAGES.md). 순서가 급의 높낮이다.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Level {
    Info,
    Warn,
    Action,
}

impl Level {
    fn name(self) -> &'static str {
        match self {
            Level::Info => "info",
            Level::Warn => "warn",
            Level::Action => "action",
        }
    }
}

/// 알림 문장 하나. 급이 `None` 이면 가장 높은 급을 따른다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Note {
    pub level: Option<Level>,
    pub text: String,
}

impl Note {
    /// 급이 있는 문장.
    pub fn new(level: Level, text: impl Into<String>) -> Note {
        Note {
            level: Some(level),
            text: text.into(),
        }
    }
}

/// python `render(notes, session_id)`: `nonce` 는 태그 끝 속성(` nonce="N"` 또는 빈 글).
pub fn render(notes: &[Note], nonce: &str) -> String {
    let top = notes
        .iter()
        .filter_map(|n| n.level)
        .max()
        .unwrap_or(Level::Info);

    // One tag per level, highest first
    let mut tags = Vec::new();
    for level in [Level::Action, Level::Warn, Level::Info] {
        let body: Vec<&str> = notes
            .iter()
            .filter(|n| n.level.unwrap_or(top) == level)
            .map(|n| n.text.as_str())
            .collect();
        if !body.is_empty() {
            tags.push(format!(
                "<harness-hook name=\"structure-reminder\" level=\"{}\"{nonce}>\n{}\n</harness-hook>",
                level.name(),
                body.join(" ")
            ));
        }
    }
    tags.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 급마다 태그 하나, 높은 급부터, 급 없는 문장은 가장 높은 급에.
    #[test]
    fn one_tag_per_level() {
        // A warn and an info note plus a level-less reference
        let notes = [
            Note::new(Level::Info, "i"),
            Note::new(Level::Warn, "w"),
            Note {
                level: None,
                text: "ref".into(),
            },
        ];
        let want = "<harness-hook name=\"structure-reminder\" level=\"warn\" n>\nw ref\n</harness-hook>\n\
                    <harness-hook name=\"structure-reminder\" level=\"info\" n>\ni\n</harness-hook>";
        assert_eq!(render(&notes, " n"), want);

        // Only level-less notes fall back to info
        let alone = [Note {
            level: None,
            text: "r".into(),
        }];
        assert!(render(&alone, "").contains("level=\"info\""));
    }
}
