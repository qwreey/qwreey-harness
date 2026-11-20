//! harness.env 층을 python 정본(home/.claude/lib/harness_env.py)과 대조한다.
//! 같은 파일 묶음과 환경을 양쪽에 주고 `load_layers` 의 값, `_file`, `_files`, `_options` 를 비교한다.

mod common;

use std::path::{Path, PathBuf};

use common::{TempDir, case, pairs, python};
use harness_hook::Env;
use harness_hook::settings::envfile::{self, Values};
use harness_hook::settings::options::option_value;
use harness_hook::settings::{self, Layers, LoadRequest, Project};
use serde_json::{Map, Value, json};

/// 한 경우의 입력. python 쪽 인자와 Rust 쪽 [`LoadRequest`] 를 같은 값에서 만든다.
struct LayerCase {
    label: &'static str,
    env: Vec<(String, String)>,
    project: Project,
    candidates: Option<Vec<PathBuf>>,
    defaults: Vec<(&'static str, String)>,
    user_only: Vec<&'static str>,
    options: Vec<(&'static str, Vec<&'static str>)>,
    /// python 의 `__file__` 디렉터리 = Rust 의 `plugin_dir`.
    module_dir: PathBuf,
}

impl LayerCase {
    fn new(
        label: &'static str,
        env: Vec<(String, String)>,
        project: Project,
        module_dir: PathBuf,
    ) -> LayerCase {
        LayerCase {
            label,
            env,
            project,
            candidates: None,
            defaults: Vec::new(),
            user_only: Vec::new(),
            options: Vec::new(),
            module_dir,
        }
    }

    fn python_case(&self) -> Value {
        let project = match &self.project {
            Project::FromEnv => Value::Null,
            Project::Skip => json!(""),
            Project::Dir(dir) => json!({"dir": dir}),
        };
        let defaults: Map<String, Value> = self
            .defaults
            .iter()
            .map(|(k, v)| ((*k).to_owned(), json!(v)))
            .collect();
        let options: Map<String, Value> = self
            .options
            .iter()
            .map(|(k, v)| ((*k).to_owned(), json!(v)))
            .collect();

        case(
            "load_layers",
            &self.env,
            json!({
                "project": project,
                "candidates": self.candidates,
                "defaults": defaults,
                "user_only": self.user_only,
                "options": options,
                "module_file": self.module_dir.join("harness_env.py"),
            }),
        )
    }

    fn rust_result(&self) -> Value {
        let defaults: Vec<(&str, &str)> = self
            .defaults
            .iter()
            .map(|(k, v)| (*k, v.as_str()))
            .collect();
        let options: Vec<(&str, &[&str])> = self
            .options
            .iter()
            .map(|(k, v)| (*k, v.as_slice()))
            .collect();
        let req = LoadRequest {
            project: self.project.clone(),
            candidates: self.candidates.clone(),
            defaults: &defaults,
            user_only: &self.user_only,
            options: &options,
            plugin_dir: Some(&self.module_dir),
        };
        match settings::load_layers(&Env::from_pairs(self.env.clone()), &req) {
            Ok(layers) => layers_json(&layers),
            Err(e) => json!({"error": e.to_string()}),
        }
    }
}

// python load_layers 가 돌려주는 dict 와 같은 꼴로 바꾼다
fn layers_json(layers: &Layers) -> Value {
    let text = |p: &Path| p.to_string_lossy().into_owned();
    let mut out: Map<String, Value> = layers
        .values
        .iter()
        .map(|(k, v)| (k.clone(), json!(v)))
        .collect();

    // 무엇을 읽었는지
    out.insert(
        "_file".into(),
        json!(layers.user_file.as_deref().map(text).unwrap_or_default()),
    );
    out.insert(
        "_files".into(),
        json!(
            layers
                .files
                .iter()
                .map(|p| text(p))
                .collect::<Vec<_>>()
                .join(" ")
        ),
    );
    out.insert("_options".into(), json!(layers.option_ids.join(" ")));
    Value::Object(out)
}

const USER_LAYER: &str = "# user layer\r\n\
export USER_A=1 # trailing comment\r\n\
USER_Q=\"quoted # not comment\"  # c\r\n\
USER_S='single $USER_A'\r\n\
USER_REF=${USER_A}-$USER_A-$NOPE-${HOME}-$\r\n\
USER_TILDE=~/x\r\n\
USER_KO=\u{d55c}\u{ae00} \u{ac12}\u{3000}\r\n\
\u{3000}USER_SPACE\u{3000}=\u{3000}v\u{3000}\r\n\
USER_UNTERMINATED=\"abc # x\r\n\
ENV_WINS=file\r\n\
HARNESS_HEAVY_WRAP=nice -n 5\r\n\
PROC_GUARD_DISK_MIN_FREE_GIB=10\r\n\
bad line here\r\n\
1BAD=x\r\n\
USER_VT=a\u{b}USER_AFTER_VT=b\u{1f}\r\n\
USER_EMPTY=\r\n\
exportUSER_GLUED=g\n";

const REPO_LAYER: &str = "HARNESS_HEAVY_WRAP=evil\n\
PROC_GUARD_DISK=off\n\
HARNESS_WORKSPACE=/evil\n\
SESSION_LOG_HOME=/evil\n\
LEAK=$HARNESS_HEAVY_WRAP\n\
DEMO_FLAG=off\n\
REPO_KEY=shared\n\
PROC_GUARD_DISK_MIN_FREE_GIB=1\n\
REF_USER=$USER_A$DEMO_NUM\n";

const SETTINGS: &str = r#"{"enabledPlugins": {"demo@m1": true, "demo@m2": false, "other@m": true},
 "pluginConfigs": {
   "demo@m2": {"options": {"demo_flag": false}},
   "demo@m1": {"options": {"demo_flag": true, "demo_num": 3, "demo_float": 1.5, "demo_intfloat": 2.0, "demo_big": 1e20,
     "demo_list": ["~/a", 1, true, null, {"x": 1}, ["n", 2.5]], "demo_path": "~/p;rel;~", "demo_null": null,
     "demo_obj": {}, "extra_demo": "from-extra", "demo_ko": "값"}},
   "other@m": {"options": {"other_key": "o", "demo_flag": "should-not-leak"}},
   "notmine": {"options": {}},
   "x@y@demo": {}
 }}"#;

