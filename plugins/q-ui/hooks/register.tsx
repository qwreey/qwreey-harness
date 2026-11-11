import { atom, read, update } from 'claude-code'
import type { Register, EngineInterface } from 'claude-code'

import type { QuiSnap } from '../types'
import { parseHint } from './hint'

// 모든 표시 값은 이 atom 하나에 모은다. 쓰면 읽는 그림이 다시 그려진다.
const snap = atom({ plugin: 'q-ui', key: 'snap' } as const, null)

// harness-status.py 의 ICON 과 같은 코드포인트(Nerd Font). 묶음마다 아이콘 하나.
const ICON = { dir: '', model: '', limit: '' }
const WARN = 70
const HOT = 90

const pc = (p: number) => (p < WARN ? 'green' : p < HOT ? 'yellow' : 'red')

// 모델 id(claude-opus-5-5, claude-sonnet-4-5[1m] 등)를 "Opus 5.5" 로. 모르는 모양이면 id 그대로.
const modelName = (id: string) => {
  const m = /^claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?(?:\[.*\])?$/.exec(id)
  if (!m) return id
  const fam = m[1] ?? ''
  return `${fam.charAt(0).toUpperCase()}${fam.slice(1)} ${m[2]}${m[3] ? `.${m[3]}` : ''}`
}

const fmtLeft = (iso: string | null) => {
  const sec = iso ? (Date.parse(iso) - Date.now()) / 1000 : NaN
  if (!(sec > 0)) return ''
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return d ? `${d}d${h}h` : h ? `${h}h${String(m).padStart(2, '0')}m` : `${m}m`
}

type Seg = { len: number; parts: { color?: string; bold?: boolean; text: string }[] }

// 묶음 목록. statusline 과 같은 순서·규칙(묶음마다 아이콘 하나, 흐린 색 없음).
const bundles = (s: QuiSnap, nerd: boolean, cwdName: string): Seg[] => {
  const out: Seg[] = []
  const add = (parts: Seg['parts']) => {
    const kept = parts.filter(p => p.text)
    if (kept.length) out.push({ len: kept.map(p => p.text).join('').length, parts: kept })
  }
  if (cwdName) {
    add([
      { bold: true, text: (nerd ? `${ICON.dir} ` : '') + cwdName },
      ...(s.branch ? [{ color: 'magenta', text: `:${s.branch}${s.dirty ? '*' : ''}` }] : []),
    ])
  }
  if (s.model) {
    add([
      { color: 'cyan', text: [nerd ? ICON.model : '', s.model, s.effort].filter(Boolean).join(' ') },
      ...(s.ctxPct === null
        ? []
        : [{ color: pc(s.ctxPct), text: ` ${nerd ? '' : 'ctx '}${Math.round(s.ctxPct)}%` }]),
    ])
  }
  if (s.limits.length) {
    const left = s.limits.map(l => fmtLeft(l.resetsAt)).filter(Boolean)
    const parts: Seg['parts'] = s.limits.map((l, i) => ({
      color: pc(l.pct),
      text: `${i ? ' ' : nerd ? `${ICON.limit} ` : 'limit '}${l.label} ${Math.round(l.pct)}%`,
    }))
    if (left.length) parts.push({ text: ` ${nerd ? '' : 'reset '}${left.sort()[0]}` })
    add(parts)
  }
  if (s.usd !== null) add([{ text: `$${s.usd.toFixed(2)}` }]) // $ 가 표지라 아이콘 없음
  return out
}

