// What the desk's list tabs draw, row by row, as plain data: register.tsx
// turns each row into elements and the tests read the same rows. Every row is
// one terminal line cut to a width counted here, so nothing wraps on its own
// and no region grows or shrinks with what it holds.

import type { DeskData, DeskDecision, DeskLogEntry, DeskStep, DeskTab } from '../types'
import { URGENCIES, ago, oneLine, runningNow, unsent, urgencyOf } from './model'

// Cells a code point takes, as terminals count East Asian widths: Hangul,
// CJK and emoji two, combining marks none, the rest (ambiguous glyphs too)
// one. Why not a library (string-width): the mod has no dependencies, and
// these ranges are all its text needs.
const ZERO: readonly (readonly [number, number])[] = [
  [0x0300, 0x036f],
  [0x1160, 0x11ff],
  [0x200b, 0x200f],
  [0x20d0, 0x20ff],
  [0xfe00, 0xfe0f],
  [0xe0100, 0xe01ef],
]
const WIDE: readonly (readonly [number, number])[] = [
  [0x1100, 0x115f],
  [0x231a, 0x231b],
  [0x2329, 0x232a],
  [0x23e9, 0x23ec],
  [0x23f0, 0x23f0],
  [0x23f3, 0x23f3],
  [0x25fd, 0x25fe],
  [0x2614, 0x2615],
  [0x2648, 0x2653],
  [0x267f, 0x267f],
  [0x2693, 0x2693],
  [0x26a1, 0x26a1],
  [0x26aa, 0x26ab],
  [0x26bd, 0x26be],
  [0x26c4, 0x26c5],
  [0x26ce, 0x26ce],
  [0x26d4, 0x26d4],
  [0x26ea, 0x26ea],
  [0x26f2, 0x26f3],
  [0x26f5, 0x26f5],
  [0x26fa, 0x26fa],
  [0x26fd, 0x26fd],
  [0x2705, 0x2705],
  [0x270a, 0x270b],
  [0x2728, 0x2728],
  [0x274c, 0x274c],
  [0x274e, 0x274e],
  [0x2753, 0x2755],
  [0x2757, 0x2757],
  [0x2795, 0x2797],
  [0x27b0, 0x27b0],
  [0x27bf, 0x27bf],
  [0x2b1b, 0x2b1c],
  [0x2b50, 0x2b50],
  [0x2b55, 0x2b55],
  [0x2e80, 0x303e],
  [0x3041, 0x33ff],
  [0x3400, 0x4dbf],
  [0x4e00, 0x9fff],
  [0xa000, 0xa4cf],
  [0xa960, 0xa97f],
  [0xac00, 0xd7a3],
  [0xf900, 0xfaff],
  [0xfe10, 0xfe19],
  [0xfe30, 0xfe6f],
  [0xff00, 0xff60],
  [0xffe0, 0xffe6],
  [0x1f000, 0x1faff],
  [0x20000, 0x3fffd],
]
const within = (ranges: readonly (readonly [number, number])[], c: number) => ranges.some(([a, b]) => c >= a && c <= b)

// Latin and Hangul syllables first: they are nearly all the desk's text, and
// the range lists are walked once per glyph otherwise.
export const cellsOf = (c: number): number =>
  c < 0x20 ? 0 : c < 0x300 ? 1 : c >= 0xac00 && c <= 0xd7a3 ? 2 : within(ZERO, c) ? 0 : within(WIDE, c) ? 2 : 1

export const cells = (text: string): number => {
  let n = 0
  for (const ch of text) n += cellsOf(ch.codePointAt(0) ?? 0)
  return n
}

/**
 * How many times each kind of text was laid out rather than found kept; the
 * tests read it to see that drawing again at the same width lays out nothing.
 */
export const laidOut = { markdown: 0, text: 0, wrap: 0 }

// Up to this many results of each layout are kept, the oldest dropped first:
// a scroll draws the same texts at the same width again, and wrapping them
// glyph by glyph was most of what a scroll step cost.
const KEEP = 512

/** `make()`'s result kept under `key`; what it returns is shared, so callers never change it. */
export const keep = <T>(kept: Map<string, T>, key: string, make: () => T): T => {
  const hit = kept.get(key)
  if (hit !== undefined) return hit
  const made = make()
  if (kept.size >= KEEP) kept.delete(kept.keys().next().value as string)
  kept.set(key, made)
  return made
}

