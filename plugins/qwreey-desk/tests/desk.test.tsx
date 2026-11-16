import { expect, mock, test } from 'claude-code/testing'
import type { Engine, Mounted } from 'claude-code/testing'
import type { On } from 'claude-code'

import { cells, laidOut, markdownRows, wrap } from '../hooks/layout'
import { decisionDetail } from '../hooks/views'
import type { Do } from '../hooks/views'

const TOOL = 'mcp__qwreey-desk__desk'
const STORE_KEY = 'project:/p'

const BAND = {
  plugin: 'qwreey-desk',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 8, bodyColumns: 40, scroll: { offset: 0, bodyRows: 8 }, view: {} },
  viewport: { columns: 45, rows: 80, isFullscreen: false },
} as const

// An inline pane in a terminal `columns` wide: the frame takes a cell each side.
const pane = (columns: number, rows = 40, placement: 'inline' | 'dock' = 'inline', body = columns - 2) =>
  ({
    plugin: 'qwreey-desk',
    component: 'Pane',
    requestId: 'desk',
    props: {
      title: '책상',
      isFocused: true,
      bodyColumns: body,
      placement,
      scroll: { offset: 0, bodyRows: rows },
      view: {},
    },
    viewport: { columns, rows: 80, isFullscreen: placement === 'dock' },
  }) as const

const PANE = pane(45)

const SURFACES = ['terminal', 'desktop', 'vscode', 'mobile'] as const

type Submitted = { text: string; context?: readonly string[] }

// Nothing sits beneath the plugin: these hooks stand for the engine.
const engine = (on: On, store: Record<string, unknown> = {}) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  // The store in memory, kept here so a test reads what the plugin wrote.
  const kept = new Map<string, unknown>(Object.entries(store))
  // Every write the desk makes, the store's counted and the session state's by key.
  const writes = { store: 0, state: [] as string[] }
  on('store.get', (_, e) => ({ value: kept.get(e.key) }))
  on('store.set', (_, e) => {
    writes.store += 1
    kept.set(e.key, JSON.parse(JSON.stringify(e.value)))
    return { value: undefined }
  })
  on('state.set', (_, e, next) => {
    writes.state.push(e.key)
    return next(e)
  })
  // What the desk last persisted for /p (it mirrors the session's state).
  const stored = () => (kept.get(STORE_KEY) as { shape: string; value: any } | undefined)?.value
  const submitted: Submitted[] = []
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/p' }))
  on('tool.register', () => ({ value: { tool: TOOL } }))
  on('command.register', () => ({ value: { command: 'desk' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('prompt.submit', (_, e) => {
    submitted.push({ text: e.text, context: e.context })
    return { text: e.text, context: e.context }
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  return { clock, submitted, kept, stored, writes }
}

const start = ($: Engine) => $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })

const desk = (input: Record<string, unknown>) => ({ tool: TOOL, ...input }) as Parameters<Engine['tool']['call']>[0]

const seed = async ($: Engine) => {
  await $.tool.call(
    desk({
      action: 'set_plan',
      steps: ['타입 쓰기', { text: '밴드 그리기', detail: '프롬프트 위 두 줄' }, { text: '패널 그리기', detail: '탭, 타임라인, 스크롤' }],
    }),
  )
  await $.tool.call(desk({ action: 'update_step', id: 'S1', state: 'doing' }))
  await $.tool.call(
    desk({
      action: 'add_decision',
      question: '밴드는 몇 줄까지?',
      context: '폰 화면 **45칸**에서 본다.',
      options: [
        { key: 'a', label: '한 줄', why: '공간 아낌' },
        { key: 'b', label: '두 줄', why: '다음 단계가 보임' },
      ],
      recommended: 'b',
      reason: '다음 할 일이 늘 보여야 함',
    }),
  )
  await $.tool.call(desk({ action: 'add_decision', question: '책상 저장은 프로젝트별?', options: [{ key: 'a', label: '예' }] }))
}

// ---- a text picture of a drawn tree -------------------------------------------
// Lays the tree out the way the terminal does for the props the desk uses
// (column and row boxes, fixed widths, gaps, heights, truncation and
// wrapping), so a test can read rows and cell widths.

// A drawn element: its tag, its props, its children beside them.
type El = { type: string; props?: Record<string, any>; children?: unknown }

declare const console: { log: (...items: unknown[]) => void }

const kids = (el: El): unknown[] => {
  const c = el.children
  return c === undefined || c === null || c === false
    ? []
    : Array.isArray(c)
      ? c.flat(Infinity).filter(x => x !== null && x !== false && x !== undefined)
      : [c]
}

const textOf = (node: unknown): string => {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (!node || typeof node !== 'object') return ''
  return kids(node as El).map(textOf).join('')
}

const pad = (line: string, width: number) => line + ' '.repeat(Math.max(0, width - cells(line)))
const cut = (line: string, width: number) => {
  let out = ''
  for (const ch of line) {
    if (cells(out + ch) > width) break
    out += ch
  }
  return out
}

const draw = (node: unknown, width: number): string[] => {
  if (typeof node === 'string' || typeof node === 'number') return [cut(String(node), width)]
  if (!node || typeof node !== 'object') return []
  const el = node as El
  const p = el.props ?? {}
  switch (el.type) {
    case 'Text': {
      const text = textOf(el)
      return p.wrap === 'wrap' ? wrap(text, width) : [cut(text, width)]
    }
    case 'Button': {
      const label = kids(el).length > 0 ? kids(el).map(textOf).join('') : String(p.label ?? '')
      const text = p.plain ? `${p.hotkey ? `${p.hotkey}: ` : ''}${label}` : `[ ${label} ]`
      return [cut(text, width)]
    }
    case 'Markdown':
      return String(p.text ?? '')
        .split('\n')
        .flatMap(l => wrap(l, width))
    case 'Input': {
      const value = String(p.value ?? '') || String(p.placeholder ?? '')
      const lines = value.split('\n').flatMap(l => wrap(l, width - 2))
      return Array.from({ length: Number(p.rows ?? 1) }, (_, i) => `|${pad(lines[i] ?? '', width - 2)}|`)
    }
    case 'Box': {
      const own = typeof p.width === 'number' ? Math.min(p.width, width) : width
      const gap = typeof p.gap === 'number' ? p.gap : 0
      const children = kids(el)
      let lines: string[]
      if (p.flexDirection === 'row') {
        const fixed = children.map(c =>
          c && typeof c === 'object' && typeof (c as El).props?.width === 'number' ? ((c as El).props?.width as number) : undefined,
        )
        const rest = own - fixed.reduce((s: number, w) => s + (w ?? 0), 0) - gap * Math.max(0, children.length - 1)
        const flexible = fixed.filter(w => w === undefined).length
        const parts = children.map((c, i) => draw(c, fixed[i] ?? Math.max(1, Math.floor(rest / Math.max(1, flexible)))))
        const widths = parts.map((part, i) => fixed[i] ?? Math.max(0, ...part.map(cells)))
        const height = Math.max(0, ...parts.map(part => part.length))
        lines = Array.from({ length: height }, (_, r) => parts.map((part, i) => pad(part[r] ?? '', widths[i] ?? 0)).join(' '.repeat(gap)))
      } else {
        lines = []
        children.forEach((c, i) => {
          if (i > 0) for (let g = 0; g < gap; g += 1) lines.push('')
          lines.push(...draw(c, own))
        })
      }
      if (typeof p.minHeight === 'number') while (lines.length < p.minHeight) lines.push('')
      if (typeof p.height === 'number') {
        lines = lines.slice(0, p.height)
        while (lines.length < p.height) lines.push('')
      }
      return lines.map(l => cut(l, own).trimEnd())
    }
    default:
      return []
  }
}

const screen = async (ui: { drawn: () => Promise<unknown> }, columns: number) => draw(await ui.drawn(), columns)

const show = (title: string, lines: readonly string[], columns: number) =>
  console.log([`--- ${title} (${columns} cells) ---`, ...lines.map(l => `|${pad(l, columns)}|`)].join('\n'))

/** A desk field as drawn: its key is its name, then the revision each Enter moves. */
const fieldOf = async (ui: Mounted<'terminal', 'Pane'>, name: string) =>
  (await ui.findAll({ type: 'Input' })).find(e => e.key?.startsWith(`${name}~`))

/** A change or an Enter in a desk field, under the key it is drawn with now. */
const typeIn = async (ui: Mounted<'terminal', 'Pane'>, name: string, text: string, kind: 'change' | 'submit') =>
  ui.input({ key: (await fieldOf(ui, name))?.key ?? `${name}~?`, text, kind })

/** The scrollbar column of a drawn list: the last cell of each row. */
const barOf = (lines: readonly string[], columns: number) => lines.map(l => (cells(l) === columns ? [...l].at(-1) : ' '))

// ---- tests --------------------------------------------------------------------

test('the tool actions change the desk and persist it', async ($, on) => {
  const { stored, kept } = engine(on)
  await start($)
  await seed($)

  const answered = await $.tool.call(desk({ action: 'answer_decision', id: 'D2', text: '응, 프로젝트별로' }))
  expect(answered.result).toBe('D2 답 기록 (대기 1)')
  await $.tool.call(desk({ action: 'memo', id: 'd1', text: '두 줄이면 좁을까' }))
  await $.tool.call(desk({ action: 'update_step', id: 'S1', state: 'done' }))
  await $.tool.call(desk({ action: 'update_step', id: 'S2', state: 'doing', text: '밴드는 두 줄로' }))
  await $.tool.call(desk({ action: 'note', text: '리뷰 끝' }))
  const deferred = await $.tool.call(desk({ action: 'defer_decision', id: 'D9' }))
  expect(deferred.result).toBe('D9: 없는 결정')

  const d = stored()
  expect(d.decisions.map((x: any) => [x.id, x.status])).toEqual([
    ['D1', 'open'],
    ['D2', 'answered'],
  ])
  expect(d.decisions[1].answer).toBe('응, 프로젝트별로')
  // A memo the model records is the person's comment, which it has already.
  expect(d.decisions[0].comments).toEqual([{ id: 'c1', by: 'user', text: '두 줄이면 좁을까', at: 1_000_000, sent: true }])
  expect(d.plan.map((s: any) => s.state)).toEqual(['done', 'doing', 'todo'])
  expect(d.plan.map((s: any) => s.detail)).toEqual([undefined, '밴드는 두 줄로', '탭, 타임라인, 스크롤'])
  expect(d.plan[0].endedAt).toBe(1_000_000)
  expect(d.log.map((l: any) => l.text)).toEqual(['D2 답: 응, 프로젝트별로', 'S1 타입 쓰기', '리뷰 끝'])

  // Sending the plan again (here to add a detail) keeps the progress.
  await $.tool.call(desk({ action: 'set_plan', steps: [{ text: '타입 쓰기', detail: '끝난 일' }, '밴드 그리기', '패널 그리기', '정리'] }))
  expect(stored().plan.map((s: any) => [s.id, s.state, s.detail])).toEqual([
    ['S1', 'done', '끝난 일'],
    ['S2', 'doing', '밴드는 두 줄로'],
    ['S3', 'todo', '탭, 타임라인, 스크롤'],
    ['S4', 'todo', undefined],
  ])

  expect((kept.get(STORE_KEY) as { shape: string }).shape).toBe('desk-1')
})

test('a chat line answers a decision and tells the model', async ($, on) => {
  const { submitted, stored } = engine(on)
  await start($)
  await seed($)

  await $.prompt.submit({ text: 'D1: b 로 가자\nD2 메모: 나중에 다시', wait: false, origin: { kind: 'composer' } })
  const d = stored()
  expect(d.decisions[0].status).toBe('answered')
  expect(d.decisions[0].answer).toBe('b 로 가자')
  expect(d.decisions[1].status).toBe('open')
  expect(d.decisions[1].comments?.map((c: any) => [c.by, c.text, c.sent])).toEqual([['user', '나중에 다시', true]])
  expect(submitted[0]?.context?.[0]).toContain('= option b) 두 줄')

  // Another session's message is not the person's answer.
  await $.prompt.submit({ text: 'D2: a', wait: false, origin: { kind: 'peer' } })
  expect(stored().decisions[1].status).toBe('open')
})

test('the band fits a phone width and hides when there is nothing', async ($, on) => {
  engine(on)
  await start($)
  for (const surface of ['terminal', 'desktop'] as const) {
    const empty = await $.ui.mount({ ...BAND, surface })
    expect((await empty.find({ type: 'Text' }))?.text).toBe('engine')
    await empty.unmount()
  }
  await seed($)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /결정/ }))?.text).toBe('결정 2')
    expect((await ui.find({ type: 'Text', text: /지금/ }))?.text).toBe('지금: 타입 쓰기')
    expect(await ui.find({ type: 'Button', key: 'open' })).toBeDefined()
    expect((await ui.findAll({ type: 'Text' })).length).toBeLessThanOrEqual(3)
    // The button stands first, where the counts cannot move it.
    expect((await screen(ui, 40))[0]).toMatch(/^d: 책상 열기/)
    await ui.unmount()
  }
})

