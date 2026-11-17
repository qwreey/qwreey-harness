import { expect, test } from 'claude-code/testing'

import type { DeskDecision } from '../types'
import { DONE_DIR, OPEN_DIR, PLAN_FILE, PLAN_README, decisionText, parseDecision, parsePlan, planText } from '../hooks/records'
import { NO_GIT } from '../hooks/files'
import { STORE_KEY, desk, engine, repo, start } from './kit'

const BAND = {
  plugin: 'qwreey-desk',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 8, bodyColumns: 40, scroll: { offset: 0, bodyRows: 8 }, view: {} },
  viewport: { columns: 45, rows: 80, isFullscreen: false },
} as const

const PANE = {
  plugin: 'qwreey-desk',
  component: 'Pane',
  requestId: 'desk',
  props: { title: '책상', isFocused: true, bodyColumns: 43, placement: 'inline', scroll: { offset: 0, bodyRows: 40 }, view: {} },
  viewport: { columns: 45, rows: 80, isFullscreen: false },
} as const

const ask = (question: string, extra: Record<string, unknown> = {}) =>
  desk({
    action: 'add_decision',
    question,
    context: '폰 화면 **45칸**에서 본다.',
    options: [
      { key: 'a', label: '한 줄', why: '공간 아낌' },
      { key: 'b', label: '두 줄', why: '다음 단계가 보임' },
    ],
    recommended: 'b',
    reason: '다음 할 일이 늘 보여야 함',
    ...extra,
  })


// ---- the file format ----------------------------------------------------------------

const FULL: DeskDecision = {
  id: 'Q12',
  question: '밴드는 몇 줄까지? (폰: 45칸)',
  context: [
    '폰 화면 **45칸**에서 본다.',
    '',
    '## 맥락 안의 제목',
    '- 한 줄: 공간',
    '',
    '```md',
    '## 선택지',
    '```',
    '  들여 쓴 줄',
  ].join('\n'),
  options: [
    { key: 'a', label: '한 줄: 짧게', why: '공간 아낌\n\n둘째 문단' },
    { key: 'b', label: '두 줄' },
    { key: 'c', label: '"따옴표" # 와 함께', why: '- 목록처럼 보이는 이유' },
  ],
  recommended: 'b',
  recommendedWhy: '다음 할 일이 늘 보여야 함\n- 근거 하나',
  urgency: 'blocking',
  blocks: 'S3: 밴드 구현',
  status: 'open',
  comments: [
    { id: 'c1', by: 'user', text: '좁으면 한 줄\n\n그래도 두 줄?', at: 1_794_000_000_123, sent: true },
    { id: 'c2', by: 'agent', text: '두 번째 줄은 다음 단계', at: 1_794_000_060_000, sent: true },
  ],
  createdAt: 1_793_999_000_000,
  file: `${OPEN_DIR}/Q12-밴드는-몇-줄까지-폰-45칸.md`,
}

test('a decision written to its file reads back the same', () => {
  const text = decisionText(FULL)
  expect(parseDecision(text, FULL.file ?? '')).toEqual(FULL)
  // Answered and deferred, with no context, options or comments.
  const answered: DeskDecision = { id: 'Q3', question: '책상 저장은 프로젝트별?', options: [], status: 'answered', answer: '응, 프로젝트별로\n둘째 줄', createdAt: 5, answeredAt: 9, file: `${DONE_DIR}/Q3.md` }
  expect(parseDecision(decisionText(answered), `${DONE_DIR}/Q3.md`)).toEqual(answered)
  const deferred: DeskDecision = { ...FULL, status: 'deferred', comments: undefined }
  const { comments: _none, ...withoutComments } = deferred
  expect(parseDecision(decisionText(deferred), FULL.file ?? '')).toEqual(withoutComments)
  expect(decisionText(parseDecision(text, FULL.file ?? '') as DeskDecision)).toBe(text)
})