const wrapKept = new Map<string, string[]>()

const ELLIPSIS = '…'

/** `text` cut to `width` cells, an ellipsis where it was cut. */
export const fit = (text: string, width: number): string => {
  if (cells(text) <= width) return text
  const room = width - cells(ELLIPSIS)
  if (room <= 0) return ''
  let out = ''
  let used = 0
  for (const ch of text) {
    const w = cellsOf(ch.codePointAt(0) ?? 0)
    if (used + w > room) break
    out += ch
    used += w
  }
  return out.trimEnd() + ELLIPSIS
}

export const padStart = (text: string, width: number): string => ' '.repeat(Math.max(0, width - cells(text))) + text

/**
 * `text` as lines of at most `width` cells, broken at spaces where one falls
 * in the line (else mid-word, as Korean is), at most `maxLines`, the last cut.
 */
export const wrap = (text: string, width: number, maxLines = Number.POSITIVE_INFINITY): string[] =>
  keep(wrapKept, `${width}:${maxLines}:${text}`, () => {
    laidOut.wrap += 1
    return wrapNow(text, width, maxLines)
  })

const wrapNow = (text: string, width: number, maxLines: number): string[] => {
  const lines: string[] = []
  let rest = oneLine(text)
  while (rest !== '' && lines.length < maxLines) {
    if (cells(rest) <= width || lines.length === maxLines - 1) {
      lines.push(fit(rest, width))
      break
    }
    const chars = [...rest]
    let used = 0
    let end = 0
    let lastSpace = -1
    while (end < chars.length) {
      const w = cellsOf(chars[end]?.codePointAt(0) ?? 0)
      if (used + w > width) break
      if (chars[end] === ' ') lastSpace = end
      used += w
      end += 1
    }
    const cut = lastSpace > 0 && chars[end] !== ' ' ? lastSpace : Math.max(1, end)
    lines.push(chars.slice(0, cut).join('').trimEnd())
    rest = chars.slice(cut).join('').trimStart()
  }
  return lines.length > 0 ? lines : ['']
}

export type Tone = 'plain' | 'dim' | 'strong' | 'accent' | 'ok' | 'code' | 'warn' | 'alert'

/** What pressing a row does; register.tsx holds the handlers. */
export type Act =
  | { kind: 'decision'; id: string }
  | { kind: 'step'; id: string }
  | { kind: 'outbox' }
  | { kind: 'scroll'; by: number }

/**
 * One row: a prefix in a cell of the list's fixed width, then text in the
 * rest, so a title's second line starts under its first, not under the id.
 * A `rule` row is one dim line across the whole row instead.
 */
export type Line = {
  /** Drawn before the prefix inside its cell, in its own style: a decision's urgency. */
  mark?: { text: string; tone: Tone }
  prefix: string
  prefixTone?: Tone
  text: string
  tone?: Tone
  act?: Act
  key?: string
  hotkey?: string
  rule?: true
}

/**
 * One entry of a list: its rows, then the row drawn between it and the next.
 * `most` is the rows it can take at any width, which the scroll keys go by.
 */
export type Item = { rows: Line[]; gap?: Line; most: number }

export type List = {
  items: Item[]
  /** The prefix cell's width, the same for every row of the list. */
  prefix: number
  /** Where the list opens until the person scrolls it. */
  auto: number
  /**
   * The list may scroll until `auto` is its first item, however little
   * follows: the timeline keeps the step in hand at the top, the finished
   * ones above it, reached by scrolling up.
   */
  keepsAutoAtTop?: true
  /** Items follow each other with no row between them: the work log's feed. */
  tight?: true
  empty: string
}

const BLANK: Line = { prefix: '', text: '' }

// Rows taken by the fixed parts around the list; the tests read them too.
export const regions = (rows: number) => {
  const footer = rows >= 14 ? 3 : 0
  const top = rows >= 8 ? 2 : 1
  const list = Math.max(3, rows - top - footer)
  return { top, list, body: list - 2, footer }
}

/** The cells the bar column takes at the right of a list row: a space and the bar. */
export const BAR = 2

