//! TOML 글을 문장 하나씩 읽는 쪽(python `tomllib._parser`): 키, 표 머리, 글, 목록, 인라인 표, 그리고 키 다시 쓰기 검사.

use std::collections::HashMap;

use super::scalar::{datetime_at, number_at, time_at};
use super::{Item, Key, MAX_KEY_PARTS, MAX_NESTING, Parsed, Table, TomlError};

const FROZEN: u8 = 1;
const EXPLICIT_NEST: u8 = 2;

/// python `Flags`: 키 경로마다 붙은 표시(FROZEN 은 인라인 목록과 표, EXPLICIT_NEST 는 `[표]` 로 이미 연 곳).
#[derive(Default)]
struct Flags {
    root: HashMap<String, FlagNode>,
    pending: Vec<(Key, u8)>,
}

#[derive(Default)]
struct FlagNode {
    flags: u8,
    recursive: u8,
    nested: HashMap<String, FlagNode>,
}

impl Flags {
    fn add_pending(&mut self, key: Key, flag: u8) {
        self.pending.push((key, flag));
    }

    fn finalize_pending(&mut self) {
        for (key, flag) in std::mem::take(&mut self.pending) {
            self.set(&key, flag, false);
        }
    }

    fn unset_all(&mut self, key: &[String]) {
        let Some((stem, parent)) = key.split_last() else {
            return;
        };
        let mut cont = &mut self.root;
        for k in parent {
            match cont.get_mut(k) {
                Some(node) => cont = &mut node.nested,
                None => return,
            }
        }
        cont.remove(stem);
    }

    fn set(&mut self, key: &[String], flag: u8, recursive: bool) {
        let Some((stem, parent)) = key.split_last() else {
            return;
        };
        let mut cont = &mut self.root;
        for k in parent {
            cont = &mut cont.entry(k.clone()).or_default().nested;
        }
        let node = cont.entry(stem.clone()).or_default();
        if recursive {
            node.recursive |= flag;
        } else {
            node.flags |= flag;
        }
    }

    fn is(&self, key: &[String], flag: u8) -> bool {
        let Some((stem, parent)) = key.split_last() else {
            return false;
        };

        // A recursive flag on a parent covers everything below it
        let mut cont = &self.root;
        for k in parent {
            let Some(node) = cont.get(k) else {
                return false;
            };
            if node.recursive & flag != 0 {
                return true;
            }
            cont = &node.nested;
        }

        cont.get(stem)
            .is_some_and(|node| (node.flags | node.recursive) & flag != 0)
    }
}

/// python `NestedDict.get_or_create_nest(key, access_lists=...)`: 경로의 표, 없으면 만든다. 표가 아닌 값이 막으면 거절.
fn nest_mut<'t>(root: &'t mut Table, key: &[String], access_lists: bool) -> Parsed<&'t mut Table> {
    let mut cont = root;
    for k in key {
        if !cont.contains(k) {
            cont.push(k.clone(), Item::Table(Table::default()));
        }

        // An array of tables leads into its last table
        let mut slot = cont.get_mut(k).ok_or(TomlError)?;
        if access_lists && let Item::Array(items) = slot {
            // python cont[-1]: 빈 목록이면 IndexError
            slot = items.last_mut().ok_or(TomlError)?;
        }
        match slot {
            Item::Table(t) => cont = t,
            _ => return Err(TomlError),
        }
    }

    Ok(cont)
}

const WS: &[char] = &[' ', '\t'];
const WS_NL: &[char] = &[' ', '\t', '\n'];

fn is_bare_key(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '-' || c == '_'
}

fn is_ctrl(c: char) -> bool {
    (c as u32) < 32 || c as u32 == 127
}

// 한 줄 글과 주석에 못 드는 글자(탭은 된다)
fn illegal_line(c: char) -> bool {
    is_ctrl(c) && c != '\t'
}

// 여러 줄 글에 못 드는 글자(탭과 줄바꿈은 된다)
fn illegal_multiline(c: char) -> bool {
    is_ctrl(c) && c != '\t' && c != '\n'
}

