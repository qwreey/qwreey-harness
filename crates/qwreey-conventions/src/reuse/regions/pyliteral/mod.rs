//! python 정본 영역의 str 상수들(python `ast.parse` 뒤 `ast.walk` 의 str `Constant`).
//!
//! why not 온전한 python 파서: 정본 영역은 거의 늘 대입 한 줄이나 괄호 안에 이어 붙인 리터럴이다. 여기서는 식의 부분 집합
//! (이름, 수, 문자열, 괄호, 목록, dict, 호출, 속성, 첨자, 단항·이항·비교·논리 연산, 조건식)과 대입, 주석 대입 문장만 읽는다.
//! 문자열은 python 과 같이 옆에 붙은 것을 하나로 합치고, f-string 은 글 조각과 칸 안의 식, 형식 지정 조각을 따로 센다.
//! bytes 는 str 상수가 아니다. `\N{...}` 는 자주 쓰는 이름 표(`names.rs`)만 읽는다.
//! 받는 꼴이 아니거나 python 이 SyntaxError 를 낼 수 있는 글은 [`Unsure`]: 부르는 쪽은 그 영역만 판정하지 않는다
//! (python 의 SyntaxError 글은 옮기지 않았다).

mod lex;
mod names;
mod parse;

use harness_hook::py::text::{is_space, strip};

use lex::Lexer;
use parse::Parser;

/// 이 판이 python 의 판정을 옮기지 못한 글.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Unsure;

type R<T> = std::result::Result<T, Unsure>;

// python 의 예약어
const KEYWORDS: &[&str] = &[
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield",
];

