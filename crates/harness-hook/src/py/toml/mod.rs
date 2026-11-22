//! python `tomllib.loads`(TOML 1.0, python 3.11~3.14 의 `Lib/tomllib/_parser.py` 를 옮긴 것): 같은 글을 받고 같은 글을 거절한다.
//!
//! why not toml crate: 새 의존성은 사용자가 정한다. 그리고 훅은 읽지 못한 파일 전체를 `{}` 로 보므로, 받는 글과 거절하는 글이
//! python 과 같아야 한다(crate 마다 날짜, 정수 크기, 키 다시 쓰기의 판정이 조금씩 다르다).
//!
//! 값은 python 이 주는 꼴 가운데 훅이 보는 것만 든다: 글, 정수, 실수, bool, 목록, 표. 날짜와 시각은 원래 글을 든다.
//! python 과 다른 곳: python 은 목록과 인라인 표가 약 490 겹을 넘으면 RecursionError 로 끝난다(부르는 깊이에 따라 몇 겹 다르다).
//! 이 판은 [`MAX_NESTING`] 겹에서 거절한다.

mod parse;
mod scalar;

use parse::Parser;

/// 이보다 깊이 겹친 목록과 인라인 표는 거절한다(python 의 재귀 한도 자리).
pub const MAX_NESTING: usize = 490;
/// 키 조각 수 한도(python `MAX_KEY_PARTS = sys.getrecursionlimit()`).
pub(crate) const MAX_KEY_PARTS: usize = 1000;
/// 10진 정수의 자릿수 한도(python `int()` 의 4300 자리).
pub(crate) const MAX_INT_DIGITS: usize = 4300;

/// TOML 값 하나(python `tomllib` 이 주는 값의 자리).
#[derive(Clone, Debug, PartialEq)]
pub enum Item {
    Str(String),
    Int(i128),
    /// i128 밖의 정수. 원래 글에서 `_` 를 뺀 것(`0x` 같은 접두사와 부호는 그대로).
    BigInt(String),
    Float(f64),
    Bool(bool),
    /// 날짜, 날짜와 시각, 시각(python `date`, `datetime`, `time`). 원래 글 그대로.
    Datetime(String),
    Array(Vec<Item>),
    Table(Table),
}

impl Item {
    /// python 에서 참인가(빈 글, 0, 빈 목록과 표, False 는 거짓이고 날짜와 시각은 늘 참).
    pub fn truthy(&self) -> bool {
        match self {
            Item::Str(s) => !s.is_empty(),
            Item::Int(i) => *i != 0,
            Item::BigInt(_) | Item::Datetime(_) => true,
            Item::Float(f) => *f != 0.0,
            Item::Bool(b) => *b,
            Item::Array(a) => !a.is_empty(),
            Item::Table(t) => !t.is_empty(),
        }
    }

    /// 글이면 그 글.
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Item::Str(s) => Some(s),
            _ => None,
        }
    }

    /// 표면 그 표.
    pub fn as_table(&self) -> Option<&Table> {
        match self {
            Item::Table(t) => Some(t),
            _ => None,
        }
    }
}

/// 넣은 순서를 지키는 표(python dict).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Table(Vec<(String, Item)>);

impl Table {
    /// 키의 값.
    pub fn get(&self, key: &str) -> Option<&Item> {
        self.0.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    /// (키, 값)들, 넣은 순서로.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Item)> {
        self.0.iter().map(|(k, v)| (k.as_str(), v))
    }

