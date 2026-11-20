//! 줄 검사가 쓰는 정규식마다의 시간: 파일의 주석 본문 전부에 패턴 하나씩 search 를 돌린 합(마이크로초, 중앙값).
//!
//! 실행: `cargo run --release -p qwreey-conventions --example regex_hot -- <파일> [반복 수]`
//! python 쪽 같은 측정은 crates/qwreey-conventions/examples/regex_hot.py 다(같은 패턴, 같은 본문).

use std::time::Instant;

use harness_hook::py::path::splitext;
use qwreey_conventions::check::config::Cfg;
use qwreey_conventions::lex::{self, comment_body};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(path) = args.first() else {
        eprintln!("usage: regex_hot <file> [runs]");
        std::process::exit(2);
    };
    let runs: usize = args.get(1).and_then(|n| n.parse().ok()).unwrap_or(11);
    let text = std::fs::read_to_string(path).expect("readable UTF-8 file");
    let fam = lex::family(&splitext(path).1.to_lowercase()).expect("a code file");
    let rows = lex::lex(&text, fam, false);
    let segs: Vec<String> = rows
        .iter()
        .filter(|r| !r.c.is_empty())
        .map(|r| {
            r.c.iter()
                .map(|c| comment_body(c))
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect();
    let pats = Cfg::defaults().patterns().expect("builtin patterns");

    // Each pattern over every comment body
    println!(
        "{path}: {} comment lines, median of {runs} runs (us per pass)",
        segs.len()
    );
    let named = pats.history.iter().map(|(k, r)| (k.clone(), r)).chain(
        pats.public
            .iter()
            .enumerate()
            .map(|(i, r)| (format!("public[{i}]"), r)),
    );
    for (name, rx) in named {
        let mut xs: Vec<u128> = (0..runs)
            .map(|_| {
                let at = Instant::now();
                let hits = segs.iter().filter(|s| rx.is_match(s)).count();
                std::hint::black_box(hits);
                at.elapsed().as_micros()
            })
            .collect();
        xs.sort_unstable();
        println!("  {name:12} {}", xs[xs.len() / 2]);
    }
}