/** Width of the text cell of a list row, for a body `columns` wide. */
export const textWidth = (columns: number, prefix: number) => Math.max(4, columns - BAR - prefix)

const RULE = '─'

/** A dim rule across the row with a label near its left end, where two groups meet. */
export const rule = (label: string, columns: number): Line => {
  const head = `${RULE}${RULE} ${label} `
  return { prefix: '', text: head + RULE.repeat(Math.max(2, columns - BAR - cells(head))), tone: 'dim', rule: true }
}

// ---- the three tabs' lists -------------------------------------------------

const decisionNote = (one: DeskDecision): string => {
  if (one.status === 'answered') return `답: ${oneLine(one.answer ?? '')}`
  // What the person drafted and has not sent comes first.
  const drafted = [one.pick ? `● 선택 ${one.pick}` : '', unsent(one).length > 0 ? '✎ 코멘트' : ''].filter(Boolean)
  if (drafted.length > 0) return `${drafted.join(' · ')} (보내기 전)`
  const parts: string[] = []
  if (one.status === 'deferred') parts.push('미룸')
  const last = one.comments?.at(-1)
  if (last) parts.push(`${last.by === 'agent' ? '▸ 에이전트' : '나'}: ${oneLine(last.text)}`)
  else if (one.recommended) {
    const option = one.options.find(o => o.key === one.recommended)
    parts.push(`권장 ${one.recommended}${option ? `) ${option.label}` : ''}`)
  } else if (one.options.length > 0) parts.push(`선택지 ${one.options.length}개`)
  return parts.join(' · ')
}

/** Lines a decision's question wraps to in the list; the rest is in its detail view. */
const QUESTION_LINES = 2

/**
 * The urgency mark before an open decision's id, always MARK cells wide so
 * no id moves with it: `!!` work waits on it, `!` the next steps do.
 */
const MARK = 3
const markOf = (one: DeskDecision): { text: string; tone: Tone } => {
  if (one.status !== 'open') return { text: ' '.repeat(MARK), tone: 'plain' }
  const urgency = urgencyOf(one)
  return urgency === 'blocking'
    ? { text: '!! ', tone: 'alert' }
    : urgency === 'soon'
      ? { text: '!  ', tone: 'warn' }
      : { text: ' '.repeat(MARK), tone: 'plain' }
}

const rank = (one: DeskDecision) => URGENCIES.indexOf(urgencyOf(one))

/**
 * The note row's prefix: how many comments the thread holds, under the id,
 * and in the urgency mark's cell a dot while an agent comment is unread.
 * At most 4 cells after the mark, inside the narrowest id cell.
 */
const threadMark = (one: DeskDecision): Pick<Line, 'mark' | 'prefix' | 'prefixTone'> => {
  const count = one.comments?.length ?? 0
  if (count === 0) return { prefix: '' }
  return {
    mark: one.unread ? { text: '●  ', tone: 'accent' } : { text: ' '.repeat(MARK), tone: 'plain' },
    prefix: `[${Math.min(count, 99)}]`,
    prefixTone: 'dim',
  }
}

const decisionItem = (one: DeskDecision, width: number): Item => {
  const done = one.status === 'answered'
  const title = wrap(one.question, width, QUESTION_LINES)
  const note = decisionNote(one)
  return {
    rows: [
      ...title.map((text, i): Line =>
        i === 0
          ? { mark: markOf(one), prefix: one.id, prefixTone: done ? 'dim' : 'strong', text, tone: done ? 'dim' : 'plain', act: { kind: 'decision', id: one.id }, key: `dec-${one.id}` }
          : { prefix: '', text, tone: done ? 'dim' : 'plain' },
      ),
      ...(note ? [{ ...threadMark(one), text: fit(note, width), tone: 'dim' as const }] : []),
    ],
    most: QUESTION_LINES + 1,
  }
}

const lineItem = (line: Line): Item => ({ rows: [line], most: 1 })

// One id cell width for both decision lists, so their texts line up; the
// urgency mark stands in it before the id.
const idCell = (d: DeskData) => MARK + Math.max(4, ...d.decisions.map(one => cells(one.id) + 1))

