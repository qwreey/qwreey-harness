// Rows of styled text for the detail views: spans, wrapping, a small markdown
// subset and GFM tables, as plain data like layout.ts (which holds the width
// counting and the layout caches this file uses).

import { cellsOf, cells, keep, laidOut } from './layout'
import type { Tone } from './layout'

const textKept = new Map<string, Span[][]>()
const markdownKept = new Map<string, Span[][]>()

/** A run of one style inside a row. */
export type Span = { text: string; tone?: Tone }

/**
 * `spans` as rows of at most `width` cells, broken at spaces where one falls
 * in the row (else mid-word, as Korean is), each run keeping its style.
 */
export const wrapSpans = (spans: readonly Span[], width: number): Span[][] => {
  const rows: Span[][] = []
  let row: Span[] = []
  let used = 0
  const put = (text: string, tone?: Tone) => {
    const tail = row[row.length - 1]
    if (tail && tail.tone === tone) tail.text += text
    else row.push(tone ? { text, tone } : { text })
    used += cells(text)
  }
  const close = () => {
    const tail = row[row.length - 1]
    if (tail) tail.text = tail.text.trimEnd()
    rows.push(row.filter(s => s.text !== ''))
    row = []
    used = 0
  }
  for (const span of spans) {
    for (const part of span.text.split(/(\s+)/)) {
      if (part === '') continue
      if (/^\s+$/.test(part)) {
        if (used > 0 && used < width) put(' ', span.tone)
        continue
      }
      if (used > 0 && used + cells(part) > width) close()
      let rest = part
      while (cells(rest) > width - used) {
        let head = ''
        let headCells = 0
        for (const ch of rest) {
          const w = cellsOf(ch.codePointAt(0) ?? 0)
          if (headCells + w > width - used) break
          head += ch
          headCells += w
        }
        if (head === '' && used > 0) {
          close()
          continue
        }
        // A cell narrower than one wide glyph still takes it, cut by its row.
        if (head === '') head = [...rest][0] ?? ''
        put(head, span.tone)
        close()
        rest = rest.slice(head.length)
      }
      if (rest !== '') put(rest, span.tone)
    }
  }
  if (row.length > 0 || rows.length === 0) close()
  return rows
}

/** Plain `text` in one tone as rows of at most `width` cells, each source line on its own rows, a blank line one empty row. */
export const textRows = (text: string, width: number, tone: Tone = 'plain'): Span[][] =>
  keep(textKept, `${width}:${tone}:${text}`, () => {
    laidOut.text += 1
    return text.split('\n').flatMap(line => (line.trim() === '' ? [[] as Span[]] : wrapSpans([{ text: line, tone }], width)))
  })

// `**bold**`, `__bold__`, `` `code` `` and `[text](url)`; anything else is drawn as written.
const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/
const MD_LINK = /^\[([^\]]+)\]\(([^)\s]+)\)$/

const spansOf = (text: string, tone: Tone | undefined, urls: boolean): Span[] =>
  text
    .split(INLINE)
    .filter(part => part !== '')
    .flatMap((part): Span[] => {
      const link = MD_LINK.exec(part)
      if (link) {
        const label = { text: link[1] ?? '', ...(tone ? { tone } : {}) }
        return urls ? [label, { text: ` (${link[2] ?? ''})`, tone: 'dim' }] : [label]
      }
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return [{ text: part.slice(1, -1), tone: 'code' }]
      if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__')))
        return [{ text: part.slice(2, -2), tone: 'strong' }]
      return [{ text: part, ...(tone ? { tone } : {}) }]
    })

const plain = (spans: readonly Span[]) => spans.map(s => s.text).join('')

/** A line's styled runs: a link as its text, its address after it, dim, only where the line still fits `width` with it. */
const inline = (text: string, tone?: Tone, width = 0): Span[] => {
  const full = spansOf(text, tone, true)
  return width > 0 && cells(plain(full)) <= width ? full : spansOf(text, tone, false)
}

// ---- GFM tables -----------------------------------------------------------------------

const TABLE_RULE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/

/** A table row's cells: the outer pipes dropped, split at each pipe not escaped. */
const tableCells = (line: string): string[] =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/(?<!\\)\|$/, '')
    .split(/(?<!\\)\|/)
    .map(c => c.trim().replace(/\\\|/g, '|'))

const GAP = 2

/**
 * A table as rows: a grid with its columns aligned and a dim rule under the
 * header when every column fits `width`, as wide glyphs count; else each body
 * row stacked, its first cell bold on a line and each other cell under it as
 * `header: value` (the value alone under an empty header), a blank row
 * between body rows. A phone's 40 cells rarely hold a grid.
 */
