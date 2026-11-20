//! reuse-check(python `hooks/reuse-check.py`): 한 사실의 사본. 막지 않고 `level="info"` 블록 하나만 낸다.
//!
//! 검사:
//! - M1 표시 자리와 꼴([`marks`]): 문서 주석의 표시, 읽히지 않는 영역 표시, 섞인 형제 저장소 꼴, JSON 의 표시.
//! - C1 사본이 원본과 같은가, C2 원본을 고치면 사본 목록([`copies`]).
//! - H1 추가한 문자열 묶음이 저장소의 다른 정의와 겹침([`judge`]). 기본은 그림자: 알리지 않고 기록만 한다([`record`]).
//!
//! 모드는 `REUSE_CHECK=off|shadow|on`, 저장소 `.claude/conventions.json` 의 `reuse.mode`, 기본 shadow([`config`]).
//! 색인([`index`])은 python 과 같은 파일을 나눠 쓴다. 첫 색인은 300 ms 에서 끊고, 400 ms 가 넘으면 겹침 판정을 그만둔다.
//! 시간은 이 훅을 부른 때부터 잰다(python 은 모듈을 읽은 때부터). Rust 가 빨라 끊기는 일이 python 보다 드물고,
//! 끊긴 실행은 두 판의 결과가 다를 수 있다(시간에 달린 판정이라 대조에서 비결정이다).

mod config;
mod copies;
mod files;
mod index;
mod judge;
mod marks;
mod packages;
mod record;
mod regions;
mod sets;

use std::collections::BTreeSet;
use std::time::Instant;

use harness_hook::HookInput;
use harness_hook::epoch::state_path;
use harness_hook::py::fs;
use harness_hook::py::path::{basename, dirname, join, relpath};
use harness_hook::py::value::Value;

use crate::context::{Context, PLUGIN};
use crate::edit::{Added, MAX_BYTES, collect, project_root};
use crate::halt::{Halt, Result};
use crate::lex::{Family, family};
use crate::pyval;

use config::{Mode, ReuseConfig};
use copies::{Siblings, Status};
use files::{H1_EXT, JSON_EXT, RULE_EXT, ext_of, generated, indexable, lang, list_files, skip_dir};
use index::Entry;
use judge::{Hit, Judge};
use packages::Packages;
use record::{Edited, ShadowRecord, State};
use sets::reason_ok;

/// 넘으면 겹침 판정을 그만둔다(python `HARD_MS`).
const HARD_MS: f64 = 400.0;
/// 기록의 `budget` 이 참이 되는 실행 시간(python `WARM_BUDGET_MS`).
const WARM_BUDGET_MS: i128 = 150;
/// 넘으면 편집한 파일의 패키지 안만 본다(python `MAX_FILES`).
const MAX_FILES: usize = 5000;
/// dedup 상태 폴더(python `compact_epoch.state_path(NAME, "claude-reuse", ...)`).
const STATE_NS: &str = "claude-reuse";

/// 훅이 시작한 때부터의 시간(python `T0` 과 `time.perf_counter()`).
pub struct Clock(Instant);

impl Clock {
    /// 지금부터 잰다.
    pub fn start() -> Clock {
        Clock(Instant::now())
    }

    /// 지난 밀리초.
    pub fn ms(&self) -> f64 {
        self.0.elapsed().as_secs_f64() * 1000.0
    }
}

/// 검사할 편집 하나(python main 의 앞부분이 고른 값).
struct Edit {
    path: String,
    root: String,
    rel: String,
    ext: String,
    is_json: bool,
    cfg: ReuseConfig,
    mode: Mode,
    text: String,
    added: Added,
}

/// reuse-check 를 돌려 stdout 글을 돌려준다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let clock = Clock::start();
    let Some(edit) = select(ctx, input)? else {
        return Ok(None);
    };

    // Dedup state for this session, caller and compact epoch
    let sid = input.get("session_id");
    let agent = pyval::truthy_text(input.get("agent_id"))?;
    let sid_text = pyval::truthy_text(sid)?.unwrap_or_default();
    let sp = state_path(
        ctx.tempdir()?,
        PLUGIN,
        STATE_NS,
        &sid_text,
        agent.as_deref(),
    )
    .map_err(|_| Halt::PyError("cannot create the state folder"))?;
    let mut state = State::load(sp)?;

    // JSON: only the marker note
    if edit.is_json {
        let note = marks::json_marker_note(&edit.rel, &edit.text, &edit.added);
        if let Some(note) = note
            && state.first_time(&format!("m:{}:json", edit.rel))
        {
            return record::emit(ctx, sid, &state, &[note]);
        }
        return Ok(None);
    }

    let notes = check(ctx, input, &edit, &mut state, &clock)?;
    record::emit(ctx, sid, &state, &notes)
}

