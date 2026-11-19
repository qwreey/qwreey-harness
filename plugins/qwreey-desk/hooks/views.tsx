// The desk's detail views: a decision, a step, the outbox. Each is a fixed
// header row (the way back and what the view shows), then a body that scrolls
// inside the pane a piece at a time, then any footer rows the view pins. The
// body is built as pieces of known height, so the window knows every row it
// holds; register.tsx holds the state and the handlers.

import type { ElementTable, EngineInterface, RenderElement, RenderSurface, ThemeKey } from 'claude-code'

import type { DeskData, DeskDecision, DeskStep, DeskView } from '../types'
import { STEP_WORD, URGENCY_WORD, ago, drafts, unsent, urgencyOf } from './model'
import { BAR, STEP_MARK, cells, detailRegions, pageOf, rule, wrap } from './layout'
import { markdownRows, textRows } from './richtext'
import type { Span } from './richtext'
import type { Line, Tone } from './layout'

export type Els = ReturnType<EngineInterface['ui']['resolve']>

export const TONE: Record<Tone, { dimColor?: boolean; bold?: boolean; color?: ThemeKey }> = {
  plain: {},
  dim: { dimColor: true },
  strong: { bold: true },
  accent: { bold: true, color: 'suggestion' },
  ok: { color: 'success' },
  code: { color: 'permission' },
  warn: { color: 'warning' },
  alert: { bold: true, color: 'error' },
}

/** An Input's wiring: the key it is drawn under now, and what its change and Enter do. */
export type Field = { key: string; onInput: (value: string) => void; onSubmit: (value: string) => void }

/** What the views' controls do; register.tsx binds each to the session. */
export type Do = {
  open: (next: DeskView) => void
  /** Moves the body `by` pieces, never past `last`. */
  scroll: (by: number, last: number) => void
  pick: (one: DeskDecision, key: string) => void
  discuss: (one: DeskDecision) => void
  defer: (id: string) => void
  reopen: (id: string) => void
  /** A decision's box for the person's next comment. */
  comment: (id: string) => Field
  cancelDraft: (id: string) => void
  /** The outbox's 전체 메모 field. */
  outboxNote: () => Field
  send: () => void
}

/** A part of a body: `rows` tall at the width it was built for, drawn only while in view. */
type Piece = { rows: number; draw: (els: Els) => RenderElement }

export type Detail = { title: string; pieces: Piece[]; footer?: Piece[] }

const MEMO_ROWS = { min: 3, max: 8 }
const BACK = '← 목록'

export const when = (now: number, at: number) => {
  const span = ago(now, at)
  return span === '방금' ? span : `${span} 전`
}

const answerLabel = (one: DeskDecision): string => {
  const answer = one.answer ?? ''
  const option = one.options.find(o => o.key.toLowerCase() === answer.split(/[\s,.)]/)[0]?.toLowerCase())
  return option && !answer.includes(option.label) ? `${answer} (${option.label})` : answer
}

/** Rows a text takes in a field `columns` wide. */
const textLines = (text: string, columns: number) =>
  text.split('\n').reduce((n, line) => n + (line.trim() === '' ? 1 : wrap(line, columns).length), 0)

/**
 * Cells a focused field's text wraps in. The engine sizes the editor from the
 * site's width (the pane's body), less the hint it draws beside it: the
 * return glyph alone for an empty `submitLabel`, and, when that still leaves
 * half the site, a `new line` hint after it (22 cells, or 17 in a terminal
 * that types the newline with a backslash). The widest hint it may draw.
 */
const fieldColumns = (columns: number) => Math.max(12, columns - ([22, 17].find(h => columns - h >= columns / 2) ?? 3))

/**
 * A field's height, by the pane's height only: drawn the same tall while the
 * person types, so no row above or below it moves, and a longer text scrolls
 * inside it.
 */
const fieldRows = (paneRows: number) => Math.min(MEMO_ROWS.max, Math.max(MEMO_ROWS.min, Math.floor(paneRows / 5)))

const KEYS = 'Enter 저장 · Shift+Enter 줄바꿈'
const COMMENT_KEYS = 'Enter 달기 · Shift+Enter 줄바꿈'
/** Cells a comment's text is indented under its header. */
const COMMENT_INDENT = 2

/**
 * A field pinned at the view's foot across the pane's whole width, which is
 * the width the engine lays a focused editor out in: under its header line,
 * which carries the keys and the save state so nothing follows the text.
 */