test("a decision's file is a record: frontmatter, sections, status by state", () => {
  const text = decisionText(FULL)
  const head = text.split('---')[1] ?? ''
  expect(head).toContain('\nformat: 1\n')
  expect(head).toContain('\ntitle: "밴드는 몇 줄까지? (폰: 45칸)"\n')
  expect(head).toContain('\ndescription: "밴드는 몇 줄까지? (폰: 45칸) 권장 b) 두 줄"\n')
  expect(head).toContain('\nstatus: active\n')
  expect(head).toContain('\nid: Q12\n')
  expect(head).toContain('\nurgency: blocking\n')
  expect(head).toContain('\nblocks: "S3: 밴드 구현"\n')
  expect(text).toContain('\n# Q12. 밴드는 몇 줄까지? (폰: 45칸)\n')
  expect(text.indexOf('## 맥락')).toBeLessThan(text.indexOf('## 선택지\n'))
  expect(text).toContain('\n- a) 한 줄: 짧게\n  공간 아낌\n\n  둘째 문단\n')
  expect(text).toContain('\n**권장 b) 두 줄**\n다음 할 일이 늘 보여야 함\n')
  expect(text).toContain('\n- 2026-11-06T21:20:00.123Z user: 좁으면 한 줄\n\n  그래도 두 줄?\n')
  const answered = decisionText({ ...FULL, status: 'answered', answer: 'a', answeredAt: 1_794_000_100_000 })
  expect(answered).toContain('\nstatus: "archived; answered a) 한 줄: 짧게"\n')
  expect(answered).toContain('\ndescription: "밴드는 몇 줄까지? (폰: 45칸) 답 a) 한 줄: 짧게"\n')
  expect(answered.trimEnd().endsWith('## 답\n\na')).toBe(true)
  const words = decisionText({ ...FULL, status: 'answered', answer: '실측부터 진행해줘' })
  expect(words).toContain('\nstatus: archived; answered 실측부터 진행해줘\n')
  // With no recommendation the line says the decision waits, never the title alone.
  expect(decisionText({ id: 'Q4', question: '미룰 결정', options: [], status: 'deferred', createdAt: 1 })).toContain('\ndescription: 미룰 결정 미룸\n')
  expect(decisionText({ ...FULL, recommended: undefined, recommendedWhy: undefined })).toContain(' 답 기다림: a) 한 줄: 짧게, b) 두 줄, c) ')
  expect(decisionText({ ...FULL, status: 'deferred' })).toContain('\nstatus: active; on hold until reopened on the desk\n')
  const long = decisionText({ ...FULL, question: '가'.repeat(300) })
  const description = /\ndescription: (.*)\n/.exec(long)?.[1] ?? ''
  expect([...description].length).toBeLessThanOrEqual(200)
})

test('a hand edit keeps what the desk does not know', () => {
  const edited = decisionText(FULL)
    .replace('id: Q12\n', 'id: Q12\nkeywords: [밴드, band]\n')
    .replace('## 코멘트', '## 메모\n\n사람이 덧붙인 줄\n\n## 코멘트')
    .replace('- b) 두 줄\n', '- b) 두 줄 (고침)\n')
  const read = parseDecision(edited, FULL.file ?? '') as DeskDecision
  expect(read.options[1]?.label).toBe('두 줄 (고침)')
  expect(read.kept).toEqual({ head: ['keywords: [밴드, band]'], sections: ['## 메모\n\n사람이 덧붙인 줄'] })
  const again = decisionText(read)
  expect(again).toContain('\nkeywords: [밴드, band]\n')
  expect(again).toContain('\n## 메모\n\n사람이 덧붙인 줄\n')
  expect(parseDecision(again, FULL.file ?? '')).toEqual(read)
  // Not a decision of the desk's: no id anywhere.
  expect(parseDecision('---\ntitle: x\n---\n# x\n', `${OPEN_DIR}/notes.md`)).toBeUndefined()
})

