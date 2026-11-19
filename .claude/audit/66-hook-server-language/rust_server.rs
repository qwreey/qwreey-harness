// Rust http hook server: std + serde_json, keep-alive, thread per connection; same two routes as the Python one.
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};

fn has_history(c: &str) -> bool {
    let b = c.as_bytes();
    for i in 0..b.len() {
        let word_start = i == 0 || !(b[i - 1].is_ascii_alphanumeric() || b[i - 1] == b'_');
        if !word_start { continue; }
        if (b[i] == b'H' || b[i] == b'D') && i + 2 < b.len() && b[i + 1] == b'-' && b[i + 2].is_ascii_digit() { return true; }
        if i + 10 <= b.len() && b[i] == b'2' && b[i + 1] == b'0' && b[i + 4] == b'-' && b[i + 7] == b'-'
            && [2, 3, 5, 6, 8, 9].iter().all(|&k| b[i + k].is_ascii_digit()) { return true; }
    }
    false
}

fn check(path: &str) -> usize {
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let mut hits = 0;
    for line in text.lines() {
        if let Some(i) = line.find("--") {
            let c = &line[i + 2..];
            hits += has_history(c) as usize + (!c.is_ascii()) as usize + c.split(|ch: char| !ch.is_alphanumeric()).any(|w| w == "TODO") as usize;
        }
    }
    hits
}

fn serve(stream: TcpStream) {
    let _ = stream.set_nodelay(true);
    let mut w = stream.try_clone().unwrap();
    let mut r = BufReader::new(stream);
    loop {
        let mut line = String::new();
        if r.read_line(&mut line).unwrap_or(0) == 0 { return; }
        let path = line.split_whitespace().nth(1).unwrap_or("").to_string();
        let mut len = 0usize;
        loop {
            let mut h = String::new();
            if r.read_line(&mut h).unwrap_or(0) == 0 { return; }
            if h == "\r\n" { break; }
            if let Some(v) = h.to_ascii_lowercase().strip_prefix("content-length:") { len = v.trim().parse().unwrap_or(0); }
        }
        let mut body = vec![0u8; len];
        if r.read_exact(&mut body).is_err() { return; }
        let data: serde_json::Value = serde_json::from_slice(&body).unwrap_or_default();
        let out = if path == "/edit" {
            let n = check(data["tool_input"]["file_path"].as_str().unwrap_or(""));
            serde_json::json!({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": format!("hits {n}")}}).to_string()
        } else { String::new() };
        let resp = format!("HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n{}", out.len(), out);
        let _ = w.write_all(resp.as_bytes());
    }
}

fn main() {
    let port = std::env::args().nth(1).unwrap_or("47502".into());
    for s in TcpListener::bind(("127.0.0.1", port.parse::<u16>().unwrap())).unwrap().incoming().flatten() {
        std::thread::spawn(move || serve(s));
    }
}
