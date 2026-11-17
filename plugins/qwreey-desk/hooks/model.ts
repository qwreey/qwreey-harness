// The desk's data and every change to it, as plain functions over DeskData:
// the hooks in register.tsx read, apply one of these, and write back.

import type {
  DeskComment,
  DeskCommentBy,
  DeskData,
  DeskDecision,
  DeskLogEntry,
  DeskLogKind,
  DeskMarks,
  DeskOption,
  DeskRun,
  DeskRunStatus,
  DeskStep,
  DeskStepState,
  DeskTimes,
  DeskUi,
  DeskUrgency,
} from '../types'

// Bump when a value of the old shape would be misread by the new code: one
// under another tag is read as empty, unless a migration reads it. desk-2
// keeps the pane's state only (decisions and the plan are files); a desk-1
// value, the whole desk, is read once into files (`fromV1`), and a memo of
// the older layout into its thread.
export const SHAPE = 'desk-2'
export const SHAPE_V1 = 'desk-1'

// The work log keeps its newest entries; older ones drop off the store.
export const LOG_KEEP = 500
const RUN_KEEP = 30

export const emptyData = (): DeskData => ({
  decisions: [],
  plan: [],
  running: [],
  log: [],
  lastSeen: 0,
  nextDecision: 1,
})

const logged = (data: DeskData, at: number, kind: DeskLogKind, text: string): DeskData => ({
  ...data,
  log: [...data.log, { at, kind, text }].slice(-LOG_KEEP),
})

const LOG_KINDS: readonly DeskLogKind[] = ['done', 'agent', 'decision', 'note']

/** A log as the feed reads it: well-formed entries in time order (ties as they were), the newest LOG_KEEP. */
const tidyLog = (log: readonly unknown[]): DeskLogEntry[] =>
  log
    .filter(
      (l): l is DeskLogEntry =>
        !!l && typeof l === 'object' && typeof (l as DeskLogEntry).at === 'number' && typeof (l as DeskLogEntry).text === 'string' && LOG_KINDS.includes((l as DeskLogEntry).kind),
    )
    .map((l, i) => ({ l, i }))
    .sort((a, b) => a.l.at - b.l.at || a.i - b.i)
    .map(({ l }) => l)
    .slice(-LOG_KEEP)

/**
 * A decision's id as the desk writes it: `Q12` for `Q12`, `q12`, `12` and
 * `D12`, the older prefix that commits and habits still use.
 */
export const decisionId = (id: string): string => {
  const m = /^[DQ]?(\d+)$/i.exec(id.trim())
  return m ? `Q${Number(m[1])}` : id.trim().toUpperCase()
}

const findDecision = (data: DeskData, id: string): DeskDecision | undefined => {
  const want = decisionId(id)
  return data.decisions.find(d => d.id === want)
}

/** The option an answer names by its first word (`b`, `b) 두 줄`, `b, 이유는`), if any. */
export const optionOf = (d: DeskDecision, answer: string): DeskOption | undefined => {
  const first = answer.trim().split(/[\s,.)]/)[0]?.toLowerCase()
  return first ? d.options.find(o => o.key.toLowerCase() === first) : undefined
}

const withDecision = (data: DeskData, id: string, change: (d: DeskDecision) => DeskDecision): DeskData => ({
  ...data,
  decisions: data.decisions.map(d => (d.id === id ? change(d) : d)),
})

export type Outcome = { data: DeskData; text: string }

export type NewDecision = {
  question: string
  context?: string
  options?: DeskOption[]
  recommended?: string
  reason?: string
  urgency?: DeskUrgency
  blocks?: string
}

export const URGENCIES: readonly DeskUrgency[] = ['blocking', 'soon', 'later']
export const URGENCY_WORD: Record<DeskUrgency, string> = { blocking: '막힘', soon: '곧', later: '나중' }
export const urgencyOf = (d: DeskDecision): DeskUrgency => d.urgency ?? 'soon'
export const isUrgency = (v: unknown): v is DeskUrgency => URGENCIES.includes(v as DeskUrgency)

