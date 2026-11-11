import { atom, read, update } from 'claude-code'
import type { Register, EngineInterface } from 'claude-code'

import type { QuiSnap } from '../types'

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

const S = { style: 'plain' as 'plain' | 'nerd', cwdName: '', cwdPath: '', model: '', effort: '' }

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


async function draw($: EngineInterface, e: any, columns: number | undefined, modes: readonly string[]) {
  const s = await read($, snap)
  if (!s) return null
  const nerd = S.style === 'nerd'
  const { Box, Text } = $.ui.resolve(e)
  let segs = bundles(s, nerd, S.cwdName)
  const sepText = nerd ? ' │ ' : ' · '
  const lead = modes.length ? `${modes.join(' & ')}${sepText}` : ''
  // 좁으면 뒤 묶음부터 통째로 뺀다. 푸터 왼쪽 문구가 쓰는 자리를 못 재므로 보수적으로 절반만 쓴다.
  const budget = columns ? Math.floor(columns * 0.5) : 10 ** 6
  const width = () => lead.length + segs.reduce((n, g) => n + g.len, 0) + sepText.length * Math.max(0, segs.length - 1)
  while (segs.length > 1 && width() > budget) segs = segs.slice(0, -1)
  if (!segs.length) return null
  return (
    <Box>
      {lead ? <Text>{lead}</Text> : null}
      {segs.flatMap((g, i) => [
        ...(i ? [<Text key={`s${i}`}>{sepText}</Text>] : []),
        ...g.parts.map((p, j) => (
          <Text key={`${i}.${j}`} color={p.color} bold={p.bold}>
            {p.text}
          </Text>
        )),
      ])}
    </Box>
  )
}


export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    S.style = await readStyle($, options.style)
    S.cwdPath = e.cwd
    S.cwdName = e.cwd.replace(/\/+$/, '').split('/').pop() || e.cwd
    S.model = modelName(await $.session.model())
    await patch($, { model: S.model })
    await readUsage($)
    await readGit($)
    $.clock.every(10_000, () => void readGit($))
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

  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (options.site === 'prompt-hint') return next(e)
    return (await draw($, e, e.viewport?.columns, e.props.modes)) ?? next(e)
  })

  // 실험: 힌트 줄 전체를 대체한다. 줄이 비는지 / 알약이 사라지는지는 실제 TUI 에서만 확인된다.
  on('ui.render', { component: 'PromptHint' }, async ($, e, next) => {
    if (options.site !== 'prompt-hint') return next(e)
    return (await draw($, e, e.viewport?.columns, [])) ?? next(e)
  })
}