test('the pane has three tabs and opens a decision', async ($, on) => {
  const { submitted, stored } = engine(on)
  const session = mock.session(on)
  await start($)
  await seed($)
  await $.tool.call(desk({ action: 'answer_decision', id: 'D2', text: 'a' }))

  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...PANE, surface })
    // 답을 기다림: the waiting decision, a rule, the answered one under it.
    expect(await ui.find({ type: 'Button', key: 'tab-wait' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^── 끝난 결정 1 ─+$/ })).toBeDefined()
    expect((await ui.find({ type: 'Button', key: 'dec-D2' }))?.text).toContain('책상 저장은')

    await ui.press({ key: 'tab-tasks' })
    expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'step-S1' })).toBeDefined()
    await ui.press({ key: 'tab-away' })
    expect(await ui.find({ type: 'Text', text: /D2 답: a/ })).toBeDefined()
    await ui.press({ key: 'tab-wait' })

    // The detail view: context, options with the recommended one, memo.
    await ui.press({ key: 'dec-D1' })
    // The context's markdown is drawn row by row, its bold kept.
    const bold = (await ui.findAll({ type: 'Text', text: /45칸/ })).find(t => t.text === '45칸')
    expect(bold?.props.bold).toBe(true)
    expect((await ui.find({ type: 'Button', key: 'opt-b' }))?.text).toContain('★권장')
    expect(await ui.find({ type: 'Text', text: /다음 할 일이 늘 보여야 함/ })).toBeDefined()
    if (surface === 'mobile') {
      expect(await ui.find({ type: 'Text', text: /D1 코멘트/ })).toBeDefined()
    } else {
      expect((await ui.findAll({ type: 'Input' })).find(e => e.key?.startsWith('comment-D1~'))).toBeDefined()
    }
    await ui.press({ key: 'back' })
    expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeDefined()
    await ui.unmount()
  }

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  await typeIn(ui, 'comment-D1', '좁으면 한 줄', 'change')
  expect(stored().decisions[0].draft).toBe('좁으면 한 줄')
  await ui.press({ key: 'discuss' })
  expect(submitted.at(-1)?.text).toBe('D1 더 논의: 밴드는 몇 줄까지?\n내 코멘트: 좁으면 한 줄')
  expect(JSON.stringify(session.appended().at(-1)?.message.content)).toContain('Recommended b')
  // The draft went with the request to talk, posted and sent: nothing waits in the outbox.
  expect(stored().decisions[0].draft).toBeUndefined()
  expect(stored().decisions[0].comments?.map((c: any) => [c.text, c.sent])).toEqual([['좁으면 한 줄', true]])
  await ui.unmount()
})

test('picks and comments wait in the outbox and go out as one prompt', async ($, on) => {
  const { submitted, stored } = engine(on)
  const session = mock.session(on)
  await start($)
  await seed($)
  await $.tool.call(desk({ action: 'add_decision', question: '탭 이름은?', options: [{ key: 'a', label: '그대로' }] }))
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Button', key: 'outbox' })).toBeUndefined()

  // Pressing an option picks it; nothing is sent.
  await ui.press({ key: 'dec-D1' })
  await ui.press({ key: 'opt-b' })
  expect(submitted).toEqual([])
  expect(stored().decisions[0].status).toBe('open')
  expect(stored().decisions[0].pick).toBe('b')
  expect((await ui.find({ type: 'Button', key: 'opt-b' }))?.text).toContain('✓ 두 줄')
  expect(await ui.find({ type: 'Text', text: /선택: b\) 두 줄 \(보내기 전/ })).toBeDefined()
  // Pressed again it is unpicked, and picked once more.
  await ui.press({ key: 'opt-b' })
  expect(stored().decisions[0].pick).toBeUndefined()
  await ui.press({ key: 'opt-b' })
  await ui.press({ key: 'back' })

  await ui.press({ key: 'dec-D2' })
  await typeIn(ui, 'comment-D2', 'D1 의 두 줄과 합칠 수 있을 듯', 'submit')
  await ui.press({ key: 'back' })
  await ui.press({ key: 'dec-D3' })
  await ui.press({ key: 'opt-a' })
  await ui.press({ key: 'back' })

  // The list says what waits; the row under the tabs opens the outbox.
  expect(await ui.find({ type: 'Text', text: '● 선택 b (보내기 전)' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '✎ 코멘트 (보내기 전)' })).toBeDefined()
  expect((await ui.find({ type: 'Button', key: 'outbox' }))?.props.hotkey).toBe('0')
  expect((await ui.find({ type: 'Button', key: 'outbox' }))?.text).toBe('보내기 (3) ▸')
  show('the list with drafts', (await screen(ui, 43)).slice(0, 14), 43)

  await ui.press({ key: 'outbox' })
  expect(await ui.find({ type: 'Text', text: '보낼 것 3개 · 전송하면 한 번에 보냄' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '→ b) 두 줄' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '코멘트: D1 의 두 줄과 합칠 수 있을 듯' })).toBeDefined()
  await ui.press({ key: 'cancel-D3' })
  expect(stored().decisions[2].pick).toBeUndefined()
  await typeIn(ui, 'outbox-note', 'D1 과 D2 는 같이 보자', 'submit')
  show('the outbox', await screen(ui, 43), 43)

  await ui.press({ key: 'send' })
  expect(submitted.map(s => s.text)).toEqual(['D1 → b\nD2 코멘트: D1 의 두 줄과 합칠 수 있을 듯\n전체 메모: D1 과 D2 는 같이 보자'])
  const d = stored()
  expect(d.decisions.map((x: any) => [x.id, x.status, x.answer, x.pick])).toEqual([
    ['D1', 'answered', 'b', undefined],
    ['D2', 'open', undefined, undefined],
    ['D3', 'open', undefined, undefined],
  ])
  expect(d.decisions[1].comments?.map((c: any) => [c.by, c.text, c.sent])).toEqual([['user', 'D1 의 두 줄과 합칠 수 있을 듯', true]])
  expect(d.outboxNote).toBeUndefined()
  expect(JSON.stringify(session.appended().at(-1)?.message.content)).toContain('do not call answer_decision')
  // Back on the list, the outbox empty.
  expect(await ui.find({ type: 'Button', key: 'outbox' })).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeDefined()
  await ui.unmount()
})

test('drafts kept in the store come back after a restart', async ($, on) => {
  const value = {
    decisions: [
      { id: 'D1', question: '밴드는 몇 줄까지?', options: [{ key: 'b', label: '두 줄' }], status: 'open', createdAt: 1, pick: 'b' },
      { id: 'D2', question: '책상 저장은?', options: [], status: 'open', createdAt: 2, memo: '합칠 듯', memoAt: 3, memoPending: true },
    ],
    plan: [],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 3,
    outboxNote: '둘 다 같이',
  }
  const { submitted } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Button', key: 'outbox' }))?.text).toBe('보내기 (2) ▸')
  await ui.press({ key: 'outbox' })
  expect((await fieldOf(ui, 'outbox-note'))?.props.value).toBe('둘 다 같이')
  await ui.press({ key: 'send' })
  // The memo waiting under the older layout went as D2's comment.
  expect(submitted.at(-1)?.text).toBe('D1 → b\nD2 코멘트: 합칠 듯\n전체 메모: 둘 다 같이')
  await ui.unmount()
})