export const addDecision = (data: DeskData, at: number, input: NewDecision): Outcome => {
  const id = `Q${data.nextDecision}`
  const decision: DeskDecision = {
    id,
    question: oneLine(input.question),
    context: input.context,
    options: input.options ?? [],
    recommended: input.recommended,
    recommendedWhy: input.reason,
    ...(input.urgency ? { urgency: input.urgency } : {}),
    ...(input.blocks ? { blocks: oneLine(input.blocks) } : {}),
    status: 'open',
    createdAt: at,
  }
  const next = logged(
    { ...data, decisions: [...data.decisions, decision], nextDecision: data.nextDecision + 1 },
    at,
    'decision',
    `${id} 올림: ${decision.question}`,
  )
  return { data: next, text: `${id} 올림 (대기 ${openDecisions(next).length})` }
}

export const answerDecision = (data: DeskData, at: number, id: string, answer: string): Outcome => {
  const found = findDecision(data, id)
  if (!found) return { data, text: `${id}: 없는 결정` }
  if (found.status === 'answered' && found.answer === answer) return { data, text: `${found.id}: 이미 기록됨` }
  const next = withDecision(data, found.id, ({ pick: _drafted, ...d }) => ({ ...d, status: 'answered', answer, answeredAt: at }))
  return {
    data: logged(next, at, 'decision', `${found.id} 답: ${oneLine(answer)}`),
    text: `${found.id} 답 기록 (대기 ${openDecisions(next).length})`,
  }
}

// ---- a decision's comment thread ------------------------------------------------

const commentNumber = (c: DeskComment) => Number(/\d+/.exec(c.id)?.[0] ?? 0)

const withComment = (d: DeskDecision, by: DeskCommentBy, text: string, at: number, sent: boolean): DeskDecision => ({
  ...d,
  comments: [
    ...(d.comments ?? []),
    { id: `c${Math.max(0, ...(d.comments ?? []).map(commentNumber)) + 1}`, by, text, at, ...(sent ? { sent: true as const } : {}) },
  ],
  ...(by === 'agent' ? { unread: true as const } : {}),
})

/** The person's comments the model has not been sent yet. */
export const unsent = (d: DeskDecision): DeskComment[] => (d.comments ?? []).filter(c => c.by === 'user' && !c.sent)

const migrateDecision = (d: DeskDecision): DeskDecision => {
  if (d.memo === undefined && d.memoAt === undefined && d.memoPending === undefined) return d
  const { memo, memoAt, memoPending, ...rest } = d
  if (!memo?.trim()) return rest
  const first: DeskComment = { id: 'c1', by: 'user', text: memo, at: memoAt ?? d.createdAt, ...(memoPending ? {} : { sent: true as const }) }
  const later = (rest.comments ?? []).map(c => ({ ...c, id: `c${commentNumber(c) + 1}` }))
  return { ...rest, comments: [first, ...later] }
}

/**
 * The desk as the comment thread keeps it: each memo of the older layout
 * becomes its decision's first comment, the person's, still waiting in the
 * outbox if it was. The same value back when there is none.
 */
export const migrate = (data: DeskData): DeskData => {
  const decisions = data.decisions.map(migrateDecision)
  return decisions.every((d, i) => d === data.decisions[i]) ? data : { ...data, decisions }
}

/** Keeps the person's next comment as they type it. */
export const setDraft = (data: DeskData, id: string, text: string, at: number): DeskData =>
  withDecision(data, id, ({ draft: _old, draftAt: _at, ...d }) => (text === '' ? d : { ...d, draft: text, draftAt: at }))

/** Puts the draft on the thread as the person's comment, waiting in the outbox; the box is left for the next. */
export const postComment = (data: DeskData, id: string, text: string, at: number): DeskData =>
  withDecision(data, id, ({ draft: _old, draftAt: _at, ...d }) => (text.trim() ? withComment(d, 'user', text.trimEnd(), at, false) : d))