// python main 의 앞부분: 볼 편집인가, 그 경로, 설정, 글, 추가한 줄. 볼 것이 없으면 None
fn select(ctx: &Context, input: &HookInput) -> Result<Option<Edit>> {
    // Tool and path; a tool_input that is not a dict ends python at .get
    let tool = input.get("tool_name");
    let ti = pyval::dict_or_empty(input.get("tool_input"))?;
    let path = pyval::str_or_empty(pyval::get(ti, "file_path"))?.to_owned();
    let ext = ext_of(&path);
    let is_json = JSON_EXT.contains(&ext.as_str());
    let tool = match tool {
        Some(Value::Str(t)) if matches!(t.as_str(), "Write" | "Edit" | "MultiEdit") => t.as_str(),
        _ => return Ok(None),
    };
    if !(RULE_EXT.contains(&ext.as_str()) || is_json) {
        return Ok(None);
    }

    // Repo-relative path and exclusions
    let root = project_root(&path, input.get("cwd"), &ctx.env)?;
    let rel = relpath(&path, &root).ok_or(Halt::PyError("relpath failed"))?;
    let dirs: Vec<&str> = rel.split('/').collect();
    let dirs = &dirs[..dirs.len() - 1];
    if is_json && dirs.iter().any(|p| skip_dir(p) || p.contains("-ignoreme")) {
        return Ok(None);
    }
    if rel.starts_with("..") || !(is_json || indexable(&rel, &[])) {
        return Ok(None);
    }
    let size =
        fs::getsize(&path).map_err(|_| Halt::PyError("os.path.getsize of a missing file"))?;
    if size > MAX_BYTES || vendored(&root, &rel)? {
        return Ok(None);
    }

    // Mode and allow list
    let cfg = ReuseConfig::load(&root);
    let mode = cfg.mode(ctx)?;
    if mode == Mode::Off || cfg.allowed(&rel)? {
        return Ok(None);
    }

    // The checked text and the added lines
    let Ok(disk) = fs::read_text(&path) else {
        return Ok(None);
    };
    let resp = match input.get("tool_response") {
        Some(Value::Dict(d)) => Some(d),
        _ => None,
    };
    let Some((text, added)) = collect(tool, ti, resp, Some(&disk))? else {
        return Ok(None);
    };
    if generated(&text) {
        return Ok(None);
    }
    Ok(Some(Edit {
        path,
        root,
        rel,
        ext,
        is_json,
        cfg,
        mode,
        text,
        added,
    }))
}

// 벤더 트리(vendor.lock.json 이 있는 폴더 아래)는 표시도 검사도 하지 않는다
fn vendored(root: &str, rel: &str) -> Result<bool> {
    let mut d = dirname(rel);
    while !d.is_empty() {
        if fs::exists(&join(&join(root, d), "vendor.lock.json")) {
            return Ok(true);
        }
        let up = dirname(d);
        if up == d {
            return Err(Halt::Unported("a path whose dirname does not shrink"));
        }
        d = up;
    }
    Ok(false)
}