// Decisions answered before answers were timed carry none: they fall back to
// when they were asked, then to their number, so the order never depends on
// where they happen to sit in the store.
const idNumber = (one: DeskDecision) => Number(/\d+/.exec(one.id)?.[0] ?? 0)
const newestFirst = (a: DeskDecision, b: DeskDecision) =>
  (b.answeredAt ?? b.createdAt ?? 0) - (a.answeredAt ?? a.createdAt ?? 0) || (b.createdAt ?? 0) - (a.createdAt ?? 0) || idNumber(b) - idNumber(a)

/**
 * One list: the decisions still waiting (open, then deferred), a rule, then
 * the answered ones dimmed, newest first, all under one scrollbar.
 */
export const waitList = (d: DeskData, columns: number): List => {
  const prefix = idCell(d)
  const width = textWidth(columns, prefix)
  // Open ones by how much waits on them, then as they were asked; deferred after.
  const open = d.decisions
    .filter(one => one.status === 'open')
    .sort((a, b) => rank(a) - rank(b) || (a.createdAt ?? 0) - (b.createdAt ?? 0) || idNumber(a) - idNumber(b))
  const waiting = [...open, ...d.decisions.filter(one => one.status === 'deferred')]
  const answered = d.decisions
    .filter(one => one.status === 'answered')
    .sort(newestFirst)
  const items = waiting.map(one => decisionItem(one, width))
  if (answered.length > 0) {
    if (waiting.length === 0) items.push(lineItem({ prefix: '', text: '기다리는 결정 없음', tone: 'dim' }))
    items.push(lineItem(rule(`끝난 결정 ${answered.length}`, columns)))
    items.push(...answered.map(one => decisionItem(one, width)))
  }
  return { items, prefix, auto: 0, empty: '기다리는 결정 없음' }
}

export const STEP_MARK = { done: '✓', doing: '◉', todo: '○' } as const
const LINK = '│'
const DETAIL_MARK = '└ '
const TITLE_LINES = 3
const DETAIL_LINES = 2

export const currentIndex = (plan: readonly DeskStep[]): number => {
  const doing = plan.findIndex(s => s.state === 'doing')
  if (doing >= 0) return doing
  const todo = plan.findIndex(s => s.state === 'todo')
  return todo >= 0 ? todo : plan.length - 1
}

/**
 * The plan as a timeline: a node per step and its title, wrapping under
 * itself, then its detail under a dim corner, the line running on to the next.
 */
export const taskList = (d: DeskData, columns: number): List => {
  const prefix = 2
  const width = textWidth(columns, prefix)
  const items = d.plan.map((s, i): Item => {
    const link = i === d.plan.length - 1 ? '' : LINK
    const tone: Tone = s.state === 'done' ? 'dim' : s.state === 'doing' ? 'accent' : 'plain'
    const title = wrap(`${s.id} ${s.text}`, width, TITLE_LINES)
    const detail = s.detail ? wrap(s.detail, width - cells(DETAIL_MARK), DETAIL_LINES) : []
    return {
      rows: [
        ...title.map((text, j): Line =>
          j === 0
            ? { prefix: STEP_MARK[s.state], prefixTone: tone, text, tone, act: { kind: 'step', id: s.id }, key: `step-${s.id}` }
            : { prefix: link, prefixTone: 'dim', text, tone },
        ),
        ...detail.map((text, j): Line => ({
          prefix: link,
          prefixTone: 'dim',
          text: `${j === 0 ? DETAIL_MARK : ' '.repeat(cells(DETAIL_MARK))}${text}`,
          tone: 'dim',
        })),
      ],
      gap: { prefix: LINK, prefixTone: 'dim', text: '' },
      most: TITLE_LINES + DETAIL_LINES,
    }
  })
  return { items, prefix, auto: Math.max(0, currentIndex(d.plan)), keepsAutoAtTop: true, empty: '계획 없음' }
}

export const LOG_MARK = { done: '✓', agent: '▸', decision: '?', note: ' ' } as const
/** `14:02`, then a space and the kind's mark, then a space before the text. */
const LOG_PREFIX = 8
// The narrowest text cell a log entry is wrapped in: a 41-column terminal's
// pane. The scroll keys count each entry at this width, never short of its rows.
const LOG_NARROW = textWidth(39, LOG_PREFIX)