/** A comment the model or a chat line adds, which the model already has. */
export const addComment = (data: DeskData, at: number, id: string, by: DeskCommentBy, text: string): Outcome => {
  const found = findDecision(data, id)
  if (!found) return { data, text: `${id}: 없는 결정` }
  if (!text.trim()) return { data, text: 'text 가 필요함' }
  const next = withDecision(data, found.id, d => withComment(d, by, text.trim(), at, true))
  const count = (found.comments?.length ?? 0) + 1
  return {
    data: by === 'agent' ? logged(next, at, 'decision', `${found.id} 코멘트: ${oneLine(text)}`) : next,
    text: `${found.id} 코멘트 ${count}`,
  }
}

/** The person opened the decision: its agent comments are read. */
export const markRead = (data: DeskData, id: string): DeskData => withDecision(data, id, ({ unread: _seen, ...d }) => d)

/** Every comment of the person's on the decision is now the model's too. */
export const markSent = (data: DeskData, id: string): DeskData =>
  withDecision(data, id, d =>
    unsent(d).length === 0 ? d : { ...d, comments: (d.comments ?? []).map(c => (c.by === 'user' && !c.sent ? { ...c, sent: true as const } : c)) },
  )

/** What the model is told with the person's comments on a decision, and asked to do. */
export const commentNote = (d: DeskDecision, texts: readonly string[], isAnswered: boolean): string =>
  `${d.id} ("${d.question}") comment from the user: ${texts.map(t => `"${oneLine(t)}"`).join(' ')}.` +
  `${isAnswered ? '' : ' The decision stays open.'} Reply on the desk with the desk action comment (id ${d.id}),` +
  ' and revise_decision if the discussion changed the decision; keep the chat to one line.'

/** What revise_decision may change; a field left out stays. */
export type Revision = Partial<Omit<NewDecision, 'options'>> & { options?: DeskOption[] }

const sameOption = (a: DeskOption, b: DeskOption) => a.label === b.label && (a.why ?? '') === (b.why ?? '')

/**
 * Changes a decision after discussion and says what changed in an agent
 * comment on its thread, so the person sees why it reads differently. A pick
 * whose option is gone is dropped.
 */
export const reviseDecision = (data: DeskData, at: number, id: string, change: Revision, note?: string): Outcome => {
  const found = findDecision(data, id)
  if (!found) return { data, text: `${id}: 없는 결정` }
  const said: string[] = []
  let d: DeskDecision = found
  const question = change.question ? oneLine(change.question) : undefined
  if (question && question !== d.question) {
    d = { ...d, question }
    said.push('질문 고침')
  }
  if (change.context !== undefined && change.context !== d.context) {
    d = { ...d, context: change.context }
    said.push('배경 고침')
  }
  if (change.options) {
    const after = change.options
    const keys = (list: readonly DeskOption[]) => list.map(o => o.key).join(', ')
    const added = after.filter(o => !d.options.some(b => b.key === o.key))
    const removed = d.options.filter(b => !after.some(o => o.key === b.key))
    const edited = after.filter(o => d.options.some(b => b.key === o.key && !sameOption(b, o)))
    if (added.length > 0) said.push(`선택지 ${keys(added)} 추가`)
    if (removed.length > 0) said.push(`선택지 ${keys(removed)} 뺌`)
    if (edited.length > 0) said.push(`선택지 ${keys(edited)} 고침`)
    const { pick, ...rest } = d
    d = { ...rest, options: after, ...(pick && after.some(o => o.key === pick) ? { pick } : {}) }
  }
  if (change.recommended !== undefined && change.recommended !== d.recommended) {
    said.push(`권장 ${d.recommended ?? '없음'} → ${change.recommended}`)
    d = { ...d, recommended: change.recommended }
  }
  if (change.reason !== undefined && change.reason !== d.recommendedWhy) {
    said.push('권장 이유 고침')
    d = { ...d, recommendedWhy: change.reason }
  }
  if (change.urgency && change.urgency !== urgencyOf(d)) {
    said.push(`${URGENCY_WORD[urgencyOf(d)]} → ${URGENCY_WORD[change.urgency]}`)
    d = { ...d, urgency: change.urgency }
  }
  const blocks = change.blocks ? oneLine(change.blocks) : undefined
  if (blocks && blocks !== d.blocks) {
    said.push('기다리는 것 고침')
    d = { ...d, blocks }
  }
  const extra = note?.trim()
  if (said.length === 0 && !extra) return { data, text: `${found.id}: 바뀐 것 없음` }
  const what = said.join(', ')
  const text = [said.length > 0 ? `결정을 다듬음: ${what}` : '', extra ?? ''].filter(Boolean).join('\n')
  const next = withDecision(data, found.id, () => withComment(d, 'agent', text, at, true))
  return {
    data: logged(next, at, 'decision', `${found.id} 다듬음${what ? `: ${what}` : ''}`),
    text: `${found.id} 다듬음${what ? `: ${what}` : ''}`,
  }
}

