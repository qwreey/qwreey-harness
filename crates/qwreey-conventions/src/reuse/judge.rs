//! 겹침 판정(H1, python reuse-check 의 `judge`, `text_of`, `shown`).
//!
//! 추가한 묶음 하나를 색인의 다른 묶음과 견준다. 원소가 `min_shared` 개 이상 겹치거나 2개 이상이면서 자카드 0.5 이상이고,
//! 한쪽이라도 정의면 짝이다. 타입 합집합과 런타임 목록은 원소가 어긋날 때만(N7), 타입끼리는 같을 때만 본다.
//! 짝마다 import 할 수 있으면 N1(참조하라), 없으면 N2(사본으로 표시하라)다.

use std::collections::BTreeSet;

use harness_hook::py::path::dirname;

use crate::halt::{Halt, Result};
use crate::reuse::config::ReuseConfig;
use crate::reuse::files::{ext_of, lang};
use crate::reuse::index::Index;
use crate::reuse::packages::Packages;
use crate::reuse::sets::{MarkKind, StringSet, reason_ok};

/// 알림 종류(그림자 기록의 `notice`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    /// 같은 언어, import 할 수 있는 정의.
    N1,
    /// import 할 수 없는 정의끼리.
    N2,
    /// 타입 합집합과 런타임 목록이 어긋남.
    N7,
}

impl Kind {
    /// 그림자 기록과 알림 종류의 글.
    pub fn code(self) -> &'static str {
        match self {
            Kind::N1 => "N1",
            Kind::N2 => "N2",
            Kind::N7 => "N7",
        }
    }
}

/// 짝 하나(python 의 hit 튜플).
#[derive(Clone, Debug)]
pub struct Hit {
    pub kind: Kind,
    pub other_rel: String,
    pub other_line: i64,
    pub other_name: String,
    pub shared: BTreeSet<String>,
    /// 겹친 원소 수.
    pub k: usize,
    /// 이쪽 원소 수.
    pub n: usize,
    /// 자카드 지수.
    pub j: f64,
    pub other_flags: i64,
    pub theirs: BTreeSet<String>,
}

/// 판정에 드는 설정 값(python 이 judge 를 부를 때마다 읽는 `min_shared`, `vocab_ok`).
pub struct Judge<'a> {
    pub rel: &'a str,
    pub min_shared: i128,
    pub vocab: Vec<BTreeSet<String>>,
}