test('a comment posts on Enter to the thread, the box saving the draft until then', async ($, on) => {
  const { stored, clock } = engine(on)
  await start($)
  await seed($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  const KEYS = 'Enter 달기 · Shift+Enter 줄바꿈'
  expect((await ui.find({ type: 'Text', text: /^새 코멘트/ }))?.text).toBe(`새 코멘트 · ${KEYS}`)
  // The engine's own hint beside a focused field is only its return glyph.
  expect((await fieldOf(ui, 'comment-D1'))?.props.submitLabel).toBe('')
  // A pane 40 rows tall: the field is 8 rows, whatever it holds.
  expect((await fieldOf(ui, 'comment-D1'))?.props.rows).toBe(8)

  // Typed, the draft is kept and says so; nothing waits in the outbox yet.
  await typeIn(ui, 'comment-D1', '엔터로', 'change')
  expect(stored().decisions[0].draft).toBe('엔터로')
  expect((await ui.find({ type: 'Text', text: /^새 코멘트/ }))?.text).toBe(`새 코멘트 · 저장됨 방금 · ${KEYS}`)
  expect(await ui.find({ type: 'Button', key: 'outbox' })).toBeUndefined()

  // Enter puts it on the thread, waiting to be sent, and empties the box for
  // the next under a new key (the terminal empties the old one's text itself).
  const before = (await fieldOf(ui, 'comment-D1'))?.key
  expect(before).toBe('comment-D1~0')
  await typeIn(ui, 'comment-D1', '엔터로 달기', 'submit')
  const d = stored().decisions[0]
  expect(d.draft).toBeUndefined()
  expect(d.comments).toEqual([{ id: 'c1', by: 'user', text: '엔터로 달기', at: 1_000_000 }])
  expect((await fieldOf(ui, 'comment-D1'))?.key).not.toBe(before)
  expect((await fieldOf(ui, 'comment-D1'))?.props.value).toBe('')
  expect((await ui.find({ type: 'Text', text: /^새 코멘트/ }))?.text).toBe(`새 코멘트 · ${KEYS}`)
  expect(await ui.find({ type: 'Text', text: /^── 코멘트 1 ─+$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '나 · 방금 · 보내기 전' })).toBeDefined()
  expect((await ui.find({ type: 'Button', key: 'outbox' }))?.text).toBe('보내기 (1)')
  await clock.advance(5 * 60_000)
  await ui.redraw()
  expect(await ui.find({ type: 'Text', text: '나 · 5분 전 · 보내기 전' })).toBeDefined()

  // A real clear of a draft still clears it.
  await typeIn(ui, 'comment-D1', '다시 쓴 글', 'change')
  await typeIn(ui, 'comment-D1', '', 'change')
  expect(stored().decisions[0].draft).toBeUndefined()

  const longer = Array.from({ length: 12 }, (_, i) => `${i + 1}번째 줄`).join('\n')
  await typeIn(ui, 'comment-D1', longer, 'change')
  expect((await fieldOf(ui, 'comment-D1'))?.props.rows).toBe(8)
  expect((await ui.find({ type: 'Text', text: /줄씩 보임/ }))?.text).toBe(`새 코멘트 · 저장됨 방금 · ${KEYS} · 12줄 중 8줄씩 보임`)
  await ui.unmount()
})

test('a comment alone goes out without an answer, the decision staying open', async ($, on) => {
  const { stored, submitted } = engine(on)
  const session = mock.session(on)
  await start($)
  await seed($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  await typeIn(ui, 'comment-D1', '두 줄이면\n폰에서 좁지 않나', 'submit')
  await ui.press({ key: 'back' })
  await ui.press({ key: 'outbox' })
  await ui.press({ key: 'send' })
  expect(submitted.map(s => s.text)).toEqual(['D1 코멘트: 두 줄이면\n폰에서 좁지 않나'])
  const d = stored().decisions[0]
  expect(d.status).toBe('open')
  expect(d.answer).toBeUndefined()
  expect(d.comments?.map((c: any) => c.sent)).toEqual([true])
  // The hidden note names the decision, quotes the comment and asks for a
  // reply on the desk, the chat kept to a line.
  const note = JSON.stringify(session.appended().at(-1)?.message.content)
  expect(note).toContain('밴드는 몇 줄까지?')
  expect(note).toContain('두 줄이면 폰에서 좁지 않나')
  expect(note).toContain('The decision stays open.')
  expect(note).toContain('Reply on the desk with the desk action comment (id D1)')
  expect(note).toContain('revise_decision')
  expect(note).toContain('keep the chat to one line')
  // With a pick too, both go and the pick answers it.
  await ui.press({ key: 'dec-D1' })
  await ui.press({ key: 'opt-a' })
  await typeIn(ui, 'comment-D1', '그래도 한 줄', 'submit')
  await ui.press({ key: 'back' })
  await ui.press({ key: 'outbox' })
  await ui.press({ key: 'send' })
  expect(submitted.at(-1)?.text).toBe('D1 → a\nD1 코멘트: 그래도 한 줄')
  expect(stored().decisions[0].status).toBe('answered')
  await ui.unmount()
})

test('a cancelled draft puts its comments back in the box', async ($, on) => {
  const { stored } = engine(on)
  await start($)
  await seed($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  await typeIn(ui, 'comment-D1', '먼저 쓴 말', 'submit')
  await typeIn(ui, 'comment-D1', '쓰는 중', 'change')
  await ui.press({ key: 'back' })
  await ui.press({ key: 'outbox' })
  await ui.press({ key: 'cancel-D1' })
  const d = stored().decisions[0]
  expect(d.comments).toEqual([])
  expect(d.draft).toBe('먼저 쓴 말\n쓰는 중')
  await ui.unmount()
})

test('the agent replies on the thread; the list marks it unread until the decision is opened', async ($, on) => {
  const { stored } = engine(on)
  await start($)
  await seed($)
  await $.prompt.submit({ text: 'D1 코멘트: 한 줄이면 모자라나?', wait: false, origin: { kind: 'composer' } })
  const replied = await $.tool.call(desk({ action: 'comment', id: 'D1', text: '두 번째 줄은 다음 단계라서\n빼면 안 보임' }))
  expect(replied.result).toBe('D1 코멘트 2')
  const d = stored().decisions[0]
  expect(d.comments?.map((c: any) => [c.id, c.by, c.sent])).toEqual([
    ['c1', 'user', true],
    ['c2', 'agent', true],
  ])
  expect(d.unread).toBe(true)
  expect(stored().log.at(-1)?.text).toBe('D1 코멘트: 두 번째 줄은 다음 단계라서 빼면 안 보임')

  const target = pane(43)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const list = await screen(ui, columns)
  show('a decision with an unread agent reply', list.slice(0, 8), columns)
  const row = list.findIndex(l => l.includes('▸ 에이전트: 두 번째 줄은'))
  expect(row).toBeGreaterThan(0)
  expect(list[row]).toMatch(/^● {2}\[2\] +▸ 에이전트: /)
  for (const line of list) expect(cells(line)).toBeLessThanOrEqual(columns)

  await ui.press({ key: 'dec-D1' })
  expect(stored().decisions[0].unread).toBeUndefined()
  const detail = await screen(ui, columns)
  show('the thread under a decision', detail, columns)
  expect(await ui.find({ type: 'Text', text: /^── 코멘트 2 ─+$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '나 · 방금' })).toBeDefined()
  // The agent's header stands out from the person's dim one.
  expect((await ui.findAll({ type: 'Text', text: '▸ 에이전트 · 방금' })).some(t => t.props.bold === true)).toBe(true)
  expect((await ui.findAll({ type: 'Text', text: '나 · 방금' })).some(t => t.props.dimColor === true)).toBe(true)
  // Each comment's text hangs two cells under its header.
  expect(detail.some(l => l.startsWith('  두 번째 줄은 다음 단계라서'))).toBe(true)
  expect(detail.some(l => l.startsWith('  빼면 안 보임'))).toBe(true)
  await ui.press({ key: 'back' })
  expect((await screen(ui, columns)).find(l => l.includes('▸ 에이전트: 두 번째'))).toMatch(/^ {3}\[2\] /)
  await ui.unmount()
})

test('revise_decision changes the decision and says what changed on its thread', async ($, on) => {
  const { stored } = engine(on)
  await start($)
  await seed($)
  await $.tool.call(desk({ action: 'answer_decision', id: 'D2', text: 'a' }))
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  await ui.press({ key: 'opt-a' })
  await ui.press({ key: 'back' })
  const revised = await $.tool.call(
    desk({
      action: 'revise_decision',
      id: 'D1',
      options: [
        { key: 'b', label: '두 줄', why: '다음 단계가 보임' },
        { key: 'c', label: '접었다 펴기', why: '평소 한 줄' },
      ],
      recommended: 'c',
      urgency: 'blocking',
      text: '한 줄 의견을 반영함',
    }),
  )
  expect(revised.result).toBe('D1 다듬음: 선택지 c 추가, 선택지 a 뺌, 권장 b → c, 곧 → 막힘')
  const d = stored().decisions[0]
  expect(d.options.map((o: any) => o.key)).toEqual(['b', 'c'])
  expect(d.recommended).toBe('c')
  expect(d.urgency).toBe('blocking')
  // The pick's option is gone, so the pick is.
  expect(d.pick).toBeUndefined()
  expect(d.comments?.at(-1)).toEqual({
    id: 'c1',
    by: 'agent',
    text: '결정을 다듬음: 선택지 c 추가, 선택지 a 뺌, 권장 b → c, 곧 → 막힘\n한 줄 의견을 반영함',
    at: 1_000_000,
    sent: true,
  })
  expect(d.unread).toBe(true)
  expect(stored().log.at(-1)?.text).toBe('D1 다듬음: 선택지 c 추가, 선택지 a 뺌, 권장 b → c, 곧 → 막힘')
  const same = await $.tool.call(desk({ action: 'revise_decision', id: 'D1', recommended: 'c' }))
  expect(same.result).toBe('D1: 바뀐 것 없음')
  const question = await $.tool.call(desk({ action: 'revise_decision', id: 'D1', question: '밴드는 기본 몇 줄?' }))
  expect(question.result).toBe('D1 다듬음: 질문 고침')
  expect(stored().decisions[0].question).toBe('밴드는 기본 몇 줄?')
  await ui.unmount()
})

test('a chat line comments on a decision', async ($, on) => {
  const { stored, submitted } = engine(on)
  await start($)
  await seed($)
  await $.prompt.submit({ text: 'D1 코멘트: 한 줄도 괜찮을지도\nD2 comment: 프로젝트별이 맞음', wait: false, origin: { kind: 'composer' } })
  const d = stored()
  expect(d.decisions[0].status).toBe('open')
  expect(d.decisions[0].comments?.map((c: any) => [c.by, c.text, c.sent])).toEqual([['user', '한 줄도 괜찮을지도', true]])
  expect(d.decisions[1].comments?.map((c: any) => c.text)).toEqual(['프로젝트별이 맞음'])
  const context = submitted[0]?.context ?? []
  expect(context[0]).toContain('"한 줄도 괜찮을지도"')
  expect(context[0]).toContain('Reply on the desk with the desk action comment (id D1)')
})

// The terminal empties the text a field holds under its key once an Enter
// settles, and shows `value` again only under a new key; a Backspace in that
// emptied copy reports ''. The kit draws no such copy: these tests check the
// key moves and the desk keeps the saved text through an empty change.
test('Enter keeps the 전체 메모 in its field, and an empty change right after it erases nothing', async ($, on) => {
  const { stored } = engine(on)
  await start($)
  await seed($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  await ui.press({ key: 'opt-b' })
  await ui.press({ key: 'back' })
  await ui.press({ key: 'outbox' })
  const before = (await fieldOf(ui, 'outbox-note'))?.key
  expect(before).toBe('outbox-note~0')

  await typeIn(ui, 'outbox-note', '같이 보자', 'submit')
  const after = await fieldOf(ui, 'outbox-note')
  expect(after?.key).not.toBe(before)
  expect(after?.props.value).toBe('같이 보자')
  expect(stored().outboxNote).toBe('같이 보자')

  await typeIn(ui, 'outbox-note', '', 'change')
  expect(stored().outboxNote).toBe('같이 보자')
  expect((await fieldOf(ui, 'outbox-note'))?.props.value).toBe('같이 보자')

  // A real clear still clears.
  await typeIn(ui, 'outbox-note', '같이 보자고', 'change')
  await typeIn(ui, 'outbox-note', '', 'change')
  expect(stored().outboxNote).toBe('')
  await ui.unmount()
})

test('typing a comment across a wrap moves no row and drops no line', async ($, on) => {
  engine(on)
  await start($)
  await $.tool.call(desk({ action: 'add_decision', question: '메모 칸이 흔들리나?', context: LONG_CONTEXT, options: [{ key: 'a', label: '예' }] }))
  // A 43-column terminal: the pane's body is 41 cells.
  const target = pane(43, 30)
  const columns = target.props.bodyColumns
  expect(columns).toBe(41)
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  const before = await screen(ui, columns)
  const head = before.findIndex(l => l.startsWith('새 코멘트 · '))
  expect(head).toBeGreaterThan(0)
  const rows = (await fieldOf(ui, 'comment-D1'))?.props.rows as number
  expect(rows).toBe(6)
  // The field sits on the pane's foot, as wide as the pane.
  expect(head + 1 + rows).toBe(before.length)

  const text = '폰에서 쓰는 메모가 한 줄을 넘어가면 다음 줄로 이어지고 그다음 줄도 그대로 보여야 한다'
  let typed = ''
  for (const ch of text) {
    typed += ch
    await typeIn(ui, 'comment-D1', typed, 'change')
    const now = await screen(ui, columns)
    expect(now.length).toBe(before.length)
    // The body above stays, and so does the header's place.
    expect(now.slice(0, head - 1)).toEqual(before.slice(0, head - 1))
    expect(now[head - 1]).toMatch(/^j: … 아래 \d+줄/)
    expect(now[head]).toMatch(/^새 코멘트 · 저장됨/)
    expect((await fieldOf(ui, 'comment-D1'))?.props.rows).toBe(rows)
    // Every wrapped line of what is typed shows in the field.
    const shown = now.slice(head + 1).map(l => l.replace(/^\||\|$/g, '').trim()).join('')
    expect(shown.replace(/\s/g, '')).toBe(typed.replace(/\s/g, ''))
  }
  show('a comment typed across a wrap at 41 cells', (await screen(ui, columns)).slice(head - 2), columns)
  await ui.unmount()
})

test('a memo of the older layout comes back as the first comment of its thread', async ($, on) => {
  const value = {
    decisions: [
      { id: 'D1', question: '밴드는 몇 줄까지?', options: [], status: 'open', createdAt: 1, memo: '재시작 전에 쓴 메모', memoAt: 5 },
      { id: 'D2', question: '책상 저장은?', options: [], status: 'open', createdAt: 2, memo: '아직 안 보낸 메모', memoAt: 6, memoPending: true },
      { id: 'D3', question: '빈 메모는?', options: [], status: 'answered', answer: 'a', createdAt: 3, memo: '' },
    ],
    plan: [],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 4,
  }
  const { stored } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  // The waiting one is in the outbox; the sent one is not.
  expect((await ui.find({ type: 'Button', key: 'outbox' }))?.text).toBe('보내기 (1) ▸')
  await ui.press({ key: 'dec-D1' })
  expect(await ui.find({ type: 'Text', text: /^── 코멘트 1 ─+$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /재시작 전에 쓴 메모/ })).toBeDefined()
  expect((await fieldOf(ui, 'comment-D1'))?.props.value).toBe('')
  await ui.unmount()
  // The first write stores the thread in place of the memo, under the same tag.
  await $.tool.call(desk({ action: 'note', text: '기록' }))
  const d = stored().decisions
  expect(d[0]).not.toHaveProperty('memo')
  expect(d[0].comments).toEqual([{ id: 'c1', by: 'user', text: '재시작 전에 쓴 메모', at: 5, sent: true }])
  expect(d[1].comments).toEqual([{ id: 'c1', by: 'user', text: '아직 안 보낸 메모', at: 6 }])
  expect(d[1]).not.toHaveProperty('memoPending')
  expect(d[2]).not.toHaveProperty('memo')
  expect(d[2].comments).toBeUndefined()
})

test('a hook that runs before session.start reads the store before writing it', async ($, on) => {
  const value = {
    decisions: [{ id: 'D4', question: '어제 질문', options: [], status: 'open', createdAt: 1 }],
    plan: [{ id: 'S1', text: '어제 단계', state: 'doing' }],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 5,
  }
  const { stored } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  on('turn.complete', (_, e) => ({ text: e.answer }))
  // A fresh process: an agent's turn ends before the plugin's session.start.
  await $.turn.complete({ answer: 'ok', durationMs: 1, isAborted: false, turnId: 'u1', agentId: 'a1', reason: 'answer' })
  expect(stored().decisions[0].question).toBe('어제 질문')
  await start($)
  expect(stored().decisions[0].question).toBe('어제 질문')
  expect(stored().plan[0].text).toBe('어제 단계')
})

test('agents and background shells show while they run', async ($, on) => {
  const { clock, stored } = engine(on)
  on('agent.spawn', () => ({ model: 'claude-sonnet', agentId: 'a1' }))
  on('turn.complete', (_, e) => ({ text: e.answer }))
  on('tool.call', () => ({ result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'b7' } }))
  await start($)

  await $.agent.spawn({
    tool_use_id: 't1',
    prompt: 'review',
    description: '코드 리뷰',
    subagentType: 'general-purpose',
    provider: { plugin: 'engine', tier: 'core' },
    parentModel: 'claude-opus',
    background: true,
    fork: false,
  })
  await $.tool.call({ tool: 'Bash', command: 'npm test', description: '테스트 돌리기', run_in_background: true } as never)
  let d = stored()
  expect(d.running.map((r: any) => [r.label, r.status, r.model])).toEqual([
    ['코드 리뷰', 'running', 'claude-sonnet'],
    ['테스트 돌리기', 'running', undefined],
  ])
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /코드 리뷰 외 1/ })).toBeDefined()
  await ui.unmount()

  await clock.advance(5 * 60_000)
  await $.turn.complete({ answer: 'ok', durationMs: 1, isAborted: false, turnId: 'u1', agentId: 'a1', reason: 'answer' })
  await $.prompt.submit({
    text: '<task-notification><task-id>b7</task-id><status>failed</status></task-notification>',
    wait: false,
    origin: { kind: 'task-notification' },
  })
  d = stored()
  expect(d.running.map((r: any) => r.status)).toEqual(['done', 'failed'])
  expect(d.log.map((l: any) => l.text)).toEqual(['끝남: 코드 리뷰', '실패: 테스트 돌리기'])
})