const fieldFooter = (head: string, rows: number, field: (els: Els) => RenderElement): Piece => ({
  rows: rows + 1,
  draw: els => {
    const { Box, Text } = els
    return (
      <Box flexDirection="column" height={rows + 1} overflow="hidden">
        <Text dimColor wrap="truncate-end">
          {head}
        </Text>
        <Box height={rows} overflow="hidden">
          {field(els)}
        </Box>
      </Box>
    )
  },
})

// ---- pieces ---------------------------------------------------------------------

const spansOf = (els: Els, row: readonly Span[]) => {
  const { Text } = els
  return (
    <Text wrap="truncate-end">
      {row.length > 0 ? row.map(s => <Text {...TONE[s.tone ?? 'plain']}>{s.text}</Text>) : ' '}
    </Text>
  )
}

const BLANK: Piece = { rows: 1, draw: ({ Text }) => <Text> </Text> }

/** One row: a prefix in a cell `lead` wide, then `body` in the rest of `width`. */
const leadRow = (lead: number, width: number, prefix: readonly Span[], body: (els: Els) => RenderElement): Piece => ({
  rows: 1,
  draw: els => {
    const { Box } = els
    // With no prefix the body is the row: the piece's box in the body column
    // already holds it to `width`, and fewer boxes keep a scroll's redraw cheap.
    if (lead <= 0) return body(els)
    return (
      <Box flexDirection="row" height={1}>
        <Box width={lead} flexShrink={0}>
          {spansOf(els, prefix)}
        </Box>
        <Box width={Math.max(1, width - lead)} flexShrink={0}>
          {body(els)}
        </Box>
      </Box>
    )
  },
})

/**
 * `text` wrapped to `width`, each source line on its own rows; with a prefix,
 * its first row carries it and the rest continue under the text.
 */
const textPieces = (text: string, width: number, tone: Tone = 'plain', prefix?: { spans: Span[]; width: number }): Piece[] => {
  const lead = prefix?.width ?? 0
  const rows = textRows(text, Math.max(4, width - lead), tone)
  return rows.map((row, i) => leadRow(lead, width, i === 0 && prefix ? prefix.spans : [], els => spansOf(els, row)))
}

/** Buttons side by side, as many rows as the width needs; each `[ label ]` four cells wider than its label. */
const buttonRows = (buttons: readonly { key: string; label: string; draw: (els: Els) => RenderElement }[], width: number): Piece[] => {
  const rows: (typeof buttons)[number][][] = []
  let used = 0
  for (const b of buttons) {
    const w = cells(b.label) + 4
    const row = rows[rows.length - 1]
    if (row && used + 1 + w <= width) {
      row.push(b)
      used += 1 + w
    } else {
      rows.push([b])
      used = w
    }
  }
  return rows.map(row => ({
    rows: 1,
    draw: els => {
      const { Box } = els
      return (
        <Box flexDirection="row" gap={1} height={1}>
          {row.map(b => b.draw(els))}
        </Box>
      )
    },
  }))
}

/** The recommended option when the pick differs from it, else undefined. */
// A recommended key with no matching option still gets a stand-in, so the note shows.
const passedOver = (one: DeskDecision): { key: string; label: string } | undefined => {
  if (!one.recommended || !one.pick || one.pick === one.recommended) return undefined
  return one.options.find(o => o.key === one.recommended) ?? { key: one.recommended, label: '' }
}

/** Rows naming the passed-over recommendation, plus a nudge when no reason goes with it. */
const offRecommendation = (one: DeskDecision, note: string, width: number, hang?: { spans: Span[]; width: number }): Piece[] => {
  const rec = passedOver(one)
  if (!rec) return []
  // A comment on this decision, or the outbox note naming it, counts as the reason.
  const hasReason = unsent(one).some(c => c.text.trim() !== '') || (one.draft ?? '').trim() !== '' || note.includes(one.id)
  return [
    ...textPieces(`권장은 ${rec.key})${rec.label ? ` ${rec.label}` : ''} 이었음`, width, 'dim', hang),
    ...(hasReason ? [] : textPieces('권장과 다른 답인데 이유가 없음: 코멘트로 한 줄 남기면 좋음', width, 'warn', hang)),
  ]
}

/** Puts a blank row between groups of pieces, leaving out the empty ones. */
const sections = (...groups: Piece[][]): Piece[] =>
  groups.filter(g => g.length > 0).flatMap((g, i) => (i === 0 ? g : [BLANK, ...g]))

