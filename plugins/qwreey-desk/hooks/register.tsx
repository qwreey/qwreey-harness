import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, RenderSurface } from 'claude-code'

import type { DeskData, DeskDecision, DeskField, DeskRunStatus, DeskStepState, DeskStored, DeskTab, DeskView } from '../types'
import {
  SHAPE,
  addDecision,
  answerDecision,
  applyChat,
  bandLines,
  addComment,
  clearDraft,
  commentNote,
  deferDecision,
  drafts,
  emptyData,
  isUrgency,
  logSince,
  markRead,
  markSent,
  mergeLoaded,
  migrate,
  normalize,
  note,
  oneLine,
  openDecisions,
  parseChat,
  postComment,
  reviseDecision,
  runEnded,
  runStarted,
  sendOutbox,
  setDraft,
  setOutboxNote,
  setPick,
  setPlan,
  setUrgency,
  settleLoaded,
  toolSummary,
  unsent,
  updateStep,
} from './model'
import type { NewDecision, NewStep, Outcome, Revision, Sent } from './model'
import {
  BAR,
  END,
  TABS,
  TAB_KEY,
  cells,
  detailRegions,
  detailStep,
  footer,
  lastOffset,
  lastOffsetOf,
  listFor,
  offsetBound,
  regions,
  tabRow,
  textWidth,
  windowOf,
} from './layout'
import type { Act, Line, List } from './layout'
import { TONE, decisionDetail, drawDetail, footerRows, heightsOf, outboxDetail, stepDetail } from './views'
import type { Detail, Do, Els, Field } from './views'

const PANE = 'desk'
const TOOL = 'mcp__qwreey-desk__desk'
// The inline pane's height: it is drawn exactly this tall (or the room it is
// given, if less), so its frame never grows or shrinks with what it holds.
const PANE_ROWS = 40

const data = atom({ plugin: 'qwreey-desk', key: 'data' } as const, emptyData(), { shape: SHAPE })
const storeKey = atom({ plugin: 'qwreey-desk', key: 'storeKey' } as const, '')
const seenFrom = atom({ plugin: 'qwreey-desk', key: 'seenFrom' } as const, 0)
const view = atom({ plugin: 'qwreey-desk', key: 'view' } as const, {})
const tab = atom({ plugin: 'qwreey-desk', key: 'tab' } as const, 'wait' as DeskTab)
const fields = atom({ plugin: 'qwreey-desk', key: 'fields' } as const, {} as Record<string, DeskField>)
// The validator reads state references off the source, so each family
// member's atom is written where it is read or written.
const readOffset = ($: EngineInterface, id: DeskTab) => read($, atom({ plugin: 'qwreey-desk', key: 'offset', id } as const, -1))
const setOffset = ($: EngineInterface, id: DeskTab, change: (v: number) => number) =>
  update($, atom({ plugin: 'qwreey-desk', key: 'offset', id } as const, -1), change)

type $ = EngineInterface

/** The session's desk, a memo of the older layout read into its thread. */
const deskNow = async ($: $) => migrate(await read($, data))

/**
 * Reads the project's desk from the store once per process, before anything
 * writes it. Session state is empty in a new process, and hooks other than
 * session.start (a turn ending, an agent starting) may run first in it; were
 * they to write before the read, the stored desk would be overwritten.
 */
const ensureLoaded = async ($: $, cwd?: string): Promise<string> => {
  const have = await read($, storeKey)
  if (have) return have
  const key = `project:${cwd ?? (await $.session.cwd())}`
  const stored = (await $.store.get(key)) as Partial<DeskStored> | undefined
  if (stored?.shape === SHAPE && stored.value) {
    const loaded = settleLoaded(normalize(stored.value))
    await update($, data, held => mergeLoaded(loaded, held))
  }
  await update($, storeKey, () => key)
  return key
}

// Every change goes through here: the session's value first (what the band
// and pane draw from), then the project's copy in the store.
const mutate = async ($: $, change: (d: DeskData, now: number) => Outcome | DeskData): Promise<string> => {
  const key = await ensureLoaded($)
  const now = await $.clock.now()
  let text = ''
  const next = await update($, data, d => {
    const out = change(migrate(d), now)
    if ('text' in out) {
      text = out.text
      return out.data
    }
    return out
  })
  await $.store.set(key, { shape: SHAPE, value: next } satisfies DeskStored)
  return text
}

