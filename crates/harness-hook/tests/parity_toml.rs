//! py::toml 을 python `tomllib` 과 대조한다: 손으로 고른 글과, 작은 조각 모음에서 만든 글 수천 개를 읽어 본다.
//! 견주는 것은 받는가 거절하는가와 읽은 값의 꼴(키 순서, 글, 정수, 실수 repr, 날짜는 날짜라는 것만)이다.

mod common;

use common::{case, python};
use harness_hook::py::num::float_repr;
use harness_hook::py::toml::{Item, Table, loads};
use harness_hook::testkit::corpus;
use serde_json::{Value, json};

const TEXTS: &[&str] = &[
    "[[packs]]\nname = \"luau-kb\"\npath = \"/p/luau-kb\"\n\n[[packs]]\nname = \"web-security\"\n",
    "format = 1\n[[contexts.docs]]\nprovider = [\"md\"]\n  [[contexts.docs.targets]]\n  options = { exclude = [\"w\"] }\n",
    "a.b.c = 1\na.b.d = 2\n[a.e]\n",
    "a.b = 1\n[a]\n",
    "[a]\nb.c = 1\n[a.b]\n",
    "[a.b]\n[a]\nc = 1\n",
    "[[a]]\n[a.b]\nc = 1\n[[a]]\n[a.b]\n",
    "a = []\n[[a]]\n",
    "a = []\n[a.b]\n",
    "s = '''\nx'''''\nt = \"\"\"a\\\n   b\"\"\"\"\"\n",
    "s = \"\\u00e9\\U0001F600\"\n",
    "s = \"\\ud800\"\n",
    "x = 0x_1\n",
    "x = +0b1\n",
    "x = 1__0\n",
    "x = 1_000.5e+1_0\n",
    "x = 01\n",
    "x = 1.\n",
    "x = .5\n",
    "x = 1e\n",
    "x = 0xffffffffffffffffffffffffffffffffffff\n",
    "x = -170141183460469231731687303715884105729\n",
    "d = 1979-05-27 07:32:00-08:00\nt = 00:00:00.123456789\n",
    "d = 1979-05-27T25:00:00\n",
    "d = 2023-02-29\n",
    "d = 2024-02-29\n",
    "d = 1979-05-27x\n",
    "d = 1979-05-27 # ok\n",
    "d = 1979-05-27T07:32:00+24:00\n",
    "k = { a = { b = 1 }, c = [1, {d = 2}] }\n",
    "k = { a = 1, a = 2 }\n",
    "k = { a.b = 1, a.c = 2 }\n",
    "k = { a = {b = 1}, a.c = 2 }\n",
    "k = {}\n[k.x]\n",
    "\"q\".'r'.s = 1\n",
    "= 1\n",
    "a = 1 # \u{7f}\n",
    "a = \"\t\"\n",
    "a = \"\r\"\n",
    "a = 1\r\nb = 2\r\n",
    "a = 1\rb = 2\n",
    "\u{feff}a = 1\n",
    "a = [1, 2,\n # c\n 3,]\n",
    "a = [,]\n",
    "a = inf\nb = -nan\nc = +inf\n",
    "a = true\nb = falsey\n",
    "",
    "# only a comment",
    "[ a . b ]\n",
    "[[ a ]]\n",
    "[a]]\n",
];

const PIECES: &[&str] = &[
    "a",
    "b",
    ".",
    " ",
    "=",
    "1",
    "\"x\"",
    "'y'",
    "[",
    "]",
    "[[",
    "]]",
    "{",
    "}",
    ",",
    "\n",
    "#c",
    "0x",
    "e",
    "_",
    "-",
    ":",
    "1979-05-27",
    "T",
    "07:32:00",
    "true",
    "\"\"\"",
    "'''",
    "\\",
    "inf",
    "+",
    "a = ",
    "\n[t]\n",
    "\n[[t]]\n",
];

/// 손으로 고른 글과 만든 글에서 받는가와 읽은 값이 python 과 같다.
#[test]
fn toml_parity() {
    // Hand-picked texts, generated texts, and generated values after a key
    let mut texts: Vec<String> = TEXTS.iter().map(|t| (*t).to_owned()).collect();
    let made = corpus(PIECES, 6000);
    texts.extend(made.iter().cloned());
    texts.extend(made.iter().map(|t| format!("k = {t}")));
    texts.extend(made.chunks(3).map(|c| c.join("\n")));

    let Some(want) = python(&[case("toml", &[], json!({ "texts": texts }))]) else {
        return;
    };
    let want = want[0].as_array().expect("a list of results");
    let mut accepted = 0;
    for (text, want) in texts.iter().zip(want) {
        let got = loads(text).map_or(Value::Null, |t| table_shape(&t));
        accepted += usize::from(!got.is_null());
        assert_eq!(&got, want, "{text:?}");
    }

    // 받은 글이 너무 적으면 대조가 값 읽기를 보지 못한 것이다
    assert!(accepted > 300, "only {accepted} accepted texts");
}

fn table_shape(t: &Table) -> Value {
    json!([
        "t",
        t.iter()
            .map(|(k, v)| json!([k, shape(v)]))
            .collect::<Vec<_>>()
    ])
}

fn shape(v: &Item) -> Value {
    match v {
        Item::Bool(b) => json!(["b", b]),
        Item::Int(i) => json!(["i", i.to_string()]),
        Item::BigInt(_) => json!(["i", "big"]),
        Item::Float(f) => json!(["f", float_repr(*f)]),
        Item::Str(s) => json!(["s", s]),
        Item::Datetime(_) => json!(["dt"]),
        Item::Array(items) => json!(["a", items.iter().map(shape).collect::<Vec<_>>()]),
        Item::Table(t) => table_shape(t),
    }
}