// Mobile draws no field; its table still answers `Input` (as an empty
// stand-in), so the surface decides, not the table.
const inputOf = (els: Els, surface: RenderSurface) => (surface === 'mobile' ? undefined : (els as ElementTable<'terminal'>).Input)

// ---- the three views ------------------------------------------------------------------

export const decisionDetail = (
  d: DeskData,
  one: DeskDecision,
  now: number,
  surface: RenderSurface,
  columns: number,
  paneRows: number,
  act: Do,
): Detail => {
  const width = columns - BAR
  const isOpen = one.status !== 'answered'
  const keyWidth = Math.max(0, ...one.options.map(o => cells(o.key))) + 2
  const draft = one.draft ?? ''
  const saved = draft && one.draftAt ? ` · 저장됨 ${when(now, one.draftAt)}` : ''
  const picked = one.pick ? one.options.find(o => o.key === one.pick) : undefined
  const waiting = drafts(d).length

  const options = one.options.map(o => {
    const isRecommended = o.key === one.recommended
    const isPicked = o.key === one.pick
    const strong: Tone = isRecommended || isPicked ? 'strong' : 'plain'
    const label = `${isPicked ? '✓ ' : ''}${o.label}${isRecommended ? ' ★권장' : ''}`
    const key = [{ text: `${o.key})`, tone: strong }]
    // A button's label stays on its row; what it cannot hold follows under it.
    const labelRows = wrap(label, Math.max(4, width - keyWidth - (isOpen ? 4 : 0)))
    const head = isOpen
      ? leadRow(keyWidth, width, key, ({ Button }) => (
          <Button key={`opt-${o.key}`} variant={isPicked ? 'primary' : undefined} onPress={() => act.pick(one, o.key)}>
            {labelRows[0] ?? ''}
          </Button>
        ))
      : leadRow(keyWidth, width, key, els => spansOf(els, [{ text: labelRows[0] ?? '' }]))
    const rest = labelRows.slice(1).map(text => leadRow(keyWidth + (isOpen ? 2 : 0), width, [], els => spansOf(els, [{ text }])))
    const why = o.why ? textPieces(o.why, width, 'dim', { spans: [], width: keyWidth }) : []
    return [head, ...rest, ...why]
  })

  const recommended = one.recommended
    ? textPieces(one.recommendedWhy ?? '', width, 'plain', {
        spans: [{ text: `권장 ${one.recommended}`, tone: 'ok' }],
        width: cells(`권장 ${one.recommended}`) + 2,
      })
    : []
  const choice = picked
    ? [...textPieces(`선택: ${picked.key}) ${picked.label} (보내기 전, 다시 누르면 취소)`, width, 'warn'), ...offRecommendation(one, d.outboxNote ?? '', width)]
    : []
  const answer = one.status === 'answered' ? textPieces(answerLabel(one), width, 'ok', { spans: [{ text: '답', tone: 'ok' }], width: 3 }) : []

  // The thread, oldest first: each comment under a header saying whose and
  // when, its text indented under it; the agent's marked by the arrow.
  const thread = one.comments ?? []
  const comments: Piece[] =
    thread.length === 0
      ? []
      : [
          leadRow(0, width, [], els => spansOf(els, [{ text: rule(`코멘트 ${thread.length}`, columns).text, tone: 'dim' }])),
          ...thread.flatMap(c => [
            ...textPieces(
              `${c.by === 'agent' ? '▸ 에이전트' : '나'} · ${when(now, c.at)}${c.by === 'user' && !c.sent ? ' · 보내기 전' : ''}`,
              width,
              c.by === 'agent' ? 'accent' : 'dim',
            ),
            ...textPieces(c.text, width, 'plain', { spans: [], width: COMMENT_INDENT }),
          ]),
        ]
  // Mobile draws no field: a comment is written in chat.
  const memoText: Piece[] = surface === 'mobile' ? textPieces(`코멘트는 채팅에 "${one.id} 코멘트: ..." (${surface})`, width, 'dim') : []
  const rows = fieldRows(paneRows)
  const lines = textLines(draft, fieldColumns(columns))
  const memoField: Piece[] =
    surface === 'mobile'
      ? []
      : [
          fieldFooter(
            ['새 코멘트' + saved, COMMENT_KEYS, ...(lines > rows ? [`${lines}줄 중 ${rows}줄씩 보임`] : [])].join(' · '),
            rows,
            els => {
              const Input = inputOf(els, surface)
              const field = act.comment(one.id)
              return Input ? (
                <Input
                  key={field.key}
                  placeholder="코멘트 쓰기 (Enter 로 달면 보내기에 담김)"
                  rows={rows}
                  value={draft}
                  submitLabel=""
                  onInput={field.onInput}
                  onSubmit={field.onSubmit}
                />
              ) : (
                <els.Text> </els.Text>
              )
            },
          ),
        ]

  const buttons = buttonRows(
    [
      ...(waiting > 0
        ? [{ key: 'outbox', label: `보내기 (${waiting})`, draw: ({ Button }: Els) => <Button key="outbox" variant="primary" onPress={() => act.open({ outbox: true })}>보내기 ({waiting})</Button> }]
        : []),
      { key: 'discuss', label: '이걸로 더 논의', draw: ({ Button }: Els) => <Button key="discuss" onPress={() => act.discuss(one)}>이걸로 더 논의</Button> },
      ...(one.status === 'open'
        ? [{ key: 'defer', label: '나중에', draw: ({ Button }: Els) => <Button key="defer" dimColor onPress={() => act.defer(one.id)}>나중에</Button> }]
        : []),
      ...(one.status === 'deferred'
        ? [{ key: 'reopen', label: '다시 열기', draw: ({ Button }: Els) => <Button key="reopen" dimColor onPress={() => act.reopen(one.id)}>다시 열기</Button> }]
        : []),
    ],
    width,
  )

  const status = one.status === 'open' ? `답을 기다림 · ${URGENCY_WORD[urgencyOf(one)]}` : one.status === 'deferred' ? '미룸' : '답함'
  return {
    title: `${one.id} · ${status}`,
    pieces: sections(
      [...textPieces(one.question, width, 'strong'), ...(one.blocks ? textPieces(`기다리는 것: ${one.blocks}`, width, 'dim') : [])],
      one.context ? markdownRows(one.context, width).map(row => leadRow(0, width, [], els => spansOf(els, row))) : [],
      ...options,
      [...recommended, ...choice, ...answer],
      comments,
      memoText,
      buttons,
    ),
    footer: memoField,
  }
}