// ---- the outbox: picks and comments the person drafts on the desk, sent together

/** Marks (or, with no key, clears) the option the person picked but has not sent. */
export const setPick = (data: DeskData, id: string, key: string | undefined): DeskData =>
  withDecision(data, id, ({ pick: _old, ...d }) => (key ? { ...d, pick: key } : d))

/**
 * Takes a decision out of the outbox: its pick unpicked, its comments not
 * sent yet taken off the thread and put back in the box, before any draft.
 */
export const clearDraft = (data: DeskData, id: string, at: number): DeskData =>
  withDecision(data, id, ({ pick: _old, ...d }) => {
    const back = unsent(d).map(c => c.text)
    if (back.length === 0) return d
    const draft = [...back, d.draft ?? ''].filter(t => t.trim() !== '').join('\n')
    return { ...d, comments: (d.comments ?? []).filter(c => c.by !== 'user' || c.sent), draft, draftAt: at }
  })

/** The remark sent once with the whole outbox, over every decision in it. */
export const setOutboxNote = (data: DeskData, text: string): DeskData => ({ ...data, outboxNote: text })

/** Decisions with a pick or a comment of the person's not sent yet, in the list's order. */
export const drafts = (data: DeskData): DeskDecision[] =>
  data.decisions.filter(d => d.status !== 'answered' && (d.pick !== undefined || unsent(d).length > 0))

const optionLabel = (d: DeskDecision, key: string) => d.options.find(o => o.key === key)?.label

export type Sent = { data: DeskData; prompt: string; note: string }

/**
 * Sends the outbox as one prompt: each pick recorded as the answer, each
 * comment marked sent, the drafts and the overall remark cleared.
 */
export const sendOutbox = (data: DeskData, at: number): Sent | undefined => {
  const list = drafts(data)
  const overall = data.outboxNote?.trim() ?? ''
  if (list.length === 0 && !overall) return undefined
  const lines: string[] = []
  const notes: string[] = []
  for (const d of list) {
    if (d.pick) {
      lines.push(`${d.id} → ${d.pick}`)
      notes.push(`${d.id} ("${d.question}") answered: ${d.pick}) ${optionLabel(d, d.pick) ?? ''}`.trimEnd())
    }
  }
  for (const d of list) {
    const texts = unsent(d).map(c => c.text.trim())
    for (const text of texts) lines.push(`${d.id} 코멘트: ${text}`)
    if (texts.length > 0) notes.push(commentNote(d, texts, d.pick !== undefined))
  }
  if (overall) lines.push(`전체 메모: ${overall}`)
  let out: DeskData = data
  for (const d of list) {
    out = markSent(out, d.id)
    if (d.pick) out = answerDecision(out, at, d.id, d.pick).data
  }
  const { outboxNote: _cleared, ...rest } = out
  const note =
    `[desk] Sent from the desk's outbox, already recorded; do not call answer_decision for these.\n${notes.join('\n')}`.trimEnd()
  return { data: rest, prompt: lines.join('\n'), note }
}

/** Changes how much waits on a decision, and what, when `blocks` is given. */
export const setUrgency = (data: DeskData, id: string, urgency: DeskUrgency, blocks?: string): Outcome => {
  const found = findDecision(data, id)
  if (!found) return { data, text: `${id}: 없는 결정` }
  const next = withDecision(data, found.id, d => ({ ...d, urgency, ...(blocks ? { blocks: oneLine(blocks) } : {}) }))
  return { data: next, text: `${found.id} ${URGENCY_WORD[urgency]}` }
}