// ---- layout ---------------------------------------------------------------------

const LONG_QUESTION = '폰 화면에서 패널을 읽을 때 결정 목록의 긴 질문은 두 줄까지 보여 주고 나머지는 상세 화면에서 보는 게 맞을까?'

const busy = async ($: Engine) => {
  await $.tool.call(
    desk({
      action: 'set_plan',
      steps: Array.from({ length: 9 }, (_, i) => ({
        text: `${i + 1}단계: 패널 레이아웃을 손보고 폰에서 다시 읽어 보기`,
        detail: `${i + 1}번째 단계의 설명, 길면 다음 줄로 이어져서 제목 아래에 들여 쓴 채로 보인다`,
      })),
    }),
  )
  for (const id of ['S1', 'S2', 'S3', 'S4', 'S5']) await $.tool.call(desk({ action: 'update_step', id, state: 'done' }))
  await $.tool.call(desk({ action: 'update_step', id: 'S6', state: 'doing' }))
  await $.tool.call(desk({ action: 'add_decision', question: LONG_QUESTION, options: [{ key: 'a', label: '두 줄' }], recommended: 'a' }))
  for (let i = 0; i < 8; i += 1) await $.tool.call(desk({ action: 'add_decision', question: `결정 ${i + 2}: 짧은 질문`, options: [] }))
  for (let i = 0; i < 6; i += 1)
    await $.tool.call(desk({ action: 'note', text: `기록 ${i + 1}: 자리 비운 사이에 끝난 일인데, 설명이 길어서 한 줄에 다 들어가지 않는다` }))
}