const tableRows = (head: readonly string[], rightAligned: readonly boolean[], body: readonly string[][], width: number): Span[][] => {
  const all = [head, ...body]
  const widths = head.map((_, i) => Math.max(...all.map(row => cells(plain(spansOf(row[i] ?? '', undefined, false))))))
  const grid = widths.reduce((n, w) => n + w, 0) + GAP * (widths.length - 1)
  if (grid <= width) {
    const line = (row: readonly string[], tone?: Tone): Span[] =>
      row.flatMap((cell, i) => {
        const spans = spansOf(cell, tone, false)
        const pad = ' '.repeat(Math.max(0, (widths[i] ?? 0) - cells(plain(spans))))
        const gap = i < row.length - 1 ? ' '.repeat(GAP) : ''
        return rightAligned[i] ? [{ text: pad }, ...spans, { text: gap }] : [...spans, { text: pad + gap }]
      })
    const trim = (row: Span[]): Span[] => {
      const tail = row[row.length - 1]
      if (tail) tail.text = tail.text.trimEnd()
      return row.filter(s => s.text !== '')
    }
    return [trim(line(head, 'strong')), [{ text: '─'.repeat(grid), tone: 'dim' }], ...body.map(row => trim(line(row)))]
  }
  return body.flatMap((row, r) => [
    ...(r > 0 ? [[] as Span[]] : []),
    ...(row[0] ? wrapSpans(spansOf(row[0], 'strong', false), width) : []),
    ...row.slice(1).flatMap((cell, i) => {
      if (cell === '') return []
      const name = head[i + 1] ?? ''
      return hung({ text: '  ' }, [...(name ? [{ text: `${plain(spansOf(name, undefined, false))}: `, tone: 'dim' as const }] : []), ...inline(cell, undefined, width - 2)], width)
    }),
  ])
}

/** Rows of `spans` wrapped under a lead (a bullet, `1. `, `> `), the rows after the first indented by its width. */
const hung = (lead: Span, spans: readonly Span[], width: number): Span[][] => {
  const indent = cells(lead.text)
  return wrapSpans(spans, Math.max(4, width - indent)).map((row, i) => [i === 0 ? lead : { text: ' '.repeat(indent) }, ...row])
}

/**
 * Markdown as rows of at most `width` cells: headings, lists, quotes, rules,
 * fenced code, GFM tables, and bold, code or links inside a line. The engine's own `Markdown`
 * element draws more, but to a height the desk cannot count, and a scrolled
 * body has to know every row it holds. Why not a library (marked): the mod
 * has no dependencies, and a decision's context needs no more than this.
 */
export const markdownRows = (text: string, width: number): Span[][] =>
  keep(markdownKept, `${width}:${text}`, () => {
    laidOut.markdown += 1
    return markdownNow(text, width)
  })

const markdownNow = (text: string, width: number): Span[][] => {
  const rows: Span[][] = []
  let fenced = false
  const lines = text.replace(/\r/g, '').split('\n')
  for (let at = 0; at < lines.length; at += 1) {
    const line = lines[at] ?? ''
    const next = lines[at + 1] ?? ''
    // A header row, then a rule of dashes with a pipe in one of them (a lone
    // `---` under a line is a setext heading's, not a table's).
    const isTable = line.includes('|') && TABLE_RULE.test(next) && next.includes('-') && (next.includes('|') || line.trim().startsWith('|'))
    if (!fenced && isTable) {
      const head = tableCells(line)
      const rightAligned = tableCells(next).map(c => /-:$/.test(c))
      const body: string[][] = []
      at += 2
      while (at < lines.length && (lines[at] ?? '').includes('|') && (lines[at] ?? '').trim() !== '') {
        const cellsIn = tableCells(lines[at] ?? '')
        body.push(head.map((_, i) => cellsIn[i] ?? ''))
        at += 1
      }
      at -= 1
      rows.push(...tableRows(head, rightAligned, body, width))
      continue
    }
    if (/^\s*(```|~~~)/.test(line)) {
      fenced = !fenced
      continue
    }
    if (fenced) {
      rows.push(...(line.trim() === '' ? [[]] : wrapSpans([{ text: line.replace(/\t/g, '  '), tone: 'code' }], width)))
      continue
    }
    if (line.trim() === '') {
      if (rows.length > 0 && (rows[rows.length - 1]?.length ?? 0) > 0) rows.push([])
      continue
    }
    const heading = /^\s{0,3}#{1,6}\s+(.*)$/.exec(line)
    const item = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line)
    const quote = /^\s{0,3}>\s?(.*)$/.exec(line)
    if (/^\s{0,3}([-*_])(\s*\1){2,}\s*$/.test(line)) rows.push([{ text: '─'.repeat(Math.max(1, width)), tone: 'dim' }])
    else if (heading) rows.push(...wrapSpans(inline(heading[1] ?? '', 'strong', width), width))
    else if (item) {
      const depth = Math.min(6, (item[1] ?? '').replace(/\t/g, '  ').length)
      const mark = /\d/.test(item[2] ?? '') ? (item[2] ?? '') : '•'
      const lead = `${' '.repeat(depth)}${mark} `
      rows.push(...hung({ text: lead }, inline(item[3] ?? '', undefined, width - cells(lead)), width))
    } else if (quote) rows.push(...hung({ text: '│ ', tone: 'dim' }, inline(quote[1] ?? '', 'dim', width - 2), width))
    else rows.push(...wrapSpans(inline(line.trim(), undefined, width), width))
  }
  while (rows.length > 0 && (rows[rows.length - 1]?.length ?? 0) === 0) rows.pop()
  return rows
}