impl<'a> Judge<'a> {
    /// 설정을 읽는다. python 은 첫 judge 에서 값이 틀리면 끝난다.
    pub fn new(rel: &'a str, cfg: &ReuseConfig) -> Result<Judge<'a>> {
        Ok(Judge {
            rel,
            min_shared: cfg.min_shared()?,
            vocab: cfg.vocab()?,
        })
    }

    /// python `judge(root, rel, st, ents, cfg, cache)`: 묶음 `st` 의 짝들, 색인 차례로.
    pub fn hits(&self, st: &StringSet, index: &Index, packages: &mut Packages) -> Result<Vec<Hit>> {
        let mine = st.members();
        let my_file_mark = index.get(self.rel).and_then(|e| file_mark(&e.marks));
        let mut out = Vec::new();

        for (orel, e) in index.iter() {
            let their_file = file_mark(&e.marks);
            for o in &e.sets {
                if orel == self.rel && st.line == o.line {
                    continue;
                }

                // Overlap
                let theirs = o.members();
                let shared: BTreeSet<&str> = mine.intersection(&theirs).copied().collect();
                let k = shared.len();
                let union = mine.union(&theirs).count();
                if union == 0 {
                    return Err(Halt::PyError("division by zero on two empty sets"));
                }
                let j = k as f64 / union as f64;
                if !(k as i128 >= self.min_shared || (k >= 2 && j >= 0.5)) {
                    continue;
                }

                // Which pair kind, if any
                let Some(kind) = self.pair_kind(st, o, orel, &mine, &theirs) else {
                    continue;
                };
                if self
                    .vocab
                    .iter()
                    .any(|vs| shared.iter().all(|x| vs.contains(*x)))
                {
                    continue;
                }

                // A marked copy and its source are not a pair
                if my_file_mark.is_some_and(|m| m == orel || Some(m) == their_file)
                    || their_file.is_some_and(|t| t == self.rel)
                {
                    continue;
                }
                if marked_pair(st, o, self.rel, orel) {
                    continue;
                }
                if st.dup.as_deref().is_some_and(reason_ok)
                    || o.dup.as_deref().is_some_and(reason_ok)
                {
                    continue;
                }

                // Same language and importable, else a cross-package copy
                let kind = match kind {
                    Kind::N1 if !packages.importable(self.rel, orel)? => {
                        if !(st.is_def() && o.is_def()) {
                            continue;
                        }
                        Kind::N2
                    }
                    other => other,
                };
                out.push(Hit {
                    kind,
                    other_rel: orel.to_owned(),
                    other_line: o.line,
                    other_name: o.name.clone(),
                    shared: shared.iter().map(|x| (*x).to_owned()).collect(),
                    k,
                    n: mine.len(),
                    j,
                    other_flags: o.flags,
                    theirs: theirs.iter().map(|x| (*x).to_owned()).collect(),
                });
            }
        }
        Ok(out)
    }

    // 정의, 같은 파일의 거리, 타입과 목록 규칙. 짝이 아니면 None
    fn pair_kind(
        &self,
        st: &StringSet,
        o: &StringSet,
        orel: &str,
        mine: &BTreeSet<&str>,
        theirs: &BTreeSet<&str>,
    ) -> Option<Kind> {
        let (me_def, o_def) = (st.is_def(), o.is_def());
        if !(me_def || o_def) {
            return None;
        }
        if orel == self.rel && !(me_def && o_def && (st.line - o.line).abs() >= 50) {
            return None;
        }

        // 타입 합집합과 런타임 목록: 어긋날 때만
        if st.is_type() != o.is_type() {
            let same_lang = lang(&ext_of(self.rel)) == lang(&ext_of(orel));
            if mine == theirs || !(me_def && o_def) || !same_lang {
                return None;
            }
            return Some(Kind::N7);
        }
        // 타입끼리는 같을 때만
        if st.is_type() && mine != theirs {
            return None;
        }
        Some(Kind::N1)
    }

    /// python `text_of(kind, rel, st, hit)`: 알림 글.
    pub fn text_of(&self, st: &StringSet, hit: &Hit) -> String {
        let rel = self.rel;
        let ln = st.line;
        let name = if st.name.is_empty() {
            "this list"
        } else {
            &st.name
        };
        let (orel, oln) = (hit.other_rel.as_str(), hit.other_line);
        let oname = hit.other_name.as_str();
        let c = match lang(&ext_of(rel)) {
            Some("luau") => "--",
            Some("py") => "#",
            _ => "//",
        };

        // One text per kind
        match hit.kind {
            Kind::N7 => {
                let mine: BTreeSet<&str> = st.members();
                let mt = if st.is_type() { "type" } else { "list" };
                let ot = if hit.other_flags & crate::reuse::sets::FLAG_TYPE != 0 {
                    "type"
                } else {
                    "list"
                };
                let miss: Vec<&str> = hit
                    .theirs
                    .iter()
                    .map(String::as_str)
                    .filter(|x| !mine.contains(x))
                    .collect();
                let extra: Vec<&str> = mine
                    .iter()
                    .copied()
                    .filter(|x| !hit.theirs.contains(*x))
                    .collect();
                format!(
                    "{rel}:{ln}: {mt} {name} and {ot} {oname} at {orel}:{oln} hold different strings (missing {}, \
                     extra {}). Make them match, or put `{c} @dup-ok: <reason>` above if they differ on purpose.",
                    or_none(&shown(&miss)),
                    or_none(&shown(&extra)),
                )
            }
            Kind::N2 => {
                let opkg = match dirname(orel) {
                    "" => ".",
                    d => d,
                };
                let target = if oname.is_empty() { name } else { oname };
                format!(
                    "{rel}:{ln}: string set repeats {name} at {orel}:{oln} in {opkg}, which this package cannot import ({}/{} shared: {}). \
                     Same knowledge: keep it, mark it `{c} @copy-of: {orel}#{target}` and compare the two in the repo's tests (or generate one from the other); \
                     do not add a cross-package import. A value each project sets differently: config with a `DEFAULT_*` fallback instead. \
                     Only alike: `{c} @dup-ok: <reason>`, the reason saying why they are different facts.",
                    hit.k,
                    hit.n,
                    shown_set(&hit.shared),
                )
            }
            Kind::N1 => {
                let (list, it) = if oname.is_empty() {
                    ("a list", "it")
                } else {
                    (oname, oname)
                };
                format!(
                    "{rel}:{ln}: string set repeats {list} at {orel}:{oln} ({}/{} shared: {}). \
                     Same knowledge: reference {it} instead, or move it to one module both import. \
                     A value each project sets differently: config with a `DEFAULT_*` fallback instead. \
                     Only alike: put `{c} @dup-ok: <reason>` above it, the reason saying why they are different facts.",
                    hit.k,
                    hit.n,
                    shown_set(&hit.shared),
                )
            }
        }
    }
}

// 파일 사본 표시의 대상(python `next((m[1] for m in marks if m[3] == "f"), None)`)
fn file_mark(marks: &[crate::reuse::sets::Mark]) -> Option<&str> {
    marks
        .iter()
        .find(|m| m.kind == MarkKind::File)
        .map(|m| m.target.as_str())
        .filter(|t| !t.is_empty())
}

// 값 사본 표시로 이은 짝
fn marked_pair(st: &StringSet, o: &StringSet, rel: &str, orel: &str) -> bool {
    let copy = st.copy_of.as_deref().filter(|c| !c.is_empty());
    let ocopy = o.copy_of.as_deref().filter(|c| !c.is_empty());
    let mine_points = copy.is_some_and(|c| c == format!("{orel}#{}", o.name) || Some(c) == ocopy);
    let theirs_points = ocopy.is_some_and(|c| c == format!("{rel}#{}", st.name));
    mine_points || theirs_points
}

/// python `shown(els)`: 정렬한 앞 5개를 따옴표로, 나머지는 `+n`.
pub fn shown(sorted: &[&str]) -> String {
    let head: Vec<String> = sorted.iter().take(5).map(|x| format!("\"{x}\"")).collect();
    let more = if sorted.len() > 5 {
        format!(" +{}", sorted.len() - 5)
    } else {
        String::new()
    };
    format!("{}{more}", head.join(", "))
}

fn shown_set(set: &BTreeSet<String>) -> String {
    let sorted: Vec<&str> = set.iter().map(String::as_str).collect();
    shown(&sorted)
}

// python `shown(x) or 'none'`
fn or_none(text: &str) -> &str {
    if text.is_empty() { "none" } else { text }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 다섯 개를 넘으면 `+n` 이고 빈 목록은 빈 글이다(알림은 그때 `none`).
    #[test]
    fn shown_like_python() {
        assert_eq!(shown(&["a", "b"]), "\"a\", \"b\"");
        assert_eq!(
            shown(&["a", "b", "c", "d", "e", "f", "g"]),
            "\"a\", \"b\", \"c\", \"d\", \"e\" +2"
        );
        assert_eq!(or_none(&shown(&[])), "none");
    }
}