    /// 키가 없는가.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// 키의 값을 고칠 수 있게.
    pub(crate) fn get_mut(&mut self, key: &str) -> Option<&mut Item> {
        self.0.iter_mut().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    /// 키가 있는가(python `key in table`).
    pub(crate) fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// 새 키를 끝에 넣는다. 부르는 곳이 먼저 [`Table::contains`] 로 없는지 본다.
    pub(crate) fn push(&mut self, key: String, value: Item) {
        self.0.push((key, value));
    }
}

/// python 이 거절하는 글(TOMLDecodeError, 또는 그 안에서 나는 ValueError, IndexError, RecursionError).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TomlError;

pub(crate) type Parsed<T> = Result<T, TomlError>;
pub(crate) type Key = Vec<String>;

/// python `tomllib.load(open(path, "rb"))`의 글 부분: UTF-8 바이트를 읽는다. UTF-8 이 아니면 거절한다.
pub fn loads_bytes(bytes: &[u8]) -> Parsed<Table> {
    let text = std::str::from_utf8(bytes).map_err(|_| TomlError)?;
    loads(text)
}

/// python `tomllib.loads(text)`.
pub fn loads(text: &str) -> Parsed<Table> {
    let src: Vec<char> = text.replace("\r\n", "\n").chars().collect();
    Parser::new(&src).document()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn packs(text: &str) -> Vec<(String, String)> {
        let doc = loads(text).unwrap();
        let Some(Item::Array(items)) = doc.get("packs") else {
            return Vec::new();
        };
        items
            .iter()
            .filter_map(Item::as_table)
            .map(|t| {
                let s = |k| t.get(k).and_then(Item::as_str).unwrap_or("").to_owned();
                (s("name"), s("path"))
            })
            .collect()
    }

    /// 배열 표, 인라인 표, 점 키, 주석과 여러 줄 글을 python 처럼 읽는다.
    #[test]
    fn reads_coderag_configs() {
        let text = "# c\nformat = 1\n[[packs]]\nname = \"a\"\npath = '/p/a' # t\n\n[[packs]]\nname = \"b\"\n\
                    [[contexts.docs]]\nprovider = [\"md\",]\n  [[contexts.docs.targets]]\n  options = { exclude = [\"w\"] }\n\
                    s = \"\"\"\nx\\\n   y\"\"\"\n";
        assert_eq!(
            packs(text),
            vec![("a".into(), "/p/a".into()), ("b".into(), String::new())]
        );
        let doc = loads(text).unwrap();
        assert_eq!(
            doc.get("s"),
            None,
            "s belongs to the last [[contexts.docs.targets]]"
        );
    }

    /// python 이 거절하는 글: 키 다시 쓰기, 표 두 번 열기, 인라인 표 고치기, 없는 날짜, 큰 10진 정수, 못 드는 글자.
    #[test]
    fn rejects_what_python_rejects() {
        for bad in [
            "a = 1\na = 2",
            "[t]\n[t]",
            "a = {b = 1}\n[a]",
            "a.b = 1\n[a]",
            "a = [1]\n[[a]]",
            "d = 1979-02-30",
            "d = 0000-01-01",
            "x = 1 2",
            "s = \"a\u{1}\"",
            "# \u{7f}",
            "t = {a = 1,}",
            "[[a]]\n[a]",
        ] {
            assert_eq!(loads(bad), Err(TomlError), "{bad:?}");
        }
        assert!(loads(&format!("a = {}", "1".repeat(4301))).is_err());
        assert!(loads(&format!("a = {}", "1".repeat(4300))).is_ok());
    }

    /// 날짜, 시각, 특수 실수, 접두사 정수와 참거짓 판정.
    #[test]
    fn values_and_truthiness() {
        let doc = loads(
            "a = 1979-05-27T07:32:00.5Z\nb = 07:32:00\nc = -0.0\nd = nan\nf = 0x1f\n\
             g = 2024-02-29 # leap\nh = 1e400\ni = 0\nj = \"\"\n[k]\n[k.l]\n",
        );
        let doc = doc.unwrap();
        assert!(matches!(doc.get("a"), Some(Item::Datetime(t)) if t == "1979-05-27T07:32:00.5Z"));
        assert!(doc.get("b").unwrap().truthy());
        assert!(!doc.get("c").unwrap().truthy());
        assert!(doc.get("d").unwrap().truthy());
        assert_eq!(doc.get("f"), Some(&Item::Int(31)));
        assert!(doc.get("h").unwrap().truthy());
        assert!(!doc.get("i").unwrap().truthy());
        assert!(!doc.get("j").unwrap().truthy());
        assert!(doc.get("k").unwrap().truthy());

        // `0x_1` is not hex: python reads 0, then rejects the rest
        assert!(loads("e = 0x_1").is_err());
    }
}