const two = (n: number) => String(n).padStart(2, '0')
/** The entry's time of day, as the machine's clock reads it. */
export const clockOf = (at: number) => {
  const t = new Date(at)
  return `${two(t.getHours())}:${two(t.getMinutes())}`
}
/** The day an entry falls on, the year only when it is not this year's. */
export const dayOf = (at: number, now: number) => {
  const t = new Date(at)
  const year = t.getFullYear() === new Date(now).getFullYear() ? '' : `${t.getFullYear()}년 `
  return `${year}${t.getMonth() + 1}월 ${t.getDate()}일`
}
const dayKey = (at: number) => new Date(at).toDateString()

/** An entry's text as rows `width` wide, every line of it, nothing cut. */
const entryRows = (text: string, width: number) => text.split('\n').flatMap(line => (line.trim() === '' ? [''] : wrap(line, width)))

export const NEW_MARK = '여기부터 새로'

/**
 * The work log as a feed, oldest first and growing at the bottom: each entry
 * whole under its time, a rule where the day changes and one where the
 * entries the person has not seen begin. The model's notes, the summaries,
 * are plain; what the desk logs on its own is dim. It opens where the unseen
 * entries begin, or at its end.
 */
// What a decision entry of the log shows, worked out at render time from the
// decision as it stands now, so entries stored before this existed gain it too.
const DECISION_EVENT = /^(D\d+) (답|올림|코멘트|다듬음|미룸)(?:: ([\s\S]*))?$/
const HANG = '  '

/** The entry's text rows below the first, from the decision; undefined when it is not about a live decision. */
const decisionRows = (l: DeskLogEntry, d: DeskData, width: number): { rows: Line[]; id: string } | undefined => {
  if (l.kind !== 'decision') return undefined
  const m = DECISION_EVENT.exec(l.text)
  const one = m && d.decisions.find(x => x.id === m[1])
  if (!m || !one) return undefined
  const [, id, what, rest = ''] = m
  const option = what === '답' ? one.options.find(o => o.key.toLowerCase() === rest.trim().toLowerCase()) : undefined
  const said = what === '코멘트' ? one.comments?.find(c => c.by === 'agent' && c.at === l.at) : undefined
  const comment = said ? oneLine(said.text.split('\n')[0] ?? '') : ''
  // The comment's first line has its own row below, so the event line is just the event.
  const head = option ? `${id} ${what}: ${option.key}) ${option.label}` : comment ? `${id} ${what}` : l.text
  const sub = (text: string) => wrap(text, Math.max(4, width - cells(HANG))).map((t): Line => ({ prefix: '', text: `${HANG}${t}`, tone: 'dim' }))
  return {
    id: one.id,
    rows: [
      ...entryRows(head, width).map((text): Line => ({ prefix: '', text, tone: 'dim' })),
      // The added line's text is the question itself already.
      ...(what === '올림' ? [] : sub(oneLine(one.question))),
      ...(comment ? sub(`▸ ${comment}`) : []),
    ],
  }
}

// Rows of a decision entry by what they were built from (the entry, the
// decision's question, answer time, comment count, options and the width):
// scrolling redraws the list on every wheel step, so they are laid out once.
const LOG_ROWS_KEPT = 2000
const logRows = new Map<string, { rows: Line[]; id: string } | null>()
const decisionRowsCached = (l: DeskLogEntry, d: DeskData, width: number) => {
  const one = /^(D\d+) /.exec(l.text)?.[1]
  const dec = d.decisions.find(x => x.id === one)
  const key = `${width}|${l.at}|${l.text}|${dec ? `${dec.id}|${dec.status}|${dec.answeredAt ?? 0}|${dec.comments?.length ?? 0}|${dec.question}|${dec.options.map(o => o.key + o.label).join(',')}` : ''}`
  const hit = logRows.get(key)
  if (hit !== undefined) return hit
  const made = decisionRows(l, d, width) ?? null
  if (logRows.size >= LOG_ROWS_KEPT) logRows.clear()
  logRows.set(key, made)
  return made
}

/**
 * The work log as a feed, oldest first and growing at the bottom: each entry
 * whole under its time, a rule where the day changes and one where the
 * entries the person has not seen begin. The model's notes, the summaries,
 * are plain; what the desk logs on its own is dim. It opens where the unseen
 * entries begin, or at its end. An entry about a decision still on the desk
 * names the chosen option and the question under it, and opens the decision.
 */
