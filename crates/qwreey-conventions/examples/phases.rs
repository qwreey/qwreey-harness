//! conventions-check 의 단계별 시간: 큰 파일 하나에서 렉서, 줄 검사, 언어, layout 이 각각 얼마를 쓰는가.
//!
//! 실행: `cargo run --release -p qwreey-conventions --example phases -- <파일> [반복 수]`
//! 파일 전체를 Write(새 파일)로 넣은 것처럼 모든 줄을 추가한 줄로 보고, 같은 파일을 반복해 중앙값(마이크로초)을 찍는다.
//! 훅 한 번의 CPU 가운데 정규식(python re 호환 엔진)이 얼마인지 보려고 둔다.

use std::time::Instant;

use harness_hook::py::path::splitext;
use qwreey_conventions::check::config::Cfg;
use qwreey_conventions::check::lang::{self, SiblingCache};
use qwreey_conventions::check::layout::{self, Lang, Limits};
use qwreey_conventions::check::{chars, history};
use qwreey_conventions::edit::Added;
use qwreey_conventions::lex;

fn median(mut xs: Vec<u128>) -> u128 {
    xs.sort_unstable();
    xs[xs.len() / 2]
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(path) = args.first() else {
        eprintln!("usage: phases <file> [runs]");
        std::process::exit(2);
    };
    let runs: usize = args.get(1).and_then(|n| n.parse().ok()).unwrap_or(20);
    let text = std::fs::read_to_string(path).expect("readable UTF-8 file");
    let ext = splitext(path).1.to_lowercase();
    let fam = lex::family(&ext).expect("a code file");
    let lang = Lang::of_ext(&ext);
    let cfg = Cfg::defaults();
    let pats = cfg.patterns().expect("builtin patterns");
    let n = text.split('\n').count();
    let all: Added = (0..n).collect();
    let lines: Vec<&str> = text.split('\n').collect();

    // Time each phase
    let mut t: Vec<(&str, Vec<u128>)> = [
        "lex",
        "check_lines",
        "step_labels",
        "expected_script",
        "invisible",
        "layout",
    ]
    .into_iter()
    .map(|name| (name, Vec::new()))
    .collect();
    for _ in 0..runs {
        let at = Instant::now();
        let rows = lex::lex(&text, fam, lang.is_some());
        t[0].1.push(at.elapsed().as_micros());

        let at = Instant::now();
        let _ = history::check_lines(&rows, &all, &pats, &cfg);
        t[1].1.push(at.elapsed().as_micros());

        let at = Instant::now();
        let labels = lang::step_labels(&rows, &lines, &cfg);
        t[2].1.push(at.elapsed().as_micros());

        let at = Instant::now();
        let _ = lang::expected_script(
            &rows,
            &Added::new(),
            &cfg,
            path,
            &ext,
            &labels,
            &mut SiblingCache::default(),
        );
        t[3].1.push(at.elapsed().as_micros());

        let at = Instant::now();
        let _ = chars::invisible_lines(&text, &all);
        t[4].1.push(at.elapsed().as_micros());

        let at = Instant::now();
        if let Some(lang) = lang {
            let _ = layout::edit_findings(&text, &rows, &all, lang, &Limits::from_user(None), &[]);
        }
        t[5].1.push(at.elapsed().as_micros());
    }

    println!("{path}: {n} lines, median of {runs} runs (us)");
    for (name, xs) in t {
        println!("  {name:16} {}", median(xs));
    }
}
