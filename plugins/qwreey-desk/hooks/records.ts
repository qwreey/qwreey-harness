// Decisions and the plan as record files under the project's `.claude/`, in
// the layout of the coderag agent-records skill: written by the desk, read
// back by it, and at times edited by hand, so the reader keeps what it does
// not know and writes it back.
// why not a YAML or markdown library: a mod loads only the plugin's own files,
// and the frontmatter here is the records' subset (`key: value` lines).

import type { DeskComment, DeskDecision, DeskKept, DeskOption, DeskStep, DeskStepState } from '../types'
import { isUrgency, oneLine, optionOf } from './model'

export const PLAN_DIR = '.claude/plan'
export const OPEN_DIR = `${PLAN_DIR}/decisions`
export const DONE_DIR = '.claude/archive/plan/decisions'
export const PLAN_FILE = `${PLAN_DIR}/now.md`
export const PLAN_README = `${PLAN_DIR}/README.md`

// coderag's limit for a description line.
const DESCRIPTION_MAX = 200
const SLUG_WORDS = 6
const SLUG_CHARS = 40

export const README_TEXT = [
  '# plan',
  '',
  '책상(qwreey-desk)이 쓰고 읽는 곳: `now.md` 는 지금 계획, `decisions/` 는 답을 기다리는 결정(`Q<n>-<slug>.md`, 답하면 `.claude/archive/plan/decisions/` 로 옮김). 책상은 커밋하지 않으니 다음 커밋에 함께 넣습니다.',
  'Commits before 2026-11-18 cite desk decisions as D<n>; that is Q<n> here.',
  '',
].join('\n')

// ---- small text helpers --------------------------------------------------------

/** At most `max` characters (code points), cut with `...`. */
const cut = (text: string, max: number): string => {
  const chars = [...text]
  return chars.length <= max ? text : `${chars.slice(0, max - 3).join('').trimEnd()}...`
}

/** A time as ISO 8601 in UTC, its milliseconds left out when zero. */
export const isoTime = (at: number): string => new Date(at).toISOString().replace('.000Z', 'Z')

const timeOf = (text: string | undefined): number | undefined => {
  if (!text) return undefined
  const at = Date.parse(text)
  return Number.isFinite(at) ? at : undefined
}

/** The file name's words: letters and digits of any script, lowercased, a few at most. */
export const slug = (question: string): string => {
  const words = question.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []
  let out = ''
  for (const word of words.slice(0, SLUG_WORDS)) {
    const next = out ? `${out}-${word}` : word
    if ([...next].length > SLUG_CHARS) break
    out = next
  }
  return out
}

export const decisionNumber = (id: string): number => Number(/\d+/.exec(id)?.[0] ?? 0)

const isClosed = (d: DeskDecision) => d.status === 'answered'

/** Where a decision's file goes: open and deferred ones under plan/, answered ones in the archive, under the name it already has. */
export const fileFor = (d: DeskDecision): string => {
  const name = d.file?.split('/').pop() ?? `${d.id}${slug(d.question) ? `-${slug(d.question)}` : ''}.md`
  return `${isClosed(d) ? DONE_DIR : OPEN_DIR}/${name}`
}

// ---- frontmatter (the records' YAML subset) -------------------------------------

