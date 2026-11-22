//! 글 속의 형제 저장소 안 경로 찾기(python `sibling_notice.find_hits`).
//!
//! python 은 형제마다, 그리고 모두에 하나씩 정규식을 만들어 finditer 한다(`REST` 는 경로 꼬리 글자):
//! - 절대 꼴(형제마다): `(?<![\w.-])(?:<루트>|~[\\/]<홈 기준 루트>)[\\/](REST+)`. 루트의 구분자 자리는 `\` 와 `/` 둘 다 받는다.
//! - 위로 꼴: `(?<![\w.-])(?:\.\.[\\/])+(<이름들>)[\\/](REST+)`.
//! - 맨 이름 꼴: `(?<![\w.\-/\\~$])(<이름들>)/(REST+)`. 그 경로가 형제 안에만 있을 때만 센다.
//!
//! why not 그 정규식(py::re): 패턴이 형제 수만큼 실행마다 새로 생기고 앞 보기가 있어 rx 가 받지 못한다. py::re 로 큰 글을
//! 형제 수만큼 훑으면 python 보다 느리다. 그래서 같은 뜻을 손으로 훑는다: 이름들은 긴 것부터 앞에서부터 맞추고(python 의
//! `|` 순서), `(?:\.\.[\\/])+` 는 가장 많이 먹은 뒤 하나씩 내려 본다(되돌아가기). Windows 는 python 처럼 대소문자를 가리지 않는다.

use std::collections::BTreeMap;

use harness_hook::py::ospath;
use harness_hook::py::text::is_space;
use harness_hook::py::unicode::is_word;

use crate::context::Context;
use crate::paths::{home, inside};
use crate::stop::{Result, Stop};

/// 형제 저장소 하나: 이름(폴더 이름)과 루트.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Sibling {
    pub name: String,
    pub root: String,
}

/// 형제 이름마다 (형제 안 상대 경로, 글에 적힌 꼴), 글에 처음 나온 순서. 같은 상대 경로는 한 번만 센다.
pub type Hits = BTreeMap<String, Vec<(String, String)>>;

const ICASE: bool = cfg!(windows);

/// 경로 하나를 맞출 꼴: 글자 조각들. 조각 사이 자리는 `\` 와 `/` 둘 다 받는다(python `_sep_re`).
type PathPattern = Vec<Vec<char>>;

// 경로 꼬리 글자(python REST): 공백, 따옴표, 괄호, 줄 번호(`:12`), 앵커(`#x`), 문장 부호 밖
fn is_rest(c: char) -> bool {
    !is_space(c) && !"`'\"<>()[]{}|,;:#*!?".contains(c)
}

fn is_sep(c: char) -> bool {
    c == '\\' || c == '/'
}

/// python `find_hits(text, sibs, local_dirs)`.
pub fn find_hits(
    ctx: &Context,
    text: &str,
    sibs: &[Sibling],
    local_dirs: &[String],
) -> Result<Hits> {
    if sibs.is_empty() || text.is_empty() {
        return Ok(Hits::new());
    }
    let scan = Scan::new(text, sibs);
    let mut found = Found::default();

    // Absolute forms, one per sibling
    for sib in sibs {
        let prefixes = abs_prefixes(ctx, &sib.root)?;
        for m in scan.matches(|at| scan.abs_at(at, &prefixes)) {
            found.add(&sib.name, &scan, &m);
        }
    }

    // `../<name>/...`
    for m in scan.matches(|at| scan.up_at(at)) {
        found.add(&scan.name_of(&m)?, &scan, &m);
    }

    // `<name>/...` that exists only in the sibling
    for m in scan.matches(|at| scan.bare_at(at)) {
        let name = scan.name_of(&m)?;
        let rel = clean(&scan.text(m.rest));
        if !keep(&rel) {
            continue;
        }
        let Some(sib) = sibs.iter().find(|s| s.name == name) else {
            return Err(Stop::Raises("KeyError: the matched name is not a sibling"));
        };
        if exists_only_there(&sib.root, &name, &rel, local_dirs) {
            found.add(&name, &scan, &m);
        }
    }
    Ok(found.into_hits())
}

// python _abs_prefixes: 루트 그대로, 홈 아래면 `~/` 꼴도. 조각마다 그 사이 구분자는 `\` 와 `/` 둘 다 받는다
fn abs_prefixes(ctx: &Context, root: &str) -> Result<Vec<PathPattern>> {
    let mut out = vec![pieces(root)];
    let home = home(ctx);
    if inside(root, &home) && root != home {
        let rel =
            ospath::relpath(root, &home).ok_or(Stop::Raises("os.path.relpath of the root"))?;
        let mut tilde = vec![vec!['~']];
        tilde.extend(pieces(&rel));
        out.push(tilde);
    }
    Ok(out)
}

