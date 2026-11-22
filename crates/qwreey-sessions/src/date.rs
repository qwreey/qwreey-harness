//! python `datetime.date` 의 조각: `date.fromisoformat`, `date.today()`, 날짜 차의 `.days`.
//!
//! 날짜는 python `date.toordinal()` 처럼 0001-01-01 을 1 로 센 날 수로 들고 다닌다. 오늘은 이 기기의 시간대(TZ, tzdb)로 jiff 가 정한다.

/// 그레고리력 날짜 하나(python `date`). 값은 `toordinal()`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date(i64);

const MAX_YEAR: i64 = 9999;
const DAYS_BEFORE_MONTH: [i64; 13] = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

fn is_leap(year: i64) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

fn days_in_month(year: i64, month: i64) -> i64 {
    match month {
        2 if is_leap(year) => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

impl Date {
    /// python `date(year, month, day)`. 범위 밖이면 `None`(python ValueError).
    pub fn new(year: i64, month: i64, day: i64) -> Option<Date> {
        if !(1..=MAX_YEAR).contains(&year) || !(1..=12).contains(&month) {
            return None;
        }
        if !(1..=days_in_month(year, month)).contains(&day) {
            return None;
        }
        let before_year = (year - 1) * 365 + (year - 1) / 4 - (year - 1) / 100 + (year - 1) / 400;
        let leap_day = i64::from(month > 2 && is_leap(year));
        Some(Date(
            before_year + DAYS_BEFORE_MONTH[month as usize] + leap_day + day,
        ))
    }

    /// python `date.today()`: 이 기기 시간대의 오늘.
    pub fn today() -> Option<Date> {
        let today = jiff::Zoned::now().date();
        Date::new(
            i64::from(today.year()),
            i64::from(today.month()),
            i64::from(today.day()),
        )
    }

    /// python `(self - other).days`.
    pub fn days_since(self, other: Date) -> i64 {
        self.0 - other.0
    }

    /// python `date.fromisoformat(text)`(3.14). 읽지 못하면 `None`(python ValueError).
    ///
    /// ASCII 이고 길이가 7, 8, 10 인 글만 받는다: `YYYY-MM-DD`, `YYYYMMDD`, `YYYY-Www[-D]`, `YYYYWww[D]`.
    /// python 처럼 날짜 뒤에 남은 글자(10자 `YYYYMMDDxx`)는 보지 않는다.
    pub fn fromisoformat(text: &str) -> Option<Date> {
        if !text.is_ascii() || ![7, 8, 10].contains(&text.len()) {
            return None;
        }
        let s = text.as_bytes();

        // 연도와 구분자
        let year = digits(s, 0, 4)?;
        let dashed = s[4] == b'-';
        let mut pos = 4 + usize::from(dashed);

        // 주 날짜
        if s.get(pos) == Some(&b'W') {
            pos += 1;
            let week = digits(s, pos, 2)?;
            pos += 2;
            let mut weekday = 1;
            if s.len() > pos {
                if (s[pos] == b'-') != dashed {
                    return None;
                }
                pos += usize::from(dashed);
                weekday = digits(s, pos, 1)?;
            }
            return Date::from_iso_week(year, week, weekday);
        }

        // 달과 날
        let month = digits(s, pos, 2)?;
        pos += 2;
        if (s.get(pos) == Some(&b'-')) != dashed {
            return None;
        }
        pos += usize::from(dashed);
        let day = digits(s, pos, 2)?;
        Date::new(year, month, day)
    }

    // python _isoweek_to_gregorian
    fn from_iso_week(year: i64, week: i64, weekday: i64) -> Option<Date> {
        if !(1..=MAX_YEAR).contains(&year) {
            return None;
        }

        // 53째 주는 목요일로 시작하는 해, 수요일로 시작하는 윤년에만 있다
        let jan1 = Date::new(year, 1, 1)?;
        let jan1_weekday = jan1.0 % 7;
        let long_year = jan1_weekday == 4 || (jan1_weekday == 3 && is_leap(year));
        if !(1..=52).contains(&week) && !(week == 53 && long_year) {
            return None;
        }
        if !(1..=7).contains(&weekday) {
            return None;
        }

        // 1주 월요일에서 센다. 결과가 9999년 뒤면 python date() 가 거절한다
        let first_weekday = (jan1.0 + 6) % 7;
        let mut week1_monday = jan1.0 - first_weekday;
        if first_weekday > 3 {
            week1_monday += 7;
        }
        let ordinal = week1_monday + (week - 1) * 7 + (weekday - 1);
        let last = Date::new(MAX_YEAR, 12, 31)?;
        (1..=last.0).contains(&ordinal).then_some(Date(ordinal))
    }
}

// s[at..at+n] 의 ASCII 숫자. 모자라거나 숫자가 아니면 None
fn digits(s: &[u8], at: usize, n: usize) -> Option<i64> {
    let part = s.get(at..at + n)?;
    part.iter().try_fold(0i64, |acc, b| {
        b.is_ascii_digit().then(|| acc * 10 + i64::from(b - b'0'))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 날짜 번호는 0001-01-01 이 1 이다(python `date.toordinal`).
    #[test]
    fn ordinals_count_from_year_one() {
        assert_eq!(Date::new(1, 1, 1), Some(Date(1)));
        assert_eq!(Date::new(2026, 11, 10).map(|d| d.0), Some(739930));
    }

    /// 달력 날짜 글은 대시 있는 꼴, 없는 꼴, 뒤에 시각이 붙은 꼴을 받는다.
    #[test]
    fn iso_calendar_forms_are_accepted() {
        let want = Date::new(2026, 11, 10);

        for ok in ["2026-11-10", "20261110", "20261110T1"] {
            assert_eq!(Date::fromisoformat(ok), want, "{ok}");
        }
    }

    /// 주 날짜 글(`W01-1`, `W01`)은 ISO 주 규칙으로 읽는다.
    #[test]
    fn iso_week_forms_follow_week_rules() {
        assert_eq!(Date::fromisoformat("2026-W01-1"), Date::new(2025, 12, 29));
        assert_eq!(Date::fromisoformat("2026W01"), Date::new(2025, 12, 29));
        assert_eq!(
            Date::fromisoformat("2026-W53-1"),
            Date::new(2026, 12, 28),
            "2026 has 53 ISO weeks"
        );
    }

    /// 자릿수가 모자라거나 없는 날짜, 범위 밖 주와 요일, 뒤 공백은 거절한다.
    #[test]
    fn malformed_iso_dates_are_rejected() {
        for bad in [
            "2026-11-1",
            "2026-02-30",
            "0000-01-01",
            "2026-W00-1",
            "2026-W01-8",
            "2026-11-10 ",
        ] {
            assert_eq!(Date::fromisoformat(bad), None, "{bad}");
        }
    }
}