// M1, C1, C2, H1 을 차례로: 알림들. 그림자 기록과 턴 끝 보고도 여기서 쓴다
fn check(
    ctx: &Context,
    input: &HookInput,
    edit: &Edit,
    state: &mut State,
    clock: &Clock,
) -> Result<Vec<String>> {
    let rel = edit.rel.as_str();
    let fam = family(&edit.ext).unwrap_or(Family::C);
    let mut notes = Vec::new();

    // M1 marker placement and sibling forms
    let mut flagged: BTreeSet<i64> = BTreeSet::new();
    for (ln, msg) in marks::marker_notes(rel, fam, &edit.text, &edit.added) {
        flagged.insert(ln as i64);
        if state.first_time(&format!("m:{rel}:{ln}")) {
            notes.push(msg);
        }
    }

    // Index of the repo, with this file read from the edited text
    let files = repo_files(&edit.root, rel);
    let ip = index::index_path(ctx.tempdir()?, &edit.root)?;
    let loaded = index::load(&ip, &edit.root, &files, rel, clock)?;
    let mut idx = loaded.index;
    let prev: Option<Entry> = idx.get(rel).cloned();
    let own = index::read_entry(&edit.root, rel, Some(&edit.text))
        .map_err(|_| Halt::PyError("os.stat of the edited file failed"))?;
    idx.insert(rel, own.clone());
    let changed = prev
        .as_ref()
        .is_none_or(|p| p.sets != own.sets || p.marks != own.marks);
    if loaded.dirty || changed {
        index::save(&ip, &idx)?;
    }

    let edited = Edited {
        rel,
        repo: basename(&edit.root),
        lang: lang(&edit.ext),
    };
    let mut log: Vec<ShadowRecord> = Vec::new();

    // C1 copies and C2 sources
    let mut siblings = Siblings::new(ctx, &edit.root);
    let differ = copy_checks(
        edit,
        &own,
        &idx,
        &flagged,
        &mut siblings,
        state,
        &edited,
        &mut notes,
        &mut log,
    )?;
    source_checks(
        edit,
        &own,
        &idx,
        prev.as_ref(),
        state,
        &edited,
        &mut notes,
        &mut log,
    )?;

    // H1 duplicate sets
    let mut dup_old = 0;
    if H1_EXT.contains(&edit.ext.as_str()) && clock.ms() < HARD_MS {
        dup_old = duplicate_checks(
            edit,
            &own,
            &idx,
            prev.as_ref(),
            state,
            clock,
            &edited,
            &mut notes,
            &mut log,
        )?;
    }

    // Shadow log and the turn-end report
    let ms = clock.ms().round_ties_even() as i128;
    record::shadow_log(ctx, log, ms, loaded.cut || ms > WARM_BUDGET_MS)?;
    let dup = if edit.mode == Mode::On { dup_old } else { 0 };
    record::record_report(
        ctx,
        input.get("session_id"),
        input.get("agent_id"),
        &edit.path,
        rel,
        dup,
        differ,
    );
    Ok(notes)
}

// 저장소 파일 목록. 너무 많으면 편집한 파일의 패키지 안만(패키지 밖 중복은 못 본다)
fn repo_files(root: &str, rel: &str) -> Vec<String> {
    let mut files = list_files(root);
    if files.len() > MAX_FILES {
        let pk = Packages::new(root).package_of(rel);
        if pk.is_empty() {
            files.truncate(MAX_FILES);
        } else {
            let prefix = format!("{pk}/");
            files.retain(|f| f.starts_with(&prefix));
        }
    }
    files
}

// C1: 어긋난 사본 수를 돌려준다
#[allow(clippy::too_many_arguments)]
fn copy_checks(
    edit: &Edit,
    own: &Entry,
    idx: &index::Index,
    flagged: &BTreeSet<i64>,
    siblings: &mut Siblings<'_>,
    state: &mut State,
    edited: &Edited<'_>,
    notes: &mut Vec<String>,
    log: &mut Vec<ShadowRecord>,
) -> Result<usize> {
    let rel = edit.rel.as_str();
    let mut results = copies::check_copies(siblings, rel, &edit.text, own, idx, &edit.added)?;
    results.extend(copies::check_regions(
        &edit.root,
        rel,
        &edit.path,
        &edit.text,
        &edit.added,
    )?);

    let mut differ = 0;
    for c in results {
        if matches!(c.status, Status::Differs | Status::Unresolved) {
            differ += 1;
        }

        // 꼴 알림(M1)이 같은 줄의 고칠 것을 이미 말했다
        if let Some(msg) = &c.notice
            && c.touched
            && !flagged.contains(&c.line)
            && state.first_time(&format!("c1:{rel}:{}:{}", c.line, c.status.code()))
        {
            notes.push(msg.clone());
        }
        if c.status != Status::Ok {
            let notice = if c.notice.is_some() { "N4" } else { "none" };
            let extra = vec![("status", Value::Str(c.status.code().to_owned()))];
            log.push(ShadowRecord::new(edited, "C1", notice, None, extra)?);
        }
    }
    Ok(differ)
}

