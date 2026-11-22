//! 모델 계열과 사용량 값(python `family`, `price_row`, `usage_usd`, `scan`, `tail_model`).
//!
//! 가격은 공식 목록가(USD / MTok, https://platform.claude.com/docs/en/about-claude/pricing). python 표의 int 와 float 를 그대로
//! 두었다: 토큰 수(int)와 int 가격의 곱은 정확한 int 이고, float 가 끼는 자리에서 float 가 된다. 그 꼴이 합의 반올림을 정한다.

use harness_hook::py::fs::{FsError, getsize, os_path};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::num::parse_int;
use harness_hook::py::repr::truthy_str;
use harness_hook::py::value::{Dict, Value};

use crate::num::Num;
use crate::pyval::{iterate, py_eq};
use crate::stop::{Result, Stop};

/// 비싼 순 계열(python `ORDER`).
pub const ORDER: &[&str] = &["fable", "opus", "sonnet", "haiku"];
/// "opus 이상"(python `BIG`).
pub const BIG: &[&str] = &["fable", "opus"];

const I: fn(i128) -> Num = Num::Int;
const F: fn(f64) -> Num = Num::Float;

/// 가격 한 줄: 모델 id 에 이 가운데 하나가 들었으면 맞는다(위에서부터 첫 일치).
struct Price {
    names: &'static [&'static str],
    /// 입력, 5분 캐시 쓰기, 1시간 캐시 쓰기, 캐시 읽기, 출력.
    row: fn() -> [Num; 5],
}

const PRICES: &[Price] = &[
    Price {
        names: &["fable-5-2", "mythos-5-2"],
        row: || [I(8), I(10), I(16), F(0.20), I(40)],
    },
    Price {
        names: &["fable-5-1", "mythos-5-1"],
        row: || [I(10), F(12.5), I(20), F(0.25), I(50)],
    },
    Price {
        names: &["fable-5", "mythos"],
        row: || [I(10), F(12.5), I(20), F(1.0), I(50)],
    },
    Price {
        names: &["opus-5-5"],
        row: || [I(4), I(5), I(8), F(0.20), I(20)],
    },
    Price {
        names: &["opus-4-1", "opus-4-2025"],
        row: || [I(15), F(18.75), I(30), F(1.5), I(75)],
    },
    Price {
        names: &["opus"],
        row: || [I(5), F(6.25), I(10), F(0.5), I(25)],
    },
    Price {
        names: &["sonnet-5-5"],
        row: || [I(2), F(2.5), I(4), F(0.10), I(10)],
    },
    Price {
        names: &["sonnet-5"],
        row: || [I(2), F(2.5), I(4), F(0.20), I(10)],
    },
    Price {
        names: &["sonnet"],
        row: || [I(3), F(3.75), I(6), F(0.30), I(15)],
    },
    Price {
        names: &["haiku-5-5"],
        row: || [F(0.10), F(0.125), F(0.20), F(0.01), F(0.50)],
    },
    Price {
        names: &["haiku"],
        row: || [I(1), F(1.25), I(2), F(0.10), I(5)],
    },
];
/// haiku 5.5 의 프롬프트가 10만 토큰을 넘을 때.
const HAIKU55_LONG: [f64; 5] = [0.50, 0.625, 1.0, 0.05, 2.50];
const LONG_PROMPT: i128 = 100_000;
/// fast mode 는 기본의 2배, inference_geo=us 는 1.1배.
const FAST_MULT: f64 = 2.0;
const GEO_US_MULT: f64 = 1.1;

/// python `family(model)`: 계열 이름, 모르면 `?`.
pub fn family(model: Option<&Value>) -> &'static str {
    let m = truthy_str(model).to_lowercase();
    ORDER
        .iter()
        .find(|f| m.contains(**f) || (**f == "fable" && m.contains("mythos")))
        .copied()
        .unwrap_or("?")
}

fn price_row(model: &str, prompt_tokens: Num) -> Option<[Num; 5]> {
    let m = model.to_lowercase();
    let price = PRICES
        .iter()
        .find(|p| p.names.iter().any(|n| m.contains(n)))?;
    if price.names[0] == "haiku-5-5" && prompt_tokens.gt(Num::Int(LONG_PROMPT)) {
        return Some(HAIKU55_LONG.map(Num::Float));
    }
    Some((price.row)())
}

// python `u.get(key) or 0` 의 수
fn tokens(usage: &Dict, key: &str) -> Result<Num> {
    match usage.get(key).filter(|v| v.truthy()) {
        None => Ok(Num::Int(0)),
        Some(v) => Num::of(v).ok_or(Stop::Unported("usage tokens that are not numbers")),
    }
}