/// 정본 영역 줄들의 str 상수 값들(차례는 python 과 다를 수 있다: 부르는 쪽은 수와, 하나일 때 그 값만 본다).
pub fn constants(lines: &[&str]) -> R<Vec<String>> {
    // Dedent by the smallest indent, counted in characters as python slices
    let indent = lines
        .iter()
        .filter(|x| !strip(x).is_empty())
        .map(|x| x.chars().take_while(|&c| is_space(c)).count())
        .min()
        .unwrap_or(0);
    let src: Vec<String> = lines
        .iter()
        .map(|x| x.chars().skip(indent).collect())
        .collect();
    let src: Vec<char> = src.join("\n").chars().collect();

    // Tokens, then statements
    let mut lexer = Lexer::new(&src);
    let toks = lexer.module()?;
    let mut p = Parser::new(&toks);
    p.module()?;
    Ok(p.into_constants())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(code: &str) -> R<Vec<String>> {
        let lines: Vec<&str> = code.split('\n').collect();
        let mut found = constants(&lines)?;
        found.sort();
        Ok(found)
    }

    /// 대입, 괄호 안 이어 붙이기, escape 를 python ast 처럼 읽는다.
    #[test]
    fn reads_the_literal_subset() {
        // Implicit concatenation inside parentheses is one constant
        assert_eq!(
            constants(&[
                "    OMIT = (",
                "        \"a\\tb\"  # note",
                "        'c'",
                "    )"
            ])
            .unwrap(),
            ["a\tbc"]
        );

        // Raw, unicode-prefixed and triple-quoted strings
        assert_eq!(constants(&[r#"X = r"\d\"""#]).unwrap(), [r#"\d\""#]);
        assert_eq!(constants(&["X: str = u'''a", "b'''"]).unwrap(), ["a\nb"]);
        assert_eq!(constants(&["A = 'x'", "B = 'y'"]).unwrap().len(), 2);

        // Escapes python leaves alone keep the backslash
        assert_eq!(
            constants(&[r#"X = "\q\101\u00e9""#]).unwrap(),
            ["\\qA\u{e9}"]
        );
    }

    /// python 3.14 `ast.walk` 의 str 상수와 같다. 기대값은 python 으로 뽑았다(SyntaxError 는 None).
    #[test]
    fn matches_python_ast() {
        let cases: &[(&str, Option<&[&str]>)] = &[
            // Concatenation, operators and calls each have their own count
            ("X = \"a\" + \"b\"", Some(&["a", "b"])),
            ("X = str(\"a\")", Some(&["a"])),
            ("X = \"a\" \\\n    \"b\"", Some(&["ab"])),
            ("X = \"a\" if c else \"b\"", Some(&["a", "b"])),
            ("X = {\"a\": 1, **d}", Some(&["a"])),
            ("x: \"int\" = \"a\"", Some(&["a", "int"])),
            ("\"doc\"\nX = 1", Some(&["doc"])),
            ("X = f(a, k=\"v\", *r, **kw)[1:2].y", Some(&["v"])),
            ("X = not a in b and c is not d or -e ** 2", Some(&[])),
            ("X = 0x1F + 1_000 + 1.5e-3j + .5", Some(&[])),
            ("X = ...; Y = 'z'", Some(&["z"])),
            ("a, *b = \"xy\"", Some(&["xy"])),
            // Bytes are not str constants
            ("X = b\"a\"", Some(&[])),
            ("X = rb'\\d'", Some(&[])),
            // Named escapes from the table, any case
            ("X = \"\\N{BULLET}\"", Some(&["\u{2022}"])),
            (
                "X = \"\\N{bullet} \\N{EM DASH}\"",
                Some(&["\u{2022} \u{2014}"]),
            ),
            // f-strings: text between fields, field constants, format specs
            ("X = f\"\"", Some(&[])),
            ("X = \"\" f\"\"", Some(&[])),
            ("X = f\"a{1}\"", Some(&["a"])),
            ("X = f\"{x}\"", Some(&[])),
            ("X = f\"{x:>10}\"", Some(&[">10"])),
            ("X = f\"{x:}\"", Some(&[])),
            ("X = f\"{x=}\"", Some(&["x="])),
            ("X = f\"a{x=}b\"", Some(&["ax=", "b"])),
            ("X = f\"{x!r:{w}.{p}}\"", Some(&["."])),
            ("X = \"a\" f\"b{x}\" \"c\" f\"d\"", Some(&["ab", "cd"])),
            ("X = f\"{{a}}\"", Some(&["{a}"])),
            ("X = f\"{ x = }\"", Some(&[" x = "])),
            ("X = f\"{'q'}\"", Some(&["q"])),
            ("X = f\"{x:{'a'}}\"", Some(&["a"])),
            ("X = f\"{a:%Y}\"", Some(&["%Y"])),
            ("X = f\"{a:{b}c}\"", Some(&["c"])),
            ("X = f\"a\" \"\" f\"\"", Some(&["a"])),
            ("X = rf'{x}\\n'", Some(&["\\n"])),
            ("X = f\"{x:=^10}\"", Some(&["=^10"])),
            ("X = f\"{x = !r:>3}\"", Some(&[">3", "x = "])),
            ("X = f\"{d['k']}\"", Some(&["k"])),
            ("X = f\"{a == b}\"", Some(&[])),
            // SyntaxError in python
            ("X = \"a\" b\"c\"", None),
            ("X = f\"{x!r=}\"", None),
            ("X = 'a", None),
            ("X = ('a'", None),
            ("class = 'a'", None),
            ("  X = 'a'\nY = 'b'", None),
            ("1 = 'a'", None),
            ("f() = 'a'", None),
            ("X = f(k=1, 'a')", None),
            ("X = f(k=1, k='a')", None),
            ("X = *a", Some(&[])),
            ("X = (*a)", None),
            ("X = f(**k, *y)", None),
            ("X = {*a: 1}", None),
            ("X = 012", None),
            ("X = f\"}\"", None),
            ("X = 'a' 'b", None),
        ];
        for &(code, want) in cases {
            let got = run(code);
            match want {
                // Where python reads it, the same constants (sorted, as only count and value matter)
                Some(want) => {
                    let mut want: Vec<String> = want.iter().map(|s| (*s).to_owned()).collect();
                    want.sort();
                    assert_eq!(got, Ok(want), "{code}");
                }
                // Where python raises, never a count of our own
                None => assert_eq!(got, Err(Unsure), "{code}"),
            }
        }
    }

    /// 읽지 않는 꼴(내포, lambda, 표에 없는 이름, t-string)은 Unsure 다: 틀린 수를 대지 않는다.
    #[test]
    fn leaves_other_code_unsure() {
        for code in [
            "X = [f\"{i}\" for i in y]",
            "X = lambda: 'a'",
            "X = \"\\N{SNOWMAN}\"",
            "X = t\"a\"",
            "import os",
            "X += 'a'",
        ] {
            assert_eq!(run(code), Err(Unsure), "{code}");
        }
    }
}