test('the plan file is a task list that reads back', () => {
  const plan = [
    { id: 'S1', text: '타입 쓰기', state: 'done' as const },
    { id: 'S2', text: '밴드 그리기', state: 'doing' as const, detail: '프롬프트 위 두 줄' },
    { id: 'S3', text: '패널 그리기', state: 'todo' as const },
  ]
  const text = planText(plan)
  expect(text).toContain('\n- [x] S1 타입 쓰기\n- [~] S2 밴드 그리기\n  프롬프트 위 두 줄\n- [ ] S3 패널 그리기\n')
  expect(text).toContain('\ndescription: 책상의 지금 계획 3단계(끝 1), 하는 중 S2 밴드 그리기\n')
  expect(parsePlan(text)).toEqual(plan)
})

// ---- the desk on a project folder ----------------------------------------------------

test('a decision goes to a file; answered, it moves to the archive with git', async ($, on) => {
  const { stored, held } = engine(on)
  const files = repo(on)
  await start($)
  const added = await $.tool.call(ask('밴드는 몇 줄까지?'))
  expect(added.result).toBe('Q1 올림 (대기 1)')
  const name = 'Q1-밴드는-몇-줄까지.md'
  expect(files.names(OPEN_DIR)).toEqual([name])
  expect(files.text(PLAN_README)).toContain('that is Q<n> here.')
  const open = files.text(`${OPEN_DIR}/${name}`) ?? ''
  expect(open).toContain('\nstatus: active\n')
  expect(open).toContain('\n## 맥락\n\n폰 화면 **45칸**에서 본다.\n')
  // The store keeps the pane's own state, not the decision.
  expect(stored().decisions).toBeUndefined()
  expect(stored().nextDecision).toBe(2)

  // A comment of the agent's goes into the file; the person's draft does not.
  await $.tool.call(desk({ action: 'comment', id: 'Q1', text: '두 번째 줄은 다음 단계' }))
  expect(files.text(`${OPEN_DIR}/${name}`)).toContain(' agent: 두 번째 줄은 다음 단계\n')

  files.tracked.add(`${OPEN_DIR}/${name}`)
  await $.prompt.submit({ text: 'Q1: b', wait: false, origin: { kind: 'composer' } })
  expect(files.runs).toContainEqual(['git', 'mv', '--', `${OPEN_DIR}/${name}`, `${DONE_DIR}/${name}`])
  expect(files.names(OPEN_DIR)).toEqual([])
  const done = files.text(`${DONE_DIR}/${name}`) ?? ''
  expect(done).toContain('\nstatus: archived; answered b) 두 줄\n')
  expect(done.trimEnd().endsWith('## 답\n\nb')).toBe(true)
  expect(held().decisions[0]).toMatchObject({ id: 'Q1', status: 'answered', file: `${DONE_DIR}/${name}` })
})

test('an untracked decision file moves with mv, and nothing is deleted', async ($, on) => {
  engine(on)
  const files = repo(on)
  await start($)
  await $.tool.call(ask('Untracked file?'))
  await $.tool.call(desk({ action: 'answer_decision', id: 'Q1', text: '그냥 a 로' }))
  expect(files.runs.some(r => r[0] === 'git' && r[1] === 'mv')).toBe(false)
  expect(files.runs).toContainEqual(['mv', '--', `${OPEN_DIR}/Q1-untracked-file.md`, `${DONE_DIR}/Q1-untracked-file.md`])
  expect(files.names(DONE_DIR)).toEqual(['Q1-untracked-file.md'])
  expect(files.text(`${DONE_DIR}/Q1-untracked-file.md`)).toContain('\nstatus: archived; answered 그냥 a 로\n')
  // The desk never commits.
  expect(files.runs.some(r => r[0] === 'git' && (r[1] === 'commit' || r[1] === 'add' || r[1] === 'rm'))).toBe(false)
})