// A value YAML would read as something other than this string, or not read at all, goes in double quotes.
const NEEDS_QUOTES = /^[\s\-?:,[\]{}#&*!|>'"%@`]|: |\s#|:$|\s$|^(true|false|yes|no|on|off|null|~)$|^[-+.\d][\d._eE+-]*$/i

export const yamlValue = (text: string): string => (text === '' || NEEDS_QUOTES.test(text) ? JSON.stringify(text) : text)

const readYaml = (raw: string): string => {
  const v = raw.trim()
  if (v.startsWith('"')) {
    try {
      return String(JSON.parse(v))
    } catch {
      return v.slice(1, v.endsWith('"') ? -1 : undefined)
    }
  }
  if (v.startsWith("'")) return v.slice(1, v.endsWith("'") ? -1 : undefined).replace(/''/g, "'")
  return v.replace(/\s+#.*$/, '')
}

type Front = { values: Map<string, string>; other: string[] }

const KNOWN = ['format', 'title', 'description', 'status', 'id', 'urgency', 'blocks', 'recommended', 'created', 'answered', 'answer']

/** The frontmatter's keys the desk reads, and the other lines as they stand (a key's indented or list lines with it). */
const readFront = (lines: readonly string[]): Front => {
  const values = new Map<string, string>()
  const other: string[] = []
  let isOther = false
  for (const line of lines) {
    const m = /^([A-Za-z_][\w-]*):(?:\s(.*))?$/.exec(line)
    if (m && m[1]) {
      const key = m[1].toLowerCase()
      isOther = !KNOWN.includes(key)
      if (isOther) other.push(line)
      else values.set(key, readYaml(m[2] ?? ''))
      continue
    }
    if (isOther || line.trim() !== '') other.push(line)
  }
  return { values, other }
}

// ---- the body ----------------------------------------------------------------------

const SECTION = { context: '맥락', options: '선택지', comments: '코멘트', answer: '답' } as const
const KNOWN_SECTIONS: readonly string[] = Object.values(SECTION)
const RECOMMEND = '권장'
const INDENT = '  '

/** Lines under a list item: each indented, blank lines left blank. */
const indented = (text: string): string[] => text.split('\n').map(l => (l.trim() === '' ? '' : `${INDENT}${l}`))

/**
 * The item's own lines below its first: indented ones, blank ones while an
 * indented line follows; returns them dedented and where the item ends.
 */
const continuation = (lines: readonly string[], from: number): { text: string[]; end: number } => {
  const text: string[] = []
  let i = from
  while (i < lines.length) {
    const line = lines[i] ?? ''
    if (line.startsWith(INDENT) && line.trim() !== '') {
      text.push(line.slice(INDENT.length))
      i += 1
      continue
    }
    if (line.trim() === '') {
      let j = i
      while (j < lines.length && (lines[j] ?? '').trim() === '') j += 1
      if (j < lines.length && (lines[j] ?? '').startsWith(INDENT)) {
        for (let k = i; k < j; k += 1) text.push('')
        i = j
        continue
      }
    }
    break
  }
  return { text, end: i }
}

const trimBlank = (lines: readonly string[]): string => {
  let a = 0
  let b = lines.length
  while (a < b && (lines[a] ?? '').trim() === '') a += 1
  while (b > a && (lines[b - 1] ?? '').trim() === '') b -= 1
  return lines.slice(a, b).join('\n')
}

type Section = { name: string; heading: string; lines: string[] }

/**
 * The body cut at its `## ` headings outside code fences. Inside 맥락, only a
 * heading of the desk's own ends it, so a context's own headings stay in it.
 */
const sections = (lines: readonly string[]): { lead: string[]; list: Section[] } => {
  const lead: string[] = []
  const list: Section[] = []
  let fence: string | undefined
  for (const line of lines) {
    const opens = /^\s*(```+|~~~+)/.exec(line)?.[1]
    if (opens) {
      if (!fence) fence = opens
      else if (line.trim().startsWith(fence)) fence = undefined
    }
    const heading = !fence && !opens ? /^##\s+(.*?)\s*$/.exec(line)?.[1] : undefined
    const current = list[list.length - 1]
    const isBreak = heading !== undefined && (current?.name !== SECTION.context || KNOWN_SECTIONS.includes(heading))
    if (isBreak && heading !== undefined) list.push({ name: heading, heading: line, lines: [] })
    else if (current) current.lines.push(line)
    else lead.push(line)
  }
  return { lead, list }
}

const optionsText = (d: DeskDecision): string[] => {
  const out: string[] = []
  for (const o of d.options) {
    out.push(`- ${o.key}) ${oneLine(o.label)}`)
    if (o.why) out.push(...indented(o.why))
  }
  if (d.recommended !== undefined || d.recommendedWhy !== undefined) {
    const label = d.recommended !== undefined ? d.options.find(o => o.key === d.recommended)?.label : undefined
    const what = d.recommended !== undefined ? ` ${d.recommended})${label ? ` ${oneLine(label)}` : ''}` : ''
    out.push('', `**${RECOMMEND}${what}**`)
    if (d.recommendedWhy) out.push(d.recommendedWhy)
  }
  return out
}

const readOptions = (lines: readonly string[]): { options: DeskOption[]; recommended?: string; why?: string } => {
  const options: DeskOption[] = []
  let recommended: string | undefined
  let why: string | undefined
  let i = 0
  while (i < lines.length) {
    const line = lines[i] ?? ''
    const item = /^- (.+?)\) (.*)$/.exec(line) ?? /^- (.+?)\)$/.exec(line)
    if (item && item[1]) {
      const rest = continuation(lines, i + 1)
      const text = rest.text.join('\n')
      options.push({ key: item[1], label: item[2] ?? '', ...(text.trim() ? { why: text } : {}) })
      i = rest.end
      continue
    }
    const said = new RegExp(`^\\*\\*${RECOMMEND}(?: (.+?)\\))?(?: .*)?\\*\\*\\s*$`).exec(line)
    if (said) {
      recommended = said[1]
      const reason = trimBlank(lines.slice(i + 1))
      if (reason) why = reason
      break
    }
    i += 1
  }
  return { options, recommended, why }
}

const commentsText = (comments: readonly DeskComment[]): string[] =>
  comments.flatMap(c => {
    const [first = '', ...rest] = c.text.split('\n')
    return [`- ${isoTime(c.at)} ${c.by}: ${first}`.trimEnd(), ...(rest.length > 0 ? indented(rest.join('\n')) : [])]
  })

const readComments = (lines: readonly string[]): DeskComment[] => {
  const out: DeskComment[] = []
  let i = 0
  while (i < lines.length) {
    const m = /^- (\S+) (user|agent):(?: (.*))?$/.exec(lines[i] ?? '')
    const at = timeOf(m?.[1])
    if (!m || at === undefined) {
      i += 1
      continue
    }
    const rest = continuation(lines, i + 1)
    const text = [m[3] ?? '', ...rest.text].join('\n')
    out.push({ id: `c${out.length + 1}`, by: m[2] as DeskComment['by'], text, at, sent: true })
    i = rest.end
  }
  return out
}

// ---- a decision ---------------------------------------------------------------------

/** The answer in a few words: the option it names, else its own words cut short. */
export const answerWords = (d: DeskDecision): string => {
  const option = optionOf(d, d.answer ?? '')
  return option ? `${option.key}) ${oneLine(option.label)}` : cut(oneLine(d.answer ?? ''), 80)
}

const statusOf = (d: DeskDecision): string =>
  d.status === 'answered'
    ? `archived; answered ${answerWords(d)}`
    : d.status === 'deferred'
      ? 'active; on hold until reopened on the desk'
      : 'active'

// The question, then where it stands: the answer, else the recommendation,
// else that it waits (and the options), so the line never just repeats the title.
const descriptionOf = (d: DeskDecision): string => {
  if (d.status === 'answered') return cut(`${d.question} 답 ${answerWords(d)}`, DESCRIPTION_MAX)
  const label = d.recommended !== undefined ? d.options.find(o => o.key === d.recommended)?.label : undefined
  const options = d.options.map(o => `${o.key}) ${oneLine(o.label)}`).join(', ')
  const stands =
    d.recommended !== undefined
      ? `권장 ${d.recommended}${label ? `) ${oneLine(label)}` : ''}`
      : `${d.status === 'deferred' ? '미룸' : '답 기다림'}${options ? `: ${options}` : ''}`
  return cut(`${d.question} ${stands}`, DESCRIPTION_MAX)
}

/** The decision's file: frontmatter, title, then 맥락, 선택지, 코멘트, other sections, 답. */
export const decisionText = (d: DeskDecision): string => {
  const head: [string, string | undefined][] = [
    ['format', '1'],
    ['title', d.question],
    ['description', descriptionOf(d)],
    ['status', statusOf(d)],
    ['id', d.id],
    ['urgency', d.urgency],
    ['blocks', d.blocks],
    ['recommended', d.recommended],
    ['created', isoTime(d.createdAt)],
    ['answered', d.status === 'answered' && d.answeredAt !== undefined ? isoTime(d.answeredAt) : undefined],
    ['answer', d.status === 'answered' ? cut(oneLine(d.answer ?? ''), DESCRIPTION_MAX) : undefined],
  ]
  const front = head.filter((kv): kv is [string, string] => kv[1] !== undefined).map(([k, v]) => `${k}: ${k === 'format' ? v : yamlValue(v)}`)
  const sent = (d.comments ?? []).filter(c => c.sent)
  const context = d.context ? trimBlank(d.context.split('\n')) : ''
  const parts: string[][] = [
    ['---', ...front, ...(d.kept?.head ?? []), '---'],
    [`# ${d.id}. ${d.question}`],
    d.kept?.lead ? [d.kept.lead] : [],
    context.trim() ? [`## ${SECTION.context}`, '', context] : [],
    d.options.length > 0 || d.recommended !== undefined || d.recommendedWhy ? [`## ${SECTION.options}`, '', ...optionsText(d)] : [],
    sent.length > 0 ? [`## ${SECTION.comments}`, '', ...commentsText(sent)] : [],
    ...(d.kept?.sections ?? []).map(s => [s]),
    d.status === 'answered' ? [`## ${SECTION.answer}`, '', d.answer ?? ''] : [],
  ]
  return `${parts
    .filter(p => p.length > 0)
    .map(p => p.join('\n'))
    .join('\n\n')
    .trimEnd()}\n`
}