pub(super) struct Parser<'s> {
    src: &'s [char],
    out: Table,
    flags: Flags,
}

impl<'s> Parser<'s> {
    /// `src` 를 읽을 준비(줄 끝 `\r\n` 은 이미 `\n` 이다).
    pub(super) fn new(src: &'s [char]) -> Parser<'s> {
        Parser {
            src,
            out: Table::default(),
            flags: Flags::default(),
        }
    }

    fn at(&self, pos: usize) -> Option<char> {
        self.src.get(pos).copied()
    }

    fn starts_with(&self, pos: usize, s: &str) -> bool {
        let mut i = pos;
        for c in s.chars() {
            if self.at(i) != Some(c) {
                return false;
            }
            i += 1;
        }
        true
    }

    fn skip(&self, mut pos: usize, chars: &[char]) -> usize {
        while self.at(pos).is_some_and(|c| chars.contains(&c)) {
            pos += 1;
        }
        pos
    }

    // python skip_until: expect 가 있는 자리(없으면 끝), 그 앞에 못 드는 글자가 있으면 거절
    fn skip_until(
        &self,
        pos: usize,
        expect: &str,
        illegal: fn(char) -> bool,
        eof_error: bool,
    ) -> Parsed<usize> {
        let found = (pos..self.src.len()).find(|&i| self.starts_with(i, expect));
        let end = match found {
            Some(end) => end,
            None if eof_error => return Err(TomlError),
            None => self.src.len(),
        };
        if self.src[pos.min(end)..end].iter().any(|&c| illegal(c)) {
            return Err(TomlError);
        }
        Ok(end)
    }

    fn skip_comment(&self, pos: usize) -> Parsed<usize> {
        if self.at(pos) == Some('#') {
            return self.skip_until(pos + 1, "\n", illegal_line, false);
        }
        Ok(pos)
    }

    fn skip_comments_and_array_ws(&self, mut pos: usize) -> Parsed<usize> {
        loop {
            let before = pos;
            pos = self.skip(pos, WS_NL);
            pos = self.skip_comment(pos)?;
            if pos == before {
                return Ok(pos);
            }
        }
    }

    /// python `loads` 의 문장 되풀이: 끝까지 읽은 표.
    pub(super) fn document(mut self) -> Parsed<Table> {
        let mut pos = 0;
        let mut header: Key = Vec::new();
        loop {
            // Leading whitespace and empty lines
            pos = self.skip(pos, WS);
            let Some(c) = self.at(pos) else { break };
            if c == '\n' {
                pos += 1;
                continue;
            }

            // One statement, a comment, then the end of the line
            pos = self.statement(pos, c, &mut header)?;
            pos = self.skip_comment(pos)?;
            match self.at(pos) {
                None => break,
                Some('\n') => pos += 1,
                Some(_) => return Err(TomlError),
            }
        }
        Ok(self.out)
    }

    // 키 = 값, [표], [[배열 표]], 또는 주석만. `[` 는 머리 키를 바꾼다
    fn statement(&mut self, pos: usize, c: char, header: &mut Key) -> Parsed<usize> {
        if is_bare_key(c) || c == '"' || c == '\'' {
            let pos = self.key_value_rule(pos, header)?;
            return Ok(self.skip(pos, WS));
        }
        if c == '[' {
            self.flags.finalize_pending();
            let (next, key) = if self.at(pos + 1) == Some('[') {
                self.create_list_rule(pos)?
            } else {
                self.create_dict_rule(pos)?
            };
            *header = key;
            return Ok(self.skip(next, WS));
        }
        if c == '#' { Ok(pos) } else { Err(TomlError) }
    }

    fn create_dict_rule(&mut self, pos: usize) -> Parsed<(usize, Key)> {
        let pos = self.skip(pos + 1, WS);
        let (pos, key) = self.parse_key(pos)?;
        if self.flags.is(&key, EXPLICIT_NEST) || self.flags.is(&key, FROZEN) {
            return Err(TomlError);
        }
        self.flags.set(&key, EXPLICIT_NEST, false);
        nest_mut(&mut self.out, &key, true)?;
        if !self.starts_with(pos, "]") {
            return Err(TomlError);
        }
        Ok((pos + 1, key))
    }

    fn create_list_rule(&mut self, pos: usize) -> Parsed<(usize, Key)> {
        let pos = self.skip(pos + 2, WS);
        let (pos, key) = self.parse_key(pos)?;
        if self.flags.is(&key, FROZEN) {
            return Err(TomlError);
        }
        self.flags.unset_all(&key);
        self.flags.set(&key, EXPLICIT_NEST, false);

        // python append_nest_to_list
        let (stem, parent) = key.split_last().ok_or(TomlError)?;
        let cont = nest_mut(&mut self.out, parent, true)?;
        match cont.get_mut(stem) {
            Some(Item::Array(items)) => items.push(Item::Table(Table::default())),
            Some(_) => return Err(TomlError),
            None => cont.push(
                stem.clone(),
                Item::Array(vec![Item::Table(Table::default())]),
            ),
        }
        if !self.starts_with(pos, "]]") {
            return Err(TomlError);
        }
        Ok((pos + 2, key))
    }

    fn key_value_rule(&mut self, pos: usize, header: &[String]) -> Parsed<usize> {
        let (pos, key, value) = self.parse_key_value_pair(pos, 0)?;
        let (stem, parent) = key.split_last().ok_or(TomlError)?;
        let abs_parent: Key = header.iter().chain(parent).cloned().collect();

        // Dotted keys may not reopen a table
        for i in 1..key.len() {
            let cont_key: Key = header.iter().chain(&key[..i]).cloned().collect();
            if self.flags.is(&cont_key, EXPLICIT_NEST) {
                return Err(TomlError);
            }
            self.flags.add_pending(cont_key, EXPLICIT_NEST);
        }
        if self.flags.is(&abs_parent, FROZEN) {
            return Err(TomlError);
        }

        // Put the value once
        let nest = nest_mut(&mut self.out, &abs_parent, true)?;
        if nest.contains(stem) {
            return Err(TomlError);
        }
        if matches!(value, Item::Array(_) | Item::Table(_)) {
            let full: Key = header.iter().chain(&key).cloned().collect();
            self.flags.set(&full, FROZEN, true);
        }
        let nest = nest_mut(&mut self.out, &abs_parent, true)?;
        nest.push(stem.clone(), value);
        Ok(pos)
    }

    fn parse_key_value_pair(&self, pos: usize, depth: usize) -> Parsed<(usize, Key, Item)> {
        let (pos, key) = self.parse_key(pos)?;
        if self.at(pos) != Some('=') {
            return Err(TomlError);
        }
        let pos = self.skip(pos + 1, WS);
        let (pos, value) = self.parse_value(pos, depth)?;
        Ok((pos, key, value))
    }

    fn parse_key(&self, pos: usize) -> Parsed<(usize, Key)> {
        let (mut pos, part) = self.parse_key_part(pos)?;
        let mut key = vec![part];
        pos = self.skip(pos, WS);
        while self.at(pos) == Some('.') {
            pos = self.skip(pos + 1, WS);
            let (next, part) = self.parse_key_part(pos)?;
            key.push(part);
            if key.len() > MAX_KEY_PARTS {
                return Err(TomlError);
            }
            pos = self.skip(next, WS);
        }
        Ok((pos, key))
    }

    fn parse_key_part(&self, pos: usize) -> Parsed<(usize, String)> {
        match self.at(pos) {
            Some(c) if is_bare_key(c) => {
                let end = (pos..self.src.len())
                    .find(|&i| !is_bare_key(self.src[i]))
                    .unwrap_or(self.src.len());
                Ok((end, self.src[pos..end].iter().collect()))
            }
            Some('\'') => self.parse_literal_str(pos),
            Some('"') => self.parse_basic_str(pos + 1, false),
            _ => Err(TomlError),
        }
    }

    fn parse_array(&self, pos: usize, depth: usize) -> Parsed<(usize, Item)> {
        let mut items = Vec::new();
        let mut pos = self.skip_comments_and_array_ws(pos + 1)?;
        if self.starts_with(pos, "]") {
            return Ok((pos + 1, Item::Array(items)));
        }
        loop {
            let (next, value) = self.parse_value(pos, depth + 1)?;
            items.push(value);

            // A comma may come before the closing bracket
            pos = self.skip_comments_and_array_ws(next)?;
            match self.at(pos) {
                Some(']') => return Ok((pos + 1, Item::Array(items))),
                Some(',') => {}
                _ => return Err(TomlError),
            }
            pos = self.skip_comments_and_array_ws(pos + 1)?;
            if self.starts_with(pos, "]") {
                return Ok((pos + 1, Item::Array(items)));
            }
        }
    }

    fn parse_inline_table(&self, pos: usize, depth: usize) -> Parsed<(usize, Item)> {
        let mut table = Table::default();
        let mut flags = Flags::default();
        let mut pos = self.skip(pos + 1, WS);
        if self.starts_with(pos, "}") {
            return Ok((pos + 1, Item::Table(table)));
        }
        loop {
            // One key/value, never twice
            let (next, key, value) = self.parse_key_value_pair(pos, depth + 1)?;
            let (stem, parent) = key.split_last().ok_or(TomlError)?;
            if flags.is(&key, FROZEN) {
                return Err(TomlError);
            }
            let nest = nest_mut(&mut table, parent, false)?;
            if nest.contains(stem) {
                return Err(TomlError);
            }
            let frozen = matches!(value, Item::Array(_) | Item::Table(_));
            nest.push(stem.clone(), value);

            // Then a comma or the closing brace
            pos = self.skip(next, WS);
            match self.at(pos) {
                Some('}') => return Ok((pos + 1, Item::Table(table))),
                Some(',') => {}
                _ => return Err(TomlError),
            }
            if frozen {
                flags.set(&key, FROZEN, true);
            }
            pos = self.skip(pos + 1, WS);
        }
    }

    fn parse_escape(&self, pos: usize, multiline: bool) -> Parsed<(usize, String)> {
        let id: String = self.src[pos..(pos + 2).min(self.src.len())]
            .iter()
            .collect();
        let pos = pos + 2;

        // A line-ending backslash eats the whitespace after it
        if multiline && matches!(id.as_str(), "\\ " | "\\\t" | "\\\n") {
            let mut pos = pos;
            if id != "\\\n" {
                pos = self.skip(pos, WS);
                match self.at(pos) {
                    None => return Ok((pos, String::new())),
                    Some('\n') => pos += 1,
                    Some(_) => return Err(TomlError),
                }
            }
            return Ok((self.skip(pos, WS_NL), String::new()));
        }

        let simple = match id.as_str() {
            "\\u" => return self.parse_hex_char(pos, 4),
            "\\U" => return self.parse_hex_char(pos, 8),
            "\\b" => '\u{8}',
            "\\t" => '\t',
            "\\n" => '\n',
            "\\f" => '\u{c}',
            "\\r" => '\r',
            "\\\"" => '"',
            "\\\\" => '\\',
            _ => return Err(TomlError),
        };
        Ok((pos, simple.to_string()))
    }

    fn parse_hex_char(&self, pos: usize, len: usize) -> Parsed<(usize, String)> {
        let hex: String = self.src[pos.min(self.src.len())..(pos + len).min(self.src.len())]
            .iter()
            .collect();
        if hex.chars().count() != len || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
            return Err(TomlError);
        }
        let code = u32::from_str_radix(&hex, 16).map_err(|_| TomlError)?;
        let c = char::from_u32(code).ok_or(TomlError)?;
        Ok((pos + len, c.to_string()))
    }