test('the plan is written to now.md on each change', async ($, on) => {
  const { stored } = engine(on)
  const files = repo(on)
  await start($)
  await $.tool.call(desk({ action: 'set_plan', steps: ['타입 쓰기', { text: '밴드 그리기', detail: '프롬프트 위 두 줄' }] }))
  expect(files.text(PLAN_FILE)).toContain('\n- [ ] S1 타입 쓰기\n- [ ] S2 밴드 그리기\n  프롬프트 위 두 줄\n')
  await $.tool.call(desk({ action: 'update_step', id: 'S1', state: 'doing' }))
  expect(files.text(PLAN_FILE)).toContain('\n- [~] S1 타입 쓰기\n')
  await $.tool.call(desk({ action: 'update_step', id: 'S1', state: 'done' }))
  expect(files.text(PLAN_FILE)).toContain('\n- [x] S1 타입 쓰기\n')
  // Times stay in the store, by step.
  expect(stored().times.S1).toMatchObject({ text: '타입 쓰기', startedAt: 1_000_000, endedAt: 1_000_000 })
  expect(stored().plan).toBeUndefined()
  // A draft typed on the desk writes no file.
  const before = files.written.length
  await $.tool.call(desk({ action: 'note', text: '타입 끝' }))
  expect(files.written.length).toBe(before)
})

// The shape of the real desk-1 store: answered and open decisions with
// threads, a memo of the older layout, a pick and a comment waiting in the
// outbox, two steps under way, log entries naming decisions.
const OLD = {
  decisions: [
    {
      id: 'D1',
      question: '스킬 힌트 훅을 luau-kb 팩 스킬부터 넣을까?',
      context: '- 지금: 힌트 없음\n- 제안: 팩 스킬부터',
      options: [
        { key: 'a', label: '넣음', why: '실측 가능' },
        { key: 'b', label: '미룸' },
      ],
      recommended: 'a',
      recommendedWhy: '작게 시작',
      status: 'answered',
      answer: '실질적으로 스킬은 사용자가 지시하지 않더라도 실려야하고 …',
      comments: [{ id: 'c1', by: 'user', text: '먼저 실측', at: 10, sent: true }],
      createdAt: 1,
      answeredAt: 20,
    },
    {
      id: 'D2',
      question: 'comments 를 rule 하나로 두고 스킬은 없앨까?',
      options: [{ key: 'a', label: '예' }, { key: 'b', label: '아니오' }],
      recommended: 'a',
      urgency: 'soon',
      blocks: 'D1 3번(comments 스킬 처리)',
      status: 'open',
      memo: '예전 메모',
      memoAt: 30,
      comments: [{ id: 'c1', by: 'agent', text: '답글', at: 40, sent: true }],
      pick: 'a',
      createdAt: 2,
    },
    { id: 'D3', question: '미뤄 둔 결정', options: [], status: 'deferred', createdAt: 3, comments: [{ id: 'c1', by: 'user', text: '보낼 코멘트', at: 50 }] },
  ],
  plan: [
    { id: 'S1', text: 'PLAN.md 수명별로 나누기', state: 'doing', detail: '옛 PLAN 은 archive' },
    { id: 'S2', text: '패널 결정·계획을 저장소 파일로', state: 'doing', startedAt: 60 },
  ],
  running: [],
  log: [
    { at: 20, kind: 'decision', text: 'D1 답: 실질적으로' },
    { at: 21, kind: 'note', text: 'D1 을 반영함' },
  ],
  lastSeen: 0,
  nextDecision: 4,
}

