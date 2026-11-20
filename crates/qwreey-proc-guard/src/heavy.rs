//! heavy-proc-guard(PreToolUse Bash): 벤치, 퍼저, 성능 실측처럼 무거운 실행은 choom 으로 감싸야 한다(`hooks/heavy-proc-guard.py`).
//!
//! 왜: 컨테이너의 메모리 cgroup 을 모든 Claude 세션이 같이 쓴다. 남은 여유를 먹는 벤치는 cgroup OOM killer 를 부르고, 그것은
//! oom_score 로 고르므로 Claude 프로세스를 죽인 적이 있다. 자식의 점수를 올리는 것은 권한 없이 되고 exec 에도 이어지므로
//! `choom -n 1000 -- <명령>` 이 무거운 나무를 첫 희생자로 만든다.
//!
//! 판정(일부러 싸게. 오탐은 choom 으로 한 번 더 돌리면 된다): 한 구간이 실행기(luau, bash, python 등)를 부르고 같은 구간에
//! 무거운 낱말이 있으면 막는다. 이미 래퍼가 있거나 git/gh 명령이면 통과. heredoc 본문은 먼저 버린다. 낱말을 값으로 가진 변수는
//! 그것을 펼치는 구간으로 옮아가고, 낱말 폴더로 가는 `cd` 는 뒤의 툴킷 실행기와 스크립트로 옮아간다(인터프리터에는 아니다).
//! 래퍼는 harness.env 의 HARNESS_HEAVY_WRAP. 비었거나 그 프로그램이 없으면(choom 없는 sandbox) 모두 통과한다.

use std::collections::BTreeSet;
use std::sync::LazyLock;

use harness_hook::py::re::{self, Flags, Regex};
use harness_hook::py::text::split_whitespace;
use harness_hook::settings::{self, Layers};
use harness_hook::tag::{self, Level};
use harness_hook::{HookInput, HookOutput};

use crate::context::{Context, project_for};
use crate::shell::{Segment, segments, strip_heredocs};

const TAG: &str = "heavy-proc-guard";
const BASE_KEYWORDS: &[&str] = &[
    "bench",
    "fuzz",
    "perf(?:orm(?:ance)?)?(?![A-Za-z])",
    "stress",
    "soak",
    "load-?test",
    "hyperfine",
];
const BASE_EXECUTORS: &[&str] = &[
    "bash",
    "sh",
    "zsh",
    "python",
    "python3",
    "node",
    "hyperfine",
];
// 툴킷마다 무거운 실행을 띄우는 실행기. 새 툴킷은 python 판의 TOOLKIT_EXECUTORS 와 함께 여기에 한 줄 더한다
const TOOLKIT_EXECUTORS: &[(&str, &[&str])] = &[
    ("luau", &["luau", "lune", "lute"]),
    (
        "web",
        &["npm", "npx", "pnpm", "yarn", "bun", "deno", "vitest"],
    ),
    ("rust", &["cargo"]),
];
// 이 훅만 읽는 harness.env 키: 표에 더할 실행기와 키워드(공백 구분). 더하기만 하므로 저장소 층도 정할 수 있다
const ENV_DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_HEAVY_EXECUTORS", ""),
    ("HARNESS_HEAVY_KEYWORDS", ""),
];
const EXEMPT_HEADS: &[&str] = &["git", "gh"];
// qwreey-delegate 의 드라이버는 자기 setpriv 실행 앞에 choom 을 둔다. 그 프롬프트 글은 bench, perf 를 말해도 된다
const DELEGATE_SCRIPTS: &[&str] = &["delegate.py", "delegate.sh"];

static ASSIGN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?:^|[;&|\s(])([A-Za-z_][A-Za-z0-9_]*)=(\S*)").expect("built-in pattern")
});
// 시간 재는 호출은 키워드보다 훨씬 정확히 벤치를 가리킨다. heredoc 본문에만 쓴다
static TIMING: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"os\.clock\(|perf_counter|timeit|performance\.now\(|hrtime|Instant::now")
        .expect("built-in pattern")
});

/// 실행기 이름과 무거운 낱말 정규식(설정 층에서).
pub struct Rules {
    executors: BTreeSet<String>,
    heavy: Regex,
}