export const deferDecision = (data: DeskData, at: number, id: string): Outcome => {
  const found = findDecision(data, id)
  if (!found) return { data, text: `${id}: 없는 결정` }
  const next = withDecision(data, found.id, d => ({ ...d, status: 'deferred' }))
  return { data: logged(next, at, 'decision', `${found.id} 미룸`), text: `${found.id} 미룸` }
}

export type NewStep = { text: string; detail?: string; state?: DeskStepState }

/**
 * Replaces the plan. A step given no state keeps the one an old step of the
 * same id and title had, so sending the plan again (to add details) does not
 * undo the progress.
 */
export const setPlan = (data: DeskData, steps: readonly (string | NewStep)[]): Outcome => {
  const plan: DeskStep[] = steps.map((s, i) => {
    const input = typeof s === 'string' ? { text: s } : s
    const id = `S${i + 1}`
    const text = oneLine(input.text)
    const old = data.plan.find(o => o.id === id && o.text === text)
    const detail = input.detail ? oneLine(input.detail) : old?.detail
    return {
      ...(old && !input.state ? { state: old.state, startedAt: old.startedAt, endedAt: old.endedAt } : { state: input.state ?? 'todo' }),
      id,
      text,
      ...(detail ? { detail } : {}),
    }
  })
  return { data: { ...data, plan }, text: `계획 ${plan.length}단계` }
}

export const updateStep = (data: DeskData, at: number, id: string, state: DeskStepState, detail?: string): Outcome => {
  const key = id.trim().toUpperCase()
  const found = data.plan.find(s => s.id === key || s.id === `S${key}`)
  if (!found) return { data, text: `${id}: 없는 단계` }
  const changed = (s: DeskStep): DeskStep => ({
    ...s,
    state,
    ...(detail ? { detail: oneLine(detail) } : {}),
    ...(state === 'doing' && !s.startedAt ? { startedAt: at } : {}),
    ...(state === 'done' ? { endedAt: at, startedAt: s.startedAt ?? at } : {}),
  })
  const next = { ...data, plan: data.plan.map(s => (s.id === found.id ? changed(s) : s)) }
  const out = state === 'done' && found.state !== 'done' ? logged(next, at, 'done', `${found.id} ${found.text}`) : next
  return { data: out, text: `${found.id} ${STEP_WORD[state]}` }
}

// A note is the model's summary of finished work: kept whole, its line breaks too.
const noteText = (text: string) =>
  text
    .split('\n')
    .map(oneLine)
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export const note = (data: DeskData, at: number, text: string): Outcome => ({
  data: logged(data, at, 'note', noteText(text)),
  text: '기록함',
})

export const runStarted = (data: DeskData, run: DeskRun): DeskData => {
  const next = { ...data, running: [...data.running.filter(r => r.id !== run.id), run].slice(-RUN_KEEP) }
  // A shell is logged when it ends only: a test run starting is not news.
  const isNew = run.kind === 'agent' && !data.running.some(r => r.id === run.id)
  return isNew ? logged(next, run.startedAt, 'agent', `시작: ${run.label}`) : next
}