export const logList = (d: DeskData, since: number, now: number, columns: number): List => {
  const width = textWidth(columns, LOG_PREFIX)
  const items: Item[] = []
  let day = ''
  let auto = Number.MAX_SAFE_INTEGER
  d.log.forEach((l, i) => {
    const isNew = l.at > since
    if (isNew && auto === Number.MAX_SAFE_INTEGER) {
      auto = items.length
      if (i > 0) items.push(lineItem(rule(NEW_MARK, columns)))
    }
    if (dayKey(l.at) !== day) {
      day = dayKey(l.at)
      items.push(lineItem(rule(dayOf(l.at, now), columns)))
    }
    const tone: Tone = l.kind === 'note' ? 'plain' : 'dim'
    const about = decisionRowsCached(l, d, width)
    const rows: Line[] = (about?.rows ?? entryRows(l.text, width).map((text): Line => ({ prefix: '', text, tone }))).map(
      (row, j): Line => ({
        ...row,
        prefix: j === 0 ? `${clockOf(l.at)} ${LOG_MARK[l.kind]}` : '',
        prefixTone: 'dim',
        ...(j === 0 && about ? { act: { kind: 'decision', id: about.id } as Act, key: `log-${i}` } : {}),
      }),
    )
    const narrow = about ? (decisionRowsCached(l, d, Math.min(width, LOG_NARROW))?.rows.length ?? 0) : entryRows(l.text, Math.min(width, LOG_NARROW)).length
    items.push({ rows, most: Math.max(narrow, rows.length) })
  })
  return { items, prefix: LOG_PREFIX, auto, tight: true, empty: '기록 없음' }
}

export const listFor = (tab: DeskTab, d: DeskData, since: number, now: number, columns: number): List =>
  tab === 'tasks' ? taskList(d, columns) : tab === 'away' ? logList(d, since, now, columns) : waitList(d, columns)

// ---- scrolling ---------------------------------------------------------------

/**
 * The last offset that still fills the window: the end of the list at its
 * bottom. `gap` rows stand between two items (a list's blank or link row).
 */
export const lastOffset = (heights: readonly number[], rows: number, gap = 1): number => {
  let used = 0
  for (let i = heights.length - 1; i >= 0; i -= 1) {
    used += (heights[i] ?? 0) + (i < heights.length - 1 ? gap : 0)
    if (used > rows) return i + 1
  }
  return 0
}

const furthest = (list: List, heights: readonly number[], rows: number) =>
  Math.max(lastOffset(heights, rows, list.tight ? 0 : 1), list.keepsAutoAtTop ? Math.min(list.auto, list.items.length - 1) : 0)

/** The furthest offset the list scrolls to, as drawn at this width. */
export const lastOffsetOf = (list: List, rows: number) =>
  furthest(
    list,
    list.items.map(item => item.rows.length),
    rows,
  )

/**
 * Where the scroll keys may move a list without knowing its width: every
 * item counted at its tallest, so the bound is never short of the real end.
 */
export const offsetBound = (list: List, rows: number): number =>
  furthest(
    list,
    list.items.map(item => item.most),
    rows,
  )

export type Window = {
  /** Exactly `rows` rows. */
  body: Line[]
  /** Exactly `rows` cells of the bar, blank when everything shows. */
  bar: string[]
  top: Line
  bottom: Line
  offset: number
}

const THUMB = '┃'
const TRACK = '│'

/**
 * The rows of `list` from its stored offset (or where it opens), in a window
 * `rows` tall. The offset is an item, but the window is cut in rows: an item
 * the window's foot crosses shows its first rows, and at the list's end the
 * last row sits on the window's foot, the item above it showing its last
 * rows. The markers count the items not wholly in view on each side.
 */