impl Rules {
    /// python `rules(env)`.
    pub fn from_layers(layers: &Layers) -> Rules {
        let words = |key: &str| -> Vec<String> {
            split_whitespace(layers.get(key).unwrap_or(""))
                .map(str::to_owned)
                .collect()
        };

        // 켠 툴킷의 실행기(없으면 모든 툴킷)
        let toolkits: BTreeSet<String> = words("HARNESS_TOOLKITS").into_iter().collect();
        let mut executors: BTreeSet<String> =
            BASE_EXECUTORS.iter().map(|s| (*s).to_owned()).collect();
        executors.extend(words("HARNESS_HEAVY_EXECUTORS"));
        for (toolkit, names) in TOOLKIT_EXECUTORS {
            if toolkits.is_empty() || toolkits.contains(*toolkit) {
                executors.extend(names.iter().map(|s| (*s).to_owned()));
            }
        }

        // 무거운 낱말: 기본 + 사용자 낱말(글자 그대로)
        let extra = words("HARNESS_HEAVY_KEYWORDS")
            .into_iter()
            .map(|k| re::escape(&k));
        let keywords: Vec<String> = BASE_KEYWORDS
            .iter()
            .map(|k| (*k).to_owned())
            .chain(extra)
            .collect();
        let pattern = format!("(?<![A-Za-z])({})", keywords.join("|"));
        let heavy =
            Regex::with_flags(&pattern, Flags::IGNORECASE).expect("escaped keywords compile");
        Rules { executors, heavy }
    }

    fn is_executor(&self, head: &str) -> bool {
        self.executors.contains(head) || head.ends_with(".sh") || head.starts_with("./")
    }
}

/// 훅 하나를 돌린다. 막을 때만 deny 출력.
pub fn run(ctx: &Context, input: &HookInput) -> Option<HookOutput> {
    // choom 과 공유 메모리 cgroup 은 Linux 의 일이다. Windows 에서는 래퍼 설정과 상관없이 막지 않는다
    if cfg!(windows) {
        return None;
    }
    let cmd = input.command().unwrap_or("");

    // 설정과 래퍼. python 에서 예외가 나는 cwd 면 설정은 {} 다
    let layers = match project_for(&ctx.env, input.raw().get("cwd")) {
        Some(project) => ctx.layers(project, ENV_DEFAULTS, &[]),
        None => Layers::default(),
    };
    let wrap = settings::heavy_wrap(&layers, &ctx.env);
    let program = wrap.first()?;
    let rules = Rules::from_layers(&layers);

    // 이미 감쌌거나, 위임 드라이버이거나, 낱말이 없으면 통과
    if cmd.contains(program.as_str())
        || DELEGATE_SCRIPTS.iter().any(|d| cmd.contains(d))
        || !(rules.heavy.is_match(cmd) || TIMING.is_match(cmd))
    {
        return None;
    }
    if !denies(cmd, &rules) {
        return None;
    }

    let reason = tag::harness_hook(
        TAG,
        Level::Action,
        ctx.nonce(input).as_ref(),
        &deny_reason(&wrap),
    );
    Some(HookOutput::deny(reason))
}

/// 명령을 막을지(래퍼, 위임 드라이버 검사 뒤의 판정).
pub fn denies(cmd: &str, rules: &Rules) -> bool {
    let segs = segments(cmd);
    if segs
        .first()
        .is_some_and(|s| EXEMPT_HEADS.contains(&s.head.as_str()))
    {
        return false;
    }

    // `F=x/fuzz.luau; luau $F`: 낱말을 값으로 가진 변수는 펼치는 곳에서 낱말로 친다
    let mut bodies = Vec::new();
    let stripped = strip_heredocs(cmd, Some(&mut bodies));
    let names: Vec<&str> = ASSIGN
        .find_iter(&stripped)
        .iter()
        .filter(|m| {
            m.text(&stripped, 2)
                .is_some_and(|v| rules.heavy.is_match(v))
        })
        .filter_map(|m| m.text(&stripped, 1))
        .collect();
    let uses = (!names.is_empty()).then(|| {
        let pattern = format!(r"\$\{{?(?:{})(?![A-Za-z0-9_])", names.join("|"));
        Regex::new(&pattern).expect("variable names compile")
    });

    let timed = TIMING.is_match(&bodies.join("\n"));
    runs_heavy(&segs, rules, uses.as_ref(), timed)
}

