//! resource-guard 의 설정: 스위치와 문턱(python 판의 `ENV_DEFAULTS`, `switch`, `number`, `thresholds`).

use harness_hook::py::num::parse_float;
use harness_hook::py::text::strip;
use harness_hook::settings::Layers;

/// 이 훅만 읽는 harness.env 키와 기본값. userConfig 키는 이 이름의 소문자다(true/false 는 on/off 로 들어온다).
pub const ENV_DEFAULTS: &[(&str, &str)] = &[
    ("PROC_GUARD_CORE", "on"),
    ("PROC_GUARD_DISK", "on"),
    ("PROC_GUARD_DISK_MIN_FREE_GIB", "10"),
    ("PROC_GUARD_DISK_MIN_FREE_PCT", "5"),
    ("PROC_GUARD_DISK_DROP_GIB", "2"),
];
// 기계 전체를 지키는 안전망이라 켜고 끄기는 사용자 몫이다: 클론한 저장소가 커밋한 harness.env 로 끄지 못하게 한다.
// 문턱은 저장소 층도 정하지만 더 엄하게만 바꾼다(thresholds). 풀 수 있으면 0 으로 스위치를 우회할 수 있기 때문이다
pub const ENV_USER_ONLY: &[&str] = &["PROC_GUARD_CORE", "PROC_GUARD_DISK"];
const ON_VALUES: &[&str] = &["on", "1", "true", "yes"];

fn default(key: &str) -> &'static str {
    ENV_DEFAULTS
        .iter()
        .find(|(k, _)| *k == key)
        .map(|(_, v)| *v)
        .expect("key has a default")
}

/// 스위치가 켜졌나(python `switch`).
pub fn switch(layers: &Layers, key: &str) -> bool {
    let value = layers.get(key).unwrap_or(default(key));
    ON_VALUES.contains(&strip(value).to_lowercase().as_str())
}

/// 0 이상의 수(python `number`: `max(0.0, float(값))`, 읽지 못하면 기본값).
pub fn number(layers: &Layers, key: &str) -> f64 {
    let value = layers.get(key).unwrap_or(default(key));
    match parse_float(value) {
        Some(x) if x > 0.0 => x,
        Some(_) => 0.0,
        None => parse_float(default(key)).expect("default parses"),
    }
}

/// 디스크 문턱. 0 은 그 검사를 끈다.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Limits {
    pub min_free_gib: f64,
    pub min_free_pct: f64,
    pub drop_gib: f64,
}

/// 저장소 층까지 합친 값 `all` 과 사용자 쪽 값 `user` 로 문턱을 정한다. 저장소 층은 사용자 값보다 엄하게만 바꾼다.
pub fn thresholds(all: &Layers, user: &Layers) -> Limits {
    let higher = |key: &str| number(all, key).max(number(user, key));
    let drops: Vec<f64> = [
        number(all, "PROC_GUARD_DISK_DROP_GIB"),
        number(user, "PROC_GUARD_DISK_DROP_GIB"),
    ]
    .into_iter()
    .filter(|v| *v > 0.0)
    .collect();
    Limits {
        min_free_gib: higher("PROC_GUARD_DISK_MIN_FREE_GIB"),
        min_free_pct: higher("PROC_GUARD_DISK_MIN_FREE_PCT"),
        drop_gib: drops.into_iter().reduce(f64::min).unwrap_or(0.0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn layers(pairs: &[(&str, &str)]) -> Layers {
        let mut l = Layers::default();
        for (k, v) in pairs {
            l.values.insert((*k).to_owned(), (*v).to_owned());
        }
        l
    }

    #[test]
    fn repo_layers_only_tighten() {
        let user = layers(&[
            ("PROC_GUARD_DISK_MIN_FREE_GIB", "10"),
            ("PROC_GUARD_DISK_DROP_GIB", "2"),
        ]);
        let all = layers(&[
            ("PROC_GUARD_DISK_MIN_FREE_GIB", "0"),
            ("PROC_GUARD_DISK_DROP_GIB", "0"),
        ]);
        let limits = thresholds(&all, &user);
        assert_eq!(limits.min_free_gib, 10.0);
        assert_eq!(limits.drop_gib, 2.0);
        assert_eq!(
            number(
                &layers(&[("PROC_GUARD_DISK_DROP_GIB", "x")]),
                "PROC_GUARD_DISK_DROP_GIB"
            ),
            2.0
        );
        assert_eq!(
            number(
                &layers(&[("PROC_GUARD_DISK_DROP_GIB", "-3")]),
                "PROC_GUARD_DISK_DROP_GIB"
            ),
            0.0
        );
    }

    #[test]
    fn switches_read_on_values() {
        assert!(switch(&layers(&[]), "PROC_GUARD_DISK"));
        assert!(switch(
            &layers(&[("PROC_GUARD_DISK", " YES ")]),
            "PROC_GUARD_DISK"
        ));
        assert!(!switch(
            &layers(&[("PROC_GUARD_DISK", "0")]),
            "PROC_GUARD_DISK"
        ));
    }
}