const openDesk = async ($: $) => {
  await ensureLoaded($)
  const d = await deskNow($)
  await update($, seenFrom, () => d.lastSeen)
  await mutate($, (cur, now) => ({ ...cur, lastSeen: now }))
  await update($, view, () => ({}))
  await update($, tab, () => 'wait' as DeskTab)
  for (const id of TABS) await setOffset($, id, () => -1)
  return $.ui.open({ id: PANE, title: '책상', focus: true, rows: PANE_ROWS, columns: 60 })
}

const TOOL_DESCRIPTION = [
  "The user's desk: a side pane they read on a phone-width terminal instead of scrolling the chat.",
  'Every question that needs their decision goes here (add_decision: one-line question, markdown context (prefer short lists over tables), options with why, recommended + reason, urgency blocking|soon|later with blocks: what waits on it; set_urgency changes it); in chat say only one line, e.g. "D3 on the desk".',
  'Keep the plan here (set_plan, update_step) and log finished work (note); a step is a short title, its detail a line under it.',
  'Chat lines like "D3: b" or "D3 코멘트: ..." are recorded automatically, and so are answers and comments the user sends from the desk; call answer_decision (their exact words) or memo only for answers or notes given another way.',
  'When the user comments on a decision, reply there with comment, and revise_decision if the discussion changed it.',
].join(' ')

const TOOL_SCHEMA = {
  type: 'object',
  properties: {
    action: {
      type: 'string',
      enum: ['add_decision', 'answer_decision', 'defer_decision', 'set_urgency', 'memo', 'comment', 'revise_decision', 'set_plan', 'update_step', 'note'],
    },
    id: { type: 'string', description: 'D3 for decisions, S2 for steps' },
    question: { type: 'string', description: 'add_decision, revise_decision: one line' },
    context: { type: 'string', description: 'add_decision, revise_decision: markdown the user needs to decide' },
    urgency: { type: 'string', enum: ['blocking', 'soon', 'later'], description: 'blocking: work stops on it; soon: next steps need it; later: can wait' },
    blocks: { type: 'string', description: 'what waits on the decision, one line' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        properties: { key: { type: 'string' }, label: { type: 'string' }, why: { type: 'string' } },
        required: ['key', 'label'],
      },
    },
    recommended: { type: 'string', description: 'option key' },
    reason: { type: 'string', description: 'why the recommended option' },
    text: {
      type: 'string',
      description:
        "answer_decision: the user's words; memo: the user's note; comment: your reply on the decision's thread; revise_decision: what the discussion settled (optional); note: the text; update_step: the step's new detail",
    },
    steps: {
      type: 'array',
      items: {
        anyOf: [
          { type: 'string' },
          {
            type: 'object',
            properties: { text: { type: 'string' }, detail: { type: 'string' } },
            required: ['text'],
          },
        ],
      },
      description: 'set_plan: ordered steps, each a short title or {text: title, detail: a line under it}',
    },
    state: { type: 'string', enum: ['todo', 'doing', 'done'] },
  },
  required: ['action'],
}

const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() !== '' ? v : undefined)

const stepInput = (s: unknown): NewStep[] => {
  if (typeof s === 'string') return str(s) ? [{ text: s }] : []
  if (!s || typeof s !== 'object') return []
  const { text, detail } = s as { text?: unknown; detail?: unknown }
  const title = str(text)
  return title ? [{ text: title, detail: str(detail) }] : []
}

const optionsOf = (v: unknown) =>
  Array.isArray(v)
    ? (v as { key?: unknown; label?: unknown; why?: unknown }[])
        .filter(o => str(o.key) && str(o.label))
        .map(o => ({ key: String(o.key), label: String(o.label), why: str(o.why) }))
    : undefined