/// python `usage_usd(model, u)`: 한 API 응답의 사용량을 USD 목록가로. 모르는 모델은 0.0.
pub fn usage_usd(model: &str, usage: &Dict) -> Result<Num> {
    // Cache writes: 5 minute and 1 hour
    let empty = Dict::new();
    let cache = match usage.get("cache_creation").filter(|v| v.truthy()) {
        None => &empty,
        Some(Value::Dict(d)) => d,
        Some(_) => return Err(Stop::Raises("cache_creation.get on a non-dict")),
    };
    let w1 = tokens(cache, "ephemeral_1h_input_tokens")?;
    let w5 = match cache.get("ephemeral_5m_input_tokens") {
        None | Some(Value::Null) => tokens(usage, "cache_creation_input_tokens")?.minus(w1)?,
        Some(v) => Num::of(v).ok_or(Stop::Unported("usage tokens that are not numbers"))?,
    };
    let input = tokens(usage, "input_tokens")?;
    let read = tokens(usage, "cache_read_input_tokens")?;
    let output = tokens(usage, "output_tokens")?;

    // Price row by model and prompt size
    let prompt = input.plus(read)?.plus(w5)?.plus(w1)?;
    let Some([p_in, p_w5, p_w1, p_read, p_out]) = price_row(model, prompt) else {
        return Ok(Num::Float(0.0));
    };
    let cost = input
        .times(p_in)?
        .plus(w5.times(p_w5)?)?
        .plus(w1.times(p_w1)?)?
        .plus(read.times(p_read)?)?
        .plus(output.times(p_out)?)?;
    let mut usd = cost.f64() / 1e6;

    // Fast mode and US inference
    if usage.get("speed").and_then(Value::as_str) == Some("fast") {
        usd *= FAST_MULT;
    }
    if truthy_str(usage.get("inference_geo")).to_lowercase() == "us" {
        usd *= GEO_US_MULT;
    }
    Ok(Num::Float(usd))
}

/// 모델 하나의 쓴 값(python `{"usd": 0.0, "tok": 0}`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Spend {
    pub usd: Num,
    pub tok: Num,
}

impl Spend {
    fn new() -> Spend {
        Spend {
            usd: Num::Float(0.0),
            tok: Num::Int(0),
        }
    }
}

/// [`scan`] 의 결과.
pub struct Scanned {
    /// 모델별 쓴 값(처음 본 차례).
    pub by_model: Vec<(String, Spend)>,
    /// 다음에 읽을 자리(python 값 그대로: 읽지 못하면 받은 값).
    pub offset: Value,
    /// 최근 message.id 50 개.
    pub recent: Vec<Value>,
    pub last_model: Option<String>,
}

/// python `scan(path, offset, recent)`: 트랜스크립트를 `offset` 부터 완결된 줄까지 읽어 모델별 쓴 값을 낸다.
///
/// 같은 message.id 는 한 번만 센다(`recent` 로 호출 사이도). python 은 `"usage"` 가 든 줄 가운데 dict 가 아닌 JSON,
/// 글이 아닌 model, 수로 읽지 못하는 토큰 수에서 예외로 끝난다.
pub fn scan(path: &str, offset: &Value, recent: Option<&Value>) -> Result<Scanned> {
    let mut seen = match recent {
        None => Vec::new(),
        Some(v) => iterate(v)?,
    };
    let unread = || Scanned {
        by_model: Vec::new(),
        offset: offset.clone(),
        recent: tail(seen.clone()),
        last_model: None,
    };
    let Some(data) = read_from(path, offset)? else {
        return Ok(unread());
    };
    let start = seek_offset(offset)?;

    // Complete lines with a usage record
    let end = data.iter().rposition(|&b| b == b'\n').map_or(0, |i| i + 1);
    let mut by_model: Vec<(String, Spend)> = Vec::new();
    let mut last_model = None;
    for line in split_lines(&data[..end]) {
        if !contains(line, b"\"usage\"") {
            continue;
        }
        let Some(record) = decode_line(line) else {
            continue;
        };
        let Some((model, usage)) = usage_record(&record, &mut seen)? else {
            continue;
        };
        last_model = Some(model.clone());
        add_usage(&mut by_model, model, usage)?;
    }

    Ok(Scanned {
        by_model,
        offset: Value::Int(start + end as i128),
        recent: tail(seen),
        last_model,
    })
}