// 실행기 구간이 무거운 낱말을 (바로 또는 변수로) 부르면 true.
// `cd <fuzz 폴더> && luau a.luau` 의 낱말은 cd 구간에 있다. 그 폴더는 뒤 구간으로 옮아가지만 툴킷 실행기와 스크립트(`./x`, `*.sh`)에만이다.
// 인터프리터(python3, bash -c)는 그런 폴더에서 대개 결과를 모으거나 고친다. `timed`(시간 재는 heredoc 본문)도 같이 옮아간다
fn runs_heavy(segs: &[Segment], rules: &Rules, uses: Option<&Regex>, timed: bool) -> bool {
    let mut carry = timed;
    for seg in segs {
        let h = seg.head.as_str();
        if h == "cd" || h == "pushd" {
            carry = carry || rules.heavy.is_match(&seg.text);
            continue;
        }
        if !rules.is_executor(h) {
            continue;
        }
        if rules.heavy.is_match(&seg.text) || uses.is_some_and(|u| u.is_match(&seg.text)) {
            return true;
        }
        if carry && (!BASE_EXECUTORS.contains(&h) || h.starts_with("./") || h.ends_with(".sh")) {
            return true;
        }
    }
    false
}

fn deny_reason(wrap: &[String]) -> String {
    let how = if wrap[0] == "choom" {
        "Re-run with `choom -n 1000 -p $$;` prepended (this shell and its children become the first OOM victims), \
         or wrap it: `choom -n 1000 -- prlimit --data=3221225472 -- <command>`."
            .to_owned()
    } else {
        format!("Re-run wrapped as `{} <command>`.", wrap.join(" "))
    };
    format!(
        "Bench/fuzz/perf/stress-looking runs must raise their OOM-victim rank first. The container's memory cgroup is shared \
         by every Claude session, and the OOM killer has killed a Claude process before. {how} \
         If this is a false positive, wrapping the same way passes."
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rules(extra: &[(&str, &str)]) -> Rules {
        let mut layers = Layers::default();
        for (k, v) in extra {
            layers.values.insert((*k).to_owned(), (*v).to_owned());
        }
        Rules::from_layers(&layers)
    }

    #[test]
    fn denies_heavy_runs() {
        let r = rules(&[]);
        for cmd in [
            "python3 fuzz.py",
            "./bench.sh",
            "cargo bench",
            "timeout 60 lune run perf.luau",
            "F=a/fuzz.luau; luau $F -a 1",
            "A=x/perf; mise exec -- luau ${A}/a.luau",
            "cd bench && ./run.sh",
            "cat > k.luau <<'EOF'\nlocal t = os.clock()\nEOF\nluau k.luau",
        ] {
            assert!(denies(cmd, &r), "{cmd}");
        }
    }

    #[test]
    fn passes_false_positives() {
        let r = rules(&[]);
        for cmd in [
            "git commit -m 'add bench'",
            "echo bench",
            "cd bench && python3 run.py",
            "python3 - <<'EOF'\nprint('Bench/fuzz')\nEOF",
            "cat <<EOF > f\nbench\nEOF\npython3 ok.py",
            "python3 build.py && echo bench",
        ] {
            assert!(!denies(cmd, &r), "{cmd}");
        }
    }

    #[test]
    fn settings_add_executors_and_keywords() {
        assert!(!denies("mytool bench", &rules(&[])));
        assert!(denies(
            "mytool bench",
            &rules(&[("HARNESS_HEAVY_EXECUTORS", "mytool")])
        ));
        assert!(denies("python3 x.py --mode=soak.test", &rules(&[])));
        assert!(denies(
            "python3 x.py c++",
            &rules(&[("HARNESS_HEAVY_KEYWORDS", "c++")])
        ));
        assert!(!denies(
            "cargo bench",
            &rules(&[("HARNESS_TOOLKITS", "luau")])
        ));
    }

    #[test]
    fn reason_names_the_wrapper() {
        assert!(deny_reason(&["choom".into()]).contains("choom -n 1000 -p $$;"));
        assert!(
            deny_reason(&["/w".into(), "-n".into()])
                .contains("Re-run wrapped as `/w -n <command>`.")
        );
    }
}