/** The frontmatter's lines and the body's, or undefined when the text has no frontmatter. */
const splitFront = (text: string): { front: string[]; body: string[] } | undefined => {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  if (lines[0]?.trim() !== '---') return undefined
  const end = lines.indexOf('---', 1)
  if (end < 0) return undefined
  return { front: lines.slice(1, end), body: lines.slice(end + 1) }
}

const ID = /^[DQ](\d+)\b/i

/**
 * A decision read from its file at `file`; undefined when it is not one of
 * the desk's (no id in its frontmatter or its name).
 */
export const parseDecision = (text: string, file: string): DeskDecision | undefined => {
  const split = splitFront(text)
  if (!split) return undefined
  const { values, other } = readFront(split.front)
  const number = ID.exec(values.get('id') ?? '')?.[1] ?? ID.exec(file.split('/').pop() ?? '')?.[1]
  if (!number) return undefined
  const { lead, list } = sections(split.body)
  const title = lead.findIndex(l => /^#\s/.test(l))
  const leadText = trimBlank(title >= 0 ? lead.slice(title + 1) : lead)
  const named = (name: string) => list.find(s => s.name === name)
  const context = trimBlank(named(SECTION.context)?.lines ?? [])
  const opts = readOptions(named(SECTION.options)?.lines ?? [])
  const status = values.get('status') ?? 'active'
  const state = /^\s*(\w+)/.exec(status)?.[1]?.toLowerCase() ?? 'active'
  const answerSection = named(SECTION.answer)
  const isAnswered = state !== 'active'
  const urgency = values.get('urgency')
  const recommended = values.get('recommended') || opts.recommended
  const kept: DeskKept = {
    ...(other.length > 0 ? { head: other } : {}),
    ...(leadText ? { lead: leadText } : {}),
  }
  const others = list.filter(s => !KNOWN_SECTIONS.includes(s.name)).map(s => trimBlank([s.heading, ...s.lines]))
  if (others.length > 0) kept.sections = others
  const comments = readComments(named(SECTION.comments)?.lines ?? [])
  const answered = timeOf(values.get('answered'))
  const question = values.get('title') || (title >= 0 ? (lead[title] ?? '').replace(/^#\s+(?:Q\d+\.\s*)?/, '') : '') || `Q${number}`
  return {
    id: `Q${number}`,
    question: oneLine(question),
    ...(context ? { context } : {}),
    options: opts.options,
    ...(recommended ? { recommended } : {}),
    ...(opts.why ? { recommendedWhy: opts.why } : {}),
    ...(isUrgency(urgency) ? { urgency } : {}),
    ...(values.get('blocks') ? { blocks: values.get('blocks') } : {}),
    status: isAnswered ? 'answered' : /on hold/i.test(status) ? 'deferred' : 'open',
    ...(isAnswered ? { answer: answerSection ? trimBlank(answerSection.lines) : (values.get('answer') ?? '') } : {}),
    ...(comments.length > 0 ? { comments } : {}),
    createdAt: timeOf(values.get('created')) ?? 0,
    ...(isAnswered && answered !== undefined ? { answeredAt: answered } : {}),
    file,
    ...(Object.keys(kept).length > 0 ? { kept } : {}),
  }
}

// ---- the plan ---------------------------------------------------------------------------

const STEP_BOX: Record<DeskStepState, string> = { todo: ' ', doing: '~', done: 'x' }
const PLAN_TITLE = '지금 계획'

const planDescription = (plan: readonly DeskStep[]): string => {
  if (plan.length === 0) return '책상의 지금 계획: 단계 없음'
  const done = plan.filter(s => s.state === 'done').length
  const now = plan.find(s => s.state === 'doing') ?? plan.find(s => s.state === 'todo')
  const where = now ? `, ${now.state === 'doing' ? '하는 중' : '다음'} ${now.id} ${now.text}` : ''
  return cut(`책상의 지금 계획 ${plan.length}단계(끝 ${done})${where}`, DESCRIPTION_MAX)
}

/** The plan's file: a task list, `[~]` for the step under way, each step's detail on the line below it. */
export const planText = (plan: readonly DeskStep[]): string => {
  const front = ['---', 'format: 1', `title: ${PLAN_TITLE}`, `description: ${yamlValue(planDescription(plan))}`, 'status: active', '---']
  const items = plan.flatMap(s => [`- [${STEP_BOX[s.state]}] ${s.id} ${oneLine(s.text)}`, ...(s.detail ? indented(oneLine(s.detail)) : [])])
  return `${[front.join('\n'), `# ${PLAN_TITLE}`, ...(items.length > 0 ? [items.join('\n')] : [])].join('\n\n')}\n`
}

export const parsePlan = (text: string): DeskStep[] => {
  const lines = (splitFront(text)?.body ?? text.replace(/\r\n/g, '\n').split('\n'))
  const out: DeskStep[] = []
  let i = 0
  while (i < lines.length) {
    const m = /^[-*] \[([ ~xX>])\] (?:(S\d+) )?(.*)$/.exec(lines[i] ?? '')
    if (!m) {
      i += 1
      continue
    }
    const rest = continuation(lines, i + 1)
    const box = m[1] ?? ' '
    const state: DeskStepState = box === ' ' ? 'todo' : box === 'x' || box === 'X' ? 'done' : 'doing'
    const detail = oneLine(rest.text.join(' '))
    out.push({ id: m[2] ?? `S${out.length + 1}`, text: oneLine(m[3] ?? ''), state, ...(detail ? { detail } : {}) })
    i = rest.end
  }
  return out
}