test('a desk-1 store moves into Q files once, its marks into the store', async ($, on) => {
  const { stored, kept, held } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value: OLD } })
  const files = repo(on)
  await start($)
  expect(files.names(DONE_DIR)).toEqual(['Q1-스킬-힌트-훅을-luau-kb-팩.md'])
  expect(files.names(OPEN_DIR)).toEqual(['Q2-comments-를-rule-하나로-두고-스킬은.md', 'Q3-미뤄-둔-결정.md'])
  const q1 = files.text(`${DONE_DIR}/Q1-스킬-힌트-훅을-luau-kb-팩.md`) ?? ''
  expect(q1).toContain('\nstatus: archived; answered 실질적으로 스킬은 사용자가 지시하지 않더라도 실려야하고 …\n')
  expect(q1).toContain('\n## 맥락\n\n- 지금: 힌트 없음\n- 제안: 팩 스킬부터\n')
  expect(q1).toContain('\n**권장 a) 넣음**\n작게 시작\n')
  expect(q1).toContain(' user: 먼저 실측\n')
  // Text inside a decision stays as written, D names included.
  const q2 = files.text(`${OPEN_DIR}/Q2-comments-를-rule-하나로-두고-스킬은.md`) ?? ''
  expect(q2).toContain('\nblocks: D1 3번(comments 스킬 처리)\n')
  // The older layout's memo, sent then, is the thread's first comment.
  expect(q2).toMatch(/- 1970-01-01T00:00:00\.030Z user: 예전 메모\n- 1970-01-01T00:00:00\.040Z agent: 답글\n/)
  // A comment waiting in the outbox is not in the file but in the store's marks.
  expect(files.text(`${OPEN_DIR}/Q3-미뤄-둔-결정.md`)).not.toContain('보낼 코멘트')
  expect(files.text(`${OPEN_DIR}/Q3-미뤄-둔-결정.md`)).toContain('\nstatus: active; on hold until reopened on the desk\n')
  expect(files.text(PLAN_FILE)).toContain('\n- [~] S1 PLAN.md 수명별로 나누기\n  옛 PLAN 은 archive\n- [~] S2 패널 결정·계획을 저장소 파일로\n')
  expect((kept.get(STORE_KEY) as { shape: string }).shape).toBe('desk-2')
  const ui = stored()
  expect(ui.decisions).toBeUndefined()
  expect(ui.marks).toEqual({ Q2: { pick: 'a' }, Q3: { unsent: [{ id: 'c1', by: 'user', text: '보낼 코멘트', at: 50 }] } })
  expect(ui.times).toEqual({ S2: { text: '패널 결정·계획을 저장소 파일로', startedAt: 60 } })
  expect(ui.log[0].text).toBe('Q1 답: 실질적으로')
  expect(ui.log[1].text).toBe('D1 을 반영함')
  expect(ui.nextDecision).toBe(4)

  // The desk reads back as it was: ids, the pick, the waiting comment, the step's time.
  const d = held()
  expect(d.decisions.map((x: any) => [x.id, x.status, x.pick])).toEqual([
    ['Q1', 'answered', undefined],
    ['Q2', 'open', 'a'],
    ['Q3', 'deferred', undefined],
  ])
  expect(d.decisions[2].comments).toEqual([{ id: 'c1', by: 'user', text: '보낼 코멘트', at: 50 }])
  expect(d.plan[1].startedAt).toBe(60)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await pane.find({ type: 'Button', key: 'outbox' })).toBeDefined()
  await pane.unmount()

  // Opening the desk again reads the files and writes nothing.
  const writes = files.written.length
  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await band.press({ key: 'open' })
  await band.unmount()
  expect(files.written.length).toBe(writes)
  const added = await $.tool.call(desk({ action: 'add_decision', question: '새 질문' }))
  expect(added.result).toBe('Q4 올림 (대기 2)')
})

test('moving a desk-1 store again writes no file a decision already has', async ($, on) => {
  // As if a first move wrote Q1 and stopped before the store was written.
  const q1 = '---\nformat: 1\ntitle: 손으로 고친 제목\ndescription: x\nstatus: "archived; answered a) 넣음"\nid: Q1\ncreated: 1970-01-01T00:00:00.001Z\n---\n# Q1. 손으로 고친 제목\n\n## 답\n\na\n'
  const { held } = engine(on, { [STORE_KEY]: { shape: 'desk-1', value: OLD } })
  const files = repo(on, { files: { [`${DONE_DIR}/Q1-old-name.md`]: q1 } })
  await start($)
  expect(files.names(DONE_DIR)).toEqual(['Q1-old-name.md'])
  expect(files.text(`${DONE_DIR}/Q1-old-name.md`)).toBe(q1)
  expect(files.written.some(p => p.includes('/Q1'))).toBe(false)
  expect(files.names(OPEN_DIR)).toEqual(['Q2-comments-를-rule-하나로-두고-스킬은.md', 'Q3-미뤄-둔-결정.md'])
  expect(held().decisions[0].question).toBe('손으로 고친 제목')
})