// python _sep_re 의 조각: 끝 구분자를 떼고 두 구분자로 나눈다
fn pieces(path: &str) -> PathPattern {
    path.trim_end_matches(is_sep)
        .split(is_sep)
        .map(|p| p.chars().collect())
        .collect()
}

// python _clean: `\` 를 `/` 로, 끝의 `.` 과 `/` 를 뗀다
fn clean(rest: &str) -> String {
    rest.replace('\\', "/")
        .trim_end_matches(['.', '/'])
        .to_owned()
}

// 위로 벗어나는 경로와 빈 경로는 세지 않는다
fn keep(rel: &str) -> bool {
    !rel.is_empty() && !rel.starts_with("../") && rel != ".."
}

/// `<name>/<rel>` 이 형제(root) 안에 있고 이 저장소 쪽(local_dirs 기준)에는 없으면 참.
pub fn exists_only_there(root: &str, name: &str, rel: &str, local_dirs: &[String]) -> bool {
    let p = ospath::normpath(&ospath::join(root, rel));
    if !inside(&p.replace('\\', "/"), &root.replace('\\', "/")) || !lexists(&p) {
        return false;
    }
    !local_dirs
        .iter()
        .any(|d| lexists(&ospath::join(&ospath::join(d, name), rel)))
}

// python os.path.lexists: 링크 자체가 있으면 참, 넘기지 못하는 경로는 거짓
fn lexists(path: &str) -> bool {
    harness_hook::py::fs::os_path(path).is_some_and(|p| std::fs::symlink_metadata(p).is_ok())
}

/// 일치 하나(글자 자리): 전체, 이름(위로 꼴과 맨 이름 꼴), 경로 꼬리.
struct Match {
    start: usize,
    end: usize,
    name: Option<(usize, usize)>,
    rest: (usize, usize),
}

/// 훑을 글과 이름들.
struct Scan {
    chars: Vec<char>,
    /// 이름들, python `|` 순서(글자 수가 긴 것부터, 같으면 형제 순서).
    alt: Vec<Vec<char>>,
    /// 맞춘 글에서 형제 이름으로(python `by_name`).
    by_name: Vec<(String, String)>,
}

impl Scan {
    fn new(text: &str, sibs: &[Sibling]) -> Scan {
        let mut alt: Vec<Vec<char>> = sibs.iter().map(|s| s.name.chars().collect()).collect();
        alt.sort_by_key(|n| std::cmp::Reverse(n.len()));
        let by_name = sibs
            .iter()
            .map(|s| (key(&s.name), s.name.clone()))
            .collect();
        Scan {
            chars: text.chars().collect(),
            alt,
            by_name,
        }
    }

    fn text(&self, (start, end): (usize, usize)) -> String {
        self.chars[start..end].iter().collect()
    }

    // python finditer: 앞에서부터, 일치 끝에서 다시
    fn matches(&self, at: impl Fn(usize) -> Option<Match>) -> Vec<Match> {
        let mut out = Vec::new();
        let mut pos = 0;
        while pos < self.chars.len() {
            match at(pos) {
                Some(m) => {
                    pos = m.end;
                    out.push(m);
                }
                None => pos += 1,
            }
        }
        out
    }

    // 이름 자리에 적힌 글의 형제 이름(python `by_name.get(g.lower() if flags else g, g)`)
    fn name_of(&self, m: &Match) -> Result<String> {
        let written = self.text(m.name.ok_or(Stop::Raises("a match without a name"))?);
        let k = key(&written);
        let name = self
            .by_name
            .iter()
            .rev()
            .find(|(lk, _)| *lk == k)
            .map_or(written, |(_, n)| n.clone());
        Ok(name)
    }

    // (?<![\w.-])
    fn after_boundary(&self, at: usize) -> bool {
        at == 0 || !matches!(self.chars[at - 1], c if is_word(u32::from(c)) || c == '.' || c == '-')
    }

    // 절대 꼴 하나를 `at` 에서
    fn abs_at(&self, at: usize, prefixes: &[PathPattern]) -> Option<Match> {
        if !self.after_boundary(at) {
            return None;
        }
        prefixes.iter().find_map(|prefix| {
            let end = self.pieces_at(at, prefix)?;
            self.tail(at, None, end)
        })
    }

    // 위로 꼴을 `at` 에서: `../` 를 가장 많이 먹은 뒤 하나씩 내려 본다
    fn up_at(&self, at: usize) -> Option<Match> {
        if !self.after_boundary(at) {
            return None;
        }
        let mut ups = 0;
        while self.chars.get(at + 3 * ups) == Some(&'.')
            && self.chars.get(at + 3 * ups + 1) == Some(&'.')
            && self.chars.get(at + 3 * ups + 2).is_some_and(|c| is_sep(*c))
        {
            ups += 1;
        }
        (1..=ups)
            .rev()
            .find_map(|n| self.name_then(at, at + 3 * n, is_sep))
    }