// python `e = out.setdefault(model, ...)`, `e["usd"] += usage_usd(...)`, `e["tok"] += sum(...)`
fn add_usage(by_model: &mut Vec<(String, Spend)>, model: String, usage: &Dict) -> Result<()> {
    let at = match by_model.iter().position(|(m, _)| *m == model) {
        Some(at) => at,
        None => {
            by_model.push((model.clone(), Spend::new()));
            by_model.len() - 1
        }
    };
    let usd = usage_usd(&model, usage)?;
    let tok = token_total(usage)?;
    let spend = &mut by_model[at].1;
    spend.usd = spend.usd.plus(usd)?;
    spend.tok = spend.tok.plus(tok)?;
    Ok(())
}

fn tail(mut seen: Vec<Value>) -> Vec<Value> {
    let cut = seen.len().saturating_sub(50);
    seen.split_off(cut)
}

// python f.seek(offset) 이 받는 int(bool 포함). float 는 TypeError, C long 을 넘으면 OverflowError
fn seek_offset(offset: &Value) -> Result<i128> {
    match offset {
        Value::Int(n) if i64::try_from(*n).is_ok() => Ok(*n),
        Value::Bool(b) => Ok(i128::from(*b)),
        Value::Int(_) | Value::BigInt(_) => Err(Stop::Raises("f.seek of an offset past a C long")),
        _ => Err(Stop::Raises("f.seek of an offset that is not an int")),
    }
}

// open(path, "rb"); f.seek(offset); f.read(). 열지 못하거나 OSError(음수 자리 포함)면 None
fn read_from(path: &str, offset: &Value) -> Result<Option<Vec<u8>>> {
    use std::io::{Read, Seek, SeekFrom};

    // python opens before it seeks: a missing file wins over a bad offset
    let os = os_path(path).ok_or(Stop::Raises("open() of a path with NUL"))?;
    let Ok(mut file) = std::fs::File::open(os) else {
        return Ok(None);
    };
    let Ok(offset) = u64::try_from(seek_offset(offset)?) else {
        return Ok(None);
    };

    if file.seek(SeekFrom::Start(offset)).is_err() {
        return Ok(None);
    }
    let mut data = Vec::new();
    Ok(file.read_to_end(&mut data).ok().map(|_| data))
}

// python bytes.splitlines(): \n, \r, \r\n
fn split_lines(data: &[u8]) -> Vec<&[u8]> {
    let mut out = Vec::new();
    let mut start = 0;

    // A line ends at \n, \r or \r\n
    let mut i = 0;
    while i < data.len() {
        match data[i] {
            b'\n' => {
                out.push(&data[start..i]);
                start = i + 1;
            }
            b'\r' => {
                out.push(&data[start..i]);
                if data.get(i + 1) == Some(&b'\n') {
                    i += 1;
                }
                start = i + 1;
            }
            _ => {}
        }
        i += 1;
    }

    // The last line without an end
    if start < data.len() {
        out.push(&data[start..]);
    }
    out
}

fn contains(hay: &[u8], needle: &[u8]) -> bool {
    hay.windows(needle.len()).any(|w| w == needle)
}

// python json.loads(bytes): UTF-8(맨 앞 BOM 은 뗀다). 다른 인코딩으로 보이는 줄과 읽지 못하는 줄은 None(python 도 거의 늘 ValueError)
fn decode_line(line: &[u8]) -> Option<Value> {
    let line = line.strip_prefix(b"\xef\xbb\xbf").unwrap_or(line);
    json_load::from_bytes(line, Decode::Strict).ok()
}

// 줄 하나가 아직 세지 않은 assistant 사용량이면 (모델, usage)
fn usage_record<'a>(
    record: &'a Value,
    seen: &mut Vec<Value>,
) -> Result<Option<(String, &'a Dict)>> {
    let Value::Dict(record) = record else {
        return Err(Stop::Raises("d.get on a line that is not a dict"));
    };
    let Some(Value::Dict(message)) = record.get("message").filter(|v| v.truthy()) else {
        return Ok(None);
    };
    let Some(Value::Dict(usage)) = message.get("usage") else {
        return Ok(None);
    };
    if record.get("type").and_then(Value::as_str) != Some("assistant") {
        return Ok(None);
    }

    // One count per message id
    let id = match message.get("id").filter(|v| v.truthy()) {
        Some(id) => id.clone(),
        None => record.get("requestId").cloned().unwrap_or(Value::Null),
    };
    if seen.iter().any(|s| py_eq(s, &id)) {
        return Ok(None);
    }
    seen.push(id);

    // Synthetic replies carry no cost
    let model = match message.get("model").filter(|v| v.truthy()) {
        None => "?".to_owned(),
        Some(Value::Str(m)) => m.clone(),
        Some(_) => return Err(Stop::Raises("model.startswith on a non-text model")),
    };
    if model.starts_with('<') {
        return Ok(None);
    }
    Ok(Some((model, usage)))
}