test('files changed on disk are what the desk shows next', async ($, on) => {
  const { held } = engine(on)
  const files = repo(on)
  await start($)
  await $.tool.call(ask('밴드는 몇 줄까지?'))
  const name = 'Q1-밴드는-몇-줄까지.md'
  const path = `${OPEN_DIR}/${name}`
  // Another session added a comment and changed the question.
  files.edit(path, (files.text(path) ?? '').replace('title: 밴드는 몇 줄까지?', 'title: 밴드는 기본 몇 줄?').replace('\n## 선택지', '\n## 코멘트\n\n- 2026-11-17T01:00:00Z user: 다른 세션에서\n\n## 선택지'))
  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await band.press({ key: 'open' })
  await band.unmount()
  let d = held()
  expect(d.decisions[0].question).toBe('밴드는 기본 몇 줄?')
  expect(d.decisions[0].comments.map((c: any) => c.text)).toEqual(['다른 세션에서'])

  // A git pull answered it: the file now sits in the archive.
  files.move(path, `${DONE_DIR}/${name}`)
  files.edit(`${DONE_DIR}/${name}`, (files.text(`${DONE_DIR}/${name}`) ?? '').replace('status: active', 'status: archived').concat('\n## 답\n\na\n'))
  // A tool call reads the files first, so it acts on the decision as it now stands.
  const replied = await $.tool.call(desk({ action: 'comment', id: 'Q1', text: '확인' }))
  expect(replied.result).toBe('Q1 코멘트 2')
  d = held()
  expect(d.decisions[0]).toMatchObject({ status: 'answered', answer: 'a', file: `${DONE_DIR}/${name}` })
  expect(files.text(`${DONE_DIR}/${name}`)).toContain(' agent: 확인\n')
  expect(files.names(OPEN_DIR)).toEqual([])
})

test('D names reach the same decisions as Q names, and show as Q', async ($, on) => {
  const { submitted, held } = engine(on)
  repo(on)
  await start($)
  await $.tool.call(ask('첫 질문'))
  await $.tool.call(ask('둘째 질문'))
  const commented = await $.tool.call(desk({ action: 'comment', id: 'D1', text: '옛 이름으로' }))
  expect(commented.result).toBe('Q1 코멘트 1')
  await $.prompt.submit({ text: 'D1: b\nd2 코멘트: 소문자도', wait: false, origin: { kind: 'composer' } })
  const d = held()
  expect(d.decisions[0]).toMatchObject({ id: 'Q1', status: 'answered', answer: 'b' })
  expect(d.decisions[1].comments.at(-1)).toMatchObject({ by: 'user', text: '소문자도' })
  expect(submitted.at(-1)?.context?.[0]).toContain('Q1 ("첫 질문") answered on the desk: "b" = option b) 두 줄')
  await $.prompt.submit({ text: 'D2 더 논의 해 보자', wait: false, origin: { kind: 'composer' } })
  expect(submitted.at(-1)?.context?.at(-1)).toContain('Q2: 둘째 질문')
  const row = await $.ui.mount({
    plugin: 'qwreey-desk',
    component: 'ToolUse',
    requestId: 't1',
    props: { tool_use_id: 't1', tool: 'mcp__qwreey-desk__desk', input: { action: 'set_urgency', id: 'd2', urgency: 'later' }, isRunning: false, isErrored: false, isInterrupted: false },
    viewport: { columns: 45, rows: 80, isFullscreen: false },
    surface: 'terminal',
  })
  expect((await row.find({ type: 'Text' }))?.text).toBe('책상 · Q2 나중')
  await row.unmount()
})

test('outside a git repository the desk stays in the store and the band says so once', async ($, on) => {
  const { stored } = engine(on)
  const files = repo(on, { isGit: false })
  await start($)
  await $.tool.call(ask('밴드는 몇 줄까지?'))
  expect(files.written).toEqual([])
  expect(stored().decisions.map((d: any) => d.id)).toEqual(['Q1'])
  let band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: NO_GIT })).toBeDefined()
  await band.unmount()
  await $.prompt.submit({ text: '알겠어', wait: false, origin: { kind: 'composer' } })
  band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: NO_GIT })).toBeUndefined()
  expect(await band.find({ type: 'Text', text: /결정 1/ })).toBeDefined()
  await band.unmount()
})
