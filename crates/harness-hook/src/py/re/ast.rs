//! 패턴을 읽은 나무. python `re._parser` 의 SubPattern 자리다.

/// 패턴 조각 하나.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) enum Node {
    /// 글자 하나(코드 포인트. 패턴이 escape 로 쓴 서로게이트처럼 문자가 아닌 코드는 어떤 글에도 맞지 않는다).
    Lit(u32),
    /// `.`
    Any,
    Class(Class),
    At(Anchor),
    /// 괄호. 번호가 없으면 묶기만 하는 `(?:...)` 다.
    Group(Option<usize>, Box<Node>),
    Concat(Vec<Node>),
    Alt(Vec<Node>),
    Repeat(Box<Repeat>),
    /// `\1`, `(?P=name)`
    Backref(usize),
    Look(Box<Look>),
    /// `(?>...)`: 안에서 처음 맞은 길로 굳히고 되돌아가 다시 찾지 않는다.
    Atomic(Box<Node>),
    /// 늘 실패한다(`(?!)`).
    Fail,
}

/// `x*`, `x{m,n}?` 같은 되풀이.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Repeat {
    pub node: Node,
    pub min: u32,
    /// `None` 은 끝없음.
    pub max: Option<u32>,
    pub greedy: bool,
    /// `x*+` 꼴. 원자 괄호로 감싼 탐욕 되풀이와 같다.
    pub possessive: bool,
}

/// `(?=...)`, `(?!...)`, `(?<=...)`, `(?<!...)`
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Look {
    pub behind: bool,
    pub negate: bool,
    pub node: Node,
}

/// `[...]` 또는 `\d` 같은 분류 하나.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Class {
    pub negate: bool,
    pub items: Vec<ClassItem>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum ClassItem {
    /// 글자 하나는 `Range(c, c)`.
    Range(u32, u32),
    Cat(Category),
}

/// `\d`, `\w`, `\s` 와 그 반대.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Category {
    Digit,
    NotDigit,
    Word,
    NotWord,
    Space,
    NotSpace,
}

/// 폭이 없는 자리 검사.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Anchor {
    /// `^`(MULTILINE 이면 줄 머리)
    Begin,
    /// `$`(MULTILINE 이면 줄 끝)
    End,
    /// `\A`
    BeginString,
    /// `\Z`
    EndString,
    /// `\b`
    Boundary,
    /// `\B`
    NotBoundary,
}

impl Node {
    /// 빈 글에도 맞을 수 있는가. 빈 되풀이가 끝없이 돌지 않게 검사를 넣을지 정할 때 본다.
    pub fn nullable(&self) -> bool {
        match self {
            Node::Lit(_) | Node::Any | Node::Class(_) | Node::Fail => false,
            Node::At(_) | Node::Look(_) | Node::Backref(_) => true,
            Node::Group(_, inner) | Node::Atomic(inner) => inner.nullable(),
            Node::Concat(items) => items.iter().all(Node::nullable),
            Node::Alt(items) => items.iter().any(Node::nullable),
            Node::Repeat(r) => r.min == 0 || r.node.nullable(),
        }
    }

    /// 맞는 글자 수의 (최소, 최대). 최대가 없으면 `None`(python `getwidth`).
    pub fn width(&self) -> (u64, Option<u64>) {
        match self {
            Node::Lit(_) | Node::Any | Node::Class(_) => (1, Some(1)),
            Node::At(_) | Node::Look(_) | Node::Fail => (0, Some(0)),
            Node::Backref(_) => (0, None),
            Node::Group(_, inner) | Node::Atomic(inner) => inner.width(),
            Node::Concat(items) => items.iter().fold((0, Some(0)), |(lo, hi), n| {
                let (l, h) = n.width();
                (lo + l, hi.zip(h).map(|(a, b)| a + b))
            }),
            Node::Alt(items) => {
                let widths: Vec<_> = items.iter().map(Node::width).collect();
                let lo = widths.iter().map(|w| w.0).min().unwrap_or(0);
                let hi = widths.iter().try_fold(0, |acc, w| w.1.map(|h| acc.max(h)));
                (lo, hi)
            }
            Node::Repeat(r) => {
                let (l, h) = r.node.width();
                let hi = match (h, r.max) {
                    (Some(0), _) => Some(0),
                    (Some(h), Some(m)) => Some(h * u64::from(m)),
                    _ => None,
                };
                (l * u64::from(r.min), hi)
            }
        }
    }
}