/** What the outbox holds, each draft cancellable, then one remark over all; 전송 pinned at its foot. */
export const outboxDetail = (d: DeskData, surface: RenderSurface, columns: number, paneRows: number, act: Do): Detail => {
  const width = columns - BAR
  const list = drafts(d)
  const overall = d.outboxNote ?? ''
  const idWidth = Math.max(4, ...list.map(one => cells(one.id) + 1))
  const items = list.map(one => {
    const option = one.pick ? one.options.find(o => o.key === one.pick) : undefined
    const hang = { spans: [], width: idWidth }
    return [
      ...textPieces(one.question, width, 'plain', { spans: [{ text: one.id, tone: 'strong' }], width: idWidth }),
      ...(one.pick ? textPieces(`→ ${one.pick})${option ? ` ${option.label}` : ''}`, width, 'warn', hang) : []),
      ...offRecommendation(one, overall, width, hang),
      ...unsent(one).flatMap(c => textPieces(`코멘트: ${c.text.trim().split('\n')[0] ?? ''}`, width, 'dim', hang)),
      leadRow(idWidth, width, [], ({ Button }) => (
        <Button key={`cancel-${one.id}`} plain dimColor onPress={() => act.cancelDraft(one.id)}>
          취소
        </Button>
      )),
    ]
  })
  const rows = fieldRows(paneRows)
  const note: Piece[] =
    surface === 'mobile'
      ? []
      : [
          fieldFooter(`전체 메모 (여러 결정에 걸친 말, 함께 보냄) · ${KEYS}`, rows, els => {
            const Input = inputOf(els, surface)
            const field = act.outboxNote()
            return Input ? (
              <Input
                key={field.key}
                placeholder="예: Q3 과 Q4 는 합칠 수 있을 듯"
                rows={rows}
                value={overall}
                submitLabel=""
                onInput={field.onInput}
                onSubmit={field.onSubmit}
              />
            ) : (
              <els.Text> </els.Text>
            )
          }),
        ]
  const canSend = list.length > 0 || overall.trim() !== ''
  return {
    title: `보낼 것 ${list.length}개 · 전송하면 한 번에 보냄`,
    pieces: sections(
      list.length === 0 ? textPieces('고른 답이나 보낼 메모가 없음', width, 'dim') : [],
      ...items,
      surface === 'mobile' && overall ? textPieces(`전체 메모: ${overall}`, width) : [],
    ),
    footer: [
      ...note,
      {
      rows: 1,
      draw: ({ Button, Text }) =>
        canSend ? (
          <Button key="send" variant="primary" onPress={() => act.send()}>
            전송
          </Button>
        ) : (
          <Text> </Text>
        ),
      },
    ],
  }
}

