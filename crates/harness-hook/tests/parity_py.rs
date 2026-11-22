//! python 표준 라이브러리 흉내(공백, 줄, float, `json.dumps`, `~`, pathlib)와 훅 출력 태그를 python 과 바이트로 대조한다.

mod common;

use common::{case, pairs, python};
use harness_hook::nonce::Nonce;
use harness_hook::py::json::{EnsureAscii, to_string};
use harness_hook::py::num::{float_repr, floor_div, integral_float_text};
use harness_hook::py::path::{expanduser, pathlib_str};
use harness_hook::py::text::{is_space, splitlines};
use harness_hook::tag::{self, Level};
use harness_hook::{Env, HookOutput};
use serde_json::json;

const TRICKY: &str =
    "q\"b\\s/n\nr\rt\tb\u{8}f\u{c}z\u{0}u\u{1f}d\u{7f}e\u{e9}k\u{d55c}x\u{1f600}l\u{2028}m\u{ffff}";

/// 공백 처리, 줄 나누기, float 표기, `~` 풀기, pathlib 글이 python 판과 같다.
#[test]
fn text_and_numbers_match_python() {
    let no_env = Vec::new();

    // All whitespace chars, line splitting
    let spaces: Vec<u32> = (0..=0x10ffff_u32)
        .filter_map(char::from_u32)
        .filter(|c| is_space(*c))
        .map(u32::from)
        .collect();
    let texts = [
        "a\r\nb\rc\nd\u{b}e\u{c}f\u{1c}g\u{1d}h\u{1e}i\u{85}j\u{2028}k\u{2029}l",
        "",
        "\n",
        "x\r",
        "\r\n\r\n",
        "\u{d55c}\u{3000}x\n\u{1f}",
    ];

    // Float spellings, integral floats, 30 second slots
    let floats = [
        1.5,
        100.0,
        1e-5,
        0.0001,
        0.001,
        1e16,
        1e22,
        1.7976931348623157e308,
        5e-324,
        0.1 + 0.2,
        1234567890123456.7,
        9999999999999998.0,
        123456789012345680.0,
        -0.0,
        -2.5e-7,
        1e15 + 0.3,
    ];
    let integral = [
        0.0,
        -0.0,
        1.0,
        -7.0,
        9007199254740992.0,
        2f64.powi(63),
        -(2f64.powi(70)),
        1e20,
        1e300,
        f64::MAX,
    ];
    let nows = [
        0.0,
        29.999999999999996,
        30.0,
        59.99999999999999,
        89.99999999999999,
        1.7e9 + 29.999999,
        -1.0,
    ];
    let bits = |xs: &[f64]| xs.iter().map(|x| x.to_bits()).collect::<Vec<_>>();
    let random = random_floats(5000);

    // Tilde expansion and pathlib strings
    let tilde = ["~", "~/", "~/a", "~nobody-here/a", "a~", "~//x"];
    let homes = ["/home/u/", "", "/"];
    let paths = [
        "",
        ".",
        "./",
        "a//b",
        "/a/./b/",
        "//a",
        "///a",
        "a/../b",
        "./.claude/x",
        "~/x",
    ];

    let mut cases = vec![case("isspace", &no_env, json!({}))];
    cases.extend(
        texts
            .iter()
            .map(|t| case("splitlines", &no_env, json!({"text": t}))),
    );
    cases.push(case("float_repr", &no_env, json!({"bits": bits(&floats)})));
    cases.push(case("float_repr", &no_env, json!({"bits": bits(&random)})));
    cases.push(case("int_text", &no_env, json!({"bits": bits(&integral)})));
    cases.push(case("floor_div", &no_env, json!({"bits": bits(&nows)})));
    cases.extend(homes.iter().map(|h| {
        case(
            "expanduser",
            &pairs(&[("HOME", h)]),
            json!({"paths": tilde}),
        )
    }));
    cases.push(case("pathlib", &no_env, json!({"paths": paths})));
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust side in the same order
    let mut want = vec![json!(spaces)];
    want.extend(texts.iter().map(|t| json!(splitlines(t))));
    want.push(json!(
        floats.iter().map(|x| float_repr(*x)).collect::<Vec<_>>()
    ));
    want.push(json!(
        random.iter().map(|x| float_repr(*x)).collect::<Vec<_>>()
    ));
    want.push(json!(
        integral
            .iter()
            .map(|x| integral_float_text(*x))
            .collect::<Vec<_>>()
    ));
    want.push(json!(
        nows.iter()
            .map(|x| floor_div(*x, 30.0) as i64)
            .collect::<Vec<_>>()
    ));
    for home in homes {
        let env = Env::from_pairs([("HOME", home)]);
        want.push(json!(
            tilde
                .iter()
                .map(|p| expanduser(p, &env))
                .collect::<Vec<_>>()
        ));
    }
    want.push(json!(
        paths.iter().map(|p| pathlib_str(p)).collect::<Vec<_>>()
    ));

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}