    // 맨 이름 꼴을 `at` 에서
    fn bare_at(&self, at: usize) -> Option<Match> {
        let blocked = at > 0
            && matches!(self.chars[at - 1], c if is_word(u32::from(c)) || matches!(c, '.' | '-' | '/' | '\\' | '~' | '$'));
        if blocked {
            return None;
        }
        self.name_then(at, at, |c| c == '/')
    }

    // `name_at` 에서 이름 하나(python `|` 순서), 구분자, 꼬리
    fn name_then(&self, start: usize, name_at: usize, sep: fn(char) -> bool) -> Option<Match> {
        self.alt.iter().find_map(|name| {
            let end = self.literal_at(name_at, name)?;
            if !self.chars.get(end).is_some_and(|c| sep(*c)) {
                return None;
            }
            self.tail(start, Some((name_at, end)), end)
        })
    }

    // `[\\/](REST+)` 를 `sep_at` 에서
    fn tail(&self, start: usize, name: Option<(usize, usize)>, sep_at: usize) -> Option<Match> {
        if !self.chars.get(sep_at).is_some_and(|c| is_sep(*c)) {
            return None;
        }
        let rest_start = sep_at + 1;
        let len = self.chars[rest_start..]
            .iter()
            .take_while(|c| is_rest(**c))
            .count();
        (len > 0).then_some(Match {
            start,
            end: rest_start + len,
            name,
            rest: (rest_start, rest_start + len),
        })
    }

    // 조각들을 사이 구분자와 함께 `at` 에서. 맞으면 끝 자리
    fn pieces_at(&self, at: usize, pieces: &[Vec<char>]) -> Option<usize> {
        let mut pos = at;
        for (i, piece) in pieces.iter().enumerate() {
            if i > 0 {
                if !self.chars.get(pos).is_some_and(|c| is_sep(*c)) {
                    return None;
                }
                pos += 1;
            }
            pos = self.literal_at(pos, piece)?;
        }
        Some(pos)
    }

    fn literal_at(&self, at: usize, literal: &[char]) -> Option<usize> {
        let end = at + literal.len();
        let got = self.chars.get(at..end)?;
        got.iter()
            .zip(literal)
            .all(|(a, b)| same_char(*a, *b))
            .then_some(end)
    }
}

// Windows 는 python re.IGNORECASE 처럼 소문자끼리 견준다
fn same_char(a: char, b: char) -> bool {
    if ICASE {
        a == b || a.to_lowercase().eq(b.to_lowercase())
    } else {
        a == b
    }
}

fn key(name: &str) -> String {
    if ICASE {
        name.to_lowercase()
    } else {
        name.to_owned()
    }
}

/// 형제 하나에서 찾은 상대 경로: 처음 나온 자리(글자)와 글에 적힌 꼴.
struct RelHit {
    rel: String,
    start: usize,
    shown: String,
}

/// 이름마다 찾은 상대 경로들, 넣은 순서(python 의 dict).
#[derive(Default)]
struct Found(Vec<(String, Vec<RelHit>)>);

impl Found {
    fn add(&mut self, name: &str, scan: &Scan, m: &Match) {
        let rel = clean(&scan.text(m.rest));
        if !keep(&rel) {
            return;
        }
        let shown = scan
            .text((m.start, m.end))
            .trim_end_matches(['.', ','])
            .to_owned();
        let hit = RelHit {
            rel,
            start: m.start,
            shown,
        };

        // python: `if rel not in seen or m.start() < seen[rel][0]`
        let rels = self.rels_of(name);
        match rels.iter_mut().find(|r| r.rel == hit.rel) {
            Some(slot) if hit.start < slot.start => *slot = hit,
            Some(_) => {}
            None => rels.push(hit),
        }
    }

    // python found.setdefault(name, {})
    fn rels_of(&mut self, name: &str) -> &mut Vec<RelHit> {
        let at = match self.0.iter().position(|(n, _)| n == name) {
            Some(i) => i,
            None => {
                self.0.push((name.to_owned(), Vec::new()));
                self.0.len() - 1
            }
        };
        &mut self.0[at].1
    }

    // 이름마다 글에 나온 순서로
    fn into_hits(self) -> Hits {
        self.0
            .into_iter()
            .map(|(name, mut rels)| {
                rels.sort_by_key(|r| r.start);
                (name, rels.into_iter().map(|r| (r.rel, r.shown)).collect())
            })
            .collect()
    }
}