const runTool = (e: Readonly<Record<string, unknown>>) => (d: DeskData, now: number): Outcome => {
  const id = str(e.id) ?? ''
  switch (e.action) {
    case 'add_decision': {
      const question = str(e.question)
      if (!question) return { data: d, text: 'question 이 필요함' }
      const options = optionsOf(e.options) ?? []
      const input: NewDecision = {
        question,
        context: str(e.context),
        options,
        recommended: str(e.recommended),
        reason: str(e.reason),
        urgency: isUrgency(e.urgency) ? e.urgency : undefined,
        blocks: str(e.blocks),
      }
      return addDecision(d, now, input)
    }
    case 'answer_decision':
      return answerDecision(d, now, id, str(e.text) ?? '')
    case 'defer_decision':
      return deferDecision(d, now, id)
    case 'set_urgency':
      return isUrgency(e.urgency) ? setUrgency(d, id, e.urgency, str(e.blocks)) : { data: d, text: 'urgency 는 blocking, soon, later 중 하나' }
    case 'memo':
      return addComment(d, now, id, 'user', str(e.text) ?? '')
    case 'comment':
      return addComment(d, now, id, 'agent', str(e.text) ?? '')
    case 'revise_decision': {
      const change: Revision = {
        question: str(e.question),
        context: str(e.context),
        options: optionsOf(e.options),
        recommended: str(e.recommended),
        reason: str(e.reason),
        urgency: isUrgency(e.urgency) ? e.urgency : undefined,
        blocks: str(e.blocks),
      }
      return reviseDecision(d, now, id, change, str(e.text))
    }
    case 'set_plan':
      return setPlan(d, Array.isArray(e.steps) ? e.steps.flatMap(stepInput) : [])
    case 'update_step': {
      const state = e.state === 'doing' || e.state === 'done' || e.state === 'todo' ? (e.state as DeskStepState) : 'done'
      return updateStep(d, now, id, state, str(e.text))
    }
    case 'note':
      return note(d, now, str(e.text) ?? '')
    default:
      return { data: d, text: `모르는 action: ${String(e.action)}` }
  }
}

const TASK_ID = /<task-id>([^<]+)<\/task-id>/
const TASK_STATUS = /<status>([^<]+)<\/status>/
const DISCUSS = /^\s*(D\d+)\s+더 논의/m

const taskStatus = (word: string | undefined): DeskRunStatus =>
  word === 'failed' ? 'failed' : word === 'killed' ? 'stopped' : 'done'

// Origins whose words are the person's own: a typed prompt, the phone bridge,
// the SDK host. The desk's own buttons tell the model through tellModel
// instead, since a plugin's hooks are not run on its own submission.
const fromPerson = (origin: { kind: string }) =>
  origin.kind === 'composer' || origin.kind === 'bridge' || origin.kind === 'sdk'