test('every tab is exactly the pane tall and no row passes its width', async ($, on) => {
  engine(on)
  await start($)
  await busy($)
  const sizes = [
    { label: '40', target: pane(40) },
    { label: '45', target: pane(45) },
    { label: '60', target: pane(60) },
    { label: '120 inline', target: pane(120) },
    { label: '120 dock', target: pane(120, 50, 'dock', 54) },
  ]
  for (const { label, target } of sizes) {
    const ui = await $.ui.mount({ ...target, surface: 'terminal' })
    const columns = target.props.bodyColumns
    for (const t of ['wait', 'tasks', 'away'] as const) {
      await ui.press({ key: `tab-${t}` })
      const lines = await screen(ui, columns)
      expect(lines.length).toBe(target.props.scroll.bodyRows)
      for (const line of lines) expect(cells(line)).toBeLessThanOrEqual(columns)
      if (label === '45') show(`${t} at 45 columns`, lines, columns)
    }
    await ui.unmount()
  }
})

test('a wrapped line continues under its text, not under its prefix', async ($, on) => {
  engine(on)
  await start($)
  await $.tool.call(
    desk({
      action: 'add_decision',
      question: LONG_QUESTION,
      options: [{ key: 'a', label: '두 줄', why: '목록에서 맥락이 조금 더 보이고, 길게 늘어진 질문은 상세 화면에서 다 읽을 수 있다' }],
    }),
  )
  await $.tool.call(desk({ action: 'note', text: '자리 비운 사이의 기록도 길면 시간 칸 아래가 아니라 글 아래로 이어지고 세 줄까지 보인다' }))
  const target = pane(40)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const lines = await screen(ui, columns)
  const first = lines.findIndex(l => l.startsWith('!  D1  '))
  expect(first).toBeGreaterThan(0)
  const second = lines[first + 1] ?? ''
  // The mark's cell is three wide and the id's four; the question's second
  // line starts under its first.
  expect(second.slice(0, 7)).toBe('       ')
  expect(second[7]).not.toBe(' ')
  expect(LONG_QUESTION.replace(/\s/g, '')).toContain(`${(lines[first] ?? '').slice(7)}${second.slice(7)}`.replace(/\s|…/g, ''))
  show('a long question at 40 columns', lines.slice(0, 8), columns)

  await ui.press({ key: 'tab-away' })
  const away = await screen(ui, columns)
  const entry = away.findIndex(l => l.includes('자리 비운 사이의 기록'))
  // The time and mark take ten cells; the entry wraps under its own text.
  expect(away[entry + 1]?.slice(0, 10)).toBe('          ')
  expect(away[entry + 1]?.[10]).not.toBe(' ')
  await ui.press({ key: 'tab-wait' })

  await ui.press({ key: 'dec-D1' })
  const detail = await screen(ui, columns)
  const why = detail.findIndex(l => l.includes('목록에서'))
  expect(detail[why]?.startsWith('   목록에서')).toBe(true)
  expect(detail[why + 1]?.slice(0, 3)).toBe('   ')
  expect(detail[why + 1]?.[3]).not.toBe(' ')
  show('the detail view at 40 columns', detail.slice(0, 16), columns)
  await ui.unmount()
})

test('a long list scrolls inside the pane with markers and a bar', async ($, on) => {
  engine(on)
  await start($)
  for (let i = 0; i < 12; i += 1) await $.tool.call(desk({ action: 'add_decision', question: `질문 ${i + 1}`, options: [] }))
  const target = pane(45, 20)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  expect(await ui.find({ type: 'Button', key: 'scroll-up' })).toBeUndefined()
  expect((await ui.find({ type: 'Button', key: 'scroll-down' }))?.props.hotkey).toBe('j')
  expect(await ui.find({ type: 'Text', text: / ┃/ })).toBeDefined()
  const before = await screen(ui, columns)

  await ui.press({ key: 'scroll-down' })
  expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeUndefined()
  expect((await ui.find({ type: 'Button', key: 'scroll-up' }))?.text).toContain('위에 1개')
  const after = await screen(ui, columns)
  expect(after.length).toBe(before.length)

  // The wheel and the arrow keys move the list, not the engine's window.
  const moved = await $.ui.scroll({ component: 'Pane', requestId: 'desk', offset: 1, by: 1, bodyRows: 20, contentRows: 20, origin: { kind: 'person' } })
  expect(moved.deny).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'dec-D2' })).toBeUndefined()
  for (let i = 0; i < 30; i += 1)
    await $.ui.scroll({ component: 'Pane', requestId: 'desk', offset: 0, by: -1, bodyRows: 20, contentRows: 20, origin: { kind: 'person' } })
  expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeDefined()
  show('a scrolled list, 20 rows', after, columns)
  await ui.unmount()
})

test('finished decisions sit under their rule in the same scrolling list', async ($, on) => {
  engine(on)
  await start($)
  for (let i = 0; i < 8; i += 1) await $.tool.call(desk({ action: 'add_decision', question: `질문 ${i + 1}`, options: [] }))
  for (let i = 4; i <= 8; i += 1) await $.tool.call(desk({ action: 'answer_decision', id: `D${i}`, text: 'a' }))
  const target = pane(45, 24)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const top = await screen(ui, columns)
  show('3 open and 5 finished, 24 rows', top, columns)
  // Three open, then the rule right after them: no rows held back between.
  const rule = top.findIndex(l => /^── 끝난 결정 5 ─+/.test(l))
  expect(rule).toBe(top.findIndex(l => l.startsWith('!  D3  ')) + 2)
  const bar = barOf(top, columns)
  const thumb = bar.filter(c => c === '┃').length
  expect(thumb).toBeGreaterThan(0)
  expect(bar.indexOf('┃')).toBe(3)

  // Scrolling down reaches the finished ones; the thumb keeps its size.
  for (let i = 0; i < 10; i += 1) await ui.press({ key: 'scroll-down' }).catch(() => undefined)
  const end = await screen(ui, columns)
  expect(end.some(l => l.startsWith('   D4  '))).toBe(true)
  expect(barOf(end, columns).filter(c => c === '┃').length).toBe(thumb)
  expect(await ui.find({ type: 'Button', key: 'scroll-down' })).toBeUndefined()
  show('scrolled to the finished ones', end, columns)
  await ui.unmount()
})

test('the plan is a timeline that opens on the current step', async ($, on) => {
  const { clock } = engine(on)
  await start($)
  await busy($)
  await clock.advance(10 * 60_000)
  const target = pane(45, 24)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  await ui.press({ key: 'tab-tasks' })
  // The step in hand at the top, what comes next below it, the finished
  // steps above, behind the marker.
  const opened = await screen(ui, columns)
  expect(opened[3]).toMatch(/^◉ S6 /)
  // The title wraps under itself, the detail under a corner, both inside the line.
  expect(opened[4]).toMatch(/^│ [^\s└]/)
  expect(opened.some(l => /^│ └ 6번째/.test(l))).toBe(true)
  expect(opened.some(l => /^│ {3}\S/.test(l) && l.includes('들여'))).toBe(true)
  expect(opened.some(l => l.startsWith('○ S7'))).toBe(true)
  expect(await ui.find({ type: 'Button', key: 'step-S5' })).toBeUndefined()
  expect((await ui.find({ type: 'Button', key: 'scroll-up' }))?.text).toContain('위에 5개')
  show('the timeline as it opens, 24 rows', opened, columns)

  await ui.press({ key: 'scroll-up' })
  const lines = await screen(ui, columns)
  expect(lines.some(l => l.startsWith('✓ S5'))).toBe(true)
  expect(lines.some(l => l.startsWith('◉ S6'))).toBe(true)
  expect((await ui.find({ type: 'Button', key: 'scroll-up' }))?.text).toContain('위에 4개')

  await ui.press({ key: 'step-S6' })
  expect(await ui.find({ type: 'Text', text: /6번째 단계의 설명/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /시작 10분 전/ })).toBeDefined()
  await ui.press({ key: 'back' })
  expect(await ui.find({ type: 'Button', key: 'step-S6' })).toBeDefined()
  await ui.unmount()
})

test('nothing moves while the desk changes under the reader', async ($, on) => {
  const { clock } = engine(on)
  on('agent.spawn', () => ({ model: 'claude-sonnet', agentId: 'a1' }))
  await start($)
  await busy($)
  const target = pane(45)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const before = await screen(ui, columns)

  await clock.advance(3 * 3600_000)
  await $.agent.spawn({
    tool_use_id: 't1',
    prompt: 'review',
    description: '아주 긴 이름의 코드 리뷰 에이전트가 도는 중',
    subagentType: 'general-purpose',
    provider: { plugin: 'engine', tier: 'core' },
    parentModel: 'claude-opus',
    background: true,
    fork: false,
  })
  await $.tool.call(desk({ action: 'add_decision', question: '새로 올라온 결정', options: [] }))
  await $.tool.call(desk({ action: 'update_step', id: 'S6', state: 'done' }))
  await ui.redraw()
  const after = await screen(ui, columns)

  expect(after.length).toBe(before.length)
  // The tab row keeps its places; the list's first rows stay where they were.
  const tabStarts = (line: string) => ['1:', '2:', '3:'].map(k => cells(line.slice(0, line.indexOf(k))))
  expect(tabStarts(after[0] ?? '')).toEqual(tabStarts(before[0] ?? ''))
  expect(after.slice(2, 8)).toEqual(before.slice(2, 8))
  // The foot rows are at the same place, now saying more.
  expect(after.findIndex(l => l.includes('S7'))).toBe(before.findIndex(l => l.includes('S6 ')))
  await ui.unmount()
})