const MANIFEST: &str = r#"{"name": "demo", "userConfig": {"demo_flag": {}, "demo_num": {}, "demo_float": {},
 "demo_intfloat": {}, "demo_big": {}, "demo_list": {}, "demo_path": {}, "demo_null": {}, "demo_obj": {},
 "demo_missing": {}, "demo_ko": {}}}"#;

#[test]
fn load_layers_matches_python() {
    let tmp = TempDir::new("layers");
    let root = tmp.text("");
    let root = root.trim_end_matches('/');

    // 설정 디렉터리, 플러그인, 저장소
    tmp.write("cfg/harness.env", USER_LAYER);
    tmp.write("cfg/settings.json", SETTINGS);
    tmp.write("plugin/.claude-plugin/plugin.json", MANIFEST);
    tmp.write("project/.claude/harness.env", REPO_LAYER);
    tmp.write("project/.claude/harness.local.env", "REPO_KEY=local\n");
    let plugin_dir = tmp.dir("plugin/hooks");
    let no_plugin = tmp.dir("none/a/b");
    let base_env = |extra: &[(&str, &str)]| {
        let mut env = pairs(&[
            ("HOME", &format!("{root}/home")),
            ("CLAUDE_CONFIG_DIR", &format!("{root}/cfg")),
            ("ENV_WINS", "env"),
            ("DEMO_NUM", "99"),
            ("HARNESS_WORKSPACE", "/from-env"),
        ]);
        env.extend(pairs(extra));
        env
    };
    let project = Project::Dir(format!("{root}/project"));

    // 1. 모든 층
    let mut full = LayerCase::new("full", base_env(&[]), project.clone(), plugin_dir.clone());
    full.defaults = vec![
        ("PROC_GUARD_DISK", "on".into()),
        ("X_DEF", "~/d/$HOME/$NOPE".into()),
    ];
    full.user_only = vec!["PROC_GUARD_DISK"];
    full.options = vec![
        ("other", vec!["OTHER_KEY", "DEMO_FLAG"]),
        ("demo", vec!["EXTRA_DEMO"]),
    ];
    let mut cases = vec![full];

    // 2. 망가진 저장소 개인 파일, settings.json 여러 꼴
    tmp.write("project2/.claude/harness.env", "REPO_KEY=shared\n");
    tmp.write("project2/.claude/harness.local.env", b"REPO_KEY=\xff\xfe\n");
    cases.push(LayerCase::new(
        "bad local",
        base_env(&[]),
        Project::Dir(format!("{root}/project2")),
        plugin_dir.clone(),
    ));
    let settings_variants = [
        ("garbled settings", "{\"pluginConfigs\": {"),
        ("settings list", "[1, 2]"),
        ("configs not object", r#"{"pluginConfigs": ["demo@m1"]}"#),
        (
            "enabled copy unset",
            r#"{"enabledPlugins": {"demo@m3": true}, "pluginConfigs": {"demo@m1": {"options": {"demo_flag": true}}}}"#,
        ),
        (
            "two markets",
            r#"{"pluginConfigs": {"demo@zz": {"options": {"demo_num": 1}}, "demo@aa": {"options": {"demo_num": 2}}}}"#,
        ),
        (
            "options not object",
            r#"{"pluginConfigs": {"demo@m": {"options": [1]}}}"#,
        ),
        (
            "bom",
            "\u{feff}{\"pluginConfigs\": {\"demo@m\": {\"options\": {\"demo_num\": 1}}}}",
        ),
    ];
    for (i, (label, text)) in settings_variants.iter().enumerate() {
        let cfg = format!("cfg-s{i}");
        tmp.write(&format!("{cfg}/settings.json"), text);
        tmp.write(&format!("{cfg}/harness.env"), "USER_A=1\n");
        let env = base_env(&[("CLAUDE_CONFIG_DIR", &format!("{root}/{cfg}"))]);
        cases.push(LayerCase::new(
            label,
            env,
            Project::Skip,
            plugin_dir.clone(),
        ));
    }

    // 3. 사용자 층 찾기: 깨진 파일, BOM, HARNESS_ENV(정규화), 없는 HARNESS_ENV 와 후보
    tmp.write("cfg-bad/harness.env", b"USER_A=\xff\n");
    tmp.write("cfg-bom/harness.env", "\u{feff}USER_A=1\nUSER_B=2\n");
    tmp.write("cand.env", "CAND=1\n");
    cases.push(LayerCase::new(
        "bad user file",
        base_env(&[("CLAUDE_CONFIG_DIR", &format!("{root}/cfg-bad"))]),
        Project::Skip,
        no_plugin.clone(),
    ));
    cases.push(LayerCase::new(
        "bom user file",
        base_env(&[("CLAUDE_CONFIG_DIR", &format!("{root}/cfg-bom"))]),
        Project::Skip,
        no_plugin.clone(),
    ));
    let odd_path = format!("{root}//cfg/./harness.env");
    cases.push(LayerCase::new(
        "HARNESS_ENV",
        base_env(&[("HARNESS_ENV", &odd_path)]),
        Project::Skip,
        no_plugin.clone(),
    ));
    let mut with_candidates = LayerCase::new(
        "candidates",
        base_env(&[("HARNESS_ENV", "/nonexistent.env")]),
        Project::Skip,
        no_plugin.clone(),
    );
    with_candidates.candidates = Some(vec![
        PathBuf::from(format!("{root}/none.env")),
        PathBuf::from(format!("{root}//cand.env")),
    ]);
    cases.push(with_candidates);

    // 4. 저장소 자리: 홈이 저장소(같은 파일은 한 번), Skip, 환경 변수, 정규화할 경로
    tmp.write("home2/.claude/harness.env", "USER_A=home\n");
    tmp.write("home2/.claude/harness.local.env", "LOCAL=1\n");
    let home2 = pairs(&[("HOME", &format!("{root}/home2"))]);
    cases.push(LayerCase::new(
        "project is home",
        home2,
        Project::Dir(format!("{root}/home2")),
        no_plugin.clone(),
    ));
    cases.push(LayerCase::new(
        "from env",
        base_env(&[("CLAUDE_PROJECT_DIR", &format!("{root}/project"))]),
        Project::FromEnv,
        no_plugin.clone(),
    ));
    cases.push(LayerCase::new(
        "from empty env",
        base_env(&[("CLAUDE_PROJECT_DIR", "")]),
        Project::FromEnv,
        no_plugin.clone(),
    ));
    cases.push(LayerCase::new(
        "odd project path",
        base_env(&[]),
        Project::Dir(format!("{root}//project/./")),
        no_plugin.clone(),
    ));

    // 5. 플러그인 찾기: 깨진 plugin.json 을 지나 위로, userConfig 없는 자기 플러그인을 options 로
    tmp.write("plugin3/hooks/.claude-plugin/plugin.json", "{");
    tmp.write("plugin3/.claude-plugin/plugin.json", MANIFEST);
    cases.push(LayerCase::new(
        "manifest walk",
        base_env(&[]),
        Project::Skip,
        tmp.dir("plugin3/hooks"),
    ));
    tmp.write("plugin4/.claude-plugin/plugin.json", r#"{"name": "demo"}"#);
    let mut own_by_options = LayerCase::new(
        "own via options",
        base_env(&[]),
        Project::Skip,
        tmp.dir("plugin4/hooks"),
    );
    own_by_options.options = vec![("demo", vec!["DEMO_FLAG"])];
    cases.push(own_by_options);

    // python 과 Rust 를 경우마다 비교
    let python_cases: Vec<Value> = cases.iter().map(LayerCase::python_case).collect();
    let Some(got) = python(&python_cases) else {
        return;
    };

    for (i, (g, c)) in got.iter().zip(&cases).enumerate() {
        assert_eq!(*g, c.rust_result(), "case {i} ({})", c.label);
    }

    // 대조한 동작 가운데 층 규칙의 요점(python 판도 같은 값이다)
    let full = &got[0];
    let expect = [
        ("HARNESS_HEAVY_WRAP", json!("nice -n 5")), // 사용자 전용: 저장소 값 무시
        ("PROC_GUARD_DISK", json!("on")),           // 호출자 user_only
        ("HARNESS_WORKSPACE", json!("/from-env")),  // 옛 키는 환경 변수만
        ("SESSION_LOG_HOME", Value::Null),          // 옛 플러그인 대신 막는 키
        ("LEAK", json!("evil")), // 막힌 키의 저장소 값이 같은 파일의 $NAME 으로는 샌다
        ("DEMO_FLAG", json!("off")), // 저장소 층이 옵션 층을 이긴다
        ("DEMO_NUM", json!("99")), // 환경 변수가 옵션을 이긴다
        ("PROC_GUARD_DISK_MIN_FREE_GIB", json!("1")),
        ("REPO_KEY", json!("local")),
        ("OTHER_KEY", json!("o")),
        ("DEMO_LIST", json!(format!("{root}/home/a;1;on;n;2.5"))),
        ("_options", json!("other@m demo@m1")),
    ];
    for (key, want) in expect {
        assert_eq!(full.get(key).cloned().unwrap_or(Value::Null), want, "{key}");
    }
}

#[test]
fn parse_and_option_values_match_python() {
    let env = pairs(&[("HOME", "/h"), ("FROM_ENV", "e")]);
    let base: Values = [("B", "base"), ("FROM_ENV", "scope")]
        .iter()
        .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
        .collect();
    let texts = [
        USER_LAYER,
        REPO_LAYER,
        "A=$B ${B}x $FROM_ENV\nFROM_ENV=file\nC='$A'\nD=\"un\nE=~\nF=~nobody/x\n",
        "export  \tK=v\nexport=1\nexport K2 = v2 # c\nK3=a#b c #d\n\u{85}K4=v\u{2028}K5=w",
        "",
    ];

    // option_value 에 넣을 값: 모든 JSON 타입, 정수 값 float, u64 끝, ~ 조각
    let values = json!([
        true,
        false,
        0,
        -5,
        3.0,
        1.5,
        1e-7,
        1e20,
        12345678901234567890u64,
        -0.0,
        null,
        {},
        [],
        "",
        "~",
        "~/a;~;x~",
        ["~/a", ["~", 1.25], null, {}, false],
        "\u{d55c}"
    ]);

    let mut cases: Vec<Value> = texts
        .iter()
        .map(|t| case("parse", &env, json!({"text": t, "base": base})))
        .collect();
    cases.push(case("option_value", &env, json!({"values": values})));
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust 쪽 같은 순서로
    let rust_env = Env::from_pairs(env.clone());
    let mut want: Vec<Value> = texts
        .iter()
        .map(|t| json!(envfile::parse(t, &base, &rust_env)))
        .collect();
    let options: Vec<Option<String>> = values
        .as_array()
        .unwrap()
        .iter()
        .map(|v| option_value(v, &rust_env))
        .collect();
    want.push(json!(options));

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}

#[test]
fn heavy_wrap_matches_python() {
    let tmp = TempDir::new("wrap");
    let exec = |rel: &str, mode: u32| {
        let path = tmp.write(rel, "#!/bin/sh\n");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(mode)).unwrap();
        }
        let _ = mode;
        path
    };
    let choom = exec("bin1/choom", 0o755);
    exec("bin2/choom", 0o644);
    exec("bin3/nice", 0o755);

    // 경우마다 PATH 와 HARNESS_HEAVY_WRAP 값(None 이면 키가 없다)
    let choom_text = choom.to_string_lossy().into_owned();
    let runs: Vec<(String, Option<String>)> = vec![
        (tmp.text("bin1"), None),
        (tmp.text("bin1"), Some(" auto ".into())),
        (tmp.text("bin2"), Some("auto".into())),
        (tmp.text("bin1"), Some(String::new())),
        (tmp.text("bin3"), Some("nice  -n\u{3000}5".into())),
        (String::new(), Some(format!("{choom_text} -n 1000 --"))),
        (tmp.text("bin3"), Some("missing-prog x".into())),
        (format!(":{}", tmp.text("bin1")), Some("choom".into())),
    ];

    let mut cases = Vec::new();
    let mut want = Vec::new();
    for (path, wrap) in &runs {
        let env = pairs(&[("PATH", path)]);
        let values: Values = wrap
            .iter()
            .map(|w| ("HARNESS_HEAVY_WRAP".to_owned(), w.clone()))
            .collect();
        cases.push(case("heavy_wrap", &env, json!({"values": values})));
        let layers = Layers {
            values,
            ..Layers::default()
        };
        want.push(json!(settings::heavy_wrap(&layers, &Env::from_pairs(env))));
    }
    let Some(got) = python(&cases) else {
        return;
    };

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}