const decisionBrief = (d: DeskDecision): string =>
  [
    `${d.id}: ${d.question}`,
    d.context ? `Context: ${d.context}` : '',
    ...d.options.map(o => `${o.key}) ${o.label}${o.why ? ` - ${o.why}` : ''}`),
    d.recommended ? `Recommended ${d.recommended}${d.recommendedWhy ? `: ${d.recommendedWhy}` : ''}` : '',
    d.pick ? `The user's pick so far (not sent as an answer): ${d.pick}` : '',
    ...(d.comments ?? []).map(c => `${c.by === 'agent' ? 'Your' : "The user's"} comment: ${c.text}`),
  ]
    .filter(Boolean)
    .join('\n')

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A reload keeps the session's value, which is never older than the
    // store's; a new process reads the store here, or at its first write.
    await ensureLoaded($, e.cwd)
    await $.tool.register({ name: 'desk', description: TOOL_DESCRIPTION, inputSchema: TOOL_SCHEMA, isDeferred: false })
    await $.command.register({ name: 'desk', description: '책상 열기: 답을 기다리는 결정, 작업 순서, 자리 비운 사이', argumentHint: '[닫기]' })
    return next(e)
  })

  on('command.run', { command: 'desk' }, async ($, e) => {
    if (/^(닫기|close)$/i.test(e.args.trim())) {
      await $.ui.close({ id: PANE })
      return { text: '책상을 닫았어요.' }
    }
    const opened = await openDesk($)
    return { text: opened.isPlaced ? '책상을 열었어요.' : `책상: ${opened.reason}` }
  })

  on('tool.call', { tool: TOOL }, async ($, e) => {
    const text = await mutate($, runTool(e as Readonly<Record<string, unknown>>))
    return { result: text }
  })

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    if ('agentId' in started && started.agentId && !e.resume && !e.workflow) {
      const run = {
        id: started.agentId,
        kind: 'agent' as const,
        label: oneLine(e.description || e.subagentType),
        model: started.model,
        startedAt: await $.clock.now(),
        status: 'running' as const,
      }
      await mutate($, d => runStarted(d, run)).catch(() => undefined)
    }
    return started
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    const agentId = e.agentId
    if (agentId) {
      const reason = (e as { reason?: string }).reason
      const status: DeskRunStatus = e.isAborted ? 'stopped' : reason === 'error' || reason === 'refusal' ? 'failed' : 'done'
      await mutate($, (d, now) => runEnded(d, now, agentId, status)).catch(() => undefined)
    }
    return done
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    const record = ran.result as { backgroundTaskId?: string } | undefined
    const taskId = record?.backgroundTaskId
    if (taskId) {
      const input = e as unknown as { description?: string; command?: string }
      const run = {
        id: taskId,
        kind: 'shell' as const,
        label: oneLine(input.description ?? input.command ?? 'shell').slice(0, 80),
        startedAt: await $.clock.now(),
        status: 'running' as const,
      }
      await mutate($, d => runStarted(d, run)).catch(() => undefined)
    }
    return ran
  })

  on('prompt.submit', async ($, e, next) => {
    if (e.origin.kind === 'task-notification') {
      const id = TASK_ID.exec(e.text)?.[1]
      if (id) {
        const status = taskStatus(TASK_STATUS.exec(e.text)?.[1])
        await mutate($, (d, now) => runEnded(d, now, id, status)).catch(() => undefined)
      }
      return next(e)
    }
    if (e.command || !fromPerson(e.origin)) return next(e)

    const lines: string[] = []
    const marks = parseChat(e.text)
    if (marks.length > 0) {
      await mutate($, (d, now) => {
        const out = applyChat(d, now, marks)
        lines.splice(0, lines.length, ...out.lines)
        return out.data
      })
    }
    const discussed = DISCUSS.exec(e.text)?.[1]
    if (discussed) {
      const d = (await deskNow($)).decisions.find(one => one.id === discussed)
      if (d) lines.push(`The user wants to discuss this desk decision further; it stays open.\n${decisionBrief(d)}`)
    }
    return lines.length > 0 ? next({ ...e, context: [...(e.context ?? []), ...lines] }) : next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const lines = bandLines(await deskNow($))
    if (!lines) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const hasOpen = openDecisions(await deskNow($)).length > 0
    // The button first: after the counts, it would move as they change.
    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={2}>
          <Button key="open" plain hotkey="d" dimColor onPress={() => void openDesk($)}>
            책상 열기
          </Button>
          <Text color={hasOpen ? 'warning' : undefined} wrap="truncate-end">
            {lines.counts}
          </Text>
        </Box>
        {lines.next ? (
          <Text dimColor wrap="truncate-end">
            {lines.next}
          </Text>
        ) : null}
      </Box>
    )
  })

  // Every view scrolls itself inside a pane drawn exactly as tall as its
  // room, so the person's wheel and scroll keys move the list or the detail's
  // body, not the engine's window, and the rows pinned around them stay.
  on('ui.scroll', { requestId: PANE }, async ($, e, next) => {
    if (e.component !== 'Pane') return next(e)
    const shown = await read($, view)
    if (shown.decision || shown.step || shown.outbox) {
      await scrollDetail($, shown, e.by, e.bodyRows, e.contentRows)
      return {}
    }
    const current = await read($, tab)
    const list = listFor(current, await deskNow($), await read($, seenFrom), await $.clock.now(), 80)
    const rows = regions(e.contentRows).body
    // A page key moves about a window of items, a wheel tick or an arrow one.
    const page = Math.max(1, Math.floor(rows / 4))
    const steps = Math.abs(e.by) >= e.bodyRows ? page : Math.max(1, Math.abs(e.by))
    await scrollList($, current, list, Math.sign(e.by) * steps, offsetBound(list, rows))
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const d = await deskNow($)
    const now = await $.clock.now()
    const shown = await read($, view)
    const room = e.props.scroll.bodyRows > 0 ? e.props.scroll.bodyRows : PANE_ROWS
    const rows = e.props.placement === 'inline' ? Math.min(room, PANE_ROWS) : room
    const columns = e.props.bodyColumns
    const act = handlers($, await read($, fields))
    const detail = detailOf(d, shown, now, e.surface, columns, rows, act)
    if (detail) return drawDetail(els, detail, shown.offset ?? 0, rows, columns, act)
    return tabs($, els, d, now, await read($, seenFrom), rows, columns)
  })

  // The desk's own call in the transcript: one dim line saying what it did,
  // not the whole input (a decision's context runs to many lines); ctrl+o
  // still shows the call as the engine draws it.
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    if (e.props.tool !== TOOL || e.props.isExpanded) return next(e)
    const { Text } = $.ui.resolve(e)
    const line = toolSummary(e.props.input, e.props.output, e.props.isErrored)
    return (
      <Text dimColor={!e.props.isErrored} color={e.props.isErrored ? 'error' : undefined} wrap="truncate-end">
        책상 · {line}
      </Text>
    )
  })

  // Its result is the short answer the call's line already carries.
  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    if (e.props.tool !== TOOL || e.props.isExpanded) return next(e)
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
}