export const windowOf = (list: List, stored: number, rows: number, columns: number): Window => {
  const last = lastOffsetOf(list, rows)
  const offset = Math.max(0, Math.min(stored < 0 ? list.auto : stored, last))
  const gap = list.tight ? 0 : 1
  const count = list.items.length
  // Where each item's first row stands in the whole list, its gap row after it.
  const starts: number[] = []
  let total = 0
  for (const item of list.items) {
    starts.push(total)
    total += item.rows.length + gap
  }
  total = Math.max(0, total - gap)
  const startOf = (i: number) => (i < count ? (starts[i] ?? total) : total + gap)
  // The end of the list stops on the window's foot, but the timeline may
  // still bring its step in hand to the top with little after it.
  const furthestStart = Math.max(0, total - rows, list.keepsAutoAtTop && count > 0 ? startOf(Math.min(list.auto, count - 1)) : 0)
  const start = Math.min(startOf(offset), furthestStart)
  const end = start + rows

  // Only the items in view are sliced; their rows are already laid out.
  const body: Line[] = []
  for (let i = 0; i < count && body.length < rows; i += 1) {
    const item = list.items[i]
    const from = starts[i] ?? 0
    const after = from + (item?.rows.length ?? 0)
    if (!item || after + gap <= start) continue
    const skip = Math.max(0, start - from)
    body.push(...item.rows.slice(skip, skip + rows - body.length))
    if (gap && i < count - 1 && after >= start && body.length < rows) body.push(item.gap ?? BLANK)
  }
  if (count === 0) body.push({ prefix: '', text: list.empty, tone: 'dim' })
  while (body.length < rows) body.push(BLANK)

  let above = 0
  let below = 0
  list.items.forEach((item, i) => {
    const from = starts[i] ?? 0
    if (from < start) above += 1
    if (from + item.rows.length > end) below += 1
  })
  const bar = scrollBar(rows, total, offset, last, above > 0 || below > 0)
  const room = textWidth(columns, list.prefix)
  const top = above > 0 ? marker(-1, `위에 ${above}개`, room) : BLANK
  const bottom = below > 0 ? marker(1, `아래 ${below}개`, room) : BLANK
  return { body, bar, top, bottom, offset }
}

/**
 * The bar beside a window `rows` tall: the thumb is the window's share of
 * the `total` rows, so it keeps its size while the content scrolls.
 */
const scrollBar = (rows: number, total: number, offset: number, last: number, scrolls: boolean): string[] => {
  const thumb = scrolls ? Math.max(1, Math.min(rows - 1, Math.round((rows * rows) / Math.max(rows, total)))) : 0
  const thumbTop = last > 0 ? Math.round(((rows - thumb) * offset) / last) : 0
  return Array.from({ length: rows }, (_, i) => (!scrolls ? ' ' : i >= thumbTop && i < thumbTop + thumb ? THUMB : TRACK))
}

/** The row above or below a window saying what is out of view; pressing it scrolls `by`. */
const marker = (by: number, words: string, width: number): Line => ({
  prefix: '',
  // A hotkey's `k: ` is drawn before the label, so the label leaves room for it.
  text: fit(`… ${words}`, width - 3),
  tone: 'dim',
  act: { kind: 'scroll', by },
  key: by < 0 ? 'scroll-up' : 'scroll-down',
  hotkey: by < 0 ? 'k' : 'j',
})

// ---- detail views ------------------------------------------------------------------
// A detail view (a decision, a step, the outbox) is a fixed header row, then
// its body in a window between two marker rows, then the view's own footer
// rows if it pins any; the body is pieces of known height, scrolled a piece
// at a time, most of them one row.

/** Rows of a detail view's parts, `footer` being the rows the view pins at its foot. */
export const detailRegions = (rows: number, footer = 0) => ({ head: 1, body: Math.max(1, rows - 3 - footer), footer })

/** Where a stored offset stands for the end, whatever the width the body is drawn at. */
export const END = Number.MAX_SAFE_INTEGER

export type Page = {
  /** The first piece shown. */
  offset: number
  /** One past the last piece shown. */
  end: number
  /** The furthest offset, as drawn at this width. */
  last: number
  bar: string[]
  top: Line
  bottom: Line
}

/**
 * The pieces of `heights` a body `rows` tall shows from the stored offset;
 * a piece taller than the whole window shows its head.
 */