/** How long a run took: `40초`, `12분`, `1시간 5분`. */
export const took = (ms: number): string => {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}초`
  const m = Math.round(s / 60)
  return m < 60 ? `${m}분` : `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ''}`
}

export const runEnded = (data: DeskData, at: number, id: string, status: DeskRunStatus): DeskData => {
  const run = data.running.find(r => r.id === id)
  if (!run || run.status !== 'running') return data
  const next = { ...data, running: data.running.map(r => (r.id === id ? { ...r, status, endedAt: at } : r)) }
  return logged(next, at, 'agent', `${RUN_WORD[status]} (${took(at - run.startedAt)}): ${run.label}`)
}

/** What a new session finds: runs the last session left running cannot be watched any more. */
export const settleLoaded = (data: DeskData): DeskData => ({
  ...data,
  running: data.running.map(r => (r.status === 'running' ? { ...r, status: 'lost' } : r)),
})

/** A stored value with any list a hand edit or an older build left out filled in. */
export const normalize = (value: Partial<DeskData>): DeskData =>
  migrate({
    ...emptyData(),
    ...value,
    decisions: Array.isArray(value.decisions) ? value.decisions : [],
    plan: Array.isArray(value.plan) ? value.plan : [],
    running: Array.isArray(value.running) ? value.running : [],
    log: Array.isArray(value.log) ? tidyLog(value.log) : [],
  })

/**
 * The stored desk with what this process gathered before it was read (a run
 * that started, an entry logged): hooks can fire before the store is read.
 */
export const mergeLoaded = (stored: DeskData, held: DeskData): DeskData => ({
  ...stored,
  running: [...stored.running, ...held.running.filter(r => !stored.running.some(s => s.id === r.id))].slice(-RUN_KEEP),
  log: tidyLog([...stored.log, ...held.log]),
})

export const openDecisions = (data: DeskData): DeskDecision[] => data.decisions.filter(d => d.status === 'open')
export const runningNow = (data: DeskData): DeskRun[] => data.running.filter(r => r.status === 'running')
export const currentStep = (data: DeskData): DeskStep | undefined =>
  data.plan.find(s => s.state === 'doing') ?? data.plan.find(s => s.state === 'todo')
export const logSince = (data: DeskData, since: number): DeskLogEntry[] => data.log.filter(l => l.at > since)

export const STEP_WORD: Record<DeskStepState, string> = { todo: '할 일', doing: '하는 중', done: '끝' }
export const RUN_WORD: Record<DeskRunStatus, string> = {
  running: '도는 중',
  done: '끝남',
  failed: '실패',
  stopped: '멈춤',
  lost: '끊김',
}

export const oneLine = (text: string): string => text.replace(/\s+/g, ' ').trim()

export const ago = (now: number, at: number): string => {
  const s = Math.max(0, Math.round((now - at) / 1000))
  if (s < 60) return '방금'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}분`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}시간`
  return `${Math.round(h / 24)}일`
}

// A chat line that answers or comments on a decision: `Q3: b`, `Q3 -> b` (or
// the arrow glyph the desk's buttons send), `Q3 = b`, or `Q3 코멘트: ...`
// (`메모` too, its older word); `D3` is the same decision. Only whole lines
// that start so count, so a sentence that merely names Q3 is left to the model.
const LINE = /^\s*([DQ]\d+)\s*(코멘트|comment|메모|memo)?\s*(?::|→|->|=)\s*(.+?)\s*$/i

export type ChatMark = { id: string; kind: 'answer' | 'comment'; text: string }

export const parseChat = (text: string): ChatMark[] =>
  text.split('\n').flatMap(line => {
    const m = LINE.exec(line)
    if (!m || !m[1] || !m[3]) return []
    return [{ id: decisionId(m[1]), kind: m[2] ? 'comment' : 'answer', text: m[3] } as ChatMark]
  })

/** Applies what parseChat found; returns the data and one line per mark for the model. */
export const applyChat = (data: DeskData, at: number, marks: readonly ChatMark[]): { data: DeskData; lines: string[] } => {
  let out = data
  const lines: string[] = []
  for (const mark of marks) {
    const found = findDecision(out, mark.id)
    if (!found) continue
    if (mark.kind === 'comment') {
      out = addComment(out, at, found.id, 'user', mark.text).data
      lines.push(`On the desk's thread: ${commentNote(found, [mark.text], found.status === 'answered')}`)
      continue
    }
    const option = optionOf(found, mark.text)
    out = answerDecision(out, at, found.id, mark.text).data
    lines.push(
      `${found.id} ("${found.question}") answered on the desk: "${mark.text}"` +
        (option ? ` = option ${option.key}) ${option.label}` : '') +
        '. Already recorded; do not call answer_decision for it.',
    )
  }
  return { data: out, lines }
}