// The width a detail's scroll bound is counted at, the wheel's hook not being
// told the pane's: a phone's 45-column terminal less the frame. Drawn
// narrower, the bound may fall short of the end; reaching it then stores
// END, which the drawing reads as the end at its own width.
const BOUND_COLUMNS = 43

const detailOf = (
  d: DeskData,
  shown: DeskView,
  now: number,
  surface: RenderSurface,
  columns: number,
  rows: number,
  act: Do,
): Detail | undefined => {
  if (shown.outbox) return outboxDetail(d, surface, columns, rows, act)
  const decision = shown.decision ? d.decisions.find(one => one.id === shown.decision) : undefined
  if (decision) return decisionDetail(d, decision, now, surface, columns, rows, act)
  const step = shown.step ? d.plan.find(s => s.id === shown.step) : undefined
  return step ? stepDetail(d, step, now, columns) : undefined
}

const scrollDetail = async ($: $, shown: DeskView, by: number, bodyRows: number, contentRows: number) => {
  const d = await deskNow($)
  const now = await $.clock.now()
  const act = handlers($)
  // The surface is not told either: the bound is the larger of a field's and none.
  const bounds = (['terminal', 'mobile'] as const).map(surface => {
    const detail = detailOf(d, shown, now, surface, BOUND_COLUMNS, contentRows, act)
    return detail ? lastOffset(heightsOf(detail), detailRegions(contentRows, footerRows(detail)).body, 0) : 0
  })
  const bound = Math.max(...bounds)
  // A page key moves most of a window, a wheel tick or an arrow one piece.
  const steps = Math.abs(by) >= bodyRows ? detailStep(detailRegions(contentRows).body) : Math.max(1, Math.abs(by))
  await update($, view, v => {
    const moved = Math.max(0, Math.min(Math.min(v.offset ?? 0, bound) + Math.sign(by) * steps, bound))
    return { ...v, offset: moved >= bound && bound > 0 ? END : moved }
  })
}

const handlers = ($: $, marks: Readonly<Record<string, DeskField>> = {}): Do => ({
  open: next => void openView($, next),
  scroll: (by, last) =>
    void update($, view, v => ({ ...v, offset: Math.max(0, Math.min(Math.min(v.offset ?? 0, last) + by, last)) })),
  pick: (one, key) => void pick($, one, key),
  discuss: one => void discuss($, one),
  defer: id => void mutate($, (cur, at) => deferDecision(cur, at, id)),
  reopen: id =>
    void mutate($, cur => ({ ...cur, decisions: cur.decisions.map(x => (x.id === id ? { ...x, status: 'open' as const } : x)) })),
  comment: id =>
    field(
      $,
      marks,
      `comment-${id}`,
      d => d.decisions.find(x => x.id === id)?.draft,
      (d, value, now) => setDraft(d, id, value, now),
      (d, value, now) => postComment(d, id, value, now),
    ),
  cancelDraft: id => void cancelDraft($, id),
  outboxNote: () => field($, marks, 'outbox-note', d => d.outboxNote, (d, value) => setOutboxNote(d, value)),
  send: () => void send($),
})

const scrollList = ($: $, id: DeskTab, list: List, by: number, last: number) =>
  setOffset($, id, v => Math.max(0, Math.min((v < 0 ? Math.min(list.auto, last) : Math.min(v, last)) + by, last)))

/**
 * The 답을 기다림 tab's row under the tabs: the outbox's button while it holds
 * drafts, its digit hotkey typed alike under any input method.
 */
const outboxLine = (count: number): Line =>
  count > 0
    ? { prefix: '', text: `보내기 (${count}) ▸`, tone: 'accent', act: { kind: 'outbox' }, key: 'outbox', hotkey: '0' }
    : { prefix: '', text: '' }