// ---- stored desks -----------------------------------------------------------------

test('a stored desk of the older layout comes back whole', async ($, on) => {
  // The shape the desk stored before steps had details: D1-D6 and S1-S5.
  const value = {
    decisions: [1, 2, 3, 4, 5, 6].map(n => ({
      id: `D${n}`,
      question: `예전 질문 ${n}`,
      options: [{ key: 'a', label: '예' }],
      status: n <= 2 ? 'answered' : 'open',
      ...(n <= 2 ? { answer: 'a' } : {}),
      ...(n === 3 ? { memo: '예전 메모' } : {}),
      createdAt: n,
    })),
    plan: [1, 2, 3, 4, 5].map(n => ({ id: `S${n}`, text: `예전 단계 ${n}`, state: n <= 2 ? 'done' : n === 3 ? 'doing' : 'todo' })),
    running: [{ id: 'a9', kind: 'agent', label: '밤새 돈 일', startedAt: 1, status: 'running' }],
    log: [{ at: 2, kind: 'done', text: '밤사이 끝난 일' }],
    lastSeen: 0,
    nextDecision: 7,
  }
  const { stored, kept } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value }, 'project:/old': { shape: 'desk-0', value } })
  await start($)

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Button', key: 'dec-D6' })).toBeDefined()
  // A memo from before the outbox was sent then: nothing waits to be sent.
  expect(await ui.find({ type: 'Button', key: 'outbox' })).toBeUndefined()
  await ui.press({ key: 'tab-tasks' })
  expect(await ui.find({ type: 'Button', key: 'step-S3' })).toBeDefined()
  await ui.press({ key: 'step-S3' })
  expect(await ui.find({ type: 'Text', text: '설명 없음' })).toBeDefined()
  await ui.press({ key: 'back' })
  await ui.press({ key: 'tab-away' })
  expect(await ui.find({ type: 'Text', text: /밤사이 끝난 일/ })).toBeDefined()
  await ui.unmount()

  const added = await $.tool.call(desk({ action: 'add_decision', question: '새 질문' }))
  expect(added.result).toBe('D7 올림 (대기 5)')
  const d = stored()
  expect(d.decisions.map((x: any) => x.id)).toEqual(['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'])
  expect(d.plan.map((s: any) => [s.id, s.state])).toEqual([
    ['S1', 'done'],
    ['S2', 'done'],
    ['S3', 'doing'],
    ['S4', 'todo'],
    ['S5', 'todo'],
  ])
  // A run the last session left running cannot be followed any more.
  expect(d.running[0].status).toBe('lost')
  expect((kept.get(STORE_KEY) as { shape: string }).shape).toBe('desk-1')
})

test('an older shape in the store starts an empty desk', async ($, on) => {
  engine(on, { [STORE_KEY]: { shape: 'desk-0', value: { decisions: [{ id: 'D1' }] } } })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

// ---- detail views: a fixed header over a scrolling body -----------------------------

const scrollBy = ($: Engine, by: number, rows: number) =>
  $.ui.scroll({ component: 'Pane', requestId: 'desk', offset: 0, by, bodyRows: rows, contentRows: rows, origin: { kind: 'person' } })

const LONG_CONTEXT = [
  '## 배경',
  ...Array.from({ length: 30 }, (_, i) => `- ${i + 1}번째 근거: 폰 화면에서 읽을 때 **이 줄**이 길면 다음 줄로 이어진다`),
  '',
  '```',
  'const width = 45',
  '```',
  '마지막 문단',
].join('\n')

test('a long decision scrolls under its header, the way back always on top', async ($, on) => {
  engine(on)
  await start($)
  await $.tool.call(
    desk({ action: 'add_decision', question: LONG_QUESTION, context: LONG_CONTEXT, options: [{ key: 'a', label: '예' }, { key: 'b', label: '아니오' }] }),
  )
  const target = pane(45, 20)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  await ui.press({ key: 'dec-D1' })
  const opened = await screen(ui, columns)
  expect(opened.length).toBe(20)
  expect(opened[0]).toMatch(/^← 목록 {2}D1 · 답을 기다림/)
  expect(await ui.find({ type: 'Button', key: 'scroll-up' })).toBeUndefined()
  expect((await ui.find({ type: 'Button', key: 'scroll-down' }))?.text).toMatch(/아래 \d+줄/)
  expect(await ui.find({ type: 'Button', key: 'discuss' })).toBeUndefined()

  // The End key's worth of wheel: the body at its end, the header unmoved.
  for (let i = 0; i < 8; i += 1) await scrollBy($, 20, 20)
  const end = await screen(ui, columns)
  show('a long decision scrolled to its end, 20 rows', end, columns)
  expect(end.length).toBe(20)
  expect(end[0]).toMatch(/^← 목록 {2}D1 · 답을 기다림/)
  expect(await ui.find({ type: 'Button', key: 'back' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'discuss' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'scroll-down' })).toBeUndefined()
  expect((await ui.find({ type: 'Button', key: 'scroll-up' }))?.text).toMatch(/위에 \d+줄/)
  expect(end.some(l => l.includes('마지막 문단'))).toBe(true)
  for (const line of end) expect(cells(line)).toBeLessThanOrEqual(columns)
  // The bar beside the body has its thumb at the bottom.
  // The body is the 20 rows less the header, the two markers and the memo
  // (its header line and a field of 4): rows 2 to 13.
  expect(barOf(end, columns)[13]).toBe('┃')

  // Back up a wheel tick at a time, then by the marker, to the top.
  await scrollBy($, -1, 20)
  expect(await ui.find({ type: 'Button', key: 'scroll-down' })).toBeDefined()
  for (let i = 0; i < 10; i += 1) await ui.press({ key: 'scroll-up' }).catch(() => undefined)
  expect((await screen(ui, columns))[2]).toBe(opened[2])
  await ui.press({ key: 'back' })
  expect(await ui.find({ type: 'Button', key: 'dec-D1' })).toBeDefined()
  // Opened again, it starts at its top.
  await ui.press({ key: 'dec-D1' })
  expect(await ui.find({ type: 'Button', key: 'scroll-up' })).toBeUndefined()
  await ui.unmount()
})

test('a long step and a full outbox keep their header, the outbox its 전송', async ($, on) => {
  // Eight decisions, each with a pick waiting in the outbox.
  const value = {
    decisions: Array.from({ length: 8 }, (_, i) => ({
      id: `D${i + 1}`,
      question: `질문 ${i + 1}: 꽤 길게 쓴 질문이라 두 줄로 넘어간다`,
      options: [{ key: 'a', label: '예' }],
      status: 'open',
      createdAt: i + 1,
      pick: 'a',
    })),
    plan: [],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 9,
  }
  engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  await start($)
  const detail = Array.from({ length: 40 }, (_, i) => `${i + 1}번째 설명 줄`).join('\n')
  await $.tool.call(desk({ action: 'set_plan', steps: [{ text: '긴 단계', detail }] }))
  const target = pane(45, 18)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })

  await ui.press({ key: 'tab-tasks' })
  await ui.press({ key: 'step-S1' })
  for (let i = 0; i < 6; i += 1) await scrollBy($, 18, 18)
  const step = await screen(ui, columns)
  show('a long step scrolled to its end, 18 rows', step, columns)
  expect(step.length).toBe(18)
  expect(step[0]).toMatch(/^← 목록 {2}S1 · 할 일 · 1\/1단계/)
  expect(step.some(l => l.includes('40번째 설명 줄'))).toBe(true)
  await ui.press({ key: 'back' })
  await ui.press({ key: 'tab-wait' })

  await ui.press({ key: 'outbox' })
  const top = await screen(ui, columns)
  expect(top[0]).toMatch(/^← 목록 {2}보낼 것 8개/)
  expect(top.at(-1)).toBe('[ 전송 ]')
  for (let i = 0; i < 8; i += 1) await scrollBy($, 18, 18)
  const end = await screen(ui, columns)
  show('a full outbox scrolled to its end, 18 rows', end, columns)
  expect(end.length).toBe(18)
  expect(end[0]).toMatch(/^← 목록 {2}보낼 것 8개/)
  expect(end.at(-1)).toBe('[ 전송 ]')
  expect(await fieldOf(ui, 'outbox-note')).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'cancel-D1' })).toBeUndefined()
  await ui.unmount()
})

test('finished decisions list the latest answer first', async ($, on) => {
  const value = {
    decisions: [
      // Two answered before answers were timed: the later asked comes first.
      { id: 'D1', question: '아주 옛날 결정', options: [], status: 'answered', answer: 'a', createdAt: 1 },
      { id: 'D2', question: '옛날 결정', options: [], status: 'answered', answer: 'a', createdAt: 2 },
      { id: 'D3', question: '지금 열린 결정', options: [], status: 'open', createdAt: 3 },
      { id: 'D4', question: '어제 끝낸 결정', options: [], status: 'answered', answer: 'a', createdAt: 4, answeredAt: 50 },
      { id: 'D5', question: '방금 끝낸 결정', options: [], status: 'answered', answer: 'a', createdAt: 5, answeredAt: 90 },
    ],
    plan: [],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 6,
  }
  const { clock } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  await start($)
  await clock.advance(1000)
  await $.tool.call(desk({ action: 'answer_decision', id: 'D3', text: 'b' }))
  const target = pane(45, 30)
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const lines = await screen(ui, target.props.bodyColumns)
  const order = lines.map(l => /^[! ]{3}(D\d)\s/.exec(l)?.[1]).filter(Boolean)
  expect(order).toEqual(['D3', 'D5', 'D4', 'D2', 'D1'])
  await ui.unmount()
})

// ---- the desk's own call in the transcript ----------------------------------------------