export const stepDetail = (d: DeskData, s: DeskStep, now: number, columns: number): Detail => {
  const width = columns - BAR
  const index = d.plan.findIndex(x => x.id === s.id)
  const times = [s.startedAt ? `시작 ${when(now, s.startedAt)}` : '', s.endedAt ? `끝 ${when(now, s.endedAt)}` : '']
    .filter(Boolean)
    .join(' · ')
  const tone: Tone = s.state === 'done' ? 'dim' : s.state === 'doing' ? 'accent' : 'plain'
  return {
    title: `${s.id} · ${STEP_WORD[s.state]} · ${index + 1}/${d.plan.length}단계`,
    pieces: sections(
      textPieces(s.text, width, 'strong', { spans: [{ text: STEP_MARK[s.state], tone }], width: 2 }),
      s.detail ? textPieces(s.detail, width) : textPieces('설명 없음', width, 'dim'),
      times ? textPieces(times, width, 'dim') : [],
    ),
  }
}

// ---- drawing ------------------------------------------------------------------------

/** The body's rows for each piece, as the scroll bound reads them. */
export const heightsOf = (detail: Detail) => detail.pieces.map(p => p.rows)

/** Rows the view pins at its foot. */
export const footerRows = (detail: Detail) => (detail.footer ?? []).reduce((n, p) => n + p.rows, 0)

/** One marker row: blank, or a dim button that scrolls the body. */
const markerRow = (els: Els, l: Line, width: number, onPress: (by: number) => void) => {
  const { Box, Button, Text } = els
  const act = l.act
  return (
    <Box flexDirection="row" height={1}>
      <Box width={width} flexShrink={0}>
        {act?.kind === 'scroll' && l.key ? (
          <Button key={l.key} plain hotkey={l.hotkey} onPress={() => onPress(act.by)}>
            <Text dimColor>{l.text}</Text>
          </Button>
        ) : (
          <Text> </Text>
        )}
      </Box>
    </Box>
  )
}

/**
 * A detail view drawn exactly `rows` tall: the header row with the way back,
 * the body's window between its markers with the bar beside it, the footer.
 */
export const drawDetail = (els: Els, detail: Detail, stored: number, rows: number, columns: number, act: Do) => {
  const { Box, Button, Text } = els
  const room = detailRegions(rows, footerRows(detail))
  const width = columns - BAR
  const page = pageOf(heightsOf(detail), stored, room.body, columns)
  const shown = detail.pieces.slice(page.offset, page.end)
  const scroll = (by: number) => act.scroll(by, page.last)
  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      <Box flexDirection="row" height={1} gap={2}>
        <Box width={cells(BACK)} flexShrink={0}>
          <Button key="back" plain onPress={() => act.open({})}>
            {BACK}
          </Button>
        </Box>
        <Box width={Math.max(1, columns - cells(BACK) - 2)} flexShrink={0}>
          <Text dimColor wrap="truncate-end">
            {detail.title}
          </Text>
        </Box>
      </Box>
      {markerRow(els, page.top, width, scroll)}
      <Box flexDirection="row" height={room.body}>
        <Box flexDirection="column" width={width} height={room.body} overflow="hidden" flexShrink={0}>
          {shown.map(p => (
            <Box flexDirection="column" height={p.rows} overflow="hidden" flexShrink={0}>
              {p.draw(els)}
            </Box>
          ))}
        </Box>
        <Box flexDirection="column" width={BAR} flexShrink={0}>
          {page.bar.map(c => (
            <Text dimColor> {c}</Text>
          ))}
        </Box>
      </Box>
      {markerRow(els, page.bottom, width, scroll)}
      {(detail.footer ?? []).map(p => (
        <Box flexDirection="column" height={p.rows} overflow="hidden" flexShrink={0}>
          {p.draw(els)}
        </Box>
      ))}
    </Box>
  )
}