// A view opens at the top of its body: the offset goes with the view. A
// decision opened has its agent comments read.
const openView = async ($: $, next: DeskView) => {
  await update($, view, () => next)
  const id = next.decision
  if (id && (await deskNow($)).decisions.some(x => x.id === id && x.unread)) await mutate($, cur => markRead(cur, id))
}

const tabs = async ($: $, els: Els, d: DeskData, now: number, since: number, rows: number, columns: number) => {
  const { Box, Text, Button } = els
  const current = await read($, tab)
  const room = regions(rows)
  const list = listFor(current, d, since, now, columns)
  const win = windowOf(list, await readOffset($, current), room.body, columns)
  const last = lastOffsetOf(list, room.body)
  const head = tabRow(columns, { wait: openDecisions(d).length, tasks: 0, away: logSince(d, since).length })

  const press = (a: Act) => {
    switch (a.kind) {
      case 'decision':
        return void openView($, { decision: a.id })
      case 'step':
        return void openView($, { step: a.id })
      case 'outbox':
        return void openView($, { outbox: true })
      case 'seen':
        return void markSeen($)
      case 'scroll':
        return void scrollList($, current, list, a.by, last)
    }
  }

  // One terminal row: the prefix in a cell of the list's width, the text in
  // the rest, then the scrollbar's cell; every width fixed, none read off the text.
  const row = (l: Line, prefix: number, bar?: string) =>
    l.rule ? (
      <Box flexDirection="row" height={1}>
        <Box width={columns - BAR} flexShrink={0}>
          <Text dimColor wrap="truncate-end">
            {l.text}
          </Text>
        </Box>
        {bar !== undefined ? (
          <Box width={2} flexShrink={0}>
            <Text dimColor> {bar}</Text>
          </Box>
        ) : null}
      </Box>
    ) : (
      <Box flexDirection="row" height={1}>
        {prefix > 0 ? (
          <Box width={prefix} flexShrink={0}>
            {l.mark ? (
              <Text wrap="truncate-end">
                <Text {...TONE[l.mark.tone]}>{l.mark.text}</Text>
                <Text {...TONE[l.prefixTone ?? 'plain']}>{l.prefix}</Text>
              </Text>
            ) : (
              <Text {...TONE[l.prefixTone ?? 'plain']} wrap="truncate-end">
                {l.prefix || ' '}
              </Text>
            )}
          </Box>
        ) : null}
        <Box width={textWidth(columns, prefix)} flexShrink={0}>
          {l.act && l.key ? (
            <Button key={l.key} plain hotkey={l.hotkey} onPress={() => press(l.act as Act)}>
              <Text {...TONE[l.tone ?? 'plain']}>{l.text}</Text>
            </Button>
          ) : (
            <Text {...TONE[l.tone ?? 'plain']} wrap="truncate-end">
              {l.text || ' '}
            </Text>
          )}
        </Box>
        {bar !== undefined ? (
          <Box width={2} flexShrink={0}>
            <Text dimColor> {bar}</Text>
          </Box>
        ) : null}
      </Box>
    )
  const blank = <Text> </Text>

  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      <Box flexDirection="row" height={1}>
        {head.tabs.flatMap((t, i) => {
          const on = t.tab === current
          return [
            ...(i > 0
              ? [
                  <Box width={cells(head.sep)} flexShrink={0}>
                    <Text dimColor>{head.sep}</Text>
                  </Box>,
                ]
              : []),
            <Box width={t.width} flexShrink={0}>
              <Button key={`tab-${t.tab}`} plain hotkey={TAB_KEY[t.tab]} onPress={() => void update($, tab, () => t.tab)}>
                <Text bold={on} underline={on} color={on ? 'suggestion' : undefined} dimColor={!on}>
                  {t.name}
                </Text>
                {t.count ? <Text color={t.tab === 'wait' ? 'warning' : undefined}>{t.count}</Text> : null}
              </Button>
            </Box>,
          ]
        })}
      </Box>
      {room.top > 1 ? current === 'wait' ? row(outboxLine(drafts(d).length), 0) : blank : null}
      {row(win.top, list.prefix)}
      {win.body.map((l, i) => row(l, list.prefix, win.bar[i]))}
      {row(win.bottom, list.prefix)}
      {room.footer > 0 ? footer(d, now, columns).map(l => row(l, 2)) : null}
    </Box>
  )
}