export const pageOf = (heights: readonly number[], stored: number, rows: number, columns: number): Page => {
  const last = lastOffset(heights, rows, 0)
  const offset = Math.max(0, Math.min(stored, last))
  let end = offset
  let used = 0
  while (end < heights.length && (used + (heights[end] ?? 0) <= rows || end === offset)) {
    used += heights[end] ?? 0
    end += 1
  }
  const sum = (from: number, to: number) => heights.slice(from, to).reduce((n, h) => n + h, 0)
  const above = sum(0, offset)
  const below = sum(end, heights.length)
  const step = detailStep(rows)
  const room = columns - BAR
  return {
    offset,
    end,
    last,
    bar: scrollBar(rows, sum(0, heights.length), offset, last, above > 0 || below > 0),
    top: above > 0 ? marker(-step, `위에 ${above}줄`, room) : BLANK,
    bottom: below > 0 ? marker(step, `아래 ${below}줄`, room) : BLANK,
  }
}

/** How far a marker's press or a page key moves a body `rows` tall: most of a window. */
export const detailStep = (rows: number) => Math.max(1, rows - 2)


// ---- tabs and the footer -------------------------------------------------------

export const TABS: readonly DeskTab[] = ['wait', 'tasks', 'away']
export const TAB_KEY: Record<DeskTab, string> = { wait: '1', tasks: '2', away: '3' }

// Names from widest to narrowest; the first set that fits the width with
// every count at its widest is drawn, so the names change with the pane's
// width only, never with what it counts.
const TAB_NAMES: readonly Record<DeskTab, string>[] = [
  { wait: '답을 기다림', tasks: '작업', away: '기록' },
  { wait: '기다림', tasks: '작업', away: '기록' },
]
const COUNTED: Record<DeskTab, boolean> = { wait: true, tasks: false, away: true }
/** Drawn dim between two tabs; the bare bar only where the spaced one does not fit. */
export const TAB_SEP = ' │ '
const TAB_SEP_TIGHT = '│'
// `1: ` before the name; ` 99` after it while the tab shows a count, so the
// tabs after it stay put as the count changes, and no blank is held for none.
const tabCells = (name: string, count: boolean) => 3 + cells(name) + (count ? 3 : 0)

export type TabRow = { sep: string; tabs: { tab: DeskTab; name: string; count: string; width: number }[] }

export const tabRow = (columns: number, counts: Record<DeskTab, number>): TabRow => {
  const sets = [
    ...TAB_NAMES.map(names => ({ names, sep: TAB_SEP })),
    { names: TAB_NAMES[TAB_NAMES.length - 1]!, sep: TAB_SEP_TIGHT },
  ]
  const chosen =
    sets.find(({ names, sep }) => TABS.reduce((sum, t) => sum + tabCells(names[t], COUNTED[t]), 0) + cells(sep) * (TABS.length - 1) <= columns) ??
    sets[sets.length - 1]!
  return {
    sep: chosen.sep,
    tabs: TABS.map(tab => {
      const shown = COUNTED[tab] && counts[tab] > 0
      return {
        tab,
        name: chosen.names[tab],
        count: shown ? ` ${Math.min(counts[tab], 99)}` : '',
        width: tabCells(chosen.names[tab], shown),
      }
    }),
  }
}

/** The cells a run's age takes in the footer. */
const TIME = 6

/** The rows at the pane's foot under a rule: the step in hand, then what runs. */
export const footer = (d: DeskData, now: number, columns: number): Line[] => {
  const width = textWidth(columns, 2)
  const index = currentIndex(d.plan)
  const step = d.plan[index]
  const stepLine: Line = !step
    ? { prefix: '', text: '계획 없음', tone: 'dim' }
    : step.state === 'done'
      ? { prefix: STEP_MARK.done, prefixTone: 'dim', text: '계획 다 끝남', tone: 'dim' }
      : step.state === 'doing'
        ? { prefix: STEP_MARK.doing, prefixTone: 'accent', text: fit(`${step.id} ${step.text}`, width), tone: 'accent' }
        : { prefix: STEP_MARK.todo, text: fit(`다음 ${step.id} ${step.text}`, width) }
  const runs = runningNow(d)
  const first = runs[0]
  let runLine: Line = { prefix: '', text: '도는 일 없음', tone: 'dim' }
  if (first) {
    const more = runs.length > 1 ? ` 외 ${runs.length - 1}` : ''
    const time = padStart(ago(now, first.startedAt), TIME)
    const label = fit(first.label, width - TIME - 2 - cells(more))
    runLine = { prefix: LOG_MARK.agent, text: `${time}  ${label}${more}` }
  }
  return [rule('지금', columns), stepLine, runLine]
}