    fn parse_literal_str(&self, pos: usize) -> Parsed<(usize, String)> {
        let start = pos + 1;
        let end = self.skip_until(start, "'", illegal_line, true)?;
        Ok((end + 1, self.src[start..end].iter().collect()))
    }

    fn parse_multiline_str(&self, pos: usize, literal: bool) -> Parsed<(usize, String)> {
        let mut pos = pos + 3;
        if self.starts_with(pos, "\n") {
            pos += 1;
        }
        let (delim, (mut pos, mut result)) = if literal {
            let end = self.skip_until(pos, "'''", illegal_multiline, true)?;
            (
                '\'',
                (end + 3, self.src[pos..end].iter().collect::<String>()),
            )
        } else {
            ('"', self.parse_basic_str(pos, true)?)
        };

        // Up to two more delimiters belong to the text
        for _ in 0..2 {
            if self.at(pos) != Some(delim) {
                break;
            }
            pos += 1;
            result.push(delim);
        }
        Ok((pos, result))
    }

    fn parse_basic_str(&self, mut pos: usize, multiline: bool) -> Parsed<(usize, String)> {
        let illegal = if multiline {
            illegal_multiline
        } else {
            illegal_line
        };
        let mut result = String::new();
        let mut start = pos;
        loop {
            let c = self.at(pos).ok_or(TomlError)?;

            // The closing quote; a lone quote inside a multi-line string is text
            if c == '"' {
                if !multiline {
                    result.extend(&self.src[start..pos]);
                    return Ok((pos + 1, result));
                }
                if self.starts_with(pos, "\"\"\"") {
                    result.extend(&self.src[start..pos]);
                    return Ok((pos + 3, result));
                }
                pos += 1;
                continue;
            }

            // An escape, or a plain character
            if c == '\\' {
                result.extend(&self.src[start..pos]);
                let (next, text) = self.parse_escape(pos, multiline)?;
                result.push_str(&text);
                pos = next;
                start = pos;
                continue;
            }
            if illegal(c) {
                return Err(TomlError);
            }
            pos += 1;
        }
    }