const markSeen = async ($: $) => {
  const now = await $.clock.now()
  await update($, seenFrom, () => now)
  await mutate($, d => ({ ...d, lastSeen: now }))
}

// A row the model reads before the prompt the button submits; the person
// sees only the short prompt.
const tellModel = ($: $, text: string) =>
  $.session.append({ message: { type: 'user', content: [{ type: 'text', text }] } }).catch(() => undefined)

// An option pressed is only picked: it waits in the outbox, changeable, until
// the person sends the outbox. Pressing the picked one again unpicks it.
const pick = ($: $, one: DeskDecision, key: string) =>
  mutate($, d => setPick(d, one.id, d.decisions.find(x => x.id === one.id)?.pick === key ? undefined : key))

/** Sends every draft as one prompt and records each, as the person's own words. */
const send = async ($: $) => {
  let sent: Sent | undefined
  await mutate($, (d, now) => {
    sent = sendOutbox(d, now)
    return sent?.data ?? d
  })
  if (!sent) return
  await openView($, {})
  await tellModel($, sent.note)
  await $.prompt.submit({ text: sent.prompt })
}

/** Takes one decision out of the outbox: its pick unpicked, its comments back in the box. */
const cancelDraft = ($: $, id: string) => mutate($, (d, now) => clearDraft(d, id, now))

// 이걸로 더 논의 asks for a conversation now, so it is sent at once: the
// decision's comments not sent yet go with it, the draft in the box posted
// first; its pick stays a draft.
const discuss = async ($: $, one: DeskDecision) => {
  const held = (await deskNow($)).decisions.find(x => x.id === one.id)
  if (held?.draft?.trim()) await mutate($, (cur, now) => postComment(cur, one.id, held.draft ?? '', now))
  const d = (await deskNow($)).decisions.find(x => x.id === one.id) ?? one
  const texts = unsent(d).map(c => c.text.trim())
  if (texts.length > 0) await mutate($, cur => markSent(cur, d.id))
  const asked = texts.length > 0 ? `\n${commentNote(d, texts, false)}` : ''
  await tellModel($, `[desk] The user wants to discuss this decision further; it stays open.\n${decisionBrief(d)}${asked}`)
  const picked = d.pick ? `\n고른 것 (아직 답 아님): ${d.pick}` : ''
  await $.prompt.submit({ text: `${one.id} 더 논의: ${one.question}${picked}${texts.length > 0 ? `\n내 코멘트: ${texts.join('\n')}` : ''}` })
}

type Saved = (d: DeskData) => string | undefined
type Save = (d: DeskData, value: string, now: number) => Outcome | DeskData

/** A desk field, drawn under its name and the revision its last Enter left; `post` is its Enter, `save` by default. */
const field = ($: $, marks: Readonly<Record<string, DeskField>>, name: string, savedOf: Saved, save: Save, post: Save = save): Field => ({
  key: `${name}~${marks[name]?.rev ?? 0}`,
  onInput: value => void fieldInput($, name, value, savedOf, save),
  onSubmit: value => void fieldSubmit($, name, value, post),
})

// A terminal field edits only its end: a key appends, Backspace drops the
// last character, so a person empties a field one character at a time. After
// Enter it holds its own text emptied until it is drawn again, and a Backspace
// there reports ''. So right after Enter an empty change over a saved text
// longer than one character is that emptied copy, not a deletion, and is dropped.
const fieldInput = async ($: $, name: string, value: string, savedOf: Saved, save: Save) => {
  const mark = (await read($, fields))[name]
  if (mark?.submitted) {
    if (value === '' && [...(savedOf(await deskNow($)) ?? '')].length > 1) return
    await update($, fields, f => ({ ...f, [name]: { rev: f[name]?.rev ?? mark.rev } }))
  }
  await mutate($, (d, now) => save(d, value, now))
}

// Saved first, then drawn under a new key: the terminal empties the text it
// holds under the old one when the submit settles, and a new key shows `value`.
const fieldSubmit = async ($: $, name: string, value: string, save: Save) => {
  await mutate($, (d, now) => save(d, value, now))
  const now = await $.clock.now()
  await update($, fields, f => ({ ...f, [name]: { rev: Math.max(now, (f[name]?.rev ?? 0) + 1), submitted: true as const } }))
}