const readStyle = async ($: EngineInterface, option: unknown) => {
  if (option === 'plain' || option === 'nerd') return option
  let v = await $.env.get('HARNESS_STATUSLINE_STYLE')
  if (!v) {
    // 환경 변수에 없으면 사용자 harness.env 에서(statusline 과 같은 키).
    const home = await $.env.get('HOME')
    try {
      const raw = await $.fs.read(`${home}/.claude/harness.env`)
      const m = /^\s*HARNESS_STATUSLINE_STYLE\s*=\s*["']?(\w+)/m.exec(typeof raw === 'string' ? raw : '')
      v = m?.[1]
    } catch {
      // 파일이 없거나 읽기 거부 — 기본 plain.
    }
  }
  return v?.trim().toLowerCase() === 'nerd' ? 'nerd' : 'plain'
}

const S = {
  style: 'plain' as 'plain' | 'nerd', cwdName: '', cwdPath: '', model: '', effort: '',
  site: 'prompt-hint' as string, hint: 'merge' as string,
}

// statusline 이 이 파일이 새것이면 자기 줄을 숨긴다(away 표시와 limits.json 기록은 남긴다).
// 갱신이 멎으면(mod 가 꺼지거나 세션이 죽으면) 90초 뒤 statusline 이 저절로 돌아온다.
const MARKER_EVERY = 30_000
async function writeMarker($: EngineInterface) {
  try {
    const sid = await $.session.id()
    const dir = `${(await $.env.get('TMPDIR')) || '/tmp'}/claude-subagent-slots`
    await $.fs.write(`${dir}/${sid}.qui-mod`, String(Date.now()))
  } catch {
    // 못 쓰면 statusline 이 그대로 남는다(중복이지만 정보는 잃지 않는다).
  }
}

async function patch($: EngineInterface, p: Partial<QuiSnap>) {
    await update($, snap, (old): QuiSnap => {
      const next = {
        model: '', effort: '', ctxPct: null, usd: null, limits: [], branch: '', dirty: false,
        ...(old ?? {}),
        ...p,
      }
      // 같으면 같은 값을 돌려줘 불필요한 다시 그리기를 줄인다.
      return old && JSON.stringify(old) === JSON.stringify(next) ? old : next
    })
  }

async function readUsage($: EngineInterface) {
    const u = await $.session.usage()
    await patch($, {
      ctxPct: u.context.percent ?? null,
      usd: u.cost ? u.cost.usd : null,
      limits: u.rateLimits.flatMap(r =>
        r.kind === 'five_hour' || r.kind === 'seven_day'
          ? [{ label: r.kind === 'five_hour' ? '5h' : 'wk', pct: r.percentUsed, resetsAt: r.resetsAt ?? null }]
          : [],
      ),
    })
  }

async function readGit($: EngineInterface) {
    // 느릴 수 있어 session.start 의 타이머(10초)에서만 부른다. 그리는 쪽은 캐시만 읽는다.
    try {
      const b = await $.process.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], { cwd: S.cwdPath, timeoutMs: 2000 })
      if (b.exitCode !== 0) return patch($, { branch: '', dirty: false })
      const d = await $.process.run(['git', 'status', '--porcelain', '-uno'], { cwd: S.cwdPath, timeoutMs: 2000 })
      return patch($, { branch: b.stdout.trim(), dirty: d.exitCode === 0 && d.stdout.trim() !== '' })
    } catch {
      return patch($, { branch: '', dirty: false })
    }
  }


type Part = { color?: string; bold?: boolean; text: string }

const render = (ui: ReturnType<EngineInterface['ui']['resolve']>, parts: Part[][], seps: string[]) => {
  const { Box, Text } = ui
  return (
    <Box>
      {parts.flatMap((g, i) => [
        ...(i ? [<Text key={`s${i}`}>{seps[i - 1]}</Text>] : []),
        ...g.map((p, j) => (
          <Text key={`${i}.${j}`} color={p.color} bold={p.bold}>
            {p.text}
          </Text>
        )),
      ])}
    </Box>
  )
}

/** 묶음들을 폭에 맞춰 뒤에서부터 통째로 뺀다(첫 묶음은 남긴다). */
const fitSegs = (segs: Seg[], extra: number, sepLen: number, budget: number) => {
  const width = () => extra + segs.reduce((n, g) => n + g.len, 0) + sepLen * Math.max(0, segs.length - 1)
  while (segs.length > 1 && width() > budget) segs = segs.slice(0, -1)
  return segs
}

/** SessionMode 자리(site=session-mode): 이전 시제품과 같다. 모드 라벨 + 묶음. */
async function drawMode($: EngineInterface, e: any, columns: number | undefined, modes: readonly string[]) {
  const s = await read($, snap)
  if (!s) return null
  const nerd = S.style === 'nerd'
  const sepText = nerd ? ' │ ' : ' · '
  const lead = modes.length ? `${modes.join(' & ')}${sepText}` : ''
  const budget = columns ? Math.floor(columns * 0.5) : 10 ** 6
  const segs = fitSegs(bundles(s, nerd, S.cwdName), lead.length, sepText.length, budget)
  if (!segs.length) return null
  const ui = $.ui.resolve(e)
  return render(ui, [...(lead ? [[{ text: lead.slice(0, -sepText.length) }]] : []), ...segs.map(g => g.parts)], Array<string>(segs.length + 1).fill(sepText))
}