    fn parse_value(&self, pos: usize, depth: usize) -> Parsed<(usize, Item)> {
        if depth > MAX_NESTING {
            return Err(TomlError);
        }
        let c = self.at(pos);

        // Strings, booleans, arrays, inline tables
        match c {
            Some('"') if self.starts_with(pos, "\"\"\"") => {
                return self
                    .parse_multiline_str(pos, false)
                    .map(|(p, s)| (p, Item::Str(s)));
            }
            Some('"') => {
                return self
                    .parse_basic_str(pos + 1, false)
                    .map(|(p, s)| (p, Item::Str(s)));
            }
            Some('\'') if self.starts_with(pos, "'''") => {
                return self
                    .parse_multiline_str(pos, true)
                    .map(|(p, s)| (p, Item::Str(s)));
            }
            Some('\'') => return self.parse_literal_str(pos).map(|(p, s)| (p, Item::Str(s))),
            Some('t') if self.starts_with(pos, "true") => return Ok((pos + 4, Item::Bool(true))),
            Some('f') if self.starts_with(pos, "false") => return Ok((pos + 5, Item::Bool(false))),
            Some('[') => return self.parse_array(pos, depth),
            Some('{') => return self.parse_inline_table(pos, depth),
            _ => {}
        }

        // Dates and times, then numbers
        if let Some(end) = datetime_at(self.src, pos)? {
            return Ok((end, Item::Datetime(self.src[pos..end].iter().collect())));
        }
        if let Some(end) = time_at(self.src, pos) {
            return Ok((end, Item::Datetime(self.src[pos..end].iter().collect())));
        }
        if let Some((end, value)) = number_at(self.src, pos)? {
            return Ok((end, value));
        }

        // Special floats
        for word in ["inf", "nan", "-inf", "+inf", "-nan", "+nan"] {
            if self.starts_with(pos, word) {
                let value = if word.ends_with("inf") {
                    if word.starts_with('-') {
                        f64::NEG_INFINITY
                    } else {
                        f64::INFINITY
                    }
                } else {
                    f64::NAN
                };
                return Ok((pos + word.len(), Item::Float(value)));
            }
        }
        Err(TomlError)
    }
}