const toolRow = (input: Record<string, unknown>, extra: Record<string, unknown> = {}) =>
  ({
    plugin: 'qwreey-desk',
    component: 'ToolUse',
    requestId: 't1',
    props: { tool_use_id: 't1', tool: TOOL, input, isRunning: false, isErrored: false, isInterrupted: false, ...extra },
    viewport: { columns: 45, rows: 80, isFullscreen: false },
  }) as const

test('a desk call shows as one line, whole under ctrl+o', async ($, on) => {
  engine(on)
  await start($)
  const call = { action: 'add_decision', question: '서브에이전트 지침의 "브리프가 길면" 문장을 고칠까?', context: LONG_CONTEXT, options: [{ key: 'a', label: '예' }] }
  const compact = await $.ui.mount({ ...toolRow(call, { output: 'D8 올림 (대기 3)' }), surface: 'terminal' })
  const texts = await compact.findAll({ type: 'Text' })
  expect(texts.length).toBe(1)
  expect(texts[0]?.text).toBe('책상 · D8 올림: 서브에이전트 지침의 "브리프가 길면" 문장을 고칠까?')
  expect(texts[0]?.props.wrap).toBe('truncate-end')
  expect(texts[0]?.props.dimColor).toBe(true)
  await compact.unmount()

  for (const [input, line] of [
    [{ action: 'update_step', id: 's5', state: 'done' }, '책상 · S5 끝'],
    [{ action: 'set_plan', steps: ['a', 'b', { text: 'c' }] }, '책상 · 계획 3단계'],
    [{ action: 'note', text: '리뷰 끝' }, '책상 · 기록: 리뷰 끝'],
    [{ action: 'answer_decision', id: 'D2', text: 'b' }, '책상 · D2 답: b'],
  ] as const) {
    const ui = await $.ui.mount({ ...toolRow(input), surface: 'terminal' })
    expect((await ui.find({ type: 'Text' }))?.text).toBe(line)
    await ui.unmount()
  }

  const failed = await $.ui.mount({ ...toolRow({ action: 'memo' }, { isErrored: true, output: 'D9: 없는 결정' }), surface: 'terminal' })
  expect((await failed.find({ type: 'Text' }))?.text).toBe('책상 · 오류: D9: 없는 결정')
  expect((await failed.find({ type: 'Text' }))?.props.color).toBe('error')
  await failed.unmount()

  // ctrl+o: the engine's own row, the input whole.
  const expanded = await $.ui.mount({ ...toolRow(call, { isExpanded: true }), surface: 'terminal' })
  expect((await expanded.find({ type: 'Text' }))?.text).toBe('engine')
  await expanded.unmount()
  // Another tool's row is left alone.
  const other = await $.ui.mount({ ...toolRow({ command: 'ls' }, { tool: 'Bash' }), surface: 'terminal' })
  expect((await other.find({ type: 'Text' }))?.text).toBe('engine')
  await other.unmount()

  // The result row under it says nothing more, except under ctrl+o.
  const result = (extra: Record<string, unknown>) =>
    ({
      plugin: 'qwreey-desk',
      component: 'ToolResult',
      requestId: 't1',
      props: { tool_use_id: 't1', tool: TOOL, output: 'D8 올림 (대기 3)', isErrored: false, ...extra },
      viewport: { columns: 45, rows: 80, isFullscreen: false },
      surface: 'terminal',
    }) as const
  const quiet = await $.ui.mount(result({}))
  expect(await quiet.find({ type: 'Text' })).toBeUndefined()
  await quiet.unmount()
  const full = await $.ui.mount(result({ isExpanded: true }))
  expect((await full.find({ type: 'Text' }))?.text).toBe('engine')
  await full.unmount()
})

// ---- urgency ------------------------------------------------------------------------

test('open decisions go by urgency, marked in a cell of fixed width', async ($, on) => {
  const value = {
    // Stored before urgency was kept: read as soon.
    decisions: [{ id: 'D1', question: '예전 결정', options: [], status: 'open', createdAt: 1 }],
    plan: [],
    running: [],
    log: [],
    lastSeen: 0,
    nextDecision: 2,
  }
  const { stored } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value } })
  await start($)
  await $.tool.call(desk({ action: 'add_decision', question: '나중에 봐도 되는 것', urgency: 'later' }))
  const added = await $.tool.call(desk({ action: 'add_decision', question: '작업이 멈춘 것', urgency: 'blocking', blocks: 'S3 구현 전부' }))
  expect(added.result).toBe('D3 올림 (대기 3)')
  await $.tool.call(desk({ action: 'add_decision', question: '다음에 필요한 것', urgency: 'soon' }))
  await $.tool.call(desk({ action: 'add_decision', question: '이것도 멈춤', urgency: 'blocking' }))
  await $.tool.call(desk({ action: 'add_decision', question: '잘못 준 값', urgency: 'now' }))
  expect(stored().decisions.map((x: any) => x.urgency)).toEqual([undefined, 'later', 'blocking', 'soon', 'blocking', undefined])
  expect(stored().decisions[2].blocks).toBe('S3 구현 전부')

  const target = pane(43, 40)
  const columns = target.props.bodyColumns
  const ui = await $.ui.mount({ ...target, surface: 'terminal' })
  const lines = await screen(ui, columns)
  show('decisions by urgency at 41 cells', lines.slice(0, 16), columns)
  const firsts = lines.filter(l => /^[! ]{3}D\d /.test(l))
  // Blocking first, then soon (an old one and an unknown value with them) as asked, then later.
  expect(firsts.map(l => l.slice(0, 5))).toEqual(['!! D3', '!! D5', '!  D1', '!  D4', '!  D6', '   D2'])
  // The id and the question start in the same columns whatever the mark.
  expect(new Set(firsts.map(l => l.indexOf('D')))).toEqual(new Set([3]))
  expect(new Set(firsts.map(l => cells(l.slice(0, 7))))).toEqual(new Set([7]))
  // The mark is drawn in the alert tone, the id beside it as before.
  const mark = (await ui.findAll({ type: 'Text', text: /!!/ })).find(x => x.text === '!! ')
  expect(mark?.props.color).toBe('error')

  // Changing it moves the decision; the detail says it and what waits on it.
  const changed = await $.tool.call(desk({ action: 'set_urgency', id: 'd2', urgency: 'blocking', blocks: '배포' }))
  expect(changed.result).toBe('D2 막힘')
  expect((await screen(ui, columns)).filter(l => /^[! ]{3}D\d /.test(l)).map(l => l.slice(0, 5))).toEqual(['!! D2', '!! D3', '!! D5', '!  D1', '!  D4', '!  D6'])
  await ui.press({ key: 'dec-D3' })
  const detail = await screen(ui, columns)
  expect(detail[0]).toBe('← 목록  D3 · 답을 기다림 · 막힘')
  expect(await ui.find({ type: 'Text', text: '기다리는 것: S3 구현 전부' })).toBeDefined()
  await ui.unmount()

  // The band counts the blocking ones apart.
  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await band.find({ type: 'Text', text: /결정/ }))?.text).toBe('결정 6 (막힘 3)')
  await band.unmount()

  // The call's row in the transcript.
  const row = await $.ui.mount({ ...toolRow({ action: 'set_urgency', id: 'D2', urgency: 'later' }), surface: 'terminal' })
  expect((await row.find({ type: 'Text' }))?.text).toBe('책상 · D2 나중')
  await row.unmount()
})

// ---- markdown in a decision's context ------------------------------------------------

const TABLE_CONTEXT = [
  '실측 결과:',
  '',
  '| | 정답 | 식별자 복원 |',
  '|---|---:|---|',
  '| CC compact 만 | 17/27 (63%) | 12/20, 긴 구간에서 놓침 |',
  '| 원문 주입 | 26/27 (96%) | 19/20 |',
  '',
  '자세한 건 [audit 61](https://example.com/a61) 참고.',
].join('\n')

const rowText = (row: readonly { text: string }[]) => row.map(s => s.text).join('')

test('a table in a context stacks its rows on a phone and stays a grid where it fits', async ($, on) => {
  // 41 cells: the grid (51 cells) does not fit, so each row stacks.
  const narrow = markdownRows(TABLE_CONTEXT, 41)
  expect(narrow.map(rowText)).toEqual([
    '실측 결과:',
    '',
    'CC compact 만',
    '  정답: 17/27 (63%)',
    '  식별자 복원: 12/20, 긴 구간에서 놓침',
    '',
    '원문 주입',
    '  정답: 26/27 (96%)',
    '  식별자 복원: 19/20',
    '',
    // The link's address does not fit beside it: its text alone.
    '자세한 건 audit 61 참고.',
  ])
  expect(narrow[2]?.[0]?.tone).toBe('strong')
  expect(narrow[3]?.[1]).toEqual({ text: '정답: ', tone: 'dim' })
  for (const row of narrow) expect(cells(rowText(row))).toBeLessThanOrEqual(41)

  // 100 cells: an aligned grid, the header bold over a dim rule, `---:` right-aligned.
  const wide = markdownRows(TABLE_CONTEXT, 100)
  expect(wide.map(rowText)).toEqual([
    '실측 결과:',
    '',
    `${' '.repeat(22)}정답  식별자 복원`,
    '─'.repeat(51),
    'CC compact 만  17/27 (63%)  12/20, 긴 구간에서 놓침',
    '원문 주입      26/27 (96%)  19/20',
    '',
    '자세한 건 audit 61 (https://example.com/a61) 참고.',
  ])
  expect(wide[2]?.some(s => s.text === '정답' && s.tone === 'strong')).toBe(true)
  expect(wide[3]?.[0]?.tone).toBe('dim')
  expect(wide.at(-1)?.find(s => s.text.includes('https'))?.tone).toBe('dim')

  // The same in a decision's detail, at a 43- and a 102-column terminal.
  engine(on)
  await start($)
  await $.tool.call(desk({ action: 'add_decision', question: '주입을 넣을까?', context: TABLE_CONTEXT, options: [{ key: 'a', label: '넣음' }] }))
  for (const [columns, grid] of [[43, false], [102, true]] as const) {
    const target = pane(columns)
    const ui = await $.ui.mount({ ...target, surface: 'terminal' })
    await ui.press({ key: 'dec-D1' })
    const lines = await screen(ui, target.props.bodyColumns)
    show(`a table in a context at ${columns} columns`, lines.slice(0, 16), target.props.bodyColumns)
    // No raw pipes of the source (the field's own frame is drawn with them).
    expect(lines.some(l => /\| ?(CC|원문|---)/.test(l))).toBe(false)
    expect(lines.some(l => l.startsWith('  정답: 17/27 (63%)'))).toBe(!grid)
    expect(lines.some(l => l.startsWith('CC compact 만  17/27 (63%)'))).toBe(grid)
    await ui.press({ key: 'back' })
    await ui.unmount()
  }
})