// python sum(int(u.get(k) or 0) for k in ...)
fn token_total(usage: &Dict) -> Result<Num> {
    let mut total: i128 = 0;
    for key in [
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ] {
        total = total
            .checked_add(py_int(usage.get(key))?)
            .ok_or(Stop::Unported("an integer past i128"))?;
    }
    Ok(Num::Int(total))
}

// python int(v or 0)
fn py_int(value: Option<&Value>) -> Result<i128> {
    match value.filter(|v| v.truthy()) {
        None => Ok(0),
        Some(Value::Bool(b)) => Ok(i128::from(*b)),
        Some(Value::Int(n)) => Ok(*n),
        Some(Value::Float(f)) if f.is_finite() && f.abs() < 1.7e38 => Ok(f.trunc() as i128),
        Some(Value::Str(s)) => {
            parse_int(s).ok_or(Stop::Raises("int() of text that is not a number"))
        }
        Some(_) => Err(Stop::Raises("int() of a value that is not a number")),
    }
}

/// python `tail_model(path)`: 트랜스크립트 끝 256 KiB 의 마지막 `"model":"claude-..."`. 읽지 못하면 `None`.
///
/// 찾은 이름이 UTF-8 이 아니면 python 은 `decode()` 에서 예외로 끝난다.
pub fn tail_model(path: &str) -> Result<Option<String>> {
    const TAIL: u64 = 262_144;
    const NEEDLE: &[u8] = b"\"model\":\"claude-";

    let size = match getsize(path) {
        Ok(size) => size,
        Err(FsError::Os(_)) => return Ok(None),
        Err(FsError::Value) => return Err(Stop::Raises("getsize of a path with NUL")),
    };
    let start = Value::Int(i128::from(size.saturating_sub(TAIL)));
    let Some(data) = read_from(path, &start)? else {
        return Ok(None);
    };

    // re.findall: non-overlapping, the last one wins
    let mut last = None;
    let mut pos = 0;
    while let Some(off) = data[pos..].windows(NEEDLE.len()).position(|w| w == NEEDLE) {
        let name_at = pos + off + NEEDLE.len() - "claude-".len();
        let body = pos + off + NEEDLE.len();
        match data[body..].iter().position(|&b| b == b'"') {
            Some(0) => pos = pos + off + 1,
            Some(len) => {
                last = Some(&data[name_at..body + len]);
                pos = body + len + 1;
            }
            None => break,
        }
    }
    match last {
        None => Ok(None),
        Some(name) => String::from_utf8(name.to_vec())
            .map(Some)
            .map_err(|_| Stop::Raises("decode() of a model name that is not UTF-8")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    fn usage(json: &str) -> Dict {
        loads(json).unwrap().into_dict().unwrap()
    }

    /// 실측한 sonnet 5.5 서브에이전트 하나의 사용량이 그 가격표로 $0.043544 다.
    #[test]
    fn prices_like_the_probe() {
        let u = usage(
            r#"{"input_tokens": 3, "output_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 17000,
                "cache_creation": {"ephemeral_5m_input_tokens": 17000, "ephemeral_1h_input_tokens": 0}}"#,
        );
        let usd = usage_usd("claude-sonnet-5-5", &u).unwrap().f64();
        assert!((usd - (3.0 * 2.0 + 17000.0 * 2.5 + 100.0 * 10.0) / 1e6).abs() < 1e-12);
        assert_eq!(usage_usd("gpt-x", &u).unwrap(), Num::Float(0.0));
        let fast = usage(r#"{"output_tokens": 1000, "speed": "fast"}"#);
        assert!((usage_usd("claude-opus-5-5", &fast).unwrap().f64() - 0.04).abs() < 1e-12);
    }

    /// 계열은 비싼 순으로 찾고 mythos 는 fable 이다.
    #[test]
    fn families() {
        let name = |s: &str| family(Some(&Value::Str(s.into())));
        assert_eq!(name("claude-opus-5-5"), "opus");
        assert_eq!(name("Mythos-5-2"), "fable");
        assert_eq!(name("gpt"), "?");
        assert_eq!(family(None), "?");
    }

    /// bytes.splitlines 는 \r, \r\n, \n 에서 나눈다.
    #[test]
    fn splits_like_python_bytes() {
        assert_eq!(
            split_lines(b"a\r\nb\rc\n\nd"),
            [&b"a"[..], b"b", b"c", b"", b"d"]
        );
    }
}