/** The band's lines at `columns` cells; empty when there is nothing to show. */
export const bandLines = (data: DeskData): { counts: string; next?: string } | undefined => {
  const open = openDecisions(data).length
  const runs = runningNow(data).length
  const step = currentStep(data)
  if (open === 0 && runs === 0 && !step) return undefined
  const blocking = openDecisions(data).filter(d => urgencyOf(d) === 'blocking').length
  const parts = [open > 0 ? `결정 ${open}${blocking > 0 ? ` (막힘 ${blocking})` : ''}` : '', runs > 0 ? `실행 ${runs}` : ''].filter(Boolean)
  const counts = parts.length > 0 ? parts.join(' · ') : '책상'
  const next = step ? `${step.state === 'doing' ? '지금' : '다음'}: ${step.text}` : undefined
  return { counts, next }
}

// ---- the desk tool's row in the transcript -------------------------------------

const field = (input: unknown, name: string): string => {
  const v = input && typeof input === 'object' ? (input as Record<string, unknown>)[name] : undefined
  return typeof v === 'string' ? oneLine(v) : ''
}

/** The text a tool's stored result holds: a string, `{ result }`, or text blocks. */
export const resultText = (output: unknown): string => {
  if (typeof output === 'string') return oneLine(output)
  if (Array.isArray(output))
    return oneLine(output.map(b => (b && typeof b === 'object' && typeof (b as { text?: unknown }).text === 'string' ? (b as { text: string }).text : '')).join(' '))
  if (output && typeof output === 'object') {
    const o = output as { result?: unknown; content?: unknown; text?: unknown }
    return resultText(o.result ?? o.content ?? o.text ?? '')
  }
  return ''
}

/**
 * One line for a desk call: what it did, by its input, the id it was given
 * read off its result once there is one (`D8 올림: ...`, `S5 끝`, `계획 7단계`).
 */
export const toolSummary = (input: unknown, output: unknown, isErrored: boolean): string => {
  const result = resultText(output)
  if (isErrored) return `오류: ${result || field(input, 'action')}`
  const given = field(input, 'id')
  const id = /^S\d+$/i.test(given) ? given.toUpperCase() : given ? decisionId(given) : ''
  const text = field(input, 'text')
  const action = field(input, 'action')
  switch (action) {
    case 'add_decision': {
      const made = /^([DQ]\d+)/.exec(result)?.[1]
      return `${made ?? '결정'} 올림: ${field(input, 'question')}`
    }
    case 'answer_decision':
      return `${id} 답: ${text}`
    case 'defer_decision':
      return `${id} 미룸`
    case 'set_urgency': {
      const urgency = field(input, 'urgency')
      return `${id} ${isUrgency(urgency) ? URGENCY_WORD[urgency] : urgency}`
    }
    case 'memo':
    case 'comment':
      return `${id} 코멘트${text ? `: ${text}` : ''}`
    case 'revise_decision':
      return `${id} 다듬음${/: (.+)$/.exec(result)?.[1] ? `: ${/: (.+)$/.exec(result)?.[1]}` : ''}`
    case 'set_plan': {
      const steps = input && typeof input === 'object' ? (input as { steps?: unknown }).steps : undefined
      return `계획 ${Array.isArray(steps) ? steps.length : 0}단계`
    }
    case 'update_step': {
      const state = field(input, 'state')
      const word = state === 'todo' || state === 'doing' || state === 'done' ? STEP_WORD[state] : STEP_WORD.done
      return `${id} ${word}${text ? `: ${text}` : ''}`
    }
    case 'note':
      return `기록${text ? `: ${text}` : ''}`
    default:
      return result || action || '호출'
  }
}

// ---- what the store keeps (desk-2), and the files joined to it --------------------------

const byNumber = (a: DeskDecision, b: DeskDecision) => Number(/\d+/.exec(a.id)?.[0] ?? 0) - Number(/\d+/.exec(b.id)?.[0] ?? 0)

/** What only the desk keeps of each decision, by id. */
export const marksOf = (data: DeskData): Record<string, DeskMarks> => {
  const out: Record<string, DeskMarks> = {}
  for (const d of data.decisions) {
    const waiting = unsent(d)
    const m: DeskMarks = {
      ...(d.pick !== undefined ? { pick: d.pick } : {}),
      ...(d.draft !== undefined ? { draft: d.draft } : {}),
      ...(d.draftAt !== undefined ? { draftAt: d.draftAt } : {}),
      ...(d.unread ? { unread: true as const } : {}),
      ...(waiting.length > 0 ? { unsent: waiting } : {}),
    }
    if (Object.keys(m).length > 0) out[d.id] = m
  }
  return out
}