// ---- a scroll's cost --------------------------------------------------------------------

const COMMENT = '이 결정은 폰 화면의 폭과 줄 수를 함께 봐야 하고, 긴 문단은 여러 줄로 감긴다. 표는 쌓인다.'

test('a scroll step writes only where the body stands and lays out no text again', async ($, on) => {
  const { writes, stored } = engine(on)
  await start($)
  await $.tool.call(
    desk({
      action: 'add_decision',
      question: LONG_QUESTION,
      context: `${LONG_CONTEXT}\n\n${TABLE_CONTEXT}`,
      options: [
        { key: 'a', label: '두 줄까지 보여 주고 나머지는 상세에서', why: '목록이 짧아짐' },
        { key: 'b', label: '다 보여 줌', why: '한눈에 보임' },
      ],
      recommended: 'a',
      reason: '폰에서 목록이 길어지면 스크롤이 늘어난다',
    }),
  )
  for (let i = 0; i < 10; i += 1) await $.tool.call(desk({ action: 'comment', id: 'D1', text: `${i + 1}: ${COMMENT}` }))

  for (const columns of [41, 100]) {
    const target = pane(columns)
    const ui = await $.ui.mount({ ...target, surface: 'terminal' })
    await ui.press({ key: 'dec-D1' })
    const opened = await screen(ui, target.props.bodyColumns)
    const before = { store: writes.store, state: writes.state.length }
    for (let i = 0; i < 6; i += 1) await scrollBy($, 1, 40)
    const moved = await screen(ui, target.props.bodyColumns)
    for (let i = 0; i < 6; i += 1) await scrollBy($, -1, 40)
    // Scrolling moves the body and nothing else: no store write, only the view's offset.
    expect(moved[2]).not.toBe(opened[2])
    expect(await screen(ui, target.props.bodyColumns)).toEqual(opened)
    expect(writes.store).toBe(before.store)
    expect(writes.state.slice(before.state)).toEqual(Array.from({ length: 12 }, () => 'view'))
    await ui.press({ key: 'back' })
    await ui.unmount()
  }

  // The same decision laid out again at a width it was laid out at: every
  // text, the markdown context and its table included, found kept.
  const d = stored()
  const act = new Proxy({}, { get: () => () => ({ key: 'k', onInput: () => undefined, onSubmit: () => undefined }) }) as Do
  for (const columns of [39, 98]) {
    const first = decisionDetail(d, d.decisions[0], 1_000_000, 'terminal', columns, 40, act)
    const counts = { ...laidOut }
    const again = decisionDetail(d, d.decisions[0], 1_000_000, 'terminal', columns, 40, act)
    expect(laidOut).toEqual(counts)
    expect(again.pieces.length).toBe(first.pieces.length)
  }
})

// ---- the timeline's look --------------------------------------------------------------

const toneOf = (p: Record<string, unknown>) =>
  p.bold && p.color === 'suggestion' ? 'accent' : p.dimColor ? 'dim' : p.bold ? 'strong' : p.color ? String(p.color) : 'plain'

const firstText = (node: unknown): El | undefined => {
  if (!node || typeof node !== 'object') return undefined
  const el = node as El
  return el.type === 'Text' ? el : kids(el).map(firstText).find(Boolean)
}

/** A list's rows above the footer's rule: each cell's text and its tone, the scrollbar's cell left out. */
const styledRows = (tree: unknown, prefix: number) => {
  const rows: El[] = []
  const walk = (node: unknown) => {
    if (!node || typeof node !== 'object') return
    const el = node as El
    if (el.type === 'Box' && el.props?.flexDirection === 'row' && el.props?.height === 1) rows.push(el)
    else kids(el).forEach(walk)
  }
  walk(tree)
  const end = rows.findIndex(r => textOf(r).includes('── 지금'))
  return rows
    .slice(0, end)
    .filter(r => (kids(r)[0] as El | undefined)?.props?.width === prefix)
    .map(r => {
      const [head, body] = kids(r).map(c => firstText(c))
      // A blank cell is drawn as one space.
      const shown = (el: El | undefined) => (textOf(el).trim() === '' ? '' : textOf(el))
      return [shown(head), toneOf(head?.props ?? {}), shown(body), toneOf(body?.props ?? {})]
    })
}

test('the plan timeline keeps its nodes, connectors, tones and indents', async ($, on) => {
  engine(on)
  await start($)
  await $.tool.call(
    desk({
      action: 'set_plan',
      steps: [
        { text: '타입 쓰기', detail: '저장 형태' },
        { text: '밴드 그리기', detail: '프롬프트 위 두 줄' },
        { text: '패널 그리기', detail: '답을 기다림, 작업, 자리 비운 사이 세 탭과 스크롤 막대' },
        { text: '보내기 함', detail: '한 번에 보냄' },
        { text: '배포', detail: '설치 안내' },
      ],
    }),
  )
  await $.tool.call(desk({ action: 'update_step', id: 'S1', state: 'done' }))
  await $.tool.call(desk({ action: 'update_step', id: 'S2', state: 'done' }))
  await $.tool.call(desk({ action: 'update_step', id: 'S3', state: 'doing' }))
  for (const columns of [41, 60]) {
    const target = pane(columns)
    const ui = await $.ui.mount({ ...target, surface: 'terminal' })
    await ui.press({ key: 'tab-tasks' })
    const narrow = columns === 41
    // It opens on the step in hand, the finished ones a marker's press above;
    // scrolled up once, it stays there for the next mount.
    if (narrow) {
      expect((await ui.find({ type: 'Button', key: 'scroll-up' }))?.text).toContain('위에 2개')
      await ui.press({ key: 'scroll-up' })
      await ui.press({ key: 'scroll-up' })
    }
    const rows = styledRows(await ui.drawn(), 2)
    // The window's foot is blank rows: past the last step, nothing is drawn.
    const blank = rows.findLastIndex(r => r[0] !== '' || r[2] !== '') + 1
    expect(rows.slice(blank).every(r => r.join('') === 'plainplain')).toBe(true)
    expect(rows.slice(0, blank)).toEqual([
      // The marker row: nothing above.
      ['', 'plain', '', 'plain'],
      ['✓', 'dim', 'S1 타입 쓰기', 'dim'],
      ['│', 'dim', '└ 저장 형태', 'dim'],
      ['│', 'dim', '', 'plain'],
      ['✓', 'dim', 'S2 밴드 그리기', 'dim'],
      ['│', 'dim', '└ 프롬프트 위 두 줄', 'dim'],
      ['│', 'dim', '', 'plain'],
      ['◉', 'accent', 'S3 패널 그리기', 'accent'],
      ...(narrow
        ? [
            ['│', 'dim', '└ 답을 기다림, 작업, 자리 비운 사이', 'dim'],
            ['│', 'dim', '  세 탭과 스크롤 막대', 'dim'],
          ]
        : [
            ['│', 'dim', '└ 답을 기다림, 작업, 자리 비운 사이 세 탭과 스크롤', 'dim'],
            ['│', 'dim', '  막대', 'dim'],
          ]),
      ['│', 'dim', '', 'plain'],
      ['○', 'plain', 'S4 보내기 함', 'plain'],
      ['│', 'dim', '└ 한 번에 보냄', 'dim'],
      ['│', 'dim', '', 'plain'],
      // The last step has no line running on below it.
      ['○', 'plain', 'S5 배포', 'plain'],
      ['', 'dim', '└ 설치 안내', 'dim'],
    ])
    await ui.unmount()
  }
})

test('the tab row is compact, a dim bar between tabs, and holds still as its counts change', async ($, on) => {
  engine(on)
  await start($)
  const head = async (columns: number) => {
    const target = pane(columns)
    const ui = await $.ui.mount({ ...target, surface: 'terminal' })
    const line = (await screen(ui, target.props.bodyColumns))[0] ?? ''
    const bars = (await ui.findAll({ type: 'Text', text: /│/ })).filter(t => t.text.trim() === '│')
    await ui.unmount()
    return { line, bars }
  }
  // No counts: no room held for one.
  expect((await head(41)).line).toBe('1: 기다림 │ 2: 작업 │ 3: 비운')
  expect((await head(60)).line).toBe('1: 답을 기다림 │ 2: 작업 │ 3: 자리 비운 사이')
  const { bars } = await head(60)
  expect(bars.length).toBe(2)
  for (const bar of bars) expect(bar.props.dimColor).toBe(true)

  await $.tool.call(desk({ action: 'add_decision', question: '하나', options: [] }))
  await $.tool.call(desk({ action: 'note', text: '기록' }))
  const one = await head(60)
  show('the tab row at 60 columns', [one.line], 58)
  show('the tab row at 41 columns', [(await head(41)).line], 39)
  expect(one.line).toBe('1: 답을 기다림 1  │ 2: 작업 │ 3: 자리 비운 사이 1')
  for (let i = 0; i < 10; i += 1) await $.tool.call(desk({ action: 'add_decision', question: `결정 ${i}`, options: [] }))
  const many = await head(60)
  expect(many.line).toBe('1: 답을 기다림 11 │ 2: 작업 │ 3: 자리 비운 사이 1')
  // Two digits where one stood: the tabs after it do not move.
  expect(many.line.indexOf('2: 작업')).toBe(one.line.indexOf('2: 작업'))
})