// Finite floats from a fixed splitmix64 seed (all exponents), near powers of 2, short decimals
fn random_floats(count: usize) -> Vec<f64> {
    let mut state = 0x9e37_79b9_7f4a_7c15_u64;
    let mut next = move || {
        state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = state;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    };

    let mut out: Vec<f64> = (0..count)
        .map(|_| f64::from_bits(next()))
        .filter(|x| x.is_finite())
        .collect();
    for k in -60..70 {
        let p = 2f64.powi(k);
        out.extend([
            p,
            f64::from_bits(p.to_bits() + 1),
            f64::from_bits(p.to_bits() - 1),
        ]);
    }
    out.extend((0..500).map(|i| (next() % 1_000_000) as f64 / 10f64.powi(i % 12)));
    out
}

/// `json.dumps`, 태그, 훅 출력 JSON 이 python 판과 같다.
#[test]
fn json_and_tags_match_python() {
    let tmp = common::TempDir::new("tags");
    let salt = tmp.write("salt", "00".repeat(32));
    let env = pairs(&[("QWREEY_HARNESS_SALT_FILE", &salt.to_string_lossy())]);

    // json.dumps: tricky strings, nesting, numbers
    let values = [
        json!(TRICKY),
        json!({"z": [1, -2, 2.5, 1e-7, 1e16, true, false, null], "a": {"k": TRICKY}, TRICKY: ""}),
        json!([]),
        json!({}),
    ];
    let mut cases = Vec::new();
    for value in &values {
        for ascii in [true, false] {
            cases.push(case("dumps", &env, json!({"value": value, "ascii": ascii})));
        }
    }

    // Tags and hook output JSON
    let tags = [
        (
            "heavy-proc-guard",
            "action",
            "Re-run with `choom -n 1000 -- <command>`.",
            Some("abc"),
        ),
        (
            "self-match-guard",
            "warn",
            TRICKY,
            Some("\u{c138}\u{c158}-\u{1f600}"),
        ),
        ("resource-guard", "info", "line1\nline2", None),
    ];
    for (name, level, body, sid) in tags {
        cases.push(case(
            "tag",
            &env,
            json!({"name": name, "level": level, "body": body, "sid": sid, "event": "PostToolUse"}),
        ));
    }
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust side in the same order
    let mut want = Vec::new();
    for value in &values {
        want.push(json!(to_string(value, EnsureAscii::Yes).unwrap()));
        want.push(json!(to_string(value, EnsureAscii::No).unwrap()));
    }

    let rust_env = Env::from_pairs(env.clone());
    for (name, level, body, sid) in tags {
        let level = match level {
            "action" => Level::Action,
            "warn" => Level::Warn,
            _ => Level::Info,
        };
        let nonce = Nonce::for_session(&rust_env, sid).unwrap();
        let rendered = tag::harness_hook(name, level, nonce.as_ref(), body);
        want.push(json!([
            rendered,
            HookOutput::deny(rendered.clone()).render(EnsureAscii::Yes),
            HookOutput::context("PostToolUse", rendered.clone()).render(EnsureAscii::No),
            tag::plugin_block(name, nonce.as_ref(), body),
        ]));
    }

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}