// C2: 이 파일이 원본인 사본 목록
#[allow(clippy::too_many_arguments)]
fn source_checks(
    edit: &Edit,
    own: &Entry,
    idx: &index::Index,
    prev: Option<&Entry>,
    state: &mut State,
    edited: &Edited<'_>,
    notes: &mut Vec<String>,
    log: &mut Vec<ShadowRecord>,
) -> Result<()> {
    let rel = edit.rel.as_str();
    let touched = copies::canon_regions_touched(&edit.path, &edit.text, &edit.added, &edit.root)?;
    let prev_sets = prev.map(|p| p.sets.as_slice());
    for sc in copies::source_copies(rel, idx, prev_sets, own, !edit.added.is_empty(), &touched) {
        if !state.first_time(&format!("c2:{rel}:{}", sc.name)) {
            continue;
        }
        let n = sc.copies.len();
        let more = if n > 5 {
            format!(" +{}", n - 5)
        } else {
            String::new()
        };
        let head: Vec<&str> = sc.copies.iter().take(5).map(String::as_str).collect();
        notes.push(format!(
            "{rel}:{}: {} has {n} @copy-of copies: {}{more}. If this change altered what they copy, update them too \
             (python3 -I tools/sync-copies.py --apply where the repo has it).",
            sc.line,
            sc.name,
            head.join(", "),
        ));
        let extra = vec![
            ("name", Value::Str(sc.name.clone())),
            ("copies", Value::Int(n as i128)),
        ];
        log.push(ShadowRecord::new(edited, "C2", "N3", None, extra)?);
    }
    Ok(())
}

// H1: 새로 추가한 묶음의 겹침. 전부터 있던 겹침 수를 돌려준다
#[allow(clippy::too_many_arguments)]
fn duplicate_checks(
    edit: &Edit,
    own: &Entry,
    idx: &index::Index,
    prev: Option<&Entry>,
    state: &mut State,
    clock: &Clock,
    edited: &Edited<'_>,
    notes: &mut Vec<String>,
    log: &mut Vec<ShadowRecord>,
) -> Result<usize> {
    let rel = edit.rel.as_str();
    let prev_els: Option<BTreeSet<Vec<&str>>> = prev.map(|p| {
        p.sets
            .iter()
            .map(|s| s.members().into_iter().collect())
            .collect()
    });
    let mut packages = Packages::new(&edit.root);
    let mut judge: Option<Judge<'_>> = None;
    let mut dup_old = 0;

    for st in &own.sets {
        if clock.ms() > HARD_MS {
            break;
        }

        // python 은 judge 를 부를 때마다 설정 값을 읽는다: 틀린 값은 첫 묶음에서 끝난다
        let j = match &judge {
            Some(j) => j,
            None => judge.insert(Judge::new(rel, &edit.cfg)?),
        };
        let hits = j.hits(st, idx, &mut packages)?;
        let Some(hit) = first_max(&hits) else {
            continue;
        };

        // Only sets this edit added
        let members: Vec<&str> = st.members().into_iter().collect();
        let is_new = match &prev_els {
            Some(pe) => !pe.contains(&members),
            None => usize::try_from(st.line - 1).is_ok_and(|k| edit.added.contains(&k)),
        };
        if !is_new {
            dup_old += 1;
            continue;
        }

        // The notice, logged always and shown in on mode
        let mut msg = j.text_of(st, hit);
        if let Some(d) = &st.dup
            && !reason_ok(d)
        {
            msg.push_str(&format!(
                " @dup-ok at {rel}:{} has no reason (\"{d}\").",
                st.line
            ));
        }
        log.push(ShadowRecord::new(
            edited,
            "H1",
            hit.kind.code(),
            Some((st, hit)),
            Vec::new(),
        )?);
        let key = format!("h1:{rel}:{}:{}", hit.other_rel, hit.other_line);
        if edit.mode == Mode::On && !state.has_seen(&key) && state.under_notice_cap(rel)? {
            state.first_time(&key);
            state.count_notice(rel)?;
            notes.push(msg);
        }
    }
    Ok(dup_old)
}

// python max(hits, key=lambda h: h[7]): 같은 값이면 앞의 것
fn first_max(hits: &[Hit]) -> Option<&Hit> {
    let mut best: Option<&Hit> = None;
    for h in hits {
        if best.is_none_or(|b| h.j > b.j) {
            best = Some(h);
        }
    }
    best
}