/** When each step started and ended, by id. */
export const timesOf = (data: DeskData): Record<string, DeskTimes> => {
  const out: Record<string, DeskTimes> = {}
  for (const s of data.plan) {
    if (s.startedAt !== undefined || s.endedAt !== undefined)
      out[s.id] = { text: s.text, ...(s.startedAt !== undefined ? { startedAt: s.startedAt } : {}), ...(s.endedAt !== undefined ? { endedAt: s.endedAt } : {}) }
  }
  return out
}

/** The store's value for the desk: with files, the pane's state only; without, the decisions and the plan too. */
export const toUi = (data: DeskData, hasFiles: boolean): DeskUi => ({
  running: data.running,
  log: data.log,
  lastSeen: data.lastSeen,
  nextDecision: data.nextDecision,
  ...(data.outboxNote !== undefined ? { outboxNote: data.outboxNote } : {}),
  marks: hasFiles ? marksOf(data) : {},
  times: hasFiles ? timesOf(data) : {},
  ...(hasFiles ? {} : { decisions: data.decisions.map(({ file: _f, kept: _k, ...d }) => d), plan: data.plan }),
})

/** The desk a desk-2 value holds: its decisions and plan only where it kept them itself. */
export const fromUi = (ui: Partial<DeskUi>): DeskData =>
  normalize({
    running: ui.running,
    log: ui.log,
    lastSeen: typeof ui.lastSeen === 'number' ? ui.lastSeen : 0,
    nextDecision: typeof ui.nextDecision === 'number' ? ui.nextDecision : 1,
    ...(ui.outboxNote !== undefined ? { outboxNote: ui.outboxNote } : {}),
    decisions: ui.decisions,
    plan: ui.plan,
  })

/** A desk-1 value under the Q names: each decision's id, and the log's entries about one. */
export const fromV1 = (data: DeskData): DeskData => ({
  ...data,
  decisions: data.decisions.map(d => ({ ...d, id: decisionId(d.id) })),
  log: data.log.map(l => (l.kind === 'decision' && /^D\d+ /.test(l.text) ? { ...l, text: `Q${l.text.slice(1)}` } : l)),
})

/**
 * The desk with its decisions and plan as the files hold them, each
 * decision's marks and each step's times laid back on: the files win over
 * what the session had, which another session or a git pull may have changed.
 */
export const withFiles = (
  base: DeskData,
  marks: Readonly<Record<string, DeskMarks>>,
  times: Readonly<Record<string, DeskTimes>>,
  files: readonly DeskDecision[],
  plan: readonly DeskStep[],
): DeskData => {
  const decisions = [...files].sort(byNumber).map(f => {
    const m = marks[f.id]
    if (!m) return f
    const said = f.comments ?? []
    const waiting = (m.unsent ?? []).map(({ sent: _s, ...c }, i) => ({ ...c, id: `c${said.length + i + 1}` }))
    return {
      ...f,
      ...(m.pick !== undefined && f.status !== 'answered' ? { pick: m.pick } : {}),
      ...(m.draft !== undefined ? { draft: m.draft } : {}),
      ...(m.draftAt !== undefined ? { draftAt: m.draftAt } : {}),
      ...(m.unread ? { unread: true as const } : {}),
      ...(waiting.length > 0 ? { comments: [...said, ...waiting] } : {}),
    }
  })
  const steps = plan.map(s => {
    const t = times[s.id]
    return t && t.text === s.text ? { ...s, ...(t.startedAt !== undefined ? { startedAt: t.startedAt } : {}), ...(t.endedAt !== undefined ? { endedAt: t.endedAt } : {}) } : s
  })
  const top = Math.max(0, ...decisions.map(d => Number(/\d+/.exec(d.id)?.[0] ?? 0)))
  return { ...base, decisions, plan: steps, nextDecision: Math.max(base.nextDecision, top + 1) }
}