/** 힌트 줄: `모드 · 프로젝트 │ 모델 │ 한도 │ 비용 · N agents`. 좁으면 비용부터 뺀다(agents 는 남긴다). */
async function drawHint($: EngineInterface, e: any, columns: number | undefined, mode: string, agents: number, rest: string) {
  const s = await read($, snap)
  if (!s) return null
  const nerd = S.style === 'nerd'
  const sepText = nerd ? ' │ ' : ' · '
  const dot = ' · '
  const agentText = agents ? `${agents} agent${agents > 1 ? 's' : ''}` : ''
  const budget = columns ? Math.max(20, columns - 4) : 10 ** 6
  const extra = (mode ? mode.length + dot.length : 0) + (agentText ? agentText.length + dot.length : 0) + (rest ? rest.length + dot.length : 0)
  const segs = fitSegs(bundles(s, nerd, S.cwdName), extra, sepText.length, budget)
  const ui = $.ui.resolve(e)
  const groups: Part[][] = []
  const seps: string[] = []
  const push = (g: Part[], sep: string) => { if (groups.length) seps.push(sep); groups.push(g) }
  if (mode) push([{ color: 'magenta', bold: true, text: mode }], dot)
  segs.forEach((g, i) => push(g.parts, i === 0 && mode ? dot : sepText))
  if (agentText) push([{ color: 'blue', text: agentText }], dot)
  if (rest) push([{ text: rest }], dot)
  return groups.length ? render(ui, groups, seps) : null
}

/** 엔진 힌트 뒤에 붙이는 dim 문자열(tail). 색 없는 한 줄이라 묶음만 잇는다. */
async function tailText($: EngineInterface, columns: number | undefined, used: number) {
  const s = await read($, snap)
  if (!s) return undefined
  const sepText = S.style === 'nerd' ? ' │ ' : ' · '
  const segs = fitSegs(bundles(s, S.style === 'nerd', S.cwdName), used + 3, sepText.length, columns ? columns - 4 : 10 ** 6)
  return segs.length ? segs.map(g => g.parts.map(p => p.text).join('')).join(sepText) : undefined
}

export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    S.style = await readStyle($, options.style)
    S.site = String(options.site ?? 'prompt-hint')
    S.hint = String(options.hint ?? 'merge')
    S.cwdPath = e.cwd
    S.cwdName = e.cwd.replace(/\/+$/, '').split('/').pop() || e.cwd
    S.model = modelName(await $.session.model())
    await patch($, { model: S.model })
    await readUsage($)
    await readGit($)
    $.clock.every(10_000, () => void readGit($))
    if (S.site !== 'off') {
      await writeMarker($)
      $.clock.every(MARKER_EVERY, () => void writeMarker($))
    }
    return next(e)
  })

  // 한도·컨텍스트·비용이 움직일 때만 온다(문서: 한도는 1%p 단위).
  on('session.measure', async ($, e, next) => {
    await readUsage($)
    return next(e)
  })

  // effort 는 $ 에서 직접 읽을 수 없다: 모델 요청이 나갈 때 e.effort 로 본다(첫 요청 전에는 비어 있음).
  on('turn.step', async function* ($, e, next) {
    if (!e.agentId) {
      const m = modelName(e.model)
      const f = e.effort === undefined ? '' : String(e.effort)
      if (m !== S.model || f !== S.effort) {
        S.model = m
        S.effort = f
        await patch($, { model: m, effort: f })
      }
    }
    yield* next(e)
  })

  // site=session-mode 에서만 오른쪽 모드 표지 자리를 쓴다. 기본(prompt-hint)에서는 엔진 원래 표시를 그대로 둔다.
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (S.site !== 'session-mode') return next(e)
    return (await drawMode($, e, e.viewport?.columns, e.props.modes)) ?? next(e)
  })

  // 힌트 줄(auto mode 줄 + "← N agent" 알약이 있는 줄).
  //  - hint=keep: 엔진 줄은 그대로(알약이 살아 있다), 묶음만 dim tail 로 덧붙인다.
  //  - hint=merge: 한가할 때만 한 줄로 합친다. 작업 중·권한 대기·입력 중 등 엔진 안내가 중요하면 엔진 줄 + tail.
  //  - hint=replace: 항상 자기 줄. 중요한 안내가 있으면 그 글자를 줄 끝에 옮겨 적는다(알약은 못 누른다).
  on('ui.render', { component: 'PromptHint' }, async ($, e, next) => {
    if (S.site !== 'prompt-hint') return next(e)
    const columns = e.viewport?.columns
    const { hint, isWorking, tail } = e.props
    const info = parseHint(hint)
    const idle = info.idle && !isWorking
    if (S.hint === 'replace' || (S.hint === 'merge' && idle)) {
      const rest = idle ? '' : hint.replace(/\s+/g, ' ').trim()
      const tree = await drawHint($, e, columns, info.mode, info.agents, rest)
      return tree ?? next(e)
    }
    // keep, 또는 merge 인데 엔진 안내가 중요한 때: 엔진 줄 + tail.
    if (S.hint === 'keep' || S.hint === 'merge') {
      const t = await tailText($, columns, hint.length + (tail ? tail.length + 1 : 0))
      return next(t ? { ...e, props: { ...e.props, tail: [tail, t].filter(Boolean).join(' ') } } : e)
    }
    return next(e)
  })
}
